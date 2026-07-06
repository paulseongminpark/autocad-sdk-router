#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cad_op_gate.py -- CAD OS Layer WAVE-0 F3: the per-op P/D roundtrip gate.

This is the P-GATE PRIMITIVE every native write op's acceptance test drives:
a small library of independently-callable checks, plus thin
``gate_roundtrip`` / ``gate_field_mutation`` orchestrators that run the right
subset of them in a fixed, documented priority order and reduce to ONE exit
code. Every function here is pure (dict-in, dict-out) and needs no live CAD
runtime -- see ``op_roundtrip_probe.py`` for the driver that feeds this module
real staged-write results.

Two halves (SS2.6 persistence classes; see ``op_dag_generate.py``)
-------------------------------------------------------------------
  P (geometry-diff=0)  -- ``gate_roundtrip``: an entity/brep/geometry_kernel
    write op is correct iff the geometry we ASKED to be written (``expected_ir``,
    built directly from the op's own args -- never a live read) and the
    geometry actually READ BACK (``actual_ir``) fingerprint-match under
    ``cad_diff.compute_diff(..., comparison_basis="geometry")`` (F1's
    handle-independent join -- a regen reissues every handle, so this is the
    ONLY honest way to ask "is the written geometry right").
  D (record-diff=0)  -- ``gate_field_mutation``: everything else (layers,
    dimstyles, xdata, ...) is tested by PERTURBING one already-populated field
    on one entity (replace its value, never inject a new key -- FAIL-CLOSED)
    and asserting the SAME-handle diff detects exactly that field on exactly
    that entity. A D-class op that can't even pass this on a synthetic,
    single-field, same-handle edit has no business being trusted on a live
    write.

Exit-code contract (EXACT; every function/CLI path returns one of these)
--------------------------------------------------------------------------
    0  OK                      -- PASS.
    1  FAIL                    -- a real, correctly-identified mismatch (e.g.
                                   a shifted coordinate on an otherwise clean
                                   roundtrip). Both sides were readable and
                                   comparable; they just disagree.
    2  ERROR                   -- usage/internal error: a required sibling
                                   module is unavailable, an argument is
                                   malformed, or the pipeline could not even
                                   be attempted (never a fake PASS instead).
    3  NOT_IMPLEMENTED         -- op/route not wired, or (via the cross-oracle
                                   leg) a field fell outside the oracle's
                                   certified set (mirrors cross_oracle.py's
                                   own EXIT_NOT_CERTIFIED, same numeric value).
    4  HOLLOW                  -- FAIL-CLOSED data loss: an absent/NULL field
                                   targeted for perturbation (replace-not-
                                   inject refuses to fabricate a value), a
                                   Rung-B corpus that never populates the
                                   field under test, a geometry fingerprint
                                   bucket collapse that makes two distinct
                                   entities indistinguishable ("degenerate
                                   dim"), a perturbed field the diff never
                                   detects (invisible data), or (via the
                                   cross-oracle leg) the independent oracle
                                   populated a field the native pipeline left
                                   absent (mirrors cross_oracle.py's own
                                   EXIT_TRIPWIRE).
    5  ORIGINAL_MUTATED        -- the original DWG's bytes changed across the
                                   probe, OR the pre-write staging setup itself
                                   risked mutating the original (same
                                   invariant, checked both before and after).
    6  UTF8                    -- a string leaf lost fidelity across the
                                   roundtrip (U+FFFD present, or a value that
                                   does not survive a lossless UTF-8 round
                                   trip).
    7  ORACLE_DISAGREE         -- the cross-oracle leg: both the independent
                                   oracle and the native pipeline populated a
                                   (kind, field) but the value multisets
                                   disagree (mirrors cross_oracle.py's own
                                   EXIT_DISAGREEMENT).
    8  IRRECONSTRUCTIBLE       -- identity check failure: a single-field,
                                   single-entity perturbation surfaced as
                                   added/removed instead of modified, as more
                                   than one modified entity, or as the WRONG
                                   entity modified -- the diff's "the single
                                   'modified' record" cannot be reconstructed
                                   back to the entity actually perturbed, so
                                   nothing else this gate found can be trusted.

Priority when more than one condition could fire in the same run (most severe
first; see ``_finalize`` / ``combine_results``): ERROR > ORIGINAL_MUTATED >
IRRECONSTRUCTIBLE > HOLLOW > ORACLE_DISAGREE > UTF8 > FAIL > NOT_IMPLEMENTED >
OK. A genuine identity break or silent data loss must never be masked by a
weaker finding; "not wired yet" is the weakest signal (it says nothing was
wrong, only that nothing was tried).

FAIL-CLOSED replace-not-inject (the D-half's core invariant)
--------------------------------------------------------------
``perturb_field_replace`` / ``validate_replace_not_inject`` enforce: (1) the
target field must already be PRESENT and non-NULL on the pre-entity -- you can
only ever REPLACE a real value, never fabricate one where none existed
(absent/NULL -> ``FieldAbsentError`` -> exit 4); (2) the post-entity's (and,
for a ``geometry.<leaf>`` field, its geometry dict's) key set must be
IDENTICAL to the pre-entity's -- a perturbation that introduces a brand-new
key instead of replacing an existing one's value is rejected
(``FieldInjectedError`` -> exit 4), because a key-injected "mutation" is not
evidence the extractor can detect a REAL field-level change; it only proves a
new key showed up.

Hard rules (mirrors cad_diff.py / cross_oracle.py / cad_refintegrity_gate.py)
--------------------------------------------------------------------------------
  * Standard library ONLY (Python 3.12). ``cad_diff`` / ``cross_oracle`` are
    imported via ``_import_optional`` (truthful sibling degradation -- this
    module's own logic never crashes if a sibling is absent; it reports
    NOT_IMPLEMENTED/ERROR instead).
  * Deterministic: no timestamps, no randomness inside any check's body.
  * No-fake-success: every degraded path returns a truthful non-OK status; a
    live-runtime leg (the cross-oracle LIVE wrapper) that cannot run reports
    exit 2/3 (mirroring cross_oracle's own EXIT_UNAVAILABLE/EXIT_NOT_CERTIFIED)
    rather than a fabricated PASS.
  * Read-only: this module never writes a DWG. ``check_original_unchanged`` /
    ``assert_staging_integrity`` only READ files to fingerprint them.

Public API:
    EXIT_OK/EXIT_FAIL/EXIT_ERROR/EXIT_NOT_IMPLEMENTED/EXIT_HOLLOW/
    EXIT_ORIGINAL_MUTATED/EXIT_UTF8/EXIT_ORACLE_DISAGREE/EXIT_IRRECONSTRUCTIBLE
    STATUS_* (string mirrors of the exit codes above)
    GateError / FieldAbsentError / FieldInjectedError
    load_ir(path) -> dict                                       # BOM-tolerant
    check_roundtrip(expected_ir, actual_ir, geometry_tolerance=..) -> dict
    check_fingerprint_discriminability(entities, geometry_tolerance=..) -> dict
    validate_replace_not_inject(pre_entity, post_entity, field_path) -> None
    perturb_field_replace(ir, handle, field_path, new_value) -> dict
    check_mutation_pair(pre_ir, post_ir, handle, field_path, ...) -> dict
    check_field_mutation(pre_ir, handle, field_path, new_value, ...) -> dict
    rung_b_population(ir, field_path, kind=None) -> dict
    rung_a_sweep(pre_ir, specs, ...) -> dict
    check_utf8_fidelity(value) -> dict
    capture_file_fingerprint(path) -> dict
    check_original_unchanged(path, fingerprint) -> dict
    assert_staging_integrity(original_path, staged_path) -> dict
    check_cross_oracle(reference_ir, native_ir, ...) -> dict
    check_cross_oracle_live(staged_dwg_path, native_ir, ...) -> dict
    gate_roundtrip(expected_ir, actual_ir, ...) -> dict
    gate_field_mutation(pre_ir, handle, field_path, new_value, ...) -> dict
    combine_results(results) -> dict

Run ``python tools/cad_op_gate.py`` for a synthetic self-demo (PASS/FAIL).
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

# --------------------------------------------------------------------------- #
# Paths / constants
# --------------------------------------------------------------------------- #

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))

SCHEMA_ID = "ariadne.cad_op_gate.v1"
IR_SCHEMA_ID = "ariadne.dwg_graph_ir.v1"

# BOM-tolerant: JSON on this box (config/status/IR) may carry a UTF-8 BOM.
_JSON_ENCODING = "utf-8-sig"

# Same value cad_diff.py / cross_oracle.py each independently define (kept
# self-contained per this tree's sibling-independence convention).
DEFAULT_GEOMETRY_TOLERANCE = 1e-6

# --------------------------------------------------------------------------- #
# Exit-code / status contract
# --------------------------------------------------------------------------- #

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_ERROR = 2
EXIT_NOT_IMPLEMENTED = 3
EXIT_HOLLOW = 4
EXIT_ORIGINAL_MUTATED = 5
EXIT_UTF8 = 6
EXIT_ORACLE_DISAGREE = 7
EXIT_IRRECONSTRUCTIBLE = 8

STATUS_OK = "ok"
STATUS_FAIL = "fail"
STATUS_ERROR = "error"
STATUS_NOT_IMPLEMENTED = "not_implemented"
STATUS_HOLLOW = "hollow"
STATUS_ORIGINAL_MUTATED = "original_mutated"
STATUS_UTF8 = "utf8_corrupt"
STATUS_ORACLE_DISAGREE = "oracle_disagree"
STATUS_IRRECONSTRUCTIBLE = "irreconstructible"

# Most-severe-first priority for combine_results/_finalize. A status not in
# this tuple (should never happen) sorts as least severe (defensive).
_SEVERITY_ORDER: Tuple[str, ...] = (
    STATUS_ERROR,
    STATUS_ORIGINAL_MUTATED,
    STATUS_IRRECONSTRUCTIBLE,
    STATUS_HOLLOW,
    STATUS_ORACLE_DISAGREE,
    STATUS_UTF8,
    STATUS_FAIL,
    STATUS_NOT_IMPLEMENTED,
    STATUS_OK,
)


class GateError(Exception):
    """Base for fail-closed perturbation-construction errors. Carries the
    exit_code the caller should surface (never crashes check_field_mutation
    itself -- callers catch this and translate it to a truthful result dict)."""
    exit_code = EXIT_ERROR
    status = STATUS_ERROR


class FieldAbsentError(GateError):
    """The target field is absent or NULL on the pre-entity -- fail-closed:
    there is nothing real to replace, so no perturbation is built."""
    exit_code = EXIT_HOLLOW
    status = STATUS_HOLLOW


class FieldInjectedError(GateError):
    """The post-entity's key set differs from the pre-entity's -- a real
    replace-in-place perturbation never adds or removes a key."""
    exit_code = EXIT_HOLLOW
    status = STATUS_HOLLOW


# --------------------------------------------------------------------------- #
# IO (BOM-tolerant, mirrors cad_diff.load_ir / cross_oracle.load_ir)
# --------------------------------------------------------------------------- #

def load_ir(path) -> Dict[str, Any]:
    """Load an IR JSON document (BOM-tolerant)."""
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _import_optional(module_name: str):
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
    try:
        return __import__(module_name)
    except Exception:  # pragma: no cover - defensive; sibling truly absent
        return None


def _sha256_file(path: str) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


# --------------------------------------------------------------------------- #
# Result combination (worst-first priority; see module docstring)
# --------------------------------------------------------------------------- #

def _severity_rank(status: Optional[str]) -> int:
    try:
        return _SEVERITY_ORDER.index(status)
    except ValueError:
        return -1  # unknown status: treat as MORE severe than everything (surface it)


def combine_results(results: Sequence[Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    """Reduce a sequence of check-result dicts to the single worst one.

    Empty / all-None input reduces to a bare OK. Ties keep the first-seen
    result at that severity (stable, deterministic). The winning dict is
    returned VERBATIM (all of its own fields) plus a ``"steps"`` key carrying
    every non-None input result, in order, for full provenance.
    """
    steps = [r for r in results if r is not None]
    if not steps:
        return {"schema": SCHEMA_ID, "status": STATUS_OK, "exit_code": EXIT_OK, "steps": []}
    worst = min(steps, key=lambda r: _severity_rank(r.get("status")))
    out = dict(worst)
    out["steps"] = steps
    out.setdefault("schema", SCHEMA_ID)
    return out


def _finalize(steps: List[Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    return combine_results(steps)


# --------------------------------------------------------------------------- #
# Field resolve/set helpers (dotted paths, e.g. "geometry.end")
# --------------------------------------------------------------------------- #

def _resolve_field(entity: Mapping[str, Any], field_path: str) -> Tuple[bool, Any]:
    """Resolve a (possibly dotted) field path. Returns (present, value)."""
    cur: Any = entity
    for part in field_path.split("."):
        if not isinstance(cur, Mapping) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def _set_field(entity: Dict[str, Any], field_path: str, value: Any) -> None:
    """Set a (possibly dotted) field path IN PLACE. Every intermediate
    container and the leaf key itself must already exist (replace-not-inject
    is enforced by the CALLER checking presence first; this setter simply
    refuses to silently create structure)."""
    parts = field_path.split(".")
    cur = entity
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            raise FieldAbsentError(
                "cannot set %r: intermediate container %r is missing/non-dict" % (field_path, part))
        cur = nxt
    last = parts[-1]
    if last not in cur:
        raise FieldAbsentError("cannot set %r: leaf key %r absent" % (field_path, last))
    cur[last] = value


def _entity_by_handle(ir: Mapping[str, Any], handle: str) -> Optional[Dict[str, Any]]:
    for e in (ir.get("entities") or []):
        if isinstance(e, dict) and e.get("handle") == handle:
            return e
    return None


# --------------------------------------------------------------------------- #
# P-gate primitive: generic geometry-basis roundtrip (comparison_basis="geometry")
# --------------------------------------------------------------------------- #

def check_roundtrip(expected_ir: Dict[str, Any], actual_ir: Dict[str, Any], *,
                    geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE,
                    cad_diff_mod=None) -> Dict[str, Any]:
    """The P-gate primitive: does the geometry we ASKED to be written
    (``expected_ir``) fingerprint-match what was actually read back
    (``actual_ir``), independent of handle (cad_diff.py's
    ``comparison_basis="geometry"``)?

    A geometry-basis diff of all-zero added/removed/modified is the
    "roundtrip diff=0" PASS. Any non-zero count is a genuine, correctly-
    identified mismatch (e.g. a shifted coordinate reports as ``modified``) --
    exit 1, FAIL (not HOLLOW: both sides were readable, they just disagree).
    """
    cd = cad_diff_mod or _import_optional("cad_diff")
    if cd is None or not hasattr(cd, "compute_diff"):
        return {"schema": SCHEMA_ID, "status": STATUS_NOT_IMPLEMENTED,
                "exit_code": EXIT_NOT_IMPLEMENTED,
                "reason": "cad_diff sibling module unavailable"}
    diff = cd.compute_diff(expected_ir, actual_ir, comparison_basis="geometry",
                           geometry_tolerance=geometry_tolerance)
    summary = diff["summary"]
    ok = (summary["added"] == 0 and summary["removed"] == 0 and summary["modified"] == 0)
    if ok:
        return {"schema": SCHEMA_ID, "status": STATUS_OK, "exit_code": EXIT_OK, "diff": diff}
    return {
        "schema": SCHEMA_ID, "status": STATUS_FAIL, "exit_code": EXIT_FAIL,
        "reason": "geometry-basis roundtrip diff is non-zero (added=%d removed=%d modified=%d) "
                  "-- the actual write/read-back does not fingerprint-match the expected geometry"
                  % (summary["added"], summary["removed"], summary["modified"]),
        "diff": diff,
    }


# --------------------------------------------------------------------------- #
# Fingerprint discriminability (a "Rung-0" precondition for ANY geometry-basis
# roundtrip check -- reimplemented LOCALLY, mirroring cad_refintegrity_gate.py's
# stated convention of no cross-module coupling to cad_diff's private helpers)
# --------------------------------------------------------------------------- #

def _canonical_local(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted((k, _canonical_local(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_canonical_local(v) for v in value)
    return value


def _quantize_local(value: Any, tol: float) -> Any:
    if isinstance(value, bool) or tol <= 0:
        return value
    if isinstance(value, (int, float)):
        return round(value / tol)
    if isinstance(value, Mapping):
        return {k: _quantize_local(v, tol) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_quantize_local(v, tol) for v in value]
    return value


def _local_fingerprint(entity: Mapping[str, Any], tol: float) -> Tuple[Any, Any, Any]:
    """``(dxf_name, layer, canonical(quantize(geometry)))`` -- the same join
    key cad_diff.py's ``comparison_basis="geometry"`` uses (reproduced here,
    not imported, per this file's sibling-independence convention)."""
    return (entity.get("dxf_name"), entity.get("layer"),
           _canonical_local(_quantize_local(entity.get("geometry"), tol)))


def check_fingerprint_discriminability(entities: Sequence[Mapping[str, Any]], *,
                                       geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE) -> Dict[str, Any]:
    """Precondition for trusting ANY geometry-basis roundtrip check: assert
    that no two DISTINCT entities in ``entities`` (different handles) collapse
    onto the SAME ``(dxf_name, layer, geometry)`` fingerprint bucket.

    ``check_roundtrip``'s geometry-basis join treats an exact fingerprint
    match as "the same physical entity, unchanged" (F1's handle-independent
    identity). If two logically-distinct entities already share a bucket --
    "degenerate dim": e.g. a DIMENSION (or any entity) whose geometry
    collapses to an indistinguishable degenerate value -- a real defect on
    ONE of them can be silently paired against the OTHER and reported as
    "unchanged". This is a STRUCTURAL precondition failure (exit 4 HOLLOW,
    never exit 1 FAIL): the corpus itself cannot discriminate identity for
    this kind, independent of whether any particular value is "right".
    """
    buckets: Dict[Any, List[str]] = {}
    for e in entities:
        if not isinstance(e, Mapping):
            continue
        fp = _local_fingerprint(e, geometry_tolerance)
        buckets.setdefault(fp, []).append(e.get("handle") or "<no-handle>")
    collisions = {fp: handles for fp, handles in buckets.items() if len(handles) > 1}
    if collisions:
        worst_fp = sorted(collisions, key=repr)[0]
        worst_handles = collisions[worst_fp]
        return {
            "schema": SCHEMA_ID, "status": STATUS_HOLLOW, "exit_code": EXIT_HOLLOW,
            "reason": "degenerate dim: %d distinct entit%s (handles=%s) collapse onto the SAME "
                      "geometry fingerprint bucket (dxf_name=%r, layer=%r) -- a geometry-basis diff "
                      "cannot discriminate them, so a real defect on one could be silently paired "
                      "against the other" % (len(worst_handles), "ies" if len(worst_handles) != 1 else "y",
                                              sorted(worst_handles), worst_fp[0], worst_fp[1]),
            "collisions": {repr(fp): handles for fp, handles in collisions.items()},
        }
    return {"schema": SCHEMA_ID, "status": STATUS_OK, "exit_code": EXIT_OK, "checked": len(entities)}


# --------------------------------------------------------------------------- #
# D-half mutation: FAIL-CLOSED replace-not-inject + identity-checked diff
# --------------------------------------------------------------------------- #

def validate_replace_not_inject(pre_entity: Mapping[str, Any], post_entity: Mapping[str, Any],
                                field_path: str) -> None:
    """FAIL-CLOSED gate on a claimed single-field perturbation.

    Raises ``FieldAbsentError`` if ``field_path`` was not already present and
    non-NULL on ``pre_entity`` (nothing real to replace). Raises
    ``FieldInjectedError`` if ``post_entity`` (or, for a ``geometry.<leaf>``
    field, its ``geometry`` dict) introduces any key ``pre_entity`` did not
    already have -- a real replace never changes the key SET, only a leaf
    VALUE. Returns None (no exception) when the perturbation shape is valid.
    """
    present, old_value = _resolve_field(pre_entity, field_path)
    if not present or old_value is None:
        raise FieldAbsentError(
            "field %r is absent/NULL on the pre-entity (handle=%r) -- fail-closed: cannot "
            "legitimately perturb a field that was never populated (no injection permitted)"
            % (field_path, pre_entity.get("handle")))

    injected_top = set(post_entity.keys()) - set(pre_entity.keys())
    if injected_top:
        raise FieldInjectedError(
            "post-entity (handle=%r) introduces new top-level key(s) %s not present on the "
            "pre-entity -- a perturbation must REPLACE an existing field's value, never inject "
            "a new key" % (pre_entity.get("handle"), sorted(injected_top)))

    if field_path.startswith("geometry."):
        pre_geom = pre_entity.get("geometry")
        post_geom = post_entity.get("geometry")
        if isinstance(pre_geom, dict) and isinstance(post_geom, dict):
            injected_geom = set(post_geom.keys()) - set(pre_geom.keys())
            if injected_geom:
                raise FieldInjectedError(
                    "post-entity's geometry (handle=%r) introduces new key(s) %s not present in "
                    "the pre-entity's geometry -- replace-not-inject violated"
                    % (pre_entity.get("handle"), sorted(injected_geom)))


def perturb_field_replace(ir: Dict[str, Any], handle: str, field_path: str,
                          new_value: Any) -> Dict[str, Any]:
    """Deep-copy ``ir``; REPLACE ``field_path``'s value on the entity with
    ``handle`` with ``new_value``. FAIL-CLOSED (replace-not-inject, see
    ``validate_replace_not_inject``): raises ``FieldAbsentError`` /
    ``FieldInjectedError`` rather than ever fabricating/injecting a field.
    """
    pre_entity = _entity_by_handle(ir, handle)
    if pre_entity is None:
        raise FieldAbsentError("no entity with handle %r in IR" % handle)

    present, old_value = _resolve_field(pre_entity, field_path)
    if not present or old_value is None:
        raise FieldAbsentError(
            "field %r is absent/NULL on entity handle=%r -- fail-closed: refusing to perturb "
            "a field that was never populated" % (field_path, handle))
    if old_value == new_value:
        raise ValueError("perturbation value must differ from the original (%r == %r)"
                         % (old_value, new_value))

    post = copy.deepcopy(ir)
    post_entity = _entity_by_handle(post, handle)
    _set_field(post_entity, field_path, new_value)
    # Defensive self-check: our OWN construction must itself satisfy
    # replace-not-inject (it always will, by construction of _set_field, but
    # this keeps the invariant load-bearing rather than merely asserted).
    validate_replace_not_inject(pre_entity, post_entity, field_path)
    return post


def _field_detected(rec: Dict[str, Any], field_path: str) -> bool:
    """True iff ``field_path`` shows up in a cad_diff ``changed_handles``
    'modified' record's field delta -- a top-level field is its own entry;
    a ``geometry.<leaf>`` field is nested under the ``geometry`` entry's
    ``changed_subfields`` (see cad_diff._field_delta)."""
    fields = rec.get("fields") or []
    by_name = {f.get("field"): f for f in fields if isinstance(f, dict)}
    if field_path in by_name:
        return True
    if "." in field_path:
        top, _, _rest = field_path.partition(".")
        top_entry = by_name.get(top)
        if top_entry and field_path in (top_entry.get("changed_subfields") or []):
            return True
    return False


def check_mutation_pair(pre_ir: Dict[str, Any], post_ir: Dict[str, Any], handle: str, field_path: str, *,
                        comparison_basis: str = "handle",
                        geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE,
                        cad_diff_mod=None) -> Dict[str, Any]:
    """The D-gate's core judge: given an ALREADY-BUILT ``(pre_ir, post_ir)``
    pair (however constructed -- ``perturb_field_replace``'s own legitimate
    replace, or a hand-built adversarial fixture) that claims to differ by one
    field on the entity with ``handle``, assert:

      0. replace-not-inject (``validate_replace_not_inject``): the field was
         really present/non-NULL pre-perturbation and no key was injected --
         else exit 4 HOLLOW.
      1. the diff never surfaces the perturbation as added/removed (an
         in-place edit must never look like a create+delete) -- else exit 8
         IRRECONSTRUCTIBLE.
      2. the diff registers AT LEAST one modified entity -- zero modified
         entities for a claimed real perturbation means the diff/extractor
         never saw ANYTHING change (a coarse-quantizing extractor collapsing
         a real edit onto an identical stored value is exactly this shape)
         -- exit 4 HOLLOW (invisible data), not an identity failure.
      3. EXACTLY one modified entity is reported -- more than one is
         ambiguous -- else exit 8 IRRECONSTRUCTIBLE.
      4. that one modified entity IS the entity with ``handle`` (identity
         check: "the single 'modified' MUST be the perturbed entity") --
         else exit 8 IRRECONSTRUCTIBLE.
      5. the perturbed field is actually among that entity's changed fields
         -- else exit 4 HOLLOW (invisible data: the diff/extractor is blind
         to this specific field even though the entity as a whole changed).
    """
    pre_entity = _entity_by_handle(pre_ir, handle)
    post_entity = _entity_by_handle(post_ir, handle)
    if pre_entity is None or post_entity is None:
        return {"schema": SCHEMA_ID, "status": STATUS_ERROR, "exit_code": EXIT_ERROR,
                "reason": "handle %r missing from pre_ir and/or post_ir" % handle,
                "handle": handle, "field": field_path}
    try:
        validate_replace_not_inject(pre_entity, post_entity, field_path)
    except GateError as exc:
        return {"schema": SCHEMA_ID, "status": exc.status, "exit_code": exc.exit_code,
                "reason": str(exc), "handle": handle, "field": field_path}

    cd = cad_diff_mod or _import_optional("cad_diff")
    if cd is None or not hasattr(cd, "compute_diff"):
        return {"schema": SCHEMA_ID, "status": STATUS_NOT_IMPLEMENTED,
                "exit_code": EXIT_NOT_IMPLEMENTED,
                "reason": "cad_diff sibling module unavailable",
                "handle": handle, "field": field_path}

    diff = cd.compute_diff(pre_ir, post_ir, comparison_basis=comparison_basis,
                           geometry_tolerance=geometry_tolerance)
    summary = diff["summary"]
    modified_records = [r for r in diff["changed_handles"] if r["change"] == "modified"]

    if summary["added"] or summary["removed"]:
        return {
            "schema": SCHEMA_ID, "status": STATUS_IRRECONSTRUCTIBLE, "exit_code": EXIT_IRRECONSTRUCTIBLE,
            "reason": "an in-place field replace must never surface as added/removed "
                      "(added=%d removed=%d) -- identity cannot be reconstructed"
                      % (summary["added"], summary["removed"]),
            "diff": diff, "handle": handle, "field": field_path,
        }
    if len(modified_records) == 0:
        return {
            "schema": SCHEMA_ID, "status": STATUS_HOLLOW, "exit_code": EXIT_HOLLOW,
            "reason": "the diff reports ZERO modified entities for a claimed field perturbation on "
                      "handle=%r -- the diff/extractor never detected ANY change (invisible data: a "
                      "coarse-quantizing or lossy extractor can collapse a real edit onto an "
                      "identical stored value)" % handle,
            "diff": diff, "handle": handle, "field": field_path,
        }
    if len(modified_records) > 1:
        return {
            "schema": SCHEMA_ID, "status": STATUS_IRRECONSTRUCTIBLE, "exit_code": EXIT_IRRECONSTRUCTIBLE,
            "reason": "expected exactly 1 modified entity for a single-field perturbation, found %d"
                      % len(modified_records),
            "diff": diff, "handle": handle, "field": field_path,
        }
    rec = modified_records[0]
    if rec["handle"] != handle:
        return {
            "schema": SCHEMA_ID, "status": STATUS_IRRECONSTRUCTIBLE, "exit_code": EXIT_IRRECONSTRUCTIBLE,
            "reason": "wrong entity modified: perturbed handle=%r but the diff reports modified "
                      "handle=%r -- the single 'modified' record does not reconstruct back to the "
                      "entity actually perturbed" % (handle, rec["handle"]),
            "diff": diff, "handle": handle, "field": field_path,
        }
    if not _field_detected(rec, field_path):
        changed_fields = sorted({f.get("field") for f in rec.get("fields", [])})
        return {
            "schema": SCHEMA_ID, "status": STATUS_HOLLOW, "exit_code": EXIT_HOLLOW,
            "reason": "perturbed field %r not detected among changed fields %s -- the diff/"
                      "extractor is blind to this field (invisible data)" % (field_path, changed_fields),
            "diff": diff, "handle": handle, "field": field_path,
        }
    return {"schema": SCHEMA_ID, "status": STATUS_OK, "exit_code": EXIT_OK,
           "diff": diff, "handle": handle, "field": field_path}


def check_field_mutation(pre_ir: Dict[str, Any], handle: str, field_path: str, new_value: Any, *,
                         comparison_basis: str = "handle",
                         geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE,
                         cad_diff_mod=None) -> Dict[str, Any]:
    """The D-gate primitive: BUILD a fail-closed, replace-not-inject
    perturbation of ``field_path`` on entity ``handle`` (``perturb_field_replace``)
    and judge it (``check_mutation_pair``). Thin convenience wrapper for the
    common self-built case; ``check_mutation_pair`` is the one to call
    directly against an already-built (e.g. hand-crafted adversarial) pair.
    """
    try:
        post_ir = perturb_field_replace(pre_ir, handle, field_path, new_value)
    except GateError as exc:
        return {"schema": SCHEMA_ID, "status": exc.status, "exit_code": exc.exit_code,
                "reason": str(exc), "handle": handle, "field": field_path}
    return check_mutation_pair(pre_ir, post_ir, handle, field_path,
                               comparison_basis=comparison_basis,
                               geometry_tolerance=geometry_tolerance, cad_diff_mod=cad_diff_mod)


# --------------------------------------------------------------------------- #
# Rung-B: non-null population precheck
# --------------------------------------------------------------------------- #

def rung_b_population(ir: Dict[str, Any], field_path: str, *,
                      kind: Optional[str] = None) -> Dict[str, Any]:
    """Rung-B: before trusting a mutation test on ``field_path``, confirm the
    fixture actually POPULATES it somewhere. A field that is null/absent
    across every candidate entity would make ``check_field_mutation``
    vacuous (or impossible, since ``perturb_field_replace`` would refuse it
    anyway) -- Rung-B catches this UPSTREAM, against the whole corpus/kind,
    not just the one handle Rung-A happens to pick.
    """
    entities = [e for e in (ir.get("entities") or []) if isinstance(e, dict)]
    if kind is not None:
        entities = [e for e in entities if e.get("dxf_name") == kind]
    populated = []
    for e in entities:
        present, value = _resolve_field(e, field_path)
        if present and value is not None:
            populated.append(e.get("handle"))
    if not populated:
        return {
            "schema": SCHEMA_ID, "status": STATUS_HOLLOW, "exit_code": EXIT_HOLLOW,
            "reason": "Rung-B: field %r is null/absent across ALL %d %s entit%s in the fixture "
                      "-- cannot certify a mutation test against a field that is never genuinely "
                      "populated" % (field_path, len(entities), kind or "(any kind)",
                                     "y" if len(entities) == 1 else "ies"),
            "field": field_path, "kind": kind, "checked": len(entities), "populated": 0,
        }
    return {
        "schema": SCHEMA_ID, "status": STATUS_OK, "exit_code": EXIT_OK,
        "field": field_path, "kind": kind, "checked": len(entities),
        "populated": len(populated), "populated_handles": sorted(populated),
    }


# --------------------------------------------------------------------------- #
# Rung-A: per (kind, field) mutation sweep
# --------------------------------------------------------------------------- #

def rung_a_sweep(pre_ir: Dict[str, Any], specs: Sequence[Mapping[str, Any]], *,
                 comparison_basis: str = "handle",
                 geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE,
                 cad_diff_mod=None) -> Dict[str, Any]:
    """Run ``check_field_mutation`` for every ``(kind, field)`` pair in
    ``specs`` (each ``{"kind": str, "field": str, "new_value": value_or_fn}``,
    ``new_value`` either a literal or a ``callable(old_value) -> new_value``),
    Rung-B-gated first. Aggregates to the single worst result across the whole
    sweep (see ``combine_results``); every per-spec result is preserved under
    ``steps`` for provenance.
    """
    results: List[Dict[str, Any]] = []
    for spec in specs:
        kind = spec.get("kind")
        field = spec["field"]
        rb = rung_b_population(pre_ir, field, kind=kind)
        if rb["exit_code"] != EXIT_OK:
            results.append(rb)
            continue
        handle = rb["populated_handles"][0]
        entity = _entity_by_handle(pre_ir, handle)
        _present, old_value = _resolve_field(entity, field)
        raw_new = spec.get("new_value")
        new_value = raw_new(old_value) if callable(raw_new) else raw_new
        r = check_field_mutation(pre_ir, handle, field, new_value,
                                 comparison_basis=comparison_basis,
                                 geometry_tolerance=geometry_tolerance, cad_diff_mod=cad_diff_mod)
        r = dict(r)
        r["kind"] = kind
        results.append(r)
    return _finalize(results)


# --------------------------------------------------------------------------- #
# UTF-8 fidelity
# --------------------------------------------------------------------------- #

_REPLACEMENT_CHAR = "�"


def _iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _iter_strings(v)


def check_utf8_fidelity(value: Any) -> Dict[str, Any]:
    """Walk every string leaf in ``value`` (an IR dict, a diff dict, or any
    JSON-shaped structure) and assert UTF-8 fidelity: no U+FFFD replacement
    char (proof of a real decode loss upstream -- see
    ``tests/unit/test_non_ascii_fidelity.py``'s established convention) and a
    lossless ``encode('utf-8').decode('utf-8')`` round trip for every string.
    """
    replacement_offenders: List[str] = []
    roundtrip_offenders: List[str] = []
    for s in _iter_strings(value):
        if _REPLACEMENT_CHAR in s:
            replacement_offenders.append(s)
            continue
        try:
            if s.encode("utf-8").decode("utf-8") != s:
                roundtrip_offenders.append(s)
        except UnicodeError:
            roundtrip_offenders.append(s)
    if replacement_offenders or roundtrip_offenders:
        return {
            "schema": SCHEMA_ID, "status": STATUS_UTF8, "exit_code": EXIT_UTF8,
            "reason": "UTF-8 fidelity violated: %d string(s) contain U+FFFD, %d failed a lossless "
                      "UTF-8 round trip" % (len(replacement_offenders), len(roundtrip_offenders)),
            "replacement_char_offenders": [ascii(s) for s in replacement_offenders[:20]],
            "roundtrip_offenders": [ascii(s) for s in roundtrip_offenders[:20]],
        }
    return {"schema": SCHEMA_ID, "status": STATUS_OK, "exit_code": EXIT_OK}


# --------------------------------------------------------------------------- #
# Original-file protection: pre-write staging-integrity assert + post-write
# byte-check (same invariant, checked on both sides of the write).
# --------------------------------------------------------------------------- #

def capture_file_fingerprint(path: str) -> Dict[str, Any]:
    """{"path", "size", "sha256"} for a file, read-only."""
    return {
        "path": os.path.abspath(path),
        "size": os.path.getsize(path) if os.path.isfile(path) else None,
        "sha256": _sha256_file(path),
    }


def assert_staging_integrity(original_path: str, staged_path: str) -> Dict[str, Any]:
    """PRE-WRITE guard, run BEFORE any mutation is attempted:
      1. ``staged_path`` must be a DISTINCT file from ``original_path`` (never
         the same path -- writing to it would mutate the original).
      2. if ``staged_path`` already exists, it must currently be byte-
         identical to ``original_path`` (staging happened correctly and
         nothing has touched the copy yet).
    Returns exit 5 ORIGINAL_MUTATED on either violation (same invariant class
    as the post-write byte-check: "the original must never be at risk").
    """
    if not original_path or not staged_path:
        return {"schema": SCHEMA_ID, "status": STATUS_ERROR, "exit_code": EXIT_ERROR,
               "reason": "original_path and staged_path are both required"}
    norm_o = os.path.normcase(os.path.normpath(os.path.abspath(original_path)))
    norm_s = os.path.normcase(os.path.normpath(os.path.abspath(staged_path)))
    if norm_o == norm_s:
        return {"schema": SCHEMA_ID, "status": STATUS_ORIGINAL_MUTATED, "exit_code": EXIT_ORIGINAL_MUTATED,
               "reason": "staged_path equals original_path -- writing to it would mutate the original",
               "original_path": original_path, "staged_path": staged_path}
    if not os.path.isfile(original_path):
        return {"schema": SCHEMA_ID, "status": STATUS_ERROR, "exit_code": EXIT_ERROR,
               "reason": "original_path does not exist: %r" % original_path}
    if os.path.isfile(staged_path):
        o_fp = capture_file_fingerprint(original_path)
        s_fp = capture_file_fingerprint(staged_path)
        if o_fp["sha256"] != s_fp["sha256"]:
            return {
                "schema": SCHEMA_ID, "status": STATUS_ORIGINAL_MUTATED, "exit_code": EXIT_ORIGINAL_MUTATED,
                "reason": "staged_path exists but is NOT a byte-identical copy of original_path "
                          "before any mutation -- staging integrity violated",
                "original": o_fp, "staged": s_fp,
            }
    return {"schema": SCHEMA_ID, "status": STATUS_OK, "exit_code": EXIT_OK,
           "original_path": original_path, "staged_path": staged_path}


def check_original_unchanged(path: str, fingerprint: Mapping[str, Any]) -> Dict[str, Any]:
    """POST-WRITE proof: ``path`` (the ORIGINAL, never the staged copy) is
    still byte-identical to the ``fingerprint`` captured (via
    ``capture_file_fingerprint``) BEFORE any write was attempted."""
    if not os.path.isfile(path):
        return {"schema": SCHEMA_ID, "status": STATUS_ORIGINAL_MUTATED, "exit_code": EXIT_ORIGINAL_MUTATED,
               "reason": "original file missing after the roundtrip: %r" % path, "before": dict(fingerprint)}
    after = capture_file_fingerprint(path)
    unchanged = (fingerprint.get("sha256") is not None
                and after["sha256"] == fingerprint.get("sha256")
                and after["size"] == fingerprint.get("size"))
    if not unchanged:
        return {
            "schema": SCHEMA_ID, "status": STATUS_ORIGINAL_MUTATED, "exit_code": EXIT_ORIGINAL_MUTATED,
            "reason": "original file bytes changed (sha256/size mismatch) -- READ-ONLY invariant violated",
            "before": dict(fingerprint), "after": after,
        }
    return {"schema": SCHEMA_ID, "status": STATUS_OK, "exit_code": EXIT_OK,
           "before": dict(fingerprint), "after": after}


# --------------------------------------------------------------------------- #
# CROSS-ORACLE leg (F1.5, tools/cross_oracle.py -- already merged)
# --------------------------------------------------------------------------- #
# cross_oracle's OWN exit-code enum (0 ok / 2 unavailable / 3 not_certified /
# 4 tripwire / 7 disagreement) is already a strict SUBSET of this module's own
# contract with matching meanings, so its result dict is passed through
# verbatim (just re-tagged with this module's schema) rather than translated.

def check_cross_oracle(reference_ir: Dict[str, Any], native_ir: Dict[str, Any], *,
                       supported_fields: Optional[Mapping[str, Mapping[str, Sequence[str]]]] = None,
                       geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE,
                       cross_oracle_mod=None) -> Dict[str, Any]:
    """The (same-file, independent-comparison) cross-oracle leg: certify
    ``native_ir`` against ``reference_ir`` via ``cross_oracle.compare_multiset``
    (full per-(kind,field) multiset re-diff -- catches a single-extractor
    monoculture drop that a same-extractor pre/post diff would never see)."""
    co = cross_oracle_mod or _import_optional("cross_oracle")
    if co is None or not hasattr(co, "compare_multiset"):
        return {"schema": SCHEMA_ID, "status": STATUS_NOT_IMPLEMENTED, "exit_code": EXIT_NOT_IMPLEMENTED,
               "reason": "cross_oracle sibling module unavailable"}
    result = co.compare_multiset(reference_ir, native_ir, supported_fields=supported_fields,
                                 geometry_tolerance=geometry_tolerance)
    out = dict(result)
    out["schema"] = SCHEMA_ID
    out["cross_oracle_schema"] = result.get("schema")
    return out


def check_cross_oracle_live(staged_dwg_path: str, native_ir: Dict[str, Any], *,
                            engine: str = "accoreconsole",
                            run_dir: Optional[str] = None,
                            router_extract=None,
                            ir_from_extract=None,
                            supported_fields: Optional[Mapping[str, Mapping[str, Sequence[str]]]] = None,
                            geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE,
                            cross_oracle_mod=None) -> Dict[str, Any]:
    """The LIVE cross-oracle leg: re-extract ``staged_dwg_path`` with an
    INDEPENDENT engine via ``cross_oracle.run_live_cross_oracle`` and certify
    against it. Environment-dependent (needs a working router + live engine);
    every unavailability mode degrades truthfully to exit 2 (mirroring
    cross_oracle's own EXIT_UNAVAILABLE) -- see that module's docstring.
    DONE_NEEDS_RUNTIME callers pass no injected ``router_extract``/
    ``ir_from_extract`` and get the REAL router wrapper (cross_oracle's own
    default); unit tests inject fakes (see cross_oracle's own test suite for
    the established injection pattern) so this leg's WIRING is exercised
    without ever shelling out to accoreconsole.
    """
    co = cross_oracle_mod or _import_optional("cross_oracle")
    if co is None or not hasattr(co, "run_live_cross_oracle"):
        return {"schema": SCHEMA_ID, "status": STATUS_NOT_IMPLEMENTED, "exit_code": EXIT_NOT_IMPLEMENTED,
               "reason": "cross_oracle sibling module unavailable"}
    result = co.run_live_cross_oracle(
        staged_dwg_path, native_ir, engine=engine, run_dir=run_dir,
        router_extract=router_extract, ir_from_extract=ir_from_extract,
        supported_fields=supported_fields, geometry_tolerance=geometry_tolerance)
    out = dict(result)
    out["schema"] = SCHEMA_ID
    out["cross_oracle_schema"] = result.get("schema")
    return out


# --------------------------------------------------------------------------- #
# Orchestrators: gate_roundtrip (P) / gate_field_mutation (D)
# --------------------------------------------------------------------------- #

def gate_roundtrip(expected_ir: Dict[str, Any], actual_ir: Dict[str, Any], *,
                   geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE,
                   original_path: Optional[str] = None,
                   original_fingerprint: Optional[Mapping[str, Any]] = None,
                   staged_path: Optional[str] = None,
                   check_utf8: bool = True,
                   oracle_reference_ir: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Full P-gate pipeline for one create/regen roundtrip: (optional)
    pre-write staging-integrity assert -> the geometry-basis roundtrip diff
    -> (optional) UTF-8 fidelity -> (optional) cross-oracle leg -> (optional)
    post-write original-unchanged proof. Stops at the first non-OK step
    (fail-fast); returns ``combine_results``' worst-of-all-attempted-steps
    otherwise (only OK survives that far).
    """
    steps: List[Optional[Dict[str, Any]]] = []
    if staged_path is not None and original_path is not None:
        r = assert_staging_integrity(original_path, staged_path)
        steps.append(r)
        if r["exit_code"] != EXIT_OK:
            return _finalize(steps)

    r = check_roundtrip(expected_ir, actual_ir, geometry_tolerance=geometry_tolerance)
    steps.append(r)
    if r["exit_code"] != EXIT_OK:
        return _finalize(steps)

    if check_utf8:
        r = check_utf8_fidelity(actual_ir)
        steps.append(r)
        if r["exit_code"] != EXIT_OK:
            return _finalize(steps)

    if oracle_reference_ir is not None:
        r = check_cross_oracle(oracle_reference_ir, actual_ir)
        steps.append(r)
        if r["exit_code"] != EXIT_OK:
            return _finalize(steps)

    if original_path is not None and original_fingerprint is not None:
        r = check_original_unchanged(original_path, original_fingerprint)
        steps.append(r)

    return _finalize(steps)


def gate_field_mutation(pre_ir: Dict[str, Any], handle: str, field_path: str, new_value: Any, *,
                        kind: Optional[str] = None,
                        comparison_basis: str = "handle",
                        geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE,
                        check_utf8: bool = True,
                        oracle_reference_ir: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Full D-gate pipeline for one field: Rung-B population precheck ->
    Rung-A single-field mutation check (fail-closed, identity-checked) ->
    (optional) UTF-8 fidelity on the resulting diff -> (optional) cross-oracle
    leg. Stops at the first non-OK step.
    """
    steps: List[Optional[Dict[str, Any]]] = []
    rb = rung_b_population(pre_ir, field_path, kind=kind)
    steps.append(rb)
    if rb["exit_code"] != EXIT_OK:
        return _finalize(steps)

    fm = check_field_mutation(pre_ir, handle, field_path, new_value,
                              comparison_basis=comparison_basis, geometry_tolerance=geometry_tolerance)
    steps.append(fm)
    if fm["exit_code"] != EXIT_OK:
        return _finalize(steps)

    if check_utf8:
        r = check_utf8_fidelity(fm.get("diff"))
        steps.append(r)
        if r["exit_code"] != EXIT_OK:
            return _finalize(steps)

    if oracle_reference_ir is not None:
        r = check_cross_oracle(oracle_reference_ir, pre_ir)
        steps.append(r)

    return _finalize(steps)


# --------------------------------------------------------------------------- #
# Self-demo (__main__): synthetic PASS + every FAIL family, print PASS/FAIL.
# --------------------------------------------------------------------------- #

def _demo_entity(handle: str, dxf_name: str = "LINE", layer: str = "0",
                 start=(0.0, 0.0, 0.0), end=(10.0, 0.0, 0.0)) -> Dict[str, Any]:
    return {
        "handle": handle, "class": "AcDbLine", "dxf_name": dxf_name,
        "owner_handle": "1F", "space": "model", "layer": layer,
        "bbox": [start[0], start[1], start[2], end[0], end[1], end[2]],
        "geometry": {"kind": "line", "start": list(start), "end": list(end)},
        "source": {"extractor": "cad_op_gate.selfdemo", "decoded": True},
    }


def _selftest() -> int:
    print("== cad_op_gate self-demo ==")

    # --- P-gate: create_line roundtrip, diff=0 -> PASS ---
    expected = {"schema": IR_SCHEMA_ID, "entities": [
        {"dxf_name": "LINE", "layer": "0",
         "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [10.0, 0.0, 0.0]}}]}
    actual_match = {"schema": IR_SCHEMA_ID, "entities": [_demo_entity("2A7")]}
    rt_pass = check_roundtrip(expected, actual_match)
    print("roundtrip match     : status=%s exit=%d (expect ok/0)" % (rt_pass["status"], rt_pass["exit_code"]))

    actual_shifted = {"schema": IR_SCHEMA_ID, "entities": [
        _demo_entity("2A7", end=(10.0, 5.0, 0.0))]}
    rt_fail = check_roundtrip(expected, actual_shifted)
    print("roundtrip shifted   : status=%s exit=%d (expect fail/1)" % (rt_fail["status"], rt_fail["exit_code"]))

    # --- D-gate: field mutation, absent field -> HOLLOW ---
    pre_ir = {"schema": IR_SCHEMA_ID, "entities": [_demo_entity("2A8", layer="WALLS")]}
    fm_hollow = check_field_mutation(pre_ir, "2A8", "xdata", ["nope"])
    print("mutation absent     : status=%s exit=%d (expect hollow/4)"
         % (fm_hollow["status"], fm_hollow["exit_code"]))

    # --- D-gate: field mutation, layer replace -> PASS ---
    fm_ok = check_field_mutation(pre_ir, "2A8", "layer", "MOVED")
    print("mutation layer      : status=%s exit=%d (expect ok/0)" % (fm_ok["status"], fm_ok["exit_code"]))

    passed = (rt_pass["status"] == STATUS_OK and rt_fail["status"] == STATUS_FAIL
             and fm_hollow["status"] == STATUS_HOLLOW and fm_ok["status"] == STATUS_OK)
    print("RESULT              : %s" % ("PASS" if passed else "FAIL"))
    return 0 if passed else 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="cad_op_gate: P/D-half roundtrip gate primitive (F3). With no "
                    "arguments, runs a synthetic self-demo.")
    ap.add_argument("--expected-ir", help="P-gate: path to the expected single-entity IR")
    ap.add_argument("--actual-ir", help="P-gate: path to the actual (read-back) IR")
    ap.add_argument("--tol", type=float, default=DEFAULT_GEOMETRY_TOLERANCE)
    ap.add_argument("--out", help="also write the result JSON to this path")
    args = ap.parse_args(argv)

    if args.expected_ir and args.actual_ir:
        result = check_roundtrip(load_ir(args.expected_ir), load_ir(args.actual_ir),
                                 geometry_tolerance=args.tol)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                json.dump(result, fh, ensure_ascii=False, indent=2)
        return int(result.get("exit_code", EXIT_ERROR))

    return _selftest()


if __name__ == "__main__":
    sys.exit(main())
