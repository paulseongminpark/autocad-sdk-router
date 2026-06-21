#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M02 TEST -- cad_diff.compute_diff: structural before/after diff.

Intent (WHY):
  * compute_diff is the engine-neutral judge of "what a patch actually changed".
    It joins two dwg_graph_ir.v1 IRs on the DWG handle (the cross-engine key) and
    classifies each handle as added / removed / modified / unchanged. If that
    classification is wrong, the validator's "the patch produced a real change"
    gate (diff_expected_changes) is meaningless. We pin it on synthetic IRs whose
    answer we know exactly.
  * The diff MUST be deterministic: handles sorted, no timestamps, no randomness,
    and diff_id a pure function of the two inputs. Re-running on the same pair
    yields byte-identical output. A non-deterministic diff can't be a stable
    contract (Rule 9).
  * No-fake-success: identical IRs produce ZERO changes (no false positives); an
    entity that cannot be joined (missing handle) is recorded in diagnostics, not
    silently matched.
  * The emitted document conforms to cad_diff.v1 (structurally always; against the
    schema when jsonschema is present).

Built from ir_builder.make_fixture_ir() so the diff is exercised against genuine
producer output (3 entities: LINE 2A7 / CIRCLE 2A8 / INSERT 2A9), then mutated in
controlled ways.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only
(plus optional jsonschema).
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

_SCHEMAS = os.path.join(_REPO, "schemas")
_JSON_ENCODING = "utf-8-sig"


def _load_json(path):
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _try_import_jsonschema():
    try:
        import jsonschema  # type: ignore
        return jsonschema
    except Exception:  # pragma: no cover
        return None


def _base_ir():
    import ir_builder
    return ir_builder.make_fixture_ir()


def _add_circle(ir, handle="2FF"):
    """Append a brand-new CIRCLE entity with a fresh handle (an 'added')."""
    ents = ir["entities"]
    ents.append({
        "handle": handle, "class": "AcDbCircle", "dxf_name": "CIRCLE",
        "owner_handle": ents[0].get("owner_handle", ""), "space": "model",
        "layer": "NEWLAYER",
        "bbox": [98.0, 98.0, 0.0, 102.0, 102.0, 0.0],
        "geometry": {"kind": "circle", "center": [100.0, 100.0, 0.0], "radius": 2.0},
        "source": {"extractor": "test", "decoded": True},
    })
    ir["diagnostics"]["entity_count"] = len(ents)
    return ir


class TestComputeDiffShape(unittest.TestCase):
    """A created+modified+deleted diff has the right cad_diff.v1 shape + counts."""

    def setUp(self):
        import cad_diff
        self.cad_diff = cad_diff
        pre = _base_ir()
        post = copy.deepcopy(pre)
        # added: new CIRCLE 2FF
        _add_circle(post, "2FF")
        # modified: LINE 2A7 -> change layer + geometry.end
        for e in post["entities"]:
            if e["handle"] == "2A7":
                e["layer"] = "MOVED"
                e["geometry"]["end"] = [99.0, 99.0, 0.0]
        # removed: drop the INSERT 2A9
        post["entities"] = [e for e in post["entities"] if e["handle"] != "2A9"]
        post["diagnostics"]["entity_count"] = len(post["entities"])
        self.pre, self.post = pre, post
        self.diff = cad_diff.compute_diff(pre, post)

    def test_schema_and_basis(self):
        self.assertEqual(self.diff["schema"], "ariadne.cad_diff.v1")
        self.assertEqual(self.diff["diagnostics"]["comparison_basis"], "handle")
        # diff_id is a content hash (deterministic), present + non-empty.
        self.assertTrue(self.diff.get("diff_id"))

    def test_summary_counts(self):
        summ = self.diff["summary"]
        self.assertEqual(summ["added"], 1)
        self.assertEqual(summ["removed"], 1)
        self.assertEqual(summ["modified"], 1)
        # the two untouched fixture entities... wait: 2A7 modified, 2A9 removed,
        # 2A8 untouched -> exactly 1 unchanged.
        self.assertEqual(summ["unchanged"], 1)
        # M02 contract aliases (created/deleted naming) mirror the frozen fields.
        self.assertEqual(summ["created_count"], 1)
        self.assertEqual(summ["deleted_count"], 1)
        self.assertEqual(summ["modified_count"], 1)

    def test_changed_handles_kinds(self):
        by = {(r["handle"], r["change"]) for r in self.diff["changed_handles"]}
        self.assertIn(("2FF", "added"), by)
        self.assertIn(("2A9", "removed"), by)
        self.assertIn(("2A7", "modified"), by)
        # 2A8 (unchanged) must NOT appear in changed_handles.
        self.assertNotIn(("2A8", "modified"), by)

    def test_modified_record_carries_field_delta(self):
        rec = next(r for r in self.diff["changed_handles"]
                   if r["handle"] == "2A7" and r["change"] == "modified")
        fields = [f["field"] for f in rec.get("fields", [])]
        self.assertIn("layer", fields)
        self.assertIn("geometry", fields)
        # before/after carry the actual layer values.
        layer_delta = next(f for f in rec["fields"] if f["field"] == "layer")
        self.assertEqual(layer_delta["before"], "0")
        self.assertEqual(layer_delta["after"], "MOVED")

    def test_changed_handles_deterministic_ordering(self):
        # added, then removed, then modified; handle-sorted within each kind.
        kinds = [r["change"] for r in self.diff["changed_handles"]]
        order = {"added": 0, "removed": 1, "modified": 2}
        self.assertEqual(kinds, sorted(kinds, key=lambda k: order[k]),
                         "changed_handles not ordered added/removed/modified")


class TestComputeDiffClassify(unittest.TestCase):
    """classify_change pinpoints exactly the changed fields."""

    def setUp(self):
        import cad_diff
        self.cad_diff = cad_diff

    def test_pure_layer_change(self):
        pre = {"handle": "1", "layer": "0", "dxf_name": "LINE",
               "bbox": [0, 0, 0, 1, 0, 0], "geometry": {"kind": "line"}}
        post = copy.deepcopy(pre)
        post["layer"] = "X"
        self.assertEqual(self.cad_diff.classify_change(pre, post), ["layer"])

    def test_geometry_leaf_is_localized(self):
        pre = {"handle": "1", "layer": "0", "dxf_name": "LINE",
               "bbox": [], "geometry": {"kind": "line", "start": [0, 0, 0],
                                        "end": [1, 0, 0]}}
        post = copy.deepcopy(pre)
        post["geometry"]["end"] = [2, 0, 0]
        fields = self.cad_diff.classify_change(pre, post)
        self.assertIn("geometry", fields)
        self.assertIn("geometry.end", fields)
        self.assertNotIn("geometry.start", fields)

    def test_no_change_is_empty(self):
        e = {"handle": "1", "layer": "0", "dxf_name": "LINE",
             "bbox": [0, 0, 0, 1, 0, 0], "geometry": {"kind": "line"}}
        self.assertEqual(self.cad_diff.classify_change(e, copy.deepcopy(e)), [])


class TestComputeDiffDeterminismAndNoFalsePositive(unittest.TestCase):

    def setUp(self):
        import cad_diff
        self.cad_diff = cad_diff

    def test_identical_irs_yield_zero_changes(self):
        ir = _base_ir()
        diff = self.cad_diff.compute_diff(ir, copy.deepcopy(ir))
        self.assertEqual(diff["summary"]["added"], 0)
        self.assertEqual(diff["summary"]["removed"], 0)
        self.assertEqual(diff["summary"]["modified"], 0)
        self.assertEqual(diff["summary"]["unchanged"], len(ir["entities"]))
        self.assertEqual(diff["changed_handles"], [])

    def test_byte_identical_on_rerun(self):
        pre = _base_ir()
        post = _add_circle(copy.deepcopy(pre), "2FF")
        d1 = self.cad_diff.compute_diff(pre, post)
        d2 = self.cad_diff.compute_diff(pre, post)
        self.assertEqual(
            json.dumps(d1, sort_keys=True, ensure_ascii=False),
            json.dumps(d2, sort_keys=True, ensure_ascii=False),
            "compute_diff is not deterministic across runs",
        )
        # same diff_id (pure function of the inputs).
        self.assertEqual(d1["diff_id"], d2["diff_id"])

    def test_unjoinable_entity_is_recorded_not_matched(self):
        # An entity with no usable handle cannot be joined; it must surface in
        # diagnostics (counted), never silently matched/dropped.
        pre = _base_ir()
        post = copy.deepcopy(pre)
        post["entities"].append({"handle": "", "dxf_name": "LINE",
                                 "geometry": {"kind": "line"}})
        diff = self.cad_diff.compute_diff(pre, post)
        self.assertGreaterEqual(diff["diagnostics"]["unjoinable_after"], 1)
        self.assertTrue(diff["diagnostics"]["warnings"])


class TestCadDiffSchemaConforms(unittest.TestCase):

    def setUp(self):
        import cad_diff
        pre = _base_ir()
        post = _add_circle(copy.deepcopy(pre), "2FF")
        self.diff = cad_diff.compute_diff(pre, post)

    def test_structural_required_keys(self):
        for k in ("schema", "diff_id", "before_ref", "after_ref",
                  "changed_handles", "summary", "diagnostics"):
            self.assertIn(k, self.diff, "diff missing required key %s" % k)
        for k in ("added", "removed", "modified"):
            self.assertIn(k, self.diff["summary"])
        self.assertIn("warnings", self.diff["diagnostics"])
        # state_refs are kind=ir with required ref.
        for side in ("before_ref", "after_ref"):
            self.assertEqual(self.diff[side]["kind"], "ir")
            self.assertIn("ref", self.diff[side])

    def test_validates_against_schema(self):
        jsonschema = _try_import_jsonschema()
        if jsonschema is None:
            self.skipTest("SKIPPED_DEP: jsonschema not importable")
        schema = _load_json(os.path.join(_SCHEMAS, "cad_diff.v1.schema.json"))
        jsonschema.Draft7Validator.check_schema(schema)
        validator = jsonschema.Draft7Validator(schema)
        errors = sorted(validator.iter_errors(self.diff), key=lambda e: list(e.path))
        self.assertEqual(
            errors, [],
            "cad_diff does not conform to cad_diff.v1: "
            + "; ".join("%s: %s" % ("/".join(str(p) for p in e.path), e.message)
                       for e in errors[:8]),
        )


if __name__ == "__main__":
    unittest.main()
