"""Governed SURFLOFT template coverage: registry presence + hostile-slot gate."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import command_template_engine as cte


def test_define_surfloft_template_loads_from_dropin_and_denies_write_original():
    templates = cte.load_templates()
    template = templates["define.surfloft"]

    assert "define.surfloft" in templates
    allowed = template.get("write_mode", {}).get("allowed", [])
    assert "write_original" not in allowed
    assert set(allowed) == {"read", "write_copy"}


def test_define_surfloft_hostile_slot_value_rejected_before_execution():
    templates = cte.load_templates()
    template = templates["define.surfloft"]
    with pytest.raises(cte.TemplateError) as cm:
        cte.render_script(template, {"surf_option": "Cross sections only;"})
    assert cm.value.code == "INJECTION_REJECTED"
