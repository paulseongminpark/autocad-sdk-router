from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.e2.company_gnn_canonical_frame import (  # noqa: E402
    canonicalize_physical_frame,
    compare_canonical_geometry,
)
from tools.e2 import company_gnn_canonical_frame as canonical_runner  # noqa: E402
from tools.e2.company_gnn_intervention import (  # noqa: E402
    PASS,
    transform_consistent_scale,
    transform_translate,
)


def _seg_ir() -> dict:
    return {
        "ir": "seg.v1",
        "drawing_id": "fixture",
        "units": "mm",
        "scale_mm_per_unit": 1.0,
        "segments": [
            {"handle": "a", "kind": "line", "layer": "W", "pts": [[100.25, 50.5], [1100.25, 50.5]]},
            {"handle": "b", "kind": "line", "layer": "W", "pts": [[100.25, 250.5], [1100.25, 250.5]]},
        ],
    }


def test_canonical_frame_is_idempotent_and_does_not_mutate_input():
    source = _seg_ir()
    frozen = copy.deepcopy(source)

    first, metadata = canonicalize_physical_frame(source)
    second, _ = canonicalize_physical_frame(first)

    assert source == frozen
    assert first == second
    assert first["scale_mm_per_unit"] == 1.0
    assert first["segments"][0]["pts"][0] == [-500.0, -100.0]
    assert metadata["maximum_rounding_error_mm"] == 0.0


def test_canonical_frame_collapses_translation_and_unit_reexpression():
    source = _seg_ir()
    translated_raw, _ = transform_translate(source)
    scaled_raw, _ = transform_consistent_scale(source)

    baseline, _ = canonicalize_physical_frame(source)
    translated, _ = canonicalize_physical_frame(translated_raw)
    scaled, _ = canonicalize_physical_frame(scaled_raw)

    assert compare_canonical_geometry(baseline, translated)["status"] == PASS
    assert compare_canonical_geometry(baseline, scaled)["status"] == PASS
    assert baseline == translated == scaled


def test_public_canonical_runner_stops_before_model_import(tmp_path: Path, monkeypatch):
    import_attempts: list[Path] = []

    def forbidden_import(path: Path, _: str):
        import_attempts.append(path)
        raise AssertionError("unsealed model import reached")

    monkeypatch.setattr(canonical_runner.base, "_import_module", forbidden_import)
    run_dir = tmp_path / "run"
    result = canonical_runner.run(
        {"experiment_id": "blocked-canonical", "c1_path": str(tmp_path / "c1.py")},
        run_dir,
        tmp_path / "missing-prereg.md",
    )

    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"
    assert result["executed"] is False
    assert import_attempts == []
    assert not run_dir.exists()


def test_public_canonical_cli_returns_the_same_terminal_refusal(tmp_path: Path, capsys):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"experiment_id": "blocked-canonical-cli"}), encoding="utf-8")

    exit_code = canonical_runner.main(
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
