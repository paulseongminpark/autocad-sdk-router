#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M02 TEST -- cadagent_mcp tools manifest + handler dispatch contract.

Intent (WHY):
  * cadagent_mcp is the agent-facing surface of the CAD OS Layer. Its CONTRACT is:
    (a) it advertises a fixed set of cad.* tools whose manifest and dispatch table
    agree exactly (no orphan/extra tools); (b) EVERY handler, when dispatched
    through the JSON-RPC path, returns a dict and NEVER crashes -- whether it
    succeeds, reports a missing arg, or truthfully degrades to not_implemented.
    An agent that gets a crash (or a non-dict) instead of a structured result
    cannot reason about failure; that is the whole no-fake-success point.
  * Every tool must delegate to a SHELL (cadctl / validator / patch_engine /
    cad_diff / visual_report) -- the manifest declares ``delegates_to`` so we can
    assert no tool secretly bypasses the shells to a raw SDK.
  * transport must be reported as ``mock`` (a stdlib JSON-RPC server), so no
    consumer mistakes it for a production MCP host -- a truthfulness invariant.

This is a pure contract test: it dispatches each tool with trivial/empty args (no
real DWG), so handlers that would mutate/extract simply report a missing-arg or
degraded dict. No AutoCAD, no network.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

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
}


class TestToolsManifest(unittest.TestCase):
    def setUp(self):
        import cadagent_mcp
        self.mcp = cadagent_mcp
        self.manifest = cadagent_mcp.tools_manifest()

    def test_transport_is_mock(self):
        self.assertEqual(self.manifest["transport"], "mock",
                         "transport must be 'mock' (a stdlib JSON-RPC server)")

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


class TestHandlerDispatchReturnsDict(unittest.TestCase):
    """Every handler returns a dict via the RPC path; none crashes."""

    def setUp(self):
        import cadagent_mcp
        self.mcp = cadagent_mcp

    def test_tools_list_rpc(self):
        resp = self.mcp.handle_rpc(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertIsNotNone(resp)
        obj = json.loads(resp)
        listed = {t["name"] for t in obj["result"]["tools"]}
        self.assertEqual(listed, _EXPECTED_TOOLS)

    def test_every_handler_returns_a_dict(self):
        for name in sorted(self.mcp._DISPATCH.keys()):
            resp = self.mcp.handle_rpc({
                "jsonrpc": "2.0", "id": "t-%s" % name, "method": "tools/call",
                "params": {"name": name, "arguments": _TRIVIAL_ARGS.get(name, {})},
            })
            self.assertIsNotNone(resp, "tool %s produced no RPC response" % name)
            obj = json.loads(resp)
            # tools/call returns an MCP CallToolResult: content[] + structuredContent.
            self.assertIn("result", obj, "tool %s returned an RPC error: %r"
                          % (name, obj.get("error")))
            ctr = obj["result"]
            self.assertIsInstance(ctr, dict)
            self.assertIsInstance(ctr.get("content"), list,
                                  "tool %s result missing content[]" % name)
            sc = ctr.get("structuredContent")
            self.assertIsInstance(sc, dict,
                                  "tool %s handler did not return a dict" % name)
            # the handler envelope always carries an 'ok' flag.
            self.assertIn("ok", sc, "tool %s payload missing 'ok'" % name)

    def test_unknown_tool_is_a_clean_rpc_error_not_a_crash(self):
        resp = self.mcp.handle_rpc({
            "jsonrpc": "2.0", "id": 9, "method": "tools/call",
            "params": {"name": "cad.does_not_exist", "arguments": {}},
        })
        obj = json.loads(resp)
        self.assertIn("error", obj, "unknown tool should return a JSON-RPC error")
        self.assertEqual(obj["error"]["code"], -32601)

    def test_live_status_is_truthful_not_implemented(self):
        # cad.live_status must NEVER fake a live pump -> not_implemented + live False.
        resp = self.mcp.handle_rpc({
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "cad.live_status", "arguments": {}},
        })
        inner = json.loads(resp)["result"]["structuredContent"]["result"]
        self.assertEqual(inner["status"], "not_implemented")
        self.assertFalse(inner["live"])

    def test_patch_apply_staged_missing_args_is_a_structured_error(self):
        # No crash on missing args: a structured _err dict (ok False) or a
        # degraded not_implemented result -- either is acceptable, both are dicts.
        resp = self.mcp.handle_rpc({
            "jsonrpc": "2.0", "id": 6, "method": "tools/call",
            "params": {"name": "cad.patch_apply_staged", "arguments": {}},
        })
        payload = json.loads(resp)["result"]["structuredContent"]
        self.assertIsInstance(payload, dict)
        self.assertIn("ok", payload)


class TestInitializeRpc(unittest.TestCase):
    def setUp(self):
        import cadagent_mcp
        self.mcp = cadagent_mcp

    def test_initialize_reports_mock_transport(self):
        resp = self.mcp.handle_rpc(
            {"jsonrpc": "2.0", "id": 0, "method": "initialize"})
        res = json.loads(resp)["result"]
        self.assertEqual(res["transport"], "mock")
        self.assertEqual(res["serverInfo"]["name"], self.mcp.SERVER_NAME)


if __name__ == "__main__":
    unittest.main()
