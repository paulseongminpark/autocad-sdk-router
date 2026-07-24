#!/usr/bin/env python3
"""Canonical world-coordinate SEG-IR / INSERT transform oracle.

The module consumes either:

1. A canonical definition graph with ``root`` and ``definitions``.  INSERT
   entities reference definitions by stable handle and may carry a parser-
   supplied ``local_matrix`` or explicit insert/rotation/scale/array fields.
2. A flat ``seg.v1``-style object containing ``segments``.  Flat segments are
   audited as already-world-coordinate root geometry and receive lineage ids.

Only stable handles, array indices, and subentity ordinals participate in
lineage hashes.  Names, layers, labels, and entity order do not.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np


ORACLE_VERSION = "worldir.oracle.v1"
DEFAULT_MAX_DEPTH = 32
DEFAULT_MAX_INSTANCES = 2_000_000
GEOMETRY_EPSILON = 1e-12


class OracleFailure(Exception):
    """An expected fail-closed integrity, geometry, or resource failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        entity_handle: str | None = None,
        source_def_handle: str | None = None,
        placement_path_uid: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.entity_handle = entity_handle
        self.source_def_handle = source_def_handle
        self.placement_path_uid = placement_path_uid

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "entity_handle": self.entity_handle,
            "source_def_handle": self.source_def_handle,
            "placement_path_uid": self.placement_path_uid,
        }


def _hash_parts(*parts: Any) -> str:
    """SHA-256 over length-prefixed UTF-8 fields (no concatenation ambiguity)."""

    digest = hashlib.sha256()
    for part in parts:
        raw = str(part).encode("utf-8")
        digest.update(len(raw).to_bytes(8, byteorder="big", signed=False))
        digest.update(raw)
    return digest.hexdigest()


def _as_handle(value: Any, label: str) -> str:
    if value is None:
        raise OracleFailure("MISSING_HANDLE", f"{label} is missing")
    handle = str(value)
    if not handle:
        raise OracleFailure("MISSING_HANDLE", f"{label} is empty")
    return handle


def _point2(value: Any, label: str) -> np.ndarray:
    try:
        arr = np.asarray(value, dtype=np.float64).reshape(-1)
    except (TypeError, ValueError) as exc:
        raise OracleFailure("INVALID_GEOMETRY", f"{label} is not numeric: {exc}") from exc
    if arr.size < 2:
        raise OracleFailure("INVALID_GEOMETRY", f"{label} requires at least two coordinates")
    point = arr[:2]
    if not np.isfinite(point).all():
        raise OracleFailure("NONFINITE_GEOMETRY", f"{label} contains NaN or infinity")
    return point


def _translation(x: float, y: float) -> np.ndarray:
    return np.array([[1.0, 0.0, x], [0.0, 1.0, y], [0.0, 0.0, 1.0]], dtype=np.float64)


def _rotation(degrees: float) -> np.ndarray:
    radians = math.radians(degrees)
    cosine, sine = math.cos(radians), math.sin(radians)
    return np.array(
        [[cosine, -sine, 0.0], [sine, cosine, 0.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )


def _scale(x: float, y: float) -> np.ndarray:
    return np.array([[x, 0.0, 0.0], [0.0, y, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)


def _matrix3(value: Any, label: str) -> np.ndarray:
    try:
        arr = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise OracleFailure("INVALID_TRANSFORM", f"{label} is not numeric: {exc}") from exc
    if arr.shape == (2, 3):
        arr = np.vstack((arr, np.array([0.0, 0.0, 1.0], dtype=np.float64)))
    if arr.shape != (3, 3):
        raise OracleFailure("INVALID_TRANSFORM", f"{label} must be 2x3 or 3x3")
    if not np.isfinite(arr).all():
        raise OracleFailure("NONFINITE_TRANSFORM", f"{label} contains NaN or infinity")
    if not np.allclose(arr[2], [0.0, 0.0, 1.0], rtol=0.0, atol=GEOMETRY_EPSILON):
        raise OracleFailure("INVALID_TRANSFORM", f"{label} is not a 2D affine matrix")
    determinant = float(np.linalg.det(arr[:2, :2]))
    if not math.isfinite(determinant) or abs(determinant) <= GEOMETRY_EPSILON:
        raise OracleFailure("SINGULAR_TRANSFORM", f"{label} is not invertible")
    return arr


def _apply(matrix: np.ndarray, point: np.ndarray) -> np.ndarray:
    homogeneous = np.array([float(point[0]), float(point[1]), 1.0], dtype=np.float64)
    out = matrix @ homogeneous
    if not np.isfinite(out).all() or abs(float(out[2])) <= GEOMETRY_EPSILON:
        raise OracleFailure("NONFINITE_TRANSFORM_RESULT", "transform produced invalid coordinates")
    return out[:2] / out[2]


def _canonical_endpoints(p0: np.ndarray, p1: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    left = (float(p0[0]), float(p0[1]))
    right = (float(p1[0]), float(p1[1]))
    return (p0, p1) if left <= right else (p1, p0)


def _entity_kind(entity: Mapping[str, Any]) -> str:
    raw = entity.get("kind", entity.get("type", entity.get("dxftype", "")))
    return str(raw).strip().upper().replace("-", "_")


def _poly_points(entity: Mapping[str, Any]) -> list[np.ndarray]:
    raw = entity.get("points", entity.get("pts", entity.get("vertices")))
    if raw is None:
        raise OracleFailure("INVALID_GEOMETRY", "polyline has no points")
    return [_point2(point, "polyline point") for point in raw]


def _line_points(entity: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    points = entity.get("points", entity.get("pts"))
    if points is not None:
        if len(points) != 2:
            raise OracleFailure("INVALID_GEOMETRY", "line/segment must have exactly two endpoints")
        return _point2(points[0], "line start"), _point2(points[1], "line end")
    if "start" not in entity or "end" not in entity:
        raise OracleFailure("INVALID_GEOMETRY", "line/segment requires points or start/end")
    return _point2(entity["start"], "line start"), _point2(entity["end"], "line end")


def _segment_count_contract(entity: Mapping[str, Any]) -> int:
    """Count expected normalizer emissions independently of the emitter."""

    kind = _entity_kind(entity)
    if kind in {"LINE", "SEGMENT", "POLY_EDGE", "ARC_CHORD"}:
        return 1
    if kind in {"LWPOLYLINE", "POLYLINE"}:
        points = entity.get("points", entity.get("pts", entity.get("vertices")))
        if points is None:
            raise OracleFailure("INVALID_GEOMETRY", "polyline has no points")
        count = max(0, len(points) - 1)
        if bool(entity.get("closed", False)) and len(points) > 2:
            count += 1
        return count
    if kind == "ARC":
        return 1
    raise OracleFailure("UNSUPPORTED_ENTITY", f"unsupported primitive kind: {kind or '<empty>'}")


def _normalize_entity(entity: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Normalize supported primitive geometry to local 2D line segments."""

    kind = _entity_kind(entity)
    segments: list[dict[str, Any]] = []
    if kind in {"LINE", "SEGMENT", "POLY_EDGE", "ARC_CHORD"}:
        p0, p1 = _line_points(entity)
        segments.append({"kind": kind.lower().replace("_", "-"), "p0": p0, "p1": p1})
    elif kind in {"LWPOLYLINE", "POLYLINE"}:
        points = _poly_points(entity)
        for index in range(max(0, len(points) - 1)):
            segments.append({"kind": "poly-edge", "p0": points[index], "p1": points[index + 1]})
        if bool(entity.get("closed", False)) and len(points) > 2:
            segments.append({"kind": "poly-edge", "p0": points[-1], "p1": points[0]})
    elif kind == "ARC":
        center = _point2(entity.get("center"), "arc center")
        try:
            radius = float(entity["radius"])
            start = math.radians(float(entity["start_angle_deg"]))
            end = math.radians(float(entity["end_angle_deg"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise OracleFailure("INVALID_GEOMETRY", f"invalid arc fields: {exc}") from exc
        if not math.isfinite(radius) or radius <= 0.0:
            raise OracleFailure("DEGENERATE_GEOMETRY", "arc radius must be finite and positive")
        p0 = center + radius * np.array([math.cos(start), math.sin(start)])
        p1 = center + radius * np.array([math.cos(end), math.sin(end)])
        segments.append({"kind": "arc-chord", "p0": p0, "p1": p1})
    else:
        raise OracleFailure("UNSUPPORTED_ENTITY", f"unsupported primitive kind: {kind or '<empty>'}")

    for segment in segments:
        p0 = segment["p0"]
        p1 = segment["p1"]
        if not np.isfinite(p0).all() or not np.isfinite(p1).all():
            raise OracleFailure("NONFINITE_GEOMETRY", "normalized segment contains NaN or infinity")
        if float(np.linalg.norm(p1 - p0)) <= GEOMETRY_EPSILON:
            raise OracleFailure("DEGENERATE_GEOMETRY", "zero-length segment")
    return segments


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise OracleFailure("INVALID_ARRAY", f"{label} must be a positive integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise OracleFailure("INVALID_ARRAY", f"{label} must be a positive integer") from exc
    if result <= 0 or result != value:
        raise OracleFailure("INVALID_ARRAY", f"{label} must be a positive integer")
    return result


def _array_spec(insert: Mapping[str, Any]) -> tuple[int, int, float, float]:
    array = insert.get("array") or {}
    rows = _positive_int(array.get("rows", insert.get("row_count", 1)), "array rows")
    columns = _positive_int(array.get("columns", insert.get("column_count", 1)), "array columns")
    try:
        row_spacing = float(array.get("row_spacing", insert.get("row_spacing", 0.0)))
        column_spacing = float(array.get("column_spacing", insert.get("column_spacing", 0.0)))
    except (TypeError, ValueError) as exc:
        raise OracleFailure("INVALID_ARRAY", f"array spacing must be numeric: {exc}") from exc
    if not math.isfinite(row_spacing) or not math.isfinite(column_spacing):
        raise OracleFailure("INVALID_ARRAY", "array spacing must be finite")
    return rows, columns, row_spacing, column_spacing


def resolve_insert_transform(
    insert: Mapping[str, Any],
    target_base_point: Sequence[float],
    row: int,
    column: int,
) -> np.ndarray:
    """Return T_insert_local @ T_array_cell using the column-vector contract.

    ``local_matrix`` is the preferred parser-adapter surface and must already
    map target-definition coordinates (including its base point convention) to
    the parent frame for the non-array INSERT.  If absent, the canonical JSON
    component fields are composed as T(insert) @ R @ S @ T(-base).
    """

    rows, columns, row_spacing, column_spacing = _array_spec(insert)
    if row < 0 or row >= rows or column < 0 or column >= columns:
        raise OracleFailure("INVALID_ARRAY", "array cell is outside declared dimensions")
    cell = _translation(column * column_spacing, row * row_spacing)

    if "local_matrix" in insert:
        base_matrix = _matrix3(insert["local_matrix"], "INSERT local_matrix")
    else:
        extrusion = insert.get("extrusion", [0.0, 0.0, 1.0])
        ext = np.asarray(extrusion, dtype=np.float64).reshape(-1)
        if ext.size < 3 or not np.isfinite(ext[:3]).all() or not np.allclose(
            ext[:3], [0.0, 0.0, 1.0], rtol=0.0, atol=GEOMETRY_EPSILON
        ):
            raise OracleFailure(
                "UNSUPPORTED_EXTRUSION",
                "non-default extrusion requires a parser-supplied local_matrix",
            )
        insertion = _point2(insert.get("insert", [0.0, 0.0]), "INSERT insertion point")
        base = _point2(target_base_point, "target base point")
        try:
            rotation = float(insert.get("rotation_deg", insert.get("rotation", 0.0)))
            scale_value = insert.get("scale", [insert.get("xscale", 1.0), insert.get("yscale", 1.0)])
            if isinstance(scale_value, (int, float)):
                sx = sy = float(scale_value)
            else:
                sx = float(scale_value[0])
                sy = float(scale_value[1])
        except (TypeError, ValueError, IndexError) as exc:
            raise OracleFailure("INVALID_TRANSFORM", f"invalid rotation/scale fields: {exc}") from exc
        if not all(math.isfinite(value) for value in (rotation, sx, sy)):
            raise OracleFailure("NONFINITE_TRANSFORM", "rotation/scale contains NaN or infinity")
        base_matrix = (
            _translation(float(insertion[0]), float(insertion[1]))
            @ _rotation(rotation)
            @ _scale(sx, sy)
            @ _translation(-float(base[0]), -float(base[1]))
        )
        base_matrix = _matrix3(base_matrix, "composed INSERT transform")

    return _matrix3(base_matrix @ cell, "INSERT transform with array cell")


def _adapt_flat_seg_ir(ir: Mapping[str, Any]) -> dict[str, Any]:
    root_handle = _as_handle(ir.get("root_def_handle", "MODELSPACE"), "root_def_handle")
    entities: list[dict[str, Any]] = []
    for index, segment in enumerate(ir.get("segments", [])):
        if not isinstance(segment, Mapping):
            raise OracleFailure("INVALID_INPUT", f"segment {index} is not an object")
        handle = segment.get("handle", segment.get("sid"))
        entity = {
            "kind": segment.get("kind", "SEGMENT"),
            "handle": _as_handle(handle, f"segment {index} handle/sid"),
            "pts": segment.get("pts", segment.get("points")),
        }
        entities.append(entity)
    return {
        "ir": "worldir.input.v1",
        "drawing_id": ir.get("drawing_id", "unknown"),
        "root": root_handle,
        "definitions": {
            root_handle: {
                "handle": root_handle,
                "base_point": [0.0, 0.0],
                "entities": entities,
            }
        },
        "_input_mode": "flat_seg_ir",
    }


def _canonical_input(ir: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(ir, Mapping):
        raise OracleFailure("INVALID_INPUT", "input must be a JSON object")
    if "definitions" not in ir and "segments" in ir:
        return _adapt_flat_seg_ir(ir)
    if "definitions" not in ir:
        raise OracleFailure("INVALID_INPUT", "input requires definitions or flat segments")
    out = dict(ir)
    out.setdefault("_input_mode", "definition_graph")
    return out


def expand_world_ir(
    input_ir: Mapping[str, Any],
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_instances: int = DEFAULT_MAX_INSTANCES,
    _emitter: Callable[[Mapping[str, Any]], list[dict[str, Any]]] = _normalize_entity,
) -> dict[str, Any]:
    """Expand an INSERT graph to canonical world segments with a loss ledger.

    Expected integrity failures return ``status=FAIL`` and an empty primary
    segment list.  Any already-produced partial segments are counted as
    discarded diagnostics and are never exposed as a successful result.
    """

    ledger: dict[str, Any] = {
        "input_entity_templates": 0,
        "input_primitive_templates": 0,
        "input_insert_templates": 0,
        "reachable_primitive_entity_instances": 0,
        "reachable_insert_placements": 0,
        "expected_segment_instances": 0,
        "emitted_segment_instances": 0,
        "empty_block_placements": 0,
        "discarded_partial_segments": 0,
        "conservation_delta": 0,
        "conservation_ok": False,
        "entity_entries": [],
        "zero_output_entries": [],
    }
    failures: list[dict[str, Any]] = []
    placed: list[dict[str, Any]] = []
    input_mode = "unknown"
    drawing_id = "unknown"

    try:
        if max_depth < 0:
            raise OracleFailure("INVALID_LIMIT", "max_depth must be non-negative")
        if max_instances <= 0:
            raise OracleFailure("INVALID_LIMIT", "max_instances must be positive")
        ir = _canonical_input(input_ir)
        input_mode = str(ir.get("_input_mode", "definition_graph"))
        drawing_id = str(ir.get("drawing_id", "unknown"))
        raw_definitions = ir.get("definitions")
        if not isinstance(raw_definitions, Mapping) or not raw_definitions:
            raise OracleFailure("INVALID_INPUT", "definitions must be a non-empty object")

        definitions: dict[str, Mapping[str, Any]] = {}
        aliases: dict[str, str] = {}
        for key, definition in raw_definitions.items():
            if not isinstance(definition, Mapping):
                raise OracleFailure("INVALID_INPUT", f"definition {key!r} is not an object")
            handle = _as_handle(definition.get("handle", key), f"definition {key!r} handle")
            if handle in definitions:
                raise OracleFailure("DUPLICATE_DEFINITION_HANDLE", f"duplicate definition handle {handle}")
            entities = definition.get("entities", [])
            if not isinstance(entities, list):
                raise OracleFailure("INVALID_INPUT", f"definition {handle} entities must be a list")
            normalized_definition = dict(definition)
            normalized_definition["handle"] = handle
            normalized_definition["entities"] = entities
            definitions[handle] = normalized_definition
            aliases[str(key)] = handle
            aliases[handle] = handle

            seen_entity_handles: set[str] = set()
            for entity in entities:
                if not isinstance(entity, Mapping):
                    raise OracleFailure("INVALID_INPUT", f"definition {handle} has a non-object entity")
                entity_handle = _as_handle(entity.get("handle"), f"entity in definition {handle}")
                if entity_handle in seen_entity_handles:
                    raise OracleFailure(
                        "DUPLICATE_ENTITY_HANDLE",
                        f"duplicate entity handle {entity_handle} in definition {handle}",
                    )
                seen_entity_handles.add(entity_handle)
                ledger["input_entity_templates"] += 1
                if _entity_kind(entity) == "INSERT":
                    ledger["input_insert_templates"] += 1
                else:
                    ledger["input_primitive_templates"] += 1

        root_raw = ir.get("root", ir.get("modelspace_root"))
        if isinstance(root_raw, Mapping):
            root_raw = root_raw.get("handle")
        root_ref = _as_handle(root_raw, "root/modelspace_root")
        root_handle = aliases.get(root_ref)
        if root_handle is None:
            raise OracleFailure("MISSING_ROOT", f"root definition {root_ref} does not exist")
        root_uid = _hash_parts("MODELSPACE_ROOT", root_handle)

        def visit(
            definition_handle: str,
            parent_transform: np.ndarray,
            path_uid: str,
            lineage_path: list[dict[str, Any]],
            active_edges: frozenset[tuple[str, str, str, int, int]],
            depth: int,
            inherited_array_member: bool,
        ) -> None:
            if depth > max_depth:
                raise OracleFailure(
                    "RESOURCE_MAX_DEPTH",
                    f"maximum INSERT depth {max_depth} exceeded",
                    source_def_handle=definition_handle,
                    placement_path_uid=path_uid,
                )
            definition = definitions[definition_handle]
            entities = definition["entities"]
            if not entities:
                ledger["empty_block_placements"] += 1
                ledger["zero_output_entries"].append(
                    {
                        "source_def_handle": definition_handle,
                        "placement_path_uid": path_uid,
                        "reason": "EMPTY_DEFINITION",
                        "expected_segments": 0,
                        "emitted_segments": 0,
                    }
                )
                return

            ordered_entities = sorted(entities, key=lambda item: str(item.get("handle")))
            for entity in ordered_entities:
                entity_handle = _as_handle(entity.get("handle"), "entity handle")
                kind = _entity_kind(entity)
                if kind == "INSERT":
                    target_ref = _as_handle(
                        entity.get("target", entity.get("target_def_handle")),
                        f"INSERT {entity_handle} target",
                    )
                    target_handle = aliases.get(target_ref)
                    if target_handle is None:
                        raise OracleFailure(
                            "MISSING_TARGET",
                            f"INSERT {entity_handle} target {target_ref} does not exist",
                            entity_handle=entity_handle,
                            source_def_handle=definition_handle,
                            placement_path_uid=path_uid,
                        )
                    rows, columns, _, _ = _array_spec(entity)
                    target_base = definitions[target_handle].get("base_point", [0.0, 0.0])
                    is_array = rows > 1 or columns > 1
                    for row in range(rows):
                        for column in range(columns):
                            edge_key = (definition_handle, entity_handle, target_handle, row, column)
                            if edge_key in active_edges:
                                raise OracleFailure(
                                    "GRAPH_CYCLE",
                                    f"cycle detected at INSERT {entity_handle} cell ({row},{column})",
                                    entity_handle=entity_handle,
                                    source_def_handle=definition_handle,
                                    placement_path_uid=path_uid,
                                )
                            local_transform = resolve_insert_transform(entity, target_base, row, column)
                            world_transform = _matrix3(
                                parent_transform @ local_transform,
                                f"world transform for INSERT {entity_handle}",
                            )
                            child_uid = _hash_parts(
                                path_uid,
                                entity_handle,
                                target_handle,
                                row,
                                column,
                            )
                            child_step = {
                                "source_def_handle": definition_handle,
                                "insert_entity_handle": entity_handle,
                                "target_def_handle": target_handle,
                                "array_row_index": row,
                                "array_col_index": column,
                            }
                            ledger["reachable_insert_placements"] += 1
                            visit(
                                target_handle,
                                world_transform,
                                child_uid,
                                lineage_path + [child_step],
                                active_edges | {edge_key},
                                depth + 1,
                                inherited_array_member or is_array,
                            )
                    continue

                ledger["reachable_primitive_entity_instances"] += 1
                expected_count = _segment_count_contract(entity)
                ledger["expected_segment_instances"] += expected_count
                try:
                    local_segments = _emitter(entity)
                except OracleFailure as exc:
                    if exc.entity_handle is None:
                        exc.entity_handle = entity_handle
                    if exc.source_def_handle is None:
                        exc.source_def_handle = definition_handle
                    if exc.placement_path_uid is None:
                        exc.placement_path_uid = path_uid
                    raise
                if len(local_segments) != expected_count:
                    raise OracleFailure(
                        "SILENT_DROP",
                        f"entity {entity_handle}: expected {expected_count} segments, emitted {len(local_segments)}",
                        entity_handle=entity_handle,
                        source_def_handle=definition_handle,
                        placement_path_uid=path_uid,
                    )

                before = len(placed)
                linear = parent_transform[:2, :2]
                determinant = float(np.linalg.det(linear))
                singular_values = np.linalg.svd(linear, compute_uv=False)
                nonuniform = not math.isclose(
                    float(singular_values[0]),
                    float(singular_values[-1]),
                    rel_tol=1e-12,
                    abs_tol=GEOMETRY_EPSILON,
                )
                for ordinal, local_segment in enumerate(local_segments):
                    p0_world = _apply(parent_transform, local_segment["p0"])
                    p1_world = _apply(parent_transform, local_segment["p1"])
                    if float(np.linalg.norm(p1_world - p0_world)) <= GEOMETRY_EPSILON:
                        raise OracleFailure(
                            "DEGENERATE_WORLD_GEOMETRY",
                            f"entity {entity_handle} collapsed under transform",
                            entity_handle=entity_handle,
                            source_def_handle=definition_handle,
                            placement_path_uid=path_uid,
                        )
                    p0_world, p1_world = _canonical_endpoints(p0_world, p1_world)
                    placed_uid = _hash_parts(path_uid, entity_handle, ordinal)
                    placed.append(
                        {
                            "placed_uid": placed_uid,
                            "lineage_id": placed_uid,
                            "source_entity_handle": entity_handle,
                            "source_def_handle": definition_handle,
                            "root_def_handle": root_handle,
                            "placement_path_uid": path_uid,
                            "lineage_path": copy.deepcopy(lineage_path),
                            "subentity_ordinal": ordinal,
                            "kind": str(local_segment.get("kind", "segment")),
                            "p0_world": [float(p0_world[0]), float(p0_world[1])],
                            "p1_world": [float(p1_world[0]), float(p1_world[1])],
                            "transform_flags": {
                                "mirrored": determinant < 0.0,
                                "nonuniform_scaled": nonuniform,
                                "array_member": inherited_array_member,
                            },
                        }
                    )
                    ledger["emitted_segment_instances"] += 1
                    if len(placed) > max_instances:
                        raise OracleFailure(
                            "RESOURCE_MAX_INSTANCES",
                            f"maximum segment instances {max_instances} exceeded",
                            entity_handle=entity_handle,
                            source_def_handle=definition_handle,
                            placement_path_uid=path_uid,
                        )
                emitted_count = len(placed) - before
                if emitted_count != expected_count:
                    raise OracleFailure(
                        "SILENT_DROP",
                        f"entity {entity_handle}: transformed emission mismatch",
                        entity_handle=entity_handle,
                        source_def_handle=definition_handle,
                        placement_path_uid=path_uid,
                    )
                ledger["entity_entries"].append(
                    {
                        "source_def_handle": definition_handle,
                        "source_entity_handle": entity_handle,
                        "placement_path_uid": path_uid,
                        "expected_segments": expected_count,
                        "emitted_segments": emitted_count,
                        "status": "PRESERVED",
                    }
                )

        visit(
            root_handle,
            np.identity(3, dtype=np.float64),
            root_uid,
            [],
            frozenset(),
            0,
            False,
        )

        placed_uids = [segment["placed_uid"] for segment in placed]
        if len(placed_uids) != len(set(placed_uids)):
            raise OracleFailure("DUPLICATE_PLACED_UID", "placed_uid values are not unique")
        ledger["conservation_delta"] = (
            ledger["expected_segment_instances"] - ledger["emitted_segment_instances"]
        )
        if ledger["conservation_delta"] != 0:
            raise OracleFailure(
                "SILENT_DROP",
                "global expected/emitted segment balance is non-zero",
            )
        ledger["conservation_ok"] = True
        placed.sort(key=lambda segment: segment["placed_uid"])
        for index, segment in enumerate(placed, start=1):
            segment["sid"] = f"s{index:06d}"
        status = "PASS"
    except OracleFailure as exc:
        failures.append(exc.as_dict())
        ledger["discarded_partial_segments"] = len(placed)
        ledger["conservation_delta"] = (
            ledger["expected_segment_instances"] - ledger["emitted_segment_instances"]
        )
        ledger["conservation_ok"] = False
        placed = []
        status = "FAIL"

    return {
        "oracle": ORACLE_VERSION,
        "status": status,
        "drawing_id": drawing_id,
        "input_mode": input_mode,
        "segments": placed,
        "conservation_ledger": ledger,
        "failure_ledger": failures,
    }


@dataclass(frozen=True)
class ExpectedSegment:
    handle: str
    local_points: tuple[tuple[float, float], tuple[float, float]]
    world_points: tuple[tuple[float, float], tuple[float, float]]
    world_matrix: np.ndarray


@dataclass(frozen=True)
class SelfTestResult:
    name: str
    passed: bool
    detail: str


def _canonical_pair(points: Iterable[Sequence[float]]) -> tuple[tuple[float, float], tuple[float, float]]:
    pair = [tuple(float(value) for value in point[:2]) for point in points]
    if len(pair) != 2:
        raise ValueError("expected two endpoints")
    pair.sort()
    return pair[0], pair[1]


def _expected(
    handle: str,
    local_points: Sequence[Sequence[float]],
    world_points: Sequence[Sequence[float]],
    matrix: Sequence[Sequence[float]],
) -> ExpectedSegment:
    return ExpectedSegment(
        handle=handle,
        local_points=_canonical_pair(local_points),
        world_points=_canonical_pair(world_points),
        world_matrix=np.asarray(matrix, dtype=np.float64),
    )


def _normal_case(
    name: str,
    ir: Mapping[str, Any],
    expected: Sequence[ExpectedSegment],
    *,
    extra: Callable[[dict[str, Any]], tuple[bool, str]] | None = None,
) -> SelfTestResult:
    result = expand_world_ir(ir)
    segments = result["segments"]
    ledger = result["conservation_ledger"]
    if result["status"] != "PASS":
        return SelfTestResult(name, False, f"unexpected status={result['status']} failures={result['failure_ledger']}")
    if len(segments) != len(expected):
        return SelfTestResult(name, False, f"instance count got={len(segments)} want={len(expected)}")

    actual_sorted = sorted(
        segments,
        key=lambda segment: (
            segment["source_entity_handle"],
            tuple(segment["p0_world"]),
            tuple(segment["p1_world"]),
        ),
    )
    expected_sorted = sorted(
        expected,
        key=lambda segment: (segment.handle, segment.world_points[0], segment.world_points[1]),
    )
    max_error = 0.0
    max_inverse_error = 0.0
    all_expected_points: list[tuple[float, float]] = []
    for actual, wanted in zip(actual_sorted, expected_sorted):
        if actual["source_entity_handle"] != wanted.handle:
            return SelfTestResult(
                name,
                False,
                f"source handle got={actual['source_entity_handle']} want={wanted.handle}",
            )
        actual_world = np.asarray([actual["p0_world"], actual["p1_world"]], dtype=np.float64)
        wanted_world = np.asarray(wanted.world_points, dtype=np.float64)
        max_error = max(max_error, float(np.max(np.abs(actual_world - wanted_world))))
        all_expected_points.extend(wanted.world_points)

        inverse = np.linalg.inv(wanted.world_matrix)
        recovered = []
        for point in actual_world:
            recovered.append(_apply(inverse, point))
        recovered_pair = np.asarray(_canonical_pair(recovered), dtype=np.float64)
        wanted_local = np.asarray(wanted.local_points, dtype=np.float64)
        max_inverse_error = max(
            max_inverse_error,
            float(np.max(np.abs(recovered_pair - wanted_local))),
        )

    coords = np.asarray(all_expected_points, dtype=np.float64)
    extent = 0.0
    if coords.size:
        extent = float(max(np.ptp(coords[:, 0]), np.ptp(coords[:, 1])))
    tolerance = 1e-9 * max(1.0, extent)
    uids = [segment["placed_uid"] for segment in segments]
    conditions = [
        max_error <= tolerance,
        max_inverse_error <= tolerance,
        len(uids) == len(set(uids)),
        bool(ledger["conservation_ok"]),
        ledger["expected_segment_instances"] == len(expected),
        ledger["emitted_segment_instances"] == len(expected),
    ]
    extra_detail = ""
    if extra is not None:
        extra_ok, extra_detail = extra(result)
        conditions.append(extra_ok)
    detail = (
        f"n={len(segments)} max_error={max_error:.3e} "
        f"inverse_error={max_inverse_error:.3e} tol={tolerance:.3e} "
        f"conservation={ledger['expected_segment_instances']}/{ledger['emitted_segment_instances']}"
    )
    if extra_detail:
        detail += f" {extra_detail}"
    return SelfTestResult(name, all(conditions), detail)


def _failure_case(
    name: str,
    ir: Mapping[str, Any],
    expected_code: str,
    *,
    emitter: Callable[[Mapping[str, Any]], list[dict[str, Any]]] = _normalize_entity,
) -> SelfTestResult:
    result = expand_world_ir(ir, _emitter=emitter)
    codes = [entry["code"] for entry in result["failure_ledger"]]
    passed = result["status"] == "FAIL" and result["segments"] == [] and expected_code in codes
    detail = (
        f"status={result['status']} codes={codes} output_segments={len(result['segments'])} "
        f"discarded={result['conservation_ledger']['discarded_partial_segments']}"
    )
    return SelfTestResult(name, passed, detail)


def _graph(
    definitions: Mapping[str, Any],
    *,
    root: str = "D0",
    drawing_id: str = "fixture",
) -> dict[str, Any]:
    return {
        "ir": "worldir.input.v1",
        "drawing_id": drawing_id,
        "root": root,
        "definitions": definitions,
    }


def _definition(handle: str, entities: Sequence[Mapping[str, Any]], base: Sequence[float] = (0, 0)) -> dict[str, Any]:
    return {"handle": handle, "base_point": list(base), "entities": [dict(item) for item in entities]}


def _line(handle: str, p0: Sequence[float], p1: Sequence[float], **extra: Any) -> dict[str, Any]:
    out = {"kind": "LINE", "handle": handle, "points": [list(p0), list(p1)]}
    out.update(extra)
    return out


def _insert(handle: str, target: str, point: Sequence[float] = (0, 0), **extra: Any) -> dict[str, Any]:
    out = {"kind": "INSERT", "handle": handle, "target": target, "insert": list(point)}
    out.update(extra)
    return out


def run_selftest() -> tuple[list[SelfTestResult], str]:
    """Run the fixed, deterministic transform/integrity battery."""

    tests: list[SelfTestResult] = []
    identity = np.identity(3)

    tests.append(
        _normal_case(
            "identity_modelspace",
            _graph({"D0": _definition("D0", [_line("E0", (0, 0), (4, 2))])}),
            [_expected("E0", ((0, 0), (4, 2)), ((0, 0), (4, 2)), identity)],
        )
    )

    translation_matrix = [[1, 0, 10], [0, 1, -3], [0, 0, 1]]
    tests.append(
        _normal_case(
            "translation",
            _graph(
                {
                    "D0": _definition("D0", [_insert("I0", "D1", (10, -3))]),
                    "D1": _definition("D1", [_line("E1", (1, 2), (5, 2))]),
                }
            ),
            [_expected("E1", ((1, 2), (5, 2)), ((11, -1), (15, -1)), translation_matrix)],
        )
    )

    rotation_matrix = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
    tests.append(
        _normal_case(
            "rotation_90",
            _graph(
                {
                    "D0": _definition("D0", [_insert("I0", "D1", rotation_deg=90)]),
                    "D1": _definition("D1", [_line("E1", (1, 0), (3, 0))]),
                }
            ),
            [_expected("E1", ((1, 0), (3, 0)), ((0, 1), (0, 3)), rotation_matrix)],
        )
    )

    uniform_matrix = [[2, 0, 5], [0, 2, 7], [0, 0, 1]]
    tests.append(
        _normal_case(
            "uniform_scale",
            _graph(
                {
                    "D0": _definition("D0", [_insert("I0", "D1", (5, 7), scale=[2, 2])]),
                    "D1": _definition("D1", [_line("E1", (0, 0), (2, 1))]),
                }
            ),
            [_expected("E1", ((0, 0), (2, 1)), ((5, 7), (9, 9)), uniform_matrix)],
        )
    )

    nonuniform_matrix = [[0, -3, 10], [2, 0, -5], [0, 0, 1]]
    tests.append(
        _normal_case(
            "rotation_nonuniform_scale",
            _graph(
                {
                    "D0": _definition(
                        "D0",
                        [_insert("I0", "D1", (10, -5), rotation_deg=90, scale=[2, 3])],
                    ),
                    "D1": _definition("D1", [_line("E1", (1, 2), (4, 6))]),
                }
            ),
            [_expected("E1", ((1, 2), (4, 6)), ((4, -3), (-8, 3)), nonuniform_matrix)],
            extra=lambda result: (
                result["segments"][0]["transform_flags"]["nonuniform_scaled"],
                "nonuniform_flag=true",
            ),
        )
    )

    reflection_matrix = [[-1, 0, 10], [0, 1, 0], [0, 0, 1]]
    tests.append(
        _normal_case(
            "reflection",
            _graph(
                {
                    "D0": _definition("D0", [_insert("I0", "D1", (10, 0), scale=[-1, 1])]),
                    "D1": _definition("D1", [_line("E1", (1, 2), (3, 4))]),
                }
            ),
            [_expected("E1", ((1, 2), (3, 4)), ((9, 2), (7, 4)), reflection_matrix)],
            extra=lambda result: (
                result["segments"][0]["transform_flags"]["mirrored"],
                "mirrored_flag=true",
            ),
        )
    )

    nested2_matrix = [[1, 0, 12], [0, 1, 0], [0, 0, 1]]
    tests.append(
        _normal_case(
            "nested_depth_2",
            _graph(
                {
                    "D0": _definition("D0", [_insert("I0", "D1", (10, 0))]),
                    "D1": _definition("D1", [_insert("I1", "D2", (2, 0))]),
                    "D2": _definition("D2", [_line("E2", (0, 0), (1, 0))]),
                }
            ),
            [_expected("E2", ((0, 0), (1, 0)), ((12, 0), (13, 0)), nested2_matrix)],
            extra=lambda result: (len(result["segments"][0]["lineage_path"]) == 2, "path_depth=2"),
        )
    )

    nested3_matrix = [[0, -1, 5], [1, 0, 8], [0, 0, 1]]
    tests.append(
        _normal_case(
            "nested_depth_3",
            _graph(
                {
                    "D0": _definition("D0", [_insert("I0", "D1", (5, 5))]),
                    "D1": _definition("D1", [_insert("I1", "D2", (0, 2), rotation_deg=90)]),
                    "D2": _definition("D2", [_insert("I2", "D3", (1, 0))]),
                    "D3": _definition("D3", [_line("E3", (0, 0), (0, 1))]),
                }
            ),
            [_expected("E3", ((0, 0), (0, 1)), ((5, 8), (4, 8)), nested3_matrix)],
            extra=lambda result: (len(result["segments"][0]["lineage_path"]) == 3, "path_depth=3"),
        )
    )

    array_expected: list[ExpectedSegment] = []
    for row in range(2):
        for column in range(3):
            tx = 10 + 5 * column
            ty = 20 + 7 * row
            matrix = [[1, 0, tx], [0, 1, ty], [0, 0, 1]]
            array_expected.append(_expected("EA", ((0, 0), (1, 0)), ((tx, ty), (tx + 1, ty)), matrix))
    tests.append(
        _normal_case(
            "array_2x3",
            _graph(
                {
                    "D0": _definition(
                        "D0",
                        [
                            _insert(
                                "IA",
                                "DA",
                                (10, 20),
                                array={"rows": 2, "columns": 3, "row_spacing": 7, "column_spacing": 5},
                            )
                        ],
                    ),
                    "DA": _definition("DA", [_line("EA", (0, 0), (1, 0))]),
                }
            ),
            array_expected,
            extra=lambda result: (
                all(segment["transform_flags"]["array_member"] for segment in result["segments"]),
                "array_flags=true",
            ),
        )
    )

    base_matrix = [[1, 0, 99], [0, 1, 198], [0, 0, 1]]
    tests.append(
        _normal_case(
            "target_base_point",
            _graph(
                {
                    "D0": _definition("D0", [_insert("I0", "D1", (100, 200))]),
                    "D1": _definition("D1", [_line("E1", (1, 2), (4, 2))], base=(1, 2)),
                }
            ),
            [_expected("E1", ((1, 2), (4, 2)), ((100, 200), (103, 200)), base_matrix)],
        )
    )

    tests.append(
        _normal_case(
            "child_modelspace_combination",
            _graph(
                {
                    "D0": _definition("D0", [_line("ER", (0, 0), (2, 0)), _insert("I0", "D1", (3, 0))]),
                    "D1": _definition("D1", [_line("EC", (0, 1), (2, 1))]),
                }
            ),
            [
                _expected("ER", ((0, 0), (2, 0)), ((0, 0), (2, 0)), identity),
                _expected("EC", ((0, 1), (2, 1)), ((3, 1), (5, 1)), [[1, 0, 3], [0, 1, 0], [0, 0, 1]]),
            ],
        )
    )

    explicit_matrix = [[0, -2, 30], [3, 0, 40], [0, 0, 1]]
    tests.append(
        _normal_case(
            "parser_local_matrix",
            _graph(
                {
                    "D0": _definition("D0", [_insert("I0", "D1", local_matrix=explicit_matrix)]),
                    "D1": _definition("D1", [_line("E1", (1, 1), (2, 4))]),
                }
            ),
            [_expected("E1", ((1, 1), (2, 4)), ((28, 43), (22, 46)), explicit_matrix)],
        )
    )

    arc_matrix = [[2, 0, 1], [0, 2, 2], [0, 0, 1]]
    tests.append(
        _normal_case(
            "arc_chord_normalization",
            _graph(
                {
                    "D0": _definition("D0", [_insert("I0", "D1", (1, 2), scale=2)]),
                    "D1": _definition(
                        "D1",
                        [{"kind": "ARC", "handle": "EA", "center": [0, 0], "radius": 2, "start_angle_deg": 0, "end_angle_deg": 90}],
                    ),
                }
            ),
            [_expected("EA", ((0, 2), (2, 0)), ((1, 6), (5, 2)), arc_matrix)],
        )
    )

    poly_ir = _graph(
        {"D0": _definition("D0", [{"kind": "LWPOLYLINE", "handle": "EP", "points": [[0, 0], [2, 0], [2, 1]], "closed": True}])}
    )
    tests.append(
        _normal_case(
            "polyline_subentity_ordinals",
            poly_ir,
            [
                _expected("EP", ((0, 0), (2, 0)), ((0, 0), (2, 0)), identity),
                _expected("EP", ((2, 0), (2, 1)), ((2, 0), (2, 1)), identity),
                _expected("EP", ((2, 1), (0, 0)), ((2, 1), (0, 0)), identity),
            ],
            extra=lambda result: (
                {segment["subentity_ordinal"] for segment in result["segments"]} == {0, 1, 2},
                "ordinals=0,1,2",
            ),
        )
    )

    repeat_ir = _graph(
        {
            "D0": _definition("D0", [_insert("I0", "D1", (0, 0)), _insert("I1", "D1", (10, 0))]),
            "D1": _definition("D1", [_line("E1", (0, 0), (1, 0))]),
        }
    )
    tests.append(
        _normal_case(
            "repeated_placement_unique_lineage",
            repeat_ir,
            [
                _expected("E1", ((0, 0), (1, 0)), ((0, 0), (1, 0)), identity),
                _expected("E1", ((0, 0), (1, 0)), ((10, 0), (11, 0)), [[1, 0, 10], [0, 1, 0], [0, 0, 1]]),
            ],
            extra=lambda result: (
                len({segment["lineage_id"] for segment in result["segments"]}) == 2,
                "lineage_ids_unique=2",
            ),
        )
    )

    nested_array_expected = [
        _expected("E2", ((0, 0), (1, 0)), ((100, 5), (100, 7)), [[0, -2, 100], [2, 0, 5], [0, 0, 1]]),
        _expected("E2", ((0, 0), (1, 0)), ((100, 11), (100, 13)), [[0, -2, 100], [2, 0, 11], [0, 0, 1]]),
    ]
    tests.append(
        _normal_case(
            "nested_array_composition",
            _graph(
                {
                    "D0": _definition("D0", [_insert("I0", "D1", (100, 5), rotation_deg=90, scale=2)]),
                    "D1": _definition(
                        "D1",
                        [_insert("I1", "D2", array={"rows": 1, "columns": 2, "row_spacing": 0, "column_spacing": 3})],
                    ),
                    "D2": _definition("D2", [_line("E2", (0, 0), (1, 0))]),
                }
            ),
            nested_array_expected,
        )
    )

    flat_ir = {
        "ir": "seg.v1",
        "drawing_id": "flat",
        "segments": [{"sid": "s0001", "handle": "EF", "kind": "line", "pts": [[2, 3], [5, 7]]}],
    }
    tests.append(
        _normal_case(
            "flat_seg_ir_input",
            flat_ir,
            [_expected("EF", ((2, 3), (5, 7)), ((2, 3), (5, 7)), identity)],
            extra=lambda result: (result["input_mode"] == "flat_seg_ir", "input_mode=flat_seg_ir"),
        )
    )

    rename_a = _graph(
        {
            "ROOT_ALPHA": {"handle": "D0", "name": "ROOT_ALPHA", "entities": [_insert("I0", "D1", (3, 4), layer="WALL_A")]},
            "CHILD_ALPHA": {"handle": "D1", "name": "CHILD_ALPHA", "entities": [_line("E1", (0, 0), (2, 0), layer="WALL_A")]},
        },
        root="D0",
        drawing_id="rename",
    )
    rename_b = _graph(
        {
            "ROOT_OMEGA": {"handle": "D0", "name": "ROOT_OMEGA", "entities": [_insert("I0", "D1", (3, 4), layer="DO_NOT_HASH")]},
            "CHILD_OMEGA": {"handle": "D1", "name": "CHILD_OMEGA", "entities": [_line("E1", (0, 0), (2, 0), layer="RENAMED")]},
        },
        root="D0",
        drawing_id="rename",
    )
    rename_result_a = expand_world_ir(rename_a)
    rename_result_b = expand_world_ir(rename_b)
    rename_equal = (
        rename_result_a["status"] == "PASS"
        and rename_result_b["status"] == "PASS"
        and rename_result_a["segments"] == rename_result_b["segments"]
    )
    tests.append(
        SelfTestResult(
            "transform_name_rename_parity",
            rename_equal,
            f"status_a={rename_result_a['status']} status_b={rename_result_b['status']} segment_parity={rename_equal}",
        )
    )

    reorder_a = _graph({"D0": _definition("D0", [_line("E2", (2, 0), (3, 0)), _line("E1", (0, 0), (1, 0))])})
    reorder_b = _graph({"D0": _definition("D0", [_line("E1", (0, 0), (1, 0)), _line("E2", (2, 0), (3, 0))])})
    reorder_result_a = expand_world_ir(reorder_a)
    reorder_result_b = expand_world_ir(reorder_b)
    reorder_equal = reorder_result_a["segments"] == reorder_result_b["segments"]
    tests.append(
        SelfTestResult(
            "entity_reorder_determinism",
            reorder_result_a["status"] == "PASS" and reorder_result_b["status"] == "PASS" and reorder_equal,
            f"status_a={reorder_result_a['status']} status_b={reorder_result_b['status']} segment_parity={reorder_equal}",
        )
    )

    degenerate_ir = _graph({"D0": _definition("D0", [_line("E0", (1, 1), (1, 1))])})
    tests.append(_failure_case("degenerate_fail_closed", degenerate_ir, "DEGENERATE_GEOMETRY"))

    empty_ir = _graph(
        {
            "D0": _definition("D0", [_insert("I0", "EMPTY")]),
            "EMPTY": _definition("EMPTY", []),
        }
    )
    empty_result = expand_world_ir(empty_ir)
    empty_ledger = empty_result["conservation_ledger"]
    empty_ok = (
        empty_result["status"] == "PASS"
        and empty_result["segments"] == []
        and empty_ledger["empty_block_placements"] == 1
        and empty_ledger["conservation_ok"]
        and len(empty_ledger["zero_output_entries"]) == 1
    )
    tests.append(
        SelfTestResult(
            "empty_block_audited",
            empty_ok,
            f"status={empty_result['status']} empty_placements={empty_ledger['empty_block_placements']} zero_entries={len(empty_ledger['zero_output_entries'])}",
        )
    )

    cycle_ir = _graph(
        {
            "D0": _definition("D0", [_insert("I0", "D1")]),
            "D1": _definition("D1", [_insert("I1", "D0")]),
        }
    )
    tests.append(_failure_case("cycle_reference_defense", cycle_ir, "GRAPH_CYCLE"))

    missing_ir = _graph({"D0": _definition("D0", [_insert("I0", "DOES_NOT_EXIST")])})
    tests.append(_failure_case("missing_target_fail_closed", missing_ir, "MISSING_TARGET"))

    singular_ir = _graph(
        {
            "D0": _definition("D0", [_insert("I0", "D1", scale=[0, 1])]),
            "D1": _definition("D1", [_line("E1", (0, 0), (1, 0))]),
        }
    )
    tests.append(_failure_case("singular_transform_fail_closed", singular_ir, "SINGULAR_TRANSFORM"))

    nonfinite_ir = _graph({"D0": _definition("D0", [_line("E0", (0, 0), (math.inf, 1))])})
    tests.append(_failure_case("nonfinite_geometry_fail_closed", nonfinite_ir, "NONFINITE_GEOMETRY"))

    def dropping_emitter(entity: Mapping[str, Any]) -> list[dict[str, Any]]:
        del entity
        return []

    drop_ir = _graph({"D0": _definition("D0", [_line("E0", (0, 0), (1, 0))])})
    tests.append(_failure_case("silent_drop_detector", drop_ir, "SILENT_DROP", emitter=dropping_emitter))

    passed = sum(result.passed for result in tests)
    lines = [
        "WORLDIR ORACLE SELFTEST",
        f"oracle={ORACLE_VERSION}",
        f"python={platform.python_version()} numpy={np.__version__}",
        "coordinate_contract=column-vector T_parent @ T_insert_local @ T_array_cell",
        "normal_tolerance=1e-9 * max(1, fixture_extent)",
        "-" * 88,
    ]
    for result in tests:
        lines.append(f"[{('PASS' if result.passed else 'FAIL')}] {result.name}: {result.detail}")
    lines.extend(
        [
            "-" * 88,
            f"SUMMARY: {passed}/{len(tests)} cases passed",
            f"SELFTEST_RESULT: {'PASS' if passed == len(tests) else 'FAIL'}",
        ]
    )
    return tests, "\n".join(lines)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="canonical graph JSON or flat SEG-IR JSON")
    parser.add_argument("--output", help="write expanded JSON to this path (stdout when omitted)")
    parser.add_argument("--selftest", action="store_true", help="run the fixed transform/integrity battery")
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    parser.add_argument("--max-instances", type=int, default=DEFAULT_MAX_INSTANCES)
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.selftest:
        if args.input or args.output:
            print("error: --selftest does not accept input or --output", file=sys.stderr)
            return 2
        tests, report = run_selftest()
        print(report)
        return 0 if all(result.passed for result in tests) else 1

    if not args.input:
        print("error: provide an input JSON path or use --selftest", file=sys.stderr)
        return 2
    input_path = Path(args.input)
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read input JSON: {exc}", file=sys.stderr)
        return 2

    result = expand_world_ir(
        payload,
        max_depth=args.max_depth,
        max_instances=args.max_instances,
    )
    indent = None if args.compact else 2
    rendered = json.dumps(result, ensure_ascii=False, indent=indent, sort_keys=True)
    if args.output:
        try:
            Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write output JSON: {exc}", file=sys.stderr)
            return 2
    else:
        print(rendered)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
