#!/usr/bin/env python3
"""Anonymous block-definition capture tests."""
from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ir_builder import build_ir_from_database_graph  # noqa: E402

_NATIVE = Path(_REPO) / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"


def _native_src() -> str:
    return _NATIVE.read_text(encoding="utf-8", errors="replace")


def _block_table_records_region(src: str) -> str:
    m = re.search(
        r"static std::string blockTableRecordsJson\(.*?\)\s*\{(.*?)\n\}",
        src,
        re.S,
    )
    assert m, "blockTableRecordsJson not found"
    return m.group(1)


class TestNativeAnonymousDefinitionCapture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _native_src()
        cls.region = _block_table_records_region(cls.src)

    def test_native_graph_projection_no_longer_filters_out_anonymous_defs(self):
        self.assertIn(
            "const bool emitBlockDef = !isLayout && !isXref;",
            self.region,
        )
        self.assertNotIn(
            "const bool isUserBlock = !isLayout && !isAnon && !isXref;",
            self.region,
        )

    def test_native_graph_projection_marks_anonymous_defs_additively(self):
        self.assertIn('\\"anonymous\\":true', self.region)
        self.assertIn("if (isAnon)", self.region)


class TestIrBuilderAnonymousPassthrough(unittest.TestCase):
    def test_build_ir_preserves_anonymous_flag_and_normalizes_def_entities(self):
        graph_result = {
            "modelspace_entities": 1,
            "entities": [
                {
                    "handle": "M1",
                    "dxf_name": "AcDbBlockReference",
                    "owner_handle": "MS",
                    "space": "model",
                    "layer": "0",
                    "position": [10.0, 0.0, 0.0],
                    "scale": [1.0, 1.0, 1.0],
                    "rotation": 0.0,
                    "block_name": "*U172",
                }
            ],
            "block_definitions": [
                {
                    "handle": "BD1",
                    "name": "*U172",
                    "anonymous": True,
                    "entity_count": 1,
                    "def_entities": [
                        {
                            "handle": "R1",
                            "dxf_name": "AcDbBlockReference",
                            "owner_handle": "BD1",
                            "space": "block",
                            "layer": "0",
                            "position": [1.0, 2.0, 0.0],
                            "scale": [1.0, 1.0, 1.0],
                            "rotation": 0.0,
                            "block_name": "INNER",
                        }
                    ],
                },
                {
                    "handle": "BD2",
                    "name": "NAMED",
                    "entity_count": 0,
                    "def_entities": [],
                },
            ],
        }

        ir = build_ir_from_database_graph(graph_result, {"dwg_path": "fixture.dwg"})

        self.assertEqual(ir["block_definitions"][0]["name"], "*U172")
        self.assertTrue(ir["block_definitions"][0]["anonymous"])
        self.assertNotIn("anonymous", ir["block_definitions"][1])

        def_ent = ir["block_definitions"][0]["def_entities"][0]
        self.assertEqual(def_ent["dxf_name"], "INSERT")
        self.assertEqual(def_ent["space"], "block")
        self.assertEqual(def_ent["geometry"]["kind"], "block_reference")
        self.assertEqual(def_ent["geometry"]["block_name"], "INNER")
        self.assertIn("stable_id", def_ent)
        self.assertIn("stable_id_ordinal", def_ent)

        self.assertEqual(ir["block_references"][0]["block_name"], "*U172")


if __name__ == "__main__":
    unittest.main()
