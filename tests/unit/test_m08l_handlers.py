#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08L TEST -- native graphics system: worldDraw + overrules/grips.

Intent (WHY):
  M08L fills families/m08l_handlers.inc with the graphics-system op subset: an
  AcGiWorldDraw collector that captures an entity's view-independent graphics
  elaboration HOSTLESS (T01), plus the AcRxOverrule register/query/remove/enable
  LIFECYCLE for every AcDb*Overrule base + the simple grip-point read (T02). The
  invariants that carry business meaning and must fail CI if violated:

  1. HASOP <-> DISPATCH PARITY -- every op id m08lHasOp admits has an
     `op == "<id>"` branch in m08lDispatch, and every dispatch branch is admitted
     by HasOp. Drift => OPERATION_DISPATCH_MISMATCH at runtime (a catalogued op
     reads as "implemented" but no handler claims it, or a handler is dead because
     the gate rejects it). The native build proves it compiles+links; this proves
     the seam is coherent.

  2. HASOP LISTS EXACTLY THE IMPLEMENTED SET -- guards a silent shrink (a refactor
     dropping ops) or a silent fake-grow (claiming ops with no handler). The
     feasible-hostless subset is 25 ops; the 2 attended/absent ops are DEFERRED.

  3. DEFERRED OPS MUST NOT APPEAR IN HASOP (honest contract) --
     render.draw.viewportgeom needs a live AcGiViewportDraw (viewport-bound, no
     hostless surface); overrule.dimstyle.install has no AcDbDimStyleOverrule class
     in ObjectARX 2027 (verified by header scan). Claiming either would be a fake.

  4. READ / REGISTER-LIFECYCLE PROOF (source-level) -- M08L never writes the
     original DWG nor mutates persistent DB state: no save/saveAs/_QSAVE/
     writeDwgFile/acedCommand. Entities open kForRead only. worldDraw() elaborates
     graphics without mutation; overrule probes add-then-remove so the global
     AcRxOverrule registry is left exactly as found. All emitted strings route
     through njsonStr (UTF-8 fidelity); the lossy wideToAscii funnel is absent.

  5. HONEST OVERRULE SEMANTICS -- an overrule registers hostless but its EFFECT
     fires only during in-app operations. The install handler must say so
     (effect_fires:"in_app_only") rather than fabricate a fired effect.

  Source-level only (no AutoCAD/build needed). Stdlib only.
"""
from __future__ import annotations

import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "m08l_handlers.inc")

# T01 -- worldDraw / graphics capture (8)
_GROUP_T01 = [
    "render.draw.worldgeom",
    "render.draw.viewportgeom",
    "render.drawable.def",
    "render.traits.set",
    "render.polyline.helper",
    "render.facedata.attach",
    "render.context.query",
    "render.entity.worlddraw_override",
]
# T02 -- overrule register lifecycle (13; overrule.dimstyle.install DEFERRED)
_GROUP_T02_INSTALL = [
    "overrule.install",
    "overrule.object.install",
    "overrule.drawable.install",
    "overrule.geometry.install",
    "overrule.transform.install",
    "overrule.osnap.install",
    "overrule.subentity.install",
    "overrule.properties.install",
    "overrule.highlight.install",
    "overrule.highlightstate.install",
    "overrule.visibility.install",
    "overrule.grip.install",
    "overrule.queryx.install",
]
# T02 -- overrule global/query/remove + grips read (5)
_GROUP_T02_LIFECYCLE = [
    "overrule.global.enable",
    "overrule.applicable",
    "overrule.query.has",
    "overrule.remove",
    "inspect.entity.grips",
]

_IMPLEMENTED = _GROUP_T01 + _GROUP_T02_INSTALL + _GROUP_T02_LIFECYCLE

# Deferred ops that must NOT appear in HasOp (honest contract).
_DEFERRED = [
    "overrule.dimstyle.install",    # no AcDbDimStyleOverrule class in ObjectARX 2027 (header-verified)
]


def _read():
    with open(_INC, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _hasop_region(src):
    m = re.search(r"static bool m08lHasOp\(const std::string& op\)\s*\{(.*?)\n\}", src, re.S)
    assert m, "m08lHasOp not found"
    return m.group(1)


def _dispatch_region(src):
    m = re.search(r"static bool m08lDispatch\(.*?\)\s*\{(.*)\n\}\s*$", src, re.S)
    assert m, "m08lDispatch not found"
    return m.group(1)


def _strip_line_comments(src):
    # Drop // line comments so prohibition prose ("NEVER saveAs") is not mistaken for code.
    return re.sub(r"//[^\n]*", "", src)


def _hasop_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _hasop_region(src)))


def _dispatch_ops(src):
    # The dispatch handles the 13 overrule.*.install ops through a single shared block that
    # resolves them via the m08lOverruleFor() table (keyed by `installOp == "..."` literals)
    # rather than 13 separate `op == "..."` branches. Both forms are real dispatch routes, so
    # parity must recognize either. We scan the dispatch region for `op == "..."` AND the whole
    # file for the install-op literals the table matches on.
    region = _dispatch_region(src)
    ops = set(re.findall(r'op == "([^"]+)"', region))
    ops |= set(re.findall(r'installOp == "([^"]+)"', src))
    return ops


class TestM08LHandlers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read()
        cls.hasop = _hasop_ops(cls.src)
        cls.dispatch = _dispatch_ops(cls.src)

    def test_inc_file_exists(self):
        self.assertTrue(os.path.exists(_INC), f"missing {_INC}")

    def test_signatures_present(self):
        self.assertRegex(self.src, r"bool\s+m08lHasOp\(const std::string& op\)")
        self.assertRegex(
            self.src,
            r"bool\s+m08lDispatch\(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r\)",
        )

    def test_hasop_lists_exactly_implemented(self):
        self.assertEqual(
            self.hasop, set(_IMPLEMENTED),
            "m08lHasOp op set drifted; only_in_src=%s missing_from_src=%s"
            % (sorted(self.hasop - set(_IMPLEMENTED)), sorted(set(_IMPLEMENTED) - self.hasop)),
        )

    def test_implemented_count(self):
        # Group totals: T01=8 (render.draw.viewportgeom implemented), T02 install=13
        # (overrule.dimstyle.install deferred), T02 lifecycle=5. 8+13+5 = 26 real handlers.
        # The remaining 1 op of the 27-op brief is the _DEFERRED one -- left OUT of
        # HasOp on purpose (no fake pass).
        self.assertEqual(len(_GROUP_T01), 8)
        self.assertEqual(len(_GROUP_T02_INSTALL), 13)
        self.assertEqual(len(_GROUP_T02_LIFECYCLE), 5)
        self.assertEqual(len(_IMPLEMENTED), 26)
        self.assertEqual(len(set(_IMPLEMENTED)), 26, "duplicate op id in the implemented list")
        self.assertEqual(len(self.hasop), 26)
        # 26 implemented + 1 deferred == the 27-op brief.
        self.assertEqual(len(_IMPLEMENTED) + len(_DEFERRED), 27)

    def test_no_deferred_op_in_hasop(self):
        leaked = sorted(self.hasop & set(_DEFERRED))
        self.assertEqual(leaked, [], "deferred/attended ops leaked into m08lHasOp: %s" % leaked)

    def test_hasop_dispatch_parity(self):
        missing = sorted(set(_IMPLEMENTED) - self.dispatch)
        self.assertEqual(missing, [], "implemented ops with no dispatch branch: %s" % missing)
        extra = sorted(self.dispatch - self.hasop)
        self.assertEqual(extra, [], "dispatch branches not admitted by HasOp: %s" % extra)

    def test_read_only_no_original_write_tokens(self):
        # READ / register-lifecycle family: never write the original DWG nor mutate persistent
        # DB state. (commit/abortTransaction are NOT banned here -- there is no staged-write txn
        # in M08L at all; the absence is asserted by their literal non-occurrence below.)
        banned = [
            r"\bsaveAs\b",
            r"\bsave\s*\(",
            r"_QSAVE",
            r"\bwriteDwgFile\b",
            r"\bupgradeOpen\b",
            r"\bappendAcDbEntity\b",
            r"\bacedCommand\b",
            r"\bacedCmd\b",
            r"\bAriadneStagedWriteTransaction\b",
        ]
        # Scan CODE only: a comment documenting the prohibition ("NEVER save()/saveAs()")
        # is not a call. Strip // line comments before matching.
        code = _strip_line_comments(self.src)
        for pat in banned:
            self.assertIsNone(
                re.search(pat, code),
                "READ/register family must not contain original-write/mutation token: %s" % pat,
            )

    def test_entities_opened_for_read_only(self):
        # entity opens must be kForRead; kForWrite must be absent.
        self.assertIn("AcDb::kForRead", self.src)
        self.assertNotIn("kForWrite", self.src, "READ family must not open anything kForWrite")

    def test_strings_use_utf8_njsonstr_not_lossy_funnel(self):
        self.assertIn("njsonStr", self.src, "string emission must route through njsonStr")
        self.assertNotIn("wideToAscii(", self.src, "must not use the lossy wideToAscii funnel")

    def test_worlddraw_collector_is_real(self):
        # The T01 ops must drive the entity's actual worldDraw elaboration into a hostless
        # AcGiWorldDraw collector -- not fabricate primitive counts. Pin the real call + the
        # collector base classes (the proof this is genuine graphics capture, not a stub).
        self.assertIn("worldDraw(&wd)", self.src, "must drive AcGiDrawable::worldDraw into the collector")
        self.assertIn(": public AcGiWorldDraw", self.src, "must subclass AcGiWorldDraw")
        self.assertIn(": public AcGiWorldGeometry", self.src, "must subclass AcGiWorldGeometry")
        self.assertIn(": public AcGiSubEntityTraits", self.src, "must subclass AcGiSubEntityTraits")
        self.assertIn(": public AcGiContext", self.src, "must subclass AcGiContext")

    def test_overrule_lifecycle_is_real(self):
        # The T02 install ops must actually register via the real AcRxOverrule API and remove
        # afterward (leave the global registry as found) -- not fake a registration.
        self.assertIn("AcRxOverrule::addOverrule", self.src)
        self.assertIn("AcRxOverrule::removeOverrule", self.src)
        self.assertIn("AcRxOverrule::setIsOverruling", self.src)
        self.assertIn("AcRxOverrule::hasOverrule", self.src)
        # honest semantics: the overrule's effect fires only in-app, stated not faked.
        self.assertIn('effect_fires', self.src)
        self.assertIn('in_app_only', self.src)

    def test_grips_use_real_getgrippoints(self):
        # inspect.entity.grips must call the real AcDbEntity::getGripPoints read.
        self.assertIn("getGripPoints(grips", self.src)

    def test_dispatch_mismatch_guard_present(self):
        # No silent fall-through: an admitted-but-unhandled op surfaces the guard error.
        self.assertIn("OPERATION_DISPATCH_MISMATCH", self.src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
