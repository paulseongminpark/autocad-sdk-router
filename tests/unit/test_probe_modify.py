#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wave-0 tests for tools/probe_modify.py (R1-5 modify-probe).

Source-level / mocked only (no AutoCAD runtime needed): a live accoreconsole run
cannot be part of this suite's fixed 456-test gate, so these tests exercise the
two things that actually carry the probe's business logic without a live CAD
process --

  1. handle-resolve (pick_handle_for_dxf_name / entity_by_handle / discover_
     candidates) -- given a synthetic entity list, does it find the right
     handle, and is it honest ("no candidate") when the drawing lacks one?
  2. target-changed assertion (assert_common_changed / assert_transform_changed
     / assert_explode_effect / assert_boolean_changed / classify_registry_
     repin) -- given synthetic before/after snapshots, does it correctly say
     "changed" only when the entity genuinely changed, and "failed" (not a
     rubber-stamped "ok") when it didn't?

A _FakeCad test double (real on-disk JSON/text fixtures, no unittest.mock --
matching this codebase's existing fixture-file convention, e.g.
ir_builder.make_fixture_ir() / test_cados_m06_runner.py's _fixture_pair())
drives run_probe_common/run_probe_transform end-to-end through discover_
candidates, proving the full handle-resolve -> mutate -> re-verify wiring
without ever touching accoreconsole.
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

import probe_modify  # noqa: E402


class _FakeCad:
    """Stand-in for cadctl.Cad() that never touches a live CAD runtime.

    Each inspect()/run_operation() call consumes the next canned result from a
    fixed sequence and writes it to REAL files under a tmp dir (matching this
    codebase's existing fixture-file convention rather than unittest.mock),
    since probe_modify's I/O helpers read dwg_graph_ir.json / stdout.txt paths
    off disk, not in-memory objects.
    """

    def __init__(self, inspect_irs=(), run_results=(), registry=None):
        self._inspect_irs = list(inspect_irs)
        self._run_results = list(run_results)
        self._registry = registry or {}
        self.inspect_calls = 0
        self.run_calls = 0

    def inspect(self, dwg_path, out_dir, mode="graph", include_rich=False):
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        ir = self._inspect_irs[self.inspect_calls]
        self.inspect_calls += 1
        ir_path = out / "dwg_graph_ir.json"
        ir_path.write_text(json.dumps(ir), encoding="utf-8")
        return {"status": "ok", "dwg_graph_ir": str(ir_path),
               "entity_count": len(ir.get("entities", []))}

    def run_operation(self, op_id, args=None, write_mode=None, dwg_path=None, out_dir=None):
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        result = self._run_results[self.run_calls]
        self.run_calls += 1
        # Only the *existence* of this path matters to probe_modify's
        # _staged_input_of(); its content is irrelevant to a FAKE run.
        staged = out / "staged_input.dwg"
        staged.write_text("fake-staged-dwg", encoding="utf-8")
        stdout_path = out / "stdout.txt"
        envelope = {"execution": {"engine_output": {"input": str(staged)}}}
        stdout_path.write_text(json.dumps(envelope), encoding="utf-8")
        return {"status": "ok", "executed": True, "stdout": str(stdout_path), "result": result}

    def registry_explain(self, op_id):
        return self._registry.get(op_id) or {
            "schema": "ariadne.cadctl.registry_explain.v1", "status": "not_found",
            "operation": op_id, "reason": f"operation '{op_id}' not found in registry",
        }


def _circle(handle, layer="0", center=(1.0, 2.0, 0.0), radius=5.0):
    return {"handle": handle, "dxf_name": "CIRCLE", "layer": layer,
           "geometry": {"kind": "circle", "center": list(center), "radius": radius}}


def _line(handle, layer="0", start=(0.0, 0.0, 0.0), end=(10.0, 0.0, 0.0)):
    return {"handle": handle, "dxf_name": "LINE", "layer": layer,
           "geometry": {"kind": "line", "start": list(start), "end": list(end)}}


def _insert(handle, layer="0"):
    return {"handle": handle, "dxf_name": "INSERT", "layer": layer,
           "geometry": {"kind": "block_reference", "position": [0.0, 0.0, 0.0]}}


def _solid(handle, layer="0"):
    return {"handle": handle, "dxf_name": "3DSOLID", "layer": layer, "bbox": [],
           "geometry": {"kind": "solid"}}


# --------------------------------------------------------------------------- #
# Pure handle-resolve tests
# --------------------------------------------------------------------------- #

class TestHandleResolve(unittest.TestCase):
    def test_pick_handle_for_dxf_name_finds_first_match(self):
        entities = [_line("L1"), _circle("C1"), _circle("C2")]
        self.assertEqual(probe_modify.pick_handle_for_dxf_name(entities, "CIRCLE"), "C1")

    def test_pick_handle_for_dxf_name_is_honest_about_no_candidate(self):
        entities = [_line("L1")]
        self.assertIsNone(probe_modify.pick_handle_for_dxf_name(entities, "INSERT"))

    def test_pick_handle_for_dxf_name_skips_entities_with_empty_handle(self):
        entities = [{"handle": "", "dxf_name": "CIRCLE"}, _circle("C2")]
        self.assertEqual(probe_modify.pick_handle_for_dxf_name(entities, "CIRCLE"), "C2")

    def test_entity_by_handle_found_and_not_found(self):
        entities = [_line("L1"), _circle("C1")]
        self.assertEqual(probe_modify.entity_by_handle(entities, "C1")["dxf_name"], "CIRCLE")
        self.assertIsNone(probe_modify.entity_by_handle(entities, "NOPE"))
        self.assertIsNone(probe_modify.entity_by_handle(entities, None))

    def test_discover_candidates_ok_when_all_three_kinds_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir = {"entities": [_circle("C1"), _line("L1"), _insert("I1")]}
            cad = _FakeCad(inspect_irs=[ir])
            out = probe_modify.discover_candidates(cad, Path("fixture.dwg"), Path(tmp) / "discover")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["handles"], {"common": "C1", "transform": "L1", "explode": "I1"})
        self.assertEqual(out["entity_count"], 3)

    def test_discover_candidates_fails_honestly_when_a_kind_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir = {"entities": [_circle("C1"), _line("L1")]}  # no INSERT
            cad = _FakeCad(inspect_irs=[ir])
            out = probe_modify.discover_candidates(cad, Path("fixture.dwg"), Path(tmp) / "discover")
        self.assertEqual(out["status"], "failed")
        self.assertIn("INSERT", out["reason"])


# --------------------------------------------------------------------------- #
# Pure target-changed assertion tests (R1/R2/R3/R4/R5)
# --------------------------------------------------------------------------- #

class TestAssertCommonChanged(unittest.TestCase):
    def test_changed_true_when_layer_actually_moved(self):
        before = _circle("C1", layer="0")
        after = _circle("C1", layer="ARIADNE_PROBE_MODIFY_COMMON")
        out = probe_modify.assert_common_changed(before, after, "ARIADNE_PROBE_MODIFY_COMMON")
        self.assertTrue(out["changed"])
        self.assertIsNone(out["reason"])

    def test_changed_false_when_layer_did_not_move(self):
        before = _circle("C1", layer="0")
        after = _circle("C1", layer="0")  # op claimed success but nothing moved
        out = probe_modify.assert_common_changed(before, after, "ARIADNE_PROBE_MODIFY_COMMON")
        self.assertFalse(out["changed"])
        self.assertIsNotNone(out["reason"])

    def test_changed_false_when_snapshot_missing(self):
        out = probe_modify.assert_common_changed(None, _circle("C1"), "X")
        self.assertFalse(out["changed"])


class TestAssertTransformChanged(unittest.TestCase):
    def test_changed_true_when_geometry_moved_by_exact_translate(self):
        before = _line("L1", start=(0.0, 0.0, 0.0), end=(10.0, 0.0, 0.0))
        translate = {"x": 12.5, "y": -7.25, "z": 0.0}
        after = _line("L1", start=(12.5, -7.25, 0.0), end=(22.5, -7.25, 0.0))
        out = probe_modify.assert_transform_changed(before, after, translate)
        self.assertTrue(out["changed"])
        self.assertTrue(all(c["ok"] for c in out["checks"]))

    def test_changed_false_when_geometry_did_not_move(self):
        before = _line("L1", start=(0.0, 0.0, 0.0), end=(10.0, 0.0, 0.0))
        translate = {"x": 12.5, "y": -7.25, "z": 0.0}
        after = _line("L1", start=(0.0, 0.0, 0.0), end=(10.0, 0.0, 0.0))  # unchanged
        out = probe_modify.assert_transform_changed(before, after, translate)
        self.assertFalse(out["changed"])

    def test_changed_false_when_moved_by_wrong_delta(self):
        before = _line("L1", start=(0.0, 0.0, 0.0), end=(10.0, 0.0, 0.0))
        translate = {"x": 12.5, "y": -7.25, "z": 0.0}
        after = _line("L1", start=(1.0, 1.0, 0.0), end=(11.0, 1.0, 0.0))  # wrong delta
        out = probe_modify.assert_transform_changed(before, after, translate)
        self.assertFalse(out["changed"])

    def test_within_tolerance_still_counts_as_changed(self):
        before = _line("L1", start=(0.0, 0.0, 0.0), end=(10.0, 0.0, 0.0))
        translate = {"x": 12.5, "y": -7.25, "z": 0.0}
        after = _line("L1", start=(12.500001, -7.249999, 0.0), end=(22.500001, -7.249999, 0.0))
        out = probe_modify.assert_transform_changed(before, after, translate, tolerance=1e-4)
        self.assertTrue(out["changed"])

    def test_no_point_geometry_to_compare_is_honest_not_a_fake_pass(self):
        # A 3DSOLID's geometry has no 3-tuple point field under the current
        # native_full extractor -- must not silently claim "changed".
        before = _solid("S1")
        after = _solid("S1")
        out = probe_modify.assert_transform_changed(before, after, {"x": 1.0, "y": 0.0, "z": 0.0})
        self.assertFalse(out["changed"])
        self.assertIn("no 3-tuple point field", out["reason"])


class TestAssertExplodeEffect(unittest.TestCase):
    def test_changed_true_when_count_grew_by_exactly_piece_count(self):
        after_entities = [_insert("I1")] + [_line(f"P{i}") for i in range(4)]
        out = probe_modify.assert_explode_effect(10, 14, 4, "I1", after_entities)
        self.assertTrue(out["changed"])

    def test_changed_false_when_count_did_not_grow_as_expected(self):
        after_entities = [_insert("I1")] + [_line(f"P{i}") for i in range(2)]
        out = probe_modify.assert_explode_effect(10, 12, 4, "I1", after_entities)  # claims 4 pieces, only 2 landed
        self.assertFalse(out["changed"])

    def test_changed_false_when_piece_count_is_zero(self):
        out = probe_modify.assert_explode_effect(10, 10, 0, "I1", [_insert("I1")])
        self.assertFalse(out["changed"])

    def test_source_preserved_flag_reflects_non_destructive_semantics(self):
        after_entities = [_insert("I1"), _line("P0")]
        out = probe_modify.assert_explode_effect(1, 2, 1, "I1", after_entities)
        source_check = next(c for c in out["checks"] if c["field"] == "source_entity_preserved")
        self.assertTrue(source_check["ok"])


class TestAssertBooleanChanged(unittest.TestCase):
    def _entities(self):
        return [_solid("A1"), _solid("B1")]

    def test_changed_true_when_native_ok_and_both_handles_survive_as_solids(self):
        op_result = {"modified": True, "errorstatus": 0, "handle": "A1", "other_handle": "B1"}
        out = probe_modify.assert_boolean_changed(op_result, self._entities(), self._entities(), "A1", "B1")
        self.assertTrue(out["changed"])
        self.assertFalse(out["geometry_diff_available"])  # honestly documented limitation

    def test_changed_false_when_native_errorstatus_nonzero(self):
        op_result = {"modified": False, "errorstatus": 5107, "handle": "A1", "other_handle": "B1"}
        out = probe_modify.assert_boolean_changed(op_result, self._entities(), self._entities(), "A1", "B1")
        self.assertFalse(out["changed"])

    def test_changed_false_when_other_operand_was_unexpectedly_consumed(self):
        op_result = {"modified": True, "errorstatus": 0}
        after = [_solid("A1")]  # B1 vanished -- would violate the documented clone-not-consume semantics
        out = probe_modify.assert_boolean_changed(op_result, self._entities(), after, "A1", "B1")
        self.assertFalse(out["changed"])

    def test_changed_false_when_entity_count_shifted_unexpectedly(self):
        op_result = {"modified": True, "errorstatus": 0}
        after = [_solid("A1"), _solid("B1"), _solid("EXTRA")]
        out = probe_modify.assert_boolean_changed(op_result, self._entities(), after, "A1", "B1")
        self.assertFalse(out["changed"])


class TestClassifyRegistryRepin(unittest.TestCase):
    def test_ok_when_all_four_implemented_and_decoy_not_found(self):
        records = {op_id: {"status": "ok", "registry_operation_status": "implemented"}
                  for op_id in probe_modify.MODIFY_OP_IDS}
        records[probe_modify.DECOY_OP_ID] = {"status": "not_found"}
        out = probe_modify.classify_registry_repin(records)
        self.assertEqual(out["status"], "ok")

    def test_failed_when_decoy_id_unexpectedly_resolves(self):
        records = {op_id: {"status": "ok", "registry_operation_status": "implemented"}
                  for op_id in probe_modify.MODIFY_OP_IDS}
        records[probe_modify.DECOY_OP_ID] = {"status": "ok", "registry_operation_status": "implemented"}
        out = probe_modify.classify_registry_repin(records)
        self.assertEqual(out["status"], "failed")

    def test_failed_when_a_real_op_id_is_not_implemented(self):
        records = {op_id: {"status": "ok", "registry_operation_status": "implemented"}
                  for op_id in probe_modify.MODIFY_OP_IDS}
        records["modify.entity.solid3d.boolean"] = {"status": "ok", "registry_operation_status": "catalogued"}
        records[probe_modify.DECOY_OP_ID] = {"status": "not_found"}
        out = probe_modify.classify_registry_repin(records)
        self.assertEqual(out["status"], "failed")


class TestClassifyRunStatus(unittest.TestCase):
    def test_gate_refusal_is_failed_not_needs_runtime(self):
        self.assertEqual(probe_modify._classify_run_status({"executed": False, "status": "not_found"}), "failed")

    def test_ok_status_is_ok(self):
        self.assertEqual(probe_modify._classify_run_status({"status": "ok"}), "ok")

    def test_unavailable_partial_not_implemented_are_needs_runtime(self):
        for status in ("unavailable", "partial", "not_implemented"):
            self.assertEqual(probe_modify._classify_run_status({"status": status}), "needs_runtime")

    def test_native_error_after_execution_is_failed(self):
        self.assertEqual(probe_modify._classify_run_status({"status": "error", "executed": True}), "failed")


# --------------------------------------------------------------------------- #
# Orchestration-level mocked tests: discover_candidates + run_probe_common /
# run_probe_transform end-to-end through a _FakeCad, never touching a live CAD
# runtime, proving the handle-resolve -> mutate -> re-verify wiring is correct.
# --------------------------------------------------------------------------- #

class TestOrchestrationWithFakeCad(unittest.TestCase):
    def test_run_probe_common_end_to_end_reports_ok_on_a_genuine_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            handle = "C1"
            before_ir = {"entities": [_circle(handle, layer="0"), _line("L1"), _insert("I1")]}
            after_ir = {"entities": [_circle(handle, layer=probe_modify.PROBE_LAYER_NAME)]}
            native_result = {"modified": True, "layer_set": True, "handle": handle}
            cad = _FakeCad(inspect_irs=[before_ir, after_ir], run_results=[native_result])

            candidates = probe_modify.discover_candidates(cad, Path("fixture.dwg"), Path(tmp) / "discover")
            self.assertEqual(candidates["status"], "ok")
            self.assertEqual(candidates["handles"]["common"], handle)

            result = probe_modify.run_probe_common(cad, Path("fixture.dwg"), candidates, Path(tmp) / "common")
            self.assertEqual(result["status"], "ok")
            self.assertTrue(result["assertion"]["changed"])

    def test_run_probe_common_end_to_end_reports_failed_when_layer_did_not_really_move(self):
        # The native op claims success, but the independent re-inspect shows no
        # real change -- run_probe_common must NOT rubber-stamp this as ok.
        with tempfile.TemporaryDirectory() as tmp:
            handle = "C1"
            before_ir = {"entities": [_circle(handle, layer="0"), _line("L1"), _insert("I1")]}
            after_ir = {"entities": [_circle(handle, layer="0")]}  # unchanged despite "modified": true
            native_result = {"modified": True, "layer_set": True, "handle": handle}
            cad = _FakeCad(inspect_irs=[before_ir, after_ir], run_results=[native_result])

            candidates = probe_modify.discover_candidates(cad, Path("fixture.dwg"), Path(tmp) / "discover")
            result = probe_modify.run_probe_common(cad, Path("fixture.dwg"), candidates, Path(tmp) / "common")
            self.assertEqual(result["status"], "failed")
            self.assertFalse(result["assertion"]["changed"])

    def test_run_probe_transform_end_to_end_reports_ok_on_a_genuine_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            handle = "L1"
            before_ir = {"entities": [_circle("C1"), _line(handle), _insert("I1")]}
            translate = probe_modify.PROBE_TRANSLATE
            moved = _line(handle, start=(translate["x"], translate["y"], translate["z"]),
                         end=(10.0 + translate["x"], translate["y"], translate["z"]))
            after_ir = {"entities": [moved]}
            native_result = {"transformed": True, "errorstatus": 0, "handle": handle}
            cad = _FakeCad(inspect_irs=[before_ir, after_ir], run_results=[native_result])

            candidates = probe_modify.discover_candidates(cad, Path("fixture.dwg"), Path(tmp) / "discover")
            self.assertEqual(candidates["handles"]["transform"], handle)
            result = probe_modify.run_probe_transform(cad, Path("fixture.dwg"), candidates, Path(tmp) / "transform")
            self.assertEqual(result["status"], "ok")
            self.assertTrue(result["assertion"]["changed"])

    def test_run_registry_repin_end_to_end_confirms_decoy_not_found(self):
        registry = {op_id: {"status": "ok", "registry_operation_status": "implemented"}
                   for op_id in probe_modify.MODIFY_OP_IDS}
        cad = _FakeCad(registry=registry)
        out = probe_modify.run_registry_repin(cad)
        self.assertEqual(out["status"], "ok")
        decoy_check = next(c for c in out["checks"] if c["op_id"] == probe_modify.DECOY_OP_ID)
        self.assertEqual(decoy_check["registry_status"], "not_found")
        self.assertTrue(decoy_check["ok"])


# --------------------------------------------------------------------------- #
# Safety-net + overall-status aggregation
# --------------------------------------------------------------------------- #

class TestSafeAndOverallStatus(unittest.TestCase):
    def test_safe_converts_exception_to_needs_runtime_not_a_crash(self):
        def _boom():
            raise RuntimeError("accoreconsole not found")
        out = probe_modify._safe(_boom)
        self.assertEqual(out["status"], "needs_runtime")
        self.assertIn("accoreconsole not found", out["reason"])

    def test_overall_status_ok_only_when_every_check_ok(self):
        self.assertEqual(probe_modify._overall_status({"a": {"status": "ok"}, "b": {"status": "ok"}}), "ok")

    def test_overall_status_needs_runtime_when_no_failures_but_one_pending(self):
        checks = {"a": {"status": "ok"}, "b": {"status": "needs_runtime"}}
        self.assertEqual(probe_modify._overall_status(checks), "needs_runtime")

    def test_overall_status_failed_wins_over_needs_runtime(self):
        checks = {"a": {"status": "failed"}, "b": {"status": "needs_runtime"}}
        self.assertEqual(probe_modify._overall_status(checks), "failed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
