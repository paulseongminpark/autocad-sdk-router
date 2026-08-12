#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lane E TEST -- cadctl control surface: status (read-only), registry, error paths.

Intent (WHY):
  * cadctl.status() preserves the v1 read-only compatibility contract, while
    ``schema_version=2`` exposes separately typed current-status projections.
    Neither form may spawn ``-Action status``.
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
import subprocess
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
    """status() preserves v1 and exposes v2 only through explicit negotiation."""

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
        self.assertEqual(out.get("evidence_class"), "historical_unbound")
        self.assertFalse(out.get("bound_to_current_revision"))
        self.assertEqual(out.get("route_count"), published.get("route_count"))
        self.assertEqual(
            out.get("available_count"), published.get("available_count")
        )
        self.assertEqual(out.get("router_status"), published.get("status"))
        self.assertIsInstance(out.get("routes"), list)
        self.assertEqual(len(out["routes"]), len(published.get("routes", [])))
        # Each normalized route carries route/available/engine.
        for r in out["routes"]:
            self.assertIn("route", r)
            self.assertIn("available", r)
            self.assertIsInstance(r["available"], bool)

    def test_status_v2_separates_current_facts_from_historical_claims(self):
        out = self.cad.status(schema_version=2)

        self.assertEqual(out.get("schema"), "ariadne.cadctl.status.v2")
        self.assertEqual(out.get("status"), "PASS")
        self.assertEqual(out.get("status_scope"), "projection_assembly_only")
        self.assertEqual(
            out["historical_snapshot"].get("classification"),
            "HISTORICAL_UNBOUND",
        )
        self.assertFalse(
            out["historical_snapshot"].get("bound_to_current_revision")
        )
        self.assertEqual(out["runtime_observation"]["availability"], "UNKNOWN")
        self.assertNotIn("native_available", out)

    def test_module_level_status_matches_instance(self):
        if not os.path.isfile(_STATUS_JSON):
            self.skipTest("SKIPPED_ENV: published router status JSON absent")
        # The convenience wrapper must agree with the bound method.
        self.assertEqual(
            self.cadctl.status().get("route_count"),
            self.cad.status().get("route_count"),
        )

        current = self.cadctl.status(
            schema_version=2,
            expected_revision="0" * 40,
        )
        self.assertEqual(current.get("schema"), "ariadne.cadctl.status.v2")

    def test_status_missing_file_reports_unavailable_not_crash(self):
        # Point Cad at a router_home with no status JSON: it must report
        # 'unavailable' truthfully, never raise and never spawn a probe.
        with tempfile.TemporaryDirectory() as tmp:
            cad = self.cadctl.Cad(router_home=tmp)
            out = cad.status()
            self.assertEqual(out.get("schema"), "ariadne.cadctl.status.v1")
            self.assertEqual(out.get("status"), "unavailable")
            self.assertEqual(out.get("route_count"), 0)
            self.assertFalse(out.get("native_available"))

    def test_status_note_declares_read_only(self):
        if not os.path.isfile(_STATUS_JSON):
            self.skipTest("SKIPPED_ENV: published router status JSON absent")
        out = self.cad.status(schema_version=2)
        self.assertIn("did not start autocad", (
            out["runtime_observation"].get("reason") or ""
        ).lower())

    def test_status_json_cli_includes_registry_summary(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(_REPO, "tools", "cadctl_cli.py"),
             "status", "--json"],
            cwd=_REPO,
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out.get("schema"), "ariadne.cadctl.status.v1")
        self.assertEqual(out.get("status"), "ok")
        self.assertIn("registry", out)

        current = subprocess.run(
            [sys.executable, os.path.join(_REPO, "tools", "cadctl_cli.py"),
             "status", "--schema-version", "2"],
            cwd=_REPO,
            text=True,
            capture_output=True,
        )
        self.assertEqual(current.returncode, 0, current.stderr)
        current_out = json.loads(current.stdout)
        self.assertEqual(current_out.get("schema"), "ariadne.cadctl.status.v2")
        registry = current_out["capability"]["operation_registry"]
        self.assertEqual(registry.get("status"), "PASS")
        self.assertTrue(registry["receipt"].get("verified"))

    def test_status_rejects_an_unknown_schema_version(self):
        with self.assertRaisesRegex(ValueError, "schema_version"):
            self.cad.status(schema_version=3)
        with self.assertRaisesRegex(ValueError, "expected_revision"):
            self.cad.status(expected_revision="a" * 40)


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

    def test_cli_registry_explain_returns_registry_operation_status(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(_REPO, "tools", "cadctl_cli.py"),
             "registry", "explain", "inspect.database.graph"],
            cwd=_REPO,
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out.get("status"), "ok")
        self.assertEqual(out.get("operation"), "inspect.database.graph")
        self.assertEqual(out.get("registry_operation_status"), "implemented")


class TestCadctlToolSurfaceCli(unittest.TestCase):
    """M04 CLI parity for high-value read/query shell commands."""

    def test_get_entity_cli_fetches_one_handle(self):
        import sqlite_ir_store

        with tempfile.TemporaryDirectory() as tmp:
            ir_path = os.path.join(tmp, "dwg_graph_ir.json")
            with open(ir_path, "w", encoding="utf-8") as fh:
                json.dump(sqlite_ir_store._fixture_ir(), fh, ensure_ascii=False, indent=2)
            proc = subprocess.run(
                [sys.executable, os.path.join(_REPO, "tools", "cadctl_cli.py"),
                 "get-entity", "--ir", ir_path, "--handle", "2A7"],
                cwd=_REPO,
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(out.get("schema"), "ariadne.cadctl.get_entity.v1")
            self.assertEqual(out.get("status"), "ok")
            self.assertEqual(out.get("handle"), "2A7")
            self.assertEqual(out.get("row_count"), 1)

    def test_cli_shell_surfaces_degrade_without_crash(self):
        commands = [
            ["patch", "dry-run", "--patch-json", '{"schema":"ariadne.cad_patch.v1"}'],
            ["diff", "--pre-ir", "missing-before.json", "--post-ir", "missing-after.json"],
            ["visual", "--source-ref", "missing-source.dwg", "--kind", "png"],
            ["live", "status"],
        ]
        for cmd in commands:
            with self.subTest(cmd=cmd):
                proc = subprocess.run(
                    [sys.executable, os.path.join(_REPO, "tools", "cadctl_cli.py"), *cmd],
                    cwd=_REPO,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                out = json.loads(proc.stdout)
                self.assertIn(out.get("status"), {
                    "ok", "planned", "rejected", "blocked", "not_implemented", "error",
                })


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
