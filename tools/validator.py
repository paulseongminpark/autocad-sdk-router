#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validator.py -- Lane E deterministic validation shell for the CAD OS Layer.

Emits an ``ariadne.validation_report.v1`` document (conforms
``schemas/validation_report.v1.schema.json``) by running a fixed set of
DETERMINISTIC gates against a DWG-graph IR document and/or a run folder.

Hard rules (CAD OS Layer build invariants):
  * Standard library ONLY (Python 3.12). No third-party imports.
  * NO LLM, NO heuristics, NO sampling -- every gate is a pure assertion over
    structured inputs. The same inputs always yield the same report.
  * No-fake-success: a gate that cannot run reports ``blocked`` (never ``pass``);
    overall ``status`` is ``pass`` only when every REQUIRED gate passed.
  * Read-only: this module never writes the IR, the run folder, or any DWG. It
    only reads files and returns / prints a report dict.

The canonical truth gate is ``entity_count_consistency``:
    ir.diagnostics.entity_count == len(ir.entities)
    and (when a summary modelspace count is recoverable) == that count too.

Public API:
    validate_target(ir_path=None, run_dir=None) -> dict   # validation_report.v1

Run ``python tools/validator.py`` to validate a tiny inline fixture IR and print
the report (used as the module self-test).
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Paths / constants
# --------------------------------------------------------------------------- #

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)

SCHEMA_ID = "ariadne.validation_report.v1"
IR_SCHEMA_ID = "ariadne.dwg_graph_ir.v1"

# The operation registry that records which ops are actually wired ("implemented").
_OPERATIONS_V2 = os.path.join(_ROUTER_HOME, "config", "operations.v2.json")

# Ops the CAD OS Layer treats as the wired inspection/query baseline. These MUST
# be present AND status=="implemented" in operations.v2.json for the registry
# consistency gate to pass. (Deliberately a small, stable subset -- not all 29 --
# so the gate stays meaningful without coupling to every catalog edit.)
_REQUIRED_WIRED_OPS = (
    "inspect.database.summary",
    "inspect.entity.count",
)

# On this box the catalog/config JSON is written with a UTF-8 BOM; json.load on
# the cp949 locale needs utf-8-sig to decode it.
_JSON_ENCODING = "utf-8-sig"


# --------------------------------------------------------------------------- #
# Small helpers (pure)
# --------------------------------------------------------------------------- #

def _load_json(path: str) -> Any:
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _gate(
    gid: str,
    status: str,
    *,
    description: str = "",
    expected: Any = None,
    actual: Any = None,
    operator: Optional[str] = None,
    message: str = "",
    required: bool = True,
    evidence_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """Build one validation_report gate object (schema $defs/gate)."""
    g: Dict[str, Any] = {"id": gid, "status": status, "required": required}
    if description:
        g["description"] = description
    if expected is not None:
        g["expected"] = expected
    if actual is not None:
        g["actual"] = actual
    if operator is not None:
        g["operator"] = operator
    if message:
        g["message"] = message
    if evidence_ref is not None:
        g["evidence_ref"] = evidence_ref
    return g


def _summary_count_from_ir(ir: Dict[str, Any]) -> Tuple[Optional[int], str]:
    """
    Recover an independent 'summary'/modelspace count from an IR, if present, to
    cross-check against diagnostics.entity_count. Returns (count_or_None, source).

    Looked-up locations, in order:
      * ir.diagnostics.realized_entity_count   (the producer's own realized len)
      * ir.diagnostics.entities_by_type        (sum of per-type counts)
      * ir.source.summary_modelspace_count     (carried-through extract count)
    """
    diag = ir.get("diagnostics") or {}
    if isinstance(diag.get("realized_entity_count"), int):
        return diag["realized_entity_count"], "diagnostics.realized_entity_count"

    ebt = diag.get("entities_by_type")
    if isinstance(ebt, dict) and ebt and all(isinstance(v, int) for v in ebt.values()):
        return sum(ebt.values()), "diagnostics.entities_by_type(sum)"

    src = ir.get("source") or {}
    smc = src.get("summary_modelspace_count")
    if isinstance(smc, int):
        return smc, "source.summary_modelspace_count"

    return None, ""


# --------------------------------------------------------------------------- #
# Individual gates -- each is pure: (inputs) -> gate dict
# --------------------------------------------------------------------------- #

def _gate_ir_schema_present(ir: Optional[Dict[str, Any]], ir_path: Optional[str]) -> Dict[str, Any]:
    gid = "ir_schema_present"
    if ir is None:
        return _gate(gid, "blocked", expected=IR_SCHEMA_ID, actual=None,
                     operator="eq", message="no IR document supplied",
                     description="IR document carries the expected schema tag")
    actual = ir.get("schema")
    ok = actual == IR_SCHEMA_ID
    return _gate(
        gid, "pass" if ok else "fail",
        description="IR document carries the expected schema tag",
        expected=IR_SCHEMA_ID, actual=actual, operator="eq",
        message="" if ok else "IR.schema does not equal %s" % IR_SCHEMA_ID,
        evidence_ref=ir_path,
    )


def _gate_entity_count_consistency(ir: Optional[Dict[str, Any]], ir_path: Optional[str]) -> Dict[str, Any]:
    gid = "entity_count_consistency"
    desc = ("diagnostics.entity_count == len(entities) "
            "== independent summary count (when present)")
    if ir is None:
        return _gate(gid, "blocked", message="no IR document supplied",
                     description=desc, operator="eq")

    entities = ir.get("entities")
    diag = ir.get("diagnostics") or {}
    asserted = diag.get("entity_count")

    if not isinstance(entities, list) or not isinstance(asserted, int):
        return _gate(
            gid, "fail", description=desc, operator="eq",
            expected="int entity_count and list entities",
            actual="entities=%s diagnostics.entity_count=%s"
                   % (type(entities).__name__, type(asserted).__name__),
            message="IR missing entities[] or diagnostics.entity_count",
            evidence_ref=ir_path,
        )

    realized = len(entities)
    summary_count, summary_src = _summary_count_from_ir(ir)

    primary_ok = asserted == realized
    summary_ok = (summary_count is None) or (summary_count == asserted)

    if primary_ok and summary_ok:
        msg = "entity_count==len(entities)==%d" % asserted
        if summary_count is not None:
            msg += " (cross-checked vs %s=%d)" % (summary_src, summary_count)
        return _gate(gid, "pass", description=desc, operator="eq",
                     expected=asserted, actual=realized, message=msg,
                     evidence_ref=ir_path)

    parts = []
    if not primary_ok:
        parts.append("asserted entity_count=%d but len(entities)=%d" % (asserted, realized))
    if not summary_ok:
        parts.append("independent %s=%d != asserted %d"
                     % (summary_src, summary_count, asserted))
    return _gate(gid, "fail", description=desc, operator="eq",
                 expected=asserted, actual=realized, message="; ".join(parts),
                 evidence_ref=ir_path)


def _gate_required_artifacts_exist(run_dir: Optional[str]) -> Dict[str, Any]:
    gid = "required_artifacts_exist"
    desc = "run folder contains the expected cadctl artifacts"
    required = ["cad_job.json", "cad_result.json", "dwg_graph_ir.json"]
    if not run_dir:
        return _gate(gid, "blocked", description=desc, operator="exists",
                     expected=required,
                     message="no run_dir supplied; artifact gate not run",
                     required=False)
    if not os.path.isdir(run_dir):
        return _gate(gid, "fail", description=desc, operator="exists",
                     expected=required, actual="run_dir does not exist",
                     message="run_dir not found: %s" % run_dir,
                     evidence_ref=run_dir)
    present = {n: os.path.isfile(os.path.join(run_dir, n)) for n in required}
    missing = [n for n, ok in present.items() if not ok]
    ok = not missing
    return _gate(
        gid, "pass" if ok else "fail", description=desc, operator="exists",
        expected=required, actual=sorted(n for n, v in present.items() if v),
        message="" if ok else "missing artifacts: %s" % ", ".join(missing),
        evidence_ref=run_dir,
    )


def _gate_no_original_write_evidence(ir: Optional[Dict[str, Any]], run_dir: Optional[str]) -> Dict[str, Any]:
    """
    Assert the extraction operated on a STAGED COPY, not on the read-only
    original. Evidence comes from ir.source: a staged dwg_path that differs from
    original_path (and ideally lives under a 'staging' segment).
    """
    gid = "no_original_write_evidence"
    desc = "extraction operated on a staged copy, never the read-only original"

    if ir is None:
        return _gate(gid, "blocked", description=desc,
                     message="no IR document supplied", required=True)

    src = ir.get("source") or {}
    staged = src.get("dwg_path")
    original = src.get("original_path")

    if not staged:
        return _gate(gid, "fail", description=desc, operator="ne",
                     expected="staged dwg_path present and != original_path",
                     actual="source.dwg_path missing",
                     message="cannot prove a staged copy was used (no source.dwg_path)")

    # Normalize for comparison (case-insensitive on this platform).
    def _norm(p: str) -> str:
        return os.path.normcase(os.path.normpath(p))

    staged_n = _norm(staged)
    distinct = (original is None) or (_norm(original) != staged_n)
    under_staging = "staging" in staged_n.replace("\\", "/").split("/")

    if distinct and (under_staging or original is not None):
        return _gate(
            gid, "pass", description=desc, operator="ne",
            expected="dwg_path != original_path",
            actual={"dwg_path": staged, "original_path": original},
            message="operated on staged copy%s" % (
                " under staging/" if under_staging else ""),
        )

    if not distinct:
        return _gate(gid, "fail", description=desc, operator="ne",
                     expected="dwg_path != original_path",
                     actual={"dwg_path": staged, "original_path": original},
                     message="source.dwg_path equals original_path: original may "
                             "have been operated on in place")

    # Distinct but no original recorded and not under staging/: partial evidence.
    return _gate(gid, "partial", description=desc, operator="ne",
                 expected="staged path under staging/ or original_path recorded",
                 actual={"dwg_path": staged, "original_path": original},
                 message="staged-copy evidence is weak (no original_path, not "
                         "under staging/)", required=False)


def _gate_registry_status_consistency() -> Dict[str, Any]:
    """
    Assert the wired-baseline ops are present and status=='implemented' in
    config/operations.v2.json. Pure file read; no router invocation.
    """
    gid = "registry_status_consistency"
    desc = "wired baseline ops present and implemented in operations.v2.json"
    if not os.path.isfile(_OPERATIONS_V2):
        return _gate(gid, "blocked", description=desc, operator="exists",
                     expected=list(_REQUIRED_WIRED_OPS),
                     message="operations.v2.json not found: %s" % _OPERATIONS_V2)
    try:
        reg = _load_json(_OPERATIONS_V2)
    except (OSError, ValueError) as exc:
        return _gate(gid, "blocked", description=desc,
                     message="could not read operations.v2.json: %s" % exc,
                     evidence_ref=_OPERATIONS_V2)

    ops = reg.get("operations")
    if not isinstance(ops, list):
        return _gate(gid, "fail", description=desc,
                     expected="operations[] list",
                     actual=type(ops).__name__,
                     message="operations.v2.json has no operations[] list",
                     evidence_ref=_OPERATIONS_V2)

    status_by_id = {o.get("id"): o.get("status") for o in ops if isinstance(o, dict)}
    bad: List[str] = []
    for op_id in _REQUIRED_WIRED_OPS:
        st = status_by_id.get(op_id)
        if st != "implemented":
            bad.append("%s=%s" % (op_id, st))

    # Also surface the headline wired count for evidence (advisory, not gated).
    wired_total = sum(1 for s in status_by_id.values() if s == "implemented")
    ok = not bad
    return _gate(
        gid, "pass" if ok else "fail", description=desc, operator="eq",
        expected={op: "implemented" for op in _REQUIRED_WIRED_OPS},
        actual={"wired_total": wired_total,
                "required_ops_status": {op: status_by_id.get(op)
                                        for op in _REQUIRED_WIRED_OPS}},
        message="" if ok else "wired-baseline ops not implemented: %s" % ", ".join(bad),
        evidence_ref=_OPERATIONS_V2,
    )


def _gate_run_folder_completeness(run_dir: Optional[str]) -> Dict[str, Any]:
    """
    Assert the run folder captured external-command evidence (stdout + stderr)
    alongside the job/result, per the 'capture stdout+stderr+exit code' rule.
    """
    gid = "run_folder_completeness"
    desc = "run folder captured stdout/stderr evidence for the external command"
    expected = ["stdout", "stderr"]  # matched by prefix (stdout*.txt etc.)
    if not run_dir:
        return _gate(gid, "blocked", description=desc, operator="exists",
                     expected=expected,
                     message="no run_dir supplied; completeness gate not run",
                     required=False)
    if not os.path.isdir(run_dir):
        return _gate(gid, "fail", description=desc, operator="exists",
                     expected=expected, actual="run_dir does not exist",
                     message="run_dir not found: %s" % run_dir, evidence_ref=run_dir)

    try:
        names = os.listdir(run_dir)
    except OSError as exc:
        return _gate(gid, "blocked", description=desc,
                     message="could not list run_dir: %s" % exc, evidence_ref=run_dir)

    lower = [n.lower() for n in names]
    have_stdout = any(n.startswith("stdout") for n in lower)
    have_stderr = any(n.startswith("stderr") for n in lower)
    missing = []
    if not have_stdout:
        missing.append("stdout*")
    if not have_stderr:
        missing.append("stderr*")
    ok = not missing
    return _gate(
        gid, "pass" if ok else "fail", description=desc, operator="exists",
        expected=expected,
        actual=sorted(n for n in names if n.lower().startswith(("stdout", "stderr"))),
        message="" if ok else "missing run evidence: %s" % ", ".join(missing),
        # missing run evidence downgrades to partial, not a hard fail of the subject
        required=False,
        evidence_ref=run_dir,
    )


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def _roll_up_status(gates: List[Dict[str, Any]]) -> str:
    """
    Overall verdict per validation_report.v1 semantics:
      * any REQUIRED gate fail/blocked -> fail / blocked
      * else any non-required fail/partial, or any blocked -> partial
      * else pass
    """
    required_fail = any(g["status"] == "fail" and g.get("required", True) for g in gates)
    required_blocked = any(g["status"] == "blocked" and g.get("required", True) for g in gates)
    if required_fail:
        return "fail"
    if required_blocked:
        return "blocked"
    soft_problem = any(
        (g["status"] in ("fail", "partial") and not g.get("required", True))
        or g["status"] in ("blocked", "skipped")
        for g in gates
    )
    return "partial" if soft_problem else "pass"


def validate_target(ir_path: Optional[str] = None,
                    run_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Run all deterministic gates over an IR document and/or a run folder.

    Either argument may be None; gates that need a missing input report
    ``blocked`` (required) or are skipped softly (non-required), never ``pass``.

    Returns an ``ariadne.validation_report.v1`` dict.
    """
    errors: List[str] = []
    warnings: List[str] = []
    artifacts: List[Dict[str, Any]] = []

    ir: Optional[Dict[str, Any]] = None
    if ir_path is not None:
        if os.path.isfile(ir_path):
            try:
                ir = _load_json(ir_path)
                artifacts.append({"kind": "ir_json", "ref": ir_path})
            except (OSError, ValueError) as exc:
                errors.append("failed to read IR %s: %s" % (ir_path, exc))
        else:
            errors.append("ir_path not found: %s" % ir_path)

    if run_dir is not None:
        artifacts.append({"kind": "run_dir", "ref": run_dir})

    gates: List[Dict[str, Any]] = [
        _gate_ir_schema_present(ir, ir_path),
        _gate_entity_count_consistency(ir, ir_path),
        _gate_required_artifacts_exist(run_dir),
        _gate_no_original_write_evidence(ir, run_dir),
        _gate_registry_status_consistency(),
        _gate_run_folder_completeness(run_dir),
    ]

    for g in gates:
        if g["status"] == "fail" and g.get("message"):
            errors.append("[%s] %s" % (g["id"], g["message"]))
        elif g["status"] in ("blocked", "partial", "skipped") and g.get("message"):
            warnings.append("[%s] %s" % (g["id"], g["message"]))

    status = _roll_up_status(gates)

    subject_ref: Dict[str, Any] = {}
    if ir_path:
        subject_ref = {"kind": "ir", "ref": ir_path}
    elif run_dir:
        subject_ref = {"kind": "cad_result", "ref": run_dir}

    report: Dict[str, Any] = {
        "schema": SCHEMA_ID,
        "validation_id": "val-%s" % uuid.uuid4().hex[:12],
        "status": status,
        "gates": gates,
        "errors": errors,
        "warnings": warnings,
        "artifacts": artifacts,
        "summary": {
            "gates_total": len(gates),
            "gates_passed": sum(1 for g in gates if g["status"] == "pass"),
            "gates_failed": sum(1 for g in gates if g["status"] == "fail"),
            "gates_skipped": sum(1 for g in gates if g["status"] in ("skipped", "blocked")),
        },
    }
    if subject_ref:
        report["subject_ref"] = subject_ref
    return report


# --------------------------------------------------------------------------- #
# Self-test (__main__): validate a tiny inline fixture IR, print the report
# --------------------------------------------------------------------------- #

def _fixture_ir() -> Dict[str, Any]:
    """A minimal, internally-consistent IR that should PASS the IR-only gates."""
    entities = [
        {
            "handle": "2A", "class": "AcDbLine", "dxf_name": "LINE",
            "owner_handle": "1F", "space": "model", "layer": "0",
            "bbox": [0.0, 0.0, 0.0, 10.0, 0.0, 0.0],
            "geometry": {"kind": "line",
                         "start": [0.0, 0.0, 0.0], "end": [10.0, 0.0, 0.0]},
            "source": {"extractor": "fixture", "decoded": True},
        },
        {
            "handle": "2B", "class": "AcDbCircle", "dxf_name": "CIRCLE",
            "owner_handle": "1F", "space": "model", "layer": "0",
            "bbox": [-5.0, -5.0, 0.0, 5.0, 5.0, 0.0],
            "geometry": {"kind": "circle", "center": [0.0, 0.0, 0.0], "radius": 5.0},
            "source": {"extractor": "fixture", "decoded": True},
        },
    ]
    return {
        "schema": IR_SCHEMA_ID,
        "ir_version": "1.0.0",
        "coverage_level": "geometry_only",
        "source": {
            "dwg_path": os.path.join(_ROUTER_HOME, "staging", "golden",
                                     "fixture", "input.dwg"),
            "original_path": os.path.join(_ROUTER_HOME, "samples", "input.dwg"),
            "format": "dwg", "extractor": "fixture", "engine_tier": "dxf",
        },
        "database": {"header_vars": {}},
        "symbol_tables": {"layers": [{"name": "0", "color_index": 7}]},
        "entities": entities,
        "diagnostics": {
            "entity_count": len(entities),
            "count_scope": "modelspace",
            "realized_entity_count": len(entities),
            "entities_by_type": {"LINE": 1, "CIRCLE": 1},
            "warnings": [],
            "errors": [],
            "coverage": {"sections_present": ["layers", "entities"]},
        },
    }


def _selftest() -> int:
    import tempfile

    tmpdir = tempfile.mkdtemp(prefix="validator_selftest_")
    ir = _fixture_ir()
    ir_path = os.path.join(tmpdir, "dwg_graph_ir.json")
    with open(ir_path, "w", encoding="utf-8") as fh:
        json.dump(ir, fh, indent=2)

    report = validate_target(ir_path=ir_path, run_dir=None)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # Self-test contract: the IR-only required gates must pass; run-folder gates
    # are blocked/soft because no run_dir was supplied. The registry gate depends
    # on the live operations.v2.json -- it passes on a healthy tree, but a missing
    # registry must NOT crash the validator (it reports blocked).
    ir_schema = next(g for g in report["gates"] if g["id"] == "ir_schema_present")
    count_gate = next(g for g in report["gates"] if g["id"] == "entity_count_consistency")
    staged_gate = next(g for g in report["gates"] if g["id"] == "no_original_write_evidence")

    ok = (
        report["schema"] == SCHEMA_ID
        and ir_schema["status"] == "pass"
        and count_gate["status"] == "pass"
        and staged_gate["status"] == "pass"
    )
    print("SELFTEST_OK" if ok else "SELFTEST_FAIL",
          "| overall=%s | ir_schema=%s count=%s staged=%s"
          % (report["status"], ir_schema["status"],
             count_gate["status"], staged_gate["status"]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_selftest())
