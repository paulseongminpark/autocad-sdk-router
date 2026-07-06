#!/usr/bin/env python3
"""DISPATCH/templated SURFEXTRUDE test coverage."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import command_template_engine as cte  # noqa: E402

TEMPLATE_ID = "define.surfextrude"


def test_dropin_template_is_loaded():
    templates = cte.load_templates()
    assert TEMPLATE_ID in templates


def test_surfextrude_write_mode_does_not_allow_write_original():
    template = cte.load_templates()[TEMPLATE_ID]
    allowed = template.get("write_mode", {}).get("allowed", [])
    assert "write_original" not in allowed


def test_hostile_slot_value_rejected_by_gate():
    template = cte.load_templates()[TEMPLATE_ID]
    with pytest.raises(cte.TemplateError) as ctx:
        cte._validate_slot_value(template["slots"]["selection"], "selection", "L;rm")
    assert ctx.value.code == "INJECTION_REJECTED"
