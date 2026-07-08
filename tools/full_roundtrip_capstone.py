#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""full_roundtrip_capstone.py -- CAD OS Layer north-star capstone (PLAN Sec.
0.6 A1): full-drawing extract -> regen (certified classes only) -> re-extract
-> handle-independent multiset diff, driven on the real lane-A production
drawing.

This module is a DRIVER, not a new engine. It reuses, unmodified:
  * tools/patch_engine.py       -- create_staged_copy / apply_staged (the
                                    real staged-write lifecycle: staging,
                                    per-op native writes, post-extraction,
                                    original-unchanged proof).
  * tools/run_job.py            -- run_router_cad_job (the native inspect/
                                    write host invocation + capture).
  * tools/ir_builder.py         -- build_ir_from_database_graph (native
                                    result -> dwg_graph_ir.v1), via patch_
                                    engine._native_full_ir (the SAME helper
                                    apply_staged's own pre/post-inspect steps
                                    use, so census IRs are shaped identically
                                    to regen's pre/post IRs).
  * tools/ir_to_patch.py + tools/patch_ops/*  -- IR entity -> cad_patch op,
                                    per-family dispatch. NOT edited here:
                                    whatever ir_op_for cannot map today is
                                    honestly reported as deferred, never
                                    guessed at in this file.
  * tools/cad_diff.py's comparison_basis="geometry" -- the ALREADY-EXISTING
                                    handle-independent, tolerance-aware
                                    (dxf_name, layer, geometry) multiset join
                                    (PLAN 0.6 A1's own required mechanism).
                                    This module does not reimplement that
                                    join; it only derives a per-(dxf_name)
                                    rollup ("regen_attempted / diff0 /
                                    modified / removed / added") from its
                                    output.
  * tools/op_roundtrip_probe.py's LAYER_RECORD_FIELDS / layer_record_diff
                                    (and its documented DIMSTYLE sibling) --
                                    reused for the record-table (layer/
                                    dimstyle) comparison, never reimplemented.

No C++, no registry, no edits to patch_ops/ir_builder/op_roundtrip_probe:
this is a NEW file per the capstone-prep packet.

Public API (pure -- no I/O, no CAD engine; independently unit-testable):
    sha256_file(path) -> str | None
    check_identity(path_a, path_b) -> dict
    classify_entity_bucket(dxf_name, kind) -> str
    census_report(ir) -> dict
    filter_ir_to_certified(ir, kinds=None, limit=None, per_kind_limit=None) -> dict
    layer_op_args_from_record(record, op_roundtrip_probe_mod) -> dict
    dimstyle_op_args_from_record(record, op_roundtrip_probe_mod) -> dict
    record_diff_report(kind_label, records, actual_ir, *, name_field, fields, diff_fn, lookup_fn) -> dict
    per_kind_verdict(pre_ir, diff, *, deferred=None) -> dict
    resolvable_ops_report(patch, patch_ops_mod=None) -> dict
    record_op_args_from_record(record, fields) -> dict
    build_records_patch(census_ir, target_dwg, patch_id, ...) -> (patch, meta)
    table_record_diff_reports(census_ir, post_ir, ...) -> dict  (Closeout #130)
    regen_gate_report(op_count, apply_result) -> dict  (Closeout #129a)
    combine_gate_statuses(statuses) -> str

Public API (live -- needs a real AutoCAD runtime via patch_engine/run_job):
    run_census(staged_path, original_path, run_dir, ...) -> dict
    run_regen_batch(filtered_ir, blank_seed_path, run_dir, patch_id, ...) -> dict
    run_records_batch(census_ir, blank_seed_path, run_dir, patch_id, ...) -> dict
    run_capstone(...) -> dict  (top-level orchestrator; see main() / CLI)

CLI:
    python tools/full_roundtrip_capstone.py --census-only \\
        --dwg tests/fixtures/native_sample.dwg --out-dir runs/capstone/<ts>

    python tools/full_roundtrip_capstone.py \\
        --dwg tests/fixtures/native_sample.dwg --seed tests/fixtures/blank_seed.dwg \\
        --out-dir runs/capstone/<ts> --kinds line,circle,arc --per-kind-limit 20
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import shutil
import sys
import time
from collections import Counter, defaultdict
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

# Mission-cited path (D:\dev\_ariadne\alm\build\input.dwg) does not exist on
# disk as of this build -- the live file at that location is input0616.dwg.
# check_identity() is run explicitly (see main()) against native_sample.dwg
# so this drift is recorded as data, never silently assumed.
DEFAULT_DWG = os.path.join(_ROUTER_HOME, "tests", "fixtures", "native_sample.dwg")
DEFAULT_COMPARE_PATH = r"D:\dev\_ariadne\alm\build\input0616.dwg"
DEFAULT_SEED = os.path.join(_ROUTER_HOME, "tests", "fixtures", "blank_seed.dwg")


# --------------------------------------------------------------------------- #
# 0. sha256 / identity (pure, read-only)
# --------------------------------------------------------------------------- #

def sha256_file(path: Optional[str]) -> Optional[str]:
    if not path or not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_identity(path_a: str, path_b: str) -> Dict[str, Any]:
    """Byte-identity check between two DWG paths (e.g. the tracked test
    fixture vs the workitem's production file) -- pure file hashing, no CAD
    engine, no mutation of either path."""
    sha_a = sha256_file(path_a)
    sha_b = sha256_file(path_b)
    return {
        "path_a": path_a, "path_b": path_b,
        "exists_a": bool(path_a and os.path.isfile(path_a)),
        "exists_b": bool(path_b and os.path.isfile(path_b)),
        "sha256_a": sha_a, "sha256_b": sha_b,
        "identical": bool(sha_a) and bool(sha_b) and sha_a == sha_b,
    }


# --------------------------------------------------------------------------- #
# 1. certified-class classification, re-derived live against
#    ir_builder._NATIVE_CLASS_TO_DXF_KIND (as of ced3ee8) -- see build_log.md
#    for the full derivation. (dxf_name, geometry.kind) is the real join key:
#    dxf_name alone is not unique (POLYLINE covers legacy-2D/3D-polyline,
#    polygon_mesh AND poly_face_mesh, only separated by "kind"; LEADER vs
#    MULTILEADER share kind=="leader" but differ by dxf_name) -- this mirrors
#    cad_diff._geometry_fingerprint's own (dxf_name, layer, geometry) tuple.
# --------------------------------------------------------------------------- #

CERTIFIED_BUCKETS: Dict[Tuple[str, str], str] = {
    ("LINE", "line"): "line",
    ("CIRCLE", "circle"): "circle",
    ("ARC", "arc"): "arc",
    ("ELLIPSE", "ellipse"): "ellipse",
    ("SPLINE", "spline"): "spline",
    ("LWPOLYLINE", "lwpolyline"): "lwpolyline",
    # AcDb2dPolyline AND AcDb3dPolyline both normalize to dxf_name=POLYLINE,
    # kind=polyline in ir_builder._NATIVE_CLASS_TO_DXF_KIND -- the IR itself
    # cannot separate "polyline2d" from "polyline3d" (both wave certs land in
    # this one census bucket; documented gap, not a miscount).
    ("POLYLINE", "polyline"): "polyline2d_or_polyline3d",
    ("POLYLINE", "polygon_mesh"): "polygonmesh",
    ("POLYLINE", "poly_face_mesh"): "polyfacemesh",
    ("TEXT", "text"): "text",
    ("MTEXT", "mtext"): "mtext",
    ("MLINE", "mline"): "mline",
    ("LEADER", "leader"): "leader",
    ("MULTILEADER", "leader"): "mleader",
    # All 9 DIMENSION subtypes (rotated/aligned/radial/diametric/ordinate/
    # arc/angular2line/angular3pt/radiallarge) normalize to ONE
    # (dxf_name, kind) = (DIMENSION, dimension) pair -- not separable from
    # geometry.kind alone (same caveat as polyline2d/3d above).
    ("DIMENSION", "dimension"): "dimension_all_subtypes",
    ("INSERT", "block_reference"): "insert",
}

CERTIFIED_KINDS: Set[str] = {kind for (_dxf, kind) in CERTIFIED_BUCKETS}

# Known-but-not-certified native classes -> why, for the census's out-of-class
# reason column. Anything ir_builder itself cannot decode (kind=="unsupported")
# is "unmapped_native_class" instead -- a distinct, more severe gap.
_OUT_OF_CLASS_REASON_BY_DXF: Dict[str, str] = {
    "HATCH": "attended_or_read_pending (a1-hatchread wave in progress)",
    "ATTDEF": "in_progress (p3-insattr wave: block def_entities ATTDEF)",
    "ATTRIB": "in_progress (p3-insattr wave: INSERT-attached ATTRIB)",
    "3DSOLID": "asm_solids_pending (Wave-S / s0-asmprobe)",
    "REGION": "asm_solids_pending (Wave-S / s0-asmprobe)",
    "VIEWPORT": "no_wave_assignment_as_of_ced3ee8",
    "POINT": "no_wave_assignment_as_of_ced3ee8",
    "SOLID": "no_wave_assignment_as_of_ced3ee8",
}


def classify_entity_bucket(dxf_name: str, kind: str) -> str:
    """CERTIFIED_BUCKETS label, or an out-of-class reason string. Never
    raises. An unrecognized pair is "recognized_not_certified" (kind !=
    "unsupported", i.e. ir_builder DID decode it, just not into a certified
    bucket) or "unmapped_native_class" (ir_builder's own
    _NATIVE_CLASS_TO_DXF_KIND has no entry for this native class at all)."""
    label = CERTIFIED_BUCKETS.get((dxf_name, kind))
    if label is not None:
        return label
    if kind == "unsupported":
        return "unmapped_native_class"
    return _OUT_OF_CLASS_REASON_BY_DXF.get(dxf_name, "recognized_not_certified")


# --------------------------------------------------------------------------- #
# 2. census (pure -- operates on an already-loaded dwg_graph_ir.v1 dict)
# --------------------------------------------------------------------------- #

def census_report(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Full per-(dxf_name, kind) breakdown of an IR's top-level modelspace
    entities, cross-tabulated into certified vs out-of-class (with reasons),
    plus a block-definitions census and a symbol-tables record census."""
    entities = [e for e in (ir.get("entities") or []) if isinstance(e, dict)]
    by_bucket: Counter = Counter()
    for e in entities:
        dxf = e.get("dxf_name", "") or ""
        kind = (e.get("geometry") or {}).get("kind", "") or ""
        by_bucket[(dxf, kind)] += 1

    rows = []
    certified_total = 0
    out_of_class_total = 0
    for (dxf, kind), count in sorted(by_bucket.items(), key=lambda kv: (-kv[1], kv[0])):
        is_certified = (dxf, kind) in CERTIFIED_BUCKETS
        rows.append({
            "dxf_name": dxf, "kind": kind, "count": count,
            "certified": is_certified,
            "label": classify_entity_bucket(dxf, kind),
        })
        if is_certified:
            certified_total += count
        else:
            out_of_class_total += count

    # Block-def contents census: nested (block_definitions[].entities), NOT
    # part of the modelspace multiset the regen/diff steps operate over.
    block_defs = ir.get("block_definitions") or []
    block_def_entity_total = 0
    block_def_by_bucket: Counter = Counter()
    for bd in block_defs:
        if not isinstance(bd, dict):
            continue
        bd_entities = bd.get("entities")
        if bd_entities is None:
            bd_entities = bd.get("def_entities") or []
        for e in bd_entities:
            if not isinstance(e, dict):
                continue
            block_def_entity_total += 1
            dxf = e.get("dxf_name", "") or ""
            kind = (e.get("geometry") or {}).get("kind", "") or ""
            block_def_by_bucket[(dxf, kind)] += 1

    symbol_tables = ir.get("symbol_tables") or {}
    symbol_table_counts = {
        k: (len(v) if isinstance(v, list) else None) for k, v in symbol_tables.items()
    }

    return {
        "modelspace_entity_total": len(entities),
        "certified_total": certified_total,
        "out_of_class_total": out_of_class_total,
        "by_bucket": rows,
        "block_definitions_count": len(block_defs),
        "block_definitions_entity_total": block_def_entity_total,
        "block_definitions_by_bucket": [
            {"dxf_name": d, "kind": k, "count": c}
            for (d, k), c in sorted(block_def_by_bucket.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "symbol_tables_present": sorted(symbol_tables.keys()),
        "symbol_table_record_counts": symbol_table_counts,
        "diagnostics_entities_by_type": (ir.get("diagnostics") or {}).get("entities_by_type"),
    }


def filter_ir_to_certified(ir: Dict[str, Any], *, kinds: Optional[Set[str]] = None,
                           limit: Optional[int] = None,
                           per_kind_limit: Optional[int] = None) -> Dict[str, Any]:
    """A shallow copy of ``ir`` whose entities[] is restricted to certified
    (dxf_name, kind) buckets (optionally narrowed further by ``kinds``), with
    an optional global ``limit`` and/or ``per_kind_limit`` -- the capstone's
    "per-kind batches" / "largest feasible assembled subset" knobs. Never
    mutates the input IR; iteration order (and therefore which entities get
    dropped once a limit is hit) follows the input entities[] order."""
    allowed_kinds = CERTIFIED_KINDS if kinds is None else (CERTIFIED_KINDS & set(kinds))
    out_entities: List[Dict[str, Any]] = []
    per_kind_seen: Dict[str, int] = defaultdict(int)
    for e in (ir.get("entities") or []):
        if not isinstance(e, dict):
            continue
        dxf = e.get("dxf_name", "") or ""
        kind = (e.get("geometry") or {}).get("kind", "") or ""
        if (dxf, kind) not in CERTIFIED_BUCKETS or kind not in allowed_kinds:
            continue
        if per_kind_limit is not None and per_kind_seen[kind] >= per_kind_limit:
            continue
        out_entities.append(e)
        per_kind_seen[kind] += 1
        if limit is not None and len(out_entities) >= limit:
            break
    filtered = dict(ir)
    filtered["entities"] = out_entities
    return filtered


def apply_def_entity_budget(ir: Dict[str, Any],
                            max_def_entities: int) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """(ir-copy, dropped[]) where block_definitions entries whose def_entities
    count exceeds ``max_def_entities`` are removed whole. ir_to_patch then
    defers any create_blockref naming a dropped definition with its honest
    'no block_definitions entry for block_name ...' reason instead of
    attempting a synthesis whose per-op cost is out of wall-clock budget
    (measured ~13 s/op; e.g. 1.dwg's X-평면도(기본형) is 20,567 def
    entities in closure -- ~74 h per-op). Whole-def drop + explicit report
    only; a definition is never silently truncated to fit the budget."""
    dropped: List[Dict[str, Any]] = []
    kept: List[Dict[str, Any]] = []
    for bd in (ir.get("block_definitions") or []):
        n = len(bd.get("def_entities") or [])
        if n > max_def_entities:
            dropped.append({
                "name": bd.get("name"), "handle": bd.get("handle"),
                "def_entity_count": n,
                "reason": "def_entity_count %d > --max-def-entities-per-block %d" % (
                    n, max_def_entities),
            })
        else:
            kept.append(bd)
    out = dict(ir)
    out["block_definitions"] = kept
    return out, dropped


# --------------------------------------------------------------------------- #
# 3. layer / dimstyle record regen + record-diff (reuses op_roundtrip_probe's
#    EXISTING LAYER_RECORD_FIELDS/layer_record_diff and its documented
#    DIMSTYLE_RECORD_FIELDS/dimstyle_record_diff sibling -- never
#    reimplemented here; this module only builds op ARGS from a census
#    record and drives the diff function the wave already certified with).
# --------------------------------------------------------------------------- #

# Fallback field lists used only if op_roundtrip_probe's own DIMSTYLE
# constant isn't present under this exact name in a given checkout --
# mirrors patch_ops.tables._DIMSTYLE_PASSTHROUGH_FIELDS/_DIMSTYLE_FLAG_FIELDS
# so this module degrades gracefully instead of raising AttributeError.
_DIMSTYLE_FIELDS_FALLBACK = ("dimtxt", "dimasz", "dimexe", "dimexo", "dimdec",
                            "dimscale", "dimclrd", "dimclre", "dimclrt", "dimse1")


def layer_op_args_from_record(record: Dict[str, Any], op_roundtrip_probe_mod) -> Dict[str, Any]:
    """create_layer op args that replicate one census-extracted
    symbol_tables.layers[] record (name + every LAYER_RECORD_FIELDS key
    present on the record)."""
    args: Dict[str, Any] = {"name": record.get("name")}
    for k in op_roundtrip_probe_mod.LAYER_RECORD_FIELDS:
        if k in record:
            args[k] = record[k]
    return args


def dimstyle_op_args_from_record(record: Dict[str, Any], op_roundtrip_probe_mod) -> Dict[str, Any]:
    """create_dimstyle op args that replicate one census-extracted dimstyle
    record (name + every DIMSTYLE_RECORD_FIELDS key present on the record)."""
    fields = getattr(op_roundtrip_probe_mod, "DIMSTYLE_RECORD_FIELDS", _DIMSTYLE_FIELDS_FALLBACK)
    args: Dict[str, Any] = {"name": record.get("name")}
    for k in fields:
        if k in record:
            args[k] = record[k]
    return args


def record_diff_report(label: str, records: List[Dict[str, Any]], actual_ir: Dict[str, Any], *,
                       table_key: str, fields: Tuple[str, ...],
                       diff_fn: Callable[[Dict[str, Any], Optional[Dict[str, Any]]], List[str]]
                       ) -> Dict[str, Any]:
    """Per-record diff of ``records`` (the census's OWN extracted rows, taken
    as ground truth -- what regen was asked to reproduce) against
    ``actual_ir.symbol_tables[table_key]`` (re-extracted after regen),
    joined by name (the table's own unique key, never a handle). Mirrors
    op_roundtrip_probe.probe_layer_roundtrip's record-diff shape, generalized
    over the join field set."""
    actual_by_name = {
        r.get("name"): r for r in ((actual_ir.get("symbol_tables") or {}).get(table_key) or [])
        if isinstance(r, dict)
    }
    rows = []
    zero_diff_count = 0
    for rec in records:
        name = rec.get("name")
        expected = {k: rec[k] for k in fields if k in rec}
        actual = actual_by_name.get(name)
        diff = diff_fn(expected, actual)
        if not diff:
            zero_diff_count += 1
        rows.append({"name": name, "expected": expected, "actual": actual, "record_diff": diff})
    return {
        "label": label, "table_key": table_key,
        "record_count": len(records), "zero_diff_count": zero_diff_count,
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# 4. handle-independent per-kind verdict -- rolls up cad_diff.compute_diff's
#    OWN comparison_basis="geometry" output; does not reimplement its
#    (dxf_name, layer, geometry) fingerprint/tolerance matching.
# --------------------------------------------------------------------------- #

def per_kind_verdict(pre_ir: Dict[str, Any], diff: Dict[str, Any], *,
                     deferred: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Per-dxf_name regen verdict from a comparison_basis="geometry" diff
    between ``pre_ir`` (the filtered ORIGINAL production drawing's subset
    regen was asked to reproduce) and the regenerated-then-re-extracted
    ``post_ir`` that diff was computed against.

    diff0_count ("unchanged" -- matched byte-exact or within tolerance, see
    cad_diff._compute_diff_geometry_basis tiers 1/1.5) is derived as
    pre_count[dxf] - modified[dxf] - removed[dxf]: compute_diff's own
    summary.by_type tracks only added/removed/modified per type (not
    unchanged), so this is arithmetic on ITS OWN counts, not a re-derivation
    of the match itself.
    """
    pre_counts: Counter = Counter(
        e.get("dxf_name", "") or "" for e in (pre_ir.get("entities") or []) if isinstance(e, dict))
    by_type = (diff.get("summary") or {}).get("by_type") or {}
    changed = diff.get("changed_handles") or []
    dxf_names_by_kind: Dict[str, Set[str]] = defaultdict(set)
    for dxf_name, kind in CERTIFIED_BUCKETS:
        dxf_names_by_kind[kind].add(dxf_name)
    dxf_by_deferred_kind = {
        kind: next(iter(dxf_names))
        for kind, dxf_names in dxf_names_by_kind.items()
        if len(dxf_names) == 1
    }
    deferred_counts: Counter = Counter()
    for rec in deferred or []:
        if not isinstance(rec, dict):
            continue
        dxf_name = dxf_by_deferred_kind.get(rec.get("kind", "") or "")
        if dxf_name:
            deferred_counts[dxf_name] += 1

    examples: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for rec in changed:
        dxf = rec.get("dxf_name", "") or ""
        bucket = examples[dxf][rec.get("change", "")]
        if len(bucket) < 3:
            bucket.append(rec)

    rows = []
    for dxf in sorted(set(pre_counts) | set(by_type)):
        pre_count = pre_counts.get(dxf, 0)
        t = by_type.get(dxf, {})
        added, removed, modified = t.get("added", 0), t.get("removed", 0), t.get("modified", 0)
        deferred_count = deferred_counts.get(dxf, 0)
        rows.append({
            "dxf_name": dxf,
            "regen_attempted_count": pre_count,
            "deferred_count": deferred_count,
            "attempted_live_count": max(pre_count - deferred_count, 0),
            "diff0_count": pre_count - modified - removed,
            "modified_count": modified,
            "removed_count": removed,  # in pre (original), no post (regen) match -> real miss
            "added_count": added,      # in post (regen), no pre (original) match -> unexpected extra
            "examples": {ch: examples[dxf][ch] for ch in ("removed", "modified", "added")
                        if examples[dxf].get(ch)},
        })
    totals = {
        k: sum(r[k] for r in rows)
        for k in ("regen_attempted_count", "diff0_count", "modified_count", "removed_count", "added_count")
    }
    totals["deferred_count"] = sum(r["deferred_count"] for r in rows)
    totals["attempted_live_count"] = sum(r["attempted_live_count"] for r in rows)
    return {
        "comparison_basis": (diff.get("diagnostics") or {}).get("comparison_basis"),
        "rows": rows,
        "totals": totals,
    }


def record_op_args_from_record(record: Dict[str, Any], fields: Tuple[str, ...]) -> Dict[str, Any]:
    """Generic form of layer_op_args_from_record/dimstyle_op_args_from_record:
    create_<table> op args replicating one census-extracted symbol_tables
    record (name + every key in ``fields`` present on the record). Used by
    build_records_patch/RECORD_TABLE_CLASSES to cover all 7 record-table
    classes (layer/dimstyle/linetype/textstyle/ucs/view/vport) through ONE
    code path instead of a hand-written per-table function each; the two
    named wrappers above are unchanged (existing call sites/tests) and are
    now equivalent special cases of this one."""
    args: Dict[str, Any] = {"name": record.get("name")}
    for k in fields:
        if k in record:
            args[k] = record[k]
    return args


# Every symbol-table record class with a live create_* native write handler
# (patch_ops.NATIVE_WRITE_OP_MAP) AND a record-diff driver in
# op_roundtrip_probe.py -- the table-tier D-class certs' own field lists /
# diff functions, reused verbatim (never reimplemented; see module
# docstring). fields_attr/diff_attr are attribute NAMES (not the values
# themselves), resolved via getattr with a fallback, so a checkout missing
# one constant degrades gracefully (see table_record_diff_reports) instead
# of raising AttributeError at import time.
RECORD_TABLE_CLASSES: Tuple[Dict[str, str], ...] = (
    {"label": "layer", "op_name": "create_layer", "table_key": "layers",
     "fields_attr": "LAYER_RECORD_FIELDS", "diff_attr": "layer_record_diff"},
    {"label": "dimstyle", "op_name": "create_dimstyle", "table_key": "dim_styles",
     "fields_attr": "DIMSTYLE_RECORD_FIELDS", "diff_attr": "dimstyle_record_diff"},
    {"label": "linetype", "op_name": "create_linetype", "table_key": "linetypes",
     "fields_attr": "LINETYPE_RECORD_FIELDS", "diff_attr": "linetype_record_diff"},
    {"label": "textstyle", "op_name": "create_textstyle", "table_key": "text_styles",
     "fields_attr": "TEXTSTYLE_RECORD_FIELDS", "diff_attr": "textstyle_record_diff"},
    {"label": "ucs", "op_name": "create_ucs", "table_key": "ucs",
     "fields_attr": "UCS_RECORD_FIELDS", "diff_attr": "ucs_record_diff"},
    {"label": "view", "op_name": "create_view", "table_key": "views",
     "fields_attr": "VIEW_RECORD_FIELDS", "diff_attr": "view_record_diff"},
    {"label": "vport", "op_name": "create_vport", "table_key": "viewports",
     "fields_attr": "VPORT_RECORD_FIELDS", "diff_attr": "vport_record_diff"},
)


# --------------------------------------------------------------------------- #
# 3.6 vport "*Active" managed-field policy (closeout follow-up F-a): AutoCAD
#     reserves the "*Active" viewport record and recomputes several of its
#     fields on its own open/regen/save cycle, independent of anything a
#     create_vport op asked for -- build_log.md's #130 note already flagged
#     this ("plausibly *Active is a reserved, AutoCAD-managed record that
#     create_vport cannot fully override, not a bug in this batch's own diff
#     machinery"), but left it as an unannotated, informational mismatch.
#
#     Evidence for EXACTLY these 3 fields (not a superset guess): in
#     runs/capstone_composed_20260706 (the reference run that note was
#     written against), records_regen_summary.json's applied batch is 221
#     ops and regen/patch.json contains ZERO vport-touching operations (no
#     "vport"/"viewport" substring anywhere in that patch's op list) -- so
#     nothing THIS run issued could have written to the vport table at all.
#     Its table_record_diffs.json "vport" row for name="*Active" still
#     reports record_diff=["center", "height", "width"] against the
#     census's captured values. Since no vport op ran, those 3 fields can
#     only have moved via AutoCAD's own regen/save of the reserved active
#     viewport -- not evidence for any OTHER field, and not evidence for
#     any OTHER (non-"*Active") viewport record.
# --------------------------------------------------------------------------- #

VPORT_ACTIVE_RECORD_NAME = "*Active"
VPORT_MANAGED_FIELDS: Tuple[str, ...] = ("center", "height", "width")


def classify_vport_managed_drift(row: Dict[str, Any]) -> Dict[str, Any]:
    """Split a vport record_diff_report() row into real diff vs
    VPORT_MANAGED_FIELDS drift, for the reserved "*Active" record ONLY.

    Returns a NEW row dict:
      - "record_diff": the input row's record_diff with any
        VPORT_MANAGED_FIELDS names removed -- so an "*Active" row whose
        ONLY differences are managed fields ends up record_diff=[] (a real
        pass, counted in zero_diff_count, never landing in the "diffs"
        list), while any OTHER differing field still fails as before.
      - "managed_field_drift": always present (empty list if nothing
        managed drifted) -- {field, expected, actual} for every managed
        field that differed, so the drift is annotated in the report JSON
        rather than silently dropped.

    A row for any name other than "*Active" is returned with
    managed_field_drift=[] and record_diff UNCHANGED -- this policy never
    excludes a non-"*Active" vport record, even if it happens to differ on
    a field that shares a name with VPORT_MANAGED_FIELDS. No blanket vport
    exclusion.
    """
    record_diff = list(row.get("record_diff") or [])
    if row.get("name") != VPORT_ACTIVE_RECORD_NAME:
        return dict(row, managed_field_drift=[])
    managed = [f for f in record_diff if f in VPORT_MANAGED_FIELDS]
    real = [f for f in record_diff if f not in VPORT_MANAGED_FIELDS]
    expected = row.get("expected") or {}
    actual = row.get("actual") or {}
    drift = [{"field": f, "expected": expected.get(f), "actual": (actual or {}).get(f)}
             for f in managed]
    return dict(row, record_diff=real, managed_field_drift=drift)


def build_records_patch(census_ir: Dict[str, Any], target_dwg: Dict[str, Any], patch_id: str, *,
                        op_roundtrip_probe_mod=None, table_classes: Tuple[Dict[str, str], ...] = RECORD_TABLE_CLASSES,
                        per_table_limit: Optional[int] = None
                        ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """A SINGLE cad_patch.v1 whose operations[] replicate every requested
    symbol_tables record across every RECORD_TABLE_CLASSES entry (one
    create_* op per named record, via record_op_args_from_record) -- the
    table-tier sibling of ir_to_patch.build_patch_from_ir's entity batching
    (one patch, one apply_staged call; patch_engine chains each op's
    mutated staged copy into the next, same as run_regen_batch).

    Records with no "name" (dwg_graph_ir.v1's table join key; every create_*
    op here requires one) are counted in meta["skipped_unnamed"][label]
    rather than silently shrinking the op count. meta["per_table_requested"]
    [label] is the op count actually built for that table -- the
    "requested" side of this batch's own gate arithmetic (see
    regen_gate_report).
    """
    op_roundtrip_probe_mod = op_roundtrip_probe_mod or importlib.import_module("op_roundtrip_probe")
    operations: List[Dict[str, Any]] = []
    postconditions: List[Dict[str, Any]] = []
    skipped_unnamed: Dict[str, int] = {}
    per_table_requested: Dict[str, int] = {}
    for cls in table_classes:
        records = [r for r in ((census_ir.get("symbol_tables") or {}).get(cls["table_key"]) or [])
                  if isinstance(r, dict)]
        fields = getattr(op_roundtrip_probe_mod, cls["fields_attr"], ())
        count = 0
        for rec in records:
            if per_table_limit is not None and count >= per_table_limit:
                break
            if not rec.get("name"):
                skipped_unnamed[cls["label"]] = skipped_unnamed.get(cls["label"], 0) + 1
                continue
            args = record_op_args_from_record(rec, fields)
            operations.append({"step_id": "%s_%d" % (cls["label"], count),
                              "operation": cls["op_name"], "args": args})
            # Same "<table>_exists" subject op_roundtrip_probe._build_patch's
            # single-record P-gate patches already declare (see e.g.
            # create_layer's postconditions=[{"subject": "layer_exists", ...}]
            # a few lines up in that module) -- one entry per op here, not a
            # NEW convention. An earlier version of this function shipped
            # postconditions=[] unconditionally, reasoning (correctly) that
            # classify_patch_risk's missing-postconditions bump only applies
            # to mutation-of-existing ops (delete_entity/move_entity/
            # set_layer), which these 7 create_* ops are not -- but missed
            # patch_engine.require_validation, a SEPARATE, unconditional guard
            # ("ops and not postconds" -> blocked) that fired on every
            # non-empty batch regardless of op type. Caught live: a bounded
            # --with-records E2E run came back apply_status="blocked"
            # ("guards failed: require_validation") on this exact patch; see
            # build_log.md.
            postconditions.append({"subject": "%s_exists" % cls["label"], "op": "exists", "value": args["name"]})
            count += 1
        per_table_requested[cls["label"]] = count
    patch = {
        "schema": "ariadne.cad_patch.v1",
        "patch_id": patch_id,
        "title": "table-record regen from census IR (%d ops)" % len(operations),
        "source_agent": "full_roundtrip_capstone",
        "target_dwg": target_dwg,
        "operations": operations,
        "postconditions": postconditions,
        "policy": {"staged_copy": True, "write_mode": "write_copy"},
    }
    return patch, {"skipped_unnamed": skipped_unnamed, "per_table_requested": per_table_requested}


def table_record_diff_reports(census_ir: Dict[str, Any], post_ir: Optional[Dict[str, Any]], *,
                              op_roundtrip_probe_mod=None,
                              table_classes: Tuple[Dict[str, str], ...] = RECORD_TABLE_CLASSES,
                              per_table_limit: Optional[int] = None,
                              unavailable_reason: Optional[str] = None) -> Dict[str, Any]:
    """TRUE post-regen record-diff for every RECORD_TABLE_CLASSES entry:
    reuses record_diff_report() (already generic over table_key/fields/
    diff_fn -- never reimplemented) against ``post_ir``, the re-extracted
    IR from AFTER build_records_patch's ops actually ran -- instead of
    diffing census_ir against itself (Closeout #130: the old
    layer_record_report compared the census's OWN layer records to the
    census IR they came from, which is zero-diff by construction and
    proves nothing about whether create_layer actually reproduces a
    record; see build_log.md).

    If ``post_ir`` is None (the records regen batch never reached
    post-inspect -- apply_staged returned a non-"ok" status before writing
    post/dwg_graph_ir.json), every table's report says so explicitly via
    "structural_note" instead of silently emitting a zero-record report
    that LOOKS like a real all-matched diff.
    """
    op_roundtrip_probe_mod = op_roundtrip_probe_mod or importlib.import_module("op_roundtrip_probe")
    reports: Dict[str, Any] = {}
    for cls in table_classes:
        records = [r for r in ((census_ir.get("symbol_tables") or {}).get(cls["table_key"]) or [])
                  if isinstance(r, dict) and r.get("name")]
        if per_table_limit is not None:
            records = records[:per_table_limit]
        if post_ir is None:
            reports[cls["label"]] = {
                "label": cls["label"], "table_key": cls["table_key"],
                "records_compared": 0, "zero_diff_count": 0, "rows": [], "diffs": [],
                "structural_note": (unavailable_reason or
                    "post-regen IR unavailable -- the records regen batch did not reach "
                    "post-inspect, so no post-regen record-diff could be computed for this "
                    "table (this is NOT a zero-diff pass; see records_regen.apply_status)"),
            }
            continue
        fields = getattr(op_roundtrip_probe_mod, cls["fields_attr"], ())
        # `or`, not getattr(..., default=) -- a getattr default expression is
        # evaluated eagerly (before the call), so a hardcoded
        # op_roundtrip_probe_mod.layer_record_diff default would raise
        # AttributeError on any module that lacks THAT name, even when
        # cls["diff_attr"] itself resolves fine (caught by this module's own
        # unit tests against a non-layer/dimstyle fake table class). `or`
        # short-circuits: the fallback is only touched if the primary lookup
        # is falsy/missing.
        diff_fn = (getattr(op_roundtrip_probe_mod, cls["diff_attr"], None)
                  or getattr(op_roundtrip_probe_mod, "layer_record_diff", None))
        base = record_diff_report(cls["label"], records, post_ir, table_key=cls["table_key"],
                                  fields=fields, diff_fn=diff_fn)
        rows = base["rows"]
        if cls["label"] == "vport":
            # See "3.6 vport *Active managed-field policy" above -- reclassify
            # AutoCAD-managed drift on the reserved "*Active" record before
            # this table's zero_diff_count/diffs are derived, so a
            # managed-only mismatch counts as a pass instead of a failure.
            rows = [classify_vport_managed_drift(row) for row in rows]
        zero_diff_count = sum(1 for row in rows if not row["record_diff"])
        reports[cls["label"]] = {
            "label": base["label"], "table_key": base["table_key"],
            "records_compared": base["record_count"], "zero_diff_count": zero_diff_count,
            "rows": rows,
            "diffs": [row for row in rows if row["record_diff"]],
            "structural_note": (None if records else
                "0 named records in census for this table -- vacuously 0 compared, "
                "not evidence of a passing roundtrip"),
        }
    return reports


# --------------------------------------------------------------------------- #
# 4.5 fail-loud regen gate (Closeout #129a): apply_staged's own status=="ok"
#     means every RESOLVABLE op in a batch applied cleanly -- it does NOT
#     mean every op ir_to_patch/build_records_patch BUILT for the batch ran.
#     Ops with no NATIVE_WRITE_OP_MAP entry (e.g. ir_to_patch's
#     "insert_block", which no family's write handler accepts -- see
#     resolvable_ops_report's own docstring) are silently bucketed into
#     apply_result["deferred_ops"] and never move apply_status off "ok".
#     Before this fix, main() printed status="ok" whenever the entity/
#     records batch reached this far, REGARDLESS of dropped ops -- a real
#     reference run (runs/capstone_final_20260706_062040) requested 14 ops,
#     applied 12, and reported apply_status="ok" with no top-level signal
#     that 2 were silently skipped. These two functions make that
#     requested-vs-applied arithmetic explicit and un-skippable.
# --------------------------------------------------------------------------- #

def regen_gate_report(op_count: int, apply_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Reconcile ``op_count`` (ops REQUESTED this batch -- e.g.
    len(patch["operations"])) against ``apply_result`` (patch_engine.
    apply_staged's own return envelope) and report whether every requested
    op actually applied.

    applied_count is read from apply_result["op_count_applied"] when present
    (only populated on the FINAL status=="ok" envelope -- see patch_engine.
    apply_staged's last _finish(_result_envelope("ok", ..., extra={...
    "op_count_applied": len(applied_ok) ...}))); apply_result["applied_ops"]
    length is the fallback (present on that same "ok" envelope, and absent
    -- so applied_count falls to 0 -- on every earlier blocked/partial/
    not_implemented/unavailable return, which is the conservative, honest
    reading: no evidence any op ran).

    dropped_ops is built primarily from apply_result["deferred_ops"] (the
    SAME NATIVE_WRITE_OP_MAP check patch_engine._resolve_native_write_ops
    already performs internally -- reused, not re-derived). If applied_count
    + len(deferred_ops) still falls short of op_count (e.g. a mid-batch
    apply[n] step failed and stopped the loop early -- a case deferred_ops
    alone does not cover), one synthetic entry accounts for the remainder,
    so the arithmetic always reconciles to op_count; never silently smaller.

    gate_status:
      "ok"            -- apply_result status=="ok" and applied_count==op_count.
      "ok_with_drops" -- apply_result status=="ok" but applied_count<op_count
                         (patch_engine itself is satisfied; this batch's own
                         requested-vs-applied count is not 1:1 -- exactly the
                         permissiveness this gate exists to catch).
      <status>        -- any apply_result status other than "ok" passes
                         through unchanged (blocked/partial/not_implemented/
                         unavailable are already fail-loud on their own; this
                         function only refuses to launder them back into "ok"
                         the way main() used to with its unconditional
                         summary["status"] = "ok").

    NOTE (deliberately NOT a gate signal): patch_engine's journal.json
    carries "operations[i].operation '<op>' is not a declared op [...]"
    schema warnings from validate_patch_schema against patch_engine.
    DECLARED_OPS -- a small legacy op-name allowlist wholly disconnected
    from NATIVE_WRITE_OP_MAP. In the reference capstone run
    (runs/capstone_final_20260706_062040/regen/journal.json) this warning
    fires for create_mtext/create_arc/create_circle too, all of which
    applied successfully (they're in applied_ops) -- wiring that warning
    into this gate would flag successful ops as drops (false positives on
    every run), so it is intentionally excluded. Flagged here for a
    separate schema/DECLARED_OPS cleanup, not blended into this gate.
    """
    apply_result = apply_result or {}
    applied_ops = apply_result.get("applied_ops")
    op_count_applied = apply_result.get("op_count_applied")
    if op_count_applied is not None:
        applied_count = op_count_applied
    elif isinstance(applied_ops, list):
        applied_count = len(applied_ops)
    else:
        applied_count = 0

    deferred_ops = [d for d in (apply_result.get("deferred_ops") or []) if isinstance(d, dict)]
    dropped_ops: List[Dict[str, Any]] = [
        {"index": d.get("index"), "operation": d.get("operation"), "reason": d.get("reason")}
        for d in deferred_ops
    ]
    unexplained = op_count - (applied_count + len(dropped_ops))
    if unexplained > 0:
        dropped_ops.append({
            "index": None, "operation": None,
            "reason": ("%d op(s) unaccounted for by applied_count + deferred_ops "
                      "(apply_result status=%r, reason=%r)"
                      % (unexplained, apply_result.get("status"), apply_result.get("reason"))),
        })

    apply_status = apply_result.get("status")
    has_drops = bool(dropped_ops)
    if apply_status == "ok":
        gate_status = "ok_with_drops" if has_drops else "ok"
    else:
        gate_status = apply_status or "unknown"

    return {
        "requested_count": op_count,
        "applied_count": applied_count,
        "dropped_count": len(dropped_ops),
        "dropped_ops": dropped_ops,
        "apply_status": apply_status,
        "gate_status": gate_status,
        "ok": gate_status == "ok",
    }


_GATE_OK_STATUSES = ("ok", "ok_with_drops")


def combine_gate_statuses(statuses: List[str]) -> str:
    """Roll up multiple regen_gate_report()["gate_status"] values (the
    entity batch + any --with-records table batch) into ONE overall
    verdict: "ok" iff every component is "ok"; "ok_with_drops" iff every
    component is "ok" or "ok_with_drops" (at least one drop, nothing
    worse); otherwise the first status that is neither -- e.g. a batch
    that came back "blocked" outranks a sibling "ok_with_drops" (blocked
    can mean the original-unchanged invariant failed; patch_engine.
    apply_staged step 10 -- strictly more severe than a merely-deferred
    op). Empty input is vacuously "ok" (nothing ran, nothing dropped)."""
    if not statuses:
        return "ok"
    if all(s in _GATE_OK_STATUSES for s in statuses):
        return "ok_with_drops" if any(s == "ok_with_drops" for s in statuses) else "ok"
    for s in statuses:
        if s not in _GATE_OK_STATUSES:
            return s
    return "ok_with_drops"  # unreachable, defensive


def resolvable_ops_report(patch: Dict[str, Any], patch_ops_mod=None) -> Dict[str, Any]:
    """For a built cad_patch.v1, split its operations into those whose
    "operation" id has a live entry in patch_ops.NATIVE_WRITE_OP_MAP
    (patch_engine would actually apply them) vs those that do not.

    patch_engine.apply_staged's own _resolve_native_write_ops silently
    buckets an unresolvable op into ITS OWN deferred_ops -- catching that
    HERE, before spending an accoreconsole launch, is free and prevents
    miscounting "ops ir_to_patch built" as "ops that can possibly apply"
    (e.g. blocks.py's ir_op_for emits an "insert_block" operation id that no
    family's WRITE_OP_MAP maps to any native handler -- entities.py's own
    wired path is "create_blockref" -> "write.entity.blockref", which
    ir_to_patch never emits -- so every block_reference entity ir_to_patch
    "builds an op for" is unresolvable today; see build_log.md)."""
    patch_ops_mod = patch_ops_mod or importlib.import_module("patch_ops")
    live_map = patch_ops_mod.NATIVE_WRITE_OP_MAP
    resolvable, unresolvable = [], []
    for op in patch.get("operations") or []:
        (resolvable if op.get("operation") in live_map else unresolvable).append(op)
    return {
        "resolvable_count": len(resolvable),
        "unresolvable_count": len(unresolvable),
        "unresolvable_op_ids": sorted({op.get("operation") for op in unresolvable}),
    }


# --------------------------------------------------------------------------- #
# 5. live orchestration -- needs a real AutoCAD runtime. Every function above
#    this line is pure and independently unit-testable without one.
# --------------------------------------------------------------------------- #

def run_census(staged_path: str, original_path: str, run_dir: str, *,
               run_job_mod=None, ir_builder_mod=None, patch_engine_mod=None) -> Dict[str, Any]:
    """inspect.database.graph on ``staged_path`` -> a native_full IR, reusing
    patch_engine._native_full_ir (the SAME helper apply_staged's own pre/
    post-inspect steps use), so census IRs are shaped identically to regen's
    pre/post IRs (same source_meta/diagnostics conventions)."""
    run_job_mod = run_job_mod or importlib.import_module("run_job")
    ir_builder_mod = ir_builder_mod or importlib.import_module("ir_builder")
    patch_engine_mod = patch_engine_mod or importlib.import_module("patch_engine")
    run_res = run_job_mod.run_router_cad_job(
        staged_path, run_dir, "inspect.database.graph", write_mode="read")
    ir_path = os.path.join(run_dir, "dwg_graph_ir.json")
    return patch_engine_mod._native_full_ir(
        ir_builder_mod, run_res, staged_path, original_path, ir_path, "census")


def census_extraction_vacuous(census_ir: Dict[str, Any]) -> bool:
    """True when an extraction returned a structurally-valid but EMPTY graph
    (0 entities AND 0 block definitions)."""
    return (not (census_ir.get("entities") or [])
            and not (census_ir.get("block_definitions") or []))


def run_census_with_vacuous_retry(staged_path: str, original_path: str, out_dir: str,
                                  *, retries: int = 2, pause_seconds: float = 10.0,
                                  allow_empty: bool = False, census_fn=None):
    """run_census plus a fail-closed vacuous-extraction guard.

    Measured failure (runs/e2e_1dwg_R3_full_20260708, 2026-07-08): an
    accoreconsole double-script race executed ARIADNE_NATIVE_JOB after the
    first script instance's QUIT had discarded the drawing, so the native job
    inspected a blank default document and reported 0 entities / 0 block
    definitions with empty errors -- structurally valid, semantically vacuous
    (native modelspace count null, coverage match vacuously true). A vacuous
    extraction is retried (the race is transient) and, if it persists, the
    census FAILS (VACUOUS != PASS) unless allow_empty declares the drawing
    genuinely empty.

    Returns (census, census_ir_or_None, attempts, vacuous_final).
    """
    census_fn = census_fn or run_census
    attempts = 0
    census: Dict[str, Any] = {}
    census_ir = None
    while attempts <= retries:
        attempts += 1
        census_dir = os.path.join(
            out_dir, "census" if attempts == 1 else "census_retry%d" % (attempts - 1))
        census = census_fn(staged_path, original_path, census_dir)
        if not census.get("ok"):
            return census, None, attempts, False
        census_ir = json.load(open(census["ir_path"], encoding="utf-8-sig"))
        if allow_empty or not census_extraction_vacuous(census_ir):
            return census, census_ir, attempts, False
        if attempts <= retries:
            time.sleep(pause_seconds)
    return census, census_ir, attempts, True


def run_records_batch(census_ir: Dict[str, Any], blank_seed_path: str, run_dir: str,
                      patch_id: str, *, per_table_limit: Optional[int] = None,
                      table_classes: Tuple[Dict[str, str], ...] = RECORD_TABLE_CLASSES,
                      op_roundtrip_probe_mod=None, patch_engine_mod=None) -> Dict[str, Any]:
    """Table-tier sibling of run_regen_batch: build ONE cad_patch.v1 via
    build_records_patch (7 record classes: layer/dimstyle/linetype/
    textstyle/ucs/view/vport) and apply it in ONE patch_engine.apply_staged
    call against a copy of ``blank_seed_path`` -- independent of, and run
    into its own ``run_dir`` alongside, the entity batch (run_regen_batch),
    so a --with-records run always has its own separate pre/post IR pair
    for table_record_diff_reports to compare against (Closeout #130)."""
    op_roundtrip_probe_mod = op_roundtrip_probe_mod or importlib.import_module("op_roundtrip_probe")
    patch_engine_mod = patch_engine_mod or importlib.import_module("patch_engine")
    target_dwg = {
        "original_path": os.path.abspath(blank_seed_path),
        "staged_path": os.path.join(run_dir, "staged_input.dwg"),
    }
    patch, build_meta = build_records_patch(
        census_ir, target_dwg, patch_id, op_roundtrip_probe_mod=op_roundtrip_probe_mod,
        table_classes=table_classes, per_table_limit=per_table_limit)
    ops_report = resolvable_ops_report(patch)
    t0 = time.time()
    result = patch_engine_mod.apply_staged(patch, blank_seed_path, run_dir)
    elapsed = time.time() - t0
    op_count = len(patch.get("operations") or [])
    return {
        "patch": patch, "build_meta": build_meta, "resolvable_ops": ops_report,
        "apply_result": result, "op_count": op_count, "elapsed_seconds": elapsed,
        "seconds_per_op": (elapsed / op_count) if op_count else None,
    }


def run_regen_batch(filtered_ir: Dict[str, Any], blank_seed_path: str, run_dir: str,
                    patch_id: str, *, batch_size: Optional[int] = None,
                    ir_to_patch_mod=None, patch_engine_mod=None
                    ) -> Dict[str, Any]:
    """Build ONE cad_patch.v1 from ``filtered_ir`` (via the existing, unedited
    ir_to_patch.build_patch_from_ir) and apply it in ONE patch_engine.
    apply_staged call against a copy of ``blank_seed_path``.

    "Batch the ops" means one staged-write session carrying every op in this
    filtered_ir, not one apply_staged call per entity -- patch_engine still
    launches one accoreconsole invocation PER OP internally (chaining each
    op's mutated staged copy into the next), so op_count is the real
    throughput unit; see the elapsed/seconds_per_op fields and build_log.md's
    throughput section for the measured floor and full-scale extrapolation.
    """
    ir_to_patch_mod = ir_to_patch_mod or importlib.import_module("ir_to_patch")
    patch_engine_mod = patch_engine_mod or importlib.import_module("patch_engine")
    target_dwg = {
        "original_path": os.path.abspath(blank_seed_path),
        "staged_path": os.path.join(run_dir, "staged_input.dwg"),
    }
    patch, deferred = ir_to_patch_mod.build_patch_from_ir(filtered_ir, target_dwg, patch_id)
    ops_report = resolvable_ops_report(patch)
    t0 = time.time()
    result = patch_engine_mod.apply_staged(
        patch, blank_seed_path, run_dir, batch_size=batch_size)
    elapsed = time.time() - t0
    op_count = len(patch.get("operations") or [])
    return {
        "patch": patch, "deferred": deferred, "resolvable_ops": ops_report,
        "apply_result": result, "op_count": op_count, "elapsed_seconds": elapsed,
        "seconds_per_op": (elapsed / op_count) if op_count else None,
    }


def build_regen_summary(batch: Dict[str, Any], gate: Dict[str, Any]) -> Dict[str, Any]:
    apply_result = (batch or {}).get("apply_result") or {}
    return {
        "op_count": batch["op_count"], "deferred_count": len(batch["deferred"]),
        "resolvable_ops": batch["resolvable_ops"],
        "elapsed_seconds": batch["elapsed_seconds"], "seconds_per_op": batch["seconds_per_op"],
        "apply_status": apply_result.get("status"),
        "apply_reason": apply_result.get("reason"),
        "batch_size": apply_result.get("batch_size"),
        "batch_count": apply_result.get("batch_count"),
        "gate": gate,
    }


def pre_ir_path(run_dir: str) -> str:
    """apply_staged's own stable output layout for the pre-mutation IR
    (patch_engine.py apply_staged step 5: pre_dir = out_dir/pre,
    pre_ir_path = pre_dir/dwg_graph_ir.json)."""
    return os.path.join(run_dir, "pre", "dwg_graph_ir.json")


def post_ir_path(run_dir: str) -> str:
    """apply_staged's own stable output layout for the post-mutation IR
    (patch_engine.py apply_staged step 7: post_dir = out_dir/post,
    post_ir_path = post_dir/dwg_graph_ir.json) -- kept as one named
    function so this convention is declared once, not re-typed at each
    call site."""
    return os.path.join(run_dir, "post", "dwg_graph_ir.json")


def isolate_regenerated_entities(pre_ir: Dict[str, Any], post_ir: Dict[str, Any], *,
                                 op_roundtrip_probe_mod=None, cad_diff_mod=None) -> Dict[str, Any]:
    """The IR-shaped subset of ``post_ir`` whose handle is NEW relative to
    ``pre_ir`` -- reuses op_roundtrip_probe.added_entities_ir (a handle-basis
    diff, already exercised by every WAVE cert's own P-gate) so the regen
    target does NOT need to be a blank seed: this isolates exactly what THIS
    batch created even when regenerating directly onto a staged copy of the
    full production drawing (pre_ir already has 21,747 entities; only the
    NEW handles this batch's ops produced are returned). If the target
    happens to be genuinely blank, pre_ir has 0 entities and every post_ir
    entity is trivially "new" -- the same call is correct in both cases."""
    op_roundtrip_probe_mod = op_roundtrip_probe_mod or importlib.import_module("op_roundtrip_probe")
    return op_roundtrip_probe_mod.added_entities_ir(pre_ir, post_ir, cad_diff_mod=cad_diff_mod)


def ensure_blank_seed(seed_path: str, run_dir: str, *, mint_blank_seed_mod=None) -> Dict[str, Any]:
    """Mint ``seed_path`` via tools/mint_blank_seed.py if it does not already
    exist locally (the .dwg is a generated/gitignored artifact -- a fresh
    ``git worktree add`` never checks it out, unlike the tracked
    tools/mint_blank_seed.py script that produces it).

    OPTIONAL: a truly-blank seed gives the cleanest regen target, but
    isolate_regenerated_entities() (handle-basis added_entities_ir) makes a
    non-blank target (e.g. the production drawing's own staged copy) an
    equally valid regen target -- see resolve_regen_target(). This function
    is only called when the caller explicitly asked for a blank seed and one
    is not already present."""
    if os.path.isfile(seed_path):
        return {"minted": False, "seed_path": seed_path, "reason": "already present"}
    mint_blank_seed_mod = mint_blank_seed_mod or importlib.import_module("mint_blank_seed")
    mint_run_dir = os.path.join(run_dir, "mint_blank_seed")
    result = mint_blank_seed_mod.mint_blank_seed(
        template=None, output=__import__("pathlib").Path(seed_path),
        run_dir=__import__("pathlib").Path(mint_run_dir))
    return {"minted": True, "seed_path": seed_path, "mint_result": result}


def resolve_regen_target(seed_path: Optional[str], fallback_dwg: str) -> Dict[str, Any]:
    """Pick the DWG apply_staged should stage-and-mutate: ``seed_path`` if it
    already exists on disk (a genuinely blank seed -- the cleanest target,
    no isolation math needed since pre_ir is empty by construction), else
    ``fallback_dwg`` (e.g. the production drawing itself -- safe because
    isolate_regenerated_entities() isolates NEW handles regardless of how
    much pre-existing content the target already has). Never mints; see
    ensure_blank_seed for that (a separate, explicit opt-in)."""
    if seed_path and os.path.isfile(seed_path):
        return {"target": seed_path, "used_blank_seed": True}
    return {"target": fallback_dwg, "used_blank_seed": False,
           "reason": "no blank seed on disk; regenerating onto the source drawing's own "
                    "staged copy and isolating new handles instead (isolate_regenerated_entities)"}


# --------------------------------------------------------------------------- #
# 6. CLI
# --------------------------------------------------------------------------- #

def _write_json(path: str, obj: Any) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, default=str)
    return path


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="full_roundtrip_capstone: full-drawing extract -> regen "
                    "(certified classes) -> re-extract -> handle-independent "
                    "multiset diff, on the real lane-A production drawing.")
    ap.add_argument("--dwg", default=DEFAULT_DWG, help="source DWG (read-only; staged internally)")
    ap.add_argument("--compare-path", default=DEFAULT_COMPARE_PATH,
                   help="workitem production file to identity-check --dwg against")
    ap.add_argument("--skip-identity", action="store_true")
    ap.add_argument("--seed", default=DEFAULT_SEED,
                   help="blank-seed target DWG if present on disk (OPTIONAL -- falls back to "
                        "regenerating onto --dwg's own staged copy + isolating new handles "
                        "when absent; see resolve_regen_target/isolate_regenerated_entities)")
    ap.add_argument("--mint-seed-if-missing", action="store_true",
                   help="attempt tools/mint_blank_seed.py if --seed is absent, instead of "
                        "falling back to --dwg as the regen target")
    ap.add_argument("--out-dir", required=True, help="run output directory")
    ap.add_argument("--census-only", action="store_true", help="stop after the census; no regen/diff")
    ap.add_argument("--kinds", default=None, help="comma-separated geometry.kind allowlist for regen")
    ap.add_argument("--limit", type=int, default=None, help="global op cap for this batch")
    ap.add_argument("--per-kind-limit", type=int, default=None, help="per-kind op cap for this batch")
    ap.add_argument("--batch-size", type=int, default=None,
                   help="EXPERIMENTAL flag-gated native batching size for the regen apply_staged call")
    ap.add_argument("--max-def-entities-per-block", type=int, default=None,
                   help="drop block_definitions entries with more def_entities than this "
                        "from the regen input; their INSERTs then defer honestly in "
                        "ir_to_patch ('no block_definitions entry'). Whole-def drop with "
                        "an explicit report -- never a silent truncation")
    ap.add_argument("--with-records", action="store_true",
                   help="also regen+record-diff layer/dimstyle tables (stretch)")
    ap.add_argument("--cross-verify", dest="cross_verify", action=argparse.BooleanOptionalAction, default=True,
                   help="run LibreDWG sidecar verification as a post-write gate (default: on)")
    ap.add_argument("--visual-gate", dest="visual_gate", action=argparse.BooleanOptionalAction, default=True,
                   help="run SVG->raster SSIM visual verification as a post-write gate (default: on)")
    ap.add_argument("--allow-empty-census", action="store_true",
                   help="accept a 0-entity/0-blockdef extraction as census truth. Without "
                        "this flag a vacuous extraction is retried and then FAILS the run "
                        "(fail-closed guard for the accoreconsole blank-document race)")
    return ap


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    summary: Dict[str, Any] = {"out_dir": out_dir}

    if not args.skip_identity:
        identity = check_identity(args.dwg, args.compare_path)
        summary["identity"] = identity
        _write_json(os.path.join(out_dir, "identity.json"), identity)

    patch_engine_mod = importlib.import_module("patch_engine")
    staged = patch_engine_mod.create_staged_copy(args.dwg, os.path.join(out_dir, "census_stage"))
    summary["staged"] = staged
    if not staged.get("ok"):
        summary["status"] = "blocked"
        summary["reason"] = staged.get("reason")
        _write_json(os.path.join(out_dir, "summary.json"), summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
        return 2

    census, census_ir, census_attempts, census_vacuous = run_census_with_vacuous_retry(
        staged["staged_path"], staged["original_path"], out_dir,
        allow_empty=args.allow_empty_census)
    summary["census_ok"] = bool(census.get("ok")) and not census_vacuous
    summary["census_attempts"] = census_attempts
    if not census.get("ok") or census_vacuous:
        summary["status"] = "blocked" if census_vacuous else "partial"
        summary["reason"] = (
            ("census extraction vacuous after %d attempt(s): 0 entities and 0 "
             "block definitions (VACUOUS != PASS; pass --allow-empty-census "
             "only for a genuinely empty drawing)" % census_attempts)
            if census_vacuous else census.get("reason"))
        _write_json(os.path.join(out_dir, "summary.json"), summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
        return 2

    report = census_report(census_ir)
    summary["census_report"] = report
    _write_json(os.path.join(out_dir, "census_report.json"), report)

    original_sha_after_census = sha256_file(args.dwg)
    summary["original_unchanged_after_census"] = (
        original_sha_after_census == (summary.get("identity") or {}).get("sha256_a")
        if not args.skip_identity else None)

    if args.census_only:
        summary["status"] = "ok"
        _write_json(os.path.join(out_dir, "summary.json"), summary)
        print(json.dumps({k: v for k, v in summary.items() if k != "census_report"},
                         ensure_ascii=False, indent=2, default=str))
        return 0

    kinds = set(args.kinds.split(",")) if args.kinds else None
    filtered = filter_ir_to_certified(census_ir, kinds=kinds, limit=args.limit,
                                      per_kind_limit=args.per_kind_limit)
    summary["filtered_entity_count"] = len(filtered.get("entities") or [])

    if args.max_def_entities_per_block is not None:
        filtered, dropped_defs = apply_def_entity_budget(
            filtered, args.max_def_entities_per_block)
        summary["def_entity_budget"] = {
            "max_def_entities_per_block": args.max_def_entities_per_block,
            "dropped_block_definitions": dropped_defs,
        }

    if args.mint_seed_if_missing and not os.path.isfile(args.seed):
        seed_status = ensure_blank_seed(args.seed, out_dir)
        summary["seed_status"] = {k: v for k, v in seed_status.items() if k != "mint_result"}
        summary["mint_result"] = seed_status.get("mint_result")
    regen_target = resolve_regen_target(args.seed, args.dwg)
    summary["regen_target"] = regen_target

    regen_dir = os.path.join(out_dir, "regen")
    batch = run_regen_batch(
        filtered, regen_target["target"], regen_dir, "full_roundtrip_capstone/batch",
        batch_size=args.batch_size)
    entity_gate = regen_gate_report(batch["op_count"], batch["apply_result"])
    summary["regen"] = build_regen_summary(batch, entity_gate)
    _write_json(os.path.join(out_dir, "regen_summary.json"), summary["regen"])
    _write_json(os.path.join(out_dir, "deferred.json"), batch["deferred"])
    gate_statuses = [entity_gate["gate_status"]]

    pre_path, post_path = pre_ir_path(regen_dir), post_ir_path(regen_dir)
    records_gate = {"dropped_ops": []}
    if os.path.isfile(pre_path) and os.path.isfile(post_path):
        cad_diff_mod = importlib.import_module("cad_diff")
        pre_ir = json.load(open(pre_path, encoding="utf-8-sig"))
        post_ir = json.load(open(post_path, encoding="utf-8-sig"))
        # Isolate what THIS batch actually created (handle-basis) before the
        # geometry-basis multiset compare -- required whenever regen_target
        # is not a blank seed (its pre_ir already carries the full drawing),
        # and harmless (a no-op re-listing) when it is.
        regenerated_ir = isolate_regenerated_entities(pre_ir, post_ir, cad_diff_mod=cad_diff_mod)
        _write_json(os.path.join(out_dir, "regenerated_only_ir.json"), regenerated_ir)
        diff = cad_diff_mod.compute_diff(filtered, regenerated_ir, comparison_basis="geometry",
                                         diff_scope="modelspace_entities_only")
        _write_json(os.path.join(out_dir, "geometry_diff.json"), diff)
        verdict = per_kind_verdict(filtered, diff, deferred=batch["deferred"])
        summary["verdict"] = verdict
        _write_json(os.path.join(out_dir, "verdict.json"), verdict)
        if args.cross_verify:
            cross_verify_mod = importlib.import_module("cross_verify")
            cross_verify_result = cross_verify_mod.cross_verify_dwg(
                os.path.join(regen_dir, "staged_output.dwg"),
                ir_path=post_path,
                out_dir=os.path.join(out_dir, "cross_verify_regen"),
            )
            summary["regen"]["cross_verify"] = cross_verify_result
            gate_statuses.append(cross_verify_result["status"])
        if args.visual_gate:
            visual_gate_mod = importlib.import_module("visual_gate")
            visual_gate_result = visual_gate_mod.visual_gate_from_ir_docs(
                filtered,
                regenerated_ir,
                diff_doc=diff,
                out_dir=os.path.join(out_dir, "visual_gate_regen"),
            )
            summary["regen"]["visual_gate"] = visual_gate_result
            gate_statuses.append(visual_gate_result["status"])
    else:
        summary["verdict"] = None
        summary["verdict_skipped_reason"] = (
            "missing pre/post IR (pre=%s post=%s) -- apply_staged did not reach post-inspect"
            % (os.path.isfile(pre_path), os.path.isfile(post_path)))

    if args.with_records:
        # Closeout #130: a REAL post-regen table-record diff, not the old
        # layer_record_report self-check (which compared census_ir's own
        # layer records to the census IR they came from -- zero-diff by
        # construction, proves nothing). run_records_batch actually applies
        # a create_layer/create_dimstyle/.../create_vport patch (7 table
        # classes) to its own staged copy of regen_target["target"]; the
        # diff below is against THAT batch's re-extracted post_ir.
        records_dir = os.path.join(out_dir, "regen_records")
        records_batch = run_records_batch(
            census_ir, regen_target["target"], records_dir,
            "full_roundtrip_capstone/records_batch", per_table_limit=args.per_kind_limit)
        records_gate = regen_gate_report(records_batch["op_count"], records_batch["apply_result"])
        summary["records_regen"] = {
            "op_count": records_batch["op_count"],
            "skipped_unnamed": records_batch["build_meta"]["skipped_unnamed"],
            "per_table_requested": records_batch["build_meta"]["per_table_requested"],
            "resolvable_ops": records_batch["resolvable_ops"],
            "elapsed_seconds": records_batch["elapsed_seconds"],
            "seconds_per_op": records_batch["seconds_per_op"],
            "apply_status": (records_batch["apply_result"] or {}).get("status"),
            "apply_reason": (records_batch["apply_result"] or {}).get("reason"),
            "gate": records_gate,
        }
        _write_json(os.path.join(out_dir, "records_regen_summary.json"), summary["records_regen"])
        gate_statuses.append(records_gate["gate_status"])

        records_post_path = post_ir_path(records_dir)
        records_post_ir = (
            json.load(open(records_post_path, encoding="utf-8-sig"))
            if os.path.isfile(records_post_path) else None
        )
        table_diffs = table_record_diff_reports(
            census_ir, records_post_ir, per_table_limit=args.per_kind_limit,
            unavailable_reason=(
                None if records_post_ir is not None else
                "records regen batch apply_status=%r (reason=%r) -- never reached post-inspect"
                % (summary["records_regen"]["apply_status"], summary["records_regen"]["apply_reason"])
            ))
        summary["table_record_diffs"] = table_diffs
        _write_json(os.path.join(out_dir, "table_record_diffs.json"), table_diffs)
        if args.cross_verify and records_post_ir is not None:
            cross_verify_mod = importlib.import_module("cross_verify")
            cross_verify_result = cross_verify_mod.cross_verify_dwg(
                os.path.join(records_dir, "staged_output.dwg"),
                ir_path=records_post_path,
                out_dir=os.path.join(out_dir, "cross_verify_records"),
            )
            summary["records_regen"]["cross_verify"] = cross_verify_result
            gate_statuses.append(cross_verify_result["status"])
        if args.visual_gate and records_post_ir is not None:
            visual_gate_mod = importlib.import_module("visual_gate")
            visual_gate_result = visual_gate_mod.visual_gate_from_ir_paths(
                pre_ir_path(records_dir),
                records_post_path,
                diff_path=None,
                out_dir=os.path.join(out_dir, "visual_gate_records"),
            )
            summary["records_regen"]["visual_gate"] = visual_gate_result
            gate_statuses.append(visual_gate_result["status"])

    overall_gate = combine_gate_statuses(gate_statuses)
    summary["status"] = overall_gate
    summary["dropped_ops"] = (
        [dict(d, batch="entity") for d in entity_gate["dropped_ops"]] +
        ([dict(d, batch="records") for d in records_gate["dropped_ops"]] if args.with_records else [])
    )
    _write_json(os.path.join(out_dir, "summary.json"), summary)
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("census_report",)}, ensure_ascii=False, indent=2, default=str))
    # "ok" -> success; "ok_with_drops" -> ran to completion but requested !=
    # applied somewhere (Closeout #129a's own case -- visible in
    # summary["status"]/summary["dropped_ops"], never silently "ok"); anything
    # else (blocked/partial/unavailable/...) is a harder failure, same
    # severity as the earlier staged/census "blocked" exits above.
    if overall_gate == "ok":
        return 0
    if overall_gate == "ok_with_drops":
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
