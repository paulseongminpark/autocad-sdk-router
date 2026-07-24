#!/usr/bin/env python3
"""S4-A geometry normalization module for the E2 wall-detector campaign.

Turns raw DXF geometry into SEGMENT-IR v1 (the shared line-segment contract that
downstream S4 modules consume). This module is a plain script in a plain script
dir: it does NOT import the sibling S4 modules (insert_expand / unit_anchor /
evidence_grid). cli.py wires them together via dependency injection.

Public surface (per the S4 wiring contract):
  parse_modelspace(dxf_path, expand_inserts=False) -> SEG-IR dict
  entity_to_segments(entity, transform=None)        -> list[segment-dict]

SEGMENT-IR v1 (exact keys, version field required):
  {"ir":"seg.v1","drawing_id":"str","units":"mm|unknown","scale_mm_per_unit":null,
   "segments":[{"sid":"s0001","handle":"8B52 or null","pts":[[x1,y1],[x2,y2]],
                "layer":"str","kind":"line|poly-edge|arc-chord",
                "label":"wall|opening|other|unknown",
                "source":"native|synth|floorplancad|cubicasa"}]}

Mapping performed here:
  LINE                 -> one "line" segment.
  LWPOLYLINE/POLYLINE  -> consecutive "poly-edge" segments (closed flag respected).
  ARC                  -> one "arc-chord" segment (chord endpoints; arc height in
                          the extra key "sagitta").
  MLINE (if present)   -> component "line" segments (via ezdxf virtual_entities).
  INSERT               -> SKIPPED here when expand_inserts=False. Recursion into
                          block references is owned by insert_expand.py (S4-B).
  everything else      -> ignored, no crash.

Coordinates are in the world units of the source doc. handle = entity handle.
The optional `transform` argument is a 2x3 affine ((a,b,tx),(c,d,ty)) applied to
every point, so insert_expand.py can inject composed block transforms.
"""

import math
import os
import sys

try:
    import ezdxf
except ImportError:  # pragma: no cover - surfaced at call time
    ezdxf = None

IR_VERSION = "seg.v1"

# SEG-IR label/source defaults for native geometry. Wall/opening labels are
# assigned later by evidence_grid.py; this module stays label-agnostic.
_DEFAULT_LABEL = "unknown"
_DEFAULT_SOURCE = "native"


# --------------------------------------------------------------------------- #
# affine helpers
# --------------------------------------------------------------------------- #
def _apply(transform, x, y):
    """Apply the 2x3 affine transform to a point, returning [x, y] as floats.

    transform is ((a,b,tx),(c,d,ty)) or None. None is identity.
    """
    if transform is None:
        return [float(x), float(y)]
    (a, b, tx), (c, d, ty) = transform
    return [float(a * x + b * y + tx), float(c * x + d * y + ty)]


def _scale_factor(transform):
    """Uniform-equivalent scale of the transform's linear part (sqrt|det|).

    Used to scale the arc sagitta consistently with its transformed endpoints.
    For non-uniform scale this is an approximation (see module LIMITS).
    """
    if transform is None:
        return 1.0
    (a, b, _), (c, d, _) = transform
    return math.sqrt(abs(a * d - b * c))


def _seg(handle, pts, layer, kind, **extra):
    """Build one SEG-IR segment dict. sid is None until the assembler finalizes it."""
    seg = {
        "sid": None,
        "handle": handle,
        "pts": pts,
        "layer": layer,
        "kind": kind,
        "label": _DEFAULT_LABEL,
        "source": _DEFAULT_SOURCE,
    }
    seg.update(extra)
    return seg


# --------------------------------------------------------------------------- #
# per-entity conversion
# --------------------------------------------------------------------------- #
def _edges(pts, closed, transform, handle, layer):
    """Consecutive poly-edge segments from an ordered point list."""
    out = []
    if len(pts) < 2:
        return out
    seq = list(pts)
    if closed and len(pts) >= 3:
        seq = seq + [pts[0]]
    for i in range(len(seq) - 1):
        x1, y1 = seq[i]
        x2, y2 = seq[i + 1]
        out.append(
            _seg(handle, [_apply(transform, x1, y1), _apply(transform, x2, y2)],
                 layer, "poly-edge")
        )
    return out


def _line(entity, transform, handle, layer):
    s = entity.dxf.start
    e = entity.dxf.end
    return [
        _seg(handle, [_apply(transform, s.x, s.y), _apply(transform, e.x, e.y)],
             layer, "line")
    ]


def _lwpolyline(entity, transform, handle, layer):
    pts = [(p[0], p[1]) for p in entity.get_points("xy")]
    return _edges(pts, bool(entity.closed), transform, handle, layer)


def _polyline(entity, transform, handle, layer):
    # Old-style 2D/3D POLYLINE: iterate its VERTEX children.
    pts = []
    for v in entity.vertices:
        loc = v.dxf.location
        pts.append((loc.x, loc.y))
    return _edges(pts, bool(entity.is_closed), transform, handle, layer)


def _arc(entity, transform, handle, layer):
    cx = entity.dxf.center.x
    cy = entity.dxf.center.y
    r = entity.dxf.radius
    sa_deg = entity.dxf.start_angle
    ea_deg = entity.dxf.end_angle
    sa = math.radians(sa_deg)
    ea = math.radians(ea_deg)
    start = (cx + r * math.cos(sa), cy + r * math.sin(sa))
    end = (cx + r * math.cos(ea), cy + r * math.sin(ea))
    # ezdxf arcs sweep counter-clockwise from start_angle to end_angle.
    theta_deg = (ea_deg - sa_deg) % 360.0
    sagitta = r * (1.0 - math.cos(math.radians(theta_deg) / 2.0))
    sagitta *= _scale_factor(transform)
    return [
        _seg(handle,
             [_apply(transform, start[0], start[1]),
              _apply(transform, end[0], end[1])],
             layer, "arc-chord", sagitta=sagitta)
    ]


def _mline(entity, transform, handle, layer):
    """MLINE -> component line segments.

    Reconstructed from ezdxf's virtual_entities() (the exploded LINE/ARC parts of
    the multiline). We keep the MLINE's own handle on every component so callers
    can trace segments back to the source entity. If the installed ezdxf cannot
    explode this MLINE we return [] rather than crash.
    """
    out = []
    try:
        for ve in entity.virtual_entities():
            vt = ve.dxftype()
            if vt == "LINE":
                out.extend(_line(ve, transform, handle, layer))
            elif vt == "ARC":
                out.extend(_arc(ve, transform, handle, layer))
    except Exception:
        return []
    return out


_DISPATCH = {
    "LINE": _line,
    "LWPOLYLINE": _lwpolyline,
    "POLYLINE": _polyline,
    "ARC": _arc,
    "MLINE": _mline,
}


def entity_to_segments(entity, transform=None):
    """Convert a single DXF entity to a list of SEG-IR segment dicts.

    `transform` is a 2x3 affine ((a,b,tx),(c,d,ty)) or None (identity). It is
    applied to every emitted point so insert_expand.py can inject composed block
    transforms. INSERT and any unsupported entity type return [] (no crash).
    Emitted segments carry sid=None; the assembler (parse_modelspace / the
    injected caller) assigns final sids.
    """
    try:
        dxftype = entity.dxftype()
    except Exception:
        return []
    fn = _DISPATCH.get(dxftype)
    if fn is None:
        return []
    dxf = getattr(entity, "dxf", None)
    handle = getattr(dxf, "handle", None)
    layer = getattr(dxf, "layer", "0")
    try:
        return fn(entity, transform, handle, layer)
    except Exception:
        # Malformed / degenerate geometry must not crash the whole parse.
        return []


# --------------------------------------------------------------------------- #
# modelspace assembly
# --------------------------------------------------------------------------- #
def _units_from_doc(doc):
    """Map the DXF $INSUNITS header to the SEG-IR units enum.

    4 == millimeters in the DXF spec. Anything else -> "unknown"; precise
    scale inference is unit_anchor.py's job, not ours.
    """
    try:
        insunits = doc.header.get("$INSUNITS", 0)
    except Exception:
        insunits = 0
    return "mm" if insunits == 4 else "unknown"


def _finalize(drawing_id, units, segments):
    """Assign sequential sids and wrap segments in the SEG-IR v1 envelope."""
    for i, seg in enumerate(segments, start=1):
        seg["sid"] = "s%04d" % i
    return {
        "ir": IR_VERSION,
        "drawing_id": drawing_id,
        "units": units,
        "scale_mm_per_unit": None,
        "segments": segments,
    }


def parse_modelspace(dxf_path, expand_inserts=False):
    """Parse a DXF modelspace into a SEG-IR v1 dict.

    expand_inserts=False (default) SKIPS INSERT entities: recursion into block
    references is owned by insert_expand.py (S4-B), which cli.py wires by
    injecting entity_to_segments. This module never imports that sibling, so it
    cannot expand inserts itself; expand_inserts=True is therefore treated the
    same as False here (INSERTs skipped) and the caller is expected to route
    expansion through insert_expand.expand().
    """
    if ezdxf is None:
        raise RuntimeError("ezdxf is required for parse_modelspace but is not installed")
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    units = _units_from_doc(doc)
    segments = []
    for entity in msp:
        if entity.dxftype() == "INSERT":
            # S4-B owns INSERT recursion; skip here regardless of the flag.
            continue
        segments.extend(entity_to_segments(entity, None))
    drawing_id = os.path.splitext(os.path.basename(dxf_path))[0]
    return _finalize(drawing_id, units, segments)


# --------------------------------------------------------------------------- #
# selftest
# --------------------------------------------------------------------------- #
def _build_fixture(path):
    """Build a small self-contained DXF fixture in the OS temp dir.

    Contents: two LINEs, one closed LWPOLYLINE, one ARC, and a nested INSERT
    (OUTER block references INNER block; both carry DOOR-layer geometry). Header
    $INSUNITS is set to 4 (mm) so units inference has something to read.
    """
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4  # millimeters
    msp = doc.modelspace()

    msp.add_line((0, 0), (1000, 0), dxfattribs={"layer": "WALL"})
    msp.add_line((1000, 0), (1000, 800), dxfattribs={"layer": "WALL"})
    msp.add_lwpolyline([(0, 0), (0, 800), (1000, 800)],
                       dxfattribs={"layer": "WALL"}, close=True)
    msp.add_arc(center=(500, 400), radius=200, start_angle=0, end_angle=90,
                dxfattribs={"layer": "CURVE"})

    inner = doc.blocks.new("INNER")
    inner.add_line((0, 0), (100, 0), dxfattribs={"layer": "DOOR"})
    outer = doc.blocks.new("OUTER")
    outer.add_blockref("INNER", (50, 50))
    outer.add_line((0, 0), (0, 100), dxfattribs={"layer": "DOOR"})
    msp.add_blockref("OUTER", (200, 200),
                     dxfattribs={"xscale": 2, "yscale": 2, "rotation": 30})

    doc.saveas(path)


def _approx(a, b, tol=1e-6):
    return abs(a - b) <= tol


def _selftest():
    import tempfile

    checks = []  # (name, ok, detail)

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    tmpdir = tempfile.mkdtemp(prefix="s4a_normalize_")
    fixture = os.path.join(tmpdir, "s4a_fixture.dxf")
    _build_fixture(fixture)
    check("fixture built", os.path.exists(fixture), fixture)

    ir = parse_modelspace(fixture, expand_inserts=False)

    # Envelope shape / exact top-level keys.
    check("ir version", ir.get("ir") == "seg.v1", ir.get("ir"))
    check("top-level keys",
          set(ir.keys()) == {"ir", "drawing_id", "units", "scale_mm_per_unit", "segments"},
          sorted(ir.keys()))
    check("drawing_id from filename", ir["drawing_id"] == "s4a_fixture", ir["drawing_id"])
    check("units == mm (INSUNITS=4)", ir["units"] == "mm", ir["units"])
    check("scale_mm_per_unit is None", ir["scale_mm_per_unit"] is None, ir["scale_mm_per_unit"])

    segs = ir["segments"]
    kinds = [s["kind"] for s in segs]
    # 2 lines + closed 3-pt polyline (3 edges) + 1 arc = 6 segments; INSERT skipped.
    check("segment count == 6 (INSERT skipped)", len(segs) == 6, len(segs))
    check("line count == 2", kinds.count("line") == 2, kinds.count("line"))
    check("poly-edge count == 3 (closed loop)", kinds.count("poly-edge") == 3,
          kinds.count("poly-edge"))
    check("arc-chord count == 1", kinds.count("arc-chord") == 1, kinds.count("arc-chord"))

    # INSERT geometry must NOT leak in (DOOR layer lives only inside blocks).
    layers = {s["layer"] for s in segs}
    check("no DOOR-layer geometry (INSERT skipped)", "DOOR" not in layers, sorted(layers))

    # sids sequential and zero-padded.
    sids = [s["sid"] for s in segs]
    check("sids sequential s0001..s0006",
          sids == ["s%04d" % i for i in range(1, 7)], sids)

    # Every segment has the exact required keys (+ sagitta only on arc-chord).
    required = {"sid", "handle", "pts", "layer", "kind", "label", "source"}
    keys_ok = True
    for s in segs:
        base = set(s.keys())
        if s["kind"] == "arc-chord":
            if base != required | {"sagitta"}:
                keys_ok = False
        elif base != required:
            keys_ok = False
    check("segment keys exact (sagitta only on arc-chord)", keys_ok)

    # handle present and non-null for native geometry.
    check("handles non-null", all(s["handle"] for s in segs))
    check("labels default unknown", all(s["label"] == "unknown" for s in segs))
    check("source native", all(s["source"] == "native" for s in segs))

    # Arc geometry: chord endpoints and sagitta.
    arc = next(s for s in segs if s["kind"] == "arc-chord")
    (ax1, ay1), (ax2, ay2) = arc["pts"]
    check("arc chord start == (700,400)", _approx(ax1, 700) and _approx(ay1, 400),
          arc["pts"][0])
    check("arc chord end == (500,600)", _approx(ax2, 500) and _approx(ay2, 600),
          arc["pts"][1])
    # sagitta for r=200, 90deg sweep = 200*(1-cos45) ~= 58.5786
    check("arc sagitta ~= 58.5786",
          _approx(arc["sagitta"], 200 * (1 - math.cos(math.radians(45))), tol=1e-4),
          arc["sagitta"])

    # Closed polyline produced the wrap-around edge (last vertex -> first vertex).
    poly = [s for s in segs if s["kind"] == "poly-edge"]
    last_edge = poly[-1]["pts"]
    check("closed poly wrap edge (1000,800)->(0,0)",
          _approx(last_edge[0][0], 1000) and _approx(last_edge[0][1], 800)
          and _approx(last_edge[1][0], 0) and _approx(last_edge[1][1], 0),
          last_edge)

    # --- entity_to_segments transform injection (unit-level) ---
    import ezdxf as _ez
    doc2 = _ez.new("R2010")
    msp2 = doc2.modelspace()
    ln = msp2.add_line((0, 0), (10, 0))
    # translate (+100,+200) then check both endpoints moved.
    t_translate = ((1, 0, 100), (0, 1, 200))
    tsegs = entity_to_segments(ln, t_translate)
    check("translate transform applied",
          len(tsegs) == 1
          and _approx(tsegs[0]["pts"][0][0], 100) and _approx(tsegs[0]["pts"][0][1], 200)
          and _approx(tsegs[0]["pts"][1][0], 110) and _approx(tsegs[0]["pts"][1][1], 200),
          tsegs[0]["pts"] if tsegs else None)

    # scale-only transform (2x) doubles arc sagitta.
    arc_e = msp2.add_arc(center=(0, 0), radius=100, start_angle=0, end_angle=90)
    t_scale = ((2, 0, 0), (0, 2, 0))
    a_plain = entity_to_segments(arc_e, None)[0]["sagitta"]
    a_scaled = entity_to_segments(arc_e, t_scale)[0]["sagitta"]
    check("scale transform doubles sagitta",
          _approx(a_scaled, a_plain * 2, tol=1e-4), (a_plain, a_scaled))

    # Unsupported entity types return [] (no crash).
    txt = msp2.add_text("hello")
    circ = msp2.add_circle((0, 0), 5)
    check("TEXT ignored -> []", entity_to_segments(txt) == [], entity_to_segments(txt))
    check("CIRCLE ignored -> []", entity_to_segments(circ) == [], entity_to_segments(circ))
    doc2.blocks.new("BLK").add_line((0, 0), (1, 1))
    ins = msp2.add_blockref("BLK", (0, 0))
    check("INSERT via entity_to_segments -> [] (dispatch skip)",
          entity_to_segments(ins) == [], entity_to_segments(ins))

    # --- report ---
    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    print("=" * 64)
    print("S4-A normalize.py selftest")
    print("fixture:", fixture)
    print("segments parsed (expand_inserts=False):", len(segs))
    print("kinds:", {k: kinds.count(k) for k in sorted(set(kinds))})
    print("-" * 64)
    for name, ok, detail in checks:
        line = "  [%s] %s" % ("PASS" if ok else "FAIL", name)
        if not ok or detail != "":
            line += "  -> %r" % (detail,)
        print(line)
    print("-" * 64)
    print("sample segment[0]:", segs[0])
    print("arc-chord segment:", arc)
    print("=" * 64)
    print("RESULT: %d/%d checks passed -> %s"
          % (passed, total, "PASS" if passed == total else "FAIL"))
    return 0 if passed == total else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    print(__doc__)
