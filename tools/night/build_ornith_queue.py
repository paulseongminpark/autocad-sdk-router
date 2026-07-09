#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build an Ornith overnight annotation queue from a DWG graph IR."""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


def load_ir(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8-sig") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("IR root must be a JSON object")
    return data


def _slug(value: Any) -> str:
    text = str(value or "unnamed").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "unnamed"


def _def_name(block_def: dict[str, Any]) -> str:
    return str(block_def.get("name") or block_def.get("block_name") or block_def.get("handle") or "unnamed")


def _entity_count(block_def: dict[str, Any]) -> int:
    raw = block_def.get("entity_count")
    if isinstance(raw, int):
        return raw
    try:
        return int(raw)
    except Exception:
        return len(_def_entities(block_def))


def _def_entities(block_def: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("def_entities", "entities", "block_entities"):
        value = block_def.get(key)
        if isinstance(value, list):
            return [e for e in value if isinstance(e, dict)]
    return []


def _dxf_name(ent: dict[str, Any]) -> str:
    raw = ent.get("dxf_name") or ent.get("type") or ent.get("class") or ent.get("kind")
    if not raw and isinstance(ent.get("geometry"), dict):
        raw = ent["geometry"].get("kind")
    text = str(raw or "UNKNOWN").strip()
    if text.startswith("AcDb"):
        text = text[4:]
    return text.upper()


def _layer(ent: dict[str, Any]) -> str:
    return str(ent.get("layer") or "(none)")


def _fmt_num(value: Any) -> str:
    try:
        num = float(value)
    except Exception:
        return "?"
    if not math.isfinite(num):
        return "?"
    if abs(num - round(num)) < 1e-9:
        return str(int(round(num)))
    return f"{num:.3f}".rstrip("0").rstrip(".")


def _point(value: Any) -> tuple[float, float, float] | None:
    if isinstance(value, dict):
        try:
            return (
                float(value.get("x", 0.0)),
                float(value.get("y", 0.0)),
                float(value.get("z", 0.0)),
            )
        except Exception:
            return None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            z = value[2] if len(value) >= 3 else 0.0
            return (float(value[0]), float(value[1]), float(z))
        except Exception:
            return None
    return None


def _line_points(ent: dict[str, Any]) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    geom = ent.get("geometry") if isinstance(ent.get("geometry"), dict) else {}
    start = _point(ent.get("start")) or _point(geom.get("start"))
    end = _point(ent.get("end")) or _point(geom.get("end"))
    if start is None or end is None:
        return None
    return start, end


def line_bbox(entities: Iterable[dict[str, Any]]) -> list[float] | None:
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for ent in entities:
        if _dxf_name(ent) != "LINE":
            continue
        pts = _line_points(ent)
        if pts is None:
            continue
        for x, y, z in pts:
            xs.append(x)
            ys.append(y)
            zs.append(z)
    if not xs:
        return None
    return [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]


def _hist_text(counter: Counter[str]) -> str:
    if not counter:
        return "(empty)"
    return ", ".join(f"{key}={counter[key]}" for key in sorted(counter))


def _text_value(ent: dict[str, Any]) -> str:
    geom = ent.get("geometry") if isinstance(ent.get("geometry"), dict) else {}
    for key in ("text", "plain_text", "contents", "value", "string"):
        val = ent.get(key)
        if val is None:
            val = geom.get(key)
        if val is not None:
            text = str(val).replace("\n", " ").strip()
            return text[:80]
    return ""


def _entity_line(ent: dict[str, Any]) -> str:
    dxf = _dxf_name(ent)
    layer = _layer(ent)
    handle = str(ent.get("handle") or "?")
    geom = ent.get("geometry") if isinstance(ent.get("geometry"), dict) else {}
    if dxf == "LINE":
        pts = _line_points(ent)
        if pts is not None:
            (x1, y1, _z1), (x2, y2, _z2) = pts
            return (
                f"LINE layer={layer} handle={handle} "
                f"({_fmt_num(x1)},{_fmt_num(y1)})->({_fmt_num(x2)},{_fmt_num(y2)})"
            )
        return f"LINE layer={layer} handle={handle}"
    if dxf == "HATCH":
        pattern = ent.get("pattern_name") or geom.get("pattern_name") or ent.get("pattern") or "?"
        loops = ent.get("loops")
        if loops is None:
            loops = geom.get("loops")
        loop_count = len(loops) if isinstance(loops, list) else ent.get("loop_count", "?")
        return f"HATCH layer={layer} handle={handle} pattern={pattern} loops={loop_count}"
    if dxf in {"TEXT", "MTEXT"}:
        return f"{dxf} layer={layer} handle={handle} '{_text_value(ent)}'"
    if dxf == "INSERT":
        name = ent.get("block_name") or geom.get("block_name") or ent.get("name") or "?"
        return f"INSERT layer={layer} handle={handle} block={name}"
    if dxf in {"POLYLINE", "LWPOLYLINE"}:
        vertices = ent.get("vertices") or geom.get("vertices") or []
        count = len(vertices) if isinstance(vertices, list) else "?"
        return f"{dxf} layer={layer} handle={handle} vertices={count}"
    if dxf == "CIRCLE":
        radius = ent.get("radius") if ent.get("radius") is not None else geom.get("radius")
        return f"CIRCLE layer={layer} handle={handle} radius={_fmt_num(radius)}"
    return f"{dxf} layer={layer} handle={handle}"


def build_prompt(block_def: dict[str, Any]) -> str:
    name = _def_name(block_def)
    entities = _def_entities(block_def)
    dxf_hist = Counter(_dxf_name(ent) for ent in entities)
    layer_hist = Counter(_layer(ent) for ent in entities)
    bbox = line_bbox(entities)
    bbox_text = "(not derivable from LINE start/end)" if bbox is None else "[" + ", ".join(_fmt_num(v) for v in bbox) + "]"
    samples = [_entity_line(ent) for ent in entities[:30]]
    sample_text = "\n".join(f"- {line}" for line in samples) if samples else "- (no inline entities available)"
    return (
        "DWG block definition annotation task / DWG 블록 정의 주석 작업\n"
        "The model has no filesystem access. Use only the inline projection below.\n\n"
        f"Definition name: {name}\n"
        f"entity_count: {_entity_count(block_def)}\n"
        f"dxf_name histogram: {_hist_text(dxf_hist)}\n"
        f"layer histogram: {_hist_text(layer_hist)}\n"
        f"bbox from LINE start/end: {bbox_text}\n"
        "sampled entities (max 30):\n"
        f"{sample_text}\n\n"
        "Instructions / 지시사항:\n"
        "Classify the definition's likely architectural role. 보기: 평면 부분도, 심볼, 치수캐시, 가구, 기타.\n"
        "Estimate wall_likelihood as a number from 0 to 1.\n"
        "List up to 10 entity handles that look like wall lines, with a one-phrase reason each.\n"
        "Answer STRICTLY as one JSON object with this shape and no surrounding prose:\n"
        '{"def":"...","role":"...","wall_likelihood":0.0,'
        '"wall_line_handles":[{"handle":"...","reason":"..."}],"notes":"..."}'
    )


def build_units(ir: dict[str, Any], min_entities: int = 5, max_defs: int = 0) -> list[dict[str, Any]]:
    block_defs = [bd for bd in ir.get("block_definitions", []) if isinstance(bd, dict)]
    selected = [bd for bd in block_defs if _entity_count(bd) >= min_entities]
    selected.sort(key=lambda bd: (_def_name(bd).lower(), _def_name(bd), str(bd.get("handle") or "")))
    if max_defs and max_defs > 0:
        selected = selected[:max_defs]
    units: list[dict[str, Any]] = []
    for idx, block_def in enumerate(selected, start=1):
        name = _def_name(block_def)
        units.append({
            "unit_id": f"defannot-{_slug(name)}-{idx}",
            "kind": "def_annotation",
            "prompt": build_prompt(block_def),
        })
    return units


def write_queue(units: Iterable[dict[str, Any]], out_path: str | Path) -> int:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for unit in units:
            fh.write(json.dumps(unit, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def build_queue_file(ir_path: str | Path, out_path: str | Path, min_entities: int = 5, max_defs: int = 0) -> int:
    ir = load_ir(ir_path)
    return write_queue(build_units(ir, min_entities=min_entities, max_defs=max_defs), out_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ir", required=True, help="Path to dwg_graph_ir.json")
    parser.add_argument("--min-entities", type=int, default=5)
    parser.add_argument("--max-defs", type=int, default=0, help="0 means all")
    parser.add_argument("--out", required=True, help="Output queue JSONL path")
    args = parser.parse_args(argv)
    count = build_queue_file(args.ir, args.out, min_entities=args.min_entities, max_defs=args.max_defs)
    print(f"wrote {count} units to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
