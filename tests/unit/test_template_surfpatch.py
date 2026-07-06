#!/usr/bin/env python3
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


class TestSurfPatchTemplate(unittest.TestCase):
    def test_load_templates_includes_define_surfpatch(self):
        templates = cte.load_templates()
        self.assertIn("define.surfpatch", templates)

    def test_write_mode_never_allows_write_original(self):
        template = cte.load_templates()["define.surfpatch"]
        self.assertNotIn("write_original", template["write_mode"]["allowed"])

    def test_hostile_slot_value_is_rejected_before_execution(self):
        template = cte.load_templates()["define.surfpatch"]
        with self.assertRaises(cte.TemplateError) as cm:
            cte.render_script(template, {"continuity": "G0;", "bulge_magnitude": 0.5})
        self.assertEqual(cm.exception.code, "INJECTION_REJECTED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
