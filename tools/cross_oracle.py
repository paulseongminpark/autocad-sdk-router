#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cross_oracle.py -- CAD OS Layer WAVE-0 F1.5: the independent cross-oracle.

Every roundtrip gate in this repo (F3's W/D halves, ``cad_diff.py``) reads the
STAGED regenerated DWG back through the SAME native pipeline it was written
with. That is a single-extractor monoculture (H-R29 / RT-FOLD R4-01): if the
native extractor correlated-drops a field on both the pre- and post- read, the
diff sees ``0 == 0`` and reports a clean PASS on data it never actually looked
at. F1.5 closes that hole by re-extracting the SAME staged file with a
*different* engine -- ``autocad-router.ps1 -Action run -Intent dwg`` (accoreconsole,
ObjectARX/ObjectDBX/AutoLISP ground-truth) or ``-Intent dxf`` (ezdxf, fast/lossy)
-- and certifying the native IR against that independent oracle IR.

v2-A1 upgrade (``.build/cados_plan/final/PLAN.md`` Sec. 0.6, folded AUTHORITATIVE)
-----------------------------------------------------------------------------
The original F1.5 sketch was a per-kind COUNT spot-check on >=1 entity/kind --
"good enough" only until a reviewer noticed the sample could miss exactly the
entities whose field the native extractor silently drops. This module
implements the upgraded contract instead:

  (a) For every oracle-CERTIFIED ``(kind, field)`` pair, the multiset of
      populated values is compared over **ALL** entities of that kind (not a
      sample): ``multiset(oracle_values) == multiset(native_values)``. A
      mismatch is ``disagreement`` (exit 7, ORACLE-DISAGREE).
  (b) A second, higher-priority pass is the invisible-data tripwire: a field
      the oracle POPULATED (present, non-None) that the native IR left
      absent/null for a net number of entities is ``tripwire`` (exit 4,
      HOLLOW) -- the native extractor dropped something the independent
      reference actually has. This is checked and reported BEFORE the
      value-multiset compare so a silent drop is never merely reported as a
      generic "disagreement".
  (c) A field the oracle entity carries that is outside the ACTIVE certified
      set for its kind is ``not_certified`` (exit 3) -- explicit, and never
      folded into ``ok``. "Certified" is a STRICTER bar than merely
      "recognized by the ``dwg_graph_ir.v1`` schema": a schema-known field
      (e.g. ``linetype``, ``visible``, ``xdata``) the oracle actually
      populates but that sits outside ``certified_fields_for_kind``'s active
      multiset-compare set is ALSO ``not_certified`` -- recognized is not
      certified, and a schema-legal key must never buy a silent pass on data
      nobody compared. This is how the module honors "a field no oracle
      engine can supply is not_certified, never a PASS": we simply refuse to
      silently trust (or silently ignore) data outside the oracle's proven
      capability.

Why MULTISET, not a per-handle join
------------------------------------
``cad_diff.py``'s ``comparison_basis="geometry"`` exists because a REGENERATED
drawing reissues every handle, so its PRE/POST diff cannot rely on the DWG
handle as a join key. Cross-oracle's two reads are of the very same static
staged file, so handles usually line up -- but relying on that is fragile
(anonymous dynamic-block instances, proxy graphics, or an oracle engine that
enumerates in a different order are all real edge cases) and it is exactly the
kind of assumption a "single extractor monoculture" bug hides behind. Grouping
by ``(kind, field)`` and comparing value MULTISETS is handle-independent and
order-independent by construction: two same-shape kinds with N entities each
agree iff their per-field value distributions agree, with zero assumption
about which physical entity maps to which.

Exit-code contract (this module's own; see module docstring below for how it
lines up with the overall F3 gate's ``0/3/4/5/6/7/8`` enum in PLAN.md Sec. 6.2)
--------------------------------------------------------------------------------
    EXIT_OK             0   compare_multiset: fully certified, no disagreement.
    EXIT_UNAVAILABLE    2   run_live_cross_oracle only: the router / a sibling
                            module needed for the LIVE leg is not available --
                            never returned by compare_multiset itself.
    EXIT_NOT_CERTIFIED  3   compare_multiset: an oracle field fell outside the
                            certified set (echoes the overall gate's "3 =
                            not fully wired/certified", at field granularity).
    EXIT_TRIPWIRE       4   compare_multiset: HOLLOW -- oracle populated,
                            native absent/null (matches PLAN.md's exit-4 HOLLOW).
    EXIT_DISAGREEMENT   7   compare_multiset: ORACLE-DISAGREE (matches PLAN.md's
                            step 7b "else EXIT 7").
Status priority when more than one condition fires in the same run: tripwire
(worst -- silent data loss) > disagreement (both sides populated, values
differ) > not_certified (nothing mis-measured, but part of the oracle's
assertion is out of scope) > ok. See ``compare_multiset``.

Known-field registries are schema-derived, not invented: ``_KNOWN_ENTITY_FIELDS``
and ``_KNOWN_GEOMETRY_LEAF_FIELDS`` are the literal ``properties`` lists of
``schemas/dwg_graph_ir.v1.schema.json``'s ``$defs/entity`` and ``$defs/geometry``
(a unit test pins this against the schema file so the two cannot silently
drift apart).

The LIVE leg (``run_live_cross_oracle``) needs a working ``autocad-router.ps1``
plus a live engine (accoreconsole/AutoCAD for ``engine="accoreconsole"``; ezdxf,
already vendored behind the router's ``dxf_fast_secondary`` route, for
``engine="ezdxf"``) and is therefore environment-dependent. It is written with
injectable ``router_extract`` / ``ir_from_extract`` callables (defaulting to
sibling modules ``run_job.run_router_extract`` / ``ir_builder.build_ir_from_extract``)
specifically so its control flow -- truthful degradation on every failure mode,
never a fake ok -- can be unit-tested without a live router. NOTE: the router's
CURRENT ``dxf_fast_secondary`` route (``run_route.py::r_dxf_fast_secondary``)
returns aggregate ``entities_by_type`` counts only, not a per-entity geometry
list; until that route (out of this node's fileset) is extended, the
``engine="ezdxf"`` leg cannot feed a full per-entity oracle IR and
``run_live_cross_oracle`` reports that truthfully (``unavailable``) rather than
certifying against a partial extraction. ``engine="accoreconsole"`` already
produces a full per-entity ``dwg_geometry_extract.v1`` (via the same
ObjectARX/ObjectDBX/AutoLISP chain ``cadctl.py`` drives) and is fully wired
through ``ir_builder.build_ir_from_extract``.

Public API:
    SCHEMA_ID / IR_SCHEMA_ID
    STATUS_OK / STATUS_NOT_CERTIFIED / STATUS_TRIPWIRE / STATUS_DISAGREEMENT
    EXIT_OK / EXIT_UNAVAILABLE / EXIT_NOT_CERTIFIED / EXIT_TRIPWIRE / EXIT_DISAGREEMENT
    DEFAULT_GEOMETRY_TOLERANCE
    certified_fields_for_kind(kind, supported_fields=None) -> list[str]
    find_uncertified_oracle_fields(oracle_ir, supported_fields=None) -> list[dict]
    compare_multiset(oracle_ir, native_ir, supported_fields=None,
                      geometry_tolerance=DEFAULT_GEOMETRY_TOLERANCE) -> dict
    run_live_cross_oracle(staged_dwg_path, native_ir, engine="accoreconsole", ...) -> dict
    load_ir(path) -> dict                                       # BOM-tolerant

Run ``python tools/cross_oracle.py`` for a synthetic self-demo (PASS/FAIL), or
``python tools/cross_oracle.py --oracle-ir a.json --native-ir b.json`` to
certify two on-disk ``dwg_graph_ir.v1`` documents.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

# --------------------------------------------------------------------------- #
# Paths / constants
# --------------------------------------------------------------------------- #

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)

SCHEMA_ID = "ariadne.cross_oracle.v1"
IR_SCHEMA_ID = "ariadne.dwg_graph_ir.v1"

# BOM-tolerant: JSON on this box (config/status/IR) may carry a UTF-8 BOM.
_JSON_ENCODING = "utf-8-sig"

STATUS_OK = "ok"
STATUS_NOT_CERTIFIED = "not_certified"
STATUS_TRIPWIRE = "tripwire"
STATUS_DISAGREEMENT = "disagreement"
STATUS_UNAVAILABLE = "unavailable"

EXIT_OK = 0
EXIT_UNAVAILABLE = 2
EXIT_NOT_CERTIFIED = 3
EXIT_TRIPWIRE = 4
EXIT_DISAGREEMENT = 7

# AutoCAD COMPARETOLERANCE analog, same value/semantics as cad_diff.py's
# DEFAULT_GEOMETRY_TOLERANCE: numeric leaves within this distance are treated as
# equal so cross-engine floating-point roundoff doesn't register as a fake
# disagreement. tol <= 0 disables snapping (exact compare).
DEFAULT_GEOMETRY_TOLERANCE = 1e-6

# ``-Intent`` value the router maps to each independent oracle engine (see
# autocad-router.ps1's Resolve-IntentToRoute / capabilities intent_aliases).
_ENGINE_INTENT = {
    "accoreconsole": "dwg",
    "ezdxf": "dxf",
}

# --------------------------------------------------------------------------- #
# Schema-derived known-field registries (schemas/dwg_graph_ir.v1.schema.json)
# --------------------------------------------------------------------------- #
# These are the LITERAL property lists of $defs/entity and $defs/geometry (both
# declare additionalProperties:true at the JSON-schema level -- engine-specific
# extras are structurally legal). cross_oracle layers a STRICTER, oracle-
# certification gate on top: any entity/geometry key outside these recognized
# sets (and outside a caller's explicit supported_fields override) is
# not_certified rather than silently compared or silently ignored.
# test_known_field_registries_match_schema pins these against the schema file
# itself so the two cannot silently drift apart.

_KNOWN_ENTITY_FIELDS = frozenset({
    "handle", "object_id", "class", "dxf_name", "owner_handle", "space",
    "layout", "layer", "linetype", "color_index", "lineweight", "visible",
    "bbox", "geometry", "xdata", "extension_dictionary_handle", "reactors",
    "source",
})

_KNOWN_GEOMETRY_LEAF_FIELDS = frozenset({
    "kind", "start", "end", "center", "position", "radius", "major_axis",
    "minor_ratio", "start_angle", "end_angle", "normal", "closed", "vertices",
    "text", "height", "rotation", "block_name", "scale", "dimension_type",
    "measurement", "control_points", "degree", "loops", "pattern_name",
})

# Entity keys that are IDENTITY / PROVENANCE, not oracle-asserted DATA: they
# say WHICH entity this is or WHERE it came from (a join/grouping key or an
# extraction-pipeline breadcrumb), never a claim about the entity's own state
# an independent oracle could agree or disagree with. These are the ONLY
# recognized entity fields find_uncertified_oracle_fields exempts outright.
# Every OTHER _KNOWN_ENTITY_FIELDS member (layout, linetype, color_index,
# lineweight, visible, xdata, extension_dictionary_handle, reactors) is DATA:
# if the oracle populates one and it is not in the active certified-compare
# set below, find_uncertified_oracle_fields flags it not_certified rather than
# silently skipping it (recognized-by-schema != oracle-certified).
_IDENTITY_PROVENANCE_FIELDS = frozenset({
    "handle", "object_id", "class", "dxf_name", "owner_handle", "space", "source",
})

# Top-level fields ACTIVELY multiset-compared by default (a subset of the known
# set above; "geometry" is handled separately below and _IDENTITY_PROVENANCE_
# FIELDS are exempt outright -- see above). Mirrors cad_diff.py's own
# _SCALAR_COMPARE_FIELDS + bbox.
_DEFAULT_TOP_LEVEL_COMPARE_FIELDS: Tuple[str, ...] = ("layer", "bbox")

# Geometry leaves compared by default: every schema-declared leaf except "kind"
# is compared as ordinary DATA; "kind" (the geometry discriminator, e.g. "line")
# is included too since it is legitimate, stable, cross-engine-comparable data.
_DEFAULT_GEOMETRY_COMPARE_FIELDS: Tuple[str, ...] = tuple(sorted(_KNOWN_GEOMETRY_LEAF_FIELDS))


# --------------------------------------------------------------------------- #
# IO (BOM-tolerant, mirrors cad_diff.load_ir)
# --------------------------------------------------------------------------- #

def load_ir(path) -> Dict[str, Any]:
    """Load an IR JSON document (BOM-tolerant)."""
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _write_json(payload: Dict[str, Any], path) -> str:
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, indent=2))
        fh.write("\n")
    return str(path)


# --------------------------------------------------------------------------- #
# Entity/field helpers
# --------------------------------------------------------------------------- #

def _iter_entities(ir: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    entities = (ir or {}).get("entities")
    if not isinstance(entities, list):
        return []
    return [e for e in entities if isinstance(e, dict)]


def _kind_of(entity: Dict[str, Any]) -> str:
    """The oracle-comparison grouping key: the DXF type (matches cad_diff.py's
    own ``by_type`` grouping, which is also keyed on ``dxf_name``)."""
    return str(entity.get("dxf_name") or "")


def _group_by_kind(entities: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for e in entities:
        grouped.setdefault(_kind_of(e), []).append(e)
    return grouped


def _resolve_field(entity: Dict[str, Any], field_path: str) -> Tuple[bool, Any]:
    """Resolve a (possibly dotted, e.g. 'geometry.start') field path.

    Returns ``(present, value)``. ``present`` is False when the key (or an
    intermediate container) is missing -- this is what distinguishes "absent"
    from "present but null" for the tripwire/multiset logic below.
    """
    cur: Any = entity
    for part in field_path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def _populated(entity: Dict[str, Any], field_path: str) -> Tuple[bool, Any]:
    """True + value iff field_path is present AND non-None ("populated" in the
    v2-A1 sense: "a field populated in the oracle IR")."""
    present, value = _resolve_field(entity, field_path)
    return (present and value is not None), value


def _quantize(value: Any, tol: float) -> Any:
    """Snap numeric leaves onto a tol-wide grid (cad_diff.py's COMPARETOLERANCE
    analog, reproduced locally to keep this module's public compare surface
    self-contained). tol <= 0 disables snapping (exact compare)."""
    if isinstance(value, bool) or tol <= 0:
        return value
    if isinstance(value, (int, float)):
        return round(value / tol)
    if isinstance(value, dict):
        return {k: _quantize(v, tol) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_quantize(v, tol) for v in value]
    return value


def _hashable(value: Any) -> Any:
    """Canonical, hashable form of a value for Counter-based multiset
    comparison (lists/dicts are not hashable; two structurally-equal values
    must hash identically regardless of container identity)."""
    if isinstance(value, dict):
        return tuple(sorted((k, _hashable(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_hashable(v) for v in value)
    return value


# --------------------------------------------------------------------------- #
# Certified-field registry (default + supported_fields override)
# --------------------------------------------------------------------------- #

def _kind_override(kind: str, supported_fields: Optional[Mapping[str, Mapping[str, Sequence[str]]]]) -> Mapping[str, Sequence[str]]:
    cfg = supported_fields or {}
    return cfg.get(kind) or cfg.get("*") or {}


def certified_fields_for_kind(kind: str,
                              supported_fields: Optional[Mapping[str, Mapping[str, Sequence[str]]]] = None
                              ) -> List[str]:
    """The ordered list of field paths ACTIVELY multiset-compared for ``kind``.

    ``supported_fields`` is the seam for the plan's open "[Paul decision]" on
    which engine certifies which (kind, field): ``{kind_or_"*": {"top": [...],
    "geometry": [...]}}``. Absent an override, every kind gets the same
    conservative default (``_DEFAULT_TOP_LEVEL_COMPARE_FIELDS`` +
    ``geometry.<leaf>`` for every ``_DEFAULT_GEOMETRY_COMPARE_FIELDS`` leaf).
    Fields never populated on either side for a given kind simply contribute
    an empty/empty multiset comparison (a no-op), so widening this default
    union-of-kinds list costs correctness nothing.
    """
    kind_cfg = _kind_override(kind, supported_fields)
    top = list(kind_cfg.get("top", _DEFAULT_TOP_LEVEL_COMPARE_FIELDS))
    geometry = list(kind_cfg.get("geometry", _DEFAULT_GEOMETRY_COMPARE_FIELDS))
    ordered: List[str] = []
    seen = set()
    for field in top:
        if field not in seen:
            seen.add(field)
            ordered.append(field)
    for leaf in geometry:
        field = "geometry.%s" % leaf
        if field not in seen:
            seen.add(field)
            ordered.append(field)
    return ordered


def _recognized_top_level_fields(kind: str,
                                 supported_fields: Optional[Mapping[str, Mapping[str, Sequence[str]]]]
                                 ) -> set:
    kind_cfg = _kind_override(kind, supported_fields)
    return _KNOWN_ENTITY_FIELDS | set(kind_cfg.get("top", ()))


def _recognized_geometry_leaves(kind: str,
                                supported_fields: Optional[Mapping[str, Mapping[str, Sequence[str]]]]
                                ) -> set:
    kind_cfg = _kind_override(kind, supported_fields)
    return _KNOWN_GEOMETRY_LEAF_FIELDS | set(kind_cfg.get("geometry", ()))


def _active_top_level_fields(kind: str,
                             supported_fields: Optional[Mapping[str, Mapping[str, Sequence[str]]]]
                             ) -> set:
    """Top-level field names ACTIVELY multiset-compared for ``kind`` -- the
    non-``geometry.``-prefixed subset of ``certified_fields_for_kind``. This
    is the STRICTER "certified" bar find_uncertified_oracle_fields checks a
    recognized field against (see ``_recognized_top_level_fields`` for the
    looser "is this key legal at all" bar)."""
    return {f for f in certified_fields_for_kind(kind, supported_fields) if not f.startswith("geometry.")}


def _active_geometry_leaves(kind: str,
                            supported_fields: Optional[Mapping[str, Mapping[str, Sequence[str]]]]
                            ) -> set:
    """Geometry leaf names ACTIVELY multiset-compared for ``kind`` -- the
    ``geometry.``-prefixed subset of ``certified_fields_for_kind``, unprefixed
    back down to bare leaf names."""
    return {f.split(".", 1)[1] for f in certified_fields_for_kind(kind, supported_fields) if f.startswith("geometry.")}


def find_uncertified_oracle_fields(oracle_ir: Dict[str, Any],
                                   supported_fields: Optional[Mapping[str, Mapping[str, Sequence[str]]]] = None
                                   ) -> List[Dict[str, Any]]:
    """Scan the ORACLE IR for any entity/geometry field that is not fully
    ORACLE-CERTIFIED for its kind. Only the oracle is scanned: the oracle is
    the reference being certified as trustworthy, not the native pipeline
    under test (an unexpected native field is exactly what the rest of this
    module exists to catch, via disagreement/tripwire, not via this scan).

    Two distinct ways a field fails certification, both reported here:

      1. UNRECOGNIZED -- the key is outside ``dwg_graph_ir.v1``'s own schema
         (``_KNOWN_ENTITY_FIELDS`` / ``_KNOWN_GEOMETRY_LEAF_FIELDS``) and
         outside any ``supported_fields`` override for its kind: literally
         unknown data the oracle is emitting.
      2. RECOGNIZED BUT NOT ACTIVELY CERTIFIED -- the key IS a legal
         ``dwg_graph_ir.v1`` field, it is not an identity/provenance field
         (``_IDENTITY_PROVENANCE_FIELDS`` -- e.g. ``handle``/``class``, which
         are never oracle-asserted DATA), and it is outside
         ``certified_fields_for_kind``'s ACTIVE compare set for this kind --
         yet the oracle actually POPULATED it (present, non-None). Without
         this check, "recognized by the schema" silently stood in for
         "certified": a schema-known field such as ``linetype``/``visible``/
         ``xdata`` could sit outside the active compare set forever and never
         be flagged, so a genuine oracle-vs-native mismatch on it would PASS
         by omission -- the exact v2-A1 hole this scan exists to close (see
         ``test_supported_fields_override_widens_active_comparison``).

    Returns a deterministically-sorted list of
    ``{"handle", "kind", "field", "reason"}`` dicts; empty when every oracle
    field is either identity/provenance or actively certified.
    """
    findings: List[Dict[str, Any]] = []
    for entity in _iter_entities(oracle_ir):
        kind = _kind_of(entity)
        handle = entity.get("handle")
        allowed_top = _recognized_top_level_fields(kind, supported_fields)
        active_top = _active_top_level_fields(kind, supported_fields)
        for key in entity.keys():
            if key not in allowed_top:
                findings.append({
                    "handle": handle, "kind": kind, "field": key,
                    "reason": "field is not in the recognized dwg_graph_ir.v1 entity "
                              "schema and is not declared oracle-supported for this kind",
                })
                continue
            if key == "geometry" or key in _IDENTITY_PROVENANCE_FIELDS or key in active_top:
                continue
            present, _value = _populated(entity, key)
            if present:
                findings.append({
                    "handle": handle, "kind": kind, "field": key,
                    "reason": "field is a recognized dwg_graph_ir.v1 entity field the "
                              "oracle populated, but it is outside the ACTIVE oracle-"
                              "certified compare set for this kind (recognized != "
                              "certified -- add it to supported_fields to certify it)",
                })
        geometry = entity.get("geometry")
        if isinstance(geometry, dict):
            allowed_geom = _recognized_geometry_leaves(kind, supported_fields)
            active_geom = _active_geometry_leaves(kind, supported_fields)
            for key in geometry.keys():
                field = "geometry.%s" % key
                if key not in allowed_geom:
                    findings.append({
                        "handle": handle, "kind": kind, "field": field,
                        "reason": "geometry leaf is not in the recognized dwg_graph_ir.v1 "
                                  "geometry schema and is not declared oracle-supported "
                                  "for this kind",
                    })
                    continue
                if key in active_geom:
                    continue
                present, _value = _populated(entity, field)
                if present:
                    findings.append({
                        "handle": handle, "kind": kind, "field": field,
                        "reason": "geometry leaf is a recognized dwg_graph_ir.v1 geometry "
                                  "field the oracle populated, but it is outside the "
                                  "ACTIVE oracle-certified compare set for this kind "
                                  "(recognized != certified -- add it to supported_fields "
                                  "to certify it)",
                    })
    findings.sort(key=lambda f: (f.get("kind") or "", f.get("field") or "", f.get("handle") or ""))
    return findings


# --------------------------------------------------------------------------- #
# The multiset re-diff (v2-A1 core)
# --------------------------------------------------------------------------- #

def _multiset(values: Sequence[Any], tol: float) -> Tuple[Counter, Dict[Any, Any]]:
    """Build a (Counter, representative-original-value) pair over quantized,
    hashable keys so the disagreement report can show a real JSON value rather
    than an internal tuple-canonicalization."""
    counts: Counter = Counter()
    representative: Dict[Any, Any] = {}
    for v in values:
        key = _hashable(_quantize(v, tol))
        counts[key] += 1
        representative.setdefault(key, v)
    return counts, representative


def compare_multiset(oracle_ir: Dict[str, Any], native_ir: Dict[str, Any],
                     supported_fields: Optional[Mapping[str, Mapping[str, Sequence[str]]]] = None,
                     geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE) -> Dict[str, Any]:
    """Full per-entity, per-field multiset re-diff of an oracle IR against a
    native IR of the SAME staged (regenerated) DWG (v2-A1).

    For every entity kind present in either document, and for every field
    ``certified_fields_for_kind(kind, supported_fields)`` returns:

      1. TRIPWIRE (checked first): if the oracle has strictly MORE populated
         (present, non-None) values for ``(kind, field)`` than the native IR,
         the native extractor dropped something the independent reference
         actually has -- HOLLOW, exit 4. This is a net-count check, not a
         per-entity join (see module docstring for why), and it is
         intentionally ONE-DIRECTIONAL: a native IR that populates MORE than
         the oracle for a field is not a tripwire (the oracle itself may be
         the fast/lossy leg) -- it instead surfaces as a disagreement below,
         because the two populated-value multisets then necessarily differ in
         size and cannot be equal.
      2. DISAGREEMENT: multiset(oracle populated values) != multiset(native
         populated values) (after quantizing numeric leaves onto a
         ``geometry_tolerance``-wide grid, the AutoCAD COMPARETOLERANCE
         analog) -- ORACLE-DISAGREE, exit 7.
      3. NOT_CERTIFIED: independent of the field loop above,
         ``find_uncertified_oracle_fields`` flags any oracle entity field
         outside the certified/recognized set -- exit 3.

    Overall ``status``/``exit_code`` is the worst of the three that fired, in
    that order (tripwire > disagreement > not_certified > ok): a genuine data
    loss or conflict is a stronger signal than "part of the oracle's claim was
    out of certified scope", and "never folded into a PASS" only requires that
    not_certified beat ``ok``, not that it beat a detected disagreement/loss.

    Returns a deterministic dict (no timestamps/randomness -- re-running on the
    same two IRs yields byte-identical JSON):
        {schema, status, exit_code,
         summary: {kinds_compared, fields_checked, oracle_entity_count,
                   native_entity_count, tripwire_count, disagreement_count,
                   not_certified_count},
         tripwires: [{kind, field, oracle_populated_count,
                      native_populated_count, reason}],
         disagreements: [{kind, field, oracle_populated_count,
                           native_populated_count, value_diffs}],
         not_certified_fields: [{handle, kind, field, reason}],
         diagnostics: {geometry_tolerance, warnings}}
    """
    oracle_entities = _iter_entities(oracle_ir)
    native_entities = _iter_entities(native_ir)
    oracle_by_kind = _group_by_kind(oracle_entities)
    native_by_kind = _group_by_kind(native_entities)

    not_certified = find_uncertified_oracle_fields(oracle_ir, supported_fields)

    kinds = sorted(set(oracle_by_kind) | set(native_by_kind))
    tripwires: List[Dict[str, Any]] = []
    disagreements: List[Dict[str, Any]] = []
    fields_checked = 0

    for kind in kinds:
        o_ents = oracle_by_kind.get(kind, [])
        n_ents = native_by_kind.get(kind, [])
        for field in certified_fields_for_kind(kind, supported_fields):
            fields_checked += 1
            o_values = [v for present, v in (_populated(e, field) for e in o_ents) if present]
            n_values = [v for present, v in (_populated(e, field) for e in n_ents) if present]
            o_count, n_count = len(o_values), len(n_values)

            if o_count > n_count:
                tripwires.append({
                    "kind": kind, "field": field,
                    "oracle_populated_count": o_count,
                    "native_populated_count": n_count,
                    "reason": "field populated in the oracle IR for %d %s entit%s but "
                              "absent/null in the native IR for at least %d of them"
                              % (o_count, kind or "(no dxf_name)",
                                 "y" if o_count == 1 else "ies", o_count - n_count),
                })
                continue  # HOLLOW already reported for this field; skip the value compare.

            if o_count == 0 and n_count == 0:
                continue  # neither side ever populates this field -- nothing to certify.

            o_counts, o_repr = _multiset(o_values, geometry_tolerance)
            n_counts, n_repr = _multiset(n_values, geometry_tolerance)
            if o_counts != n_counts:
                value_diffs = []
                for key in sorted(set(o_counts) | set(n_counts), key=repr):
                    oc, nc = o_counts.get(key, 0), n_counts.get(key, 0)
                    if oc != nc:
                        value_diffs.append({
                            "value": o_repr.get(key, n_repr.get(key)),
                            "oracle_count": oc, "native_count": nc,
                        })
                disagreements.append({
                    "kind": kind, "field": field,
                    "oracle_populated_count": o_count,
                    "native_populated_count": n_count,
                    "value_diffs": value_diffs,
                })

    if tripwires:
        status, exit_code = STATUS_TRIPWIRE, EXIT_TRIPWIRE
    elif disagreements:
        status, exit_code = STATUS_DISAGREEMENT, EXIT_DISAGREEMENT
    elif not_certified:
        status, exit_code = STATUS_NOT_CERTIFIED, EXIT_NOT_CERTIFIED
    else:
        status, exit_code = STATUS_OK, EXIT_OK

    warnings: List[str] = []
    if oracle_ir.get("schema") != IR_SCHEMA_ID:
        warnings.append("oracle IR schema is %r (expected %s)" % (oracle_ir.get("schema"), IR_SCHEMA_ID))
    if native_ir.get("schema") != IR_SCHEMA_ID:
        warnings.append("native IR schema is %r (expected %s)" % (native_ir.get("schema"), IR_SCHEMA_ID))

    return {
        "schema": SCHEMA_ID,
        "status": status,
        "exit_code": exit_code,
        "summary": {
            "kinds_compared": kinds,
            "fields_checked": fields_checked,
            "oracle_entity_count": len(oracle_entities),
            "native_entity_count": len(native_entities),
            "tripwire_count": len(tripwires),
            "disagreement_count": len(disagreements),
            "not_certified_count": len(not_certified),
        },
        "tripwires": tripwires,
        "disagreements": disagreements,
        "not_certified_fields": not_certified,
        "diagnostics": {
            "geometry_tolerance": geometry_tolerance,
            "warnings": warnings,
        },
    }


# --------------------------------------------------------------------------- #
# Truthful sibling-lane import (mirrors cad_diff.py / cadctl.py's own pattern;
# each file in tools/ keeps its own copy rather than importing another
# module's private helper).
# --------------------------------------------------------------------------- #

def _import_optional(module_name: str):
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
    try:
        return __import__(module_name)
    except Exception:  # pragma: no cover - defensive; sibling truly absent
        return None


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


# --------------------------------------------------------------------------- #
# LIVE leg: wrap autocad-router.ps1 -Action run -Intent {dwg|dxf}
# --------------------------------------------------------------------------- #

def run_live_cross_oracle(staged_dwg_path: str, native_ir: Dict[str, Any], *,
                          engine: str = "accoreconsole",
                          run_dir: Optional[str] = None,
                          router_extract=None,
                          ir_from_extract=None,
                          supported_fields: Optional[Mapping[str, Mapping[str, Sequence[str]]]] = None,
                          geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE) -> Dict[str, Any]:
    """Re-extract ``staged_dwg_path`` with an INDEPENDENT engine and certify it
    against ``native_ir`` via ``compare_multiset``.

    Wraps ``autocad-router.ps1 -Action run -Intent dwg`` (``engine=
    "accoreconsole"``, ObjectARX/ObjectDBX/AutoLISP ground-truth via the same
    lane ``cadctl.inspect`` drives) or ``-Intent dxf`` (``engine="ezdxf"``,
    fast/lossy) by delegating to sibling module ``run_job.run_router_extract``
    (default; injectable as ``router_extract`` purely for testability) and
    normalizing the router's ``dwg_geometry_extract.v1`` output to an IR via
    sibling module ``ir_builder.build_ir_from_extract`` (default; injectable as
    ``ir_from_extract``).

    Every failure mode degrades truthfully to ``status="unavailable"``
    (``exit_code=EXIT_UNAVAILABLE``) -- never a fake ``ok``:
      * unknown ``engine``;
      * ``run_job``/``ir_builder`` not importable (sibling module missing);
      * the router process itself errored/timed out/could not be spawned
        (``router_extract`` returned ``{"error": ...}``);
      * the router ran but did not report ``PASS`` (route unavailable on this
        host, non-zero engine exit, ...);
      * the router reported PASS but did not produce a per-entity
        ``extract_json`` (this is the CURRENT state of ``engine="ezdxf"``:
        ``run_route.py``'s ``dxf_fast_secondary`` route returns aggregate
        ``entities_by_type`` counts only -- see module docstring).

    On genuine success the return value IS ``compare_multiset``'s dict (plus
    ``engine``/``intent``/``run_dir`` echoed in for provenance).
    """
    if engine not in _ENGINE_INTENT:
        return {
            "schema": SCHEMA_ID, "status": STATUS_UNAVAILABLE, "exit_code": EXIT_UNAVAILABLE,
            "engine": engine,
            "reason": "unknown engine %r; expected one of %s" % (engine, sorted(_ENGINE_INTENT)),
        }
    intent = _ENGINE_INTENT[engine]

    if router_extract is None:
        run_job_mod = _import_optional("run_job")
        router_extract = getattr(run_job_mod, "run_router_extract", None)
    if router_extract is None:
        return {
            "schema": SCHEMA_ID, "status": STATUS_UNAVAILABLE, "exit_code": EXIT_UNAVAILABLE,
            "engine": engine, "intent": intent,
            "reason": "run_job.run_router_extract unavailable (sibling module not importable)",
        }

    if ir_from_extract is None:
        ir_builder_mod = _import_optional("ir_builder")
        ir_from_extract = getattr(ir_builder_mod, "build_ir_from_extract", None)
    if ir_from_extract is None:
        return {
            "schema": SCHEMA_ID, "status": STATUS_UNAVAILABLE, "exit_code": EXIT_UNAVAILABLE,
            "engine": engine, "intent": intent,
            "reason": "ir_builder.build_ir_from_extract unavailable (sibling module not importable)",
        }

    run_dir = run_dir or os.path.join(_ROUTER_HOME, "runs", "cross_oracle_%s_%s" % (engine, _timestamp()))
    run_res = router_extract(staged_dwg_path, run_dir, intent=intent)

    if run_res.get("error"):
        return {
            "schema": SCHEMA_ID, "status": STATUS_UNAVAILABLE, "exit_code": EXIT_UNAVAILABLE,
            "engine": engine, "intent": intent, "run_dir": run_dir,
            "reason": run_res["error"], "command": run_res.get("command"),
        }

    envelope = run_res.get("envelope")
    if not isinstance(envelope, dict) or envelope.get("status") != "PASS":
        return {
            "schema": SCHEMA_ID, "status": STATUS_UNAVAILABLE, "exit_code": EXIT_UNAVAILABLE,
            "engine": engine, "intent": intent, "run_dir": run_dir,
            "reason": "router did not report PASS for -Intent %s" % intent,
            "router_status": (envelope or {}).get("status"),
            "router_exit_code": run_res.get("exit_code"),
        }

    execution = envelope.get("execution") or {}
    engine_output = execution.get("engine_output")
    if not isinstance(engine_output, dict):
        engine_output = {}
    extract_json = engine_output.get("extract_json")
    if not extract_json or not os.path.exists(extract_json):
        return {
            "schema": SCHEMA_ID, "status": STATUS_UNAVAILABLE, "exit_code": EXIT_UNAVAILABLE,
            "engine": engine, "intent": intent, "run_dir": run_dir,
            "reason": "router route for -Intent %s did not produce a per-entity "
                      "dwg_geometry_extract.v1 JSON (execution.engine_output.extract_json "
                      "missing); engine='ezdxf' currently only wires the aggregate-count "
                      "dxf_fast_secondary route (see module docstring) -- cannot certify a "
                      "full per-entity multiset from it" % intent,
            "engine_output_status": engine_output.get("status"),
        }

    try:
        extract = load_ir(extract_json)
    except (OSError, ValueError) as exc:
        return {
            "schema": SCHEMA_ID, "status": STATUS_UNAVAILABLE, "exit_code": EXIT_UNAVAILABLE,
            "engine": engine, "intent": intent, "run_dir": run_dir,
            "reason": "failed to read extract_json %r: %s: %s" % (extract_json, type(exc).__name__, exc),
        }

    try:
        oracle_ir = ir_from_extract(extract, extract.get("summary"), {
            "extractor": engine,
            "engine_tier": engine_output.get("winning_engine") or engine,
            "route": "dwg_truth_autocad" if engine == "accoreconsole" else "dxf_fast_secondary",
            "dwg_path": staged_dwg_path,
            "byte_size": os.path.getsize(staged_dwg_path) if os.path.exists(staged_dwg_path) else 0,
        })
    except Exception as exc:
        return {
            "schema": SCHEMA_ID, "status": STATUS_UNAVAILABLE, "exit_code": EXIT_UNAVAILABLE,
            "engine": engine, "intent": intent, "run_dir": run_dir,
            "reason": "ir_from_extract failed: %s: %s" % (type(exc).__name__, exc),
        }

    result = compare_multiset(oracle_ir, native_ir, supported_fields=supported_fields,
                              geometry_tolerance=geometry_tolerance)
    result["engine"] = engine
    result["intent"] = intent
    result["run_dir"] = run_dir
    return result


# --------------------------------------------------------------------------- #
# Self-demo (__main__): certify a synthetic agreeing pair, print PASS/FAIL.
# --------------------------------------------------------------------------- #

def _demo_entity(handle: str, layer: str = "0") -> Dict[str, Any]:
    return {
        "handle": handle, "class": "AcDbLine", "dxf_name": "LINE",
        "owner_handle": "1F", "space": "model", "layer": layer,
        "bbox": [0.0, 0.0, 0.0, 10.0, 0.0, 0.0],
        "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [10.0, 0.0, 0.0]},
        "source": {"extractor": "cross_oracle.selfdemo", "decoded": True},
    }


def _selftest() -> int:
    oracle = {"schema": IR_SCHEMA_ID, "entities": [_demo_entity("2A7"), _demo_entity("2A8", layer="WALLS")]}
    native = {"schema": IR_SCHEMA_ID, "entities": [_demo_entity("2A8", layer="WALLS"), _demo_entity("2A7")]}
    agree = compare_multiset(oracle, native)

    tampered_native = json.loads(json.dumps(native))
    tampered_native["entities"][0]["layer"] = "MOVED"
    disagree = compare_multiset(oracle, tampered_native)

    hollow_native = json.loads(json.dumps(native))
    del hollow_native["entities"][0]["layer"]
    tripwire = compare_multiset(oracle, hollow_native)

    print("== cross_oracle self-demo ==")
    print("agree     : status=%s exit=%d (expect ok/0)" % (agree["status"], agree["exit_code"]))
    print("disagree  : status=%s exit=%d (expect disagreement/7)" % (disagree["status"], disagree["exit_code"]))
    print("tripwire  : status=%s exit=%d (expect tripwire/4)" % (tripwire["status"], tripwire["exit_code"]))

    passed = (agree["status"] == STATUS_OK and agree["exit_code"] == EXIT_OK
              and disagree["status"] == STATUS_DISAGREEMENT and disagree["exit_code"] == EXIT_DISAGREEMENT
              and tripwire["status"] == STATUS_TRIPWIRE and tripwire["exit_code"] == EXIT_TRIPWIRE)
    print("RESULT    : %s" % ("PASS" if passed else "FAIL"))
    return 0 if passed else 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="cross_oracle: independent-engine multiset re-diff of a dwg_graph_ir.v1 pair "
                    "(F1.5 / v2-A1). With no arguments, runs a synthetic self-demo.")
    ap.add_argument("--oracle-ir", help="path to an independent-engine oracle IR JSON (dwg_graph_ir.v1)")
    ap.add_argument("--native-ir", help="path to the native-pipeline IR JSON to certify against")
    ap.add_argument("--staged-dwg", help="LIVE leg: staged regenerated DWG to re-extract via the router "
                                         "(requires --native-ir; wraps autocad-router.ps1)")
    ap.add_argument("--engine", choices=sorted(_ENGINE_INTENT), default="accoreconsole",
                    help="LIVE leg: which independent engine to wrap via autocad-router.ps1 "
                         "(-Intent dwg for accoreconsole, -Intent dxf for ezdxf)")
    ap.add_argument("--out", help="also write the result JSON to this path")
    args = ap.parse_args(argv)

    if args.staged_dwg:
        if not args.native_ir:
            print(json.dumps({"schema": SCHEMA_ID, "status": "blocked",
                              "reason": "--staged-dwg requires --native-ir"}, indent=2))
            return 2
        result = run_live_cross_oracle(args.staged_dwg, load_ir(args.native_ir), engine=args.engine)
    elif args.oracle_ir and args.native_ir:
        result = compare_multiset(load_ir(args.oracle_ir), load_ir(args.native_ir))
    elif args.oracle_ir or args.native_ir:
        print(json.dumps({"schema": SCHEMA_ID, "status": "blocked",
                          "reason": "both --oracle-ir and --native-ir are required together"}, indent=2))
        return 2
    else:
        return _selftest()

    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        _write_json(result, args.out)
    return int(result.get("exit_code", 1))


if __name__ == "__main__":
    sys.exit(main())
