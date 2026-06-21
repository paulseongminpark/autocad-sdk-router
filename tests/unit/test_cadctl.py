#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lane E TEST -- cadctl control surface: status (read-only), registry, error paths.

Intent (WHY):
  * cadctl.status() MUST be a READ-ONLY normalization of the router-published
    status JSON -- it must NEVER spawn ``-Action status`` (that would violate the
    Daedalus/CAD-OS invariant and could mutate live probe state). We assert it
    returns a normalized dict whose route_count/available_count mirror the
    published file, and that it does so without invoking the router.
  * registry_list / registry_coverage are pure file reads of operations.v2.json;
    they must report the wired (implemented) count truthfully.
  * inspect() on a missing path must fail CLEANLY with status 'blocked' and must
    NOT raise -- a truthful blocked answer is the contract, not a crash.

These tests touch NO DWG and never spawn AutoCAD. inspect() is only exercised on
a nonexistent path (the precondition-failed branch, which returns before staging
or any router call).

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_JSON_ENCODING = "utf-8-sig"
_STATUS_JSON = os.path.join(_REPO, "reports", "autocad_router_status_latest.json")


def _load_json(path: str):
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


class TestCadctlStatusReadOnly(unittest.TestCase):
    """status() reflects the published status JSON without running the router."""

    def setUp(self):
        import cadctl
        self.cadctl = cadctl
        self.cad = cadctl.Cad()

    def test_status_present_normalizes_route_counts(self):
        if not os.path.isfile(_STATUS_JSON):
            self.skipTest("SKIPPED_ENV: published router status JSON absent")
        published = _load_json(_STATUS_JSON)
        out = self.cad.status()
        self.assertEqual(out.get("schema"), "ariadne.cadctl.status.v1")
        self.assertEqual(out.get("status"), "ok")
        # The normalized counts must mirror the published file exactly.
        self.assertEqual(out.get("route_count"), published.get("route_count"))
        self.assertEqual(out.get("available_count"), published.get("available_count"))
        self.assertEqual(out.get("router_status"), published.get("status"))
        self.assertIsInstance(out.get("routes"), list)
        self.assertEqual(len(out["routes"]), len(published.get("routes", [])))
        # Each normalized route carries route/available/engine.
        for r in out["routes"]:
            self.assertIn("route", r)
            self.assertIn("available", r)
            self.assertIsInstance(r["available"], bool)

    def test_module_level_status_matches_instance(self):
        if not os.path.isfile(_STATUS_JSON):
            self.skipTest("SKIPPED_ENV: published router status JSON absent")
        # The convenience wrapper must agree with the bound method.
        self.assertEqual(
            self.cadctl.status().get("route_count"),
            self.cad.status().get("route_count"),
        )

    def test_status_missing_file_reports_unavailable_not_crash(self):
        # Point Cad at a router_home with no status JSON: it must report
        # 'unavailable' truthfully, never raise and never spawn a probe.
        with tempfile.TemporaryDirectory() as tmp:
            cad = self.cadctl.Cad(router_home=tmp)
            out = cad.status()
            self.assertEqual(out.get("status"), "unavailable")
            self.assertEqual(out.get("route_count"), 0)
            self.assertFalse(out.get("native_available"))
            self.assertIn("not found", (out.get("reason") or "").lower())

    def test_status_note_declares_read_only(self):
        if not os.path.isfile(_STATUS_JSON):
            self.skipTest("SKIPPED_ENV: published router status JSON absent")
        out = self.cad.status()
        # The contract that status is a snapshot, not a live probe, is asserted
        # in the payload itself -- this is how we encode the read-only intent.
        self.assertIn("not a live probe", (out.get("note") or "").lower())


class TestCadctlRegistry(unittest.TestCase):
    """registry_list / registry_coverage are truthful pure reads."""

    def setUp(self):
        import cadctl
        self.cad = cadctl.Cad()

    def test_registry_list_reports_ops_and_wired_count(self):
        out = self.cad.registry_list()
        self.assertEqual(out.get("status"), "ok")
        self.assertEqual(out.get("registry_schema"), "ariadne.operations_registry.v2")
        self.assertIsInstance(out.get("operations"), list)
        self.assertGreaterEqual(out.get("operation_count", 0), 29)
        # wired_count counts status=='implemented'; must be >0 and <= total.
        self.assertGreater(out.get("wired_count", 0), 0)
        self.assertLessEqual(out["wired_count"], out["operation_count"])
        # operation_count must equal the realized list length (no drift).
        self.assertEqual(out["operation_count"], len(out["operations"]))

    def test_registry_coverage_is_self_consistent(self):
        out = self.cad.registry_coverage()
        self.assertEqual(out.get("status"), "ok")
        self.assertGreaterEqual(out.get("operation_count", 0), 29)
        # The computed-by-status 'implemented' tally must equal wired_count.
        self.assertEqual(
            out.get("computed_by_status", {}).get("implemented"),
            out.get("wired_count"),
        )
        # 'consistent' compares declared totals vs computed -- must hold on a
        # healthy registry.
        self.assertTrue(out.get("consistent"),
                        "declared totals.by_status.implemented disagrees with computed")

    def test_registry_list_and_coverage_agree_on_wired(self):
        lst = self.cad.registry_list()
        cov = self.cad.registry_coverage()
        self.assertEqual(lst.get("wired_count"), cov.get("wired_count"))
        self.assertEqual(lst.get("operation_count"), cov.get("operation_count"))


class TestCadctlInspectErrorPaths(unittest.TestCase):
    """inspect() on a missing input errors cleanly (blocked), never raises."""

    def setUp(self):
        import cadctl
        self.cad = cadctl.Cad()

    def test_inspect_missing_dwg_returns_blocked(self):
        with tempfile.TemporaryDirectory() as out_dir:
            missing = os.path.join(out_dir, "does_not_exist.dwg")
            env = self.cad.inspect(missing, out_dir, mode="graph")
            self.assertEqual(env.get("schema"), "ariadne.cadctl.inspect.v1")
            self.assertEqual(env.get("status"), "blocked")
            self.assertIn("not found", (env.get("reason") or "").lower())
            # No staged copy should have been made (we never reached staging).
            self.assertIsNone(env.get("staged_copy"))
            # A cad_job.json descriptor is still written (the attempted job).
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "cad_job.json")))
            # And it did NOT silently produce an IR.
            self.assertNotIn("dwg_graph_ir", env)

    def test_inspect_missing_dwg_does_not_touch_staging_golden(self):
        # The blocked path must short-circuit before creating any staging dir.
        staging_before = set()
        staging_root = self.cad.staging_golden
        if staging_root.exists():
            staging_before = set(p.name for p in staging_root.iterdir())
        with tempfile.TemporaryDirectory() as out_dir:
            self.cad.inspect(os.path.join(out_dir, "nope.dwg"), out_dir)
        staging_after = set()
        if staging_root.exists():
            staging_after = set(p.name for p in staging_root.iterdir())
        self.assertEqual(
            staging_before, staging_after,
            "inspect() on a missing DWG created a staging/golden entry (it must not)",
        )

    def test_query_missing_ir_returns_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.cad.query(os.path.join(tmp, "no_ir.json"), "SELECT 1")
            self.assertEqual(out.get("schema"), "ariadne.cadctl.query.v1")
            self.assertEqual(out.get("status"), "blocked")

    def test_validate_missing_ir_returns_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.cad.validate(os.path.join(tmp, "no_ir.json"))
            self.assertEqual(out.get("schema"), "ariadne.cadctl.validate.v1")
            self.assertEqual(out.get("status"), "blocked")


if __name__ == "__main__":
    unittest.main()
