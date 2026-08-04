from __future__ import annotations

import copy
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.e2.company_gnn_canonical_frame import (  # noqa: E402
    canonicalize_physical_frame,
    compare_canonical_geometry,
)
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
