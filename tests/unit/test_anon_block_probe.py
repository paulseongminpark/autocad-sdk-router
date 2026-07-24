#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EXP-C anon_block_probe test -- gap map for block references naming undefined defs.

Intent (WHY):
  * R3b deferred ~320 nested block references naming anonymous dynamic-block
    definitions ('*U172' etc.) that are absent from block_definitions[]. Before
    a fix can be built, anon_block_probe.analyze() must produce an exact,
    deterministic gap map (referenced vs defined set math) so the fix targets
    the real gap, not a guess.
  * Synthetic IRs only (stdlib json/unittest) -- no dependency on a real DWG
    sample being present on this box.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import anon_block_probe as probe  # noqa: E402  (after sys.path setup, matches sibling tests)


def _entity(space, kind, block_name=None):
    geometry = {"kind": kind}
    if block_name is not None:
        geometry["block_name"] = block_name
    return {
        "handle": "1",
        "class": "AcDbBlockReference",
        "dxf_name": "INSERT",
        "owner_handle": "0",
        "space": space,
        "layer": "0",
        "bbox": None,
        "geometry": geometry,
        "source": "test",
    }


class TestSetMath(unittest.TestCase):
    def test_referenced_vs_defined(self):
        ir = {
            "entities": [
                _entity("model", "block_reference", "A"),
                _entity("model", "block_reference", "B"),
            ],
            "block_definitions": [{"name": "A"}],
        }
        result = probe.analyze(ir)
        self.assertEqual(result["schema"], "ariadne.anon_block_probe.v1")
        self.assertEqual(result["defined_names"], ["A"])
        self.assertEqual(result["referenced_names"], {"A": 1, "B": 1})
        self.assertEqual(set(result["undefined"]), {"B"})
        self.assertEqual(result["undefined"]["B"]["references"], 1)
        self.assertEqual(result["summary"]["undefined_unique"], 1)
        self.assertEqual(result["summary"]["undefined_total_refs"], 1)

    def test_defined_excluded_regardless_of_source(self):
        ir = {
            "entities": [_entity("model", "block_reference", "DEFINED")],
            "block_definitions": [{"name": "DEFINED"}],
        }
        result = probe.analyze(ir)
        self.assertEqual(result["undefined"], {})
        self.assertEqual(result["summary"]["undefined_unique"], 0)

    def test_paperspace_block_reference_not_counted_as_modelspace(self):
        ir = {
            "entities": [_entity("paper", "block_reference", "PAPER_ONLY")],
            "block_definitions": [],
        }
        result = probe.analyze(ir)
        self.assertNotIn("PAPER_ONLY", result["referenced_names"])

    def test_non_block_reference_geometry_ignored(self):
        ir = {
            "entities": [_entity("model", "line")],
            "block_definitions": [],
        }
        result = probe.analyze(ir)
        self.assertEqual(result["referenced_names"], {})


class TestNestedAggregation(unittest.TestCase):
    def test_single_nested_reference_from_def_entities(self):
        ir = {
            "entities": [],
            "block_definitions": [
                {"name": "PARENT", "def_entities": [_entity("block", "block_reference", "*U172")]},
            ],
        }
        result = probe.analyze(ir)
        self.assertEqual(result["referenced_names"]["*U172"], 1)
        self.assertIn("*U172", result["undefined"])
        self.assertEqual(result["undefined"]["*U172"]["referenced_from"], ["PARENT"])

    def test_multiple_parents_aggregate_count(self):
        ir = {
            "entities": [],
            "block_definitions": [
                {"name": "PARENT_A", "def_entities": [_entity("block", "block_reference", "*U144")]},
                {"name": "PARENT_B", "def_entities": [_entity("block", "block_reference", "*U144")]},
            ],
        }
        result = probe.analyze(ir)
        self.assertEqual(result["referenced_names"]["*U144"], 2)
        self.assertEqual(result["undefined"]["*U144"]["references"], 2)
        self.assertEqual(result["undefined"]["*U144"]["referenced_from"], ["PARENT_A", "PARENT_B"])

    def test_referenced_from_sample_capped_at_five(self):
        block_definitions = [
            {"name": "PARENT_%d" % i, "def_entities": [_entity("block", "block_reference", "*U172")]}
            for i in range(7)
        ]
        ir = {"entities": [], "block_definitions": block_definitions}
        result = probe.analyze(ir)
        self.assertEqual(result["referenced_names"]["*U172"], 7)
        self.assertEqual(len(result["undefined"]["*U172"]["referenced_from"]), 5)


class TestAnonymousClassification(unittest.TestCase):
    def test_anonymous_vs_named(self):
        ir = {
            "entities": [
                _entity("model", "block_reference", "*U1"),
                _entity("model", "block_reference", "NAMED_BLOCK"),
            ],
            "block_definitions": [],
        }
        result = probe.analyze(ir)
        self.assertTrue(result["undefined"]["*U1"]["anonymous"])
        self.assertFalse(result["undefined"]["NAMED_BLOCK"]["anonymous"])
        self.assertFalse(result["summary"]["all_undefined_anonymous"])

    def test_all_undefined_anonymous_true_when_only_anonymous(self):
        ir = {
            "entities": [_entity("model", "block_reference", "*U9")],
            "block_definitions": [],
        }
        result = probe.analyze(ir)
        self.assertTrue(result["summary"]["all_undefined_anonymous"])

    def test_anonymous_defined_count(self):
        ir = {
            "entities": [],
            "block_definitions": [{"name": "*U1"}, {"name": "NORMAL"}, {"name": "*U2"}],
        }
        result = probe.analyze(ir)
        self.assertEqual(result["anonymous_defined_count"], 2)


class TestMarkdownRender(unittest.TestCase):
    def test_top_row_sorted_by_references_desc_and_findings_present(self):
        ir = {
            "entities": [_entity("model", "block_reference", "LOW")],
            "block_definitions": [
                {"name": "PARENT_1", "def_entities": [_entity("block", "block_reference", "HIGH")]},
                {"name": "PARENT_2", "def_entities": [_entity("block", "block_reference", "HIGH")]},
            ],
        }
        result = probe.analyze(ir)
        md = probe.render_markdown(result)
        self.assertLess(md.index("HIGH"), md.index("LOW"))
        for tag in ("(H1)", "(H2)", "(H3)"):
            self.assertIn(tag, md)


class TestCli(unittest.TestCase):
    def test_missing_file_exits_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "nope.json")
            buf = StringIO()
            with redirect_stdout(buf):
                rc = probe.main(["--ir", missing])
        self.assertEqual(rc, 3)

    def test_writes_json_and_md(self):
        ir = {
            "entities": [_entity("model", "block_reference", "*U172")],
            "block_definitions": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = os.path.join(tmp, "ir.json")
            with open(ir_path, "w", encoding="utf-8-sig") as fh:
                json.dump(ir, fh)
            out_json = os.path.join(tmp, "out.json")
            out_md = os.path.join(tmp, "out.md")

            buf = StringIO()
            with redirect_stdout(buf):
                rc = probe.main(["--ir", ir_path, "--out-json", out_json, "--out-md", out_md])

            self.assertEqual(rc, 0)
            with open(out_json, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data["schema"], "ariadne.anon_block_probe.v1")
            self.assertIn("*U172", data["undefined"])
            with open(out_md, encoding="utf-8") as fh:
                md_text = fh.read()
            self.assertIn("*U172", md_text)


if __name__ == "__main__":
    unittest.main()
