#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.e2.qualification._phase2_geometry import audit_unsupported_visibility  # noqa: E402
from tools.e2.qualification._phase2_review import (  # noqa: E402
    build_hypotheses,
    build_review_queue,
    fuse_jury,
)


def _native_with_clipped_and_visible_circle() -> dict:
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "coverage_level": "native_full",
        "symbol_tables": {
            "block_table_records": [
                {"handle": "1F", "name": "*Model_Space", "origin": [0, 0, 0]}
            ]
        },
        "entities": [
            {
                "handle": "I1",
                "dxf_name": "INSERT",
                "block_record_handle": "B1",
                "layer": "0",
                "geometry": {"kind": "insert", "position": [100, 0, 0], "scale": [1, 1, 1], "rotation": 0},
                "xclip": {
                    "enabled": True,
                    "boundary_block": [[-5, -5], [15, 15]],
                    "boundary_wcs": [[95, -5, 0], [115, 15, 0]],
                    "inverted": False,
                },
            },
            {
                "handle": "I2",
                "dxf_name": "INSERT",
                "block_record_handle": "B1",
                "layer": "0",
                "geometry": {"kind": "insert", "position": [200, 0, 0], "scale": [1, 1, 1], "rotation": 0},
                "xclip": {
                    "enabled": True,
                    "boundary_block": [[-200, 0], [-180, 20]],
                    "boundary_wcs": [[0, 0, 0], [20, 20, 0]],
                    "inverted": False,
                },
            },
        ],
        "block_definitions": [
            {
                "handle": "B1",
                "name": "circle-def",
                "origin": [0, 0, 0],
                "def_entities": [
                    {
                        "handle": "C1",
                        "dxf_name": "CIRCLE",
                        "layer": "SYMB",
                        "bbox": [0, 0, 0, 10, 10, 0],
                        "geometry": {"kind": "circle", "center": [5, 5, 0], "radius": 5},
                    }
                ],
            }
        ],
    }


def _hypothesis_fixture():
    seg_ir = {
        "drawing_id": "fixture",
        "segments": [
            {"handle": "A", "pts": [[0, 0], [100, 0]], "layer": "WALL"},
            {"handle": "B", "pts": [[0, 10], [100, 10]], "layer": "WALL"},
            {"handle": "C", "pts": [[0, 20], [100, 20]], "layer": "A-DIM"},
            {"handle": "D", "pts": [[200, 0], [300, 0]], "layer": "WALL"},
            {"handle": "E", "pts": [[200, 10], [300, 10]], "layer": "WALL"},
        ],
    }
    candidates = {
        "candidate_count": 5,
        "candidates": [
            {"placed_uid": handle, "score": 0.8, "evidence": {}}
            for handle in ("A", "B", "C", "D", "E")
        ],
        "wall_pair_records": [
            {"handles": ["A", "B"], "axis": [[0, 5], [100, 5]], "thickness": 10},
            {"handles": ["B", "C"], "axis": [[0, 15], [100, 15]], "thickness": 10},
            {"handles": ["D", "E"], "axis": [[200, 5], [300, 5]], "thickness": 10},
        ],
    }
    return seg_ir, candidates


def test_unsupported_visibility_is_one_sided_and_xclip_aware():
    result = audit_unsupported_visibility(_native_with_clipped_and_visible_circle())

    assert result["status"] == "PASS"
    assert result["counts"]["placed_unsupported_instances"] == 2
    assert result["counts"]["potentially_visible"] == 1
    assert result["counts"]["clipped_by_footprint_proof"] == 1
    assert result["potentially_visible_curve_or_region_types"] == ["CIRCLE"]


def test_hypotheses_account_every_candidate_once_and_do_not_merge_disjoint_pairs():
    seg_ir, candidates = _hypothesis_fixture()
    result = build_hypotheses(seg_ir, candidates)

    assert result["balance_ok"] is True
    assert result["accounted_candidate_count"] == 5
    assert result["hypothesis_count"] == 2
    assert sorted(row["member_count"] for row in result["hypotheses"]) == [2, 3]


def test_fusion_counts_shared_training_as_one_family_and_layer_cue_vetoes_silver():
    seg_ir, candidates = _hypothesis_fixture()
    hypotheses = build_hypotheses(seg_ir, candidates)
    base_scores = {
        "rules": {handle: 0.8 for handle in "ABCDE"},
        "gbdt": {handle: 0.92 for handle in "ABCDE"},
        "gnn": {handle: 0.94 for handle in "ABCDE"},
        "diagnostics": {},
    }
    scores = {
        "baseline": base_scores,
        "interventions": {
            name: base_scores
            for name in (
                "rotate_37_degrees",
                "translate_large_offset",
                "scale_units_x1000_consistent",
                "strip_layer_names",
                "split_every_segment_at_midpoint",
            )
        },
    }

    jury = fuse_jury(hypotheses, scores)

    assert jury["independent_evidence_family_count"] == 2
    labels = {row["hypothesis_id"]: row["automatic_label"] for row in jury["results"]}
    dim_hypothesis = next(row["hypothesis_id"] for row in hypotheses["hypotheses"] if row["anti_wall_layer_cues"])
    clean_hypothesis = next(row["hypothesis_id"] for row in hypotheses["hypotheses"] if not row["anti_wall_layer_cues"])
    assert labels[dim_hypothesis] == "REVIEW"
    assert labels[clean_hypothesis] == "PROVISIONAL_SILVER_WALL"


def test_review_holdout_is_score_independent_and_disjoint():
    seg_ir, candidates = _hypothesis_fixture()
    hypotheses = build_hypotheses(seg_ir, candidates)
    base_scores = {juror: {handle: 0.9 for handle in "ABCDE"} for juror in ("rules", "gbdt", "gnn")}
    base_scores["diagnostics"] = {}
    scores = {"baseline": base_scores, "interventions": {"rotate_37_degrees": base_scores}}
    jury = fuse_jury(hypotheses, scores)
    queue = build_review_queue("fixture", hypotheses, jury, public_limit=1, audit_count=1, sealed_holdout_count=1)

    public_ids = {row["hypothesis_id"] for row in queue["public_queue"]}
    holdout_ids = {row["hypothesis_id"] for row in queue["sealed_holdout_queue"]}
    assert public_ids.isdisjoint(holdout_ids)
    assert all(row["jury"] is None for row in queue["sealed_holdout_queue"])


def test_phase2_schemas_are_valid_json_schemas():
    names = (
        "e2_model_assisted_spec.v1.schema.json",
        "e2_wall_hypotheses.v1.schema.json",
        "e2_jury_results.v1.schema.json",
        "e2_review_queue.v1.schema.json",
        "e2_phase2_receipt.v1.schema.json",
    )
    for name in names:
        schema = json.loads((REPO / "schemas" / name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
