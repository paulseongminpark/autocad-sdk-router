#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import verify_sheet_dissection as tool  # noqa: E402


def _insert(handle: str, block_name: str, *, space: str = "paper", layout: str = "S1") -> dict:
    return {
        "handle": handle,
        "class": "AcDbBlockReference",
        "dxf_name": "INSERT",
        "owner_handle": "0",
        "space": space,
        "layout": layout,
        "layer": "0",
        "bbox": [0.0, 0.0, 0.0, 1.0, 1.0, 0.0],
        "geometry": {
            "kind": "block_reference",
            "block_name": block_name,
            "position": [0.0, 0.0, 0.0],
        },
        "source": {"extractor": "test", "engine_tier": "managed", "decoded": True},
    }


def _line(handle: str) -> dict:
    return {
        "handle": handle,
        "class": "AcDbLine",
        "dxf_name": "LINE",
        "owner_handle": "B1",
        "space": "block",
        "layer": "0",
        "bbox": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
        "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [1.0, 0.0, 0.0]},
        "source": {"extractor": "test", "engine_tier": "managed", "decoded": True},
    }


def _ir(block_defs: list[dict], entities: list[dict]) -> dict:
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "block_definitions": block_defs,
        "entities": entities,
    }


class TestAnalyze(unittest.TestCase):
    def test_matching_ir_has_no_findings(self):
        original = _ir(
            [{"name": "SHEET_A", "bbox": [0.0, 0.0, 0.0, 10.0, 5.0, 0.0], "def_entities": [_line("L1"), _line("L2")]}],
            [_insert("I1", "SHEET_A")],
        )
        replay = _ir(
            [{"name": "SHEET_A", "bbox": [0.0, 0.0, 0.0, 10.0, 5.0, 0.0], "def_entities": [_line("L9"), _line("L8")]}],
            [_insert("I9", "SHEET_A")],
        )

        report = tool.analyze(original, replay, threshold=0)

        self.assertEqual(report["summary"]["total_issues"], 0)
        self.assertEqual(report["summary"]["exit_code"], 0)
        self.assertEqual(report["def_entity_counts"]["original"], {"SHEET_A": 2})
        self.assertEqual(report["insert_comparison"]["SHEET_A"]["original"]["insert_count"], 1)
        self.assertEqual(report["per_sheet"]["S1"]["missing_blocks"], [])
        self.assertEqual(report["warnings"]["bbox_degenerate"], [])

    def test_missing_block_and_degenerate_bbox_are_reported(self):
        original = _ir(
            [
                {"name": "SHEET_A", "bbox": [0.0, 0.0, 0.0, 10.0, 5.0, 0.0], "def_entities": [_line("L1"), _line("L2")]},
                {"name": "*U15K", "bbox": [-320000000.0, 0.0, 0.0, -320000000.0, 0.0, 0.0],
                 "def_entities": [_line("U1"), _line("U2"), _line("U3")]},
            ],
            [_insert("I1", "SHEET_A"), _insert("I2", "*U15K")],
        )
        replay = _ir(
            [{"name": "SHEET_A", "bbox": [0.0, 0.0, 0.0, 10.0, 5.0, 0.0], "def_entities": [_line("L9"), _line("L8")]}],
            [_insert("I9", "SHEET_A")],
        )

        report = tool.analyze(original, replay, threshold=0)

        self.assertEqual(report["summary"]["exit_code"], 1)
        self.assertEqual(report["summary"]["missing_block_count"], 1)
        self.assertEqual(report["insert_comparison"]["*U15K"]["delta"]["insert_count"], -1)
        self.assertEqual(report["insert_comparison"]["*U15K"]["delta"]["def_entities"], -3)
        self.assertEqual(report["per_sheet"]["S1"]["missing_blocks"], ["*U15K"])
        self.assertEqual(report["per_sheet"]["S1"]["def_entity_delta"], -3)
        self.assertEqual(len(report["warnings"]["bbox_degenerate"]), 1)
        self.assertEqual(report["warnings"]["bbox_degenerate"][0]["block_name"], "*U15K")


class TestCli(unittest.TestCase):
    def test_cli_writes_report_and_exits_one_when_threshold_exceeded(self):
        original = _ir(
            [{"name": "*U15K", "bbox": [1.0, 1.0, 0.0, 1.0, 1.0, 0.0], "def_entities": [_line("U1")]}],
            [_insert("I1", "*U15K")],
        )
        replay = _ir([], [])

        with tempfile.TemporaryDirectory() as tmp:
            original_path = os.path.join(tmp, "original.json")
            replay_path = os.path.join(tmp, "replay.json")
            report_path = os.path.join(tmp, "report.json")
            with open(original_path, "w", encoding="utf-8") as fh:
                json.dump(original, fh)
            with open(replay_path, "w", encoding="utf-8") as fh:
                json.dump(replay, fh)

            buf = StringIO()
            with redirect_stdout(buf):
                rc = tool.main([original_path, replay_path, "--report", report_path, "--threshold", "0"])

            self.assertEqual(rc, 1)
            self.assertEqual(
                buf.getvalue().strip(),
                "sheet_dissection issues=2 missing_blocks=1 degenerate_bbox=1 threshold=0",
            )
            with open(report_path, "r", encoding="utf-8") as fh:
                report = json.load(fh)
            self.assertEqual(report["summary"]["exit_code"], 1)
            self.assertEqual(report["summary"]["total_issues"], 2)


if __name__ == "__main__":
    unittest.main()
