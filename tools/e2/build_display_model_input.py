#!/usr/bin/env python3
"""Build the exact XCLIP-visible segment population consumed by E2 model arms.

The input is the already source-scoped native DWG graph.  This tool keeps
XCLIP metadata intact, adapts the graph to WorldIR, expands every placement,
and writes two hash-bound artifacts:

* ``display_worldir_probe.json`` -- the complete visibility/conservation proof;
* ``display_model_input.json`` -- only the requested target segments, with the
  same stable placed identities that every downstream feature/model arm must
  consume.

It does not decide that WorldIR is correct.  ``experiment_guard.py`` compares
these outputs to the independent full-AutoCAD/ObjectARX target oracle and fails
closed on any count or identity disagreement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping


_E2_DIR = Path(__file__).resolve().parent
if str(_E2_DIR) not in sys.path:
    sys.path.insert(0, str(_E2_DIR))

from instruments import dwg_graph_to_worldir as graph_adapter
from instruments import worldir_oracle


PASS = "PASS"
BLOCKED = "BLOCKED"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _stable_segment_id(segment: Mapping[str, Any]) -> str:
    return str(segment.get("placed_uid") or segment.get("lineage_id") or "")


def build_population(
    *,
    scoped_native_graph: Path,
    source_dwg: Path,
    target_layers: list[str],
    out_dir: Path,
) -> dict[str, Any]:
    """Build a source-bound display WorldIR and exact target population."""

    out_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = out_dir / "display_model_input_receipt.json"
    world_path = out_dir / "display_worldir_probe.json"
    model_path = out_dir / "display_model_input.json"

    def finish(status: str, reason_code: str, reason: str, **extra: Any) -> dict[str, Any]:
        receipt = {
            "schema": "ariadne.e2.model_input_population_receipt.v1",
            "status": status,
            "reason_code": reason_code,
            "reason": reason,
            **extra,
        }
        _write_json(receipt_path, receipt)
        receipt["receipt"] = str(receipt_path)
        return receipt

    existing = [path for path in (receipt_path, world_path, model_path) if path.exists()]
    if existing:
        return {
            "schema": "ariadne.e2.model_input_population_receipt.v1",
            "status": BLOCKED,
            "reason_code": "OUTPUT_ALREADY_EXISTS",
            "reason": "Refusing to overwrite existing evidence: " + ", ".join(map(str, existing)),
        }
    if not source_dwg.is_file() or source_dwg.suffix.lower() != ".dwg":
        return finish(
            BLOCKED,
            "SOURCE_DWG_REQUIRED",
            f"Source DWG is missing or has the wrong extension: {source_dwg}",
        )
    if not scoped_native_graph.is_file():
        return finish(
            BLOCKED,
            "SCOPED_NATIVE_GRAPH_REQUIRED",
            f"Scoped native graph is missing: {scoped_native_graph}",
        )
    if (
        not isinstance(target_layers, list)
        or not target_layers
        or any(not isinstance(layer, str) or not layer.strip() for layer in target_layers)
        or len(set(target_layers)) != len(target_layers)
    ):
        return finish(
            BLOCKED,
            "TARGET_LAYERS_INVALID",
            "Target layers must be a non-empty list of unique non-empty strings.",
        )

    source_before = _sha256(source_dwg)
    graph_sha256 = _sha256(scoped_native_graph)
    try:
        native = _read_json(scoped_native_graph)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return finish(
            BLOCKED,
            "SCOPED_NATIVE_GRAPH_INVALID",
            f"Scoped native graph could not be read: {type(exc).__name__}: {exc}",
            source_sha256_before=source_before,
            scoped_native_graph_sha256=graph_sha256,
        )

    graph_drawing_id = str((native.get("source") or {}).get("sha256") or "").lower()
    if graph_drawing_id != source_before:
        return finish(
            BLOCKED,
            "SOURCE_IDENTITY_MISMATCH",
            "The scoped native graph and source DWG do not identify the same bytes.",
            source_sha256_before=source_before,
            scoped_native_graph_drawing_id=graph_drawing_id,
            scoped_native_graph_sha256=graph_sha256,
        )

    try:
        adapted = graph_adapter.adapt(native)
        world = worldir_oracle.expand_world_ir(adapted)
    except Exception as exc:  # fail closed at the instrument boundary
        return finish(
            BLOCKED,
            "WORLDIR_EXPANSION_FAILED",
            f"Display WorldIR expansion failed: {type(exc).__name__}: {exc}",
            source_sha256_before=source_before,
            scoped_native_graph_sha256=graph_sha256,
        )

    source_after = _sha256(source_dwg)
    if source_after != source_before:
        return finish(
            BLOCKED,
            "SOURCE_CHANGED_DURING_BUILD",
            "The source DWG changed while the read-only model population was built.",
            source_sha256_before=source_before,
            source_sha256_after=source_after,
            scoped_native_graph_sha256=graph_sha256,
        )
    conservation = world.get("conservation_ledger")
    if (
        adapted.get("status") != PASS
        or world.get("status") != PASS
        or world.get("drawing_id") != source_before
        or not isinstance(conservation, Mapping)
        or conservation.get("conservation_ok") is not True
    ):
        return finish(
            BLOCKED,
            "WORLDIR_CONSERVATION_FAILED",
            "Adapter status, drawing identity, or WorldIR conservation is incomplete.",
            source_sha256_before=source_before,
            source_sha256_after=source_after,
            scoped_native_graph_sha256=graph_sha256,
            adapter_status=adapted.get("status"),
            world_status=world.get("status"),
            world_drawing_id=world.get("drawing_id"),
        )

    target_set = set(target_layers)
    world_segments = world.get("segments")
    entries = conservation.get("entity_entries")
    if not isinstance(world_segments, list) or not isinstance(entries, list):
        return finish(
            BLOCKED,
            "WORLDIR_LINEAGE_MISSING",
            "WorldIR has no segment population or per-entity conservation ledger.",
            source_sha256_before=source_before,
            source_sha256_after=source_after,
            scoped_native_graph_sha256=graph_sha256,
        )

    segments = [
        segment
        for segment in world_segments
        if isinstance(segment, Mapping) and segment.get("source_layer") in target_set
    ]
    ids = [_stable_segment_id(segment) for segment in segments]
    counts = Counter(str(segment.get("source_layer")) for segment in segments)
    if any(not segment_id for segment_id in ids) or len(ids) != len(set(ids)):
        return finish(
            BLOCKED,
            "MODEL_INPUT_IDENTITY_INVALID",
            "Every target segment must have one unique stable placed identity.",
            source_sha256_before=source_before,
            source_sha256_after=source_after,
            scoped_native_graph_sha256=graph_sha256,
        )
    empty_layers = [layer for layer in target_layers if counts.get(layer, 0) == 0]
    if empty_layers:
        return finish(
            BLOCKED,
            "TARGET_LAYER_EMPTY",
            "WorldIR emitted no visible segments for: " + ", ".join(empty_layers),
            source_sha256_before=source_before,
            source_sha256_after=source_after,
            scoped_native_graph_sha256=graph_sha256,
        )

    target_entries = [
        entry
        for entry in entries
        if isinstance(entry, Mapping) and entry.get("source_layer") in target_set
    ]
    expected = sum(int(entry.get("expected_segments", 0)) for entry in target_entries)
    visible = sum(int(entry.get("visible_source_segments", 0)) for entry in target_entries)
    clipped = sum(int(entry.get("clipped_away_segments", 0)) for entry in target_entries)
    if expected != visible + clipped or visible != len(segments):
        return finish(
            BLOCKED,
            "TARGET_CONSERVATION_FAILED",
            "Target source-segment conservation or emitted identity count is inconsistent.",
            source_sha256_before=source_before,
            source_sha256_after=source_after,
            scoped_native_graph_sha256=graph_sha256,
            expected_source_segments=expected,
            visible_source_segments=visible,
            emitted_segment_instances=len(segments),
            clipped_away_source_segments=clipped,
        )

    model = {
        "schema": "ariadne.e2.model_input_population.v1",
        "ir": "seg.v1",
        "drawing_id": source_before,
        "source_sha256": source_before,
        "population_role": "canonical_segment_population_for_all_model_arms",
        "population_exact": True,
        "xclip_applied": True,
        "target_layers": target_layers,
        "target_counts": {layer: counts[layer] for layer in target_layers},
        "segments": segments,
    }
    _write_json(world_path, world)
    _write_json(model_path, model)
    world_sha256 = _sha256(world_path)
    model_sha256 = _sha256(model_path)
    return finish(
        PASS,
        "MODEL_INPUT_POPULATION_BUILT",
        "XCLIP-visible WorldIR segments were preserved as the canonical model population.",
        source_path=str(source_dwg.resolve()),
        source_sha256_before=source_before,
        source_sha256_after=source_after,
        source_unchanged=True,
        scoped_native_graph=str(scoped_native_graph.resolve()),
        scoped_native_graph_sha256=graph_sha256,
        world_ir_probe=str(world_path),
        world_ir_probe_sha256=world_sha256,
        model_input_ir=str(model_path),
        model_input_ir_sha256=model_sha256,
        target_layers=target_layers,
        target_counts={layer: counts[layer] for layer in target_layers},
        expected_source_segments=expected,
        visible_source_segments=visible,
        clipped_away_source_segments=clipped,
        emitted_segment_instances=len(segments),
    )


def _parse_layers(values: Iterable[str]) -> list[str]:
    layers: list[str] = []
    for value in values:
        layers.extend(piece.strip() for piece in value.split(",") if piece.strip())
    return layers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build an exact XCLIP-visible E2 model segment population."
    )
    parser.add_argument("--scoped-native-graph", type=Path, required=True)
    parser.add_argument("--source-dwg", type=Path, required=True)
    parser.add_argument("--target-layer", action="append", default=[], required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = build_population(
        scoped_native_graph=args.scoped_native_graph,
        source_dwg=args.source_dwg,
        target_layers=_parse_layers(args.target_layer),
        out_dir=args.out_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == PASS else 2


if __name__ == "__main__":
    raise SystemExit(main())
