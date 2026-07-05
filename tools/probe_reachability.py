#!/usr/bin/env python
"""probe_reachability.py -- CADOS WAVE-0 F1: the reachability prober.

For every operation in config/operations.v2.json with top-level status ==
"implemented" (457 today), empirically classify its LIVE, headless
runnability by driving Lane A (`cad_run_operation` / cadctl.Cad.run_operation)
against a THROWAWAY staged copy of a fixture DWG. The registry's own `status`
and `policy.status_policy` fields are NOT trusted (PLAN.md PART 1 sec 1.5: the
four runnability surfaces "do NOT agree" -- e.g. write.entity.text carries
policy.status_policy == "catalogued_not_runnable" while status ==
"implemented"). Only a live probe tells the truth.

Classification set (CADOS FULL-SDK BUILD PLAN, PART 1 sec 1.5 / PART 3 F1):
    RUNNABLE                   a deliberately-authored valid-arg fixture
                                created a real, non-degenerate result.
    RUNNABLE_BUT_DEGENERATE     the op "succeeds" (created:true) on EMPTY /
                                underspecified args -- input-unvalidated
                                (RT-FOLD R1-1/R1-6). Never trusted as RUNNABLE
                                until it either arg-validates or passes a
                                non-degeneracy assertion via its read branch
                                (out of F1's scope -- that's T3a/T9).
    REACHABLE                  the native dispatcher responded with a
                                structured arg/precondition error (MISSING_ARG
                                et al.) -- reachable, zero roundtrip value on
                                its own.
    OPERATION_NOT_IMPLEMENTED  registry status != implemented, OR the native
                                job dispatcher itself has no handler
                                (OPERATION_NOT_IMPLEMENTED /
                                OPERATION_DISPATCH_MISMATCH -- the registry can
                                lie about a compiled handler existing; F1 is
                                exactly the check that catches that drift).
    BLOCKED_BY_POLICY           never agent-exposed by policy: raw AutoCAD
                                command dispatch, or the op's only write mode
                                is write_original (the original DWG is
                                READ-ONLY). Refused before any native call.
    CRASH                       the isolated probe subprocess died abnormally,
                                or the native job produced no parseable result
                                (the engine died mid-run).
    ATTENDED_ONLY               the probe timed out -- headless accoreconsole
                                has no UI, so a hang means the op needs an
                                interactive session (PLAN.md PART 1 sec 1.6:
                                "L" class ops need a behavioral discriminator
                                or are non-goal; F1 cannot build one, so it
                                reports the honest ATTENDED_ONLY rather than a
                                fake PASS -- RT-FOLD R4-17).

v2-A4 (PLAN.md PART 0 sec 0.6): text / mtext / lwpolyline (write.entity.
polyline -- the registry's own summary/native_api confirm this IS the
LWPOLYLINE op) / rotated dimension are REQUIRED, GATING probe rows: the H1
"write is cheap Python" cost model stays PROVISIONAL until these four reach
RUNNABLE (not DEGENERATE, not REACHABLE-arg-error) on a genuinely-authored
valid-arg fixture. See V2_A4_REQUIRED_OPS / FIXTURES below.

Each op's probe pair (empty-arg control + valid-arg fixture, where authored)
runs in its OWN isolated child process (mirrors tools/probe_routes.py) so one
hard crash can never poison the sweep or its exit code, and so a hung/
interactive op can be killed on a bounded timeout instead of stalling the
whole 457-op matrix.

Two run modes:
    --plan (default) -- NO CAD runtime touched. Emits one row per implemented
        op: policy-refused / not-implemented rows get their real class (pure
        registry facts, always correct, free); every other row is honestly
        `class: null, classification_source: "pending"` -- never a fabricated
        RUNNABLE.
    --live -- actually calls cad_run_operation. `--ops op1,op2,...` restricts
        the LIVE calls to a subset (a bounded smoke run); every op outside the
        subset (or every op, if no fixture DWG/runtime is available) still
        gets its own row via --plan rules. Omit --ops for the full 457-op
        sweep (long-running -- see the module docstring's runtime note in the
        F1 build report for a wall-clock estimate).

No side effects on the original DWG: cadctl.Cad.run_operation stages a COPY
per call and verifies the original's sha is unchanged after every single
call; a violation (H-R8) raises OriginalMutatedError and aborts the whole
sweep rather than silently continuing against a possibly-compromised
invariant. Never fabricates a result (Rule 12 / PLAN.md "no fake success").

Usage:
    python tools/probe_reachability.py --out measure/reachable_matrix.jsonl
    python tools/probe_reachability.py --live --ops write.entity.arc,write.entity.text \\
        --dwg tests/fixtures/native_sample.dwg --out measure/reachable_matrix.jsonl
    python tools/probe_reachability.py --check-runtime

Standard library only. Config/registry JSON on this box is BOM-prefixed --
read with encoding="utf-8-sig" (matches cadctl.py's own convention).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_THIS_FILE = Path(__file__).resolve()
_THIS_DIR = _THIS_FILE.parent
ROUTER_HOME = _THIS_DIR.parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import cadctl  # noqa: E402  (sibling tool, Lane A -- cad_run_operation)
import probe_routes  # noqa: E402  (sibling tool -- shared accoreconsole resolver)
from operation_coverage_matrix import is_raw_command  # noqa: E402  (shared policy classifier)

OPERATIONS_V2 = ROUTER_HOME / "config" / "operations.v2.json"
DEFAULT_DWG = ROUTER_HOME / "tests" / "fixtures" / "native_sample.dwg"
DEFAULT_OUT = ROUTER_HOME / "measure" / "reachable_matrix.jsonl"
MATRIX_SCHEMA = "ariadne.cados.reachable_matrix_row.v1"
DEFAULT_TIMEOUT_SEC = 120.0

# Worker-subprocess exit codes (the isolation wrapper; see _spawn_worker).
EXIT_OK = 0
EXIT_ORIGINAL_MUTATED = 3  # H-R8 hard-stop signal, never a plain crash

# --------------------------------------------------------------------------- #
# The F1 runnability ontology (PLAN.md PART 1 sec 1.5 / PART 3 F1 / PART 7 G6)
# --------------------------------------------------------------------------- #
RUNNABLE = "RUNNABLE"
RUNNABLE_BUT_DEGENERATE = "RUNNABLE_BUT_DEGENERATE"
REACHABLE = "REACHABLE"
OPERATION_NOT_IMPLEMENTED = "OPERATION_NOT_IMPLEMENTED"
BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"
CRASH = "CRASH"
ATTENDED_ONLY = "ATTENDED_ONLY"
ALL_CLASSES = (
    RUNNABLE, RUNNABLE_BUT_DEGENERATE, REACHABLE, OPERATION_NOT_IMPLEMENTED,
    BLOCKED_BY_POLICY, CRASH, ATTENDED_ONLY,
)

# v2-A4 (PLAN.md PART 0 sec 0.6): REQUIRED, gating probe rows. write.entity.
# polyline is confirmed (registry summary "Create lightweight polyline
# (LWPOLYLINE)...", native_api "AcDbPolyline::...") to be the LWPOLYLINE op id
# -- there is no separate "lwpolyline" op_id in the registry.
V2_A4_REQUIRED_OPS = (
    "write.entity.text",
    "write.entity.mtext",
    "write.entity.polyline",
    "write.entity.dim.rotated",
)


class OriginalMutatedError(RuntimeError):
    """The original DWG's sha changed mid-probe (H-R8). Hard stop: the caller
    must abort the whole sweep, never classify around it."""


class RuntimeAvailabilityError(RuntimeError):
    """The router/accoreconsole infrastructure itself did not run (missing
    binary, router entrypoint, etc.) -- distinct from a per-op timeout/crash.
    This is a sweep-level fact, never filed as one op's class."""


# --------------------------------------------------------------------------- #
# Registry loading + static (no-live-call) policy classification
# --------------------------------------------------------------------------- #
def load_registry(path: Path | str = OPERATIONS_V2) -> dict:
    """Load config/operations.v2.json (BOM-safe)."""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def load_operations(path: Path | str = OPERATIONS_V2, *, status: str | None = "implemented") -> list[dict]:
    """Registry op records with the given top-level `status` (default: the
    457 F1 must classify). status=None returns the full 517-op catalog."""
    ops = load_registry(path).get("operations") or []
    if status is None:
        return list(ops)
    return [o for o in ops if o.get("status") == status]


def is_write_original_only(op: dict) -> bool:
    """True iff the op's ONLY allowed write mode is write_original (PLAN.md
    PART 1 sec 1.6: "the 8 active_document_write_original ops ... are never
    gate-certified runnable"). F1 never calls these -- the original DWG stays
    READ-ONLY by charter, not by luck."""
    wl = op.get("write_level") or {}
    allowed = set(wl.get("allowed_write_modes") or [])
    if not allowed:
        return wl.get("default_write_mode") in ("write_original", "original")
    return allowed <= {"write_original", "original"}


def policy_preclassify(op: dict) -> str | None:
    """Classify WITHOUT any live call, or None if a live probe is required.

    Two refusals are hard/static and never agent-exposed regardless of what a
    live call might show (mirrors operation_coverage_matrix.py's own
    agent_exposed rule + config/policy.v2.json raw_command_forbidden):
      * raw AutoCAD command dispatch (acedCommand*/acedCmd*/command.invoke/...)
      * ops whose only write mode is write_original.
    A registry status other than "implemented" is likewise decided without a
    call (F1 only ever iterates status=="implemented" rows, but this function
    stays total so it is meaningful outside that iteration too)."""
    if op.get("status") != "implemented":
        return OPERATION_NOT_IMPLEMENTED
    if is_raw_command(op):
        return BLOCKED_BY_POLICY
    if is_write_original_only(op):
        return BLOCKED_BY_POLICY
    return None


def _policy_note(op: dict, cls: str) -> str:
    if cls == OPERATION_NOT_IMPLEMENTED:
        return f"registry status={op.get('status')!r} (not 'implemented')"
    if is_raw_command(op):
        return "raw AutoCAD command dispatch -- never agent-exposed (policy.v2.json raw_command_forbidden)"
    if is_write_original_only(op):
        return "only write_mode is write_original -- refused (the original DWG is READ-ONLY)"
    return ""


# --------------------------------------------------------------------------- #
# Per-op valid-arg fixtures (first-class deliverable, PLAN.md sec 0.6 v2-A4).
# Each entry is evidence-grounded: harvested from an existing, already-used
# job fixture (test_native/job_*.json), the v2 job schema's per-op if/then arg
# rules (schemas/cad_job.v2.schema.json), or the C++ handler's own arg-key
# reads (src/Ariadne.AcadNative/families/m08g_handlers.inc / m08h_handlers.inc)
# -- never a blind guess. Deliberately NOT authored for the ASM family
# (solid3d.loft/revolve/sweep, nurbsurface, body, region): a genuinely
# non-degenerate cross-section/profile is a modeler-dependent input barriered
# behind the B6 ASM non-degeneracy gate (PLAN.md sec 0.6 v2-A5), out of F1's
# scope -- leaving them fixture-less lets the empty-arg control probe's
# RUNNABLE_BUT_DEGENERATE stand as their honest overall class.
# --------------------------------------------------------------------------- #
_F1_LAYER = "ARIADNE_F1_PROBE"

FIXTURES: dict[str, dict] = {
    # v2-A4 REQUIRED rows -----------------------------------------------------
    "write.entity.text": {
        "args": {"layer": _F1_LAYER, "text": "ARIADNE_F1_PROBE_TEXT",
                 "position": {"x": 0.0, "y": 0.0, "z": 0.0}, "height": 2.5},
        "evidence": "src/Ariadne.AcadNative/families/m08h_handlers.inc "
                    "(write.entity.text: layer/text/position/height keys, m08hDispatch)",
    },
    "write.entity.mtext": {
        "args": {"layer": _F1_LAYER, "text": "ARIADNE_F1_PROBE_MTEXT",
                 "position": {"x": 0.0, "y": 10.0, "z": 0.0}, "height": 2.5},
        "evidence": "src/Ariadne.AcadNative/families/m08h_handlers.inc "
                    "(write.entity.mtext: layer/text/position/height keys, m08hDispatch)",
    },
    "write.entity.polyline": {
        "args": {"layer": _F1_LAYER, "points": [
            {"x": 0.0, "y": 0.0}, {"x": 5.0, "y": 0.0}, {"x": 5.0, "y": 5.0},
        ]},
        "evidence": "src/Ariadne.AcadNative/families/m08g_handlers.inc "
                    "(write.entity.polyline/polyline2d: 'points':[{x,y[,bulge]}], "
                    "requires >=2 or MISSING_ARG)",
    },
    "write.entity.dim.rotated": {
        "args": {"layer": _F1_LAYER, "dim_text": "", "rotation": 0.0,
                 "xline1": {"x": 0.0, "y": 0.0, "z": 0.0},
                 "xline2": {"x": 10.0, "y": 0.0, "z": 0.0},
                 "dim_line": {"x": 0.0, "y": 5.0, "z": 0.0}},
        "evidence": "src/Ariadne.AcadNative/families/m08h_handlers.inc "
                    "(write.entity.dim.rotated requires xline1/xline2/dim_line points; "
                    "PLAN.md PART 0 sec 0.1 [V]: MISSING_ARG 'needs xline1,xline2,dim_line' on {})",
    },
    # Bonus rows explicitly named in the F1 accept criterion (arc/text/ellipse
    # RUNNABLE) -----------------------------------------------------------
    "write.entity.arc": {
        "args": {"layer": _F1_LAYER, "center": {"x": 5.0, "y": 5.0, "z": 0.0},
                 "radius": 2.5, "start_angle": 0.0, "end_angle": 3.14159265},
        "evidence": "src/Ariadne.AcadNative/families/m08g_handlers.inc "
                    "(write.entity.arc: center/radius/start_angle/end_angle keys); "
                    "PLAN.md PART 0 sec 0.1 [V]: full-arg create is HONEST (control)",
    },
    "write.entity.ellipse": {
        "args": {"layer": _F1_LAYER, "center": {"x": 0.0, "y": 0.0, "z": 0.0},
                 "major_axis": {"x": 4.0, "y": 0.0, "z": 0.0}, "radius_ratio": 0.5},
        "evidence": "src/Ariadne.AcadNative/families/m08g_handlers.inc "
                    "(write.entity.ellipse: center/normal/major_axis/radius_ratio keys)",
    },
    "write.entity.mpolygon": {
        "args": {"layer": _F1_LAYER, "points": [
            {"x": 0.0, "y": 0.0}, {"x": 8.0, "y": 0.0},
            {"x": 8.0, "y": 8.0}, {"x": 0.0, "y": 8.0},
        ]},
        "evidence": "src/Ariadne.AcadNative/families/m08g_handlers.inc "
                    "(write.entity.mpolygon: m08gRead2dVertices 'points':[{x,y}] + layer; "
                    "append-shell-first then appendMPolygonLoop(closed=true) per a0-engineprep "
                    "409 fix; AcMPolygonObj26.dbx engine-load in-handler per wA-cert)",
    },
    # Already-wired v1 ops -- harvested verbatim from existing, already-used
    # fixtures (test_native/job_*.json) and the v2 job schema's if/then rules.
    "write.entity.line": {
        "args": {"layer": _F1_LAYER, "start": {"x": 1.0, "y": 2.0, "z": 0.0},
                 "end": {"x": 11.0, "y": 12.0, "z": 0.0}},
        "evidence": "test_native/job_line_create.json (existing working fixture)",
    },
    "write.entity.circle": {
        "args": {"layer": _F1_LAYER, "center": {"x": 12.0, "y": 14.0, "z": 0.0}, "radius": 3.5},
        "evidence": "test_native/job_circle_create.json (existing working fixture)",
    },
    "write.layer.create": {
        "args": {"name": "ARIADNE_F1_PROBE_LAYER", "color_index": 3},
        "evidence": "test_native/job_layer_create.json (existing working fixture)",
    },
    "write.block.simple_create": {
        "args": {"name": "ARIADNE_F1_PROBE_BLOCK"},
        "evidence": "test_native/job_block_create.json (existing working fixture)",
    },
    "extend.customobject.create": {
        "args": {"key": "ARIADNE_F1_PROBE_KEY", "value": 42},
        "evidence": "test_native/job_record_create.json (existing working fixture)",
    },
    "extend.customclass.create": {
        "args": {"center": {"x": 10.0, "y": 20.0, "z": 0.0}, "size": 5.0},
        "evidence": "test_native/job_create_args.json (existing working fixture)",
    },
    "write.xdata.set": {
        "args": {"app": "ARIADNEF1PROBE", "value": "f1-probe-xdata"},
        "evidence": "test_native/job_xdata_set.json (existing working fixture)",
    },
    "write.xrecord.set": {
        "args": {"dictionary": "ARIADNE_F1_PROBE", "key": "f1_probe_key", "value": "f1-probe-value"},
        "evidence": "test_native/job_xrecord_set.json (existing working fixture)",
    },
}


# --------------------------------------------------------------------------- #
# Runtime availability (cheap, read-only; does not guarantee any one op runs)
# --------------------------------------------------------------------------- #
def runtime_available() -> tuple[bool, str]:
    """Rule out the "not installed here at all" case honestly. Reuses
    probe_routes.py's own accoreconsole candidate search (single source of
    truth for "where is accoreconsole" on this box)."""
    exe = probe_routes._cli(probe_routes.ACCORECONSOLE_CANDIDATES)
    if not exe:
        return False, "accoreconsole.exe not found (dwg_truth_autocad route unavailable)"
    if not DEFAULT_DWG.exists():
        return False, f"no fixture DWG at {DEFAULT_DWG}"
    return True, exe


# --------------------------------------------------------------------------- #
# The core classifier -- PURE, no I/O, no subprocess. This is what the
# synthetic/mocked unit tests exercise directly.
# --------------------------------------------------------------------------- #
def classify_probe_response(env: dict, *, is_empty_arg: bool) -> str:
    """Classify ONE cad_run_operation response envelope (the dict returned by
    cadctl.Cad.run_operation) into one of the 7 F1 buckets.

    `is_empty_arg` says whether THIS call used the {} control probe -- it is
    the only thing that distinguishes a genuinely-demonstrated create
    (RUNNABLE) from an input-unvalidated fake success (RUNNABLE_BUT_DEGENERATE,
    RT-FOLD R1-1/R1-6): the SAME `created:true` signal means different things
    depending on whether the args behind it were deliberately valid or empty.
    """
    if not isinstance(env, dict):
        raise ValueError("classify_probe_response requires a probe envelope dict")

    if env.get("_probe_crash"):
        return CRASH
    if env.get("_probe_timeout"):
        return ATTENDED_ONLY

    executed = env.get("executed", True)
    status = env.get("status")

    if not executed:
        # cadctl's own allow-list / write-mode gate refused the call BEFORE
        # any native dispatch (cadctl.py Cad._run_op_refusal). "not_found"
        # means the op_id isn't in the registry at all; every other
        # pre-dispatch refusal (registry status != implemented /
        # write_original / disallowed write_mode / missing dwg_path) is a
        # POLICY-governed refusal, not a native-layer signal.
        if status == "not_found":
            return OPERATION_NOT_IMPLEMENTED
        return BLOCKED_BY_POLICY

    if status == "unavailable":
        reason = (env.get("reason") or "").lower()
        if "timed out" in reason:
            return ATTENDED_ONLY
        # The router/powershell/accoreconsole itself never ran -- an
        # INFRASTRUCTURE gap, not a per-op fact. Never silently mis-file the
        # rest of the sweep on the back of this.
        raise RuntimeAvailabilityError(env.get("reason") or "router unavailable")

    if status == "partial":
        # Native job produced no parseable result JSON -- the engine most
        # likely died mid-run without an OS-level crash exit code reaching us.
        return CRASH

    result = env.get("result")
    result = result if isinstance(result, dict) else {}

    if status == "error":
        code = str(result.get("error_code") or "").upper()
        if code in ("OPERATION_NOT_IMPLEMENTED", "OPERATION_DISPATCH_MISMATCH"):
            return OPERATION_NOT_IMPLEMENTED
        if code == "ORIGINAL_WRITE_FORBIDDEN":
            return BLOCKED_BY_POLICY
        # Every other structured native error (MISSING_ARG, MISSING_HANDLE,
        # HANDLE_NOT_FOUND, NO_WORKING_DATABASE, READ_DWG_FAILED, ...) is an
        # honest, reachable dispatcher response (PLAN.md PART 3 F1 change (a):
        # "structured native arg-error = REACHABLE").
        return REACHABLE

    if status in ("blocked", "not_implemented"):
        # A native-layer self-report of non-runnability post-dispatch
        # (distinct from cadctl's pre-dispatch policy refusal handled above).
        return OPERATION_NOT_IMPLEMENTED

    # status == "ok" (or any other unmodeled, non-error native status): a
    # genuine dispatcher response with no error.
    if result.get("created") is True:
        return RUNNABLE_BUT_DEGENERATE if is_empty_arg else RUNNABLE
    return RUNNABLE


def _probe_field_summary(env: dict, cls: str) -> dict:
    result = env.get("result") if isinstance(env.get("result"), dict) else {}
    return {
        "attempted": True,
        "class": cls,
        "status": env.get("status"),
        "created": result.get("created"),
        "error_code": result.get("error_code"),
        "reason": env.get("reason") or result.get("error"),
    }


def classify_op_result(payload: dict) -> dict:
    """Aggregate ONE op's raw two-probe payload (from probe_one() / the
    isolated worker) into the matrix row's live-probe fields:
    {class, empty_arg_probe, valid_arg_probe, input_validated}.

    Aggregation rule (resolves the v2-A4 vs R1-1 tension -- see the F1 build
    report): a genuinely-authored valid-arg fixture that shows RUNNABLE always
    wins (text/mtext/polyline/dim.rotated/arc/ellipse all default-fill on {}
    without argument validation, yet must reach overall RUNNABLE per v2-A4);
    otherwise a RUNNABLE_BUT_DEGENERATE empty-arg result stands (the ASM
    family, which F1 deliberately gives no fixture); otherwise fall back to
    whichever probe actually ran.

    Raises OriginalMutatedError straight through for `_original_mutated`
    payloads (H-R8 hard-stop) -- the caller aborts the sweep, it does not
    classify a row for it."""
    if payload.get("_original_mutated"):
        raise OriginalMutatedError(payload.get("error") or "original DWG mutated mid-probe")

    if payload.get("_probe_crash"):
        empty_summary = {"attempted": True, "class": CRASH, "status": None, "created": None,
                          "error_code": None,
                          "reason": payload.get("reason") or "isolated probe worker crashed"}
        return {"class": CRASH, "empty_arg_probe": empty_summary, "valid_arg_probe": None,
                "input_validated": None}
    if payload.get("_probe_timeout"):
        empty_summary = {"attempted": True, "class": ATTENDED_ONLY, "status": None, "created": None,
                          "error_code": None,
                          "reason": f"probe exceeded {payload.get('timeout_sec')}s (no headless UI to answer it)"}
        return {"class": ATTENDED_ONLY, "empty_arg_probe": empty_summary, "valid_arg_probe": None,
                "input_validated": None}

    empty_env = payload.get("empty_env") or {}
    empty_class = classify_probe_response(empty_env, is_empty_arg=True)
    empty_summary = _probe_field_summary(empty_env, empty_class)

    valid_env = payload.get("valid_env")
    valid_class = None
    valid_summary = None
    if valid_env is not None:
        valid_class = classify_probe_response(valid_env, is_empty_arg=False)
        valid_summary = _probe_field_summary(valid_env, valid_class)

    if valid_class == RUNNABLE:
        overall = RUNNABLE
    elif empty_class == RUNNABLE_BUT_DEGENERATE:
        overall = RUNNABLE_BUT_DEGENERATE
    elif valid_class is not None:
        overall = valid_class
    else:
        overall = empty_class

    return {
        "class": overall,
        "empty_arg_probe": empty_summary,
        "valid_arg_probe": valid_summary,
        "input_validated": empty_class != RUNNABLE_BUT_DEGENERATE,
    }


# --------------------------------------------------------------------------- #
# Live probing: in-process (probe_one) + the isolated-subprocess wrapper.
# --------------------------------------------------------------------------- #
def _check_original_unchanged(op_id: str, probe_label: str, env: dict) -> None:
    if env.get("executed") and env.get("original_unchanged") is False:
        raise OriginalMutatedError(
            f"{op_id} ({probe_label} probe): original DWG sha changed mid-run -- {env.get('reason')!r}"
        )


def probe_one(op_id: str, dwg_path: Path | str, out_dir: Path | str, *, fixture: dict | None = None) -> dict:
    """Run the empty-arg control probe, then (if `fixture` is given) the
    valid-arg fixture probe, for ONE op, in-process, against a REAL
    cadctl.Cad(). Never raises for an ordinary native-layer failure (that is
    cadctl's own no-fake-success contract) -- ONLY raises OriginalMutatedError
    for the H-R8 safety violation."""
    cad = cadctl.Cad()
    out_dir = Path(out_dir)

    empty_dir = out_dir / "empty"
    empty_dir.mkdir(parents=True, exist_ok=True)
    empty_env = cad.run_operation(op_id, args={}, dwg_path=str(dwg_path), out_dir=str(empty_dir))
    _check_original_unchanged(op_id, "empty-arg", empty_env)

    valid_env = None
    if fixture is not None:
        valid_dir = out_dir / "valid"
        valid_dir.mkdir(parents=True, exist_ok=True)
        valid_env = cad.run_operation(op_id, args=fixture, dwg_path=str(dwg_path), out_dir=str(valid_dir))
        _check_original_unchanged(op_id, "valid-arg", valid_env)

    return {"op_id": op_id, "empty_env": empty_env, "valid_env": valid_env}


def _write_json_atomic(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())


def _worker_main(op_id: str, dwg_path: str, out_dir: str, fixture_json: str | None) -> int:
    """The `--probe-one` entrypoint: run ONE op's probe pair and write the
    result to <out_dir>/probe_result.json. Runs as a CHILD process (spawned by
    _run_isolated) so a native-layer crash here can never take down the sweep."""
    fixture = json.loads(fixture_json) if fixture_json else None
    out_dir_p = Path(out_dir)
    result_path = out_dir_p / "probe_result.json"
    try:
        payload = probe_one(op_id, dwg_path, out_dir_p, fixture=fixture)
    except OriginalMutatedError as exc:
        _write_json_atomic(result_path, {"op_id": op_id, "_original_mutated": True, "error": str(exc)})
        return EXIT_ORIGINAL_MUTATED
    _write_json_atomic(result_path, payload)
    return EXIT_OK


def _spawn_worker(cmd: list[str], *, cwd: str, timeout_sec: float, result_path: Path) -> dict:
    """Run `cmd` (a worker subprocess) with isolation semantics: a hard crash
    or a timeout in the child can never raise out of this call. Returns the
    parsed JSON at `result_path` on a normal exit, or a synthetic
    {"_probe_crash"|"_probe_timeout"|"_original_mutated": True, ...} marker
    otherwise. Split out from _run_isolated so it is unit-testable against a
    trivial synthetic child (no cadctl/CAD dependency)."""
    result_path = Path(result_path)
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        return {"_probe_timeout": True, "timeout_sec": timeout_sec}

    if proc.returncode == EXIT_ORIGINAL_MUTATED:
        if result_path.exists():
            try:
                payload = json.loads(result_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                payload = {}
            payload["_original_mutated"] = True
            return payload
        return {"_original_mutated": True, "reason": "worker exited ORIGINAL_MUTATED with no result file"}

    if proc.returncode != EXIT_OK:
        return {"_probe_crash": True, "exit_code": proc.returncode,
                "stderr_tail": (proc.stderr or "")[-2000:]}

    if not result_path.exists():
        return {"_probe_crash": True, "reason": "worker exited 0 but wrote no result file",
                "stderr_tail": (proc.stderr or "")[-2000:]}
    try:
        return json.loads(result_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        return {"_probe_crash": True, "reason": f"result file unreadable: {exc}"}


def _run_isolated(op_id: str, dwg_path: Path | str, out_dir: Path | str,
                   fixture: dict | None, timeout_sec: float) -> dict:
    """Probe ONE op in its OWN child python process (mirrors probe_routes.py's
    isolated-import pattern) so heavy geometry/solid ops (PLAN.md PART 3 F1
    change (d)) -- or any op at all -- can crash or hang without poisoning the
    sweep or its exit code."""
    out_dir = Path(out_dir)
    cmd = [sys.executable, str(_THIS_FILE), "--probe-one", op_id,
           "--dwg", str(dwg_path), "--out-dir", str(out_dir)]
    if fixture is not None:
        cmd += ["--fixture-json", json.dumps(fixture, ensure_ascii=False)]
    return _spawn_worker(cmd, cwd=str(ROUTER_HOME), timeout_sec=timeout_sec,
                          result_path=out_dir / "probe_result.json")


# --------------------------------------------------------------------------- #
# Row building + the two run modes
# --------------------------------------------------------------------------- #
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def _safe_name(op_id: str) -> str:
    return op_id.replace(".", "_").replace(":", "_")


def build_row(op: dict, *, live_payload: dict | None = None) -> dict:
    """Build ONE matrix row. Without `live_payload`, the row is either a
    static policy/registry fact (always correct, no call made) or an honest
    `pending` placeholder -- never a fabricated class."""
    op_id = op.get("id") or op.get("operation")
    row = {
        "schema": MATRIX_SCHEMA,
        "op_id": op_id,
        "family": op.get("family"),
        "registry_status": op.get("status"),
        "policy_status_policy": (op.get("policy") or {}).get("status_policy"),
        "fixture_available": op_id in FIXTURES,
        "fixture_evidence": FIXTURES.get(op_id, {}).get("evidence"),
        "gating_v2_a4": op_id in V2_A4_REQUIRED_OPS,
    }

    static_class = policy_preclassify(op)
    if static_class is not None:
        row.update({
            "class": static_class,
            "classification_source": "policy_static",
            "empty_arg_probe": None,
            "valid_arg_probe": None,
            "input_validated": None,
            "probed_at": None,
            "notes": _policy_note(op, static_class),
        })
        return row

    if live_payload is None:
        row.update({
            "class": None,
            "classification_source": "pending",
            "empty_arg_probe": None,
            "valid_arg_probe": None,
            "input_validated": None,
            "probed_at": None,
            "notes": "live probe deferred (DONE_NEEDS_RUNTIME) -- "
                     "see the F1 build report for the exact deferred command",
        })
        return row

    agg = classify_op_result(live_payload)
    row.update(agg)
    row["classification_source"] = "live_probe"
    row["probed_at"] = _now_iso()
    row["notes"] = ""
    return row


def write_jsonl(rows: list[dict], out_path: Path | str) -> None:
    """Atomic write: one JSON object per line, UTF-8, no BOM (Korean
    byte-exact per PLAN.md discipline), flush+fsync before the rename so a
    crash mid-sweep never leaves a half-written matrix file."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False))
            fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(out_path)


def run_plan(registry_path: Path | str = OPERATIONS_V2, out_path: Path | str = DEFAULT_OUT) -> list[dict]:
    """No CAD runtime touched. One row per implemented op: real policy/
    registry facts where determinable, honest `pending` everywhere else."""
    ops = load_operations(registry_path)
    rows = [build_row(op) for op in ops]
    write_jsonl(rows, out_path)
    return rows


def run_live(registry_path: Path | str = OPERATIONS_V2, dwg_path: Path | str = DEFAULT_DWG,
             out_path: Path | str = DEFAULT_OUT, ops_subset: list[str] | None = None,
             timeout_sec: float = DEFAULT_TIMEOUT_SEC, work_dir: Path | str | None = None) -> list[dict]:
    """Drive the live sweep. Always emits a row for EVERY implemented op (no
    op silently skipped) -- `ops_subset` (if given) only restricts which rows
    get an actual live call this run; every other row still gets its correct
    policy_static/pending row. Omit `ops_subset` for the full 457-op sweep."""
    ok, detail = runtime_available()
    if not ok:
        raise RuntimeAvailabilityError(f"--live requested but the CAD runtime is unavailable: {detail}")

    ops = load_operations(registry_path)
    wanted = set(ops_subset) if ops_subset else None
    work_dir = Path(work_dir) if work_dir else ROUTER_HOME / "runs" / "probe_reachability" / _ts()

    rows: list[dict] = []
    for op in ops:
        op_id = op.get("id") or op.get("operation")
        static_class = policy_preclassify(op)
        if static_class is not None:
            rows.append(build_row(op))
        elif wanted is not None and op_id not in wanted:
            rows.append(build_row(op))  # stays "pending" -- not in this run's subset
        else:
            fixture = FIXTURES.get(op_id, {}).get("args")
            op_dir = work_dir / _safe_name(op_id)
            payload = _run_isolated(op_id, dwg_path, op_dir, fixture, timeout_sec)
            if payload.get("_original_mutated"):
                write_jsonl(rows + [build_row(op)], out_path)  # DISK-FIRST before aborting
                raise OriginalMutatedError(f"{op_id}: {payload}")
            rows.append(build_row(op, live_payload=payload))
        write_jsonl(rows, out_path)  # crash-safe progressive flush after every op

    return rows


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--registry", default=str(OPERATIONS_V2), help="path to config/operations.v2.json")
    ap.add_argument("--dwg", default=str(DEFAULT_DWG), help="fixture DWG to stage from (never mutated)")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output measure/reachable_matrix.jsonl path")
    ap.add_argument("--live", action="store_true",
                     help="actually call cad_run_operation; default is a static --plan (no CAD runtime touched)")
    ap.add_argument("--ops", default=None,
                     help="comma-separated op_id subset for --live (omit = full sweep of every implemented op)")
    ap.add_argument("--timeout-sec", type=float, default=DEFAULT_TIMEOUT_SEC,
                     help="per-op isolated-subprocess timeout (a hang past this = ATTENDED_ONLY)")
    ap.add_argument("--work-dir", default=None, help="scratch dir for staged copies (default: runs/probe_reachability/<ts>)")
    ap.add_argument("--check-runtime", action="store_true", help="report whether a --live sweep is even possible here, then exit")
    # Hidden worker entrypoint (spawned by _run_isolated); not part of the public contract.
    ap.add_argument("--probe-one", dest="probe_one_op", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--fixture-json", dest="fixture_json", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--out-dir", dest="out_dir", default=None, help=argparse.SUPPRESS)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if args.probe_one_op:
        return _worker_main(args.probe_one_op, args.dwg, args.out_dir, args.fixture_json)

    if args.check_runtime:
        ok, detail = runtime_available()
        print(json.dumps({"available": ok, "detail": detail}, indent=1))
        return 0 if ok else 1

    try:
        if args.live:
            ops_subset = [o.strip() for o in args.ops.split(",") if o.strip()] if args.ops else None
            rows = run_live(args.registry, args.dwg, args.out, ops_subset, args.timeout_sec, args.work_dir)
        else:
            rows = run_plan(args.registry, args.out)
    except (OriginalMutatedError, RuntimeAvailabilityError) as exc:
        print(f"ABORTED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    by_class: dict[str | None, int] = {}
    by_source: dict[str, int] = {}
    for row in rows:
        by_class[row["class"]] = by_class.get(row["class"], 0) + 1
        by_source[row["classification_source"]] = by_source.get(row["classification_source"], 0) + 1
    print(json.dumps({
        "schema": MATRIX_SCHEMA,
        "total_rows": len(rows),
        "by_class": by_class,
        "by_classification_source": by_source,
        "out": str(args.out),
    }, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
