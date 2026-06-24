#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08G TEST -- native WRITE family: entity-create + entity/geometry modify (staged-write).

Intent (WHY):
  M08G fills families/m08g_handlers.inc with the feasible-hostless subset of the
  WRITE op brief (45 ops): real ObjectARX entity creation (AcDb* ctor +
  appendAcDbEntity) and entity/geometry modify (transformBy / getTransformedCopy /
  explode / AcDbCurve offset|split|getSpline). The invariants that carry business
  meaning and must fail CI if violated:

  1. HASOP <-> DISPATCH PARITY -- every op id m08gHasOp admits must have an
     `op == "<id>"` branch in m08gDispatch, and every dispatch branch must be
     admitted by HasOp. Drift => OPERATION_DISPATCH_MISMATCH at runtime (a
     catalogued op reads as "implemented" but no handler claims it, or a handler is
     dead because the gate rejects it). The native build proves it compiles+links;
     this proves the seam is coherent.

  2. HASOP LISTS EXACTLY THE IMPLEMENTED SET -- guards a silent shrink (a refactor
     dropping ops) or a silent fake-grow (claiming ops with no handler). The
     deferred ops (ASM-modeler / external-resource / editor-bound) must NOT appear.

  3. STAGED-WRITE PROOF (source-level) -- a WRITE family legitimately mutates the
     STAGED db (appendAcDbEntity / kForWrite / transformBy), but it must NEVER
     write the ORIGINAL DWG nor drive the command stack: no save()/saveAs()/
     writeDwgFile/_QSAVE and no acedCommand/acedCmd/acedInvoke. All emitted strings
     route through njsonStr (UTF-8 fidelity); the lossy wideToAscii funnel is absent.

  4. NO-FAKE ERROR DISCIPLINE -- handlers surface structured emitNativeError codes
     (MISSING_ARG / *_FAILED / ENTITY_NOT_FOUND ...) instead of fabricating "ok",
     and the dispatch-mismatch guard exists (no silent fall-through).

  5. APPEND-OWNERSHIP HYGIENE -- the file uses the close()-on-success / delete()-on-
     failure idiom for appended entities and frees caller-owned heap returned by the
     explode/offset/split/getSpline protocols (no leaks, no dangling DB objects).

  Source-level only (no AutoCAD/build needed). Stdlib only.
"""
from __future__ import annotations

import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "m08g_handlers.inc")

# Entity-create ops implemented (real AcDb* ctor + appendAcDbEntity / owner append). (34)
_CREATE = [
    "write.entity.arc",
    "write.entity.ellipse",
    "write.entity.point",
    "write.entity.ray",
    "write.entity.xline",
    "write.entity.trace",
    "write.entity.solid2d",
    "write.entity.face",
    "write.entity.spline",
    "write.entity.polyline",
    "write.entity.polyline2d",
    "write.entity.polyline3d",
    "write.entity.attribdef",
    "write.entity.attribute",
    "write.entity.body",
    "write.entity.mline",
    "write.entity.mpolygon",
    "write.entity.nurbsurface",
    "write.entity.rasterimage",
    "write.entity.shape",
    "write.entity.solid3d.extrude",
    "write.entity.solid3d.loft",
    "write.entity.solid3d.primitive",
    "write.entity.solid3d.revolve",
    "write.entity.solid3d.sweep",
    "write.entity.subdmesh",
    "write.entity.surface",
    "write.entity.wipeout",
    "write.entity.polygonmesh",
    "write.entity.polyfacemesh",
    "write.entity.region",
    "write.entity.blockref",
    "write.entity.minsert",
    "write.entity.tolerance",
]
# Modify / geometry-edit ops implemented. (11)
_MODIFY = [
    "modify.entity.transform",
    "modify.entity.copy_transformed",
    "modify.entity.common",
    "modify.entity.explode",
    "modify.entity.solid3d.boolean",
    "modify.curve.offset",
    "modify.curve.split",
    "modify.curve.to_spline",
    "edit.subentity.add_paths",
    "edit.subentity.delete_paths",
    "edit.subentity.transform",
]

_IMPLEMENTED = _CREATE + _MODIFY

# Deferred/hard-blocked ops that must NOT appear in HasOp (honest contract).
# The original 3 editor-bound subentity mutations were reopened in Wave4X with an
# explicit staged AcDbFullSubentPath contract, so this family currently has no
# remaining deferred op tracked by this source-level test.
_DEFERRED = []


def _read():
    with open(_INC, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _strip_comments(src):
    """Remove // line comments and /* */ block comments so banned-token checks fire
    on real CODE only. The .inc legitimately MENTIONS save()/saveAs()/acedCommand in
    its safety header to document the prohibition (same pattern the M08D test uses for
    the AcDrawBridge.lib mention) -- the prose must not be a false positive."""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"//[^\n]*", " ", src)
    return src


def _hasop_region(src):
    m = re.search(r"static bool m08gHasOp\(const std::string& op\)\s*\{(.*?)\n\}", src, re.S)
    assert m, "m08gHasOp not found"
    return m.group(1)


def _dispatch_region(src):
    m = re.search(r"static bool m08gDispatch\(.*?\)\s*\{(.*)\n\}\s*$", src, re.S)
    assert m, "m08gDispatch not found"
    return m.group(1)


def _hasop_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _hasop_region(src)))


def _dispatch_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _dispatch_region(src)))


class TestM08GHandlers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read()
        cls.code = _strip_comments(cls.src)   # comment-free view for banned-token checks
        cls.hasop = _hasop_ops(cls.src)
        cls.dispatch = _dispatch_ops(cls.src)

    def test_inc_file_exists(self):
        self.assertTrue(os.path.exists(_INC), f"missing {_INC}")

    def test_signatures_present(self):
        self.assertRegex(self.src, r"bool\s+m08gHasOp\(const std::string& op\)")
        self.assertRegex(
            self.src,
            r"bool\s+m08gDispatch\(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r\)",
        )

    def test_hasop_lists_exactly_implemented(self):
        self.assertEqual(
            self.hasop, set(_IMPLEMENTED),
            "m08gHasOp op set drifted; only_in_src=%s missing_from_src=%s"
            % (sorted(self.hasop - set(_IMPLEMENTED)), sorted(set(_IMPLEMENTED) - self.hasop)),
        )

    def test_implemented_count(self):
        # 34 entity-create + 11 modify/subentity-edit = the full 45-op staged-write brief.
        self.assertEqual(len(_CREATE), 34)
        self.assertEqual(len(_MODIFY), 11)
        self.assertEqual(len(_IMPLEMENTED), 45)
        self.assertEqual(len(set(_IMPLEMENTED)), 45, "duplicate op id in the implemented list")
        self.assertEqual(len(self.hasop), 45)
        # the brief is 45 ops total: all are now implemented in this family.
        self.assertEqual(len(_IMPLEMENTED) + len(_DEFERRED), 45)
        self.assertEqual(len(set(_DEFERRED)), 0, "duplicate op id in the deferred list")

    def test_minimum_implemented_floor(self):
        # A sane floor independent of the exact list: at least 20 ops, and both the
        # create and modify halves must be non-trivially present.
        self.assertGreaterEqual(len(self.hasop), 20)
        self.assertGreaterEqual(len([o for o in self.hasop if o.startswith("write.entity.")]), 15)
        self.assertGreaterEqual(len([o for o in self.hasop if o.startswith("modify.")]), 5)

    def test_no_deferred_op_in_hasop(self):
        leaked = sorted(self.hasop & set(_DEFERRED))
        self.assertEqual(leaked, [], "deferred/blocked ops leaked into m08gHasOp: %s" % leaked)

    def test_hasop_dispatch_parity(self):
        missing = sorted(set(_IMPLEMENTED) - self.dispatch)
        self.assertEqual(missing, [], "implemented ops with no dispatch branch: %s" % missing)
        extra = sorted(self.dispatch - self.hasop)
        self.assertEqual(extra, [], "dispatch branches not admitted by HasOp: %s" % extra)

    def test_no_original_dwg_write_or_command_stack(self):
        # A WRITE family mutates the STAGED db (appendAcDbEntity / kForWrite is
        # expected & required) but must NEVER write the original DWG nor drive the
        # command stack.
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
                re.search(pat, self.code),
                "WRITE family must not contain original-write/command-stack token (in code): %s" % pat,
            )

    def test_does_real_staged_write(self):
        # Positive proof this is a genuine WRITE family (not a fake stub): it appends
        # entities and opens for write.
        self.assertIn("appendAcDbEntity", self.src, "entity-create must append to model space")
        self.assertIn("AcDb::kForWrite", self.src, "modify ops must open the staged target for write")
        self.assertIn("transformBy", self.src, "modify.entity.transform must call transformBy")
        self.assertIn("createBox", self.src, "solid primitive must call real AcDb3dSolid modeler API")
        self.assertIn("createExtrudedSolid", self.src, "solid extrude must call real modeler API")
        self.assertIn("AcDbMPolygon", self.src, "mpolygon must use real AcDbMPolygon")
        self.assertIn("AcDbRasterImageDef", self.src, "rasterimage must create an image definition")

    def test_strings_use_utf8_njsonstr_not_lossy_funnel(self):
        self.assertIn("njsonStr", self.src, "string emission must route through njsonStr")
        self.assertNotIn("wideToAscii(", self.src, "must not use the lossy wideToAscii funnel")

    def test_no_fake_success_error_discipline(self):
        # Handlers surface structured errors rather than fabricating "ok".
        self.assertIn("emitNativeError", self.src)
        self.assertIn("MISSING_ARG", self.src)
        self.assertIn("OPERATION_DISPATCH_MISMATCH", self.src)

    def test_append_ownership_hygiene(self):
        # close()-on-success / delete()-on-failure idiom present, and caller-owned
        # heap from the explode/offset/split protocols is freed (no leaks).
        self.assertIn("delete pEnt", self.src)
        self.assertIn("explode", self.src)
        self.assertIn("getOffsetCurves", self.src)
        self.assertIn("getSplitCurves", self.src)
        self.assertIn("getSpline", self.src)
        # the void-ptr-array piece appender frees failed/unappendable elements.
        self.assertRegex(self.src, r"delete static_cast<AcDbEntity\*>")

    def test_subentity_write_ops_use_real_apis_and_explicit_path_contract(self):
        self.assertIn('op == "edit.subentity.add_paths"', self.src)
        self.assertIn('op == "edit.subentity.delete_paths"', self.src)
        self.assertIn('op == "edit.subentity.transform"', self.src)
        self.assertIn("AcDbFullSubentPathArray", self.src)
        self.assertIn("m08gReadSubentPaths", self.src)
        self.assertIn("addSubentPaths", self.src)
        self.assertIn("deleteSubentPaths", self.src)
        self.assertIn("transformSubentPathsBy", self.src)
        self.assertIn("getGsMarkersAtSubentPath", self.src)
        self.assertIn("getSubentPathGeomExtents", self.src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
