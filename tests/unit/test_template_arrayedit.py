from __future__ import annotations

import sys
from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).resolve().parent
_REPO = _THIS_DIR.parents[1]
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import command_template_engine as cte  # noqa: E402


def test_load_templates_includes_define_arrayedit():
    templates = cte.load_templates()
    assert "define.arrayedit" in templates


def test_define_arrayedit_never_allows_write_original():
    template = cte.load_templates()["define.arrayedit"]
    allowed = template.get("write_mode", {}).get("allowed", [])
    assert "write_original" not in allowed


@pytest.mark.parametrize("hostile", ["Reset;", "Source(command)"])
def test_define_arrayedit_rejects_hostile_slot_values_before_execution(hostile: str):
    template = cte.load_templates()["define.arrayedit"]
    with pytest.raises(cte.TemplateError) as excinfo:
        cte.render_script(template, {"subcommand": hostile})
    assert excinfo.value.code == "INJECTION_REJECTED"
