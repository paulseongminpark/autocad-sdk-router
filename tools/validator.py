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

Every gate record carries a stable NAME field ``gate`` (string id, mirrors
``id`` which is kept for validation_report.v1 schema conformance), a ``status``,
and a ``detail`` string (mirrors ``message``). Gates whose inputs are simply
absent SKIP cleanly (status ``skipped`` + ``skip_benign`` true) and do NOT
downgrade the overall verdict -- only a REQUIRED gate that actually fails/blocks,
or a non-required gate that genuinely fails/partials, lowers the verdict.

Patch/diff gates (added for M02): pass ``patch_path=`` and/or ``diff_path=`` (or
``run_dir=`` containing a patch run) to fire the cad_diff/cad_patch gates. With a
plain IR and no patch/diff inputs those gates skip benignly.

Public API:
    validate_target(ir_path=None, run_dir=None, patch_path=None, diff_path=None)
        -> dict   # validation_report.v1

CLI:
    python tools/validator.py                 # validate inline fixture IR (selftest)
    python tools/validator.py --run <dir>     # validate a run/patch folder
    python tools/validator.py --ir <ir.json>  # validate a specific IR document
    python tools/validator.py --latest        # validate the most recent runs/* folder
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
CAD_DIFF_SCHEMA_ID = "ariadne.cad_diff.v1"
CAD_PATCH_SCHEMA_ID = "ariadne.cad_patch.v1"

_SCHEMAS_DIR = os.path.join(_ROUTER_HOME, "schemas")
_CAD_DIFF_SCHEMA_PATH = os.path.join(_SCHEMAS_DIR, "cad_diff.v1.schema.json")
_CAD_PATCH_SCHEMA_PATH = os.path.join(_SCHEMAS_DIR, "cad_patch.v1.schema.json")

# jsonschema is OPTIONAL. The validator is stdlib-only by contract, so a
# structural fallback is always available; when jsonschema happens to be present
# we additionally run a full schema validation for stronger evidence. A missing
# jsonschema degrades to structural checks (never a crash, never a fake pass).
try:  # _import_optional pattern (truthful degradation)
    import jsonschema as _jsonschema  # type: ignore
except Exception:  # noqa: BLE001
    _jsonschema = None  # type: ignore

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
    skip_benign: bool = False,
) -> Dict[str, Any]:
    """Build one validation_report gate object (schema $defs/gate).

    Every record carries a stable NAME field ``gate`` (mirrors ``id``) AND a
    ``status`` AND a ``detail`` string (mirrors ``message``) so a downstream
    consumer can key on ``gate`` and read ``detail`` regardless of the legacy
    ``id``/``message`` pair (both retained for schema conformance + back-compat).

    ``skip_benign`` marks a gate that did nothing wrong -- its input was simply
    not supplied (status ``skipped``). Such gates do NOT downgrade the overall
    verdict (see ``_roll_up_status``).
    """
    g: Dict[str, Any] = {
        "id": gid,
        "gate": gid,        # stable NAME field (alias of id) required by M02
        "status": status,
        "required": required,
    }
    if description:
        g["description"] = description
    if expected is not None:
        g["expected"] = expected
    if actual is not None:
        g["actual"] = actual
    if operator is not None:
        g["operator"] = operator
    # ``detail`` is the M02 stable explanation field; ``message`` kept for
    # back-compat. Always emit ``detail`` (possibly empty) so the field is stable.
    g["message"] = message
    g["detail"] = message
    if evidence_ref is not None:
        g["evidence_ref"] = evidence_ref
    if skip_benign:
        g["skip_benign"] = True
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
    desc = "run folder contains the expected artifacts (cadctl inspect OR patch run)"
    inspect_required = ["cad_job.json", "cad_result.json", "dwg_graph_ir.json"]
    if not run_dir:
        return _gate(gid, "skipped", description=desc, operator="exists",
                     expected=inspect_required,
                     message="no run_dir supplied; artifact gate skipped",
                     required=False, skip_benign=True)
    if not os.path.isdir(run_dir):
        return _gate(gid, "fail", description=desc, operator="exists",
                     expected=inspect_required, actual="run_dir does not exist",
                     message="run_dir not found: %s" % run_dir,
                     evidence_ref=run_dir)
    # A patch run carries patch.json + cad_diff.json at top level (its cadctl
    # inspect artifacts live in pre/ + apply/ subdirs); an inspect run carries the
    # cadctl artifacts at top level. Require the set that matches the run type so a
    # patch run is not failed for lacking cad_job.json / cad_result.json.
    if os.path.isfile(os.path.join(run_dir, "patch.json")):
        required = ["patch.json", "cad_diff.json", "journal.json", "staged_output.dwg"]
        desc = ("patch run folder contains patch.json, cad_diff.json, journal.json, "
                "staged_output.dwg")
    else:
        required = inspect_required
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
        return _gate(gid, "skipped", description=desc, operator="exists",
                     expected=expected,
                     message="no run_dir supplied; completeness gate skipped",
                     required=False, skip_benign=True)
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
    # A patch run captures stdout/stderr inside per-phase subdirs (pre/ apply/
    # post/), not at the top level. Accept command evidence found one level down.
    if not (have_stdout and have_stderr):
        for n in names:
            sub = os.path.join(run_dir, n)
            if not os.path.isdir(sub):
                continue
            try:
                subnames = [s.lower() for s in os.listdir(sub)]
            except OSError:
                continue
            if any(s.startswith("stdout") for s in subnames):
                have_stdout = True
            if any(s.startswith("stderr") for s in subnames):
                have_stderr = True
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
# Schema-conformance helper (jsonschema if present, else structural)
# --------------------------------------------------------------------------- #

def _schema_conforms(doc: Any, schema_path: str) -> Tuple[bool, str, str]:
    """
    Check ``doc`` against the JSON-Schema at ``schema_path``.

    Returns (ok, basis, detail) where basis is "jsonschema" when the optional
    jsonschema package validated it, else "structural" (required-keys walk).
    Never raises: a load/validation problem returns (False, basis, reason).
    """
    if _jsonschema is not None and os.path.isfile(schema_path):
        try:
            schema = _load_json(schema_path)
            _jsonschema.validate(instance=doc, schema=schema)  # type: ignore[union-attr]
            return True, "jsonschema", "validated against %s" % os.path.basename(schema_path)
        except Exception as exc:  # noqa: BLE001  (jsonschema.ValidationError et al.)
            # Compact the error: first line only (avoid dumping a huge trace).
            first = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
            return False, "jsonschema", "schema violation: %s" % first[:400]

    # Structural fallback: load the schema's top-level required[] and confirm the
    # doc is an object carrying each required key. Deterministic, stdlib-only.
    if os.path.isfile(schema_path):
        try:
            schema = _load_json(schema_path)
        except (OSError, ValueError) as exc:
            return False, "structural", "could not read schema: %s" % exc
        required = schema.get("required") or []
        if not isinstance(doc, dict):
            return False, "structural", "document is not an object"
        missing = [k for k in required if k not in doc]
        if missing:
            return False, "structural", "missing required keys: %s" % ", ".join(missing)
        return True, "structural", "carries required keys: %s" % ", ".join(required)

    # No schema file at all -> minimal structural sanity (object).
    if not isinstance(doc, dict):
        return False, "structural", "document is not an object (schema file absent)"
    return True, "structural", "schema file absent; minimal object check only"


# --------------------------------------------------------------------------- #
# Patch/diff loading + run-folder discovery (pure, read-only)
# --------------------------------------------------------------------------- #

def _coerce_doc(value: Any, encoding: str = _JSON_ENCODING) -> Tuple[Optional[Dict[str, Any]], str, Optional[str]]:
    """
    Accept either a dict (already-loaded doc) or a path string. Returns
    (doc_or_None, ref_string, error_or_None). A dict yields ref "<in-memory>".
    """
    if value is None:
        return None, "", None
    if isinstance(value, dict):
        return value, "<in-memory>", None
    if isinstance(value, str):
        if not os.path.isfile(value):
            return None, value, "path not found: %s" % value
        try:
            return _load_json(value), value, None
        except (OSError, ValueError) as exc:
            return None, value, "failed to read %s: %s" % (value, exc)
    return None, str(value), "unsupported document type: %s" % type(value).__name__


def _discover_diff_in_run(run_dir: Optional[str]) -> Optional[str]:
    """Find a cad_diff document in a run folder (cad_diff.json or *_diff.json)."""
    if not run_dir or not os.path.isdir(run_dir):
        return None
    candidates = ["cad_diff.json", "diff.json"]
    for name in candidates:
        p = os.path.join(run_dir, name)
        if os.path.isfile(p):
            return p
    try:
        for name in sorted(os.listdir(run_dir)):
            if name.lower().endswith("_diff.json") or name.lower().endswith(".diff.json"):
                return os.path.join(run_dir, name)
    except OSError:
        return None
    return None


def _discover_patch_in_run(run_dir: Optional[str]) -> Optional[str]:
    """Find a cad_patch document in a run folder (cad_patch.json / patch.json)."""
    if not run_dir or not os.path.isdir(run_dir):
        return None
    for name in ("cad_patch.json", "patch.json"):
        p = os.path.join(run_dir, name)
        if os.path.isfile(p):
            return p
    return None


def _load_journal(run_dir: Optional[str]) -> Optional[Dict[str, Any]]:
    """Load journal.json from a patch run folder, if present."""
    if not run_dir or not os.path.isdir(run_dir):
        return None
    p = os.path.join(run_dir, "journal.json")
    if not os.path.isfile(p):
        return None
    try:
        return _load_json(p)
    except (OSError, ValueError):
        return None


def _is_patch_run(run_dir: Optional[str], patch: Optional[Dict[str, Any]],
                  diff: Optional[Dict[str, Any]], journal: Optional[Dict[str, Any]]) -> bool:
    """True when there is any evidence this run_dir is a PATCH run (vs a plain
    read/inspect run): a patch doc, a diff doc, a journal, or staged_*.dwg."""
    if patch is not None or diff is not None or journal is not None:
        return True
    if run_dir and os.path.isdir(run_dir):
        try:
            names = {n.lower() for n in os.listdir(run_dir)}
        except OSError:
            names = set()
        if "staged_input.dwg" in names or "staged_output.dwg" in names:
            return True
        if "cad_patch.json" in names or "patch.json" in names:
            return True
    return False


# --------------------------------------------------------------------------- #
# Patch/diff gates (M02) -- each pure: (inputs) -> gate dict
# --------------------------------------------------------------------------- #

def _gate_cad_diff_schema(diff: Optional[Dict[str, Any]], diff_ref: Optional[str],
                          diff_err: Optional[str]) -> Dict[str, Any]:
    gid = "cad_diff_schema"
    desc = "diff parses and conforms to cad_diff.v1 (structural if jsonschema absent)"
    if diff is None and diff_err is None:
        return _gate(gid, "skipped", description=desc, operator="exists",
                     expected=CAD_DIFF_SCHEMA_ID,
                     message="no diff supplied; cad_diff schema gate skipped",
                     required=False, skip_benign=True)
    if diff is None:
        return _gate(gid, "fail", description=desc, operator="exists",
                     expected=CAD_DIFF_SCHEMA_ID, actual=None,
                     message="diff could not be loaded: %s" % diff_err,
                     evidence_ref=diff_ref)
    ok, basis, detail = _schema_conforms(diff, _CAD_DIFF_SCHEMA_PATH)
    schema_tag = diff.get("schema")
    tag_ok = schema_tag == CAD_DIFF_SCHEMA_ID
    if ok and tag_ok:
        return _gate(gid, "pass", description=desc, operator="eq",
                     expected=CAD_DIFF_SCHEMA_ID, actual=schema_tag,
                     message="%s (%s)" % (detail, basis), evidence_ref=diff_ref)
    parts = []
    if not tag_ok:
        parts.append("schema tag=%r != %s" % (schema_tag, CAD_DIFF_SCHEMA_ID))
    if not ok:
        parts.append(detail)
    return _gate(gid, "fail", description=desc, operator="eq",
                 expected=CAD_DIFF_SCHEMA_ID, actual=schema_tag,
                 message="; ".join(parts) + " [%s]" % basis, evidence_ref=diff_ref)


def _diff_change_counts(diff: Dict[str, Any]) -> Tuple[int, int, int]:
    """Return (created, modified, deleted) from a cad_diff, preferring summary
    counts and falling back to counting changed_handles by change kind."""
    summ = diff.get("summary") or {}
    created = summ.get("added")
    modified = summ.get("modified")
    deleted = summ.get("removed")
    if all(isinstance(x, int) for x in (created, modified, deleted)):
        return created, modified, deleted
    # Fallback: count from changed_handles.
    c = m = d = 0
    for ch in diff.get("changed_handles") or []:
        if not isinstance(ch, dict):
            continue
        kind = ch.get("change")
        if kind == "added":
            c += 1
        elif kind == "modified":
            m += 1
        elif kind == "removed":
            d += 1
    return c, m, d


def _gate_diff_expected_changes(diff: Optional[Dict[str, Any]], diff_ref: Optional[str],
                                diff_err: Optional[str]) -> Dict[str, Any]:
    gid = "diff_expected_changes"
    desc = ("diff records >=1 created/modified/deleted "
            "(a patch that produced NO diff is NOT a success)")
    if diff is None and diff_err is None:
        return _gate(gid, "skipped", description=desc, operator="ge",
                     expected=">=1 change",
                     message="no diff supplied; expected-changes gate skipped",
                     required=False, skip_benign=True)
    if diff is None:
        return _gate(gid, "blocked", description=desc, operator="ge",
                     expected=">=1 change",
                     message="diff could not be loaded: %s" % diff_err,
                     evidence_ref=diff_ref)
    created, modified, deleted = _diff_change_counts(diff)
    total = created + modified + deleted
    ok = total >= 1
    return _gate(
        gid, "pass" if ok else "fail", description=desc, operator="ge",
        expected=">=1 change",
        actual={"created": created, "modified": modified, "deleted": deleted, "total": total},
        message="%d change(s): +%d ~%d -%d" % (total, created, modified, deleted)
                if ok else "diff has zero changes -- the patch produced no effect",
        evidence_ref=diff_ref,
    )


def _patch_expected_handles(patch: Optional[Dict[str, Any]]) -> Optional[set]:
    """Best-effort set of handles a patch declares it will touch (from op args
    that name a 'handle'/'handles'). Returns None when nothing is declared."""
    if not isinstance(patch, dict):
        return None
    declared: set = set()
    found_any = False
    for op in patch.get("operations") or []:
        if not isinstance(op, dict):
            continue
        args = op.get("args") or {}
        if isinstance(args, dict):
            if isinstance(args.get("handle"), str):
                declared.add(args["handle"].upper())
                found_any = True
            hs = args.get("handles")
            if isinstance(hs, list):
                for h in hs:
                    if isinstance(h, str):
                        declared.add(h.upper())
                        found_any = True
    return declared if found_any else None


def _gate_no_unrelated_changes(diff: Optional[Dict[str, Any]], diff_ref: Optional[str],
                               diff_err: Optional[str],
                               patch: Optional[Dict[str, Any]],
                               patch_path: Optional[str]) -> Dict[str, Any]:
    gid = "no_unrelated_changes"
    desc = ("modified/deleted handles fall within the patch's declared "
            "expectation when a patch is given (else informational)")
    if diff is None and diff_err is None:
        return _gate(gid, "skipped", description=desc, operator="eq",
                     message="no diff supplied; unrelated-changes gate skipped",
                     required=False, skip_benign=True)
    if diff is None:
        return _gate(gid, "blocked", description=desc,
                     message="diff could not be loaded: %s" % diff_err,
                     evidence_ref=diff_ref, required=False)

    # Handles the diff reports as modified or removed (these are the ones a patch
    # could "unrelatedly" touch; additions are new geometry and are expected).
    touched: List[str] = []
    for ch in diff.get("changed_handles") or []:
        if isinstance(ch, dict) and ch.get("change") in ("modified", "removed"):
            h = ch.get("handle")
            if isinstance(h, str):
                touched.append(h.upper())

    declared = _patch_expected_handles(patch) if patch is not None else None
    if patch is None or declared is None:
        # No patch (or patch declares no explicit handles): informational only.
        return _gate(
            gid, "pass", description=desc, operator="eq",
            expected="informational (no per-handle expectation declared)",
            actual={"modified_or_removed": sorted(set(touched))},
            message="informational: %d modified/removed handle(s); no declared "
                    "per-handle expectation to enforce" % len(set(touched)),
            required=False, evidence_ref=diff_ref or patch_path,
        )

    unrelated = sorted(set(touched) - declared)
    ok = not unrelated
    # Non-required: an out-of-scope touch downgrades to partial (a scope warning),
    # not a hard fail -- the task frames this gate as informational/advisory.
    return _gate(
        gid, "pass" if ok else "fail", description=desc, operator="eq",
        expected={"within_declared_handles": sorted(declared)},
        actual={"modified_or_removed": sorted(set(touched)), "unrelated": unrelated},
        message="all modified/removed handles are within the patch's declared set"
                if ok else "patch touched handles it did not declare: %s"
                % ", ".join(unrelated),
        required=False,
        evidence_ref=diff_ref or patch_path,
    )


def _gate_patch_policy(patch: Optional[Dict[str, Any]], patch_path: Optional[str],
                       patch_err: Optional[str]) -> Dict[str, Any]:
    gid = "patch_policy"
    desc = ("patch (cad_patch.v1) declares allow_original_write false "
            "(policy.staged_copy true + safe write_mode)")
    if patch is None and patch_err is None:
        return _gate(gid, "skipped", description=desc, operator="eq",
                     message="no patch supplied; patch-policy gate skipped",
                     required=False, skip_benign=True)
    if patch is None:
        return _gate(gid, "fail", description=desc, operator="eq",
                     message="patch could not be loaded: %s" % patch_err,
                     evidence_ref=patch_path)

    pol = patch.get("policy") or {}
    staged_copy = pol.get("staged_copy")
    write_mode = pol.get("write_mode", "write_copy")
    # allow_original_write may be expressed explicitly or implied by write_mode.
    explicit_allow = pol.get("allow_original_write", False) is True
    targets_original = write_mode in ("write_original", "live_edit") or explicit_allow

    tgt = patch.get("target_dwg") or {}
    staged = tgt.get("staged_path")
    original = tgt.get("original_path")
    staged_distinct = isinstance(staged, str) and staged.strip() != "" and (
        not isinstance(original, str)
        or os.path.normcase(os.path.normpath(staged)) != os.path.normcase(os.path.normpath(original))
    )

    ok = (staged_copy is True) and (not targets_original) and staged_distinct
    parts = []
    if staged_copy is not True:
        parts.append("policy.staged_copy != true")
    if targets_original:
        parts.append("write level targets the original (write_mode=%s, allow_original_write=%s)"
                     % (write_mode, explicit_allow))
    if not staged_distinct:
        parts.append("staged_path missing or equals original_path")
    return _gate(
        gid, "pass" if ok else "fail", description=desc, operator="eq",
        expected={"staged_copy": True, "allow_original_write": False},
        actual={"staged_copy": staged_copy, "write_mode": write_mode,
                "allow_original_write": explicit_allow,
                "staged_path": staged, "original_path": original},
        message="staged write, original protected" if ok else "; ".join(parts),
        evidence_ref=patch_path,
    )


def _gate_staged_copy_used(run_dir: Optional[str], is_patch_run: bool) -> Dict[str, Any]:
    gid = "staged_copy_used"
    desc = "patch run folder contains staged_input.dwg / staged_output.dwg"
    if not run_dir:
        return _gate(gid, "skipped", description=desc, operator="exists",
                     message="no run_dir supplied; staged-copy gate skipped",
                     required=False, skip_benign=True)
    if not is_patch_run:
        return _gate(gid, "skipped", description=desc, operator="exists",
                     message="run_dir is not a patch run; staged-copy gate skipped",
                     required=False, skip_benign=True, evidence_ref=run_dir)
    if not os.path.isdir(run_dir):
        return _gate(gid, "fail", description=desc, operator="exists",
                     actual="run_dir does not exist",
                     message="run_dir not found: %s" % run_dir, evidence_ref=run_dir)
    try:
        names = {n.lower() for n in os.listdir(run_dir)}
    except OSError as exc:
        return _gate(gid, "blocked", description=desc,
                     message="could not list run_dir: %s" % exc, evidence_ref=run_dir)
    have_in = "staged_input.dwg" in names
    have_out = "staged_output.dwg" in names
    ok = have_in and have_out
    missing = [n for n, have in (("staged_input.dwg", have_in),
                                 ("staged_output.dwg", have_out)) if not have]
    return _gate(
        gid, "pass" if ok else "fail", description=desc, operator="exists",
        expected=["staged_input.dwg", "staged_output.dwg"],
        actual=sorted(n for n in ("staged_input.dwg", "staged_output.dwg")
                      if n in names),
        message="staged copies present" if ok else "missing: %s" % ", ".join(missing),
        evidence_ref=run_dir,
    )


def _gate_journal_present(journal: Optional[Dict[str, Any]], run_dir: Optional[str],
                          is_patch_run: bool) -> Dict[str, Any]:
    gid = "journal_present"
    desc = "patch run folder records a journal.json"
    if not run_dir or not is_patch_run:
        return _gate(gid, "skipped", description=desc, operator="exists",
                     message="not a patch run; journal gate skipped",
                     required=False, skip_benign=True,
                     evidence_ref=run_dir if run_dir else None)
    if journal is None:
        return _gate(gid, "fail", description=desc, operator="exists",
                     expected="journal.json",
                     message="patch run folder has no readable journal.json",
                     evidence_ref=run_dir)
    return _gate(gid, "pass", description=desc, operator="exists",
                 expected="journal.json", actual="present",
                 message="journal.json present", evidence_ref=run_dir)


def _journal_original_sha(journal: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Recover (sha_before, sha_after) of the ORIGINAL DWG from a journal, across
    a few plausible field layouts. Returns (None, None) when absent."""
    # Layout A: top-level original_sha256_before / _after.
    b = journal.get("original_sha256_before")
    a = journal.get("original_sha256_after")
    if isinstance(b, str) or isinstance(a, str):
        return (b if isinstance(b, str) else None,
                a if isinstance(a, str) else None)
    # Layout B: nested under 'original' / 'original_dwg'.
    for key in ("original", "original_dwg", "source"):
        node = journal.get(key)
        if isinstance(node, dict):
            nb = node.get("sha256_before") or node.get("sha_before") or node.get("sha256")
            na = node.get("sha256_after") or node.get("sha_after")
            if isinstance(nb, str) or isinstance(na, str):
                return (nb if isinstance(nb, str) else None,
                        na if isinstance(na, str) else None)
    return None, None


def _gate_original_dwg_unchanged(journal: Optional[Dict[str, Any]], run_dir: Optional[str],
                                 is_patch_run: bool) -> Dict[str, Any]:
    gid = "original_dwg_unchanged"
    desc = "journal records original DWG sha256 before == after (read-only honored)"
    if not run_dir or not is_patch_run:
        return _gate(gid, "skipped", description=desc, operator="eq",
                     message="not a patch run; original-unchanged gate skipped",
                     required=False, skip_benign=True,
                     evidence_ref=run_dir if run_dir else None)
    if journal is None:
        return _gate(gid, "skipped", description=desc, operator="eq",
                     message="no journal.json; original-unchanged gate skipped "
                             "(see journal_present)",
                     required=False, skip_benign=True, evidence_ref=run_dir)
    before, after = _journal_original_sha(journal)
    if before is None and after is None:
        return _gate(gid, "skipped", description=desc, operator="eq",
                     message="journal records no original sha256 before/after; "
                             "original-unchanged gate skipped",
                     required=False, skip_benign=True, evidence_ref=run_dir)
    ok = (before is not None) and (after is not None) and (before == after)
    return _gate(
        gid, "pass" if ok else "fail", description=desc, operator="eq",
        expected={"sha256_before == sha256_after": True},
        actual={"before": before, "after": after},
        message="original DWG sha256 unchanged across the patch" if ok
                else "original DWG sha256 CHANGED (before != after) -- read-only "
                     "invariant violated",
        evidence_ref=run_dir,
    )


# Coverage-section name -> where its realized collection lives in the IR.
# 'st:<key>' means symbol_tables[<key>]; 'top:<key>' means ir[<key>].
_SECTION_LOCATION: Dict[str, str] = {
    "layers": "st:layers",
    "linetypes": "st:linetypes",
    "text_styles": "st:text_styles",
    "dim_styles": "st:dim_styles",
    "block_table_records": "st:block_table_records",
    "ucs": "st:ucs",
    "views": "st:views",
    "viewports": "st:viewports",
    "registered_apps": "st:app_ids",
    "app_ids": "st:app_ids",
    "entities": "top:entities",
    "block_definitions": "top:block_definitions",
    "block_references": "top:block_references",
    "layouts": "top:layouts",
    "dictionaries": "top:dictionaries",
    "xrecords": "top:xrecords",
    "xrefs": "top:xrefs",
}


def _resolve_section(ir: Dict[str, Any], name: str) -> Tuple[bool, Optional[int]]:
    """Return (present, size) for a coverage section.

    present == True  -> the IR actually emitted the key (even if empty list/dict).
    present == False -> the key is missing entirely.
    size is len() when the value is a list/dict, else None.
    A section we don't know how to locate returns (True, None) (not asserted on).
    """
    loc = _SECTION_LOCATION.get(name)
    if loc is None:
        return True, None  # unknown section -> do not assert
    where, key = loc.split(":", 1)
    container = (ir.get("symbol_tables") or {}) if where == "st" else ir
    if key not in container:
        return False, None
    v = container.get(key)
    if isinstance(v, (list, dict)):
        return True, len(v)
    return True, None


def _no_fake_success_offenders(ir: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find genuine fake-success contradictions (deterministic, no heuristics):

      * a section marked 'implemented' whose IR key is ENTIRELY ABSENT
        (the producer claimed to implement a section it never emitted), OR
      * a coverage that asserts modelspace_count_from_native but the realized
        entities length disagrees (a claimed-but-unbacked entity count).

    A section that is present-but-empty (e.g. xrefs == [] for a drawing with no
    external references) is HONEST and is NOT flagged -- 'implemented' means the
    extractor processed the section, and an empty result is a truthful result.
    """
    diag = ir.get("diagnostics") or {}
    cov = diag.get("coverage") or {}
    offenders: List[Dict[str, Any]] = []

    sec_status = cov.get("section_status") or {}
    if isinstance(sec_status, dict):
        for name, status in sec_status.items():
            if status != "implemented":
                continue
            present, _size = _resolve_section(ir, name)
            if not present:
                offenders.append({
                    "section": name,
                    "reason": "marked implemented but IR emitted no such key",
                })

    # Cross-check: a native modelspace count that the entities list does not back.
    claimed = cov.get("modelspace_count_from_native")
    entities = ir.get("entities")
    if isinstance(claimed, int) and isinstance(entities, list):
        if claimed != len(entities):
            offenders.append({
                "section": "entities",
                "reason": "coverage.modelspace_count_from_native=%d but "
                          "len(entities)=%d" % (claimed, len(entities)),
            })

    return offenders


def _gate_no_fake_success(ir: Optional[Dict[str, Any]], ir_path: Optional[str]) -> Dict[str, Any]:
    gid = "no_fake_success"
    desc = ("IR coverage flags do not claim 'implemented' for a section the IR "
            "never emitted, nor assert an entity count the entities[] cannot back "
            "(no-fake-success; present-but-empty is honest)")
    if ir is None:
        return _gate(gid, "skipped", description=desc, operator="eq",
                     message="no IR supplied; no-fake-success gate skipped",
                     required=False, skip_benign=True)
    offenders = _no_fake_success_offenders(ir)
    ok = not offenders
    return _gate(
        gid, "pass" if ok else "fail", description=desc, operator="eq",
        expected="no implemented-but-absent section; entity count is backed",
        actual={"contradictions": offenders},
        message="coverage flags are honest (no fake-success contradiction)"
                if ok else "fake-success contradiction(s): %s"
                % "; ".join("%s (%s)" % (o["section"], o["reason"]) for o in offenders),
        evidence_ref=ir_path,
    )


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def _roll_up_status(gates: List[Dict[str, Any]]) -> str:
    """
    Overall verdict per validation_report.v1 semantics:
      * any REQUIRED gate fail/blocked -> fail / blocked
      * else any non-required fail/partial, or any NON-benign blocked/skip -> partial
      * else pass

    BENIGN skips (``skip_benign`` true: a gate whose input was simply not
    supplied) never downgrade the verdict -- a plain-IR validation that supplies
    no run_dir/patch/diff still rolls up to ``pass`` when every required gate
    passed. A ``blocked``/``skipped`` gate WITHOUT ``skip_benign`` (it tried and
    couldn't) still downgrades to ``partial`` (no-fake-success).
    """
    required_fail = any(g["status"] == "fail" and g.get("required", True) for g in gates)
    required_blocked = any(g["status"] == "blocked" and g.get("required", True) for g in gates)
    if required_fail:
        return "fail"
    if required_blocked:
        return "blocked"
    soft_problem = any(
        (g["status"] in ("fail", "partial") and not g.get("required", True))
        or (g["status"] in ("blocked", "skipped") and not g.get("skip_benign", False))
        for g in gates
    )
    return "partial" if soft_problem else "pass"


def validate_target(ir_path: Optional[str] = None,
                    run_dir: Optional[str] = None,
                    patch_path: Optional[Any] = None,
                    diff_path: Optional[Any] = None) -> Dict[str, Any]:
    """
    Run all deterministic gates over an IR document, a run folder, and/or a
    cad_patch + cad_diff pair.

    Args:
        ir_path:    path to an ariadne.dwg_graph_ir.v1 document.
        run_dir:    a run/patch folder (may carry cad_job/result/ir, staged_*.dwg,
                    journal.json, and a cad_diff/cad_patch). Patch/diff/journal are
                    auto-discovered here when not passed explicitly.
        patch_path: path to (or already-loaded dict of) an ariadne.cad_patch.v1.
        diff_path:  path to (or already-loaded dict of) an ariadne.cad_diff.v1.

    Inputs that are absent SKIP their gates benignly (status ``skipped`` +
    ``skip_benign``) and do NOT downgrade the verdict; a gate that tries and
    cannot run reports ``blocked``/``fail`` (never a fake ``pass``).

    Plain-IR behavior (ir_path set, no run_dir/patch/diff) is unchanged for the
    read surface: the IR gates run and the patch/diff/run gates skip benignly.

    Returns an ``ariadne.validation_report.v1`` dict.
    """
    errors: List[str] = []
    warnings: List[str] = []
    artifacts: List[Dict[str, Any]] = []

    if ir_path is None and run_dir is not None:
        ir_path = _ir_in_run(run_dir)

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

    # ---- resolve patch / diff (explicit arg, else auto-discover in run_dir) ----
    diff_doc, diff_ref, diff_err = _coerce_doc(diff_path)
    if diff_doc is None and diff_err is None and run_dir:
        discovered = _discover_diff_in_run(run_dir)
        if discovered:
            diff_doc, diff_ref, diff_err = _coerce_doc(discovered)
    if diff_doc is not None:
        artifacts.append({"kind": "diff", "ref": diff_ref})
    if diff_err:
        errors.append("diff load: %s" % diff_err)

    patch_doc, patch_ref, patch_err = _coerce_doc(patch_path)
    if patch_doc is None and patch_err is None and run_dir:
        discovered = _discover_patch_in_run(run_dir)
        if discovered:
            patch_doc, patch_ref, patch_err = _coerce_doc(discovered)
    if patch_doc is not None:
        artifacts.append({"kind": "patch", "ref": patch_ref})
    if patch_err:
        errors.append("patch load: %s" % patch_err)

    journal = _load_journal(run_dir)
    is_patch_run = _is_patch_run(run_dir, patch_doc, diff_doc, journal)

    # Normalize a string patch_ref/diff_ref for evidence (in-memory dicts have no path).
    diff_ev = diff_ref if (diff_ref and diff_ref != "<in-memory>") else None
    patch_ev = patch_ref if (patch_ref and patch_ref != "<in-memory>") else None

    gates: List[Dict[str, Any]] = [
        # --- existing IR / run gates (preserved) ---
        _gate_ir_schema_present(ir, ir_path),
        _gate_entity_count_consistency(ir, ir_path),
        _gate_required_artifacts_exist(run_dir),
        _gate_no_original_write_evidence(ir, run_dir),
        _gate_registry_status_consistency(),
        _gate_run_folder_completeness(run_dir),
        # --- M02 patch/diff gates (skip benignly when their input is absent) ---
        _gate_cad_diff_schema(diff_doc, diff_ev, diff_err),
        _gate_diff_expected_changes(diff_doc, diff_ev, diff_err),
        _gate_no_unrelated_changes(diff_doc, diff_ev, diff_err, patch_doc, patch_ev),
        _gate_patch_policy(patch_doc, patch_ev, patch_err),
        _gate_staged_copy_used(run_dir, is_patch_run),
        _gate_journal_present(journal, run_dir, is_patch_run),
        _gate_original_dwg_unchanged(journal, run_dir, is_patch_run),
        _gate_no_fake_success(ir, ir_path),
    ]

    for g in gates:
        if g["status"] == "fail" and g.get("message"):
            errors.append("[%s] %s" % (g["id"], g["message"]))
        elif (g["status"] in ("blocked", "partial", "skipped")
              and g.get("message") and not g.get("skip_benign", False)):
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
            "gates_skipped_benign": sum(1 for g in gates if g.get("skip_benign")),
            "gates_blocked": sum(1 for g in gates if g["status"] == "blocked"),
            "schema_check_basis": "jsonschema" if _jsonschema is not None else "structural",
            "is_patch_run": is_patch_run,
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


def _make_synthetic_diff() -> Dict[str, Any]:
    """A minimal, schema-conformant cad_diff.v1 with exactly one created entity.
    Used by the self-test to fire the patch/diff gates deterministically."""
    return {
        "schema": CAD_DIFF_SCHEMA_ID,
        "diff_id": "diff-selftest-0001",
        "patch_id": "patch-selftest-0001",
        "before_ref": {"kind": "ir", "ref": "before.json", "entity_count": 2},
        "after_ref": {"kind": "ir", "ref": "after.json", "entity_count": 3},
        "changed_handles": [
            {"handle": "3C", "change": "added", "dxf_name": "LINE", "layer": "DIM"},
        ],
        "summary": {
            "added": 1, "removed": 0, "modified": 0, "unchanged": 2,
            "entity_count_before": 2, "entity_count_after": 3,
            "by_type": {"LINE": {"added": 1, "removed": 0, "modified": 0}},
        },
        "diagnostics": {"comparison_basis": "handle", "warnings": [], "errors": []},
    }


def _gate_by_name(report: Dict[str, Any], gate_name: str) -> Optional[Dict[str, Any]]:
    for g in report["gates"]:
        if g.get("gate") == gate_name or g.get("id") == gate_name:
            return g
    return None


def _selftest() -> int:
    import tempfile

    tmpdir = tempfile.mkdtemp(prefix="validator_selftest_")
    ir = _fixture_ir()
    ir_path = os.path.join(tmpdir, "dwg_graph_ir.json")
    with open(ir_path, "w", encoding="utf-8") as fh:
        json.dump(ir, fh, indent=2)

    # ---- Phase 1: plain IR, no run/patch/diff -> overall pass, gates skip benign.
    report = validate_target(ir_path=ir_path, run_dir=None)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    ir_schema = _gate_by_name(report, "ir_schema_present")
    count_gate = _gate_by_name(report, "entity_count_consistency")
    staged_gate = _gate_by_name(report, "no_original_write_evidence")
    nofake_gate = _gate_by_name(report, "no_fake_success")

    # Every gate must carry a stable 'gate' id AND a 'detail' field.
    all_have_gate_id = all(isinstance(g.get("gate"), str) and g["gate"] for g in report["gates"])
    all_have_detail = all("detail" in g for g in report["gates"])

    ok = (
        report["schema"] == SCHEMA_ID
        and report["status"] == "pass"            # benign skips no longer downgrade
        and ir_schema["status"] == "pass"
        and count_gate["status"] == "pass"
        and staged_gate["status"] == "pass"
        and nofake_gate["status"] == "pass"
        and all_have_gate_id
        and all_have_detail
    )

    # ---- Phase 2: synthetic diff -> the diff gates must FIRE (pass).
    diff = _make_synthetic_diff()
    rep2 = validate_target(ir_path=ir_path, diff_path=diff)
    diff_schema_g = _gate_by_name(rep2, "cad_diff_schema")
    diff_changes_g = _gate_by_name(rep2, "diff_expected_changes")
    ok = ok and diff_schema_g["status"] == "pass" and diff_changes_g["status"] == "pass"

    # ---- Phase 3: an EMPTY diff (no changes) -> diff_expected_changes must FAIL
    # and force overall fail (a no-effect patch is a HARD failure, not partial).
    empty_diff = _make_synthetic_diff()
    empty_diff["changed_handles"] = []
    empty_diff["summary"].update({"added": 0, "removed": 0, "modified": 0})
    rep3 = validate_target(ir_path=ir_path, diff_path=empty_diff)
    empty_changes_g = _gate_by_name(rep3, "diff_expected_changes")
    ok = ok and empty_changes_g["status"] == "fail" and rep3["status"] == "fail"

    # ---- Phase 4: a malformed patch (write_original) -> patch_policy must FAIL
    # and force overall fail (an original-write policy is a HARD safety failure).
    bad_patch = {
        "schema": CAD_PATCH_SCHEMA_ID, "patch_id": "p-bad",
        "target_dwg": {"staged_path": os.path.join(tmpdir, "staged.dwg"),
                       "original_path": os.path.join(tmpdir, "orig.dwg")},
        "operations": [{"operation": "create_line", "args": {}}],
        "policy": {"staged_copy": True, "write_mode": "write_original"},
    }
    rep4 = validate_target(ir_path=ir_path, patch_path=bad_patch)
    policy_g = _gate_by_name(rep4, "patch_policy")
    ok = ok and policy_g["status"] == "fail" and rep4["status"] == "fail"

    print("SELFTEST_OK" if ok else "SELFTEST_FAIL",
          "| p1_overall=%s ir=%s count=%s staged=%s nofake=%s gate_ids=%s detail=%s"
          " | p2 diff_schema=%s diff_changes=%s | p3 empty=%s | p4 policy=%s"
          % (report["status"], ir_schema["status"], count_gate["status"],
             staged_gate["status"], nofake_gate["status"],
             all_have_gate_id, all_have_detail,
             diff_schema_g["status"], diff_changes_g["status"],
             empty_changes_g["status"], policy_g["status"]))
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _find_latest_run() -> Optional[str]:
    """Return the most recently modified subfolder of runs/ (or None)."""
    runs_root = os.path.join(_ROUTER_HOME, "runs")
    if not os.path.isdir(runs_root):
        return None
    subdirs = []
    try:
        for name in os.listdir(runs_root):
            p = os.path.join(runs_root, name)
            if os.path.isdir(p):
                subdirs.append((os.path.getmtime(p), p))
    except OSError:
        return None
    if not subdirs:
        return None
    subdirs.sort(reverse=True)
    return subdirs[0][1]


def _ir_in_run(run_dir: str) -> Optional[str]:
    """Locate the IR document inside a run folder, if present.

    Prefers the canonical ``dwg_graph_ir.json``, then a coverage-tagged variant
    (``dwg_graph_ir.native_full.json`` / ``...geometry_only.json``). Patch runs
    write their subject IR below ``post/``; fall back to ``pre/`` only when no
    post-apply IR exists. Finally, accept any one-level nested file whose name
    contains ``dwg_graph_ir`` and ends in ``.json``.
    """
    if not os.path.isdir(run_dir):
        return None
    preferred_names = [
        "dwg_graph_ir.json",
        "dwg_graph_ir.native_full.json",
        "dwg_graph_ir.geometry_only.json",
    ]
    for name in preferred_names:
        p = os.path.join(run_dir, name)
        if os.path.isfile(p):
            return p
    preferred_dirs = ["post", "pre"]
    for dirname in preferred_dirs:
        for name in preferred_names:
            p = os.path.join(run_dir, dirname, name)
            if os.path.isfile(p):
                return p
    try:
        for name in sorted(os.listdir(run_dir)):
            low = name.lower()
            if "dwg_graph_ir" in low and low.endswith(".json"):
                return os.path.join(run_dir, name)
            sub = os.path.join(run_dir, name)
            if os.path.isdir(sub):
                for child in sorted(os.listdir(sub)):
                    child_low = child.lower()
                    if "dwg_graph_ir" in child_low and child_low.endswith(".json"):
                        return os.path.join(sub, child)
    except OSError:
        return None
    return None


def _main(argv: List[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="validator.py",
        description="Deterministic CAD OS Layer validation gates "
                    "(emits ariadne.validation_report.v1).")
    parser.add_argument("--ir", dest="ir", default=None,
                        help="path to an ariadne.dwg_graph_ir.v1 document")
    parser.add_argument("--run", dest="run", default=None,
                        help="path to a run/patch folder to validate")
    parser.add_argument("--patch", dest="patch", default=None,
                        help="path to an ariadne.cad_patch.v1 document")
    parser.add_argument("--diff", dest="diff", default=None,
                        help="path to an ariadne.cad_diff.v1 document")
    parser.add_argument("--latest", dest="latest", action="store_true",
                        help="validate the most recently modified runs/* folder")
    parser.add_argument("--out", dest="out", default=None,
                        help="write the report JSON to this path (else stdout)")
    args = parser.parse_args(argv)

    ir_path = args.ir
    run_dir = args.run

    if args.latest:
        latest = _find_latest_run()
        if latest is None:
            print(json.dumps({"error": "no runs/* folder found under %s"
                              % os.path.join(_ROUTER_HOME, "runs")}))
            return 2
        run_dir = run_dir or latest
        if ir_path is None:
            ir_path = _ir_in_run(latest)

    # When a run folder is given without an explicit IR, use the run's IR.
    if run_dir and ir_path is None:
        ir_path = _ir_in_run(run_dir)

    if ir_path is None and run_dir is None and args.patch is None and args.diff is None:
        # No target at all -> run the inline self-test (back-compat with bare run).
        return _selftest()

    report = validate_target(ir_path=ir_path, run_dir=run_dir,
                             patch_path=args.patch, diff_path=args.diff)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("wrote %s (status=%s)" % (args.out, report["status"]))
    else:
        print(text)
    return 0 if report["status"] in ("pass", "partial") else 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
