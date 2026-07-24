#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""unit_anchor.py -- dimension-anchored unit inference for E2 wall detection.

WHY:
  * A SEG-IR document needs a truthful `scale_mm_per_unit` so downstream
    geometry (wall thickness, junction radii) can be reasoned about in real
    millimetres. DWG/DXF drawings carry an INSUNITS header, but it is often
    wrong, unitless (0), or contradicted by the actual geometry.
  * This module infers the scale by ANCHORING geometry against human-authored
    numbers already in the drawing, using three independent signals:
      A. DIMENSION entities -- geometric measurement (drawing units) vs a
         numeric text override (the value a human intends, read as mm).
      B. numeric MTEXT/TEXT tokens vs the length of a nearby LINE, where
         "nearby" means within a search radius proportional to text height.
      C. the INSUNITS header, as a weak tie-breaker / confirmation.
  * Signals A and B are geometric and self-consistent; INSUNITS only nudges
    confidence. A drawing whose numeric texts match line spans at ratio ~1.0
    is reported as native-mm.

CONTRACT (S4 wiring -- modules do NOT import each other; cli.py injects):
    infer_from_dxf(dxf_path) ->
        {"scale_mm_per_unit": float|None, "confidence": 0..1, "evidence": [str]}

ezdxf is ALLOWED for this card. This module is a pure read: it opens the DXF,
reads modelspace entities, and never mutates the drawing.
"""
from __future__ import annotations

import argparse
import math
import os
import re
import sys
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple

import ezdxf

Point = Tuple[float, float]
Segment = Tuple[Point, Point]

# --- INSUNITS -> (name, millimetres-per-drawing-unit) --------------------------
# DXF $INSUNITS enumeration. None means "unitless" (no scale information).
_INSUNITS: Dict[int, Tuple[str, Optional[float]]] = {
    0: ("Unitless", None),
    1: ("Inches", 25.4),
    2: ("Feet", 304.8),
    3: ("Miles", 1609344.0),
    4: ("Millimeters", 1.0),
    5: ("Centimeters", 10.0),
    6: ("Meters", 1000.0),
    7: ("Kilometers", 1_000_000.0),
    8: ("Microinches", 2.54e-5),
    9: ("Mils", 0.0254),
    10: ("Yards", 914.4),
    11: ("Angstroms", 1e-7),
    12: ("Nanometers", 1e-6),
    13: ("Microns", 1e-3),
    14: ("Decimeters", 100.0),
    15: ("Decameters", 10_000.0),
    16: ("Hectometers", 100_000.0),
    17: ("Gigameters", 1e12),
}

# Unit-suffix on an annotation string -> millimetres-per-unit-of-that-suffix.
# Anything without a recognised suffix is assumed already in millimetres.
_TEXT_UNIT_MM: Dict[str, float] = {
    "mm": 1.0, "millimeter": 1.0, "millimeters": 1.0, "millimetre": 1.0, "millimetres": 1.0,
    "cm": 10.0, "centimeter": 10.0, "centimeters": 10.0,
    "m": 1000.0, "meter": 1000.0, "meters": 1000.0, "metre": 1000.0, "metres": 1000.0,
    "in": 25.4, "inch": 25.4, "inches": 25.4, '"': 25.4,
    "ft": 304.8, "feet": 304.8, "foot": 304.8, "'": 304.8,
}

# Matching / clustering tuning. Radius is a multiple of the text's cap height.
_RADIUS_FACTOR = 15.0
_CLUSTER_TOL = 0.10       # relative tolerance for "candidates agree"
_INSUNITS_TOL = 0.10      # relative tolerance for "INSUNITS confirms geometry"
_NATIVE_MM_TOL = 0.02     # |scale - 1.0| below this => call it native-mm
_HIGH_CONF = 0.75         # evidence label threshold
_EPS = 1e-9


# --- small numeric helpers -----------------------------------------------------
def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def _seg_length(seg: Segment) -> float:
    (ax, ay), (bx, by) = seg
    return math.hypot(bx - ax, by - ay)


def _point_seg_distance(p: Point, seg: Segment) -> float:
    """Shortest distance from point p to the finite segment seg."""
    (px, py) = p
    (ax, ay), (bx, by) = seg
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom <= _EPS:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / denom
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


_NUMBER_RE = re.compile(
    r"^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*"
    r"([a-zA-Z]+|['\"])?\s*$"
)


def _parse_measure_mm(text: str) -> Optional[float]:
    """Parse a standalone number (optionally with a unit suffix) into mm.

    Returns None when the string is not a bare measurement (e.g. 'Room 3',
    'A-12', 'DN'), so annotations that merely contain a digit do not pollute
    the scale estimate.
    """
    if not text:
        return None
    m = _NUMBER_RE.match(text.strip())
    if not m:
        return None
    try:
        value = float(m.group(1))
    except ValueError:
        return None
    if value <= 0:
        return None
    suffix = (m.group(2) or "").lower()
    if suffix:
        if suffix not in _TEXT_UNIT_MM:
            return None  # a letter suffix we don't understand -> not a measure
        return value * _TEXT_UNIT_MM[suffix]
    return value  # bare number: assume already millimetres


# --- entity readers ------------------------------------------------------------
def _collect_line_segments(msp) -> List[Segment]:
    segs: List[Segment] = []
    for e in msp.query("LINE"):
        try:
            s, t = e.dxf.start, e.dxf.end
            segs.append(((float(s.x), float(s.y)), (float(t.x), float(t.y))))
        except Exception:
            continue
    return segs


def _collect_numeric_texts(msp) -> List[Dict[str, Any]]:
    """Return numeric annotations as {value_mm, pos, height, raw}."""
    out: List[Dict[str, Any]] = []
    for e in msp.query("MTEXT TEXT"):
        try:
            if e.dxftype() == "MTEXT":
                raw = e.plain_text()
                pos = e.dxf.insert
                height = float(getattr(e.dxf, "char_height", 0.0) or 0.0)
            else:  # TEXT
                raw = e.dxf.text
                pos = e.dxf.insert
                height = float(getattr(e.dxf, "height", 0.0) or 0.0)
        except Exception:
            continue
        value_mm = _parse_measure_mm(raw or "")
        if value_mm is None:
            continue
        out.append({
            "value_mm": value_mm,
            "pos": (float(pos.x), float(pos.y)),
            "height": height,
            "raw": (raw or "").strip(),
        })
    return out


def _dimension_candidates(msp) -> List[Dict[str, Any]]:
    """Signal A: DIMENSION measurement (units) vs numeric text override (mm)."""
    cands: List[Dict[str, Any]] = []
    for e in msp.query("DIMENSION"):
        try:
            override = (getattr(e.dxf, "text", "") or "").strip()
        except Exception:
            override = ""
        # "<>" or "" both mean "show the measurement" -- no explicit value.
        if not override or override in ("<>",):
            continue
        value_mm = _parse_measure_mm(override)
        if value_mm is None:
            continue
        try:
            measurement = e.get_measurement()
        except Exception:
            continue
        if not isinstance(measurement, (int, float)):
            continue
        measurement = float(measurement)
        if measurement <= _EPS:
            continue
        scale = value_mm / measurement
        cands.append({
            "scale": scale,
            "source": "dimension",
            "evidence": (
                f"DIMENSION override '{override}' (= {value_mm:g} mm) "
                f"vs measured {measurement:.3f} units -> {scale:.4f} mm/unit"
            ),
        })
    return cands


def _text_span_candidates(
    texts: List[Dict[str, Any]],
    segs: List[Segment],
    radius_factor: float = _RADIUS_FACTOR,
) -> List[Dict[str, Any]]:
    """Signal B: numeric text vs the nearest LINE within a height-scaled radius."""
    cands: List[Dict[str, Any]] = []
    for idx, txt in enumerate(texts):
        height = txt["height"]
        if height <= _EPS:
            # No usable height -> we cannot bound "nearby"; skip rather than guess.
            continue
        radius = radius_factor * height
        best: Optional[Tuple[float, int, float]] = None  # (gap, seg_index, span)
        for j, seg in enumerate(segs):
            span = _seg_length(seg)
            if span <= _EPS:
                continue
            gap = _point_seg_distance(txt["pos"], seg)
            if gap > radius:
                continue
            if best is None or gap < best[0]:
                best = (gap, j, span)
        if best is None:
            continue
        gap, seg_index, span = best
        scale = txt["value_mm"] / span
        cands.append({
            "scale": scale,
            "source": "text-span",
            "evidence": (
                f"text '{txt['raw']}' (= {txt['value_mm']:g} mm) matches LINE #"
                f"{seg_index} span {span:.3f} units (gap {gap:.1f} <= r {radius:.1f}) "
                f"-> {scale:.4f} mm/unit"
            ),
        })
    return cands


def _read_insunits(doc) -> Tuple[int, str, Optional[float]]:
    try:
        raw = int(doc.header.get("$INSUNITS", 0) or 0)
    except Exception:
        raw = 0
    name, mm = _INSUNITS.get(raw, ("Unknown", None))
    return raw, name, mm


# --- combination ---------------------------------------------------------------
def _combine(
    geo_cands: List[Dict[str, Any]],
    insunits: Tuple[int, str, Optional[float]],
) -> Dict[str, Any]:
    ins_raw, ins_name, ins_mm = insunits
    evidence: List[str] = []
    for c in geo_cands:
        evidence.append(c["evidence"])

    if not geo_cands:
        # No geometric anchor: fall back to INSUNITS alone (weak).
        if ins_mm is not None:
            evidence.append(
                f"INSUNITS={ins_raw} ({ins_name}) -> {ins_mm:g} mm/unit "
                f"(header only, no geometric anchor)"
            )
            scale = ins_mm
            conf = 0.45
            if abs(scale - 1.0) <= _NATIVE_MM_TOL:
                evidence.append("native-mm (INSUNITS says millimetres)")
            return {"scale_mm_per_unit": scale, "confidence": round(conf, 3),
                    "evidence": evidence}
        evidence.append(
            f"INSUNITS={ins_raw} ({ins_name}) carries no scale; "
            f"no numeric anchors found -> scale unknown"
        )
        return {"scale_mm_per_unit": None, "confidence": 0.05, "evidence": evidence}

    values = [c["scale"] for c in geo_cands]
    med = _median(values)
    inliers = [v for v in values if abs(v - med) / med <= _CLUSTER_TOL] if med > _EPS else values
    agreement = len(inliers) / len(values)
    scale = _median(inliers) if inliers else med

    ins_consistent = (
        ins_mm is not None and scale > _EPS
        and abs(ins_mm - scale) / scale <= _INSUNITS_TOL
    )
    if ins_mm is not None:
        evidence.append(
            f"INSUNITS={ins_raw} ({ins_name}) -> {ins_mm:g} mm/unit "
            f"({'consistent' if ins_consistent else 'INCONSISTENT'} with geometry)"
        )

    conf = 0.55 + 0.35 * agreement + 0.03 * min(len(inliers) - 1, 3)
    if ins_consistent:
        conf += 0.10
    conf = min(conf, 0.97)

    label = "high" if conf >= _HIGH_CONF else "low"
    evidence.append(
        f"scale={scale:.4f} mm/unit from {len(inliers)}/{len(values)} agreeing "
        f"geometric candidate(s), agreement={agreement:.0%}, confidence={conf:.2f} ({label})"
    )
    if abs(scale - 1.0) <= _NATIVE_MM_TOL:
        evidence.append("native-mm (numeric texts match spans at ratio ~1.0)")

    return {"scale_mm_per_unit": scale, "confidence": round(conf, 3), "evidence": evidence}


# --- public entrypoint ---------------------------------------------------------
def infer_from_dxf(dxf_path: str) -> Dict[str, Any]:
    """Infer millimetres-per-drawing-unit for a DXF file.

    Returns {"scale_mm_per_unit": float|None, "confidence": 0..1,
             "evidence": [str]}.
    """
    try:
        doc = ezdxf.readfile(dxf_path)
    except Exception as exc:  # unreadable / not a DXF
        return {
            "scale_mm_per_unit": None,
            "confidence": 0.0,
            "evidence": [f"could not read DXF '{dxf_path}': {exc}"],
        }

    msp = doc.modelspace()
    segs = _collect_line_segments(msp)
    texts = _collect_numeric_texts(msp)

    geo_cands: List[Dict[str, Any]] = []
    geo_cands.extend(_dimension_candidates(msp))
    geo_cands.extend(_text_span_candidates(texts, segs))

    insunits = _read_insunits(doc)
    result = _combine(geo_cands, insunits)
    result["evidence"].insert(
        0,
        f"scanned modelspace: {len(segs)} LINE(s), {len(texts)} numeric "
        f"annotation(s), {len(geo_cands)} geometric anchor(s)",
    )
    return result


# --- selftest ------------------------------------------------------------------
def _build_selftest_dxf(path: str) -> None:
    """Build a small native-mm DXF: a 3280-unit line annotated '3280', plus
    LWPOLYLINE + ARC + a nested INSERT (S4 fixture requirement) and a
    consistent aligned DIMENSION. Extra geometry is placed far from the
    annotation so only the intended line falls inside the search radius.
    """
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4  # millimetres
    msp = doc.modelspace()

    # Primary anchor: a 3280-unit horizontal line + MTEXT "3280" just above it.
    msp.add_line((0, 0), (3280, 0))
    mt = msp.add_mtext("3280")
    mt.dxf.insert = (1640, 60)
    mt.dxf.char_height = 80  # radius = 15 * 80 = 1200 >> 60 gap

    # Extra shapes, far away (gap >> radius) so they never match.
    msp.add_lwpolyline([(0, 20000), (500, 20000), (500, 20500), (0, 20500)], close=True)
    msp.add_arc(center=(2000, 20000), radius=300, start_angle=0, end_angle=90)
    msp.add_line((0, 25000), (1000, 25000))  # unannotated -> no candidate

    # Nested INSERT tree (PARENT -> CHILD), also far away.
    child = doc.blocks.new("CHILD")
    child.add_line((0, 0), (100, 0))
    parent = doc.blocks.new("PARENT")
    parent.add_blockref("CHILD", (0, 0))
    msp.add_blockref(
        "PARENT", (0, 30000),
        dxfattribs={"xscale": 2.0, "yscale": 2.0, "rotation": 45.0},
    )

    # Aligned DIMENSION with a numeric override consistent with 1.0 mm/unit.
    try:
        dim = msp.add_aligned_dim(p1=(0, 40000), p2=(1000, 40000), distance=300)
        dim.dimension.dxf.text = "1000"  # 1000 mm over a 1000-unit span -> 1.0
        dim.render()
    except Exception:
        pass  # dimension is a bonus signal; never fail the fixture on it

    doc.saveas(path)


def _selftest() -> int:
    tmpdir = tempfile.mkdtemp(prefix="unit_anchor_selftest_")
    dxf_path = os.path.join(tmpdir, "native_mm.dxf")
    lines: List[str] = []

    def emit(s: str = "") -> None:
        lines.append(s)
        print(s)

    emit(f"[selftest] temp dir: {tmpdir}")
    _build_selftest_dxf(dxf_path)
    emit(f"[selftest] built fixture: {dxf_path} "
         f"({os.path.getsize(dxf_path)} bytes)")

    result = infer_from_dxf(dxf_path)
    emit("")
    emit("=== infer_from_dxf result ===")
    emit(f"scale_mm_per_unit: {result['scale_mm_per_unit']}")
    emit(f"confidence:        {result['confidence']}")
    emit("evidence:")
    for line in result["evidence"]:
        emit(f"  - {line}")
    emit("")

    # --- assertions -----------------------------------------------------------
    checks: List[Tuple[str, bool]] = []
    scale = result["scale_mm_per_unit"]
    conf = result["confidence"]
    checks.append(("scale is a float", isinstance(scale, float)))
    checks.append((
        "scale ~= 1.0 (native-mm)",
        isinstance(scale, float) and abs(scale - 1.0) <= _NATIVE_MM_TOL,
    ))
    checks.append(("confidence is high (>= 0.75)", conf >= _HIGH_CONF))
    checks.append((
        "evidence mentions native-mm",
        any("native-mm" in e for e in result["evidence"]),
    ))
    checks.append((
        "text-span anchor fired",
        any("matches LINE" in e for e in result["evidence"]),
    ))

    # Negative control: an unreadable path must fail safely, not crash.
    bad = infer_from_dxf(os.path.join(tmpdir, "does_not_exist.dxf"))
    checks.append((
        "missing file -> scale None, confidence 0.0",
        bad["scale_mm_per_unit"] is None and bad["confidence"] == 0.0,
    ))

    # Negative control: a unitless drawing with no anchors -> unknown scale.
    blank_path = os.path.join(tmpdir, "blank_unitless.dxf")
    bdoc = ezdxf.new("R2010")
    bdoc.header["$INSUNITS"] = 0
    bdoc.modelspace().add_line((0, 0), (10, 0))
    bdoc.saveas(blank_path)
    blank = infer_from_dxf(blank_path)
    checks.append((
        "unitless + no anchor -> scale None, low confidence",
        blank["scale_mm_per_unit"] is None and blank["confidence"] < 0.2,
    ))

    emit("=== assertions ===")
    all_ok = True
    for name, ok in checks:
        emit(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        all_ok = all_ok and ok

    emit("")
    emit(f"SELFTEST {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="dimension-anchored unit inference")
    parser.add_argument("dxf", nargs="?", help="DXF file to infer units for")
    parser.add_argument("--selftest", action="store_true",
                        help="build a temp fixture and self-verify")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.dxf:
        parser.error("provide a DXF path or --selftest")
    result = infer_from_dxf(args.dxf)
    import json
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
