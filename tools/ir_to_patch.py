"""IR -> cad_patch.v1 builder for perfect DWG roundtrip.

Converts a native_full dwg_graph_ir.json into a cad_patch.v1 whose operations
regenerate each model-space entity through the WIRED native write ops
(patch_engine.NATIVE_WRITE_OP_MAP). This module is the SINGLE place where the
IR's array geometry ([x,y,z]) is converted to the native job's object form
({x,y,z}) and where the IR 'vertices' key is renamed to the native 'points' key.

no-fake-success: an entity kind without a runnable write op (or, for dimension,
without extracted geometry) is reported in `deferred`, never silently emitted.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple


def _pt(arr: Any) -> Optional[Dict[str, float]]:
    """IR coordinate array [x,y,z] -> native job object {x,y,z}."""
    if not arr:
        return None
    return {"x": arr[0], "y": arr[1], "z": arr[2] if len(arr) > 2 else 0.0}


def _op_for(ent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map one IR entity to a cad_patch operation, or None if not regenerable."""
    g = ent.get("geometry") or {}
    kind = g.get("kind")
    layer = ent.get("layer")

    if kind == "line":
        return {"operation": "create_line",
                "args": {"start": _pt(g.get("start")), "end": _pt(g.get("end")), "layer": layer}}
    if kind == "circle":
        return {"operation": "create_circle",
                "args": {"center": _pt(g.get("center")), "radius": g.get("radius"), "layer": layer}}
    if kind == "block_reference":
        return {"operation": "insert_block",
                "args": {"name": g.get("block_name"), "position": _pt(g.get("position"))}}
    # --- Tier 2 (require family-op promotion to be runnable) ---
    if kind == "text":
        return {"operation": "create_text",
                "args": {"position": _pt(g.get("position")), "text": g.get("text"),
                         "height": g.get("height", 2.5), "layer": layer}}
    if kind in ("lwpolyline", "polyline"):
        points: List[Dict[str, float]] = []
        for v in (g.get("vertices") or []):
            p = v.get("point") if isinstance(v, dict) else v
            if not p:
                continue
            points.append({"x": p[0], "y": p[1],
                           "bulge": (v.get("bulge", 0.0) if isinstance(v, dict) else 0.0)})
        return {"operation": "create_polyline",
                "args": {"points": points, "closed": int(bool(g.get("closed"))), "layer": layer}}
    # --- Tier 3 (requires dimension extraction to populate geometry) ---
    if kind == "dimension":
        need = ("xline1_point", "xline2_point", "dim_line_point")
        if all(g.get(x) for x in need):
            return {"operation": "create_dimension",
                    "args": {"layer": layer, "dim_text": g.get("dim_text", ""),
                             "rotation": g.get("rotation", 0.0),
                             "xline1": _pt(g["xline1_point"]), "xline2": _pt(g["xline2_point"]),
                             "dim_line": _pt(g["dim_line_point"])}}
        return None  # extraction not landed yet -> deferred
    return None


def build_patch_from_ir(ir: Dict[str, Any], target_dwg: Dict[str, Any], patch_id: str,
                        kinds: Optional[set] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Build a (cad_patch.v1, deferred[]) pair from a native_full IR.

    kinds: optional set of geometry.kind to include (e.g. {"line","circle"} for a
    Tier-1a roundtrip); None = all kinds.
    """
    ops: List[Dict[str, Any]] = []
    deferred: List[Dict[str, Any]] = []
    for i, ent in enumerate(ir.get("entities") or []):
        g = ent.get("geometry") or {}
        kind = g.get("kind")
        if kinds is not None and kind not in kinds:
            continue
        op = _op_for(ent)
        if op is None:
            deferred.append({"index": i, "handle": ent.get("handle"), "kind": kind})
            continue
        op["step_id"] = "e%d" % i
        ops.append(op)
    patch = {
        "schema": "ariadne.cad_patch.v1",
        "patch_id": patch_id,
        "title": "roundtrip regen from IR (%d ops)" % len(ops),
        "source_agent": "ir_to_patch",
        "target_dwg": target_dwg,
        "operations": ops,
        "postconditions": [{"subject": "entity_count", "op": "delta_ge", "value": 1}],
        "policy": {"staged_copy": True, "write_mode": "write_copy"},
    }
    return patch, deferred


def kind_counts(ir: Dict[str, Any]) -> Dict[str, int]:
    from collections import Counter
    c = Counter((e.get("geometry") or {}).get("kind") for e in ir.get("entities") or [])
    return dict(c)


if __name__ == "__main__":
    import sys
    from collections import Counter
    ir_path = sys.argv[1]
    out_patch = sys.argv[2] if len(sys.argv) > 2 else None
    kinds = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
    ir = json.load(open(ir_path, encoding="utf-8-sig"))
    patch, deferred = build_patch_from_ir(
        ir, {"staged_path": "", "original_path": ""}, "cli", kinds)
    summary = {
        "ops": len(patch["operations"]),
        "deferred": len(deferred),
        "deferred_by_kind": dict(Counter(d["kind"] for d in deferred)),
        "ir_kinds": kind_counts(ir),
    }
    print(json.dumps(summary, ensure_ascii=False))
    if out_patch:
        with open(out_patch, "w", encoding="utf-8") as fh:
            json.dump(patch, fh, ensure_ascii=False)
        print("wrote", out_patch)
