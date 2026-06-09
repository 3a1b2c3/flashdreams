# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

"""Ludus-based HD map rasterizer wrapping ``ludus_renderer`` for conditioning.

When :class:`BevConfig` is enabled it also renders a top-down BEV via a
synthetic ``FThetaCamera`` above the rig (pinhole projection + a fixed
straight-down sensor-to-rig matrix); the BEV rides alongside the main RGB on
each :class:`PresentedFrame`.
"""

import concurrent.futures
import contextlib
import math
import os
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
import torch
from loguru import logger
from ludus_renderer import (
    FThetaCamera,
    load_clipgt_scene,
)
from ludus_renderer.clipgt import ClipgtGpuScene
from ludus_renderer.render_utils import SceneAdapter
from ludus_renderer.torch import LudusCudaTimestampedContext
from ludus_renderer.torch.ops import CAMERA_TYPE_BEV, CAMERA_TYPE_REGULAR
from omnidreams.interactive_drive.config import BevConfig, RasterConfig
from omnidreams.interactive_drive.cuda_env import DISABLE_CUDA_INTEROP_ENV, env_truthy
from omnidreams.interactive_drive.camera import FThetaCameraModel
from omnidreams.interactive_drive.cuda_host_prefetch import CudaHostPrefetch
from omnidreams.interactive_drive.types import PresentedFrame, RasterChunk, SceneBundle
from torch import Tensor

_BEV_CAMERA_NAME = "interactive_drive_bev"

# Distance (m) within which the ego is considered to have "passed over" the
# static first-intersection goal, after which it disappears for good.
_INTERSECTION_REACH_M = 10.0

# Height (m) of the translucent cylinder marker drawn over the main viewport at
# the first-intersection goal (base on the ground, top this far above it).
_INTERSECTION_MARKER_HEIGHT_M = 3.0


def _extract_clipgt_from_usdz(usdz_path: Path, dest_dir: Path) -> Path:
    """Extract clipgt parquet files from USDZ archive.

    Our USDZ bundles contain clipgt/ subdirectory with parquet files.
    This extracts them to a directory compatible with load_clipgt_scene.

    Returns:
        Path to the clipgt directory with extracted parquets.
    """
    clipgt_dir = dest_dir / "clipgt"
    clipgt_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(usdz_path, "r") as zf:
        for name in zf.namelist():
            if not name.startswith("clipgt/") or name.endswith("/"):
                continue
            relative = Path(name).relative_to("clipgt")
            if relative.suffix in {".parquet", ".json"}:
                target_name = f"clipgt.{relative.name}"
            else:
                target_name = relative.name
            (clipgt_dir / target_name).write_bytes(zf.read(name))

    return clipgt_dir


@dataclass
class _LoadedSceneData:
    """Loaded clipgt scene + its adapter."""

    clipgt_scene: ClipgtGpuScene
    scene_adapter: SceneAdapter


@dataclass(frozen=True)
class _RenderedCameraFrames:
    frames_hwc_uint8: Tensor
    ready_event: object | None


class _LazyRasterFrame:
    """Expose a rendered HDMap frame as CUDA first, NumPy only on fallback."""

    def __init__(
        self,
        frames_hwc_uint8: Tensor,
        frame_index: int,
        *,
        source_event: object | None = None,
    ) -> None:
        self._frames_hwc_uint8: Tensor | None = frames_hwc_uint8
        self._frame_index = int(frame_index)
        self._source_event = source_event
        self._host: np.ndarray | None = None
        self._prefetch: CudaHostPrefetch | None = None

    def prefetch_to_numpy(self) -> None:
        if (
            self._host is not None
            or self._prefetch is not None
            or self._frames_hwc_uint8 is None
        ):
            return
        frame = self._frames_hwc_uint8[self._frame_index].detach()
        prefetch = CudaHostPrefetch(frame, source_event=self._source_event)
        if prefetch.start():
            self._prefetch = prefetch

    def to_numpy(self) -> np.ndarray:
        if self._host is None:
            if self._prefetch is not None:
                self._host = self._prefetch.to_numpy()
                self._prefetch = None
                self._frames_hwc_uint8 = None
                return self._host
            if self._frames_hwc_uint8 is None:
                raise RuntimeError(
                    "Lazy raster frame lost its source tensor before materialization."
                )
            synchronize = getattr(self._source_event, "synchronize", None)
            if callable(synchronize):
                synchronize()
            frame = self._frames_hwc_uint8[self._frame_index].detach().cpu().numpy()
            self._host = np.ascontiguousarray(frame, dtype=np.uint8)
            self._frames_hwc_uint8 = None
        return self._host

    def to_cuda_tensor(self) -> Tensor:
        if self._frames_hwc_uint8 is None:
            raise RuntimeError(
                "Lazy raster frame was already materialized on the host."
            )
        return self._frames_hwc_uint8[self._frame_index]

    def to_cuda_event(self) -> object | None:
        if self._frames_hwc_uint8 is None:
            return None
        return self._source_event

    def __array__(
        self,
        dtype: object | None = None,
        copy: bool | None = None,
    ) -> np.ndarray:
        array = self.to_numpy()
        if dtype is not None:
            array = array.astype(dtype, copy=False)
        if copy:
            return np.array(array, copy=True)
        return array


class _LudusConditionRasterizerImpl:
    """Single-threaded implementation backing :class:`LudusConditionRasterizer`.

    Do not construct directly; the public facade thread-pins it to one worker
    (see :class:`LudusConditionRasterizer` for the EGL rationale).
    """

    def __init__(self, raster: RasterConfig, bev: BevConfig | None = None) -> None:
        """Initialize the rasterizer.

        Args:
            raster: Raster configuration specifying resolution and rendering params.
            bev: Optional BEV configuration. When ``enabled``, the rasterizer
                appends a synthetic top-down camera to the scene's camera list
                on :meth:`load_scene` and ``render_chunk`` populates
                :attr:`PresentedFrame.bev_host_uint8`.
        """
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required for LudusConditionRasterizer.")

        self._raster = raster
        self._bev = bev
        self._device = torch.device("cuda:0")
        self._use_cuda_frames = not env_truthy(DISABLE_CUDA_INTEROP_ENV)
        if self._use_cuda_frames:
            logger.info(
                "[rasterizer] cuda_backend=enabled; returning lazy CUDA raster frames",
            )
        else:
            logger.info(
                f"[rasterizer] cuda_backend=disabled by {DISABLE_CUDA_INTEROP_ENV}; "
                "using host raster frames",
            )

        self.ctx = LudusCudaTimestampedContext(device=self._device)
        self.ctx.set_depth_scaling(True)
        self.ctx.set_msaa_samples(4)
        self.ctx.set_max_tessellation_levels(cube=0)
        # Use thinner BEV linework so the small map panel doesn't get
        # swallowed by the heavier polylines designed for the main view.
        bev_line_width = max(2.0, float(raster.line_width_px) * 0.4)
        bev_pole_width = max(2.0, float(raster.pole_width_px) * 0.6)
        self.ctx.set_line_widths(
            polyline_regular=float(raster.line_width_px),
            polyline_bev=bev_line_width,
            ego_traj_regular=float(raster.pole_width_px),
            ego_traj_bev=bev_pole_width,
            wireframe=4.0,
        )

        self._scene_data: _LoadedSceneData | None = None
        self._scene_id: int | None = None
        self._all_cameras: list[FThetaCamera] = []
        self._all_camera_map: dict[str, int] = {}
        self._sensor_to_rig: dict[str, Tensor] = {}
        self._selected_camera_name: str | None = None
        self._bev_camera_id: int | None = None
        self._bev_sensor_to_rig: Tensor | None = None
        # Fixed world (x, y) the BEV target dot is pinned to. Set to the ego's
        # spawn position on the first render after load_scene ("home"), so the
        # dot sits on a real spot and falls behind as you drive away.
        self._bev_target_world: tuple[float, float] | None = None
        # Fixed world (x, y, z) of the static "first intersection" goal, set at
        # load_scene to the intersection-area polygon centroid nearest the
        # spawn. ``None`` when the scene has no intersection data.
        # ``_intersection_target_reached`` latches True once the ego drives over
        # it so the dot disappears permanently for the rest of the rollout.
        self._bev_intersection_target_world: tuple[float, float, float] | None = None
        self._intersection_target_reached: bool = False
        # F-theta projection model for the selected main camera, used to project
        # the intersection goal into the viewport for the cylinder overlay.
        self._main_camera_model: FThetaCameraModel | None = None
        # Only let the goal count as "passed over" after the ego has first been
        # outside the reach radius, so spawning on/near the intersection shows
        # the dot instead of instantly hiding it.
        self._intersection_target_armed: bool = False
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None

    def _to_ludus_camera_pose(self, camera_poses: Tensor) -> Tensor:
        """Convert sensor-to-world camera poses to Ludus' world-to-sensor format."""
        return torch.linalg.inv(camera_poses)

    def load_scene(self, scene: SceneBundle) -> None:
        """Load a scene from the USDZ bundle.

        Args:
            scene: Scene bundle containing path to USDZ and camera selection.
        """
        self.ctx.clear_scenes()
        # Re-pin "home" for the new scene on its first rendered frame.
        self._bev_target_world = None
        # Pin the static goal to the intersection nearest the spawn (or leave it
        # unset if the scene ships no intersection data), and re-arm its
        # "passed over" latch for the new rollout.
        self._bev_intersection_target_world = self._find_first_intersection_world(scene)
        self._intersection_target_reached = False
        self._intersection_target_armed = False
        # Projection model for the selected main camera at the render resolution,
        # so projected pixels normalize cleanly by (raster.width, raster.height).
        self._main_camera_model = FThetaCameraModel(
            scene.selected_camera,
            output_width=self._raster.width,
            output_height=self._raster.height,
        )
        if self._bev_intersection_target_world is not None:
            ix, iy, iz = self._bev_intersection_target_world
            spawn_x = float(scene.initial_rig_to_world[0, 3])
            spawn_y = float(scene.initial_rig_to_world[1, 3])
            dist = math.hypot(ix - spawn_x, iy - spawn_y)
            logger.info(
                f"[rasterizer] pinned first-intersection goal at world "
                f"({ix:.1f}, {iy:.1f}, {iz:.1f}); {dist:.1f} m from spawn."
            )
        else:
            logger.info(
                "[rasterizer] no intersection_areas polygons in scene "
                f"{scene.scene_id!r}; first-intersection goal disabled "
                f"(polygon layers: "
                f"{[layer.layer_name for layer in scene.polygon_layers]})."
            )

        if self._temp_dir is not None:
            self._temp_dir.cleanup()
        self._temp_dir = tempfile.TemporaryDirectory()

        clipgt_dir = _extract_clipgt_from_usdz(
            scene.scene_path, Path(self._temp_dir.name)
        )

        clipgt_scene = load_clipgt_scene(
            clipgt_dir,
            device=self._device,
            target_resolution=(self._raster.width, self._raster.height),
            include_ego_trajectory=False,
            include_ego_obstacle=False,
        )

        scene_adapter = SceneAdapter(clipgt_scene)
        self._scene_data = _LoadedSceneData(
            clipgt_scene=clipgt_scene,
            scene_adapter=scene_adapter,
        )

        # Copy the scene's camera list so we can append our synthetic BEV
        # camera without mutating ``clipgt_scene.cameras`` (the loader returns
        # a shared list and downstream consumers expect stable indices).
        self._all_cameras = list(clipgt_scene.cameras)
        self._all_camera_map = dict(clipgt_scene.camera_name_to_id)
        self._sensor_to_rig = dict(clipgt_scene.sensor_to_rig)
        self._selected_camera_name = scene.selected_camera.clipgt_name

        if self._bev is not None and self._bev.enabled:
            bev_camera = _build_bev_camera(self._bev, self._device)
            self._bev_camera_id = len(self._all_cameras)
            self._all_cameras.append(bev_camera)
            self._all_camera_map[_BEV_CAMERA_NAME] = self._bev_camera_id
            self._bev_sensor_to_rig = _bev_sensor_to_rig(
                height_m=self._bev.height_m,
                tilt_deg=self._bev.tilt_deg,
                device=self._device,
            )
            self._sensor_to_rig[_BEV_CAMERA_NAME] = self._bev_sensor_to_rig
        else:
            self._bev_camera_id = None
            self._bev_sensor_to_rig = None

        self.ctx.upload_cameras(self._all_cameras)

        # Single scene upload shared by the main camera and the BEV minimap.
        self._scene_id = self.ctx.upload_scene(clipgt_scene.timestamped_scene)

    def rearm_intersection_target(self) -> None:
        """Clear the passed-over latch so the first-intersection marker reappears.

        Called on a manual reset / home: the ego returns to the same spawn, so
        the pinned world point is still valid -- only the reached/armed state
        resets, bringing the marker (minimap dot + viewport cylinder) back.
        """
        self._intersection_target_reached = False
        self._intersection_target_armed = False

    def _find_first_intersection_world(
        self, scene: SceneBundle
    ) -> tuple[float, float, float] | None:
        """World (x, y, z) of the first intersection ahead of the spawn.

        The scene exposes intersection geometry as a polygon layer named
        ``intersection_areas`` (loaded from ``clipgt/intersection_area.parquet``).
        "First" means the intersection the ego would reach driving forward: among
        polygon centroids that are *ahead* of spawn (positive forward projection)
        and within a lateral corridor, pick the smallest forward distance -- not
        the smallest straight-line distance, which can grab one off to the side or
        skip past the first along the road. Falls back to the nearest overall when
        none are ahead/in-corridor. ``z`` is the centroid height (ground), used as
        the base of the viewport cylinder marker. Returns ``None`` when the scene
        has no intersection layer or all its polygons are empty.
        """
        spawn_x = float(scene.initial_rig_to_world[0, 3])
        spawn_y = float(scene.initial_rig_to_world[1, 3])
        # Testing placement: pin the goal a fixed distance straight ahead of
        # spawn so it's visible immediately and stays put until the car drives
        # over it. Defaults to 200 m; IDRIVE_TEST_MARKER_AHEAD_M overrides the
        # distance, and setting it to 0 falls back to the real first-intersection
        # search below.
        ahead_env = os.environ.get("IDRIVE_TEST_MARKER_AHEAD_M")
        try:
            ahead_m = float(ahead_env) if ahead_env is not None else 200.0
        except ValueError:
            ahead_m = 200.0
        if ahead_m > 0.0:
            fwd = np.asarray(scene.initial_rig_to_world[:2, 0], dtype=np.float64)
            norm = float(np.hypot(fwd[0], fwd[1]))
            if norm > 1e-6:
                fwd = fwd / norm
                spawn_z = float(scene.initial_rig_to_world[2, 3])
                target = (
                    spawn_x + ahead_m * float(fwd[0]),
                    spawn_y + ahead_m * float(fwd[1]),
                    spawn_z,
                )
                logger.info(
                    f"[rasterizer] pinning test goal {ahead_m:.1f} m ahead of "
                    f"spawn at ({target[0]:.1f}, {target[1]:.1f}) "
                    f"(set IDRIVE_TEST_MARKER_AHEAD_M=0 for real intersection)."
                )
                return target
        # Spawn forward / left unit vectors (rig +X / +Y in world xy), used to
        # order intersections by how far *ahead* they are rather than raw range.
        fwd = np.asarray(scene.initial_rig_to_world[:2, 0], dtype=np.float64)
        left = np.asarray(scene.initial_rig_to_world[:2, 1], dtype=np.float64)
        fnorm = float(np.hypot(fwd[0], fwd[1]))
        lnorm = float(np.hypot(left[0], left[1]))
        if fnorm > 1e-6:
            fwd = fwd / fnorm
        if lnorm > 1e-6:
            left = left / lnorm

        # "Ahead" = at least a couple metres in front; corridor keeps an
        # intersection that's only marginally ahead but far to the side from
        # winning over the one actually down the road.
        min_ahead_m = 2.0
        corridor_half_w_m = 40.0

        best_ahead: tuple[float, float, float] | None = None
        best_ahead_fwd = math.inf
        best_any: tuple[float, float, float] | None = None
        best_any_d2 = math.inf
        for layer in scene.polygon_layers:
            if "intersection" not in layer.layer_name.lower():
                continue
            for poly in layer.polygons_world:
                if poly is None or len(poly) == 0:
                    continue
                cx = float(np.mean(poly[:, 0]))
                cy = float(np.mean(poly[:, 1]))
                cz = float(np.mean(poly[:, 2])) if poly.shape[1] > 2 else 0.0
                d2 = (cx - spawn_x) ** 2 + (cy - spawn_y) ** 2
                if d2 < best_any_d2:
                    best_any_d2 = d2
                    best_any = (cx, cy, cz)
                forward_m = (cx - spawn_x) * fwd[0] + (cy - spawn_y) * fwd[1]
                lateral_m = (cx - spawn_x) * left[0] + (cy - spawn_y) * left[1]
                if (
                    forward_m >= min_ahead_m
                    and abs(lateral_m) <= corridor_half_w_m
                    and forward_m < best_ahead_fwd
                ):
                    best_ahead_fwd = forward_m
                    best_ahead = (cx, cy, cz)
        return best_ahead if best_ahead is not None else best_any

    def _project_bev_point(
        self,
        rig_pose_world: npt.NDArray[np.float32],
        target_world: tuple[float, float],
    ) -> tuple[float, float, bool]:
        """Project a fixed world (x, y) into normalized BEV panel coords.

        ``rig_pose_world`` is the 4x4 rig-to-world pose. Returns ``(nx, ny,
        offscreen)`` in [0,1] when on-panel. The vertical origin is the ego's
        rendered position in the tilted BEV (``_bev_ego_y_rel``, near the bottom
        for the default forward tilt) -- the same anchor the HUD uses for the
        ego chevron -- so the dot lines up with the ego and the map instead of
        assuming the ego sits at panel centre. Assumes ``self._bev`` is set.
        """
        assert self._bev is not None
        ego_x = float(rig_pose_world[0, 3])
        ego_y = float(rig_pose_world[1, 3])
        forward = rig_pose_world[:2, 0]  # rig +X (forward) in world xy
        left = rig_pose_world[:2, 1]  # rig +Y (left) in world xy
        dx = target_world[0] - ego_x
        dy = target_world[1] - ego_y
        forward_m = float(dx * forward[0] + dy * forward[1])
        left_m = float(dx * left[0] + dy * left[1])
        half_m = max(
            1e-3, self._bev.height_m * math.tan(math.radians(self._bev.fov_deg) / 2.0)
        )
        nx = 0.5 - left_m / (2.0 * half_m)
        ny = self._bev_ego_y_rel() - forward_m / (2.0 * half_m)
        offscreen = not (0.0 <= nx <= 1.0 and 0.0 <= ny <= 1.0)
        return nx, ny, offscreen

    def _bev_ego_y_rel(self) -> float:
        """Vertical [0,1] position of the ego in the rendered BEV image.

        Mirrors ``demo._bev_marker_y_rel``: a straight-down BEV (tilt=0) puts
        the ego at the centre (0.5); forward tilt pushes it lower. Kept here so
        the projected target origin matches where the HUD draws the ego chevron.
        """
        assert self._bev is not None
        half_fov = math.radians(self._bev.fov_deg / 2.0)
        if half_fov <= 0:
            return 0.5
        return min(
            0.95,
            0.5 + math.tan(math.radians(self._bev.tilt_deg)) / (2.0 * math.tan(half_fov)),
        )

    def _project_bev_target(
        self, rig_pose_world: npt.NDArray[np.float32]
    ) -> tuple[float, float, bool]:
        """Project the pinned home/spawn target into normalized BEV coords."""
        assert self._bev_target_world is not None
        return self._project_bev_point(rig_pose_world, self._bev_target_world)

    def _project_viewport_marker(
        self,
        rig_pose_world: npt.NDArray[np.float32],
        target_xyz: tuple[float, float, float],
    ) -> tuple[float, float, float, float] | None:
        """Project the cylinder base + top into normalized main-viewport coords.

        Projects the ground point ``target_xyz`` and a point
        ``_INTERSECTION_MARKER_HEIGHT_M`` above it through the selected main
        camera. Returns ``(base_nx, base_ny, top_nx, top_ny)`` as [0,1] image
        fractions, or ``None`` when the camera model is unset or either point is
        behind the camera (so the HUD skips drawing).
        """
        if self._main_camera_model is None:
            return None
        bx, by, bz = target_xyz
        pts = np.array(
            [[bx, by, bz], [bx, by, bz + _INTERSECTION_MARKER_HEIGHT_M]],
            dtype=np.float32,
        )
        uv, _depth, valid = self._main_camera_model.project_world(
            pts, rig_pose_world.astype(np.float32)
        )
        if not (bool(valid[0]) and bool(valid[1])):
            return None
        w = float(self._raster.width)
        h = float(self._raster.height)
        return (
            float(uv[0, 0]) / w,
            float(uv[0, 1]) / h,
            float(uv[1, 0]) / w,
            float(uv[1, 1]) / h,
        )

    def render_chunk(
        self,
        rig_poses_world: npt.NDArray[np.float32],
        timestamps_us: npt.NDArray[np.int64],
    ) -> RasterChunk:
        """Render a chunk of frames from the scene's selected camera.

        When BEV is enabled (see :class:`BevConfig`) the rasterizer also
        renders a top-down map for each frame and attaches it to
        :attr:`PresentedFrame.bev_host_uint8`.

        Args:
            rig_poses_world: Rig-to-world poses [num_frames, 4, 4].
            timestamps_us: Frame timestamps in microseconds [num_frames].

        Returns:
            RasterChunk containing rendered frames.
        """
        if (
            self._scene_data is None
            or self._scene_id is None
            or self._selected_camera_name is None
        ):
            raise RuntimeError("load_scene() must be called before render_chunk().")

        camera_name = self._selected_camera_name
        if camera_name not in self._all_camera_map:
            available = sorted(self._all_camera_map.keys())
            raise RuntimeError(
                f"Camera {camera_name!r} not found. Available: {available}"
            )

        rig_poses_torch = torch.from_numpy(
            np.ascontiguousarray(rig_poses_world, dtype=np.float32)
        ).to(device=self._device)
        timestamps_batch = torch.from_numpy(
            np.ascontiguousarray(timestamps_us, dtype=np.int64)
        ).to(device=self._device)

        rgb_frames = self._render_one_camera(
            rig_poses=rig_poses_torch,
            timestamps_batch=timestamps_batch,
            scene_id=self._scene_id,
            camera_id=self._all_camera_map[camera_name],
            sensor_to_rig=self._sensor_to_rig[camera_name],
            camera_type=CAMERA_TYPE_REGULAR,
            resolution=(self._raster.height, self._raster.width),
        )

        bev_frames: _RenderedCameraFrames | None = None
        if (
            self._bev is not None
            and self._bev.enabled
            and self._bev_camera_id is not None
            and self._bev_sensor_to_rig is not None
        ):
            bev_frames = self._render_one_camera(
                rig_poses=rig_poses_torch,
                timestamps_batch=timestamps_batch,
                scene_id=self._scene_id,
                camera_id=self._bev_camera_id,
                sensor_to_rig=self._bev_sensor_to_rig,
                camera_type=CAMERA_TYPE_BEV,
                resolution=(self._bev.height, self._bev.width),
            )

        # Pin the target to the spawn on the first BEV frame, then project it
        # into normalized panel coords per frame using that frame's ego pose.
        if bev_frames is not None:
            if self._bev_target_world is None:
                # Pin the goal 200 m straight ahead of the ego's spawn (forward
                # = rig +X in world xy) so the dot sits in front and the ego
                # drives toward it, instead of behind at the spawn point.
                pose0 = rig_poses_world[0]
                fwd0 = pose0[:2, 0]
                self._bev_target_world = (
                    float(pose0[0, 3]) + 200.0 * float(fwd0[0]),
                    float(pose0[1, 3]) + 200.0 * float(fwd0[1]),
                )
            bev_targets: list[tuple[float, float, bool] | None] = [
                self._project_bev_target(rig_poses_world[idx])
                for idx in range(len(timestamps_us))
            ]
        else:
            bev_targets = [None] * len(timestamps_us)

        # Static first-intersection goal: pinned in the world, projected per
        # frame onto both the BEV minimap (intersection_targets) and the main
        # viewport cylinder overlay (viewport_markers), and removed for good once
        # the ego drives within _INTERSECTION_REACH_M of it (both then disappear
        # for the rest of the rollout).
        intersection_targets: list[tuple[float, float, bool] | None] = [None] * len(
            timestamps_us
        )
        viewport_markers: list[tuple[float, float, float, float] | None] = [
            None
        ] * len(timestamps_us)
        if self._bev_intersection_target_world is not None:
            gx, gy, gz = self._bev_intersection_target_world
            reach2 = _INTERSECTION_REACH_M * _INTERSECTION_REACH_M
            for idx in range(len(timestamps_us)):
                if self._intersection_target_reached:
                    break
                ego_x = float(rig_poses_world[idx][0, 3])
                ego_y = float(rig_poses_world[idx][1, 3])
                if (ego_x - gx) ** 2 + (ego_y - gy) ** 2 > reach2:
                    # Outside the radius: keep showing the marker and arm it so a
                    # later approach can count as "passed over".
                    self._intersection_target_armed = True
                elif self._intersection_target_armed:
                    # Drove over it after starting away: hide it for good.
                    self._intersection_target_reached = True
                    logger.info(
                        f"[rasterizer] ego passed over first-intersection goal "
                        f"at ({gx:.1f}, {gy:.1f}); hiding marker."
                    )
                    break
                if bev_frames is not None:
                    intersection_targets[idx] = self._project_bev_point(
                        rig_poses_world[idx], self._bev_intersection_target_world
                    )
                viewport_markers[idx] = self._project_viewport_marker(
                    rig_poses_world[idx], (gx, gy, gz)
                )

        if self._use_cuda_frames:
            frames = [
                PresentedFrame(
                    timestamp_us=int(timestamps_us[idx]),
                    rgb_host_uint8=_LazyRasterFrame(
                        rgb_frames.frames_hwc_uint8,
                        idx,
                        source_event=rgb_frames.ready_event,
                    ),
                    depth_host_f32=None,
                    bev_host_uint8=(
                        _LazyRasterFrame(
                            bev_frames.frames_hwc_uint8,
                            idx,
                            source_event=bev_frames.ready_event,
                        )
                        if bev_frames is not None
                        else None
                    ),
                    bev_target_norm=(
                        (bev_targets[idx][0], bev_targets[idx][1])
                        if bev_targets[idx] is not None
                        else None
                    ),
                    bev_target_offscreen=(
                        bev_targets[idx][2] if bev_targets[idx] is not None else False
                    ),
                    bev_intersection_target_norm=(
                        (intersection_targets[idx][0], intersection_targets[idx][1])
                        if intersection_targets[idx] is not None
                        else None
                    ),
                    bev_intersection_target_offscreen=(
                        intersection_targets[idx][2]
                        if intersection_targets[idx] is not None
                        else False
                    ),
                    viewport_intersection_marker=viewport_markers[idx],
                )
                for idx in range(len(timestamps_us))
            ]
            return RasterChunk(frames=tuple(frames))

        rgb_host_frames = _rendered_frames_to_numpy(rgb_frames)
        bev_host_frames = (
            _rendered_frames_to_numpy(bev_frames) if bev_frames is not None else None
        )
        frames = [
            PresentedFrame(
                timestamp_us=int(timestamps_us[idx]),
                rgb_host_uint8=rgb_host_frames[idx],
                depth_host_f32=None,
                bev_host_uint8=(
                    bev_host_frames[idx] if bev_host_frames is not None else None
                ),
                bev_target_norm=(
                    (bev_targets[idx][0], bev_targets[idx][1])
                    if bev_targets[idx] is not None
                    else None
                ),
                bev_target_offscreen=(
                    bev_targets[idx][2] if bev_targets[idx] is not None else False
                ),
                bev_intersection_target_norm=(
                    (intersection_targets[idx][0], intersection_targets[idx][1])
                    if intersection_targets[idx] is not None
                    else None
                ),
                bev_intersection_target_offscreen=(
                    intersection_targets[idx][2] if intersection_targets[idx] is not None else False
                ),
                viewport_intersection_marker=viewport_markers[idx],
            )
            for idx in range(len(timestamps_us))
        ]
        return RasterChunk(frames=tuple(frames))

    def _render_one_camera(
        self,
        *,
        rig_poses: Tensor,
        timestamps_batch: Tensor,
        scene_id: int,
        camera_id: int,
        sensor_to_rig: Tensor,
        camera_type: int,
        resolution: tuple[int, int],
    ) -> _RenderedCameraFrames:
        """Single-camera rasterizer dispatch shared by the main view and BEV.

        Frames stay CUDA-backed so the world model consumes HDMap conditioning
        without a GPU->CPU->GPU round trip (presenters materialize NumPy lazily).
        """
        n_frames = timestamps_batch.shape[0]
        camera_poses_world = torch.einsum(
            "nij,jk->nik", rig_poses, sensor_to_rig.to(self._device)
        )
        camera_poses_ludus = self._to_ludus_camera_pose(camera_poses_world)
        scene_id_batch = torch.full(
            (n_frames,), scene_id, dtype=torch.int32, device=self._device
        )
        camera_id_batch = torch.full(
            (n_frames,), camera_id, dtype=torch.int32, device=self._device
        )
        camera_type_id_batch = torch.full(
            (n_frames,), camera_type, dtype=torch.int32, device=self._device
        )

        height, width = resolution
        images = self.ctx.render(
            scene_id_batch,
            camera_id_batch,
            timestamps_batch,
            camera_type_id_batch,
            camera_poses_ludus,
            resolution=(height, width),
        )

        rgb = images[:, :, :, :3]
        if self.ctx.needs_vflip:
            rgb = rgb.flip(1)
        if rgb.dtype != torch.uint8:
            rgb = (rgb.clamp(0.0, 1.0) * 255.0 + 0.5).to(torch.uint8)
        rgb = rgb.detach().contiguous()
        ready_event = None
        if rgb.is_cuda:
            ready_event = torch.cuda.Event()
            ready_event.record(torch.cuda.current_stream(rgb.device))
        return _RenderedCameraFrames(frames_hwc_uint8=rgb, ready_event=ready_event)

    def cleanup(self) -> None:
<<<<<<< HEAD
        """Cleanup resources."""
        # getattr guard: __init__ can raise before _temp_dir is assigned (e.g.
        # the ludus extension build fails), and __del__ still runs cleanup.
        temp_dir = getattr(self, "_temp_dir", None)
        if temp_dir is not None:
            temp_dir.cleanup()
=======
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
>>>>>>> main
            self._temp_dir = None

    def __del__(self) -> None:
        self.cleanup()


class LudusConditionRasterizer:
    """Thread-pinned facade over :class:`_LudusConditionRasterizerImpl`.

    NVIDIA EGL on the Blackwell + 595.58.03 driver can't migrate a headless
    surfaceless GL context across threads (``eglMakeCurrent`` fails off the
    init thread), so every public entry point runs synchronously on one
    dedicated worker that owns the GL context for its lifetime. Behaves
    exactly like the underlying implementation.
    """

    def __init__(self, raster: RasterConfig, bev: BevConfig | None = None) -> None:
        self._exec = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="ludus-render"
        )
        self._impl: _LudusConditionRasterizerImpl | None = self._exec.submit(
            _LudusConditionRasterizerImpl, raster, bev
        ).result()

    def load_scene(self, scene: SceneBundle) -> None:
        exec_, impl = self._require_alive()
        return exec_.submit(impl.load_scene, scene).result()

    def render_chunk(
        self,
        rig_poses_world: npt.NDArray[np.float32],
        timestamps_us: npt.NDArray[np.int64],
    ) -> "RasterChunk":
        exec_, impl = self._require_alive()
        return exec_.submit(impl.render_chunk, rig_poses_world, timestamps_us).result()

    def rearm_intersection_target(self) -> None:
        exec_, impl = self._require_alive()
        return exec_.submit(impl.rearm_intersection_target).result()

    def _require_alive(
        self,
    ) -> tuple[concurrent.futures.ThreadPoolExecutor, _LudusConditionRasterizerImpl]:
        exec_ = self._exec
        impl = self._impl
        assert exec_ is not None and impl is not None, "rasterizer has been cleaned up"
        return exec_, impl

    def cleanup(self) -> None:
        exec_ = getattr(self, "_exec", None)
        if exec_ is None:
            return
        impl = self._impl
        self._impl = None
        if impl is not None:
            with contextlib.suppress(Exception):
                exec_.submit(impl.cleanup).result()
        exec_.shutdown(wait=True)
        self._exec = None

    def __del__(self) -> None:
        with contextlib.suppress(Exception):
            self.cleanup()


def _rendered_frames_to_numpy(rendered: _RenderedCameraFrames) -> list[np.ndarray]:
    synchronize = getattr(rendered.ready_event, "synchronize", None)
    if callable(synchronize):
        synchronize()
    frames = rendered.frames_hwc_uint8.detach().cpu().numpy()
    frames = np.ascontiguousarray(frames, dtype=np.uint8)
    return [frames[idx] for idx in range(frames.shape[0])]


def _build_bev_camera(bev: BevConfig, device: torch.device) -> FThetaCamera:
    """Construct a synthetic pinhole-as-FTheta camera for BEV rendering.

    Reproduces a pinhole projection by feeding the Taylor expansion of
    ``f * tan(theta)`` into the F-theta forward polynomial; ``height_m`` +
    ``fov_deg`` set how much ground the BEV covers around the rig.
    """
    cx = float(bev.width) / 2.0
    cy = float(bev.height) / 2.0
    half_fov = math.radians(float(bev.fov_deg)) / 2.0
    focal = (float(bev.height) / 2.0) / math.tan(half_fov)
    diagonal = math.sqrt((float(bev.width) / 2.0) ** 2 + (float(bev.height) / 2.0) ** 2)
    max_ray_angle = math.atan(diagonal / focal)
    poly_coeffs = torch.tensor(
        [0.0, focal, 0.0, focal / 3.0, 0.0, 2.0 * focal / 15.0],
        device=device,
        dtype=torch.float32,
    )
    return FThetaCamera(
        principal_point=torch.tensor([cx, cy], device=device, dtype=torch.float32),
        image_size=torch.tensor(
            [float(bev.width), float(bev.height)], device=device, dtype=torch.float32
        ),
        fw_poly=poly_coeffs,
        max_ray_angle=max_ray_angle,
        depth_max=max(150.0, float(bev.height_m) * 4.0),
    )


def _bev_sensor_to_rig(
    *, height_m: float, tilt_deg: float, device: torch.device
) -> Tensor:
    """Sensor-to-rig transform for a top-down (or forward-tilted) BEV camera.

    Sensor (FLU): X=forward (optical axis), Y=left, Z=up
    Rig (FLU):    X=forward, Y=left, Z=up

    At ``tilt_deg = 0`` (straight-down BEV):
      Sensor X (depth)    -> Rig -Z (down)
      Sensor Y (left)     -> Rig +Y
      Sensor Z (up image) -> Rig +X (forward)

    ``tilt_deg > 0`` pitches the optical axis forward around the rig Y axis for
    a navigation-style chase view; camera position stays at ``(0, 0, height_m)``
    so tilt doesn't require retuning ``height_m``.
    """
    theta = math.radians(float(tilt_deg))
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    # Rotation columns express where the sensor axes land in rig FLU:
    #   col 0 (sensor X / optical axis) -> ( sin θ,  0, -cos θ)
    #   col 1 (sensor Y / image left)   -> (     0,  1,       0)
    #   col 2 (sensor Z / image up)     -> ( cos θ,  0,  sin θ)
    # At θ = 0 this collapses to the straight-down matrix above.
    return torch.tensor(
        [
            [sin_t, 0.0, cos_t, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [-cos_t, 0.0, sin_t, float(height_m)],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=torch.float32,
        device=device,
    )
