#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lane E SMOKE -- the router-published status JSON exists and cadctl reflects it.

Intent (WHY):
  * The published reports/autocad_router_status_latest.json is the read-only
    source cadctl.status() normalizes. This smoke test proves the live artifact
    is present and that cadctl's normalized view agrees with it on the headline
    facts (route_count / available_count). If they ever disagree, cadctl is
    misreading the router and every status-dependent decision is wrong.
  * Read-only: this test only READS the status file (allowed) and calls
    cadctl.status() (which is itself read-only). It never runs ``-Action status``
    and never spawns AutoCAD.

If the published file is absent (a fresh checkout that never ran a probe), the
test SKIPS with an explicit SKIPPED marker rather than failing -- the artifact is
environment-produced, not committed-guaranteed.

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

_JSON_ENCODING = "utf-8-sig"
_STATUS_JSON = os.path.join(_REPO, "reports", "autocad_router_status_latest.json")


class TestRouterStatusSmoke(unittest.TestCase):
    def setUp(self):
        if not os.path.isfile(_STATUS_JSON):
            self.skipTest("SKIPPED_ENV: published router status JSON absent: %s" % _STATUS_JSON)
        with open(_STATUS_JSON, "r", encoding=_JSON_ENCODING) as fh:
            self.published = json.load(fh)
        import cadctl
        self.cad = cadctl.Cad()
        self.normalized = self.cad.status()

    def test_published_status_is_well_formed(self):
        self.assertIn("routes", self.published)
        self.assertIsInstance(self.published["routes"], list)
        self.assertIn("route_count", self.published)
        self.assertIn("available_count", self.published)
        # route_count should match the realized routes list length.
        self.assertEqual(self.published["route_count"], len(self.published["routes"]))

    def test_cadctl_status_reflects_route_count(self):
        self.assertEqual(self.normalized["status"], "ok")
        self.assertEqual(
            self.normalized["route_count"], self.published["route_count"],
            "cadctl route_count disagrees with the published status",
        )

    def test_cadctl_status_reflects_available_count(self):
        self.assertEqual(
            self.normalized["available_count"], self.published["available_count"],
            "cadctl available_count disagrees with the published status",
        )
        # available_count must never exceed route_count (basic sanity).
        self.assertLessEqual(
            self.normalized["available_count"], self.normalized["route_count"]
        )

    def test_native_available_matches_pass_semantics(self):
        # cadctl reports native_available True ONLY when native_modules.status
        # is exactly 'PASS' -- assert it tracks the published value truthfully
        # (no fake native availability).
        native_status = (self.published.get("native_modules") or {}).get("status")
        expected = str(native_status).upper() == "PASS"
        self.assertEqual(self.normalized.get("native_available"), expected)


if __name__ == "__main__":
    unittest.main()
