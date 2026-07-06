#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for the maintenance.drawing.recover governed command template
(config/command_templates.d/maintenance.drawing.recover.json).

Pins the same 3 guarantees every drop-in command template must satisfy (see
tests/unit/test_command_templates_dropin.py for the drop-in loader's own
generic contract, and tests/unit/test_command_template_engine.py for the
generic injection-guard tests this mirrors for THIS template specifically):

  1. The real registry load (config/command_templates.json plus its
     config/command_templates.d/*.json fragments) includes this template.
  2. Its write_mode.allowed never contains "write_original" -- the same
     write_original-impossible invariant every template must hold.
  3. A hostile value in its one real slot (recover_target_path) is rejected
     by the universal injection guard / staged_path escape check before it
     could ever reach a rendered .scr line.

No accoreconsole, no network -- pure registry load + render_script().
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
ROUTER_HOME = _THIS_DIR.parents[1]
TOOLS_DIR = ROUTER_HOME / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import command_template_engine as cte  # noqa: E402

TEMPLATE_ID = "maintenance.drawing.recover"


class TestRecoverTemplateRegistered(unittest.TestCase):
    def test_load_templates_includes_recover(self):
        templates = cte.load_templates()
        self.assertIn(TEMPLATE_ID, templates)

    def test_recover_command_sequence_starts_with_recover_literal(self):
        template = cte.load_templates()[TEMPLATE_ID]
        first_step = template["command_sequence"][0]
        self.assertEqual(first_step.get("literal"), "RECOVER")


class TestRecoverWriteModeExcludesWriteOriginal(unittest.TestCase):
    def test_write_mode_allowed_excludes_write_original(self):
        template = cte.load_templates()[TEMPLATE_ID]
        allowed = template["write_mode"]["allowed"]
        self.assertNotIn("write_original", allowed)
        self.assertTrue(set(allowed) <= {"read", "write_copy"})
        self.assertIn(template["write_mode"]["default"], allowed)


class TestRecoverHostileSlotRejected(unittest.TestCase):
    """The recover_target_path slot is a staged_path -- both the universal
    hostile-character gate AND the staging/-root escape check must hold."""

    HOSTILE_VALUES = [
        "input.dwg; QUIT",
        'input.dwg"',
        "input.dwg'",
        "input.dwg(command)",
        "input.dwg\n",
        "input.dwg\x00",
        "input.dwg\x7f",
        "../../etc/passwd",
    ]

    def setUp(self):
        self.template = cte.load_templates()[TEMPLATE_ID]

    def test_hostile_value_in_recover_target_path_is_rejected(self):
        for hostile in self.HOSTILE_VALUES:
            with self.assertRaises(cte.TemplateError) as ctx:
                cte.render_script(self.template, {"recover_target_path": hostile})
            self.assertIn(
                ctx.exception.code,
                ("INJECTION_REJECTED", "VALIDATION_ERROR"),
                msg=repr(hostile),
            )

    def test_safe_staged_path_is_accepted(self):
        inside = cte.STAGING_DIR / "tmpl_maintenance_drawing_recover_00000000_000000_000" / "input.dwg"
        tokens = cte.render_script(self.template, {"recover_target_path": str(inside)})
        self.assertEqual(tokens[0], "RECOVER")
        self.assertTrue(tokens[1].startswith(str(cte.STAGING_DIR.resolve()).replace("\\", "/")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
