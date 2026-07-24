#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flatten_blocks.py -- resolve INSERTs to world-space entities for dwg_graph_ir.v1.

Companion to issue #25's usability note: block-definition geometry IS captured
(``block_definitions[].def_entities``), but a consumer iterating only the
top-level ``entities[]`` never sees it -- e.g. a drawing border / title block
(도각) that is placed via an INSERT whose geometry lives one level down in the
block definition. This tool resolves every ``block_reference`` recursively and
applies its insert transform (translation, scale, rotation) to each nested
entity, emitting a flat, world-coordinate ``entities[]`` list so the block
content (border, symbols, etc.) appears directly.

Pure geometry, standard library only. Nested INSERTs compose transforms; a
cycle guard and depth cap prevent runaway self-referencing blocks. Entity kinds
whose points are recoverable (line, lwpolyline, polyline, circle, arc, ellipse,
text, mtext, point, solid, leader) are transformed exactly; unknown kinds get a
best-effort deep point transform and are flagged ``_transform_approx``.

Usage:
    python tools/flatten_blocks.py <dwg_graph_ir.json> [-o <out.json>]
                                   [--max-depth N] [--max-entities N]
"""
from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_MAX_DEPTH = 24
DEFAULT_MAX_ENTITIES = 3_000_000

# 2D affine (a, b, c, d, e, f) : x' = a*x + c*y + e ; y' = b*x + d*y + f
# plus an independent z scale/offset (zs, zt) : z' = zs*z + zt
Matrix = Tuple[float, float, float, float, float, float, float, float]
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0)


def _mat_from_insert(pos, scale, rot) -> Matrix:
    sx, sy, sz = (list(scale) + [1, 1, 1])[:3] if isinstance(scale, list) else (1, 1, 1)
    tx, ty, tz = (list(pos) + [0, 0, 0])[:3] if isinstance(pos, list) else (0, 0, 0)
    c, s = math.cos(rot or 0.0), math.sin(rot or 0.0)
    return (sx * c, sx * s, -sy * s, sy * c, tx, ty, sz, tz)


def _compose(p: Matrix, ch: Matrix) -> Matrix:
    a1, b1, c1, d1, e1, f1, zs1, zt1 = p
    a2, b2, c2, d2, e2, f2, zs2, zt2 = ch
    return (
        a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1,
        zs1 * zs2, zs1 * zt2 + zt1,
    )


def _tpt(p, m: Matrix) -> List[float]:
    a, b, c, d, e, f, zs, zt = m
    x = p[0] if len(p) > 0 else 0.0
    y = p[1] if len(p) > 1 else 0.0
    z = p[2] if len(p) > 2 else 0.0
    return [a * x + c * y + e, b * x + d * y + f, zs * z + zt]


def _tvec(v, m: Matrix) -> List[float]:
    a, b, c, d = m[0], m[1], m[2], m[3]
    x = v[0] if len(v) > 0 else 0.0
    y = v[1] if len(v) > 1 else 0.0
    z = v[2] if len(v) > 2 else 0.0
    return [a * x + c * y, b * x + d * y, z]


def _net_rot(m: Matrix) -> float:
    return math.atan2(m[1], m[0])


def _net_scale(m: Matrix) -> float:
    det = m[0] * m[3] - m[1] * m[2]
    return math.sqrt(abs(det)) if det else math.hypot(m[0], m[1])


def _xform_geometry(g: Dict[str, Any], m: Matrix) -> Dict[str, Any]:
    k = g.get("kind")
    r, sc = _net_rot(m), _net_scale(m)
    o = dict(g)
    if k == "line":
        o["start"], o["end"] = _tpt(g["start"], m), _tpt(g["end"], m)
    elif k in ("lwpolyline", "polyline"):
        o["vertices"] = [dict(v, point=_tpt(v["point"], m)) for v in g.get("vertices", [])]
    elif k == "circle":
        o["center"], o["radius"] = _tpt(g["center"], m), g["radius"] * sc
    elif k == "arc":
        o["center"], o["radius"] = _tpt(g["center"], m), g["radius"] * sc
        o["start_angle"] = g.get("start_angle", 0.0) + r
        o["end_angle"] = g.get("end_angle", 0.0) + r
    elif k == "ellipse":
        o["center"], o["major_axis"] = _tpt(g["center"], m), _tvec(g["major_axis"], m)
    elif k in ("text", "mtext"):
        for pk in ("position", "insertion_point", "alignment_point"):
            if isinstance(g.get(pk), list):
                o[pk] = _tpt(g[pk], m)
        if "height" in g:
            o["height"] = g["height"] * sc
        if "rotation" in g:
            o["rotation"] = g.get("rotation", 0.0) + r
    elif k == "point":
        if isinstance(g.get("position"), list):
            o["position"] = _tpt(g["position"], m)
    elif k == "solid":
        for pk in ("p0", "p1", "p2", "p3"):
            if isinstance(g.get(pk), list):
                o[pk] = _tpt(g[pk], m)
    elif k == "leader":
        o["vertices"] = [dict(v, point=_tpt(v["point"], m)) for v in g.get("vertices", [])]
    else:
        def walk(v):
            if isinstance(v, list):
                if v and all(isinstance(n, (int, float)) for n in v) and 2 <= len(v) <= 3:
                    return _tpt(v, m)
                return [walk(x) for x in v]
            if isinstance(v, dict):
                return {kk: walk(vv) for kk, vv in v.items()}
            return v
        o = {kk: (vv if kk in ("kind", "radius", "normal", "radius_ratio",
                               "closed", "block_name") else walk(vv))
             for kk, vv in g.items()}
        o["_transform_approx"] = True
    return o


def flatten(ir: Dict[str, Any], *, max_depth: int = DEFAULT_MAX_DEPTH,
            max_entities: int = DEFAULT_MAX_ENTITIES) -> Dict[str, Any]:
    """Return a flat world-space entity document from a dwg_graph_ir.v1 IR."""
    bd: Dict[str, List[Dict[str, Any]]] = {}
    for b in ir.get("block_definitions", []) or []:
        if isinstance(b, dict) and b.get("name") is not None:
            bd[str(b["name"])] = b.get("def_entities", []) or []

    out: List[Dict[str, Any]] = []
    stats = Counter()
    unresolved = Counter()

    def emit(dxf_name, layer, geom, origin):
        if len(out) >= max_entities:
            return
        out.append({"dxf_name": dxf_name, "layer": layer,
                    "geometry": geom, "flattened_from": origin})
        stats["emitted"] += 1

    def walk_block(name, m: Matrix, depth: int, stack: frozenset, origin):
        if depth > max_depth:
            stats["max_depth_hit"] += 1
            return
        des = bd.get(str(name))
        if des is None:
            unresolved[str(name)] += 1
            stats["unresolved_blocks"] += 1
            return
        if str(name) in stack:
            return
        stack = stack | {str(name)}
        for de in des:
            if not isinstance(de, dict):
                continue
            g = de.get("geometry") or {}
            if g.get("kind") == "block_reference":
                child = _compose(m, _mat_from_insert(
                    g.get("position", [0, 0, 0]), g.get("scale", [1, 1, 1]),
                    g.get("rotation", 0.0)))
                walk_block(g.get("block_name"), child, depth + 1, stack, origin)
            else:
                emit(de.get("dxf_name"), de.get("layer", "0"),
                     _xform_geometry(g, m), origin)

    for e in ir.get("entities", []) or []:
        g = e.get("geometry") or {}
        if g.get("kind") == "block_reference":
            stats["top_inserts"] += 1
            m = _mat_from_insert(g.get("position", [0, 0, 0]),
                                 g.get("scale", [1, 1, 1]), g.get("rotation", 0.0))
            walk_block(g.get("block_name"), m, 0, frozenset(),
                       {"insert_handle": e.get("handle"), "block": g.get("block_name")})
        else:
            stats["passthrough"] += 1
            out.append({"dxf_name": e.get("dxf_name"), "layer": e.get("layer"),
                        "geometry": g, "flattened_from": None})
            stats["emitted"] += 1

    return {
        "schema": "ariadne.dwg_flat.v1",
        "issue": 25,
        "note": ("block references resolved recursively; insert transforms "
                 "(translate/scale/rotate) applied to nested geometry -> world "
                 "coordinates, so block content (e.g. the 도각/border) appears "
                 "directly in entities[]."),
        "flatten_info": {
            **dict(stats),
            "unresolved_block_names": [n for n, _ in unresolved.most_common(40)],
        },
        "entities": out,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ir", help="path to dwg_graph_ir.json")
    ap.add_argument("-o", "--out", default=None,
                    help="output path (default: <ir>_flat.json next to the input)")
    ap.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    ap.add_argument("--max-entities", type=int, default=DEFAULT_MAX_ENTITIES)
    args = ap.parse_args(argv)

    with open(args.ir, "r", encoding="utf-8-sig") as fh:
        ir = json.load(fh)
    flat = flatten(ir, max_depth=args.max_depth, max_entities=args.max_entities)

    out = args.out or (os.path.splitext(args.ir)[0] + "_flat.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(flat, fh, ensure_ascii=False)
    info = flat["flatten_info"]
    print("wrote %s (emitted=%d, top_inserts=%d, unresolved_blocks=%d)"
          % (out, info.get("emitted", 0), info.get("top_inserts", 0),
             info.get("unresolved_blocks", 0)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
