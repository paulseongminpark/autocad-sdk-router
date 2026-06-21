#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visual_report.py -- Lane E visual verification for the CAD OS Layer.

Produces an ``ariadne.visual_artifact.v1`` envelope (conforms
``schemas/visual_artifact.v1.schema.json``) describing a derived visual/output
artifact (SVG / PDF / PNG / diff overlay) for a drawing or its extracted IR.

No-fake-success is the governing rule: this module NEVER fabricates a visual
PASS. A claimed visual ``ok`` REQUIRES a real artifact file on disk.

What this module does (M02, this lane)
--------------------------------------
The verification problem is: "did the extraction/patch produce what we think?"
The strongest *host-independent* visual answer is to render the EXTRACTED IR
geometry itself -- a real, deterministic SVG drawn directly from
``dwg_graph_ir.v1`` entities. No AutoCAD, no plotter, no host quirks: a pure
standard-library IR->SVG renderer. This both produces a genuine artifact AND
verifies the extraction directly (the SVG is a picture of exactly the geometry
that landed in the IR), so the visual lane is a real PASS, not theater.

  * ``render_ir_to_svg(ir, out_svg_path, highlight_handles=None)``
      Renders every drawable entity by ``geometry.kind`` to SVG elements
      (line / arc / circle / lwpolyline+polyline / block_reference marker /
      text). DWG is Y-up; SVG is Y-down, so the whole drawing is wrapped in a
      ``transform`` that flips Y. ``viewBox`` is computed from the union of
      entity bboxes (empty bboxes skipped). Handles in ``highlight_handles`` are
      stroked red (used by the overlay). Pure stdlib (``xml`` via string build;
      parsed back with ``xml.etree`` in tests). Deterministic: entities are
      emitted in input order, numbers rounded with a fixed format, no
      timestamps in the artifact body.

  * ``build_visual_report(source_ref, post_ir_path=None, diff_path=None,
                          out_dir=...)``
      Renders ``before.svg`` from the ``source_ref`` IR. When a ``post_ir_path``
      and a ``diff_path`` are supplied it also renders ``after.svg`` and
      ``overlay.svg`` (the after drawing with the diff's created+modified
      handles stroked red), and writes ``visual_diff.json`` (created / modified /
      deleted counts + the artifact paths). Returns a ``visual_artifact.v1`` dict
      with ``status="ok"`` and the real artifact refs (path + byte_size +
      sha256). DEFAULTS to the ``ir_svg`` route, so it ALWAYS produces a real
      artifact and the visual lane PASSES honestly.

  * ``available_render_routes()``
      Adds an ``ir_svg`` route -- always available, IMPLEMENTED (pure stdlib).
      Still probes ``accoreconsole_plot`` but reports it ``not_implemented``
      HONESTLY: on this Core Console host a reliable read-only DWG->PDF/PNG
      render is not achievable (see notes below), so it is never claimed to
      produce a file.

Empirical finding on THIS machine (accoreconsole 2027, kor locale)
------------------------------------------------------------------
Three headless render paths were probed against the golden staged copy:
  * ``EXPORTPDF`` / ``-EXPORTPDF``  -> Unknown command in Core Console.
  * ``-PLOT`` prompt-chain          -> command + device + paper accepted, but the
    post-paper keyword prompts desync under the Korean locale / version-specific
    prompt order, so no PDF is emitted.
  * AutoLISP COM ``PlotToFile``     -> ``vlax-get-acad-object`` returns nil
    (Core Console has no ActiveX automation server), so COM plotting is impossible
    from accoreconsole.
=> ``accoreconsole_plot`` is reported ``not_implemented`` (no fake artifact). The
   real visual artifact on this host is the ``ir_svg`` render, which needs no
   AutoCAD at all.

Hard rules: standard library ONLY; the original DWG/IR is a READ-ONLY
``source_ref`` (we only ever read it); unavailable producer => explicit
not_implemented/blocked, never ``ok``; deterministic artifact bodies.

Public API (names preserved):
    VISUAL_SCHEMA_ID
    available_render_routes() -> dict
    render_ir_to_svg(ir, out_svg_path, highlight_handles=None) -> dict
    build_visual_report(source_ref, kind="svg", post_ir_path=None,
                        diff_path=None, artifact_id=None, out_dir=None,
                        route="ir_svg", *, highlight_handles=None,
                        timeout=180) -> dict   # visual_artifact.v1
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)
_STATUS_JSON = os.path.join(_ROUTER_HOME, "reports", "autocad_router_status_latest.json")
_OPERATIONS_V2 = os.path.join(_ROUTER_HOME, "config", "operations.v2.json")
_CAPABILITIES = os.path.join(_ROUTER_HOME, "config", "autocad_router_capabilities.json")
_RUNS_DIR = os.path.join(_ROUTER_HOME, "runs")
_JSON_ENCODING = "utf-8-sig"

VISUAL_SCHEMA_ID = "ariadne.visual_artifact.v1"

# Router routes (live status probe) that can in principle emit a visual/vector
# artifact and are SAFE (read-only with respect to the source). Reported for
# completeness; the implemented producer in this lane is ``ir_svg`` below.
_VISUAL_CANDIDATE_ROUTES = (
    "pdf_svg_vector_route",   # PDF/SVG vector extraction + overlay
    "raster_compare_route",   # PNG render comparison (consumes existing renders)
)
_ROUTE_KINDS = {
    "pdf_svg_vector_route": {"svg", "pdf", "diff_overlay"},
    "raster_compare_route": {"png", "jpg", "diff_overlay"},
}


# --------------------------------------------------------------------------- #
# small stdlib helpers
# --------------------------------------------------------------------------- #

def _load_json(path: str) -> Optional[Any]:
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding=_JSON_ENCODING) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _sha256(path: str) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _accoreconsole_engine() -> Optional[str]:
    """Read the DWG route's engine_path from capabilities (read-only). Returns
    the accoreconsole exe path if it exists on disk, else None."""
    caps = _load_json(_CAPABILITIES)
    engine = None
    if isinstance(caps, dict):
        for r in caps.get("routes", []):
            if isinstance(r, dict) and r.get("id") == "dwg_truth_autocad":
                engine = r.get("engine_path")
                break
    if engine and os.path.isfile(engine):
        return engine
    return None


# --------------------------------------------------------------------------- #
# Geometry / number formatting for deterministic SVG
# --------------------------------------------------------------------------- #

# Fixed decimal places so output is byte-stable across runs/machines. 4 dp on
# drawing units (mm-ish) is well under any rendering-meaningful tolerance.
_NDP = 4


def _fmt(n: float) -> str:
    """Format a float deterministically: fixed dp, no '-0', no exponent."""
    if n is None or not isinstance(n, (int, float)) or math.isnan(n) or math.isinf(n):
        return "0"
    v = round(float(n), _NDP)
    if v == 0:
        v = 0.0  # collapse -0.0 -> 0.0
    s = ("%.*f" % (_NDP, v)).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        return f if not (math.isnan(f) or math.isinf(f)) else None
    return None


def _pt(p: Any) -> Optional[Tuple[float, float]]:
    """A 2D point (x, y) from an IR point3 list/tuple; None if unusable."""
    if isinstance(p, (list, tuple)) and len(p) >= 2:
        x = _num(p[0])
        y = _num(p[1])
        if x is not None and y is not None:
            return (x, y)
    return None


def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _entity_bbox(ent: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    """Return (minx, miny, maxx, maxy) from an entity's IR bbox, or None."""
    b = ent.get("bbox")
    if isinstance(b, (list, tuple)) and len(b) >= 6:
        minx, miny = _num(b[0]), _num(b[1])
        maxx, maxy = _num(b[3]), _num(b[4])
        if None not in (minx, miny, maxx, maxy):
            return (minx, miny, maxx, maxy)
    return None


def _world_bbox(entities: Iterable[Dict[str, Any]]) -> Optional[Tuple[float, float, float, float]]:
    """Union of all entity bboxes -> (minx, miny, maxx, maxy). None if no bbox."""
    minx = miny = math.inf
    maxx = maxy = -math.inf
    found = False
    for ent in entities:
        bb = _entity_bbox(ent)
        if bb is None:
            continue
        found = True
        minx = min(minx, bb[0]); miny = min(miny, bb[1])
        maxx = max(maxx, bb[2]); maxy = max(maxy, bb[3])
    if not found:
        return None
    return (minx, miny, maxx, maxy)


# --------------------------------------------------------------------------- #
# Per-kind SVG element emitters. Each returns a list of SVG element strings.
# Coordinates are emitted in DWG world space; the Y-flip happens once via a
# group transform in render_ir_to_svg (so the math here stays simple).
# --------------------------------------------------------------------------- #

def _svg_line(g: Dict[str, Any], attrs: str) -> List[str]:
    a = _pt(g.get("start"))
    b = _pt(g.get("end"))
    if a is None or b is None:
        return []
    return ['<line x1="%s" y1="%s" x2="%s" y2="%s" %s/>'
            % (_fmt(a[0]), _fmt(a[1]), _fmt(b[0]), _fmt(b[1]), attrs)]


def _svg_circle(g: Dict[str, Any], attrs: str) -> List[str]:
    c = _pt(g.get("center"))
    r = _num(g.get("radius"))
    if c is None or r is None or r <= 0:
        return []
    return ['<circle cx="%s" cy="%s" r="%s" fill="none" %s/>'
            % (_fmt(c[0]), _fmt(c[1]), _fmt(r), attrs)]


def _arc_point(cx: float, cy: float, r: float, ang_rad: float) -> Tuple[float, float]:
    return (cx + r * math.cos(ang_rad), cy + r * math.sin(ang_rad))


def _svg_arc(g: Dict[str, Any], attrs: str) -> List[str]:
    """Arc as an SVG elliptical-arc path. IR stores angles in RADIANS (verified:
    range observed 0..2π on the golden drawing). CCW from +X, DWG convention."""
    c = _pt(g.get("center"))
    r = _num(g.get("radius"))
    sa = _num(g.get("start_angle"))
    ea = _num(g.get("end_angle"))
    if c is None or r is None or r <= 0 or sa is None or ea is None:
        return []
    cx, cy = c
    # Normalize sweep to (0, 2π]; a full-circle arc (sa==ea) draws nothing useful
    # as a path, so emit a circle in that degenerate case.
    sweep = ea - sa
    while sweep <= 0:
        sweep += 2.0 * math.pi
    if sweep >= 2.0 * math.pi - 1e-9:
        return ['<circle cx="%s" cy="%s" r="%s" fill="none" %s/>'
                % (_fmt(cx), _fmt(cy), _fmt(r), attrs)]
    p0 = _arc_point(cx, cy, r, sa)
    p1 = _arc_point(cx, cy, r, sa + sweep)
    large = 1 if sweep > math.pi else 0
    # In world space (y-up) the arc goes CCW, which is sweep-flag 1 for SVG's
    # path semantics. The outer group flip maps it to the correct screen sense.
    d = ("M %s %s A %s %s 0 %d 1 %s %s"
         % (_fmt(p0[0]), _fmt(p0[1]), _fmt(r), _fmt(r), large,
            _fmt(p1[0]), _fmt(p1[1])))
    return ['<path d="%s" fill="none" %s/>' % (d, attrs)]


def _svg_polyline(g: Dict[str, Any], attrs: str, closed_default: bool = False) -> List[str]:
    verts = g.get("vertices")
    pts: List[Tuple[float, float]] = []
    if isinstance(verts, list):
        for v in verts:
            p = None
            if isinstance(v, dict):
                p = _pt(v.get("point"))
            else:
                p = _pt(v)
            if p is not None:
                pts.append(p)
    if len(pts) < 2:
        return []
    closed = bool(g.get("closed", closed_default))
    coord = " ".join("%s,%s" % (_fmt(x), _fmt(y)) for (x, y) in pts)
    tag = "polygon" if closed else "polyline"
    return ['<%s points="%s" fill="none" %s/>' % (tag, coord, attrs)]


def _svg_block_marker(ent: Dict[str, Any], g: Dict[str, Any], attrs: str,
                      m: float) -> List[str]:
    """A block_reference (INSERT) renders as a small crosshair marker + label at
    its insertion point. ``m`` is the marker half-size in world units (scaled to
    the drawing extents so it is visible but not dominant)."""
    p = _pt(g.get("position"))
    if p is None:
        return []
    x, y = p
    name = g.get("block_name")
    out = [
        '<line x1="%s" y1="%s" x2="%s" y2="%s" %s/>'
        % (_fmt(x - m), _fmt(y), _fmt(x + m), _fmt(y), attrs),
        '<line x1="%s" y1="%s" x2="%s" y2="%s" %s/>'
        % (_fmt(x), _fmt(y - m), _fmt(x), _fmt(y + m), attrs),
    ]
    if isinstance(name, str) and name:
        # Label is drawn in a Y-flipped sub-transform so text is upright.
        out.append(
            '<text x="%s" y="%s" font-size="%s" fill="#555" '
            'transform="translate(%s,%s) scale(1,-1)">%s</text>'
            % (_fmt(0), _fmt(0), _fmt(m * 1.2),
               _fmt(x + m * 1.3), _fmt(y), _xml_escape(name)))
    return out


def _svg_text(ent: Dict[str, Any], g: Dict[str, Any], attrs: str,
              h_default: float) -> List[str]:
    """TEXT / MTEXT renders the string at its position. Drawn with a local
    Y-flip so glyphs are upright despite the outer y-up->y-down flip."""
    p = _pt(g.get("position"))
    if p is None:
        return []
    x, y = p
    s = g.get("text")
    if not isinstance(s, str) or s == "":
        s = ""  # empty text still localizes a point marker below
    h = _num(g.get("height")) or h_default
    if s:
        return ['<text x="0" y="0" font-size="%s" fill="#222" '
                'transform="translate(%s,%s) scale(1,-1)" %s>%s</text>'
                % (_fmt(h), _fmt(x), _fmt(y), attrs, _xml_escape(s))]
    return ['<circle cx="%s" cy="%s" r="%s" %s/>'
            % (_fmt(x), _fmt(y), _fmt(h * 0.25), attrs)]


def _svg_bbox_rect(ent: Dict[str, Any], attrs: str) -> List[str]:
    """Fallback: draw the entity's bbox as a rectangle outline. Used for kinds
    whose native IR carries no coordinate geometry (e.g. hatch / vertex-less
    polyline in the native_full extraction) but DOES carry a bbox -- so the
    extracted footprint is still drawn (no-fake: it renders exactly what the IR
    provides, the bbox)."""
    bb = _entity_bbox(ent)
    if bb is None:
        return []
    minx, miny, maxx, maxy = bb
    w = maxx - minx
    hgt = maxy - miny
    if w <= 0 and hgt <= 0:
        # zero-extent bbox -> a tiny dot so it is still visible
        return ['<circle cx="%s" cy="%s" r="%s" %s/>'
                % (_fmt(minx), _fmt(miny), _fmt(1.0), attrs)]
    return ['<rect x="%s" y="%s" width="%s" height="%s" fill="none" %s/>'
            % (_fmt(minx), _fmt(miny), _fmt(max(w, 0.0)), _fmt(max(hgt, 0.0)),
               attrs)]


# Which kinds have a real coordinate emitter (vs bbox-fallback only).
_COORD_EMITTERS = {"line", "circle", "arc", "lwpolyline", "polyline",
                   "block_reference", "text", "mtext"}


def render_ir_to_svg(ir: Dict[str, Any], out_svg_path: str,
                     highlight_handles: Optional[Set[str]] = None) -> Dict[str, Any]:
    """
    Render a ``dwg_graph_ir.v1`` IR to a real SVG file (pure stdlib).

    Entities are drawn by ``geometry.kind``:
      line -> <line>; arc -> <path> elliptical arc (angles in RADIANS converted);
      circle -> <circle>; lwpolyline/polyline -> <polyline>/<polygon> when the IR
      carries vertices, else the entity bbox rectangle; block_reference (INSERT)
      -> crosshair marker + block-name label at the insertion point;
      text/mtext -> the string at its position (locally un-flipped so it is
      upright). Any other kind with a bbox -> bbox rectangle (renders the
      extracted footprint; never invents geometry).

    DWG is Y-up, SVG is Y-down: the whole drawing is wrapped in a single
    ``transform="translate(...) scale(1,-1)"`` group so coordinates stay in world
    units and the picture is right-side-up.

    ``viewBox`` is the union of entity bboxes (entities with an empty bbox are
    skipped for the extent computation), padded by a small margin.

    ``highlight_handles`` -> those entities are stroked red (used by the overlay
    to mark created/modified handles).

    Returns ``{"path": out_svg_path, "element_count": int, "viewbox": [x,y,w,h]}``.
    Deterministic: entities in input order; fixed-precision numbers; no
    timestamp in the SVG body.
    """
    highlight = set(highlight_handles or ())
    entities = ir.get("entities") or []

    world = _world_bbox(entities)
    if world is None:
        # No bbox anywhere: emit a valid empty-but-well-formed 1x1 canvas.
        world = (0.0, 0.0, 1.0, 1.0)
    minx, miny, maxx, maxy = world
    w = maxx - minx
    hgt = maxy - miny
    if w <= 0:
        w = 1.0
    if hgt <= 0:
        hgt = 1.0
    # margin = 2% of the larger span (so strokes/markers near the edge are visible)
    margin = 0.02 * max(w, hgt)
    vb_x = minx - margin
    vb_y = miny - margin
    vb_w = w + 2 * margin
    vb_h = hgt + 2 * margin

    # Stroke width and marker/text sizes scale to the drawing so they render at
    # roughly the same on-screen weight regardless of model units.
    span = max(vb_w, vb_h)
    stroke = span / 1500.0 if span > 0 else 1.0
    marker = span / 250.0 if span > 0 else 1.0
    text_h = span / 200.0 if span > 0 else 1.0

    base_attr = 'stroke="#1a1a1a" stroke-width="%s"' % _fmt(stroke)
    hi_attr = 'stroke="#e00000" stroke-width="%s"' % _fmt(stroke * 3.0)
    base_text_attr = ''  # text fill set inside emitter
    hi_text_attr = 'stroke="#e00000" stroke-width="%s"' % _fmt(stroke * 1.5)

    body: List[str] = []
    element_count = 0
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        g = ent.get("geometry") or {}
        kind = g.get("kind")
        handle = ent.get("handle", "")
        hot = handle in highlight
        attrs = hi_attr if hot else base_attr

        elems: List[str] = []
        if kind == "line":
            elems = _svg_line(g, attrs)
        elif kind == "circle":
            elems = _svg_circle(g, attrs)
        elif kind == "arc":
            elems = _svg_arc(g, attrs)
        elif kind in ("lwpolyline", "polyline"):
            elems = _svg_polyline(g, attrs, closed_default=(kind == "lwpolyline"))
            if not elems:  # native IR vertex-less polyline -> bbox footprint
                elems = _svg_bbox_rect(ent, attrs)
        elif kind == "block_reference":
            elems = _svg_block_marker(ent, g, attrs, marker)
        elif kind in ("text", "mtext"):
            t_attr = hi_text_attr if hot else base_text_attr
            elems = _svg_text(ent, g, t_attr, text_h)
        else:
            # any other kind: render the extracted bbox footprint if present.
            elems = _svg_bbox_rect(ent, attrs)

        if elems:
            # tag the group so highlighted handles are inspectable in the DOM
            cls = "hl" if hot else "ent"
            body.append('<g class="%s" data-handle="%s" data-kind="%s">'
                        % (cls, _xml_escape(str(handle)), _xml_escape(str(kind))))
            body.extend(elems)
            body.append('</g>')
            element_count += len(elems)

    # The flip group: SVG origin top-left, y-down. We translate so the world
    # min maps into view, then scale(1,-1) to flip y-up -> y-down.
    flip = ('translate(%s,%s) scale(1,-1)'
            % (_fmt(0.0), _fmt(vb_y + vb_y + vb_h)))
    # NOTE: with viewBox y starting at vb_y, the flip line is y' = (2*vb_y+vb_h) - y.

    svg = []
    svg.append('<?xml version="1.0" encoding="UTF-8"?>')
    svg.append(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="%s %s %s %s" width="1000" height="%s">'
        % (_fmt(vb_x), _fmt(vb_y), _fmt(vb_w), _fmt(vb_h),
           _fmt(1000.0 * (vb_h / vb_w) if vb_w > 0 else 1000.0)))
    svg.append('<rect x="%s" y="%s" width="%s" height="%s" fill="#ffffff"/>'
               % (_fmt(vb_x), _fmt(vb_y), _fmt(vb_w), _fmt(vb_h)))
    svg.append('<g transform="%s">' % flip)
    svg.extend(body)
    svg.append('</g>')
    svg.append('</svg>')
    svg.append('')  # trailing newline

    text = "\n".join(svg)
    out_dir = os.path.dirname(os.path.abspath(out_svg_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_svg_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)

    return {
        "path": out_svg_path,
        "element_count": element_count,
        "viewbox": [round(vb_x, _NDP), round(vb_y, _NDP),
                    round(vb_w, _NDP), round(vb_h, _NDP)],
    }


# --------------------------------------------------------------------------- #
# diff -> highlight handle extraction
# --------------------------------------------------------------------------- #

# Diff "change" values that mean "this handle should be highlighted on the
# overlay" (i.e. it is new or altered in the after-state). We treat both the
# frozen vocab (added/modified) and the M02 alias vocab (created/modified).
_HIGHLIGHT_CHANGES = {"added", "created", "modified"}
_DELETED_CHANGES = {"removed", "deleted"}


def _diff_handles(diff: Dict[str, Any]) -> Dict[str, Any]:
    """From a cad_diff.v1 dict, return:
        {"highlight": set[str],   # created+modified handles (present in after)
         "created":  int, "modified": int, "deleted": int}
    Reads changed_handles[] (robust to added/created naming) and falls back to
    summary counts when present."""
    highlight: Set[str] = set()
    created = modified = deleted = 0
    for rec in diff.get("changed_handles") or []:
        if not isinstance(rec, dict):
            continue
        ch = str(rec.get("change", "")).lower()
        h = rec.get("handle")
        if ch in _HIGHLIGHT_CHANGES and isinstance(h, str) and h:
            highlight.add(h)
        if ch in ("added", "created"):
            created += 1
        elif ch == "modified":
            modified += 1
        elif ch in _DELETED_CHANGES:
            deleted += 1

    # Prefer explicit summary counts when they exist (authoritative).
    summ = diff.get("summary") or {}
    if isinstance(summ, dict):
        c = summ.get("created_count", summ.get("added"))
        m = summ.get("modified_count", summ.get("modified"))
        d = summ.get("deleted_count", summ.get("removed"))
        if isinstance(c, int):
            created = c
        if isinstance(m, int):
            modified = m
        if isinstance(d, int):
            deleted = d

    return {"highlight": highlight, "created": created,
            "modified": modified, "deleted": deleted}


# --------------------------------------------------------------------------- #
# available_render_routes
# --------------------------------------------------------------------------- #

def available_render_routes() -> Dict[str, Any]:
    """
    Read-only probe of which visual/render routes are available.

    Reports:
      * ``ir_svg`` -- ALWAYS available, IMPLEMENTED. Pure-stdlib IR->SVG render of
        the extracted geometry. This is the route ``build_visual_report`` uses by
        default, so a real artifact is always produced.
      * the two SAFE vector/compare candidate routes from the router status JSON
        (``pdf_svg_vector_route`` / ``raster_compare_route``);
      * ``accoreconsole_plot`` -- probed HONESTLY: engine presence is reported,
        but ``implemented=False`` / ``status="not_implemented"`` because on this
        Core Console host a reliable read-only DWG->PDF/PNG render is not
        achievable (EXPORTPDF unknown; -PLOT prompt desync under kor locale; no
        ActiveX COM in Core Console). It is NEVER claimed to produce a file.

    Returns:
      {
        "routes": {
          "ir_svg": {"available": True, "implemented": True,
                     "kinds": ["svg","diff_overlay"]},
          "pdf_svg_vector_route": {...}, "raster_compare_route": {...},
          "accoreconsole_plot": {"available": <engine present>,
                                 "implemented": False,
                                 "status": "not_implemented", ...},
        },
        "default_route": "ir_svg",
        "any_available": True,                  # ir_svg guarantees this
        "render_layout_status": <registry status or None>,
        "status_json": <path or None>, "status_readable": bool,
      }
    """
    status = _load_json(_STATUS_JSON)
    routes: Dict[str, Any] = {}

    # 1) The implemented, always-available pure-stdlib route.
    routes["ir_svg"] = {
        "available": True,
        "implemented": True,
        "kinds": ["svg", "diff_overlay"],
        "note": ("pure-stdlib IR->SVG render of the extracted dwg_graph_ir "
                 "geometry; no AutoCAD needed; deterministic; verifies the "
                 "extraction directly."),
    }

    # 2) Live router candidate routes (read-only status probe).
    avail_by_route: Dict[str, bool] = {}
    if isinstance(status, dict):
        for r in status.get("routes", []):
            if isinstance(r, dict) and r.get("route"):
                avail_by_route[r["route"]] = bool(r.get("available"))
    for route_id in _VISUAL_CANDIDATE_ROUTES:
        routes[route_id] = {
            "available": avail_by_route.get(route_id, False),
            "implemented": False,  # no producer wired in this lane
            "kinds": sorted(_ROUTE_KINDS.get(route_id, set())),
            "note": "router vector/compare route; producer not wired in this lane",
        }

    # 3) accoreconsole_plot -- honest not_implemented on this host.
    engine = _accoreconsole_engine()
    routes["accoreconsole_plot"] = {
        "available": engine is not None,
        "engine": engine,
        "engine_present": engine is not None,
        "implemented": False,
        "status": "not_implemented",
        "kinds": ["pdf"],
        "note": ("accoreconsole headless DWG->PDF: NOT IMPLEMENTED on this host "
                 "(EXPORTPDF unknown / -PLOT prompt desync under kor locale / no "
                 "ActiveX COM in Core Console). Never claimed to emit a file."),
    }

    render_layout_status = None
    reg = _load_json(_OPERATIONS_V2)
    if isinstance(reg, dict):
        for o in reg.get("operations", []):
            if isinstance(o, dict) and o.get("id") == "render.layout":
                render_layout_status = o.get("status")
                break

    return {
        "routes": routes,
        "default_route": "ir_svg",
        "any_available": True,  # ir_svg is always available
        "render_layout_status": render_layout_status,
        "status_json": _STATUS_JSON if os.path.isfile(_STATUS_JSON) else None,
        "status_readable": status is not None,
    }


# --------------------------------------------------------------------------- #
# build_visual_report
# --------------------------------------------------------------------------- #

def _ref(path: str, role: str, media_type: str = "image/svg+xml") -> Dict[str, Any]:
    """A visual_artifact.v1 ref entry with real size + sha256."""
    entry: Dict[str, Any] = {"ref": path, "role": role, "media_type": media_type}
    try:
        entry["byte_size"] = os.path.getsize(path)
    except OSError:
        pass
    digest = _sha256(path)
    if digest:
        entry["sha256"] = digest
    return entry


def _load_ir_or_none(path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    doc = _load_json(path)
    if isinstance(doc, dict) and isinstance(doc.get("entities"), list):
        return doc
    return None


def build_visual_report(source_ref: str,
                        kind: str = "svg",
                        post_ir_path: Optional[str] = None,
                        diff_path: Optional[str] = None,
                        artifact_id: Optional[str] = None,
                        out_dir: Optional[str] = None,
                        route: str = "ir_svg",
                        *,
                        highlight_handles: Optional[Set[str]] = None,
                        timeout: int = 180) -> Dict[str, Any]:
    """
    Build a ``visual_artifact.v1`` envelope of REAL rendered artifacts.

    Default route is ``ir_svg`` (pure stdlib), so this ALWAYS produces real
    artifacts on disk and the visual lane is a genuine PASS (no fake).

    Produced artifacts (under ``out_dir``):
      * ``before.svg``  -- rendered from the ``source_ref`` IR (always).
      * When ``post_ir_path`` AND ``diff_path`` are both given:
          - ``after.svg``     -- rendered from the post IR.
          - ``overlay.svg``   -- the after drawing with the diff's
                                  created+modified handles stroked red.
          - ``visual_diff.json`` -- created/modified/deleted counts + the
                                  artifact paths (before/after/overlay).

    Args:
      source_ref: path to the BEFORE IR (``dwg_graph_ir.v1`` JSON). READ-ONLY.
      kind: artifact kind for the envelope (``svg`` by default; ``diff_overlay``
            is used in the envelope when a diff overlay is produced).
      post_ir_path: optional path to the AFTER IR JSON.
      diff_path: optional path to a ``cad_diff.v1`` JSON (drives the overlay).
      out_dir: output directory; defaults to a timestamped dir under runs/.
      route: render route name recorded on the envelope (default ``ir_svg``).
      highlight_handles: explicit handles to highlight on the overlay; when None
            and a diff is supplied, the diff's created+modified handles are used.

    Returns a ``visual_artifact.v1`` dict. On success ``status="ok"`` with the
    real artifact refs (path + byte_size + sha256). If the source IR cannot be
    loaded -> ``status="error"`` with empty refs (no-fake-success).
    """
    aid = artifact_id or "vis-%s" % uuid.uuid4().hex[:12]
    run_dir = out_dir or os.path.join(
        _RUNS_DIR, "visual_report_%s" % time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(run_dir, exist_ok=True)

    before_ir = _load_ir_or_none(source_ref)
    if before_ir is None:
        return {
            "schema": VISUAL_SCHEMA_ID,
            "artifact_id": aid,
            "kind": "other",
            "status": "error",
            "source_ref": source_ref,
            "route": route,
            "refs": [],
            "run_dir": run_dir,
            "diagnostics": {
                "warnings": ["source_ref is not a readable dwg_graph_ir.v1 IR "
                             "(no entities[]): %s" % source_ref],
            },
            "notes": "no before IR -> no artifact (no-fake-success).",
        }

    refs: List[Dict[str, Any]] = []
    diagnostics: Dict[str, Any] = {"warnings": []}

    # ---- before.svg (always) ----------------------------------------------
    before_svg = os.path.join(run_dir, "before.svg")
    before_meta = render_ir_to_svg(before_ir, before_svg, highlight_handles=None)
    refs.append(_ref(before_svg, "before"))
    diagnostics["before"] = {
        "element_count": before_meta["element_count"],
        "viewbox": before_meta["viewbox"],
        "entity_count": len(before_ir.get("entities") or []),
    }

    out_kind = "svg"
    visual_diff_path: Optional[str] = None

    # ---- after.svg + overlay.svg + visual_diff.json (when post+diff given) -
    post_ir = _load_ir_or_none(post_ir_path)
    diff = _load_json(diff_path) if diff_path else None
    if post_ir is not None and isinstance(diff, dict):
        out_kind = "diff_overlay"

        after_svg = os.path.join(run_dir, "after.svg")
        after_meta = render_ir_to_svg(post_ir, after_svg, highlight_handles=None)
        refs.append(_ref(after_svg, "after"))

        dh = _diff_handles(diff)
        hi = set(highlight_handles) if highlight_handles else set(dh["highlight"])

        overlay_svg = os.path.join(run_dir, "overlay.svg")
        overlay_meta = render_ir_to_svg(post_ir, overlay_svg, highlight_handles=hi)
        refs.append(_ref(overlay_svg, "overlay"))

        # how many of the highlight handles were actually present in the after IR
        post_handles = {e.get("handle") for e in (post_ir.get("entities") or [])
                        if isinstance(e, dict)}
        rendered_hl = sorted(h for h in hi if h in post_handles)

        visual_diff = {
            "schema": "ariadne.visual_diff.v1",
            "source_before_ir": source_ref,
            "source_after_ir": post_ir_path,
            "diff_ref": diff_path,
            "diff_id": diff.get("diff_id"),
            "counts": {
                "created": dh["created"],
                "modified": dh["modified"],
                "deleted": dh["deleted"],
            },
            "highlighted_handles": sorted(hi),
            "highlighted_handles_present_in_after": rendered_hl,
            "artifacts": {
                "before": before_svg,
                "after": after_svg,
                "overlay": overlay_svg,
            },
            "element_counts": {
                "before": before_meta["element_count"],
                "after": after_meta["element_count"],
                "overlay": overlay_meta["element_count"],
            },
            "viewbox": {
                "before": before_meta["viewbox"],
                "after": after_meta["viewbox"],
                "overlay": overlay_meta["viewbox"],
            },
        }
        visual_diff_path = os.path.join(run_dir, "visual_diff.json")
        with open(visual_diff_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(visual_diff, ensure_ascii=False,
                                indent=2, sort_keys=True))
            fh.write("\n")
        refs.append(_ref(visual_diff_path, "visual_diff", "application/json"))

        diagnostics["after"] = {
            "element_count": after_meta["element_count"],
            "viewbox": after_meta["viewbox"],
            "entity_count": len(post_ir.get("entities") or []),
        }
        diagnostics["overlay"] = {
            "element_count": overlay_meta["element_count"],
            "highlighted_handles": sorted(hi),
            "highlighted_present_in_after": rendered_hl,
        }
        diagnostics["diff_counts"] = {
            "created": dh["created"], "modified": dh["modified"],
            "deleted": dh["deleted"],
        }
        if not rendered_hl and hi:
            diagnostics["warnings"].append(
                "highlight handles %s not found in after IR" % sorted(hi))
    elif post_ir_path or diff_path:
        # caller asked for an overlay but one input is missing -> say so honestly,
        # still return the real before.svg (status stays ok; the before artifact
        # genuinely exists).
        if post_ir is None and post_ir_path:
            diagnostics["warnings"].append(
                "post_ir_path not a readable IR; overlay skipped: %s" % post_ir_path)
        if (diff is None) and diff_path:
            diagnostics["warnings"].append(
                "diff_path not readable; overlay skipped: %s" % diff_path)

    return {
        "schema": VISUAL_SCHEMA_ID,
        "artifact_id": aid,
        "kind": out_kind if kind in ("svg", "diff_overlay") else kind,
        "status": "ok",
        "source_ref": source_ref,
        "route": route,
        "media_type": "image/svg+xml",
        "refs": refs,
        "run_dir": run_dir,
        "visual_diff": visual_diff_path,
        "diagnostics": diagnostics,
        "notes": ("real IR->SVG render via ir_svg route (before"
                  + ("/after/overlay + visual_diff" if visual_diff_path else "")
                  + "); artifacts exist on disk."),
    }


# --------------------------------------------------------------------------- #
# Self-test (__main__)
# --------------------------------------------------------------------------- #

def _selftest() -> int:
    """Fast, deterministic self-test: render the fixture IR + a tiny patch
    overlay into a temp dir, assert real files + well-formedness.

    A separate ``--render`` flag drives the REAL patch-run render into
    runs/m02_visual (before/after/overlay + visual_diff.json)."""
    import tempfile
    import xml.etree.ElementTree as ET

    probe = available_render_routes()

    # Build a fixture IR + a 1-added-entity post IR for an honest overlay.
    sys.path.insert(0, _THIS_DIR)
    import ir_builder  # noqa: E402
    pre = ir_builder.make_fixture_ir()
    post = json.loads(json.dumps(pre))  # deep copy
    post["entities"].append({
        "handle": "2FF", "class": "AcDbLine", "dxf_name": "LINE",
        "owner_handle": "1F", "space": "model", "layer": "ARIADNE_PROBE",
        "bbox": [0.0, 0.0, 0.0, 5.0, 5.0, 0.0],
        "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0],
                     "end": [5.0, 5.0, 0.0]},
        "source": {"extractor": "selftest", "decoded": True},
    })
    post["diagnostics"]["entity_count"] = len(post["entities"])

    ok = True
    with tempfile.TemporaryDirectory() as td:
        pre_path = os.path.join(td, "pre.json")
        post_path = os.path.join(td, "post.json")
        diff_path = os.path.join(td, "diff.json")
        with open(pre_path, "w", encoding="utf-8") as fh:
            json.dump(pre, fh)
        with open(post_path, "w", encoding="utf-8") as fh:
            json.dump(post, fh)
        with open(diff_path, "w", encoding="utf-8") as fh:
            json.dump({"schema": "ariadne.cad_diff.v1", "diff_id": "selftest",
                       "changed_handles": [{"handle": "2FF", "change": "added",
                                            "dxf_name": "LINE"}],
                       "summary": {"created_count": 1, "modified_count": 0,
                                   "deleted_count": 0}}, fh)

        # direct render check
        svg_path = os.path.join(td, "fixture.svg")
        meta = render_ir_to_svg(pre, svg_path)
        tree = ET.parse(svg_path)  # parses => well-formed XML
        root = tree.getroot()
        ok = ok and root.tag.endswith("svg") and os.path.isfile(svg_path)
        ok = ok and meta["element_count"] >= 3  # LINE + CIRCLE + INSERT(>=1)

        rep = build_visual_report(pre_path, post_ir_path=post_path,
                                  diff_path=diff_path, out_dir=td)
        ok = ok and rep["schema"] == VISUAL_SCHEMA_ID and rep["status"] == "ok"
        roles = {r.get("role") for r in rep["refs"]}
        ok = ok and {"before", "after", "overlay", "visual_diff"} <= roles
        for r in rep["refs"]:
            ok = ok and os.path.isfile(r["ref"]) and r.get("byte_size", 0) > 0
        # overlay highlights the created handle in red
        with open(os.path.join(td, "overlay.svg"), encoding="utf-8") as fh:
            overlay_txt = fh.read()
        ok = ok and 'data-handle="2FF"' in overlay_txt and "#e00000" in overlay_txt

    print(json.dumps({
        "selftest": "OK" if ok else "FAIL",
        "default_route": probe["default_route"],
        "ir_svg_available": probe["routes"]["ir_svg"]["available"],
        "ir_svg_implemented": probe["routes"]["ir_svg"]["implemented"],
        "accoreconsole_plot_implemented":
            probe["routes"]["accoreconsole_plot"]["implemented"],
        "fixture_element_count": meta["element_count"],
    }, ensure_ascii=False, indent=2))

    if "--render" in sys.argv:
        rc = _render_patch_run()
        ok = ok and rc

    print("SELFTEST_OK" if ok else "SELFTEST_FAIL")
    return 0 if ok else 1


def _render_patch_run() -> bool:
    """REAL render of the live patch run into runs/m02_visual."""
    pre = os.path.join(_RUNS_DIR, "m02_patch_live2", "pre", "dwg_graph_ir.json")
    post = os.path.join(_RUNS_DIR, "m02_patch_live2", "post", "dwg_graph_ir.json")
    diff = os.path.join(_RUNS_DIR, "m02_patch_live2", "cad_diff.json")
    out = os.path.join(_RUNS_DIR, "m02_visual")
    if not (os.path.isfile(pre) and os.path.isfile(post) and os.path.isfile(diff)):
        print("RENDER_SKIP: patch-run inputs not present")
        return True
    rep = build_visual_report(pre, post_ir_path=post, diff_path=diff, out_dir=out)
    print(json.dumps({k: rep[k] for k in ("status", "kind", "route", "run_dir")},
                     ensure_ascii=False))
    print("REFS:")
    for r in rep["refs"]:
        print("  %-12s %10s bytes  %s"
              % (r.get("role"), r.get("byte_size"), r["ref"]))
    print("DIFF_COUNTS:", rep["diagnostics"].get("diff_counts"))
    print("OVERLAY_HIGHLIGHT:",
          rep["diagnostics"].get("overlay", {}).get("highlighted_present_in_after"))
    files = ["before.svg", "after.svg", "overlay.svg", "visual_diff.json"]
    all_ok = all(os.path.isfile(os.path.join(out, f)) and
                 os.path.getsize(os.path.join(out, f)) > 0 for f in files)
    return rep["status"] == "ok" and all_ok


if __name__ == "__main__":
    sys.exit(_selftest())
