#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08N A3 TEST -- editor/jig/selection/UI command builder.

Source-contract tests only: prove the M08N family seam admits exactly the feasible
implemented A3 operations, keeps raw execution / registry-mutating operations out
of HasOp, uses real ObjectARX APIs behind attended gates, and avoids original DWG
writes / raw command execution.
"""
from __future__ import annotations

import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "m08n_handlers.inc")
_SRC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "AriadneNativeJob.cpp")
_PALETTE = os.path.join(_REPO, "src", "Ariadne.AcadNative", "AriadnePalette.cpp")

_T01 = [
    "editor.react.events",
    "input.get.angle",
    "input.get.corner",
    "input.get.dist",
    "input.get.int",
    "input.get.keyword",
    "input.get.point",
    "input.get.real",
    "input.get.string",
    "input.initget.constrain",
    "interact.inputcontext.react",
    "interact.inputpoint.filter",
    "interact.inputpoint.monitor",
    "interact.jig.acquire",
    "interact.jig.run",
    "prompt.alert",
    "prompt.print",
]

_SELECTION = [
    "select.entity.pick",
    "select.nentity.pick",
    "select.pickfirst.get",
    "select.pickfirst.set",
    "select.ss.addremove",
    "select.ss.count",
    "select.ss.free",
    "select.ssget.interactive",
    "select.ssget.preview",
]

_RUNTIME = [
    "command.register.define",
    "module.ads.register_symbol",
    "module.app.accessor",
    "module.class.register_object",
    "module.command.flags",
    "module.command.register_auto",
    "module.command.register_manual",
    "module.command.stack_handle",
    "module.entrypoint.define",
    "module.entrypoint.dispatch",
    "module.lifecycle.init",
    "module.lifecycle.on_load_dwg",
    "module.lifecycle.on_unload_dwg",
    "module.lifecycle.other",
    "module.lifecycle.unload",
    "module.register_mdi",
    "module.register_service",
]

_UI = [
    "editor.command.register",
    "editor.command.unregister",
    "editor.menu.add_item",
    "editor.menu.context",
    "editor.menu.menubar_get",
    "editor.palette.add_palette",
    "editor.palette.create",
    "editor.palette.create_dockable",
    "editor.palette.dock",
    "editor.palette.persist",
    "editor.palette.style",
    "editor.statusbar.add_pane",
    "editor.statusbar.context_menu",
    "editor.statusbar.get",
    "editor.statusbar.pane",
    "editor.statusbar.pane_config",
    "editor.statusbar.remove_pane",
    "editor.toolpalette.add_tool",
    "editor.toolpalette.catalog_item_props",
    "editor.toolpalette.catalog_manager",
    "editor.toolpalette.create",
    "editor.toolpalette.export",
    "editor.toolpalette.global_init",
    "editor.toolpalette.group_activate",
    "editor.toolpalette.group_create",
    "editor.toolpalette.refresh",
    "editor.toolpalette.scheme_create",
    "editor.toolpalette.scheme_register",
    "editor.toolpalette.stocktool_find",
    "editor.toolpalette.tool_set_command",
    "editor.toolpalette.window_get",
    "editor.toolpalette.window_show",
    "editor.toolpaletteset.add_palette",
    "editor.toolpaletteset.show",
    "editor.tray.add_item",
    "editor.tray.item_config",
    "editor.tray.remove",
]

_DOC = [
    "doc.current",
    "doc.lock",
    "doc.new",
    "doc.syncopen",
]

_IMPLEMENTED = _T01 + _SELECTION + _RUNTIME + _UI + _DOC

_HARD_BLOCKED = [
    "command.menu.invoke",             # arbitrary menu macro execution => raw command surface
    "module.load.demand_register",     # registry/AutoCAD autoload mutation outside ticket scope
    "editor.toolpalette.tool_execute", # arbitrary tool execution may mutate active/user drawing
]


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _code_only(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def _hasop_region(src: str) -> str:
    m = re.search(r"static bool m08nHasOp\(const std::string& op\)\s*\{(.*?)\n\}", src, re.S)
    assert m, "m08nHasOp not found"
    return m.group(1)


def _dispatch_region(src: str) -> str:
    m = re.search(r"static bool m08nDispatch\(.*?\)\s*\{(.*)\n\}\s*$", src, re.S)
    assert m, "m08nDispatch not found"
    return m.group(1)


def _hasop_ops(src: str) -> set[str]:
    return set(re.findall(r'op == "([^"]+)"', _hasop_region(src)))


def _dispatch_literal_ops(src: str) -> set[str]:
    return set(re.findall(r'op == "([^"]+)"', _dispatch_region(src)))


class TestM08NHandlers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read(_INC)
        cls.code = _code_only(cls.src)
        cls.hasop = _hasop_ops(cls.src)
        cls.dispatch_literals = _dispatch_literal_ops(cls.src)
        cls.native_job = _read(_SRC)
        cls.palette = _read(_PALETTE)

    def test_files_exist_and_wired(self):
        self.assertTrue(os.path.exists(_INC))
        self.assertIn('#include "families/m08n_handlers.inc"', self.native_job)
        self.assertIn('m08nHasOp(op)', self.native_job)
        self.assertIn('m08nDispatch(op, ctx, r)', self.native_job)

    def test_signatures_present(self):
        self.assertRegex(self.src, r"bool\s+m08nHasOp\(const std::string& op\)")
        self.assertRegex(self.src, r"bool\s+m08nDispatch\(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r\)")

    def test_hasop_lists_exactly_feasible_implemented(self):
        self.assertEqual(len(_IMPLEMENTED), 84)
        self.assertEqual(len(set(_IMPLEMENTED)), 84)
        self.assertEqual(
            self.hasop,
            set(_IMPLEMENTED),
            "m08nHasOp drift; only_in_src=%s missing=%s" %
            (sorted(self.hasop - set(_IMPLEMENTED)), sorted(set(_IMPLEMENTED) - self.hasop)),
        )

    def test_hard_blocked_ops_not_in_hasop(self):
        self.assertEqual(len(_HARD_BLOCKED), 3)
        leaked = sorted(self.hasop & set(_HARD_BLOCKED))
        self.assertEqual(leaked, [], "hard-blocked raw/registry ops leaked into HasOp: %s" % leaked)
        for op in _HARD_BLOCKED:
            self.assertIn(op, self.src, "hard-blocked op must be documented in source: %s" % op)

    def test_dispatch_coverage(self):
        # Most ops have explicit op == branches. The remaining editor.* UI operations are routed
        # by the m08nUiBuilderResult(op, ...) group branch, which is a real handler for that family.
        ui_builder = {op for op in _UI if op not in self.dispatch_literals}
        missing = sorted(set(_IMPLEMENTED) - self.dispatch_literals - ui_builder)
        self.assertEqual(missing, [], "implemented ops with no dispatch path: %s" % missing)
        self.assertIn("m08nUiBuilderResult(op, ctx, r)", self.src)

    def test_no_original_dwg_write_or_raw_command_api(self):
        banned = [
            r"\bsaveAs\b",
            r"\bsave\s*\(",
            r"_QSAVE",
            r"\bwriteDwgFile\b",
            r"\bacedCommand\b",
            r"\bacedCmd\b",
            r"\bacedInvoke\b",
            r"\bRegSetValue",
            r"\bSHSetValue",
        ]
        for pat in banned:
            self.assertIsNone(re.search(pat, self.code), "M08N must not contain unsafe token: %s" % pat)

    def test_attended_gates_present(self):
        self.assertIn("m08nFullEditor", self.src)
        self.assertIn("HOST_UNAVAILABLE", self.src)
        self.assertIn("execute_requested", self.src)
        self.assertIn("attended_editor_required", self.src)

    def test_real_editor_input_apis_referenced(self):
        for token in [
            "acedGetPoint", "acedGetCorner", "acedGetDist", "acedGetAngle",
            "acedGetInt", "acedGetReal", "acedGetString", "acedInitGet",
            "acedEntSel", "acedNEntSel", "acedSSGet", "acedSSSetFirst",
            "acedSSAdd", "acedSSDel", "acedSSFree", "acedSSLength",
        ]:
            self.assertIn(token, self.src)

    def test_real_jig_and_input_manager_apis_referenced(self):
        for token in [
            "AriadneLineJig", ".drag()", "AcEdInputPointManager",
            "addPointMonitor", "removePointMonitor", "registerPointFilter",
            "revokePointFilter", "addInputContextReactor", "removeInputContextReactor",
        ]:
            self.assertIn(token, self.src)

    def test_command_and_ads_lifecycle_apis_referenced(self):
        for token in [
            "addCommand", "lookupGlobalCmd", "removeCmd", "removeGroup",
            "acedDefun", "acedRegFunc", "acedUndef", "acrxRegisterService",
            "acrxServiceIsRegistered", "acrxRegisterAppMDIAware",
        ]:
            self.assertIn(token, self.src + self.native_job)

    def test_module_lifecycle_evidence_is_status_only(self):
        for token in [
            "m08nModuleLifecycleEvidence",
            "module.entrypoint.define",
            "module.entrypoint.dispatch",
            "module.lifecycle.init",
            "module.lifecycle.on_load_dwg",
            "module.lifecycle.on_unload_dwg",
            "module.lifecycle.other",
            "module.lifecycle.unload",
            "actual_lifecycle_callback_invoked",
            "synthetic_loader_message_dispatched",
            "lifecycle_evidence_status_only",
        ]:
            self.assertIn(token, self.src)

    def test_module_command_flags_is_read_only_inventory(self):
        self.assertIn('op == "module.command.flags"', self.src)
        self.assertIn("ACRX_CMD_MODAL", self.src)
        self.assertIn("ACRX_CMD_TRANSPARENT", self.src)
        self.assertIn("ACRX_CMD_SESSION", self.src)
        self.assertIn('"read_only":true', self.src)

    def test_selection_filter_structure_present(self):
        self.assertIn("m08nBuildTypeFilter", self.src)
        self.assertIn("acutBuildList", self.src)
        self.assertIn("RTDXF0", self.src)

    def test_palette_status_ui_source_updated(self):
        self.assertIn("A3 UI builders", self.palette)
        self.assertIn("No raw command macro/tool execution", self.palette)
        self.assertIn("ARIADNE_PALETTE", self.palette)

    def test_dispatch_mismatch_guard_present(self):
        self.assertIn("OPERATION_DISPATCH_MISMATCH", self.src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
