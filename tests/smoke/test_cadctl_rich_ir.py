#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M02 SMOKE -- the LIVE native_full IR fixture is what it claims.

Intent (WHY):
  * The M02 rich path's deliverable is a native_full IR (runs/m02_cadctl_rich/
    dwg_graph_ir.json) carrying the full symbol-table/blocks/layouts depth for the
    golden DWG. This smoke test loads that REAL artifact (no AutoCAD needed -- it
    is already on disk) and asserts the single fact everything downstream rests
    on: coverage_level == native_full AND the truth gate holds at 21747
    (diagnostics.entity_count == len(entities) == the golden modelspace total).
  * It cross-checks the realized entities[] against the golden by-type histogram
    and the pinned golden manifest/expected_counts, so a regenerated-but-wrong IR
    (right count, wrong composition) is caught.
  * No-fake-success / no-bypass: this reads an already-produced IR; it performs no
    DWG parsing. If the 15MB artifact is absent, it SKIPS with an explicit reason
    -- it must never hard-fail merely because the fixture has not been produced on
    this checkout.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tests.live_fixture_utils import ensure_m02_cadctl_rich_fixture

_JSON_ENCODING = "utf-8-sig"
_LIVE_IR = os.path.join(_REPO, "runs", "m02_cadctl_rich", "dwg_graph_ir.json")
_GOLDEN_DIR = os.path.join(_REPO, "tests", "golden")
_EXPECTED_COUNTS = os.path.join(_GOLDEN_DIR, "expected_counts.json")

_GOLDEN_TOTAL = 21747


def _load_json(path):
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


class TestLiveNativeFullIr(unittest.TestCase):
    def setUp(self):
        if not os.path.isfile(_LIVE_IR):
            ok, reason = ensure_m02_cadctl_rich_fixture(_REPO)
            if not ok:
                self.skipTest(
                    "SKIPPED_FIXTURE: native_full IR not present: %s (%s)"
                    % (_LIVE_IR, reason)
                )
        # Load via ir_builder.load_ir so we exercise the producer's own BOM-tolerant
        # reader (the path consumers actually use), not an ad-hoc open.
        import ir_builder
        self.ir = ir_builder.load_ir(_LIVE_IR)

    def test_schema_and_coverage_level(self):
        self.assertEqual(self.ir.get("schema"), "ariadne.dwg_graph_ir.v1")
        self.assertEqual(self.ir.get("coverage_level"), "native_full",
                         "live IR is not native_full")

    def test_truth_gate_21747(self):
        diag = self.ir["diagnostics"]
        self.assertEqual(diag["entity_count"], _GOLDEN_TOTAL,
                         "diagnostics.entity_count != 21747")
        self.assertEqual(len(self.ir["entities"]), _GOLDEN_TOTAL,
                         "len(entities) != 21747")
        self.assertEqual(diag["entity_count"], len(self.ir["entities"]),
                         "truth gate broken: entity_count != len(entities)")

    def test_by_type_matches_pinned_expected_counts(self):
        if not os.path.isfile(_EXPECTED_COUNTS):
            self.skipTest("SKIPPED_FIXTURE: expected_counts.json not present")
        expected = _load_json(_EXPECTED_COUNTS)
        self.assertEqual(expected["modelspace_total"], _GOLDEN_TOTAL)
        self.assertEqual(self.ir["diagnostics"]["entities_by_type"],
                         expected["by_type"],
                         "live IR by-type histogram drifted from golden expected_counts")

    def test_realized_entities_recompute_by_type(self):
        # Recompute the histogram from the realized entities[] (not the diagnostics
        # echo) and confirm it still sums to 21747 and matches the declared one.
        from collections import Counter
        recomputed = Counter(e.get("dxf_name") for e in self.ir["entities"])
        self.assertEqual(sum(recomputed.values()), _GOLDEN_TOTAL)
        self.assertEqual(dict(recomputed),
                         self.ir["diagnostics"]["entities_by_type"],
                         "recomputed by-type != declared entities_by_type")


if __name__ == "__main__":
    unittest.main()
