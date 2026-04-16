"""Asyncio WebSocket server: CTRL in, batched FRME out.

Defaults match a **mock cloud renderer**: 1280×720 WebP batches of 8 frames, plus a
fixed **200 ms** ``asyncio.sleep`` per CTRL-driven batch (prefill batches skip the
sleep). Tune ``--stub-latency-ms``, ``--frame-width``, ``--frame-height`` for other
scenarios.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from projects.streaming_ws.protocol import pack_frme, unpack_ctrl
from projects.streaming_ws.stub_frames import encode_stub_batch

# Producer waits on ``await control_q.get()``; when the socket closes, the reader
# must unblock it. ``_SENTINEL`` is a unique object we push after draining stale CTRLs.
_SENTINEL = object()


@dataclass(frozen=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8765
    frames_per_batch: int = 8
    # Default mock: 720p batches with a fixed "inference" delay before encode+send.
    frame_width: int = 1280
    frame_height: int = 720
    prefill_batches: int = 2
    stub_latency_ms: float = 800.0
    max_ws_message_bytes: int = 64 * 1024 * 1024


async def _reader(control_q: asyncio.Queue, conn: ServerConnection) -> None:
    """Decode CTRL messages; keep only the **latest** control (interactive coalescing)."""
    try:
        async for message in conn:
            if not isinstance(message, (bytes, bytearray)):
                continue
            try:
                cm = unpack_ctrl(bytes(message))
            except ValueError:
                continue
            try:
                control_q.put_nowait(cm)
            except asyncio.QueueFull:
                # Queue size 1: drop the previous CTRL so gameplay stays on newest input.
                with contextlib.suppress(asyncio.QueueEmpty):
                    control_q.get_nowait()
                with contextlib.suppress(asyncio.QueueFull):
                    control_q.put_nowait(cm)
    finally:
        # Wake the producer if it is blocked on control_q.get() after disconnect.
        while True:
            try:
                control_q.get_nowait()
            except asyncio.QueueEmpty:
                break
        await control_q.put(_SENTINEL)


async def _handle_connection(conn: ServerConnection, cfg: ServerConfig) -> None:
    """Send prefill FRMEs (no CTRL needed), then one FRME per latest CTRL until close."""
    control_q: asyncio.Queue = asyncio.Queue(maxsize=1)
    # Reader runs concurrently so CTRL can arrive while we encode/send prefill.
    reader = asyncio.create_task(_reader(control_q, conn))
    batch_id = 0
    base_frame = 0
    try:
        # Warm the client buffer before first real CTRL/RTT (no stub_latency sleep here).
        for _ in range(cfg.prefill_batches):
            frames = encode_stub_batch(
                ctrl=None,
                batch_id=batch_id,
                width=cfg.frame_width,
                height=cfg.frame_height,
                n_frames=cfg.frames_per_batch,
                base_frame=base_frame,
            )
            base_frame += cfg.frames_per_batch
            blob = pack_frme(
                n_frames=cfg.frames_per_batch,
                width=cfg.frame_width,
                height=cfg.frame_height,
                batch_id=batch_id,
                frames=frames,
            )
            await conn.send(blob)
            batch_id += 1

        while True:
            item = await control_q.get()
            if item is _SENTINEL:
                break
            ctrl = item
            # Mock GPU/inference time before building the next 8-frame WebP batch.
            if cfg.stub_latency_ms > 0:
                await asyncio.sleep(cfg.stub_latency_ms / 1000.0)
            frames = encode_stub_batch(
                ctrl=ctrl,
                batch_id=batch_id,
                width=cfg.frame_width,
                height=cfg.frame_height,
                n_frames=cfg.frames_per_batch,
                base_frame=base_frame,
            )
            base_frame += cfg.frames_per_batch
            blob = pack_frme(
                n_frames=cfg.frames_per_batch,
                width=cfg.frame_width,
                height=cfg.frame_height,
                batch_id=batch_id,
                frames=frames,
            )
            await conn.send(blob)
            batch_id += 1
    except ConnectionClosed:
        # Peer disconnected (e.g. during slow 720p prefill); not a server bug.
        pass
    except asyncio.CancelledError:
        raise
    finally:
        reader.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reader


async def run_server(cfg: ServerConfig) -> None:
    """Listen until cancelled (Ctrl+C under ``asyncio.run``)."""

    async def handler(conn: ServerConnection) -> None:
        await _handle_connection(conn, cfg)

    async with serve(
        handler,
        cfg.host,
        cfg.port,
        # Pre-compressed images: disable permessage-deflate (CPU + latency).
        compression=None,
        max_size=cfg.max_ws_message_bytes,
    ):
        # Block forever until SIGINT cancels the process / event loop.
        await asyncio.Future()


def main_server(cfg: ServerConfig) -> None:
    asyncio.run(run_server(cfg))
