#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08K TEST -- native custom object/entity/protocol lifecycle handlers.

Intent (WHY):
  M08K fills families/m08k_handlers.inc with the feasible-hostless subset of the custom
  object/entity/protocol lifecycle op family (ObjectARX RTTI / protocol extension /
  class registration / custom-object filer+clone / custom-entity geometry protocol). The
  invariants that carry business meaning and must fail CI if violated:

  1. HASOP <-> DISPATCH PARITY -- every op id m08kHasOp admits must have an
     `op == "<id>"` branch in m08kDispatch, and every dispatch branch must be admitted
     by HasOp. Drift => OPERATION_DISPATCH_MISMATCH at runtime (a catalogued op reads as
     "implemented" but no handler claims it, or a handler is dead because the gate rejects
     it). The native build proves it compiles+links; this proves the seam is coherent.

  2. HASOP LISTS EXACTLY THE IMPLEMENTED SET -- guards a silent shrink (a refactor
     dropping ops) or a silent fake-grow (claiming ops with no handler).

  3. WAVE3 CALLBACK OPS ARE REAL HANDLERS -- the former deferred custom entity/object
     callbacks now have native class overrides plus m08k dispatcher branches. The only
     claimed op kept out of HasOp is the install-time demand-register registry write,
     which is hard-blocked in the registry/report for safety and Pane-1 deploy ownership.

  4. STAGED-WRITE-ONLY / NO ORIGINAL-WRITE / NO EDITOR-COMMAND (source-level) -- the
     family operates on the router-staged copy and rolls every scratch mutation back; it
     must contain no original-DWG-write token (saveAs / save( / _QSAVE / writeDwgFile) and
     no editor-command reentrancy (acedCommand / acedCmd / acedInvoke) IN CODE (comments
     that name the bans for documentation are allowed and are stripped before scanning).
     All emitted strings go through njsonStr (UTF-8 fidelity); the lossy wideToAscii(
     funnel must be absent.

  5. LINKAGE-SAFE CUSTOM-CLASS ACCESS -- the custom Ariadne* classes' C++ ::desc()/::cast()
     symbols are NOT exported by the DBX import lib, so the family must reach them via the
     class dictionary (acrxClassDictionary->at) + the DBX extern "C" predicates, never via
     direct AriadneProbe::desc()/AriadneRecord::cast(). This test pins that so a future edit
     cannot regress to an unresolved-external (LNK2001) build break.

  Source-level only (no AutoCAD/build needed here; the build gate is build_native_acad.ps1).
  Stdlib only.
"""
from __future__ import annotations

import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "m08k_handlers.inc")

# --- IMPLEMENTED (44) -- grouped --------------------------------------------
_RTTI = [
    "inspect.runtime.cast",
    "inspect.runtime.desc",
    "inspect.runtime.isa",
    "inspect.runtime.iskindof",
    "inspect.proxy.detect",
]
_PROTOCOL = [
    "extend.protocol.declare",
    "extend.protocol.attach",
    "extend.protocol.detach",
    "extend.protocol.query",
]
_CLASS_REG = [
    "extend.customclass.declare",
    "extend.customclass.define",
    "extend.customclass.define_cons",
    "extend.customclass.define_dxf",
    "extend.customclass.define_nocons",
    "extend.customclass.rxinit",
    "extend.customclass.unregister",
    "extend.service.register",
    "extend.module.entrypoint",
    "extend.object_enabler.build",
    "extend.object_enabler.register_classes",
]
_OBJECT_LIFECYCLE = [
    "extend.customobject.define",
    "extend.customobject.embedded",
    "extend.customobject.filer_dwgout",
    "extend.customobject.filer_dwgin",
    "extend.customobject.filer_dxfout",
    "extend.customobject.filer_dxfin",
    "extend.customobject.partial_undo",
    "extend.customobject.deepclone",
    "extend.customobject.wblockclone",
    "extend.customobject.version",
]
_CUSTOM_ENTITY = [
    "extend.customentity.define",
    "extend.customentity.draw_world",
    "extend.customentity.draw_viewport",
    "extend.customentity.grips",
    "extend.customentity.osnap",
    "extend.customentity.stretch",
    "extend.customentity.db_defaults",
    "extend.customentity.geom_extents",
    "extend.customentity.explode",
    "extend.customentity.transform",
    "extend.customentity.intersect",
    "extend.customentity.list",
    "extend.customentity.subentpaths",
]
_CUSTOM_OSNAP = [
    "extend.osnap.custom_mode",
]

_IMPLEMENTED = _RTTI + _PROTOCOL + _CLASS_REG + _OBJECT_LIFECYCLE + _CUSTOM_ENTITY + _CUSTOM_OSNAP

# --- HARD-BLOCKED (must NOT appear in HasOp; registry/report carries blocker) --
_HARD_BLOCKED = [
    "extend.object_enabler.demand_register",  # HKLM demand-load/canonical deploy is Pane 1 only
]

# Invented / dead handler cleanup: this op was a teammate-added duplicate and must stay out
# of both HasOp and Dispatch; the registry-correct `extend.customentity.db_defaults` remains.
_DRIFT = [
    "extend.customobject.db_defaults",
]


def _read():
    with open(_INC, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _strip_comments(src):
    """Remove /* */ block comments and // line comments so code-only scans ignore prose
    (the file legitimately NAMES the banned tokens in its safety comments)."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def _hasop_region(src):
    m = re.search(r"static bool m08kHasOp\(const std::string& op\)\s*\{(.*?)\n\}", src, re.S)
    assert m, "m08kHasOp not found"
    return m.group(1)


def _dispatch_region(src):
    # dispatch is the last function in the file; take from its signature to EOF.
    i = src.index("static bool m08kDispatch")
    return src[i:]


def _hasop_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _hasop_region(src)))


def _dispatch_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _dispatch_region(src)))


class TestM08KHandlers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read()
        cls.code = _strip_comments(cls.src)
        cls.hasop = _hasop_ops(cls.src)
        cls.dispatch = _dispatch_ops(cls.src)

    def test_inc_file_exists(self):
        self.assertTrue(os.path.exists(_INC), f"missing {_INC}")

    def test_signatures_present(self):
        self.assertRegex(self.src, r"bool\s+m08kHasOp\(const std::string& op\)")
        self.assertRegex(
            self.src,
            r"bool\s+m08kDispatch\(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r\)",
        )

    def test_hasop_lists_exactly_implemented(self):
        self.assertEqual(
            self.hasop, set(_IMPLEMENTED),
            "m08kHasOp op set drifted; only_in_src=%s missing_from_src=%s"
            % (sorted(self.hasop - set(_IMPLEMENTED)), sorted(set(_IMPLEMENTED) - self.hasop)),
        )

    def test_implemented_count(self):
        # Group totals: RTTI=5, protocol=4, class-registration=11, object-lifecycle=10,
        # custom-entity=13, custom-osnap=1. 5+4+11+10+13+1 = 44 real handlers.
        self.assertEqual(len(_RTTI), 5)
        self.assertEqual(len(_PROTOCOL), 4)
        self.assertEqual(len(_CLASS_REG), 11)
        self.assertEqual(len(_OBJECT_LIFECYCLE), 10)
        self.assertEqual(len(_CUSTOM_ENTITY), 13)
        self.assertEqual(len(_CUSTOM_OSNAP), 1)
        self.assertEqual(len(_IMPLEMENTED), 44)
        self.assertEqual(len(set(_IMPLEMENTED)), 44, "duplicate op id in the implemented list")
        self.assertEqual(len(self.hasop), 44)

    def test_hard_blocked_install_time_op_not_in_hasop(self):
        leaked = sorted(self.hasop & set(_HARD_BLOCKED))
        self.assertEqual(leaked, [], "hard-blocked install/deploy ops leaked into m08kHasOp: %s" % leaked)

    def test_no_drift_op_in_hasop(self):
        leaked = sorted(self.hasop & set(_DRIFT))
        self.assertEqual(leaked, [], "invented/dead ops leaked into m08kHasOp: %s" % leaked)

    def test_no_drift_op_in_dispatch(self):
        leaked = sorted(self.dispatch & set(_DRIFT))
        self.assertEqual(leaked, [], "invented/dead ops leaked into m08kDispatch: %s" % leaked)

    def test_hasop_dispatch_parity(self):
        missing = sorted(set(_IMPLEMENTED) - self.dispatch)
        self.assertEqual(missing, [], "implemented ops with no dispatch branch: %s" % missing)
        extra = sorted(self.dispatch - self.hasop)
        self.assertEqual(extra, [], "dispatch branches not admitted by HasOp: %s" % extra)

    def test_no_original_write_or_editor_command_tokens_in_code(self):
        # Staged-write-only / no original-DWG-write / no editor-command reentrancy. Scanned
        # on COMMENTS-STRIPPED source: the file documents the bans in prose (allowed); the
        # CODE must be clean.
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
                "family CODE must not contain original-write/editor-command token: %s" % pat,
            )

    def test_staged_writes_never_committed(self):
        # Every clone/append op uses AriadneStagedWriteTransaction as pure scratch and rolls
        # back via the dtor: the family must never call .commit() (which would persist the
        # scratch into the staged DB) and must never hand-call abortTransaction.
        self.assertIsNone(re.search(r"\.commit\(\)", self.code),
                          "staged-write txns must roll back (no .commit() in M08K)")
        self.assertNotIn("abortTransaction", self.code,
                         "rollback is the dtor's job; no explicit abortTransaction")

    def test_strings_use_utf8_njsonstr_not_lossy_funnel(self):
        self.assertIn("njsonStr", self.src, "string emission must route through njsonStr")
        self.assertNotIn("wideToAscii(", self.code, "must not use the lossy wideToAscii funnel")

    def test_linkage_safe_custom_class_access(self):
        # The DBX import lib exports only extern "C" symbols, NOT the custom classes' C++
        # ::desc()/::cast(). Direct use would be LNK2001. The family must reach the custom
        # classes via the class dictionary + extern "C" predicates only.
        self.assertNotIn("AriadneProbe::desc(", self.code,
                         "direct AriadneProbe::desc() is an unresolved external; use acrxClassDictionary")
        self.assertNotIn("AriadneRecord::desc(", self.code,
                         "direct AriadneRecord::desc() is an unresolved external; use acrxClassDictionary")
        self.assertNotIn("AriadneProbe::cast(", self.code,
                         "direct AriadneProbe::cast() is an unresolved external; use isKindOf via dict desc")
        self.assertNotIn("AriadneRecord::cast(", self.code,
                         "direct AriadneRecord::cast() is an unresolved external; use the extern C predicate")
        # The linkage-safe primitives must be present.
        self.assertIn("acrxClassDictionary", self.code, "must look up custom classes by name")
        self.assertIn("ariadneIsRecordObject", self.code, "must use the extern C type predicate")

    def test_real_objectarx_apis_present(self):
        # Spot-check that the handlers do REAL ObjectARX work (not stubbed): the class-system,
        # protocol-extension, clone, and entity-protocol calls that ground the family.
        for token in [
            "newAcRxClass",            # runtime class declaration
            "acrxBuildClassHierarchy", # class hierarchy build
            "deleteAcRxClass",         # class teardown
            "->addX(",                 # protocol-extension attach
            "->delX(",                 # protocol-extension detach
            "->queryX(",               # protocol-extension query
            "deepCloneObjects",        # deep clone
            "wblockCloneObjects",      # wblock clone
            "acrxRegisterService",     # service registration
            "getGeomExtents",          # custom-entity geometry protocol
            "transformBy",             # custom-entity transform protocol
            "worldDraw",               # custom-entity world draw callback
            "viewportDraw",            # custom-entity viewport draw callback
            "getGripPoints",           # custom-entity grip protocol
            "moveGripPointsAt",        # custom-entity grip edit protocol
            "getOsnapPoints",          # custom-entity osnap protocol
            "getStretchPoints",        # custom-entity stretch protocol
            "moveStretchPointsAt",     # custom-entity stretch edit protocol
            "AcDbCustomOsnapInfo",     # custom osnap PE protocol
            "addCustomOsnapMode",      # custom osnap manager registration
            "applyPartialUndo",        # custom object partial undo override
            "getSubentPathsAtGsMarker",# subentity-path protocol
        ]:
            self.assertIn(token, self.code, "expected real ObjectARX call missing: %s" % token)

    def test_dispatch_mismatch_guard_present(self):
        # No silent fall-through: an op admitted by HasOp but unmatched surfaces a structured
        # OPERATION_DISPATCH_MISMATCH (mirrors the host dispatcher contract).
        self.assertIn("OPERATION_DISPATCH_MISMATCH", self.src)

    def test_missing_arg_validation_present(self):
        # Handle-bound ops must surface MISSING_ARG, not fabricate output.
        self.assertIn("MISSING_ARG", self.src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
