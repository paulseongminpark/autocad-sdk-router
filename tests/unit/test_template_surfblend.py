"""Tests for the SURFBLEND command template registry entry."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_THIS = Path(__file__).resolve().parent
_REPO = _THIS.parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "tools") not in sys.path:
    sys.path.insert(0, str(_REPO / "tools"))

import command_template_engine as cte  # noqa: E402


TEMPLATE_ID = "define.surfblend"


def test_define_surfblend_template_is_loaded_from_dropin():
    templates = cte.load_templates()
    assert TEMPLATE_ID in templates


def test_define_surfblend_template_write_mode_forbidden_write_original():
    templates = cte.load_templates()
    allowed = templates[TEMPLATE_ID].get("write_mode", {}).get("allowed", [])
    assert "write_original" not in allowed


def test_define_surfblend_hostile_slot_value_rejected_by_injection_gate():
    templates = cte.load_templates()
    template = templates[TEMPLATE_ID]
    slot = template["slots"]["continuity"]
    with pytest.raises(cte.TemplateError) as exc:
        cte._validate_slot_value(slot, "continuity", "G1; QUIT")
    assert exc.value.code == "INJECTION_REJECTED"

