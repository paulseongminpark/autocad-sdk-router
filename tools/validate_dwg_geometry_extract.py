#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_COORDINATE_TYPES = {
    "LINE": {"line"},
    "LWPOLYLINE": {"polyline"},
    "POLYLINE": {"polyline"},
    "ARC": {"arc"},
    "CIRCLE": {"circle"},
    "INSERT": {"block_reference"},
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def require_coordinate_payloads(payload: dict) -> list[str]:
    errors: list[str] = []
    seen: dict[str, int] = {}
    for entity in payload.get("entities", []):
        entity_type = entity.get("type")
        geometry = entity.get("geometry") or {}
        kind = geometry.get("kind")
        if entity_type in REQUIRED_COORDINATE_TYPES and kind in REQUIRED_COORDINATE_TYPES[entity_type]:
            seen[entity_type] = seen.get(entity_type, 0) + 1
            if kind == "line" and not (geometry.get("start") and geometry.get("end")):
                errors.append(f"{entity_type}:{entity.get('handle')} missing start/end")
            if kind == "polyline" and not geometry.get("vertices"):
                errors.append(f"{entity_type}:{entity.get('handle')} missing vertices")
            if kind in {"arc", "circle"} and not geometry.get("center"):
                errors.append(f"{entity_type}:{entity.get('handle')} missing center")
            if kind == "block_reference" and not geometry.get("position"):
                errors.append(f"{entity_type}:{entity.get('handle')} missing position")

    available_types = set((payload.get("summary") or {}).get("entities_by_type", {}).keys())
    for entity_type in sorted(available_types & REQUIRED_COORDINATE_TYPES.keys()):
        if seen.get(entity_type, 0) == 0:
            errors.append(f"{entity_type} exists in summary but has no coordinate payloads")
    return errors


def validate(payload: dict) -> dict:
    errors: list[str] = []
    entities = payload.get("entities", [])
    summary = payload.get("summary") or {}
    # entities.length == summary.modelspace_count
    if len(entities) != summary.get("modelspace_count"):
        errors.append(
            f"entities.length != summary.modelspace_count ({len(entities)} != {summary.get('modelspace_count')})"
        )
    errors.extend(require_coordinate_payloads(payload))
    return {
        "schema": "ariadne.dwg_geometry_validation.v1",
        "status": "PASS" if not errors else "FAIL",
        "entity_count": len(entities),
        "modelspace_count": summary.get("modelspace_count"),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_path")
    parser.add_argument("--out")
    args = parser.parse_args()

    result = validate(load_json(Path(args.json_path)))
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
