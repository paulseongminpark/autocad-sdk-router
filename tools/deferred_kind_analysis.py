"""Build a strategy matrix for deferred kind writes in R3b runs.

Strategy rules used by this module:
- ``native_append_extension`` when the entity geometry includes explicit shape data
  that is directly reconstructible (``vertices`` or ``paths`` keys).
- ``decompose_to_certified`` when the geometry looks like a hatch boundary and can be
  approximated by certified entities (``boundary`` key or hatch-like kind).
- ``defer_documented`` when only lightweight metadata is present (for example
  bbox-only payloads), meaning the existing IR payload is insufficient.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional

SCHEMA_VERSION = "ariadne.deferred_kind_analysis.v1"


def _reason_class(reason: Optional[Any]) -> str:
    reason_text = str(reason or "")
    lowered = reason_text.lower()
    if "no block_definitions entry" in lowered and "nested block_name" in lowered:
        return "missing_nested_def"
    if "unsupported" in lowered and "append_entity" in lowered:
        return "unsupported_kind"
    return "other"


def _ensure_list(value: Any, default: List[Any]) -> List[Any]:
    return value if isinstance(value, list) else default


def _extract_block_definitions(census_ir: Mapping[str, Any]) -> Dict[str, List[Mapping[str, Any]]]:
    blocks = _ensure_list(census_ir.get("block_definitions"), [])
    result: Dict[str, List[Mapping[str, Any]]] = {}
    for block in blocks:
        if not isinstance(block, Mapping):
            continue
        name = block.get("name")
        if not isinstance(name, str):
            continue
        defs = _ensure_list(block.get("def_entities"), [])
        result[name] = [item for item in defs if isinstance(item, Mapping)]
    return result


def _to_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _entity_geometry(entity: Mapping[str, Any]) -> Mapping[str, Any]:
    geometry = entity.get("geometry")
    if isinstance(geometry, Mapping):
        return geometry
    return {}

def _entity_kind(entity: Mapping[str, Any], fallback: Optional[Any]) -> str:
    geometry = _entity_geometry(entity)
    kind = entity.get("kind")
    if isinstance(kind, str) and kind:
        return kind
    geom_kind = geometry.get("kind")
    if isinstance(geom_kind, str) and geom_kind:
        return geom_kind
    if isinstance(fallback, str) and fallback:
        return fallback
    return "unknown"


def _entity_dxf_name(entity: Mapping[str, Any]) -> Optional[str]:
    dxf_name = entity.get("dxf_name")
    if isinstance(dxf_name, str) and dxf_name:
        return dxf_name
    geometry = _entity_geometry(entity)
    dxf = geometry.get("dxf_name")
    if isinstance(dxf, str) and dxf:
        return dxf
    return None


def _strategy_for(kind: str, geometry: Mapping[str, Any]) -> str:
    keys = set(geometry.keys())

    if kind.upper() in {"HATCH", "HATCHBOUNDARY", "HATCH_BOUNDARY"} or "boundary" in keys:
        return "decompose_to_certified"

    explicit_shape_keys = {"vertices", "paths"}
    if keys & explicit_shape_keys:
        return "native_append_extension"

    return "defer_documented"


def analyze(deferred: Iterable[Mapping[str, Any]], census_ir: Mapping[str, Any]) -> Dict[str, Any]:
    reasons = Counter({"unsupported_kind": 0, "missing_nested_def": 0, "other": 0})
    block_entities = _extract_block_definitions(census_ir)

    kind_stats: MutableMapping[str, MutableMapping[str, Any]] = {}
    missing_nested_names: List[str] = []

    for record in deferred:
        if not isinstance(record, Mapping):
            continue

        kind_class = _reason_class(record.get("reason"))
        reasons[kind_class] += 1

        if kind_class == "missing_nested_def":
            block_name = record.get("block_name")
            if isinstance(block_name, str):
                missing_nested_names.append(block_name)
            continue

        if kind_class != "unsupported_kind":
            continue

        block_name = record.get("block_name")
        def_index = _to_int(record.get("def_entity_index"))
        resolved_kind = record.get("kind")
        if not isinstance(resolved_kind, str) or not resolved_kind:
            resolved_kind = None

        if not isinstance(block_name, str):
            if resolved_kind is None:
                continue
            block_name = None
        block_defs = block_entities.get(block_name) if isinstance(block_name, str) else None

        if (
            block_defs is None
            or def_index is None
            or def_index < 0
            or def_index >= len(block_defs)
        ):
            if resolved_kind is None:
                continue
            stats = kind_stats.setdefault(
                resolved_kind,
                {
                    "count": 0,
                    "dxf_name_set": set(),
                    "geometry_key_counts": Counter(),
                    "sample": None,
                },
            )
            stats["count"] += 1
            if stats["sample"] is None:
                stats["sample"] = {
                    "block_name": block_name,
                    "def_entity_index": def_index,
                    "geometry": [],
                }
            continue

        if not isinstance(block_name, str) or def_index is None:
            if resolved_kind is None:
                continue
            stats = kind_stats.setdefault(
                resolved_kind,
                {
                    "count": 0,
                    "dxf_name_set": set(),
                    "geometry_key_counts": Counter(),
                    "sample": None,
                },
            )
            stats["count"] += 1
            if stats["sample"] is None:
                stats["sample"] = {
                    "block_name": block_name if isinstance(block_name, str) else None,
                    "def_entity_index": def_index,
                    "geometry": [],
                }
            continue
        
        entity = block_defs[def_index]
        geometry = _entity_geometry(entity)
        resolved_kind = _entity_kind(entity, resolved_kind)
        dxf_name = _entity_dxf_name(entity)

        stats = kind_stats.setdefault(
            resolved_kind,
            {
                "count": 0,
                "dxf_name_set": set(),
                "geometry_key_counts": Counter(),
                "sample": None,
            },
        )
        stats["count"] += 1
        if dxf_name is not None:
            stats["dxf_name_set"].add(dxf_name)

        geometry_keys = set(geometry.keys())
        for key in geometry_keys:
            stats["geometry_key_counts"][key] += 1

        if stats["sample"] is None:
            stats["sample"] = {
                "block_name": block_name,
                "def_entity_index": def_index,
                "geometry": sorted(geometry_keys),
            }

    unsupported_kinds = []
    for kind, stats in kind_stats.items():
        count = stats["count"]
        if count <= 0:
            continue
        geometry_key_counts: Counter = stats["geometry_key_counts"]
        geometry_key_fractions = {
            key: geometry_key_counts[key] / count for key in sorted(geometry_key_counts.keys())
        }
        dxf_names = sorted(stats["dxf_name_set"])
        sample = stats["sample"] or {
            "block_name": None,
            "def_entity_index": None,
            "geometry": [],
        }

        sample_geometry = {}
        if sample and sample.get("geometry") is not None:
            sample_geometry = {key: True for key in sample["geometry"]}

        unsupported_kinds.append(
            {
                "kind": kind,
                "dxf_name_set": dxf_names,
                "count": count,
                "geometry_keys_present": geometry_key_fractions,
                "sample": sample if sample else {"block_name": None, "def_entity_index": None, "geometry": []},
                "strategy": _strategy_for(kind, sample_geometry),
            }
        )

    unsupported_kinds.sort(key=lambda item: item["count"], reverse=True)

    missing_nested = [name for name in missing_nested_names if isinstance(name, str)]
    all_anonymous = False
    if missing_nested:
        all_anonymous = all(name.startswith("*") for name in missing_nested)

    total = reasons["unsupported_kind"] + reasons["missing_nested_def"] + reasons["other"]
    return {
        "schema": SCHEMA_VERSION,
        "reasons": dict(reasons),
        "unsupported_kinds": unsupported_kinds,
        "missing_nested_defs": {
            "names": missing_nested[:30],
            "count": len(missing_nested),
            "all_anonymous": all_anonymous,
        },
        "totals": {
            "total": total,
            "unsupported_kind": reasons["unsupported_kind"],
            "missing_nested_def": reasons["missing_nested_def"],
            "other": reasons["other"],
        },
    }


def _render_markdown(report: Mapping[str, Any]) -> str:
    rows = sorted(
        report.get("unsupported_kinds", []),
        key=lambda row: row.get("count", 0),
        reverse=True,
    )
    lines = [
        "# Deferred kind analysis",
        "",
        "| kind | count | strategy | dxf_name_set | geometry_key_count |",
        "| --- | --- | --- | --- | --- |",
    ]

    if not rows:
        lines.append("| *(none)* | 0 | - | - | - |")
        return "\n".join(lines) + "\n"

    for row in rows:
        lines.append(
            "| {kind} | {count} | {strategy} | {dxf} | {geom_count} |".format(
                kind=row["kind"],
                count=row["count"],
                strategy=row["strategy"],
                dxf=";".join(row["dxf_name_set"]),
                geom_count=len(row["geometry_keys_present"]),
            )
        )
    return "\n".join(lines) + "\n"


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _load_input(deferred_path: Path, census_path: Path) -> Any:
    return _load_json(deferred_path), _load_json(census_path)


def run_analysis(run_dir: Path, out_json: Optional[Path], out_md: Optional[Path]) -> int:
    deferred_path = run_dir / "deferred.json"
    census_path = run_dir / "census" / "dwg_graph_ir.json"
    if not deferred_path.exists() or not census_path.exists():
        missing = []
        if not deferred_path.exists():
            missing.append(str(deferred_path))
        if not census_path.exists():
            missing.append(str(census_path))
        print(f"Missing file(s): {', '.join(missing)}", file=sys.stderr)
        return 3

    deferred, census_ir = _load_input(deferred_path, census_path)
    report = analyze(deferred, census_ir)
    json_text = json.dumps(report, indent=2, sort_keys=True)
    if out_json is not None:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json_text, encoding="utf-8-sig")
    if out_md is not None:
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(_render_markdown(report), encoding="utf-8-sig")
    if out_json is None and out_md is None:
        print(json_text)
    return 0


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deferred kind strategy matrix.")
    parser.add_argument("--run-dir", required=True, type=Path, dest="run_dir")
    parser.add_argument("--out-json", type=Path, help="Optional JSON output path")
    parser.add_argument("--out-md", type=Path, help="Optional Markdown output path")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    return run_analysis(args.run_dir, args.out_json, args.out_md)


if __name__ == "__main__":
    raise SystemExit(main())
