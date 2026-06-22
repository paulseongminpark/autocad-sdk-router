#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08C TEST -- native db / object / symbol-table READ handlers.

Intent (WHY):
  M08C fills families/m08c_handlers.inc with the READ-only subset of the
  objectdbx_database + symbol_tables_dictionaries op families. Three invariants
  carry business meaning and must fail CI if violated:

  1. GATE PARITY -- m08cHasOp must return true for EXACTLY the implemented ops and
     false for every deferred (write-lane) op. If a write op (save_as, dxf_out,
     wblock_clone, write.object.close/upgrade/downgrade, create_ext_dict,
     register, set_working_db, the side-db file readers, flush_input) leaks into
     HasOp without a real read-only handler, the dispatcher would admit it and
     either misroute or (worse) a write op would be reported runnable -- breaking
     the "READ family is read-only / no original DWG write" hard constraint.

  2. HASOP<->DISPATCH PARITY -- every op HasOp claims must have an `op == "<id>"`
     branch in m08cDispatch. Drift = OPERATION_DISPATCH_MISMATCH at runtime.

  3. READ-ONLY PROOF (source-level) -- the .inc must contain no original-DWG-write
     token (saveAs / save( / _QSAVE / writeDwgFile / upgradeOpen / setAt /
     appendAcDbEntity), and the wblock probe must delete its clone and never saveAs
     it. All emitted strings go through njsonStr (UTF-8 fidelity; the lossy
     wideToAscii funnel must not appear in this file).

  Source-level only (no AutoCAD/build needed); the native build
  (tools/build_native_acad.ps1) separately proves it compiles + links against the
  ObjectARX 2027 SDK. Stdlib only.
"""
from __future__ import annotations

import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "m08c_handlers.inc")

# The 11 ops M08C implements as real read-only handlers.
_IMPLEMENTED = [
    "infra.hostapp.get_services",
    "inspect.database.summaryinfo",
    "inspect.database.sysvar",
    "inspect.object.open",
    "inspect.object.id",
    "inspect.object.handle",
    "inspect.object.ext_dict",
    "inspect.symboltable.block",
    "inspect.symboltable.layers",
    "transform.database.wblock",
    "write.object.cancel",
]

# Write-lane / host-mutation / side-db ops M08C deliberately does NOT implement.
# (Catalog default_write_mode in {write_copy, live_edit} or a host/side-db mutation.)
_DEFERRED = [
    "infra.hostapp.set_working_db",
    "inspect.database.read_dwg",
    "inspect.database.read_dwg_handle",
    "inspect.database.dxf_in",
    "inspect.database.flush_input",
    "inspect.object.upgrade_open",      # write-intent primitive
    "write.object.upgrade_open",        # same op under the write.* spelling
    "transform.database.dxf_out",
    "transform.database.save_as",
    "transform.database.save_as_simple",
    "write.object.close",
    "write.object.downgrade_open",
    "transform.database.wblock_clone",
    "write.object.create_ext_dict",
    "write.regapp.register",
]


def _read():
    with open(_INC, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _hasop_region(src):
    m = re.search(r"static bool m08cHasOp\(const std::string& op\)\s*\{(.*?)\n\}", src, re.S)
    assert m, "m08cHasOp not found"
    return m.group(1)


def _dispatch_region(src):
    m = re.search(r"static bool m08cDispatch\(.*?\)\s*\{(.*)\n\}\s*$", src, re.S)
    assert m, "m08cDispatch not found"
    return m.group(1)


def _hasop_ops(src):
    # the op-ids HasOp compares against: op == "<id>"
    return set(re.findall(r'op == "([^"]+)"', _hasop_region(src)))


def _dispatch_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _dispatch_region(src)))


class TestM08CHandlers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read()
        cls.hasop = _hasop_ops(cls.src)
        cls.dispatch = _dispatch_ops(cls.src)

    def test_inc_file_exists(self):
        self.assertTrue(os.path.exists(_INC), f"missing {_INC}")

    def test_signatures_present(self):
        self.assertRegex(self.src, r"bool\s+m08cHasOp\(const std::string& op\)")
        self.assertRegex(
            self.src,
            r"bool\s+m08cDispatch\(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r\)",
        )

    def test_hasop_lists_exactly_implemented(self):
        self.assertEqual(
            self.hasop, set(_IMPLEMENTED),
            "m08cHasOp op set drifted; only_in_src=%s missing_from_src=%s"
            % (sorted(self.hasop - set(_IMPLEMENTED)), sorted(set(_IMPLEMENTED) - self.hasop)),
        )

    def test_no_deferred_op_in_hasop(self):
        leaked = sorted(self.hasop & set(_DEFERRED))
        self.assertEqual(leaked, [], "deferred write-lane ops leaked into m08cHasOp: %s" % leaked)

    def test_hasop_dispatch_parity(self):
        # every implemented op must have a dispatch branch
        missing = sorted(set(_IMPLEMENTED) - self.dispatch)
        self.assertEqual(missing, [], "implemented ops with no dispatch branch: %s" % missing)
        # dispatch must not branch on an op HasOp does not admit (would be dead/misrouted)
        extra = sorted(self.dispatch - self.hasop)
        self.assertEqual(extra, [], "dispatch branches not admitted by HasOp: %s" % extra)

    def test_read_only_no_original_write_tokens(self):
        # The READ family must never CALL an original-DWG-write / db-mutation API.
        # Strip // comments first: the file's header + deferral rationale legitimately
        # NAME these APIs (saveAs / writeDwgFile / upgradeOpen / downgradeOpen) in
        # prose; the invariant is that none are CALLED in code.
        code = re.sub(r"//[^\n]*", "", self.src)
        banned = [
            r"\bsaveAs\s*\(",
            r"\bsave\s*\(",
            r"_QSAVE",
            r"\bwriteDwgFile\s*\(",
            r"\bupgradeOpen\s*\(",
            r"\bdowngradeOpen\s*\(",
            r"\bappendAcDbEntity\s*\(",
            r"->setAt\s*\(",
            r"\bcreateExtensionDictionary\s*\(",
            r"\bwblockCloneObjects\s*\(",
            r"\bdxfOut\s*\(",
        ]
        for pat in banned:
            self.assertIsNone(
                re.search(pat, code),
                "READ family must not CALL original-write/mutation API: %s" % pat,
            )

    def test_wblock_probe_deletes_clone_and_never_saves(self):
        # the wblock op clones to a NEW db, must delete it, must not saveAs it.
        # JSON is emitted from C++ with escaped quotes (\"output_saved\":false), so
        # match the key+value tolerant of the source escaping/whitespace.
        self.assertIn("pDb->wblock(pOut)", self.src, "wblock must clone via AcDbDatabase::wblock")
        self.assertIn("delete pOut", self.src, "wblock clone must be deleted (no leak)")
        self.assertRegex(
            self.src, r'output_saved\\?"\s*:\s*false',
            "wblock must report output_saved:false (never persisted)",
        )
        self.assertNotIn("pOut->saveAs", self.src, "wblock clone must never be saved to disk")

    def test_strings_use_utf8_njsonstr_not_lossy_funnel(self):
        # njsonStr is the canonical UTF-8 writer; the lossy '?' funnel must be absent.
        self.assertIn("njsonStr", self.src, "string emission must route through njsonStr")
        self.assertNotIn("wideToAscii(", self.src, "must not use the lossy wideToAscii funnel")

    def test_sysvar_is_read_only(self):
        # inspect.database.sysvar implements ONLY the read side; no sysvar SETTER is
        # CALLED. Check for an actual call (name followed by '('), not the bare word,
        # so the design-rationale comment ("...setSysVar... not implemented") doesn't
        # false-trip. Strip // comments first for robustness.
        code = re.sub(r"//[^\n]*", "", self.src)
        for setter in (r"setSysVar\s*\(", r"\bsetVar\s*\(", r"acedSetVar\s*\("):
            self.assertIsNone(
                re.search(setter, code),
                "READ-only sysvar handler must not call a setter: %s" % setter,
            )
        self.assertIn("acedGetVar", self.src, "named sysvar read should use acedGetVar")

    def test_summaryinfo_frees_pinfo(self):
        # acdbGetSummaryInfo gives caller ownership; must delete to avoid a leak.
        self.assertIn("acdbGetSummaryInfo", self.src)
        self.assertIn("delete pInfo", self.src, "summaryinfo must delete the caller-owned pInfo")


if __name__ == "__main__":
    unittest.main(verbosity=2)
