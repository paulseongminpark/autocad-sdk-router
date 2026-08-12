#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lane E SMOKE -- cadctl classifies the router-published JSON as historical.

Intent (WHY):
  * The published reports/autocad_router_status_latest.json is an unbound legacy
    observation, not current runtime truth. This smoke test proves cadctl keeps
    its route claims available under the historical compatibility section while
    refusing to elevate them into live availability.
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
        self.normalized = self.cad.status(schema_version=2)

    def test_published_status_is_well_formed(self):
        self.assertIn("routes", self.published)
        self.assertIsInstance(self.published["routes"], list)
        self.assertIn("route_count", self.published)
        self.assertIn("available_count", self.published)
        # route_count should match the realized routes list length.
        self.assertEqual(self.published["route_count"], len(self.published["routes"]))

    def test_cadctl_status_reflects_route_count(self):
        self.assertEqual(self.normalized["status"], "PASS")
        self.assertEqual(
            self.normalized["status_scope"], "projection_assembly_only"
        )
        self.assertEqual(
            self.normalized["compatibility"]["route_count"],
            self.published["route_count"],
            "cadctl route_count disagrees with the published status",
        )

    def test_cadctl_status_reflects_available_count(self):
        self.assertEqual(
            self.normalized["compatibility"]["available_count"],
            self.published["available_count"],
            "cadctl available_count disagrees with the published status",
        )
        # available_count must never exceed route_count (basic sanity).
        compatibility = self.normalized["compatibility"]
        self.assertLessEqual(
            compatibility["available_count"], compatibility["route_count"]
        )

    def test_historical_native_claim_never_becomes_runtime_availability(self):
        historical = self.normalized["historical_snapshot"]
        self.assertEqual(historical["classification"], "HISTORICAL_UNBOUND")
        self.assertFalse(historical["bound_to_current_revision"])
        self.assertEqual(
            self.normalized["runtime_observation"]["availability"], "UNKNOWN"
        )
        self.assertNotIn("native_available", self.normalized)


if __name__ == "__main__":
    unittest.main()
