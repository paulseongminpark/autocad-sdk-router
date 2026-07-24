#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer -- reconcile <-> familyHasOp() family-gate PARITY.

Intent (WHY):
  tools/reconcile_native_registry.py builds the native live-gate op universe
  (all_coded_ops) by scanning each family module's `<gate>HasOp()` body. The
  AUTHORITATIVE list of which family gates actually admit an op at runtime is
  familyHasOp() in AriadneNativeJob.cpp:

      return m08cHasOp(op) || ... || m08nHasOp(op)
          || w6LayerStateHasOp(op) || w6dynblkHasOp(op) || w6sectionHasOp(op)
          || materialsReadHasOp(op) || annoscaleReadHasOp(op);

  The reconcile tool discovers m08{letter}HasOp gates by a filename regex
  (RE_FAMFILE) and the 5 non-m08 gates from an explicit list (_NON_M08_FAMILIES).
  If those two sources drift from familyHasOp() -- a new family added to the
  .cpp gate but not to reconcile (or vice versa) -- reconcile silently
  UNDER-counts the live-gate universe and check_vocab_lockstep falsely reports
  no_live_hasop for the orphaned family's ops. That exact drift (w6/w7 omitted)
  under-counted the universe by 15 ops until 2026-07-13. This test fails CI on
  any such future drift. Source-level (no AutoCAD/build needed).

Stdlib only. Discoverable by pytest and unittest.
"""
from __future__ import annotations

import os
import re
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_SRC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "AriadneNativeJob.cpp")
_TOOLS = os.path.join(_REPO, "tools")

if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
import reconcile_native_registry as rec  # noqa: E402


def _familyhasop_gate_fns(src):
    """The set of `<name>HasOp` fns familyHasOp() actually ORs together --
    the runtime's authoritative family-admission gate."""
    m = re.search(r"bool\s+familyHasOp\s*\([^)]*\)\s*\{(.*?)\}", src, re.S)
    assert m, "familyHasOp() definition not found in AriadneNativeJob.cpp"
    return set(re.findall(r"(\b\w+HasOp)\s*\(\s*op\s*\)", m.group(1)))


def _reconcile_gate_fns():
    """The set of `<name>HasOp` fns reconcile_native_registry.py scans --
    m08{letter}HasOp for every auto-discovered m08 family PLUS the explicit
    non-m08 list. Mirrors discover_families()'s own two sources exactly."""
    fams = rec.discover_families(None)
    non_m08_keys = {key for key, _, _, _ in rec._NON_M08_FAMILIES}
    non_m08_gate = {hasop for _, _, hasop, _ in rec._NON_M08_FAMILIES}
    gates = set(non_m08_gate)
    for key in fams:
        if key not in non_m08_keys:
            gates.add("m08" + key + "HasOp")
    return gates


class TestReconcileFamilyGateParity(unittest.TestCase):
    def setUp(self):
        with open(_SRC, "r", encoding="utf-8", errors="replace") as f:
            self.src = f.read()

    def test_gate_sets_match_exactly(self):
        cpp = _familyhasop_gate_fns(self.src)
        rc = _reconcile_gate_fns()
        missing = cpp - rc   # gate in .cpp that reconcile does NOT scan (under-count)
        extra = rc - cpp     # gate reconcile scans that .cpp no longer admits (over-count)
        self.assertEqual(
            cpp, rc,
            "familyHasOp() <-> reconcile family gate DRIFT.\n"
            "  in familyHasOp() but NOT scanned by reconcile (under-count): %s\n"
            "  scanned by reconcile but NOT in familyHasOp() (over-count):  %s\n"
            "  -> add/remove the family in tools/reconcile_native_registry.py "
            "(_NON_M08_FAMILIES or the m08 file) to match the .cpp gate."
            % (sorted(missing), sorted(extra)),
        )

    def test_all_16_families_discovered(self):
        # regression floor: the 2026-07-13 fix brought this from 11 to 16.
        fams = rec.discover_families(None)
        self.assertGreaterEqual(
            len(fams), 16,
            "discover_families() found %d families (<16). The w6/w7 non-m08 "
            "families may have regressed out of _NON_M08_FAMILIES." % len(fams),
        )

    def test_non_m08_gate_bodies_are_parseable(self):
        # every non-m08 gate must yield a non-empty op set (a rename that breaks
        # _hasop_body's anchor would silently return {} and under-count again).
        for key, fn, hasop_fn, _label in rec._NON_M08_FAMILIES:
            path = os.path.join(rec.FAMILIES_DIR, fn)
            self.assertTrue(os.path.exists(path), "missing family file: %s" % fn)
            ops, _unresolved = rec.parse_family(path, hasop_fn)
            self.assertTrue(
                ops,
                "non-m08 family %s (%s -> %s) parsed to an EMPTY op set -- the "
                "gate fn name or _hasop_body anchor drifted." % (key, fn, hasop_fn),
            )


if __name__ == "__main__":
    unittest.main()
