#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""insert_expand.py -- INSERT world-coordinate expansion module for SEG-IR v1.

Part of the E2 wall-detector S4 pipeline. Walks a DXF's INSERT (block
reference) tree depth-first, composing the affine transform of each block
reference -- insert point, rotation, x/y scale, and the block-definition base
point -- and produces flat, world-coordinate segments by delegating the actual
per-entity geometry conversion to an *injected* ``entity_to_segments`` callable.

Wiring contract (S4 modules must NOT import each other; cli.py wires them):

    expand(dxf_path, entity_to_segments) -> SEG-IR dict

where the injected callable has the signature

    entity_to_segments(entity, transform=None) -> list[segment-dict]

and ``transform`` is a 2x3 affine ``((a, b, tx), (c, d, ty))`` mapping the
entity's own (block-local) coordinates to world coordinates, or ``None`` for a
top-level (already world-space) entity::

    x' = a*x + b*y + tx
    y' = c*x + d*y + ty

Segments produced from geometry that lives inside a nested block carry:
  * ``handle``    -- the handle of the DEEPEST source entity (the leaf that was
                     actually converted), naturally set by entity_to_segments
                     and re-asserted here for safety; and
  * ``insert_path`` -- a NEW key: the list of INSERT handles from the
                     top-level block reference down to the immediate parent.

A cycle guard (a visited block-name stack) and a hard depth cap (16) prevent
runaway self-referencing or pathologically deep block trees.

SEG-IR v1 (shared contract -- exact top-level keys, ``ir`` version required)::

    {"ir": "seg.v1", "drawing_id": "str", "units": "mm|unknown",
     "scale_mm_per_unit": null,
     "segments": [{"sid": "s0001", "handle": "8B52 or null",
                   "pts": [[x1, y1], [x2, y2]], "layer": "str",
                   "kind": "line|poly-edge|arc-chord",
                   "label": "wall|opening|other|unknown",
                   "source": "native|synth|floorplancad|cubicasa"}]}

ezdxf is used only to READ the DXF and enumerate the block tree; the geometry
conversion itself is entirely the injected callable's responsibility (this
module never imports normalize.py). Selftest builds its own DXF with ezdxf in
the OS temp dir.

Usage:
    python tools/e2/detect/insert_expand.py --selftest
    python tools/e2/detect/insert_expand.py <file.dxf> [-o out.json]
"""
from __future__ import annotations

import argparse
import json
import math
import os
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

import ezdxf

MAX_DEPTH = 16  # hard cap on INSERT nesting depth (top-level ref == depth 1)

# Internal 2x3 affine as a flat 6-tuple (a, b, tx, c, d, ty):
#   x' = a*x + b*y + tx ; y' = c*x + d*y + ty
Affine = Tuple[float, float, float, float, float, float]
Segment = Dict[str, Any]
EntityToSegments = Callable[..., List[Segment]]


# --------------------------------------------------------------------------- #
# Affine helpers                                                              #
# --------------------------------------------------------------------------- #
def _base_point(block) -> Tuple[float, float]:
    """Return the (x, y) base point of a block definition (default origin)."""
    try:
        bp = block.block.dxf.base_point
        return float(bp[0]), float(bp[1])
    except Exception:
        return 0.0, 0.0


def _insert_matrix(insert, base: Tuple[float, float]) -> Affine:
    """Affine that maps a referenced block's local coords to its parent frame.

    world = insert_point + R(rot) * S(xscale, yscale) * (p - base_point)
    """
    ins = insert.dxf.insert
    ix, iy = float(ins[0]), float(ins[1])
    rot = math.radians(float(insert.dxf.get("rotation", 0.0) or 0.0))
    sx = float(insert.dxf.get("xscale", 1.0) or 1.0)
    sy = float(insert.dxf.get("yscale", 1.0) or 1.0)
    bx, by = base
    cos, sin = math.cos(rot), math.sin(rot)
    a = cos * sx
    b = -sin * sy
    c = sin * sx
    d = cos * sy
    # translation absorbs "- M2x2 * base" so the base point maps to the insert
    tx = ix - (a * bx + b * by)
    ty = iy - (c * bx + d * by)
    return (a, b, tx, c, d, ty)


def _compose(p: Affine, ch: Affine) -> Affine:
    """Return the affine equivalent to applying ``ch`` then ``p`` (p o ch)."""
    pa, pb, ptx, pc, pd, pty = p
    ca, cb, ctx, cc, cd, cty = ch
    return (
        pa * ca + pb * cc, pa * cb + pb * cd, pa * ctx + pb * cty + ptx,
        pc * ca + pd * cc, pc * cb + pd * cd, pc * ctx + pd * cty + pty,
    )


def _to_contract(m: Affine) -> Tuple[Tuple[float, float, float],
                                     Tuple[float, float, float]]:
    """Convert the internal 6-tuple to the injected callable's ((a,b,tx),(c,d,ty))."""
    a, b, tx, c, d, ty = m
    return ((a, b, tx), (c, d, ty))


# --------------------------------------------------------------------------- #
# INSERT tree walk                                                            #
# --------------------------------------------------------------------------- #
def _walk(insert, doc, parent_xform: Optional[Affine], parent_path: List[str],
          depth: int, block_stack: frozenset,
          entity_to_segments: EntityToSegments,
          out: List[Segment], counters: Dict[str, int]) -> None:
    """Depth-first descent into a single INSERT (block reference)."""
    name = insert.dxf.name
    insert_handle = getattr(insert.dxf, "handle", None)

    if depth > MAX_DEPTH:
        counters["max_depth_hit"] += 1
        return
    if name in block_stack:
        counters["cycle_skipped"] += 1
        return
    block = doc.blocks.get(name)
    if block is None:
        counters["missing_block"] += 1
        return

    counters["inserts_walked"] += 1
    local = _insert_matrix(insert, _base_point(block))
    xform = local if parent_xform is None else _compose(parent_xform, local)
    path = parent_path + [insert_handle]
    stack = block_stack | {name}

    for sub in block:
        if sub.dxftype() == "INSERT":
            _walk(sub, doc, xform, path, depth + 1, stack,
                  entity_to_segments, out, counters)
            continue
        leaf_handle = getattr(sub.dxf, "handle", None)
        segs = entity_to_segments(sub, _to_contract(xform)) or []
        for s in segs:
            s = dict(s)
            s["handle"] = leaf_handle          # deepest source entity
            s["insert_path"] = list(path)      # top-level -> immediate parent
            out.append(s)
            counters["nested_segments"] += 1


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #
def expand(dxf_path: str, entity_to_segments: EntityToSegments) -> Dict[str, Any]:
    """Expand every INSERT in a DXF modelspace to flat world-coordinate SEG-IR.

    Top-level (non-INSERT) entities are converted with ``transform=None`` (they
    are already world-space); geometry reached through one or more INSERTs is
    converted with the composed transform and tagged with ``insert_path``.
    """
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    out: List[Segment] = []
    counters: Dict[str, int] = defaultdict(int)

    for e in msp:
        if e.dxftype() == "INSERT":
            counters["top_inserts"] += 1
            _walk(e, doc, None, [], 1, frozenset(),
                  entity_to_segments, out, counters)
        else:
            segs = entity_to_segments(e, None) or []
            for s in segs:
                out.append(dict(s))
                counters["top_segments"] += 1

    # Re-number sids sequentially across the merged document.
    for i, s in enumerate(out, 1):
        s["sid"] = "s%04d" % i

    return {
        "ir": "seg.v1",
        "drawing_id": os.path.splitext(os.path.basename(dxf_path))[0],
        "units": "unknown",
        "scale_mm_per_unit": None,
        "segments": out,
        # non-contract diagnostic sidecar (ignored by SEG-IR consumers)
        "_expand_info": dict(counters),
    }


# --------------------------------------------------------------------------- #
# Selftest                                                                    #
# --------------------------------------------------------------------------- #
def _selftest_entity_to_segments(entity, transform=None) -> List[Segment]:
    """Minimal stand-in for normalize.entity_to_segments (LINE/LWPOLYLINE/ARC).

    Exists ONLY for the selftest -- exercises the same injection contract the
    real normalize.py callable satisfies. This module never imports normalize.
    """
    def ap(p) -> List[float]:
        x, y = float(p[0]), float(p[1])
        if transform is None:
            return [x, y]
        (a, b, tx), (c, d, ty) = transform
        return [a * x + b * y + tx, c * x + d * y + ty]

    et = entity.dxftype()
    h = getattr(entity.dxf, "handle", None)
    layer = getattr(entity.dxf, "layer", "0")
    segs: List[Segment] = []

    if et == "LINE":
        segs.append({"sid": "s0000", "handle": h,
                     "pts": [ap(entity.dxf.start), ap(entity.dxf.end)],
                     "layer": layer, "kind": "line",
                     "label": "unknown", "source": "native"})
    elif et == "LWPOLYLINE":
        pts = [(pt[0], pt[1]) for pt in entity.get_points("xy")]
        for i in range(len(pts) - 1):
            segs.append({"sid": "s0000", "handle": h,
                         "pts": [ap(pts[i]), ap(pts[i + 1])],
                         "layer": layer, "kind": "poly-edge",
                         "label": "unknown", "source": "native"})
        if entity.closed and len(pts) > 2:
            segs.append({"sid": "s0000", "handle": h,
                         "pts": [ap(pts[-1]), ap(pts[0])],
                         "layer": layer, "kind": "poly-edge",
                         "label": "unknown", "source": "native"})
    elif et == "ARC":
        c = entity.dxf.center
        r = float(entity.dxf.radius)
        sa = math.radians(float(entity.dxf.start_angle))
        ea = math.radians(float(entity.dxf.end_angle))
        p1 = (c[0] + r * math.cos(sa), c[1] + r * math.sin(sa))
        p2 = (c[0] + r * math.cos(ea), c[1] + r * math.sin(ea))
        segs.append({"sid": "s0000", "handle": h,
                     "pts": [ap(p1), ap(p2)],
                     "layer": layer, "kind": "arc-chord",
                     "label": "unknown", "source": "native"})
    return segs


def _build_fixture(path: str) -> Dict[str, Any]:
    """Build a small DXF exercising LINE + LWPOLYLINE + ARC + nested INSERT,
    a self-referencing block (cycle guard), and a deep chain (depth guard)."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # --- top-level primitives ------------------------------------------------
    top_line = msp.add_line((0, 0), (50, 0), dxfattribs={"layer": "WALL"})
    top_poly = msp.add_lwpolyline(
        [(0, 0), (10, 0), (10, 10)], dxfattribs={"layer": "WALL"})
    top_arc = msp.add_arc(
        center=(0, 0), radius=5, start_angle=0, end_angle=90,
        dxfattribs={"layer": "OPENING"})

    # --- nested block tree: OUTER contains an INSERT of INNER ---------------
    inner = doc.blocks.new(name="INNER", base_point=(0, 0, 0))
    inner_line = inner.add_line((0, 0), (10, 0), dxfattribs={"layer": "WALL"})

    outer = doc.blocks.new(name="OUTER", base_point=(0, 0, 0))
    outer.add_line((0, 0), (0, 5), dxfattribs={"layer": "WALL"})
    inner_ref = outer.add_blockref("INNER", (5, 0))  # nested INSERT, no rot/scale

    outer_ref = msp.add_blockref(
        "OUTER", (100, 200),
        dxfattribs={"rotation": 90, "xscale": 2, "yscale": 2, "layer": "WALL"})

    # --- self-referencing block to exercise the cycle guard ------------------
    cyc = doc.blocks.new(name="CYC")
    cyc.add_line((0, 0), (1, 1))
    cyc.add_blockref("CYC", (0, 0))  # references itself
    msp.add_blockref("CYC", (0, 0))

    # --- deep distinct-block chain to exercise the depth cap -----------------
    chain_len = MAX_DEPTH + 4
    for i in range(chain_len):
        blk = doc.blocks.new(name="CH%02d" % i)
        if i == chain_len - 1:
            blk.add_line((0, 0), (1, 0))  # deepest leaf, beyond MAX_DEPTH
        else:
            blk.add_blockref("CH%02d" % (i + 1), (0, 0))
    msp.add_blockref("CH00", (0, 0))

    doc.saveas(path)
    return {
        "top_line": top_line.dxf.handle,
        "top_poly": top_poly.dxf.handle,
        "top_arc": top_arc.dxf.handle,
        "inner_line": inner_line.dxf.handle,
        "inner_ref": inner_ref.dxf.handle,
        "outer_ref": outer_ref.dxf.handle,
    }


def _selftest() -> int:
    import tempfile

    checks: List[Tuple[str, bool, str]] = []

    def chk(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    tmpdir = tempfile.mkdtemp(prefix="s4b_insert_")
    dxf_path = os.path.join(tmpdir, "fixture.dxf")
    handles = _build_fixture(dxf_path)

    ir = expand(dxf_path, _selftest_entity_to_segments)
    segs = ir["segments"]
    info = ir["_expand_info"]

    # -- SEG-IR contract shape -----------------------------------------------
    chk("ir_version", ir.get("ir") == "seg.v1", ir.get("ir"))
    chk("drawing_id", ir.get("drawing_id") == "fixture", ir.get("drawing_id"))
    chk("scale_null", ir.get("scale_mm_per_unit") is None, "")
    chk("sids_sequential",
        [s["sid"] for s in segs] == ["s%04d" % i for i in range(1, len(segs) + 1)],
        "n=%d" % len(segs))

    # -- top-level entities carry NO insert_path -----------------------------
    top_line_segs = [s for s in segs if s["handle"] == handles["top_line"]]
    chk("top_line_present", len(top_line_segs) == 1, "")
    chk("top_line_no_insert_path",
        all("insert_path" not in s for s in top_line_segs), "")
    chk("top_line_world_coords",
        top_line_segs and top_line_segs[0]["pts"] == [[0.0, 0.0], [50.0, 0.0]],
        str(top_line_segs[0]["pts"]) if top_line_segs else "missing")

    top_arc_segs = [s for s in segs if s["handle"] == handles["top_arc"]]
    chk("top_arc_chord", top_arc_segs and top_arc_segs[0]["kind"] == "arc-chord",
        top_arc_segs[0]["kind"] if top_arc_segs else "missing")

    top_poly_segs = [s for s in segs if s["handle"] == handles["top_poly"]]
    chk("top_poly_edges",
        len(top_poly_segs) == 2 and all(s["kind"] == "poly-edge" for s in top_poly_segs),
        "n=%d" % len(top_poly_segs))

    # -- nested INNER line: deepest handle + full insert_path + world coords ---
    inner_segs = [s for s in segs if s["handle"] == handles["inner_line"]]
    chk("nested_line_present", len(inner_segs) == 1, "n=%d" % len(inner_segs))
    if inner_segs:
        s = inner_segs[0]
        chk("nested_handle_is_deepest", s["handle"] == handles["inner_line"],
            s["handle"])
        chk("nested_insert_path",
            s.get("insert_path") == [handles["outer_ref"], handles["inner_ref"]],
            str(s.get("insert_path")))
        # OUTER: insert (100,200) rot 90 scale 2 ; INNER: insert (5,0)
        # INNER local (0,0)->(100,210) ; (10,0)->(100,230)
        got = [[round(v, 6) for v in pt] for pt in s["pts"]]
        want = [[100.0, 210.0], [100.0, 230.0]]
        chk("nested_composed_transform", got == want, "got=%s want=%s" % (got, want))

    # -- OUTER's own direct line: single-level insert_path -------------------
    outer_direct = [s for s in segs
                    if s.get("insert_path") == [handles["outer_ref"]]]
    chk("outer_direct_line", len(outer_direct) == 1, "n=%d" % len(outer_direct))
    if outer_direct:
        # OUTER line (0,0)-(0,5): (0,0)->(100,200); (0,5): scale2 ->(0,10),
        # rot90 ->(-10,0), +insert ->(90,200)
        got = [[round(v, 6) for v in pt] for pt in outer_direct[0]["pts"]]
        want = [[100.0, 200.0], [90.0, 200.0]]
        chk("outer_direct_transform", got == want, "got=%s want=%s" % (got, want))

    # -- guards --------------------------------------------------------------
    chk("cycle_guard_fired", info.get("cycle_skipped", 0) >= 1,
        "cycle_skipped=%d" % info.get("cycle_skipped", 0))
    chk("depth_cap_fired", info.get("max_depth_hit", 0) >= 1,
        "max_depth_hit=%d" % info.get("max_depth_hit", 0))

    # -- report --------------------------------------------------------------
    npass = sum(1 for _, ok, _ in checks if ok)
    print("=" * 64)
    print("insert_expand.py --selftest")
    print("fixture: %s" % dxf_path)
    print("segments emitted: %d  (top=%d nested=%d)"
          % (len(segs), info.get("top_segments", 0), info.get("nested_segments", 0)))
    print("expand_info: %s" % json.dumps(dict(sorted(info.items()))))
    print("-" * 64)
    for name, ok, detail in checks:
        line = "  %-28s %s" % (name, "PASS" if ok else "FAIL")
        if detail and not ok:
            line += "   <%s>" % detail
        print(line)
    print("-" * 64)
    print("RESULT: %d/%d checks PASS" % (npass, len(checks)))
    print("=" * 64)
    return 0 if npass == len(checks) else 1


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dxf", nargs="?", help="path to a .dxf file")
    ap.add_argument("-o", "--out", default=None, help="output SEG-IR json path")
    ap.add_argument("--selftest", action="store_true",
                    help="build a temp-dir DXF and exercise expand()")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.dxf:
        ap.error("a .dxf path is required unless --selftest is given")

    # Standalone CLI use requires an entity_to_segments; without normalize.py
    # wired in this module cannot convert geometry, so refuse rather than fake.
    raise SystemExit(
        "insert_expand is a library: call expand(dxf_path, entity_to_segments) "
        "with normalize.entity_to_segments injected by cli.py. "
        "Use --selftest for a self-contained demo.")


if __name__ == "__main__":
    raise SystemExit(main())
