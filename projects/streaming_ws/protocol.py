"""Binary wire format: CTRL (client → server), FRME (server → client).

All multi-byte integers are **big-endian** (network order).

CTRL layout::

    u32 magic | u32 seq | u32 payload_len | payload_len bytes UTF-8 JSON object

FRME layout::

    u32 magic | u8 version | u8 n_frames | u16 width | u16 height | u32 batch_id
    then n_frames times: u32 len_i | len_i bytes (e.g. WebP)
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass

CTRL_MAGIC = 0x4354524C
FRME_MAGIC = 0x46524D45
PROTO_VERSION = 1

# CTRL: magic, client monotonic seq (opaque to server), JSON byte length
_CTRL_HEADER_STRUCT = struct.Struct(">III")
# FRME: magic, protocol version, frame count, dimensions, server batch counter
_FRME_HEADER_STRUCT = struct.Struct(">IBBHHI")


@dataclass(frozen=True)
class CtrlMessage:
    """Decoded client control."""

    seq: int
    control: dict


@dataclass(frozen=True)
class FrmeMessage:
    """Decoded frame batch."""

    version: int
    n_frames: int
    width: int
    height: int
    batch_id: int
    frames: tuple[bytes, ...]


def pack_ctrl(seq: int, control: dict) -> bytes:
    """Pack one WebSocket **binary** control message (not text WS frames)."""
    payload = json.dumps(control, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _CTRL_HEADER_STRUCT.pack(CTRL_MAGIC, seq, len(payload)) + payload


def unpack_ctrl(data: bytes) -> CtrlMessage:
    """Unpack a control message; raises ValueError on bad magic or JSON."""
    if len(data) < _CTRL_HEADER_STRUCT.size:
        raise ValueError("CTRL message too short")
    magic, seq, payload_len = _CTRL_HEADER_STRUCT.unpack_from(data, 0)
    if magic != CTRL_MAGIC:
        raise ValueError(f"bad CTRL magic {magic:#x}")
    end = _CTRL_HEADER_STRUCT.size + payload_len
    if end > len(data):
        raise ValueError("CTRL payload length out of range")
    if end < len(data):
        # One CTRL message must exactly fill one WS binary frame for this minimal stack.
        raise ValueError("CTRL trailing bytes")
    raw = data[_CTRL_HEADER_STRUCT.size : end]
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError("CTRL invalid JSON") from e
    if not isinstance(obj, dict):
        raise ValueError("CTRL JSON must be an object")
    return CtrlMessage(seq=seq, control=obj)


def pack_frme(
    *,
    n_frames: int,
    width: int,
    height: int,
    batch_id: int,
    frames: list[bytes],
) -> bytes:
    """Pack one FRME WebSocket binary message."""
    if len(frames) != n_frames:
        raise ValueError("n_frames must match len(frames)")
    if not (0 <= n_frames <= 255):
        raise ValueError("n_frames must fit in u8")
    parts: list[bytes] = [
        _FRME_HEADER_STRUCT.pack(
            FRME_MAGIC,
            PROTO_VERSION,
            n_frames,
            width & 0xFFFF,
            height & 0xFFFF,
            batch_id & 0xFFFFFFFF,
        )
    ]
    for blob in frames:
        parts.append(struct.pack(">I", len(blob) & 0xFFFFFFFF))
        parts.append(blob)
    return b"".join(parts)


def unpack_frme(data: bytes) -> FrmeMessage:
    """Unpack one FRME message."""
    pos = 0
    if len(data) < _FRME_HEADER_STRUCT.size:
        raise ValueError("FRME message too short")
    magic, version, n_frames, width, height, batch_id = _FRME_HEADER_STRUCT.unpack_from(
        data, pos
    )
    pos += _FRME_HEADER_STRUCT.size
    if magic != FRME_MAGIC:
        raise ValueError(f"bad FRME magic {magic:#x}")
    if version != PROTO_VERSION:
        raise ValueError(f"unsupported FRME version {version}")
    frames: list[bytes] = []
    for _ in range(n_frames):
        if pos + 4 > len(data):
            raise ValueError("FRME truncated frame length")
        (ln,) = struct.unpack_from(">I", data, pos)
        pos += 4
        if pos + ln > len(data):
            raise ValueError("FRME truncated frame bytes")
        frames.append(bytes(data[pos : pos + ln]))
        pos += ln
    if pos != len(data):
        raise ValueError("FRME trailing bytes")
    return FrmeMessage(
        version=version,
        n_frames=n_frames,
        width=width,
        height=height,
        batch_id=batch_id,
        frames=tuple(frames),
    )
