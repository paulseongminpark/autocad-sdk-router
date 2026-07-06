from __future__ import annotations

import sys
from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).resolve().parent
ROUTER_HOME = _THIS_DIR.parents[1]
TOOLS_DIR = ROUTER_HOME / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import command_template_engine as cte  # noqa: E402


def test_surffillet_template_loads_from_dropin_registry():
    templates = cte.load_templates()
    assert "define.surffillet" in templates

    tmpl = templates["define.surffillet"]
    assert tmpl["command"] == "SURFFILLET"
    assert tmpl["slots"]["radius"]["type"] == "float_range"
    assert tmpl["slots"]["trim_mode"]["type"] == "enum"


def test_surffillet_template_never_allows_write_original():
    tmpl = cte.load_templates()["define.surffillet"]
    allowed = tmpl.get("write_mode", {}).get("allowed", [])
    assert "write_original" not in allowed


def test_surffillet_hostile_slot_value_is_rejected_before_execution():
    tmpl = cte.load_templates()["define.surffillet"]

    with pytest.raises(cte.TemplateError) as exc:
        cte.render_script(tmpl, {"radius": 2.5, "trim_mode": "TRIM;QUIT"})

    assert exc.value.code == "INJECTION_REJECTED"
