#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/unit/test_template_overkill.py -- offline contract test for the
config/command_templates.d/maintenance.drawing.overkill.json drop-in template.

Pins three things, fully offline (no accoreconsole, no staging, no network):
  1. The real repo registry (base command_templates.json + every fragment
     under command_templates.d/) loads this template through
     command_template_engine.load_templates() -- i.e. the drop-in file is
     actually wired into the governed registry, not just sitting on disk.
  2. Its write_mode.allowed never contains "write_original" -- write_original
     is impossible by construction for every template in this registry (see
     docs/GOVERNED_COMMAND_TEMPLATES.md section 3); this test pins that
     invariant for this specific drop-in.
  3. A hostile value fed into its float_range "tolerance" slot is rejected
     (raises TemplateError) rather than silently coerced or smuggled into the
     rendered .scr token list.
"""
from __future__ import annotations

import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import command_template_engine as cte  # noqa: E402

TEMPLATE_ID = "maintenance.drawing.overkill"


class TestOverkillTemplate(unittest.TestCase):
    def setUp(self):
        self.templates = cte.load_templates()
        self.assertIn(
            TEMPLATE_ID, self.templates,
            f"{TEMPLATE_ID!r} not found via load_templates() -- is "
            "config/command_templates.d/maintenance.drawing.overkill.json present?",
        )
        self.template = self.templates[TEMPLATE_ID]

    def test_loaded_via_dropin_registry(self):
        self.assertEqual(self.template["template_id"], TEMPLATE_ID)

    def test_write_mode_excludes_write_original(self):
        allowed = self.template["write_mode"]["allowed"]
        self.assertNotIn("write_original", allowed)
        self.assertTrue(set(allowed) <= {"read", "write_copy"})

    def test_hostile_tolerance_slot_rejected(self):
        hostile = '1.0"); (command "FORMAT" "C:") ('
        with self.assertRaises(cte.TemplateError) as cm:
            cte.render_script(self.template, {"tolerance": hostile})
        # Rejected either by the universal hostile-char gate (INJECTION_REJECTED)
        # or because the float_range numeric parse fails on a non-numeric
        # hostile payload (VALIDATION_ERROR) -- either way it must never reach
        # the rendered token list.
        self.assertIn(cm.exception.code, ("INJECTION_REJECTED", "VALIDATION_ERROR"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
