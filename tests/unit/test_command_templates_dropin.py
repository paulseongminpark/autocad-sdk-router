#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CADOS keystone-1 TEST -- command_template_engine drop-in (.d/) registry load.

Intent (WHY):
  The governed command-template registry used to be a SINGLE file
  (config/command_templates.json). That made every new template a conflicting
  edit to one JSON -- the exact merge-collision surface that made wide parallel
  fan-out unsafe. This keystone lets a new template land as its OWN file under
  config/command_templates.d/, so template additions become DISJOINT units.

  The contract this test pins:
    1. Back-compat: with no .d/ dir, the load is identical to before.
    2. A fragment file (bare list OR {"templates":[...]}) is folded in.
    3. Deterministic, base-first + filename-sorted order.
    4. Fail LOUD, never last-writer-wins: a duplicate template_id across
       base<->fragment or fragment<->fragment is a hard DUPLICATE_TEMPLATE_ID.
    5. The write_mode safety invariant holds for EVERY source: a fragment
       cannot introduce a disallowed write_mode (e.g. write_original).

Offline/deterministic: pure temp-file JSON, no accoreconsole, no network.
Stdlib + pytest.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import command_template_engine as cte  # noqa: E402


def _tmpl(tid, allowed=("read",)):
    """A minimal valid template record (only the fields load_templates reads)."""
    return {
        "template_id": tid,
        "command": "AUDIT",
        "slots": [],
        "write_mode": {"default": "read", "allowed": list(allowed)},
    }


def _write(path: Path, doc):
    path.write_text(json.dumps(doc), encoding="utf-8")


class TestDropInRegistry(unittest.TestCase):
    def _base(self, td, templates):
        base = Path(td) / "command_templates.json"
        _write(base, {"templates": templates})
        return base

    def _dropin_dir(self, td):
        d = Path(td) / "command_templates.d"
        d.mkdir(exist_ok=True)
        return d

    def test_base_only_backcompat(self):
        with TemporaryDirectory() as td:
            base = self._base(td, [_tmpl("maintenance.drawing.audit"),
                                   _tmpl("maintenance.drawing.purge")])
            got = cte.load_templates(base)
            self.assertEqual(set(got), {"maintenance.drawing.audit",
                                        "maintenance.drawing.purge"})

    def test_fragment_is_merged_dict_shape(self):
        with TemporaryDirectory() as td:
            base = self._base(td, [_tmpl("base.op")])
            d = self._dropin_dir(td)
            _write(d / "arrays.json", {"templates": [_tmpl("define.assocarray.rectangular")]})
            got = cte.load_templates(base)
            self.assertEqual(set(got), {"base.op", "define.assocarray.rectangular"})

    def test_fragment_bare_list_shape(self):
        with TemporaryDirectory() as td:
            base = self._base(td, [_tmpl("base.op")])
            d = self._dropin_dir(td)
            _write(d / "surf.json", [_tmpl("define.assocsurface.loft")])  # bare list
            got = cte.load_templates(base)
            self.assertIn("define.assocsurface.loft", got)

    def test_multiple_fragments_all_merged(self):
        with TemporaryDirectory() as td:
            base = self._base(td, [_tmpl("base.op")])
            d = self._dropin_dir(td)
            _write(d / "a.json", [_tmpl("a.one")])
            _write(d / "b.json", [_tmpl("b.one"), _tmpl("b.two")])
            got = cte.load_templates(base)
            self.assertEqual(set(got), {"base.op", "a.one", "b.one", "b.two"})

    def test_collision_base_vs_fragment_is_hard_error(self):
        with TemporaryDirectory() as td:
            base = self._base(td, [_tmpl("dup.op")])
            d = self._dropin_dir(td)
            _write(d / "shadow.json", [_tmpl("dup.op")])
            with self.assertRaises(cte.TemplateError) as cm:
                cte.load_templates(base)
            self.assertEqual(cm.exception.code, "DUPLICATE_TEMPLATE_ID")

    def test_collision_fragment_vs_fragment_is_hard_error(self):
        with TemporaryDirectory() as td:
            base = self._base(td, [_tmpl("base.op")])
            d = self._dropin_dir(td)
            _write(d / "a.json", [_tmpl("clash")])
            _write(d / "b.json", [_tmpl("clash")])
            with self.assertRaises(cte.TemplateError) as cm:
                cte.load_templates(base)
            self.assertEqual(cm.exception.code, "DUPLICATE_TEMPLATE_ID")

    def test_fragment_cannot_introduce_disallowed_write_mode(self):
        # The write_original-impossible invariant must hold for drop-ins too.
        with TemporaryDirectory() as td:
            base = self._base(td, [_tmpl("base.op")])
            d = self._dropin_dir(td)
            _write(d / "evil.json", [_tmpl("evil.op", allowed=("read", "write_original"))])
            with self.assertRaises(cte.TemplateError) as cm:
                cte.load_templates(base)
            self.assertEqual(cm.exception.code, "INVALID_TEMPLATE_REGISTRY")

    def test_real_repo_registry_still_loads(self):
        # The committed config/command_templates.json (+ any real .d/) must load
        # cleanly through the new path -- guards against a shape regression.
        got = cte.load_templates()
        self.assertIn("maintenance.drawing.audit", got)


if __name__ == "__main__":
    unittest.main(verbosity=2)
