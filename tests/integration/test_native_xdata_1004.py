#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#50 regression: native rich inspect must preserve code-1004 XDATA bytes.

The committed DWG contains one LINE with one 24-byte code-1004 XDATA row.
This test exercises the public ``cadctl.Cad.inspect`` boundary, which stages a
copy and routes ``inspect.database.graph`` through the native AutoCAD lane.
It is opt-in because a real AutoCAD 2027 host is required; the source-level
classification tripwire in ``test_xdata_extract.py`` runs on every machine.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
for candidate in (str(ROOT), str(TOOLS)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

FIXTURE = ROOT / "tests" / "fixtures" / "xdata_1004_binary_24bytes.dwg"
EXPECTED_SHA256 = "529373624b0bb388f21ffbb58a3a15c0da3d09d80eb51d0ce8a9523ef900e39a"
EXPECTED_HEX = bytes(range(24)).hex()
ACCORECONSOLE = Path(r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe")
RUN_ROOT = Path(r"D:\runs\autocad-sdk-router\pytest")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _code_rows(value: object, code: int) -> list[dict]:
    rows: list[dict] = []
    if isinstance(value, dict):
        if value.get("code") == code:
            rows.append(value)
        for child in value.values():
            rows.extend(_code_rows(child, code))
    elif isinstance(value, list):
        for child in value:
            rows.extend(_code_rows(child, code))
    return rows


@unittest.skipUnless(
    os.environ.get("CADOS_LIVE") == "1" and ACCORECONSOLE.is_file(),
    "SKIPPED_ENV: set CADOS_LIVE=1 on an AutoCAD 2027 host",
)
class TestNativeXdata1004(unittest.TestCase):
    def test_rich_inspect_reads_binary_row_without_process_failure(self) -> None:
        self.assertTrue(FIXTURE.is_file())
        self.assertEqual(_sha256(FIXTURE), EXPECTED_SHA256)
        size_before = FIXTURE.stat().st_size

        RUN_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="issue50_", dir=RUN_ROOT) as out_dir:
            import cadctl

            envelope = cadctl.Cad().inspect(
                str(FIXTURE), out_dir, mode="rich", include_rich=True
            )
            self.assertEqual(envelope.get("schema"), "ariadne.cadctl.inspect.v1")
            self.assertEqual(envelope.get("status"), "ok", envelope.get("reason"))
            ir_path = Path(str(envelope.get("dwg_graph_ir") or ""))
            self.assertTrue(ir_path.is_file())
            ir = json.loads(ir_path.read_text(encoding="utf-8-sig"))
            self.assertEqual(len(ir.get("entities") or []), 1)

            rows = _code_rows(ir, 1004)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].get("value_kind"), "binary")
            self.assertEqual(rows[0].get("byte_count"), 24)
            self.assertEqual(rows[0].get("value"), EXPECTED_HEX)

        self.assertEqual(_sha256(FIXTURE), EXPECTED_SHA256)
        self.assertEqual(FIXTURE.stat().st_size, size_before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
