"""Offline coverage for the SURFTRIM governed template."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
ROUTER_HOME = _THIS_DIR.parents[1]
TOOLS_DIR = ROUTER_HOME / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import command_template_engine as cte  # noqa: E402


class TestSurftrimTemplate(unittest.TestCase):
    def test_template_loads_and_never_allows_write_original(self):
        templates = cte.load_templates()
        self.assertIn("define.surftrim", templates)
        allowed = templates["define.surftrim"]["write_mode"]["allowed"]
        self.assertNotIn("write_original", allowed)

    def test_hostile_slot_value_is_rejected_before_execution(self):
        template = cte.load_templates()["define.surftrim"]
        with self.assertRaises(cte.TemplateError) as ctx:
            cte.render_script(template, {
                "extend": "Y;QUIT",
                "projection_direction": "A",
            })
        self.assertEqual(ctx.exception.code, "INJECTION_REJECTED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
