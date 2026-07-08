#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cad_diff.py -- CAD OS Layer structural diff between two DWG-graph IRs.

Computes a deterministic, engine-neutral difference between a ``before`` and an
``after`` ``ariadne.dwg_graph_ir.v1`` document and emits an
``ariadne.cad_diff.v1`` report (conforms ``schemas/cad_diff.v1.schema.json``).

Join model
----------
Entities are joined on their DWG ``handle`` -- the IR's stable, cross-engine key
(uppercase hex). A handle present only in ``after`` is ``added``; only in
``before`` is ``removed``; present in both with any changed field is
``modified``; present in both with no changed field is unchanged. The comparison
is therefore exact (``diagnostics.comparison_basis == "handle"``); it does not
fall back to positional/geometry matching, so a drawing whose engine reissues
handles would be reported truthfully as wholesale added/removed rather than
faking a positional match (no-fake-success).

An explicit ``comparison_basis="geometry"`` opts into a handle-INDEPENDENT join
instead: entities are matched on ``(dxf_name, layer, geometry)`` under a
per-quantity tolerance profile (the AutoCAD COMPARETOLERANCE analog -- see
``DEFAULT_GEOMETRY_TOLERANCE``, ``default_tolerance_profile`` and the
``geometry_tolerance`` / ``tolerance_profile`` kwargs), so a regenerated drawing
whose engine reissued every handle can still report zero changes when the
geometry itself is unchanged. Matching is three-tier: entities with a
BYTE-EXACT fingerprint match on both sides are unchanged (tier 1, no
tolerance involved at all); whatever is left is matched pairwise -- a direct
``abs(a - b) <= tol`` compare against a same-``(dxf_name, layer)`` leftover on
the other side, never a hash/bucket (tier 1.5 -- see ``_geometry_within_tolerance``,
the v2-A5 tolerance-rigor fix: a bucket/hash scheme either collapses distinct
large coordinates onto one bucket if the per-scalar tolerance is derived from
each value independently, or false-fails two within-tolerance values that
straddle a bucket boundary; a direct pairwise compare has neither failure
mode); whatever STILL doesn't match is paired by ``(dxf_name, layer)`` alone
and classified via ``classify_change``, so a genuine geometry edit becomes
``modified`` rather than a fake added+removed pair (tier 2).
``"handle"`` remains the default and is completely unaffected by this mode.

Diff scope (``config/diff_scope.json``)
----------------------------------------
Which entities are even eligible to be diffed is itself legislated, not
implicit. ``diff_scope="modelspace_entities_only"`` (the default, and the
config's ``default_scope``) keeps only entities whose IR ``space`` is
``"model"`` -- paperspace/layout entities and any future symbol-table-shaped
record are out of scope. ``diff_scope="full_database"`` (the config's
``freeze_scope``) keeps every space and additionally subtracts a
``seed_baseline_mask`` -- entries matching a blank-seed's default
symbol-table/block-definition records (see node F4) so those never pollute a
full-database diff (H-R18: default layers/text styles/dimstyles/linetypes/block
defs). A mask entry without a ``"geometry"`` key is a ``(dxf_name, layer)``
wildcard (a table-record match); one carrying ``"geometry"`` matches only within
the active tolerance profile. No mask supplied => no subtraction -- an honest
degraded mode, since F4's real baseline is a separate, not-yet-minted fixture and
this module never fabricates an exclusion it cannot justify.

Change taxonomy (``classify_change``)
-------------------------------------
For a handle in both IRs the following fields are compared, in this order, and
the sorted list of changed field names is returned:

  * ``layer``          -- entity.layer string changed.
  * ``dxf_name``       -- entity.dxf_name (DXF type) changed.
  * ``bbox``           -- entity.bbox (axis-aligned box) changed.
  * ``geometry``       -- entity.geometry changed (canonicalized compare); the
                          specific changed leaf is also surfaced as
                          ``geometry.<key>`` (e.g. ``geometry.start``) when it can
                          be localized to a single key.

Hard rules (CAD OS Layer build invariants)
-------------------------------------------
  * Standard library ONLY (Python 3.12). No third-party imports.
  * Deterministic: handles are sorted; there are NO timestamps inside the diff
    body and NO randomness. ``diff_id`` is a content hash that also signs
    ``comparison_basis`` and ``diff_scope`` (two bases/scopes over the same IR
    pair never collide on one id); for ``comparison_basis=="geometry"`` the hash
    is additionally handle-INDEPENDENT -- it signs the sorted MULTISET of
    geometry fingerprints, never handles, so two regen runs of the same source
    (fresh handles each run) yield an IDENTICAL geometry-basis ``diff_id`` while
    the handle-basis id stays exactly as handle-sensitive as it always was.
  * No-fake-success: an entity missing a handle cannot be joined and is recorded
    in ``diagnostics.warnings`` (counted, never silently dropped or matched).
  * Read-only: this module never writes an IR or a DWG. It returns / prints a
    diff dict.
  * Truthful sibling degradation: ``ir_builder`` is imported via
    ``_import_optional``; if it is absent the public diff API still works and the
    ``__main__`` self-demo degrades to ``not_implemented`` rather than crashing.

Public API:
    DIFF_SCHEMA_ID
    DEFAULT_GEOMETRY_TOLERANCE
    MODELSPACE_ENTITIES_ONLY, FULL_DATABASE, VALID_DIFF_SCOPES
    compute_diff(pre_ir: dict, post_ir: dict, comparison_basis: str = "handle",
                 geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE,
                 diff_scope: str | None = None,
                 seed_baseline_mask: list[dict] | None = None,
                 tolerance_profile: dict | None = None) -> dict
    classify_change(pre_entity: dict, post_entity: dict) -> list[str]
    default_tolerance_profile(geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE) -> dict
    load_diff_scope_config() -> dict                            # BOM-tolerant
    load_diff(path) -> dict ; write_diff(diff, path) -> str
    load_ir(path) -> dict                                       # BOM-tolerant
    index_entities_by_handle(ir: dict) -> (dict, list[str])

Run ``python tools/cad_diff.py`` to diff two synthetic IRs (a fixture IR vs a
copy with one added + one modified entity) and print PASS/FAIL.
"""

from __future__ import annotations

import json
import hashlib
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Paths / constants
# --------------------------------------------------------------------------- #

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)

DIFF_SCHEMA_ID = "ariadne.cad_diff.v1"
IR_SCHEMA_ID = "ariadne.dwg_graph_ir.v1"

# On this box the catalog/config/IR JSON may carry a UTF-8 BOM; json.load on the
# cp949 locale needs utf-8-sig to decode it. Writes are plain UTF-8.
_JSON_ENCODING = "utf-8-sig"

# Entity fields compared for the "modified" classification. geometry/bbox are
# compared structurally (see _geometry_changed / _bbox_changed); layer/dxf_name
# are scalar string compares.
_SCALAR_COMPARE_FIELDS = ("layer", "dxf_name")

# Default tolerance for comparison_basis="geometry" (the AutoCAD COMPARETOLERANCE
# analog): numeric geometry leaves within this distance of each other are treated
# as equal so floating-point roundtrip noise doesn't register as a change.
DEFAULT_GEOMETRY_TOLERANCE = 1e-6

# v2-A5: a single tol cannot be right for every quantity a geometry payload
# mixes -- a coordinate/length, an angle (radians), and a dimensionless ratio
# (scale/bulge) have different natural magnitudes. These seed
# default_tolerance_profile(); DEFAULT_GEOMETRY_TOLERANCE remains the "length"
# default so the existing geometry_tolerance= kwarg keeps its exact meaning.
DEFAULT_ANGLE_TOLERANCE = 1e-9
DEFAULT_SCALE_TOLERANCE = 1e-9
# Beyond this magnitude a "length" leaf's epsilon switches from pure-absolute to
# a relative (magnitude-proportional) one and WIDENS (never narrows) -- IEEE-754
# doubles carry ~15-17 significant digits, so a coordinate at large-site scale
# accrues roundtrip noise that a fixed absolute epsilon would false-fail on.
LARGE_COORDINATE_THRESHOLD = 1.0e6
LARGE_COORDINATE_RELATIVE_TOLERANCE = 1e-9

# Diff-scope legislation (config/diff_scope.json). See the module docstring.
MODELSPACE_ENTITIES_ONLY = "modelspace_entities_only"
FULL_DATABASE = "full_database"
VALID_DIFF_SCOPES = (MODELSPACE_ENTITIES_ONLY, FULL_DATABASE)
_DIFF_SCOPE_CONFIG_PATH = os.path.join(_ROUTER_HOME, "config", "diff_scope.json")


# --------------------------------------------------------------------------- #
# Truthful sibling-lane import (keep the _import_optional pattern)
# --------------------------------------------------------------------------- #

def _import_optional(module_name: str):
    """Import a sibling-lane module if present, else return None (no crash).

    Mirrors the truthful-degradation pattern used across the CAD OS Layer: a
    sibling module that is not yet on disk degrades the dependent feature to
    ``not_implemented`` instead of raising at import time.
    """
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
    try:
        return __import__(module_name)
    except Exception:  # pragma: no cover - defensive; sibling truly absent
        return None


# --------------------------------------------------------------------------- #
# IO (BOM-tolerant)
# --------------------------------------------------------------------------- #

def load_ir(path) -> Dict[str, Any]:
    """Load an IR JSON document (BOM-tolerant)."""
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def load_diff(path) -> Dict[str, Any]:
    """Load a cad_diff JSON document (BOM-tolerant)."""
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


class DiffConformanceError(ValueError):
    """Raised by the conformance gate when a cad_diff.v1-tagged diff does not
    satisfy the schema of record."""


_DIFF_SCHEMA_PATH = os.path.join(_ROUTER_HOME, "schemas", "cad_diff.v1.schema.json")


def validate_diff(diff: Dict[str, Any]) -> Tuple[bool, str, List[str]]:
    """Validate a diff against cad_diff.v1. Returns ``(ok, method, errors)``.

    Uses jsonschema when importable (the machine has 4.26.0), else a structural
    fallback over cad_diff.v1's required keys. Reusable core of the T1 gate.
    """
    errors: List[str] = []
    try:
        import jsonschema  # type: ignore
        with open(_DIFF_SCHEMA_PATH, "r", encoding=_JSON_ENCODING) as fh:
            schema = json.load(fh)
        validator = jsonschema.Draft7Validator(schema)
        errors = [
            "%s: %s" % ("/".join(str(p) for p in e.path), e.message)
            for e in sorted(validator.iter_errors(diff), key=lambda e: list(e.path))
        ]
        return (len(errors) == 0, "jsonschema", errors[:20])
    except ImportError:
        for key in ("schema", "diff_id", "before_ref", "after_ref",
                    "changed_handles", "summary", "diagnostics"):
            if key not in diff:
                errors.append("missing required key: %s" % key)
        if diff.get("schema") != DIFF_SCHEMA_ID:
            errors.append("schema const mismatch: %r" % diff.get("schema"))
        # each changed_handles[] record must carry a usable handle AND a
        # change kind in the schema's closed enum -- the measured adversarial
        # defect was `{"handle": "X"}` (no "change") silently passing here.
        for i, rec in enumerate(diff.get("changed_handles") or []):
            if not isinstance(rec, dict):
                errors.append("changed_handles[%d] is not an object" % i)
                continue
            handle = rec.get("handle")
            if not isinstance(handle, str) or not handle.strip():
                errors.append("changed_handles[%d] missing a usable handle" % i)
            change = rec.get("change")
            if change not in ("added", "removed", "modified"):
                errors.append(
                    "changed_handles[%d] change must be one of "
                    "added/removed/modified, got %r" % (i, change))
        summ = diff.get("summary") or {}
        for key in ("added", "removed", "modified"):
            if key not in summ:
                errors.append("summary missing required key: %s" % key)
                continue
            val = summ.get(key)
            if isinstance(val, bool) or not isinstance(val, int) or val < 0:
                errors.append(
                    "summary.%s must be a non-negative int, got %r" % (key, val))
        return (len(errors) == 0, "structural", errors[:20])


def assert_diff_conforms(diff: Dict[str, Any]) -> bool:
    """Hard conformance gate: raise ``DiffConformanceError`` if ``diff`` does not
    conform to cad_diff.v1. Returns True on success (it raises otherwise)."""
    ok, method, errors = validate_diff(diff)
    if not ok:
        raise DiffConformanceError(
            "cad_diff.v1 conformance FAILED (%s); %d error(s): %s"
            % (method, len(errors), "; ".join(errors[:8])))
    return True


def write_diff(diff: Dict[str, Any], path, *, enforce_schema: bool = True) -> str:
    """Write a cad_diff document (UTF-8, pretty). Returns the path written.

    Conformance gate (T1): when ``enforce_schema`` is true and ``diff`` carries
    the cad_diff.v1 schema tag, the diff is validated against the schema of
    record and a non-conformant diff raises ``DiffConformanceError`` BEFORE any
    bytes are written. Pass ``enforce_schema=False`` only for a deliberately
    partial or non-tagged document.
    """
    if enforce_schema and isinstance(diff, dict) and diff.get("schema") == DIFF_SCHEMA_ID:
        assert_diff_conforms(diff)
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(diff, ensure_ascii=False, indent=2))
        fh.write("\n")
    return str(path)


# --------------------------------------------------------------------------- #
# Entity indexing
# --------------------------------------------------------------------------- #

def index_entities_by_handle(ir: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Index an IR's entities[] by handle.

    Returns ``(by_handle, problems)`` where ``by_handle`` maps the (string)
    handle to its entity dict and ``problems`` lists diagnostic strings for
    entities that could not be joined: a missing/empty handle, or a duplicate
    handle (later occurrence wins, which is recorded). Handles are NOT
    case-folded -- IR handles are emitted as uppercase hex and compared verbatim
    so the join stays exact.
    """
    by_handle: Dict[str, Dict[str, Any]] = {}
    problems: List[str] = []
    entities = ir.get("entities")
    if not isinstance(entities, list):
        problems.append("entities[] missing or not a list")
        return by_handle, problems
    for i, ent in enumerate(entities):
        if not isinstance(ent, dict):
            problems.append("entity at index %d is not an object" % i)
            continue
        handle = ent.get("handle")
        if not isinstance(handle, str) or not handle.strip():
            problems.append("entity at index %d has no usable handle (cannot join)" % i)
            continue
        if handle in by_handle:
            problems.append("duplicate handle %r (later occurrence kept)" % handle)
        by_handle[handle] = ent
    return by_handle, problems


# --------------------------------------------------------------------------- #
# Diff scope (config/diff_scope.json) -- see module docstring "Diff scope"
# --------------------------------------------------------------------------- #

def load_diff_scope_config() -> Dict[str, Any]:
    """Load ``config/diff_scope.json`` (BOM-tolerant).

    Truthful degradation: a missing/unreadable/malformed config file falls back
    to the documented in-code default rather than crashing -- the same pattern
    ``_import_optional`` uses for the sibling-lane import.
    """
    try:
        with open(_DIFF_SCOPE_CONFIG_PATH, "r", encoding=_JSON_ENCODING) as fh:
            cfg = json.load(fh)
        if isinstance(cfg, dict) and cfg.get("default_scope") in VALID_DIFF_SCOPES:
            return cfg
    except Exception:  # pragma: no cover - defensive; config truly unreadable
        pass
    return {"default_scope": MODELSPACE_ENTITIES_ONLY, "freeze_scope": FULL_DATABASE}


def _resolve_diff_scope(diff_scope: Optional[str]) -> str:
    """Resolve the effective scope: an explicit arg wins, else the config default.

    Fails loud (``ValueError``) on an unrecognized scope rather than silently
    falling back to a default -- a typo'd scope name is a bug, not a preference.
    """
    scope = diff_scope or load_diff_scope_config().get("default_scope", MODELSPACE_ENTITIES_ONLY)
    if scope not in VALID_DIFF_SCOPES:
        raise ValueError("diff_scope must be one of %s, got %r" % (VALID_DIFF_SCOPES, scope))
    return scope


def _build_seed_baseline_masks(mask: Optional[List[Dict[str, Any]]],
                                profile: Dict[str, Any]
                               ) -> Tuple[set, set]:
    """Split a ``seed_baseline_mask`` into (exact fingerprints, (dxf_name,layer) wildcards).

    A mask entry carrying a ``"geometry"`` key matches only entities whose
    geometry fingerprint is equal within ``profile`` (an exact graphical-entity
    match); one without it matches ANY geometry for its ``(dxf_name, layer)``
    pair (a symbol-table-record-style wildcard -- most seed default records,
    e.g. a layer or linetype definition, are not shaped like a graphical
    entity at all). Non-dict entries are ignored, not silently coerced.
    """
    exact: set = set()
    wildcard: set = set()
    for m in (mask or []):
        if not isinstance(m, dict):
            continue
        if "geometry" in m:
            exact.add(_canonical(_geometry_fingerprint(m, profile)))
        else:
            wildcard.add((m.get("dxf_name"), m.get("layer")))
    return exact, wildcard


def _apply_diff_scope(ir: Dict[str, Any], scope: str,
                       seed_baseline_mask: Optional[List[Dict[str, Any]]],
                       profile: Dict[str, Any]
                      ) -> Tuple[Dict[str, Any], int]:
    """Return ``(scoped_ir, excluded_count)`` -- ``ir`` filtered per ``scope``.

    ``modelspace_entities_only``: keep entities whose ``space`` is ``"model"``
    (``ir_builder``'s own default when a producer omits ``space``), dropping
    any other-space entity so a future layout/paperspace extraction does not
    silently widen today's diff population.

    ``full_database``: keep every space; additionally, when ``seed_baseline_mask``
    is supplied, drop entities matching the mask (the blank-seed default records
    that would otherwise pollute a full-database diff, H-R18). No mask => no
    subtraction (no-fake-success: F4's real baseline is not yet minted).

    The returned IR is a shallow copy (only ``entities`` is replaced), so
    ``source`` / ``coverage_level`` / etc. pass through unchanged for
    ``_state_ref`` and the diagnostics coverage fields.
    """
    ir = ir or {}
    entities = [e for e in (ir.get("entities") or []) if isinstance(e, dict)]

    if scope == FULL_DATABASE:
        exact, wildcard = _build_seed_baseline_masks(seed_baseline_mask, profile)
        if exact or wildcard:
            kept: List[Dict[str, Any]] = []
            excluded = 0
            for e in entities:
                if ((e.get("dxf_name"), e.get("layer")) in wildcard
                        or _canonical(_geometry_fingerprint(e, profile)) in exact):
                    excluded += 1
                else:
                    kept.append(e)
            entities = kept
        else:
            excluded = 0
    else:
        kept = [e for e in entities if (e.get("space") or "model") == "model"]
        excluded = len(entities) - len(kept)
        entities = kept

    scoped = dict(ir)
    scoped["entities"] = entities
    return scoped, excluded


# --------------------------------------------------------------------------- #
# Field-level comparison
# --------------------------------------------------------------------------- #

def _canonical(value: Any) -> Any:
    """Return a canonical, order-stable, JSON-comparable form of a value.

    Dicts are turned into sorted-key tuples and lists are recursed element-wise
    so two structurally-equal geometries compare equal regardless of key
    insertion order. Numbers are left as-is (no rounding) to keep the compare
    exact; callers that need tolerance can pre-round.
    """
    if isinstance(value, dict):
        return tuple(sorted((k, _canonical(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_canonical(v) for v in value)
    return value


def _bbox_changed(pre: Any, post: Any) -> bool:
    """True when two IR bboxes differ. Empty/absent boxes compare as themselves."""
    return _canonical(pre) != _canonical(post)


def _geometry_changed(pre: Any, post: Any) -> bool:
    """True when two IR geometry payloads differ (canonical structural compare)."""
    return _canonical(pre) != _canonical(post)


def _changed_geometry_keys(pre_geom: Any, post_geom: Any) -> List[str]:
    """List the geometry leaf keys that differ, as ``geometry.<key>``.

    When the whole geometry differs but the change cannot be localized to
    individual keys (e.g. one side is not a dict), returns ``["geometry"]``.
    """
    if not isinstance(pre_geom, dict) or not isinstance(post_geom, dict):
        return ["geometry"]
    keys = set(pre_geom.keys()) | set(post_geom.keys())
    changed: List[str] = []
    for k in keys:
        if _canonical(pre_geom.get(k)) != _canonical(post_geom.get(k)):
            changed.append("geometry.%s" % k)
    return sorted(changed) if changed else []


def classify_change(pre_entity: Dict[str, Any], post_entity: Dict[str, Any]) -> List[str]:
    """Return the sorted list of field names that changed between two entities.

    Compared fields: ``layer``, ``dxf_name`` (scalar), ``bbox`` (structural),
    and ``geometry`` (structural). When geometry differs, the specific changed
    leaves are also included as ``geometry.<key>`` so a consumer can see e.g.
    ``["geometry", "geometry.start"]``. An empty list means the two entities are
    structurally identical on the compared fields (i.e. unchanged).
    """
    if not isinstance(pre_entity, dict) or not isinstance(post_entity, dict):
        return []
    changed: List[str] = []
    for field in _SCALAR_COMPARE_FIELDS:
        if pre_entity.get(field) != post_entity.get(field):
            changed.append(field)
    if _bbox_changed(pre_entity.get("bbox"), post_entity.get("bbox")):
        changed.append("bbox")
    if _geometry_changed(pre_entity.get("geometry"), post_entity.get("geometry")):
        changed.append("geometry")
        changed.extend(_changed_geometry_keys(
            pre_entity.get("geometry"), post_entity.get("geometry")))
    return sorted(set(changed))


def _field_delta(pre_entity: Dict[str, Any], post_entity: Dict[str, Any],
                 changed_fields: List[str]) -> List[Dict[str, Any]]:
    """Build the schema ``fields[]`` delta list for a modified entity.

    One entry per changed top-level field (the ``geometry.<key>`` sub-entries
    are not duplicated here; the top-level ``geometry`` entry carries the whole
    before/after geometry, and the sub-keys are echoed under
    ``changed_subfields`` for convenience). before/after carry the actual values.
    """
    top_fields = [f for f in changed_fields if "." not in f]
    sub_by_top: Dict[str, List[str]] = {}
    for f in changed_fields:
        if "." in f:
            top, _, _rest = f.partition(".")
            sub_by_top.setdefault(top, []).append(f)
    deltas: List[Dict[str, Any]] = []
    for field in top_fields:
        entry: Dict[str, Any] = {
            "field": field,
            "before": pre_entity.get(field),
            "after": post_entity.get(field),
        }
        if field in sub_by_top:
            entry["changed_subfields"] = sorted(sub_by_top[field])
        deltas.append(entry)
    return deltas


# --------------------------------------------------------------------------- #
# State-ref construction
# --------------------------------------------------------------------------- #

def _state_ref(ir: Dict[str, Any], realized_count: int) -> Dict[str, Any]:
    """Build a cad_diff ``state_ref`` from an IR (kind=ir).

    ``ref`` prefers the IR's staged dwg_path, then dwg_name, else the schema id.
    sha256 is carried from source when present (integrity passthrough only --
    this module does not hash DWG bytes itself).
    """
    src = ir.get("source") or {}
    ref = (src.get("dwg_path") or src.get("dwg_name")
           or src.get("original_path") or IR_SCHEMA_ID)
    state: Dict[str, Any] = {"kind": "ir", "ref": str(ref), "entity_count": realized_count}
    sha = src.get("sha256")
    if isinstance(sha, str) and sha:
        state["sha256"] = sha
    return state


# --------------------------------------------------------------------------- #
# Deterministic diff id
# --------------------------------------------------------------------------- #

def _deterministic_diff_id(pre_ir: Dict[str, Any], post_ir: Dict[str, Any],
                           comparison_basis: str = "handle",
                           diff_scope: Optional[str] = None,
                           tolerance_profile: Optional[Dict[str, Any]] = None) -> str:
    """Content-hash the two IRs for a stable, basis/scope-aware id.

    The id is a function of the inputs only (no time, no randomness), so
    re-diffing the same pair of IRs under the same basis/scope yields the same
    ``diff_id``. ``comparison_basis`` and ``diff_scope`` are hashed in so the
    SAME IR pair under a different basis or scope never collides on one id
    (the SEED open caveat / RT-FOLD R4-06 basis-collision symptom).

    For ``comparison_basis == "handle"`` the signature uses each entity's
    join-relevant fields (handle/dxf_name/layer/bbox/geometry) -- unchanged
    from before, and deliberately still handle-SENSITIVE: that is the
    handle-basis join's actual contract, so reissued handles correctly produce
    a different id.

    For ``comparison_basis == "geometry"`` the signature MUST instead be
    handle-INDEPENDENT (RT-FOLD R4-06's dual-defect fix): it signs the sorted
    MULTISET of geometry fingerprints ``(dxf_name, layer, quantize(geometry))``
    -- see ``_geometry_fingerprint_multiset`` -- never handles, so a
    regenerated drawing whose engine reissued every handle still reproduces
    the IDENTICAL id on re-diff (two regen runs of the same source give the
    same geometry-basis ``diff_id``; the ledger key stays meaningful).
    """
    scope_key = diff_scope or ""

    if comparison_basis == "geometry":
        profile = tolerance_profile or default_tolerance_profile()
        payload_obj: Any = [
            "geometry",
            scope_key,
            _geometry_fingerprint_multiset(pre_ir, profile),
            _geometry_fingerprint_multiset(post_ir, profile),
        ]
    else:
        def sig(ir: Dict[str, Any]) -> List[Any]:
            by_handle, _ = index_entities_by_handle(ir)
            out: List[Any] = []
            for h in sorted(by_handle):
                e = by_handle[h]
                out.append([
                    h,
                    e.get("dxf_name"),
                    e.get("layer"),
                    e.get("bbox"),
                    _canonical(e.get("geometry")),
                ])
            return out

        payload_obj = [comparison_basis, scope_key,
                       _canonical(sig(pre_ir)), _canonical(sig(post_ir))]

    payload = json.dumps(payload_obj, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return "diff-%s" % digest


# --------------------------------------------------------------------------- #
# Geometry-fingerprint join (comparison_basis="geometry")
# --------------------------------------------------------------------------- #

#: geometry leaf key -> quantity kind, so tolerance lookup is mechanical rather
#: than guessed at each call site. Anything not listed defaults to "length"
#: (the common case: most numeric CAD geometry fields are coordinates/lengths).
_ANGLE_KEYS = frozenset({"start_angle", "end_angle", "rotation"})
# v2-A5 tolerance rigor fix: minor_ratio (an ELLIPSE's minor/major axis
# ratio, see dwg_graph_ir.v1.schema.json) is a dimensionless ratio exactly
# like scale/bulge -- before this fix it fell through to the "length" default
# and was compared with the (far looser, magnitude-widening) length
# tolerance, which could false-pass a real ratio edit smaller than the length
# tolerance but larger than the scale tolerance.
_SCALE_KEYS = frozenset({"scale", "bulge", "minor_ratio"})


def default_tolerance_profile(geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE
                              ) -> Dict[str, Any]:
    """Build the default v2-A5 per-quantity tolerance profile.

    ``geometry_tolerance`` seeds the "length" base tolerance only, keeping the
    existing ``compute_diff(..., geometry_tolerance=...)`` kwarg meaningful;
    angle/scale/large-coordinate stay independent constants so widening the
    length tolerance for one caller never silently widens angle comparisons
    (see ``_effective_tolerance``).
    """
    return {
        "length": geometry_tolerance,
        "angle": DEFAULT_ANGLE_TOLERANCE,
        "scale": DEFAULT_SCALE_TOLERANCE,
        "large_coordinate_threshold": LARGE_COORDINATE_THRESHOLD,
        "large_coordinate_relative_tolerance": LARGE_COORDINATE_RELATIVE_TOLERANCE,
    }


def _quantity_kind(key: Optional[str]) -> str:
    """Classify a geometry leaf key into a tolerance kind (default: "length")."""
    if key in _ANGLE_KEYS:
        return "angle"
    if key in _SCALE_KEYS:
        return "scale"
    return "length"


def _effective_tolerance(kind: str, value: float, profile: Dict[str, Any]) -> float:
    """Resolve the epsilon for one numeric leaf given its quantity ``kind``.

    Only "length" widens (never narrows) for magnitude past
    ``large_coordinate_threshold`` -- the unit/extent-scaling half of v2-A5. The
    widening is a function of THIS leaf's own magnitude only, so a huge
    coordinate on one field never loosens a sibling angle/scale field's
    tolerance (kinds never share state -- see boundary tests).

    CAUTION for hashing/quantization callers: because the widening scales
    PROPORTIONALLY to ``value`` (``tol = magnitude * rel_tol``), calling this
    per-scalar with EACH value's own magnitude to build a ``round(value / tol)``
    bucket collapses ``value / tol`` to the constant ``1 / rel_tol`` for every
    magnitude past the threshold -- two genuinely different large coordinates
    then land on the SAME bucket (large-coordinate false-pass). Hashing/
    quantization callers must resolve ONE shared tolerance for the whole
    comparison first via ``_resolve_tolerance_profile`` rather than calling
    this per-scalar with each leaf's own value.
    """
    base = profile.get(kind, profile.get("length", DEFAULT_GEOMETRY_TOLERANCE))
    if kind != "length":
        return base
    threshold = profile.get("large_coordinate_threshold", LARGE_COORDINATE_THRESHOLD)
    rel_tol = profile.get("large_coordinate_relative_tolerance",
                          LARGE_COORDINATE_RELATIVE_TOLERANCE)
    magnitude = abs(value)
    if magnitude <= threshold:
        return base
    return max(base, magnitude * rel_tol)


def _length_leaf_extent(value: Any, kind: str = "length") -> float:
    """Recursively find the max abs magnitude of any "length"-kind numeric leaf
    inside a geometry payload (mirrors ``_quantize``'s traversal and per-key
    kind reclassification, but MEASURES instead of snapping). Used only to
    seed ``_resolve_tolerance_profile``'s drawing-extent reference magnitude.
    """
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return abs(float(value)) if kind == "length" else 0.0
    if isinstance(value, dict):
        return max((_length_leaf_extent(v, _quantity_kind(k)) for k, v in value.items()),
                  default=0.0)
    if isinstance(value, (list, tuple)):
        return max((_length_leaf_extent(v, kind) for v in value), default=0.0)
    return 0.0


def _drawing_length_extent(*irs: Dict[str, Any]) -> float:
    """Max abs magnitude of any "length"-kind geometry leaf across every
    entity in ``irs`` (0.0 if none) -- the shared reference magnitude
    ``_resolve_tolerance_profile`` widens the "length" tolerance from, so both
    sides of a comparison always resolve to the identical tolerance."""
    extent = 0.0
    for ir in irs:
        for e in ((ir or {}).get("entities") or []):
            if isinstance(e, dict):
                extent = max(extent, _length_leaf_extent(e.get("geometry")))
    return extent


def _resolve_tolerance_profile(profile: Dict[str, Any], *irs: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve ``profile``'s "length" tolerance ONCE for this whole comparison
    (v2-A5 large-coordinate false-pass fix, RT-FOLD F5 tolerance rigor).

    Do NOT re-derive a per-scalar relative tolerance during hashing/matching
    -- see ``_effective_tolerance``'s caution note. Instead this widens the
    "length" tolerance exactly ONCE, from the combined drawing extent of
    ``irs`` (shared by both sides of the comparison, never from an individual
    scalar's own magnitude), and pins ``large_coordinate_threshold`` to
    infinity in the returned profile so no downstream per-leaf
    ``_effective_tolerance("length", ...)`` call can re-derive (and re-break)
    the widening from its own scalar. This keeps the widening's purpose intact
    (large-site-scale roundtrip noise still must not false-fail) while
    restoring the magnitude information that per-scalar widening was
    destroying (two coordinates that differ by more than the shared tolerance
    now always land on different buckets/comparisons, regardless of how large
    both happen to be).
    """
    resolved = dict(profile)
    extent = _drawing_length_extent(*irs)
    resolved["length"] = _effective_tolerance("length", extent, profile)
    resolved["large_coordinate_threshold"] = float("inf")
    return resolved


def _quantize(value: Any, profile: Dict[str, Any], kind: str = "length") -> Any:
    """Recursively snap numeric leaves in ``value`` onto a per-quantity grid.

    AutoCAD COMPARETOLERANCE analog, v2-A5 per-quantity edition: two geometries
    whose numeric leaves differ by less than that leaf's effective tolerance
    (``_effective_tolerance``) quantize to the same integer grid point and
    therefore compare equal once passed through ``_canonical``. ``kind`` seeds
    the classification for scalar leaves; dict keys reclassify their own values
    via ``_quantity_kind`` as recursion descends (so a geometry dict's
    ``rotation`` quantizes as an angle even though its sibling ``center``
    quantizes as a length), and list elements inherit their parent key's kind
    (every number inside ``center`` is a length). ``bool`` is excluded from the
    numeric branch (it is an int subclass but never a coordinate); a
    non-positive tolerance disables snapping for that leaf (exact compare).
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        tol = _effective_tolerance(kind, float(value), profile)
        if tol <= 0:
            return value
        return round(value / tol)
    if isinstance(value, dict):
        return {k: _quantize(v, profile, _quantity_kind(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_quantize(v, profile, kind) for v in value]
    return value


def _geometry_fingerprint(entity: Dict[str, Any], profile: Dict[str, Any]
                          ) -> Tuple[Any, Any, Any]:
    """Build the ``(dxf_name, layer, geometry)`` join key for basis="geometry".

    Two entities with an equal fingerprint are the same physical entity
    regardless of DWG handle -- this is what lets ``comparison_basis="geometry"``
    report zero changes against a regenerated drawing whose engine reissued every
    handle (a handle-basis diff can never do that; see the module docstring).
    The geometry leg reuses ``_canonical`` (the same structural normalizer
    ``_geometry_changed`` uses) over the ``profile``-quantized geometry, so two
    geometries that are structurally equal after quantization hash identically.
    """
    geom_key = _canonical(_quantize(entity.get("geometry"), profile))
    return (entity.get("dxf_name"), entity.get("layer"), geom_key)


def _geometry_fingerprint_multiset(ir: Dict[str, Any], profile: Dict[str, Any]) -> List[Any]:
    """Return the SORTED multiset of an IR's entities' geometry fingerprints.

    Handle-independent by construction (fingerprints never carry a handle), so
    two independently-regenerated IRs of the same source -- fresh handles each
    run -- yield the IDENTICAL multiset. This is what ``_deterministic_diff_id``
    signs for ``comparison_basis=="geometry"`` (RT-FOLD R4-06). Sort key is
    ``repr`` (fingerprints nest arbitrary str/float/None/dict-derived values,
    not always mutually orderable; this is only a canonical iteration order,
    not user-visible data -- same rationale as ``_compute_diff_geometry_basis``).
    """
    entities = [e for e in (ir.get("entities") or []) if isinstance(e, dict)]
    fps = [_canonical(_geometry_fingerprint(e, profile)) for e in entities]
    fps.sort(key=repr)
    return fps


def _exact_fingerprint(entity: Dict[str, Any]) -> Tuple[Any, Any, Any]:
    """Byte-exact ``(dxf_name, layer, geometry)`` key -- NO tolerance and NO
    quantization, unlike ``_geometry_fingerprint``. Two entities sharing this
    key are unambiguously the same geometry regardless of which tolerance
    profile is active, so this tier can never itself false-pass (collapse two
    genuinely different values) or false-fail (straddle a rounding boundary)
    -- see ``_compute_diff_geometry_basis`` tier 1.
    """
    return (entity.get("dxf_name"), entity.get("layer"), _canonical(entity.get("geometry")))


def _bucket_by_exact_fingerprint(entities: List[Dict[str, Any]]
                                ) -> Dict[Tuple[Any, Any, Any], List[Dict[str, Any]]]:
    """Group entities by ``_exact_fingerprint``, preserving each bucket's input order."""
    buckets: Dict[Tuple[Any, Any, Any], List[Dict[str, Any]]] = {}
    for ent in entities:
        if isinstance(ent, dict):
            buckets.setdefault(_exact_fingerprint(ent), []).append(ent)
    return buckets


def _by_handle_sort_key(ent: Dict[str, Any]) -> str:
    """Sort key used to pair up same-bucket entities deterministically."""
    return ent.get("handle") or ""


def _geometry_within_tolerance(pre_geom: Any, post_geom: Any, profile: Dict[str, Any],
                               kind: str = "length") -> bool:
    """True when two geometry payloads are equal within ``profile``'s
    per-quantity tolerance, leaf-by-leaf, via a DIRECT ``abs(a - b) <= tol``
    compare -- the pairwise fix for the half-bucket false-fail defect a
    round()-based hash bucket cannot avoid (two values within tolerance of
    each other can still straddle a rounding-grid boundary and hash unequal;
    a direct threshold compare has no grid to straddle in the first place).
    ``kind`` seeds the classification for scalar leaves; dict keys reclassify
    their own values via ``_quantity_kind`` as recursion descends and list
    elements inherit their parent key's kind -- mirrors ``_quantize``'s
    traversal. A structural mismatch (missing dict key, differing list
    length, non-numeric type mismatch) is never "within tolerance".
    """
    if isinstance(pre_geom, bool) or isinstance(post_geom, bool):
        return pre_geom == post_geom
    if isinstance(pre_geom, (int, float)) and isinstance(post_geom, (int, float)):
        magnitude = max(abs(float(pre_geom)), abs(float(post_geom)))
        tol = _effective_tolerance(kind, magnitude, profile)
        return abs(float(pre_geom) - float(post_geom)) <= tol
    if isinstance(pre_geom, dict) and isinstance(post_geom, dict):
        if set(pre_geom.keys()) != set(post_geom.keys()):
            return False
        return all(_geometry_within_tolerance(pre_geom[k], post_geom[k], profile,
                                              _quantity_kind(k))
                  for k in pre_geom)
    if isinstance(pre_geom, (list, tuple)) and isinstance(post_geom, (list, tuple)):
        if len(pre_geom) != len(post_geom):
            return False
        return all(_geometry_within_tolerance(a, b, profile, kind)
                  for a, b in zip(pre_geom, post_geom))
    return pre_geom == post_geom


def _match_leftovers_within_tolerance(
        leftover_pre: List[Dict[str, Any]], leftover_post: List[Dict[str, Any]],
        profile: Dict[str, Any]
       ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    """Tier 1.5: pairwise-tolerant match among tier-1 byte-exact-match leftovers.

    Grouped by ``(dxf_name, layer)`` (nothing here matched byte-for-byte, so
    geometry is otherwise unknown-equal), each remaining pre entity is matched,
    in handle-sorted order, against the first not-yet-matched post entity
    (also handle-sorted) whose geometry is ``_geometry_within_tolerance`` --
    deterministic greedy first-fit, mirroring the handle-sort tie-break used
    throughout this module. This is what lets floating-point roundtrip jitter
    (a regenerated drawing whose engine reissued handles AND perturbed a
    coordinate by less than the tolerance) still report ``unchanged`` without
    the hash-bucket defects a fingerprint-multiset join cannot avoid.

    Returns ``(still_unmatched_pre, still_unmatched_post, matched_count)``.
    """
    def _type_layer(ent: Dict[str, Any]) -> Tuple[Any, Any]:
        return (ent.get("dxf_name"), ent.get("layer"))

    pre_groups: Dict[Tuple[Any, Any], List[Dict[str, Any]]] = {}
    for e in leftover_pre:
        pre_groups.setdefault(_type_layer(e), []).append(e)
    post_groups: Dict[Tuple[Any, Any], List[Dict[str, Any]]] = {}
    for e in leftover_post:
        post_groups.setdefault(_type_layer(e), []).append(e)

    still_pre: List[Dict[str, Any]] = []
    still_post: List[Dict[str, Any]] = []
    matched = 0

    for tl in sorted(set(pre_groups) | set(post_groups), key=lambda k: (k[0] or "", k[1] or "")):
        pre_list = sorted(pre_groups.get(tl, []), key=_by_handle_sort_key)
        post_list = sorted(post_groups.get(tl, []), key=_by_handle_sort_key)
        used_post = [False] * len(post_list)
        for pre_e in pre_list:
            match_idx = None
            for j, post_e in enumerate(post_list):
                if used_post[j]:
                    continue
                if _geometry_within_tolerance(pre_e.get("geometry"), post_e.get("geometry"),
                                              profile):
                    match_idx = j
                    break
            if match_idx is None:
                still_pre.append(pre_e)
            else:
                used_post[match_idx] = True
                matched += 1
        still_post.extend(post_e for j, post_e in enumerate(post_list) if not used_post[j])

    return still_pre, still_post, matched


def _compute_diff_geometry_basis(pre_ir: Dict[str, Any], post_ir: Dict[str, Any],
                                 tolerance_profile: Dict[str, Any],
                                 diff_scope: Optional[str] = None) -> Dict[str, Any]:
    """compute_diff's geometry-fingerprint join (comparison_basis="geometry").

    Matching is three-tier, all deterministic (ties broken by sorted handle):

      1. Entities with a BYTE-EXACT fingerprint match (``dxf_name``, ``layer``,
         and geometry literally equal -- no tolerance, no quantization) on both
         sides are ``unchanged``. Duplicate fingerprints are matched as a
         multiset (pairs up to ``min(count_pre, count_post)`` per bucket).
      2. Whatever is left is matched PAIRWISE within ``tolerance_profile``
         (v2-A5 per-quantity), grouped by ``(dxf_name, layer)`` -- a direct
         ``abs(a - b) <= tol`` compare (``_geometry_within_tolerance``), never a
         hash/bucket, so this tier is immune to both the large-coordinate
         false-pass and the half-bucket false-fail a fingerprint HASH cannot
         avoid (see ``_resolve_tolerance_profile`` / ``_geometry_within_tolerance``).
         A match here is also ``unchanged`` (floating-point roundtrip jitter,
         not a real edit).
      3. Whatever is STILL left is paired up by ``(dxf_name, layer)`` alone --
         genuinely different geometry, by construction of steps 1-2 -- and
         classified via ``classify_change``, so a real geometry edit surfaces as
         ``modified`` instead of a fake added+removed pair.
      4. Anything still unpaired (a type/layer with more entities on one side
         than the other) is ``added`` (post-only) / ``removed`` (pre-only).

    ``pre_ir`` / ``post_ir`` are expected already scope-filtered (see
    ``_apply_diff_scope``); ``diff_scope`` is carried through only for
    diagnostics + the ``diff_id`` hash, not re-applied here.

    Returns a ``cad_diff.v1`` dict shaped identically to ``compute_diff``'s
    handle-basis output (same summary/changed_handles/projection keys), with
    ``diagnostics.comparison_basis == "geometry"``.
    """
    pre_ir = pre_ir or {}
    post_ir = post_ir or {}
    # tolerance_profile stays the RAW, caller-requested profile (surfaced
    # verbatim in diagnostics below); `profile` is the ONE shared tolerance
    # resolved from the combined drawing extent (v2-A5 large-coordinate
    # false-pass fix) used for every match decision + the diff_id hash.
    profile = _resolve_tolerance_profile(tolerance_profile, pre_ir, post_ir)

    pre_entities = [e for e in (pre_ir.get("entities") or []) if isinstance(e, dict)]
    post_entities = [e for e in (post_ir.get("entities") or []) if isinstance(e, dict)]

    # Tier 1: BYTE-EXACT fingerprint match -> unchanged (multiset: pair
    # min(count) per bucket). No tolerance/quantization here at all, so this
    # tier can never itself false-pass or false-fail on a tolerance boundary.
    pre_fp = _bucket_by_exact_fingerprint(pre_entities)
    post_fp = _bucket_by_exact_fingerprint(post_entities)

    unchanged_count = 0
    leftover_pre: List[Dict[str, Any]] = []
    leftover_post: List[Dict[str, Any]] = []
    # key=repr: fingerprints nest arbitrary geometry values (str/float/None mixed),
    # which is not safely orderable directly -- repr() is always comparable and
    # deterministic, and this is only an iteration order, not user-visible data.
    for fp in sorted(set(pre_fp) | set(post_fp), key=repr):
        pre_list = sorted(pre_fp.get(fp, []), key=_by_handle_sort_key)
        post_list = sorted(post_fp.get(fp, []), key=_by_handle_sort_key)
        n = min(len(pre_list), len(post_list))
        unchanged_count += n
        leftover_pre.extend(pre_list[n:])
        leftover_post.extend(post_list[n:])

    # Tier 1.5: pairwise-tolerant match among the byte-exact-match leftovers
    # (v2-A5 tolerance rigor fix -- see _match_leftovers_within_tolerance).
    leftover_pre, leftover_post, tol_matched = _match_leftovers_within_tolerance(
        leftover_pre, leftover_post, profile)
    unchanged_count += tol_matched

    # Tier 2: pair remaining leftovers by (dxf_name, layer) only -> modified via classify_change.
    def _type_layer(ent: Dict[str, Any]) -> Tuple[Any, Any]:
        return (ent.get("dxf_name"), ent.get("layer"))

    pre_tl: Dict[Tuple[Any, Any], List[Dict[str, Any]]] = {}
    for e in leftover_pre:
        pre_tl.setdefault(_type_layer(e), []).append(e)
    post_tl: Dict[Tuple[Any, Any], List[Dict[str, Any]]] = {}
    for e in leftover_post:
        post_tl.setdefault(_type_layer(e), []).append(e)

    changed_handles: List[Dict[str, Any]] = []
    by_type: Dict[str, Dict[str, int]] = {}
    layer_changes: List[Dict[str, Any]] = []
    geometry_changes: List[Dict[str, Any]] = []
    bbox_changes: List[Dict[str, Any]] = []
    modified_count = 0
    added_entities: List[Dict[str, Any]] = []
    removed_entities: List[Dict[str, Any]] = []

    def _bump(dxf: str, kind: str) -> None:
        slot = by_type.setdefault(dxf or "", {"added": 0, "removed": 0, "modified": 0})
        slot[kind] += 1

    for tl in sorted(set(pre_tl) | set(post_tl), key=lambda k: (k[0] or "", k[1] or "")):
        pre_list = sorted(pre_tl.get(tl, []), key=_by_handle_sort_key)
        post_list = sorted(post_tl.get(tl, []), key=_by_handle_sort_key)
        n = min(len(pre_list), len(post_list))
        for pre_e, post_e in zip(pre_list[:n], post_list[:n]):
            fields = classify_change(pre_e, post_e)
            if not fields:
                # Defensive: an arbitrary same-bucket pairing landed on two
                # entities that turn out geometry-identical (possible under
                # duplicate fingerprints split across tier 1/2 by count
                # mismatch). Correct outcome is unchanged, not a fake modify.
                unchanged_count += 1
                continue
            modified_count += 1
            dxf = post_e.get("dxf_name", pre_e.get("dxf_name", "")) or ""
            handle = post_e.get("handle") or pre_e.get("handle") or ""
            rec: Dict[str, Any] = {
                "handle": handle,
                "change": "modified",
                "fields": _field_delta(pre_e, post_e, fields),
            }
            if dxf:
                rec["dxf_name"] = dxf
            post_layer = post_e.get("layer")
            if isinstance(post_layer, str):
                rec["layer"] = post_layer
            changed_handles.append(rec)
            _bump(dxf, "modified")

            if "layer" in fields:
                layer_changes.append({
                    "handle": handle, "dxf_name": dxf,
                    "before": pre_e.get("layer"), "after": post_e.get("layer"),
                })
            if "geometry" in fields:
                geometry_changes.append({
                    "handle": handle, "dxf_name": dxf,
                    "changed_keys": [f for f in fields if f.startswith("geometry.")],
                })
            if "bbox" in fields:
                bbox_changes.append({
                    "handle": handle, "dxf_name": dxf,
                    "before": pre_e.get("bbox"), "after": post_e.get("bbox"),
                })
        added_entities.extend(post_list[n:])
        removed_entities.extend(pre_list[n:])

    for ent in sorted(added_entities, key=_by_handle_sort_key):
        dxf = ent.get("dxf_name", "") or ""
        rec = {"handle": ent.get("handle") or "", "change": "added"}
        if dxf:
            rec["dxf_name"] = dxf
        layer = ent.get("layer")
        if isinstance(layer, str):
            rec["layer"] = layer
        changed_handles.append(rec)
        _bump(dxf, "added")

    for ent in sorted(removed_entities, key=_by_handle_sort_key):
        dxf = ent.get("dxf_name", "") or ""
        rec = {"handle": ent.get("handle") or "", "change": "removed"}
        if dxf:
            rec["dxf_name"] = dxf
        layer = ent.get("layer")
        if isinstance(layer, str):
            rec["layer"] = layer
        changed_handles.append(rec)
        _bump(dxf, "removed")

    _kind_order = {"added": 0, "removed": 1, "modified": 2}
    changed_handles.sort(key=lambda r: (_kind_order.get(r["change"], 9), r["handle"]))

    added_count = len(added_entities)
    deleted_count = len(removed_entities)
    entity_count_before = len(pre_entities)
    entity_count_after = len(post_entities)

    summary: Dict[str, Any] = {
        "added": added_count,
        "removed": deleted_count,
        "modified": modified_count,
        "unchanged": unchanged_count,
        "entity_count_before": entity_count_before,
        "entity_count_after": entity_count_after,
        "by_type": by_type,
        "created_count": added_count,
        "deleted_count": deleted_count,
        "modified_count": modified_count,
        "unchanged_count": unchanged_count,
    }

    warnings: List[str] = []
    if pre_ir.get("schema") != IR_SCHEMA_ID:
        warnings.append("before IR schema is %r (expected %s)"
                        % (pre_ir.get("schema"), IR_SCHEMA_ID))
    if post_ir.get("schema") != IR_SCHEMA_ID:
        warnings.append("after IR schema is %r (expected %s)"
                        % (post_ir.get("schema"), IR_SCHEMA_ID))

    diagnostics: Dict[str, Any] = {
        "comparison_basis": "geometry",
        # surfaced verbatim from the caller's request, not the internally
        # resolved/widened `profile` used for matching -- see the docstring.
        "geometry_tolerance": tolerance_profile.get("length"),
        "tolerance_profile": dict(tolerance_profile),
        "warnings": warnings,
        "errors": [],
        "pre_coverage_level": pre_ir.get("coverage_level"),
        "post_coverage_level": post_ir.get("coverage_level"),
    }

    return {
        "schema": DIFF_SCHEMA_ID,
        "diff_id": _deterministic_diff_id(pre_ir, post_ir, comparison_basis="geometry",
                                          diff_scope=diff_scope, tolerance_profile=profile),
        "before_ref": _state_ref(pre_ir, entity_count_before),
        "after_ref": _state_ref(post_ir, entity_count_after),
        "changed_handles": changed_handles,
        "summary": summary,
        "diagnostics": diagnostics,
        "layer_changes": layer_changes,
        "geometry_changes": geometry_changes,
        "bbox_changes": bbox_changes,
    }


# --------------------------------------------------------------------------- #
# Public diff
# --------------------------------------------------------------------------- #

def compute_diff(pre_ir: Dict[str, Any], post_ir: Dict[str, Any],
                 comparison_basis: str = "handle",
                 geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE,
                 diff_scope: Optional[str] = None,
                 seed_baseline_mask: Optional[List[Dict[str, Any]]] = None,
                 tolerance_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compute a deterministic structural diff between two dwg_graph_ir.v1 IRs.

    Args:
        pre_ir:  the 'before' IR document (ariadne.dwg_graph_ir.v1).
        post_ir: the 'after' IR document.
        comparison_basis: ``"handle"`` (default) joins entities on their DWG
            handle (see module docstring). ``"geometry"`` instead joins on
            ``(dxf_name, layer, geometry)`` within ``tolerance_profile``,
            independent of handle -- see ``_compute_diff_geometry_basis``.
        geometry_tolerance: the "length" base tolerance seeding the default
            per-quantity tolerance profile (v2-A5); used only when
            ``comparison_basis="geometry"`` and ``tolerance_profile`` is not
            given explicitly (the AutoCAD COMPARETOLERANCE analog).
        diff_scope: ``"modelspace_entities_only"`` (default) or
            ``"full_database"`` -- see the module docstring "Diff scope" and
            ``config/diff_scope.json``. ``None`` resolves the config's
            ``default_scope``.
        seed_baseline_mask: entity-shaped dicts to subtract under
            ``diff_scope="full_database"`` (a blank-seed's default
            symbol-table/block-definition records, node F4). Ignored under
            ``modelspace_entities_only`` -- see ``_apply_diff_scope``.
        tolerance_profile: an explicit v2-A5 per-quantity tolerance profile
            (``default_tolerance_profile()`` shape); overrides
            ``geometry_tolerance`` entirely when given. Used only when
            ``comparison_basis="geometry"``.

    Returns:
        A dict conforming to ``ariadne.cad_diff.v1``. Entities are joined on
        ``handle``: handles only in ``post`` are ``added``, only in ``pre`` are
        ``removed``, in both with a changed field are ``modified``. The diff body
        contains no timestamps and is fully determined by the two inputs (plus
        the basis/scope/tolerance chosen -- ``diff_id`` hashes all of that in,
        see ``_deterministic_diff_id``).

        In addition to the frozen schema fields (``changed_handles`` with change
        in added/removed/modified, ``summary`` with added/removed/modified), the
        report carries extension fields (allowed by the schema's
        additionalProperties:true) requested by the CAD OS Layer M02 contract:
        ``summary.created_count/deleted_count/modified_count/unchanged_count``,
        ``summary.by_type`` (per-DXF-type added/removed/modified), the
        ``layer_changes`` / ``geometry_changes`` / ``bbox_changes`` projections,
        and ``diagnostics.diff_scope`` / ``scope_excluded_before`` /
        ``scope_excluded_after`` (+ ``seed_baseline_excluded_before`` /
        ``_after`` aliases under ``full_database``).
    """
    resolved_scope = _resolve_diff_scope(diff_scope)
    profile = (tolerance_profile if tolerance_profile is not None
              else default_tolerance_profile(geometry_tolerance))

    pre_ir, pre_excluded = _apply_diff_scope(pre_ir or {}, resolved_scope,
                                             seed_baseline_mask, profile)
    post_ir, post_excluded = _apply_diff_scope(post_ir or {}, resolved_scope,
                                               seed_baseline_mask, profile)

    if comparison_basis == "geometry":
        diff = _compute_diff_geometry_basis(pre_ir, post_ir, profile, resolved_scope)
        diff["diagnostics"]["diff_scope"] = resolved_scope
        diff["diagnostics"]["scope_excluded_before"] = pre_excluded
        diff["diagnostics"]["scope_excluded_after"] = post_excluded
        if resolved_scope == FULL_DATABASE:
            diff["diagnostics"]["seed_baseline_excluded_before"] = pre_excluded
            diff["diagnostics"]["seed_baseline_excluded_after"] = post_excluded
        return diff

    pre_by_handle, pre_problems = index_entities_by_handle(pre_ir)
    post_by_handle, post_problems = index_entities_by_handle(post_ir)

    pre_handles = set(pre_by_handle)
    post_handles = set(post_by_handle)

    created = sorted(post_handles - pre_handles)
    deleted = sorted(pre_handles - post_handles)
    common = sorted(pre_handles & post_handles)

    changed_handles: List[Dict[str, Any]] = []

    # per-type net change accounting, keyed by DXF type.
    by_type: Dict[str, Dict[str, int]] = {}

    def _bump(dxf: str, kind: str) -> None:
        slot = by_type.setdefault(dxf or "", {"added": 0, "removed": 0, "modified": 0})
        slot[kind] += 1

    # added (present only in post)
    for h in created:
        ent = post_by_handle[h]
        dxf = ent.get("dxf_name", "") or ""
        rec: Dict[str, Any] = {"handle": h, "change": "added"}
        if dxf:
            rec["dxf_name"] = dxf
        layer = ent.get("layer")
        if isinstance(layer, str):
            rec["layer"] = layer
        changed_handles.append(rec)
        _bump(dxf, "added")

    # removed (present only in pre)
    for h in deleted:
        ent = pre_by_handle[h]
        dxf = ent.get("dxf_name", "") or ""
        rec = {"handle": h, "change": "removed"}
        if dxf:
            rec["dxf_name"] = dxf
        layer = ent.get("layer")
        if isinstance(layer, str):
            rec["layer"] = layer
        changed_handles.append(rec)
        _bump(dxf, "removed")

    # modified (present in both, changed) + projections
    modified_handles: List[str] = []
    unchanged_count = 0
    layer_changes: List[Dict[str, Any]] = []
    geometry_changes: List[Dict[str, Any]] = []
    bbox_changes: List[Dict[str, Any]] = []

    for h in common:
        pre_e = pre_by_handle[h]
        post_e = post_by_handle[h]
        fields = classify_change(pre_e, post_e)
        if not fields:
            unchanged_count += 1
            continue
        modified_handles.append(h)
        dxf = post_e.get("dxf_name", pre_e.get("dxf_name", "")) or ""
        rec = {
            "handle": h,
            "change": "modified",
            "fields": _field_delta(pre_e, post_e, fields),
        }
        if dxf:
            rec["dxf_name"] = dxf
        # report the post-layer for orientation; the per-field delta carries both.
        post_layer = post_e.get("layer")
        if isinstance(post_layer, str):
            rec["layer"] = post_layer
        changed_handles.append(rec)
        _bump(dxf, "modified")

        if "layer" in fields:
            layer_changes.append({
                "handle": h, "dxf_name": dxf,
                "before": pre_e.get("layer"), "after": post_e.get("layer"),
            })
        if "geometry" in fields:
            geometry_changes.append({
                "handle": h, "dxf_name": dxf,
                "changed_keys": [f for f in fields if f.startswith("geometry.")],
            })
        if "bbox" in fields:
            bbox_changes.append({
                "handle": h, "dxf_name": dxf,
                "before": pre_e.get("bbox"), "after": post_e.get("bbox"),
            })

    # stable ordering of changed_handles: by change kind then handle. The lists
    # above are already handle-sorted within each kind; concatenation order is
    # added, removed, modified. Re-sort defensively to guarantee determinism.
    _kind_order = {"added": 0, "removed": 1, "modified": 2}
    changed_handles.sort(key=lambda r: (_kind_order.get(r["change"], 9), r["handle"]))

    added_count = len(created)
    deleted_count = len(deleted)
    modified_count = len(modified_handles)
    entity_count_before = len(pre_handles)
    entity_count_after = len(post_handles)

    summary: Dict[str, Any] = {
        # frozen schema fields
        "added": added_count,
        "removed": deleted_count,
        "modified": modified_count,
        "unchanged": unchanged_count,
        "entity_count_before": entity_count_before,
        "entity_count_after": entity_count_after,
        "by_type": by_type,
        # CAD OS Layer M02 contract aliases (created/deleted naming)
        "created_count": added_count,
        "deleted_count": deleted_count,
        "modified_count": modified_count,
        "unchanged_count": unchanged_count,
    }

    # diagnostics: handle-exact comparison; surface unjoinable entities truthfully.
    warnings: List[str] = []
    errors: List[str] = []
    for label, probs in (("before", pre_problems), ("after", post_problems)):
        for p in probs:
            warnings.append("%s IR: %s" % (label, p))
    if pre_ir.get("schema") != IR_SCHEMA_ID:
        warnings.append("before IR schema is %r (expected %s)"
                        % (pre_ir.get("schema"), IR_SCHEMA_ID))
    if post_ir.get("schema") != IR_SCHEMA_ID:
        warnings.append("after IR schema is %r (expected %s)"
                        % (post_ir.get("schema"), IR_SCHEMA_ID))

    diagnostics: Dict[str, Any] = {
        "comparison_basis": "handle",
        "warnings": warnings,
        "errors": errors,
        "unjoinable_before": len(pre_problems),
        "unjoinable_after": len(post_problems),
        "pre_coverage_level": pre_ir.get("coverage_level"),
        "post_coverage_level": post_ir.get("coverage_level"),
    }

    diff: Dict[str, Any] = {
        "schema": DIFF_SCHEMA_ID,
        "diff_id": _deterministic_diff_id(pre_ir, post_ir, comparison_basis=comparison_basis,
                                          diff_scope=resolved_scope),
        "before_ref": _state_ref(pre_ir, entity_count_before),
        "after_ref": _state_ref(post_ir, entity_count_after),
        "changed_handles": changed_handles,
        "summary": summary,
        "diagnostics": diagnostics,
        # top-level projections (extension; additionalProperties:true)
        "layer_changes": layer_changes,
        "geometry_changes": geometry_changes,
        "bbox_changes": bbox_changes,
    }
    diff["diagnostics"]["diff_scope"] = resolved_scope
    diff["diagnostics"]["scope_excluded_before"] = pre_excluded
    diff["diagnostics"]["scope_excluded_after"] = post_excluded
    if resolved_scope == FULL_DATABASE:
        diff["diagnostics"]["seed_baseline_excluded_before"] = pre_excluded
        diff["diagnostics"]["seed_baseline_excluded_after"] = post_excluded
    return diff


# --------------------------------------------------------------------------- #
# Self-demo (__main__): diff two synthetic IRs, assert created + modified
# --------------------------------------------------------------------------- #

def _mutated_fixture(base_ir: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep copy of ``base_ir`` with one added and one modified entity.

    Modification: the LINE (handle 2A7) has its layer changed 0 -> DEMO_MOVED and
    its geometry end point shifted. Addition: a new CIRCLE with a fresh handle.
    diagnostics.entity_count is kept consistent with the new entities[] length so
    the post IR is itself internally valid.
    """
    post = json.loads(json.dumps(base_ir))  # deep copy (stdlib)
    ents = post.get("entities") or []

    # modify the LINE: layer + geometry.end
    for e in ents:
        if e.get("handle") == "2A7" and e.get("dxf_name") == "LINE":
            e["layer"] = "DEMO_MOVED"
            geom = e.setdefault("geometry", {"kind": "line"})
            geom["end"] = [20.0, 5.0, 0.0]
            e["bbox"] = [0.0, 0.0, 0.0, 20.0, 5.0, 0.0]
            break

    # add a brand-new CIRCLE entity (unique handle)
    new_ent = {
        "handle": "2FF",
        "class": "AcDbCircle",
        "dxf_name": "CIRCLE",
        "owner_handle": ents[0].get("owner_handle", "") if ents else "",
        "space": "model",
        "layer": "NEWLAYER",
        "bbox": [98.0, 98.0, 0.0, 102.0, 102.0, 0.0],
        "geometry": {"kind": "circle", "center": [100.0, 100.0, 0.0], "radius": 2.0},
        "source": {"extractor": "cad_diff.selfdemo", "decoded": True},
    }
    ents.append(new_ent)
    post["entities"] = ents

    # keep the post IR internally consistent (truth gate) for any downstream read.
    diag = post.setdefault("diagnostics", {})
    diag["entity_count"] = len(ents)
    diag["realized_entity_count"] = len(ents)
    by_type: Dict[str, int] = {}
    for e in ents:
        dxf = e.get("dxf_name", "") or ""
        by_type[dxf] = by_type.get(dxf, 0) + 1
    diag["entities_by_type"] = by_type
    return post


def _selftest() -> int:
    ir_builder = _import_optional("ir_builder")
    if ir_builder is None or not hasattr(ir_builder, "make_fixture_ir"):
        # Truthful degradation: cannot self-demo without the sibling fixture.
        print("== cad_diff self-demo ==")
        print("ir_builder.make_fixture_ir unavailable -> NOT_IMPLEMENTED (no fake PASS)")
        return 2

    pre = ir_builder.make_fixture_ir()
    post = _mutated_fixture(pre)

    diff = compute_diff(pre, post)

    # locate the records we asserted on
    by_handle_change = {(r["handle"], r["change"]): r for r in diff["changed_handles"]}
    added_rec = by_handle_change.get(("2FF", "added"))
    modified_rec = by_handle_change.get(("2A7", "modified"))

    summary = diff["summary"]

    print("== cad_diff self-demo ==")
    print("schema                 : %s" % diff["schema"])
    print("diff_id                : %s" % diff["diff_id"])
    print("before entities        : %s" % diff["before_ref"].get("entity_count"))
    print("after  entities        : %s" % diff["after_ref"].get("entity_count"))
    print("summary added/removed/modified/unchanged : %d/%d/%d/%d"
          % (summary["added"], summary["removed"], summary["modified"],
             summary["unchanged"]))
    print("summary created/deleted/modified (alias) : %d/%d/%d"
          % (summary["created_count"], summary["deleted_count"],
             summary["modified_count"]))
    print("by_type                : %s" % json.dumps(summary["by_type"],
                                                     ensure_ascii=False, sort_keys=True))
    print("added handle 2FF       : %s" % ("present" if added_rec else "MISSING"))
    if modified_rec:
        fields = [f["field"] for f in modified_rec.get("fields", [])]
        print("modified handle 2A7    : fields=%s" % sorted(fields))
    print("layer_changes          : %s" % json.dumps(diff["layer_changes"],
                                                     ensure_ascii=False))
    print("geometry_changes       : %s" % json.dumps(diff["geometry_changes"],
                                                     ensure_ascii=False))
    print("diagnostics.basis      : %s" % diff["diagnostics"]["comparison_basis"])

    # determinism: recompute and compare byte-for-byte.
    diff2 = compute_diff(pre, post)
    deterministic = (json.dumps(diff, sort_keys=True, ensure_ascii=False)
                     == json.dumps(diff2, sort_keys=True, ensure_ascii=False))
    print("determinism (re-run)   : %s" % deterministic)

    # ---- assertions ----
    added_ok = added_rec is not None and added_rec["change"] == "added"
    modified_fields = ([f["field"] for f in modified_rec["fields"]]
                       if modified_rec else [])
    modified_ok = (modified_rec is not None
                   and modified_rec["change"] == "modified"
                   and "layer" in modified_fields
                   and "geometry" in modified_fields)
    counts_ok = (summary["added"] == 1 and summary["removed"] == 0
                 and summary["modified"] == 1
                 and summary["created_count"] == 1
                 and summary["deleted_count"] == 0
                 and summary["unchanged_count"] == summary["unchanged"])
    # the two untouched fixture entities (CIRCLE 2A8, INSERT 2A9) stay unchanged
    unchanged_ok = summary["unchanged"] == 2
    schema_ok = diff["schema"] == DIFF_SCHEMA_ID
    basis_ok = diff["diagnostics"]["comparison_basis"] == "handle"
    # classify_change directly: a pure layer change shows exactly that field set
    line_pre = next(e for e in pre["entities"] if e["handle"] == "2A7")
    line_post = next(e for e in post["entities"] if e["handle"] == "2A7")
    classify_fields = classify_change(line_pre, line_post)
    classify_ok = ("layer" in classify_fields and "geometry" in classify_fields
                   and "geometry.end" in classify_fields)
    # identical IRs => empty diff (no false positives)
    self_diff = compute_diff(pre, pre)
    self_ok = (self_diff["summary"]["added"] == 0
               and self_diff["summary"]["removed"] == 0
               and self_diff["summary"]["modified"] == 0
               and self_diff["summary"]["unchanged"] == len(pre["entities"]))

    print("added_ok=%s modified_ok=%s counts_ok=%s unchanged_ok=%s "
          "schema_ok=%s basis_ok=%s classify_ok=%s self_ok=%s deterministic=%s"
          % (added_ok, modified_ok, counts_ok, unchanged_ok, schema_ok,
             basis_ok, classify_ok, self_ok, deterministic))

    passed = all([added_ok, modified_ok, counts_ok, unchanged_ok, schema_ok,
                  basis_ok, classify_ok, self_ok, deterministic])
    print("RESULT                 : %s" % ("PASS" if passed else "FAIL"))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(_selftest())
