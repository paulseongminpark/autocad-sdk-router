#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEST -- P3b fragment-level fixture-DWG override.

Intent (WHY):
  handle_provisioned_3.json fixtures reference handles that only exist in the
  purpose-built enriched seed (tests/fixtures/enriched_seed_20260716.dwg).
  _merge_reachable_fixtures must route those ops' probes to THAT dwg -- if the
  override is lost, a future sweep runs their valid legs against
  native_sample.dwg, every handle is dead, and the sweep silently DEMOTES the
  promoted rows back to REACHABLE. This locks: (1) the override loads, (2) it
  never leaks onto other fragments or the curated inline set, (3) the enriched
  seed exists and matches its committed sha256 (a stale/replaced fixture would
  invalidate every harvested handle).

Stdlib only; registry-static (no accoreconsole run).
"""
from __future__ import annotations

import hashlib
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
sys.path.insert(0, os.path.join(_REPO, "tools"))

import probe_reachability as pr  # noqa: E402

_FRAGMENT = "handle_provisioned_3.json"
_ENRICHED = "tests/fixtures/enriched_seed_20260716.dwg"


class TestFixtureDwgOverride(unittest.TestCase):
    def setUp(self):
        self.frag_ops = {op: fx for op, fx in pr.FIXTURES.items()
                         if fx.get("source_fragment") == _FRAGMENT}

    def test_fragment_loaded_with_dwg_override(self):
        self.assertGreater(len(self.frag_ops), 0, "fragment fixtures did not load")
        for op, fx in self.frag_ops.items():
            self.assertEqual(fx.get("dwg"), _ENRICHED, op)

    def test_override_does_not_leak_to_other_fixtures(self):
        for op, fx in pr.FIXTURES.items():
            if fx.get("source_fragment") != _FRAGMENT:
                self.assertNotEqual(fx.get("dwg"), _ENRICHED, op)

    def test_solid_tail_ops_are_covered(self):
        # The solid ceiling the enriched seed exists to break: if these drop
        # out of the fragment, the 12-op needs_3d_solid class silently regresses.
        for op in ("compute.brep.volume", "compute.solid3d.interference",
                   "modify.entity.solid3d.boolean", "inspect.brep.from_entity"):
            self.assertIn(op, self.frag_ops, op)

    def test_enriched_seed_exists_and_matches_sha(self):
        dwg = os.path.join(_REPO, _ENRICHED)
        sha_file = dwg + ".sha256"
        self.assertTrue(os.path.isfile(dwg), "enriched seed missing")
        self.assertTrue(os.path.isfile(sha_file), "enriched seed sha256 missing")
        with open(sha_file, encoding="utf-8") as fh:
            expected = fh.read().split()[0].strip().lower()
        h = hashlib.sha256()
        with open(dwg, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        self.assertEqual(h.hexdigest().lower(), expected,
                         "enriched seed content drifted from its committed sha256 -- "
                         "harvested handles in handle_provisioned_3.json are no longer trustworthy")


if __name__ == "__main__":
    unittest.main()
