#!/usr/bin/env python3
"""Regression coverage for the LIBREDWG_KIND_MAP dimension entries.

Locks in the fix from commit 3bf9894: an R1a cross-verify run flagged
DIMENSION_LINEAR/AcDbRotatedDimension as unmapped while the IR side counted
kind:dimension -- a label-map gap, not a real entity mismatch.
"""
from __future__ import annotations

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "tools"))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import cross_verify as cv

DIMENSION_ENTITY_NAMES = [
    "DIMENSION_LINEAR",
    "DIMENSION_ALIGNED",
    "DIMENSION_ANG2LN",
    "DIMENSION_ANG3PT",
    "DIMENSION_DIAMETER",
    "DIMENSION_RADIUS",
    "DIMENSION_ORDINATE",
]


def _build_lib_doc(entity_specs, layer_names=()):
    objects = []
    entity_refs = []
    for idx, (name, subclass) in enumerate(entity_specs):
        handle_id = 100 + idx
        entity_refs.append([3, 2, handle_id, handle_id])
        objects.append(
            {
                "entity": name,
                "_subclass": subclass,
                "handle": [0, 2, handle_id],
            }
        )
    objects.append(
        {
            "object": "BLOCK_HEADER",
            "name": "*Model_Space",
            "entities": entity_refs,
        }
    )
    for idx, layer_name in enumerate(layer_names):
        objects.append(
            {
                "object": "LAYER",
                "handle": [0, 1, 200 + idx],
                "name": layer_name,
            }
        )
    return {"OBJECTS": objects}


def test_all_dimension_subtypes_map_to_canonical_dimension():
    lib_doc = _build_lib_doc(
        [(name, "AcDbRotatedDimension") for name in DIMENSION_ENTITY_NAMES]
    )

    summary = cv.summarize_libredwg_doc(lib_doc)

    assert summary["mapped_kind_counts"] == {"dimension": len(DIMENSION_ENTITY_NAMES)}
    assert summary["unmapped"] == []
    assert summary["entity_total"] == len(DIMENSION_ENTITY_NAMES)


def test_mapped_kind_counts_aggregates_across_mixed_entities():
    lib_doc = _build_lib_doc(
        [
            ("DIMENSION_LINEAR", "AcDbRotatedDimension"),
            ("DIMENSION_LINEAR", "AcDbRotatedDimension"),
            ("LINE", "AcDbLine"),
        ]
    )

    summary = cv.summarize_libredwg_doc(lib_doc)

    assert summary["mapped_kind_counts"] == {"dimension": 2, "line": 1}
    assert summary["entity_total"] == 3
    assert summary["unmapped"] == []


def test_unknown_entity_name_lands_in_unmapped_but_counts_toward_total():
    lib_doc = _build_lib_doc(
        [
            ("MLEADER", "AcDbMLeader"),
            ("LINE", "AcDbLine"),
        ]
    )

    summary = cv.summarize_libredwg_doc(lib_doc)

    assert summary["unmapped"] == [
        {"entity": "MLEADER", "subclass": "AcDbMLeader", "count": 1}
    ]
    assert summary["mapped_kind_counts"] == {"line": 1}
    assert summary["entity_total"] == 2


def test_build_verdict_agrees_on_equal_summaries():
    lib_summary = {
        "entity_total": 2,
        "layer_count": 1,
        "mapped_kind_counts": {"dimension": 2},
        "unmapped": [],
    }
    ir_summary = {
        "entity_total": 2,
        "layer_count": 1,
        "mapped_kind_counts": {"dimension": 2},
    }

    verdict = cv.build_verdict(lib_summary, ir_summary)

    assert verdict["agree"] is True
    assert verdict["deltas"] == []


def test_build_verdict_reports_kind_dimension_delta_on_mismatch():
    lib_summary = {
        "entity_total": 0,
        "layer_count": 0,
        "mapped_kind_counts": {},
        "unmapped": [],
    }
    ir_summary = {
        "entity_total": 2,
        "layer_count": 0,
        "mapped_kind_counts": {"dimension": 2},
    }

    verdict = cv.build_verdict(lib_summary, ir_summary)

    assert verdict["agree"] is False
    assert verdict["deltas"] == [
        {"field": "entity_total", "libredwg": 0, "ir": 2},
        {"field": "kind:dimension", "libredwg": 0, "ir": 2},
    ]


def test_layer_rows_counted_into_layer_count():
    lib_doc = _build_lib_doc(
        [("LINE", "AcDbLine")],
        layer_names=["0", "A-WALL", "A-DOOR"],
    )

    summary = cv.summarize_libredwg_doc(lib_doc)

    assert summary["layer_count"] == 3
