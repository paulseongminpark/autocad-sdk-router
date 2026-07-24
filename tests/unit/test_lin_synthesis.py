#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lin_synthesis as ls  # noqa: E402


def test_simple_linetype_writes_exact_lin_content(tmp_path):
    out_path = tmp_path / "batch.lin"
    result = ls.synthesize_lin_file(
        [
            {
                "name": "DASHDOT",
                "description": "Dash dot example",
                "pattern_length": 1.0,
                "is_scaled_to_fit": False,
                "dashes": [
                    {"length": 0.5},
                    {"length": -0.25},
                    {"length": 0.0},
                    {"length": -0.25},
                ],
            }
        ],
        out_path,
    )

    assert result == {"written": ["DASHDOT"], "deferred": []}
    assert out_path.read_text(encoding="utf-8") == (
        "*DASHDOT,Dash dot example\n"
        "A,0.5,-0.25,0,-0.25\n"
    )


def test_complex_segments_are_deferred_honestly(tmp_path):
    out_path = tmp_path / "batch.lin"
    result = ls.synthesize_lin_file(
        [
            {
                "name": "GAS_LINE",
                "description": "Gas line text replay",
                "pattern_length": 1.0,
                "is_scaled_to_fit": False,
                "dashes": [
                    {"length": 0.5},
                    {"length": -0.25, "text": {"value": "GAS"}},
                ],
            }
        ],
        out_path,
    )

    assert result == {
        "written": [],
        "deferred": [
            {
                "name": "GAS_LINE",
                "reason": "text segments are not supported in lin_synthesis v1",
            }
        ],
    }
    assert out_path.read_text(encoding="utf-8") == ""


def test_small_numbers_clamp_and_never_use_scientific_notation(tmp_path):
    out_path = tmp_path / "batch.lin"
    result = ls.synthesize_lin_file(
        [
            {
                "name": "CLAMP",
                "description": "Clamp float noise",
                "pattern_length": 1.0,
                "is_scaled_to_fit": False,
                "dashes": [
                    {"length": 8.526512829121202e-14},
                    {"length": 1e-8},
                    {"length": -0.125},
                ],
            }
        ],
        out_path,
    )

    text = out_path.read_text(encoding="utf-8")
    assert result == {"written": ["CLAMP"], "deferred": []}
    assert "e-" not in text and "E-" not in text and "e+" not in text and "E+" not in text
    assert text == (
        "*CLAMP,Clamp float noise\n"
        "A,0,0.00000001,-0.125\n"
    )
