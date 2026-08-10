#!/usr/bin/env python3
"""
Live Ludus BEV viewer - renders actual scene geometry.
"""

import math
import tkinter as tk
from tkinter import Canvas, Scale, Label, Frame, HORIZONTAL, Button, messagebox
import numpy as np

try:
    from PIL import Image, ImageDraw, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("ERROR: PIL required. Install with: pip install Pillow")
    exit(1)


class LudusViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Ludus BEV Viewer - OmniDreams")
        self.root.geometry("1100x750")

        self.x_m = 0.0
        self.y_m = 0.0
        self.yaw_deg = 0.0

        self.rasterizer = None
        self.photo_image = None

        self._create_ui()
        self._load_omnidreams()

    def _create_ui(self):
        # Left panel
        left = Frame(self.root, bg="lightgray", width=250)
        left.pack(side="left", padx=10, pady=10, fill="both")
        left.pack_propagate(False)

        Label(left, text="LUDUS BEV VIEWER", font=("Arial", 12, "bold"), bg="lightgray").pack()

        self.status_label = Label(left, text="Loading OmniDreams...", fg="orange", font=("Arial", 9), bg="lightgray")
        self.status_label.pack(pady=5)

        # Controls
        Label(left, text="\nVEHICLE STATE", font=("Arial", 11, "bold"), bg="lightgray").pack()

        Label(left, text="X (m):", bg="lightgray").pack()
        self.x_slider = Scale(left, from_=-50, to=50, orient=HORIZONTAL, length=200)
        self.x_slider.set(0)
        self.x_slider.pack(fill="x", pady=5, padx=5)

        Label(left, text="Y (m):", bg="lightgray").pack()
        self.y_slider = Scale(left, from_=-50, to=50, orient=HORIZONTAL, length=200)
        self.y_slider.set(0)
        self.y_slider.pack(fill="x", pady=5, padx=5)

        Label(left, text="Yaw (degrees):", bg="lightgray").pack()
        self.yaw_slider = Scale(left, from_=0, to=360, orient=HORIZONTAL, length=200)
        self.yaw_slider.set(0)
        self.yaw_slider.pack(fill="x", pady=5, padx=5)

        # Render button
        Button(left, text="Render BEV Frame", command=self.render_frame, bg="lightblue", height=2).pack(fill="x", pady=5, padx=5)

        # Quick tests
        Label(left, text="\nQUICK TESTS", font=("Arial", 10, "bold"), bg="lightgray").pack()

        tests = [("Yaw 0°", 0, 0, 0), ("Yaw 45°", 0, 0, 45), ("Yaw 90°", 0, 0, 90), ("Yaw 180°", 0, 0, 180), ("Reset", 0, 0, 0)]
        for label, x, y, yaw in tests:
            Button(left, text=label, height=1, command=lambda x=x, y=y, yaw=yaw: self.set_state(x, y, yaw)).pack(fill="x", pady=2, padx=5)

        Label(left, text="\nTEST", font=("Arial", 10, "bold"), bg="lightgray").pack()
        info = "✓ Chevron center\n✓ stays fixed during\n  yaw rotation\n\nIf it moves → bug"
        Label(left, text=info, justify="left", font=("Arial", 9), bg="lightgray").pack(pady=10, padx=5)

        # Right panel - canvas
        right = Frame(self.root)
        right.pack(side="right", padx=10, pady=10, fill="both", expand=True)

        Label(right, text="ACTUAL LUDUS RENDER", font=("Arial", 12, "bold")).pack()

        self.canvas = Canvas(right, bg="black", highlightthickness=1, highlightbackground="gray")
        self.canvas.pack(fill="both", expand=True, pady=10)

    def _load_omnidreams(self):
        """Load OmniDreams components."""
        try:
            from omnidreams.interactive_drive.config import AppConfig, BevConfig
            from omnidreams.interactive_drive.rasterizer import LudusConditionRasterizer
            from omnidreams.interactive_drive.scene_loader import load_scene_bundle
            from omnidreams.interactive_drive.math3d import rig_pose_from_state
            from omnidreams.scenes import normalise_scene_uuid, local_scene_archive_path

            self.rig_pose_from_state = rig_pose_from_state
            self.AppConfig = AppConfig
            self.BevConfig = BevConfig

            # Load scene
            scene_uuid = normalise_scene_uuid("default")
            scene_path = local_scene_archive_path(scene_uuid)

            if not scene_path.exists():
                self.status_label.config(text="Scene not found.\nRun: omnidreams-prepare --scene-uuid default", fg="red")
                return

            scene_bundle = load_scene_bundle(scene_path, selected_camera=None, variant=None)
            raster_config = AppConfig().raster
            bev_config = BevConfig(enabled=True, tilt_deg=0.0)

            self.rasterizer = LudusConditionRasterizer(raster=raster_config, bev=bev_config)
            self.rasterizer.load_scene(scene_bundle)

            self.status_label.config(text="Ready ✓", fg="green")

        except Exception as e:
            self.status_label.config(text=f"Error: {e}", fg="red")

    def set_state(self, x, y, yaw):
        """Set and render."""
        self.x_slider.set(x)
        self.y_slider.set(y)
        self.yaw_slider.set(yaw)
        self.render_frame()

    def render_frame(self):
        """Render BEV from Ludus."""
        if not self.rasterizer:
            messagebox.showerror("Error", "OmniDreams not loaded")
            return

        try:
            self.x_m = self.x_slider.get()
            self.y_m = self.y_slider.get()
            self.yaw_deg = self.yaw_slider.get()

            # Create rig pose
            rig_pose = self.rig_pose_from_state(
                x_m=self.x_m, y_m=self.y_m, z_m=0.0,
                yaw_rad=math.radians(self.yaw_deg)
            )
            # DEBUG: the pose fed to the rasterizer. If R changes with yaw but the
            # rendered map does NOT rotate, the BEV camera ignores the rig yaw
            # (rasterizer/BevConfig bug), not rig_pose_from_state.
            print(f"[bev-debug] yaw={self.yaw_deg:.0f} pos=({self.x_m:.1f},{self.y_m:.1f}) "
                  f"R_row0={rig_pose[0, :3]}", flush=True)

            # Render
            timestamps_us = np.array([0], dtype=np.int64)
            rig_poses = np.array([rig_pose], dtype=np.float32)

            chunk = self.rasterizer.render_chunk(rig_poses, timestamps_us)
            frame = chunk.frames[0]

            if frame.bev_host_uint8 is None:
                self.status_label.config(text="No BEV frame", fg="red")
                return

            self._display_ludus_bev(frame.bev_host_uint8)
            self.status_label.config(text=f"Yaw {self.yaw_deg}°", fg="green")

        except Exception as e:
            self.status_label.config(text=f"Render error: {e}", fg="red")

    def _display_ludus_bev(self, bev_rgb):
        """Display BEV with chevron overlay."""
        bev_np = np.asarray(bev_rgb)
        if bev_np.ndim != 3 or bev_np.shape[2] != 3:
            return

        img = Image.fromarray(bev_np, mode="RGB")

        # Car (ego) at image center; green cross drawn IN FRONT of it along the
        # heading. Forward in image space is up (-y) at yaw=0, rotated by yaw.
        draw = ImageDraw.Draw(img)
        cx, cy = img.width // 2, img.height // 2

        yaw_rad = math.radians(self.yaw_deg)
        fwd_x, fwd_y = math.sin(yaw_rad), -math.cos(yaw_rad)   # heading unit vector
        dist = 100                                             # px ahead of the car
        gx, gy = int(cx + fwd_x * dist), int(cy + fwd_y * dist)

        # heading line car -> cross
        draw.line([(cx, cy), (gx, gy)], fill=(0, 255, 0), width=2)
        # green cross IN FRONT
        s = 22
        draw.line([(gx - s, gy), (gx + s, gy)], fill=(0, 255, 0), width=4)
        draw.line([(gx, gy - s), (gx, gy + s)], fill=(0, 255, 0), width=4)
        # car position marker (white dot, black outline)
        draw.ellipse([(cx - 6, cy - 6), (cx + 6, cy + 6)], fill=(255, 255, 255), outline=(0, 0, 0), width=2)

        # Live camera pose readout (the x,y,yaw fed to rig_pose_from_state).
        # Watch these change as you drag the sliders to confirm the pose updates.
        draw.text((10, 10), f"cam  x={self.x_m:.1f}m  y={self.y_m:.1f}m  yaw={self.yaw_deg:.0f}deg",
                  fill=(0, 255, 0), font=None)

        # Fit to canvas
        w = self.canvas.winfo_width() or 600
        h = self.canvas.winfo_height() or 600

        aspect = img.width / img.height
        if aspect > w / h:
            new_w = int(w * 0.95)
            new_h = int(new_w / aspect)
        else:
            new_h = int(h * 0.95)
            new_w = int(new_h * aspect)

        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        self.photo_image = ImageTk.PhotoImage(img_resized)
        self.canvas.delete("all")
        self.canvas.create_image(w // 2, h // 2, image=self.photo_image)


if __name__ == "__main__":
    root = tk.Tk()
    app = LudusViewer(root)
    root.mainloop()
