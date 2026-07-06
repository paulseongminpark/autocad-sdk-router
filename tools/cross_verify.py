#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional

if __package__ in (None, ""):
    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)

import cadctl
import run_route


LIBREDWG_KIND_MAP: Dict[str, str] = {
    "LINE": "line",
    "ARC": "arc",
    "CIRCLE": "circle",
    "INSERT": "block_reference",
    "MTEXT": "mtext",
    "TEXT": "text",
    "HATCH": "hatch",
    "POLYLINE_2D": "polyline",
    "POLYLINE_3D": "polyline",
    "LWPOLYLINE": "lwpolyline",
    "POINT": "point",
}

_JSON_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin1")


def _load_json_with_fallback(path: str, encodings: Iterable[str] = _JSON_ENCODINGS) -> Dict[str, Any]:
    data = open(path, "rb").read()
    last_error: Optional[Exception] = None
    for encoding in encodings:
        try:
            return json.loads(data.decode(encoding))
        except Exception as exc:
            last_error = exc
    raise ValueError(f"could not decode JSON at {path}: {last_error}")


def summarize_ir_doc(ir_doc: Dict[str, Any]) -> Dict[str, Any]:
    entities = [e for e in (ir_doc.get("entities") or []) if isinstance(e, dict)]
    mapped = Counter()
    for ent in entities:
        kind = (ent.get("geometry") or {}).get("kind")
        if isinstance(kind, str) and kind:
            mapped[kind] += 1
    layers = (ir_doc.get("symbol_tables") or {}).get("layers") or []
    return {
        "entity_total": len(entities),
        "layer_count": len([row for row in layers if isinstance(row, dict)]),
        "mapped_kind_counts": dict(sorted(mapped.items())),
    }


def _libredwg_modelspace_records(lib_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    objects = [row for row in (lib_doc.get("OBJECTS") or []) if isinstance(row, dict)]
    by_handle_id: Dict[int, Dict[str, Any]] = {}
    for row in objects:
        handle = row.get("handle")
        if isinstance(handle, list) and handle:
            by_handle_id[int(handle[-1])] = row
    model = next(
        (
            row
            for row in objects
            if row.get("object") == "BLOCK_HEADER" and row.get("name") == "*Model_Space"
        ),
        None,
    )
    if model is None:
        raise ValueError("LibreDWG JSON has no *Model_Space block header")
    records: List[Dict[str, Any]] = []
    for ref in model.get("entities") or []:
        if not isinstance(ref, list) or not ref:
            continue
        row = by_handle_id.get(int(ref[-1]))
        if row is not None:
            records.append(row)
    return records


def summarize_libredwg_doc(lib_doc: Dict[str, Any]) -> Dict[str, Any]:
    objects = [row for row in (lib_doc.get("OBJECTS") or []) if isinstance(row, dict)]
    layers = [row for row in objects if row.get("object") == "LAYER"]
    mapped = Counter()
    unmapped = Counter()
    for row in _libredwg_modelspace_records(lib_doc):
        entity_name = row.get("entity") or row.get("object") or row.get("_subclass") or "UNKNOWN"
        canonical = LIBREDWG_KIND_MAP.get(str(entity_name))
        if canonical is not None:
            mapped[canonical] += 1
        else:
            unmapped[(str(entity_name), str(row.get("_subclass") or ""))] += 1
    return {
        "entity_total": sum(mapped.values()) + sum(unmapped.values()),
        "layer_count": len(layers),
        "mapped_kind_counts": dict(sorted(mapped.items())),
        "unmapped": [
            {"entity": entity, "subclass": subclass or None, "count": count}
            for (entity, subclass), count in sorted(unmapped.items())
        ],
    }


def build_verdict(lib_summary: Dict[str, Any], ir_summary: Dict[str, Any]) -> Dict[str, Any]:
    deltas: List[Dict[str, Any]] = []
    if lib_summary["entity_total"] != ir_summary["entity_total"]:
        deltas.append(
            {"field": "entity_total", "libredwg": lib_summary["entity_total"], "ir": ir_summary["entity_total"]}
        )
    if lib_summary["layer_count"] != ir_summary["layer_count"]:
        deltas.append(
            {"field": "layer_count", "libredwg": lib_summary["layer_count"], "ir": ir_summary["layer_count"]}
        )
    keys = sorted(
        set(lib_summary.get("mapped_kind_counts") or {}) | set(ir_summary.get("mapped_kind_counts") or {})
    )
    for key in keys:
        lib_count = int((lib_summary.get("mapped_kind_counts") or {}).get(key, 0))
        ir_count = int((ir_summary.get("mapped_kind_counts") or {}).get(key, 0))
        if lib_count != ir_count:
            deltas.append({"field": f"kind:{key}", "libredwg": lib_count, "ir": ir_count})
    return {
        "agree": not deltas,
        "deltas": deltas,
        "unmapped": list(lib_summary.get("unmapped") or []),
        "notes": [
            "LibreDWG is compared on modelspace entity total, layer table count, and explicit mapped kinds only.",
            "Unmapped LibreDWG entities are surfaced in unmapped and excluded from per-kind equality checks.",
        ],
    }


def _load_ir_summary(dwg_path: str, *, ir_path: Optional[str], out_dir: str) -> Dict[str, Any]:
    if ir_path:
        ir_doc = _load_json_with_fallback(ir_path)
        return {
            "summary": summarize_ir_doc(ir_doc),
            "ir_path": ir_path,
            "source": "existing_ir",
        }
    inspect_out = os.path.join(out_dir, "inspect")
    env = cadctl.Cad().inspect(dwg_path, inspect_out, mode="rich", include_rich=True)
    generated_ir = env.get("dwg_graph_ir")
    if env.get("status") != "ok" or not generated_ir or not os.path.isfile(generated_ir):
        raise ValueError(f"cadctl inspect failed: {env.get('status')} ({env.get('reason')})")
    ir_doc = _load_json_with_fallback(generated_ir)
    return {
        "summary": summarize_ir_doc(ir_doc),
        "ir_path": generated_ir,
        "source": "cadctl.inspect",
    }


def cross_verify_dwg(
    dwg_path: str,
    *,
    ir_path: Optional[str] = None,
    out_dir: Optional[str] = None,
    libredwg_bin: Optional[str] = None,
) -> Dict[str, Any]:
    run_dir = out_dir or tempfile.mkdtemp(prefix="cross_verify_")
    os.makedirs(run_dir, exist_ok=True)
    sidecar = run_route.run_libredwg_sidecar(
        input_path=dwg_path,
        run_root=run_dir,
        libredwg_bin=libredwg_bin,
    )
    if sidecar.get("status") != "ok":
        return {
            "status": sidecar.get("status", "error"),
            "agree": False,
            "reason": sidecar.get("error") or sidecar.get("detail"),
            "sidecar": sidecar,
        }
    try:
        lib_doc = _load_json_with_fallback(sidecar["json_output"])
        lib_summary = summarize_libredwg_doc(lib_doc)
        ir_loaded = _load_ir_summary(dwg_path, ir_path=ir_path, out_dir=run_dir)
        verdict = build_verdict(lib_summary, ir_loaded["summary"])
    except Exception as exc:
        return {
            "status": "blocked",
            "agree": False,
            "reason": str(exc),
            "sidecar": sidecar,
        }

    result = {
        "status": "ok" if verdict["agree"] else "mismatch",
        "agree": verdict["agree"],
        "dwg_path": dwg_path,
        "ir_path": ir_loaded["ir_path"],
        "ir_source": ir_loaded["source"],
        "libredwg": lib_summary,
        "ir": ir_loaded["summary"],
        "deltas": verdict["deltas"],
        "unmapped": verdict["unmapped"],
        "notes": verdict["notes"],
        "sidecar": {
            "run_dir": sidecar.get("run_dir"),
            "json_output": sidecar.get("json_output"),
            "dxf_output": sidecar.get("dxf_output"),
            "license_boundary": sidecar.get("license_boundary"),
        },
    }
    verdict_path = os.path.join(run_dir, "cross_verify_verdict.json")
    with open(verdict_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    result["verdict_path"] = verdict_path
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Cross-engine DWG verification via LibreDWG sidecar + CADOS IR.")
    ap.add_argument("dwg", help="DWG path to verify")
    ap.add_argument("--ir", dest="ir_path", default=None, help="Existing dwg_graph_ir.json path")
    ap.add_argument("--out-dir", default=None, help="Output directory for sidecar artifacts and verdict JSON")
    ap.add_argument("--libredwg-bin", default=None, help="LibreDWG sidecar bin dir")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    verdict = cross_verify_dwg(
        args.dwg,
        ir_path=args.ir_path,
        out_dir=args.out_dir,
        libredwg_bin=args.libredwg_bin,
    )
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0 if verdict.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
