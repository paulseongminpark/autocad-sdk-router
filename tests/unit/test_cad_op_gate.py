#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer F3 TEST -- cad_op_gate.py, the P/D-half roundtrip gate primitive.

Intent (WHY):
  * The P-gate (``check_roundtrip``) is the north-star acceptance for every
    entity/brep/geometry_kernel write op: does the geometry we ASKED to be
    written fingerprint-match what was actually read back, independent of
    handle (cad_diff.py's ``comparison_basis="geometry"``, F1, already
    merged)? A create_line/create_circle roundtrip with diff=0 MUST pass
    (exit 0); a shifted coordinate MUST fail (exit 1) -- both pinned directly
    against the SAME ``op_roundtrip_probe.expected_ir_for_op`` ground-truth
    builder the live driver uses, so this test cannot drift from what F3's
    driver actually asks the gate to judge.
  * The D-gate (``check_field_mutation`` / ``check_mutation_pair``) is
    FAIL-CLOSED by construction: it must refuse to fabricate a perturbation
    against an absent/NULL field (exit 4 HOLLOW), refuse a key-injected
    "replace" (exit 4 HOLLOW), and refuse to trust an identity it cannot
    reconstruct (added/removed, >1 modified, or the WRONG entity modified --
    exit 8 IRRECONSTRUCTIBLE). Rule 9: each of these is pinned against the
    SPECIFIC business rule it protects, not just "returns non-zero".
  * Rung-B (non-null population) is checked UPSTREAM of Rung-A so a
    field that is null-filled across an entire corpus is caught before a
    mutation test would even be attempted against it.
  * The exit-code contract itself (0/1/2/3/4/5/6/7/8) is pinned as a constant
    surface -- a future refactor that silently renumbers one is a real
    regression for every downstream caller of this module.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib
only.
"""
from __future__ import annotations

import copy
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cad_op_gate  # noqa: E402
import op_roundtrip_probe  # noqa: E402

IR_SCHEMA_ID = cad_op_gate.IR_SCHEMA_ID


def _line_entity(handle, start, end, layer="0"):
    return {"handle": handle, "class": "AcDbLine", "dxf_name": "LINE", "owner_handle": "1F",
           "space": "model", "layer": layer,
           "bbox": list(start) + list(end),
           "geometry": {"kind": "line", "start": list(start), "end": list(end)},
           "source": {"extractor": "test_cad_op_gate", "decoded": True}}


def _circle_entity(handle, center, radius, layer="0"):
    return {"handle": handle, "class": "AcDbCircle", "dxf_name": "CIRCLE", "owner_handle": "1F",
           "space": "model", "layer": layer,
           "bbox": [center[0] - radius, center[1] - radius, center[2],
                    center[0] + radius, center[1] + radius, center[2]],
           "geometry": {"kind": "circle", "center": list(center), "radius": radius},
           "source": {"extractor": "test_cad_op_gate", "decoded": True}}


# --------------------------------------------------------------------------- #
# Exit-code contract surface
# --------------------------------------------------------------------------- #

class TestExitCodeContract(unittest.TestCase):
    def test_exact_exit_code_values(self):
        self.assertEqual(cad_op_gate.EXIT_OK, 0)
        self.assertEqual(cad_op_gate.EXIT_FAIL, 1)
        self.assertEqual(cad_op_gate.EXIT_ERROR, 2)
        self.assertEqual(cad_op_gate.EXIT_NOT_IMPLEMENTED, 3)
        self.assertEqual(cad_op_gate.EXIT_HOLLOW, 4)
        self.assertEqual(cad_op_gate.EXIT_ORIGINAL_MUTATED, 5)
        self.assertEqual(cad_op_gate.EXIT_UTF8, 6)
        self.assertEqual(cad_op_gate.EXIT_ORACLE_DISAGREE, 7)
        self.assertEqual(cad_op_gate.EXIT_IRRECONSTRUCTIBLE, 8)


# --------------------------------------------------------------------------- #
# P-gate: check_roundtrip -- the create_line / create_circle acceptance
# --------------------------------------------------------------------------- #

class TestCheckRoundtripAcceptance(unittest.TestCase):
    """Pinned directly against op_roundtrip_probe.expected_ir_for_op -- the
    SAME ground-truth builder the live driver feeds the gate."""

    def test_create_line_roundtrip_diff_zero_is_exit_0(self):
        expected = op_roundtrip_probe.expected_ir_for_op(
            "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"})
        actual = {"schema": IR_SCHEMA_ID,
                 "entities": [_line_entity("9F1", (0.0, 0.0, 0.0), (100.0, 0.0, 0.0), layer="DIM")]}
        result = cad_op_gate.check_roundtrip(expected, actual)
        self.assertEqual(result["status"], cad_op_gate.STATUS_OK)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)
        self.assertEqual(result["diff"]["summary"]["modified"], 0)
        self.assertEqual(result["diff"]["summary"]["added"], 0)
        self.assertEqual(result["diff"]["summary"]["removed"], 0)

    def test_create_circle_roundtrip_diff_zero_is_exit_0(self):
        expected = op_roundtrip_probe.expected_ir_for_op(
            "create_circle", {"center": [5, 5, 0], "radius": 2.5, "layer": "0"})
        actual = {"schema": IR_SCHEMA_ID,
                 "entities": [_circle_entity("9F2", (5.0, 5.0, 0.0), 2.5)]}
        result = cad_op_gate.check_roundtrip(expected, actual)
        self.assertEqual(result["status"], cad_op_gate.STATUS_OK)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)

    def test_shifted_coordinate_is_exit_1_fail(self):
        expected = op_roundtrip_probe.expected_ir_for_op(
            "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"})
        shifted = {"schema": IR_SCHEMA_ID,
                  "entities": [_line_entity("9F1", (0.0, 0.0, 0.0), (100.0, 5.0, 0.0), layer="DIM")]}
        result = cad_op_gate.check_roundtrip(expected, shifted)
        self.assertEqual(result["status"], cad_op_gate.STATUS_FAIL)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_FAIL)
        self.assertGreaterEqual(result["diff"]["summary"]["modified"], 1)

    def test_within_tolerance_noise_still_passes(self):
        expected = op_roundtrip_probe.expected_ir_for_op(
            "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"})
        noisy = {"schema": IR_SCHEMA_ID,
                "entities": [_line_entity("9F1", (0.0, 0.0, 0.0), (100.0 + 1e-9, 0.0, 0.0), layer="DIM")]}
        result = cad_op_gate.check_roundtrip(expected, noisy, geometry_tolerance=1e-6)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)

    def test_cad_diff_sibling_unavailable_is_not_implemented(self):
        result = cad_op_gate.check_roundtrip({"entities": []}, {"entities": []}, cad_diff_mod=object())
        self.assertEqual(result["status"], cad_op_gate.STATUS_NOT_IMPLEMENTED)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_NOT_IMPLEMENTED)


# --------------------------------------------------------------------------- #
# Fingerprint discriminability ("degenerate dim" precondition)
# --------------------------------------------------------------------------- #

class TestFingerprintDiscriminability(unittest.TestCase):
    def test_distinct_geometry_is_discriminable(self):
        entities = [
            _line_entity("A1", (0, 0, 0), (10, 0, 0)),
            _line_entity("A2", (0, 0, 0), (20, 0, 0)),
        ]
        result = cad_op_gate.check_fingerprint_discriminability(entities)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)

    def test_collapsed_bucket_is_exit_4_hollow(self):
        same_geom = {"kind": "circle", "center": [0.0, 0.0, 0.0], "radius": 0.0}
        entities = [
            {"handle": "B1", "dxf_name": "CIRCLE", "layer": "0", "geometry": dict(same_geom)},
            {"handle": "B2", "dxf_name": "CIRCLE", "layer": "0", "geometry": dict(same_geom)},
        ]
        result = cad_op_gate.check_fingerprint_discriminability(entities)
        self.assertEqual(result["status"], cad_op_gate.STATUS_HOLLOW)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_HOLLOW)
        self.assertIn("degenerate dim", result["reason"])


# --------------------------------------------------------------------------- #
# D-gate: replace-not-inject + perturb_field_replace
# --------------------------------------------------------------------------- #

class TestReplaceNotInject(unittest.TestCase):
    def test_absent_field_raises_field_absent(self):
        pre = {"handle": "H1", "layer": "0"}
        post = {"handle": "H1", "layer": "0"}
        with self.assertRaises(cad_op_gate.FieldAbsentError):
            cad_op_gate.validate_replace_not_inject(pre, post, "xdata")

    def test_null_field_raises_field_absent(self):
        pre = {"handle": "H1", "layer": "0", "xdata": None}
        post = {"handle": "H1", "layer": "0", "xdata": None}
        with self.assertRaises(cad_op_gate.FieldAbsentError):
            cad_op_gate.validate_replace_not_inject(pre, post, "xdata")

    def test_injected_key_raises_field_injected(self):
        pre = {"handle": "H1", "layer": "0"}
        post = {"handle": "H1", "layer": "0", "extra": "new"}
        with self.assertRaises(cad_op_gate.FieldInjectedError):
            cad_op_gate.validate_replace_not_inject(pre, post, "layer")

    def test_injected_geometry_leaf_raises_field_injected(self):
        pre = {"handle": "H1", "layer": "0", "geometry": {"kind": "line", "start": [0, 0, 0]}}
        post = {"handle": "H1", "layer": "0",
               "geometry": {"kind": "line", "start": [0, 0, 0], "extra_leaf": 1}}
        with self.assertRaises(cad_op_gate.FieldInjectedError):
            cad_op_gate.validate_replace_not_inject(pre, post, "geometry.start")

    def test_clean_replace_raises_nothing(self):
        pre = {"handle": "H1", "layer": "0"}
        post = {"handle": "H1", "layer": "MOVED"}
        cad_op_gate.validate_replace_not_inject(pre, post, "layer")  # must not raise


class TestPerturbFieldReplace(unittest.TestCase):
    def setUp(self):
        self.pre_ir = {"schema": IR_SCHEMA_ID,
                      "entities": [_line_entity("H1", (0, 0, 0), (10, 0, 0), layer="WALLS")]}

    def test_replace_layer_produces_deep_copy_not_aliased(self):
        post_ir = cad_op_gate.perturb_field_replace(self.pre_ir, "H1", "layer", "MOVED")
        self.assertEqual(post_ir["entities"][0]["layer"], "MOVED")
        self.assertEqual(self.pre_ir["entities"][0]["layer"], "WALLS", "pre_ir must be untouched")

    def test_absent_field_raises(self):
        with self.assertRaises(cad_op_gate.FieldAbsentError):
            cad_op_gate.perturb_field_replace(self.pre_ir, "H1", "xdata", ["x"])

    def test_unknown_handle_raises(self):
        with self.assertRaises(cad_op_gate.FieldAbsentError):
            cad_op_gate.perturb_field_replace(self.pre_ir, "NOPE", "layer", "MOVED")

    def test_identical_value_raises_value_error(self):
        with self.assertRaises(ValueError):
            cad_op_gate.perturb_field_replace(self.pre_ir, "H1", "layer", "WALLS")


# --------------------------------------------------------------------------- #
# D-gate: check_field_mutation / check_mutation_pair (identity + detection)
# --------------------------------------------------------------------------- #

class TestCheckFieldMutation(unittest.TestCase):
    def setUp(self):
        self.pre_ir = {"schema": IR_SCHEMA_ID, "entities": [
            _line_entity("H1", (0, 0, 0), (10, 0, 0), layer="WALLS"),
            _line_entity("H2", (0, 0, 0), (5, 0, 0), layer="0"),
        ]}

    def test_clean_layer_replace_is_ok(self):
        result = cad_op_gate.check_field_mutation(self.pre_ir, "H1", "layer", "MOVED")
        self.assertEqual(result["status"], cad_op_gate.STATUS_OK)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)

    def test_clean_geometry_leaf_replace_is_ok(self):
        result = cad_op_gate.check_field_mutation(self.pre_ir, "H1", "geometry.end", [20.0, 0.0, 0.0])
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)

    def test_absent_field_is_hollow(self):
        result = cad_op_gate.check_field_mutation(self.pre_ir, "H1", "xdata", ["nope"])
        self.assertEqual(result["status"], cad_op_gate.STATUS_HOLLOW)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_HOLLOW)

    def test_other_entity_never_flagged_alongside(self):
        result = cad_op_gate.check_field_mutation(self.pre_ir, "H1", "layer", "MOVED")
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)
        modified = [r for r in result["diff"]["changed_handles"] if r["change"] == "modified"]
        self.assertEqual([r["handle"] for r in modified], ["H1"])

    def test_cad_diff_sibling_unavailable_is_not_implemented(self):
        result = cad_op_gate.check_field_mutation(self.pre_ir, "H1", "layer", "MOVED", cad_diff_mod=object())
        self.assertEqual(result["status"], cad_op_gate.STATUS_NOT_IMPLEMENTED)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_NOT_IMPLEMENTED)


class TestCheckMutationPairIdentity(unittest.TestCase):
    """Direct pair-level identity checks (added/removed masquerade, >1
    modified, wrong entity) -- constructed by hand since perturb_field_replace
    itself would refuse to build these shapes."""

    def test_added_removed_alongside_a_real_edit_is_irreconstructible(self):
        # H1 is legitimately perturbed on both sides, but H2 (pre-only) /
        # H3 (post-only) also differ -- an in-place D-half probe must never
        # tolerate stray added/removed noise riding along with its own edit.
        pre = {"schema": IR_SCHEMA_ID, "entities": [
            _line_entity("H1", (0, 0, 0), (10, 0, 0), layer="A"),
            _line_entity("H2", (0, 0, 0), (5, 0, 0), layer="A"),
        ]}
        post = {"schema": IR_SCHEMA_ID, "entities": [
            _line_entity("H1", (0, 0, 0), (10, 0, 0), layer="MOVED"),
            _line_entity("H3", (0, 0, 0), (5, 0, 0), layer="A"),
        ]}
        result = cad_op_gate.check_mutation_pair(pre, post, "H1", "layer")
        self.assertEqual(result["status"], cad_op_gate.STATUS_IRRECONSTRUCTIBLE)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_IRRECONSTRUCTIBLE)

    def test_missing_handle_on_either_side_is_error(self):
        pre = {"schema": IR_SCHEMA_ID, "entities": [_line_entity("H1", (0, 0, 0), (10, 0, 0))]}
        post = {"schema": IR_SCHEMA_ID, "entities": [_line_entity("H2", (0, 0, 0), (10, 0, 0))]}
        result = cad_op_gate.check_mutation_pair(pre, post, "H1", "layer")
        self.assertEqual(result["status"], cad_op_gate.STATUS_ERROR)  # H1 absent from post

    def test_more_than_one_modified_is_irreconstructible(self):
        pre = {"schema": IR_SCHEMA_ID, "entities": [
            _line_entity("H1", (0, 0, 0), (10, 0, 0), layer="A"),
            _line_entity("H2", (0, 0, 0), (10, 0, 0), layer="A"),
        ]}
        post = {"schema": IR_SCHEMA_ID, "entities": [
            _line_entity("H1", (0, 0, 0), (10, 0, 0), layer="MOVED"),
            _line_entity("H2", (0, 0, 0), (10, 0, 0), layer="MOVED"),
        ]}
        result = cad_op_gate.check_mutation_pair(pre, post, "H1", "layer")
        self.assertEqual(result["status"], cad_op_gate.STATUS_IRRECONSTRUCTIBLE)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_IRRECONSTRUCTIBLE)

    def test_zero_modified_is_hollow_not_irreconstructible(self):
        pre = {"schema": IR_SCHEMA_ID, "entities": [_line_entity("H1", (0, 0, 0), (10, 0, 0), layer="A")]}
        post = {"schema": IR_SCHEMA_ID, "entities": [_line_entity("H1", (0, 0, 0), (10, 0, 0), layer="A")]}
        result = cad_op_gate.check_mutation_pair(pre, post, "H1", "layer")
        self.assertEqual(result["status"], cad_op_gate.STATUS_HOLLOW)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_HOLLOW)


# --------------------------------------------------------------------------- #
# Rung-B: non-null population
# --------------------------------------------------------------------------- #

class TestRungBPopulation(unittest.TestCase):
    def test_populated_field_passes(self):
        ir = {"schema": IR_SCHEMA_ID, "entities": [_line_entity("H1", (0, 0, 0), (10, 0, 0), layer="A")]}
        result = cad_op_gate.rung_b_population(ir, "layer")
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)
        self.assertEqual(result["populated_handles"], ["H1"])

    def test_null_filled_corpus_is_hollow(self):
        ir = {"schema": IR_SCHEMA_ID, "entities": [
            {"handle": "H1", "dxf_name": "LINE", "layer": "0", "xdata": None},
            {"handle": "H2", "dxf_name": "LINE", "layer": "0"},  # absent entirely
        ]}
        result = cad_op_gate.rung_b_population(ir, "xdata", kind="LINE")
        self.assertEqual(result["status"], cad_op_gate.STATUS_HOLLOW)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_HOLLOW)
        self.assertIn("Rung-B", result["reason"])

    def test_kind_filter_restricts_corpus(self):
        ir = {"schema": IR_SCHEMA_ID, "entities": [
            _line_entity("H1", (0, 0, 0), (10, 0, 0), layer="A"),
            _circle_entity("H2", (0, 0, 0), 1.0, layer="A"),
        ]}
        result = cad_op_gate.rung_b_population(ir, "layer", kind="CIRCLE")
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["populated_handles"], ["H2"])


class TestRungASweep(unittest.TestCase):
    def test_sweep_over_two_kind_field_pairs_all_pass(self):
        ir = {"schema": IR_SCHEMA_ID, "entities": [
            _line_entity("H1", (0, 0, 0), (10, 0, 0), layer="A"),
            _circle_entity("H2", (0, 0, 0), 1.0, layer="A"),
        ]}
        specs = [
            {"kind": "LINE", "field": "layer", "new_value": "MOVED"},
            {"kind": "CIRCLE", "field": "geometry.radius", "new_value": lambda old: old + 1.0},
        ]
        result = cad_op_gate.rung_a_sweep(ir, specs)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)
        self.assertEqual(len(result["steps"]), 2)

    def test_sweep_surfaces_worst_result(self):
        ir = {"schema": IR_SCHEMA_ID, "entities": [
            _line_entity("H1", (0, 0, 0), (10, 0, 0), layer="A"),
        ]}
        specs = [
            {"kind": "LINE", "field": "layer", "new_value": "MOVED"},
            {"kind": "LINE", "field": "xdata", "new_value": ["x"]},  # absent -> HOLLOW
        ]
        result = cad_op_gate.rung_a_sweep(ir, specs)
        self.assertEqual(result["status"], cad_op_gate.STATUS_HOLLOW)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_HOLLOW)


# --------------------------------------------------------------------------- #
# UTF-8 fidelity
# --------------------------------------------------------------------------- #

class TestUtf8Fidelity(unittest.TestCase):
    def test_hangul_is_fine(self):
        value = {"layer": "X-평면도$0$TEXT"}
        result = cad_op_gate.check_utf8_fidelity(value)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)

    def test_replacement_char_is_utf8_exit(self):
        value = {"layer": "corrupted-�-name"}
        result = cad_op_gate.check_utf8_fidelity(value)
        self.assertEqual(result["status"], cad_op_gate.STATUS_UTF8)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_UTF8)

    def test_surrogate_fails_roundtrip(self):
        lone_surrogate = "bad-\udc80-name"
        result = cad_op_gate.check_utf8_fidelity({"layer": lone_surrogate})
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_UTF8)

    def test_nested_lists_and_dicts_are_walked(self):
        value = {"entities": [{"geometry": {"vertices": ["ok", "also-ok"]}}]}
        result = cad_op_gate.check_utf8_fidelity(value)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)


# --------------------------------------------------------------------------- #
# Original-file protection: staging-integrity assert + original-unchanged proof
# --------------------------------------------------------------------------- #

class TestOriginalProtection(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp(prefix="cad_op_gate_test_")
        self.original = os.path.join(self.tmpdir, "original.dwg")
        with open(self.original, "wb") as fh:
            fh.write(b"FAKE-DWG-BYTES-ORIGINAL")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_staged_path_equals_original_is_rejected(self):
        result = cad_op_gate.assert_staging_integrity(self.original, self.original)
        self.assertEqual(result["status"], cad_op_gate.STATUS_ORIGINAL_MUTATED)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_ORIGINAL_MUTATED)

    def test_distinct_nonexistent_staged_path_is_ok(self):
        staged = os.path.join(self.tmpdir, "staged.dwg")  # not yet materialized
        result = cad_op_gate.assert_staging_integrity(self.original, staged)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)

    def test_staged_copy_not_byte_identical_is_rejected(self):
        staged = os.path.join(self.tmpdir, "staged.dwg")
        with open(staged, "wb") as fh:
            fh.write(b"DIFFERENT-BYTES")
        result = cad_op_gate.assert_staging_integrity(self.original, staged)
        self.assertEqual(result["status"], cad_op_gate.STATUS_ORIGINAL_MUTATED)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_ORIGINAL_MUTATED)

    def test_original_unchanged_after_no_mutation(self):
        fp = cad_op_gate.capture_file_fingerprint(self.original)
        result = cad_op_gate.check_original_unchanged(self.original, fp)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)

    def test_original_mutated_is_detected(self):
        fp = cad_op_gate.capture_file_fingerprint(self.original)
        with open(self.original, "ab") as fh:
            fh.write(b"TAMPERED")
        result = cad_op_gate.check_original_unchanged(self.original, fp)
        self.assertEqual(result["status"], cad_op_gate.STATUS_ORIGINAL_MUTATED)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_ORIGINAL_MUTATED)

    def test_original_missing_is_detected(self):
        fp = cad_op_gate.capture_file_fingerprint(self.original)
        os.remove(self.original)
        result = cad_op_gate.check_original_unchanged(self.original, fp)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_ORIGINAL_MUTATED)


# --------------------------------------------------------------------------- #
# Cross-oracle leg (F1.5, tools/cross_oracle.py -- already merged)
# --------------------------------------------------------------------------- #

class TestCrossOracleLeg(unittest.TestCase):
    def _entity_ir(self, layer="0"):
        return {"schema": IR_SCHEMA_ID, "entities": [_line_entity("2A7", (0, 0, 0), (10, 0, 0), layer=layer)]}

    def test_agreeing_pair_is_ok(self):
        ir = self._entity_ir()
        result = cad_op_gate.check_cross_oracle(ir, copy.deepcopy(ir))
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)

    def test_disagreeing_pair_is_exit_7(self):
        oracle = self._entity_ir(layer="A")
        native = self._entity_ir(layer="B")
        result = cad_op_gate.check_cross_oracle(oracle, native)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_ORACLE_DISAGREE)

    def test_native_hollow_is_exit_4(self):
        oracle = self._entity_ir(layer="A")
        native_entity = _line_entity("2A7", (0, 0, 0), (10, 0, 0))
        del native_entity["layer"]
        native = {"schema": IR_SCHEMA_ID, "entities": [native_entity]}
        result = cad_op_gate.check_cross_oracle(oracle, native)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_HOLLOW)

    def test_cross_oracle_sibling_unavailable_is_not_implemented(self):
        result = cad_op_gate.check_cross_oracle({}, {}, cross_oracle_mod=object())
        self.assertEqual(result["status"], cad_op_gate.STATUS_NOT_IMPLEMENTED)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_NOT_IMPLEMENTED)

    def test_live_leg_unavailable_engine_is_exit_2(self):
        # mirrors cross_oracle.py's own EXIT_UNAVAILABLE=2 contract
        result = cad_op_gate.check_cross_oracle_live("staged.dwg", self._entity_ir(), engine="bogus")
        self.assertEqual(result["exit_code"], 2)

    def test_live_leg_injected_router_end_to_end(self):
        """DONE_NEEDS_RUNTIME wiring proof: the LIVE leg's plumbing (injected
        router_extract -> real ir_builder normalization -> compare_multiset)
        with the router subprocess itself faked out -- no accoreconsole
        invoked. Mirrors cross_oracle.py's own established test pattern."""
        import tempfile
        import json as _json
        import ir_builder

        extract = {
            "schema": "ariadne.dwg_geometry_extract.v1", "route": "dwg_truth_autocad",
            "status": "ok", "source": {"dwg_name": "staged.dwg", "format": "dwg"},
            "summary": {"modelspace_count": 1, "entities_by_type": {"LINE": 1}},
            "entities": [{"handle": "2A7", "object_id": "id-1", "type": "LINE", "layer": "0",
                         "geometry": {"kind": "line", "start": {"x": 0.0, "y": 0.0, "z": 0.0},
                                     "end": {"x": 10.0, "y": 0.0, "z": 0.0}}}],
        }
        with tempfile.TemporaryDirectory() as td:
            extract_path = os.path.join(td, "extract_arx.json")
            with open(extract_path, "w", encoding="utf-8") as fh:
                _json.dump(extract, fh)

            def fake_router_extract(staged, run_dir, *, intent):
                self.assertEqual(intent, "dwg")
                return {"command": ["powershell"], "exit_code": 0, "error": None,
                       "envelope": {"status": "PASS",
                                   "execution": {"engine_exit_code": 0,
                                                "engine_output": {"status": "ok",
                                                                  "winning_engine": "arx",
                                                                  "extract_json": extract_path}}}}

            native_ir = ir_builder.build_ir_from_extract(
                extract, extract["summary"],
                {"extractor": "native_fixture", "engine_tier": "native_arx",
                "route": "dwg_truth_autocad", "dwg_path": "staged.dwg", "byte_size": 0})

            result = cad_op_gate.check_cross_oracle_live(
                "staged.dwg", native_ir, engine="accoreconsole",
                router_extract=fake_router_extract, ir_from_extract=ir_builder.build_ir_from_extract)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)


# --------------------------------------------------------------------------- #
# combine_results / _finalize priority ordering
# --------------------------------------------------------------------------- #

class TestCombineResults(unittest.TestCase):
    def test_empty_is_ok(self):
        result = cad_op_gate.combine_results([])
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)

    def test_hollow_beats_fail(self):
        results = [
            {"status": cad_op_gate.STATUS_FAIL, "exit_code": cad_op_gate.EXIT_FAIL},
            {"status": cad_op_gate.STATUS_HOLLOW, "exit_code": cad_op_gate.EXIT_HOLLOW},
        ]
        out = cad_op_gate.combine_results(results)
        self.assertEqual(out["exit_code"], cad_op_gate.EXIT_HOLLOW)

    def test_original_mutated_beats_hollow(self):
        results = [
            {"status": cad_op_gate.STATUS_HOLLOW, "exit_code": cad_op_gate.EXIT_HOLLOW},
            {"status": cad_op_gate.STATUS_ORIGINAL_MUTATED, "exit_code": cad_op_gate.EXIT_ORIGINAL_MUTATED},
        ]
        out = cad_op_gate.combine_results(results)
        self.assertEqual(out["exit_code"], cad_op_gate.EXIT_ORIGINAL_MUTATED)

    def test_irreconstructible_beats_oracle_disagree(self):
        results = [
            {"status": cad_op_gate.STATUS_ORACLE_DISAGREE, "exit_code": cad_op_gate.EXIT_ORACLE_DISAGREE},
            {"status": cad_op_gate.STATUS_IRRECONSTRUCTIBLE, "exit_code": cad_op_gate.EXIT_IRRECONSTRUCTIBLE},
        ]
        out = cad_op_gate.combine_results(results)
        self.assertEqual(out["exit_code"], cad_op_gate.EXIT_IRRECONSTRUCTIBLE)

    def test_not_implemented_is_weakest_non_ok(self):
        results = [
            {"status": cad_op_gate.STATUS_NOT_IMPLEMENTED, "exit_code": cad_op_gate.EXIT_NOT_IMPLEMENTED},
            {"status": cad_op_gate.STATUS_OK, "exit_code": cad_op_gate.EXIT_OK},
        ]
        out = cad_op_gate.combine_results(results)
        self.assertEqual(out["exit_code"], cad_op_gate.EXIT_NOT_IMPLEMENTED)


# --------------------------------------------------------------------------- #
# gate_roundtrip / gate_field_mutation orchestrators
# --------------------------------------------------------------------------- #

class TestGateRoundtripOrchestrator(unittest.TestCase):
    def test_full_pass_pipeline(self):
        expected = op_roundtrip_probe.expected_ir_for_op(
            "create_line", {"start": [0, 0, 0], "end": [10, 0, 0], "layer": "0"})
        actual = {"schema": IR_SCHEMA_ID, "entities": [_line_entity("9F1", (0, 0, 0), (10, 0, 0))]}
        result = cad_op_gate.gate_roundtrip(expected, actual)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)

    def test_staging_integrity_violation_stops_pipeline_early(self):
        expected = op_roundtrip_probe.expected_ir_for_op(
            "create_line", {"start": [0, 0, 0], "end": [10, 0, 0], "layer": "0"})
        actual = {"schema": IR_SCHEMA_ID, "entities": [_line_entity("9F1", (0, 0, 0), (10, 0, 0))]}
        result = cad_op_gate.gate_roundtrip(
            expected, actual, original_path="same.dwg", staged_path="same.dwg")
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_ORIGINAL_MUTATED)
        # only the staging-integrity step ran -- the roundtrip diff must never
        # have been attempted once the original is already at risk.
        self.assertEqual(len(result["steps"]), 1)


class TestGateFieldMutationOrchestrator(unittest.TestCase):
    def test_full_pass_pipeline(self):
        ir = {"schema": IR_SCHEMA_ID, "entities": [_line_entity("H1", (0, 0, 0), (10, 0, 0), layer="A")]}
        result = cad_op_gate.gate_field_mutation(ir, "H1", "layer", "MOVED", kind="LINE")
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)

    def test_rung_b_failure_stops_before_mutation_attempted(self):
        ir = {"schema": IR_SCHEMA_ID, "entities": [
            {"handle": "H1", "dxf_name": "LINE", "layer": "0"},  # xdata never populated
        ]}
        result = cad_op_gate.gate_field_mutation(ir, "H1", "xdata", ["x"], kind="LINE")
        self.assertEqual(result["status"], cad_op_gate.STATUS_HOLLOW)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_HOLLOW)
        self.assertEqual(len(result["steps"]), 1, "Rung-A must never run once Rung-B has failed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
