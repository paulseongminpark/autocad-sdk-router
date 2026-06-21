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
    body and NO randomness. ``diff_id`` is a content hash of the two IRs, so the
    same pair of IRs always yields byte-identical output.
  * No-fake-success: an entity missing a handle cannot be joined and is recorded
    in ``diagnostics.warnings`` (counted, never silently dropped or matched).
  * Read-only: this module never writes an IR or a DWG. It returns / prints a
    diff dict.
  * Truthful sibling degradation: ``ir_builder`` is imported via
    ``_import_optional``; if it is absent the public diff API still works and the
    ``__main__`` self-demo degrades to ``not_implemented`` rather than crashing.

Public API:
    DIFF_SCHEMA_ID
    compute_diff(pre_ir: dict, post_ir: dict) -> dict          # cad_diff.v1
    classify_change(pre_entity: dict, post_entity: dict) -> list[str]
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


def write_diff(diff: Dict[str, Any], path) -> str:
    """Write a cad_diff document (UTF-8, pretty). Returns the path written."""
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

def _deterministic_diff_id(pre_ir: Dict[str, Any], post_ir: Dict[str, Any]) -> str:
    """Content-hash the (sorted) handle->signature of both IRs for a stable id.

    The id is a function of the inputs only (no time, no randomness), so re-diffing
    the same pair of IRs yields the same ``diff_id``. The signature uses each
    entity's join-relevant fields (handle/dxf_name/layer/bbox/geometry).
    """
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

    payload = json.dumps([_canonical(sig(pre_ir)), _canonical(sig(post_ir))],
                         ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return "diff-%s" % digest


# --------------------------------------------------------------------------- #
# Public diff
# --------------------------------------------------------------------------- #

def compute_diff(pre_ir: Dict[str, Any], post_ir: Dict[str, Any]) -> Dict[str, Any]:
    """Compute a deterministic structural diff between two dwg_graph_ir.v1 IRs.

    Args:
        pre_ir:  the 'before' IR document (ariadne.dwg_graph_ir.v1).
        post_ir: the 'after' IR document.

    Returns:
        A dict conforming to ``ariadne.cad_diff.v1``. Entities are joined on
        ``handle``: handles only in ``post`` are ``added``, only in ``pre`` are
        ``removed``, in both with a changed field are ``modified``. The diff body
        contains no timestamps and is fully determined by the two inputs.

        In addition to the frozen schema fields (``changed_handles`` with change
        in added/removed/modified, ``summary`` with added/removed/modified), the
        report carries extension fields (allowed by the schema's
        additionalProperties:true) requested by the CAD OS Layer M02 contract:
        ``summary.created_count/deleted_count/modified_count/unchanged_count``,
        ``summary.by_type`` (per-DXF-type added/removed/modified), and the
        ``layer_changes`` / ``geometry_changes`` / ``bbox_changes`` projections.
    """
    pre_ir = pre_ir or {}
    post_ir = post_ir or {}

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
        "diff_id": _deterministic_diff_id(pre_ir, post_ir),
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
