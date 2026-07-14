#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PR-B TEST -- paper-space entities wired into IR entities[] + derived count_scope.

Intent (WHY):
  * The native `inspect.database.graph` op now appends paper-space (layout)
    entities to entities[] alongside model space (previously model-space only).
    ir_builder.build_ir_from_database_graph must carry those entities through
    with `space == "paper"` intact -- dropping or relabeling them would silently
    erase paper-space geometry from the IR.
  * diagnostics.count_scope must be DERIVED from the entity spaces actually
    realized in entities[], never hardcoded -- a graph_result that mixes model
    and paper entities must report `modelspace_and_paperspace`; a model-only
    graph_result (e.g. an older native build, or a drawing with no paper-space
    geometry) must still report plain `modelspace`.

Mirrors tests/unit/test_ir_builder.py's TestNativeGraphGeometryLifting: feeds
build_ir_from_database_graph a synthetic graph_result shaped exactly like the
native op's JSON, no native build or AutoCAD required.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
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


def _line_entity(handle, owner_handle, space, start, end):
    return {
        "handle": handle, "dxf_name": "AcDbLine", "layer": "0",
        "owner_handle": owner_handle, "space": space,
        "start": start, "end": end,
    }


class TestMixedModelAndPaperSpaceWiring(unittest.TestCase):
    """A native graph_result with both model- and paper-space entities."""

    def setUp(self):
        import ir_builder
        self.ir_builder = ir_builder
        self.graph_result = {
            "modelspace_entities": 2,
            "paperspace_entities": 1,
            "entities": [
                _line_entity("10", "1F", "model", [0.0, 0.0, 0.0], [10.0, 0.0, 0.0]),
                _line_entity("11", "1F", "model", [0.0, 0.0, 0.0], [0.0, 10.0, 0.0]),
                _line_entity("20", "2F", "paper", [0.0, 0.0, 0.0], [5.0, 5.0, 0.0]),
            ],
        }
        self.ir = ir_builder.build_ir_from_database_graph(
            self.graph_result, {"dwg_path": "fake.dwg"},
        )

    def test_paper_entity_present_with_space_paper(self):
        by_handle = {e["handle"]: e for e in self.ir["entities"]}
        self.assertIn("20", by_handle, "paper-space entity missing from IR entities[]")
        self.assertEqual(by_handle["20"]["space"], "paper")
        # model entities are untouched.
        self.assertEqual(by_handle["10"]["space"], "model")
        self.assertEqual(by_handle["11"]["space"], "model")

    def test_truth_gate_holds_across_both_spaces(self):
        # entities[] realized length includes model + paper entities.
        self.assertEqual(len(self.ir["entities"]), 3)
        self.assertEqual(self.ir["diagnostics"]["entity_count"], 3)
        # The realized array length is modelspace_entities + paperspace_entities
        # (2 + 1 == 3). The truth gate must compare against that TOTAL, not against
        # modelspace_entities alone -- else every paper-bearing drawing raises a
        # false "!= realized" mismatch. Regression guard for that exact bug
        # (caught by adversarial audit SBC-20260714-001).
        diag = self.ir["diagnostics"]
        self.assertEqual(
            [w for w in diag["warnings"] if "realized" in w], [],
            f"spurious paperspace truth-gate mismatch warning: {diag['warnings']}")
        self.assertTrue(diag["coverage"]["match"], "coverage.match must hold with paper space")
        # the modelspace-named field stays model-only (accurate), not the total.
        self.assertEqual(diag["coverage"]["modelspace_count_from_native"], 2)

    def test_count_scope_is_modelspace_and_paperspace(self):
        self.assertEqual(
            self.ir["diagnostics"]["count_scope"], "modelspace_and_paperspace",
        )


class TestModelOnlyCountScopeUnchanged(unittest.TestCase):
    """A model-space-only graph_result must still derive plain 'modelspace'."""

    def test_count_scope_is_modelspace(self):
        import ir_builder
        graph_result = {
            "modelspace_entities": 2,
            "entities": [
                _line_entity("10", "1F", "model", [0.0, 0.0, 0.0], [10.0, 0.0, 0.0]),
                _line_entity("11", "1F", "model", [0.0, 0.0, 0.0], [0.0, 10.0, 0.0]),
            ],
        }
        ir = ir_builder.build_ir_from_database_graph(graph_result, {"dwg_path": "fake.dwg"})
        self.assertEqual(ir["diagnostics"]["count_scope"], "modelspace")
        self.assertEqual(len(ir["entities"]), 2)
        self.assertEqual(ir["diagnostics"]["entity_count"], 2)


if __name__ == "__main__":
    unittest.main()
