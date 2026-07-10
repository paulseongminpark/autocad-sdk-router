#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_ops.blocks -- block / insert / BTR write ops (CAD OS Layer, Lane E
family split).

p2-blockapp wave: two ops gain their first-ever patch_ops wiring.
  create_block         -> write.block.simple_create (createSimpleBlock,
                          AriadneNativeJob.cpp) -- creates a NEW named block
                          table record (idempotent: a no-op if the name
                          already exists) seeded with one hardcoded line;
                          already real/certified, just never exposed here.
  append_block_entity  -> write.block.append_entity (m08eHandleBlockAppend,
                          families/m08e_handlers.inc) -- graduated from an
                          always-rollback probe to a REAL, persisting write in
                          this same wave (see that file's header comment).
                          Appends one of {line,circle,arc,text,ellipse,point,
                          spline,lwpolyline,polyline,block_reference} into a
                          NAMED block-table record (or model space if
                          'block_name' is omitted).
create_blockref (write.entity.blockref, the INSERT itself) is registered in
patch_ops.entities (its kind=="block_reference" IR-op-case), not this
family -- w3-insert wired the WRITE_OP_MAP/build_job_args side there, but
(cb2-irmap/#129b) the ir_op_for side was never added, so this module's own
ir_op_for used to fill the gap with an "insert_block" op id no registry
entry declares (regen/journal.json's "insert_block is not declared"
warning -- an active fake-success this module's own docstring already
called out as merely "degrading to deferred", which the code did not
actually do). Fixed by adding the missing case to entities.py and deleting
it here; this family's ir_op_for now returns None for every kind (it maps
no IR kind of its own).

p3-insattr (same wave, concurrent lane) independently wired the SAME native
op under a second patch-op id: create_block_simple (write.block.
simple_create), used as the setup step for an ATTDEF-in-block-definition +
INSERT-with-attributes multi-op patch (see op_roundtrip_probe.py's
probe_insert_attributes_roundtrip). Both aliases are kept -- each lane's
oracle/probe references its own id, and two patch-op ids mapping to one
native op is an established pattern (create_polyline2d).

cb2-irmap/#129b block-def dependency: create_blockref only succeeds against
a target whose block table already has the referenced name (m08g_handlers.
inc's write.entity.blockref branch returns BLOCK_NOT_FOUND otherwise) --
true for a fresh/blank regen seed, which starts with none of the source
DWG's custom blocks. block_def_ops() below synthesizes that block-def (a
create_block plus one append_block_entity per def_entity write.block.
append_entity's native handler can represent) from the source IR's own
block_definitions[] entry, so ir_to_patch.build_patch_from_ir can emit it
ahead of the first create_blockref referencing that name.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

# patch op id -> native ObjectARX write op (operations.v2.json, status
# "implemented"). Only entries with a live native handler belong here.
WRITE_OP_MAP: Dict[str, str] = {
    "create_block": "write.block.simple_create",
    "append_block_entity": "write.block.append_entity",
    "create_block_simple": "write.block.simple_create",
}

_UNSUPPORTED_APPEND_REASON = "def_entity kind unsupported by write.block.append_entity"
_GRADIENT_HATCH_DEFER_REASON = _UNSUPPORTED_APPEND_REASON + " (no gradient replay)"
_CUSTOM_HATCH_DEFER_REASON = (_UNSUPPORTED_APPEND_REASON
                              + " (custom hatch pattern replay pending .pat synthesis)")
_UNSUPPORTED_HATCH_EDGE_REASON = _UNSUPPORTED_APPEND_REASON + " (unsupported edge type in loop)"
_WIPEOUT_EXTERNAL_IMAGE_DEFER_REASON = (_UNSUPPORTED_APPEND_REASON
                                        + " (external raster image wipeout)")
_WIPEOUT_MISSING_CLIP_DEFER_REASON = (_UNSUPPORTED_APPEND_REASON
                                      + " (missing clip_boundary)")
_WIPEOUT_INCOMPLETE_GEOMETRY_REASON = (_UNSUPPORTED_APPEND_REASON
                                       + " (incomplete wipeout geometry)")
_SUPPORTED_HATCH_EDGE_TYPES = frozenset({"line", "arc", "ellipse", "spline"})

# acad.pat standard pattern names resolvable headless via kPreDefined.
# Anything else is drawing-custom and must wait for definition-line replay.
_STANDARD_HATCH_PATTERNS = frozenset({
    "SOLID", "ANGLE", "ANSI31", "ANSI32", "ANSI33", "ANSI34", "ANSI35",
    "ANSI36", "ANSI37", "ANSI38", "BOX", "BRASS", "BRICK", "BRSTONE", "CLAY",
    "CORK", "CROSS", "DASH", "DOLMIT", "DOTS", "EARTH", "ESCHER", "FLEX",
    "GRASS", "GRATE", "GRAVEL", "HEX", "HONEY", "HOUND", "INSUL", "LINE",
    "MUDST", "NET", "NET3", "PLAST", "PLASTI", "SACNCR", "SQUARE", "STARS",
    "STEEL", "SWAMP", "TRANS", "TRIANG", "ZIGZAG",
})


def build_job_args(native_op: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Native job "args" for a block-family write op, or None if native_op
    isn't ours."""
    if native_op == "write.block.simple_create":
        out: Dict[str, Any] = {}
        if "name" in args:
            out["name"] = args["name"]
        # Passthrough only: block_def_ops emits seed_line=0 for SYNTHESIS
        # create_block ops (suppresses the op's self-test heritage line, the
        # measured "+1 per def" drift). create_block_simple keeps its legacy
        # certified behavior by simply not carrying the key. Numeric 0/1 on
        # purpose: the native handler reads it via jsonFindNumber.
        if "seed_line" in args:
            out["seed_line"] = args["seed_line"]
        return out
    if native_op == "write.block.append_entity":
        # Flat passthrough is correct here even though "entity" is itself a
        # nested {kind,...} object: m08eHandleBlockAppend/m08eBuildEntityForAppend
        # (m08e_handlers.inc) do their OWN nested jsonFindString/jsonFindObject
        # parsing of the "entity" sub-object out of the native job JSON, so no
        # per-field flattening belongs on the Python side.
        out = {}
        for k in ("block_name", "entity", "layer"):
            if k in args:
                out[k] = args[k]
        return out
    return None


def _pt(arr: Any) -> Optional[Dict[str, float]]:
    """IR coordinate array [x,y,z] -> native job object {x,y,z}."""
    if not arr:
        return None
    return {"x": arr[0], "y": arr[1], "z": arr[2] if len(arr) > 2 else 0.0}


def _points2d(vertices: Any, *, include_widths: bool = False) -> List[Dict[str, float]]:
    out: List[Dict[str, float]] = []
    for v in (vertices or []):
        p = v.get("point") if isinstance(v, dict) else v
        if not p:
            continue
        item: Dict[str, float] = {
            "x": p[0],
            "y": p[1],
            "bulge": (v.get("bulge", 0.0) if isinstance(v, dict) else 0.0),
        }
        if include_widths:
            item["start_width"] = v.get("start_width", 0.0) if isinstance(v, dict) else 0.0
            item["end_width"] = v.get("end_width", 0.0) if isinstance(v, dict) else 0.0
        out.append(item)
    return out


def _common_vertex_z(vertices: Any) -> float:
    """Common z of a vertex list, or 0.0 when absent/mixed.

    The census extractor writes lwpolyline vertices as OCS [x, y, z] with z =
    the entity's elevation on every vertex; a mixed-z list is not a planar
    lwpolyline and returns 0.0 (fail-safe: no carry, honest mismatch)."""
    zs: List[float] = []
    for v in (vertices or []):
        p = v.get("point") if isinstance(v, dict) else v
        if not p or len(p) < 3 or not isinstance(p[2], (int, float)):
            return 0.0
        zs.append(float(p[2]))
    if not zs:
        return 0.0
    z0 = zs[0]
    return z0 if all(abs(z - z0) <= 1e-9 for z in zs) else 0.0


def _points3d(vertices: Any) -> List[Dict[str, float]]:
    out: List[Dict[str, float]] = []
    for v in (vertices or []):
        p = v.get("point") if isinstance(v, dict) else v
        pt = _pt(p)
        if pt is not None:
            out.append(pt)
    return out


def _is_numeric_array(value: Any, *, min_len: int) -> bool:
    return isinstance(value, (list, tuple)) and len(value) >= min_len


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_flag_like(value: Any) -> bool:
    return isinstance(value, bool) or _is_number(value)


def _is_point2d_array(points: Any, *, min_len: int = 1) -> bool:
    return (isinstance(points, list)
            and len(points) >= min_len
            and all(_is_numeric_array(point, min_len=2) for point in points))


def _is_hatch_polyline_loop(loop: Any) -> bool:
    if not isinstance(loop, dict):
        return False
    vertices = loop.get("vertices")
    if not isinstance(vertices, list) or len(vertices) < 3:
        return False
    for vertex in vertices:
        point = vertex.get("point") if isinstance(vertex, dict) else vertex
        if not _is_numeric_array(point, min_len=2):
            return False
    return True


def _is_hatch_supported_edge(edge: Any) -> bool:
    if not isinstance(edge, dict):
        return False
    edge_type = edge.get("type")
    if edge_type == "line":
        return (_is_numeric_array(edge.get("start"), min_len=2)
                and _is_numeric_array(edge.get("end"), min_len=2))
    if edge_type == "arc":
        return (_is_numeric_array(edge.get("center"), min_len=2)
                and _is_number(edge.get("radius"))
                and _is_number(edge.get("start_angle"))
                and _is_number(edge.get("end_angle"))
                and _is_flag_like(edge.get("ccw")))
    if edge_type == "ellipse":
        return (_is_numeric_array(edge.get("center"), min_len=2)
                and _is_numeric_array(edge.get("major"), min_len=2)
                and _is_number(edge.get("ratio"))
                and _is_number(edge.get("start_angle"))
                and _is_number(edge.get("end_angle"))
                and _is_flag_like(edge.get("ccw")))
    if edge_type == "spline":
        control = edge.get("control")
        weights = edge.get("weights")
        rational = edge.get("rational")
        if (not _is_number(edge.get("degree"))
                or not _is_point2d_array(control)
                or not isinstance(edge.get("knots"), list)
                or not edge.get("knots")
                or not _is_flag_like(rational)):
            return False
        if weights is not None and not isinstance(weights, list):
            return False
        if bool(rational) and len(weights or []) != len(control):
            return False
        return True
    return False


def _is_hatch_edge_loop(loop: Any) -> bool:
    if not isinstance(loop, dict):
        return False
    edges = loop.get("edges")
    if not isinstance(edges, list) or not edges:
        return False
    return all(_is_hatch_supported_edge(edge) for edge in edges)


def _has_hatch_representable_loops(loops: Any) -> bool:
    if not isinstance(loops, list) or not loops:
        return False
    for loop in loops:
        if _is_hatch_polyline_loop(loop) or _is_hatch_edge_loop(loop):
            continue
        return False
    return True


def _has_hatch_unsupported_edge_type(loops: Any) -> bool:
    if not isinstance(loops, list):
        return False
    for loop in loops:
        if not isinstance(loop, dict):
            continue
        edges = loop.get("edges")
        if not isinstance(edges, list):
            continue
        for edge in edges:
            edge_type = edge.get("type") if isinstance(edge, dict) else None
            if isinstance(edge_type, str) and edge_type.startswith("unsupported_"):
                return True
            if edge_type not in _SUPPORTED_HATCH_EDGE_TYPES:
                if isinstance(edge_type, str) and edge_type.startswith("unsupported_"):
                    return True
                continue
    return False


def _has_hatch_polyline_loops(loops: Any) -> bool:
    if not isinstance(loops, list) or not loops:
        return False
    for loop in loops:
        if not _is_hatch_polyline_loop(loop):
            return False
    return True


def _is_custom_hatch_pattern(g: Dict[str, Any]) -> bool:
    return (not bool(g.get("is_solid_fill"))
            and str(g.get("pattern_name") or "").upper() not in _STANDARD_HATCH_PATTERNS)


def _has_hatch_pattern_definitions(g: Dict[str, Any]) -> bool:
    return bool(g.get("pattern_definitions"))


def _has_wipeout_clip_boundary(g: Dict[str, Any]) -> bool:
    clip = g.get("clip_boundary")
    return (isinstance(clip, list)
            and len(clip) > 0
            and all(_is_numeric_array(pt, min_len=2) for pt in clip))


def _has_wipeout_external_source(g: Dict[str, Any]) -> bool:
    src = g.get("source_file_name")
    return isinstance(src, str) and src.strip() != ""


def _is_wipeout_representable(g: Dict[str, Any]) -> bool:
    # Field set mirrors m08eBuildExtendedEntityForAppend kind=wipeout
    # (families/m08e_handlers.inc): origin/u_vector/v_vector/image_size,
    # clip_boundary_type, clip_boundary, source_file_name, frame_on.
    return (_is_numeric_array(g.get("origin"), min_len=3)
            and _is_numeric_array(g.get("u_vector"), min_len=3)
            and _is_numeric_array(g.get("v_vector"), min_len=3)
            and _is_numeric_array(g.get("image_size"), min_len=2)
            and _is_number(g.get("clip_boundary_type"))
            and _has_wipeout_clip_boundary(g)
            and _is_flag_like(g.get("frame_on"))
            and not _has_wipeout_external_source(g))


def _def_entity_append_reason(def_ent: Dict[str, Any]) -> str:
    g = def_ent.get("geometry") or {}
    if g.get("kind") == "hatch":
        if bool(g.get("is_gradient")):
            return _GRADIENT_HATCH_DEFER_REASON
        if g.get("pattern_name") and _is_custom_hatch_pattern(g) and not _has_hatch_pattern_definitions(g):
            return _CUSTOM_HATCH_DEFER_REASON
        if _has_hatch_unsupported_edge_type(g.get("loops")):
            return _UNSUPPORTED_HATCH_EDGE_REASON
    if g.get("kind") == "wipeout":
        if _has_wipeout_external_source(g):
            return _WIPEOUT_EXTERNAL_IMAGE_DEFER_REASON
        if not _has_wipeout_clip_boundary(g):
            return _WIPEOUT_MISSING_CLIP_DEFER_REASON
        return _WIPEOUT_INCOMPLETE_GEOMETRY_REASON
    return _UNSUPPORTED_APPEND_REASON


def ir_op_for(ent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Block family maps no IR entity ``kind`` of its own -- create_blockref
    (kind=="block_reference") is entities.py's case; see module docstring."""
    return None


def _def_entity_append_op(block_name: str, def_ent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One block_definitions[].def_entities[] item -> an append_block_entity
    op targeting ``block_name``, or None if this def_entity's kind is not one
    of the kinds write.block.append_entity's native handler can build."""
    g = def_ent.get("geometry") or {}
    kind = g.get("kind")
    layer = def_ent.get("layer")
    native_class = def_ent.get("class")
    entity: Optional[Dict[str, Any]] = None
    if kind == "line":
        entity = {"kind": "line", "start": _pt(g.get("start")), "end": _pt(g.get("end"))}
    elif kind == "circle":
        entity = {"kind": "circle", "center": _pt(g.get("center")), "radius": g.get("radius")}
    elif kind == "arc":
        entity = {"kind": "arc", "center": _pt(g.get("center")), "radius": g.get("radius"),
                  "start_angle": g.get("start_angle"), "end_angle": g.get("end_angle")}
    elif kind == "text":
        entity = {"kind": "text", "position": _pt(g.get("position")), "text": g.get("text"),
                  "height": g.get("height", 2.5)}
    elif kind == "ellipse":
        entity = {"kind": "ellipse", "center": _pt(g.get("center")), "normal": _pt(g.get("normal")),
                  "major_axis": _pt(g.get("major_axis")), "radius_ratio": g.get("radius_ratio"),
                  "start_angle": g.get("start_angle"), "end_angle": g.get("end_angle")}
    elif kind == "point":
        entity = {"kind": "point", "position": _pt(g.get("position"))}
    elif kind == "spline":
        control_points = def_ent.get("spline_control_points")
        if control_points is None:
            control_points = g.get("control_points")
        # Extractor emits spline data at the def-entity top level, not inside
        # geometry: knots MUST ride along -- the native builder fail-louds on
        # control_points without knots (measured: 45/45 b010 errors on R4).
        knots = def_ent.get("spline_knots")
        if knots is None:
            knots = g.get("knots")
        weights = def_ent.get("spline_weights")
        if weights is None:
            weights = g.get("weights")
        entity = {"kind": "spline",
                  "fit_points": list(g.get("fit_points") or []),
                  "control_points": list(control_points or []),
                  "degree": g.get("degree"),
                  "closed": g.get("closed")}
        if knots:
            entity["knots"] = list(knots)
        if weights:
            entity["weights"] = list(weights)
    elif kind == "lwpolyline":
        entity = {"kind": "lwpolyline", "points": _points2d(g.get("vertices")),
                  "closed": int(bool(g.get("closed")))}
        if "const_width" in g:
            entity["const_width"] = g.get("const_width")
        # LWPOLYLINE geometry has no elevation field in the IR -- the OCS
        # elevation rides baked into every census vertex point's z (measured
        # R4s, reports/interior100/loops_residue_analysis_R4s.json: 25
        # residual pairs, all vertices z=0.4010621945564553, replay
        # flattened them to 0.0 because nothing carried it). A planar
        # lwpolyline has one common z; carry it so m08e can setElevation.
        elevation = _common_vertex_z(g.get("vertices"))
        if elevation:
            entity["elevation"] = elevation
    elif kind == "polyline":
        if native_class == "AcDb3dPolyline":
            entity = {"kind": "polyline", "class": native_class, "points": _points3d(g.get("vertices"))}
        else:
            entity = {"kind": "polyline",
                      "points": _points2d(g.get("vertices"), include_widths=True),
                      "closed": int(bool(g.get("closed"))),
                      "elevation": g.get("elevation", 0.0),
                      "default_start_width": g.get("default_start_width", 0.0),
                      "default_end_width": g.get("default_end_width", 0.0)}
            if native_class:
                entity["class"] = native_class
    elif kind == "block_reference":
        nested_name = g.get("block_name")
        if nested_name:
            entity = {"kind": "block_reference", "block_name": nested_name,
                      "position": _pt(g.get("position")), "scale": _pt(g.get("scale")),
                      "rotation": g.get("rotation")}
    elif kind == "hatch":
        if bool(g.get("is_gradient")):
            return None
        if _is_custom_hatch_pattern(g) and not _has_hatch_pattern_definitions(g):
            # Drawing-custom pattern names (measured: H3 x181, H1 x1 on 1.dwg)
            # are NOT in headless acad.pat - setPattern(kPreDefined, name)
            # fails errorstatus 3 and fail-closed aborts the whole batch
            # (R4f b157). Defer until the definition-line replay lands
            # (extract getPatternDefinitionAt -> staging .pat -> kCustomDefined;
            # advisory ledger in docs/HATCH_APPEND_DESIGN.md).
            return None
        loops = g.get("loops")
        if (_is_numeric_array(g.get("normal"), min_len=3)
                and g.get("pattern_name")
                and _has_hatch_representable_loops(loops)):
            entity = {
                "kind": "hatch",
                "normal": list(g.get("normal")),
                "elevation": g.get("elevation"),
                "pattern_angle": g.get("pattern_angle"),
                "pattern_scale": g.get("pattern_scale"),
                "pattern_type": g.get("pattern_type"),
                "hatch_style": g.get("hatch_style"),
                "loop_count": g.get("loop_count"),
                "pattern_name": g.get("pattern_name"),
                "pattern_double": g.get("pattern_double"),
                "is_solid_fill": g.get("is_solid_fill"),
                "is_associative": g.get("is_associative"),
                "is_gradient": g.get("is_gradient"),
                "loops": copy.deepcopy(loops),
            }
            if _is_custom_hatch_pattern(g) and _has_hatch_pattern_definitions(g):
                entity["pattern_definitions"] = copy.deepcopy(g.get("pattern_definitions"))
            # Per-hatch pattern origin (HPORIGIN). Live cert 2026-07-09
            # (runs/hatch_origin_cert3_20260709): setOriginPoint [123.5, -77.25]
            # -> DWG -> originPoint() -> final IR round-trips exactly.
            #
            # Custom patterns with definition rows carry their per-hatch phase
            # BAKED into the row base points, NOT in the origin field (R4n
            # census probe, runs/e2e_1dwg_R4n_origin_20260709: all 233
            # residual pairs differ by one common per-row base vector,
            # divergent 0, while their census pattern_origin is [0,0]). The
            # synthesized .pat is shared per NAME and rebased to zero phase
            # (patch_engine._synthesize_batch_pat_files), so the per-hatch
            # phase must ride HPORIGIN: effective origin = rows[0].base +
            # census origin. Additivity of base+origin is evidenced by the 27
            # nonzero-origin hatches already diff0 under the shared-base
            # replay. Plain passthrough remains for defs-less hatches.
            pattern_origin = g.get("pattern_origin")
            census_origin = None
            if (isinstance(pattern_origin, list) and len(pattern_origin) >= 2
                    and all(isinstance(v, (int, float)) for v in pattern_origin[:2])):
                census_origin = [float(pattern_origin[0]), float(pattern_origin[1])]
                entity["pattern_origin"] = list(census_origin)
            # Read rows from the CENSUS geometry, not the serialized entity:
            # predefined-name patterns (DASH x66 on 1.dwg) never ride
            # pattern_definitions in the job (the drawing resolves the name),
            # yet their census rows carry the per-hatch phase in base -- R4p
            # measured all 66 losing phase because this lookup used the
            # entity and skipped the base fold for exactly that class.
            rows = g.get("pattern_definitions")
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                base1 = rows[0].get("base")
                if (isinstance(base1, list) and len(base1) >= 2
                        and all(isinstance(v, (int, float)) for v in base1[:2])):
                    off = census_origin or [0.0, 0.0]
                    entity["pattern_origin"] = [float(base1[0]) + off[0],
                                                float(base1[1]) + off[1]]
    elif kind == "face3d":
        edge_visibility = g.get("edge_visibility")
        if (_is_numeric_array(g.get("p0"), min_len=3)
                and _is_numeric_array(g.get("p1"), min_len=3)
                and _is_numeric_array(g.get("p2"), min_len=3)
                and _is_numeric_array(g.get("p3"), min_len=3)
                and isinstance(edge_visibility, list)
                and len(edge_visibility) == 4):
            entity = {
                "kind": "face3d",
                "p0": list(g.get("p0")),
                "p1": list(g.get("p1")),
                "p2": list(g.get("p2")),
                "p3": list(g.get("p3")),
                "edge_visibility": copy.deepcopy(edge_visibility),
            }
    elif kind == "wipeout":
        # Native builder live-certified 2026-07-09 (runs/wipeout_cert_census_
        # 20260709): append_entity kind=wipeout returned appended:true and the
        # census re-extraction matched the fixture exactly (clip 11pts,
        # u/v_vector, origin, clip_type, frame_on). Root cause of the earlier
        # WIPEOUT_MODULE_UNAVAILABLE was an inverted loadModule bool==eOk gate
        # in m08e, not a missing module. Field set = the cert-proven payload;
        # external-source / missing-clip inputs still defer via
        # _def_entity_append_reason.
        if _is_wipeout_representable(g):
            entity = {
                "kind": "wipeout",
                "origin": list(g.get("origin")),
                "u_vector": list(g.get("u_vector")),
                "v_vector": list(g.get("v_vector")),
                "clip_boundary_type": g.get("clip_boundary_type"),
                "clip_boundary": copy.deepcopy(g.get("clip_boundary")),
            }
    if entity is None:
        return None
    return {"operation": "append_block_entity",
            "args": {"block_name": block_name, "entity": entity, "layer": layer}}


def block_def_ops(block_def: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """One IR block_definitions[] entry -> (ops, deferred) that synthesize
    that block definition in a fresh/seed target: a create_block (idempotent
    BTR creation, see WRITE_OP_MAP's comment) followed by one
    append_block_entity per def_entity write.block.append_entity's native
    handler can represent. A def_entity of an unsupported kind, or a
    block_definitions entry with no inlined def_entities at all (schema
    allows content to live via owner_handle instead -- not followed here),
    is reported in ``deferred``, never silently dropped (no-fake-success).
    """
    name = block_def.get("name")
    # seed_line=0: synthesis rebuilds the definition from census def_entities
    # only - the native op's default self-test line ((0,0,0)->(5,0,0)) was the
    # measured "+1 per def" fixed-point drift (GEN2 / R4b blockdef_diff).
    ops: List[Dict[str, Any]] = [
        {"operation": "create_block", "args": {"name": name, "seed_line": 0}}]
    deferred: List[Dict[str, Any]] = []
    def_entities = block_def.get("def_entities") or []
    if not def_entities:
        deferred.append({
            "block_name": name, "def_entity_index": None, "handle": block_def.get("handle"),
            "kind": None,
            "reason": "block_definitions entry has no inlined def_entities "
                      "(content may live via owner_handle, not lifted here)",
        })
    for i, def_ent in enumerate(def_entities):
        op = _def_entity_append_op(name, def_ent)
        if op is None:
            deferred.append({
                "block_name": name, "def_entity_index": i, "handle": def_ent.get("handle"),
                "kind": (def_ent.get("geometry") or {}).get("kind"),
                "reason": _def_entity_append_reason(def_ent),
            })
            continue
        ops.append(op)
    return ops, deferred
