"""Offline regression coverage for the governed ARRAYPOLAR template."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO = _THIS_DIR.parents[1]
_TOOLS = _REPO / "tools"
for _p in (_REPO, _TOOLS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import command_template_engine as cte  # noqa: E402


class TestArrayPolarTemplate(unittest.TestCase):
    def test_template_loads_from_dropin_dir(self):
        templates = cte.load_templates()
        self.assertIn("define.arraypolar", templates)

    def test_write_mode_never_allows_write_original(self):
        template = cte.load_templates()["define.arraypolar"]
        allowed = template.get("write_mode", {}).get("allowed", [])
        self.assertIn("read", allowed)
        self.assertIn("write_copy", allowed)
        self.assertNotIn("write_original", allowed)

    def test_hostile_slot_value_is_rejected_before_execution(self):
        template = cte.load_templates()["define.arraypolar"]
        slot_def = template["slots"]["rotate_items"]
        with self.assertRaises(cte.TemplateError) as cm:
            cte._validate_slot_value(slot_def, "rotate_items", "Y;QUIT")
        self.assertEqual(cm.exception.code, "INJECTION_REJECTED")

    def test_hostile_paren_value_is_rejected_before_execution(self):
        template = cte.load_templates()["define.arraypolar"]
        slot_def = template["slots"]["rotate_items"]
        with self.assertRaises(cte.TemplateError) as cm:
            cte._validate_slot_value(slot_def, "rotate_items", "Y(QUIT)")
        self.assertEqual(cm.exception.code, "INJECTION_REJECTED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
