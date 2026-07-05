#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer WAVE-0 F0 TEST -- catalog-completeness meter.

Intent (WHY):
  F0 (tools/catalog_completeness.py) exists because R3_coverage.md finding G0
  proved the plan's "~446 legitimate parity targets" denominator is measured
  against a 517-op catalog that OMITS whole AcDbEntity/AcDbObject classes
  present in ordinary production DWGs (viewport/group/field/underlay/... all
  measured 0 catalog ops that session). The fix is a forced disposition on
  EVERY observed class -- never a silent omission. These tests encode that
  contract at two levels:

    1. The op-level denominator formula (compute_catalog_denominator) is
       proven against a hand-built synthetic registry so the subtraction
       logic itself is pinned -- a synthetic case is used (not just the live
       517-op registry) because PLAN.md explicitly says the derived
       "~446" figure "jitters +/-1 -- never hard-code"; a test that hardcoded
       today's live 447 would be asserting a snapshot, not the formula.
    2. The class-level disposition-forcing (disposition_for / run) is proven
       against both the REAL sample IR named by the F0 task
       (`.build/cados_plan/measure/m4_inspect/dwg_graph_ir.json`, gated with a
       graceful skip if that machine-local artifact is absent -- the same
       "skip if live artifact missing, never fake" convention
       test_dwg_graph_ir_schema.py already uses for runs/ fixtures) and a
       synthetic IR that deliberately injects an uncatalogued class WITH a
       curated R3 disposition (AcDbViewport), an uncatalogued class WITHOUT
       one (forcing the default fallback, flagged needs_review), and a
       proxy custom_object (G8). A test that only fed already-catalogued
       classes could never fail if the forcing logic silently became a no-op.

Stdlib only; BOM-tolerant (utf-8-sig read, the registry's own encoding).
Discoverable by pytest and ``python -m unittest discover -s tests``.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import catalog_completeness as cc  # noqa: E402

# The F0 task's named sample IR ("Sample IR to test against"). It lives outside
# this repo, under the work-root's shared `.build/` planning tree, so it is
# derived relative to the work-root (two levels above ANY sibling worktree of
# this repo -- D:\dev\99_tools\<worktree-name>\..\.. == D:\dev regardless of
# which worktree is checked out) rather than hardcoded as an absolute string.
_WORK_ROOT = Path(_REPO).resolve().parent.parent
_SAMPLE_IR = _WORK_ROOT / ".build" / "cados_plan" / "measure" / "m4_inspect" / "dwg_graph_ir.json"

_SAMPLE_EXPECTED_CLASSES = {
    "AcDbBlockReference": "INSERT",
    "AcDbCircle": "CIRCLE",
    "AcDbLine": "LINE",
    "AcDbPolyline": "LWPOLYLINE",
    "AcDbRotatedDimension": "DIMENSION",
    "AcDbText": "TEXT",
}


def _write_ir(tmp_dir: str, name: str, ir: dict) -> str:
    path = os.path.join(tmp_dir, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ir, fh, ensure_ascii=False)
    return path


def _minimal_entity(handle, class_name, dxf_name, **extra):
    e = {
        "handle": handle, "class": class_name, "dxf_name": dxf_name,
        "owner_handle": "", "space": "model", "layer": "0",
        "bbox": [], "geometry": {}, "source": {"extractor": "fixture", "decoded": True},
    }
    e.update(extra)
    return e


class TestCatalogDenominatorFormula(unittest.TestCase):
    """The subtraction formula, pinned against a controlled synthetic registry
    (never the live one -- PLAN.md: the derived figure jitters, the FORMULA
    must not)."""

    def test_formula_on_synthetic_ops(self):
        ops = [
            {"id": "entities.write.a", "status": "implemented", "family": "entities"},
            {"id": "entities.write.b", "status": "implemented", "family": "entities"},
            {"id": "entities.blocked.c", "status": "blocked", "family": "entities"},
            {"id": "doc.write_original.d", "status": "implemented",
             "family": "active_document_write_original"},
            {"id": "automate.com.e", "status": "implemented", "family": "com_activex"},
            {"id": "automate.com.f", "status": "blocked", "family": "com_activex"},
            {"id": "extend.opm.g", "status": "implemented", "family": "com_activex"},
        ]
        denom = cc.compute_catalog_denominator(ops)
        self.assertEqual(denom["total_catalogued_ops"], 7)
        self.assertEqual(denom["hard_blocked"], 2)  # entities.blocked.c + automate.com.f
        self.assertEqual(denom["write_original_charter_forbidden"], 1)  # doc.write_original.d
        # only the "automate." prefix counts as session-bound COM automation --
        # extend.opm.g (same com_activex family, catalog-only classification) must NOT.
        self.assertEqual(denom["com_activex_session_bound_estimate"], 1)  # automate.com.e
        self.assertEqual(denom["catalog_parity_targets"], 7 - 2 - 1 - 1)
        self.assertEqual(denom["catalog_parity_targets"], 3)

    def test_formula_excludes_extend_and_inspect_com_activex_ops(self):
        # A family == com_activex op NOT under the "automate." id prefix must
        # never be counted as session-bound automation, regardless of status.
        ops = [{"id": "inspect.property.by_name", "status": "implemented", "family": "com_activex"}]
        denom = cc.compute_catalog_denominator(ops)
        self.assertEqual(denom["com_activex_session_bound_estimate"], 0)
        self.assertEqual(denom["catalog_parity_targets"], 1)

    def test_denominator_never_hardcodes_a_final_number(self):
        # the summary must show its work (formula + source), not just a number,
        # so a reader can recompute it -- PLAN.md's "never hard-code" applies to
        # the OUTPUT contract, not just the implementation.
        denom = cc.compute_catalog_denominator([])
        self.assertIn("formula", denom)
        self.assertIn("source", denom)
        self.assertEqual(denom["catalog_parity_targets"], 0)


class TestCatalogDenominatorLiveSmoke(unittest.TestCase):
    """A loose-bound integration smoke against the real, live registry -- the
    517-op total is the F0 task's own pinned anchor (repeated throughout
    PLAN.md/R3_coverage.md as "the 517-op catalogue"), but the DERIVED parity
    figure is asserted only within a wide, documented neighborhood of PLAN.md's
    "~446" estimate, never pinned exactly (that number is explicitly provisional)."""

    def test_live_registry_is_517_ops(self):
        # w3-dimstyle adds one new synthetic op (write.dimstyle.create,
        # DIMSTYLE table D-class TABLES tier) on top of the F0 517-op
        # anchor -- 517 -> 518. See tools/patch_ops/tables.py. P10 adds a
        # second new synthetic op (modify.entity.xdata, entity-handle-
        # targeted xdata write) -- 518 -> 519. See tools/patch_ops/entities.py.
        ops = cc.load_operations_catalog()
        self.assertEqual(len(ops), 519,
                         "the F0 task's own '517-op catalogue' anchor (+2, "
                         "w3-dimstyle and P10); if this moves again, the whole "
                         "WAVE-0 accounting must be recomputed")

    def test_live_denominator_lands_near_plan_446_estimate(self):
        ops = cc.load_operations_catalog()
        denom = cc.compute_catalog_denominator(ops)
        self.assertEqual(denom["total_catalogued_ops"], len(ops))
        self.assertTrue(430 <= denom["catalog_parity_targets"] <= 460,
                        "parity_targets {0} far outside PLAN.md's ~446 neighborhood "
                        "(+/-1 jitter is expected, not this)".format(
                            denom["catalog_parity_targets"]))


class TestObservedClassCollection(unittest.TestCase):
    """collect_observed_classes must walk every place the schema allows a
    class/dxf_name pair to live: top-level entities[], block_definitions[]
    .def_entities (the alternate inlined-block strategy), and custom_objects[]
    (the dedicated proxy/custom-object record)."""

    def test_collects_top_level_entities(self):
        ir = {"schema": cc.IR_SCHEMA_ID, "entities": [
            _minimal_entity("1", "AcDbLine", "LINE"),
            _minimal_entity("2", "AcDbLine", "LINE"),
        ]}
        observed = cc.collect_observed_classes([(Path("f.json"), ir)])
        self.assertEqual(set(observed), {"AcDbLine"})
        self.assertEqual(observed["AcDbLine"]["observed_count"], 2)
        self.assertEqual(observed["AcDbLine"]["dxf_names"], {"LINE"})

    def test_collects_inlined_block_definition_entities(self):
        ir = {"schema": cc.IR_SCHEMA_ID, "entities": [],
              "block_definitions": [{"handle": "B1", "name": "BLOCK1", "def_entities": [
                  _minimal_entity("5", "AcDbCircle", "CIRCLE"),
              ]}]}
        observed = cc.collect_observed_classes([(Path("f.json"), ir)])
        self.assertEqual(set(observed), {"AcDbCircle"})
        self.assertIn("entities", observed["AcDbCircle"]["sources"])

    def test_collects_custom_objects_and_proxy_flag(self):
        ir = {"schema": cc.IR_SCHEMA_ID, "entities": [],
              "custom_objects": [
                  {"handle": "6", "class_name": "AcDbProxyEntity",
                   "dxf_name": "ACAD_PROXY_ENTITY", "is_proxy": True},
              ]}
        observed = cc.collect_observed_classes([(Path("f.json"), ir)])
        self.assertEqual(set(observed), {"AcDbProxyEntity"})
        self.assertTrue(observed["AcDbProxyEntity"]["is_proxy"])
        self.assertIn("custom_objects", observed["AcDbProxyEntity"]["sources"])

    def test_missing_class_field_never_silently_dropped(self):
        ir = {"schema": cc.IR_SCHEMA_ID, "entities": [
            _minimal_entity("9", "", "MYSTERYTHING"),
        ]}
        observed = cc.collect_observed_classes([(Path("f.json"), ir)])
        self.assertEqual(len(observed), 1)
        key = next(iter(observed))
        self.assertTrue(key.startswith("UNKNOWN_CLASS:"))
        self.assertIn("MYSTERYTHING", key)


class TestCataloguedMatching(unittest.TestCase):
    """The literal-class-name-substring matching rule, validated against the
    live registry so a regression in the match rule (e.g. reverting to a bare
    keyword search) is caught."""

    @classmethod
    def setUpClass(cls):
        ops = cc.load_operations_catalog()
        cls.text_index = cc.build_catalog_text_index([("config/operations.v2.json", ops)])

    def test_common_entity_classes_are_catalogued(self):
        for cls_name in ("AcDbLine", "AcDbCircle", "AcDbPolyline", "AcDbText",
                         "AcDbBlockReference", "AcDbRotatedDimension"):
            hits = cc.catalogued_by(cls_name, self.text_index)
            self.assertGreater(len(hits), 0, "{0} expected catalogued".format(cls_name))

    def test_r3_g0_classes_are_uncatalogued(self):
        # R3_coverage.md G0 (measured live, HEAD 543ae61): these AcDb classes
        # had 0 matching catalog ops. A regression here means either the
        # catalog gained real coverage (update the seed table) or the match
        # rule broke (false catalogued).
        for cls_name in ("AcDbViewport", "AcDbGroup", "AcDbField", "AcDbHelix",
                         "AcDbPointCloud", "AcDbSection"):
            hits = cc.catalogued_by(cls_name, self.text_index)
            self.assertEqual(hits, [], "{0} expected uncatalogued per R3 G0".format(cls_name))

    def test_empty_class_name_never_vacuously_matches(self):
        self.assertEqual(cc.catalogued_by("", self.text_index), [])
        self.assertEqual(cc.catalogued_by("UNKNOWN_CLASS:X", self.text_index), [])

    def test_bare_keyword_false_positive_is_not_repeated(self):
        # R3's own coarse "id contains 'viewport'" search found 2 unrelated
        # hits (render.draw.viewportgeom / extend.customentity.draw_viewport).
        # The exact-class-name rule must NOT count those as AcDbViewport coverage.
        hits = cc.catalogued_by("AcDbViewport", self.text_index)
        self.assertEqual(hits, [])


class TestDispositionForcing(unittest.TestCase):
    """Every observed class gets exactly one of DISPOSITIONS -- never None,
    never a 4th value, never silently skipped."""

    def test_catalogued_class_gets_author_with_catalogued_basis(self):
        d = cc.disposition_for("AcDbLine", ["LINE"], [{"source": "x", "op_id": "write.entity.line"}], False)
        self.assertEqual(d["disposition"], "author")
        self.assertEqual(d["disposition_basis"], "catalogued")
        self.assertFalse(d["needs_review"])

    def test_seeded_uncatalogued_class_gets_curated_disposition(self):
        d = cc.disposition_for("AcDbViewport", ["VIEWPORT"], [], False)
        self.assertEqual(d["disposition"], "author")
        self.assertTrue(d["disposition_basis"].startswith("known_uncatalogued_seed:"))
        self.assertFalse(d["needs_review"])

    def test_proxy_class_gets_non_goal_preserve(self):
        d = cc.disposition_for("AcDbProxyEntity", ["ACAD_PROXY_ENTITY"], [], False)
        self.assertEqual(d["disposition"], "non-goal-preserve")

    def test_ole_class_gets_non_goal_preserve_not_author(self):
        d = cc.disposition_for("AcDbOle2Frame", ["OLE2FRAME"], [], False)
        self.assertEqual(d["disposition"], "non-goal-preserve")

    def test_is_proxy_flag_forces_non_goal_preserve_even_without_seed_match(self):
        d = cc.disposition_for("AcDbSomeVendorCustomThing", ["VENDORTHING"], [], True)
        self.assertEqual(d["disposition"], "non-goal-preserve")
        self.assertEqual(d["disposition_basis"], "custom_object_is_proxy_flag")

    def test_unknown_uncatalogued_class_gets_forced_default_flagged_for_review(self):
        d = cc.disposition_for("AcDbTotallyNovelWidget", ["NOVELWIDGET"], [], False)
        self.assertIn(d["disposition"], cc.DISPOSITIONS)
        self.assertEqual(d["disposition_basis"], "default_uncatalogued_fallback")
        self.assertTrue(d["needs_review"])

    def test_disposition_always_in_closed_vocabulary(self):
        cases = [
            ("AcDbLine", ["LINE"], [{"source": "x", "op_id": "y"}], False),
            ("AcDbViewport", ["VIEWPORT"], [], False),
            ("AcDbProxyEntity", ["ACAD_PROXY_ENTITY"], [], False),
            ("AcDbNovel", ["NOVEL"], [], False),
            ("UNKNOWN_CLASS:X", [], [], False),
        ]
        for class_name, dxf_names, matched, is_proxy in cases:
            d = cc.disposition_for(class_name, dxf_names, matched, is_proxy)
            self.assertIn(d["disposition"], cc.DISPOSITIONS, class_name)


class TestRunPipelineSynthetic(unittest.TestCase):
    """End-to-end run() against a synthetic corpus exercising every branch:
    an already-catalogued class, a seeded-uncatalogued class, an unseeded
    (default-fallback) uncatalogued class, and a proxy custom_object -- a test
    that only fed catalogued classes could never catch a broken forcing rule."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        ir = {
            "schema": cc.IR_SCHEMA_ID,
            "entities": [
                _minimal_entity("1", "AcDbLine", "LINE"),
                _minimal_entity("2", "AcDbViewport", "VIEWPORT"),
                _minimal_entity("3", "AcDbTotallyNovelWidget", "NOVELWIDGET"),
            ],
            "custom_objects": [
                {"handle": "4", "class_name": "AcDbProxyEntity",
                 "dxf_name": "ACAD_PROXY_ENTITY", "is_proxy": True},
            ],
        }
        self.ir_path = _write_ir(self._tmp.name, "synthetic_ir.json", ir)
        self.result = cc.run([self.ir_path])

    def test_all_four_classes_observed(self):
        classes = {r["class"] for r in self.result["rows"]}
        self.assertEqual(classes, {"AcDbLine", "AcDbViewport", "AcDbTotallyNovelWidget",
                                    "AcDbProxyEntity"})

    def test_every_row_has_a_forced_disposition(self):
        for row in self.result["rows"]:
            self.assertIn(row["disposition"], cc.DISPOSITIONS, row["class"])

    def test_catalogued_vs_uncatalogued_split_is_correct(self):
        by_class = {r["class"]: r for r in self.result["rows"]}
        self.assertTrue(by_class["AcDbLine"]["catalogued"])
        self.assertFalse(by_class["AcDbViewport"]["catalogued"])
        self.assertFalse(by_class["AcDbTotallyNovelWidget"]["catalogued"])
        self.assertFalse(by_class["AcDbProxyEntity"]["catalogued"])

    def test_summary_counts_and_gate(self):
        s = self.result["summary"]
        self.assertEqual(s["observed_class_count"], 4)
        self.assertEqual(s["catalogued_class_count"], 1)
        self.assertEqual(s["uncatalogued_class_count"], 3)
        self.assertEqual(s["denominator"]["uncatalogued_class_count_U"], 3)
        self.assertTrue(s["gate"]["every_observed_class_has_disposition"])
        self.assertTrue(s["gate"]["no_class_silently_omitted"])
        self.assertEqual(s["missing_disposition"], [])
        self.assertIn("AcDbTotallyNovelWidget", s["classes_needing_review"])
        self.assertNotIn("AcDbViewport", s["classes_needing_review"])

    def test_denominator_annotated_with_uncatalogued_set_u(self):
        # PLAN.md section 2.6 / the F0 task: "annotate the 446 denominator with
        # the uncatalogued set U" -- the summary must literally show both
        # numbers together, not just the raw op-level denominator.
        annotated = self.result["summary"]["denominator"]["catalog_parity_denominator_annotated"]
        self.assertIn("U(3)", annotated)


class TestCorpusDiscoveryAndSkip(unittest.TestCase):
    """Directory scanning must find real IR files and skip (never crash on)
    unrelated or malformed json files."""

    def test_directory_scan_finds_ir_and_skips_non_ir_json(self):
        with tempfile.TemporaryDirectory() as d:
            _write_ir(d, "a_dwg_graph_ir.json",
                      {"schema": cc.IR_SCHEMA_ID, "entities": [_minimal_entity("1", "AcDbLine", "LINE")]})
            with open(os.path.join(d, "unrelated.json"), "w", encoding="utf-8") as fh:
                json.dump({"not_an_ir": True}, fh)
            with open(os.path.join(d, "broken.json"), "w", encoding="utf-8") as fh:
                fh.write("{not valid json")

            ir_docs, skipped = cc.load_corpus([d])
            self.assertEqual(len(ir_docs), 1)
            self.assertEqual(len(skipped), 2)
            reasons = {s["reason"].split(":")[0] for s in skipped}
            self.assertIn("not_a_dwg_graph_ir_document", reasons)
            self.assertIn("json_parse_error", reasons)

    def test_missing_corpus_path_raises_not_silently_ignored(self):
        with self.assertRaises(FileNotFoundError):
            cc.discover_corpus_files([r"D:\this\path\does\not\exist\anywhere"])


class TestWriteReportsToDisk(unittest.TestCase):
    """DISK-FIRST artifacts: measure/uncatalogued_classes.jsonl (one json object
    per line, one per observed class) + measure/catalog_completeness_summary.json."""

    def test_writes_valid_jsonl_and_summary_json(self):
        ir = {"schema": cc.IR_SCHEMA_ID, "entities": [_minimal_entity("1", "AcDbLine", "LINE")]}
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as out_dir:
            ir_path = _write_ir(src_dir, "ir.json", ir)
            result = cc.run([ir_path])
            jsonl_path, summary_path = cc.write_reports(result, out_dir=Path(out_dir))

            self.assertEqual(jsonl_path.name, "uncatalogued_classes.jsonl")
            self.assertEqual(summary_path.name, "catalog_completeness_summary.json")
            self.assertTrue(jsonl_path.exists())
            self.assertTrue(summary_path.exists())

            rows = [json.loads(line) for line in
                    jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["class"], "AcDbLine")
            self.assertIn(rows[0]["disposition"], cc.DISPOSITIONS)

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["schema"], "ariadne.cad_os.f0_catalog_completeness_summary.v1")
            self.assertTrue(summary["gate"]["every_observed_class_has_disposition"])


class TestCLIMain(unittest.TestCase):
    def test_main_writes_reports_and_returns_0_when_gate_passes(self):
        ir = {"schema": cc.IR_SCHEMA_ID, "entities": [_minimal_entity("1", "AcDbLine", "LINE")]}
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as out_dir:
            ir_path = _write_ir(src_dir, "ir.json", ir)
            rc = cc.main([ir_path, "--out-dir", out_dir])
            self.assertEqual(rc, 0)
            self.assertTrue((Path(out_dir) / cc.OUT_FILENAME).exists())
            self.assertTrue((Path(out_dir) / cc.SUMMARY_FILENAME).exists())


@unittest.skipUnless(_SAMPLE_IR.exists(),
                      "SKIPPED_FIXTURE: F0 sample IR not present: {0}".format(_SAMPLE_IR))
class TestSampleIRFromTask(unittest.TestCase):
    """The exact sample the F0 task names: 'Sample IR to test against:
    .../.build/cados_plan/measure/m4_inspect/dwg_graph_ir.json'. Skips (never
    fakes a pass) when the machine-local artifact is absent, matching
    test_dwg_graph_ir_schema.py's existing convention for runs/ fixtures."""

    @classmethod
    def setUpClass(cls):
        cls.result = cc.run([str(_SAMPLE_IR)])

    def test_observed_classes_match_the_known_pilot_histogram(self):
        by_class = {r["class"]: r for r in self.result["rows"]}
        self.assertEqual(set(by_class), set(_SAMPLE_EXPECTED_CLASSES))
        for class_name, dxf_name in _SAMPLE_EXPECTED_CLASSES.items():
            self.assertEqual(by_class[class_name]["dxf_names"], [dxf_name], class_name)

    def test_every_class_has_a_forced_disposition(self):
        for row in self.result["rows"]:
            self.assertIn(row["disposition"], cc.DISPOSITIONS, row["class"])

    def test_pilot_corpus_classes_are_all_already_catalogued(self):
        # R3_coverage.md: "375/375 on test.dws is a model-space entity PILOT,
        # not full read+write parity" -- this pilot corpus only exercises
        # already-catalogued common entity classes; it does NOT prove U == 0
        # in general (a richer corpus with viewports/groups/fields would
        # surface U > 0, exactly what F0 is built to catch).
        for row in self.result["rows"]:
            self.assertTrue(row["catalogued"], row["class"])
        self.assertEqual(self.result["summary"]["uncatalogued_class_count"], 0)

    def test_gate_passes_and_no_silent_omission(self):
        gate = self.result["summary"]["gate"]
        self.assertTrue(gate["every_observed_class_has_disposition"])
        self.assertTrue(gate["no_class_silently_omitted"])
        self.assertEqual(self.result["summary"]["missing_disposition"], [])

    def test_write_reports_roundtrip_on_the_real_sample(self):
        with tempfile.TemporaryDirectory() as out_dir:
            jsonl_path, summary_path = cc.write_reports(self.result, out_dir=Path(out_dir))
            lines = jsonl_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), len(_SAMPLE_EXPECTED_CLASSES))
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["observed_class_count"], len(_SAMPLE_EXPECTED_CLASSES))


if __name__ == "__main__":
    unittest.main(verbosity=2)
