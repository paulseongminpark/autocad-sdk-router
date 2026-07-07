#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MATERIALS-READ family fragment gate (wave-7 native follow-up).

Intent (WHY):
  The materials family lands in two synchronized halves: the native handler
  (families/materials_read.inc, compiled into the .arx) and the registry
  op-entries (reports/ops_fragments/nat.materials.json, unioned into
  config/operations.v2.json only after the native build + live proof). A
  fragment claiming an op the .inc does not dispatch -- or an .inc write path
  in a family declared read-only -- would be a fake-implementation drift; this
  test pins the two halves together OFFLINE (no compiler, no AutoCAD).
"""
from __future__ import annotations

import json
import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_FRAG = os.path.join(_REPO, "reports", "ops_fragments", "nat.materials.json")
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "materials_read.inc")
_REQUIRED_KEYS = ("id", "family", "status", "engine_tier", "handler", "write_level", "tests", "summary")


class TestMaterialsFragment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frag = json.load(open(_FRAG, encoding="utf-8-sig"))
        cls.inc = open(_INC, encoding="utf-8", errors="replace").read()

    def test_fragment_is_a_nonempty_array_of_wellformed_entries(self):
        self.assertIsInstance(self.frag, list)
        self.assertGreater(len(self.frag), 0)
        for o in self.frag:
            missing = [k for k in _REQUIRED_KEYS if k not in o]
            self.assertEqual(missing, [], f"{o.get('id')} missing keys: {missing}")
            self.assertEqual(o["status"], "implemented")
            self.assertEqual(o["handler"]["dispatcher_symbol"], "materialsReadDispatch")

    def test_every_fragment_op_is_dispatched_by_the_inc(self):
        # the .inc must contain each op id as a string literal (HasOp/Dispatch).
        for o in self.frag:
            self.assertIn('"%s"' % o["id"], self.inc,
                          f"{o['id']} claimed by fragment but not dispatched in materials_read.inc")

    def test_family_is_read_only_everywhere(self):
        for o in self.frag:
            wl = o["write_level"]
            self.assertEqual(wl["allowed_write_modes"], ["read"], o["id"])
            self.assertFalse(wl["original_write_default"], o["id"])
        # and the .inc has no write-path CODE (a comment line stating the
        # invariant is allowed; strip comments before scanning).
        code = "\n".join(l for l in self.inc.splitlines() if not l.lstrip().startswith("//"))
        for tok in ("kForWrite", "writeDwgFile", "_QSAVE", "acedCommand", "saveAs"):
            self.assertNotIn(tok, code, f"write-path token {tok!r} in read-only family code")

    def test_inc_defines_the_family_contract_pair(self):
        self.assertRegex(self.inc, r"bool\s+materialsReadHasOp\s*\(")
        self.assertRegex(self.inc, r"bool\s+materialsReadDispatch\s*\(")

    # w7-hardening regression guards -----------------------------------------
    # The first deployed build short-circuited tryFamilyDispatch: dispatch
    # emitted OPERATION_DISPATCH_MISMATCH (and returned true) for ops it did
    # NOT own, so later families in the || chain were unreachable (live-proof
    # failure: annoscale ops died inside materialsReadDispatch). The family
    # contract requires the m08d-style HasOp guard as the FIRST statement.
    def test_dispatch_guards_unowned_ops_with_hasop_first(self):
        self.assertRegex(
            self.inc,
            r"materialsReadDispatch\([^)]*\)\s*\{\s*if\s*\(!materialsReadHasOp\(op\)\)\s*return\s+false;",
            "materialsReadDispatch must open with the HasOp guard returning false "
            "for unowned ops (else the family chain is short-circuited)")

    def test_properties_handler_reads_the_claimed_material_api(self):
        # the fragment's native_api claims AcDbMaterial accessors; a handler
        # that only dumps xdata is a fake implementation (adversarial review
        # finding, wave-7). Pin the accessor calls at source level.
        self.assertIn("AcDbMaterial::cast", self.inc)
        for accessor in ("->ambient(", "->diffuse(", "->specular(", "->opacity(",
                         "->mode(", "->channelFlags(", "->illuminationModel("):
            self.assertIn(accessor, self.inc,
                          f"materials properties handler must call {accessor} "
                          "(fragment native_api claims it)")


if __name__ == "__main__":
    unittest.main()
