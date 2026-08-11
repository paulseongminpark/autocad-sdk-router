from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
E2 = REPO / "tools" / "e2"
if str(E2) not in sys.path:
    sys.path.insert(0, str(E2))

import build_display_model_input as builder  # noqa: E402


def _native_graph(drawing_id: str) -> dict:
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "coverage_level": "native_full",
        "source": {"sha256": drawing_id, "dwg_name": "source.dwg"},
        "symbol_tables": {
            "block_table_records": [
                {
                    "handle": "1F",
                    "name": "*Model_Space",
                    "is_layout": True,
                    "origin": [0, 0, 0],
                },
                {
                    "handle": "A",
                    "name": "A",
                    "is_layout": False,
                    "origin": [0, 0, 0],
                },
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
                    "boundary_block": [[0, -1], [5, -1], [5, 1], [0, 1]],
                },
            }
        ],
        "block_definitions": [
            {
                "handle": "A",
                "name": "A",
                "origin": [0, 0, 0],
                "entity_count": 2,
                "def_entities": [
                    {
                        "handle": "VISIBLE",
                        "dxf_name": "LINE",
                        "owner_handle": "A",
                        "space": "block",
                        "layer": "W1",
                        "geometry": {
                            "kind": "line",
                            "start": [1, 0, 0],
                            "end": [4, 0, 0],
                        },
                    },
                    {
                        "handle": "CLIPPED",
                        "dxf_name": "LINE",
                        "owner_handle": "A",
                        "space": "block",
                        "layer": "W1",
                        "geometry": {
                            "kind": "line",
                            "start": [6, 0, 0],
                            "end": [8, 0, 0],
                        },
                    },
                ],
            }
        ],
    }


def test_build_population_retains_xclip_and_writes_exact_visible_segments(tmp_path: Path):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg")
    drawing_id = hashlib.sha256(source.read_bytes()).hexdigest()
    graph = tmp_path / "scoped_native_graph.json"
    graph.write_text(json.dumps(_native_graph(drawing_id)), encoding="utf-8")

    result = builder.build_population(
        scoped_native_graph=graph,
        source_dwg=source,
        target_layers=["W1"],
        out_dir=tmp_path / "out",
    )

    assert result["status"] == "PASS"
    assert result["target_counts"] == {"W1": 1}
    assert result["expected_source_segments"] == 2
    assert result["visible_source_segments"] == 1
    assert result["clipped_away_source_segments"] == 1
    model = json.loads(Path(result["model_input_ir"]).read_text(encoding="utf-8"))
    assert model["schema"] == "ariadne.e2.model_input_population.v1"
    assert model["drawing_id"] == drawing_id
    assert model["xclip_applied"] is True
    assert model["population_exact"] is True
    assert len(model["segments"]) == 1
    assert model["segments"][0]["source_entity_handle"] == "VISIBLE"
    assert source.read_bytes() == b"immutable-dwg"


def test_build_population_blocks_source_identity_mismatch_without_outputs(tmp_path: Path):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"one-drawing")
    graph = tmp_path / "scoped_native_graph.json"
    graph.write_text(json.dumps(_native_graph("0" * 64)), encoding="utf-8")

    result = builder.build_population(
        scoped_native_graph=graph,
        source_dwg=source,
        target_layers=["W1"],
        out_dir=tmp_path / "out",
    )

    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "SOURCE_IDENTITY_MISMATCH"
    assert not (tmp_path / "out" / "display_worldir_probe.json").exists()
    assert not (tmp_path / "out" / "display_model_input.json").exists()
    assert (tmp_path / "out" / "display_model_input_receipt.json").is_file()
