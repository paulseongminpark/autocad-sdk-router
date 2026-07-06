#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extraction_coverage.py -- CAD OS Layer per-kind geometry extraction-coverage meter.

WAVE-0 F6: bucket every entity in a ``ariadne.dwg_graph_ir.v1`` document by its
``geometry.kind`` and report, per kind, how many entities carry FULL
reconstructable geometry vs PARTIAL (some anchor fields present, some missing)
vs EMPTY (no anchor field populated -- including kinds the extractor has not
wired an anchor for at all yet, e.g. ``dimension``). This is the meter that
drives T3a's extraction punch-list and seeds the per-kind FULL/empty gate T17
freezes against (D:\\dev\\.build\\cados_plan\\final\\PLAN.md, node F6 / H-R2 / H-R3).

What "FULL" means here
-----------------------
Per kind, ``ANCHOR_FIELDS_BY_KIND`` lists the ``geometry`` keys that must all
be populated for an entity of that kind to be considered reconstructable. Each
entry is grounded in one of three sources -- never guessed:

  1. the existing sibling validator ``validate_dwg_geometry_extract.py``'s
     ``REQUIRED_COORDINATE_TYPES`` (line, polyline, lwpolyline, arc, circle,
     block_reference);
  2. an unambiguous, kind-named field in ``schemas/dwg_graph_ir.v1.schema.json``
     (``spline.control_points`` = "Spline control points",
     ``hatch.loops`` = "Hatch boundary loops");
  3. direct empirical confirmation against the M4 sample IR (``text.position``
     is populated by every ``AcDbText`` entity extracted so far).

A kind NOT in this table (ellipse, point, mtext, attribute, dimension, leader,
solid, region, viewport, ray, xline, proxy, unsupported) has no wired anchor
field yet on this build -- it is honestly reported ``empty`` rather than
guessed at, so a kind's bucket only turns FULL once its real extraction lands
(Rule 12: no fake success) and this table is extended with real evidence.

This deliberately does NOT use ``dimension.measurement`` as dimension's
anchor: the plan (G13) flags ``measurement`` as the wrong discriminator for
dimension (repeated grid dimensions legitimately share a measurement value),
and the true defining-point field names (``xline1``/``xline2``/``text_pos``/
...) are not in the IR schema yet -- so ``dimension`` has zero anchor fields
and always reports ``empty`` until T3a.1 lands and this table is revisited.

Run ``python tools/extraction_coverage.py <dwg_graph_ir.json> [--out report.json]``.
Stdlib only. BOM-tolerant load (``utf-8-sig``, matches ``cad_diff.load_ir``);
deterministic (buckets sorted by kind name; no timestamps, no randomness).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# On this box the IR JSON may carry a UTF-8 BOM; json.load on the cp949 locale
# needs utf-8-sig to decode it. Writes are plain UTF-8 (mirrors cad_diff.py).
_JSON_ENCODING = "utf-8-sig"

SCHEMA_ID = "ariadne.extraction_coverage.v1"
IR_SCHEMA_ID = "ariadne.dwg_graph_ir.v1"

# Every kind the IR schema's geometry.kind enum recognizes
# (schemas/dwg_graph_ir.v1.schema.json $defs.geometry.properties.kind.enum).
ALL_KNOWN_KINDS: Tuple[str, ...] = (
    "line", "polyline", "lwpolyline", "arc", "circle", "ellipse", "spline",
    "point", "text", "mtext", "block_reference", "attribute", "dimension",
    "leader", "hatch", "solid", "region", "viewport", "ray", "xline",
    "proxy", "unsupported",
)

# kind -> the geometry.* keys that must ALL be populated for an entity of that
# kind to count as reconstructable geometry. See module docstring for the
# provenance of every entry. Kinds absent from this table have no wired anchor
# yet and always classify "empty".
ANCHOR_FIELDS_BY_KIND: Dict[str, Tuple[str, ...]] = {
    "line": ("start", "end"),
    "polyline": ("vertices",),
    "lwpolyline": ("vertices",),
    "arc": ("center",),
    "circle": ("center",),
    "block_reference": ("position",),
    "text": ("position",),
    "spline": ("control_points",),
    "hatch": ("loops",),
}

STATUS_FULL = "full"
STATUS_PARTIAL = "partial"
STATUS_EMPTY = "empty"

# How many example handles of incomplete (non-full) entities to keep per
# bucket, as a starting punch-list pointer for T3a triage.
_SAMPLE_HANDLES_LIMIT = 5


def load_ir(path) -> Dict[str, Any]:
    """Load an IR JSON document (BOM-tolerant, matches cad_diff.load_ir)."""
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _has_value(geom: Dict[str, Any], field: str) -> bool:
    """True if geom[field] is present and non-empty (missing key -> None -> False)."""
    return bool(geom.get(field))


def classify_entity(entity: Dict[str, Any]) -> str:
    """Return 'full' | 'partial' | 'empty' for one entity's geometry payload."""
    geom = entity.get("geometry") if isinstance(entity, dict) else None
    if not isinstance(geom, dict):
        return STATUS_EMPTY
    kind = geom.get("kind") or "unsupported"
    required = ANCHOR_FIELDS_BY_KIND.get(kind, ())
    if not required:
        return STATUS_EMPTY
    present = [f for f in required if _has_value(geom, f)]
    if len(present) == len(required):
        return STATUS_FULL
    if present:
        return STATUS_PARTIAL
    return STATUS_EMPTY


def _bucket_status(counts: Dict[str, int]) -> str:
    """Aggregate one kind's full/partial/empty entity counts into a bucket status.

    all-full -> "full"; all-empty -> "empty"; anything mixed (including
    all-entities-individually-partial) -> "partial".
    """
    total = counts[STATUS_FULL] + counts[STATUS_PARTIAL] + counts[STATUS_EMPTY]
    if total == 0:
        return STATUS_EMPTY
    if counts[STATUS_FULL] == total:
        return STATUS_FULL
    if counts[STATUS_EMPTY] == total:
        return STATUS_EMPTY
    return STATUS_PARTIAL


def build_report(ir: Dict[str, Any], source_path: Optional[str] = None) -> Dict[str, Any]:
    """Bucket ir['entities'] by geometry.kind and classify FULL/PARTIAL/EMPTY.

    Deterministic: buckets are keyed and emitted in sorted-by-kind order
    regardless of the entities[] encounter order in the source IR.
    """
    entities = ir.get("entities")
    entities = entities if isinstance(entities, list) else []

    by_kind: Dict[str, List[Dict[str, Any]]] = {}
    for ent in entities:
        geom = ent.get("geometry") if isinstance(ent, dict) else None
        kind = (geom or {}).get("kind") or "unsupported"
        by_kind.setdefault(kind, []).append(ent)

    buckets: Dict[str, Dict[str, Any]] = {}
    total_counts = {STATUS_FULL: 0, STATUS_PARTIAL: 0, STATUS_EMPTY: 0}

    for kind in sorted(by_kind):
        ents = by_kind[kind]
        counts = {STATUS_FULL: 0, STATUS_PARTIAL: 0, STATUS_EMPTY: 0}
        incomplete_handles: List[str] = []
        for ent in ents:
            status = classify_entity(ent)
            counts[status] += 1
            total_counts[status] += 1
            if status != STATUS_FULL and len(incomplete_handles) < _SAMPLE_HANDLES_LIMIT:
                handle = ent.get("handle") if isinstance(ent, dict) else None
                if handle:
                    incomplete_handles.append(str(handle))
        buckets[kind] = {
            "kind": kind,
            "count": len(ents),
            "full": counts[STATUS_FULL],
            "partial": counts[STATUS_PARTIAL],
            "empty": counts[STATUS_EMPTY],
            "status": _bucket_status(counts),
            "anchor_fields": list(ANCHOR_FIELDS_BY_KIND.get(kind, ())),
            "sample_incomplete_handles": incomplete_handles,
        }

    diagnostics = ir.get("diagnostics") or {}
    reported_entity_count = diagnostics.get("entity_count")

    # A kind outside the schema's own enum is a stronger signal than "empty":
    # it means the IR schema/catalog doesn't even know this class exists yet
    # (plan risk H-R32, "uncatalogued real-DWG classes"), distinct from a
    # recognized-but-unwired kind like dimension.
    unrecognized_kinds = sorted(k for k in buckets if k not in ALL_KNOWN_KINDS)

    return {
        "schema": SCHEMA_ID,
        "generated_from": "tools/extraction_coverage.py",
        "source_ir": source_path,
        "ir_schema": ir.get("schema"),
        "entity_count": len(entities),
        "diagnostics_entity_count_match": (
            reported_entity_count is None or reported_entity_count == len(entities)
        ),
        "unrecognized_kinds": unrecognized_kinds,
        "buckets": buckets,
        "totals": {
            "kinds_seen": len(buckets),
            "full": total_counts[STATUS_FULL],
            "partial": total_counts[STATUS_PARTIAL],
            "empty": total_counts[STATUS_EMPTY],
            "kinds_full": sorted(k for k, b in buckets.items() if b["status"] == STATUS_FULL),
            "kinds_partial": sorted(k for k, b in buckets.items() if b["status"] == STATUS_PARTIAL),
            "kinds_empty": sorted(k for k, b in buckets.items() if b["status"] == STATUS_EMPTY),
        },
    }


def write_report(report: Dict[str, Any], path) -> str:
    """Write an extraction_coverage report (UTF-8, pretty). Returns the path written."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(report, ensure_ascii=False, indent=2))
        fh.write("\n")
    return str(path)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bucket a dwg_graph_ir.v1 IR by geometry.kind; report "
                     "FULL/PARTIAL/EMPTY geometry coverage per kind."
    )
    parser.add_argument("ir_path", help="Path to a dwg_graph_ir.v1 JSON document")
    parser.add_argument("--out", help="Optional path to also write the report JSON")
    args = parser.parse_args(argv)

    try:
        ir = load_ir(args.ir_path)
    except (OSError, json.JSONDecodeError) as exc:
        print("error: failed to load %s: %s" % (args.ir_path, exc), file=sys.stderr)
        return 1

    report = build_report(ir, source_path=str(args.ir_path))
    text = json.dumps(report, ensure_ascii=False, indent=2)

    if args.out:
        write_report(report, args.out)

    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
