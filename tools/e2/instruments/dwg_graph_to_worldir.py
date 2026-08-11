#!/usr/bin/env python3
"""Adapt native_full DWG Graph IR to the verified WorldIR definition graph.

Scope is intentionally narrow: LINE, POLYLINE/LWPOLYLINE, ARC, and INSERT.
Every other source entity is counted as an explicit exclusion.  The adapter
never guesses a missing block origin because that would silently corrupt every
placement of a non-zero-base-point block.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping


SUPPORTED_DXF_NAMES = {"LINE", "POLYLINE", "LWPOLYLINE", "ARC", "INSERT"}
GEOMETRY_EPSILON = 1e-12


class AdapterFailure(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _handle(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise AdapterFailure("MISSING_HANDLE", f"{label} has no stable handle")
    return text


def _point2(value: Any, label: str) -> list[float]:
    try:
        x = float(value[0])
        y = float(value[1])
    except (TypeError, ValueError, IndexError) as exc:
        raise AdapterFailure("INVALID_POINT", f"{label} is not a 2D/3D point") from exc
    if not math.isfinite(x) or not math.isfinite(y):
        raise AdapterFailure("NONFINITE_POINT", f"{label} contains NaN or infinity")
    return [x, y]


def _finite(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise AdapterFailure("INVALID_NUMBER", f"{label} is not numeric") from exc
    if not math.isfinite(result):
        raise AdapterFailure("NONFINITE_NUMBER", f"{label} contains NaN or infinity")
    return result


def _same_point(a: list[float], b: list[float]) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= GEOMETRY_EPSILON


def _adapt_entity(entity: Mapping[str, Any]) -> dict[str, Any]:
    handle = _handle(entity.get("handle"), "entity")
    dxf_name = str(entity.get("dxf_name") or "").upper()
    geometry = entity.get("geometry")
    if not isinstance(geometry, Mapping):
        raise AdapterFailure("MISSING_GEOMETRY", f"entity {handle} has no geometry object")

    base: dict[str, Any] = {
        "handle": handle,
        "kind": dxf_name,
        "layer": str(entity.get("layer") or ""),
    }
    if dxf_name == "LINE":
        start = _point2(geometry.get("start"), f"LINE {handle} start")
        end = _point2(geometry.get("end"), f"LINE {handle} end")
        if _same_point(start, end):
            raise AdapterFailure("DEGENERATE_GEOMETRY", f"LINE {handle} has zero length")
        return {
            **base,
            "start": start,
            "end": end,
        }
    if dxf_name in {"POLYLINE", "LWPOLYLINE"}:
        raw_vertices = geometry.get("vertices")
        if not isinstance(raw_vertices, list):
            raise AdapterFailure("MISSING_VERTICES", f"{dxf_name} {handle} has no vertices")
        points: list[list[float]] = []
        excluded_degenerate_subsegments = 0
        for index, vertex in enumerate(raw_vertices):
            point = vertex.get("point") if isinstance(vertex, Mapping) else vertex
            candidate = _point2(point, f"{dxf_name} {handle} vertex {index}")
            if points and _same_point(points[-1], candidate):
                excluded_degenerate_subsegments += 1
                continue
            points.append(candidate)
        closed = bool(geometry.get("closed", False))
        if closed and len(points) > 1 and _same_point(points[0], points[-1]):
            points.pop()
            excluded_degenerate_subsegments += 1
        if len(points) < 2:
            raise AdapterFailure(
                "DEGENERATE_GEOMETRY",
                f"{dxf_name} {handle} has fewer than two distinct vertices",
            )
        return {
            **base,
            "points": points,
            "closed": closed,
            "_adapter_excluded_degenerate_subsegments": excluded_degenerate_subsegments,
        }
    if dxf_name == "ARC":
        return {
            **base,
            "center": _point2(geometry.get("center"), f"ARC {handle} center"),
            "radius": _finite(geometry.get("radius"), f"ARC {handle} radius"),
            "start_angle_deg": math.degrees(
                _finite(geometry.get("start_angle"), f"ARC {handle} start_angle")
            ),
            "end_angle_deg": math.degrees(
                _finite(geometry.get("end_angle"), f"ARC {handle} end_angle")
            ),
        }
    if dxf_name == "INSERT":
        target = _handle(entity.get("block_record_handle"), f"INSERT {handle} target")
        scale = geometry.get("scale", [1.0, 1.0, 1.0])
        try:
            sx = _finite(scale[0], f"INSERT {handle} x scale")
            sy = _finite(scale[1], f"INSERT {handle} y scale")
        except (TypeError, IndexError) as exc:
            raise AdapterFailure("INVALID_SCALE", f"INSERT {handle} has invalid scale") from exc
        output = {
            **base,
            "target": target,
            "insert": _point2(geometry.get("position"), f"INSERT {handle} position"),
            "scale": [sx, sy],
            # Native ObjectARX BlockReference::rotation() is radians; WorldIR
            # accepts an explicit degree field.
            "rotation_deg": math.degrees(
                _finite(geometry.get("rotation", 0.0), f"INSERT {handle} rotation")
            ),
        }
        raw_clip = entity.get("xclip")
        if isinstance(raw_clip, Mapping) and bool(raw_clip.get("enabled", False)):
            # WorldIR transforms an INSERT-owned clip from the owner's block-local
            # coordinates into world space together with the INSERT.  The native
            # extractor's boundary_wcs is already transformed, so feeding it here
            # applies the INSERT transform twice.  boundary_block is the same
            # spatial-filter boundary expressed in the owning block definition.
            raw_boundary = raw_clip.get("boundary_block")
            if not isinstance(raw_boundary, list) or len(raw_boundary) < 2:
                raise AdapterFailure(
                    "INVALID_XCLIP",
                    f"INSERT {handle} has enabled XCLIP without a usable boundary_block",
                )
            output["clip"] = {
                "boundary_owner": [
                    _point2(point, f"INSERT {handle} XCLIP point {index}")
                    for index, point in enumerate(raw_boundary)
                ],
                "boundary_space": "referenced_block_local",
                "inverted": bool(raw_clip.get("inverted", False)),
            }
        return output
    raise AdapterFailure("UNSUPPORTED_ENTITY", f"unsupported entity type {dxf_name or '<empty>'}")


def _adapt_entities(
    entities: Iterable[Any],
    *,
    excluded: Counter[str],
    counters: Counter[str],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for raw in entities:
        counters["source_entity_templates"] += 1
        if not isinstance(raw, Mapping):
            excluded["<NON_OBJECT>"] += 1
            counters["explicitly_excluded_entity_templates"] += 1
            continue
        dxf_name = str(raw.get("dxf_name") or "<EMPTY>").upper()
        if dxf_name not in SUPPORTED_DXF_NAMES:
            excluded[dxf_name] += 1
            counters["explicitly_excluded_entity_templates"] += 1
            continue
        try:
            adapted = _adapt_entity(raw)
        except AdapterFailure as exc:
            if exc.code != "DEGENERATE_GEOMETRY":
                raise
            excluded[f"DEGENERATE:{dxf_name}"] += 1
            counters["explicitly_excluded_entity_templates"] += 1
            counters["excluded_invalid_geometry_templates"] += 1
            continue
        counters["excluded_degenerate_subsegments"] += int(
            adapted.pop("_adapter_excluded_degenerate_subsegments", 0)
        )
        output.append(adapted)
        counters["adapted_entity_templates"] += 1
    return output


def _modelspace_btr(ir: Mapping[str, Any]) -> Mapping[str, Any]:
    symbol_tables = ir.get("symbol_tables")
    records = symbol_tables.get("block_table_records") if isinstance(symbol_tables, Mapping) else None
    if not isinstance(records, list):
        raise AdapterFailure("MISSING_BLOCK_TABLE", "symbol_tables.block_table_records is required")
    candidates = [
        record
        for record in records
        if isinstance(record, Mapping)
        and str(record.get("name") or "").lower() == "*model_space"
    ]
    if len(candidates) != 1:
        raise AdapterFailure(
            "MODELSPACE_BTR_AMBIGUOUS",
            f"expected one *Model_Space BTR, found {len(candidates)}",
        )
    return candidates[0]


def adapt(ir: Mapping[str, Any]) -> dict[str, Any]:
    if ir.get("schema") != "ariadne.dwg_graph_ir.v1":
        raise AdapterFailure("WRONG_SCHEMA", "input must be ariadne.dwg_graph_ir.v1")
    if ir.get("coverage_level") != "native_full":
        raise AdapterFailure("INSUFFICIENT_COVERAGE", "input must declare coverage_level=native_full")

    root_btr = _modelspace_btr(ir)
    root_handle = _handle(root_btr.get("handle"), "modelspace BTR")
    root_origin = root_btr.get("origin")
    if root_origin is None:
        raise AdapterFailure("MISSING_BLOCK_ORIGIN", "modelspace BTR origin is missing")

    excluded: Counter[str] = Counter()
    counters: Counter[str] = Counter()
    definitions: dict[str, dict[str, Any]] = {
        root_handle: {
            "handle": root_handle,
            "name": str(root_btr.get("name") or "*Model_Space"),
            "base_point": _point2(root_origin, "modelspace BTR origin"),
            "entities": _adapt_entities(
                ir.get("entities") or [], excluded=excluded, counters=counters
            ),
        }
    }

    raw_definitions = ir.get("block_definitions")
    if not isinstance(raw_definitions, list):
        raise AdapterFailure("MISSING_BLOCK_DEFINITIONS", "block_definitions must be an array")
    for raw_definition in raw_definitions:
        if not isinstance(raw_definition, Mapping):
            raise AdapterFailure("INVALID_BLOCK_DEFINITION", "block definition is not an object")
        handle = _handle(raw_definition.get("handle"), "block definition")
        if handle in definitions:
            raise AdapterFailure("DUPLICATE_DEFINITION_HANDLE", f"duplicate definition {handle}")
        origin = raw_definition.get("origin")
        if origin is None:
            raise AdapterFailure(
                "MISSING_BLOCK_ORIGIN",
                f"block definition {handle} has no origin; refusing zero-origin inference",
            )
        entities = raw_definition.get("def_entities")
        if not isinstance(entities, list):
            raise AdapterFailure(
                "MISSING_DEFINITION_ENTITIES",
                f"block definition {handle} has no inlined def_entities",
            )
        definitions[handle] = {
            "handle": handle,
            "name": str(raw_definition.get("name") or ""),
            "base_point": _point2(origin, f"block definition {handle} origin"),
            "entities": _adapt_entities(entities, excluded=excluded, counters=counters),
        }

    targets = {
        entity["target"]
        for definition in definitions.values()
        for entity in definition["entities"]
        if entity.get("kind") == "INSERT"
    }
    missing_targets = sorted(targets - set(definitions))
    if missing_targets:
        raise AdapterFailure(
            "MISSING_TARGET_DEFINITION",
            f"INSERT targets are absent from block_definitions: {missing_targets[:10]}",
        )

    source_count = counters["source_entity_templates"]
    adapted_count = counters["adapted_entity_templates"]
    excluded_count = counters["explicitly_excluded_entity_templates"]
    balance_ok = source_count == adapted_count + excluded_count
    if not balance_ok:
        raise AdapterFailure("ADAPTER_IMBALANCE", "adapted and excluded counts do not balance source")

    source = ir.get("source") if isinstance(ir.get("source"), Mapping) else {}
    status = "PASS" if excluded_count == 0 else "PARTIAL"
    return {
        "ir": "worldir.input.v1",
        "status": status,
        "drawing_id": source.get("sha256", source.get("dwg_name", "unknown")),
        "root": root_handle,
        "definitions": definitions,
        "adapter_ledger": {
            "scope": "LINE_POLYLINE_ARC_INSERT",
            "source_entity_templates": source_count,
            "adapted_entity_templates": adapted_count,
            "explicitly_excluded_entity_templates": excluded_count,
            "excluded_invalid_geometry_templates": counters[
                "excluded_invalid_geometry_templates"
            ],
            "excluded_degenerate_subsegments": counters[
                "excluded_degenerate_subsegments"
            ],
            "excluded_by_dxf_name": dict(sorted(excluded.items())),
            "balance_ok": balance_ok,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Adapt native_full DWG Graph IR to WorldIR input.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)

    try:
        source = json.loads(args.input.read_text(encoding="utf-8-sig"))
        output = adapt(source)
        payload = json.dumps(
            output,
            ensure_ascii=False,
            indent=None if args.compact else 2,
            separators=(",", ":") if args.compact else None,
        ) + "\n"
        if args.output is None:
            print(payload, end="")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8", newline="\n")
        return 0 if output["status"] == "PASS" else 10
    except AdapterFailure as exc:
        print(json.dumps({"status": "FAIL", "code": exc.code, "reason": str(exc)}, ensure_ascii=False))
        return 11


if __name__ == "__main__":
    raise SystemExit(main())
