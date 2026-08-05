#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate a DXF drawing from an ``ariadne.dwg_graph_ir.v1`` IR document.

WHY this exists
---------------
The IR (see ``tools/ir_builder.py``, the schema of record for every field name
used here) is the engine-neutral truth captured from a DWG. Round-trip
verification -- "does the IR carry enough to rebuild the drawing?" -- needs the
other half of the trip: an IR -> DXF regenerator. This module is that half.

Public API
----------
``build_dxf_from_ir(ir, out_path=None, *, inline_block_dims=False,
dxfversion=DEFAULT_DXFVERSION) -> (ezdxf.document.Drawing, BuildReport)``

  * builds the symbol tables, then the block definitions, then the entities;
  * writes the DXF when ``out_path`` is given (the Drawing is returned either
    way, so an in-memory caller never touches the filesystem);
  * NEVER fails silently: every entity that is not rebuilt lands in
    ``BuildReport.skipped`` with a ``"<subject>:<reason>"`` key, and every
    exception lands in ``BuildReport.errors``. A count that goes missing must
    be visible in the report, not inferred from a diff afterwards.

Block-internal dimensions (#51)
-------------------------------
Inlining a block-internal dimension (drawing the ``*D`` anonymous block's
contents in place of the DIMENSION entity) orphans that ``*D`` definition; a
later purge cascade then deletes the INSERTs that referenced it. So the default
is inline OFF -- the ``*D`` definition is preserved and the DIMENSION entity is
created with ``dxf.geometry`` pointing back at it. ``inline_block_dims=True``
selects the opposite trade (needed only by drawings whose DXF->DWG conversion
fails with rc53/eInvalidInput). The *decision* of when to flip the flag --
build, convert, and on rc53 rebuild with inlining -- belongs to the driver
layer, not here: this function is a pure builder and never shells out.

Known gaps (counted in ``BuildReport.skipped``, never silent)
-------------------------------------------------------------
ACIS-backed kinds (``solid3d``/``region``/``surface``/``nurbsurface``/
``body``), ``ole2frame`` (needs the embedded compound document),
``rasterimage``/``image`` (needs the external raster), ``viewport``,
``mline`` (needs the MLINESTYLE table), ``polygon_mesh``/``poly_face_mesh``,
and hatch gradients.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import ezdxf
from ezdxf.document import Drawing
from ezdxf.math import Vec3, open_uniform_knot_vector

DEFAULT_DXFVERSION = "AC1027"  # R2013 -- the version the DWG convert step reads
STANDARD = "Standard"  # ezdxf's pre-created text/dim style name (see #54, #58)

# Kinds that cannot be rebuilt from IR alone -- the reason is the counter key,
# so a caller reading the report learns WHY, not just how many.
_UNREBUILDABLE = {
    "solid3d": "acis_binary_not_in_ir",
    "region": "acis_binary_not_in_ir",
    "surface": "acis_binary_not_in_ir",
    "nurbsurface": "acis_binary_not_in_ir",
    "body": "acis_binary_not_in_ir",
    "ole2frame": "embedded_compound_document_needed",
    "rasterimage": "external_raster_file_needed",
    "image": "external_raster_file_needed",
    "viewport": "layout_viewport_not_rebuilt",
    "mline": "mlinestyle_table_not_rebuilt",
    "polygon_mesh": "not_implemented",
    "poly_face_mesh": "not_implemented",
    "proxy": "proxy_graphics_only",
    "unsupported": "kind_not_decoded_by_extractor",
}


@dataclass
class BuildReport:
    """What the build did, in three counters.

    ``added``   -- geometry kind (or a ``table:*`` event) -> count created.
    ``skipped`` -- ``"<subject>:<reason>"`` -> count NOT reproduced.
    ``errors``  -- ``"<subject>:<ExcType>:<msg>"`` -> count of swallowed failures.
    """

    added: Counter = field(default_factory=Counter)
    skipped: Counter = field(default_factory=Counter)
    errors: Counter = field(default_factory=Counter)

    @property
    def total_added(self) -> int:
        return sum(v for k, v in self.added.items() if not k.startswith("table:"))

    @property
    def total_skipped(self) -> int:
        return sum(self.skipped.values())

    @property
    def total_errors(self) -> int:
        return sum(self.errors.values())

    def to_dict(self) -> dict:
        return {
            "added": dict(self.added),
            "skipped": dict(self.skipped),
            "errors": dict(self.errors),
            "total_added": self.total_added,
            "total_skipped": self.total_skipped,
            "total_errors": self.total_errors,
        }


@dataclass
class _Ctx:
    """Everything a handler needs that is not the entity itself."""

    doc: Drawing
    report: BuildReport
    dim_style_ref: str = STANDARD
    inline_block_dims: bool = False
    block_defs: dict = field(default_factory=dict)  # name -> IR block_definition


# --- small coercions ----------------------------------------------------------

def _num(value, default=None):
    """Return ``value`` as float, or ``default`` when it is not a number."""
    if isinstance(value, bool) or value is None:
        return default
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _p3(value, default=(0.0, 0.0, 0.0)):
    """Coerce an IR point (array form; dict form tolerated) to an (x, y, z) tuple."""
    if isinstance(value, dict):
        return (_num(value.get("x"), 0.0), _num(value.get("y"), 0.0),
                _num(value.get("z"), 0.0))
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (_num(value[0], 0.0), _num(value[1], 0.0),
                _num(value[2], 0.0) if len(value) > 2 else 0.0)
    return default


def _p2(value, default=(0.0, 0.0)):
    p = _p3(value, None)
    return default if p is None else (p[0], p[1])


def _deg(radians, default=0.0):
    r = _num(radians, None)
    return default if r is None else math.degrees(r)


def _vertex_points(geom, *, with_bulge=False):
    """IR ``vertices`` -> point tuples (or (x, y, bulge) triples for LWPOLYLINE)."""
    out = []
    for v in geom.get("vertices") or []:
        if isinstance(v, dict):
            pt = _p3(v.get("point"))
            bulge = _num(v.get("bulge"), 0.0)
        else:
            pt = _p3(v)
            bulge = 0.0
        if with_bulge:
            out.append((pt[0], pt[1], bulge))
        else:
            out.append(pt)
    return out


# --- symbol tables ------------------------------------------------------------

def _layer_attribs(rec: dict) -> dict:
    attrs: dict = {}
    ci = rec.get("color_index")
    if isinstance(ci, int) and -256 <= ci <= 256 and ci != 0:
        attrs["color"] = abs(ci)
    lw = rec.get("lineweight")
    if isinstance(lw, int):
        attrs["lineweight"] = lw
    if rec.get("plottable") is False:
        attrs["plot"] = 0
    return attrs


def _build_layers(doc: Drawing, ir: dict, report: BuildReport) -> None:
    """Create the LAYER table from ``symbol_tables.layers``.

    Two symbol-table casing traps live here, both reproduced against ezdxf
    1.4.3. A new document already holds ``0`` and ``Defpoints`` in ezdxf's OWN
    casing, and table lookup is case-INsensitive, so:

      * #60 -- ``layers.add("DEFPOINTS")`` raises (the pre-created ``Defpoints``
        already occupies that name), the exception gets swallowed, and every
        entity on the original ``DEFPOINTS`` ends up compared against a layer
        that is spelled differently (7,326 POINTs in the HDC 267 run). Fix:
        when the IR name differs from the pre-created one by case ONLY, discard
        the pre-created record and recreate it with the original casing. Safe
        exactly here -- no entity has been created yet.
      * #54's sibling -- the ``Defpoints`` prune guard must compare
        case-INsensitively, or a drawing whose own layer is ``DEFPOINTS`` has
        that very record deleted.
    """
    records = [r for r in ((ir.get("symbol_tables") or {}).get("layers") or [])
               if isinstance(r, dict)]
    ir_folded = {str(r.get("name") or "").strip().casefold() for r in records}
    pre_created = {layer.dxf.name.casefold(): layer.dxf.name for layer in doc.layers}
    seen = set()
    for rec in records:
        name = str(rec.get("name") or "").strip()
        folded = name.casefold()
        if not name or folded in seen:
            continue
        seen.add(folded)
        pre_name = pre_created.get(folded)
        if pre_name is not None and pre_name != name:
            try:
                doc.layers.discard(pre_name)
                pre_created.pop(folded, None)
                pre_name = None
                report.added["table:layer_recased"] += 1
            except Exception as ex:  # noqa: BLE001
                report.errors[f"layer_recase:{type(ex).__name__}:{str(ex)[:40]}"] += 1
        try:
            if pre_name is None:
                layer = doc.layers.add(name, **_layer_attribs(rec))
            else:
                layer = doc.layers.get(pre_name)
                for key, value in _layer_attribs(rec).items():
                    layer.dxf.set(key, value)
        except Exception as ex:  # noqa: BLE001 -- table churn must not abort a build
            report.errors[f"layer:{type(ex).__name__}:{str(ex)[:40]}"] += 1
            continue
        report.added["table:layer"] += 1
        linetype = str(rec.get("linetype") or "")
        if linetype and linetype in doc.linetypes:
            layer.dxf.linetype = linetype
        if rec.get("frozen"):
            layer.freeze()
        if rec.get("locked"):
            layer.lock()
        if rec.get("off"):
            layer.off()
    # Drop ezdxf's pre-created "Defpoints" when the original had no such layer
    # (case-insensitively -- see #54) so the rebuilt LAYER table matches the IR.
    if ir_folded and "defpoints" not in ir_folded and "defpoints" in pre_created:
        try:
            doc.layers.discard(pre_created["defpoints"])
            report.added["table:layer_pruned"] += 1
        except Exception:  # noqa: BLE001
            pass


def _build_linetypes(doc: Drawing, ir: dict, report: BuildReport) -> None:
    for rec in (ir.get("symbol_tables") or {}).get("linetypes") or []:
        if not isinstance(rec, dict):
            continue
        name = str(rec.get("name") or "").strip()
        if not name or name in doc.linetypes:
            continue
        dashes = [_num(d, 0.0) for d in rec.get("dash_lengths") or []]
        total = _num(rec.get("pattern_length"), sum(abs(d) for d in dashes))
        try:
            if dashes:
                doc.linetypes.add(name, pattern=[total] + dashes,
                                  description=str(rec.get("description") or ""))
            else:
                doc.linetypes.add(name, pattern=[0.0],
                                  description=str(rec.get("description") or ""))
            report.added["table:linetype"] += 1
        except Exception as ex:  # noqa: BLE001
            report.errors[f"linetype:{type(ex).__name__}:{str(ex)[:40]}"] += 1


def _text_style_attribs(rec: dict) -> dict:
    attrs: dict = {}
    font = str(rec.get("font_file") or "")
    if font:
        attrs["font"] = font
    big = str(rec.get("big_font_file") or "")
    if big:
        attrs["bigfont"] = big
    height = _num(rec.get("height"))
    if height is not None:
        attrs["height"] = height
    width = _num(rec.get("width_factor"))
    if width:
        attrs["width"] = width
    oblique = _num(rec.get("oblique_angle"))
    if oblique is not None:
        attrs["oblique"] = math.degrees(oblique) if abs(oblique) <= math.pi else oblique
    return attrs


def _build_text_styles(doc: Drawing, ir: dict, report: BuildReport) -> None:
    """Create the STYLE table from ``symbol_tables.text_styles``.

    #58: a SHAPE-file record is not a text style. It shares the STYLE table
    (flags bit0=1) but is keyed by its .shx file, and its ``name`` is unreliable
    -- records named ``STANDARD`` do occur. Sending one down the text-style path
    corrupted real data: ezdxf's case-INsensitive lookup made
    ``"STANDARD" in doc.styles`` true for the pre-created ``Standard``, so the
    "already exists, reuse it" branch overwrote that style's font with the shape
    file (``arial.ttf``/``malgun.ttf`` -> ``SYMBOL``, 24 occurrences over 7
    drawings). Shape records therefore take the ``add_shx``/``find_shx`` path
    ONLY, keyed by font name, and are never matched by record name.
    """
    for rec in (ir.get("symbol_tables") or {}).get("text_styles") or []:
        if not isinstance(rec, dict):
            continue
        font_file = str(rec.get("font_file") or "")
        if rec.get("is_shape_file"):
            if not font_file:
                report.skipped["text_style:shape_record_without_font"] += 1
                continue
            try:
                if doc.styles.find_shx(font_file) is None:
                    doc.styles.add_shx(font_file)
                    report.added["table:shape_file"] += 1
            except Exception as ex:  # noqa: BLE001
                report.errors[f"shape_file:{type(ex).__name__}:{str(ex)[:40]}"] += 1
            continue
        name = str(rec.get("name") or "").strip()
        if not name:
            report.skipped["text_style:unnamed_record"] += 1
            continue
        attrs = _text_style_attribs(rec)
        try:
            if name in doc.styles:
                style = doc.styles.get(name)
                for key, value in attrs.items():
                    style.dxf.set(key, value)
            else:
                doc.styles.add(name, font=attrs.pop("font", ""), dxfattribs=attrs)
            report.added["table:text_style"] += 1
        except Exception as ex:  # noqa: BLE001
            report.errors[f"text_style:{type(ex).__name__}:{str(ex)[:40]}"] += 1


def _build_dim_styles(doc: Drawing, ir: dict, report: BuildReport) -> str:
    """Create the DIMSTYLE table; return the name created dimensions reference."""
    records = [r for r in (ir.get("symbol_tables") or {}).get("dim_styles") or []
               if isinstance(r, dict)]
    ir_names = [str(r.get("name") or "").strip() for r in records]
    ir_names = [n for n in ir_names if n]
    for rec, name in zip(records, ir_names):
        try:
            style = doc.dimstyles.get(name) if name in doc.dimstyles \
                else doc.dimstyles.add(name)
            report.added["table:dim_style"] += 1
        except Exception as ex:  # noqa: BLE001
            report.errors[f"dim_style:{type(ex).__name__}:{str(ex)[:40]}"] += 1
            continue
        for key, value in (rec.get("dim_vars") or {}).items():
            attr = str(key).lower()
            try:
                if style.dxf.is_supported(attr):
                    style.dxf.set(attr, value)
            except Exception:  # noqa: BLE001 -- one bad var must not lose the style
                report.errors[f"dim_var:{attr}"] += 1
    dim_style_ref = ir_names[0] if ir_names else STANDARD
    # Drop ezdxf's pre-created "Standard" dimstyle when the original had none,
    # so the rebuilt DIMSTYLE table matches the IR one.
    #
    # #54: this comparison MUST be case-insensitive. AutoCAD symbol-table names
    # are case-insensitive, so an IR record named "STANDARD" merges into ezdxf's
    # pre-created "Standard"; a case-sensitive guard read that as "the original
    # has no Standard" and deleted the ONLY dimstyle 213 dimensions referenced,
    # which made AutoCAD reject the whole DXF ("invalid dimension style name",
    # rc53).
    if (ir_names and "standard" not in {n.casefold() for n in ir_names}
            and dim_style_ref != STANDARD):
        try:
            doc.dimstyles.discard(STANDARD)
            report.added["table:prune_dimstyle_std"] += 1
        except Exception:  # noqa: BLE001
            pass
    if dim_style_ref not in doc.dimstyles:
        dim_style_ref = STANDARD
    return dim_style_ref


# --- entity attributes --------------------------------------------------------

def _ensure_layer(ctx: _Ctx, name: str) -> str:
    """Guarantee the layer exists (an entity may name a layer the table lacks)."""
    if name and name not in ctx.doc.layers:
        try:
            ctx.doc.layers.add(name)
            ctx.report.added["table:layer_implicit"] += 1
        except Exception:  # noqa: BLE001
            return name
    return name


def _entity_attribs(ctx: _Ctx, ent: dict) -> dict:
    """Common DXF attributes (layer/color/linetype/lineweight) for one IR entity."""
    attr: dict = {}
    layer = str(ent.get("layer") or "")
    if layer:
        attr["layer"] = _ensure_layer(ctx, layer)
    color = ent.get("color_index")
    if isinstance(color, int) and 0 <= color <= 256:
        attr["color"] = color
    true_color = ent.get("true_color")
    if isinstance(true_color, dict):
        rgb = tuple(true_color.get(k) for k in ("r", "g", "b"))
        if all(isinstance(c, int) and 0 <= c <= 255 for c in rgb):
            attr["true_color"] = ezdxf.colors.rgb2int(rgb)  # type: ignore[arg-type]
    linetype = str(ent.get("linetype") or "")
    if linetype and linetype in ctx.doc.linetypes:
        attr["linetype"] = linetype
    lineweight = ent.get("lineweight")
    if isinstance(lineweight, int):
        attr["lineweight"] = lineweight
    return attr


# --- entity handlers ----------------------------------------------------------
# Every handler takes (ctx, space, ent, geom, attr) and returns the created
# entity, or None after counting a skip/error itself.

def _h_line(ctx, space, ent, g, attr):
    return space.add_line(_p3(g.get("start")), _p3(g.get("end")), dxfattribs=attr)


def _h_arc(ctx, space, ent, g, attr):
    return space.add_arc(_p3(g.get("center")), _num(g.get("radius"), 1.0),
                         _deg(g.get("start_angle")), _deg(g.get("end_angle")),
                         dxfattribs=attr)


def _h_circle(ctx, space, ent, g, attr):
    return space.add_circle(_p3(g.get("center")), _num(g.get("radius"), 1.0),
                            dxfattribs=attr)


def _h_ellipse(ctx, space, ent, g, attr):
    # The ELLIPSE entity's major_axis is the full center->major-endpoint vector
    # (AriadneNativeJob.cpp restores the major radius onto it); radius_ratio is
    # minor/major. This is NOT the hatch-edge convention -- see _edge_ellipse.
    major = _p3(g.get("major_axis"), (1.0, 0.0, 0.0))
    ratio = _num(g.get("radius_ratio"), 1.0) or 1.0
    ellipse = space.add_ellipse(_p3(g.get("center")), major,
                                min(max(abs(ratio), 1e-9), 1.0),
                                _num(g.get("start_angle"), 0.0),
                                _num(g.get("end_angle"), math.tau),
                                dxfattribs=attr)
    normal = g.get("normal")
    if normal is not None:
        ellipse.dxf.extrusion = _p3(normal, (0.0, 0.0, 1.0))
    return ellipse


def _h_lwpolyline(ctx, space, ent, g, attr):
    points = _vertex_points(g, with_bulge=True)
    if not points:
        ctx.report.skipped["lwpolyline:no_vertices"] += 1
        return None
    lw = space.add_lwpolyline(points, format="xyb", dxfattribs=attr)
    lw.closed = bool(g.get("closed"))
    const_width = _num(g.get("const_width"))
    if const_width:
        lw.dxf.const_width = const_width
    # #59: an LWPOLYLINE is a planar curve, so its Z lives in `elevation`
    # (DXF group 38), not on the vertices. Reading only x/y off the vertices
    # flattened whole drawings to z=0 (measured: 2,000,000.02 -> 0). The IR
    # leaves `elevation` empty and carries that Z on every vertex instead, so
    # recover it from there when the field is absent.
    elevation = _num(g.get("elevation"))
    if elevation is None:
        vertex_z = [p[2] for p in (_p3(v.get("point")) if isinstance(v, dict) else _p3(v)
                                   for v in g.get("vertices") or [])]
        elevation = vertex_z[0] if vertex_z else None
    if elevation:
        lw.dxf.elevation = elevation
    return lw


def _h_polyline(ctx, space, ent, g, attr):
    points = _vertex_points(g)
    if not points:
        ctx.report.skipped["polyline:no_vertices"] += 1
        return None
    flat = all(abs(p[2]) < 1e-12 for p in points)
    if flat:
        poly = space.add_polyline2d(points, dxfattribs=attr)
        elevation = _num(g.get("elevation"))
        if elevation:
            poly.dxf.elevation = (0.0, 0.0, elevation)
    else:
        poly = space.add_polyline3d(points, dxfattribs=attr)
    if g.get("closed"):
        poly.close(True)
    return poly


def _h_point(ctx, space, ent, g, attr):
    return space.add_point(_p3(g.get("position")), dxfattribs=attr)


def _h_text(ctx, space, ent, g, attr):
    dxfattribs = dict(attr)
    dxfattribs["insert"] = _p3(g.get("position"))
    height = _num(g.get("height"))
    if height:
        dxfattribs["height"] = height
    rotation = _num(g.get("rotation"))
    if rotation:
        dxfattribs["rotation"] = math.degrees(rotation)
    text = space.add_text(str(g.get("text") or ""), dxfattribs=dxfattribs)
    align = g.get("alignment_point")
    if align is not None:
        text.dxf.align_point = _p3(align)
    return text


def _h_mtext(ctx, space, ent, g, attr):
    dxfattribs = dict(attr)
    dxfattribs["insert"] = _p3(g.get("position"))
    height = _num(g.get("height"))
    if height:
        dxfattribs["char_height"] = height
    rotation = _num(g.get("rotation"))
    if rotation:
        dxfattribs["rotation"] = math.degrees(rotation)
    width = _num(g.get("width"))
    if width:
        dxfattribs["width"] = width
    attachment = g.get("attachment_point")
    if isinstance(attachment, (int, float)) and 1 <= int(attachment) <= 9:
        dxfattribs["attachment_point"] = int(attachment)
    return space.add_mtext(str(g.get("text") or ""), dxfattribs=dxfattribs)


def _h_attribute(ctx, space, ent, g, attr):
    # A standalone ATTRIB cannot exist outside an INSERT; only ATTDEF inside a
    # block definition is rebuildable here.
    if not hasattr(space, "add_attdef"):
        ctx.report.skipped["attribute:not_in_block_definition"] += 1
        return None
    dxfattribs = dict(attr)
    dxfattribs["insert"] = _p3(g.get("position"))
    height = _num(g.get("height"))
    if height:
        dxfattribs["height"] = height
    attdef = space.add_attdef(str(g.get("tag") or ""),
                              text=str(g.get("text") or ""), dxfattribs=dxfattribs)
    if g.get("prompt"):
        attdef.dxf.prompt = str(g.get("prompt"))
    return attdef


def _h_block_reference(ctx, space, ent, g, attr):
    name = str(g.get("block_name") or "")
    if not name:
        ctx.report.skipped["block_reference:no_block_name"] += 1
        return None
    if name not in ctx.doc.blocks:
        # An INSERT pointing at an undefined BLOCK is an invalid DXF; define an
        # empty one rather than emit a dangling reference.
        try:
            ctx.doc.blocks.new(name=name)
            ctx.report.added["table:block_implicit"] += 1
        except Exception as ex:  # noqa: BLE001
            ctx.report.errors[f"block_implicit:{type(ex).__name__}:{str(ex)[:40]}"] += 1
    scale = _p3(g.get("scale"), (1.0, 1.0, 1.0))
    dxfattribs = dict(attr)
    dxfattribs["xscale"], dxfattribs["yscale"], dxfattribs["zscale"] = (
        scale[0] or 1.0, scale[1] or 1.0, scale[2] or 1.0)
    rotation = _num(g.get("rotation"))
    if rotation:
        dxfattribs["rotation"] = math.degrees(rotation)
    insert = space.add_blockref(name, _p3(g.get("position")), dxfattribs=dxfattribs)
    for one in g.get("attributes") or []:
        if not isinstance(one, dict):
            continue
        sub = {"insert": _p3(one.get("position"))}
        height = _num(one.get("height"))
        if height:
            sub["height"] = height
        try:
            insert.add_attrib(str(one.get("tag") or ""), str(one.get("value") or ""),
                              dxfattribs=sub)
            ctx.report.added["attrib"] += 1
        except Exception as ex:  # noqa: BLE001
            ctx.report.errors[f"attrib:{type(ex).__name__}:{str(ex)[:40]}"] += 1
    return insert


def _h_spline(ctx, space, ent, g, attr):
    degree = int(_num(g.get("degree"), 3) or 3)
    control = [_p3(p) for p in ent.get("spline_control_points") or []]
    fit = [_p3(p) for p in g.get("fit_points") or []]
    if not control and not fit:
        ctx.report.skipped["spline:no_control_or_fit_points"] += 1
        return None
    spline = space.add_spline(dxfattribs=attr)
    spline.dxf.degree = degree
    if control:
        # #53: three knot representations reach this branch, and only the first
        # is DXF-standard. Accepting just that one and silently discarding the
        # rest left control-point-only SPLINEs with an EMPTY knot vector, which
        # makes AutoCAD reject the whole file (rc53) even though ezdxf's audit
        # passes it -- 3 bad splines out of 12,980 killed a 4 MB drawing.
        knots = [_num(k, 0.0) for k in ent.get("spline_knots") or []]
        clamped = len(control) + degree + 1
        if len(knots) == clamped:
            spline.control_points = control
            spline.knots = knots
        elif g.get("closed") and len(knots) == len(control) + 1:
            # ObjectARX reports a periodic (closed) spline as nknots = ncp+1.
            # set_closed is the API for exactly this: it wraps the first
            # `degree` control points and regenerates a uniform knot vector.
            spline.set_closed(control, degree)
            ctx.report.added["spline_periodic"] += 1
        else:
            spline.control_points = control
            spline.knots = open_uniform_knot_vector(len(control), degree + 1)
            ctx.report.added["spline_knots_synthesized"] += 1
    if fit:
        spline.fit_points = fit
    return spline


def _h_solid(ctx, space, ent, g, attr):
    return space.add_solid(_quad_points(g), dxfattribs=attr)


def _h_trace(ctx, space, ent, g, attr):
    return space.add_trace(_quad_points(g), dxfattribs=attr)


def _quad_points(g) -> list:
    return [_p3(g.get(key)) for key in ("p0", "p1", "p2", "p3")]


def _h_wipeout(ctx, space, ent, g, attr):
    points = _wipeout_wcs_vertices(g)
    if len(points) < 3:
        ctx.report.skipped["wipeout:no_clip_boundary"] += 1
        return None
    wipeout = space.add_wipeout(points, dxfattribs=attr)
    # #49: ezdxf's WIPEOUT factory applies every dxfattrib EXCEPT layer, which
    # it overwrites with '0' (reproduced against ezdxf 1.4.3: color survives,
    # layer does not). Assigning it afterwards survives save+reload, and this
    # one line moved the HDC 267 run from 36 to 182 passing drawings.
    layer = attr.get("layer")
    if layer:
        wipeout.dxf.layer = layer
    return wipeout


def _wipeout_wcs_vertices(g) -> list:
    """IR wipeout clip boundary -> WCS vertices.

    The IR carries the boundary the way ObjectARX reports it: 2D coordinates in
    the image's own plane, y-axis inverted, origin at the top-left corner. The
    mapping back to WCS is ezdxf's own ``ImageBase.boundary_path_wcs``:
    ``insert + u*0.5 - v*0.5 + u*x + v*(height - y)``.
    """
    boundary = [_p2(p) for p in g.get("clip_boundary") or []
                if isinstance(p, (list, tuple))]
    if len(boundary) == 2:  # rectangular form: two opposite corners
        (x0, y0), (x1, y1) = boundary
        boundary = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if len(boundary) < 3:
        return []
    u = Vec3(_p3(g.get("u_vector"), (1.0, 0.0, 0.0)))
    v = Vec3(_p3(g.get("v_vector"), (0.0, 1.0, 0.0)))
    origin = Vec3(_p3(g.get("origin"))) + u * 0.5 - v * 0.5
    size = g.get("image_size") or [1.0, 1.0]
    height = _num(size[1] if len(size) > 1 else 1.0, 1.0)
    return [tuple(origin + u * x + v * (height - y)) for x, y in boundary]


def _h_face3d(ctx, space, ent, g, attr):
    """#56: AcDbFace had no dispatch branch at all -- 136 3DFACEs in one drawing
    fell into ``skipped`` unnoticed. Edge visibility is a group-70 bitmask
    (``dxf.invisible_edges``), which ``set_edge_visibility`` maintains; the
    unrelated group-60 ``dxf.invisible`` flag is NOT where those bits live.
    """
    face = space.add_3dface(_quad_points(g), dxfattribs=attr)
    for index, visible in enumerate(g.get("edge_visibility") or []):
        if index < 4 and not visible:
            face.set_edge_visibility(index, False)
    return face


def _h_leader(ctx, space, ent, g, attr):
    """#59: a LEADER rebuilt as a POLYLINE is a lost LEADER (137 -> 0 in d014).

    ezdxf supports the entity natively, so identity is preserved; the polyline
    form remains only as a fallback. Note that MULTILEADER also arrives with
    ``kind == "leader"`` (the extractor's class map) and is therefore rebuilt as
    a plain LEADER -- a known, separately tracked downgrade.
    """
    points = _vertex_points(g)
    if len(points) < 2:
        ctx.report.skipped["leader:too_few_vertices"] += 1
        return None
    try:
        leader = space.add_leader(points, dimstyle=ctx.dim_style_ref,
                                 dxfattribs=dict(attr))
    except Exception as ex:  # noqa: BLE001
        ctx.report.errors[f"leader:{type(ex).__name__}:{str(ex)[:40]}"] += 1
        ctx.report.added["leader_polyline_fallback"] += 1
        return space.add_polyline3d(points, dxfattribs=attr)
    if isinstance(g.get("has_arrow_head"), bool):
        leader.dxf.has_arrowhead = 1 if g["has_arrow_head"] else 0
    leader.dxf.path_type = 1 if g.get("splined") else 0
    return leader


def _h_ray(ctx, space, ent, g, attr):
    return space.add_ray(_p3(g.get("base_point")),
                         _p3(g.get("unit_dir"), (1.0, 0.0, 0.0)), dxfattribs=attr)


def _h_xline(ctx, space, ent, g, attr):
    return space.add_xline(_p3(g.get("base_point")),
                           _p3(g.get("unit_dir"), (1.0, 0.0, 0.0)), dxfattribs=attr)


def _h_dimension(ctx, space, ent, g, attr):
    """Rebuild a linear/rotated/aligned DIMENSION (the only variant IR pins down).

    ``inline_block_dims`` selects the #51 trade: OFF (default) creates the
    DIMENSION and links the preserved ``*D`` definition, ON expands that
    definition's entities in place instead.
    """
    block_name = str(ent.get("dim_block_name") or "")
    if ctx.inline_block_dims and block_name in ctx.block_defs:
        count = 0
        for sub in ctx.block_defs[block_name].get("def_entities") or []:
            if _add_entity(ctx, space, sub) is not None:
                count += 1
        ctx.report.added["dim_inlined"] += 1
        if not count:
            ctx.report.skipped["dimension:inlined_empty_block"] += 1
        return None
    p1, p2 = g.get("xline1_point"), g.get("xline2_point")
    base = g.get("dim_line_point")
    if p1 is None or p2 is None or base is None:
        ctx.report.skipped["dimension:variant_not_rebuildable"] += 1
        return None
    override = space.add_linear_dim(
        base=_p3(base), p1=_p3(p1), p2=_p3(p2),
        angle=_deg(g.get("rotation")), dimstyle=ctx.dim_style_ref,
        dxfattribs=dict(attr))
    dim = override.dimension
    if block_name:
        # Point the DIMENSION at the preserved *D definition instead of
        # rendering a fresh anonymous block (#51: keep the original).
        dim.dxf.geometry = block_name
    measurement = _num(g.get("measurement"))
    if measurement is not None:
        dim.dxf.actual_measurement = measurement
    return dim


# --- hatch / mpolygon boundaries ----------------------------------------------

def _edge_ccw(edge: dict) -> bool:
    for key in ("counterclockwise", "ccw"):
        if isinstance(edge.get(key), bool):
            return edge[key]
    return True


def _edge_ellipse(ctx, path, edge) -> bool:
    """Add one elliptical boundary edge, in either IR dialect.

    #55: ezdxf's ``add_ellipse`` wants the center->major-endpoint VECTOR (its
    magnitude IS the major radius) plus ratio = minor/major. Neither dialect the
    extractor emits looks like that:

      * ``ellipse_arc`` carries a UNIT ``major_axis`` with ``major_radius`` /
        ``minor_radius`` alongside (measured: 288 of 288 edges had length 1.0),
        and no ``radius_ratio`` key at all. Passing that vector straight through
        collapsed a radius-5000 arc to radius 1, and the missing ratio defaulted
        to 1.0, turning every ellipse into a circle.
      * ``ellipse`` carries a full-length ``major`` and an explicit ``ratio``
        (the WCS-degree emit in AriadneNativeJob.cpp).

    Both are normalized here so the dialect cannot leak into the geometry.
    """
    center = _p2(edge.get("center"))
    full_major = edge.get("major")
    if full_major is not None:
        vector = _p2(full_major, (1.0, 0.0))
        major_radius = math.hypot(vector[0], vector[1])
    else:
        unit = _p2(edge.get("major_axis"), (1.0, 0.0))
        major_radius = abs(_num(edge.get("major_radius"), 1.0) or 1.0)
        vector = (unit[0] * major_radius, unit[1] * major_radius)
    if major_radius <= 0.0:
        ctx.report.skipped["hatch_edge:ellipse_zero_major_radius"] += 1
        return False
    ratio = _num(edge.get("ratio"))
    if ratio is None:
        ratio = _num(edge.get("radius_ratio"))
    if ratio is None:
        minor_radius = abs(_num(edge.get("minor_radius"), major_radius) or major_radius)
        ratio = minor_radius / major_radius
    # ezdxf (and DXF) reject a ratio outside (0, 1].
    path.add_ellipse(center, vector, min(max(abs(ratio), 1e-9), 1.0),
                     _deg(edge.get("start_angle")), _deg(edge.get("end_angle")),
                     _edge_ccw(edge))
    return True


def _apply_edge_path(ctx, hatch, loop) -> int:
    """Add one edge-type boundary loop; return the number of edges added."""
    path = hatch.paths.add_edge_path(int(_num(loop.get("loop_type"), 1) or 1))
    added = 0
    for edge in loop.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        kind = str(edge.get("type") or "")
        if kind == "line":
            path.add_line(_p2(edge.get("start")), _p2(edge.get("end")))
            added += 1
        elif kind in ("circ_arc", "arc"):
            path.add_arc(_p2(edge.get("center")), _num(edge.get("radius"), 1.0),
                         _deg(edge.get("start_angle")), _deg(edge.get("end_angle")),
                         _edge_ccw(edge))
            added += 1
        elif kind in ("ellipse_arc", "ell_arc", "ellipse"):
            # #55: the extractor emits "ellipse_arc"/"ellipse"; a dispatch that
            # only knew "ell_arc" dropped 288 edges and, with them, the 20
            # hatches whose loops consisted of nothing else.
            if _edge_ellipse(ctx, path, edge):
                added += 1
        elif kind == "spline":
            control = [_p2(p) for p in edge.get("control_points") or []]
            if control:
                path.add_spline(
                    control_points=control,
                    knot_values=[_num(k, 0.0) for k in edge.get("knots") or []] or None,
                    degree=int(_num(edge.get("degree"), 3) or 3),
                    periodic=1 if edge.get("periodic") else 0)
                added += 1
            else:
                ctx.report.skipped["hatch_edge:spline_without_control_points"] += 1
        else:
            # #55's real lesson: an unrecognized edge type must be counted, not
            # ignored. The 288 lost ellipse arcs were invisible until 20 hatches
            # turned up boundary-less.
            ctx.report.skipped[f"hatch_edge:{kind or 'unnamed'}"] += 1
    return added


def _apply_boundaries(ctx, hatch, g) -> int:
    """Add every IR loop to ``hatch``; return the number of loops that took."""
    loops = 0
    for loop in g.get("loops") or []:
        if not isinstance(loop, dict):
            continue
        vertices = loop.get("vertices")
        if isinstance(vertices, list) and vertices:
            points = []
            for v in vertices:
                pt = _p3(v) if not isinstance(v, dict) else _p3(v.get("point"))
                bulge = _num(v.get("bulge"), 0.0) if isinstance(v, dict) else 0.0
                points.append((pt[0], pt[1], bulge))
            hatch.paths.add_polyline_path(
                points, is_closed=bool(loop.get("closed", True)),
                flags=int(_num(loop.get("loop_type"), 1) or 1))
            loops += 1
            continue
        if _apply_edge_path(ctx, hatch, loop) > 0:
            loops += 1
        else:
            hatch.paths.paths.pop()  # an empty edge path is invalid in DXF
    return loops


def _apply_hatch_pattern(ctx, hatch, g) -> None:
    if g.get("is_solid_fill"):
        hatch.set_solid_fill(color=hatch.dxf.color)
        return
    name = str(g.get("pattern_name") or "SOLID")
    try:
        hatch.set_pattern_fill(name, scale=_num(g.get("pattern_scale"), 1.0) or 1.0,
                               angle=_deg(g.get("pattern_angle")))
    except Exception as ex:  # noqa: BLE001 -- unknown .pat name must not lose the hatch
        ctx.report.errors[f"hatch_pattern:{type(ex).__name__}:{str(ex)[:40]}"] += 1
    if g.get("is_gradient"):
        ctx.report.skipped["hatch_gradient:not_implemented"] += 1


def _h_hatch(ctx, space, ent, g, attr):
    hatch = space.add_hatch(dxfattribs=dict(attr))
    _apply_hatch_pattern(ctx, hatch, g)
    if _apply_boundaries(ctx, hatch, g) == 0:
        space.delete_entity(hatch)
        ctx.report.skipped["hatch:hatch_no_boundary"] += 1
        return None
    return hatch


def _h_mpolygon(ctx, space, ent, g, attr):
    mpolygon = space.add_mpolygon(dxfattribs=dict(attr))
    if _apply_boundaries(ctx, mpolygon, g) == 0:
        space.delete_entity(mpolygon)
        ctx.report.skipped["mpolygon:no_boundary"] += 1
        return None
    return mpolygon


_HANDLERS = {
    "line": _h_line,
    "arc": _h_arc,
    "circle": _h_circle,
    "ellipse": _h_ellipse,
    "lwpolyline": _h_lwpolyline,
    "polyline": _h_polyline,
    "point": _h_point,
    "text": _h_text,
    "mtext": _h_mtext,
    "attribute": _h_attribute,
    "block_reference": _h_block_reference,
    "spline": _h_spline,
    "hatch": _h_hatch,
    "mpolygon": _h_mpolygon,
    "solid": _h_solid,
    "trace": _h_trace,
    "face3d": _h_face3d,
    "wipeout": _h_wipeout,
    "leader": _h_leader,
    "ray": _h_ray,
    "xline": _h_xline,
    "dimension": _h_dimension,
}

# Geometry kinds this builder rebuilds. Derived from the handler table so the
# advertised set can never drift from the implemented one.
SUPPORTED_KINDS = frozenset(_HANDLERS)


# --- dispatch -----------------------------------------------------------------

def _add_entity(ctx: _Ctx, space, ent: dict):
    """Rebuild one IR entity into ``space``; count it either way."""
    geom = ent.get("geometry") or {}
    kind = str(geom.get("kind") or "unsupported")
    reason = _UNREBUILDABLE.get(kind)
    if reason is not None:
        ctx.report.skipped[f"{kind}:{reason}"] += 1
        return None
    handler = _HANDLERS.get(kind)
    if handler is None:
        ctx.report.skipped[f"{kind}:unrecognized_kind"] += 1
        return None
    try:
        created = handler(ctx, space, ent, geom, _entity_attribs(ctx, ent))
    except Exception as ex:  # noqa: BLE001 -- one bad entity must not kill the build
        ctx.report.errors[f"{kind}:{type(ex).__name__}:{str(ex)[:40]}"] += 1
        return None
    if created is not None:
        ctx.report.added[kind] += 1
    return created


def _target_space(ctx: _Ctx, ent: dict):
    space = str(ent.get("space") or "model")
    if space == "paper":
        paperspace = ctx.doc.paperspace()
        if paperspace is None:
            try:
                ctx.doc.layouts.new("Layout1")
                ctx.report.added["table:paperspace_layout"] += 1
                paperspace = ctx.doc.paperspace()
            except Exception:  # noqa: BLE001
                paperspace = None
        if paperspace is not None:
            return paperspace
    return ctx.doc.modelspace()


_LAYOUT_BLOCKS = ("*MODEL_SPACE", "*PAPER_SPACE")


def _build_block_definitions(ctx: _Ctx, ir: dict) -> None:
    """Create every BLOCK definition, including the ``*D`` dimension blocks."""
    for block in ir.get("block_definitions") or []:
        if not isinstance(block, dict):
            continue
        name = str(block.get("name") or "").strip()
        upper = name.upper()
        if not name or any(upper.startswith(p) for p in _LAYOUT_BLOCKS):
            continue
        if name in ctx.doc.blocks:
            ctx.report.skipped[f"block:{name[:24]}:already_defined"] += 1
            continue
        try:
            layout = ctx.doc.blocks.new(name=name,
                                        base_point=_p3(block.get("origin")))
        except Exception as ex:  # noqa: BLE001
            ctx.report.errors[f"block:{type(ex).__name__}:{str(ex)[:40]}"] += 1
            continue
        ctx.report.added["table:block_definition"] += 1
        for sub in block.get("def_entities") or []:
            if isinstance(sub, dict):
                _add_entity(ctx, layout, sub)


def build_dxf_from_ir(ir: dict, out_path=None, *, inline_block_dims: bool = False,
                      dxfversion: str = DEFAULT_DXFVERSION):
    """Rebuild a DXF drawing from ``ir``; return ``(Drawing, BuildReport)``.

    Args:
        ir: a ``ariadne.dwg_graph_ir.v1`` document (``tools/ir_builder.py``).
        out_path: when given, the rebuilt DXF is written there.
        inline_block_dims: see the module docstring (#51). Default OFF keeps the
            ``*D`` anonymous block definitions intact.
        dxfversion: ezdxf document version to create.
    """
    if not isinstance(ir, dict):
        raise TypeError("ir must be a dwg_graph_ir.v1 dict")
    report = BuildReport()
    doc = ezdxf.new(dxfversion)
    _build_linetypes(doc, ir, report)
    _build_layers(doc, ir, report)
    _build_text_styles(doc, ir, report)
    dim_style_ref = _build_dim_styles(doc, ir, report)
    ctx = _Ctx(doc=doc, report=report, dim_style_ref=dim_style_ref,
               inline_block_dims=inline_block_dims,
               block_defs={str(b.get("name") or ""): b
                           for b in ir.get("block_definitions") or []
                           if isinstance(b, dict)})
    _build_block_definitions(ctx, ir)
    for ent in ir.get("entities") or []:
        if not isinstance(ent, dict):
            continue
        if str(ent.get("space") or "model") == "block":
            # Block-owned entities arrive via block_definitions[].def_entities.
            report.skipped["entity:block_space_duplicate"] += 1
            continue
        _add_entity(ctx, _target_space(ctx, ent), ent)
    if out_path is not None:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(str(path))
    return doc, report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild a DXF from a dwg_graph_ir.v1 IR")
    parser.add_argument("ir_path", help="IR JSON path")
    parser.add_argument("out_path", help="DXF path to write")
    parser.add_argument("--inline-block-dims", action="store_true",
                        help="expand block-internal dimensions (#51 rc53 fallback)")
    parser.add_argument("--dxfversion", default=DEFAULT_DXFVERSION)
    args = parser.parse_args(argv)
    ir = json.loads(Path(args.ir_path).read_text(encoding="utf-8-sig"))
    _, report = build_dxf_from_ir(ir, args.out_path,
                                  inline_block_dims=args.inline_block_dims,
                                  dxfversion=args.dxfversion)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
