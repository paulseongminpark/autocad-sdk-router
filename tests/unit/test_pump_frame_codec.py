#!/usr/bin/env python
"""CADAGENT pump wire-codec contract + sequential-loop simulation (pure Python).

This EXTENDS tests/integration/test_live_arx_pump.py (which already covers the
basic encode/decode roundtrip, multi-frame split, partial-frame, and a UTF-8
body). It does NOT duplicate those; it adds the parts of the C++ wire contract
that were previously unverified in Python:

  * the length-prefix BOUNDARY rules the C++ pump enforces in ariadneCadAgentPump:
        if (n == 0 || n > (1u << 20)) break;
    i.e. a 0-length frame and an oversized-length frame (> 1 MiB) must both be
    treated as a hard stop, not parsed.
  * a faithful re-implementation of the main-thread server LOOP (read frame ->
    dispatch -> write frame, until a dispatch sets stop), driven by a sequence
    of request frames, asserting (a) response ORDER matches request order, and
    (b) live.stop ends the loop and nothing after it is served.

All pure stdlib + pytest. No AutoCAD, no subprocess, fully deterministic. The
codec here is the single wire contract both the C++ pump (pumpWriteFrame /
pumpReadExact in AriadneNativeJob.cpp) and every pipe client must agree on:
a 4-byte little-endian uint32 length prefix + UTF-8 JSON body, both directions.
"""
from __future__ import annotations

import json
import struct

import pytest

# Mirror of the C++ guard constant in ariadneCadAgentPump:
#   if (n == 0 || n > (1u << 20)) break;
MAX_FRAME_BYTES = 1 << 20  # 1 MiB


# --------------------------------------------------------------------------- #
# Wire codec — the exact format pumpWriteFrame / pumpReadExact implement.
# --------------------------------------------------------------------------- #
def encode_frame(obj: dict) -> bytes:
    """4-byte LE uint32 length prefix + UTF-8 JSON body."""
    body = json.dumps(obj).encode("utf-8")
    return struct.pack("<I", len(body)) + body


class FrameError(Exception):
    pass


def read_frame(buf: bytes):
    """Decode ONE frame, enforcing the C++ pump's length-boundary rules.

    Returns (obj, rest). Raises FrameError on a length the C++ side would
    reject (0, or > 1 MiB) — those are hard-stop conditions, never bodies.
    Returns (None, buf) when the buffer does not yet hold a full frame.
    """
    if len(buf) < 4:
        return None, buf
    n = struct.unpack("<I", buf[:4])[0]
    if n == 0:
        raise FrameError("zero-length frame (C++ pump treats n==0 as stop)")
    if n > MAX_FRAME_BYTES:
        raise FrameError(f"oversized frame {n} > {MAX_FRAME_BYTES} (C++ pump aborts)")
    if len(buf) < 4 + n:
        return None, buf
    return json.loads(buf[4 : 4 + n].decode("utf-8")), buf[4 + n :]


# --------------------------------------------------------------------------- #
# 1. Frame-protocol round-trip + boundary rejection
# --------------------------------------------------------------------------- #
def test_roundtrip_preserves_object():
    frame = encode_frame({"op": "live.echo", "message": "hello"})
    n = struct.unpack("<I", frame[:4])[0]
    assert n == len(frame) - 4
    obj, rest = read_frame(frame)
    assert obj == {"op": "live.echo", "message": "hello"}
    assert rest == b""


def test_header_is_4_byte_little_endian():
    body = b'"x"'  # 3-byte JSON for a string; pick a body whose len we control
    frame = struct.pack("<I", len(body)) + body
    assert frame[:4] == bytes([len(body), 0, 0, 0])


def test_zero_length_frame_is_rejected():
    # The C++ pump: `if (n == 0 || n > (1u<<20)) break;` — a 0-length header is
    # a hard stop, not an empty body.
    zero = struct.pack("<I", 0)
    with pytest.raises(FrameError):
        read_frame(zero + b"trailing-should-not-be-read")


def test_oversized_length_is_rejected():
    # Header claims > 1 MiB. The C++ side aborts the loop before allocating.
    oversized = struct.pack("<I", MAX_FRAME_BYTES + 1)
    with pytest.raises(FrameError):
        read_frame(oversized + b"\x00" * 16)


def test_exactly_max_length_is_accepted():
    # Boundary is strict-greater (`n > (1u<<20)`), so exactly 1 MiB is legal.
    inner = "a" * (MAX_FRAME_BYTES - 2)  # 2 bytes for the surrounding quotes
    body = json.dumps(inner).encode("utf-8")
    assert len(body) == MAX_FRAME_BYTES
    frame = struct.pack("<I", len(body)) + body
    obj, rest = read_frame(frame)
    assert obj == inner
    assert rest == b""


def test_incomplete_body_returns_none_not_error():
    frame = encode_frame({"op": "live.status"})
    obj, rest = read_frame(frame[:-1])
    assert obj is None
    assert rest == frame[:-1]


def test_utf8_non_ascii_body_survives_framing():
    # Hangul payload — codepoint-level assertion (cp949 console artifacts are a
    # display issue, never a data issue; we verify the actual string).
    frame = encode_frame({"op": "live.echo", "message": "평면도"})
    obj, _ = read_frame(frame)
    assert obj["message"] == "평면도"
    assert obj["message"][0] == "평"  # U+D3C9, in the Hangul syllable block


# --------------------------------------------------------------------------- #
# 2. Queue / lifecycle — faithful re-implementation of the main-thread loop.
# --------------------------------------------------------------------------- #
def _pump_dispatch(req: dict):
    """Python mirror of pumpDispatch() in AriadneNativeJob.cpp (loop SHAPE only)."""
    op = req.get("op", "")
    out = {"schema": "ariadne.cad_pump_frame.v1", "op": op}
    if op == "live.echo":
        out["status"] = "ok"
        out["echo"] = req.get("message", "")
        return out, False
    if op == "live.status":
        out["status"] = "ok"
        out["pump"] = "running"
        return out, False
    if op == "live.list_documents":
        out["status"] = "ok"
        out["documents"] = [{"working_database": False}]
        return out, False
    if op == "live.stop":
        out["status"] = "ok"
        out["stopped"] = True
        return out, True
    out["status"] = "not_implemented"
    return out, False


def _run_server(request_stream: bytes):
    """Mirror of the while(!stop) loop in ariadneCadAgentPump."""
    responses = []
    buf = request_stream
    stop = False
    while not stop:
        obj, buf = read_frame(buf)
        if obj is None:  # ran out of complete frames (== pipe read fails -> break)
            break
        resp, stop = _pump_dispatch(obj)
        responses.append(resp)
    return responses


def test_sequential_requests_served_in_order():
    stream = (
        encode_frame({"op": "live.echo", "message": "one"})
        + encode_frame({"op": "live.status"})
        + encode_frame({"op": "live.list_documents"})
        + encode_frame({"op": "live.stop"})
    )
    responses = _run_server(stream)
    ops = [r["op"] for r in responses]
    assert ops == ["live.echo", "live.status", "live.list_documents", "live.stop"]
    assert responses[0]["echo"] == "one"
    assert responses[1]["pump"] == "running"
    assert responses[-1]["stopped"] is True
    assert all(r["schema"] == "ariadne.cad_pump_frame.v1" for r in responses)


def test_stop_ends_loop_and_nothing_after_is_served():
    stream = (
        encode_frame({"op": "live.echo", "message": "before"})
        + encode_frame({"op": "live.stop"})
        + encode_frame({"op": "live.echo", "message": "after-1"})
        + encode_frame({"op": "live.echo", "message": "after-2"})
    )
    responses = _run_server(stream)
    assert [r["op"] for r in responses] == ["live.echo", "live.stop"]
    echoes = [r.get("echo") for r in responses if r["op"] == "live.echo"]
    assert echoes == ["before"]
    assert "after-1" not in echoes and "after-2" not in echoes


def test_unknown_op_does_not_stop_loop():
    stream = (
        encode_frame({"op": "live.bogus"})
        + encode_frame({"op": "live.stop"})
    )
    responses = _run_server(stream)
    assert responses[0]["status"] == "not_implemented"
    assert responses[0]["op"] == "live.bogus"
    assert responses[1]["stopped"] is True


def test_loop_breaks_on_truncated_trailing_frame():
    good = encode_frame({"op": "live.echo", "message": "ok"})
    truncated = struct.pack("<I", 50) + b"{partial"  # claims 50 bytes, supplies 8
    responses = _run_server(good + truncated)
    assert [r["op"] for r in responses] == ["live.echo"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
