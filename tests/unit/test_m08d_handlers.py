#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08D TEST -- native entities / geometry-kernel / BRep-solid READ handlers.

Intent (WHY):
  M08D fills families/m08d_handlers.inc with the READ-only entity / AcGe geometry-
  kernel / AcBr BRep-topology op subset. The invariants that carry business meaning
  and must fail CI if violated:

  1. HASOP <-> DISPATCH PARITY -- every op id m08dHasOp admits must have an
     `op == "<id>"` branch in m08dDispatch, and every dispatch branch must be admitted
     by HasOp. Drift => OPERATION_DISPATCH_MISMATCH at runtime (a catalogued op reads
     as "implemented" but no handler claims it, or a handler is dead because the gate
     rejects it). The native build proves it compiles+links; this proves the seam is
     coherent.

  2. HASOP LISTS EXACTLY THE IMPLEMENTED SET -- guards a silent shrink (a refactor
     dropping ops) or a silent fake-grow (claiming ops with no handler).

  3. READ-ONLY PROOF (source-level) -- the .inc is a READ family: it must contain no
     original-DWG-write / db-mutation token (saveAs, save(, _QSAVE, appendAcDbEntity,
     upgradeOpen, transformBy on a DB entity, acedCommand, abortTransaction-escape).
     It opens entities kForRead only and binds AcBr read-only. All emitted strings go
     through njsonStr (UTF-8 fidelity); the lossy wideToAscii funnel must be absent.

  4. AcBr LINK PROVENANCE -- the BRep group links the REAL AcBr import lib (acbr26.lib
     under utils\\brep\\lib-x64), NOT AcDrawBridge.lib (the research slice's claim was
     wrong: AcDrawBridge.lib carries zero AcBr symbols -- verified by dumpbin). This
     test pins that correction so a future edit cannot silently regress to the
     non-existent-symbol lib and break the build.

  Source-level only (no AutoCAD/build needed). Stdlib only.
"""
from __future__ import annotations

import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "m08d_handlers.inc")

# Group A -- entities (4)
_GROUP_A = [
    "inspect.entity.common",
    "inspect.entity.geomextents",
    "inspect.entity.osnap",
    "inspect.curve.protocol",
]
# Group B -- geometry kernel (18; AcGe pure compute + 2 DB entity-pair computes)
_GROUP_B = [
    "compute.geometry.point.distance",
    "compute.geometry.point.transform",
    "compute.geometry.matrix.build",
    "compute.geometry.matrix.compose",
    "compute.geometry.scale.build",
    "compute.geometry.lineseg",
    "compute.geometry.circarc",
    "compute.geometry.elliparc",
    "compute.geometry.tolerance",
    "compute.geometry.curve.eval",
    "compute.geometry.curve.sample",
    "compute.geometry.curve.closest",
    "compute.geometry.curve.intersect",
    "compute.geometry.nurbcurve",
    "compute.geometry.compositecurve",
    "compute.geometry.surface.nurb",
    "compute.entity.intersect",
    "compute.solid3d.interference",
]
# Group C (main-path subentity reads on AcDbEntity; no AcBr lib) (3)
_GROUP_C_SUBENT = [
    "inspect.subentity.geom_extents",
    "inspect.subentity.class_id",
    "inspect.subentity.ptr",
]
# Group C -- AcBr BRep topology (48)
_GROUP_C_BREP = [
    "inspect.brep.from_entity",
    "inspect.brep.validate",
    "inspect.brep.changed",
    "inspect.brep.validation_level",
    "inspect.brep.bounds",
    "inspect.brep.owner",
    "inspect.brep.solid_roundtrip",
    "inspect.brep.from_subentpath",
    "compute.brep.volume",
    "compute.brep.surface_area",
    "compute.brep.perimeter",
    "compute.brep.massprops",
    "compute.brep.point_containment",
    "compute.brep.line_containment",
    "traverse.brep.complexes",
    "traverse.brep.shells",
    "traverse.brep.faces",
    "traverse.brep.edges",
    "traverse.brep.vertices",
    "traverse.complex.shells",
    "traverse.shell.faces",
    "traverse.face.loops",
    "traverse.loop.edges",
    "traverse.loop.vertices",
    "traverse.edge.loops",
    "traverse.vertex.edges",
    "traverse.vertex.loops",
    "inspect.shell.type",
    "inspect.shell.complex",
    "inspect.face.area",
    "inspect.face.orientation",
    "inspect.face.shell",
    "inspect.face.surface",
    "inspect.face.surface_type",
    "inspect.face.surface_as_nurb",
    "inspect.face.surface_as_trimmed_nurbs",
    "inspect.edge.curve",
    "inspect.edge.curve_type",
    "inspect.edge.curve_as_nurb",
    "inspect.edge.orientation",
    "inspect.edge.vertices",
    "inspect.vertex.point",
    "inspect.loop.type",
    "inspect.loop.face",
]

_IMPLEMENTED = _GROUP_A + _GROUP_B + _GROUP_C_SUBENT + _GROUP_C_BREP

# Deferred/hard-blocked ops that must NOT appear in HasOp (honest contract).
_DEFERRED = [
    "ui.subentity.highlight",            # attended/graphics (live editor + GS flush)
    "inspect.subentity.markers_at_path",  # editor-bound (GS marker from interactive pick)
    "inspect.subentity.path_at_marker",   # editor-bound
    "inspect.subentity.color",            # AcDbSubentColor header unverified in SDK inc
]


def _read():
    with open(_INC, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _hasop_region(src):
    m = re.search(r"static bool m08dHasOp\(const std::string& op\)\s*\{(.*?)\n\}", src, re.S)
    assert m, "m08dHasOp not found"
    return m.group(1)


def _dispatch_region(src):
    m = re.search(r"static bool m08dDispatch\(.*?\)\s*\{(.*)\n\}\s*$", src, re.S)
    assert m, "m08dDispatch not found"
    return m.group(1)


def _hasop_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _hasop_region(src)))


def _dispatch_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _dispatch_region(src)))


class TestM08DHandlers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read()
        cls.hasop = _hasop_ops(cls.src)
        cls.dispatch = _dispatch_ops(cls.src)

    def test_inc_file_exists(self):
        self.assertTrue(os.path.exists(_INC), f"missing {_INC}")

    def test_signatures_present(self):
        self.assertRegex(self.src, r"bool\s+m08dHasOp\(const std::string& op\)")
        self.assertRegex(
            self.src,
            r"bool\s+m08dDispatch\(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r\)",
        )

    def test_hasop_lists_exactly_implemented(self):
        self.assertEqual(
            self.hasop, set(_IMPLEMENTED),
            "m08dHasOp op set drifted; only_in_src=%s missing_from_src=%s"
            % (sorted(self.hasop - set(_IMPLEMENTED)), sorted(set(_IMPLEMENTED) - self.hasop)),
        )

    def test_implemented_count(self):
        # Group totals: A=4 entities, B=18 geometry-kernel, subent=3 (main-path
        # AcDbEntity subentity reads), brep=44 (AcBr). 4+18+3+44 = 69 real handlers.
        # The remaining ops of the 73-op brief are the 4 _DEFERRED (editor/graphics/
        # unverified-header) ones -- left OUT of HasOp on purpose (no fake pass).
        self.assertEqual(len(_GROUP_A), 4)
        self.assertEqual(len(_GROUP_B), 18)
        self.assertEqual(len(_GROUP_C_SUBENT), 3)
        self.assertEqual(len(_GROUP_C_BREP), 44)
        self.assertEqual(len(_IMPLEMENTED), 69)
        self.assertEqual(len(set(_IMPLEMENTED)), 69, "duplicate op id in the implemented list")
        self.assertEqual(len(self.hasop), 69)

    def test_no_deferred_op_in_hasop(self):
        leaked = sorted(self.hasop & set(_DEFERRED))
        self.assertEqual(leaked, [], "deferred/editor-bound ops leaked into m08dHasOp: %s" % leaked)

    def test_hasop_dispatch_parity(self):
        missing = sorted(set(_IMPLEMENTED) - self.dispatch)
        self.assertEqual(missing, [], "implemented ops with no dispatch branch: %s" % missing)
        extra = sorted(self.dispatch - self.hasop)
        self.assertEqual(extra, [], "dispatch branches not admitted by HasOp: %s" % extra)

    def test_read_only_no_original_write_tokens(self):
        # READ family: never write the original DWG nor mutate DB state.
        banned = [
            r"\bsaveAs\b",
            r"\bsave\s*\(",
            r"_QSAVE",
            r"\bwriteDwgFile\b",
            r"\bupgradeOpen\b",
            r"\bappendAcDbEntity\b",
            r"\bacedCommand\b",
            r"\bacedCmd\b",
            r"\bcommit\s*\(",          # no staged-write commit in a read family
            r"\babortTransaction\b",
            r"\btransformSubentPathsBy\b",  # subentity WRITE (mutates the solid)
            r"\baddSubentPaths\b",
            r"\bdeleteSubentPaths\b",
        ]
        for pat in banned:
            self.assertIsNone(
                re.search(pat, self.src),
                "READ family must not contain original-write/mutation token: %s" % pat,
            )

    def test_entities_opened_for_read_only(self):
        # entity opens must be kForRead; kForWrite must be absent.
        self.assertIn("AcDb::kForRead", self.src)
        self.assertNotIn("kForWrite", self.src, "READ family must not open anything kForWrite")

    def test_strings_use_utf8_njsonstr_not_lossy_funnel(self):
        self.assertIn("njsonStr", self.src, "string emission must route through njsonStr")
        self.assertNotIn("wideToAscii(", self.src, "must not use the lossy wideToAscii funnel")

    def test_acbr_links_real_lib_not_drawbridge(self):
        # AcBr import lib is acbr26.lib (utils\\brep\\lib-x64), NOT AcDrawBridge.lib.
        # Check the actual LINKAGE (#pragma comment(lib,...)), not prose: the file
        # legitimately MENTIONS AcDrawBridge.lib in a comment explaining why it is wrong.
        pragma_libs = re.findall(r'#pragma comment\(lib,\s*"([^"]+)"\)', self.src)
        pragma_leaves = [os.path.basename(p).lower() for p in pragma_libs]
        self.assertIn("acbr26.lib", pragma_leaves, "BRep group must link the real AcBr import lib acbr26.lib")
        self.assertNotIn(
            "acdrawbridge.lib", pragma_leaves,
            "AcDrawBridge.lib carries zero AcBr symbols (verified by dumpbin); must not be linked for AcBr",
        )
        # AcDb3dSolid / AcGeNurbSurface come from acgeoment.lib (the brep sample's own dep).
        self.assertIn("acgeoment.lib", pragma_leaves)

    def test_brep_caller_owned_heap_is_freed(self):
        # getSurface/getCurve/get(AcDb3dSolid*&)/getSurfaceAsTrimmedNurbs hand back
        # caller-owned heap; the handlers must delete to avoid leaks.
        self.assertIn("delete pSurf", self.src)
        self.assertIn("delete pCurve", self.src)
        self.assertIn("delete pSolid", self.src)
        self.assertIn("delete[] patches", self.src)
        self.assertIn("delete pContainer", self.src)

    def test_geometry_ops_validate_required_args(self):
        # pure-geometry handlers must surface MISSING_ARG, not fabricate output.
        self.assertIn("MISSING_ARG", self.src)
        # and the dispatch-mismatch guard exists (no silent fall-through).
        self.assertIn("OPERATION_DISPATCH_MISMATCH", self.src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
