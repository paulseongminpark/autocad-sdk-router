"""Internal geometry/accounting helpers for the E2 phase-2 jury.

The native Graph IR already contains unsupported entity geometry and INSERT
XCLIP data.  This module traverses that native graph without projecting the
unsupported entities to line segments.  It answers the narrower, conservative
question needed before extending the adapter: can an unsupported placed entity
possibly intersect the visible region?

``POTENTIALLY_VISIBLE`` is deliberately one-sided.  A false positive is
acceptable because it sends an entity family to review; a false negative would
silently remove evidence from the wall universe.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from tools.e2.instruments import dwg_graph_to_worldir as adapter
from tools.e2.instruments import worldir_oracle as oracle


UNSUPPORTED_DXF_NAMES = frozenset(
    {
        "3DFACE",
        "CIRCLE",
        "DIMENSION",
        "ELLIPSE",
        "HATCH",
        "MTEXT",
        "POINT",
        "SPLINE",
        "TEXT",
        "WIPEOUT",
    }
)
CURVE_OR_REGION_TYPES = frozenset({"3DFACE", "CIRCLE", "ELLIPSE", "HATCH", "SPLINE", "WIPEOUT"})
ANNOTATION_TYPES = frozenset({"DIMENSION", "MTEXT", "POINT", "TEXT"})


def _native_definitions(native: Mapping[str, Any]) -> tuple[str, dict[str, dict[str, Any]]]:
    root_btr = adapter._modelspace_btr(native)
    root_handle = adapter._handle(root_btr.get("handle"), "modelspace BTR")
    definitions: dict[str, dict[str, Any]] = {
        root_handle: {
            "handle": root_handle,
            "base_point": adapter._point2(root_btr.get("origin"), "modelspace origin"),
            "entities": list(native.get("entities") or []),
        }
    }
    for raw in native.get("block_definitions") or []:
        if not isinstance(raw, Mapping):
            continue
        handle = adapter._handle(raw.get("handle"), "block definition")
        definitions[handle] = {
            "handle": handle,
            "base_point": adapter._point2(raw.get("origin"), f"block {handle} origin"),
            "entities": list(raw.get("def_entities") or []),
        }
    return root_handle, definitions


def _numeric_point(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    if isinstance(value[0], bool) or isinstance(value[1], bool):
        return None
    try:
        x, y = float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return [x, y]


def _geometry_points(value: Any) -> list[list[float]]:
    """Collect explicit native geometry landmarks without inventing curves."""

    point = _numeric_point(value)
    if point is not None:
        return [point]
    points: list[list[float]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in {"text", "kind", "closed", "measurement", "rotation", "start_angle", "end_angle"}:
                continue
            points.extend(_geometry_points(child))
        center = _numeric_point(value.get("center"))
        try:
            radius = float(value.get("radius"))
        except (TypeError, ValueError):
            radius = 0.0
        if center is not None and math.isfinite(radius) and radius > 0.0:
            points.extend(
                [
                    [center[0] - radius, center[1]],
                    [center[0] + radius, center[1]],
                    [center[0], center[1] - radius],
                    [center[0], center[1] + radius],
                ]
            )
    elif isinstance(value, (list, tuple)):
        for child in value:
            points.extend(_geometry_points(child))
    return points


def _entity_local_footprint(entity: Mapping[str, Any]) -> tuple[list[np.ndarray], str]:
    bbox = entity.get("bbox")
    if isinstance(bbox, list) and len(bbox) >= 6:
        try:
            x0, y0, x1, y1 = float(bbox[0]), float(bbox[1]), float(bbox[3]), float(bbox[4])
        except (TypeError, ValueError):
            x0 = y0 = x1 = y1 = math.nan
        if all(math.isfinite(value) for value in (x0, y0, x1, y1)):
            lo_x, hi_x = sorted((x0, x1))
            lo_y, hi_y = sorted((y0, y1))
            if math.isclose(lo_x, hi_x, abs_tol=oracle.GEOMETRY_EPSILON) and math.isclose(
                lo_y, hi_y, abs_tol=oracle.GEOMETRY_EPSILON
            ):
                return [np.asarray([lo_x, lo_y], dtype=np.float64)], "native_bbox_point"
            return (
                [
                    np.asarray([lo_x, lo_y], dtype=np.float64),
                    np.asarray([hi_x, lo_y], dtype=np.float64),
                    np.asarray([hi_x, hi_y], dtype=np.float64),
                    np.asarray([lo_x, hi_y], dtype=np.float64),
                ],
                "native_bbox",
            )
    landmarks = _geometry_points(entity.get("geometry"))
    # Some native ObjectARX fields are intentionally first-class payload
    # properties rather than nested under ``geometry``.  Missing this surface
    # would turn decoded splines into a false UNKNOWN population.
    for key in (
        "spline_control_points",
        "spline_fit_points",
        "wipeout_boundary",
        "hatch_loops",
        "vertices",
    ):
        landmarks.extend(_geometry_points(entity.get(key)))
    if not landmarks:
        return [], "no_native_footprint"
    xs = [point[0] for point in landmarks]
    ys = [point[1] for point in landmarks]
    lo_x, hi_x = min(xs), max(xs)
    lo_y, hi_y = min(ys), max(ys)
    if math.isclose(lo_x, hi_x, abs_tol=oracle.GEOMETRY_EPSILON) and math.isclose(
        lo_y, hi_y, abs_tol=oracle.GEOMETRY_EPSILON
    ):
        return [np.asarray([lo_x, lo_y], dtype=np.float64)], "geometry_landmark_point"
    return (
        [
            np.asarray([lo_x, lo_y], dtype=np.float64),
            np.asarray([hi_x, lo_y], dtype=np.float64),
            np.asarray([hi_x, hi_y], dtype=np.float64),
            np.asarray([lo_x, hi_y], dtype=np.float64),
        ],
        "geometry_landmark_bbox",
    )


def _segments(points: Sequence[np.ndarray]) -> Iterable[tuple[np.ndarray, np.ndarray]]:
    if len(points) < 2:
        return []
    return ((points[index], points[(index + 1) % len(points)]) for index in range(len(points)))


def _segments_intersect(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> bool:
    def orientation(p: np.ndarray, q: np.ndarray, r: np.ndarray) -> float:
        return oracle._cross2(q - p, r - p)

    values = (orientation(a, b, c), orientation(a, b, d), orientation(c, d, a), orientation(c, d, b))
    if values[0] * values[1] < 0.0 and values[2] * values[3] < 0.0:
        return True
    return any(
        abs(value) <= oracle.GEOMETRY_EPSILON and oracle._point_on_segment(point, p0, p1)
        for value, point, p0, p1 in (
            (values[0], c, a, b),
            (values[1], d, a, b),
            (values[2], a, c, d),
            (values[3], b, c, d),
        )
    )


def _polygons_intersect(left: Sequence[np.ndarray], right: Sequence[np.ndarray]) -> bool:
    if len(left) == 1:
        return oracle._point_in_polygon(left[0], right)
    if any(oracle._point_in_polygon(point, right) for point in left):
        return True
    if any(oracle._point_in_polygon(point, left) for point in right):
        return True
    return any(
        _segments_intersect(a, b, c, d)
        for a, b in _segments(left)
        for c, d in _segments(right)
    )


def _clip_classification(
    world_points: Sequence[np.ndarray], active_clips: Sequence[Mapping[str, Any]]
) -> tuple[str, str]:
    if not world_points:
        return "UNKNOWN_GEOMETRY", "native payload has no usable bbox or geometry landmarks"
    for clip in active_clips:
        polygon = clip["polygon"]
        inverted = bool(clip.get("inverted", False))
        if len(world_points) == 1:
            inside = oracle._point_in_polygon(world_points[0], polygon)
            allowed = not inside if inverted else inside
        elif inverted:
            # Definite exclusion is possible only when the complete conservative
            # footprint lies inside the excluded polygon.
            allowed = not all(oracle._point_in_polygon(point, polygon) for point in world_points)
        else:
            allowed = _polygons_intersect(world_points, polygon)
        if not allowed:
            return "CLIPPED_BY_FOOTPRINT_PROOF", "conservative native footprint does not intersect an active XCLIP"
    return (
        "POTENTIALLY_VISIBLE",
        "conservative footprint intersects every active XCLIP; exact rendered visibility is not claimed",
    )


def _world_bounds(points: Sequence[np.ndarray]) -> list[float] | None:
    if not points:
        return None
    return [
        float(min(point[0] for point in points)),
        float(min(point[1] for point in points)),
        float(max(point[0] for point in points)),
        float(max(point[1] for point in points)),
    ]


def audit_unsupported_visibility(native: Mapping[str, Any], *, max_depth: int = 32) -> dict[str, Any]:
    """Conservatively account placed instances of adapter-excluded entities."""

    root_handle, definitions = _native_definitions(native)
    root_uid = oracle._hash_parts("MODELSPACE_ROOT", root_handle)
    records: list[dict[str, Any]] = []
    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    by_type_status: dict[str, Counter[str]] = {}

    def visit(
        definition_handle: str,
        parent_transform: np.ndarray,
        path_uid: str,
        active_edges: frozenset[tuple[str, str, str, int, int]],
        active_clips: tuple[dict[str, Any], ...],
        depth: int,
    ) -> None:
        if depth > max_depth:
            raise ValueError(f"unsupported visibility traversal exceeded depth {max_depth}")
        definition = definitions[definition_handle]
        for entity in sorted(definition["entities"], key=lambda item: str(item.get("handle"))):
            if not isinstance(entity, Mapping):
                continue
            handle = adapter._handle(entity.get("handle"), "native entity")
            dxf_name = str(entity.get("dxf_name") or "").upper()
            if dxf_name == "INSERT":
                adapted_insert = adapter._adapt_entity(entity)
                target = str(adapted_insert["target"])
                if target not in definitions:
                    raise ValueError(f"INSERT {handle} target {target} absent from native definitions")
                rows, columns, _, _ = oracle._array_spec(adapted_insert)
                for row in range(rows):
                    for column in range(columns):
                        edge = (definition_handle, handle, target, row, column)
                        if edge in active_edges:
                            raise ValueError(f"native INSERT cycle at {handle}")
                        local = oracle.resolve_insert_transform(
                            adapted_insert, definitions[target]["base_point"], row, column
                        )
                        world = oracle._matrix3(parent_transform @ local, f"native INSERT {handle}")
                        child_uid = oracle._hash_parts(path_uid, handle, target, row, column)
                        clip = oracle._clip_spec(adapted_insert, parent_transform)
                        child_clips = active_clips + ((clip,) if clip is not None else ())
                        counts["reachable_insert_placements"] += 1
                        visit(target, world, child_uid, active_edges | {edge}, child_clips, depth + 1)
                continue
            if dxf_name not in UNSUPPORTED_DXF_NAMES:
                continue
            counts["placed_unsupported_instances"] += 1
            local_points, footprint_source = _entity_local_footprint(entity)
            world_points = [oracle._apply(parent_transform, point) for point in local_points]
            status, reason = _clip_classification(world_points, active_clips)
            counts[status.lower()] += 1
            by_type_status.setdefault(dxf_name, Counter())[status] += 1
            role = "curve_or_region" if dxf_name in CURVE_OR_REGION_TYPES else "annotation_or_point"
            placed_uid = oracle._hash_parts(path_uid, handle, "unsupported-footprint")
            record = {
                    "placed_uid": placed_uid,
                    "source_def_handle": definition_handle,
                    "source_entity_handle": handle,
                    "dxf_name": dxf_name,
                    "layer": str(entity.get("layer") or ""),
                    "analysis_role": role,
                    "status": status,
                    "reason": reason,
                    "footprint_source": footprint_source,
                    "world_bounds": _world_bounds(world_points),
                    "active_xclip_count": len(active_clips),
                }
            group_key = (
                definition_handle,
                handle,
                dxf_name,
                str(entity.get("layer") or ""),
                status,
                footprint_source,
                str(len(active_clips)),
            )
            group = grouped.setdefault(
                group_key,
                {
                    "source_def_handle": definition_handle,
                    "source_entity_handle": handle,
                    "dxf_name": dxf_name,
                    "layer": str(entity.get("layer") or ""),
                    "status": status,
                    "footprint_source": footprint_source,
                    "active_xclip_count": len(active_clips),
                    "placed_instance_count": 0,
                    "sample_placed_uids": [],
                    "world_bounds_union": None,
                },
            )
            group["placed_instance_count"] += 1
            if len(group["sample_placed_uids"]) < 5:
                group["sample_placed_uids"].append(placed_uid)
            bounds = record["world_bounds"]
            if bounds is not None:
                if group["world_bounds_union"] is None:
                    group["world_bounds_union"] = list(bounds)
                else:
                    union = group["world_bounds_union"]
                    group["world_bounds_union"] = [
                        min(union[0], bounds[0]),
                        min(union[1], bounds[1]),
                        max(union[2], bounds[2]),
                        max(union[3], bounds[3]),
                    ]
            # Store exact placed records only for the populations that may
            # change the adapter decision. Proven-clipped instances remain
            # fully counted but are compressed by source template.
            if status != "CLIPPED_BY_FOOTPRINT_PROOF":
                records.append(record)

    visit(root_handle, np.identity(3, dtype=np.float64), root_uid, frozenset(), (), 0)
    records.sort(key=lambda row: row["placed_uid"])
    potential_curve_types = sorted(
        dxf_name
        for dxf_name, statuses in by_type_status.items()
        if dxf_name in CURVE_OR_REGION_TYPES and statuses["POTENTIALLY_VISIBLE"] > 0
    )
    return {
        "schema": "e2.unsupported_visibility_audit.v1",
        "status": "PARTIAL_PASS" if counts["unknown_geometry"] else "PASS",
        "method": "conservative native bbox/geometry-landmark intersection through the exact INSERT/XCLIP stack",
        "one_sided_contract": "POTENTIALLY_VISIBLE may over-include; CLIPPED_BY_FOOTPRINT_PROOF must not hide a visible footprint",
        "counts": dict(sorted(counts.items())),
        "by_dxf_name_and_status": {
            key: dict(sorted(value.items())) for key, value in sorted(by_type_status.items())
        },
        "potentially_visible_curve_or_region_types": potential_curve_types,
        "adapter_extension_decision": {
            "status": "REQUALIFY_BEFORE_EXTENSION" if potential_curve_types else "NO_EXTENSION_NEEDED_FOR_THIS_DRAWING",
            "reason": (
                "A potentially visible excluded curve/region family exists. Extending the projection changes the analysis universe and requires a new qualification run."
                if potential_curve_types
                else "No excluded curve/region footprint can reach the visible XCLIP region in this drawing."
            ),
        },
        "record_contract": "records contains every POTENTIALLY_VISIBLE or UNKNOWN placed instance; proven-clipped instances are losslessly counted in grouped_records",
        "records": records,
        "grouped_records": sorted(
            grouped.values(),
            key=lambda row: (
                row["dxf_name"],
                row["source_def_handle"],
                row["source_entity_handle"],
                row["status"],
            ),
        ),
    }
