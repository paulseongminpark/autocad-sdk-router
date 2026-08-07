from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
E2 = REPO / "tools" / "e2"
if str(E2) not in sys.path:
    sys.path.insert(0, str(E2))

import build_l0_detector_population as builder  # noqa: E402
from instruments import dwg_graph_to_worldir, worldir_oracle  # noqa: E402


def _native_graph(drawing_id: str) -> dict:
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "coverage_level": "native_full",
        "source": {"sha256": drawing_id, "dwg_name": "source.dwg"},
        "symbol_tables": {
            "block_table_records": [
                {"handle": "1F", "name": "*Model_Space", "is_layout": True, "origin": [0, 0, 0]},
                {"handle": "A", "name": "A", "is_layout": False, "origin": [0, 0, 0]},
            ]
        },
        "entities": [
            {
                "handle": "I1",
                "dxf_name": "INSERT",
                "owner_handle": "1F",
                "space": "model",
                "layer": "0",
                "block_record_handle": "A",
                "geometry": {
                    "kind": "block_reference",
                    "position": [0, 0, 0],
                    "scale": [1, 1, 1],
                    "rotation": 0,
                },
                "xclip": {
                    "enabled": True,
                    "inverted": False,
                    "boundary_block": [[0, -1], [5, -1], [5, 2], [0, 2]],
                },
            }
        ],
        "block_definitions": [
            {
                "handle": "A",
                "name": "A",
                "origin": [0, 0, 0],
                "entity_count": 4,
                "def_entities": [
                    {
                        "handle": "WALL_VISIBLE",
                        "dxf_name": "LINE",
                        "owner_handle": "A",
                        "space": "block",
                        "layer": builder.WALL_LAYERS[0],
                        "geometry": {"kind": "line", "start": [1, 0, 0], "end": [4, 0, 0]},
                    },
                    {
                        "handle": "WALL_CLIPPED",
                        "dxf_name": "LINE",
                        "owner_handle": "A",
                        "space": "block",
                        "layer": builder.WALL_LAYERS[0],
                        "geometry": {"kind": "line", "start": [6, 0, 0], "end": [8, 0, 0]},
                    },
                    {
                        "handle": "OTHER_VISIBLE",
                        "dxf_name": "LINE",
                        "owner_handle": "A",
                        "space": "block",
                        "layer": "N1",
                        "geometry": {"kind": "line", "start": [1, 1, 0], "end": [4, 1, 0]},
                    },
                    {
                        "handle": "ARC_VISIBLE",
                        "dxf_name": "ARC",
                        "owner_handle": "A",
                        "space": "block",
                        "layer": "N1",
                        "geometry": {
                            "kind": "arc",
                            "center": [2, 1, 0],
                            "radius": 0.5,
                            "start_angle": 0.0,
                            "end_angle": math.pi / 2,
                        },
                    },
                ],
            }
        ],
    }


def _write_oracle(
    path: Path,
    drawing_id: str,
    by_layer: dict[str, set[str]],
    *,
    geometry_scope: str | None,
) -> None:
    evidence = []
    for name, payload in (("native.json", b"native"), ("binding.json", b"binding")):
        evidence_path = path.parent / f"{path.stem}_{name}"
        evidence_path.write_bytes(payload)
        evidence.append(
            {
                "path": str(evidence_path),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    oracle = {
        "schema": "ariadne.e2.target_population_oracle.v1",
        "oracle": "autocad.native_display_membership.v1",
        "status": "PASS",
        "drawing_id": drawing_id,
        "evidence": evidence,
        "targets": [
            {
                "target_id": f"target-{index:03d}",
                "layer": layer,
                "native_source_entity_templates": len(ids),
                "native_visible_source_segments": len(ids),
                "native_visible_segment_ids": sorted(ids),
            }
            for index, (layer, ids) in enumerate(sorted(by_layer.items()), start=1)
        ],
    }
    if geometry_scope is not None:
        oracle["geometry_scope"] = geometry_scope
    path.write_text(json.dumps(oracle), encoding="utf-8")


def _world_and_ids(graph: dict) -> tuple[dict, dict[str, set[str]]]:
    world = worldir_oracle.expand_world_ir(dwg_graph_to_worldir.adapt(graph))
    by_layer: dict[str, set[str]] = {}
    for segment in world["segments"]:
        if segment["kind"] not in builder.LINEAR_KINDS:
            continue
        by_layer.setdefault(segment["source_layer"], set()).add(segment["placed_uid"])
    return world, by_layer


def test_build_population_separates_truth_and_cue_free_model_input(tmp_path: Path):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg")
    drawing_id = hashlib.sha256(source.read_bytes()).hexdigest()
    graph_value = _native_graph(drawing_id)
    graph = tmp_path / "full_native_graph.json"
    graph.write_text(json.dumps(graph_value), encoding="utf-8")
    world, by_layer = _world_and_ids(graph_value)

    full_oracle = tmp_path / "full_oracle.json"
    _write_oracle(
        full_oracle,
        drawing_id,
        by_layer,
        geometry_scope="linear_segments_v1",
    )
    positive_oracle = tmp_path / "positive_oracle.json"
    _write_oracle(
        positive_oracle,
        drawing_id,
        {layer: by_layer.get(layer, set()) for layer in builder.WALL_LAYERS},
        geometry_scope=None,
    )
    contract = tmp_path / "SPEC.md"
    contract.write_text("W1/W2 are wall; every other segment is non-wall.\n", encoding="utf-8")

    result = builder.build_population(
        native_graph=graph,
        source_dwg=source,
        full_linear_oracle=full_oracle,
        positive_oracle=positive_oracle,
        label_contract=contract,
        out_dir=tmp_path / "out",
    )

    assert result["status"] == "PASS"
    assert result["qualified_linear_candidates"] == 2
    assert result["positive_segments"] == 1
    assert result["negative_segments"] == 1
    assert result["excluded_arc_chords"] == sum(
        segment["kind"] == "arc-chord" for segment in world["segments"]
    )
    model = json.loads((tmp_path / "out" / "detector_input.seg.json").read_text(encoding="utf-8"))
    assert set(model) == {"ir", "drawing_id", "units", "scale_mm_per_unit", "segments"}
    assert all(set(segment) == builder.SEGMENT_KEYS for segment in model["segments"])
    assert all(segment["layer"] == "" and segment["label"] == "unknown" for segment in model["segments"])
    assert builder.WALL_LAYERS[0] not in json.dumps(model, ensure_ascii=False)
    truth = json.loads((tmp_path / "out" / "detector_truth.json").read_text(encoding="utf-8"))
    assert {record["label"] for record in truth["records"]} == {"wall", "non_wall"}
    assert {record["placed_uid"] for record in truth["records"]} == {
        segment["handle"] for segment in model["segments"]
    }
    assert source.read_bytes() == b"immutable-dwg"


def test_build_population_quarantines_full_oracle_identity_drift(tmp_path: Path):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg")
    drawing_id = hashlib.sha256(source.read_bytes()).hexdigest()
    graph_value = _native_graph(drawing_id)
    graph = tmp_path / "full_native_graph.json"
    graph.write_text(json.dumps(graph_value), encoding="utf-8")
    _, by_layer = _world_and_ids(graph_value)

    full_oracle = tmp_path / "full_oracle.json"
    bad = {layer: set(ids) for layer, ids in by_layer.items()}
    bad.setdefault("N1", set()).add("f" * 64)
    _write_oracle(full_oracle, drawing_id, bad, geometry_scope="linear_segments_v1")
    positive_oracle = tmp_path / "positive_oracle.json"
    _write_oracle(
        positive_oracle,
        drawing_id,
        {layer: by_layer.get(layer, set()) for layer in builder.WALL_LAYERS},
        geometry_scope=None,
    )
    contract = tmp_path / "SPEC.md"
    contract.write_text("complete binary owner labels", encoding="utf-8")

    result = builder.build_population(
        native_graph=graph,
        source_dwg=source,
        full_linear_oracle=full_oracle,
        positive_oracle=positive_oracle,
        label_contract=contract,
        out_dir=tmp_path / "out",
    )

    assert result["status"] == "PASS_WITH_DEFERRAL"
    assert result["reason_code"] == "DUAL_ORACLE_CONSENSUS_WITH_DISPUTED_SEGMENTS"
    assert result["qualified_linear_candidates"] == 2
    assert result["disputed_segments"]["native_only_count"] == 1
    assert result["disputed_segments"]["worldir_only_count"] == 0
    assert (tmp_path / "out" / "detector_input.seg.json").is_file()
    assert (tmp_path / "out" / "detector_truth.json").is_file()


def test_build_population_blocks_when_owner_wall_is_outside_consensus(tmp_path: Path):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg")
    drawing_id = hashlib.sha256(source.read_bytes()).hexdigest()
    graph_value = _native_graph(drawing_id)
    graph = tmp_path / "full_native_graph.json"
    graph.write_text(json.dumps(graph_value), encoding="utf-8")
    _, by_layer = _world_and_ids(graph_value)

    full_oracle = tmp_path / "full_oracle.json"
    missing_wall = {layer: set(ids) for layer, ids in by_layer.items()}
    missing_wall[builder.WALL_LAYERS[0]].clear()
    _write_oracle(
        full_oracle,
        drawing_id,
        missing_wall,
        geometry_scope="linear_segments_v1",
    )
    positive_oracle = tmp_path / "positive_oracle.json"
    _write_oracle(
        positive_oracle,
        drawing_id,
        {layer: by_layer.get(layer, set()) for layer in builder.WALL_LAYERS},
        geometry_scope=None,
    )
    contract = tmp_path / "SPEC.md"
    contract.write_text("complete binary owner labels", encoding="utf-8")

    result = builder.build_population(
        native_graph=graph,
        source_dwg=source,
        full_linear_oracle=full_oracle,
        positive_oracle=positive_oracle,
        label_contract=contract,
        out_dir=tmp_path / "out",
    )

    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "POPULATION_QUALIFICATION_FAILED"
    assert "dual-oracle consensus" in result["reason"]
    assert not (tmp_path / "out" / "detector_input.seg.json").exists()
