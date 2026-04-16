"""Roundtrip tests for projects.streaming_ws.protocol."""

import pytest

from projects.streaming_ws.protocol import (
    CTRL_MAGIC,
    FRME_MAGIC,
    pack_ctrl,
    pack_frme,
    unpack_ctrl,
    unpack_frme,
)


def test_pack_unpack_ctrl_roundtrip() -> None:
    msg = pack_ctrl(7, {"dx": 1, "dy": -2, "keys": ["a"]})
    assert int.from_bytes(msg[:4], "big") == CTRL_MAGIC
    c = unpack_ctrl(msg)
    assert c.seq == 7
    assert c.control == {"dx": 1, "dy": -2, "keys": ["a"]}


def test_pack_unpack_frme_roundtrip() -> None:
    frames = [b"a", b"bb", b"ccc"]
    blob = pack_frme(n_frames=3, width=640, height=360, batch_id=99, frames=frames)
    assert int.from_bytes(blob[:4], "big") == FRME_MAGIC
    f = unpack_frme(blob)
    assert f.n_frames == 3
    assert f.width == 640
    assert f.height == 360
    assert f.batch_id == 99
    assert list(f.frames) == frames


def test_unpack_ctrl_bad_magic() -> None:
    bad = (0xDEADBEEF).to_bytes(4, "big") + b"\x00" * 8
    with pytest.raises(ValueError, match="magic"):
        unpack_ctrl(bad)


def test_unpack_frme_trailing_bytes() -> None:
    blob = pack_frme(n_frames=1, width=1, height=1, batch_id=0, frames=[b"x"])
    with pytest.raises(ValueError, match="trailing"):
        unpack_frme(blob + b"extra")
