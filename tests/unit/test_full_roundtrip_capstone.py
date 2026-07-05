#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/unit/test_full_roundtrip_capstone.py -- unit coverage for the pure
(no-CAD-engine) logic in tools/full_roundtrip_capstone.py: identity hashing,
certified-class classification, census rollup, IR filtering, record-diff arg
building, and the per-kind geometry-diff verdict rollup. Every live-runtime
function (run_census/run_regen_batch/ensure_blank_seed) needs a real
AutoCAD/accoreconsole host and is exercised by the LIVE capstone run instead
(see build_log.md), matching this repo's existing split between pure-logic
unit tests and DONE_NEEDS_RUNTIME live legs (op_roundtrip_probe's own test
suite follows the same split)."""
from __future__ import annotations

import hashlib
import importlib
import os
import sys

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.join(os.path.dirname(_THIS_DIR), "..", "tools")
_TOOLS_DIR = os.path.normpath(_TOOLS_DIR)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

frc = importlib.import_module("full_roundtrip_capstone")


# --------------------------------------------------------------------------- #
# sha256 / identity
# --------------------------------------------------------------------------- #

def test_sha256_file_missing_returns_none():
    assert frc.sha256_file(None) is None
    assert frc.sha256_file("Z:/does/not/exist.dwg") is None


def test_sha256_file_matches_hashlib(tmp_path):
    p = tmp_path / "a.bin"
    p.write_bytes(b"hello capstone")
    expected = hashlib.sha256(b"hello capstone").hexdigest()
    assert frc.sha256_file(str(p)) == expected


def test_check_identity_identical_files(tmp_path):
    a = tmp_path / "a.dwg"
    b = tmp_path / "b.dwg"
    a.write_bytes(b"same bytes")
    b.write_bytes(b"same bytes")
    result = frc.check_identity(str(a), str(b))
    assert result["identical"] is True
    assert result["exists_a"] and result["exists_b"]
    assert result["sha256_a"] == result["sha256_b"]


def test_check_identity_different_files(tmp_path):
    a = tmp_path / "a.dwg"
    b = tmp_path / "b.dwg"
    a.write_bytes(b"content one")
    b.write_bytes(b"content two, different")
    result = frc.check_identity(str(a), str(b))
    assert result["identical"] is False


def test_check_identity_missing_path_never_identical(tmp_path):
    a = tmp_path / "a.dwg"
    a.write_bytes(b"exists")
    result = frc.check_identity(str(a), str(tmp_path / "missing.dwg"))
    assert result["identical"] is False
    assert result["exists_b"] is False


# --------------------------------------------------------------------------- #
# classification
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("dxf,kind,expected_label", [
    ("LINE", "line", "line"),
    ("CIRCLE", "circle", "circle"),
    ("POLYLINE", "polygon_mesh", "polygonmesh"),
    ("POLYLINE", "poly_face_mesh", "polyfacemesh"),
    ("POLYLINE", "polyline", "polyline2d_or_polyline3d"),
    ("LEADER", "leader", "leader"),
    ("MULTILEADER", "leader", "mleader"),
    ("DIMENSION", "dimension", "dimension_all_subtypes"),
    ("INSERT", "block_reference", "insert"),
])
def test_classify_entity_bucket_certified(dxf, kind, expected_label):
    assert frc.classify_entity_bucket(dxf, kind) == expected_label


def test_classify_entity_bucket_leader_vs_mleader_disambiguated_by_dxf_name():
    # Both share kind=="leader" (ir_builder._NATIVE_CLASS_TO_DXF_KIND) -- dxf_name
    # is the only field that tells them apart; this is the whole reason
    # CERTIFIED_BUCKETS is keyed by the (dxf_name, kind) PAIR, not kind alone.
    assert frc.classify_entity_bucket("LEADER", "leader") != frc.classify_entity_bucket("MULTILEADER", "leader")


def test_classify_entity_bucket_known_out_of_class_reason():
    assert "a1-hatchread" in frc.classify_entity_bucket("HATCH", "hatch")
    assert "s0-asmprobe" in frc.classify_entity_bucket("3DSOLID", "solid")


def test_classify_entity_bucket_unmapped_native_class():
    assert frc.classify_entity_bucket("SOMETHING_WEIRD", "unsupported") == "unmapped_native_class"


def test_classify_entity_bucket_recognized_not_certified_default():
    assert frc.classify_entity_bucket("TOTALLY_UNKNOWN_TYPE", "totally_unknown_kind") == "recognized_not_certified"


# --------------------------------------------------------------------------- #
# census_report
# --------------------------------------------------------------------------- #

def _entity(dxf, kind, **geom_extra):
    return {"handle": "1", "dxf_name": dxf, "layer": "0",
           "geometry": {"kind": kind, **geom_extra}}


def test_census_report_splits_certified_and_out_of_class():
    ir = {
        "entities": [
            _entity("LINE", "line"), _entity("LINE", "line"),
            _entity("CIRCLE", "circle"),
            _entity("HATCH", "hatch"),
            _entity("SOMETHING", "unsupported"),
        ],
        "block_definitions": [],
        "symbol_tables": {"layers": [{"name": "0"}, {"name": "DIM"}]},
        "diagnostics": {"entities_by_type": {"LINE": 2, "CIRCLE": 1, "HATCH": 1, "SOMETHING": 1}},
    }
    report = frc.census_report(ir)
    assert report["modelspace_entity_total"] == 5
    assert report["certified_total"] == 3   # 2 line + 1 circle
    assert report["out_of_class_total"] == 2  # hatch + unsupported
    labels = {(row["dxf_name"], row["kind"]): row["label"] for row in report["by_bucket"]}
    assert labels[("LINE", "line")] == "line"
    assert labels[("SOMETHING", "unsupported")] == "unmapped_native_class"
    assert report["symbol_table_record_counts"]["layers"] == 2


def test_census_report_block_definitions_census_tolerates_either_key_name():
    ir = {
        "entities": [],
        "block_definitions": [
            {"name": "BLOCK_A", "entities": [_entity("LINE", "line")]},
            {"name": "BLOCK_B", "def_entities": [_entity("CIRCLE", "circle"), _entity("ARC", "arc")]},
        ],
        "symbol_tables": {},
    }
    report = frc.census_report(ir)
    assert report["block_definitions_count"] == 2
    assert report["block_definitions_entity_total"] == 3
    bucket_counts = {(row["dxf_name"], row["kind"]): row["count"] for row in report["block_definitions_by_bucket"]}
    assert bucket_counts[("LINE", "line")] == 1
    assert bucket_counts[("CIRCLE", "circle")] == 1
    assert bucket_counts[("ARC", "arc")] == 1


# --------------------------------------------------------------------------- #
# filter_ir_to_certified
# --------------------------------------------------------------------------- #

def test_filter_ir_to_certified_drops_out_of_class_and_preserves_certified():
    ir = {"entities": [_entity("LINE", "line"), _entity("HATCH", "hatch"), _entity("CIRCLE", "circle")]}
    filtered = frc.filter_ir_to_certified(ir)
    kinds = [(e["dxf_name"], e["geometry"]["kind"]) for e in filtered["entities"]]
    assert ("HATCH", "hatch") not in kinds
    assert ("LINE", "line") in kinds
    assert ("CIRCLE", "circle") in kinds
    # never mutates the input
    assert len(ir["entities"]) == 3


def test_filter_ir_to_certified_kinds_narrows_further():
    ir = {"entities": [_entity("LINE", "line"), _entity("CIRCLE", "circle")]}
    filtered = frc.filter_ir_to_certified(ir, kinds={"line"})
    kinds = [e["geometry"]["kind"] for e in filtered["entities"]]
    assert kinds == ["line"]


def test_filter_ir_to_certified_global_limit():
    ir = {"entities": [_entity("LINE", "line") for _ in range(10)]}
    filtered = frc.filter_ir_to_certified(ir, limit=3)
    assert len(filtered["entities"]) == 3


def test_filter_ir_to_certified_per_kind_limit():
    ir = {"entities": ([_entity("LINE", "line") for _ in range(5)]
                       + [_entity("CIRCLE", "circle") for _ in range(5)])}
    filtered = frc.filter_ir_to_certified(ir, per_kind_limit=2)
    by_kind = {}
    for e in filtered["entities"]:
        k = e["geometry"]["kind"]
        by_kind[k] = by_kind.get(k, 0) + 1
    assert by_kind == {"line": 2, "circle": 2}


# --------------------------------------------------------------------------- #
# layer/dimstyle op-args builders (against the REAL op_roundtrip_probe module
# -- LAYER_RECORD_FIELDS/DIMSTYLE_RECORD_FIELDS are plain constants, no CAD
# engine import-time dependency).
# --------------------------------------------------------------------------- #

def test_layer_op_args_from_record_only_declared_fields():
    orp = importlib.import_module("op_roundtrip_probe")
    record = {"name": "WALLS", "color_index": 3, "linetype": "CONTINUOUS",
             "handle": "ABC123", "true_color": "not-a-layer-record-field"}
    args = frc.layer_op_args_from_record(record, orp)
    assert args["name"] == "WALLS"
    assert args["color_index"] == 3
    assert args["linetype"] == "CONTINUOUS"
    assert "handle" not in args
    assert "true_color" not in args


def test_dimstyle_op_args_from_record_uses_fallback_if_constant_absent():
    class _FakeModWithoutConstant:
        pass
    record = {"name": "MYDIM", "dimtxt": 2.5, "dimasz": 3.0, "not_a_field": 1}
    args = frc.dimstyle_op_args_from_record(record, _FakeModWithoutConstant())
    assert args["name"] == "MYDIM"
    assert args["dimtxt"] == 2.5
    assert args["dimasz"] == 3.0
    assert "not_a_field" not in args


# --------------------------------------------------------------------------- #
# record_diff_report
# --------------------------------------------------------------------------- #

def test_record_diff_report_zero_diff_and_mismatch():
    records = [{"name": "A", "color_index": 1}, {"name": "B", "color_index": 2}]
    actual_ir = {"symbol_tables": {"layers": [
        {"name": "A", "color_index": 1},   # matches
        {"name": "B", "color_index": 99},  # mismatch
    ]}}

    def _diff_fn(expected, actual):
        if actual is None:
            return sorted(expected)
        return sorted(k for k, v in expected.items() if actual.get(k) != v)

    report = frc.record_diff_report("layer", records, actual_ir, table_key="layers",
                                    fields=("color_index",), diff_fn=_diff_fn)
    assert report["record_count"] == 2
    assert report["zero_diff_count"] == 1
    by_name = {row["name"]: row for row in report["rows"]}
    assert by_name["A"]["record_diff"] == []
    assert by_name["B"]["record_diff"] == ["color_index"]


def test_record_diff_report_missing_record_reports_all_fields():
    records = [{"name": "GHOST", "color_index": 5}]
    actual_ir = {"symbol_tables": {"layers": []}}

    def _diff_fn(expected, actual):
        return sorted(expected) if actual is None else []

    report = frc.record_diff_report("layer", records, actual_ir, table_key="layers",
                                    fields=("color_index",), diff_fn=_diff_fn)
    assert report["zero_diff_count"] == 0
    assert report["rows"][0]["record_diff"] == ["color_index"]


# --------------------------------------------------------------------------- #
# per_kind_verdict
# --------------------------------------------------------------------------- #

def test_per_kind_verdict_derives_diff0_from_pre_count_minus_modified_removed():
    pre_ir = {"entities": [_entity("LINE", "line") for _ in range(5)]}
    diff = {
        "diagnostics": {"comparison_basis": "geometry"},
        "summary": {"by_type": {"LINE": {"added": 0, "removed": 1, "modified": 1}}},
        "changed_handles": [
            {"handle": "h1", "change": "removed", "dxf_name": "LINE"},
            {"handle": "h2", "change": "modified", "dxf_name": "LINE",
             "fields": {"geometry": {"before": {}, "after": {}}}},
        ],
    }
    verdict = frc.per_kind_verdict(pre_ir, diff)
    row = next(r for r in verdict["rows"] if r["dxf_name"] == "LINE")
    assert row["regen_attempted_count"] == 5
    assert row["modified_count"] == 1
    assert row["removed_count"] == 1
    assert row["diff0_count"] == 3   # 5 - 1 modified - 1 removed
    assert "removed" in row["examples"]
    assert "modified" in row["examples"]
    assert verdict["totals"]["diff0_count"] == 3


def test_per_kind_verdict_all_matched_is_full_diff0():
    pre_ir = {"entities": [_entity("CIRCLE", "circle") for _ in range(4)]}
    diff = {"diagnostics": {"comparison_basis": "geometry"},
           "summary": {"by_type": {}}, "changed_handles": []}
    verdict = frc.per_kind_verdict(pre_ir, diff)
    row = next(r for r in verdict["rows"] if r["dxf_name"] == "CIRCLE")
    assert row["diff0_count"] == 4
    assert row["modified_count"] == 0
    assert row["removed_count"] == 0
    assert row["examples"] == {}


def test_per_kind_verdict_examples_capped_at_three():
    diff = {"diagnostics": {}, "summary": {"by_type": {"LINE": {"added": 0, "removed": 5, "modified": 0}}},
           "changed_handles": [{"handle": str(i), "change": "removed", "dxf_name": "LINE"} for i in range(5)]}
    verdict = frc.per_kind_verdict({"entities": [_entity("LINE", "line") for _ in range(5)]}, diff)
    row = next(r for r in verdict["rows"] if r["dxf_name"] == "LINE")
    assert len(row["examples"]["removed"]) == 3


# --------------------------------------------------------------------------- #
# resolvable_ops_report -- exercises the real, discovered gap: blocks.py's
# ir_op_for emits "insert_block", which NO family's WRITE_OP_MAP maps to a
# native handler (entities.py's wired path is "create_blockref"), so a
# block_reference entity's op is built but never resolvable.
# --------------------------------------------------------------------------- #

def test_resolvable_ops_report_flags_create_line_resolvable():
    patch = {"operations": [{"operation": "create_line", "args": {}}]}
    report = frc.resolvable_ops_report(patch)
    assert report["resolvable_count"] == 1
    assert report["unresolvable_count"] == 0


def test_resolvable_ops_report_flags_insert_block_unresolvable():
    patch = {"operations": [{"operation": "insert_block", "args": {}}]}
    report = frc.resolvable_ops_report(patch)
    assert report["unresolvable_count"] == 1
    assert "insert_block" in report["unresolvable_op_ids"]


def test_resolvable_ops_report_mixed_patch():
    patch = {"operations": [
        {"operation": "create_line", "args": {}},
        {"operation": "create_circle", "args": {}},
        {"operation": "insert_block", "args": {}},
    ]}
    report = frc.resolvable_ops_report(patch)
    assert report["resolvable_count"] == 2
    assert report["unresolvable_count"] == 1


# --------------------------------------------------------------------------- #
# pre_ir_path / post_ir_path -- declare apply_staged's stable output layout
# --------------------------------------------------------------------------- #

def test_post_ir_path_matches_apply_staged_layout():
    assert frc.post_ir_path("/some/run/dir") == os.path.join("/some/run/dir", "post", "dwg_graph_ir.json")


def test_pre_ir_path_matches_apply_staged_layout():
    assert frc.pre_ir_path("/some/run/dir") == os.path.join("/some/run/dir", "pre", "dwg_graph_ir.json")


# --------------------------------------------------------------------------- #
# resolve_regen_target -- the blank-seed-optional fallback logic
# --------------------------------------------------------------------------- #

def test_resolve_regen_target_uses_seed_when_present(tmp_path):
    seed = tmp_path / "blank_seed.dwg"
    seed.write_bytes(b"fake dwg bytes")
    result = frc.resolve_regen_target(str(seed), "/some/fallback.dwg")
    assert result == {"target": str(seed), "used_blank_seed": True}


def test_resolve_regen_target_falls_back_when_seed_missing(tmp_path):
    missing_seed = str(tmp_path / "does_not_exist.dwg")
    result = frc.resolve_regen_target(missing_seed, "/some/fallback.dwg")
    assert result["target"] == "/some/fallback.dwg"
    assert result["used_blank_seed"] is False


def test_resolve_regen_target_falls_back_when_seed_is_none():
    result = frc.resolve_regen_target(None, "/some/fallback.dwg")
    assert result["target"] == "/some/fallback.dwg"
    assert result["used_blank_seed"] is False


# --------------------------------------------------------------------------- #
# isolate_regenerated_entities -- thin wrapper over op_roundtrip_probe.
# added_entities_ir; verifies the glue (module resolution + kwarg passing),
# not added_entities_ir's own internals (already covered by op_roundtrip_
# probe's own test suite).
# --------------------------------------------------------------------------- #

def test_isolate_regenerated_entities_delegates_to_added_entities_ir():
    calls = {}

    class _FakeOrp:
        @staticmethod
        def added_entities_ir(pre_ir, post_ir, cad_diff_mod=None):
            calls["pre_ir"] = pre_ir
            calls["post_ir"] = post_ir
            calls["cad_diff_mod"] = cad_diff_mod
            return {"schema": "fake", "entities": ["sentinel"]}

    pre_ir = {"entities": []}
    post_ir = {"entities": [_entity("LINE", "line")]}
    result = frc.isolate_regenerated_entities(pre_ir, post_ir, op_roundtrip_probe_mod=_FakeOrp())
    assert result == {"schema": "fake", "entities": ["sentinel"]}
    assert calls["pre_ir"] is pre_ir
    assert calls["post_ir"] is post_ir


def test_isolate_regenerated_entities_against_real_op_roundtrip_probe():
    # Real module, real cad_diff -- a non-blank pre_ir (simulating regen
    # directly onto the production drawing's own staged copy) with one
    # extra handle in post_ir must isolate exactly that one new entity.
    pre_ir = {"schema": "ariadne.dwg_graph_ir.v1", "entities": [
        {"handle": "10", "dxf_name": "LINE", "layer": "0", "geometry": {"kind": "line"}},
    ]}
    post_ir = {"schema": "ariadne.dwg_graph_ir.v1", "entities": [
        {"handle": "10", "dxf_name": "LINE", "layer": "0", "geometry": {"kind": "line"}},
        {"handle": "20", "dxf_name": "CIRCLE", "layer": "0", "geometry": {"kind": "circle", "radius": 5}},
    ]}
    result = frc.isolate_regenerated_entities(pre_ir, post_ir)
    handles = [e["handle"] for e in result["entities"]]
    assert handles == ["20"]
