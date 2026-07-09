#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _folded_hatch_geometry(**fields):
    import ir_builder

    raw = {
        "handle": "2F40",
        "dxf_name": "AcDbHatch",
        "layer": "0",
        "owner_handle": "1F",
        "is_associative": True,
    }
    raw.update(fields)
    ir = ir_builder.build_ir_from_database_graph(
        {"modelspace_entities": 1, "entities": [raw], "coverage": {}},
        {},
    )
    return ir["entities"][0]["geometry"]


def test_hatch_assoc_source_handles_survive_native_folding_verbatim():
    geom = _folded_hatch_geometry(assoc_source_handles=["2F3A", "2F3B"])

    assert geom["assoc_source_handles"] == ["2F3A", "2F3B"]


def test_hatch_without_assoc_source_handles_gains_no_key():
    geom = _folded_hatch_geometry()

    assert "assoc_source_handles" not in geom


def test_hatch_malformed_assoc_source_handles_are_dropped():
    for bad_value in ("2F3A", ["2F3A", 42]):
        geom = _folded_hatch_geometry(assoc_source_handles=bad_value)

        assert "assoc_source_handles" not in geom
