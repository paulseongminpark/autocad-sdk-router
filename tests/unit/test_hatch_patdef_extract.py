#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class TestHatchPatternDefinitions(unittest.TestCase):
    def _one_entity_ir(self, raw_entity):
        import ir_builder
        graph_result = {"entities": [raw_entity], "modelspace_entities": 1}
        ir = ir_builder.build_ir_from_database_graph(graph_result, {"dwg_path": "fake.dwg"})
        return ir["entities"][0]

    def test_hatch_pattern_definitions_survive_native_entity_lifting_unchanged(self):
        rows = [
            {
                "angle": 0.0,
                "base": [0.0, 0.0],
                "offset": [0.0, 4.7625],
                "dashes": [],
            },
            {
                "angle": math.pi / 4.0,
                "base": [1.5, -2.25],
                "offset": [3.0, 3.0],
                "dashes": [0.5, -0.25, 0.0],
            },
        ]
        ent = self._one_entity_ir({
            "handle": "1A01", "dxf_name": "AcDbHatch", "layer": "0",
            "owner_handle": "1F", "space": "model",
            "pattern_name": "H3", "pattern_type": 2, "pattern_angle": 0.0,
            "pattern_scale": 181.0, "pattern_double": False, "hatch_style": 0,
            "is_solid_fill": False, "is_associative": False, "is_gradient": False,
            "elevation": 0.0, "normal": [0.0, 0.0, 1.0],
            "pattern_definitions": rows,
            "loops": [{
                "index": 0, "loop_type": 2, "closed": True, "status": "ok",
                "vertices": [
                    {"point": [0.0, 0.0, 0.0], "bulge": 0.0},
                    {"point": [5.0, 0.0, 0.0], "bulge": 0.0},
                    {"point": [5.0, 5.0, 0.0], "bulge": 0.0},
                    {"point": [0.0, 0.0, 0.0], "bulge": 0.0},
                ],
            }],
        })
        self.assertEqual(ent["dxf_name"], "HATCH")
        self.assertEqual(ent["geometry"]["kind"], "hatch")
        self.assertEqual(ent["geometry"]["pattern_definitions"], rows)

    def test_pattern_definition_row_contract_keeps_radians_and_expected_keys(self):
        row = {
            "angle": math.pi / 6.0,
            "base": [12.5, -3.25],
            "offset": [0.0, 6.0],
            "dashes": [1.0, -0.5, 0.0],
        }
        ent = self._one_entity_ir({
            "handle": "1A02", "dxf_name": "AcDbHatch", "layer": "0",
            "owner_handle": "1F", "space": "model",
            "pattern_name": "H3", "pattern_type": 2, "pattern_angle": 0.0,
            "pattern_scale": 1.0, "pattern_double": False, "hatch_style": 0,
            "is_solid_fill": False, "is_associative": False, "is_gradient": False,
            "elevation": 0.0, "normal": [0.0, 0.0, 1.0],
            "pattern_definitions": [row],
            "loops": [{
                "index": 0, "loop_type": 2, "closed": True, "status": "ok",
                "vertices": [
                    {"point": [0.0, 0.0, 0.0], "bulge": 0.0},
                    {"point": [1.0, 0.0, 0.0], "bulge": 0.0},
                    {"point": [0.0, 1.0, 0.0], "bulge": 0.0},
                ],
            }],
        })
        got = ent["geometry"]["pattern_definitions"][0]
        self.assertEqual(set(got), {"angle", "base", "offset", "dashes"})
        self.assertGreaterEqual(got["angle"], -math.tau)
        self.assertLessEqual(got["angle"], math.tau)
        self.assertEqual(len(got["base"]), 2)
        self.assertEqual(len(got["offset"]), 2)
        self.assertTrue(all(isinstance(v, (int, float)) for v in got["base"]))
        self.assertTrue(all(isinstance(v, (int, float)) for v in got["offset"]))
        self.assertTrue(all(isinstance(v, (int, float)) for v in got["dashes"]))
        self.assertAlmostEqual(got["angle"], math.pi / 6.0)
