"""F1 -- probe_reachability.py classification-logic tests (no CAD runtime needed).

Intent (WHY): the F1 reachability prober's entire value proposition is that its
7-bucket classification is DERIVED CORRECTLY from a cad_run_operation envelope
-- get this wrong and the matrix either fakes a PASS (an ASM op's `created:true`
on empty args reported as RUNNABLE) or falsely fails a genuinely-working op. These
tests feed classify_probe_response()/classify_op_result() SYNTHETIC envelopes
shaped exactly like the real cadctl.Cad.run_operation contract (verified against
cadctl.py's own env-building code and the native handlers' emitNativeError /
*EmitCreated JSON, e.g. src/Ariadne.AcadNative/AriadneNativeJob.cpp and
families/m08g_handlers.inc / m08h_handlers.inc) and assert the CADOS PLAN.md
PART 1 sec 1.5 / PART 3 F1 ontology holds:
  empty-arg created:true            => RUNNABLE_BUT_DEGENERATE (RT-FOLD R1-1/R1-6)
  structured MISSING_ARG            => REACHABLE
  valid-arg created:true, non-empty => RUNNABLE
plus the policy/not-implemented/crash/attended-only/original-mutated edges a
mocked-only test suite can (and must) cover without ever touching accoreconsole.

This file touches NO DWG and never spawns AutoCAD/accoreconsole -- exactly the
same discipline as tests/unit/test_run_operation_gates.py and test_cadctl.py.

Discoverable by pytest. Stdlib only (uses pytest fixtures for tmp_path).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
import probe_reachability as pr  # noqa: E402

_REG = _ROOT / "config" / "operations.v2.json"


def _registry_ops():
    return json.loads(_REG.read_text(encoding="utf-8-sig")).get("operations", [])


# --------------------------------------------------------------------------- #
# classify_probe_response -- the core, pure classifier
# --------------------------------------------------------------------------- #
def _ok_env(created, **result_extra):
    """A cadctl.Cad.run_operation() SUCCESS envelope (status="ok"). Shape
    verified against cadctl.py's run_operation() + m08*EmitCreated (result has
    NO "status" key of its own -- status lives on the outer env)."""
    result = {"created": created, "class": "AcDbLine", "handle": "8F8D",
              "layer": "ARIADNE_F1_PROBE", "modelspace_entities_after": 376}
    result.update(result_extra)
    return {"schema": "ariadne.cadctl.run_operation.v1", "operation": "x", "executed": True,
            "registry_operation_status": "implemented", "write_mode": "write_copy",
            "original_unchanged": True, "status": "ok", "result": result}


def _error_env(error_code, message):
    """A cadctl.Cad.run_operation() native-error envelope (status="error").
    Shape verified against AriadneNativeJob.cpp emitNativeError(): the error
    fields land INSIDE `result` once run_job.py folds the native JSON (no
    "result" key at the native layer -> run_job's `doc.get("result", doc)`
    falls back to the whole envelope, which cadctl then assigns to `result`)."""
    result = {"schema": "ariadne.autocad_native_job_result.v1", "engine": "native_objectarx",
              "operation": "x", "status": "error", "error_code": error_code, "error": message}
    return {"schema": "ariadne.cadctl.run_operation.v1", "operation": "x", "executed": True,
            "registry_operation_status": "implemented", "write_mode": "write_copy",
            "original_unchanged": True, "status": "error", "result": result, "reason": None}


def test_empty_arg_created_true_is_degenerate():
    """RT-FOLD R1-1/R1-6: a create op that 'succeeds' on {} is input-
    unvalidated and must NEVER be trusted as RUNNABLE (this is the whole
    reason F1 exists: the ASM family's created:true-on-{} fake success)."""
    env = _ok_env(True)
    assert pr.classify_probe_response(env, is_empty_arg=True) == pr.RUNNABLE_BUT_DEGENERATE


def test_valid_arg_created_true_nondegenerate_is_runnable():
    """The SAME created:true signal, achieved via a deliberately-authored
    valid-arg fixture, IS trustworthy -- this is what promotes text/mtext/
    lwpolyline/dim.rotated/arc to RUNNABLE per v2-A4."""
    env = _ok_env(True)
    assert pr.classify_probe_response(env, is_empty_arg=False) == pr.RUNNABLE


def test_no_arg_read_op_success_is_runnable_not_degenerate():
    """A read/inspect op legitimately needs no args at all -- {} succeeding
    with no `created` key present is genuinely RUNNABLE even on the empty-arg
    probe (there is no fake-success signal to distrust)."""
    env = _ok_env(None)
    del env["result"]["created"]
    assert pr.classify_probe_response(env, is_empty_arg=True) == pr.RUNNABLE


def test_structured_missing_arg_is_reachable():
    """PLAN.md PART 0 sec 0.1 [V]: write.entity.region on {} -> MISSING_ARG
    'requires curves:[<handle>]' is an HONEST arg-validation response --
    reachable, zero roundtrip value on its own, never RUNNABLE."""
    env = _error_env("MISSING_ARG", "write.entity.region requires 'curves':[<handle>,...]")
    assert pr.classify_probe_response(env, is_empty_arg=True) == pr.REACHABLE


def test_other_structured_native_errors_are_reachable():
    """Every OTHER structured native error_code (not just MISSING_ARG) is
    still an honest, reachable dispatcher response (PLAN.md F1 change (a))."""
    for code in ("MISSING_HANDLE", "HANDLE_NOT_FOUND", "NO_WORKING_DATABASE", "READ_DWG_FAILED"):
        env = _error_env(code, "some precondition failed")
        assert pr.classify_probe_response(env, is_empty_arg=True) == pr.REACHABLE, code


def test_operation_not_implemented_error_code():
    """AriadneNativeJob.cpp emits error_code=OPERATION_NOT_IMPLEMENTED when an
    op_id is absent from the native dispatch table -- this is exactly the
    registry-vs-live drift F1 exists to catch (a registry status=='implemented'
    row whose C++ handler was never actually wired)."""
    env = _error_env("OPERATION_NOT_IMPLEMENTED", "operation 'x' is not implemented in the native module")
    assert pr.classify_probe_response(env, is_empty_arg=True) == pr.OPERATION_NOT_IMPLEMENTED


def test_operation_dispatch_mismatch_is_not_implemented():
    """A family's HasOp()/Dispatch() drift (claims an op, doesn't handle it)
    is functionally 'does not run' -- OPERATION_NOT_IMPLEMENTED, same bucket."""
    env = _error_env("OPERATION_DISPATCH_MISMATCH", "operation 'x' was admitted but no handler claimed it")
    assert pr.classify_probe_response(env, is_empty_arg=True) == pr.OPERATION_NOT_IMPLEMENTED


def test_original_write_forbidden_is_blocked_by_policy():
    env = _error_env("ORIGINAL_WRITE_FORBIDDEN", "write_original is never permitted")
    assert pr.classify_probe_response(env, is_empty_arg=True) == pr.BLOCKED_BY_POLICY


def test_predispatch_not_found_is_operation_not_implemented():
    """cadctl's OWN allow-list gate refuses an unknown op_id BEFORE any native
    call (executed=False, status='not_found') -- the op simply isn't in the
    registry."""
    env = {"schema": "ariadne.cadctl.run_operation.v1", "operation": "x", "status": "not_found",
           "executed": False, "reason": "operation 'x' is not in the operation registry"}
    assert pr.classify_probe_response(env, is_empty_arg=True) == pr.OPERATION_NOT_IMPLEMENTED


def test_predispatch_blocked_is_blocked_by_policy():
    """cadctl refusing BEFORE dispatch (disallowed write_mode / write_original
    / registry status != implemented) is always a POLICY refusal, never a
    native-layer fact."""
    env = {"schema": "ariadne.cadctl.run_operation.v1", "operation": "x", "status": "blocked",
           "executed": False, "reason": "write_mode 'write_original' is never permitted"}
    assert pr.classify_probe_response(env, is_empty_arg=True) == pr.BLOCKED_BY_POLICY


def test_timed_out_unavailable_is_attended_only():
    """A probe that hangs until cadctl's internal timeout fires surfaces as
    status='unavailable' with a 'timed out' reason -- headless accoreconsole
    has no UI, so a hang means the op needs interactive input (RT-FOLD R4-17)."""
    env = {"schema": "ariadne.cadctl.run_operation.v1", "operation": "x", "status": "unavailable",
           "executed": True, "original_unchanged": True,
           "reason": "router cad job timed out after 600s"}
    assert pr.classify_probe_response(env, is_empty_arg=True) == pr.ATTENDED_ONLY


def test_genuinely_unavailable_raises_not_a_fake_class():
    """A missing router/powershell (infra gap, NOT a per-op fact) must never
    be silently filed as some bogus per-op class -- it aborts the sweep."""
    env = {"schema": "ariadne.cadctl.run_operation.v1", "operation": "x", "status": "unavailable",
           "executed": True, "original_unchanged": True,
           "reason": "router entrypoint missing: tools/autocad-router.ps1"}
    with pytest.raises(pr.RuntimeAvailabilityError):
        pr.classify_probe_response(env, is_empty_arg=True)


def test_partial_status_is_crash():
    """No parseable native result JSON -- the engine most likely died mid-run
    without an OS-level crash exit code reaching us."""
    env = {"schema": "ariadne.cadctl.run_operation.v1", "operation": "x", "status": "partial",
           "executed": True, "original_unchanged": True,
           "reason": "native job produced no parseable result JSON"}
    assert pr.classify_probe_response(env, is_empty_arg=True) == pr.CRASH


def test_probe_crash_marker_is_crash():
    assert pr.classify_probe_response({"_probe_crash": True}, is_empty_arg=True) == pr.CRASH


def test_probe_timeout_marker_is_attended_only():
    assert pr.classify_probe_response({"_probe_timeout": True}, is_empty_arg=False) == pr.ATTENDED_ONLY


def test_classify_requires_a_dict():
    with pytest.raises(ValueError):
        pr.classify_probe_response(None, is_empty_arg=True)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# classify_op_result -- op-level aggregation of the two probes
# --------------------------------------------------------------------------- #
def test_aggregate_valid_runnable_overrides_empty_degenerate():
    """The arc/text/mtext/polyline/dim.rotated/line pattern (confirmed LIVE
    this session for write.entity.line and write.entity.solid3d.loft): the op
    ALSO fake-succeeds on {} (no input validation), but a deliberately-valid
    fixture proves a genuine, non-degenerate create -- overall RUNNABLE, this
    is what lets v2-A4's four gating ops reach RUNNABLE."""
    payload = {"op_id": "write.entity.arc", "empty_env": _ok_env(True), "valid_env": _ok_env(True)}
    agg = pr.classify_op_result(payload)
    assert agg["class"] == pr.RUNNABLE
    assert agg["empty_arg_probe"]["class"] == pr.RUNNABLE_BUT_DEGENERATE
    assert agg["valid_arg_probe"]["class"] == pr.RUNNABLE
    assert agg["input_validated"] is False


def test_aggregate_no_fixture_falls_back_to_empty_class_reachable():
    """write.entity.region pattern (confirmed LIVE this session): no F1
    fixture is authored (curve-handle dependent, out of scope) -- the empty
    probe's REACHABLE stands as the op's only, honest classification."""
    payload = {"op_id": "write.entity.region", "empty_env": _error_env("MISSING_ARG", "needs curves"),
               "valid_env": None}
    agg = pr.classify_op_result(payload)
    assert agg["class"] == pr.REACHABLE
    assert agg["valid_arg_probe"] is None
    assert agg["input_validated"] is True


def test_aggregate_degenerate_stands_when_no_fixture_authored():
    """solid3d.loft/revolve/sweep/nurbsurface/body pattern (confirmed LIVE
    this session for solid3d.loft): F1 deliberately authors NO valid-arg
    fixture for the ASM family (B6 non-degeneracy gate, out of scope) -- the
    empty-arg control probe's DEGENERATE verdict is the final, honest class."""
    payload = {"op_id": "write.entity.solid3d.loft", "empty_env": _ok_env(True), "valid_env": None}
    agg = pr.classify_op_result(payload)
    assert agg["class"] == pr.RUNNABLE_BUT_DEGENERATE
    assert agg["input_validated"] is False


def test_aggregate_original_mutated_raises_and_does_not_classify():
    """H-R8 hard stop: never classify a row out of a payload where the
    original DWG's sha changed -- the caller must abort the whole sweep."""
    payload = {"op_id": "write.entity.arc", "_original_mutated": True, "error": "sha changed"}
    with pytest.raises(pr.OriginalMutatedError):
        pr.classify_op_result(payload)


def test_aggregate_crash_and_timeout_markers_short_circuit():
    assert pr.classify_op_result({"_probe_crash": True})["class"] == pr.CRASH
    assert pr.classify_op_result({"_probe_timeout": True, "timeout_sec": 120})["class"] == pr.ATTENDED_ONLY


# --------------------------------------------------------------------------- #
# Static (no-live-call) policy classification
# --------------------------------------------------------------------------- #
def test_policy_preclassify_raw_command_is_blocked():
    """A synthetic op shaped like the registry's own raw-command family
    (acedCommand* dispatch) must never be agent-exposed regardless of what a
    live call might show -- policy.v2.json raw_command_forbidden."""
    op = {"id": "command.invoke.sync", "status": "implemented",
          "handler": {"native_api": "acedCommand(...)"},
          "write_level": {"default_write_mode": "read", "allowed_write_modes": ["read"]}}
    assert pr.policy_preclassify(op) == pr.BLOCKED_BY_POLICY


def test_policy_preclassify_write_original_only_is_blocked():
    op = {"id": "doc.hypothetical_saveover", "status": "implemented",
          "handler": {"native_api": "AcDbDatabase::save"},
          "write_level": {"default_write_mode": "write_original",
                          "allowed_write_modes": ["write_original"]}}
    assert pr.policy_preclassify(op) == pr.BLOCKED_BY_POLICY


def test_policy_preclassify_not_implemented_status():
    op = {"id": "some.blocked.op", "status": "blocked"}
    assert pr.policy_preclassify(op) == pr.OPERATION_NOT_IMPLEMENTED


def test_policy_preclassify_none_when_a_live_probe_is_needed():
    op = {"id": "write.entity.line", "status": "implemented",
          "handler": {"native_api": "AcDbLine ctor"},
          "write_level": {"default_write_mode": "write_copy", "allowed_write_modes": ["write_copy"]}}
    assert pr.policy_preclassify(op) is None


# --------------------------------------------------------------------------- #
# Registry-grounded sanity: the v2-A4 gating rows are real, implemented op_ids
# and carry an authored fixture (a "did I forget one" regression guard).
# --------------------------------------------------------------------------- #
def test_v2_a4_required_ops_exist_and_are_implemented():
    """PLAN.md PART 0 sec 0.6 v2-A4: text/mtext/lwpolyline/rotated-dimension
    GATE the H1 cost model. If one of these op_ids drifted or was never
    'implemented' in the live registry, F1 could never satisfy the gate."""
    ops_by_id = {(o.get("id") or o.get("operation")): o for o in _registry_ops()}
    for op_id in pr.V2_A4_REQUIRED_OPS:
        assert op_id in ops_by_id, f"{op_id} missing from the registry"
        assert ops_by_id[op_id]["status"] == "implemented", f"{op_id} is not status=='implemented'"


def test_v2_a4_required_ops_all_have_an_authored_fixture():
    """Without a valid-arg fixture, F1 can only ever report these four as
    RUNNABLE_BUT_DEGENERATE/REACHABLE (per the aggregation rule) -- never
    RUNNABLE -- silently breaking the v2-A4 gate. This is the regression the
    live smoke (write.entity.line/region/solid3d.loft, this session) exists to
    prevent from going unnoticed."""
    for op_id in pr.V2_A4_REQUIRED_OPS:
        assert op_id in pr.FIXTURES, f"{op_id} has no authored valid-arg fixture"
        assert pr.FIXTURES[op_id]["args"], f"{op_id} fixture args must be non-empty"


def test_load_operations_matches_registry_declared_total():
    """Self-consistency, not a hard-coded magic number (registry counts jitter
    -- PLAN.md's own caveat): the loader's implemented-set size must equal the
    registry's own declared total for that status."""
    doc = pr.load_registry()
    assert len(pr.load_operations()) == doc["totals"]["by_status"]["implemented"]


# --------------------------------------------------------------------------- #
# The isolation wrapper (_spawn_worker) -- genuinely exercised (not mocked)
# against a trivial synthetic child process, so crash/timeout detection is
# proven against a REAL subprocess, without any CAD/cadctl dependency.
# --------------------------------------------------------------------------- #
def test_spawn_worker_normal_exit_returns_parsed_json(tmp_path):
    result_path = tmp_path / "probe_result.json"
    payload = {"ok": True}
    write_expr = (
        "import json,sys; "
        f"json.dump({payload!r}, open(r'{result_path}', 'w'))"
    )
    cmd = [sys.executable, "-c", write_expr]
    out = pr._spawn_worker(cmd, cwd=str(tmp_path), timeout_sec=30, result_path=result_path)
    assert out == payload


def test_spawn_worker_nonzero_exit_is_probe_crash(tmp_path):
    result_path = tmp_path / "probe_result.json"
    cmd = [sys.executable, "-c", "import sys; sys.exit(7)"]
    out = pr._spawn_worker(cmd, cwd=str(tmp_path), timeout_sec=30, result_path=result_path)
    assert out["_probe_crash"] is True
    assert out["exit_code"] == 7


def test_spawn_worker_timeout_is_probe_timeout(tmp_path):
    result_path = tmp_path / "probe_result.json"
    cmd = [sys.executable, "-c", "import time; time.sleep(30)"]
    out = pr._spawn_worker(cmd, cwd=str(tmp_path), timeout_sec=0.5, result_path=result_path)
    assert out["_probe_timeout"] is True


def test_spawn_worker_original_mutated_exit_code_is_flagged(tmp_path):
    result_path = tmp_path / "probe_result.json"
    write_expr = (
        "import json,sys; "
        f"json.dump({{'op_id': 'x'}}, open(r'{result_path}', 'w')); "
        f"sys.exit({pr.EXIT_ORIGINAL_MUTATED})"
    )
    cmd = [sys.executable, "-c", write_expr]
    out = pr._spawn_worker(cmd, cwd=str(tmp_path), timeout_sec=30, result_path=result_path)
    assert out["_original_mutated"] is True
    assert out["op_id"] == "x"


def test_write_jsonl_round_trips(tmp_path):
    rows = [{"a": 1}, {"b": "한글"}]
    out_path = tmp_path / "m.jsonl"
    pr.write_jsonl(rows, out_path)
    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(l) for l in lines] == rows
