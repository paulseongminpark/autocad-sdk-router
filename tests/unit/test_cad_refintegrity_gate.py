#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer Rung-D TEST -- cad_refintegrity_gate.check_reference_integrity.

Intent (WHY):
  * The north-star roundtrip metric (cad_diff, comparison_basis="geometry") is
    deliberately handle-independent -- and therefore structurally blind to
    whether a regen correctly re-points associative cross-references onto
    their new handles (OPUS_REVIEW.md finding C2 / PLAN.md v2-A5). Rung-D is
    the rung that closes that hole. If this gate could not tell a correctly
    re-pointed reference from a silently mis-rewired one, "geometry-diff == 0"
    would keep shipping associativity corruption certified as clean -- exactly
    the failure mode this test suite exists to rule out (Rule 9: a test that
    can't fail when the business logic changes is worthless).
  * The REQUIRED acceptance (PLAN.md / progress.md): "a deliberately
    mis-rewired hatch-boundary ref FAILS; a correct roundtrip passes." Both
    halves are pinned here, plus the same discrimination for the other three
    modelled categories (field->object, group->members, dictionary->entry)
    named alongside hatch->boundary in the same v2-A5 fix.
  * No-fake-success: a reference this gate cannot resolve to any modelled
    object is NEVER silently counted as passing (it is "unverifiable" +
    warned); an IR with no modelled references reports "skipped", never a
    fake "pass" -- both are pinned directly.
  * Determinism: the same (pre_ir, post_ir) pair yields byte-identical JSON.
  * Order-independence: PLAN.md explicitly calls out "a group whose member
    set is re-ordered" as something that must NOT fail -- pinned directly.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib
only.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _gate():
    import cad_refintegrity_gate
    return cad_refintegrity_gate


class TestCorrectRoundtripPasses(unittest.TestCase):
    """A textbook-correct regen (every handle reissued, every reference
    re-pointed at the geometrically-corresponding target) must PASS."""

    def setUp(self):
        self.gate = _gate()
        self.pre = self.gate.make_fixture_pre_ir()
        self.post = self.gate.make_regenerated_ir(self.pre)
        self.report = self.gate.check_reference_integrity(self.pre, self.post)

    def test_handles_were_actually_reissued(self):
        # Sanity: the premise of every other assertion in this file is that
        # pre/post do NOT share handles. If this ever failed, the other tests
        # would be trivially "passing" by accident (Rule 9).
        pre_hatch = next(e for e in self.pre["entities"] if e["dxf_name"] == "HATCH")
        post_hatch = next(e for e in self.post["entities"] if e["dxf_name"] == "HATCH")
        self.assertNotEqual(pre_hatch["handle"], post_hatch["handle"])
        pre_boundary = pre_hatch["geometry"]["loops"][0]["boundary_handles"][0]
        post_boundary = post_hatch["geometry"]["loops"][0]["boundary_handles"][0]
        self.assertNotEqual(pre_boundary, post_boundary)

    def test_overall_status_pass(self):
        self.assertEqual(self.report["schema"], "ariadne.cad_refintegrity_gate.v1")
        self.assertEqual(self.report["status"], "pass")
        self.assertEqual(self.report["summary"]["failed"], 0)
        self.assertGreater(self.report["summary"]["checked"], 0)
        self.assertEqual(self.report["violations"], [])

    def test_all_four_categories_checked_and_clean(self):
        cats = self.report["categories"]
        for cat in ("hatch_boundary", "field_object", "group_member", "dictionary_entry"):
            self.assertIn(cat, cats)
            self.assertEqual(cats[cat]["failed"], 0, "%s must not fail on a correct roundtrip" % cat)
            self.assertGreater(cats[cat]["checked"], 0, "%s should have been exercised" % cat)

    def test_reference_integrity_ok_true(self):
        self.assertTrue(self.gate.reference_integrity_ok(self.pre, self.post))

    def test_deterministic_rerun(self):
        report2 = self.gate.check_reference_integrity(self.pre, self.post)
        self.assertEqual(
            json.dumps(self.report, sort_keys=True, ensure_ascii=False),
            json.dumps(report2, sort_keys=True, ensure_ascii=False),
            "check_reference_integrity is not deterministic across runs",
        )

    def test_group_member_reordering_is_not_a_failure(self):
        # PLAN.md v2-A5 explicitly: "a group whose member set is re-ordered"
        # must NOT be reported as a mismatch (order-independent multiset).
        reordered = copy.deepcopy(self.post)
        grp = reordered["groups"][0]
        grp["members"] = list(reversed(grp["members"]))
        report = self.gate.check_reference_integrity(self.pre, reordered)
        self.assertEqual(report["categories"]["group_member"]["failed"], 0)
        self.assertEqual(report["status"], "pass")


class TestMisRewiredHatchBoundaryFails(unittest.TestCase):
    """The literal required acceptance: a deliberately mis-rewired
    hatch-boundary ref FAILS, isolated from the other three categories."""

    def setUp(self):
        self.gate = _gate()
        self.pre = self.gate.make_fixture_pre_ir()
        self.post_bad = self.gate.make_regenerated_ir(self.pre, break_category="hatch_boundary")
        self.report = self.gate.check_reference_integrity(self.pre, self.post_bad)

    def test_overall_status_fail(self):
        self.assertEqual(self.report["status"], "fail")
        self.assertGreaterEqual(self.report["summary"]["failed"], 1)

    def test_hatch_boundary_category_failed(self):
        cat = self.report["categories"]["hatch_boundary"]
        self.assertEqual(cat["checked"], 1)
        self.assertEqual(cat["failed"], 1)
        self.assertEqual(cat["matched"], 0)

    def test_violation_identifies_the_hatch(self):
        violations = [v for v in self.report["violations"] if v["category"] == "hatch_boundary"]
        self.assertEqual(len(violations), 1)
        self.assertIn("hHATCH", violations[0]["source_label"])

    def test_other_categories_unaffected(self):
        cats = self.report["categories"]
        for cat in ("field_object", "group_member", "dictionary_entry"):
            self.assertEqual(cats[cat]["failed"], 0,
                            "breaking hatch_boundary must not spuriously fail %s" % cat)

    def test_reference_integrity_ok_false(self):
        self.assertFalse(self.gate.reference_integrity_ok(self.pre, self.post_bad))


class TestMisRewiredOtherCategoriesFail(unittest.TestCase):
    """The same discrimination for the other three categories named alongside
    hatch->boundary in PLAN.md v2-A5 / OPUS_REVIEW C2: field->object,
    group->members, dictionary->entry."""

    def setUp(self):
        self.gate = _gate()
        self.pre = self.gate.make_fixture_pre_ir()

    def _check(self, category):
        post_bad = self.gate.make_regenerated_ir(self.pre, break_category=category)
        return self.gate.check_reference_integrity(self.pre, post_bad)

    def test_field_object_mismatch_detected(self):
        report = self._check("field_object")
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["categories"]["field_object"]["failed"], 1)
        self.assertEqual(report["categories"]["hatch_boundary"]["failed"], 0)

    def test_group_member_mismatch_detected(self):
        report = self._check("group_member")
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["categories"]["group_member"]["failed"], 1)
        # the group's OTHER member (the LINE) still resolves correctly.
        self.assertEqual(report["categories"]["group_member"]["matched"], 1)

    def test_dictionary_entry_mismatch_detected(self):
        report = self._check("dictionary_entry")
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["categories"]["dictionary_entry"]["failed"], 1)

    def test_unknown_break_category_raises(self):
        with self.assertRaises(ValueError):
            self.gate.make_regenerated_ir(self.pre, break_category="not_a_real_category")


class TestNoFakeSuccessEdgeCases(unittest.TestCase):
    """An IR with nothing to check reports 'skipped', never a fake 'pass'; an
    unresolvable reference is reported as 'unverifiable', never silently
    matched or silently passed."""

    def setUp(self):
        self.gate = _gate()

    def _bare_ir(self):
        return {
            "schema": "ariadne.dwg_graph_ir.v1",
            "source": {}, "database": {},
            "symbol_tables": {"layers": [{"name": "0"}]},
            "entities": [{
                "handle": "P1", "class": "AcDbLine", "dxf_name": "LINE",
                "owner_handle": "1F", "space": "model", "layer": "0",
                "bbox": [0, 0, 0, 1, 0, 0],
                "geometry": {"kind": "line", "start": [0, 0, 0], "end": [1, 0, 0]},
                "source": {"extractor": "test", "decoded": True},
            }],
            "diagnostics": {"entity_count": 1, "warnings": [], "errors": [], "coverage": {}},
        }

    def test_no_modelled_references_is_skipped_not_pass(self):
        ir = self._bare_ir()
        report = self.gate.check_reference_integrity(ir, copy.deepcopy(ir))
        self.assertEqual(report["status"], "skipped")
        self.assertEqual(report["summary"]["checked"], 0)
        self.assertEqual(report["summary"]["failed"], 0)
        # skipped is not a violation -- the convenience wrapper agrees.
        self.assertTrue(self.gate.reference_integrity_ok(ir, copy.deepcopy(ir)))

    def test_unresolvable_target_is_unverifiable_not_matched(self):
        pre = self.gate.make_fixture_pre_ir()
        for ent in pre["entities"]:
            if ent["dxf_name"] == "HATCH":
                ent["geometry"]["loops"][0]["boundary_handles"] = ["GHOST_HANDLE_404"]
        post = copy.deepcopy(pre)  # identical, but the dangling ref stays dangling
        report = self.gate.check_reference_integrity(pre, post)
        cat = report["categories"]["hatch_boundary"]
        self.assertEqual(cat["checked"], 0, "an unresolvable target must not be counted as checked")
        self.assertEqual(cat["unverifiable"], 1)
        self.assertTrue(any("GHOST_HANDLE_404" in w for w in report["warnings"]))

    def test_status_blocked_when_the_only_reference_is_unresolvable(self):
        ir = self._bare_ir()
        ir["entities"].append({
            "handle": "HZ", "class": "AcDbHatch", "dxf_name": "HATCH",
            "owner_handle": "1F", "space": "model", "layer": "0",
            "bbox": [0, 0, 0, 0, 0, 0],
            "geometry": {"kind": "hatch", "loops": [
                {"associative": True, "boundary_handles": ["GHOST_HANDLE_404"]},
            ]},
            "source": {"extractor": "test", "decoded": True},
        })
        report = self.gate.check_reference_integrity(ir, copy.deepcopy(ir))
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["summary"]["checked"], 0)

    def test_unresolvable_field_host_is_unverifiable(self):
        pre = self.gate.make_fixture_pre_ir()
        pre["fields"][0]["host_handle"] = "GHOST_HOST_404"
        post = copy.deepcopy(pre)
        report = self.gate.check_reference_integrity(pre, post)
        self.assertEqual(report["categories"]["field_object"]["unverifiable"], 1)
        self.assertEqual(report["categories"]["field_object"]["checked"], 0)


class TestSelfDemoAndCLI(unittest.TestCase):
    """The module's own bare self-demo (``python tools/cad_refintegrity_gate.py``
    with no args) must prove the same PASS/FAIL discrimination end to end."""

    def test_selftest_returns_zero(self):
        gate = _gate()
        self.assertEqual(gate._selftest(), 0)


if __name__ == "__main__":
    unittest.main()
