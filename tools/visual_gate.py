#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Sequence, Tuple

if __package__ in (None, ""):
    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)

import cadctl
import run_route
import visual_report

_SVG_NS = "{http://www.w3.org/2000/svg}"
_TRANSFORM_RE = re.compile(r"(translate|scale)\(([^)]*)\)")
_ARC_RE = re.compile(
    r"M\s+([-\d.eE]+)\s+([-\d.eE]+)\s+A\s+([-\d.eE]+)\s+([-\d.eE]+)\s+0\s+([01])\s+([01])\s+([-\d.eE]+)\s+([-\d.eE]+)"
)


def _identity_matrix() -> List[List[float]]:
    return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _matmul(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> List[List[float]]:
    return [
        [
            sum(float(a[r][k]) * float(b[k][c]) for k in range(3))
            for c in range(3)
        ]
        for r in range(3)
    ]


def _parse_transform(transform: Optional[str]) -> List[List[float]]:
    matrix = _identity_matrix()
    if not transform:
        return matrix
    for op, raw_args in _TRANSFORM_RE.findall(transform):
        parts = [float(part) for part in re.split(r"[,\s]+", raw_args.strip()) if part]
        if op == "translate":
            tx = parts[0] if parts else 0.0
            ty = parts[1] if len(parts) > 1 else 0.0
            op_matrix = [[1.0, 0.0, tx], [0.0, 1.0, ty], [0.0, 0.0, 1.0]]
        else:
            sx = parts[0] if parts else 1.0
            sy = parts[1] if len(parts) > 1 else sx
            op_matrix = [[sx, 0.0, 0.0], [0.0, sy, 0.0], [0.0, 0.0, 1.0]]
        matrix = _matmul(matrix, op_matrix)
    return matrix


def _apply_matrix(matrix: Sequence[Sequence[float]], x: float, y: float) -> Tuple[float, float]:
    return (
        float(matrix[0][0]) * x + float(matrix[0][1]) * y + float(matrix[0][2]),
        float(matrix[1][0]) * x + float(matrix[1][1]) * y + float(matrix[1][2]),
    )


def _parse_points(raw: str) -> List[Tuple[float, float]]:
    points: List[Tuple[float, float]] = []
    for item in raw.strip().split():
        x_str, y_str = item.split(",", 1)
        points.append((float(x_str), float(y_str)))
    return points


def _svg_arc_points(path_d: str, steps: int = 64) -> List[Tuple[float, float]]:
    match = _ARC_RE.fullmatch(path_d.strip())
    if not match:
        return []
    x1, y1, rx, ry, large, sweep, x2, y2 = match.groups()
    x1 = float(x1)
    y1 = float(y1)
    x2 = float(x2)
    y2 = float(y2)
    rx = abs(float(rx))
    ry = abs(float(ry))
    large_arc = int(large)
    sweep_flag = int(sweep)
    if rx == 0 or ry == 0:
        return [(x1, y1), (x2, y2)]

    dx2 = (x1 - x2) / 2.0
    dy2 = (y1 - y2) / 2.0
    x1p = dx2
    y1p = dy2
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        scale = math.sqrt(lam)
        rx *= scale
        ry *= scale

    sign = -1.0 if large_arc == sweep_flag else 1.0
    num = (rx * rx * ry * ry) - (rx * rx * y1p * y1p) - (ry * ry * x1p * x1p)
    den = (rx * rx * y1p * y1p) + (ry * ry * x1p * x1p)
    coef = 0.0 if den == 0 else sign * math.sqrt(max(0.0, num / den))
    cxp = coef * ((rx * y1p) / ry)
    cyp = coef * (-(ry * x1p) / rx)
    cx = cxp + (x1 + x2) / 2.0
    cy = cyp + (y1 + y2) / 2.0

    def _angle(ux: float, uy: float, vx: float, vy: float) -> float:
        dot = ux * vx + uy * vy
        det = ux * vy - uy * vx
        return math.atan2(det, dot)

    ux = (x1p - cxp) / rx
    uy = (y1p - cyp) / ry
    vx = (-x1p - cxp) / rx
    vy = (-y1p - cyp) / ry
    theta1 = _angle(1.0, 0.0, ux, uy)
    delta = _angle(ux, uy, vx, vy)
    if not sweep_flag and delta > 0:
        delta -= 2.0 * math.pi
    elif sweep_flag and delta < 0:
        delta += 2.0 * math.pi

    return [
        (
            cx + rx * math.cos(theta1 + delta * (i / steps)),
            cy + ry * math.sin(theta1 + delta * (i / steps)),
        )
        for i in range(steps + 1)
    ]


def _color_to_gray(element: ET.Element) -> int:
    stroke = element.get("stroke") or element.get("fill") or "#000000"
    if stroke.lower() in ("none", "transparent"):
        return 0
    if stroke.startswith("#") and len(stroke) == 7:
        r = int(stroke[1:3], 16)
        g = int(stroke[3:5], 16)
        b = int(stroke[5:7], 16)
        rgb = 0.299 * r + 0.587 * g + 0.114 * b
        return int(max(0, min(255, round(255 - rgb))))
    return 32


def _viewbox_to_pixels(viewbox: Tuple[float, float, float, float], raster_size: int) -> Tuple[int, int]:
    _, _, width, height = viewbox
    if width <= 0 or height <= 0:
        return raster_size, raster_size
    if width >= height:
        px_w = raster_size
        px_h = max(1, int(round(raster_size * (height / width))))
    else:
        px_h = raster_size
        px_w = max(1, int(round(raster_size * (width / height))))
    return px_w, px_h


def _format_svg_number(value: float) -> str:
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _parse_viewbox(raw: Optional[str]) -> Tuple[float, float, float, float]:
    parts = [float(part) for part in re.split(r"[\s,]+", (raw or "").strip()) if part]
    if len(parts) != 4:
        raise ValueError(f"SVG has invalid viewBox: {raw!r}")
    return parts[0], parts[1], parts[2], parts[3]


def _read_svg_viewbox(svg_path: str) -> Tuple[float, float, float, float]:
    return _parse_viewbox(ET.parse(svg_path).getroot().get("viewBox"))


def _union_viewboxes(
    viewboxes: Sequence[Tuple[float, float, float, float]]
) -> Tuple[float, float, float, float]:
    if not viewboxes:
        raise ValueError("at least one viewBox is required")
    min_x = min(vb[0] for vb in viewboxes)
    min_y = min(vb[1] for vb in viewboxes)
    max_x = max(vb[0] + max(vb[2], 0.0) for vb in viewboxes)
    max_y = max(vb[1] + max(vb[3], 0.0) for vb in viewboxes)
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0:
        width = 1.0
    if height <= 0:
        height = 1.0
    return min_x, min_y, width, height


def _flip_transform_for_viewbox(viewbox: Tuple[float, float, float, float]) -> str:
    _, vb_y, _, vb_h = viewbox
    return f"translate(0,{_format_svg_number(vb_y + vb_y + vb_h)}) scale(1,-1)"


def _rewrite_svg_viewbox(svg_path: str, viewbox: Tuple[float, float, float, float]) -> None:
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    tree = ET.parse(svg_path)
    root = tree.getroot()
    vb_x, vb_y, vb_w, vb_h = viewbox
    root.set(
        "viewBox",
        " ".join(_format_svg_number(part) for part in (vb_x, vb_y, vb_w, vb_h)),
    )
    root.set("width", "1000")
    root.set("height", _format_svg_number(1000.0 * (vb_h / vb_w) if vb_w > 0 else 1000.0))

    for child in list(root):
        if child.tag.split("}")[-1] == "rect" and child.get("fill") == "#ffffff":
            child.set("x", _format_svg_number(vb_x))
            child.set("y", _format_svg_number(vb_y))
            child.set("width", _format_svg_number(vb_w))
            child.set("height", _format_svg_number(vb_h))
            break

    for child in list(root):
        if child.tag.split("}")[-1] == "g":
            child.set("transform", _flip_transform_for_viewbox(viewbox))
            break

    tree.write(svg_path, encoding="utf-8", xml_declaration=True)


def _apply_common_viewbox(svg_paths: Sequence[str]) -> Tuple[float, float, float, float]:
    # visual_report does not expose an extents override, so the gate normalizes
    # the rendered SVG files in place before rasterization.
    common = _union_viewboxes([_read_svg_viewbox(path) for path in svg_paths])
    for path in svg_paths:
        _rewrite_svg_viewbox(path, common)
    return common


def _read_visual_diff_counts(artifact: Dict[str, Any]) -> Optional[Dict[str, int]]:
    diagnostics = artifact.get("diagnostics")
    if isinstance(diagnostics, dict):
        counts = diagnostics.get("diff_counts")
        if isinstance(counts, dict):
            return {
                "created": int(counts.get("created") or 0),
                "modified": int(counts.get("modified") or 0),
                "deleted": int(counts.get("deleted") or 0),
            }

    visual_diff_path = artifact.get("visual_diff")
    if isinstance(visual_diff_path, str) and os.path.isfile(visual_diff_path):
        try:
            with open(visual_diff_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except Exception:
            return None
        counts = payload.get("counts")
        if isinstance(counts, dict):
            return {
                "created": int(counts.get("created") or 0),
                "modified": int(counts.get("modified") or 0),
                "deleted": int(counts.get("deleted") or 0),
            }
    return None


def _sync_artifact_viewboxes(
    artifact: Dict[str, Any],
    common_viewbox: Tuple[float, float, float, float],
) -> None:
    common_box = [float(part) for part in common_viewbox]
    artifact["common_viewbox"] = common_box
    diagnostics = artifact.get("diagnostics")
    if isinstance(diagnostics, dict):
        diagnostics["common_viewbox"] = common_box
        for side in ("before", "after"):
            side_diag = diagnostics.get(side)
            if isinstance(side_diag, dict) and isinstance(side_diag.get("viewbox"), list):
                side_diag["original_viewbox"] = list(side_diag["viewbox"])
                side_diag["viewbox"] = list(common_box)

    visual_diff_path = artifact.get("visual_diff")
    if not isinstance(visual_diff_path, str) or not os.path.isfile(visual_diff_path):
        return
    try:
        with open(visual_diff_path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception:
        return
    payload["common_viewbox"] = common_box
    viewbox = payload.get("viewbox")
    if not isinstance(viewbox, dict):
        viewbox = {}
        payload["viewbox"] = viewbox
    for side in ("before", "after"):
        if isinstance(viewbox.get(side), list):
            viewbox[f"{side}_original"] = list(viewbox[side])
        viewbox[side] = list(common_box)
    _write_json(visual_diff_path, payload)


def _coerce_reason(reason: Optional[Any], fallback: str) -> str:
    text = str(reason).strip() if reason is not None else ""
    return text or fallback


def _compare_failure_reason(compare: Dict[str, Any], fallback_prefix: str) -> str:
    return _coerce_reason(
        compare.get("detail") or compare.get("error") or compare.get("compare_note"),
        f"{fallback_prefix}: status={compare.get('status')} compare_status={compare.get('compare_status')}",
    )


def _entity_set_mismatch_reason(counts: Optional[Dict[str, int]]) -> Optional[str]:
    if not isinstance(counts, dict):
        return None
    created = int(counts.get("created") or 0)
    deleted = int(counts.get("deleted") or 0)
    if deleted > 0:
        return f"entity_set_mismatch: deleted={deleted} created={created} (deferred-regen ceiling)"
    if created > 0:
        return f"entity_set_mismatch: deleted={deleted} created={created}"
    return None


def rasterize_svg_to_png(svg_path: str, png_path: str, *, raster_size: int = 1600) -> str:
    import cv2
    import numpy as np

    root = ET.parse(svg_path).getroot()
    vb = [float(part) for part in (root.get("viewBox") or "0 0 1 1").split()]
    if len(vb) != 4:
        raise ValueError(f"SVG has invalid viewBox: {root.get('viewBox')!r}")
    viewbox = (vb[0], vb[1], vb[2], vb[3])
    px_w, px_h = _viewbox_to_pixels(viewbox, raster_size)
    canvas = np.full((px_h, px_w), 255, dtype=np.uint8)

    def to_px(x: float, y: float) -> Tuple[int, int]:
        px = int(round(((x - viewbox[0]) / viewbox[2]) * (px_w - 1)))
        py = int(round(((y - viewbox[1]) / viewbox[3]) * (px_h - 1)))
        return px, py

    def stroke_px(element: ET.Element) -> int:
        sw = float(element.get("stroke-width") or 1.0)
        return max(1, int(round(sw * (px_w / viewbox[2]))))

    def walk(node: ET.Element, matrix: Sequence[Sequence[float]]) -> None:
        local = _matmul(matrix, _parse_transform(node.get("transform")))
        tag = node.tag.split("}")[-1]
        gray = _color_to_gray(node)
        thickness = stroke_px(node)

        if tag == "line":
            p0 = _apply_matrix(local, float(node.get("x1")), float(node.get("y1")))
            p1 = _apply_matrix(local, float(node.get("x2")), float(node.get("y2")))
            cv2.line(canvas, to_px(*p0), to_px(*p1), gray, thickness, lineType=cv2.LINE_AA)
        elif tag == "circle":
            center = _apply_matrix(local, float(node.get("cx")), float(node.get("cy")))
            radius = abs(float(node.get("r")))
            px_center = to_px(*center)
            px_radius = max(1, int(round(radius * (px_w / viewbox[2]))))
            cv2.circle(canvas, px_center, px_radius, gray, thickness, lineType=cv2.LINE_AA)
        elif tag == "rect":
            x = float(node.get("x"))
            y = float(node.get("y"))
            w = float(node.get("width"))
            h = float(node.get("height"))
            p0 = _apply_matrix(local, x, y)
            p1 = _apply_matrix(local, x + w, y + h)
            cv2.rectangle(canvas, to_px(*p0), to_px(*p1), gray, thickness, lineType=cv2.LINE_AA)
        elif tag in ("polyline", "polygon"):
            pts = [_apply_matrix(local, x, y) for x, y in _parse_points(node.get("points") or "")]
            if len(pts) >= 2:
                arr = np.array([to_px(*pt) for pt in pts], dtype=np.int32)
                cv2.polylines(canvas, [arr], tag == "polygon", gray, thickness, lineType=cv2.LINE_AA)
        elif tag == "path":
            pts = [_apply_matrix(local, x, y) for x, y in _svg_arc_points(node.get("d") or "")]
            if len(pts) >= 2:
                arr = np.array([to_px(*pt) for pt in pts], dtype=np.int32)
                cv2.polylines(canvas, [arr], False, gray, thickness, lineType=cv2.LINE_AA)
        elif tag == "text":
            x = float(node.get("x") or 0.0)
            y = float(node.get("y") or 0.0)
            world = _apply_matrix(local, x, y)
            px = to_px(*world)
            font_size = abs(float(node.get("font-size") or 12.0))
            font_scale = max(0.25, (font_size * (px_h / viewbox[3])) / 32.0)
            cv2.putText(
                canvas,
                node.text or "",
                px,
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                gray,
                max(1, thickness),
                lineType=cv2.LINE_AA,
            )

        for child in list(node):
            walk(child, local)

    walk(root, _identity_matrix())
    os.makedirs(os.path.dirname(os.path.abspath(png_path)), exist_ok=True)
    if not cv2.imwrite(png_path, canvas):
        raise ValueError(f"failed to write rasterized PNG: {png_path}")
    return png_path


def _write_json(path: str, obj: Dict[str, Any]) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return path


def _neutral_diff_doc() -> Dict[str, Any]:
    return {
        "schema": "ariadne.cad_diff.v1",
        "diff_id": "visual-gate-neutral",
        "changed_handles": [],
        "summary": {"created_count": 0, "modified_count": 0, "deleted_count": 0},
    }


def _ensure_ir_path(dwg_path: Optional[str], ir_path: Optional[str], out_dir: str, label: str) -> str:
    if ir_path:
        return ir_path
    if not dwg_path:
        raise ValueError(f"{label} requires either an IR path or a DWG path")
    inspect_dir = os.path.join(out_dir, f"{label}_inspect")
    env = cadctl.Cad().inspect(dwg_path, inspect_dir, mode="rich", include_rich=True)
    generated = env.get("dwg_graph_ir")
    if env.get("status") != "ok" or not generated or not os.path.isfile(generated):
        raise ValueError(f"{label} inspect failed: {env.get('status')} ({env.get('reason')})")
    return generated


def _render_visual_pair(pre_ir_path: str, post_ir_path: str, diff_path: Optional[str], out_dir: str) -> Dict[str, Any]:
    visual_dir = os.path.join(out_dir, "visual")
    os.makedirs(visual_dir, exist_ok=True)
    effective_diff = diff_path
    if not effective_diff:
        effective_diff = _write_json(os.path.join(out_dir, "neutral_diff.json"), _neutral_diff_doc())
    artifact = visual_report.build_visual_report(
        pre_ir_path,
        post_ir_path=post_ir_path,
        diff_path=effective_diff,
        artifact_id="visual-gate",
        out_dir=visual_dir,
        route="ir_svg",
    )
    if artifact.get("status") != "ok":
        raise ValueError(f"visual_report failed: {artifact.get('status')} ({artifact.get('notes')})")
    before_svg = os.path.join(visual_dir, "before.svg")
    after_svg = os.path.join(visual_dir, "after.svg")
    common_viewbox = _apply_common_viewbox((before_svg, after_svg))
    _sync_artifact_viewboxes(artifact, common_viewbox)
    visual_diff_counts = _read_visual_diff_counts(artifact)
    before_png = rasterize_svg_to_png(before_svg, os.path.join(visual_dir, "before.png"))
    after_png = rasterize_svg_to_png(after_svg, os.path.join(visual_dir, "after.png"))
    artifact_path = os.path.join(out_dir, "visual_artifact.json")
    _write_json(artifact_path, artifact)
    return {
        "artifact_path": artifact_path,
        "before_svg": before_svg,
        "after_svg": after_svg,
        "before_png": before_png,
        "after_png": after_png,
        "diff_path": effective_diff,
        "common_viewbox": common_viewbox,
        "visual_diff_counts": visual_diff_counts,
    }


def measure_same_file_baseline(ir_path: str, *, out_dir: str) -> Dict[str, Any]:
    try:
        refs = _render_visual_pair(ir_path, ir_path, None, out_dir)
    except Exception as exc:
        return {"status": "error", "reason": _coerce_reason(str(exc), "baseline_render_failed")}
    compare = run_route.compare_raster_images(refs["before_png"], refs["after_png"])
    if compare.get("status") != "ok" or compare.get("ssim") is None:
        status = compare.get("status", "error")
        if status == "ok":
            status = "blocked"
        return {
            "status": status,
            "reason": _compare_failure_reason(compare, "baseline_compare_failed"),
        }
    return {
        "status": "ok",
        "baseline_ssim": float(compare["ssim"]),
        "threshold": float(compare["ssim"]),
        "before_png": refs["before_png"],
        "after_png": refs["after_png"],
        "visual_artifact": refs["artifact_path"],
        "notes": ["Threshold is set from a same-file render baseline; SSIM proves pixel similarity only."],
    }


def visual_gate_from_ir_paths(
    pre_ir_path: str,
    post_ir_path: str,
    *,
    diff_path: Optional[str] = None,
    out_dir: Optional[str] = None,
    threshold: Optional[float] = None,
) -> Dict[str, Any]:
    run_dir = out_dir or tempfile.mkdtemp(prefix="visual_gate_")
    os.makedirs(run_dir, exist_ok=True)
    baseline = measure_same_file_baseline(pre_ir_path, out_dir=os.path.join(run_dir, "baseline"))
    if baseline.get("status") != "ok":
        return {
            "status": "blocked",
            "pass": False,
            "reason": _coerce_reason(baseline.get("reason"), "baseline_failed"),
            "baseline": baseline,
        }
    try:
        refs = _render_visual_pair(pre_ir_path, post_ir_path, diff_path, os.path.join(run_dir, "gate"))
    except Exception as exc:
        return {
            "status": "blocked",
            "pass": False,
            "reason": _coerce_reason(str(exc), "visual_render_failed"),
            "baseline": baseline,
        }
    compare = run_route.compare_raster_images(refs["before_png"], refs["after_png"])
    entity_set_reason = _entity_set_mismatch_reason(refs.get("visual_diff_counts"))
    entity_set_blocked = bool((refs.get("visual_diff_counts") or {}).get("deleted"))
    if compare.get("status") != "ok" or compare.get("ssim") is None:
        return {
            "status": "blocked",
            "pass": False,
            "reason": entity_set_reason or _compare_failure_reason(compare, "raster_compare_failed"),
            "baseline": baseline,
        }
    effective_threshold = float(baseline["threshold"] if threshold is None else threshold)
    score = float(compare["ssim"])
    passed = score >= effective_threshold
    if entity_set_blocked:
        passed = False
    status = "ok" if passed else ("blocked" if entity_set_blocked else "mismatch")
    result = {
        "status": status,
        "pass": passed,
        "ssim": score,
        "threshold": effective_threshold,
        "baseline": baseline,
        "before_png": refs["before_png"],
        "after_png": refs["after_png"],
        "before_svg": refs["before_svg"],
        "after_svg": refs["after_svg"],
        "visual_artifact": refs["artifact_path"],
        "diff_path": refs["diff_path"],
        "common_viewbox": [float(part) for part in refs["common_viewbox"]],
        "visual_diff_counts": refs.get("visual_diff_counts"),
        "notes": [
            "SSIM measures rasterized pixel similarity of the rendered views.",
            "A passing SSIM gate does not prove semantic CAD equivalence on its own.",
        ],
    }
    if not passed:
        result["reason"] = entity_set_reason or f"ssim_below_threshold: ssim={score:.6f} threshold={effective_threshold:.6f}"
    _write_json(os.path.join(run_dir, "visual_gate_verdict.json"), result)
    return result


def visual_gate_from_ir_docs(
    pre_ir: Dict[str, Any],
    post_ir: Dict[str, Any],
    *,
    diff_doc: Optional[Dict[str, Any]] = None,
    out_dir: Optional[str] = None,
    threshold: Optional[float] = None,
) -> Dict[str, Any]:
    run_dir = out_dir or tempfile.mkdtemp(prefix="visual_gate_docs_")
    pre_path = _write_json(os.path.join(run_dir, "pre_ir.json"), pre_ir)
    post_path = _write_json(os.path.join(run_dir, "post_ir.json"), post_ir)
    diff_path = None
    if diff_doc is not None:
        diff_path = _write_json(os.path.join(run_dir, "diff.json"), diff_doc)
    return visual_gate_from_ir_paths(
        pre_path,
        post_path,
        diff_path=diff_path,
        out_dir=run_dir,
        threshold=threshold,
    )


def visual_gate(
    *,
    pre_dwg_path: Optional[str] = None,
    post_dwg_path: Optional[str] = None,
    pre_ir_path: Optional[str] = None,
    post_ir_path: Optional[str] = None,
    diff_path: Optional[str] = None,
    out_dir: Optional[str] = None,
    threshold: Optional[float] = None,
) -> Dict[str, Any]:
    run_dir = out_dir or tempfile.mkdtemp(prefix="visual_gate_")
    try:
        pre_ir = _ensure_ir_path(pre_dwg_path, pre_ir_path, run_dir, "pre")
        post_ir = _ensure_ir_path(post_dwg_path, post_ir_path, run_dir, "post")
    except Exception as exc:
        return {"status": "blocked", "pass": False, "reason": _coerce_reason(str(exc), "ir_resolution_failed")}
    return visual_gate_from_ir_paths(
        pre_ir,
        post_ir,
        diff_path=diff_path,
        out_dir=run_dir,
        threshold=threshold,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Visual SSIM gate over CADOS visual_report SVG output.")
    ap.add_argument("--pre-dwg", default=None)
    ap.add_argument("--post-dwg", default=None)
    ap.add_argument("--pre-ir", dest="pre_ir_path", default=None)
    ap.add_argument("--post-ir", dest="post_ir_path", default=None)
    ap.add_argument("--diff", dest="diff_path", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--threshold", type=float, default=None)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = visual_gate(
        pre_dwg_path=args.pre_dwg,
        post_dwg_path=args.post_dwg,
        pre_ir_path=args.pre_ir_path,
        post_ir_path=args.post_ir_path,
        diff_path=args.diff_path,
        out_dir=args.out_dir,
        threshold=args.threshold,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
