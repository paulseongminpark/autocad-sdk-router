#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ir_builder  # type: ignore
import ir_identity  # type: ignore


_EXTERNAL_RUNS = Path("D:/dev/99_tools/autocad-sdk-router/runs")
_MCP_VERDICT_PRE = _EXTERNAL_RUNS / "mcp_verdict_20260706" / "pre" / "dwg_graph_ir.json"
_MCP_VERDICT_POST = _EXTERNAL_RUNS / "mcp_verdict_20260706" / "post" / "dwg_graph_ir.json"
_CAPSTONE_CENSUS_IR = _EXTERNAL_RUNS / "capstone_composed_20260706" / "census" / "dwg_graph_ir.json"
_CAPSTONE_REGEN_POST = _EXTERNAL_RUNS / "capstone_composed_20260706" / "regen" / "post" / "dwg_graph_ir.json"


def _source_meta() -> dict:
    return {
        "dwg_path": "staging/identity/input.dwg",
        "original_path": "tests/fixtures/native_sample.dwg",
        "dwg_name": "input.dwg",
        "format": "dwg",
        "byte_size": 123,
        "sha256": "0" * 64,
        "extractor": "fixture_synthetic",
        "engine_tier": "native_arx",
        "route": "dwg_truth_autocad",
    }


def _build_extract_ir(entities: list[dict]) -> dict:
    return ir_builder.build_ir_from_extract(
        {
            "schema": "ariadne.dwg_geometry_extract.v1",
            "extractor": "fixture_synthetic",
            "route": "dwg_truth_autocad",
            "summary": {"modelspace_count": len(entities)},
            "entities": entities,
        },
        summary=None,
        source_meta=_source_meta(),
    )


def _spec_declared_ir_version() -> str:
    text = (Path(_REPO) / "docs" / "DWG_GRAPH_IR_SPEC.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("Current producer version:"):
            return line.split("`")[1]
    raise AssertionError("DWG_GRAPH_IR_SPEC.md missing 'Current producer version:' line")


class TestStableIdEmission(unittest.TestCase):
    def test_float_normalization_collapses_epsilon_noise(self):
        entity_a = {
            "handle": "100",
            "type": "LINE",
            "layer": "0",
            "geometry": {
                "kind": "line",
                "start": {"x": 0.0, "y": 0.0, "z": 0.0},
                "end": {"x": 10.0, "y": 1.0, "z": 0.0},
            },
        }
        entity_b = {
            "handle": "101",
            "type": "LINE",
            "layer": "0",
            "geometry": {
                "kind": "line",
                "start": {"x": 0.0, "y": 0.0, "z": 0.0},
                "end": {"x": 10.0 + 4e-7, "y": 1.0 - 4e-7, "z": 0.0},
            },
        }

        ir_a = _build_extract_ir([entity_a])
        ir_b = _build_extract_ir([entity_b])

        self.assertEqual(ir_a["entities"][0]["stable_id"], ir_b["entities"][0]["stable_id"])
        self.assertEqual(ir_a["entities"][0]["stable_id_ordinal"], 0)
        self.assertEqual(ir_b["entities"][0]["stable_id_ordinal"], 0)

    def test_viewport_managed_fields_are_excluded_from_stable_id(self):
        entity_a = {
            "handle": "200",
            "type": "VIEWPORT",
            "layer": "0",
            "geometry": {
                "kind": "viewport",
                "center": {"x": 100.0, "y": 50.0, "z": 0.0},
                "height": 25.0,
                "width": 50.0,
                "view_direction": {"x": 0.0, "y": 0.0, "z": 1.0},
            },
        }
        entity_b = copy.deepcopy(entity_a)
        entity_b["handle"] = "201"
        entity_b["geometry"]["center"] = {"x": 21.320188017861092, "y": 11.222682400458831, "z": 0.0}
        entity_b["geometry"]["height"] = 25.401645837425974
        entity_b["geometry"]["width"] = 44.846057660446235

        ir_a = _build_extract_ir([entity_a])
        ir_b = _build_extract_ir([entity_b])

        self.assertEqual(ir_a["entities"][0]["stable_id"], ir_b["entities"][0]["stable_id"])

    def test_duplicate_entities_share_stable_id_but_get_handle_sorted_ordinals(self):
        ir = _build_extract_ir(
            [
                {
                    "handle": "300",
                    "type": "LINE",
                    "layer": "DUP",
                    "geometry": {
                        "kind": "line",
                        "start": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "end": {"x": 1.0, "y": 0.0, "z": 0.0},
                    },
                },
                {
                    "handle": "2FF",
                    "type": "LINE",
                    "layer": "DUP",
                    "geometry": {
                        "kind": "line",
                        "start": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "end": {"x": 1.0, "y": 0.0, "z": 0.0},
                    },
                },
            ]
        )

        by_handle = {entity["handle"]: entity for entity in ir["entities"]}
        self.assertEqual(by_handle["2FF"]["stable_id"], by_handle["300"]["stable_id"])
        self.assertEqual(by_handle["2FF"]["stable_id_ordinal"], 0)
        self.assertEqual(by_handle["300"]["stable_id_ordinal"], 1)

    def test_emitted_ir_version_matches_spec_declared_version(self):
        ir = ir_builder.make_fixture_ir()
        self.assertEqual(ir["ir_version"], _spec_declared_ir_version())


class TestIrIdentityMatcher(unittest.TestCase):
    def test_matcher_reports_moved_added_and_removed_entities(self):
        pre = _build_extract_ir(
            [
                {
                    "handle": "010",
                    "type": "LINE",
                    "layer": "0",
                    "geometry": {
                        "kind": "line",
                        "start": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "end": {"x": 1.0, "y": 0.0, "z": 0.0},
                    },
                },
                {
                    "handle": "011",
                    "type": "CIRCLE",
                    "layer": "0",
                    "geometry": {
                        "kind": "circle",
                        "center": {"x": 5.0, "y": 5.0, "z": 0.0},
                        "radius": 2.0,
                    },
                },
            ]
        )
        post = _build_extract_ir(
            [
                {
                    "handle": "0A0",
                    "type": "LINE",
                    "layer": "0",
                    "geometry": {
                        "kind": "line",
                        "start": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "end": {"x": 1.0, "y": 0.0, "z": 0.0},
                    },
                },
                {
                    "handle": "0A1",
                    "type": "ARC",
                    "layer": "0",
                    "geometry": {
                        "kind": "arc",
                        "center": {"x": 2.0, "y": 2.0, "z": 0.0},
                        "radius": 1.0,
                        "start_angle": 0.0,
                        "end_angle": 1.57,
                    },
                },
            ]
        )

        report = ir_identity.match_ir_documents(pre, post)

        self.assertEqual(report["summary"]["matched"], 1)
        self.assertEqual(report["summary"]["moved"], 1)
        self.assertEqual(report["summary"]["added"], 1)
        self.assertEqual(report["summary"]["removed"], 1)
        self.assertEqual(len(report["lineage"]), 3)
        moved = [row for row in report["lineage"] if row["status"] == "moved"]
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0]["pre_handle"], "010")
        self.assertEqual(moved[0]["post_handle"], "0A0")

    def test_cli_writes_report_json(self):
        pre = _build_extract_ir(
            [
                {
                    "handle": "100",
                    "type": "LINE",
                    "layer": "0",
                    "geometry": {
                        "kind": "line",
                        "start": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "end": {"x": 1.0, "y": 0.0, "z": 0.0},
                    },
                }
            ]
        )
        post = _build_extract_ir(
            [
                {
                    "handle": "101",
                    "type": "LINE",
                    "layer": "0",
                    "geometry": {
                        "kind": "line",
                        "start": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "end": {"x": 1.0, "y": 0.0, "z": 0.0},
                    },
                }
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            pre_path = os.path.join(tmp, "pre.json")
            post_path = os.path.join(tmp, "post.json")
            out_path = os.path.join(tmp, "report.json")
            Path(pre_path).write_text(json.dumps(pre), encoding="utf-8")
            Path(post_path).write_text(json.dumps(post), encoding="utf-8")

            rc = ir_identity.main(["--pre", pre_path, "--post", post_path, "--out", out_path])

            self.assertEqual(rc, 0)
            report = json.loads(Path(out_path).read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["matched"], 1)
            self.assertEqual(report["summary"]["moved"], 1)


class TestRealArtifactSmoke(unittest.TestCase):
    def test_mcp_verdict_pair(self):
        if not (_MCP_VERDICT_PRE.exists() and _MCP_VERDICT_POST.exists()):
            self.skipTest("mcp_verdict_20260706 IR pair missing")

        report = ir_identity.match_ir_paths(str(_MCP_VERDICT_PRE), str(_MCP_VERDICT_POST))

        self.assertEqual(report["summary"]["matched"], 21747)
        self.assertEqual(report["summary"]["added"], 2)
        self.assertEqual(report["summary"]["removed"], 0)
        self.assertEqual(report["summary"]["moved"], 0)

    def test_capstone_regen_pair(self):
        if not (_CAPSTONE_CENSUS_IR.exists() and _CAPSTONE_REGEN_POST.exists()):
            self.skipTest("capstone_composed_20260706 census/regen IR pair missing")

        report = ir_identity.match_ir_paths(str(_CAPSTONE_CENSUS_IR), str(_CAPSTONE_REGEN_POST))

        self.assertEqual(report["summary"]["matched"], 7)
        self.assertEqual(report["summary"]["added"], 0)
        self.assertEqual(report["summary"]["removed"], 21740)
        self.assertEqual(report["summary"]["moved"], 7)


if __name__ == "__main__":
    unittest.main()
