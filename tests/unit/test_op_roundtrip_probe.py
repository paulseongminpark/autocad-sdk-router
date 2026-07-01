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
        # create_arc was the fixture here pre-WAVE-1 TIER-1 T1; promote_op.py
        # has since wired it for real -- create_hatch remains genuinely
        # unwired at the patch_ops layer today.
        import patch_ops
        self.assertIsNone(probe.resolve_native_op("create_hatch", patch_ops_mod=patch_ops))
        self.assertNotIn("create_hatch", patch_ops.NATIVE_WRITE_OP_MAP,
                         "fixture premise: create_hatch must genuinely be unwired today")

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

    def test_create_arc_builds_arc_geometry(self):
        ir = probe.expected_ir_for_op(
            "create_arc", {"center": [1, 2, 0], "radius": 5.0,
                          "start_angle": 0.0, "end_angle": 1.5707963267948966, "layer": "DIM"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "ARC")
        self.assertEqual(ent["layer"], "DIM")
        self.assertEqual(ent["geometry"],
                         {"kind": "arc", "center": [1, 2, 0], "radius": 5.0,
                          "start_angle": 0.0, "end_angle": 1.5707963267948966})
        # no "normal" key -- collectModelSpaceGraph's AcDbArc branch never
        # emits one; including it would make a real read-back mismatch.
        self.assertNotIn("normal", ent["geometry"])

    def test_create_text_builds_text_geometry_without_height(self):
        ir = probe.expected_ir_for_op(
            "create_text", {"position": [0, 0, 0], "text": "hello", "height": 2.5, "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "TEXT")
        self.assertEqual(ent["geometry"], {"kind": "text", "position": [0, 0, 0], "text": "hello"})
        self.assertNotIn("height", ent["geometry"],
                        "height is written (setHeight) but never read back by "
                        "collectModelSpaceGraph -- it must not appear in ground truth")

    def test_create_mtext_builds_mtext_geometry_without_height(self):
        ir = probe.expected_ir_for_op(
            "create_mtext", {"position": [1, 1, 0], "text": "note", "height": 3.0, "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "MTEXT")
        self.assertEqual(ent["geometry"], {"kind": "mtext", "position": [1, 1, 0], "text": "note"})
        self.assertNotIn("height", ent["geometry"])

    def test_create_polyline_builds_vertices_without_bulge_or_closed(self):
        ir = probe.expected_ir_for_op(
            "create_polyline",
            {"points": [{"x": 0, "y": 0, "bulge": 0.5}, {"x": 10, "y": 0, "bulge": 0.0}],
             "closed": 1, "layer": "0"})
        ent = ir["entities"][0]
        self.assertEqual(ent["dxf_name"], "LWPOLYLINE")
        self.assertEqual(ent["geometry"],
                         {"kind": "lwpolyline",
                          "vertices": [{"point": [0, 0, 0.0]}, {"point": [10, 0, 0.0]}]})
        # neither "bulge" (per-vertex) nor "closed" (entity-level) survives
        # collectModelSpaceGraph's AcDbPolyline branch -- ground truth omits both.
        self.assertNotIn("closed", ent["geometry"])
        for v in ent["geometry"]["vertices"]:
            self.assertNotIn("bulge", v)

    def test_unbuildable_op_raises_not_implemented_error(self):
        # create_arc was the fixture here pre-wfix-allowlist; this module has
        # since grown a ground-truth builder for it. create_ellipse remains
        # genuinely unbuildable (collectModelSpaceGraph has no AcDbEllipse
        # read branch -- see _EXPECTED_ENTITY_BUILDERS's comment).
        with self.assertRaises(NotImplementedError):
            probe.expected_ir_for_op("create_ellipse", {})

    def test_dimension_mpolygon_xdata_remain_unbuildable(self):
        # create_dimension: same reader gap as create_ellipse (no Dimension
        # branch in collectModelSpaceGraph). create_mpolygon: live create
        # fails (errorstatus=409). set_entity_xdata: not a geometry op at
        # all. All three are wired natively (patch_ops.NATIVE_WRITE_OP_MAP)
        # but none has a ground-truth builder here.
        for op_name in ("create_dimension", "create_mpolygon", "set_entity_xdata"):
            with self.assertRaises(NotImplementedError):
                probe.expected_ir_for_op(op_name, {})


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
            # top-level, mirroring the REAL patch_engine.apply_staged envelope
            # (_result_envelope(..., extra=...) does env.update(extra) -- there
            # is no nested "extra" key in the real contract).
            envelope["pre_ir"] = pre_ir
            envelope["post_ir"] = post_ir
        return envelope
    return _fn


class TestProbeRoundtrip(unittest.TestCase):
    def test_not_wired_op_is_exit_3_before_any_apply_staged_call(self):
        # create_arc was the fixture here pre-wfix-allowlist; it is natively
        # wired AND has a ground-truth builder now. create_hatch remains
        # genuinely unwired at the patch_ops layer (see TestResolveNativeOp).
        def _must_not_be_called(patch, dwg_path, out_dir):
            raise AssertionError("apply_staged must never be called for an unwired op_name")
        result = probe.probe_roundtrip("create_hatch", {}, "fake.dwg", "fake_out",
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

    def test_matching_arc_roundtrip_is_exit_0(self):
        # end-to-end wiring for one of the newly-added T1 ground-truth
        # builders (create_arc), mirroring test_matching_roundtrip_is_exit_0.
        entity = {"handle": "9F2", "dxf_name": "ARC", "layer": "0",
                  "geometry": {"kind": "arc", "center": [5.0, 5.0, 0.0], "radius": 2.5,
                              "start_angle": 0.0, "end_angle": 3.14159265358979}}
        result = probe.probe_roundtrip(
            "create_arc",
            {"center": [5, 5, 0], "radius": 2.5, "start_angle": 0.0,
             "end_angle": 3.14159265358979, "layer": "0"},
            "fake.dwg", "fake_out", apply_staged=_fake_apply_staged(entity))
        self.assertEqual(result["status"], cad_op_gate.STATUS_OK)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_OK)
        self.assertEqual(result["native_op"], "write.entity.arc")

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
        # a defensive case: an op_name that IS wired natively but this module
        # has no ground-truth builder for must still be NOT_IMPLEMENTED
        # (never silently guessed). create_ellipse is a REAL, permanent
        # instance of this today (patch_ops.NATIVE_WRITE_OP_MAP really does
        # map it to write.entity.ellipse -- no fake override needed):
        # collectModelSpaceGraph has no AcDbEllipse read branch, so this
        # module correctly refuses to assert ground truth for it.
        import patch_ops
        self.assertIn("create_ellipse", patch_ops.NATIVE_WRITE_OP_MAP,
                     "fixture premise: create_ellipse must genuinely be natively wired today")

        def _must_not_be_called(patch, dwg_path, out_dir):
            raise AssertionError("apply_staged must never be called without expected-entity ground truth")

        result = probe.probe_roundtrip(
            "create_ellipse", {}, "fake.dwg", "fake_out",
            apply_staged=_must_not_be_called)
        self.assertEqual(result["status"], cad_op_gate.STATUS_NOT_IMPLEMENTED)
        self.assertEqual(result["exit_code"], cad_op_gate.EXIT_NOT_IMPLEMENTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
