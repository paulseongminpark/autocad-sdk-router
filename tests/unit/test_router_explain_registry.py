#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M04 TEST -- autocad-router explain is registry-derived for operation ids.

This does not touch DWGs or start AutoCAD. It only runs the router's explain
action against config/operations.v2.json and asserts the returned envelope names
the registry operation status.
"""
from __future__ import annotations

import json
import os
import subprocess
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_ROUTER = os.path.join(_REPO, "tools", "autocad-router.ps1")


class TestRouterExplainRegistry(unittest.TestCase):
    def test_explain_operation_uses_registry(self):
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", _ROUTER, "-Action", "explain",
             "-Operation", "inspect.database.graph"],
            cwd=_REPO,
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out.get("schema"), "ariadne.autocad_router_operation_explain.v1")
        self.assertEqual(out.get("operation"), "inspect.database.graph")
        self.assertEqual(out.get("registry_operation_status"), "implemented")
        self.assertEqual((out.get("record") or {}).get("id"), "inspect.database.graph")


if __name__ == "__main__":
    unittest.main()
