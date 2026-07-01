#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer T0 TEST -- cad_diff geometry-fingerprint join (comparison_basis="geometry").

Intent (WHY):
  * A regenerated DWG (extract IR -> rebuild entities) gets brand-new handles
    from its writing engine even when the geometry is byte-identical to the
    source. The handle-basis join (compute_diff's default) can NEVER report
    zero changes against such a rebuild -- every old handle looks removed and
    every new handle looks added. comparison_basis="geometry" joins on
    (dxf_name, layer, geometry) instead, so a roundtrip that reproduces the same
    geometry under new handles reports zero changes, while a genuine geometry
    edit still shows up as exactly one "modified" record (Rule 9: the test
    encodes WHY the basis matters, not just that some function returns a value).
  * Tolerance is the AutoCAD COMPARETOLERANCE analog: coordinate noise smaller
    than the tolerance must NOT register as a change (floating-point roundtrip
    noise is expected on a rebuild); a shift at/beyond tolerance MUST register.
  * comparison_basis="handle" (the default) must be completely unaffected by
    this feature -- pinned as a regression against compute_diff's existing,
    already-tested handle-basis behavior.

Uses ir_builder.make_fixture_ir() for the handle-basis regression pin (genuine
producer output), and small inline synthetic entities for the geometry-basis
cases -- the fields cad_diff actually reads (handle/dxf_name/layer/geometry)
are trivial enough that inline fixtures keep each test's intent visible without
indirection through the fixture builder.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _line_entity(handle, start, end, layer="0"):
    """A minimal LINE entity dict -- just the fields cad_diff reads."""
    return {
        "handle": handle, "class": "AcDbLine", "dxf_name": "LINE",
        "owner_handle": "1F", "space": "model", "layer": layer,
        "bbox": [start[0], start[1], start[2], end[0], end[1], end[2]],
        "geometry": {"kind": "line", "start": list(start), "end": list(end)},
        "source": {"extractor": "test", "decoded": True},
    }


def _ir(entities):
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "entities": entities,
        "diagnostics": {"entity_count": len(entities)},
    }


class TestGeometryBasisRehandle(unittest.TestCase):
    """Identical geometry under brand-new handles -> zero changes."""

    def test_geometry_diff_zero_on_rehandle(self):
        import cad_diff
        pre = _ir([_line_entity("AAA", (0, 0, 0), (10, 5, 0))])
        post = _ir([_line_entity("ZZZ", (0, 0, 0), (10, 5, 0))])  # new handle, same geometry
        diff = cad_diff.compute_diff(pre, post, comparison_basis="geometry")
        self.assertEqual(diff["diagnostics"]["comparison_basis"], "geometry")
        self.assertEqual(diff["summary"]["added"], 0)
        self.assertEqual(diff["summary"]["removed"], 0)
        self.assertEqual(diff["summary"]["modified"], 0)
        self.assertEqual(diff["summary"]["unchanged"], 1)
        self.assertEqual(diff["changed_handles"], [])


class TestGeometryBasisCoordShift(unittest.TestCase):
    """A coordinate shift beyond tolerance is exactly one 'modified' record."""

    def test_geometry_diff_detects_coord_shift(self):
        import cad_diff
        pre = _ir([_line_entity("AAA", (0, 0, 0), (10, 5, 0))])
        post = _ir([_line_entity("ZZZ", (0, 0, 0), (10, 5.5, 0))])  # end.y shifted 0.5
        diff = cad_diff.compute_diff(pre, post, comparison_basis="geometry")
        self.assertEqual(diff["summary"]["added"], 0)
        self.assertEqual(diff["summary"]["removed"], 0)
        self.assertEqual(diff["summary"]["modified"], 1)
        self.assertEqual(diff["summary"]["unchanged"], 0)
        self.assertEqual(len(diff["changed_handles"]), 1)
        rec = diff["changed_handles"][0]
        self.assertEqual(rec["change"], "modified")
        fields = [f["field"] for f in rec["fields"]]
        self.assertIn("geometry", fields)


class TestGeometryBasisWithinTolerance(unittest.TestCase):
    """A shift smaller than the tolerance must NOT register as a change."""

    def test_geometry_diff_within_tolerance_is_equal(self):
        import cad_diff
        pre = _ir([_line_entity("AAA", (0, 0, 0), (10, 5, 0))])
        # shift well below the default 1e-6 tolerance
        post = _ir([_line_entity("ZZZ", (0, 0, 0), (10, 5 + 1e-9, 0))])
        diff = cad_diff.compute_diff(pre, post, comparison_basis="geometry")
        self.assertEqual(diff["summary"]["added"], 0)
        self.assertEqual(diff["summary"]["removed"], 0)
        self.assertEqual(diff["summary"]["modified"], 0)
        self.assertEqual(diff["summary"]["unchanged"], 1)
        self.assertEqual(diff["changed_handles"], [])


class TestHandleBasisRegression(unittest.TestCase):
    """comparison_basis="handle" (default) is unaffected by the geometry feature."""

    def test_handle_basis_regression(self):
        import cad_diff
        import ir_builder
        pre = ir_builder.make_fixture_ir()
        post = copy.deepcopy(pre)
        for e in post["entities"]:
            if e["handle"] == "2A7":
                e["layer"] = "MOVED"

        default_basis_diff = cad_diff.compute_diff(pre, post)
        explicit_basis_diff = cad_diff.compute_diff(pre, post, comparison_basis="handle")

        self.assertEqual(default_basis_diff["diagnostics"]["comparison_basis"], "handle")
        self.assertEqual(default_basis_diff["summary"]["modified"], 1)
        self.assertEqual(default_basis_diff["summary"]["added"], 0)
        self.assertEqual(default_basis_diff["summary"]["removed"], 0)
        # explicit basis="handle" must be byte-identical to the (unchanged) default path.
        self.assertEqual(
            json.dumps(default_basis_diff, sort_keys=True, ensure_ascii=False),
            json.dumps(explicit_basis_diff, sort_keys=True, ensure_ascii=False),
        )


if __name__ == "__main__":
    unittest.main()
