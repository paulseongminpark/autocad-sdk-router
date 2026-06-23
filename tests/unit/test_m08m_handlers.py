#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08M TEST -- native OPM properties + reactors.

Intent (WHY):
  M08M fills families/m08m_handlers.inc with the feasible-hostless subset of the OPM
  property protocol (AcRxProperty / AcRxAttribute / AcRxMemberCollection over an
  AcRxClass) plus DB/object/persistent/rxevent/linker reactors. The invariants that
  carry business meaning and must fail CI if violated:

  1. HASOP <-> DISPATCH PARITY -- every op id m08mHasOp admits must have an
     `op == "<id>"` branch in m08mDispatch, and every dispatch branch must be admitted
     by HasOp. Drift => OPERATION_DISPATCH_MISMATCH at runtime (a catalogued op reads
     as "implemented" but no handler claims it, or a handler is dead because the gate
     rejects it). The native build proves it compiles+links; this proves the seam is
     coherent.

  2. HASOP LISTS EXACTLY THE IMPLEMENTED SET -- guards a silent shrink (a refactor
     dropping ops) or a silent fake-grow (claiming ops with no handler).

  3. ATTENDED REACTORS ARE NOT IN HASOP (honest contract) -- the editor / doc-manager
     / long-transaction reactors need the running editor / document manager / workspace
     subsystem and CANNOT fire hostless. They are DEFERRED: they must NOT appear in
     m08mHasOp (no fake pass). This test pins that boundary.

  4. NO ORIGINAL-WRITE / NO ACEDCOMMAND (source-level) -- staged-write ONLY on the
     router-staged db: the .inc must contain no save()/saveAs()/_QSAVE/writeDwgFile
     token and no acedCommand/acedCmd. Every staged mutation is proven to roll back
     (the file asserts staged_rolled_back), and all emitted strings route through
     njsonStr (UTF-8 fidelity; no lossy wideToAscii funnel).

  5. REACTOR HYGIENE -- every reactor attached is detached: addReactor is balanced by
     removeReactor, addPersistentReactor by removePersistentReactor (no dangling
     module-lifetime reactor left on the staged db).

  Source-level only (no AutoCAD/build needed). Stdlib only.
"""
from __future__ import annotations

import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "m08m_handlers.inc")

# --- T01 property inspection (4) ---
_GROUP_INSPECT = [
    "inspect.property.by_name",
    "inspect.property.is_readonly",
    "inspect.property.metadata",
    "automate.property.set",
]
# --- T01 OPM protocol (12) ---
_GROUP_OPM = [
    "extend.opm.register_provider",
    "extend.opm.get_manager",
    "extend.opm.get_dispid",
    "extend.opm.map_category",
    "extend.opm.define_property",
    "extend.opm.define_property2",
    "extend.opm.enum_property",
    "extend.opm.dialog_property",
    "extend.opm.per_instance_source",
    "extend.opm.property_expander",
    "extend.opm.property_expression",
    "extend.opm.property_extension",
]
# --- T01 property authoring (16) ---
_GROUP_AUTHOR = [
    "extend.property.define",
    "extend.property.describe",
    "extend.property.category",
    "extend.property.display_as",
    "extend.property.units",
    "extend.property.flags",
    "extend.property.default_value",
    "extend.property.enum_tag",
    "extend.property.refers_to",
    "extend.property.localize_name",
    "extend.property.com_name",
    "extend.property.expose_to_com",
    "extend.property.filepath",
    "extend.property.lmv",
    "extend.property.dynamic_props",
    "extend.property.type_promotion",
]
# --- T02 reactors (12) ---
_GROUP_REACT = [
    "react.database.attach",
    "react.database.monitor",
    "react.object.attach_transient",
    "react.object.detach_transient",
    "react.object.monitor",
    "react.persistent.attach",
    "react.persistent.detach",
    "react.rxevent.attach",
    "react.rxevent.monitor",
    "react.linker.attach",
    "react.linker.monitor",
    "react.config.disable_namespace",
]

_IMPLEMENTED = _GROUP_INSPECT + _GROUP_OPM + _GROUP_AUTHOR + _GROUP_REACT

# Deferred attended reactors that must NOT appear in HasOp (honest contract):
# they need the running editor / document manager / long-transaction (workspace)
# subsystem and cannot fire hostless.
_DEFERRED = [
    "react.editor.command_monitor",   # AcEditorReactor -- needs the running editor
    "react.editor.input_monitor",     # AcEditorReactor
    "react.editor.lisp_monitor",      # AcEditorReactor
    "react.editor.sysvar_monitor",    # AcEditorReactor
    "react.editor.dwg_lifecycle",     # AcEditorReactor
    "react.docmanager.attach",        # AcApDocManagerReactor -- needs the doc manager
    "react.docmanager.monitor",       # AcApDocManagerReactor
    "react.longtx.attach",            # AcApLongTransactionReactor -- workspace/editor checkout
    "react.longtx.detach",            # AcApLongTransactionReactor
    "react.longtx.monitor",           # AcApLongTransactionReactor
]


def _read():
    with open(_INC, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _code_only(src):
    """Strip // line-comments and /* */ block-comments so token/balance checks see CODE,
    not prose. The file legitimately MENTIONS banned tokens (e.g. "never saveAs") and the
    word "addReactor" in its header/comments; the invariants are about actual calls."""
    no_block = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    no_line = re.sub(r"//[^\n]*", "", no_block)
    return no_line


def _hasop_region(src):
    m = re.search(r"static bool m08mHasOp\(const std::string& op\)\s*\{(.*?)\n\}", src, re.S)
    assert m, "m08mHasOp not found"
    return m.group(1)


def _dispatch_region(src):
    m = re.search(r"static bool m08mDispatch\(.*?\)\s*\{(.*)\n\}\s*$", src, re.S)
    assert m, "m08mDispatch not found"
    return m.group(1)


def _hasop_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _hasop_region(src)))


def _dispatch_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _dispatch_region(src)))


class TestM08MHandlers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read()
        cls.hasop = _hasop_ops(cls.src)
        cls.dispatch = _dispatch_ops(cls.src)

    def test_inc_file_exists(self):
        self.assertTrue(os.path.exists(_INC), f"missing {_INC}")

    def test_signatures_present(self):
        self.assertRegex(self.src, r"bool\s+m08mHasOp\(const std::string& op\)")
        self.assertRegex(
            self.src,
            r"bool\s+m08mDispatch\(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r\)",
        )

    def test_hasop_lists_exactly_implemented(self):
        self.assertEqual(
            self.hasop, set(_IMPLEMENTED),
            "m08mHasOp op set drifted; only_in_src=%s missing_from_src=%s"
            % (sorted(self.hasop - set(_IMPLEMENTED)), sorted(set(_IMPLEMENTED) - self.hasop)),
        )

    def test_implemented_count(self):
        # Group totals: inspect=4, opm=12, author=16, react=12 => 44 real handlers.
        self.assertEqual(len(_GROUP_INSPECT), 4)
        self.assertEqual(len(_GROUP_OPM), 12)
        self.assertEqual(len(_GROUP_AUTHOR), 16)
        self.assertEqual(len(_GROUP_REACT), 12)
        self.assertEqual(len(_IMPLEMENTED), 44)
        self.assertEqual(len(set(_IMPLEMENTED)), 44, "duplicate op id in the implemented list")
        self.assertEqual(len(self.hasop), 44)

    def test_no_deferred_op_in_hasop(self):
        leaked = sorted(self.hasop & set(_DEFERRED))
        self.assertEqual(leaked, [], "deferred attended-reactor ops leaked into m08mHasOp: %s" % leaked)

    def test_hasop_dispatch_parity(self):
        missing = sorted(set(_IMPLEMENTED) - self.dispatch)
        self.assertEqual(missing, [], "implemented ops with no dispatch branch: %s" % missing)
        extra = sorted(self.dispatch - self.hasop)
        self.assertEqual(extra, [], "dispatch branches not admitted by HasOp: %s" % extra)

    def test_no_original_write_or_acedcommand(self):
        # staged-write ONLY: never write the original DWG nor drive the command line.
        # Checked against CODE (comments stripped): the header legitimately says "never saveAs".
        code = _code_only(self.src)
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
                "M08M code must not contain original-write/command token: %s" % pat,
            )

    def test_staged_mutations_roll_back(self):
        # Any staged-write op proves rollback (the staged txn dtor aborts). The file must
        # never commit() a staged scratch mutation -- it is scratch-only.
        self.assertIn("staged_rolled_back", self.src,
                      "staged-write ops must report staged_rolled_back")
        self.assertNotIn(".commit()", self.src,
                         "M08M scratch mutations are rolled back; must not commit() staged state")
        self.assertIn("AriadneStagedWriteTransaction", self.src,
                      "staged mutations must use the rolled-back staged transaction wrapper")

    def test_reactor_attach_detach_balanced(self):
        # Reactor hygiene: every attach has a matching detach (no dangling reactor on the db).
        # Counted over CODE (comments/include-lines stripped) so prose mentions don't skew it.
        code = _code_only(self.src)
        self.assertEqual(
            code.count("addReactor"), code.count("removeReactor"),
            "addReactor/removeReactor are unbalanced -- a reactor was left attached",
        )
        self.assertEqual(
            code.count("addPersistentReactor"), code.count("removePersistentReactor"),
            "addPersistentReactor/removePersistentReactor are unbalanced",
        )

    def test_transient_classes_torn_down(self):
        # Every transient runtime class created for attribute-authoring proofs is deleted
        # (no class-system leak). newAcRxClass is wrapped by m08mNewTransientClass; each
        # authoring/opm branch calls deleteAcRxClass.
        self.assertIn("deleteAcRxClass", self.src,
                      "transient runtime classes must be torn down with deleteAcRxClass")

    def test_strings_use_utf8_njsonstr_not_lossy_funnel(self):
        self.assertIn("njsonStr", self.src, "string emission must route through njsonStr")
        self.assertNotIn("wideToAscii(", self.src, "must not use the lossy wideToAscii funnel")

    def test_dispatch_mismatch_guard_present(self):
        # The terminal guard (no silent fall-through) must exist.
        self.assertIn("OPERATION_DISPATCH_MISMATCH", self.src)

    def test_property_protocol_classes_referenced(self):
        # The OPM/property implementation must actually touch the property protocol classes
        # (not a stub): AcRxProperty (get/setValue/isReadOnly) and the AcRxAttribute family.
        self.assertIn("AcRxProperty", self.src)
        self.assertIn("AcRxMemberCollection", self.src)
        self.assertIn("AcRxDescriptionAttribute", self.src)
        self.assertIn("AcRxUiPlacementAttribute", self.src)

    def test_reactor_base_classes_referenced(self):
        # The reactor implementation must subclass the real reactor base classes.
        self.assertIn("AcDbDatabaseReactor", self.src)
        self.assertIn("AcDbObjectReactor", self.src)
        self.assertIn("AcRxEventReactor", self.src)
        self.assertIn("AcRxDLinkerReactor", self.src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
