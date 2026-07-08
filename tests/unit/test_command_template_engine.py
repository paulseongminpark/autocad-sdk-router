"""Lane W5-TMPL -- governed command template engine tests.

WIRING/VALIDATION (always run, no accoreconsole needed): registry load +
write-mode-enum guard, slot validation (enum/int_range/float_range/name_token/
staged_path), the universal hostile-character injection gate, render_script
determinism + undeclared/unknown-arg rejection, and evaluate_postconditions()
as a pure function against synthetic stdout/counts.

LIVE (env-gated): a real AUDIT + PURGE run against the golden fixture needs
accoreconsole. Runs ONLY when CADOS_LIVE=1 (explicit opt-in) AND accoreconsole
is present AND the fixture exists; otherwise SKIPS with an explicit reason
(same convention as tests/smoke/test_router_inspect_database_graph.py). The
original fixture's sha256 is asserted unchanged regardless of outcome.
"""
import json
import os
import sys
import unittest
from pathlib import Path
from shutil import which

_THIS_DIR = Path(__file__).resolve().parent
ROUTER_HOME = _THIS_DIR.parents[1]
TOOLS_DIR = ROUTER_HOME / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import command_template_engine as cte  # noqa: E402

_FIXTURE = ROUTER_HOME / "tests" / "fixtures" / "native_sample.dwg"
_FIXTURE_SHA256 = "eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76"


def _accoreconsole_present():
    return cte.resolve_engine() is not None


def _live_enabled():
    return (os.environ.get("CADOS_LIVE") == "1"
            and _accoreconsole_present()
            and _FIXTURE.is_file())


# --------------------------------------------------------------------------- #
# Registry load
# --------------------------------------------------------------------------- #
class TestLoadTemplates(unittest.TestCase):
    def test_real_registry_loads_and_has_both_templates(self):
        templates = cte.load_templates()
        self.assertIn("maintenance.drawing.audit", templates)
        self.assertIn("maintenance.drawing.purge", templates)

    def test_rejects_write_original_in_allowed_list(self, tmp_path=None):
        import tempfile
        bad = {
            "schema": "ariadne.governed_command_templates.v1",
            "templates": [{
                "template_id": "evil.template",
                "write_mode": {"default": "write_original", "allowed": ["write_original"]},
                "command_sequence": [{"literal": "QUIT"}],
                "slots": {},
            }],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(bad, fh)
            path = fh.name
        try:
            with self.assertRaises(cte.TemplateError) as ctx:
                cte.load_templates(path)
            self.assertEqual(ctx.exception.code, "INVALID_TEMPLATE_REGISTRY")
        finally:
            os.unlink(path)

    def test_real_registry_templates_never_allow_write_original(self):
        templates = cte.load_templates()
        for tid, t in templates.items():
            allowed = t.get("write_mode", {}).get("allowed", [])
            self.assertNotIn("write_original", allowed, f"{tid} must never allow write_original")


# --------------------------------------------------------------------------- #
# Injection guard + slot validation
# --------------------------------------------------------------------------- #
class TestInjectionRejection(unittest.TestCase):
    """Hostile values that must NEVER reach a rendered .scr line, across every
    declared slot type. This is the literal test of "no free-text slot ever
    reaches the command line." """

    HOSTILE_VALUES = [
        "Y; QUIT",
        'Y"',
        "Y'",
        "Y(command)",
        "Y\n",
        "Y\x00",
        "Y\x7f",
        "A;B",
        "layer(1)",
    ]

    def test_enum_slot_rejects_every_hostile_value(self):
        slot_def = {"type": "enum", "values": ["Y", "N", "Y; QUIT", 'Y"', "Y'",
                                                 "Y(command)", "Y\n", "Y\x00", "Y\x7f"]}
        # even if a hostile string were (hypothetically) whitelisted as an
        # enum member, the universal gate must still reject it first.
        for hostile in self.HOSTILE_VALUES:
            with self.assertRaises(cte.TemplateError) as ctx:
                cte._validate_slot_value(slot_def, "fix_answer", hostile)
            self.assertEqual(ctx.exception.code, "INJECTION_REJECTED", msg=repr(hostile))

    def test_name_token_slot_rejects_hostile_and_path_like_values(self):
        slot_def = {"type": "name_token"}
        for hostile in self.HOSTILE_VALUES + ["../etc/passwd", "a/b", "a\\b", "a b"]:
            with self.assertRaises(cte.TemplateError):
                cte._validate_slot_value(slot_def, "layer_name", hostile)

    def test_name_token_accepts_safe_values(self):
        slot_def = {"type": "name_token"}
        for ok in ["MyLayer", "Layer_01", "A-B-C", "x"]:
            self.assertEqual(cte._validate_slot_value(slot_def, "layer_name", ok), ok)

    def test_int_range_rejects_out_of_range_and_non_numeric(self):
        slot_def = {"type": "int_range", "min": 1, "max": 255}
        with self.assertRaises(cte.TemplateError):
            cte._validate_slot_value(slot_def, "color_index", 0)
        with self.assertRaises(cte.TemplateError):
            cte._validate_slot_value(slot_def, "color_index", 256)
        with self.assertRaises(cte.TemplateError):
            cte._validate_slot_value(slot_def, "color_index", "not_a_number")
        self.assertEqual(cte._validate_slot_value(slot_def, "color_index", 128), "128")

    def test_point2_accepts_pair_and_rejects_malformed(self):
        """point2 renders ONE 'x,y' token (AutoCAD point prompts consume a single
        comma-joined line -- the ARRAYPOLAR wave-1 mis-landing root cause)."""
        slot_def = {"type": "point2", "min": -1000, "max": 1000}
        self.assertEqual(cte._validate_slot_value(slot_def, "center_point", "0,0"), "0.0,0.0")
        self.assertEqual(cte._validate_slot_value(slot_def, "center_point", "1.5,-2"), "1.5,-2.0")
        for bad in ["0", "0,0,0", "a,b", "1,", ",1", "1;2"]:
            with self.assertRaises(cte.TemplateError, msg=repr(bad)):
                cte._validate_slot_value(slot_def, "center_point", bad)
        with self.assertRaises(cte.TemplateError):  # out of range component
            cte._validate_slot_value(slot_def, "center_point", "0,1001")
        for hostile in self.HOSTILE_VALUES:
            with self.assertRaises(cte.TemplateError, msg=repr(hostile)):
                cte._validate_slot_value(slot_def, "center_point", hostile)

    def test_staged_path_rejects_escape_outside_staging_root(self):
        slot_def = {"type": "staged_path"}
        with self.assertRaises(cte.TemplateError) as ctx:
            cte._validate_slot_value(slot_def, "some_path", str(ROUTER_HOME / "config" / "operations.v2.json"))
        self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")

    def test_staged_path_accepts_a_path_inside_staging(self):
        slot_def = {"type": "staged_path"}
        inside = cte.STAGING_DIR / "some_run" / "input.dwg"
        result = cte._validate_slot_value(slot_def, "some_path", str(inside))
        self.assertTrue(result.startswith(str(cte.STAGING_DIR.resolve()).replace("\\", "/")))

    def test_enum_value_not_in_declared_values_is_validation_error_not_injection(self):
        slot_def = {"type": "enum", "values": ["Y", "N"]}
        with self.assertRaises(cte.TemplateError) as ctx:
            cte._validate_slot_value(slot_def, "fix_answer", "MAYBE")
        self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")


# --------------------------------------------------------------------------- #
# render_script determinism + arg surface
# --------------------------------------------------------------------------- #
class TestRenderScript(unittest.TestCase):
    def setUp(self):
        self.template = {
            "command_sequence": [
                {"literal": "AUDIT"},
                {"slot": "fix_answer"},
            ],
            "slots": {
                "fix_answer": {"type": "enum", "values": ["Y"], "default": "Y"},
            },
        }

    def test_render_is_deterministic(self):
        tokens1 = cte.render_script(self.template, {"fix_answer": "Y"})
        tokens2 = cte.render_script(self.template, {"fix_answer": "Y"})
        self.assertEqual(tokens1, tokens2)
        self.assertEqual(tokens1, ["AUDIT", "Y"])

    def test_missing_required_slot_without_default_is_missing_arg(self):
        template = {
            "command_sequence": [{"slot": "no_default"}],
            "slots": {"no_default": {"type": "enum", "values": ["A"]}},
        }
        with self.assertRaises(cte.TemplateError) as ctx:
            cte.render_script(template, {})
        self.assertEqual(ctx.exception.code, "MISSING_ARG")

    def test_default_is_used_when_arg_omitted(self):
        tokens = cte.render_script(self.template, {})
        self.assertEqual(tokens, ["AUDIT", "Y"])

    def test_undeclared_slot_in_command_sequence_is_registry_error(self):
        template = {
            "command_sequence": [{"slot": "ghost"}],
            "slots": {},
        }
        with self.assertRaises(cte.TemplateError) as ctx:
            cte.render_script(template, {"ghost": "X"})
        self.assertEqual(ctx.exception.code, "INVALID_TEMPLATE_REGISTRY")

    def test_extra_unknown_arg_is_rejected_no_smuggled_lines(self):
        with self.assertRaises(cte.TemplateError) as ctx:
            cte.render_script(self.template, {"fix_answer": "Y", "extra_command": "SAVE"})
        self.assertEqual(ctx.exception.code, "UNKNOWN_ARG")

    def test_purge_template_tokens_are_all_fixed_literals(self):
        templates = cte.load_templates()
        purge = templates["maintenance.drawing.purge"]
        tokens = cte.render_script(purge, {})
        self.assertEqual(tokens, ["-PURGE", "A", "*", "N"])
        # every step in this template is a literal -- no agent-controllable
        # slot exists for the "verify each" hazard prompt.
        self.assertTrue(all("literal" in step for step in purge["command_sequence"]))


# --------------------------------------------------------------------------- #
# evaluate_postconditions -- pure function, synthetic evidence
# --------------------------------------------------------------------------- #
class TestEvaluatePostconditions(unittest.TestCase):
    def test_regex_capture_required_and_matched(self):
        pcs = [{"kind": "regex_capture", "pattern": r"(\d+) errors", "bind": ["n"], "required": True}]
        ok, results = cte.evaluate_postconditions(pcs, "3 errors found", None, None)
        self.assertTrue(ok)
        self.assertTrue(results[0]["matched"])
        self.assertEqual(results[0]["values"]["n"], "3")

    def test_regex_capture_required_and_not_matched_fails(self):
        pcs = [{"kind": "regex_capture", "pattern": r"NEVER_PRESENT", "bind": [], "required": True}]
        ok, results = cte.evaluate_postconditions(pcs, "some unrelated text", None, None)
        self.assertFalse(ok)
        self.assertFalse(results[0]["matched"])

    def test_regex_capture_optional_and_not_matched_still_ok(self):
        pcs = [{"kind": "regex_capture", "pattern": r"NEVER_PRESENT", "bind": [], "required": False}]
        ok, results = cte.evaluate_postconditions(pcs, "some unrelated text", None, None)
        self.assertTrue(ok)

    def test_entity_count_probe_expect_unchanged_true(self):
        pcs = [{"kind": "entity_count_probe", "expect_unchanged": True}]
        ok, results = cte.evaluate_postconditions(pcs, "", 21747, 21747)
        self.assertTrue(ok)
        self.assertTrue(results[0]["unchanged"])

    def test_entity_count_probe_expect_unchanged_false_fails(self):
        pcs = [{"kind": "entity_count_probe", "expect_unchanged": True}]
        ok, results = cte.evaluate_postconditions(pcs, "", 21747, 21748)
        self.assertFalse(ok)
        self.assertFalse(results[0]["unchanged"])

    def test_entity_count_probe_baseline_within_tolerance(self):
        pcs = [{"kind": "entity_count_probe", "expect_baseline": 21747, "tolerance": 0}]
        ok, results = cte.evaluate_postconditions(pcs, "", None, 21747)
        self.assertTrue(ok)
        self.assertTrue(results[0]["within_tolerance"])

    def test_entity_count_probe_baseline_outside_tolerance_fails(self):
        pcs = [{"kind": "entity_count_probe", "expect_baseline": 21747, "tolerance": 0}]
        ok, results = cte.evaluate_postconditions(pcs, "", None, 21750)
        self.assertFalse(ok)

    def test_unknown_postcondition_kind_fails_loud(self):
        pcs = [{"kind": "nonsense_kind"}]
        ok, results = cte.evaluate_postconditions(pcs, "", None, None)
        self.assertFalse(ok)
        self.assertFalse(results[0]["checked"])

    def test_real_audit_template_postconditions_against_synthetic_korean_stdout(self):
        """Uses the REAL registry entry's pattern (not a synthetic one) so a
        future edit to config/command_templates.json that breaks the regex
        is caught here without needing accoreconsole."""
        templates = cte.load_templates()
        audit = templates["maintenance.drawing.audit"]
        synthetic_stdout = "머리말 감사 중\n전체 0건의 오류를 찾아서 0건이 수정됨\n0개 객체가 지워짐\n"
        ok, results = cte.evaluate_postconditions(audit["postconditions"], synthetic_stdout, 21747, 21747)
        self.assertTrue(ok)
        regex_result = next(r for r in results if r["kind"] == "regex_capture")
        self.assertEqual(regex_result["values"], {"errors_found": "0", "errors_fixed": "0"})


# --------------------------------------------------------------------------- #
# run_template gate behavior (no accoreconsole needed -- these all short-
# circuit before staging/execution)
# --------------------------------------------------------------------------- #
class TestRunTemplateGates(unittest.TestCase):
    def test_unknown_template_id_is_blocked(self):
        env = cte.run_template("no.such.template", {}, str(_FIXTURE))
        self.assertEqual(env["status"], "blocked")
        self.assertEqual(env["error"]["code"], "TEMPLATE_NOT_FOUND")

    def test_write_mode_not_allowed_is_blocked(self):
        env = cte.run_template("maintenance.drawing.audit", {}, str(_FIXTURE),
                                write_mode="live_edit")
        self.assertEqual(env["status"], "blocked")
        self.assertEqual(env["error"]["code"], "WRITE_MODE_NOT_ALLOWED")

    def test_missing_input_dwg_is_blocked(self):
        env = cte.run_template("maintenance.drawing.audit", {}, "no/such/file.dwg")
        self.assertEqual(env["status"], "blocked")
        self.assertEqual(env["error"]["code"], "PRECONDITION_FAILED")

    def test_hostile_slot_value_is_blocked_before_any_execution(self):
        env = cte.run_template("maintenance.drawing.audit", {"fix_answer": "Y; QUIT"}, str(_FIXTURE))
        self.assertEqual(env["status"], "blocked")
        self.assertEqual(env["error"]["code"], "INJECTION_REJECTED")

    def test_fix_answer_n_is_a_valid_enum_value(self):
        """fix_answer='N' was ORIGINALLY found to hang accoreconsole on exit
        (4/4 trials); root-caused to a general accoreconsole exit hang
        whenever the staged DB has unsaved changes, and fixed by an
        unconditional _QSAVE before QUIT (docs/GOVERNED_COMMAND_TEMPLATES.md
        section 5). This just asserts 'N' passes validation (no accoreconsole
        needed) -- the actual hang-is-fixed claim is the CADOS_LIVE-gated
        TestAuditTemplateLive.test_audit_fix_n_no_longer_hangs below."""
        templates = cte.load_templates()
        audit = templates["maintenance.drawing.audit"]
        self.assertIn("N", audit["slots"]["fix_answer"]["values"])
        tokens = cte.render_script(audit, {"fix_answer": "N"})
        self.assertEqual(tokens, ["AUDIT", "N"])

    def test_scr_always_qsaves_staged_copy_regardless_of_write_mode(self):
        """The .scr must always contain _QSAVE before QUIT, even for
        write_mode='read' -- this is what fixes the accoreconsole exit hang
        (the staged copy is disposable either way; write_mode's CONTRACT with
        the caller -- original untouched, no persistence guaranteed -- is
        unaffected). Regression guard: if a future edit reintroduces the old
        'only QSAVE for write_copy' conditional, this test fails loudly."""
        import inspect
        src = inspect.getsource(cte.run_template)
        self.assertIn('scr_lines.append("_QSAVE")', src)
        self.assertNotIn('if write_mode == "write_copy":\n        scr_lines.append("_QSAVE")', src)


# --------------------------------------------------------------------------- #
# LIVE certs -- real accoreconsole, gated
# --------------------------------------------------------------------------- #
@unittest.skipUnless(_live_enabled(), "CADOS_LIVE!=1 or accoreconsole/fixture missing")
class TestAuditTemplateLive(unittest.TestCase):
    def test_audit_ok_and_original_unchanged(self):
        sha_before = cte.sha256_file(_FIXTURE)
        self.assertEqual(sha_before, _FIXTURE_SHA256, "fixture sha256 drifted -- check fixture provenance")
        env = cte.run_template("maintenance.drawing.audit", {}, str(_FIXTURE),
                                write_mode="write_copy", timeout_sec=90)
        self.assertEqual(cte.sha256_file(_FIXTURE), _FIXTURE_SHA256, "original mutated by a template run")
        self.assertEqual(env["status"], "ok", msg=json.dumps(env, ensure_ascii=False)[:2000])
        pcs = {p["kind"]: p for p in env["result"]["postconditions"]}
        self.assertTrue(pcs["regex_capture"]["matched"])
        self.assertEqual(pcs["entity_count_probe"]["before"], pcs["entity_count_probe"]["after"])

    def test_audit_fix_n_no_longer_hangs(self):
        """The actual hang-is-fixed claim: fix_answer='N' originally hung
        accoreconsole 4/4 times; the unconditional _QSAVE-before-QUIT fix
        (docs/GOVERNED_COMMAND_TEMPLATES.md section 5) resolved it. This must
        complete well within the timeout, not merely 'not time out eventually'."""
        env = cte.run_template("maintenance.drawing.audit", {"fix_answer": "N"}, str(_FIXTURE),
                                write_mode="read", timeout_sec=60)
        self.assertEqual(env["status"], "ok", msg=json.dumps(env, ensure_ascii=False)[:2000])
        self.assertNotEqual(env.get("error", {}).get("code"), "ACCORECONSOLE_TIMEOUT")


@unittest.skipUnless(_live_enabled(), "CADOS_LIVE!=1 or accoreconsole/fixture missing")
class TestPurgeTemplateLive(unittest.TestCase):
    def test_purge_ok_and_original_unchanged(self):
        sha_before = cte.sha256_file(_FIXTURE)
        env = cte.run_template("maintenance.drawing.purge", {}, str(_FIXTURE),
                                write_mode="write_copy", timeout_sec=90)
        self.assertEqual(cte.sha256_file(_FIXTURE), sha_before, "original mutated by a template run")
        self.assertEqual(env["status"], "ok", msg=json.dumps(env, ensure_ascii=False)[:2000])
        pcs = {p["kind"]: p for p in env["result"]["postconditions"]}
        self.assertTrue(pcs["entity_count_probe"]["unchanged"])


@unittest.skipUnless(_live_enabled(), "CADOS_LIVE!=1 or accoreconsole/fixture missing")
class TestArrayRectExplodeTemplateLive(unittest.TestCase):
    """DCM/constraints_associativity pilot templates (Lane W5-TMPL mission 5,
    per the 2026-07-06 SDK census re-audit's command-coverage estimate).
    Chained: ARRAYRECT's own staged output feeds EXPLODE's input, since
    exploding only makes semantic sense against a drawing that actually
    contains an associative array (EXPLODE against the pristine fixture,
    which has none, is not a meaningful test of this template)."""

    def test_arrayrect_then_explode_entity_count_roundtrips(self):
        sha_before = cte.sha256_file(_FIXTURE)
        array_env = cte.run_template(
            "define.assocarray.rectangular",
            {"rows": 3, "cols": 2, "row_spacing": 5, "col_spacing": 5},
            str(_FIXTURE), write_mode="write_copy", timeout_sec=60,
        )
        self.assertEqual(cte.sha256_file(_FIXTURE), sha_before, "original mutated by ARRAYRECT")
        self.assertEqual(array_env["status"], "ok", msg=json.dumps(array_env, ensure_ascii=False)[:2000])
        array_pc = array_env["result"]["postconditions"][0]
        self.assertTrue(array_pc["unchanged"], "associative array must not net-add entities")

        staged_with_array = array_env["details"]["staged_input"]
        explode_env = cte.run_template(
            "edit.assocarray.explode", {}, staged_with_array,
            write_mode="write_copy", timeout_sec=60,
        )
        self.assertEqual(cte.sha256_file(_FIXTURE), sha_before, "original mutated by EXPLODE")
        self.assertEqual(explode_env["status"], "ok", msg=json.dumps(explode_env, ensure_ascii=False)[:2000])
        explode_pc = explode_env["result"]["postconditions"][0]
        self.assertTrue(explode_pc["increased"], "exploding an array must increase entity count")
        self.assertEqual(explode_pc["after"] - explode_pc["before"], 5,
                         "3x2 array explode should add exactly rows*cols-1 = 5 entities")


if __name__ == "__main__":
    unittest.main()
