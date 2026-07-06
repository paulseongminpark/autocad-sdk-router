#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F10 TEST -- fixture_foundry: KIND_MANIFEST integrity + mocked mint pipeline.

Intent (WHY):
  * KIND_MANIFEST is the F10 deliverable itself (13 new kinds + 4 hard kinds,
    per PLAN.md node F10 / G9). Every op_id in it must be a REAL, registered,
    'implemented', write_copy-eligible operation -- a manifest entry pointing
    at a made-up or unwired op_id would silently defeat F10's whole purpose.
  * mint_fixture()'s core contract is "no fake success": (a) an unknown kind
    or a missing hard precondition (rasterimage's image asset) must refuse
    BEFORE touching the CAD runtime; (b) a create that reports failure must
    leave NO fixture on disk; (c) a create that SELF-REPORTS success but whose
    entity a fresh, independent re-inspect cannot re-find must ALSO leave NO
    fixture -- this is the one behavior that distinguishes this harness from
    naively trusting cadctl.Cad.run_operation's envelope status (which reports
    'ok' as soon as ANY native result parses -- see cadctl.Cad.run_operation).
    We exercise all of this by MOCKING run_job (no AutoCAD needed), the same
    technique already used by
    tests/unit/test_patch_engine_policy.py::_FakeRunJob, so mint_fixture's
    REAL control flow (staging, sha verification, envelope building, re-open,
    re-query-by-handle) runs for real.
  * foundry_status() must detect a tampered/stale fixture (sha mismatch) as
    UNVERIFIED, never trust a bare "the .dwg file exists".
  * deferred_mint_commands() is the exact per-kind command the HARD RULES
    require when the runtime is unavailable -- it must cover every manifest
    kind and never silently drop one.

We do NOT require AutoCAD. Discoverable by pytest and
``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
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

_JSON_ENCODING = "utf-8-sig"
_OPERATIONS_V2 = os.path.join(_REPO, "config", "operations.v2.json")


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _native_result(handles):
    """Minimal native graph result with the given handles (LINE-shaped payload).

    Mirrors tests/unit/test_patch_engine_policy.py::_native_result -- this exact
    shape is already proven, in this repo, to round-trip through
    ir_builder.build_ir_from_database_graph -> sqlite_ir_store correctly.
    """
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


class _FakeRunJob:
    """Stand-in for the run_job sibling: returns canned results per operation
    so cadctl.Cad.run_operation / .inspect run their REAL control flow
    (staging, sha verification, envelope building) without AutoCAD. Mirrors
    tests/unit/test_patch_engine_policy.py::_FakeRunJob, extended to dispatch
    by arbitrary op_id (create_results) rather than a single write op.
    """

    def __init__(self, create_results, inspect_result):
        # create_results: dict[op_id -> native result dict (or None)].
        self.create_results = dict(create_results)
        self.inspect_result = inspect_result
        self.calls = []

    def run_router_cad_job(self, staged_dwg, run_dir, operation, *,
                           write_mode="read", job_path=None, timeout=600,
                           intent="dwg"):
        self.calls.append({"staged": staged_dwg, "operation": operation,
                           "write_mode": write_mode, "job_path": job_path})
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
            out["result"] = self.inspect_result
        else:
            out["result"] = self.create_results.get(operation)
        return out


class _RunJobPatch:
    """Context manager: monkeypatch run_job.run_router_cad_job for the block."""

    def __init__(self, fake):
        self.fake = fake

    def __enter__(self):
        import run_job
        self._mod = run_job
        self._orig = run_job.run_router_cad_job
        run_job.run_router_cad_job = self.fake.run_router_cad_job
        return self.fake

    def __exit__(self, *exc):
        self._mod.run_router_cad_job = self._orig
        return False


def _make_seed(tmp) -> str:
    seed = os.path.join(tmp, "seed.dwg")
    with open(seed, "wb") as fh:
        fh.write(b"FAKE-DWG-BYTES-DO-NOT-TOUCH")
    return seed


class TestKindManifestIntegrity(unittest.TestCase):
    """The manifest itself is the F10 deliverable -- it must stay honest."""

    @classmethod
    def setUpClass(cls):
        with open(_OPERATIONS_V2, "r", encoding=_JSON_ENCODING) as fh:
            reg = json.load(fh)
        cls.registry = {o["id"]: o for o in reg.get("operations", [])}

    def test_manifest_has_13_new_plus_4_hard_kinds(self):
        import fixture_foundry as ff

        self.assertEqual(len(ff.NEW_KINDS), 13)
        self.assertEqual(len(ff.HARD_KINDS), 4)
        self.assertEqual(len(ff.KIND_MANIFEST), 17)
        self.assertEqual(set(ff.NEW_KINDS) | set(ff.HARD_KINDS), set(ff.KIND_MANIFEST))
        self.assertEqual(set(ff.NEW_KINDS) & set(ff.HARD_KINDS), set())

    def test_every_manifest_op_id_is_registered_implemented_write_copy(self):
        import fixture_foundry as ff

        for kind, spec in ff.KIND_MANIFEST.items():
            with self.subTest(kind=kind):
                op_id = spec["op_id"]
                rec = self.registry.get(op_id)
                self.assertIsNotNone(rec, "%s: op_id %r not in operations.v2.json" % (kind, op_id))
                self.assertEqual(rec.get("status"), "implemented",
                                 "%s: %r is not status=='implemented'" % (kind, op_id))
                allowed = (rec.get("write_level") or {}).get("allowed_write_modes") or []
                self.assertIn("write_copy", allowed,
                             "%s: %r does not allow write_copy" % (kind, op_id))

    def test_region_prereq_op_is_also_registered(self):
        import fixture_foundry as ff

        prereq = ff.KIND_MANIFEST["region"]["prereq"]
        rec = self.registry.get(prereq["op_id"])
        self.assertIsNotNone(rec)
        self.assertEqual(rec.get("status"), "implemented")
        self.assertEqual(prereq["wire_into"], "curves")
        self.assertEqual(prereq["wire_as"], "list")

    def test_body_is_declared_negative_control(self):
        import fixture_foundry as ff

        spec = ff.KIND_MANIFEST["body"]
        self.assertIs(spec.get("expected_non_degenerate"), False)
        self.assertEqual(spec.get("role"), "negative_control")

    def test_no_manifest_entry_has_empty_args(self):
        # F10 fixtures must be deliberately non-degenerate, non-empty-arg
        # constructions -- the {} empty-arg control probe is F1's job.
        import fixture_foundry as ff

        for kind, spec in ff.KIND_MANIFEST.items():
            with self.subTest(kind=kind):
                self.assertTrue(spec["args"], "%s: args must not be empty" % kind)


class TestMintFixtureMocked(unittest.TestCase):
    """mint_fixture()'s core pipeline, run_job mocked (no AutoCAD)."""

    def setUp(self):
        import cadctl
        import fixture_foundry as ff
        self.cadctl = cadctl
        self.ff = ff

    def test_unknown_kind_refuses_before_touching_runtime(self):
        with tempfile.TemporaryDirectory(prefix="f10_unknown_") as tmp:
            seed = _make_seed(tmp)
            fake = _FakeRunJob({}, _native_result([]))
            with _RunJobPatch(fake):
                rec = self.ff.mint_fixture(
                    "not_a_real_kind", seed_dwg=seed,
                    fixtures_dir=os.path.join(tmp, "fixtures"),
                    run_root=os.path.join(tmp, "run"),
                    cad=self.cadctl.Cad(router_home=tmp))
            self.assertEqual(rec["status"], "UNVERIFIED")
            self.assertFalse(rec["verified"])
            self.assertIn("unknown kind", rec["reason"])
            self.assertEqual(fake.calls, [], "unknown kind must never call the CAD runtime")

    def test_missing_asset_refuses_before_touching_runtime(self):
        with tempfile.TemporaryDirectory(prefix="f10_asset_") as tmp:
            seed = _make_seed(tmp)
            fake = _FakeRunJob({}, _native_result([]))
            with _RunJobPatch(fake):
                rec = self.ff.mint_fixture(
                    "rasterimage", seed_dwg=seed,
                    fixtures_dir=os.path.join(tmp, "fixtures"),
                    run_root=os.path.join(tmp, "run"),
                    cad=self.cadctl.Cad(router_home=tmp))
            self.assertEqual(rec["status"], "UNVERIFIED")
            self.assertIn("missing_asset", rec["reason"])
            self.assertEqual(fake.calls, [], "missing asset must never call the CAD runtime")
            self.assertFalse(os.path.isdir(os.path.join(tmp, "fixtures")))

    def test_successful_mint_writes_fixture_and_matching_sha(self):
        with tempfile.TemporaryDirectory(prefix="f10_ok_") as tmp:
            seed = _make_seed(tmp)
            sha_before = _sha256(seed)
            fixtures_dir = os.path.join(tmp, "fixtures")
            fake = _FakeRunJob(
                {"write.entity.point": {"created": True, "errorstatus": 0,
                                        "handle": "AAA1", "layer": "0",
                                        "modelspace_entities_after": 1}},
                _native_result(["AAA1"]))
            with _RunJobPatch(fake):
                rec = self.ff.mint_fixture(
                    "point", seed_dwg=seed, fixtures_dir=fixtures_dir,
                    run_root=os.path.join(tmp, "run"),
                    cad=self.cadctl.Cad(router_home=tmp))

            self.assertEqual(rec["status"], "VERIFIED", rec)
            self.assertTrue(rec["verified"])
            self.assertEqual(rec["handle"], "AAA1")
            self.assertIsNone(rec["reason"])
            fixture_path = Path(fixtures_dir) / "point.dwg"
            sha_path = Path(fixtures_dir) / "point.dwg.sha256"
            self.assertTrue(fixture_path.is_file())
            self.assertTrue(sha_path.is_file())
            self.assertEqual(sha_path.read_text(encoding="utf-8").strip(), _sha256(fixture_path))
            self.assertEqual(rec["sha256"], _sha256(fixture_path))
            # exactly one create call + one re-inspect call.
            ops_called = [c["operation"] for c in fake.calls]
            self.assertEqual(ops_called, ["write.entity.point", "inspect.database.graph"])
            # the seed (the ORIGINAL) must never be mutated.
            self.assertEqual(_sha256(seed), sha_before)

    def test_creation_failure_leaves_no_fixture_and_skips_reinspect(self):
        with tempfile.TemporaryDirectory(prefix="f10_fail_") as tmp:
            seed = _make_seed(tmp)
            fixtures_dir = os.path.join(tmp, "fixtures")
            fake = _FakeRunJob(
                {"write.entity.point": {"status": "error", "error_code": "MISSING_ARG",
                                        "error": "write.entity.point requires position"}},
                _native_result(["AAA1"]))
            with _RunJobPatch(fake):
                rec = self.ff.mint_fixture(
                    "point", seed_dwg=seed, fixtures_dir=fixtures_dir,
                    run_root=os.path.join(tmp, "run"),
                    cad=self.cadctl.Cad(router_home=tmp))

            self.assertEqual(rec["status"], "UNVERIFIED")
            self.assertIn("not confirmed", rec["reason"])
            self.assertFalse(Path(fixtures_dir, "point.dwg").exists())
            ops_called = [c["operation"] for c in fake.calls]
            self.assertEqual(ops_called, ["write.entity.point"],
                            "a failed create must never proceed to re-inspect")

    def test_created_true_but_reinspect_cannot_refind_handle_is_unverified(self):
        # The self-report says success; an independent re-inspect disagrees.
        # This is the behavior that distinguishes F10 from trusting the
        # envelope alone (Rule 12 -- no fake success).
        with tempfile.TemporaryDirectory(prefix="f10_ghost_") as tmp:
            seed = _make_seed(tmp)
            fixtures_dir = os.path.join(tmp, "fixtures")
            fake = _FakeRunJob(
                {"write.entity.point": {"created": True, "errorstatus": 0,
                                        "handle": "GHOST1", "layer": "0",
                                        "modelspace_entities_after": 1}},
                _native_result(["SOMETHING_ELSE"]))  # GHOST1 never re-found
            with _RunJobPatch(fake):
                rec = self.ff.mint_fixture(
                    "point", seed_dwg=seed, fixtures_dir=fixtures_dir,
                    run_root=os.path.join(tmp, "run"),
                    cad=self.cadctl.Cad(router_home=tmp))

            self.assertEqual(rec["status"], "UNVERIFIED")
            self.assertEqual(rec["handle"], "GHOST1")
            self.assertIn("not proven persisted", rec["reason"])
            self.assertFalse(Path(fixtures_dir, "point.dwg").exists(),
                             "a self-reported-only success must NOT produce a fixture")

    def test_region_prereq_handle_is_wired_into_curves_arg(self):
        with tempfile.TemporaryDirectory(prefix="f10_region_") as tmp:
            seed = _make_seed(tmp)
            fixtures_dir = os.path.join(tmp, "fixtures")
            fake = _FakeRunJob(
                {
                    "write.entity.circle": {"created": True, "errorstatus": 0,
                                            "handle": "CIR1", "layer": "0",
                                            "modelspace_entities_after": 1},
                    # region's REAL envelope shape (m08gAppendPieces) has no
                    # singular "handle"/"errorstatus" -- only "region_count"
                    # + a plural "handles" array. mint_fixture must resolve
                    # its representative handle from handles[0].
                    "write.entity.region": {"created": True, "region_count": 1,
                                           "handles": ["REG1"], "layer": "0",
                                           "modelspace_entities_after": 2},
                },
                _native_result(["CIR1", "REG1"]))
            with _RunJobPatch(fake):
                rec = self.ff.mint_fixture(
                    "region", seed_dwg=seed, fixtures_dir=fixtures_dir,
                    run_root=os.path.join(tmp, "run"),
                    cad=self.cadctl.Cad(router_home=tmp))

            self.assertEqual(rec["status"], "VERIFIED", rec)
            self.assertEqual(rec["prereq"]["handle"], "CIR1")
            self.assertEqual(rec["args"].get("curves"), ["CIR1"])
            # the representative handle must be resolved from handles[0]
            # since region's envelope has no singular "handle" key.
            self.assertEqual(rec["handle"], "REG1")
            # find the SECOND (region) create call and confirm the job args
            # file it was given actually carries curves:["CIR1"].
            create_calls = [c for c in fake.calls if c["operation"] == "write.entity.region"]
            self.assertEqual(len(create_calls), 1)
            job_path = create_calls[0]["job_path"]
            self.assertIsNotNone(job_path)
            with open(job_path, "r", encoding="utf-8") as fh:
                sent = json.load(fh)
            self.assertEqual(sent.get("curves"), ["CIR1"])

    def test_region_prereq_failure_blocks_main_create(self):
        with tempfile.TemporaryDirectory(prefix="f10_region_fail_") as tmp:
            seed = _make_seed(tmp)
            fixtures_dir = os.path.join(tmp, "fixtures")
            fake = _FakeRunJob(
                {"write.entity.circle": {"status": "error", "error_code": "DB_ERROR",
                                         "error": "getBlockTable"}},
                _native_result([]))
            with _RunJobPatch(fake):
                rec = self.ff.mint_fixture(
                    "region", seed_dwg=seed, fixtures_dir=fixtures_dir,
                    run_root=os.path.join(tmp, "run"),
                    cad=self.cadctl.Cad(router_home=tmp))

            self.assertEqual(rec["status"], "UNVERIFIED")
            self.assertIn("prereq", rec["reason"])
            ops_called = [c["operation"] for c in fake.calls]
            self.assertEqual(ops_called, ["write.entity.circle"],
                            "a failed prereq must never reach the dependent create")
            self.assertFalse(Path(fixtures_dir, "region.dwg").exists())

    def test_negative_control_body_is_minted_but_flagged(self):
        with tempfile.TemporaryDirectory(prefix="f10_body_") as tmp:
            seed = _make_seed(tmp)
            fixtures_dir = os.path.join(tmp, "fixtures")
            fake = _FakeRunJob(
                {"write.entity.body": {"created": True, "kind": "AcDbBody",
                                       "errorstatus": 0, "handle": "BODY1",
                                       "layer": "0", "modelspace_entities_after": 1}},
                _native_result(["BODY1"]))
            with _RunJobPatch(fake):
                rec = self.ff.mint_fixture(
                    "body", seed_dwg=seed, fixtures_dir=fixtures_dir,
                    run_root=os.path.join(tmp, "run"),
                    cad=self.cadctl.Cad(router_home=tmp))

            self.assertEqual(rec["status"], "VERIFIED_NEGATIVE_CONTROL", rec)
            self.assertIs(rec["expected_non_degenerate"], False)
            self.assertTrue(Path(fixtures_dir, "body.dwg").is_file(),
                            "the entity genuinely persists -- it must still be minted")

    def test_mint_all_reports_totals_and_writes_manifest_run(self):
        with tempfile.TemporaryDirectory(prefix="f10_all_") as tmp:
            seed = _make_seed(tmp)
            fixtures_dir = os.path.join(tmp, "fixtures")
            run_root = os.path.join(tmp, "run")
            fake = _FakeRunJob(
                {"write.entity.point": {"created": True, "errorstatus": 0,
                                        "handle": "P1", "layer": "0",
                                        "modelspace_entities_after": 1},
                 "write.entity.trace": None},  # no result at all -> failure
                _native_result(["P1"]))
            with _RunJobPatch(fake):
                payload = self.ff.mint_all(
                    ["point", "trace"], seed_dwg=seed, fixtures_dir=fixtures_dir,
                    run_root=run_root, cad=self.cadctl.Cad(router_home=tmp))

            self.assertEqual(payload["total"], 2)
            self.assertEqual(payload["verified_count"], 1)
            self.assertEqual(payload["unverified_count"], 1)
            self.assertFalse(payload["all_verified"])
            self.assertTrue(os.path.isfile(os.path.join(run_root, "manifest_run.json")))


class TestFoundryStatus(unittest.TestCase):
    def setUp(self):
        import fixture_foundry as ff
        self.ff = ff

    def test_status_all_unverified_on_empty_dir(self):
        with tempfile.TemporaryDirectory(prefix="f10_status_empty_") as tmp:
            out = self.ff.foundry_status(tmp)
            self.assertEqual(out["total_kinds"], 17)
            self.assertEqual(out["verified_count"], 0)
            self.assertFalse(out["all_verified"])
            self.assertTrue(all(k["status"] == "UNVERIFIED" for k in out["kinds"]))

    def test_status_detects_tampered_fixture_as_unverified(self):
        with tempfile.TemporaryDirectory(prefix="f10_status_tamper_") as tmp:
            fixture = Path(tmp) / "point.dwg"
            fixture.write_bytes(b"REAL-CONTENT")
            (Path(tmp) / "point.dwg.sha256").write_text(_sha256(fixture) + "\n", encoding="utf-8")

            out_ok = self.ff.foundry_status(tmp)
            point_ok = next(k for k in out_ok["kinds"] if k["kind"] == "point")
            self.assertEqual(point_ok["status"], "VERIFIED")

            # tamper the fixture WITHOUT updating the sidecar sha.
            fixture.write_bytes(b"TAMPERED-CONTENT")
            out_bad = self.ff.foundry_status(tmp)
            point_bad = next(k for k in out_bad["kinds"] if k["kind"] == "point")
            self.assertEqual(point_bad["status"], "UNVERIFIED")
            self.assertFalse(point_bad["sha_matches"])

    def test_status_flags_body_as_negative_control_when_verified(self):
        with tempfile.TemporaryDirectory(prefix="f10_status_body_") as tmp:
            fixture = Path(tmp) / "body.dwg"
            fixture.write_bytes(b"EMPTY-ASM-BODY")
            (Path(tmp) / "body.dwg.sha256").write_text(_sha256(fixture) + "\n", encoding="utf-8")
            out = self.ff.foundry_status(tmp)
            body = next(k for k in out["kinds"] if k["kind"] == "body")
            self.assertEqual(body["status"], "VERIFIED_NEGATIVE_CONTROL")


class TestDeferredMintCommands(unittest.TestCase):
    def setUp(self):
        import fixture_foundry as ff
        self.ff = ff

    def test_one_command_per_manifest_kind(self):
        cmds = self.ff.deferred_mint_commands()
        self.assertEqual(len(cmds), len(self.ff.KIND_MANIFEST))
        for kind, cmd in zip(self.ff.KIND_MANIFEST, cmds):
            self.assertIn("--kind %s" % kind, cmd)
            self.assertIn("fixture_foundry.py mint", cmd)

    def test_rasterimage_command_flags_the_required_asset(self):
        cmds = {k: c for k, c in zip(self.ff.KIND_MANIFEST,
                                     self.ff.deferred_mint_commands())}
        self.assertIn("--asset-image", cmds["rasterimage"])
        self.assertNotIn("--asset-image", cmds["point"])

    def test_unknown_kind_raises(self):
        with self.assertRaises(KeyError):
            self.ff.deferred_mint_command("not_a_real_kind")


class TestCli(unittest.TestCase):
    """CLI subprocess parity, mirroring tests/unit/test_cadctl.py's style."""

    def test_status_cli_reports_json_and_nonzero_when_unverified(self):
        with tempfile.TemporaryDirectory(prefix="f10_cli_status_") as tmp:
            proc = subprocess.run(
                [sys.executable, os.path.join(_REPO, "tools", "fixture_foundry.py"),
                 "status", "--out", tmp],
                cwd=_REPO, text=True, capture_output=True,
            )
            self.assertEqual(proc.returncode, 1, proc.stderr)  # nothing verified yet
            out = json.loads(proc.stdout)
            self.assertEqual(out.get("schema"), "ariadne.cad_os.f10.status.v1")
            self.assertEqual(out.get("total_kinds"), 17)
            self.assertFalse(out.get("all_verified"))

    def test_deferred_commands_cli_prints_one_line_per_kind(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(_REPO, "tools", "fixture_foundry.py"),
             "deferred-commands"],
            cwd=_REPO, text=True, capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 17)

    def test_mint_cli_requires_kind_or_all(self):
        with tempfile.TemporaryDirectory(prefix="f10_cli_mint_noargs_") as tmp:
            proc = subprocess.run(
                [sys.executable, os.path.join(_REPO, "tools", "fixture_foundry.py"),
                 "mint", "--seed", os.path.join(tmp, "nope.dwg"), "--out", tmp],
                cwd=_REPO, text=True, capture_output=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("--kind", proc.stderr + proc.stdout)


if __name__ == "__main__":
    unittest.main()
