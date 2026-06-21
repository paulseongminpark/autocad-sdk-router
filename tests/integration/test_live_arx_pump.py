#!/usr/bin/env python
"""Live ARX named-pipe pump (CADAGENT_PUMP) — protocol unit test (always runs)
+ headless live round-trip integration test (env-gated on CADOS_LIVE=1).

The pump is a main-thread, blocking, length-prefixed-JSON named-pipe server built
into the native module (.crx / versioned .arx). The wire protocol is a 4-byte
little-endian uint32 length prefix + UTF-8 JSON body, in both directions. Ops:
live.echo / live.status / live.list_documents / live.stop.

- TestPumpFrameProtocol: pure-Python encode/decode roundtrip of the exact wire
  format (no AutoCAD); always runs, locks the protocol contract.
- TestLiveArxPumpRoundTrip: spawns accoreconsole running CADAGENT_PUMP and drives
  it with a pipe client; SKIPPED unless CADOS_LIVE=1 and accoreconsole + the .crx
  are present (so the headless CI suite never depends on AutoCAD).
"""
from __future__ import annotations

import json
import os
import struct
import sys
import time
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_ACCORE = r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe"
_BIN = _REPO / "src" / "Ariadne.AcadNative" / "bin" / "x64" / "Release"
_GOLDEN = _REPO / "staging" / "dwg_20260617_191504" / "input.dwg"


def _encode_frame(op: str, **kw) -> bytes:
    body = json.dumps({"op": op, **kw}).encode("utf-8")
    return struct.pack("<I", len(body)) + body


def _decode_frame(buf: bytes):
    """Decode one length-prefixed frame from a bytes buffer; returns (obj, rest)."""
    if len(buf) < 4:
        return None, buf
    n = struct.unpack("<I", buf[:4])[0]
    if len(buf) < 4 + n:
        return None, buf
    return json.loads(buf[4:4 + n].decode("utf-8")), buf[4 + n:]


class TestPumpFrameProtocol(unittest.TestCase):
    """The wire contract the C++ pump and any client must agree on."""

    def test_roundtrip_echo(self):
        frame = _encode_frame("live.echo", message="hello")
        # header is 4-byte LE length
        n = struct.unpack("<I", frame[:4])[0]
        self.assertEqual(n, len(frame) - 4)
        obj, rest = _decode_frame(frame)
        self.assertEqual(obj["op"], "live.echo")
        self.assertEqual(obj["message"], "hello")
        self.assertEqual(rest, b"")

    def test_multiple_frames_in_stream(self):
        stream = _encode_frame("live.status") + _encode_frame("live.stop")
        obj1, rest = _decode_frame(stream)
        obj2, rest2 = _decode_frame(rest)
        self.assertEqual(obj1["op"], "live.status")
        self.assertEqual(obj2["op"], "live.stop")
        self.assertEqual(rest2, b"")

    def test_partial_frame_returns_none(self):
        full = _encode_frame("live.echo", message="x")
        obj, rest = _decode_frame(full[:-1])  # one byte short
        self.assertIsNone(obj)
        self.assertEqual(rest, full[:-1])

    def test_utf8_body(self):
        # the pump returns UTF-8; non-ASCII payloads must survive the framing
        frame = _encode_frame("live.echo", message="평면도")
        obj, _ = _decode_frame(frame)
        self.assertEqual(obj["message"], "평면도")


class TestLiveArxPumpRoundTrip(unittest.TestCase):
    """Headless live pump: accoreconsole CADAGENT_PUMP + a pipe client."""

    def setUp(self):
        if os.environ.get("CADOS_LIVE") != "1":
            self.skipTest("SKIPPED_ENV: live pump test requires CADOS_LIVE=1")
        if not os.path.isfile(_ACCORE):
            self.skipTest(f"SKIPPED_ENV: accoreconsole not found at {_ACCORE}")
        crx = _BIN / "Ariadne.AcadNative.crx"
        dbx = _BIN / "Ariadne.AcadNativeDbx.dbx"
        if not (crx.is_file() and dbx.is_file()):
            self.skipTest("SKIPPED_ENV: native .crx/.dbx not built")
        if not _GOLDEN.is_file():
            self.skipTest("SKIPPED_FIXTURE: golden DWG absent")

    def test_pump_echo_status_list_stop(self):
        import shutil
        import subprocess

        crx = (_BIN / "Ariadne.AcadNative.crx").as_posix()
        dbx = (_BIN / "Ariadne.AcadNativeDbx.dbx").as_posix()
        test = _REPO / "runs" / "m02_pump_test_pytest"
        test.mkdir(parents=True, exist_ok=True)
        staged = test / "input.dwg"
        shutil.copy2(_GOLDEN, staged)
        scr = test / "pump.scr"
        scr.write_text(
            '(setvar "SECURELOAD" 0)\n(setvar "FILEDIA" 0)\n(setvar "CMDECHO" 0)\n'
            f'(arxload "{dbx}")\n(arxload "{crx}")\nCADAGENT_PUMP\nQUIT\n',
            encoding="ascii",
        )
        pipe = r"\\.\pipe\ariadne_cad_pump_pytest"
        env = dict(os.environ, ARIADNE_PUMP_PIPE=pipe, ARIADNE_PUMP_TIMEOUT="45")
        proc = subprocess.Popen(
            [_ACCORE, "/i", str(staged), "/s", str(scr)],
            cwd=str(test), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            fh = None
            for _ in range(90):
                try:
                    fh = open(pipe, "r+b", buffering=0)
                    break
                except OSError:
                    time.sleep(0.5)
            self.assertIsNotNone(fh, "client could not connect to the pump pipe")

            def call(op, **kw):
                fh.write(_encode_frame(op, **kw))
                fh.flush()
                hdr = fh.read(4)
                n = struct.unpack("<I", hdr)[0]
                return json.loads(fh.read(n).decode("utf-8"))

            echo = call("live.echo", message="PYTEST_PUMP")
            status = call("live.status")
            docs = call("live.list_documents")
            stop = call("live.stop")
            fh.close()

            self.assertEqual(echo.get("echo"), "PYTEST_PUMP")
            self.assertEqual(status.get("pump"), "running")
            self.assertTrue(status.get("has_database"))
            self.assertEqual(status.get("modelspace_entities"), 21747)
            self.assertEqual(docs.get("status"), "ok")
            self.assertTrue(stop.get("stopped"))
        finally:
            try:
                proc.wait(timeout=60)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    unittest.main()
