from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.e2.company_gnn_intervention import (  # noqa: E402
    BLOCKED,
    PASS,
    compare_graphs,
    compare_runtime_replay,
    paired_unlabeled,
    transform_consistent_scale,
    transform_strip_layers,
    transform_translate,
    validate_seg_ir,
)
from tools.e2 import company_gnn_intervention as gnn_runner  # noqa: E402


def _seg_ir() -> dict:
    return {
        "ir": "seg.v1",
        "drawing_id": "fixture",
        "units": "mm",
        "scale_mm_per_unit": 1.0,
        "segments": [
            {
                "handle": "a",
                "pts": [[0.0, 0.0], [1000.0, 0.0]],
                "layer": "A-WALL",
                "kind": "line",
                "sagitta": 0.0,
            },
            {
                "handle": "b",
                "pts": [[0.0, 200.0], [1000.0, 200.0]],
                "layer": "A-WALL",
                "kind": "line",
            },
        ],
    }


def test_seg_ir_contract_rejects_duplicate_handles_and_bad_scale():
    seg_ir = _seg_ir()
    seg_ir["scale_mm_per_unit"] = 12.0
    seg_ir["segments"][1]["handle"] = "a"

    result = validate_seg_ir(seg_ir)

    assert result["status"] == BLOCKED
    assert any("scale_mm_per_unit" in error for error in result["errors"])
    assert any("duplicate handles" in error for error in result["errors"])


def test_semantic_identity_transforms_do_not_mutate_input():
    original = _seg_ir()
    frozen = copy.deepcopy(original)

    translated, translated_map = transform_translate(original)
    scaled, scaled_map = transform_consistent_scale(original)
    stripped, stripped_map = transform_strip_layers(original)

    assert original == frozen
    assert translated["segments"][0]["pts"][0] == [1_000_000.0, -2_000_000.0]
    assert scaled["segments"][0]["pts"][1] == [1_000_000.0, 0.0]
    assert scaled["scale_mm_per_unit"] == 0.001
    assert stripped["segments"][0]["layer"] == ""
    assert translated_map == scaled_map == stripped_map == {"a": "a", "b": "b"}


def test_paired_unlabeled_aggregates_split_children_to_original_handle():
    baseline = {
        "handles": ["a", "b"],
        "gnn": np.asarray([0.4, 0.8], dtype=np.float64),
    }
    transformed = {
        "handles": ["a::s0", "a::s1", "b::s0", "b::s1"],
        "gnn": np.asarray([0.2, 0.6, 0.7, 0.9], dtype=np.float64),
    }
    mapping = {"a::s0": "a", "a::s1": "a", "b::s0": "b", "b::s1": "b"}

    result = paired_unlabeled(baseline, transformed, mapping)

    assert result["matched_original_handles"] == 2
    assert result["missing_baseline_handle_count"] == 0
    assert result["max_abs_delta"] < 1e-12
    assert all(row["transformed_child_count"] == 2 for row in result["per_handle"])


def test_runtime_replay_ignores_only_time_fields_and_detects_science_drift():
    baseline = {
        "created_at": "before",
        "wall_seconds": 10.0,
        "corpora": {"fpc": {"mean": 0.125, "processed": 6}},
    }
    replay = {
        "created_at": "after",
        "wall_seconds": 99.0,
        "corpora": {"fpc": {"mean": 0.125, "processed": 6}},
    }
    same = compare_runtime_replay(baseline, replay)
    replay["corpora"]["fpc"]["mean"] = 0.126
    drifted = compare_runtime_replay(baseline, replay)

    assert same["status"] == PASS
    assert same["difference_count"] == 0
    assert drifted["status"] == BLOCKED
    assert drifted["difference_count"] == 1


def test_unconsumed_edge_attributes_are_a_sidecar_warning_not_gnn_input_drift():
    def graph(attribute: float) -> dict:
        return {
            "prepared": {"records": [{"handle": "a"}, {"handle": "b"}]},
            "features": np.asarray([[1.0] * 17, [2.0] * 17], dtype=np.float32),
            "edge_src": np.asarray([0], dtype=np.int64),
            "edge_dst": np.asarray([1], dtype=np.int64),
            "edge_type": np.asarray([0], dtype=np.int16),
            "edge_attr": np.asarray([[attribute] * 8], dtype=np.float32),
            "stats": {"graph_hash": "same"},
        }

    result = compare_graphs(graph(0.0), graph(0.125), ("parallel_band",), 1e-7)

    assert result["status"] == PASS
    assert result["edge_attribute_sidecar_status"] == "SIDECAR_ORDER_SENSITIVITY"
    assert result["max_edge_attribute_delta"] == 0.125


def test_public_gnn_runner_stops_before_model_import(tmp_path: Path, monkeypatch):
    import_attempts: list[Path] = []

    def forbidden_import(path: Path, _: str):
        import_attempts.append(path)
        raise AssertionError("unsealed model import reached")

    monkeypatch.setattr(gnn_runner, "_import_module", forbidden_import)
    run_dir = tmp_path / "run"
    result = gnn_runner.run(
        {"experiment_id": "blocked-gnn", "c1_path": str(tmp_path / "c1.py")},
        run_dir,
        tmp_path / "missing-prereg.md",
    )

    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"
    assert result["executed"] is False
    assert import_attempts == []
    assert not run_dir.exists()


def test_public_gnn_cli_returns_the_same_terminal_refusal(tmp_path: Path, capsys):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"experiment_id": "blocked-gnn-cli"}), encoding="utf-8")

    exit_code = gnn_runner.main(
        [
            "--spec",
            str(spec),
            "--run-dir",
            str(tmp_path / "run"),
            "--prereg",
            str(tmp_path / "missing-prereg.md"),
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert output["status"] == "BLOCKED"
    assert output["reason_code"] == "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"
    assert output["executed"] is False
