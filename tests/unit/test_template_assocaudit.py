import sys
from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).resolve().parent
ROUTER_HOME = _THIS_DIR.parents[1]
TOOLS_DIR = ROUTER_HOME / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import command_template_engine as cte  # noqa: E402


def test_assocaudit_template_loads_from_dropin():
    templates = cte.load_templates()
    assert "define.assocaudit" in templates
    assert templates["define.assocaudit"]["command"] == "AUDIT"


def test_assocaudit_never_allows_write_original():
    template = cte.load_templates()["define.assocaudit"]
    assert "write_original" not in template["write_mode"]["allowed"]
    assert set(template["write_mode"]["allowed"]) == {"read", "write_copy"}


@pytest.mark.parametrize("hostile", ["Y; QUIT", "N(a)"])
def test_assocaudit_rejects_hostile_slot_values_before_execution(hostile):
    template = cte.load_templates()["define.assocaudit"]
    with pytest.raises(cte.TemplateError) as exc:
        cte.render_script(template, {"fix_answer": hostile})
    assert exc.value.code == "INJECTION_REJECTED"
