#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEST -- P5a module_event reclassification registry contract.

Intent (WHY):
  The 16 blocked `runtime_commands` ops are host-owned module/loader lifecycle
  events (kInitAppMsg, acrxEntryPoint dispatch, acrxLoadModule, ...) -- not
  dispatchable job operations. Encoding that as ``kind=module_event`` +
  ``dispatchable=false`` keeps any future dispatcher/probe sweep from ever
  trying to dispatch them (and from counting them as un-built gaps). This test
  locks the contract: exactly that blocked set is reclassified, nothing else
  inherits the flags, and the 10 genuinely dispatchable runtime_commands ops
  (command.register.define etc.) stay dispatchable.

Stdlib only; registry-static (no native build, no AutoCAD).
"""
from __future__ import annotations

import json
import os
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_REGISTRY = os.path.join(_REPO, "config", "operations.v2.json")

_EXPECTED_MODULE_EVENTS = frozenset((
    "module.command.lookup",
    "module.command.remove_group",
    "module.entrypoint.define",
    "module.entrypoint.dispatch",
    "module.lifecycle.init",
    "module.lifecycle.on_load_dwg",
    "module.lifecycle.on_ole_unload",
    "module.lifecycle.on_unload_dwg",
    "module.lifecycle.other",
    "module.lifecycle.unload",
    "module.load",
    "module.load.acad_rx",
    "module.load.by_app",
    "module.load.demand_register",
    "module.load.lisp",
    "module.unload",
))


def _ops():
    with open(_REGISTRY, "r", encoding="utf-8-sig") as fh:
        reg = json.load(fh)
    ops = reg["operations"]
    return list(ops.values()) if isinstance(ops, dict) else ops


class TestModuleEventReclassification(unittest.TestCase):
    def setUp(self):
        self.ops = _ops()
        self.by_id = {o["id"]: o for o in self.ops}

    def test_exactly_the_16_blocked_runtime_commands_are_module_events(self):
        actual = {o["id"] for o in self.ops if o.get("kind") == "module_event"}
        self.assertEqual(actual, set(_EXPECTED_MODULE_EVENTS))

    def test_every_module_event_is_not_dispatchable(self):
        for op_id in _EXPECTED_MODULE_EVENTS:
            op = self.by_id[op_id]
            self.assertIs(op.get("dispatchable"), False, op_id)
            self.assertEqual(op.get("family"), "runtime_commands", op_id)
            self.assertEqual(op.get("status"), "blocked", op_id)

    def test_no_dispatchable_false_outside_module_events(self):
        stray = [o["id"] for o in self.ops
                 if o.get("dispatchable") is False and o.get("kind") != "module_event"]
        self.assertEqual(stray, [])

    def test_runnable_runtime_commands_stay_dispatchable(self):
        # The 10 probed-RUNNABLE registration/inventory ops must NOT be swept
        # into the module_event class (they dispatch fine in coreconsole).
        for op_id in ("command.register.define", "module.command.flags",
                      "module.register_service", "module.class.register_object"):
            op = self.by_id[op_id]
            self.assertNotEqual(op.get("kind"), "module_event", op_id)
            self.assertIsNot(op.get("dispatchable"), False, op_id)


if __name__ == "__main__":
    unittest.main()
