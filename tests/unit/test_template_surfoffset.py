import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
ROUTER_HOME = _THIS_DIR.parents[1]
TOOLS_DIR = ROUTER_HOME / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import command_template_engine as cte  # noqa: E402


class TestSurfOffsetTemplate(unittest.TestCase):
    def test_template_loads_from_drop_in_dir(self):
        templates = cte.load_templates()
        self.assertIn("define.surfoffset", templates)

    def test_write_mode_never_allows_write_original(self):
        template = cte.load_templates()["define.surfoffset"]
        self.assertNotIn("write_original", template["write_mode"]["allowed"])

    def test_hostile_value_is_rejected_by_engine_gate_before_execution(self):
        with self.assertRaises(cte.TemplateError) as ctx:
            cte._reject_if_hostile("12.5;", "distance")
        self.assertEqual(ctx.exception.code, "INJECTION_REJECTED")

        with self.assertRaises(cte.TemplateError) as ctx:
            cte._reject_if_hostile("12.5)", "distance")
        self.assertEqual(ctx.exception.code, "INJECTION_REJECTED")


if __name__ == "__main__":
    unittest.main()
