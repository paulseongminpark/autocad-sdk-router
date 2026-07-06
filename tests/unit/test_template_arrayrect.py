"""Offline coverage for the governed ARRAYRECT drop-in template."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO = _THIS_DIR.parents[1]
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import command_template_engine as cte  # noqa: E402


class TestArrayRectTemplate(unittest.TestCase):
    def test_dropin_template_is_loaded_and_write_original_is_excluded(self):
        templates = cte.load_templates()
        self.assertIn("define.arrayrect", templates)
        allowed = templates["define.arrayrect"].get("write_mode", {}).get("allowed", [])
        self.assertNotIn("write_original", allowed)

    def test_hostile_value_hits_injection_gate_before_execution(self):
        with self.assertRaises(cte.TemplateError) as ctx:
            cte._validate_slot_value(
                {"type": "enum", "values": ["L", "C"]},
                "array_mode",
                "L;QUIT",
            )
        self.assertEqual(ctx.exception.code, "INJECTION_REJECTED")


if __name__ == "__main__":
    unittest.main()
