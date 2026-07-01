#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer F3 TEST -- op_roundtrip_probe.py, the op_id -> P-gate driver.

Intent (WHY):
  * "exit 3 on not-wired" is THIS module's own responsibility (resolved
    BEFORE any disk/process activity): an op_name outside
    ``patch_ops.NATIVE_WRITE_OP_MAP`` must never even attempt a staged write.
    Pinned against the REAL ``patch_ops`` module (already merged, F9) so this
    test cannot silently pass against a stale/fake registry.
  * ``expected_ir_for_op`` is the P-gate's ground truth -- it must be built
    from the op's OWN args, never from a live read (an op_name this module
    cannot honestly build ground truth for is NOT_IMPLEMENTED, not guessed).
  * ``probe_roundtrip`` is fully driven through an INJECTED fake
    ``apply_staged`` (mirrors cross_oracle.py's own established injection
    pattern for its LIVE leg) -- no accoreconsole is ever invoked by this
    suite; every degraded ``apply_staged`` envelope status (not_implemented /
    unavailable / blocked / a missing original-unchanged proof) must degrade
    truthfully rather than fake a PASS.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib
only.
"""
from __future__ import annotations

import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cad_op_gate  # noqa: E402
import op_roundtrip_probe as probe  # noqa: E402

IR_SCHEMA_ID = probe.IR_SCHEMA_ID


# --------------------------------------------------------------------------- #
# resolve_native_op -- exit 3 on not-wired
# --------------------------------------------------------------------------- #

class TestResolveNativeOp(unittest.TestCase):
    def test_create_line_resolves_against_real_patch_ops(self):
        import patch_ops
        self.assertEqual(probe.resolve_native_op("create_line", patch_ops_mod=patch_ops),
                        "write.entity.line")

    def test_create_circle_resolves_against_real_patch_ops(self):
        import patch_ops
        self.assertEqual(probe.resolve_native_op("create_circle", patch_ops_mod=patch_ops),
                        "write.entity.circle")

    def test_unwired_op_resolves_to_none(self):
        import patch_ops
        self.assertIsNone(probe.resolve_native_op("create_arc", patch_ops_mod=patch_ops))
        self.assertNotIn("create_arc", patch_ops.NATIVE_WRITE_OP_MAP,
                         "fixture premise: create_arc must genuinely be unwired today")

    def test_missing_patch_ops_sibling_resolves_to_none(self):
        self.assertIsNone(probe.resolve_native_op("create_line", patch_ops_mod=object()))


# --------------------------------------------------------------------------- #
# expected_ir_for_op -- ground truth from the op's own args
# --------------------------------------------------------------------------- #

class TestExpectedIrForOp(unittest.TestCase):
    def test_create_line_builds_line_geometry(self):
        ir = probe.expected_ir_for_op("create_line", {"start": [0, 0, 0], "end": [10, 0, 0], "layer": "DIM"})
        self.assertEqual(ir["schema"], IR_SCHEMA_ID)
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "LINE")
        self.assertEqual(ent["layer"], "DIM")
        self.assertEqual(ent["geometry"], {"kind": "line", "start": [0, 0, 0], "end": [10, 0, 0]})

    def test_create_circle_builds_circle_geometry(self):
        ir = probe.expected_ir_for_op("create_circle", {"center": [1, 2, 0], "radius": 3.0, "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "CIRCLE")
        self.assertEqual(ent["geometry"], {"kind": "circle", "center": [1, 2, 0], "radius": 3.0})

    def test_default_layer_is_zero(self):
        ir = probe.expected_ir_for_op("create_line", {"start": [0, 0, 0], "end": [10, 0, 0]})
        self.assertEqual(ir["entities"][0]["layer"], "0")

    def test_unbuildable_op_raises_not_implemented_error(self):
        with self.assertRaises(NotImplementedError):
            probe.expected_ir_for_op("create_arc", {})


# --------------------------------------------------------------------------- #
# added_entities_ir -- resolves the diff's added-handle set back to FULL records
# --------------------------------------------------------------------------- #

class TestAddedEntitiesIr(unittest.TestCase):
    def test_resolves_full_entity_not_just_summary_fields(self):
        pre_ir = {"schema": IR_SCHEMA_ID, "entities": []}
        new_entity = {"handle": "9F1", "dxf_name": "LINE", "layer": "DIM",
                     "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [10.0, 0.0, 0.0]}}
        post_ir = {"schema": IR_SCHEMA_ID, "entities": [new_entity]}
        actual = probe.added_entities_ir(pre_ir, post_ir)
        self.assertEqual(actual["entities"], [new_entity])

    def test_unchanged_entities_are_excluded(self):
        shared = {"handle": "1A", "dxf_name": "LINE", "layer": "0",
                 "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [1.0, 0.0, 0.0]}}
        new_entity = {"handle": "1B", "dxf_name": "CIRCLE", "layer": "0",
                     "geometry": {"kind": "circle", "center": [0.0, 0.0, 0.0], "radius": 1.0}}
        pre_ir = {"schema": IR_SCHEMA_ID, "entities": [dict(shared)]}
        post_ir = {"schema": IR_SCHEMA_ID, "entities": [dict(shared), new_entity]}
        actual = probe.added_entities_ir(pre_ir, post_ir)
        self.assertEqual([e["handle"] for e in actual["entities"]], ["1B"])


# --------------------------------------------------------------------------- #
# probe_roundtrip -- the full driver, apply_staged injected (no live runtime)
# --------------------------------------------------------------------------- #

def _fake_apply_staged(post_entity, *, status="ok", reason=None, original_unchanged=True,
                      pre_entities=None):
    def _fn(patch, dwg_path, out_dir):
        pre_ir = {"schema": IR_SCHEMA_ID, "entities": list(pre_entities or [])}
        post_ir = {"schema": IR_SCHEMA_ID, "entities": list(pre_entities or []) + [dict(post_entity)]}
        envelope = {"status": status}
        if reason is not None:
            envelope["reason"] = reason
        if status == "ok":
            envelope["original_unchanged"] = {"unchanged": original_unchanged}
            envelope["extra"] = {"pre_ir": pre_ir, "post_ir": post_ir}
        return envelope
    return _fn


class TestProbeRoundtrip(unittest.TestCase):
    def test_not_wired_op_is_exit_3_before_any_apply_staged_call(self):
        def _must_not_be_called(patch, dwg_path, out_dir):
            raise AssertionError("apply_staged must never be called for an unwired op_name")
        result = probe.probe_roundtrip("create_arc", {}, "fake.dwg", "fake_out",
                                       apply_staged=_must_not_be_called)
        self.assertEqual(result["status"], cad_op_gate.STATUS_NOT_IMPLEMENTED)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_NOT_IMPLEMENTED)

    def test_matching_roundtrip_is_exit_0(self):
        entity = {"handle": "9F1", "dxf_name": "LINE", "layer": "DIM",
                  "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [100.0, 0.0, 0.0]}}
        result = probe.probe_roundtrip(
            "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"},
            "fake.dwg", "fake_out", apply_staged=_fake_apply_staged(entity))
        self.assertEqual(result["status"], cad_op_gate.STATUS_OK)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)
        self.assertEqual(result["native_op"], "write.entity.line")

    def test_shifted_roundtrip_is_exit_1(self):
        entity = {"handle": "9F1", "dxf_name": "LINE", "layer": "DIM",
                  "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [100.0, 5.0, 0.0]}}
        result = probe.probe_roundtrip(
            "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"},
            "fake.dwg", "fake_out", apply_staged=_fake_apply_staged(entity))
        self.assertEqual(result["status"], cad_op_gate.STATUS_FAIL)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_FAIL)

    def test_apply_staged_not_implemented_degrades_truthfully(self):
        result = probe.probe_roundtrip(
            "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"},
            "fake.dwg", "fake_out",
            apply_staged=_fake_apply_staged(
                {}, status="not_implemented", reason="run_job.run_router_cad_job unavailable"))
        self.assertEqual(result["status"], cad_op_gate.STATUS_NOT_IMPLEMENTED)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_NOT_IMPLEMENTED)

    def test_apply_staged_blocked_is_error_not_fake_pass(self):
        result = probe.probe_roundtrip(
            "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"},
            "fake.dwg", "fake_out",
            apply_staged=_fake_apply_staged({}, status="blocked", reason="guards failed"))
        self.assertEqual(result["status"], cad_op_gate.STATUS_ERROR)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_ERROR)

    def test_original_mutated_during_apply_is_exit_5(self):
        entity = {"handle": "9F1", "dxf_name": "LINE", "layer": "DIM",
                  "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [100.0, 0.0, 0.0]}}
        result = probe.probe_roundtrip(
            "create_line", {"start": [0, 0, 0], "end": [100, 0, 0], "layer": "DIM"},
            "fake.dwg", "fake_out",
            apply_staged=_fake_apply_staged(entity, original_unchanged=False))
        self.assertEqual(result["status"], cad_op_gate.STATUS_ORIGINAL_MUTATED)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_ORIGINAL_MUTATED)

    def test_unbuildable_expected_ir_is_exit_3_even_if_natively_wired(self):
        # a defensive case: an op_name that WERE wired natively but this
        # module has no ground-truth builder for must still be NOT_IMPLEMENTED
        # (never silently guessed).
        import patch_ops

        class _FakePatchOps:
            NATIVE_WRITE_OP_MAP = dict(patch_ops.NATIVE_WRITE_OP_MAP)
            NATIVE_WRITE_OP_MAP["create_polyline"] = "write.entity.polyline"

        def _must_not_be_called(patch, dwg_path, out_dir):
            raise AssertionError("apply_staged must never be called without expected-entity ground truth")

        result = probe.probe_roundtrip(
            "create_polyline", {}, "fake.dwg", "fake_out",
            apply_staged=_must_not_be_called, patch_ops_mod=_FakePatchOps)
        self.assertEqual(result["status"], cad_op_gate.STATUS_NOT_IMPLEMENTED)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_NOT_IMPLEMENTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
