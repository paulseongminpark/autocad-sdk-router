from __future__ import annotations

import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.e2.company_pair_intervention import (  # noqa: E402
    PASS,
    derive_main_only,
    measure_interventions,
    scorer_parity,
)
from tools.e2 import company_pair_intervention as pair_runner  # noqa: E402
from tools.e2 import w1_real_defs  # noqa: E402
from tools.e2.qualification import engine  # noqa: E402


def _segment(handle: str, lineage: list[str], y: float) -> dict:
    return {
        "placed_uid": handle,
        "source_def_handle": "ROOT",
        "source_entity_handle": handle,
        "kind": "line",
        "p0_world": [0.0, y],
        "p1_world": [1000.0, y],
        "lineage_path": [{"insert_entity_handle": item} for item in lineage],
    }


def test_main_only_excludes_every_active_xclip_ancestor():
    adapter = {
        "definitions": {
            "ROOT": {
                "entities": [
                    {"handle": "CLIP", "kind": "INSERT", "clip": {"boundary_owner": [[0, 0], [1, 1]]}},
                    {"handle": "PLAIN", "kind": "INSERT"},
                    {"handle": "R", "kind": "LINE", "layer": "WALL"},
                    {"handle": "P", "kind": "LINE", "layer": "A-WALL"},
                ]
            }
        }
    }
    world = {
        "drawing_id": "fixture",
        "segments": [
            _segment("root", [], 0.0),
            _segment("plain", ["PLAIN"], 100.0),
            _segment("clip", ["CLIP"], 200.0),
            _segment("nested_clip", ["CLIP", "PLAIN"], 300.0),
        ],
        "conservation_ledger": {
            "expected_segment_instances": 4,
            "clipped_away_segment_instances": 0,
            "conservation_ok": True,
        },
    }

    seg_ir, summary = derive_main_only(adapter, world)

    assert summary["status"] == PASS
    assert summary["main_only_segments"] == 2
    assert summary["xclip_descendant_visible_segments"] == 2
    assert summary["main_only_xclip_lineage_violations"] == 0
    assert {row["handle"] for row in seg_ir["segments"]} == {"root", "plain"}


def test_exact_vectorized_scorer_matches_reference_and_invariant_controls():
    segments = []
    for index, y in enumerate((0.0, 200.0, 1000.0, 1200.0)):
        segments.append(
            {
                "sid": f"s{index}",
                "handle": f"h{index}",
                "pts": [[0.0, y], [1000.0, y]],
                "layer": "WALL",
                "kind": "line",
                "label": "unknown",
                "source": "fixture",
            }
        )
    seg_ir = {
        "ir": "seg.v1",
        "drawing_id": "fixture",
        "units": "mm",
        "scale_mm_per_unit": 1.0,
        "segments": segments,
    }

    parity = scorer_parity(seg_ir, sample_size=4)
    _, interventions = measure_interventions(seg_ir)
    by_name = {row["intervention"]: row for row in interventions["interventions"]}

    assert parity["status"] == PASS
    assert parity["max_score_or_channel_deviation"] <= 1e-6
    assert by_name["translate_large_offset"]["result"] == "INVARIANCE_PASS"
    assert by_name["scale_coordinates_x1000_consistent"]["result"] == "INVARIANCE_PASS"


def test_endpoint_contact_cannot_become_translation_dependent_thickness():
    # Coordinates are the real counterexample found in the A30 implementation
    # drawing.  The second segment begins exactly at the first segment's end.
    # Their longitudinal overlap is zero in every coordinate frame.
    segments = [
        {
            "sid": "s0",
            "handle": "target",
            "pts": [
                [19475.457002999072, 16233.512800710334],
                [19697.500000000582, 15848.923048455414],
            ],
            "layer": "4L",
            "kind": "poly-edge",
        },
        {
            "sid": "s1",
            "handle": "contact",
            "pts": [
                [19697.500000000582, 15848.923048455414],
                [19757.500000000582, 15745.00000000128],
            ],
            "layer": "4L",
            "kind": "poly-edge",
        },
    ]
    seg_ir = {
        "ir": "seg.v1",
        "drawing_id": "contact-regression",
        "units": "mm",
        "scale_mm_per_unit": 1.0,
        "segments": segments,
    }
    reference = w1_real_defs.evidence_grid.score(seg_ir)
    baseline = w1_real_defs.fast_score(seg_ir)
    translated_ir, translated_params = engine._transform_seg_ir(seg_ir, "translate_large_offset")
    translated = w1_real_defs.fast_score(translated_ir, params=translated_params)
    scaled_ir, scaled_params = engine._transform_seg_ir(seg_ir, "scale_coordinates_x1000_consistent")
    scaled = w1_real_defs.fast_score(scaled_ir, params=scaled_params)

    assert reference["per_handle"]["target"]["evidence"]["thickness"] == 0.0
    assert baseline["per_handle"]["target"]["score"] == reference["per_handle"]["target"]["score"]
    assert baseline["per_handle"]["target"]["evidence"] == reference["per_handle"]["target"]["evidence"]
    assert translated["per_handle"]["target"] == baseline["per_handle"]["target"]
    assert scaled["per_handle"]["target"] == baseline["per_handle"]["target"]


def test_parallel_pair_on_400mm_boundary_survives_rigid_rotation():
    seg_ir = {
        "ir": "seg.v1",
        "drawing_id": "band-boundary-regression",
        "units": "mm",
        "scale_mm_per_unit": 1.0,
        "segments": [
            {
                "sid": "s0",
                "handle": "a",
                "pts": [[30400.0, 9159.999999995343], [32800.0, 9159.999999995343]],
                "layer": "FORM",
                "kind": "line",
            },
            {
                "sid": "s1",
                "handle": "b",
                "pts": [[30400.0, 8759.999999995343], [32800.0, 8759.999999995343]],
                "layer": "FORM",
                "kind": "line",
            },
        ],
    }
    baseline = w1_real_defs.fast_score(seg_ir)
    rotated_ir, rotated_params = engine._transform_seg_ir(seg_ir, "rotate_37_degrees")
    rotated = w1_real_defs.fast_score(rotated_ir, params=rotated_params)

    assert baseline["per_handle"]["a"]["evidence"]["parallel"] == 1.0
    assert rotated["per_handle"]["a"] == baseline["per_handle"]["a"]
    assert rotated["per_handle"]["b"] == baseline["per_handle"]["b"]


def test_subnanometer_worldir_noise_at_400mm_survives_translation():
    seg_ir = {
        "ir": "seg.v1",
        "drawing_id": "translated-band-boundary-regression",
        "units": "mm",
        "scale_mm_per_unit": 1.0,
        "segments": [
            {
                "sid": "s0",
                "handle": "a",
                "pts": [
                    [148247.50000000096, 20107.499999999807],
                    [148247.50000000096, 21197.499999999785],
                ],
                "layer": "CEN",
                "kind": "line",
            },
            {
                "sid": "s1",
                "handle": "b",
                "pts": [
                    [147847.50000000058, 20107.4999999998],
                    [147847.50000000058, 21197.499999999778],
                ],
                "layer": "CEN",
                "kind": "line",
            },
        ],
    }
    baseline = w1_real_defs.fast_score(seg_ir)
    translated_ir, translated_params = engine._transform_seg_ir(seg_ir, "translate_large_offset")
    translated = w1_real_defs.fast_score(translated_ir, params=translated_params)

    assert baseline["per_handle"]["a"]["evidence"]["parallel"] == 1.0
    assert translated["per_handle"]["a"] == baseline["per_handle"]["a"]
    assert translated["per_handle"]["b"] == baseline["per_handle"]["b"]


def test_public_pair_runner_stops_before_unsealed_experiment_work(tmp_path: Path):
    run_dir = tmp_path / "run"

    result = pair_runner.run(
        {"experiment_id": "blocked-pair"},
        run_dir,
        tmp_path / "missing-prereg.md",
    )

    assert result["status"] == "BLOCKED"
    assert result["reason_code"] == "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"
    assert result["executed"] is False
    assert result["terminal_authorized"] is False
    assert not run_dir.exists()


def test_public_pair_cli_returns_the_same_terminal_refusal(tmp_path: Path, capsys):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"experiment_id": "blocked-pair-cli"}), encoding="utf-8")

    exit_code = pair_runner.main(
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
