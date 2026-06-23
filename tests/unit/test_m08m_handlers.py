#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08M TEST -- native OPM properties + reactors.

Intent (WHY):
  M08M owns the native AcRxProperty/OPM + reactor family seam. Wave 3 extends the
  earlier hostless subset with the real full-host editor/doc-manager/long-transaction
  reactors claimed by Pane 8. CI must fail if the source/registry seam drifts.

  Invariants pinned here:
    1. HasOp <-> Dispatch parity for every implemented op.
    2. HasOp lists exactly the implemented set (no fake-grow / silent shrink).
    3. The 9 Wave 3 claimed ops are PRESENT in HasOp.
    4. No original DWG write / no raw command dispatch tokens.
    5. Reactor hygiene: add/remove and persistent add/remove stay balanced.
    6. Full-host cleanup helpers are wired into module unload.

  Source-only: no AutoCAD runtime required.
"""
from __future__ import annotations

import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "m08m_handlers.inc")
_SRC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "AriadneNativeJob.cpp")

_GROUP_INSPECT = [
    "inspect.property.by_name",
    "inspect.property.is_readonly",
    "inspect.property.metadata",
    "inspect.entity.properties",
    "inspect.members.promoted",
    "inspect.value.to_string",
    "extend.members.facet_provider",
    "automate.com.bridge_objectid",
    "automate.com.hold_objectref",
    "automate.com.entity_helpers",
    "automate.com.objectid_from_iunknown",
    "automate.com.lock_document",
    "automate.property.set",
]

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
    "extend.property.define_collection",
    "extend.property.define_dictionary",
    "extend.property.define_indexed",
    "extend.property.overrule",
]

_GROUP_REACT = [
    "react.database.attach",
    "react.database.monitor",
    "react.object.attach_transient",
    "react.object.detach_transient",
    "react.object.monitor",
    "react.entity.monitor",
    "react.persistent.attach",
    "react.persistent.detach",
    "react.rxevent.attach",
    "react.rxevent.monitor",
    "react.linker.attach",
    "react.linker.monitor",
    "react.docmanager.attach",
    "react.docmanager.monitor",
    "react.editor.command_monitor",
    "react.editor.dwg_lifecycle",
    "react.editor.input_monitor",
    "react.editor.lisp_monitor",
    "react.editor.sysvar_monitor",
    "react.longtx.attach",
    "react.longtx.monitor",
    "react.config.disable_namespace",
]

_IMPLEMENTED = _GROUP_INSPECT + _GROUP_OPM + _GROUP_AUTHOR + _GROUP_REACT

_WAVE3_CLAIMED = [
    "react.docmanager.attach",
    "react.docmanager.monitor",
    "react.editor.command_monitor",
    "react.editor.dwg_lifecycle",
    "react.editor.input_monitor",
    "react.editor.lisp_monitor",
    "react.editor.sysvar_monitor",
    "react.longtx.attach",
    "react.longtx.monitor",
]

_DRIFT = [
    "extend.property.lmv",
    "extend.property.dynamic_props",
    "extend.property.type_promotion",
    "react.longtx.detach",
]


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _code_only(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def _hasop_region(src: str) -> str:
    m = re.search(r"static bool m08mHasOp\(const std::string& op\)\s*\{(.*?)\n\}", src, re.S)
    assert m, "m08mHasOp not found"
    return m.group(1)


def _dispatch_region(src: str) -> str:
    m = re.search(r"static bool m08mDispatch\(.*?\)\s*\{(.*)\n\}\s*$", src, re.S)
    assert m, "m08mDispatch not found"
    return m.group(1)


def _hasop_ops(src: str) -> set[str]:
    return set(re.findall(r'op == "([^"]+)"', _hasop_region(src)))


def _dispatch_ops(src: str) -> set[str]:
    return set(re.findall(r'op == "([^"]+)"', _dispatch_region(src)))


class TestM08MHandlers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read(_INC)
        cls.code = _code_only(cls.src)
        cls.native_job = _read(_SRC)
        cls.hasop = _hasop_ops(cls.src)
        cls.dispatch = _dispatch_ops(cls.src)

    def test_files_exist(self):
        self.assertTrue(os.path.exists(_INC))
        self.assertTrue(os.path.exists(_SRC))

    def test_signatures_present(self):
        self.assertRegex(self.src, r"bool\s+m08mHasOp\(const std::string& op\)")
        self.assertRegex(
            self.src,
            r"bool\s+m08mDispatch\(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r\)",
        )

    def test_hasop_lists_exactly_implemented(self):
        self.assertEqual(
            self.hasop,
            set(_IMPLEMENTED),
            "m08mHasOp drifted; only_in_src=%s missing=%s"
            % (sorted(self.hasop - set(_IMPLEMENTED)), sorted(set(_IMPLEMENTED) - self.hasop)),
        )

    def test_implemented_counts(self):
        self.assertEqual(len(_GROUP_INSPECT), 13)
        self.assertEqual(len(_GROUP_OPM), 12)
        self.assertEqual(len(_GROUP_AUTHOR), 17)
        self.assertEqual(len(_GROUP_REACT), 22)
        self.assertEqual(len(_IMPLEMENTED), 64)
        self.assertEqual(len(set(_IMPLEMENTED)), 64)
        self.assertEqual(len(self.hasop), 64)

    def test_wave3_claimed_ops_present(self):
        self.assertEqual(len(_WAVE3_CLAIMED), 9)
        missing = sorted(set(_WAVE3_CLAIMED) - self.hasop)
        self.assertEqual(missing, [], "claimed Pane 8 ops missing from HasOp: %s" % missing)

    def test_no_drift_ops_in_hasop_or_dispatch(self):
        leaked_hasop = sorted(self.hasop & set(_DRIFT))
        leaked_dispatch = sorted(self.dispatch & set(_DRIFT))
        self.assertEqual(leaked_hasop, [], "drift ops leaked into HasOp: %s" % leaked_hasop)
        self.assertEqual(leaked_dispatch, [], "drift ops leaked into Dispatch: %s" % leaked_dispatch)

    def test_hasop_dispatch_parity(self):
        missing = sorted(set(_IMPLEMENTED) - self.dispatch)
        extra = sorted(self.dispatch - self.hasop)
        self.assertEqual(missing, [], "implemented ops with no dispatch branch: %s" % missing)
        self.assertEqual(extra, [], "dispatch branches not admitted by HasOp: %s" % extra)

    def test_no_original_write_or_raw_command_dispatch(self):
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
            self.assertIsNone(re.search(pat, self.code), "unsafe token present: %s" % pat)

    def test_staged_write_tokens_still_present(self):
        self.assertIn("AriadneStagedWriteTransaction", self.src)
        self.assertIn("staged_rolled_back", self.src)
        self.assertNotIn(".commit()", self.src)

    def test_reactor_attach_detach_balanced(self):
        self.assertEqual(
            self.code.count("addReactor"),
            self.code.count("removeReactor"),
            "addReactor/removeReactor imbalance",
        )
        self.assertEqual(
            self.code.count("addPersistentReactor"),
            self.code.count("removePersistentReactor"),
            "addPersistentReactor/removePersistentReactor imbalance",
        )

    def test_property_protocol_tokens_present(self):
        for token in [
            "AcRxProperty",
            "AcRxMemberCollection",
            "AcRxDescriptionAttribute",
            "AcRxUiPlacementAttribute",
            "deleteAcRxClass",
        ]:
            self.assertIn(token, self.src)

    def test_reactor_base_classes_present(self):
        for token in [
            "AcDbDatabaseReactor",
            "AcDbObjectReactor",
            "AcRxEventReactor",
            "AcRxDLinkerReactor",
            "AcEditorReactor",
            "AcApDocManagerReactor",
            "AcApLongTransactionReactor",
        ]:
            self.assertIn(token, self.src)

    def test_full_host_gate_and_safe_probe_tokens_present(self):
        for token in [
            "m08mFullAutoCadHost",
            "execute_requested",
            "acedSSSetFirst",
            "acedSSAdd",
            "acedGetVar",
            "acedSetVar",
            "lockDocument",
            "unlockDocument",
            "acDocManager",
            "acapLongTransactionManager",
        ]:
            self.assertIn(token, self.src)

    def test_unload_cleanup_helpers_wired(self):
        for token in [
            "m08mDisableEditorMonitor(removed);",
            "m08mDisableDocManagerMonitor(removed);",
            "m08mDisableLongTransactionMonitor(removed);",
        ]:
            self.assertIn(token, self.native_job)

    def test_strings_use_njsonstr(self):
        self.assertIn("njsonStr", self.src)
        self.assertNotIn("wideToAscii(", self.src)

    def test_dispatch_mismatch_guard_present(self):
        self.assertIn("OPERATION_DISPATCH_MISMATCH", self.src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
