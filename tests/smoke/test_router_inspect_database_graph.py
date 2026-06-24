#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M02 SMOKE -- inspect.database.graph wiring (env-gated live run).

Intent (WHY):
  * The rich native_full path is cadctl.Cad().inspect(dwg, out_dir,
    include_rich=True) -> the native ``inspect.database.graph`` router op. This
    smoke test proves the WIRING is in place at every layer, then -- only when a
    live host is available -- drives the real op and asserts the result is
    internally consistent (truth gate) with the ORIGINAL never written.
  * WIRING (always runs, headless): the op exists + is implemented in the
    operation registry; cadctl exposes the include_rich path; run_job exposes the
    native cad-job builder. If any of these regressed, the rich path is broken
    regardless of AutoCAD. This catches a wiring regression on a headless box.
  * LIVE (env-gated): a real native inspect needs accoreconsole + the golden DWG.
    It runs ONLY when CADOS_LIVE=1 (explicit opt-in) AND both are present;
    otherwise it SKIPS with an explicit reason. It must NEVER hard-fail because
    the box lacks AutoCAD -- a skip is the truthful answer there.
  * No-bypass: the live path performs NO ad-hoc DWG parsing; every byte of CAD
    truth comes from the router via cadctl, operating on a STAGED COPY. The
    original DWG's sha256 is asserted unchanged regardless of outcome.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import hashlib
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
_ACCORECONSOLE = r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe"
_GOLDEN_DWG = os.path.join(_REPO, "staging", "dwg_20260617_191504", "input.dwg")
_TRACKED_GOLDEN_DWG = os.path.join(_REPO, "tests", "fixtures", "native_sample.dwg")
_OPERATIONS_V2 = os.path.join(_REPO, "config", "operations.v2.json")

_TRUTHFUL = {"ok", "blocked", "partial", "unavailable", "not_implemented"}
_GOLDEN_TOTAL = 21747


def _accoreconsole_present():
    if os.path.isfile(_ACCORECONSOLE):
        return True
    from shutil import which
    return which("accoreconsole") is not None or which("accoreconsole.exe") is not None


def _golden_dwg():
    if os.path.isfile(_GOLDEN_DWG):
        return _GOLDEN_DWG
    return _TRACKED_GOLDEN_DWG


def _live_enabled():
    """Live native run requires explicit opt-in AND a host AND the golden DWG."""
    return (os.environ.get("CADOS_LIVE") == "1"
            and _accoreconsole_present()
            and os.path.isfile(_golden_dwg()))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path):
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


class TestInspectDatabaseGraphWiring(unittest.TestCase):
    """Headless: the rich native path is wired end-to-end (no AutoCAD needed)."""

    def test_op_is_registered_and_implemented(self):
        reg = _load_json(_OPERATIONS_V2)
        rec = next((o for o in reg.get("operations", [])
                    if isinstance(o, dict) and o.get("id") == "inspect.database.graph"),
                   None)
        self.assertIsNotNone(rec, "inspect.database.graph not in operations.v2.json")
        self.assertEqual(rec.get("status"), "implemented")

    def test_cadctl_exposes_include_rich(self):
        import cadctl
        import inspect as _inspect
        sig = _inspect.signature(cadctl.Cad.inspect)
        self.assertIn("include_rich", sig.parameters,
                      "cadctl.Cad.inspect lost its include_rich parameter")

    def test_run_job_exposes_native_cad_job(self):
        import run_job
        self.assertTrue(hasattr(run_job, "run_router_cad_job"))
        self.assertTrue(hasattr(run_job, "build_cad_job_command"))
        # the native command must carry the -Operation flag for the op.
        cmd = run_job.build_cad_job_command(
            "staged.dwg", "inspect.database.graph", write_mode="read")
        self.assertIn("-Operation", cmd)
        self.assertIn("inspect.database.graph", cmd)

    def test_ir_builder_has_native_full_builder(self):
        import ir_builder
        self.assertTrue(hasattr(ir_builder, "build_ir_from_database_graph"),
                        "ir_builder lost the native_full builder")


class TestInspectDatabaseGraphLive(unittest.TestCase):
    """Env-gated: drive the real native inspect on the golden DWG (staged copy)."""

    def setUp(self):
        if not _live_enabled():
            reasons = []
            if os.environ.get("CADOS_LIVE") != "1":
                reasons.append("CADOS_LIVE!=1")
            if not _accoreconsole_present():
                reasons.append("no accoreconsole")
            if not os.path.isfile(_golden_dwg()):
                reasons.append("no golden DWG")
            self.skipTest("SKIPPED_ENV: live native inspect disabled (%s)"
                          % ", ".join(reasons))
        import cadctl
        self.cad = cadctl.Cad()
        self.golden_dwg = _golden_dwg()

    def test_native_inspect_rich_is_consistent_and_safe(self):
        sha_before = _sha256(self.golden_dwg)
        size_before = os.path.getsize(self.golden_dwg)
        with tempfile.TemporaryDirectory(prefix="rich_inspect_") as out_dir:
            env = self.cad.inspect(self.golden_dwg, out_dir, mode="graph",
                                   include_rich=True)
            self.assertEqual(env.get("schema"), "ariadne.cadctl.inspect.v1")
            self.assertIn(env.get("status"), _TRUTHFUL,
                          "rich inspect returned non-truthful status: %r" % env)
            # job/result descriptors always written; stdout/stderr captured.
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "cad_job.json")))
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "cad_result.json")))
            if env.get("status") == "ok":
                ir_path = env.get("dwg_graph_ir")
                self.assertTrue(ir_path and os.path.isfile(ir_path))
                import ir_builder
                ir = ir_builder.load_ir(ir_path)
                self.assertEqual(ir.get("coverage_level"), "native_full")
                self.assertEqual(ir["diagnostics"]["entity_count"],
                                 len(ir["entities"]),
                                 "native_full IR violates the truth gate")
                # the golden DWG is 21747 -- if we got ok, it must be that.
                self.assertEqual(ir["diagnostics"]["entity_count"], _GOLDEN_TOTAL)
        # INVARIANT: the original was never written.
        self.assertEqual(_sha256(self.golden_dwg), sha_before,
                         "ORIGINAL golden DWG MODIFIED -- invariant breach")
        self.assertEqual(os.path.getsize(self.golden_dwg), size_before)


if __name__ == "__main__":
    unittest.main()
