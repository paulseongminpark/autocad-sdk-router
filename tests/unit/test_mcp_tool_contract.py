#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M02 TEST -- cadagent_mcp catalogue + handler dispatch contract.

Intent (WHY):
  * cadagent_mcp is the agent-facing catalogue of the CAD OS Layer. Its CONTRACT is:
    (a) it declares a fixed set of cad.* tools whose manifest and dispatch table
    agree exactly (no orphan/extra tools); (b) EVERY handler, when dispatched
    through the retained local dispatch helper, returns a dict and NEVER crashes -- whether it
    succeeds, reports a missing arg, or truthfully degrades to not_implemented.
    An agent that gets a crash (or a non-dict) instead of a structured result
    cannot reason about failure; that is the whole no-fake-success point.
  * Every tool must delegate to a SHELL (cadctl / validator / patch_engine /
    cad_diff / visual_report) -- the manifest declares ``delegates_to`` so we can
    assert no tool secretly bypasses the shells to a raw SDK.
  * transport must report the official Python MCP SDK host.  The separate
    integration test owns initialize, stdio, and MCP wire behavior.

This is a pure catalogue/dispatch test: it dispatches each tool with
trivial/empty args (no real DWG), so handlers that would mutate/extract simply
report a missing-arg or degraded dict. No AutoCAD, no network.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import json
import io
import os
import sys
import unittest
from contextlib import redirect_stdout

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_EXPECTED_TOOLS = {
    "cad.status", "cad.inspect_drawing", "cad.query_entities", "cad.get_entity",
    "cad.validate_ir", "cad.registry_status", "cad.registry_explain",
    "cad.patch_dry_run", "cad.patch_apply_staged", "cad.anchor_set",
    "cad.anchor_get", "cad.anchor_list", "cad.anchor_clear", "cad.diff_before_after",
    "cad.visual_report", "cad.live_status", "cad.run_operation",
    "cad.run_command_template", "cad.inspect_display_membership",
}

# Trivial args per tool: deliberately minimal/invalid so handlers report a
# missing-arg or degrade -- never mutate/extract. Each MUST still return a dict.
_TRIVIAL_ARGS = {
    "cad.status": {},
    "cad.inspect_drawing": {},
    "cad.query_entities": {},
    "cad.get_entity": {},
    "cad.validate_ir": {"ir": "/nonexistent/ir.json"},
    "cad.registry_status": {},
    "cad.registry_explain": {"op_id": "inspect.database.graph"},
    "cad.patch_dry_run": {"patch": {"schema": "ariadne.cad_patch.v1"}},
    "cad.patch_apply_staged": {},
    "cad.anchor_set": {},
    "cad.anchor_get": {},
    "cad.anchor_list": {},
    "cad.anchor_clear": {},
    "cad.diff_before_after": {},
    "cad.visual_report": {"source_ref": "/nonexistent/source.dwg", "kind": "png"},
    "cad.live_status": {},
    # op_id only (no dwg) -> run_operation returns a refusal dict; no accoreconsole.
    "cad.run_operation": {"op_id": "inspect.database.graph"},
    # nonexistent dwg -> run_command_template returns a refusal dict; no accoreconsole.
    "cad.run_command_template": {"template_id": "maintenance.drawing.audit", "dwg": "/nonexistent/source.dwg", "slots": {}},
    "cad.inspect_display_membership": {},
}


class TestToolsManifest(unittest.TestCase):
    def setUp(self):
        import cadagent_mcp
        self.mcp = cadagent_mcp
        self.manifest = cadagent_mcp.tools_manifest()

    def test_transport_is_official_sdk(self):
        self.assertEqual(self.manifest["transport"], "mcp-sdk",
                         "transport must name the official MCP SDK host")

    def test_manifest_lists_exactly_the_cad_tools(self):
        names = {t["name"] for t in self.manifest["tools"]}
        self.assertEqual(names, _EXPECTED_TOOLS,
                         "manifest tool set drifted from the cad.* contract")
        # every advertised tool is a cad.* tool.
        for n in names:
            self.assertTrue(n.startswith("cad."), "non-cad tool advertised: %s" % n)

    def test_manifest_and_dispatch_agree(self):
        # No orphan tools: the dispatch table and the manifest must match exactly.
        names = {t["name"] for t in self.manifest["tools"]}
        self.assertEqual(set(self.mcp._DISPATCH.keys()), names,
                         "dispatch table and manifest disagree (orphan tool)")

    def test_module_selftest_tracks_the_declared_tool_set(self):
        with redirect_stdout(io.StringIO()):
            result = self.mcp._selftest()
        self.assertEqual(result, 0)

    def test_every_tool_declares_a_delegate(self):
        # Each tool must delegate to a shell (no raw-SDK tool).
        for t in self.manifest["tools"]:
            self.assertIn("delegates_to", t,
                          "tool %s does not declare delegates_to" % t["name"])
            self.assertTrue(t["delegates_to"])

    def test_each_tool_has_input_schema(self):
        for t in self.manifest["tools"]:
            self.assertIn("inputSchema", t, "tool %s missing inputSchema" % t["name"])
            self.assertEqual(t["inputSchema"].get("type"), "object")

    def test_display_membership_geometry_scope_is_closed_and_forwarded(self):
        tool = next(
            item for item in self.manifest["tools"]
            if item["name"] == "cad.inspect_display_membership"
        )
        scope = tool["inputSchema"]["properties"]["geometry_scope"]
        self.assertEqual(
            scope["enum"], ["strict_layer_entities_v1", "linear_segments_v1"]
        )
        self.assertEqual(scope["default"], "strict_layer_entities_v1")

        invalid = self.mcp._tool_inspect_display_membership({
            "dwg": "source.dwg",
            "target_layers": ["W1"],
            "geometry_scope": "curve_segments_v1",
        })
        self.assertFalse(invalid["ok"])
        self.assertIn("geometry_scope", invalid["error"])

        calls = []

        class FakeCad:
            def inspect_display_membership(self, *args, **kwargs):
                calls.append((args, kwargs))
                return {"status": "NEEDS_BUILD"}

        original_cad = self.mcp._cad
        self.mcp._cad = lambda: (FakeCad(), None)
        try:
            forwarded = self.mcp._tool_inspect_display_membership({
                "dwg": "source.dwg",
                "target_layers": ["W1"],
                "geometry_scope": "linear_segments_v1",
            })
        finally:
            self.mcp._cad = original_cad

        self.assertTrue(forwarded["ok"])
        self.assertEqual(calls[0][1]["geometry_scope"], "linear_segments_v1")


class TestHandlerDispatchReturnsDict(unittest.TestCase):
    """Every retained handler returns a dict; no private JSON-RPC shim remains."""

    def setUp(self):
        import cadagent_mcp
        self.mcp = cadagent_mcp

    def test_every_handler_returns_a_dict(self):
        for name in sorted(self.mcp._DISPATCH.keys()):
            payload = self.mcp._dispatch_tool(name, _TRIVIAL_ARGS.get(name, {}))
            self.assertIsInstance(payload, dict,
                                  "tool %s handler did not return a dict" % name)
            # the handler envelope always carries an 'ok' flag.
            self.assertIn("ok", payload, "tool %s payload missing 'ok'" % name)

    def test_unknown_tool_is_a_truthful_local_error(self):
        payload = self.mcp._dispatch_tool("cad.does_not_exist", {})
        self.assertFalse(payload["ok"])
        self.assertIn("unknown tool", payload["error"])

    def test_live_status_is_truthful_not_implemented(self):
        # cad.live_status must NEVER fake a live pump -> not_implemented + live False.
        inner = self.mcp._dispatch_tool("cad.live_status", {})["result"]
        self.assertEqual(inner["status"], "not_implemented")
        self.assertFalse(inner["live"])

    def test_patch_apply_staged_missing_args_is_a_structured_error(self):
        # No crash on missing args: a structured _err dict (ok False) or a
        # degraded not_implemented result -- either is acceptable, both are dicts.
        payload = self.mcp._dispatch_tool("cad.patch_apply_staged", {})
        self.assertIsInstance(payload, dict)
        self.assertIn("ok", payload)


if __name__ == "__main__":
    unittest.main()
