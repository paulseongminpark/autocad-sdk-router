#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""corpus_ledger.build_ledger correctness gate (synthetic run dir, no live corpus).

Intent (WHY):
  corpus_ledger.py turns a corpus-batch run directory into a JSONL ledger
  that tools/corpus_query.py folds into aggregates and z-score outliers.
  Two failure modes would corrupt that downstream analysis silently:
  (1) emitting by_layer/by_entity_type from a *truncated* entities list,
      which would make corpus_query treat a partial sample as the file's
      whole population; and
  (2) a row shape that corpus_query.load_ledger cannot parse back off disk
      (encoding drift, malformed JSON lines).
  This test builds a small SYNTHETIC run dir (no dependency on the real
  166-file corpus_smoke_20260707 run) with one ok/non-truncated file and
  one non-ok/truncated file, then asserts both the in-memory rows and the
  on-disk JSONL round-trip (via corpus_query.load_ledger) are correct.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO_TOOLS = os.path.normpath(os.path.join(_THIS, "..", "..", "tools"))

sys.path.insert(0, _REPO_TOOLS)

import corpus_ledger  # noqa: E402
import corpus_query  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_op_stdout(file_dir: Path, op_dirname: str, result_payload: dict) -> None:
    stdout_path = file_dir / op_dirname / "stdout.txt"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"execution": {"engine_output": {"result": {"result": result_payload}}}}
    stdout_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def _write_result_ref(path: Path, result_payload: dict) -> None:
    # mirrors the native job's own artifact: utf-8-sig, payload under "result".
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"schema": "ariadne.autocad_native_job_result.v1", "engine": "native_objectarx",
           "operation": "inspect.entities", "result": result_payload, "status": "ok"}
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8-sig")


def _make_synthetic_run(run_dir: Path) -> None:
    # File 0000: ok, non-truncated entities -> expect by_layer/by_entity_type.
    # Its entities op carries BOTH a result_ref artifact (clean Korean layer
    # name, utf-8-sig -- as the native job writes it) and a stdout.txt whose
    # cp949-console pipeline baked U+FFFD into the same layer name. The
    # builder must prefer result_ref (wave-7 corpus audit: stdout-sourced
    # ledgers corrupted Korean layer keys while every result_ref was clean).
    file0 = run_dir / "0000_ok_file"
    ref_path = file0 / "native_result_entities.json"
    _write_json(
        file0 / "result_envelope.json",
        {
            "source_path": r"C:\corpus\ok_file.dwg",
            "ordinal": 0,
            "status": "ok",
            "error_class": None,
            "reason": None,
            "source_sha256_match": True,
            "worker_exit_code": 0,
            "ops_run": [
                {"operation": "inspect.database.summary", "elapsed_sec": 1.2, "status": "ok"},
                {"operation": "inspect.entities", "elapsed_sec": 0.8, "status": "ok",
                 "result_ref": str(ref_path)},
            ],
        },
    )
    _write_op_stdout(
        file0,
        "op_00_inspect_database_summary",
        {"modelspace_entities": 3, "layers": 2, "blocks": 0, "layouts": 1, "insunits": 4},
    )
    _write_result_ref(
        ref_path,
        {
            "truncated": False,
            "matching_entities": 3,
            "entities": [
                {"dxf_name": "LINE", "layer": "0"},
                {"dxf_name": "LINE", "layer": "벽체"},
                {"dxf_name": "CIRCLE", "layer": "벽체"},
            ],
        },
    )
    _write_op_stdout(
        file0,
        "op_02_inspect_entities",
        {
            "truncated": False,
            "matching_entities": 3,
            "entities": [
                {"dxf_name": "LINE", "layer": "0"},
                {"dxf_name": "LINE", "layer": "��체"},
                {"dxf_name": "CIRCLE", "layer": "��체"},
            ],
        },
    )

    # File 0001: non-ok status, truncated entities -> no by_layer/by_entity_type.
    file1 = run_dir / "0001_bad_file"
    _write_json(
        file1 / "result_envelope.json",
        {
            "source_path": r"C:\corpus\bad_file.dwg",
            "ordinal": 1,
            "status": "error",
            "error_class": "engine_timeout",
            "reason": "accoreconsole did not exit within timeout",
            "source_sha256_match": True,
            "worker_exit_code": 1,
            "ops_run": [
                {"operation": "inspect.database.summary", "elapsed_sec": 5.0, "status": "ok"},
                {"operation": "inspect.entities", "elapsed_sec": 30.0, "status": "timeout"},
            ],
        },
    )
    _write_op_stdout(
        file1,
        "op_00_inspect_database_summary",
        {"modelspace_entities": 50000, "layers": 40, "blocks": 12, "layouts": 3, "insunits": 4},
    )
    _write_op_stdout(
        file1,
        "op_02_inspect_entities",
        {
            "truncated": True,
            "matching_entities": 50000,
            "entities": [{"dxf_name": "LINE", "layer": "0"}] * 5,
        },
    )


class TestBuildLedger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.run_dir = Path(cls.tmpdir.name) / "synthetic_run"
        cls.run_dir.mkdir(parents=True)
        _make_synthetic_run(cls.run_dir)
        cls.rows = corpus_ledger.build_ledger(cls.run_dir)

    @classmethod
    def tearDownClass(cls):
        cls.tmpdir.cleanup()

    def test_row_count_matches_synthetic_files(self):
        self.assertEqual(len(self.rows), 2)

    def test_required_fields_present_on_every_row(self):
        required = {
            "source_path", "status", "error_class", "reason", "ordinal",
            "source_sha256_match", "worker_exit_code", "op_elapsed_sec", "op_status",
        }
        for row in self.rows:
            missing = required - row.keys()
            self.assertEqual(missing, set(), f"row {row.get('ordinal')} missing {missing}")

    def test_entity_count_extracted_from_op00_summary(self):
        row0 = self.rows[0]
        self.assertEqual(row0["entity_count"], 3)
        row1 = self.rows[1]
        self.assertEqual(row1["entity_count"], 50000)

    def test_by_entity_type_present_only_for_non_truncated_row(self):
        row0, row1 = self.rows
        self.assertFalse(row0["entities_truncated"])
        self.assertIn("by_entity_type", row0)
        self.assertIn("by_layer", row0)
        self.assertEqual(row0["by_entity_type"], {"LINE": 2, "CIRCLE": 1})
        self.assertEqual(row0["by_layer"], {"0": 1, "벽체": 2})

        self.assertTrue(row1["entities_truncated"])
        self.assertNotIn("by_entity_type", row1)
        self.assertNotIn("by_layer", row1)

    def test_result_ref_preferred_over_corrupted_stdout(self):
        # file0 ships a clean utf-8-sig result_ref AND a mojibake stdout for
        # the same op; the clean Korean layer name must win, and no U+FFFD
        # may leak into ledger keys (the wave-7 corpus-audit regression).
        row0 = self.rows[0]
        self.assertIn("벽체", row0["by_layer"])
        for key in list(row0["by_layer"]) + list(row0["by_entity_type"]):
            self.assertNotIn("�", key,
                             "ledger keys must come from the clean result_ref artifact")

    def test_stdout_fallback_used_when_no_result_ref(self):
        # file1's entities op has no result_ref -> the stdout.txt fallback
        # must still populate truncation metadata.
        row1 = self.rows[1]
        self.assertTrue(row1["entities_truncated"])
        self.assertEqual(row1["matching_entities"], 50000)

    def test_op_status_propagated(self):
        row0, row1 = self.rows
        self.assertEqual(row0["op_status"]["inspect.entities"], "ok")
        self.assertEqual(row1["op_status"]["inspect.entities"], "timeout")
        self.assertEqual(row1["status"], "error")

    def test_jsonl_round_trip_through_corpus_query_load_ledger(self):
        out_path = self.run_dir / "ledger.jsonl"
        with open(out_path, "w", encoding="utf-8") as fh:
            for row in self.rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

        loaded = corpus_query.load_ledger(out_path)
        self.assertEqual(len(loaded), 2)

        summary = corpus_query.summarize(loaded)
        self.assertEqual(summary["files"], 2)
        self.assertEqual(summary["ok"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["total_entities"], 50003)
        # only the non-truncated row's histogram should have folded in.
        self.assertEqual(summary["by_entity_type"], {"LINE": 2, "CIRCLE": 1})
        self.assertEqual(summary["by_layer"], {"0": 1, "벽체": 2})


if __name__ == "__main__":
    unittest.main()
