#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08C0 TEST -- family handler seam wiring.

Intent (WHY):
  The seam lets C-F READ-family teammates add native ops by filling ONE disjoint
  `.inc` file each, with zero edits to AriadneNativeJob.cpp / the .vcxproj -> parallel
  worktrees merge without conflict. That property holds ONLY if the dispatcher is
  actually wired to the family modules: the gate must ADMIT family-claimed ops
  (familyHasOp) and the dispatcher must ROUTE them (tryFamilyDispatch). If a refactor
  silently drops a family #include or the gate stops consulting familyHasOp, every
  family op would regress to OPERATION_NOT_IMPLEMENTED -- this test fails CI.

Stdlib only.
"""
from __future__ import annotations

import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_SRC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "AriadneNativeJob.cpp")
_FAM = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families")
_FAMILIES = ("c", "d", "e", "f")


def _read(p):
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


class TestM08C0FamilySeam(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read(_SRC)

    def test_four_family_inc_files_exist(self):
        for x in _FAMILIES:
            p = os.path.join(_FAM, f"m08{x}_handlers.inc")
            self.assertTrue(os.path.exists(p), f"missing family stub: {p}")

    def test_dispatcher_includes_all_families(self):
        for x in _FAMILIES:
            self.assertIn(f'#include "families/m08{x}_handlers.inc"', self.src,
                          f"AriadneNativeJob.cpp must #include the m08{x} family")

    def test_each_family_defines_hasop_and_dispatch(self):
        for x in _FAMILIES:
            body = _read(os.path.join(_FAM, f"m08{x}_handlers.inc"))
            self.assertRegex(body, rf"bool\s+m08{x}HasOp\(const std::string& op\)")
            self.assertRegex(body, rf"bool\s+m08{x}Dispatch\(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r\)")

    def test_ctx_struct_defined(self):
        self.assertRegex(self.src, r"struct AriadneJobCtx")
        self.assertIn("AcDbDatabase* pDb", self.src)

    def test_gate_admits_family_ops(self):
        # gate must consult familyHasOp, else family ops -> OPERATION_NOT_IMPLEMENTED
        self.assertIn("familyHasOp(op)", self.src)
        self.assertRegex(self.src, r"findAriadneNativeOp\(op\) == nullptr && !familyHasOp\(op\)")

    def test_dispatcher_routes_to_families(self):
        self.assertIn("tryFamilyDispatch(op, ctx, r)", self.src)
        # tryFamilyDispatch chains all four families
        m = re.search(r"static bool tryFamilyDispatch\(.*?\)\s*\{(.*?)\}", self.src, re.S)
        self.assertIsNotNone(m)
        for x in _FAMILIES:
            self.assertIn(f"m08{x}Dispatch(op, ctx, r)", m.group(1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
