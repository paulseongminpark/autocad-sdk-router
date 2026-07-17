#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Synthetic dimension/geometry IR authoring for L5 semantic-gate mutation testing.

Builds IR documents whose dimension-vs-geometry relations are correct by
construction (see dim_geometry.py for the field contract and span formula),
then seeds exactly one known violation per call so a gate's conviction rate
can be measured against a known-good baseline instead of only a real DWG
census fixture.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Dict, List

from .dim_geometry import _dimension_span

_DIM_LAYER = "DIM"
_ANCHOR_LAYER = "0"

_BASE_X_STEP = 10000.0
_BASE_Y_STEP = 5000.0
_LENGTH_BASE = 1000.0
_LENGTH_STEP = 100.0
_ROTATION_STEPS = 12

_MEASUREMENT_DRIFT = 1.0
_XLINE_SHIFT = 750.0
_ANCHOR_MOVE = 4000.0

MUTATION_KINDS = ("measurement_drift", "xline_shift", "dim_deleted", "anchor_line_moved")


def _line_for_index(idx: int) -> Dict[str, Any]:
    """Derive one line's endpoints/rotation arithmetically from idx (no randomness)."""
    base_x = _BASE_X_STEP * idx
    base_y = _BASE_Y_STEP * idx
    length = _LENGTH_BASE + _LENGTH_STEP * idx
    rotation = (idx % _ROTATION_STEPS) * (math.pi / _ROTATION_STEPS)
    start = [base_x, base_y, 0.0]
    end = [base_x + length * math.cos(rotation), base_y + length * math.sin(rotation), 0.0]
    return {"start": start, "end": end, "rotation": rotation}


def make_dim_ir(n_dims: int, seed_offset: int = 0) -> Dict[str, Any]:
    """Author an IR doc of n_dims rotated dimensions, each measuring a real line entity.

    Every dimension's xline points sit exactly on its paired anchor line's
    endpoints, and its measurement is computed with dim_geometry's own span
    formula, so the returned doc is 100% coherent under extract_dim_relations.
    """
    dimensions: List[Dict[str, Any]] = []
    anchor_geometry: List[Dict[str, Any]] = []

    for i in range(n_dims):
        idx = i + seed_offset
        line = _line_for_index(idx)
        dim_handle = f"SYNDIM{idx:06d}"
        anchor_handle = f"SYNANC{idx:06d}"

        geometry: Dict[str, Any] = {
            "kind": "dimension",
            "xline1_point": list(line["start"]),
            "xline2_point": list(line["end"]),
            "rotation": line["rotation"],
        }
        geometry["measurement"] = _dimension_span(geometry)

        dimensions.append({"handle": dim_handle, "layer": _DIM_LAYER, "geometry": geometry})
        anchor_geometry.append(
            {
                "handle": anchor_handle,
                "layer": _ANCHOR_LAYER,
                "geometry": {
                    "kind": "line",
                    "start": list(line["start"]),
                    "end": list(line["end"]),
                },
            }
        )

    return {
        "schema": "ariadne.synthetic_dim_truth.v1",
        "dimensions": dimensions,
        "anchor_geometry": anchor_geometry,
    }


def mutate(ir_doc: Dict[str, Any], kind: str) -> Dict[str, Any]:
    """Return a deep copy of ir_doc with exactly one seeded violation of `kind`."""
    if kind not in MUTATION_KINDS:
        raise ValueError(f"unknown mutation kind: {kind!r} (expected one of {MUTATION_KINDS})")

    doc = copy.deepcopy(ir_doc)
    dimensions = doc["dimensions"]
    if not dimensions:
        raise ValueError("ir_doc has no dimensions to mutate")

    if kind == "measurement_drift":
        dimensions[0]["geometry"]["measurement"] += _MEASUREMENT_DRIFT

    elif kind == "xline_shift":
        dimensions[0]["geometry"]["xline2_point"][0] += _XLINE_SHIFT

    elif kind == "dim_deleted":
        dimensions.pop(0)

    elif kind == "anchor_line_moved":
        anchors = doc.get("anchor_geometry") or []
        if not anchors:
            raise ValueError("ir_doc has no anchor_geometry to mutate")
        anchor_geom = anchors[0]["geometry"]
        dim_geom = dimensions[0]["geometry"]
        for axis in (0, 1):
            anchor_geom["start"][axis] += _ANCHOR_MOVE
            anchor_geom["end"][axis] += _ANCHOR_MOVE
            dim_geom["xline1_point"][axis] += _ANCHOR_MOVE
            dim_geom["xline2_point"][axis] += _ANCHOR_MOVE

    return doc
