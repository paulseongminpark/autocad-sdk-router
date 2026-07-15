#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEST -- polyline width + MTEXT placement wire survival: native graph -> IR.

Intent (WHY):
  * Issue #35 (PR #29): the AcDbPolyline branch emits const_width (uniform
    "thick" polylines) and per-vertex start_width/end_width. The per-vertex lift
    pre-existed, but const_width was NOT in _geometry_from_native_entity's
    numeric allow-list, so the lift silently DROPPED it -- a thick polyline came
    back hairline even though the native side emitted the width. That exact gap
    is regression-guarded here.
  * Issue #37 (PR #29): AcDbMText now emits attachment_point (1-9; 5 =
    middle-center), rotation, and width; ir_builder lifts all three into
    geometry. Without attachment_point a consumer anchors top-left and text
    renders offset (worst on middle-anchored dimension text).

Hermetic: stdlib only. No native build, no AutoCAD, no real DWG.
"""
from __future__ import annotations

import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _build_ir(entities):
    import ir_builder
    graph_result = {"entities": entities, "modelspace_entities": len(entities)}
    return ir_builder.build_ir_from_database_graph(graph_result, {"dwg_path": "fake.dwg"})


class TestPolylineWidthWire(unittest.TestCase):
    """#35: const_width + per-vertex widths must survive the native -> IR lift."""

    def setUp(self):
        self.ir = _build_ir([
            # Uniform thick polyline (the CHECK_BIPV case: width 500 stored
            # per vertex AND reported constant).
            {"handle": "10", "dxf_name": "AcDbPolyline", "layer": "0",
             "owner_handle": "1F", "space": "model", "vertex_count": 2,
             "closed": True, "const_width": 500.0,
             "vertices": [
                 {"point": [0.0, 0.0, 0.0], "bulge": 0.0,
                  "start_width": 500.0, "end_width": 500.0},
                 {"point": [10.0, 0.0, 0.0], "bulge": 0.0,
                  "start_width": 500.0, "end_width": 500.0},
             ]},
            # Width-less polyline: no const_width key, vertices carry no widths.
            {"handle": "11", "dxf_name": "AcDbPolyline", "layer": "0",
             "owner_handle": "1F", "space": "model", "vertex_count": 2,
             "closed": False,
             "vertices": [
                 {"point": [0.0, 0.0, 0.0], "bulge": 0.0},
                 {"point": [5.0, 5.0, 0.0], "bulge": 0.0},
             ]},
        ])
        self.entities = {e["handle"]: e for e in self.ir["entities"]}

    def test_const_width_lifts_into_geometry(self):
        # Regression guard: const_width was dropped by the numeric allow-list
        # until the #35 supplement added it.
        geom = self.entities["10"]["geometry"]
        self.assertEqual(geom.get("const_width"), 500.0)

    def test_per_vertex_widths_lift(self):
        verts = self.entities["10"]["geometry"]["vertices"]
        self.assertEqual(len(verts), 2)
        for v in verts:
            self.assertEqual(v.get("start_width"), 500.0)
            self.assertEqual(v.get("end_width"), 500.0)

    def test_widthless_polyline_stays_widthless(self):
        geom = self.entities["11"]["geometry"]
        self.assertNotIn("const_width", geom)
        for v in geom["vertices"]:
            self.assertNotIn("start_width", v)
            self.assertNotIn("end_width", v)


class TestMTextPlacementWire(unittest.TestCase):
    """#37: attachment_point / rotation / width must survive into geometry."""

    def test_mtext_placement_fields_lift(self):
        ir = _build_ir([
            {"handle": "20", "dxf_name": "AcDbMText", "layer": "0",
             "owner_handle": "1F", "space": "model",
             "position": [1.0, 2.0, 0.0], "text": "\\A1;1,000",
             "height": 360.0, "attachment_point": 5, "rotation": 0.5,
             "width": 1200.0},
        ])
        geom = ir["entities"][0]["geometry"]
        self.assertEqual(geom.get("attachment_point"), 5)
        self.assertEqual(geom.get("rotation"), 0.5)
        self.assertEqual(geom.get("width"), 1200.0)
        self.assertEqual(geom.get("height"), 360.0)


if __name__ == "__main__":
    unittest.main()
