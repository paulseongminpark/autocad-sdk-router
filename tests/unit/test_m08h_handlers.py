#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08H TEST -- native WRITE family: dimensions / annotations / hatch (staged-write).

Intent (WHY):
  M08H fills families/m08h_handlers.inc with the staged-WRITE annotation / dimension /
  hatch op subset. The invariants that carry business meaning and must fail CI if
  violated:

  1. HASOP <-> DISPATCH PARITY -- every op id m08hHasOp admits must have an
     `op == "<id>"` branch in m08hDispatch, and every dispatch branch must be admitted
     by HasOp. Drift => OPERATION_DISPATCH_MISMATCH at runtime (a catalogued op reads
     as "implemented" but no handler claims it, or a handler is dead because the gate
     rejects it). The native build proves it compiles+links; this proves the seam is
     coherent.

  2. HASOP LISTS EXACTLY THE IMPLEMENTED SET -- guards a silent shrink (a refactor
     dropping ops) or a silent fake-grow (claiming ops with no handler).

  3. DEFERRED OPS STAY OUT OF HASOP -- leader / mleader / table are NOT feasible to
     build into a *valid* annotation hostless (they need an mleader/table STYLE +
     content layout that accoreconsole's seed DB does not carry). They must keep
     returning the honest OPERATION_NOT_IMPLEMENTED -- never faked into HasOp.

  4. STAGED-WRITE SAFETY (source-level) -- this family appends entities into the
     staged in-memory model space ONLY. It must NEVER persist the original DWG nor
     drive the command stack: no save(/saveAs/writeDwgFile/_QSAVE, and no
     acedCommand/acedCmd/acedInvoke (compile-disabled in 2027 + would mutate the
     attended doc). It is a WRITE family, so it legitimately USES appendAcDbEntity +
     kForWrite (the opposite of the READ families). All emitted strings go through
     njsonStr (UTF-8 fidelity for the Korean layer/text case); the lossy wideToAscii
     funnel must be absent.

  5. ARG VALIDATION -- geometry/annotation handlers must surface MISSING_ARG when the
     required points are absent, not fabricate a degenerate entity. The dispatch-
     mismatch guard must exist (no silent fall-through).

  Source-level only (no AutoCAD/build needed). Stdlib only. The native build is the
  separate, authoritative link gate (tools/build_native_acad.ps1).
"""
from __future__ import annotations

import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "m08h_handlers.inc")

# Implemented (12): annotation (2) + dimensions (9) + hatch (1).
_ANNOTATION = [
    "write.entity.text",
    "write.entity.mtext",
]
_DIMENSIONS = [
    "write.entity.dim.aligned",
    "write.entity.dim.rotated",
    "write.entity.dim.radial",
    "write.entity.dim.diametric",
    "write.entity.dim.angular2line",
    "write.entity.dim.angular3pt",
    "write.entity.dim.ordinate",
    "write.entity.dim.arc",
    "write.entity.dim.radiallarge",
]
_HATCH = [
    "write.entity.hatch",
]
_IMPLEMENTED = _ANNOTATION + _DIMENSIONS + _HATCH

# Deferred/hard-blocked ops that must NOT appear in HasOp (honest contract).
# leader  -> AcDbLeader: needs an annotation (mtext/block) association + appendVertex
#            sequence to be a valid leader; a bare leader with no annotation is degenerate.
# mleader -> AcDbMLeader: requires an MLeaderStyle dictionary entry + a content block /
#            mtext content object; the headless seed DB has no usable mleader style/content.
# table   -> AcDbTable: requires a TableStyle id + a cell/row/column layout; not constructible
#            into a valid table hostless without a table style in the seed DB.
_DEFERRED = [
    "write.entity.leader",
    "write.entity.mleader",
    "write.entity.table",
]


def _read():
    with open(_INC, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _strip_comments(src):
    """Remove C++ // line and /* */ block comments so banned-CODE-token scans do not
    trip on prose. The safety/contract comments legitimately MENTION save()/saveAs()/
    acedCommand to explain why they are forbidden; the ban is on executable code."""
    # block comments
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    # line comments
    src = re.sub(r"//[^\n]*", " ", src)
    return src


def _hasop_region(src):
    m = re.search(r"static bool m08hHasOp\(const std::string& op\)\s*\{(.*?)\n\}", src, re.S)
    assert m, "m08hHasOp not found"
    return m.group(1)


def _dispatch_region(src):
    m = re.search(r"static bool m08hDispatch\(.*?\)\s*\{(.*)\n\}\s*$", src, re.S)
    assert m, "m08hDispatch not found"
    return m.group(1)


def _hasop_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _hasop_region(src)))


def _dispatch_ops(src):
    # Exclude the dispatch-mismatch guard message (it contains no `op == "..."`).
    return set(re.findall(r'op == "([^"]+)"', _dispatch_region(src)))


class TestM08HHandlers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read()
        cls.hasop = _hasop_ops(cls.src)
        cls.dispatch = _dispatch_ops(cls.src)

    def test_inc_file_exists(self):
        self.assertTrue(os.path.exists(_INC), f"missing {_INC}")

    def test_signatures_present(self):
        self.assertRegex(self.src, r"bool\s+m08hHasOp\(const std::string& op\)")
        self.assertRegex(
            self.src,
            r"bool\s+m08hDispatch\(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r\)",
        )

    def test_hasop_lists_exactly_implemented(self):
        self.assertEqual(
            self.hasop, set(_IMPLEMENTED),
            "m08hHasOp op set drifted; only_in_src=%s missing_from_src=%s"
            % (sorted(self.hasop - set(_IMPLEMENTED)), sorted(set(_IMPLEMENTED) - self.hasop)),
        )

    def test_implemented_count(self):
        # Group totals: annotation=2, dimensions=9, hatch=1 => 12 real staged-write handlers.
        # The remaining 3 of the 15-op brief are the _DEFERRED (style/content-bound) ones,
        # left OUT of HasOp on purpose (no fake pass).
        self.assertEqual(len(_ANNOTATION), 2)
        self.assertEqual(len(_DIMENSIONS), 9)
        self.assertEqual(len(_HATCH), 1)
        self.assertEqual(len(_IMPLEMENTED), 12)
        self.assertEqual(len(set(_IMPLEMENTED)), 12, "duplicate op id in the implemented list")
        self.assertEqual(len(self.hasop), 12)

    def test_no_deferred_op_in_hasop(self):
        leaked = sorted(self.hasop & set(_DEFERRED))
        self.assertEqual(leaked, [], "deferred/style-bound ops leaked into m08hHasOp: %s" % leaked)

    def test_hasop_dispatch_parity(self):
        missing = sorted(set(_IMPLEMENTED) - self.dispatch)
        self.assertEqual(missing, [], "implemented ops with no dispatch branch: %s" % missing)
        extra = sorted(self.dispatch - self.hasop)
        self.assertEqual(extra, [], "dispatch branches not admitted by HasOp: %s" % extra)

    def test_staged_write_no_original_persist_tokens(self):
        # WRITE family: stage into the in-memory DB only; never persist the original
        # DWG nor drive the command stack. Scanned over comment-stripped CODE (the
        # contract comments legitimately name these tokens to explain the ban).
        code = _strip_comments(self.src)
        banned = [
            r"\bsaveAs\b",
            r"\bsave\s*\(",
            r"_QSAVE",
            r"\bwriteDwgFile\b",
            r"\bacedCommand\b",
            r"\bacedCmd\b",
            r"\bacedInvoke\b",
        ]
        for pat in banned:
            self.assertIsNone(
                re.search(pat, code),
                "WRITE family must not contain original-persist/command-stack token: %s" % pat,
            )

    def test_is_a_write_family(self):
        # Opposite of the READ families: it must append entities for write.
        self.assertIn("appendAcDbEntity", self.src, "WRITE family must append entities")
        self.assertIn("AcDb::kForWrite", self.src, "WRITE family must open model space kForWrite")

    def test_strings_use_utf8_njsonstr_not_lossy_funnel(self):
        self.assertIn("njsonStr", self.src, "string emission must route through njsonStr")
        self.assertNotIn("wideToAscii(", self.src, "must not use the lossy wideToAscii funnel")
        # entity content must use the lossless UTF-8 -> UTF-16 path (Hangul fidelity).
        self.assertIn("utf8ToWide", self.src, "entity text/content must use utf8ToWide for UTF-8 fidelity")

    def test_arg_validation_and_dispatch_guard(self):
        self.assertIn("MISSING_ARG", self.src, "annotation/dim handlers must validate required args")
        self.assertIn("OPERATION_DISPATCH_MISMATCH", self.src, "must guard against silent fall-through")

    def test_dimensions_use_default_dimstyle(self):
        # All dimension subclasses take the DB default dim style id when none requested.
        self.assertIn("pDb->dimstyle()", self.src, "dimensions must bind the DB default dim style id")

    def test_hatch_is_solid_fill_single_loop(self):
        # The priority hatch target: a solid-fill external loop, evaluated.
        self.assertIn("AcDbHatch", self.src)
        self.assertIn("kPreDefined", self.src)
        self.assertIn("kExternal", self.src)
        self.assertIn("evaluateHatch", self.src)

    def test_dimension_classes_present(self):
        # Pin the concrete AcDb dimension classes (so a refactor cannot silently swap one out).
        for cls in (
            "AcDbAlignedDimension",
            "AcDbRotatedDimension",
            "AcDbRadialDimension",
            "AcDbDiametricDimension",
            "AcDb2LineAngularDimension",
            "AcDb3PointAngularDimension",
            "AcDbOrdinateDimension",
            "AcDbArcDimension",
            "AcDbRadialDimensionLarge",
        ):
            self.assertIn(cls, self.src, "missing dimension class %s" % cls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
