#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for tools/certify_headless_safe.py.

WHY:
  Live template certification is orchestrator-owned and requires AutoCAD.
  These tests prove the certification gate, resume/apply behavior, and exact
  registry serialization strictly offline by stubbing cadctl's live call.

  The AUTHORITATIVE effect signal is the router's handle-based logical IR diff
  (finding 6): whole-file DWG sha always changes because run_template _QSAVEs on
  every save, so a raw-sha delta cannot distinguish a real edit from a no-op.
  The FakeCad below therefore drives `effect_took` through diff_before_after's
  summary, NOT through staged bytes -- and one test proves a byte-changed but
  logically-empty run is NOT certified.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import certify_headless_safe as chs  # noqa: E402


def _minimal_template(tid: str, *, headless_safe: bool = False, summary: str = "테스트"):
    return {
        "template_id": tid,
        "summary": summary,
        "headless_safe": headless_safe,
        "write_mode": {"default": "write_copy", "allowed": ["read", "write_copy"]},
        "command_sequence": [
            {"literal": "AUDIT"},
            {"slot": "fix_answer"},
        ],
        "slots": {
            "fix_answer": {
                "type": "enum",
                "values": ["Y", "N"],
                "default": "Y",
            },
        },
        "postconditions": [],
    }


def _write_json(path: Path, doc) -> None:
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _synthetic_router(root: Path, template: dict) -> tuple[Path, Path]:
    config = root / "config"
    frag_dir = config / "command_templates.d"
    frag_dir.mkdir(parents=True)
    _write_json(config / "command_templates.json", {"templates": []})
    frag_path = frag_dir / f"{template['template_id'].replace('.', '_')}.json"
    _write_json(frag_path, {"templates": [template]})
    return root, frag_path


def _build_cad_env(
    work_root: Path,
    dwg_path: Path,
    *,
    mutate_staged: bool = True,
    stdout_text: str = "completed\n",
    stderr_text: str = "",
    status: str = "ok",
    exit_code=0,
    error_code: str | None = None,
    reason: str | None = None,
    mutate_original: bool = False,
) -> dict:
    before_sha = chs.tls.sha256_file(dwg_path)
    original_bytes = dwg_path.read_bytes()

    staged = work_root / "staged" / "input.dwg"
    staged.parent.mkdir(parents=True, exist_ok=True)
    # mutate_staged models QSAVE's unconditional header rewrite -- the staged bytes
    # change on every save regardless of logical effect. The logical effect is decided
    # by the IR diff (FakeCad.diff_before_after), never by these bytes.
    staged.write_bytes(original_bytes + (b"_STAGED" if mutate_staged else b""))

    if mutate_original:
        dwg_path.write_bytes(original_bytes + b"_ORIGINAL_MUTATED")

    stdout_path = work_root / "stdout.txt"
    stderr_path = work_root / "stderr.txt"
    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")

    after_sha = chs.tls.sha256_file(dwg_path)
    result = {
        "status": status,
        "write_mode": "write_copy",
        "diagnostics": {
            "exit_code": exit_code,
            "stdout_ref": str(stdout_path),
            "stderr_ref": str(stderr_path),
        },
        "details": {
            "staged_input": str(staged),
            "original_input": str(dwg_path),
            "original_sha256_before": before_sha,
            "original_sha256_after": after_sha,
            "original_unchanged": (before_sha == after_sha),
        },
    }
    if error_code or reason:
        result["error"] = {
            "code": error_code or "ERROR",
            "message": reason or "error",
            "retryable": False,
            "details": {},
        }

    env = {
        "schema": "ariadne.cadctl.run_command_template.v1",
        "template_id": "unused",
        "status": status,
        "executed": True,
        "staged_copy": str(staged),
        "original_unchanged": (before_sha == after_sha),
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "result": result,
    }
    if reason:
        env["reason"] = reason
    return env


class _FakeCadBase:
    """Offline stand-in for cadctl.Cad.

    `run_command_template` is overridden per test. `inspect`/`diff_before_after`
    implement the logical-effect probe path: inspect writes a canned IR file and
    diff returns a summary whose (added, removed, modified) counts the subclass
    controls -- that, not the staged bytes, decides effect_took.
    """

    diff_added = 1
    diff_removed = 0
    diff_modified = 0

    def __init__(self, router_home):
        self.router_home = Path(router_home)

    def inspect(self, dwg_path, out_dir, mode="graph", include_rich=False):
        p = Path(out_dir)
        p.mkdir(parents=True, exist_ok=True)
        (p / "dwg_graph_ir.json").write_text(
            json.dumps({"schema": "ariadne.dwg_graph_ir.v1", "src": str(dwg_path)}),
            encoding="utf-8",
        )
        return {"status": "ok"}

    def diff_before_after(self, pre_ir, post_ir):
        added, removed, modified = self.diff_added, self.diff_removed, self.diff_modified
        return {
            "schema": "ariadne.cad_diff.v1",
            "summary": {
                "added": added,
                "removed": removed,
                "modified": modified,
                "entity_count_before": 10,
                "entity_count_after": 10 + added - removed,
            },
        }


class TestCertifyHeadlessSafe(unittest.TestCase):
    """WHY: prove the bounded certification gate and runtime-only registry flips."""

    def _router_and_dwg(self, *, headless_safe: bool = False):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        router, frag_path = _synthetic_router(
            root,
            _minimal_template("tmpl.audit", headless_safe=headless_safe),
        )
        dwg = root / "fixture.dwg"
        dwg.write_bytes(b"DWG_BYTES")
        out_dir = root / "out"
        return tmp, router, frag_path, dwg, out_dir

    def test_certify_happy_path_returns_certified(self):
        """WHY: a real LOGICAL effect (IR diff non-empty) plus exit=0/status=ok/no-attended is the only pass path."""
        tmp, router, _frag_path, dwg, out_dir = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)
        calls: list[dict] = []

        class FakeCad(_FakeCadBase):
            def run_command_template(self, template_id, slots, dwg=None, timeout_sec=None):
                calls.append({"template_id": template_id, "slots": slots, "dwg": dwg})
                return _build_cad_env(self.router_home, Path(dwg), mutate_staged=True)

        with mock.patch.object(chs.cadctl, "Cad", FakeCad):
            envelope = chs.certify(
                "tmpl.audit", dwg, out_dir, 30,
                router_home=router,
            )

        self.assertEqual(calls, [{
            "template_id": "tmpl.audit",
            "slots": {"fix_answer": "Y"},
            "dwg": str(dwg),
        }])
        self.assertEqual(envelope["verdict"], chs.CERTIFIED)
        self.assertEqual(envelope["reason"], chs.REASON_CERTIFIED)
        self.assertTrue(envelope["original_unchanged"])
        self.assertTrue(envelope["effect_took"])
        self.assertEqual(envelope["effect_basis"], "logical_ir_diff")
        self.assertEqual(envelope["effect_diff_summary"]["added"], 1)
        # whole-file staged sha is recorded as evidence only, never as the gate.
        self.assertEqual(envelope["staged_input_sha256"], envelope["original_sha256_before"])
        self.assertNotEqual(envelope["staged_result_sha256"], envelope["staged_input_sha256"])
        self.assertTrue(envelope["staged_whole_file_sha_changed"])
        self.assertTrue(chs.envelope_path(out_dir, "tmpl.audit").is_file())

    def test_certify_original_sha_change_raises_safety_error(self):
        """WHY: any original-byte mutation is a hard-stop safety violation, not an ordinary miss."""
        tmp, router, _frag_path, dwg, out_dir = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)

        class FakeCad(_FakeCadBase):
            def run_command_template(self, template_id, slots, dwg=None, timeout_sec=None):
                return _build_cad_env(
                    self.router_home, Path(dwg),
                    mutate_staged=True,
                    mutate_original=True,
                )

        with mock.patch.object(chs.cadctl, "Cad", FakeCad):
            with self.assertRaises(chs.CertificationSafetyError) as ctx:
                chs.certify("tmpl.audit", dwg, out_dir, 30, router_home=router)

        self.assertEqual(ctx.exception.envelope["reason"], chs.REASON_ORIGINAL_SHA_CHANGED)
        self.assertFalse(ctx.exception.envelope["original_unchanged"])
        # the effect probe is skipped once an original mutation is detected (safety stop).
        self.assertFalse(ctx.exception.envelope["effect_took"])
        self.assertIn("safety stop", (ctx.exception.envelope["effect_note"] or ""))
        self.assertTrue(chs.envelope_path(out_dir, "tmpl.audit").is_file())

    def test_certify_qsave_byte_change_without_logical_effect_is_not_certified(self):
        """WHY (finding 6): QSAVE churns the staged bytes on EVERY save; a byte delta is not
        evidence of effect. A run whose logical IR diff is empty must NOT certify even though
        staged_whole_file_sha_changed is True."""
        tmp, router, _frag_path, dwg, out_dir = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)

        class FakeCad(_FakeCadBase):
            diff_added = 0
            diff_removed = 0
            diff_modified = 0

            def run_command_template(self, template_id, slots, dwg=None, timeout_sec=None):
                # staged bytes DO change (QSAVE), but the logical diff is empty.
                return _build_cad_env(self.router_home, Path(dwg), mutate_staged=True)

        with mock.patch.object(chs.cadctl, "Cad", FakeCad):
            envelope = chs.certify("tmpl.audit", dwg, out_dir, 30, router_home=router)

        self.assertTrue(envelope["staged_whole_file_sha_changed"])  # bytes moved...
        self.assertFalse(envelope["effect_took"])                   # ...but no logical effect
        self.assertEqual(envelope["verdict"], chs.NOT_CERTIFIED)
        self.assertEqual(envelope["reason"], chs.REASON_NO_STAGED_EFFECT)
        self.assertEqual(envelope["effect_basis"], "logical_ir_diff")

    def test_certify_effect_probe_fails_closed_on_dependency_failures(self):
        """WHY (safety-critical): the effect probe MUST fail closed. If inspect/diff fails or
        returns garbage, effect_took must be False (-> NOT_CERTIFIED), never a silent True that
        would certify a no-op or attended template. Covers every failure branch of
        _structural_effect: pre/post inspect not-ok, diff error, diff missing summary, and a
        malformed (non-numeric) summary (finding 3 coercion)."""
        tmp, router, _frag_path, dwg, out_dir = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)

        def _runner(self, template_id, slots, dwg=None, timeout_sec=None):
            return _build_cad_env(self.router_home, Path(dwg), mutate_staged=True)

        class InspectNotOk(_FakeCadBase):
            run_command_template = _runner

            def inspect(self, dwg_path, out_dir, mode="graph", include_rich=False):
                return {"status": "partial"}  # no IR file written -> _produce_ir None

        class DiffError(_FakeCadBase):
            run_command_template = _runner

            def diff_before_after(self, pre_ir, post_ir):
                return {"schema": "ariadne.cad_diff.v1", "status": "error", "reason": "boom"}

        class DiffNoSummary(_FakeCadBase):
            run_command_template = _runner

            def diff_before_after(self, pre_ir, post_ir):
                return {"schema": "ariadne.cad_diff.v1"}  # summary key absent

        class DiffNonNumeric(_FakeCadBase):
            run_command_template = _runner

            def diff_before_after(self, pre_ir, post_ir):
                # summary present but counts are garbage; must coerce to 0, not crash/pass
                return {"schema": "ariadne.cad_diff.v1",
                        "summary": {"added": "NaN", "removed": None, "modified": "x"}}

        for label, Fake in (
            ("inspect_not_ok", InspectNotOk),
            ("diff_error", DiffError),
            ("diff_no_summary", DiffNoSummary),
            ("diff_non_numeric", DiffNonNumeric),
        ):
            with self.subTest(mode=label):
                with mock.patch.object(chs.cadctl, "Cad", Fake):
                    env = chs.certify("tmpl.audit", dwg, out_dir / label, 30, router_home=router)
                self.assertFalse(env["effect_took"], label)
                self.assertEqual(env["verdict"], chs.NOT_CERTIFIED, label)
                self.assertEqual(env["reason"], chs.REASON_NO_STAGED_EFFECT, label)
                self.assertIsNotNone(env["effect_note"], label)

    def test_certify_diagnostic_template_judged_by_stdout_not_ir_diff(self):
        """WHY (cert wave 2 carve-out): a registry-declared diagnostic template (AUDIT/
        RECOVER class) correctly produces a ZERO entity diff on a healthy drawing, so its
        effect is proven by the declared completion line in stdout instead. Fail-closed:
        pattern present -> CERTIFIED even with empty IR diff; pattern absent -> NOT."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        template = _minimal_template("tmpl.diag")
        template["certification"] = {
            "effect_mode": "diagnostic",
            "diagnostic_stdout_pattern": "건의 오류를 찾아서 .*건이 수정됨|Total errors found .* fixed",
        }
        router, _frag = _synthetic_router(root, template)
        dwg = root / "fixture.dwg"
        dwg.write_bytes(b"DWG_BYTES")
        out_dir = root / "out"

        class DiagCad(_FakeCadBase):
            diff_added = 0  # IR diff empty -- must NOT matter for a diagnostic template
            stdout_text = "전체 0건의 오류를 찾아서 0건이 수정됨\n"

            def run_command_template(self, template_id, slots, dwg=None, timeout_sec=None):
                return _build_cad_env(self.router_home, Path(dwg), mutate_staged=True,
                                      stdout_text=type(self).stdout_text)

            def inspect(self, *a, **k):  # diagnostic path must never inspect
                raise AssertionError("diagnostic template must not run the IR probe")

        with mock.patch.object(chs.cadctl, "Cad", DiagCad):
            env = chs.certify("tmpl.diag", dwg, out_dir / "match", 30, router_home=router)
        self.assertEqual(env["verdict"], chs.CERTIFIED)
        self.assertEqual(env["effect_basis"], "diagnostic_stdout")
        self.assertIn("diagnostic output matched", env["effect_note"])

        class DiagCadNoMatch(DiagCad):
            stdout_text = "some unrelated output\n"

        with mock.patch.object(chs.cadctl, "Cad", DiagCadNoMatch):
            env = chs.certify("tmpl.diag", dwg, out_dir / "nomatch", 30, router_home=router)
        self.assertEqual(env["verdict"], chs.NOT_CERTIFIED)
        self.assertEqual(env["reason"], chs.REASON_NO_STAGED_EFFECT)
        self.assertFalse(env["effect_took"])

        # declared diagnostic mode WITHOUT a pattern must fail closed, not pass open
        template_nopat = _minimal_template("tmpl.diag2")
        template_nopat["certification"] = {"effect_mode": "diagnostic"}
        tmp2 = tempfile.TemporaryDirectory()
        self.addCleanup(tmp2.cleanup)
        root2 = Path(tmp2.name)
        router2, _f2 = _synthetic_router(root2, template_nopat)
        dwg2 = root2 / "fixture.dwg"
        dwg2.write_bytes(b"DWG_BYTES")
        with mock.patch.object(chs.cadctl, "Cad", DiagCad):
            env = chs.certify("tmpl.diag2", dwg2, root2 / "out", 30, router_home=router2)
        self.assertEqual(env["verdict"], chs.NOT_CERTIFIED)
        self.assertIn("no diagnostic_stdout_pattern", env["effect_note"])

    def test_certify_attended_marker_on_incomplete_run_is_not_certified(self):
        """WHY: a prompt marker in the tail of a run that FAILED to complete means it died
        at an interactive prompt -- the attended signal (markers on a COMPLETED run are
        echo artifacts; see the completed-run tests below)."""
        tmp, router, _frag_path, dwg, out_dir = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)

        class FakeCad(_FakeCadBase):
            def run_command_template(self, template_id, slots, dwg=None, timeout_sec=None):
                return _build_cad_env(
                    self.router_home, Path(dwg),
                    mutate_staged=True,
                    stdout_text="Specify opposite corner:\n",
                    status="error", exit_code=1,
                    error_code="ROUTE_NONZERO_EXIT", reason="accoreconsole exited 1",
                )

        with mock.patch.object(chs.cadctl, "Cad", FakeCad):
            envelope = chs.certify("tmpl.audit", dwg, out_dir, 30, router_home=router)

        self.assertEqual(envelope["verdict"], chs.NOT_CERTIFIED)
        self.assertEqual(envelope["reason"], chs.REASON_ATTENDED_MARKERS)
        self.assertIn("Specify", envelope["attended_markers"])

    def test_certify_broadened_attended_markers_catch_prompt_variants(self):
        """WHY (finding 4): the earlier marker set missed real accoreconsole prompts. Prove the
        broadened patterns catch a plural 'Select objects to array:' and a default-bracket
        'Continue? <Y>:' on an INCOMPLETE run -- both must block certification."""
        tmp, router, _frag_path, dwg, out_dir = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)

        for prompt, expect_label in (
            ("Select objects to array:\n", "Select object(s)"),
            ("Continue? <Y>:\n", "default-bracket prompt"),
        ):
            with self.subTest(prompt=prompt):
                class FakeCad(_FakeCadBase):
                    def run_command_template(self, template_id, slots, dwg=None, timeout_sec=None):
                        return _build_cad_env(
                            self.router_home, Path(dwg),
                            mutate_staged=True, stdout_text=prompt,
                            status="error", exit_code=1,
                            error_code="ROUTE_NONZERO_EXIT", reason="accoreconsole exited 1",
                        )

                with mock.patch.object(chs.cadctl, "Cad", FakeCad):
                    envelope = chs.certify(
                        "tmpl.audit", dwg, out_dir / expect_label.replace(" ", "_"),
                        30, router_home=router,
                    )
                self.assertEqual(envelope["verdict"], chs.NOT_CERTIFIED)
                self.assertEqual(envelope["reason"], chs.REASON_ATTENDED_MARKERS)
                self.assertIn(expect_label, envelope["attended_markers"])

    def test_certify_stderr_utf16_marker_is_detected(self):
        """WHY (finding 4b): accoreconsole writes UTF-16LE. A marker that lands on stderr must be
        decoded with the UTF-16 reader, not plain UTF-8, or it is silently missed."""
        tmp, router, _frag_path, dwg, out_dir = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)

        class FakeCad(_FakeCadBase):
            def run_command_template(self, template_id, slots, dwg=None, timeout_sec=None):
                env = _build_cad_env(
                    self.router_home, Path(dwg), mutate_staged=True,
                    status="error", exit_code=1,
                    error_code="ROUTE_NONZERO_EXIT", reason="accoreconsole exited 1",
                )
                # overwrite stderr with UTF-16LE bytes carrying a prompt marker
                Path(env["stderr"]).write_bytes("Enter selection:\n".encode("utf-16-le"))
                return env

        with mock.patch.object(chs.cadctl, "Cad", FakeCad):
            envelope = chs.certify("tmpl.audit", dwg, out_dir, 30, router_home=router)

        self.assertEqual(envelope["verdict"], chs.NOT_CERTIFIED)
        self.assertEqual(envelope["reason"], chs.REASON_ATTENDED_MARKERS)
        self.assertIn("Enter", envelope["attended_markers"])

    def test_certify_completed_run_ignores_echoed_prompt_markers(self):
        """WHY (cert wave 2, measured): CMDECHO=1 echoes every prompt the script ANSWERED,
        so a marker in a COMPLETED (exit 0) run's tail is an echo artifact. -OVERKILL
        completed with a real dedup effect yet its echoed option prompt matched the
        default-bracket pattern -- that run must CERTIFY (markers stay recorded), and a
        completed no-effect run must fall to NO_STAGED_EFFECT, not ATTENDED."""
        tmp, router, _frag_path, dwg, out_dir = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)
        # the echoed prompt that was ANSWERED WITH A BLANK line ends in the bare
        # colon (exactly the live -OVERKILL tail shape that matched the pattern)
        echoed = "변경할 옵션 입력 [종료(D)/공차(O)] <종료>:\ncompleted\n"

        class EchoEffect(_FakeCadBase):  # completed + real effect + echoed prompt
            def run_command_template(self, template_id, slots, dwg=None, timeout_sec=None):
                return _build_cad_env(self.router_home, Path(dwg),
                                      mutate_staged=True, stdout_text=echoed)

        class EchoNoEffect(EchoEffect):  # completed + NO effect + echoed prompt
            diff_added = 0

        with mock.patch.object(chs.cadctl, "Cad", EchoEffect):
            env = chs.certify("tmpl.audit", dwg, out_dir / "effect", 30, router_home=router)
        self.assertEqual(env["verdict"], chs.CERTIFIED)
        self.assertIn("default-bracket prompt", env["attended_markers"])  # recorded, not fatal

        with mock.patch.object(chs.cadctl, "Cad", EchoNoEffect):
            env = chs.certify("tmpl.audit", dwg, out_dir / "noeffect", 30, router_home=router)
        self.assertEqual(env["verdict"], chs.NOT_CERTIFIED)
        self.assertEqual(env["reason"], chs.REASON_NO_STAGED_EFFECT)

    def test_certify_crash_is_not_certified(self):
        """WHY: non-ok / nonzero execution must stay a failure even if the staged copy changed."""
        tmp, router, _frag_path, dwg, out_dir = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)

        class FakeCad(_FakeCadBase):
            def run_command_template(self, template_id, slots, dwg=None, timeout_sec=None):
                return _build_cad_env(
                    self.router_home, Path(dwg),
                    mutate_staged=True,
                    status="error",
                    exit_code=7,
                    error_code="ROUTE_NONZERO_EXIT",
                    reason="accoreconsole exited 7",
                )

        with mock.patch.object(chs.cadctl, "Cad", FakeCad):
            envelope = chs.certify("tmpl.audit", dwg, out_dir, 30, router_home=router)

        self.assertEqual(envelope["verdict"], chs.NOT_CERTIFIED)
        self.assertEqual(envelope["reason"], chs.REASON_CRASH)

    def test_certify_timeout_is_not_certified(self):
        """WHY: a timeout is attended-suspect and must be distinguished from an ordinary crash."""
        tmp, router, _frag_path, dwg, out_dir = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)

        class FakeCad(_FakeCadBase):
            def run_command_template(self, template_id, slots, dwg=None, timeout_sec=None):
                return _build_cad_env(
                    self.router_home, Path(dwg),
                    mutate_staged=False,
                    status="error",
                    exit_code=None,
                    error_code="ACCORECONSOLE_TIMEOUT",
                    reason="accoreconsole did not exit within 30s",
                )

        with mock.patch.object(chs.cadctl, "Cad", FakeCad):
            envelope = chs.certify("tmpl.audit", dwg, out_dir, 30, router_home=router)

        self.assertEqual(envelope["verdict"], chs.NOT_CERTIFIED)
        self.assertEqual(envelope["reason"], chs.REASON_TIMEOUT)

    def test_certify_forwards_timeout_to_engine(self):
        """WHY (finding 5): the wall-clock budget must reach the engine's accoreconsole timeout,
        not be a dead parameter enforced only at the fixed 120s default."""
        tmp, router, _frag_path, dwg, out_dir = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)
        seen: list = []

        class FakeCad(_FakeCadBase):
            def run_command_template(self, template_id, slots, dwg=None, timeout_sec=None):
                seen.append(timeout_sec)
                return _build_cad_env(self.router_home, Path(dwg), mutate_staged=True)

        with mock.patch.object(chs.cadctl, "Cad", FakeCad):
            chs.certify("tmpl.audit", dwg, out_dir, 47, router_home=router)

        self.assertEqual(seen, [47])

    def test_apply_flips_headless_safe_only_for_certified_and_matches_serialization_style(self):
        """WHY: runtime apply is the only registry-changing path, and it must serialize exactly like merge_fragments."""
        tmp, router, frag_path, dwg, out_dir = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)

        class FakeCad(_FakeCadBase):
            def run_command_template(self, template_id, slots, dwg=None, timeout_sec=None):
                return _build_cad_env(self.router_home, Path(dwg), mutate_staged=True)

        with mock.patch.object(chs.cadctl, "Cad", FakeCad):
            envelopes, exit_code = chs.run_batch(
                ["tmpl.audit"],
                dwg_path=dwg,
                out_dir=out_dir,
                timeout_sec=30,
                apply=True,
                router_home=router,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(envelopes[0]["verdict"], chs.CERTIFIED)

        expected_doc = {
            "templates": [
                _minimal_template("tmpl.audit", headless_safe=True)
            ]
        }
        expected_doc["templates"][0]["evidence_refs"] = [
            chs._repo_relative_ref(router, chs.envelope_path(out_dir, "tmpl.audit"))
        ]
        expected_text = json.dumps(expected_doc, indent=2, ensure_ascii=False) + "\n"
        expected_bytes = expected_text.replace("\n", os.linesep).encode("utf-8")
        self.assertEqual(frag_path.read_bytes(), expected_bytes)

    def test_apply_refuses_not_certified_and_never_writes_true(self):
        """WHY: a failed certification must never flip the registry bit or add fake evidence."""
        tmp, router, frag_path, dwg, out_dir = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)

        class FakeCad(_FakeCadBase):
            diff_added = 0  # empty logical diff -> NOT_CERTIFIED even with byte churn

            def run_command_template(self, template_id, slots, dwg=None, timeout_sec=None):
                return _build_cad_env(self.router_home, Path(dwg), mutate_staged=True)

        with mock.patch.object(chs.cadctl, "Cad", FakeCad):
            envelopes, exit_code = chs.run_batch(
                ["tmpl.audit"],
                dwg_path=dwg,
                out_dir=out_dir,
                timeout_sec=30,
                apply=True,
                router_home=router,
            )

        self.assertEqual(exit_code, 1)
        self.assertEqual(envelopes[0]["verdict"], chs.NOT_CERTIFIED)
        doc = json.loads(frag_path.read_text(encoding="utf-8-sig"))
        self.assertFalse(doc["templates"][0]["headless_safe"])
        self.assertNotIn("evidence_refs", doc["templates"][0])

    def test_apply_preserves_compact_fragment_style(self):
        """WHY: apply_certification edits a hand-authored compact fragment IN PLACE so a
        --apply flip is a minimal diff, not a whole-file array reflow. Assert the compact
        single-line arrays survive byte-for-byte while headless_safe flips and the
        evidence_ref is appended (regression for the pre-push reformatting finding)."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        frag_dir = root / "config" / "command_templates.d"
        frag_dir.mkdir(parents=True)
        _write_json(root / "config" / "command_templates.json", {"templates": []})
        frag = frag_dir / "define_arrayrect.json"
        compact = (
            '{\n'
            '  "templates": [\n'
            '    {\n'
            '      "template_id": "define.arrayrect",\n'
            '      "headless_safe": false,\n'
            '      "write_mode": {\n'
            '        "default": "write_copy",\n'
            '        "allowed": ["read", "write_copy"]\n'
            '      },\n'
            '      "command_sequence": [\n'
            '        { "literal": "ARRAYRECT" },\n'
            '        { "literal": "L" }\n'
            '      ],\n'
            '      "evidence_refs": [\n'
            '        "docs/GOVERNED_COMMAND_TEMPLATES.md#5-live-verification"\n'
            '      ]\n'
            '    }\n'
            '  ]\n'
            '}\n'
        )
        frag.write_text(compact, encoding="utf-8")

        envelope = {
            "verdict": chs.CERTIFIED,
            "evidence_paths": {
                "envelope": str(root / "out" / "define_arrayrect.certification.json")},
        }
        changed = chs.apply_certification("define.arrayrect", envelope, router_home=root)
        self.assertTrue(changed)

        out = frag.read_text(encoding="utf-8")
        # the two intended changes only
        self.assertIn('"headless_safe": true', out)
        self.assertNotIn('"headless_safe": false', out)
        # compact hand-authored style preserved byte-for-byte
        self.assertIn('"allowed": ["read", "write_copy"]', out)
        self.assertIn('{ "literal": "ARRAYRECT" }', out)
        self.assertIn('{ "literal": "L" }', out)
        # command_sequence was NOT reflowed to expanded multi-line objects
        self.assertNotIn('"literal": "ARRAYRECT"\n', out.replace('{ "literal": "ARRAYRECT" }', ''))
        # structure is valid JSON with the flip + appended ref
        doc = json.loads(out)
        t = doc["templates"][0]
        self.assertTrue(t["headless_safe"])
        self.assertEqual(len(t["evidence_refs"]), 2)
        self.assertEqual(t["evidence_refs"][-1], "out/define_arrayrect.certification.json")
        # apply is idempotent (already-safe + already-ref -> no-op)
        self.assertFalse(chs.apply_certification("define.arrayrect", envelope, router_home=root))

    def test_apply_refused_when_resumed_envelope_fixture_sha_mismatches(self):
        """WHY (safety, no-fake-CERTIFIED): --apply must not flip the registry from a resumed
        envelope whose recorded fixture sha does not match the current --dwg (stale / other-
        fixture / hand-tampered verdict). The flip is refused; the bit stays false."""
        tmp, router, frag_path, dwg, out_dir = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)
        out_dir.mkdir(parents=True, exist_ok=True)
        env = {
            "schema": chs.ENVELOPE_SCHEMA,
            "template_id": "tmpl.audit",
            "verdict": chs.CERTIFIED,
            "reason": chs.REASON_CERTIFIED,
            "original_sha256_before": "0" * 64,  # does NOT match dwg -> untrusted
            "evidence_paths": {"envelope": "prebuilt"},
        }
        chs.envelope_path(out_dir, "tmpl.audit").write_text(
            json.dumps(env, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        class FakeCad(_FakeCadBase):
            def run_command_template(self, *a, **k):
                raise AssertionError("resume path must not execute cadctl")

        with mock.patch.object(chs.cadctl, "Cad", FakeCad):
            envelopes, exit_code = chs.run_batch(
                ["tmpl.audit"], dwg_path=dwg, out_dir=out_dir,
                timeout_sec=30, apply=True, router_home=router)

        self.assertGreaterEqual(exit_code, 1)
        self.assertIn("apply_refused_reason", envelopes[0])
        doc = json.loads(frag_path.read_text(encoding="utf-8-sig"))
        self.assertFalse(doc["templates"][0]["headless_safe"])
        self.assertNotIn("evidence_refs", doc["templates"][0])

    def test_apply_trust_check_matches_and_rejects(self):
        """Unit: _apply_trust_check passes only on schema + template_id + fixture-sha match,
        and -- when the current template is supplied -- on a matching content fingerprint."""
        tmp, router, _frag, dwg, _out = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)
        template = chs._load_template_registry(router)["tmpl.audit"]
        good = {
            "schema": chs.ENVELOPE_SCHEMA,
            "template_id": "tmpl.audit",
            "original_sha256_before": chs.tls.sha256_file(dwg),
            "template_fingerprint": chs._template_fingerprint(template),
        }
        self.assertTrue(chs._apply_trust_check(good, "tmpl.audit", dwg)[0])
        self.assertFalse(chs._apply_trust_check({**good, "schema": "x"}, "tmpl.audit", dwg)[0])
        self.assertFalse(chs._apply_trust_check(good, "other.id", dwg)[0])
        self.assertFalse(
            chs._apply_trust_check({**good, "original_sha256_before": "0" * 64}, "tmpl.audit", dwg)[0])
        # content binding (adversarial-audit class fix): a fingerprint that does not
        # match the CURRENT registry template refuses the flip...
        ok, reason = chs._apply_trust_check(
            {**good, "template_fingerprint": "f" * 64}, "tmpl.audit", dwg, template=template)
        self.assertFalse(ok)
        self.assertIn("drifted", reason)
        # ...a fingerprint-less legacy envelope refuses fail-closed...
        legacy = dict(good)
        legacy.pop("template_fingerprint")
        ok, reason = chs._apply_trust_check(legacy, "tmpl.audit", dwg, template=template)
        self.assertFalse(ok)
        self.assertIn("re-certify", reason)
        # ...and the true current fingerprint passes.
        self.assertTrue(chs._apply_trust_check(good, "tmpl.audit", dwg, template=template)[0])

    def test_apply_refused_when_template_edited_after_certification(self):
        """WHY (adversarial-audit general-class fix): certify, then EDIT the template's
        command_sequence, then --apply from the stale envelope -- the flip must be refused
        (the envelope proves the OLD sequence, not the one that would run in production)."""
        tmp, router, frag_path, dwg, out_dir = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)

        class FakeCad(_FakeCadBase):
            def run_command_template(self, template_id, slots, dwg=None, timeout_sec=None):
                return _build_cad_env(self.router_home, Path(dwg), mutate_staged=True)

        with mock.patch.object(chs.cadctl, "Cad", FakeCad):
            envelope = chs.certify("tmpl.audit", dwg, out_dir, 30, router_home=router)
        self.assertEqual(envelope["verdict"], chs.CERTIFIED)
        self.assertTrue(envelope.get("template_fingerprint"))

        # post-certification template edit (append a step to command_sequence)
        doc = json.loads(frag_path.read_text(encoding="utf-8-sig"))
        doc["templates"][0]["command_sequence"].append({"literal": "EXTRA"})
        frag_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")

        with mock.patch.object(chs.cadctl, "Cad", FakeCad):
            envelopes, exit_code = chs.run_batch(
                ["tmpl.audit"], dwg_path=dwg, out_dir=out_dir,
                timeout_sec=30, apply=True, router_home=router)  # resume: no CAD

        self.assertGreaterEqual(exit_code, 1)
        self.assertIn("drifted", envelopes[0].get("apply_refused_reason", ""))
        doc = json.loads(frag_path.read_text(encoding="utf-8-sig"))
        self.assertFalse(doc["templates"][0]["headless_safe"])

    def test_resume_skip_reuses_existing_envelope_without_invoking_cad(self):
        """WHY: certification is resumable; an existing envelope is the source of truth unless --force reruns it."""
        tmp, router, _frag_path, dwg, out_dir = self._router_and_dwg()
        self.addCleanup(tmp.cleanup)
        out_dir.mkdir(parents=True, exist_ok=True)

        existing = {
            "schema": chs.ENVELOPE_SCHEMA,
            "template_id": "tmpl.audit",
            "verdict": chs.CERTIFIED,
            "reason": chs.REASON_CERTIFIED,
            "exit_code": 0,
            "original_sha256_before": chs.tls.sha256_file(dwg),
            "original_sha256_after": chs.tls.sha256_file(dwg),
            "original_unchanged": True,
            "staged_input_sha256": chs.tls.sha256_file(dwg),
            "staged_result_sha256": "deadbeef",
            "effect_took": True,
            "attended_markers": [],
            "elapsed_sec": 0.1,
            "timeout_sec": 30,
            "evidence_paths": {"envelope": "prebuilt"},
        }
        chs.envelope_path(out_dir, "tmpl.audit").write_text(
            json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        touched: list[str] = []

        class FakeCad(_FakeCadBase):
            def run_command_template(self, template_id, slots, dwg=None, timeout_sec=None):
                touched.append("run:" + template_id)
                raise AssertionError("resume path must not execute cadctl")

            def inspect(self, dwg_path, out_dir, mode="graph", include_rich=False):
                touched.append("inspect")
                raise AssertionError("full resume must not inspect (no baseline IR needed)")

        with mock.patch.object(chs.cadctl, "Cad", FakeCad):
            envelopes, exit_code = chs.run_batch(
                ["tmpl.audit"],
                dwg_path=dwg,
                out_dir=out_dir,
                timeout_sec=30,
                router_home=router,
            )

        self.assertEqual(touched, [])
        self.assertEqual(exit_code, 0)
        self.assertEqual(envelopes[0]["verdict"], chs.CERTIFIED)


if __name__ == "__main__":
    unittest.main()
