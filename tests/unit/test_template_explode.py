"""tests/unit/test_template_explode.py -- offline validation for the
edit.assocarray.explode governed command template (EXPLODE / release
associativity on an associative array; census DCM edit.assocarray.explode).

Discovery note: by the time this lane ran, edit.assocarray.explode had
already landed directly in the base registry (config/command_templates.json)
via the wave-7 W5-TMPL harvest (commit 66cce00), live-verified against
accoreconsole (see TestArrayRectExplodeTemplateLive in
tests/unit/test_command_template_engine.py). command_template_engine's
drop-in loader (_ingest_templates) treats a duplicate template_id as a hard
DUPLICATE_TEMPLATE_ID collision by design -- a .d/ fragment must never
silently re-declare or override a governed base template -- so
config/command_templates.d/edit.assocarray.explode.json is an intentionally
empty fragment (declares zero templates) rather than a colliding
re-declaration. This file exercises the required invariants (registry
presence, write_mode exclusion of write_original, and the universal
hostile-character injection gate) against the real, already-governed
template, offline (no accoreconsole needed).
"""
import json
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
ROUTER_HOME = _THIS_DIR.parents[1]
TOOLS_DIR = ROUTER_HOME / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import command_template_engine as cte  # noqa: E402

_TEMPLATE_ID = "edit.assocarray.explode"
_FRAGMENT_PATH = ROUTER_HOME / "config" / "command_templates.d" / "edit.assocarray.explode.json"


class TestExplodeTemplateRegistered(unittest.TestCase):
    def test_the_d_fragment_file_exists_and_declares_zero_templates(self):
        """The real template already lives in the base registry; this
        fragment must stay empty to avoid a DUPLICATE_TEMPLATE_ID collision
        (see module docstring)."""
        self.assertTrue(_FRAGMENT_PATH.is_file())
        doc = json.loads(_FRAGMENT_PATH.read_text(encoding="utf-8-sig"))
        self.assertEqual(cte._templates_of(doc), [])

    def test_merged_registry_loads_cleanly_with_the_d_fragment_present(self):
        """Proves the keystone-1 drop-in loader merges base + this fragment
        without error (an empty fragment is a valid, non-colliding unit)."""
        templates = cte.load_templates()
        self.assertIn(_TEMPLATE_ID, templates)

    def test_write_mode_allowed_excludes_write_original(self):
        templates = cte.load_templates()
        allowed = templates[_TEMPLATE_ID]["write_mode"]["allowed"]
        self.assertNotIn("write_original", allowed)
        self.assertTrue(set(allowed) <= {"read", "write_copy"})
        self.assertIn("write_copy", allowed)

    def test_template_is_attended_full_autocad_headless_safe(self):
        templates = cte.load_templates()
        template = templates[_TEMPLATE_ID]
        self.assertTrue(template.get("headless_safe"))


class TestExplodeInjectionGuard(unittest.TestCase):
    """edit.assocarray.explode's real command_sequence is EXPLODE/L with zero
    agent-controllable slots (v1 scope: 'L' Last-object selection only, see
    the template's own notes in config/command_templates.json). The
    universal hostile-character gate in _validate_slot_value applies to
    every slot type regardless of which template declares it -- exercise it
    here with representative slot definitions to prove a hostile value
    (semicolon / parens) is rejected as INJECTION_REJECTED before any
    render/execution path is reached."""

    def test_semicolon_value_is_injection_rejected_before_execution(self):
        slot_def = {"type": "name_token"}
        with self.assertRaises(cte.TemplateError) as ctx:
            cte._validate_slot_value(slot_def, "selector", "L;QUIT")
        self.assertEqual(ctx.exception.code, "INJECTION_REJECTED")

    def test_paren_value_is_injection_rejected_before_execution(self):
        slot_def = {"type": "enum", "values": ["L", "L(command)"]}
        with self.assertRaises(cte.TemplateError) as ctx:
            cte._validate_slot_value(slot_def, "selector", "L(command)")
        self.assertEqual(ctx.exception.code, "INJECTION_REJECTED")

    def test_explode_template_has_no_agent_controllable_slots_in_v1(self):
        templates = cte.load_templates()
        explode = templates[_TEMPLATE_ID]
        self.assertEqual(explode.get("slots", {}), {})
        tokens = cte.render_script(explode, {})
        self.assertEqual(tokens, ["EXPLODE", "L"])


if __name__ == "__main__":
    unittest.main()
