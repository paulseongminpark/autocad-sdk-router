#!/usr/bin/env python
"""Lane B3 — DWG Graph IR builder (CAD OS Layer, Phase 2).

Normalize a ``dwg_geometry_extract.v1`` payload (the output of the
``dwg_truth_autocad`` router route: a flat list of entities shaped
``{handle, object_id, type, layer, geometry}`` plus ``summary.modelspace_count``)
into the engine-neutral ``ariadne.dwg_graph_ir.v1`` graph IR
(see schemas/dwg_graph_ir.v1.schema.json).

Stdlib only (Python 3.12). The catalog/config JSON on this box is BOM-prefixed,
so any JSON read here uses ``encoding="utf-8-sig"``.

Public API (INTERFACE CONTRACT):
    build_ir_from_extract(extract: dict, summary: dict | None, source_meta: dict) -> dict
    load_ir(path) -> dict
    write_ir(ir, path) -> str
    make_fixture_ir() -> dict          # small valid golden IR for skeleton/tests

The truth gate is ``diagnostics.entity_count == len(ir["entities"])``; cross-checking
against ``summary.modelspace_count`` produces ``diagnostics.coverage`` + warnings.
This module never fakes success: a count mismatch is recorded as a warning and
``coverage.match == False``, not silently smoothed over.
"""
from __future__ import annotations

import json
from pathlib import Path

IR_SCHEMA_ID = "ariadne.dwg_graph_ir.v1"
IR_PRODUCER_VERSION = "1.0.0"

# dwg_geometry_extract geometry.kind -> IR geometry.kind. The extract contract
# uses a narrower kind set; map straight through and fall back to "unsupported"
# for anything the extractor flagged as undecoded (no-fake-success).
_EXTRACT_KIND_TO_IR_KIND = {
    "line": "line",
    "polyline": "polyline",
    "lwpolyline": "lwpolyline",
    "arc": "arc",
    "circle": "circle",
    "ellipse": "ellipse",
    "spline": "spline",
    "point": "point",
    "text": "text",
    "mtext": "mtext",
    "block_reference": "block_reference",
    "attribute": "attribute",
    "dimension": "dimension",
    "leader": "leader",
    "hatch": "hatch",
    "solid": "solid",
    "region": "region",
    "viewport": "viewport",
    "ray": "ray",
    "xline": "xline",
    "proxy": "proxy",
    "unsupported": "unsupported",
}

# DXF type name -> runtime (AcDb*) class name, best-effort. Only used to populate
# entity.class when the extract did not carry a runtime_type. Unknown types get a
# generic "AcDbEntity" so the required field is always a non-empty string.
_DXF_TO_RUNTIME_CLASS = {
    "LINE": "AcDbLine",
    "LWPOLYLINE": "AcDbPolyline",
    "POLYLINE": "AcDb2dPolyline",
    "ARC": "AcDbArc",
    "CIRCLE": "AcDbCircle",
    "ELLIPSE": "AcDbEllipse",
    "SPLINE": "AcDbSpline",
    "POINT": "AcDbPoint",
    "TEXT": "AcDbText",
    "MTEXT": "AcDbMText",
    "INSERT": "AcDbBlockReference",
    "ATTRIB": "AcDbAttribute",
    "ATTDEF": "AcDbAttributeDefinition",
    "DIMENSION": "AcDbDimension",
    "LEADER": "AcDbLeader",
    "MLEADER": "AcDbMLeader",
    "HATCH": "AcDbHatch",
    "SOLID": "AcDbTrace",
    "3DSOLID": "AcDb3dSolid",
    "REGION": "AcDbRegion",
    "VIEWPORT": "AcDbViewport",
    "RAY": "AcDbRay",
    "XLINE": "AcDbXline",
}


# --- point / bbox normalization ------------------------------------------------

def _to_number(v):
    """Coerce a scalar to float, returning None when not numeric."""
    if isinstance(v, bool):  # bool is an int subclass; never a coordinate
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    return None


def _as_point3(p):
    """Normalize a point from any extract form into IR [x, y, z] (point3).

    Accepts dict {x,y,z} / {X,Y,Z}, list/tuple [x,y(,z)], or None.
    Missing z defaults to 0.0. Returns None when no usable point is present.
    """
    if p is None:
        return None
    if isinstance(p, dict):
        x = _to_number(p.get("x", p.get("X")))
        y = _to_number(p.get("y", p.get("Y")))
        z = _to_number(p.get("z", p.get("Z")))
        if x is None and y is None and z is None:
            return None
        return [x or 0.0, y or 0.0, z or 0.0]
    if isinstance(p, (list, tuple)):
        nums = [_to_number(c) for c in p]
        nums = [n for n in nums if n is not None]
        if not nums:
            return None
        while len(nums) < 3:
            nums.append(0.0)
        return [nums[0], nums[1], nums[2]]
    return None


def _vertex_point(v):
    """Extract a point3 from one polyline vertex (dict, point-dict, or list)."""
    if isinstance(v, dict):
        if "point" in v:
            return _as_point3(v.get("point"))
        # vertex may itself be the point dict {x,y,z}
        pt = _as_point3(v)
        if pt is not None:
            return pt
        return None
    return _as_point3(v)


def _iter_geometry_points(geom):
    """Yield every point3 referenced by a geometry payload (for bbox compute)."""
    if not isinstance(geom, dict):
        return
    for key in ("start", "end", "center", "position"):
        pt = _as_point3(geom.get(key))
        if pt is not None:
            yield pt
    for v in geom.get("vertices") or []:
        pt = _vertex_point(v)
        if pt is not None:
            yield pt
    for cp in geom.get("control_points") or []:
        pt = _as_point3(cp)
        if pt is not None:
            yield pt


def _normalize_bbox(raw_bbox, geom):
    """Return an IR bbox [minX,minY,minZ,maxX,maxY,maxZ], or [] if none.

    Priority: an explicit bbox carried on the extract entity (dict {min,max}
    or {x_min,...} or a 6-list); otherwise compute the AABB from geometry points.
    A circle/arc carrying center+radius expands the box by the radius.
    """
    box = _bbox_from_explicit(raw_bbox)
    if box is not None:
        return box

    pts = list(_iter_geometry_points(geom))

    # circle / arc: grow the AABB to the radius around the center.
    if isinstance(geom, dict):
        center = _as_point3(geom.get("center"))
        radius = _to_number(geom.get("radius"))
        if center is not None and radius is not None and radius >= 0:
            cx, cy, cz = center
            return [cx - radius, cy - radius, cz, cx + radius, cy + radius, cz]

    if not pts:
        return []
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    zs = [p[2] for p in pts]
    return [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]


def _bbox_from_explicit(raw_bbox):
    """Parse an explicit bbox the extractor may have attached. None if unusable."""
    if raw_bbox is None:
        return None
    if isinstance(raw_bbox, (list, tuple)):
        nums = [_to_number(c) for c in raw_bbox]
        if len(nums) == 6 and all(n is not None for n in nums):
            return [float(n) for n in nums]
        if len(nums) == 4 and all(n is not None for n in nums):
            # [minX,minY,maxX,maxY] -> add z=0 plane
            return [nums[0], nums[1], 0.0, nums[2], nums[3], 0.0]
        return None
    if isinstance(raw_bbox, dict):
        mn = _as_point3(raw_bbox.get("min"))
        mx = _as_point3(raw_bbox.get("max"))
        if mn is not None and mx is not None:
            return [mn[0], mn[1], mn[2], mx[0], mx[1], mx[2]]
        # flat keyed form
        x0 = _to_number(raw_bbox.get("x_min", raw_bbox.get("min_x")))
        y0 = _to_number(raw_bbox.get("y_min", raw_bbox.get("min_y")))
        z0 = _to_number(raw_bbox.get("z_min", raw_bbox.get("min_z")))
        x1 = _to_number(raw_bbox.get("x_max", raw_bbox.get("max_x")))
        y1 = _to_number(raw_bbox.get("y_max", raw_bbox.get("max_y")))
        z1 = _to_number(raw_bbox.get("z_max", raw_bbox.get("max_z")))
        if None not in (x0, y0, x1, y1):
            return [x0, y0, z0 or 0.0, x1, y1, z1 or 0.0]
        return None
    return None


# --- geometry normalization ----------------------------------------------------

def _normalize_geometry(raw_geom):
    """Normalize an extract geometry payload into an IR geometry dict.

    Always returns a dict with a valid ``kind``. Point-bearing fields are
    converted to point3 arrays; vertices are normalized to {point,...}.
    additionalProperties is open in the IR, so unknown extras pass through.
    """
    if not isinstance(raw_geom, dict):
        return {"kind": "unsupported"}

    raw_kind = raw_geom.get("kind")
    kind = _EXTRACT_KIND_TO_IR_KIND.get(
        raw_kind.lower() if isinstance(raw_kind, str) else raw_kind,
        "unsupported",
    )

    geom: dict = {"kind": kind}

    # pass through unknown/extra fields verbatim (richer engines attach extras)
    for k, v in raw_geom.items():
        if k in ("kind", "start", "end", "center", "position", "vertices",
                 "control_points", "normal", "major_axis", "scale"):
            continue
        geom[k] = v

    for key in ("start", "end", "center", "position", "normal", "major_axis", "scale"):
        pt = _as_point3(raw_geom.get(key))
        if pt is not None:
            geom[key] = pt

    verts = raw_geom.get("vertices")
    if isinstance(verts, list) and verts:
        norm_verts = []
        for v in verts:
            pt = _vertex_point(v)
            entry: dict = {}
            if pt is not None:
                entry["point"] = pt
            if isinstance(v, dict):
                for vk in ("bulge", "start_width", "end_width"):
                    if vk in v:
                        num = _to_number(v.get(vk))
                        if num is not None:
                            entry[vk] = num
            if entry:
                norm_verts.append(entry)
        if norm_verts:
            geom["vertices"] = norm_verts

    cps = raw_geom.get("control_points")
    if isinstance(cps, list) and cps:
        pts = [_as_point3(c) for c in cps]
        pts = [p for p in pts if p is not None]
        if pts:
            geom["control_points"] = pts

    return geom


# --- entity normalization ------------------------------------------------------

def _normalize_entity(raw, source_block):
    """Map one dwg_geometry_extract entity to one IR entity (all required fields)."""
    handle = str(raw.get("handle", "") or "")
    dxf_name = str(raw.get("type", "") or "")
    runtime = raw.get("runtime_type")
    if isinstance(runtime, str) and runtime:
        cls = runtime
    else:
        cls = _DXF_TO_RUNTIME_CLASS.get(dxf_name.upper(), "AcDbEntity")

    layer = raw.get("layer")
    layer = str(layer) if layer is not None else ""

    raw_geom = raw.get("geometry") or {}
    geom = _normalize_geometry(raw_geom)
    bbox = _normalize_bbox(raw.get("bbox"), raw_geom)

    decoded = geom.get("kind") != "unsupported"

    entity: dict = {
        "handle": handle,
        "class": cls,
        "dxf_name": dxf_name,
        "owner_handle": str(raw.get("owner_handle", "") or ""),
        "space": "model",
        "layer": layer,
        "bbox": bbox,
        "geometry": geom,
        "source": {
            "extractor": source_block.get("extractor", ""),
            "engine_tier": source_block.get("engine_tier", ""),
            "route": source_block.get("route", ""),
            "decoded": decoded,
        },
    }

    obj_id = raw.get("object_id")
    if obj_id is not None and obj_id != "":
        entity["object_id"] = str(obj_id)
    layout = raw.get("layout")
    if layout:
        entity["layout"] = str(layout)
    # carry XDATA through untouched if the extractor attached it
    if isinstance(raw.get("xdata"), list) and raw["xdata"]:
        entity["xdata"] = raw["xdata"]

    return entity


# --- public builder ------------------------------------------------------------

def build_ir_from_extract(extract: dict, summary: dict | None, source_meta: dict) -> dict:
    """Normalize a dwg_geometry_extract.v1 payload into a dwg_graph_ir.v1 dict.

    Args:
        extract: the extract payload (must carry ``entities``; may carry
            ``summary``, ``source``, ``extractor``, ``route``).
        summary: explicit summary override; falls back to ``extract['summary']``.
        source_meta: provenance to merge into ir.source (dwg_path, original_path,
            byte_size, sha256, extractor, engine_tier, route, ...).

    Returns:
        dict conforming to ariadne.dwg_graph_ir.v1. The truth gate
        (entity_count == len(entities)) holds by construction; the
        summary cross-check populates diagnostics.coverage + warnings.
    """
    extract = extract or {}
    summary = summary if summary is not None else (extract.get("summary") or {})
    source_meta = source_meta or {}

    entities_raw = extract.get("entities") or []

    # provenance: source_meta wins, extract.source/extractor/route fill gaps.
    extract_source = extract.get("source") or {}
    extractor = (
        source_meta.get("extractor")
        or extract.get("extractor")
        or extract_source.get("extractor")
        or "unknown"
    )
    route = source_meta.get("route") or extract.get("route") or ""
    engine_tier = source_meta.get("engine_tier") or extract_source.get("engine_tier") or ""

    source_block = {"extractor": extractor, "engine_tier": engine_tier, "route": route}

    entities = [_normalize_entity(e, source_block) for e in entities_raw]

    # symbol_tables.layers from distinct entity layers (geometry_only fidelity).
    layer_names: list[str] = []
    seen_layers = set()
    for ent in entities:
        ln = ent.get("layer", "")
        if ln not in seen_layers:
            seen_layers.add(ln)
            layer_names.append(ln)
    layers = [{"name": ln} for ln in layer_names]

    # diagnostics: entity_count is the realized length (truth-gate numerator).
    entity_count = len(entities)
    entities_by_type: dict[str, int] = {}
    proxy_undecoded = 0
    for ent in entities:
        dxf = ent.get("dxf_name", "") or ""
        entities_by_type[dxf] = entities_by_type.get(dxf, 0) + 1
        if not ent["source"].get("decoded", True):
            proxy_undecoded += 1

    modelspace_count = summary.get("modelspace_count")
    match = (modelspace_count is not None) and (modelspace_count == entity_count)

    warnings: list[str] = []
    errors: list[str] = []
    if modelspace_count is None:
        warnings.append(
            "summary.modelspace_count absent; cannot cross-check entity count"
        )
    elif not match:
        warnings.append(
            f"entity count mismatch: realized {entity_count} != "
            f"summary.modelspace_count {modelspace_count}"
        )

    diagnostics = {
        "entity_count": entity_count,
        "count_scope": "modelspace",
        "realized_entity_count": entity_count,
        "entities_by_type": entities_by_type,
        "warnings": warnings,
        "errors": errors,
        "coverage": {
            "modelspace_count_from_summary": modelspace_count,
            "realized_entity_count": entity_count,
            "match": bool(match),
            "sections_present": ["entities", "layers"],
            "sections_skipped": [
                "header_vars", "block_definitions", "xdata",
                "dictionaries", "custom_objects",
            ],
            "proxy_or_undecoded_count": proxy_undecoded,
        },
        "engines": [
            {"extractor": extractor, "engine_tier": engine_tier, "entity_count": entity_count},
        ],
    }

    source = _build_source(source_meta, extract_source, extractor, engine_tier)

    ir = {
        "schema": IR_SCHEMA_ID,
        "ir_version": IR_PRODUCER_VERSION,
        "coverage_level": "geometry_only",
        "source": source,
        "database": {"header_vars": {}},
        "symbol_tables": {"layers": layers},
        "entities": entities,
        "diagnostics": diagnostics,
    }
    return ir


def _build_source(source_meta, extract_source, extractor, engine_tier):
    """Assemble the IR source descriptor from source_meta + extract.source."""
    source: dict = {}
    # start from extract.source (string-keyed fields only), then overlay source_meta
    for key in (
        "dwg_path", "original_path", "dwg_name", "format", "dwg_version",
        "byte_size", "sha256", "mtime",
    ):
        if isinstance(extract_source, dict) and extract_source.get(key) is not None:
            source[key] = extract_source[key]
    for key, val in source_meta.items():
        if key in ("extractor", "engine_tier", "route"):
            continue
        if val is not None:
            source[key] = val
    source["extractor"] = extractor
    if engine_tier:
        # engine_tier on the source descriptor is an enum; only set when valid.
        if engine_tier in {
            "native_arx", "objectdbx", "managed", "accoreconsole_lisp", "dxf",
        }:
            source["engine_tier"] = engine_tier
    return source


# --- rich native database-graph builder (M02) ----------------------------------

# Native collectModelSpaceGraph emits dxf_name = the runtime class name
# (AcDbLine, AcDb2dPolyline, ...). Map it back to the (class, dxf_name, kind)
# triple the IR schema wants. Unknown classes pass through as class==dxf_name
# with geometry kind "unsupported" (no-fake-success).
_NATIVE_CLASS_TO_DXF_KIND = {
    "AcDbLine": ("LINE", "line"),
    "AcDbArc": ("ARC", "arc"),
    "AcDbCircle": ("CIRCLE", "circle"),
    "AcDbEllipse": ("ELLIPSE", "ellipse"),
    "AcDbPolyline": ("LWPOLYLINE", "lwpolyline"),
    "AcDb2dPolyline": ("POLYLINE", "polyline"),
    "AcDb3dPolyline": ("POLYLINE", "polyline"),
    "AcDbBlockReference": ("INSERT", "block_reference"),
    "AcDbMText": ("MTEXT", "mtext"),
    "AcDbText": ("TEXT", "text"),
    "AcDbAttributeDefinition": ("ATTDEF", "attribute"),
    "AcDbAttribute": ("ATTRIB", "attribute"),
    "AcDbHatch": ("HATCH", "hatch"),
    "AcDbSpline": ("SPLINE", "spline"),
    "AcDbPoint": ("POINT", "point"),
    "AcDbSolid": ("SOLID", "solid"),
    "AcDb3dSolid": ("3DSOLID", "solid"),
    "AcDbRegion": ("REGION", "region"),
    "AcDbViewport": ("VIEWPORT", "viewport"),
    "AcDbRotatedDimension": ("DIMENSION", "dimension"),
    "AcDbAlignedDimension": ("DIMENSION", "dimension"),
    "AcDbDimension": ("DIMENSION", "dimension"),
    "AcDbLeader": ("LEADER", "leader"),
    "AcDbMLeader": ("MULTILEADER", "leader"),
}


def _geometry_from_native_entity(raw: dict, kind: str) -> dict:
    """Lift a native graph entity's inline geometry fields into an IR geometry dict.

    The native collector writes geometry inline on the entity record (start/end,
    center/radius/angles, position/scale/rotation/block_name, text, vertices).
    Returns an IR geometry dict with a valid ``kind``; unrepresented kinds get a
    geometry that carries only ``kind`` (decoded=False is decided by the caller).
    """
    geom: dict = {"kind": kind}
    for key in ("start", "end", "center", "position", "scale", "normal"):
        pt = _as_point3(raw.get(key))
        if pt is not None:
            geom[key] = pt
    radius = _to_number(raw.get("radius"))
    if radius is not None:
        geom["radius"] = radius
    for nk, ik in (("start_angle", "start_angle"), ("end_angle", "end_angle"),
                   ("rotation", "rotation")):
        num = _to_number(raw.get(nk))
        if num is not None:
            geom[ik] = num
    if raw.get("text") is not None:
        geom["text"] = str(raw.get("text"))
    if raw.get("block_name") is not None:
        geom["block_name"] = str(raw.get("block_name"))
    verts = raw.get("vertices")
    if isinstance(verts, list) and verts:
        norm = []
        for v in verts:
            pt = _as_point3(v)
            if pt is not None:
                norm.append({"point": pt})
        if norm:
            geom["vertices"] = norm
    return geom


def _entity_from_native(raw: dict, source_block: dict) -> dict:
    """Map one native graph entity record to one IR entity (all required fields)."""
    handle = str(raw.get("handle", "") or "")
    native_class = str(raw.get("dxf_name", "") or "")  # native dxf_name == class name
    dxf_name, kind = _NATIVE_CLASS_TO_DXF_KIND.get(
        native_class, (native_class or "UNKNOWN", "unsupported"))
    layer = str(raw.get("layer", "") or "")
    geom = _geometry_from_native_entity(raw, kind)
    bbox = _normalize_bbox(None, geom)
    decoded = kind != "unsupported"

    entity: dict = {
        "handle": handle,
        "class": native_class or "AcDbEntity",
        "dxf_name": dxf_name,
        "owner_handle": str(raw.get("owner_handle", "") or ""),
        "space": str(raw.get("space", "model") or "model"),
        "layer": layer,
        "bbox": bbox,
        "geometry": geom,
        "source": {
            "extractor": source_block.get("extractor", ""),
            "engine_tier": source_block.get("engine_tier", ""),
            "route": source_block.get("route", ""),
            "decoded": decoded,
        },
    }
    if raw.get("block_record_handle"):
        entity["block_record_handle"] = str(raw["block_record_handle"])
    return entity


def build_ir_from_database_graph(graph_result: dict, source_meta: dict) -> dict:
    """Normalize a native ``inspect.database.graph`` result into dwg_graph_ir.v1.

    Args:
        graph_result: the ``result`` object of the native job result JSON
            (keys: modelspace_entities, entities[], database, symbol_tables,
            block_table_records, block_definitions, layouts, xrefs,
            dictionaries, xrecords, coverage).
        source_meta: provenance (dwg_path, original_path, byte_size, sha256, ...).

    Returns:
        dict conforming to ariadne.dwg_graph_ir.v1 at coverage_level
        "native_full". Truth gate (entity_count == len(entities)) holds by
        construction; native coverage flags are carried into diagnostics.coverage.
    """
    graph_result = graph_result or {}
    source_meta = source_meta or {}
    extractor = source_meta.get("extractor") or "native_objectarx"
    engine_tier = source_meta.get("engine_tier") or "native_arx"
    route = source_meta.get("route") or "dwg_truth_autocad"
    source_block = {"extractor": extractor, "engine_tier": engine_tier, "route": route}

    raw_entities = graph_result.get("entities") or []
    entities = [_entity_from_native(e, source_block) for e in raw_entities]

    entity_count = len(entities)
    asserted = graph_result.get("modelspace_entities")
    entities_by_type: dict[str, int] = {}
    proxy_undecoded = 0
    for ent in entities:
        dxf = ent.get("dxf_name", "") or ""
        entities_by_type[dxf] = entities_by_type.get(dxf, 0) + 1
        if not ent["source"].get("decoded", True):
            proxy_undecoded += 1

    warnings: list[str] = []
    errors: list[str] = []
    if asserted is not None and asserted != entity_count:
        warnings.append(
            f"native modelspace_entities {asserted} != realized {entity_count}")

    native_cov = graph_result.get("coverage") or {}
    sections_present = list(native_cov.get("sections_present") or [])
    if "entities" not in sections_present:
        sections_present = ["entities"] + sections_present

    # carry the native rich sections straight through (schema is additive).
    symbol_tables = graph_result.get("symbol_tables") or {}
    if "layers" not in symbol_tables:
        symbol_tables = {**symbol_tables, "layers": []}

    # block_references projection from INSERT entities (convenience index).
    block_references = []
    for ent in entities:
        if ent.get("dxf_name") == "INSERT":
            g = ent.get("geometry", {})
            block_references.append({
                "handle": ent["handle"],
                "block_name": g.get("block_name", ""),
                "block_record_handle": ent.get("block_record_handle", ""),
                "space": ent.get("space", "model"),
                "layer": ent.get("layer", ""),
                "insertion_point": g.get("position", [0.0, 0.0, 0.0]),
                "scale": g.get("scale", [1.0, 1.0, 1.0]),
                "rotation": g.get("rotation", 0.0),
            })

    diagnostics = {
        "entity_count": entity_count,
        "count_scope": "modelspace",
        "realized_entity_count": entity_count,
        "entities_by_type": entities_by_type,
        "warnings": warnings,
        "errors": errors,
        "coverage": {
            "modelspace_count_from_native": asserted,
            "realized_entity_count": entity_count,
            "match": (asserted is None) or (asserted == entity_count),
            "sections_present": sections_present,
            "sections_skipped": list(native_cov.get("sections_skipped") or []),
            "section_status": {k: v for k, v in native_cov.items()
                               if isinstance(v, str)},
            "counts": native_cov.get("counts", {}),
            "proxy_or_undecoded_count": proxy_undecoded,
        },
        "engines": [
            {"extractor": extractor, "engine_tier": engine_tier,
             "entity_count": entity_count},
        ],
    }

    source = _build_source(source_meta, {}, extractor, engine_tier)

    ir = {
        "schema": IR_SCHEMA_ID,
        "ir_version": IR_PRODUCER_VERSION,
        "coverage_level": "native_full",
        "source": source,
        "database": graph_result.get("database") or {"header_vars": {}},
        "symbol_tables": symbol_tables,
        "block_definitions": graph_result.get("block_definitions") or [],
        "block_references": block_references,
        "xrefs": graph_result.get("xrefs") or [],
        "dictionaries": graph_result.get("dictionaries") or [],
        "xrecords": graph_result.get("xrecords") or [],
        "layouts": graph_result.get("layouts") or [],
        "entities": entities,
        "diagnostics": diagnostics,
    }
    btr = graph_result.get("block_table_records")
    if btr is not None:
        ir["symbol_tables"]["block_table_records"] = btr
    return ir


def load_native_graph_result(path) -> dict:
    """Load a native job result JSON and return its ``result`` object (BOM-tolerant)."""
    doc = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return doc.get("result", doc)


# --- IO ------------------------------------------------------------------------

def load_ir(path) -> dict:
    """Load an IR JSON document (BOM-tolerant)."""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_ir(ir: dict, path) -> str:
    """Write an IR JSON document (UTF-8, pretty). Returns the path written."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ir, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(p)


# --- fixtures / validation helpers --------------------------------------------

def make_fixture_ir() -> dict:
    """Return a small, valid golden IR (used by the skeleton/tests).

    Three entities (a LINE, a CIRCLE, an INSERT) across two layers. Counts are
    internally consistent so the truth gate and the summary cross-check pass.
    """
    fake_extract = {
        "schema": "ariadne.dwg_geometry_extract.v1",
        "route": "dwg_truth_autocad",
        "extractor": "fixture_synthetic",
        "status": "ok",
        "source": {"dwg_name": "fixture.dwg", "format": "dwg"},
        "summary": {
            "modelspace_count": 3,
            "entities_by_type": {"LINE": 1, "CIRCLE": 1, "INSERT": 1},
        },
        "entities": [
            {
                "handle": "2A7", "object_id": "id-1", "type": "LINE", "layer": "0",
                "geometry": {
                    "kind": "line",
                    "start": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "end": {"x": 10.0, "y": 5.0, "z": 0.0},
                },
            },
            {
                "handle": "2A8", "object_id": "id-2", "type": "CIRCLE", "layer": "WALLS",
                "geometry": {
                    "kind": "circle",
                    "center": {"x": 5.0, "y": 5.0, "z": 0.0},
                    "radius": 2.5,
                },
            },
            {
                "handle": "2A9", "object_id": "id-3", "type": "INSERT", "layer": "WALLS",
                "geometry": {
                    "kind": "block_reference",
                    "position": {"x": 1.0, "y": 2.0, "z": 0.0},
                    "block_name": "DOOR",
                },
            },
        ],
    }
    return build_ir_from_extract(
        fake_extract,
        summary=None,
        source_meta={
            "extractor": "fixture_synthetic",
            "engine_tier": "accoreconsole_lisp",
            "route": "dwg_truth_autocad",
            "dwg_path": "staging/golden/fixture/fixture.dwg",
            "byte_size": 0,
        },
    )


def _validate_ir(ir: dict):
    """Validate an IR dict against the schema if jsonschema is importable.

    Returns (ok: bool, method: str, errors: list[str]). Falls back to structural
    checks (required keys + truth gate) when jsonschema is unavailable.
    """
    schema_path = Path(__file__).resolve().parent.parent / "schemas" / "dwg_graph_ir.v1.schema.json"
    errors: list[str] = []
    try:
        import jsonschema  # type: ignore
        schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
        validator = jsonschema.Draft7Validator(schema)
        errors = [
            f"{'/'.join(str(p) for p in e.path)}: {e.message}"
            for e in sorted(validator.iter_errors(ir), key=lambda e: list(e.path))
        ]
        return (len(errors) == 0, "jsonschema", errors[:20])
    except ImportError:
        # structural fallback
        for key in ("schema", "source", "database", "symbol_tables", "entities", "diagnostics"):
            if key not in ir:
                errors.append(f"missing top-level key: {key}")
        if ir.get("schema") != IR_SCHEMA_ID:
            errors.append(f"schema const mismatch: {ir.get('schema')!r}")
        if "layers" not in (ir.get("symbol_tables") or {}):
            errors.append("symbol_tables.layers missing")
        diag = ir.get("diagnostics") or {}
        if diag.get("entity_count") != len(ir.get("entities") or []):
            errors.append("truth gate: diagnostics.entity_count != len(entities)")
        for ent in ir.get("entities") or []:
            for rk in ("handle", "class", "dxf_name", "owner_handle", "space",
                       "layer", "bbox", "geometry", "source"):
                if rk not in ent:
                    errors.append(f"entity {ent.get('handle')!r} missing required field {rk}")
                    break
        return (len(errors) == 0, "structural", errors[:20])


# --- self-demo -----------------------------------------------------------------

def _selftest() -> int:
    """Build an IR from a tiny inline fake extract, validate, print a report."""
    ir = make_fixture_ir()
    entity_count = ir["diagnostics"]["entity_count"]
    realized = len(ir["entities"])
    coverage = ir["diagnostics"]["coverage"]

    ok, method, errors = _validate_ir(ir)

    # spot-check the LINE bbox came out right (computed from start/end)
    line = next(e for e in ir["entities"] if e["dxf_name"] == "LINE")
    line_bbox = line["bbox"]
    # spot-check the CIRCLE bbox expanded by radius
    circ = next(e for e in ir["entities"] if e["dxf_name"] == "CIRCLE")
    circ_bbox = circ["bbox"]

    print("== ir_builder self-demo ==")
    print(f"schema                : {ir['schema']}")
    print(f"entity_count          : {entity_count}")
    print(f"realized len(entities): {realized}")
    print(f"truth gate match      : {entity_count == realized}")
    print(f"summary cross-check   : match={coverage['match']} "
          f"(summary={coverage['modelspace_count_from_summary']})")
    print(f"entities_by_type      : {ir['diagnostics']['entities_by_type']}")
    print(f"layers                : {[l['name'] for l in ir['symbol_tables']['layers']]}")
    print(f"LINE bbox             : {line_bbox}")
    print(f"CIRCLE bbox (r=2.5)   : {circ_bbox}")
    print(f"validation method     : {method}")
    print(f"validation ok         : {ok}")
    if errors:
        print("validation errors:")
        for e in errors:
            print(f"  - {e}")

    truth_ok = (entity_count == realized == 3) and coverage["match"] is True
    # LINE bbox = [0,0,0,10,5,0]; CIRCLE bbox = [2.5,2.5,0,7.5,7.5,0]
    bbox_ok = (line_bbox == [0.0, 0.0, 0.0, 10.0, 5.0, 0.0]
               and circ_bbox == [2.5, 2.5, 0.0, 7.5, 7.5, 0.0])
    print(f"bbox spot-check ok    : {bbox_ok}")

    passed = ok and truth_ok and bbox_ok
    print(f"RESULT                : {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
