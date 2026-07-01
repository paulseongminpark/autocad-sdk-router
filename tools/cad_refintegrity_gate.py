#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cad_refintegrity_gate.py -- CAD OS Layer Rung-D: cross-object reference-integrity gate.

Wave-0 v2-A5 (Opus C2 / OPUS_REVIEW.md finding C2): the north-star metric is a
handle-INDEPENDENT geometry diff -- ``geometry fingerprint = (dxf_name, layer,
canonical(quantize(geometry, tol)))`` (see ``cad_diff.py``) -- which is exactly
right for entity geometry but structurally BLIND to inter-object handle
references. When a regen roundtrip reissues every handle, an associative link
must be re-pointed at its new handle; a handle-independent diff reports
``diff == 0`` whether that re-pointing was correct, scrambled, or dropped
entirely. Rung-A (cardinality), Rung-B (golden-keys) and Rung-C (container
fidelity) all still read ``ir["entities"]`` and none of them enumerate
associative cross-references. This module is the missing rung: it walks the
persistent cross-object references a DWG can carry and asserts that each one's
POST-regen counterpart resolves to the GEOMETRICALLY-CORRESPONDING target of
what it pointed at PRE-regen -- matched by fingerprint, never by raw handle
equality (a raw-handle compare would trivially fail on every correct regen,
since regen reissues handles by design).

Reference categories modelled (the four named in PLAN.md v2-A5 / OPUS_REVIEW C2)
----------------------------------------------------------------------------
  * ``hatch_boundary``   -- an associative HATCH's loop boundary references.
                            Convention: ``entity.geometry.kind == "hatch"``;
                            each ``geometry.loops[i]`` MAY carry
                            ``associative: true`` + ``boundary_handles: [...]``
                            (extension fields; ``loops[]`` items are
                            ``additionalProperties: true`` in
                            ``dwg_graph_ir.v1.schema.json``, so this is a
                            schema-legal extension, not a violation).
  * ``field_object``     -- an ``AcDbField`` bound to a host object and
                            referencing the object(s) its expression reads.
                            ``AcDbField`` is uncatalogued in the current IR
                            (PLAN.md H-R42 / R3-G7) so there is no formal
                            schema section for it yet. Convention adopted here
                            (an IR EXTENSION, root-level, additionalProperties
                            allows it): ``ir["fields"] = [{"handle",
                            "host_handle", "referenced_handles": [...]}]``.
                            NOTE (documented limitation): matching is scoped to
                            the field's HOST, not the individual field index --
                            a swap between two references that both remain
                            present on the SAME host is not distinguished. The
                            concrete regen bug this rung must catch (a
                            reference silently re-pointed at the wrong object)
                            is still caught.
  * ``group_member``     -- ``groups[].members[]`` (already in
                            ``dwg_graph_ir.v1.schema.json``; ``name`` is a
                            required field of a group record and is the stable,
                            handle-independent identity of a NAMED group across
                            a regen. An ``anonymous`` group instead keys off
                            the sorted multiset of its members' own identities,
                            since an anonymous group's auto-name is not
                            guaranteed stable across regen).
  * ``dictionary_entry``  -- ``dictionaries[].entries[].value_handle`` (already
                            in the schema; ``dictionary_record.name`` -- "name
                            as keyed in its PARENT" -- is the stable identity
                            when present; an unnamed dictionary keys off the
                            sorted multiset of its ``(entry key, resolved
                            target identity)`` pairs).

Matching algorithm
-------------------
1. ``_build_indexes`` builds handle -> record lookup tables (entities, groups,
   dictionaries, xrecords, our ``fields`` extension) for one IR.
2. ``_resolve_object_identity`` maps ANY handle in that IR to a
   handle-independent identity tuple: an entity's identity is its geometry
   fingerprint (mirrors ``cad_diff._geometry_fingerprint``, reimplemented here
   so this module carries no cross-module coupling to ``cad_diff``'s
   internals); a group/dictionary/xrecord/field's identity recurses per the
   rules above (cycle-guarded via a ``_seen`` handle set -- defensive; DWG
   object graphs are not expected to cycle, but a resolver must never hang or
   crash on malformed input -- no-fake-success extends to "never silently
   succeeds by looping forever").
3. ``_all_edges`` walks one IR and yields every modelled reference as
   ``{category, source_id, source_label, target_handle, context}``, where
   ``source_id`` is the REFERRING object's identity (e.g. the HATCH itself for
   ``hatch_boundary``) computed directly from that IR's own records.
4. ``check_reference_integrity(pre_ir, post_ir)`` groups PRE edges by
   ``(category, source_id)`` and, for each group, resolves every
   ``target_handle`` to an identity and builds a ``Counter`` MULTISET of
   expected target identities (order-independent -- a reordered member list is
   NOT a violation, matching PLAN.md's explicit "group whose member set is
   re-ordered" non-failure case). The same is done for POST edges sharing that
   ``(category, source_id)`` key. ``pre_multiset - post_multiset`` (Python
   ``Counter`` subtraction keeps only strictly-positive remainders) is the set
   of PRE-side references that the POST IR does not reproduce at the expected
   target identity -- each surviving remainder is a violation: a dropped
   reference, a rewired-to-the-wrong-target reference, or (report-worthy but
   not fatal on its own) a target this gate could not resolve to any modelled
   object kind.

Hard rules (CAD OS Layer build invariants -- mirrors cad_diff.py / validator.py)
---------------------------------------------------------------------------
  * Standard library ONLY (Python 3.12). No third-party imports.
  * Deterministic: no timestamps, no randomness; the same ``(pre_ir, post_ir)``
    pair always yields byte-identical JSON (violations/warnings are built from
    sorted iteration wherever ordering could otherwise vary run-to-run).
  * No-fake-success: a reference whose source OR target cannot be resolved to
    any modelled object kind is counted under ``unverifiable`` and surfaced in
    ``warnings`` -- it is NEVER silently treated as passing, and it never
    inflates the pass count. An IR with zero modelled references reports
    ``status: "skipped"`` (truthfully nothing to check), never a fake "pass".
  * Read-only: this module never writes an IR or a DWG; it returns / prints a
    report dict. ``make_regenerated_ir`` builds a NEW dict (deep copy) and
    never mutates its input.

Public API:
    REFINTEGRITY_SCHEMA_ID
    DEFAULT_GEOMETRY_TOLERANCE
    check_reference_integrity(pre_ir, post_ir, geometry_tolerance=DEFAULT_GEOMETRY_TOLERANCE) -> dict
    reference_integrity_ok(pre_ir, post_ir, geometry_tolerance=DEFAULT_GEOMETRY_TOLERANCE) -> bool
    load_ir(path) -> dict                                              # BOM-tolerant
    make_fixture_pre_ir() -> dict                # synthetic IR exercising all 4 categories
    make_regenerated_ir(pre_ir, break_category=None, rehandle_map=None) -> dict

CLI:
    python tools/cad_refintegrity_gate.py                       # self-demo (no args)
    python tools/cad_refintegrity_gate.py --pre a.json --post b.json [--tol 1e-6] [--out report.json]
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

# --------------------------------------------------------------------------- #
# Paths / constants
# --------------------------------------------------------------------------- #

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)

REFINTEGRITY_SCHEMA_ID = "ariadne.cad_refintegrity_gate.v1"
IR_SCHEMA_ID = "ariadne.dwg_graph_ir.v1"

# On this box the catalog/config/IR JSON may carry a UTF-8 BOM; json.load on
# the cp949 locale needs utf-8-sig to decode it. Writes are plain UTF-8.
_JSON_ENCODING = "utf-8-sig"

# Default tolerance for the geometry fingerprint (the AutoCAD COMPARETOLERANCE
# analog -- mirrors cad_diff.DEFAULT_GEOMETRY_TOLERANCE). Kept as an
# independent constant so this module has no import-time dependency on
# cad_diff's internals (see module docstring, matching algorithm step 2).
DEFAULT_GEOMETRY_TOLERANCE = 1e-6

# The four reference categories this gate models (PLAN.md v2-A5 / OPUS_REVIEW
# C2). Always present as keys in a report's ``categories`` dict, even at zero
# count, so a consumer never has to guess which keys exist (stable contract).
_CATEGORIES: Tuple[str, ...] = (
    "hatch_boundary", "field_object", "group_member", "dictionary_entry",
)


# --------------------------------------------------------------------------- #
# IO (BOM-tolerant)
# --------------------------------------------------------------------------- #

def load_ir(path) -> Dict[str, Any]:
    """Load an IR JSON document (BOM-tolerant)."""
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# Geometry fingerprint (self-contained mirror of cad_diff's algorithm)
# --------------------------------------------------------------------------- #

def _canonical(value: Any) -> Any:
    """Order-stable, hashable, JSON-comparable form of a value (dicts/lists ->
    sorted-key / element-wise tuples). Mirrors ``cad_diff._canonical``."""
    if isinstance(value, dict):
        return tuple(sorted((k, _canonical(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_canonical(v) for v in value)
    return value


def _quantize(value: Any, tol: float) -> Any:
    """Snap numeric leaves onto a ``tol``-wide grid (COMPARETOLERANCE analog).
    Mirrors ``cad_diff._quantize``. ``bool`` is excluded (int subclass, never a
    coordinate); ``tol <= 0`` disables snapping (exact compare)."""
    if isinstance(value, bool) or tol <= 0:
        return value
    if isinstance(value, (int, float)):
        return round(value / tol)
    if isinstance(value, dict):
        return {k: _quantize(v, tol) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_quantize(v, tol) for v in value]
    return value


def _fingerprint_geometry_payload(geometry: Any) -> Any:
    """Strip embedded cross-object HANDLE reference fields out of a geometry
    payload before it is used as (part of) an identity fingerprint.

    A HATCH's ``geometry.loops[].boundary_handles`` is exactly the kind of
    reference Rung-D exists to verify -- if it were left in, the HATCH
    entity's OWN fingerprint would change every time regen reissues its
    boundary's handle, and a CORRECT re-point would spuriously look like "a
    different hatch" (the source-side match in ``check_reference_integrity``
    would never line up between pre and post). Every other geometry kind in
    this IR has no embedded handle fields, so this is a no-op for them.
    """
    if not isinstance(geometry, dict):
        return geometry
    geom = dict(geometry)
    loops = geom.get("loops")
    if isinstance(loops, list):
        geom["loops"] = [
            ({k: v for k, v in loop.items() if k != "boundary_handles"}
             if isinstance(loop, dict) else loop)
            for loop in loops
        ]
    return geom


def _geometry_fingerprint(entity: Dict[str, Any], tol: float) -> Tuple[Any, Any, Any]:
    """The handle-independent ``(dxf_name, layer, geometry)`` join key.
    Mirrors ``cad_diff._geometry_fingerprint``: two entities with an equal
    fingerprint are the same physical entity regardless of DWG handle (see
    ``_fingerprint_geometry_payload`` for why embedded reference handles are
    excluded first)."""
    geom_key = _canonical(_quantize(_fingerprint_geometry_payload(entity.get("geometry")), tol))
    return (entity.get("dxf_name"), entity.get("layer"), geom_key)


# --------------------------------------------------------------------------- #
# Per-IR indexing
# --------------------------------------------------------------------------- #

def _index_by_handle(records: Any) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if not isinstance(records, list):
        return out
    for rec in records:
        if isinstance(rec, dict) and isinstance(rec.get("handle"), str) and rec["handle"]:
            out[rec["handle"]] = rec
    return out


def _build_indexes(ir: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Build handle -> record lookup tables for one IR (entities + the three
    named-object collections already in dwg_graph_ir.v1 + our ``fields``
    extension)."""
    return {
        "entities": _index_by_handle(ir.get("entities")),
        "groups": _index_by_handle(ir.get("groups")),
        "dictionaries": _index_by_handle(ir.get("dictionaries")),
        "xrecords": _index_by_handle(ir.get("xrecords")),
        "fields": _index_by_handle(ir.get("fields")),
    }


# --------------------------------------------------------------------------- #
# Handle -> handle-independent identity resolution
# --------------------------------------------------------------------------- #

def _group_identity(idx: Dict[str, Dict[str, Any]], grp: Dict[str, Any],
                    tol: float, seen: Set[str]) -> Tuple[Any, ...]:
    """A named group's identity is its ``name`` (required field, stable across
    regen). An anonymous group instead keys off the SORTED multiset of its
    members' own identities -- order-independent, so a re-ordered member list
    is not itself a mismatch (PLAN.md explicitly calls this out as a non-goal
    failure mode)."""
    if not grp.get("anonymous") and grp.get("name"):
        return ("group", grp["name"])
    member_ids = []
    for mh in grp.get("members") or []:
        mid = _resolve_object_identity(idx, mh, tol, seen)
        member_ids.append(mid if mid is not None else ("unresolved", mh))
    return ("group_anonymous", grp.get("name"), tuple(sorted(member_ids, key=repr)))


def _dictionary_identity(idx: Dict[str, Dict[str, Any]], rec: Dict[str, Any],
                         tol: float, seen: Set[str]) -> Tuple[Any, ...]:
    """A dictionary's identity is its ``name`` ("name as keyed in its parent"
    per the schema -- stable across regen) when present. An unnamed dictionary
    keys off the sorted multiset of its ``(entry key, resolved target
    identity)`` pairs."""
    if rec.get("name"):
        return ("dictionary", rec["name"])
    entry_sigs = []
    for entry in rec.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        tgt_id = _resolve_object_identity(idx, entry.get("value_handle"), tol, seen)
        entry_sigs.append((entry.get("key"),
                           tgt_id if tgt_id is not None else ("unresolved", entry.get("value_handle"))))
    return ("dictionary_anonymous", tuple(sorted(entry_sigs, key=repr)))


def _resolve_object_identity(idx: Dict[str, Dict[str, Any]], handle: Optional[str],
                             tol: float, seen: Optional[Set[str]] = None) -> Optional[Tuple[Any, ...]]:
    """Resolve ANY handle within one IR to a handle-independent identity tuple.

    Checks, in order: entity (geometry fingerprint) -> group -> dictionary ->
    xrecord -> field (our extension). Returns None when the handle does not
    resolve to any object kind this gate models (a real gap -- e.g. a viewport
    or layout target -- is reported as ``unverifiable``, never silently
    matched or silently passed; see module docstring, no-fake-success).

    ``seen`` cycle-guards recursive identity resolution (dictionaries/groups
    can reference other dictionaries/groups); a handle re-entered mid-recursion
    resolves to a distinguishable ``("cycle", handle)`` marker rather than
    recursing forever.
    """
    if not handle:
        return None
    if seen is None:
        seen = set()
    if handle in seen:
        return ("cycle", handle)
    seen = seen | {handle}

    ent = idx["entities"].get(handle)
    if ent is not None:
        return ("entity",) + _geometry_fingerprint(ent, tol)

    grp = idx["groups"].get(handle)
    if grp is not None:
        return _group_identity(idx, grp, tol, seen)

    rec = idx["dictionaries"].get(handle)
    if rec is not None:
        return _dictionary_identity(idx, rec, tol, seen)

    xr = idx["xrecords"].get(handle)
    if xr is not None:
        owner_id = _resolve_object_identity(idx, xr.get("owner_handle"), tol, seen)
        return ("xrecord", xr.get("dictionary"), xr.get("key"), owner_id)

    fld = idx["fields"].get(handle)
    if fld is not None:
        host_id = _resolve_object_identity(idx, fld.get("host_handle"), tol, seen)
        return ("field", host_id)

    return None


# --------------------------------------------------------------------------- #
# Edge extraction (one IR -> the reference edges it carries)
# --------------------------------------------------------------------------- #

def _hatch_boundary_edges(ir: Dict[str, Any], idx: Dict[str, Dict[str, Any]],
                          tol: float) -> List[Dict[str, Any]]:
    edges: List[Dict[str, Any]] = []
    for ent in ir.get("entities") or []:
        if not isinstance(ent, dict):
            continue
        geom = ent.get("geometry") or {}
        if geom.get("kind") != "hatch":
            continue
        source_id = ("entity",) + _geometry_fingerprint(ent, tol)
        label = "HATCH:%s" % ent.get("handle")
        for li, loop in enumerate(geom.get("loops") or []):
            if not isinstance(loop, dict) or not loop.get("associative"):
                continue
            for bi, bh in enumerate(loop.get("boundary_handles") or []):
                edges.append({
                    "category": "hatch_boundary",
                    "source_id": source_id,
                    "source_label": label,
                    "target_handle": bh,
                    "context": {"loop_index": li, "boundary_index": bi},
                })
    return edges


def _field_object_edges(ir: Dict[str, Any], idx: Dict[str, Dict[str, Any]],
                        tol: float) -> List[Dict[str, Any]]:
    edges: List[Dict[str, Any]] = []
    for i, rec in enumerate(ir.get("fields") or []):
        if not isinstance(rec, dict):
            continue
        host_handle = rec.get("host_handle")
        source_id = _resolve_object_identity(idx, host_handle, tol)
        label = "FIELD-HOST:%s" % host_handle
        for ti, th in enumerate(rec.get("referenced_handles") or []):
            edges.append({
                "category": "field_object",
                "source_id": source_id,
                "source_label": label,
                "target_handle": th,
                "context": {"field_index": i, "field_handle": rec.get("handle"), "ref_index": ti},
            })
    return edges


def _group_member_edges(ir: Dict[str, Any], idx: Dict[str, Dict[str, Any]],
                        tol: float) -> List[Dict[str, Any]]:
    edges: List[Dict[str, Any]] = []
    for grp in ir.get("groups") or []:
        if not isinstance(grp, dict):
            continue
        source_id = _group_identity(idx, grp, tol, set())
        label = "GROUP:%s" % (grp.get("name") or grp.get("handle"))
        for mi, mh in enumerate(grp.get("members") or []):
            edges.append({
                "category": "group_member",
                "source_id": source_id,
                "source_label": label,
                "target_handle": mh,
                "context": {"member_index": mi},
            })
    return edges


def _dictionary_entry_edges(ir: Dict[str, Any], idx: Dict[str, Dict[str, Any]],
                            tol: float) -> List[Dict[str, Any]]:
    edges: List[Dict[str, Any]] = []
    for rec in ir.get("dictionaries") or []:
        if not isinstance(rec, dict):
            continue
        source_id = _dictionary_identity(idx, rec, tol, set())
        label = "DICTIONARY:%s" % (rec.get("name") or rec.get("handle"))
        for ei, entry in enumerate(rec.get("entries") or []):
            if not isinstance(entry, dict):
                continue
            edges.append({
                "category": "dictionary_entry",
                "source_id": source_id,
                "source_label": label,
                "target_handle": entry.get("value_handle"),
                "context": {"entry_index": ei, "entry_key": entry.get("key")},
            })
    return edges


def _all_edges(ir: Dict[str, Any], idx: Dict[str, Dict[str, Any]],
               tol: float) -> List[Dict[str, Any]]:
    return (_hatch_boundary_edges(ir, idx, tol)
           + _field_object_edges(ir, idx, tol)
           + _group_member_edges(ir, idx, tol)
           + _dictionary_entry_edges(ir, idx, tol))


# --------------------------------------------------------------------------- #
# Public check
# --------------------------------------------------------------------------- #

def check_reference_integrity(pre_ir: Dict[str, Any], post_ir: Dict[str, Any],
                              geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE
                              ) -> Dict[str, Any]:
    """Rung-D: assert every persistent cross-object reference in ``pre_ir``
    resolves, in ``post_ir``, to the geometrically-corresponding target of what
    it referenced pre-regen (matched by fingerprint, never by raw handle).

    Returns a report dict:
        schema, status ("pass"|"fail"|"skipped"|"blocked"), geometry_tolerance,
        categories (per-category checked/matched/failed/unverifiable, all 4
        keys always present), summary (the same 4 counters totalled),
        violations (list of dicts; empty when clean), warnings (list of str).

    status:
      * "skipped" -- pre_ir carries ZERO modelled references (nothing to
        check; a truthful non-verdict, never a fake "pass").
      * "blocked" -- pre_ir carries references but NONE could be resolved to a
        checkable identity (source and/or target unresolvable throughout);
        the gate could not run to a verdict.
      * "fail"    -- at least one reference's post-regen counterpart does not
        resolve to the expected geometrically-corresponding target (dropped,
        or rewired to the wrong target).
      * "pass"    -- at least one reference was checked and none failed.
    """
    tol = geometry_tolerance
    pre_idx = _build_indexes(pre_ir or {})
    post_idx = _build_indexes(post_ir or {})

    pre_edges = _all_edges(pre_ir or {}, pre_idx, tol)
    post_edges = _all_edges(post_ir or {}, post_idx, tol)

    # Group PRE edges by (category, source_id) so a whole reference list (e.g.
    # one hatch loop's boundary_handles, or one group's members) is compared
    # as an order-independent MULTISET, not edge-by-edge.
    pre_groups: Dict[Tuple[str, Any], List[Dict[str, Any]]] = {}
    for e in pre_edges:
        pre_groups.setdefault((e["category"], e["source_id"]), []).append(e)

    post_multiset_by_source: Dict[Tuple[str, Any], "Counter[Any]"] = {}
    for e in post_edges:
        tgt_id = _resolve_object_identity(post_idx, e["target_handle"], tol)
        key = (e["category"], e["source_id"])
        post_multiset_by_source.setdefault(key, Counter())[tgt_id] += 1

    per_category: Dict[str, Dict[str, int]] = {
        cat: {"checked": 0, "matched": 0, "failed": 0, "unverifiable": 0}
        for cat in _CATEGORIES
    }
    violations: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for (cat, source_id), edges in sorted(pre_groups.items(), key=lambda kv: repr(kv[0])):
        slot = per_category[cat]

        if source_id is None:
            slot["unverifiable"] += len(edges)
            warnings.append(
                "%s: %d reference(s) whose SOURCE (%s) could not be resolved to "
                "a known object in the pre-regen IR" % (cat, len(edges), edges[0]["source_label"]))
            continue

        pre_multiset: "Counter[Any]" = Counter()
        target_handles_by_id: Dict[Any, List[str]] = {}
        unresolved_targets: List[str] = []
        for e in edges:
            tgt_id = _resolve_object_identity(pre_idx, e["target_handle"], tol)
            if tgt_id is None:
                unresolved_targets.append(e["target_handle"])
                continue
            pre_multiset[tgt_id] += 1
            target_handles_by_id.setdefault(tgt_id, []).append(e["target_handle"])

        if unresolved_targets:
            slot["unverifiable"] += len(unresolved_targets)
            warnings.append(
                "%s: source %s references %d target handle(s) unresolvable in "
                "the pre-regen IR: %s"
                % (cat, edges[0]["source_label"], len(unresolved_targets),
                   sorted(unresolved_targets)))

        checked = sum(pre_multiset.values())
        if checked == 0:
            continue
        slot["checked"] += checked

        post_multiset = post_multiset_by_source.get((cat, source_id), Counter())
        missing = pre_multiset - post_multiset  # Counter subtraction: positive remainders only
        matched = checked - sum(missing.values())
        slot["matched"] += matched

        if missing:
            slot["failed"] += sum(missing.values())
            violations.append({
                "category": cat,
                "source_label": edges[0]["source_label"],
                "source_id": repr(source_id),
                "expected_target_handles_pre": sorted(
                    h for tid in missing for h in target_handles_by_id.get(tid, [])),
                "missing_target_ids": [repr(k) for k in sorted(missing, key=repr)],
                "post_target_ids_seen": [repr(k) for k in sorted(post_multiset, key=repr)],
                "detail": ("post-regen counterpart of %s does not reference the "
                          "geometrically-corresponding target for %d of %d "
                          "checked reference(s)"
                          % (edges[0]["source_label"], sum(missing.values()), checked)),
            })

    total_checked = sum(c["checked"] for c in per_category.values())
    total_failed = sum(c["failed"] for c in per_category.values())
    total_unverifiable = sum(c["unverifiable"] for c in per_category.values())

    if total_checked == 0 and total_unverifiable == 0:
        status = "skipped"
    elif total_checked == 0:
        status = "blocked"
    elif total_failed > 0:
        status = "fail"
    else:
        status = "pass"

    return {
        "schema": REFINTEGRITY_SCHEMA_ID,
        "status": status,
        "geometry_tolerance": tol,
        "categories": per_category,
        "summary": {
            "checked": total_checked,
            "matched": total_checked - total_failed,
            "failed": total_failed,
            "unverifiable": total_unverifiable,
        },
        "violations": violations,
        "warnings": warnings,
    }


def reference_integrity_ok(pre_ir: Dict[str, Any], post_ir: Dict[str, Any],
                           geometry_tolerance: float = DEFAULT_GEOMETRY_TOLERANCE) -> bool:
    """True unless the gate found an actual violation (``status == "fail"``).

    ``"skipped"`` (nothing to check) and ``"blocked"`` (could not resolve
    enough to check) are NOT violations, but a caller that must distinguish
    "verified clean" from "nothing was verified" should read
    ``check_reference_integrity(...)["status"]`` directly instead.
    """
    return check_reference_integrity(pre_ir, post_ir, geometry_tolerance)["status"] != "fail"


# --------------------------------------------------------------------------- #
# Synthetic fixtures (shared by the self-demo below AND tests/unit)
# --------------------------------------------------------------------------- #

def make_fixture_pre_ir() -> Dict[str, Any]:
    """Small synthetic ``ariadne.dwg_graph_ir.v1`` IR exercising all four
    Rung-D reference categories in one document:

      * an associative HATCH (``hHATCH``) whose one loop is bound to a CIRCLE
        boundary (``hE1``);
      * a FIELD-extension record (``hF1``, IR extension -- see module
        docstring) hosted on an MTEXT (``hE5``) that references a second,
        geometrically-distinct CIRCLE (``hE2``);
      * a named GROUP (``hG1``, "DOORGROUP") whose members are the boundary
        CIRCLE (``hE1``, deliberately shared with the hatch) and a LINE
        (``hE3``);
      * a DICTIONARY (``hD1``, "ACAD_GROUP") with one entry pointing at that
        group.

    ``make_regenerated_ir`` is the only thing that should ever be compared
    against this fixture as a "post" document -- see its docstring.
    """
    def _entity(handle: str, cls: str, dxf_name: str, layer: str,
               geometry: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "handle": handle,
            "class": cls,
            "dxf_name": dxf_name,
            "owner_handle": "1F",
            "space": "model",
            "layer": layer,
            "bbox": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "geometry": geometry,
            "source": {"extractor": "cad_refintegrity_gate.fixture", "decoded": True},
        }

    entities = [
        _entity("hE1", "AcDbCircle", "CIRCLE", "0",
               {"kind": "circle", "center": [5.0, 5.0, 0.0], "radius": 2.5}),
        _entity("hE2", "AcDbCircle", "CIRCLE", "0",
               {"kind": "circle", "center": [50.0, 50.0, 0.0], "radius": 1.0}),
        _entity("hE3", "AcDbLine", "LINE", "0",
               {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [10.0, 0.0, 0.0]}),
        _entity("hE5", "AcDbMText", "MTEXT", "TEXT",
               {"kind": "mtext", "position": [1.0, 1.0, 0.0], "text": "Area = <field>"}),
        _entity("hHATCH", "AcDbHatch", "HATCH", "HATCH",
               {
                   "kind": "hatch",
                   "pattern_name": "SOLID",
                   "loops": [
                       {"associative": True, "loop_type": "polyline",
                        "boundary_handles": ["hE1"]},
                   ],
               }),
    ]

    fields = [
        {"handle": "hF1", "host_handle": "hE5", "referenced_handles": ["hE2"],
         "evaluator_id": "AcDb::ObjectValue"},
    ]

    groups = [
        {"handle": "hG1", "name": "DOORGROUP", "anonymous": False,
         "selectable": True, "members": ["hE1", "hE3"]},
    ]

    dictionaries = [
        {"handle": "hD1", "name": "ACAD_GROUP", "owner_handle": "0",
         "is_hard_owner": True,
         "entries": [{"key": "DOORGROUP", "value_handle": "hG1"}]},
    ]

    return {
        "schema": IR_SCHEMA_ID,
        "ir_version": "1.0.0",
        "coverage_level": "native_full",
        "source": {"dwg_name": "refintegrity_fixture.dwg", "format": "dwg"},
        "database": {},
        "symbol_tables": {"layers": [{"name": "0"}, {"name": "HATCH"}, {"name": "TEXT"}]},
        "entities": entities,
        "fields": fields,
        "groups": groups,
        "dictionaries": dictionaries,
        "diagnostics": {
            "entity_count": len(entities),
            "realized_entity_count": len(entities),
            "warnings": [],
            "errors": [],
            "coverage": {"sections_present": ["entities", "fields", "groups", "dictionaries"]},
        },
    }


# Deterministic rehandle map used by make_regenerated_ir: old fixture handle ->
# new (regen-reissued) handle. Values are arbitrary and unrelated to the old
# handle string ON PURPOSE -- Rung-D must resolve references by FINGERPRINT,
# never by any residual textual relationship between an old and a new handle.
_FIXTURE_REHANDLE_MAP: Dict[str, str] = {
    "hE1": "9F3", "hE2": "1A0", "hE3": "77C", "hE5": "5D9",
    "hHATCH": "E01", "hF1": "B44", "hG1": "C12", "hD1": "3E7",
}


def _rehandle(value: Any, rehandle_map: Dict[str, str]) -> Any:
    if isinstance(value, str) and value in rehandle_map:
        return rehandle_map[value]
    return value


def make_regenerated_ir(pre_ir: Dict[str, Any], *, break_category: Optional[str] = None,
                        rehandle_map: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Simulate a regen roundtrip of ``pre_ir``: every object handle is
    reissued (per ``rehandle_map``, default ``_FIXTURE_REHANDLE_MAP``) while
    dxf_name / layer / geometry / name / key content is preserved
    byte-for-byte, and every cross-reference this gate models is re-pointed to
    follow its ORIGINAL target through that target's new handle -- i.e. a
    textbook-correct roundtrip that a handle-independent geometry diff would
    report as ``diff == 0``.

    ``break_category`` optionally names ONE of ``hatch_boundary`` /
    ``field_object`` / ``group_member`` / ``dictionary_entry``; when given,
    that single reference is instead re-pointed at a geometrically-DIFFERENT
    object already present in the fixture, reproducing the exact class of
    silent corruption Rung-D exists to catch (PLAN.md v2-A5 / OPUS_REVIEW C2).
    Every other reference remains correctly re-pointed, so a correct gate
    implementation must flag ONLY the requested category.
    """
    rehandle_map = rehandle_map or _FIXTURE_REHANDLE_MAP
    post = json.loads(json.dumps(pre_ir))  # deep copy (stdlib only)

    for ent in post.get("entities", []):
        ent["handle"] = _rehandle(ent.get("handle"), rehandle_map)
        geom = ent.get("geometry") or {}
        if geom.get("kind") == "hatch":
            for loop in geom.get("loops") or []:
                loop["boundary_handles"] = [_rehandle(h, rehandle_map)
                                           for h in loop.get("boundary_handles") or []]

    for rec in post.get("fields", []):
        rec["handle"] = _rehandle(rec.get("handle"), rehandle_map)
        rec["host_handle"] = _rehandle(rec.get("host_handle"), rehandle_map)
        rec["referenced_handles"] = [_rehandle(h, rehandle_map)
                                    for h in rec.get("referenced_handles") or []]

    for grp in post.get("groups", []):
        grp["handle"] = _rehandle(grp.get("handle"), rehandle_map)
        grp["members"] = [_rehandle(h, rehandle_map) for h in grp.get("members") or []]

    for rec in post.get("dictionaries", []):
        rec["handle"] = _rehandle(rec.get("handle"), rehandle_map)
        for entry in rec.get("entries") or []:
            entry["value_handle"] = _rehandle(entry.get("value_handle"), rehandle_map)

    if break_category is None:
        return post
    if break_category not in _CATEGORIES:
        raise ValueError("unknown break_category %r (expected one of %s)"
                        % (break_category, _CATEGORIES))

    wrong = rehandle_map  # shorthand: look up the (already-reissued) wrong-target handle
    if break_category == "hatch_boundary":
        for ent in post["entities"]:
            geom = ent.get("geometry") or {}
            if geom.get("kind") == "hatch":
                geom["loops"][0]["boundary_handles"] = [wrong["hE2"]]  # correct target is hE1
    elif break_category == "field_object":
        post["fields"][0]["referenced_handles"] = [wrong["hE1"]]  # correct target is hE2
    elif break_category == "group_member":
        members = post["groups"][0]["members"]
        post["groups"][0]["members"] = [wrong["hE2"] if m == wrong["hE1"] else m
                                       for m in members]  # correct target is hE1
    elif break_category == "dictionary_entry":
        post["dictionaries"][0]["entries"][0]["value_handle"] = wrong["hE1"]  # correct target is hG1

    return post


# --------------------------------------------------------------------------- #
# Self-demo (__main__ with no args): correct roundtrip PASSes, each
# deliberately mis-rewired category FAILs.
# --------------------------------------------------------------------------- #

def _selftest() -> int:
    print("== cad_refintegrity_gate self-demo (Rung-D) ==")
    pre = make_fixture_pre_ir()

    post_ok = make_regenerated_ir(pre, break_category=None)
    report_ok = check_reference_integrity(pre, post_ok)
    print("correct roundtrip        : status=%s checked=%d failed=%d"
         % (report_ok["status"], report_ok["summary"]["checked"], report_ok["summary"]["failed"]))
    correct_ok = report_ok["status"] == "pass" and report_ok["summary"]["failed"] == 0

    # determinism: recompute and compare byte-for-byte (no timestamps/randomness).
    report_ok2 = check_reference_integrity(pre, post_ok)
    deterministic = (json.dumps(report_ok, sort_keys=True, ensure_ascii=False)
                    == json.dumps(report_ok2, sort_keys=True, ensure_ascii=False))
    print("determinism (re-run)     : %s" % deterministic)

    results: Dict[str, bool] = {}
    for cat in _CATEGORIES:
        post_bad = make_regenerated_ir(pre, break_category=cat)
        rep = check_reference_integrity(pre, post_bad)
        cat_ok = (rep["status"] == "fail"
                 and any(v["category"] == cat for v in rep["violations"]))
        results[cat] = cat_ok
        print("mis-rewired %-16s: status=%s violations=%d (%s)"
             % (cat, rep["status"], len(rep["violations"]),
                "detected" if cat_ok else "MISSED"))
        if cat == "hatch_boundary" and rep["violations"]:
            v0 = rep["violations"][0]
            print("  first violation        : %s" % v0["detail"])

    passed = correct_ok and deterministic and all(results.values())
    print("RESULT                    : %s" % ("PASS" if passed else "FAIL"))
    return 0 if passed else 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _main(argv: List[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="cad_refintegrity_gate.py",
        description="Rung-D cross-object reference-integrity gate "
                    "(emits ariadne.cad_refintegrity_gate.v1).")
    parser.add_argument("--pre", dest="pre", default=None,
                       help="path to the pre-regen ariadne.dwg_graph_ir.v1 document")
    parser.add_argument("--post", dest="post", default=None,
                       help="path to the post-regen ariadne.dwg_graph_ir.v1 document")
    parser.add_argument("--tol", dest="tol", type=float, default=DEFAULT_GEOMETRY_TOLERANCE,
                       help="geometry tolerance (COMPARETOLERANCE analog)")
    parser.add_argument("--out", dest="out", default=None,
                       help="write the report JSON to this path (else stdout)")
    args = parser.parse_args(argv)

    if not args.pre or not args.post:
        # No target given -> run the inline self-demo (back-compat with bare run).
        return _selftest()

    pre_ir = load_ir(args.pre)
    post_ir = load_ir(args.post)
    report = check_reference_integrity(pre_ir, post_ir, geometry_tolerance=args.tol)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("wrote %s (status=%s)" % (args.out, report["status"]))
    else:
        print(text)
    return 0 if report["status"] in ("pass", "skipped") else 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
