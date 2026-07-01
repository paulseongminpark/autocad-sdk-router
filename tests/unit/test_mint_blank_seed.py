#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer WAVE-0 F4 TEST -- tools/mint_blank_seed.py.

Intent (WHY):
  F4 mints fixtures/blank_seed.dwg ONCE from the Korean acad.dwt via the native
  transform.database.save_as op, then captures the template's default symbol
  tables via inspect.database.graph so F5 can subtract them from a real
  drawing's full_database diff. Getting any of the following wrong silently
  corrupts that downstream contract:
    1. "Mint ONCE" -- an existing fixtures/blank_seed.dwg must short-circuit
       (ALREADY_MINTED) and never re-run the router, so a stray re-mint can't
       silently invalidate a frozen fixture F5 already built a mask from.
    2. No-fake-success -- a missing template or a failed/unavailable router
       run must report DONE_NEEDS_RUNTIME with the exact deferred command, and
       must NEVER leave a half-written .dwg claimed as done.
    3. The AcDbDatabase::saveAs(bBakAndRename=true) + router's write_copy
       _QSAVE combination is empirically known (see F4 report) to leave a
       stray "<stem>.bak" of the SUPERSEDED first save next to the real
       output; the mint must clean it up and say so (cleaned_bak_sidecar).
    4. modelspace_entities must be checked, not just copied through -- a
       non-zero count on what is supposed to be a blank seed is a concern,
       not a silent pass.

This does NOT require AutoCAD/accoreconsole: run_job.run_router_cad_job is
monkeypatched (module-attribute swap, restored in tearDown -- same pattern as
tests/unit/test_patch_engine_policy.py's _FakeRunJob) with a fake that mimics
the real router's ariadne.autocad_router_run.v2 envelope shape (envelope.status
== "PASS", inner "result" dict) and performs the fake's own on-disk write, so
mint_blank_seed's real control flow (mint -> sha256 -> baseline -> cleanup) is
genuinely exercised end to end.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import run_job  # noqa: E402  (sibling helper; module attr gets swapped per-test)
import mint_blank_seed  # noqa: E402  (module under test)


_GRAPH_RESULT_ZERO_ENTITIES = {
    "modelspace_entities": 0,
    "entities": [],
    "symbol_tables": {
        "layers": [{"handle": "10", "name": "0"}],
        "linetypes": [{"handle": "14", "name": "ByBlock"}],
        "text_styles": [{"handle": "11", "name": "Standard"}],
        "dim_styles": [{"handle": "27", "name": "Standard"}],
        "viewports": [{"handle": "94", "name": "*Active"}],
        "app_ids": [{"handle": "12", "name": "ACAD"}],
    },
    "block_table_records": [{"handle": "1F", "name": "*Model_Space", "entity_count": 0}],
    "block_definitions": [],
    "layouts": [{"handle": "22", "name": "Model"}],
    "coverage": {"counts": {"layers": 1}},
}


class _FakeRunJob:
    """Stand-in for run_job.run_router_cad_job -- no accoreconsole needed.

    Mirrors the REAL envelope shape observed from a live run (F4 report):
    envelope.status == "PASS", exit_code == 0, and result == the INNER native
    payload (run_job.run_router_cad_job already unwraps doc["result"]).
    """

    def __init__(self, *, save_as_result=None, save_as_error=None,
                graph_result=None, graph_error=None,
                write_bytes=b"FAKE-DWG-BYTES", also_write_bak=False):
        self.calls: list[dict] = []
        self._save_as_result = save_as_result
        self._save_as_error = save_as_error
        self._graph_result = graph_result
        self._graph_error = graph_error
        self._write_bytes = write_bytes
        self._also_write_bak = also_write_bak

    def run_router_cad_job(self, staged_dwg, run_dir, operation, *,
                           write_mode="read", job_path=None, timeout=600,
                           intent="dwg"):
        self.calls.append({"staged": staged_dwg, "operation": operation,
                           "write_mode": write_mode, "job_path": job_path})
        os.makedirs(run_dir, exist_ok=True)

        if operation == mint_blank_seed.MINT_OPERATION:
            if self._save_as_error:
                return self._envelope(exit_code=1, error=self._save_as_error, result=None)
            job = json.loads(Path(job_path).read_text(encoding="utf-8"))
            out_path = Path(job["output_path"])
            out_path.parent.mkdir(parents=True, exist_ok=True)
            # Simulate AcDbDatabase::saveAs actually persisting bytes.
            out_path.write_bytes(self._write_bytes)
            if self._also_write_bak:
                out_path.with_suffix(".bak").write_bytes(b"STALE-SUPERSEDED-SAVE")
            result = self._save_as_result if self._save_as_result is not None else {
                "written": True, "errorstatus": 0,
                "output_path": str(out_path), "staged_db_only": True,
            }
            return self._envelope(exit_code=0, result=result)

        if operation == mint_blank_seed.BASELINE_OPERATION:
            if self._graph_error:
                return self._envelope(exit_code=1, error=self._graph_error, result=None)
            result = self._graph_result if self._graph_result is not None else _GRAPH_RESULT_ZERO_ENTITIES
            return self._envelope(exit_code=0, result=result)

        return self._envelope(exit_code=1, error=f"unexpected operation {operation}", result=None)

    @staticmethod
    def _envelope(*, exit_code, result=None, error=None):
        return {
            "command": ["fake-router"],
            "exit_code": exit_code,
            "stdout_path": None,
            "stderr_path": None,
            "envelope": {"status": "PASS" if exit_code == 0 and result is not None else "ROUTE_NONZERO"},
            "result_json": None,
            "result": result,
            "staged_used": None,
            "timed_out": False,
            "error": error,
        }


class MintBlankSeedTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)
        self._orig_run_router_cad_job = run_job.run_router_cad_job
        self.addCleanup(self._restore_run_job)

    def _restore_run_job(self):
        run_job.run_router_cad_job = self._orig_run_router_cad_job

    def _install_fake(self, fake: _FakeRunJob) -> _FakeRunJob:
        run_job.run_router_cad_job = fake.run_router_cad_job
        return fake

    def _make_template_file(self) -> Path:
        template = self.tmp_path / "acad.dwt"
        template.write_bytes(b"FAKE-TEMPLATE-BYTES")
        return template


class TestFindTemplate(MintBlankSeedTestCase):
    def test_explicit_path_that_exists_is_returned(self):
        template = self._make_template_file()
        found = mint_blank_seed.find_template(str(template))
        self.assertEqual(found, template)

    def test_explicit_path_missing_returns_none_not_fabricated(self):
        missing = self.tmp_path / "does_not_exist.dwt"
        self.assertIsNone(mint_blank_seed.find_template(str(missing)))

    def test_auto_discovers_via_home_glob_when_no_explicit_path(self):
        # Build a fake %LOCALAPPDATA%\Autodesk\AutoCAD 2027\R26.0\kor\Template\acad.dwt
        # under a synthetic home, and prove find_template's glob-based discovery
        # (not just a hardcoded path) locates it.
        fake_home = self.tmp_path / "home"
        template_dir = fake_home / "AppData" / "Local" / "Autodesk" / "AutoCAD 2027" / "R26.0" / "kor" / "Template"
        template_dir.mkdir(parents=True)
        template = template_dir / "acad.dwt"
        template.write_bytes(b"FAKE-TEMPLATE-BYTES")

        orig_home = Path.home
        orig_env = os.environ.pop(mint_blank_seed._TEMPLATE_ENV_VAR, None)
        Path.home = staticmethod(lambda: fake_home)
        try:
            found = mint_blank_seed.find_template(None)
        finally:
            Path.home = orig_home
            if orig_env is not None:
                os.environ[mint_blank_seed._TEMPLATE_ENV_VAR] = orig_env

        self.assertEqual(found, template)

    def test_env_var_override_is_honored(self):
        template = self._make_template_file()
        orig_env = os.environ.get(mint_blank_seed._TEMPLATE_ENV_VAR)
        os.environ[mint_blank_seed._TEMPLATE_ENV_VAR] = str(template)
        try:
            found = mint_blank_seed.find_template(None)
        finally:
            if orig_env is None:
                os.environ.pop(mint_blank_seed._TEMPLATE_ENV_VAR, None)
            else:
                os.environ[mint_blank_seed._TEMPLATE_ENV_VAR] = orig_env
        self.assertEqual(found, template)


class TestMintBlankSeed(MintBlankSeedTestCase):
    def test_already_minted_short_circuits_without_touching_router(self):
        output = self.tmp_path / "blank_seed.dwg"
        output.write_bytes(b"ALREADY-HERE")
        fake = self._install_fake(_FakeRunJob())  # would record a call if (wrongly) invoked

        result = mint_blank_seed.mint_blank_seed(
            template=str(self._make_template_file()), output=output,
            run_dir=self.tmp_path / "runs",
        )

        self.assertEqual(result["status"], "ALREADY_MINTED")
        self.assertEqual(fake.calls, [], "ALREADY_MINTED must not invoke the router at all")
        self.assertEqual(output.read_bytes(), b"ALREADY-HERE", "must never overwrite without --force")

    def test_missing_template_reports_done_needs_runtime_with_deferred_command(self):
        output = self.tmp_path / "blank_seed.dwg"
        fake = self._install_fake(_FakeRunJob())

        result = mint_blank_seed.mint_blank_seed(
            template=str(self.tmp_path / "no_such_template.dwt"), output=output,
            run_dir=self.tmp_path / "runs",
        )

        self.assertEqual(result["status"], "DONE_NEEDS_RUNTIME")
        self.assertIn("mint_blank_seed.py", result["deferred_command"])
        self.assertFalse(output.exists(), "must never fabricate a .dwg when the template is missing")
        self.assertEqual(fake.calls, [], "must not call the router when no template was found")

    def test_router_mint_failure_reports_done_needs_runtime_with_real_template_path(self):
        output = self.tmp_path / "blank_seed.dwg"
        template = self._make_template_file()
        self._install_fake(_FakeRunJob(save_as_error="accoreconsole not found"))

        result = mint_blank_seed.mint_blank_seed(
            template=str(template), output=output, run_dir=self.tmp_path / "runs",
        )

        self.assertEqual(result["status"], "DONE_NEEDS_RUNTIME")
        self.assertIn(str(template), result["deferred_command"])
        self.assertFalse(output.exists())

    def test_successful_mint_writes_dwg_sha256_and_baseline(self):
        output = self.tmp_path / "blank_seed.dwg"
        template = self._make_template_file()
        payload = b"REAL-ENOUGH-DWG-BYTES-FOR-A-HASH"
        fake = self._install_fake(_FakeRunJob(write_bytes=payload))

        result = mint_blank_seed.mint_blank_seed(
            template=str(template), output=output, run_dir=self.tmp_path / "runs",
        )

        self.assertEqual(result["status"], "DONE")
        self.assertIsNone(result["concern"])
        self.assertEqual(result["modelspace_entities"], 0)
        self.assertFalse(result["cleaned_bak_sidecar"])

        # dwg on disk, byte-for-byte what the (fake) native op wrote.
        self.assertEqual(output.read_bytes(), payload)

        # sha256 sidecar matches a fresh recompute -- not just copied from the result dict.
        sidecar = Path(result["sha256_path"])
        self.assertTrue(sidecar.exists())
        import hashlib
        self.assertEqual(sidecar.read_text(encoding="ascii").split()[0], hashlib.sha256(payload).hexdigest())
        self.assertEqual(result["sha256"], hashlib.sha256(payload).hexdigest())

        # baseline JSON carries the exact native symbol-table payload F5 subtracts.
        baseline_doc = json.loads(Path(result["baseline_path"]).read_text(encoding="utf-8"))
        self.assertEqual(baseline_doc["schema"], "ariadne.blank_seed_symbol_table_baseline.v1")
        self.assertEqual(baseline_doc["baseline"], _GRAPH_RESULT_ZERO_ENTITIES)
        self.assertEqual(baseline_doc["minted_from_template"], str(template))

        # exactly two router round trips: mint, then baseline capture.
        ops = [c["operation"] for c in fake.calls]
        self.assertEqual(ops, [mint_blank_seed.MINT_OPERATION, mint_blank_seed.BASELINE_OPERATION])
        # the second (read) call must target the MINTED file, never the template.
        self.assertEqual(fake.calls[1]["staged"], str(output))
        self.assertEqual(fake.calls[1]["write_mode"], "read")

    def test_stray_bak_sidecar_from_the_qsave_double_save_is_cleaned_up(self):
        output = self.tmp_path / "blank_seed.dwg"
        template = self._make_template_file()
        self._install_fake(_FakeRunJob(also_write_bak=True))

        result = mint_blank_seed.mint_blank_seed(
            template=str(template), output=output, run_dir=self.tmp_path / "runs",
        )

        self.assertEqual(result["status"], "DONE")
        self.assertTrue(result["cleaned_bak_sidecar"])
        self.assertFalse(output.with_suffix(".bak").exists(),
                         "the superseded first-save .bak must not survive as a stray file")

    def test_nonzero_modelspace_entities_is_a_surfaced_concern_not_a_silent_pass(self):
        output = self.tmp_path / "blank_seed.dwg"
        template = self._make_template_file()
        dirty_graph = dict(_GRAPH_RESULT_ZERO_ENTITIES, modelspace_entities=3)
        self._install_fake(_FakeRunJob(graph_result=dirty_graph))

        result = mint_blank_seed.mint_blank_seed(
            template=str(template), output=output, run_dir=self.tmp_path / "runs",
        )

        self.assertEqual(result["status"], "DONE")
        self.assertIsNotNone(result["concern"])
        self.assertIn("3", result["concern"])

    def test_baseline_capture_failure_after_a_successful_mint_is_a_concern_not_silently_dropped(self):
        output = self.tmp_path / "blank_seed.dwg"
        template = self._make_template_file()
        self._install_fake(_FakeRunJob(graph_error="router timed out"))

        result = mint_blank_seed.mint_blank_seed(
            template=str(template), output=output, run_dir=self.tmp_path / "runs",
        )

        # the .dwg itself is still a truthful DONE (it really was minted);
        # the missing baseline must be visible, never silently absent.
        self.assertEqual(result["status"], "DONE")
        self.assertTrue(output.exists())
        self.assertIsNone(result["baseline_path"])
        self.assertIsNotNone(result["concern"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
