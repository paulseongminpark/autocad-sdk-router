#!/usr/bin/env python3
"""Build the leakage-free L0 detector population from a full native DWG graph.

The native display oracle decides which *linear* source-segment instances are
visible after INSERT transforms, layer/entity visibility and XCLIP.  This tool
independently expands the full native graph to WorldIR, requires exact stable-ID
agreement with that oracle, and then separates two files:

* ``detector_truth.json`` retains only the owner-supplied W1/W2 positive
  *layer* anchor; every object label remains ``UNKNOWN``;
* ``detector_input.seg.json`` is exact SEG-IR v1 with drawing-salted,
  collision-free layer pseudonyms and unknown labels.  It preserves only the
  within-drawing layer partition, so a detector cannot read the owner's names.

The layer anchor does not prove W1/W2 purity, wall completeness, or any
object-level negative.  Arc chords are accounted for but are outside the v1
linear detector universe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping


_E2_DIR = Path(__file__).resolve().parent
if str(_E2_DIR) not in sys.path:
    sys.path.insert(0, str(_E2_DIR))

from instruments import dwg_graph_to_worldir as graph_adapter  # noqa: E402
from instruments import worldir_oracle  # noqa: E402
from target_population_oracle import (  # noqa: E402
    TargetPopulationContractError,
    validate_target_population_oracle,
)


PASS = "PASS"
PASS_WITH_DEFERRAL = "PASS_WITH_DEFERRAL"
BLOCKED = "BLOCKED"
WALL_LAYERS = (
    "X-평면도(기본형)$0$W1",
    "X-평면도(기본형)$0$W2",
)
LINEAR_KINDS = frozenset({"line", "poly-edge"})
SEGMENT_KEYS = frozenset({"sid", "handle", "pts", "layer", "kind", "label", "source"})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _file_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def _stable_id(segment: Mapping[str, Any]) -> str:
    return str(segment.get("placed_uid") or segment.get("lineage_id") or "")


def _oracle_ids(
    oracle_path: Path,
    drawing_id: str,
    *,
    source_dwg: Path | None = None,
    required_geometry_scope: str | None,
) -> tuple[set[str], dict[str, set[str]], dict[str, Any]]:
    oracle = _read_json(oracle_path)
    contract = validate_target_population_oracle(
        oracle,
        oracle_path=oracle_path,
        source_dwg=source_dwg,
        expected_source_sha256=drawing_id,
        expected_geometry_scope=required_geometry_scope,
    )

    targets = oracle.get("targets")
    if not isinstance(targets, list):
        raise ValueError(f"native oracle has no targets: {oracle_path}")
    union: set[str] = set()
    by_layer: dict[str, set[str]] = {}
    declared_visible = 0
    for index, target in enumerate(targets):
        if not isinstance(target, Mapping):
            raise ValueError(f"oracle target[{index}] is not an object")
        layer = str(target.get("layer") or "")
        values = target.get("native_visible_segment_ids")
        visible = target.get("native_visible_source_segments")
        if not layer or not isinstance(values, list) or not isinstance(visible, int) or visible < 0:
            raise ValueError(f"oracle target[{index}] is incomplete")
        ids = {str(value) for value in values if isinstance(value, str) and value}
        if len(ids) != len(values) or len(ids) != visible:
            raise ValueError(f"oracle target[{index}] has duplicate or incomplete stable IDs")
        if union & ids:
            raise ValueError("a native stable segment ID appears in more than one target layer")
        union.update(ids)
        by_layer[layer] = ids
        declared_visible += visible
    if declared_visible != len(union):
        raise ValueError("native oracle union does not conserve declared visible counts")
    return union, by_layer, {
        **contract,
        "path": str(oracle_path.resolve()),
        "sha256": _sha256(oracle_path),
    }


def _model_segment(
    segment: Mapping[str, Any], layer_pseudonyms: Mapping[str, str]
) -> dict[str, Any]:
    segment_id = _stable_id(segment)
    source_layer = str(segment.get("source_layer") or "")
    return {
        "sid": segment_id,
        "handle": segment_id,
        "pts": [list(segment["p0_world"]), list(segment["p1_world"])],
        "layer": layer_pseudonyms[source_layer],
        "kind": str(segment.get("kind") or "line"),
        "label": "unknown",
        "source": "native",
    }


def _truth_record(segment: Mapping[str, Any]) -> dict[str, Any]:
    layer = str(segment.get("source_layer") or "")
    return {
        "placed_uid": _stable_id(segment),
        "object_label": "UNKNOWN",
        "layer_anchor": "POSITIVE_UNLABELED" if layer in WALL_LAYERS else "UNKNOWN",
        "owner_wall_layer": layer if layer in WALL_LAYERS else None,
        "source_layer": layer,
        "kind": str(segment.get("kind") or ""),
        "source_entity_handle": str(segment.get("source_entity_handle") or ""),
        "source_def_handle": str(segment.get("source_def_handle") or ""),
        "lineage_id": str(segment.get("lineage_id") or ""),
    }


def _drawing_local_layer_pseudonyms(
    layers: Iterable[str], drawing_id: str
) -> dict[str, str]:
    unique_layers = set(layers)
    salted_order = sorted(
        unique_layers,
        key=lambda layer: (
            hashlib.sha256(f"{drawing_id}\0{layer}".encode("utf-8")).digest(),
            layer,
        ),
    )
    return {
        layer: f"L{index:06d}"
        for index, layer in enumerate(salted_order, start=1)
    }


def _validate_model_input(
    model: Mapping[str, Any],
    expected_ids: set[str],
    expected_layer_by_id: Mapping[str, str],
) -> dict[str, Any]:
    expected_top = {"ir", "drawing_id", "units", "scale_mm_per_unit", "segments"}
    if set(model) != expected_top or model.get("ir") != "seg.v1":
        raise ValueError("detector input is not exact SEG-IR v1")
    segments = model.get("segments")
    if not isinstance(segments, list):
        raise ValueError("detector input segments must be a list")
    observed: set[str] = set()
    for index, segment in enumerate(segments):
        if not isinstance(segment, Mapping) or set(segment) != SEGMENT_KEYS:
            raise ValueError(f"detector input segment[{index}] violates the exact key contract")
        segment_id = str(segment.get("handle") or "")
        if (
            not segment_id
            or segment.get("sid") != segment_id
            or not isinstance(segment.get("layer"), str)
            or re.fullmatch(r"L\d{6}", str(segment.get("layer"))) is None
            or segment.get("layer") != expected_layer_by_id.get(segment_id)
            or segment.get("label") != "unknown"
            or segment.get("source") != "native"
            or segment.get("kind") not in LINEAR_KINDS
        ):
            raise ValueError(f"detector input segment[{index}] contains a cue or invalid identity")
        if segment_id in observed:
            raise ValueError("detector input contains duplicate stable IDs")
        observed.add(segment_id)
    missing = expected_ids - observed
    extra = observed - expected_ids
    if missing or extra:
        raise ValueError(
            f"detector input identity mismatch: missing={len(missing)} extra={len(extra)}"
        )
    serialized = json.dumps(model, ensure_ascii=False, sort_keys=True)
    leaked_names = [name for name in WALL_LAYERS if name in serialized]
    if leaked_names:
        raise ValueError("detector input serialized payload contains owner label-layer names")
    observed_layers = {str(segment["layer"]) for segment in segments}
    expected_layers = set(expected_layer_by_id.values())
    if observed_layers != expected_layers:
        raise ValueError("detector input did not preserve the source-layer partition")
    return {
        "exact_seg_ir_v1": True,
        "stable_id_count": len(observed),
        "blank_layer_count": 0,
        "pseudonymous_layer_count": len(observed_layers),
        "source_layer_partition_preserved": True,
        "unknown_label_count": len(observed),
        "source_layer_fields": 0,
        "wall_layer_name_occurrences": 0,
    }


def build_population(
    *,
    native_graph: Path,
    source_dwg: Path,
    full_linear_oracle: Path,
    positive_oracle: Path,
    label_contract: Path,
    out_dir: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = out_dir / "detector_population_receipt.json"
    world_path = out_dir / "detector_worldir_probe.json"
    truth_path = out_dir / "detector_truth.json"
    model_path = out_dir / "detector_input.seg.json"

    existing = [path for path in (receipt_path, world_path, truth_path, model_path) if path.exists()]
    if existing:
        return {
            "schema": "ariadne.e2.l0.detector_population_receipt.v1",
            "status": BLOCKED,
            "reason_code": "OUTPUT_ALREADY_EXISTS",
            "reason": "Refusing to overwrite evidence: " + ", ".join(map(str, existing)),
        }

    def finish(status: str, reason_code: str, reason: str, **extra: Any) -> dict[str, Any]:
        receipt = {
            "schema": "ariadne.e2.l0.detector_population_receipt.v1",
            "status": status,
            "reason_code": reason_code,
            "reason": reason,
            **extra,
        }
        _write_json(receipt_path, receipt)
        receipt["receipt"] = str(receipt_path)
        return receipt

    required = (source_dwg, native_graph, full_linear_oracle, positive_oracle, label_contract)
    missing = [str(path) for path in required if not path.is_file()]
    if missing or source_dwg.suffix.lower() != ".dwg":
        return finish(BLOCKED, "INPUT_MISSING", "Required input is missing: " + ", ".join(missing))

    source_before = _sha256(source_dwg)
    try:
        native = _read_json(native_graph)
        if (
            native.get("schema") != "ariadne.dwg_graph_ir.v1"
            or str((native.get("source") or {}).get("sha256") or "").lower() != source_before
        ):
            raise ValueError("full native graph does not identify the source DWG bytes")
        adapted = graph_adapter.adapt(native)
        world = worldir_oracle.expand_world_ir(adapted)
        conservation = world.get("conservation_ledger")
        if (
            adapted.get("status") not in {PASS, "PARTIAL"}
            or world.get("status") != PASS
            or world.get("drawing_id") != source_before
            or not isinstance(conservation, Mapping)
            or conservation.get("conservation_ok") is not True
        ):
            raise ValueError("full WorldIR projection did not conserve source segment instances")

        raw_segments = [segment for segment in world.get("segments", []) if isinstance(segment, Mapping)]
        world_linear_segments = [
            segment for segment in raw_segments if segment.get("kind") in LINEAR_KINDS
        ]
        arc_segments = [segment for segment in raw_segments if segment.get("kind") == "arc-chord"]
        world_linear_ids = [_stable_id(segment) for segment in world_linear_segments]
        if any(not value for value in world_linear_ids) or len(world_linear_ids) != len(set(world_linear_ids)):
            raise ValueError("WorldIR linear candidates have missing or duplicate stable identities")
        world_linear_id_set = set(world_linear_ids)

        native_ids, native_by_layer, full_oracle_record = _oracle_ids(
            full_linear_oracle,
            source_before,
            source_dwg=source_dwg,
            required_geometry_scope="linear_segments_v1",
        )
        consensus_ids = world_linear_id_set & native_ids
        native_only_ids = native_ids - world_linear_id_set
        worldir_only_ids = world_linear_id_set - native_ids
        if not consensus_ids:
            raise ValueError("native and WorldIR have no common visible linear segment identities")

        positive_ids, positive_by_layer, positive_oracle_record = _oracle_ids(
            positive_oracle,
            source_before,
            source_dwg=source_dwg,
            required_geometry_scope=None,
        )
        expected_positive_layers = set(WALL_LAYERS)
        if set(positive_by_layer) != expected_positive_layers:
            raise ValueError("positive oracle must contain exactly the two owner-supplied wall layers")
        world_positive_ids = {
            _stable_id(segment)
            for segment in world_linear_segments
            if segment.get("source_layer") in expected_positive_layers
        }
        if positive_ids != world_positive_ids or not positive_ids <= consensus_ids:
            raise ValueError(
                "positive wall anchor must exactly match the owner wall layers and lie in the dual-oracle consensus"
            )

        linear_segments = [
            segment
            for segment in world_linear_segments
            if _stable_id(segment) in consensus_ids
        ]

        truth_records = sorted((_truth_record(segment) for segment in linear_segments), key=lambda row: row["placed_uid"])
        source_layers = {
            str(segment.get("source_layer") or "") for segment in linear_segments
        }
        layer_pseudonyms = _drawing_local_layer_pseudonyms(
            source_layers, source_before
        )
        expected_layer_by_id = {
            _stable_id(segment): layer_pseudonyms[str(segment.get("source_layer") or "")]
            for segment in linear_segments
        }
        model_segments = sorted(
            (_model_segment(segment, layer_pseudonyms) for segment in linear_segments),
            key=lambda row: row["handle"],
        )
        model = {
            "ir": "seg.v1",
            "drawing_id": source_before,
            "units": "mm",
            "scale_mm_per_unit": 1.0,
            "segments": model_segments,
        }
        leakage = _validate_model_input(model, consensus_ids, expected_layer_by_id)
        anchor_counts = Counter(row["layer_anchor"] for row in truth_records)
        kind_counts = Counter(str(segment.get("kind")) for segment in raw_segments)
        layer_counts = Counter(str(segment.get("source_layer") or "") for segment in linear_segments)

        truth = {
            "schema": "ariadne.e2.l0.detector_label_anchors.v1",
            "drawing_id": source_before,
            "candidate_scope": "xclip_visible_linear_segments_v1",
            "label_authority": "owner_layer_positive_only",
            "object_truth_completeness": "UNKNOWN",
            "positive_layers": list(WALL_LAYERS),
            "label_contract": {
                "path": str(label_contract.resolve()),
                "sha256": _sha256(label_contract),
            },
            "records": truth_records,
        }
        _write_json(world_path, world)
        _write_json(truth_path, truth)
        _write_json(model_path, model)
        source_after = _sha256(source_dwg)
        if source_after != source_before:
            raise ValueError("source DWG changed during read-only population construction")

        artifacts = {
            "world_ir": {"path": str(world_path), "sha256": _sha256(world_path)},
            "truth": {"path": str(truth_path), "sha256": _sha256(truth_path)},
            "model_input": {"path": str(model_path), "sha256": _sha256(model_path)},
        }
        has_dispute = bool(native_only_ids or worldir_only_ids)
        terminal_status = PASS_WITH_DEFERRAL
        reason_code = "LABEL_COMPLETENESS_UNKNOWN"
        reason = (
            "The candidate population is instrument-qualified, but W1/W2 provide only a positive "
            "layer anchor. Object purity, negative labels and wall completeness remain unknown."
        )
        native_only_by_layer = {
            layer: len(ids & native_only_ids)
            for layer, ids in sorted(native_by_layer.items())
            if ids & native_only_ids
        }
        worldir_only_by_layer = Counter(
            str(segment.get("source_layer") or "")
            for segment in world_linear_segments
            if _stable_id(segment) in worldir_only_ids
        )
        return finish(
            terminal_status,
            reason_code,
            reason,
            source={
                "path": str(source_dwg.resolve()),
                "sha256_before": source_before,
                "sha256_after": source_after,
                "unchanged": True,
            },
            native_graph={"path": str(native_graph.resolve()), "sha256": _sha256(native_graph)},
            implementation={
                "population_builder": _file_record(Path(__file__)),
                "native_graph_adapter": _file_record(Path(graph_adapter.__file__)),
                "worldir_oracle": _file_record(Path(worldir_oracle.__file__)),
            },
            full_linear_oracle=full_oracle_record,
            positive_oracle=positive_oracle_record,
            adapter_status=adapted.get("status"),
            world_status=world.get("status"),
            world_conservation_ok=True,
            world_visible_all_kinds=len(raw_segments),
            world_kind_counts=dict(sorted(kind_counts.items())),
            worldir_visible_linear_candidates=len(world_linear_id_set),
            native_visible_linear_candidates=len(native_ids),
            qualified_linear_candidates=len(consensus_ids),
            known_wall_layer_members=anchor_counts["POSITIVE_UNLABELED"],
            unlabeled_layer_members=anchor_counts["UNKNOWN"],
            object_positive_gold_segments=0,
            object_negative_gold_segments=0,
            object_unknown_segments=len(truth_records),
            observation_status=PASS_WITH_DEFERRAL if has_dispute else PASS,
            observation_reason_code=(
                "DUAL_ORACLE_CONSENSUS_WITH_DISPUTED_SEGMENTS"
                if has_dispute
                else "DETECTOR_POPULATION_QUALIFIED"
            ),
            excluded_arc_chords=len(arc_segments),
            disputed_segments={
                "native_only_count": len(native_only_ids),
                "worldir_only_count": len(worldir_only_ids),
                "union_count": len(native_only_ids | worldir_only_ids),
                "native_only_by_layer": native_only_by_layer,
                "worldir_only_by_layer": dict(sorted(worldir_only_by_layer.items())),
                "native_only_id_sample": sorted(native_only_ids)[:20],
                "worldir_only_id_sample": sorted(worldir_only_ids)[:20],
                "policy": "quarantined_before_model_inference",
            },
            linear_candidates_by_layer=dict(sorted(layer_counts.items())),
            native_layers_with_visible_linear_segments=sum(bool(values) for values in native_by_layer.values()),
            layer_leakage_guard=leakage,
            artifacts=artifacts,
        )
    except TargetPopulationContractError as exc:  # fail closed at the authority boundary
        return finish(
            BLOCKED,
            exc.reason_code,
            str(exc),
            source_sha256_before=source_before,
            native_graph_sha256=_sha256(native_graph),
            full_linear_oracle_sha256=_sha256(full_linear_oracle),
            positive_oracle_sha256=_sha256(positive_oracle),
            label_contract_sha256=_sha256(label_contract),
        )
    except Exception as exc:  # fail closed at the measurement boundary
        return finish(
            BLOCKED,
            "POPULATION_QUALIFICATION_FAILED",
            f"{type(exc).__name__}: {exc}",
            source_sha256_before=source_before,
            native_graph_sha256=_sha256(native_graph),
            full_linear_oracle_sha256=_sha256(full_linear_oracle),
            positive_oracle_sha256=_sha256(positive_oracle),
            label_contract_sha256=_sha256(label_contract),
        )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-graph", type=Path, required=True)
    parser.add_argument("--source-dwg", type=Path, required=True)
    parser.add_argument("--full-linear-oracle", type=Path, required=True)
    parser.add_argument("--positive-oracle", type=Path, required=True)
    parser.add_argument("--label-contract", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = build_population(
        native_graph=args.native_graph,
        source_dwg=args.source_dwg,
        full_linear_oracle=args.full_linear_oracle,
        positive_oracle=args.positive_oracle,
        label_contract=args.label_contract,
        out_dir=args.out_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {PASS, PASS_WITH_DEFERRAL} else 2


if __name__ == "__main__":
    raise SystemExit(main())
