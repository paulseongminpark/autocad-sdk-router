#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_dcm TEST -- DCM (dimensional constraint solver) availability probe.

Intent (WHY):
  probe_dcm.py exists to answer ONE precondition question with live evidence,
  never a guess: can accoreconsole headlessly evaluate the DCM/AcDbAssocManager
  network (AUTOCONSTRAIN -> geometry actually moves)? These tests do NOT
  require a live accoreconsole: they exercise the real staging / env-wiring /
  parsing / classification pipeline with a stand-in ``runner`` (dependency
  injection, matching this suite's stdlib-only convention -- no
  unittest.mock anywhere in tests/unit), and separately hold the pure decision
  function (classify) to its honesty contract:
    * a real geometry snap-to-horizontal -> available=True
    * geometry unchanged after AUTOCONSTRAIN -> available=False
    * a vacuous/broken test setup (line was never non-horizontal, or the
      result file never appeared) -> available=None ("inconclusive"), NEVER a
      fabricated True or False (Rule 12 -- no fake pass, no fake fail).
  A regression that makes classify() return True/False on missing or vacuous
  data, or that makes run_probe() invoke the real accoreconsole binary when it
  was never found, would silently break the "never claim availability without
  evidence" contract this tool exists for -- these tests fail loudly instead.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import probe_dcm  # noqa: E402


class TestParseResultKv(unittest.TestCase):
    def test_parses_well_formed_lines(self):
        text = "before_y1=0.0\nbefore_y2=0.02\nafter_y1=0.0\nafter_y2=0.0\n"
        self.assertEqual(
            probe_dcm._parse_result_kv(text),
            {"before_y1": 0.0, "before_y2": 0.02, "after_y1": 0.0, "after_y2": 0.0},
        )

    def test_ignores_blank_and_malformed_lines(self):
        text = "\n  \nbefore_y1=0.0\nnot_a_kv_line\nafter_y1=oops\nafter_y2=1.5\n"
        # "not_a_kv_line" has no '=' (skipped); "after_y1=oops" fails float() (skipped).
        self.assertEqual(probe_dcm._parse_result_kv(text), {"before_y1": 0.0, "after_y2": 1.5})


class TestClassify(unittest.TestCase):
    """The core honesty contract: True/False only on real evidence, else None."""

    def test_available_true_when_geometry_snaps_horizontal(self):
        values = {"before_y1": 0.0, "before_y2": 0.02, "after_y1": 0.0, "after_y2": 0.0}
        out = probe_dcm.classify(values)
        self.assertIs(out["available"], True)
        self.assertEqual(out["reason"], "autoconstrain_solved_geometry")
        self.assertAlmostEqual(out["before_dy"], 0.02)
        self.assertAlmostEqual(out["after_dy"], 0.0)

    def test_available_false_when_geometry_unchanged(self):
        values = {"before_y1": 0.0, "before_y2": 0.02, "after_y1": 0.0, "after_y2": 0.02}
        out = probe_dcm.classify(values)
        self.assertIs(out["available"], False)
        self.assertEqual(out["reason"], "geometry_unchanged_after_autoconstrain")

    def test_inconclusive_when_before_state_already_horizontal(self):
        # The probe's OWN test geometry was supposed to start non-horizontal;
        # if it didn't, the run proves nothing either way -- must not be
        # reported as "available" just because before==after.
        values = {"before_y1": 0.0, "before_y2": 0.0, "after_y1": 0.0, "after_y2": 0.0}
        out = probe_dcm.classify(values)
        self.assertIsNone(out["available"])
        self.assertEqual(out["reason"], "test_precondition_failed")

    def test_inconclusive_when_result_incomplete(self):
        out = probe_dcm.classify({"before_y1": 0.0})
        self.assertIsNone(out["available"])
        self.assertEqual(out["reason"], "result_incomplete")

    def test_near_threshold_within_tolerance_counts_as_solved(self):
        # after_dy just under GEOMETRY_TOL must still read as "solved" (exact
        # float equality is not required, matching the P-gate's own tol basis).
        tiny = probe_dcm.GEOMETRY_TOL / 10
        values = {"before_y1": 0.0, "before_y2": 0.02, "after_y1": 0.0, "after_y2": tiny}
        out = probe_dcm.classify(values)
        self.assertIs(out["available"], True)


class TestFindAccoreconsole(unittest.TestCase):
    """Exercises the real detection function via the ``candidates`` injection
    seam -- no monkeypatching of os.path/shutil needed."""

    def test_returns_first_existing_absolute_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            real = Path(td) / "accoreconsole.exe"
            real.write_text("stand-in binary", encoding="utf-8")
            missing = str(Path(td) / "does_not_exist" / "accoreconsole.exe")
            found = probe_dcm.find_accoreconsole(candidates=[missing, str(real)])
            self.assertEqual(found, str(real))

    def test_returns_none_when_no_candidate_exists(self):
        with tempfile.TemporaryDirectory() as td:
            missing = str(Path(td) / "nope" / "accoreconsole.exe")
            found = probe_dcm.find_accoreconsole(candidates=[missing])
            self.assertIsNone(found)


class TestRunProbeRuntimeUnavailable(unittest.TestCase):
    """The hard-rule contract: if the runtime isn't there, NEVER attempt a run
    and NEVER claim availability either way."""

    def test_missing_engine_short_circuits_before_any_subprocess_call(self):
        def _must_not_be_called(*a, **k):
            raise AssertionError("runner must not be invoked when accoreconsole is absent")

        with tempfile.TemporaryDirectory() as td:
            missing_engine = str(Path(td) / "no_such_accoreconsole.exe")
            out = probe_dcm.run_probe(engine=missing_engine, runner=_must_not_be_called)

        self.assertEqual(out["schema"], "ariadne.dcm_probe.v1")
        self.assertFalse(out["runtime_available"])
        self.assertIsNone(out["available"])
        self.assertEqual(out["reason"], "accoreconsole_not_found")
        # DONE_NEEDS_RUNTIME contract: the exact deferred command must be recorded.
        self.assertIn("probe_dcm.py", out["deferred_command"])

    def test_missing_fixture_is_reported_not_fabricated(self):
        with tempfile.TemporaryDirectory() as td:
            dummy_engine = Path(td) / "accoreconsole.exe"
            dummy_engine.write_text("stand-in", encoding="utf-8")
            missing_fixture = str(Path(td) / "no_such.dwg")

            def _must_not_be_called(*a, **k):
                raise AssertionError("runner must not be invoked when the fixture is absent")

            out = probe_dcm.run_probe(engine=str(dummy_engine), fixture=missing_fixture,
                                      runner=_must_not_be_called)
        self.assertTrue(out["runtime_available"])
        self.assertIsNone(out["available"])
        self.assertEqual(out["reason"], "fixture_dwg_not_found")


class _StageDirCapturingRunnerBase(unittest.TestCase):
    """Shared scaffolding: a real dummy 'engine' + real dummy 'fixture' file so
    run_probe's existence checks pass, then a fake runner plays the role of
    accoreconsole by writing the ``ARIADNE_DCM_PROBE_OUT`` result file itself
    (exactly what the real AutoLISP defun does), returning a REAL
    subprocess.CompletedProcess (no mock library involved)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        td = Path(self._tmp.name)
        self.engine = td / "accoreconsole.exe"
        self.engine.write_text("stand-in", encoding="utf-8")
        self.fixture = td / "fixture.dwg"
        self.fixture.write_text("stand-in dwg bytes", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _make_runner(self, result_text):
        captured = {}

        def _runner(cmd, cwd=None, env=None, **kwargs):
            captured["cmd"] = cmd
            captured["cwd"] = cwd
            captured["env"] = env
            out_path = env[probe_dcm.ENV_OUT]
            with open(out_path, "w", encoding="ascii") as fh:
                fh.write(result_text)
            return subprocess.CompletedProcess(args=cmd, returncode=0,
                                               stdout="ARIADNE_DCM_PROBE_DONE\n", stderr="")

        return _runner, captured


class TestRunProbeEndToEnd(_StageDirCapturingRunnerBase):
    def test_solved_geometry_yields_available_true_and_cleans_stage(self):
        runner, captured = self._make_runner(
            "before_x1=0.0\nbefore_y1=0.0\nbefore_x2=10.0\nbefore_y2=0.02\n"
            "after_x1=0.0\nafter_y1=0.0\nafter_x2=10.0\nafter_y2=0.0\n"
        )
        out = probe_dcm.run_probe(engine=str(self.engine), fixture=str(self.fixture), runner=runner)

        self.assertIs(out["available"], True)
        self.assertEqual(out["reason"], "autoconstrain_solved_geometry")
        self.assertEqual(out["endpoints"]["after_y2"], 0.0)
        self.assertEqual(out["exit_code"], 0)
        # The real staged copy + generated .scr/.lsp existed at call time...
        self.assertTrue(str(captured["cmd"][0]).endswith("accoreconsole.exe"))
        self.assertEqual(captured["cmd"][1], "/i")
        self.assertTrue(captured["cmd"][2].endswith("staged.dwg"))
        self.assertEqual(captured["cmd"][3], "/s")
        self.assertTrue(captured["cmd"][4].endswith("dcm_probe.scr"))
        # ...but the stage dir is cleaned up afterward (no keep_stage).
        self.assertNotIn("stage_dir", out)
        self.assertFalse(os.path.exists(captured["cwd"]))

    def test_unchanged_geometry_yields_available_false(self):
        runner, _ = self._make_runner(
            "before_x1=0.0\nbefore_y1=0.0\nbefore_x2=10.0\nbefore_y2=0.02\n"
            "after_x1=0.0\nafter_y1=0.0\nafter_x2=10.0\nafter_y2=0.02\n"
        )
        out = probe_dcm.run_probe(engine=str(self.engine), fixture=str(self.fixture), runner=runner)
        self.assertIs(out["available"], False)
        self.assertEqual(out["reason"], "geometry_unchanged_after_autoconstrain")

    def test_missing_result_file_is_inconclusive_not_fabricated(self):
        def _runner_writes_nothing(cmd, cwd=None, env=None, **kwargs):
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        out = probe_dcm.run_probe(engine=str(self.engine), fixture=str(self.fixture),
                                  runner=_runner_writes_nothing)
        self.assertIsNone(out["available"])
        self.assertEqual(out["reason"], "result_file_missing")

    def test_timeout_is_inconclusive_not_fabricated(self):
        def _runner_times_out(cmd, cwd=None, env=None, **kwargs):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 1))

        out = probe_dcm.run_probe(engine=str(self.engine), fixture=str(self.fixture),
                                  runner=_runner_times_out, timeout=1)
        self.assertIsNone(out["available"])
        self.assertEqual(out["reason"], "accoreconsole_launch_error")
        self.assertTrue(out["timed_out"])

    def test_keep_stage_preserves_the_directory(self):
        runner, _ = self._make_runner("before_y1=0.0\nbefore_y2=0.02\nafter_y1=0.0\nafter_y2=0.0\n")
        out = probe_dcm.run_probe(engine=str(self.engine), fixture=str(self.fixture),
                                  runner=runner, keep_stage=True)
        self.assertIn("stage_dir", out)
        try:
            self.assertTrue(os.path.exists(out["stage_dir"]))
        finally:
            import shutil
            shutil.rmtree(out["stage_dir"], ignore_errors=True)


class TestBuildLispAndScrText(unittest.TestCase):
    """Regression guard for the exact, live-verified command sequence (see
    report.md for the transcript this was derived from) -- a refactor that
    silently drops AUTOCONSTRAIN or the ssadd pickset would revert to the
    proven-broken GCHORIZONTAL/bare-entity-name selection forms."""

    def test_lisp_uses_autoconstrain_with_ssadd_pickset(self):
        text = probe_dcm._build_lisp_text()
        self.assertIn(f"defun c:{probe_dcm.LISP_DEFUN}", text)
        self.assertIn('(command "_.AUTOCONSTRAIN" ss "")', text)
        self.assertIn("(ssadd ln ss)", text)
        self.assertIn('(command "_.LINE" p1 p2 "")', text)
        # the safety cancel after AUTOCONSTRAIN (flush any leftover prompt state)
        self.assertIn("(command)", text)

    def test_scr_loads_lisp_forward_slashed_and_never_saves(self):
        text = probe_dcm._build_scr_text("C:/tmp/dcm_probe.lsp")
        lines = [ln for ln in text.splitlines() if ln]
        self.assertIn("FILEDIA", lines)
        self.assertIn('(load "C:/tmp/dcm_probe.lsp")', lines)
        self.assertIn(probe_dcm.LISP_DEFUN, lines)
        self.assertIn("QUIT", lines)
        self.assertNotIn("QSAVE", lines)
        self.assertNotIn("SAVE", lines)


if __name__ == "__main__":
    unittest.main(verbosity=2)
