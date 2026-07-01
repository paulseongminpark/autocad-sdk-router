#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M02 TEST -- patch_engine: schema/risk/guards + truthful apply_staged.

Intent (WHY):
  * patch_engine is the ONLY sanctioned path to mutate a drawing, and its whole
    reason to exist is SAFETY: it must (a) reject any patch that does not target a
    staged copy, (b) refuse write_original/live_edit by default, and (c) NEVER
    touch the read-only original. These are not nice-to-haves; a hole here means a
    fake/destructive write. We pin each guard.
  * validate_patch_schema is the structural gate; classify_patch_risk encodes the
    blast-radius policy (delete > modify > create; mutate-without-postcondition
    bumps to high). If these drift, a dangerous patch could be planned as "low".
  * apply_staged must DEGRADE TRUTHFULLY without AutoCAD: an op with no native
    write handler returns not_implemented BEFORE touching disk (no-fake-success);
    a supported op whose router host is unavailable returns
    unavailable/partial/blocked -- never a fake "ok" -- and the ORIGINAL bytes are
    proven unchanged. We exercise the full staged lifecycle by MOCKING run_job so
    no AutoCAD is needed, and separately assert the no-handler short-circuit.

We do NOT require AutoCAD. The staged-write lifecycle is driven against a tiny
fake "DWG" (bytes on disk) with run_job + ir_builder monkeypatched, so the test
is deterministic and headless while still exercising apply_staged's real control
flow (stage copy -> pre-inspect -> apply -> post-inspect -> diff -> validate ->
journal -> original-unchanged proof).

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import copy
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

PATCH_SCHEMA_ID = "ariadne.cad_patch.v1"

_TRUTHFUL = {"ok", "blocked", "partial", "unavailable", "not_implemented"}


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _good_patch(staged, original):
    """A schema-valid, low-risk, staged create_line patch."""
    return {
        "schema": PATCH_SCHEMA_ID,
        "patch_id": "p-good-0001",
        "target_dwg": {"staged_path": staged, "original_path": original},
        "operations": [
            {"step_id": "s1", "operation": "create_line",
             "args": {"start": [0, 0, 0], "end": [10, 0, 0], "layer": "0"}},
        ],
        "postconditions": [{"subject": "entity_count", "op": "delta_eq", "value": 1}],
        "policy": {"staged_copy": True, "write_mode": "write_copy"},
    }


class TestValidatePatchSchema(unittest.TestCase):
    def setUp(self):
        import patch_engine
        self.pe = patch_engine

    def test_good_patch_is_valid(self):
        v = self.pe.validate_patch_schema(_good_patch("a/staged.dwg", "b/orig.dwg"))
        self.assertTrue(v["valid"], "good patch reported invalid: %r" % v["errors"])
        self.assertEqual(v["errors"], [])

    def test_missing_required_fields_fail(self):
        v = self.pe.validate_patch_schema({"schema": PATCH_SCHEMA_ID})
        self.assertFalse(v["valid"])
        joined = " ".join(v["errors"])
        for req in ("patch_id", "target_dwg", "operations", "policy"):
            self.assertIn(req, joined)

    def test_staged_equals_original_is_rejected(self):
        same = os.path.join("x", "input.dwg")
        v = self.pe.validate_patch_schema(_good_patch(same, same))
        self.assertFalse(v["valid"])
        self.assertTrue(any("staged_path must differ" in e for e in v["errors"]))

    def test_staged_copy_false_is_rejected(self):
        p = _good_patch("a/staged.dwg", "b/orig.dwg")
        p["policy"]["staged_copy"] = False
        v = self.pe.validate_patch_schema(p)
        self.assertFalse(v["valid"])
        self.assertTrue(any("staged_copy must be true" in e for e in v["errors"]))

    def test_non_object_patch_is_rejected(self):
        v = self.pe.validate_patch_schema("not a dict")
        self.assertFalse(v["valid"])


class TestClassifyPatchRisk(unittest.TestCase):
    def setUp(self):
        import patch_engine
        self.pe = patch_engine

    def test_create_only_is_low(self):
        r = self.pe.classify_patch_risk(_good_patch("a/s.dwg", "b/o.dwg"))
        self.assertEqual(r["risk"], "low")

    def test_delete_without_postcondition_is_high(self):
        p = _good_patch("a/s.dwg", "b/o.dwg")
        p["operations"] = [{"operation": "delete_entity", "args": {"handle": "2A"}}]
        p.pop("postconditions", None)
        r = self.pe.classify_patch_risk(p)
        self.assertEqual(r["risk"], "high")
        self.assertTrue(any("no postconditions" in s for s in r["reasons"]))

    def test_staged_copy_false_is_blocked(self):
        p = _good_patch("a/s.dwg", "b/o.dwg")
        p["policy"]["staged_copy"] = False
        self.assertEqual(self.pe.classify_patch_risk(p)["risk"], "blocked")

    def test_write_original_is_blocked(self):
        p = _good_patch("a/s.dwg", "b/o.dwg")
        p["policy"]["write_mode"] = "write_original"
        self.assertEqual(self.pe.classify_patch_risk(p)["risk"], "blocked")


class TestGuards(unittest.TestCase):
    def setUp(self):
        import patch_engine
        self.pe = patch_engine

    def test_require_staged_copy(self):
        ok = self.pe.require_staged_copy(_good_patch("a/s.dwg", "b/o.dwg"))
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["guard"], "require_staged_copy")
        bad = self.pe.require_staged_copy(_good_patch("a/x.dwg", "a/x.dwg"))
        self.assertFalse(bad["ok"])

    def test_reject_write_original_by_default(self):
        p = _good_patch("a/s.dwg", "b/o.dwg")
        self.assertTrue(self.pe.reject_write_original_by_default(p)["ok"])
        p["policy"]["write_mode"] = "live_edit"
        self.assertFalse(self.pe.reject_write_original_by_default(p)["ok"])

    def test_require_validation(self):
        p = _good_patch("a/s.dwg", "b/o.dwg")
        self.assertTrue(self.pe.require_validation(p)["ok"])
        p.pop("postconditions", None)
        self.assertFalse(self.pe.require_validation(p)["ok"])

    def test_every_guard_record_has_a_guard_id(self):
        for g in (self.pe.require_staged_copy(_good_patch("a/s.dwg", "b/o.dwg")),
                  self.pe.reject_write_original_by_default(_good_patch("a/s.dwg", "b/o.dwg")),
                  self.pe.require_validation(_good_patch("a/s.dwg", "b/o.dwg"))):
            self.assertIsInstance(g.get("guard"), str)
            self.assertTrue(g["guard"])


class TestDryRunPlan(unittest.TestCase):
    def setUp(self):
        import patch_engine
        self.pe = patch_engine

    def test_dry_run_plans_but_never_executes(self):
        plan = self.pe.dry_run_plan(_good_patch("a/s.dwg", "b/o.dwg"))
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["execution"], "not_implemented")
        self.assertTrue(plan["guards_ok"])
        for op in plan["planned_ops"]:
            self.assertEqual(op["execution_status"], "not_implemented")

    def test_dry_run_rejects_bad_guard(self):
        p = _good_patch("a/s.dwg", "b/o.dwg")
        p["policy"]["write_mode"] = "write_original"
        plan = self.pe.dry_run_plan(p)
        self.assertEqual(plan["status"], "rejected")
        self.assertFalse(plan["guards_ok"])


class TestApplyStagedNoHandlerDegrades(unittest.TestCase):
    """An op with no native write handler -> not_implemented BEFORE disk."""

    def setUp(self):
        import patch_engine
        self.pe = patch_engine

    def test_resolve_native_write_op_rejects_unsupported(self):
        # delete_entity / create_hatch / move_entity have NO native handler.
        # (create_polyline was the third fixture here pre-WAVE-1 TIER-1 T1;
        # tools/promote_op.py has since wired it for real -- write.entity.hatch
        # remains genuinely unwired at the patch_ops layer today.)
        for op_name in ("delete_entity", "create_hatch", "move_entity"):
            patch = _good_patch("a/s.dwg", "b/o.dwg")
            patch["operations"] = [{"operation": op_name, "args": {}}]
            rec, err = self.pe._resolve_native_write_op(patch)
            self.assertIsNone(rec, "%s should have no native handler" % op_name)
            self.assertIsNotNone(err)

    def test_apply_staged_not_implemented_for_unsupported_op(self):
        with tempfile.TemporaryDirectory(prefix="patch_ni_") as tmp:
            # a real (fake) original on disk so create_staged_copy could run, but
            # the op resolution short-circuits to not_implemented FIRST.
            original = os.path.join(tmp, "orig.dwg")
            with open(original, "wb") as fh:
                fh.write(b"FAKE-DWG-BYTES")
            sha_before = _sha256(original)
            out_dir = os.path.join(tmp, "run")
            patch = _good_patch(os.path.join(out_dir, "staged_input.dwg"), original)
            patch["operations"] = [{"operation": "delete_entity",
                                    "args": {"handle": "2A"}}]
            patch["postconditions"] = [{"subject": "entity_count",
                                        "op": "delta_eq", "value": -1}]
            res = self.pe.apply_staged(patch, original, out_dir)
            self.assertEqual(res["status"], "not_implemented")
            self.assertIn(res["status"], _TRUTHFUL)
            # ORIGINAL never touched.
            self.assertEqual(_sha256(original), sha_before,
                             "original DWG was modified on a not_implemented path")

    def test_apply_staged_blocks_when_input_missing(self):
        with tempfile.TemporaryDirectory(prefix="patch_blk_") as tmp:
            out_dir = os.path.join(tmp, "run")
            missing = os.path.join(tmp, "nope.dwg")
            patch = _good_patch(os.path.join(out_dir, "staged_input.dwg"), missing)
            res = self.pe.apply_staged(patch, missing, out_dir)
            self.assertEqual(res["status"], "blocked")

    def test_apply_staged_blocks_malformed_patch(self):
        with tempfile.TemporaryDirectory(prefix="patch_bad_") as tmp:
            original = os.path.join(tmp, "orig.dwg")
            with open(original, "wb") as fh:
                fh.write(b"FAKE")
            out_dir = os.path.join(tmp, "run")
            # write_original policy -> risk blocked.
            patch = _good_patch(os.path.join(out_dir, "staged_input.dwg"), original)
            patch["policy"]["write_mode"] = "write_original"
            res = self.pe.apply_staged(patch, original, out_dir)
            self.assertEqual(res["status"], "blocked")
            self.assertEqual(_sha256(original), _sha256(original))


class _FakeRunJob:
    """A stand-in for the run_job sibling: returns canned native graph results so
    apply_staged runs its full staged lifecycle without AutoCAD. Records every
    call so the test can assert NO write ever targeted the original path."""

    def __init__(self, original_path, pre_result, post_result):
        self.original_path = os.path.abspath(original_path)
        self._pre = pre_result
        self._post = post_result
        self.calls = []
        self._n = 0

    def run_router_cad_job(self, staged_dwg, run_dir, operation, *,
                           write_mode="read", job_path=None, timeout=600,
                           intent="dwg"):
        self.calls.append({"staged": os.path.abspath(staged_dwg),
                           "operation": operation, "write_mode": write_mode})
        # SAFETY ASSERTION INSIDE THE MOCK: the router must never be pointed at
        # the original path -- only at staged copies.
        assert os.path.abspath(staged_dwg) != self.original_path, \
            "router invoked on the ORIGINAL path: %s" % staged_dwg
        os.makedirs(run_dir, exist_ok=True)
        stdout = os.path.join(run_dir, "stdout.txt")
        stderr = os.path.join(run_dir, "stderr.txt")
        with open(stdout, "w", encoding="utf-8") as fh:
            fh.write("{}")
        with open(stderr, "w", encoding="utf-8") as fh:
            fh.write("")
        out = {"command": ["fake"], "exit_code": 0, "stdout_path": stdout,
               "stderr_path": stderr, "envelope": {"status": "ok"},
               "result_json": None, "staged_used": None,
               "timed_out": False, "error": None}
        if operation == "inspect.database.graph":
            # pre-inspect first, post-inspect second.
            self._n += 1
            out["result"] = self._pre if self._n == 1 else self._post
        else:
            # a write op: produce a "mutated" staged copy by copying staged_dwg.
            import shutil
            mutated = os.path.join(run_dir, "staged_output_mut.dwg")
            shutil.copy2(staged_dwg, mutated)
            out["result"] = None
            out["staged_used"] = mutated
        return out


def _native_result(handles):
    """Minimal native graph result with the given LINE handles."""
    return {
        "modelspace_entities": len(handles),
        "database": {"header_vars": {}},
        "symbol_tables": {"layers": [{"name": "0", "handle": "10"}]},
        "entities": [
            {"handle": h, "dxf_name": "AcDbLine", "owner_handle": "1F",
             "space": "model", "layer": "0",
             "start": {"x": 0, "y": 0, "z": 0}, "end": {"x": 1, "y": 0, "z": 0}}
            for h in handles
        ],
        "coverage": {"sections_present": ["entities", "layers"]},
    }


class TestApplyStagedLifecycleMocked(unittest.TestCase):
    """Full staged lifecycle with run_job mocked -> never writes the original."""

    def setUp(self):
        import patch_engine
        self.pe = patch_engine

    def test_create_line_runs_lifecycle_and_protects_original(self):
        with tempfile.TemporaryDirectory(prefix="patch_life_") as tmp:
            original = os.path.join(tmp, "orig.dwg")
            with open(original, "wb") as fh:
                fh.write(b"ORIGINAL-DWG-BYTES-DO-NOT-TOUCH")
            sha_before = _sha256(original)
            out_dir = os.path.join(tmp, "run")
            patch = _good_patch(os.path.join(out_dir, "staged_input.dwg"), original)

            # pre = 1 entity (2A7); post = 2 entities (2A7 + the new line 3FF).
            fake = _FakeRunJob(original,
                               _native_result(["2A7"]),
                               _native_result(["2A7", "3FF"]))
            saved_run_job = self.pe.run_job if hasattr(self.pe, "run_job") else None
            # patch_engine imports run_job lazily via _import_optional; patch the
            # module attribute that the lazy import resolves to.
            import run_job as real_run_job
            orig_fn = real_run_job.run_router_cad_job
            real_run_job.run_router_cad_job = fake.run_router_cad_job
            try:
                res = self.pe.apply_staged(patch, original, out_dir)
            finally:
                real_run_job.run_router_cad_job = orig_fn

            # truthful status, never a crash.
            self.assertIn(res["status"], _TRUTHFUL,
                          "apply_staged returned non-truthful status: %r" % res)
            # The mock asserts (internally) the router was never aimed at the
            # original. Belt + suspenders: the original bytes are unchanged.
            self.assertEqual(_sha256(original), sha_before,
                             "ORIGINAL DWG WAS MODIFIED during staged apply")
            # original_unchanged proof must reflect that (when present).
            proof = res.get("original_unchanged")
            if isinstance(proof, dict) and proof.get("sha256_after") is not None:
                self.assertNotEqual(proof.get("unchanged"), False,
                                    "original_unchanged proof says the original changed")
            # a journal must have been written (the audit trail).
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "journal.json")),
                            "no journal.json written by apply_staged")
            # at least one router call happened, all on staged copies.
            self.assertTrue(fake.calls, "apply_staged never invoked the router")
            for c in fake.calls:
                self.assertNotEqual(c["staged"], os.path.abspath(original))

    def test_ir_builder_unavailable_degrades_not_implemented(self):
        # If the ir_builder sibling lacks the rich builder, apply_staged must
        # report not_implemented (no fake), without writing the original.
        with tempfile.TemporaryDirectory(prefix="patch_noirb_") as tmp:
            original = os.path.join(tmp, "orig.dwg")
            with open(original, "wb") as fh:
                fh.write(b"ORIG")
            sha_before = _sha256(original)
            out_dir = os.path.join(tmp, "run")
            patch = _good_patch(os.path.join(out_dir, "staged_input.dwg"), original)

            import ir_builder as real_irb
            saved = real_irb.build_ir_from_database_graph
            del real_irb.build_ir_from_database_graph
            try:
                res = self.pe.apply_staged(patch, original, out_dir)
            finally:
                real_irb.build_ir_from_database_graph = saved
            self.assertEqual(res["status"], "not_implemented")
            self.assertEqual(_sha256(original), sha_before)


if __name__ == "__main__":
    unittest.main()
