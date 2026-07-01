#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WAVE-0 F6 TEST -- extraction_coverage.build_report: per-kind FULL/PARTIAL/EMPTY meter.

Intent (WHY):
  * extraction_coverage.py buckets entities by geometry.kind and classifies each
    bucket FULL / PARTIAL / EMPTY. This is the meter that drives T3a's extraction
    punch-list and seeds the per-kind FULL/empty gate T17 freezes against -- if
    its classification logic is wrong, the punch-list is wrong and T3a triages
    the wrong kinds first.
  * The single hard fact this tool must never get wrong: on the real M4 sample
    IR, the ``dimension`` bucket (113 AcDbRotatedDimension entities, each with
    bare ``geometry: {"kind": "dimension"}`` and no coordinate payload) MUST
    report status "empty" -- this is a KNOWN, EXPECTED extraction gap (plan
    risk H-R2 "Dimension double-gap"), not a bug to be smoothed over. A build
    that reports dimension as anything but empty would fake T3a's punch-list
    (Rule 12: no fake success).
  * Per-entity classification must genuinely distinguish full / partial / empty
    (Rule 9: a test that can't fail when the classification logic changes is
    worthless) -- covered with synthetic entities whose answer is known exactly,
    independent of any external fixture.
  * Two layers of evidence (mirrors test_ir_builder.py's synthetic+live split):
    a synthetic in-memory IR (deterministic, always runs) proving the
    classification + aggregation logic; the REAL M4 sample IR (present on this
    box) exercising the literal accept criterion. If the sample is ever absent
    (fresh clone without the shared .build scratch dir) that piece SKIPS with an
    explicit reason -- it never silently passes.

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

import extraction_coverage as ec  # noqa: E402  (after sys.path setup, matches sibling tests)

# The M4 measure-phase sample IR the F6 packet names explicitly. Computed as
# two levels above the repo root (D:\dev\99_tools\<worktree>\..\..) so the path
# resolves the same from any worktree checkout, exactly as the packet phrased
# it (``autocad-sdk-router\..\..\.build\...``).
_DEV_ROOT = os.path.dirname(os.path.dirname(_REPO))
_M4_SAMPLE_IR = os.path.join(_DEV_ROOT, ".build", "cados_plan", "measure",
                              "m4_inspect", "dwg_graph_ir.json")


def _entity(handle, kind, **geom_fields):
    """A minimal synthetic IR entity with just enough shape to classify."""
    geom = {"kind": kind}
    geom.update(geom_fields)
    return {"handle": handle, "class": "AcDbEntity", "dxf_name": kind.upper(),
            "owner_handle": "1", "space": "model", "layer": "0", "bbox": [],
            "geometry": geom}


def _synthetic_ir(entities):
    return {
        "schema": ec.IR_SCHEMA_ID,
        "entities": entities,
        "diagnostics": {"entity_count": len(entities)},
    }


class TestClassifyEntity(unittest.TestCase):
    """Per-entity full/partial/empty classification (the core logic)."""

    def test_line_with_start_and_end_is_full(self):
        e = _entity("1", "line", start=[0.0, 0.0, 0.0], end=[1.0, 0.0, 0.0])
        self.assertEqual(ec.classify_entity(e), ec.STATUS_FULL)

    def test_line_missing_end_is_partial(self):
        e = _entity("2", "line", start=[0.0, 0.0, 0.0])
        self.assertEqual(ec.classify_entity(e), ec.STATUS_PARTIAL)

    def test_line_with_no_anchor_fields_is_empty(self):
        e = _entity("3", "line")
        self.assertEqual(ec.classify_entity(e), ec.STATUS_EMPTY)

    def test_lwpolyline_requires_nonempty_vertices(self):
        full = _entity("4", "lwpolyline", vertices=[{"point": [0.0, 0.0, 0.0]}])
        empty_list = _entity("5", "lwpolyline", vertices=[])
        missing = _entity("6", "lwpolyline")
        self.assertEqual(ec.classify_entity(full), ec.STATUS_FULL)
        self.assertEqual(ec.classify_entity(empty_list), ec.STATUS_EMPTY)
        self.assertEqual(ec.classify_entity(missing), ec.STATUS_EMPTY)

    def test_block_reference_with_position_is_full(self):
        e = _entity("7", "block_reference", position=[1.0, 2.0, 0.0], block_name="DOOR")
        self.assertEqual(ec.classify_entity(e), ec.STATUS_FULL)

    def test_circle_center_present_radius_irrelevant_to_status(self):
        # center is circle's wired anchor (matches validate_dwg_geometry_extract.py);
        # radius is real extractor output but not part of the anchor contract.
        with_radius = _entity("8", "circle", center=[0.0, 0.0, 0.0], radius=2.5)
        without_radius = _entity("9", "circle", center=[0.0, 0.0, 0.0])
        self.assertEqual(ec.classify_entity(with_radius), ec.STATUS_FULL)
        self.assertEqual(ec.classify_entity(without_radius), ec.STATUS_FULL)

    def test_dimension_is_always_empty_even_with_stray_fields(self):
        """dimension has zero wired anchor fields (H-R2); a bare {"kind":...} or
        one carrying an incidental stray field (e.g. a future 'measurement' the
        plan explicitly forbids as the discriminator, G13) must both read empty."""
        bare = _entity("10", "dimension")
        with_measurement = _entity("11", "dimension", measurement=42.0)
        self.assertEqual(ec.classify_entity(bare), ec.STATUS_EMPTY)
        self.assertEqual(ec.classify_entity(with_measurement), ec.STATUS_EMPTY)

    def test_unsupported_kind_is_empty(self):
        e = _entity("12", "unsupported")
        self.assertEqual(ec.classify_entity(e), ec.STATUS_EMPTY)

    def test_unknown_kind_not_in_schema_enum_falls_back_to_empty(self):
        e = _entity("13", "totally_made_up_kind", position=[0.0, 0.0, 0.0])
        self.assertEqual(ec.classify_entity(e), ec.STATUS_EMPTY)

    def test_missing_geometry_key_is_empty(self):
        e = {"handle": "14", "class": "AcDbEntity"}
        self.assertEqual(ec.classify_entity(e), ec.STATUS_EMPTY)

    def test_non_dict_geometry_is_empty(self):
        e = {"handle": "15", "geometry": "not-a-dict"}
        self.assertEqual(ec.classify_entity(e), ec.STATUS_EMPTY)


class TestBuildReport(unittest.TestCase):
    """Bucketing + aggregation over a small synthetic multi-kind IR."""

    def setUp(self):
        self.entities = [
            _entity("A1", "line", start=[0.0, 0.0, 0.0], end=[1.0, 0.0, 0.0]),
            _entity("A2", "line", start=[0.0, 0.0, 0.0], end=[2.0, 0.0, 0.0]),
            _entity("A3", "line", start=[0.0, 0.0, 0.0]),  # partial (no end)
            _entity("B1", "block_reference", position=[1.0, 2.0, 0.0]),
            _entity("D1", "dimension"),
            _entity("D2", "dimension"),
            _entity("U1", "unsupported"),
        ]
        self.ir = _synthetic_ir(self.entities)

    def test_bucket_counts_and_status_per_kind(self):
        report = ec.build_report(self.ir, source_path="synthetic.json")
        buckets = report["buckets"]

        line = buckets["line"]
        self.assertEqual(line["count"], 3)
        self.assertEqual(line["full"], 2)
        self.assertEqual(line["partial"], 1)
        self.assertEqual(line["empty"], 0)
        self.assertEqual(line["status"], ec.STATUS_PARTIAL)
        self.assertIn("A3", line["sample_incomplete_handles"])

        block_ref = buckets["block_reference"]
        self.assertEqual(block_ref["status"], ec.STATUS_FULL)
        self.assertEqual(block_ref["sample_incomplete_handles"], [])

        dimension = buckets["dimension"]
        self.assertEqual(dimension["count"], 2)
        self.assertEqual(dimension["full"], 0)
        self.assertEqual(dimension["empty"], 2)
        self.assertEqual(dimension["status"], ec.STATUS_EMPTY)
        self.assertEqual(dimension["anchor_fields"], [])

        unsupported = buckets["unsupported"]
        self.assertEqual(unsupported["status"], ec.STATUS_EMPTY)

    def test_unrecognized_kind_is_flagged_distinctly_from_wired_gaps(self):
        """A kind outside the IR schema's own enum (a catalog gap, H-R32) must be
        surfaced separately from a recognized-but-unwired kind like dimension."""
        ir = _synthetic_ir(self.entities + [_entity("X1", "brand_new_kind")])
        report = ec.build_report(ir)
        self.assertEqual(report["unrecognized_kinds"], ["brand_new_kind"])
        self.assertNotIn("dimension", report["unrecognized_kinds"])

    def test_totals_rollup(self):
        report = ec.build_report(self.ir)
        totals = report["totals"]
        self.assertEqual(totals["full"], 3)   # A1, A2, B1
        self.assertEqual(totals["partial"], 1)  # A3
        self.assertEqual(totals["empty"], 3)   # D1, D2, U1
        self.assertEqual(totals["kinds_empty"], ["dimension", "unsupported"])
        self.assertEqual(totals["kinds_partial"], ["line"])
        self.assertEqual(totals["kinds_full"], ["block_reference"])

    def test_entity_count_and_schema(self):
        report = ec.build_report(self.ir)
        self.assertEqual(report["schema"], ec.SCHEMA_ID)
        self.assertEqual(report["entity_count"], len(self.entities))
        self.assertTrue(report["diagnostics_entity_count_match"])

    def test_buckets_are_sorted_by_kind_regardless_of_encounter_order(self):
        shuffled = list(reversed(self.entities))
        report = ec.build_report(_synthetic_ir(shuffled))
        self.assertEqual(list(report["buckets"].keys()), sorted(report["buckets"].keys()))

    def test_deterministic_rerun_is_byte_identical(self):
        r1 = ec.build_report(self.ir, source_path="x.json")
        r2 = ec.build_report(self.ir, source_path="x.json")
        self.assertEqual(json.dumps(r1, sort_keys=True), json.dumps(r2, sort_keys=True))

    def test_empty_entities_list_yields_no_buckets(self):
        report = ec.build_report(_synthetic_ir([]))
        self.assertEqual(report["buckets"], {})
        self.assertEqual(report["entity_count"], 0)

    def test_diagnostics_mismatch_is_surfaced_not_hidden(self):
        ir = _synthetic_ir(self.entities)
        ir["diagnostics"]["entity_count"] = len(self.entities) + 1
        report = ec.build_report(ir)
        self.assertFalse(report["diagnostics_entity_count_match"])


class TestMainCli(unittest.TestCase):
    """The CLI entrypoint: load -> build_report -> print (+ optional --out)."""

    def test_main_writes_report_to_out_path(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = os.path.join(tmp, "ir.json")
            out_path = os.path.join(tmp, "coverage.json")
            with open(ir_path, "w", encoding="utf-8") as fh:
                json.dump(_synthetic_ir([_entity("Z1", "dimension")]), fh)

            rc = ec.main([ir_path, "--out", out_path])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isfile(out_path))
            with open(out_path, "r", encoding="utf-8") as fh:
                written = json.load(fh)
            self.assertEqual(written["buckets"]["dimension"]["status"], ec.STATUS_EMPTY)

    def test_main_returns_1_on_missing_file(self):
        rc = ec.main([os.path.join(_THIS, "no_such_ir_file.json")])
        self.assertEqual(rc, 1)


class TestM4SampleAcceptance(unittest.TestCase):
    """The F6 packet's literal accept criterion, against the real M4 sample IR.

    "on run_01 IR reports the known-empty buckets (dimension=empty [V])"
    (D:\\dev\\.build\\cados_plan\\final\\PLAN.md, node F6). Skips (never fails)
    if the shared .build scratch artifact is absent from this checkout.
    """

    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(_M4_SAMPLE_IR):
            raise unittest.SkipTest(
                "M4 sample IR not present at %s (shared .build scratch dir "
                "absent from this checkout) -- skipping live-sample assertion, "
                "never faking it" % _M4_SAMPLE_IR)
        cls.report = ec.build_report(ec.load_ir(_M4_SAMPLE_IR), source_path=_M4_SAMPLE_IR)

    def test_dimension_bucket_reports_empty(self):
        dimension = self.report["buckets"]["dimension"]
        self.assertEqual(dimension["status"], ec.STATUS_EMPTY)
        self.assertEqual(dimension["full"], 0)
        self.assertEqual(dimension["partial"], 0)
        self.assertEqual(dimension["count"], 113)
        self.assertEqual(dimension["empty"], 113)

    def test_known_wired_kinds_report_full(self):
        # Proves the meter isn't just reporting everything empty -- these 5
        # kinds' anchors ARE wired on this sample and must read full.
        for kind in ("line", "circle", "text", "lwpolyline", "block_reference"):
            with self.subTest(kind=kind):
                self.assertEqual(self.report["buckets"][kind]["status"], ec.STATUS_FULL)
                self.assertEqual(self.report["buckets"][kind]["partial"], 0)
                self.assertEqual(self.report["buckets"][kind]["empty"], 0)

    def test_entity_count_matches_known_sample_size(self):
        self.assertEqual(self.report["entity_count"], 375)
        self.assertTrue(self.report["diagnostics_entity_count_match"])

    def test_totals_kinds_empty_includes_dimension(self):
        self.assertIn("dimension", self.report["totals"]["kinds_empty"])


if __name__ == "__main__":
    unittest.main()
