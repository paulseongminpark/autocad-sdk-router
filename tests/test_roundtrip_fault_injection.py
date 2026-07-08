#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Roundtrip fault-injection tests for geometry-basis CAD diff verdicts."""
from __future__ import annotations

import copy
import os
import sys
from collections import Counter

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_THIS)
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cad_diff
from full_roundtrip_capstone import per_kind_verdict


def _line_entity(handle, start, end, layer="0"):
    return {
        "handle": handle,
        "class": "AcDbLine",
        "dxf_name": "LINE",
        "owner_handle": "1F",
        "space": "model",
        "layer": layer,
        "bbox": [start[0], start[1], start[2], end[0], end[1], end[2]],
        "geometry": {"kind": "line", "start": list(start), "end": list(end)},
        "source": {"extractor": "test", "decoded": True},
    }


def _circle_entity(handle, center, radius, layer="0"):
    return {
        "handle": handle,
        "class": "AcDbCircle",
        "dxf_name": "CIRCLE",
        "owner_handle": "1F",
        "space": "model",
        "layer": layer,
        "bbox": [
            center[0] - radius,
            center[1] - radius,
            center[2],
            center[0] + radius,
            center[1] + radius,
            center[2],
        ],
        "geometry": {"kind": "circle", "center": list(center), "radius": radius},
        "source": {"extractor": "test", "decoded": True},
    }


def _text_entity(handle, insert, text, layer="NOTES"):
    return {
        "handle": handle,
        "class": "AcDbText",
        "dxf_name": "TEXT",
        "owner_handle": "1F",
        "space": "model",
        "layer": layer,
        "bbox": [insert[0], insert[1], insert[2], insert[0] + 1.0, insert[1] + 1.0, insert[2]],
        "geometry": {"kind": "text", "insert": list(insert), "text": text, "height": 1.0, "rotation": 0.0},
        "source": {"extractor": "test", "decoded": True},
    }


def _ir(entities):
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "entities": entities,
        "diagnostics": {"entity_count": len(entities)},
    }


def _base_ir():
    return _ir([
        _line_entity("A10", (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), layer="A"),
        _line_entity("A11", (0.0, 1.0, 0.0), (10.0, 1.0, 0.0), layer="A"),
        _circle_entity("A12", (5.0, 5.0, 0.0), 2.0, layer="B"),
        _circle_entity("A13", (15.0, 5.0, 0.0), 3.0, layer="B"),
        _text_entity("A14", (1.0, 8.0, 0.0), "alpha", layer="NOTES"),
        _text_entity("A15", (1.0, 10.0, 0.0), "beta", layer="NOTES"),
    ])


def _rehandled(ir, prefix="B"):
    post = copy.deepcopy(ir)
    for i, ent in enumerate(post["entities"], start=1):
        ent["handle"] = f"{prefix}{i:02X}"
    return post


def _diff(pre, post):
    return cad_diff.compute_diff(
        pre,
        post,
        comparison_basis="geometry",
        geometry_tolerance=1e-6,
    )


def _verdict(pre, post):
    return per_kind_verdict(pre, _diff(pre, post))


def _row(verdict, dxf_name):
    return next(row for row in verdict["rows"] if row["dxf_name"] == dxf_name)


def _assert_all_diff0(verdict):
    for row in verdict["rows"]:
        assert row["diff0_count"] == row["regen_attempted_count"]
        assert row["modified_count"] == 0
        assert row["removed_count"] == 0
        assert row["added_count"] == 0


def _detects_fault(pre, post):
    totals = _verdict(pre, post)["totals"]
    return (
        totals["modified_count"] > 0
        or totals["removed_count"] > 0
        or totals["added_count"] > 0
    )


def _naive_count_only(pre, post):
    pre_counts = Counter(e.get("dxf_name") for e in pre["entities"])
    post_counts = Counter(e.get("dxf_name") for e in post["entities"])
    return "PASS" if pre_counts == post_counts else "FAIL"


def test_identical_ir_zero_diff():
    pre = _base_ir()
    post = _rehandled(pre)

    verdict = _verdict(pre, post)

    assert verdict["comparison_basis"] == "geometry"
    _assert_all_diff0(verdict)


def test_moved_entity_detected():
    pre = _base_ir()
    post = _rehandled(pre)
    post["entities"][0] = _line_entity("B01", (100.0, 0.0, 0.0), (110.0, 0.0, 0.0), layer="A")

    row = _row(_verdict(pre, post), "LINE")

    assert row["diff0_count"] == row["regen_attempted_count"] - 1
    assert row["removed_count"] + row["modified_count"] >= 1


def test_deleted_entity_detected():
    pre = _base_ir()
    post = _rehandled(pre)
    del post["entities"][2]
    post["diagnostics"]["entity_count"] = len(post["entities"])

    row = _row(_verdict(pre, post), "CIRCLE")

    assert row["removed_count"] == 1


def test_extra_entity_detected():
    pre = _base_ir()
    post = _rehandled(pre)
    post["entities"].append(_circle_entity("B99", (25.0, 5.0, 0.0), 1.5, layer="B"))
    post["diagnostics"]["entity_count"] = len(post["entities"])

    row = _row(_verdict(pre, post), "CIRCLE")

    assert row["added_count"] == 1


def test_layer_change_detected():
    pre = _base_ir()
    post = _rehandled(pre)
    post["entities"][2]["layer"] = "RENAMED"

    row = _row(_verdict(pre, post), "CIRCLE")

    assert row["removed_count"] + row["modified_count"] + row["added_count"] >= 1


def test_text_content_change_detected():
    pre = _base_ir()
    post = _rehandled(pre)
    post["entities"][4]["geometry"]["text"] = "changed"

    row = _row(_verdict(pre, post), "TEXT")

    assert row["removed_count"] + row["modified_count"] + row["added_count"] >= 1


def test_within_tolerance_passes():
    pre = _base_ir()
    post = _rehandled(pre)
    post["entities"][0]["geometry"]["end"][0] += 1e-9
    post["entities"][0]["bbox"][3] += 1e-9

    verdict = _verdict(pre, post)

    _assert_all_diff0(verdict)


def test_naive_count_foil_is_blind():
    """ALM naive-foil discipline: a gate that cannot fail is not a gate."""
    scenarios = []

    pre = _base_ir()
    moved = _rehandled(pre)
    moved["entities"][0] = _line_entity("B01", (100.0, 0.0, 0.0), (110.0, 0.0, 0.0), layer="A")
    scenarios.append((pre, moved))

    pre = _base_ir()
    layer_changed = _rehandled(pre)
    layer_changed["entities"][2]["layer"] = "RENAMED"
    scenarios.append((pre, layer_changed))

    pre = _base_ir()
    text_changed = _rehandled(pre)
    text_changed["entities"][4]["geometry"]["text"] = "changed"
    scenarios.append((pre, text_changed))

    for pre, post in scenarios:
        assert _naive_count_only(pre, post) == "PASS"
        assert _detects_fault(pre, post)
