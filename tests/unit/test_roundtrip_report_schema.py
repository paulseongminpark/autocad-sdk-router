#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for ariadne.roundtrip_report.v1 schema + validate_roundtrip_report."""
from __future__ import annotations

import builtins
import copy
import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from unittest import mock

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import validate_roundtrip_report as vrr


def _valid_report() -> dict:
    """R1b2-era roundtrip report shape built by hand for schema conformance."""
    return {
        "schema": "ariadne.roundtrip_report.v1",
        "run_dir": r"D:\runs\R1b2_capstone",
        "source": {
            "original_path": r"D:\fixtures\input.dwg",
            "original_sha256": "orig-sha",
            "staged_sha256": "staged-sha",
        },
        "ceiling": {
            "modelspace_entity_total": 21747,
            "certified_total": 21078,
            "out_of_class_total": 669,
            "deferred_count": 1,
        },
        "kind_buckets": {
            "INSERT": {
                "status": "FAIL",
                "certified": True,
                "label": "insert",
                "kind": "insert",
                "census_count": 2027,
                "attempted_count": 3,
                "diff0_count": 1,
                "modified_count": 0,
                "removed_count": 2,
                "added_count": 0,
            },
            "ARC": {
                "status": "PASS",
                "certified": True,
                "label": "arc",
                "kind": "arc",
                "census_count": 753,
                "attempted_count": 753,
                "diff0_count": 753,
                "modified_count": 0,
                "removed_count": 0,
                "added_count": 0,
            },
        },
        "patterns": [
            {
                "signature": {
                    "dxf_name": "INSERT",
                    "change": "deferred",
                    "context": "reason:no block_definitions entry",
                },
                "count": 1,
                "examples": [
                    {
                        "op_id": "insert_block",
                        "reason": "no block_definitions entry",
                        "dxf_name": "INSERT",
                    }
                ],
                "judgment": "harmful",
                "rule_id": "R_DEFERRED_BLOCK_DEF",
                "note": "Deferred op references a missing block definition; real fidelity loss.",
            },
            {
                "signature": {
                    "dxf_name": "POLYLINE",
                    "change": "removed",
                    "context": "layer:0",
                },
                "count": 2,
                "examples": [],
                "judgment": "harmless",
                "rule_id": "R_KIND_DRIFT_POLYLINE_LWPOLYLINE",
                "note": "kind drift",
            },
        ],
        "naive_vs_smart": {
            "naive_pass": True,
            "smart_all_diff0": False,
            "contrast_note": (
                "Naive foil passes while smart diff0 gate fails; "
                "the foil is blind to moves and modifications."
            ),
        },
        "totals": {
            "regen_attempted_count": 756,
            "diff0_count": 754,
            "modified_count": 0,
            "removed_count": 2,
            "added_count": 0,
            "deferred_count": 1,
            "pattern_count": 2,
            "harmful_pattern_count": 1,
            "harmless_pattern_count": 1,
            "unreviewed_pattern_count": 0,
        },
        "wave_sibling_top_level": "accepted",
    }


@contextmanager
def _no_jsonschema():
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "jsonschema" or name.startswith("jsonschema."):
            raise ImportError("jsonschema blocked for structural-fallback test")
        return real_import(name, *args, **kwargs)

    with mock.patch.object(builtins, "__import__", side_effect=_fake_import):
        yield


class TestRoundtripReportSchema(unittest.TestCase):
    def test_valid_fixture_passes_jsonschema_path(self):
        errors = vrr.validate_report_doc(_valid_report())
        self.assertEqual(errors, [], errors)

    def test_valid_fixture_passes_structural_fallback(self):
        with _no_jsonschema():
            errors = vrr.validate_report_doc(_valid_report())
        self.assertEqual(errors, [], errors)

    def test_structural_fallback_direct_call(self):
        errors = vrr.validate_report_structural(_valid_report())
        self.assertEqual(errors, [], errors)

    def test_forward_compat_extra_fields_accepted(self):
        doc = _valid_report()
        doc["extra_top_level"] = {"nested_unknown": 42}
        doc["kind_buckets"]["INSERT"]["future_metric"] = 99
        doc["patterns"][0]["extra_pattern_field"] = True
        doc["patterns"][0]["signature"]["extra_sig"] = "ok"
        doc["totals"]["future_total"] = 1
        self.assertEqual(vrr.validate_report_doc(doc), [])
        with _no_jsonschema():
            self.assertEqual(vrr.validate_report_doc(doc), [])

    def test_wrong_schema_id_rejected(self):
        doc = _valid_report()
        doc["schema"] = "ariadne.roundtrip_report.v0"
        errors = vrr.validate_report_doc(doc)
        self.assertTrue(errors)
        joined = " ".join(errors).lower()
        self.assertIn("schema", joined)

    def test_kind_bucket_bad_status_rejected(self):
        doc = _valid_report()
        doc["kind_buckets"]["INSERT"]["status"] = "OK"
        errors = vrr.validate_report_doc(doc)
        self.assertTrue(errors)
        joined = " ".join(errors)
        self.assertTrue(
            any("status" in err and "INSERT" in err for err in errors)
            or any("kind_buckets" in err and "status" in err for err in errors),
            msg=errors,
        )

    def test_pattern_bad_judgment_rejected(self):
        doc = _valid_report()
        doc["patterns"][0]["judgment"] = "fine"
        errors = vrr.validate_report_doc(doc)
        self.assertTrue(errors)
        joined = " ".join(errors)
        self.assertTrue(
            any("judgment" in err for err in errors),
            msg=joined,
        )

    def test_negative_count_rejected(self):
        doc = _valid_report()
        doc["patterns"][0]["count"] = -1
        errors = vrr.validate_report_doc(doc)
        self.assertTrue(errors)
        self.assertTrue(any("count" in err for err in errors), msg=errors)

    def test_structural_fallback_rejects_same_invalid_docs(self):
        cases = [
            ("schema", lambda d: d.update({"schema": "wrong.id"})),
            ("status", lambda d: d["kind_buckets"]["INSERT"].update({"status": "OK"})),
            ("judgment", lambda d: d["patterns"][0].update({"judgment": "fine"})),
            ("count", lambda d: d["patterns"][0].update({"count": -5})),
        ]
        for label, mutate in cases:
            doc = copy.deepcopy(_valid_report())
            mutate(doc)
            with _no_jsonschema():
                errors = vrr.validate_report_doc(doc)
            self.assertTrue(errors, f"structural fallback should reject bad {label}")

    def test_cli_validate_exit_codes(self):
        doc = _valid_report()
        with tempfile.TemporaryDirectory() as td:
            good_path = os.path.join(td, "good.json")
            bad_path = os.path.join(td, "bad.json")
            with open(good_path, "w", encoding="utf-8") as fh:
                json.dump(doc, fh)
            bad = copy.deepcopy(doc)
            bad["schema"] = "ariadne.roundtrip_report.v0"
            with open(bad_path, "w", encoding="utf-8") as fh:
                json.dump(bad, fh)

            self.assertEqual(vrr.main(["validate", good_path]), 0)
            self.assertEqual(vrr.main(["validate", bad_path]), 2)


if __name__ == "__main__":
    unittest.main()
