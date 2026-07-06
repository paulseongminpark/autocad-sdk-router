from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO = _THIS_DIR.parents[1]
_TOOLS = _REPO / "tools"
for _p in (str(_REPO), str(_TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import command_template_engine as cte  # noqa: E402


class TestArrayPathTemplate(unittest.TestCase):
    def test_template_loads_and_blocks_hostile_values(self):
        templates = cte.load_templates()
        self.assertIn("define.arraypath", templates)

        template = templates["define.arraypath"]
        self.assertNotIn("write_original", template["write_mode"]["allowed"])

        with self.assertRaises(cte.TemplateError) as ctx:
            cte._reject_if_hostile("7;QUIT", "item_count")

        self.assertEqual(ctx.exception.code, "INJECTION_REJECTED")


if __name__ == "__main__":
    unittest.main()
