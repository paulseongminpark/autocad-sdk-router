#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer cb2-irmap TEST -- IR-to-patch mapping truth (#129b + #119).

Intent (WHY):
  #129b: kind=="block_reference" had no ir_to_patch op-case of its own --
  every INSERT fell through to patch_ops.blocks' now-removed "insert_block"
  stand-in, an op id no registry entry ever declared (regen/journal.json's
  "insert_block is not declared" warning) -- an active no-op on apply, not
  the "degrades to deferred" that module's own docstring claimed. Fixed by
  giving entities.py a real kind=="block_reference" case (create_blockref,
  write.entity.blockref, wired since w3-insert but never reachable from
  ir_to_patch) plus a block-def dependency: a fresh regen seed has none of
  the source DWG's custom blocks, so ir_to_patch.build_patch_from_ir now
  synthesizes each referenced block's definition from the IR's own
  block_definitions[] (patch_ops.blocks.block_def_ops) ahead of the first
  create_blockref naming it, or defers honestly if the IR has no such entry.

  #119: AcDb2dPolyline and AcDb3dPolyline both normalize to IR kind
  "polyline" (dxf_name POLYLINE), but were folded into the SAME lift as
  real LWPOLYLINE ("lwpolyline" kind) -- create_polyline, which regenerates
  an AcDbPolyline/LWPOLYLINE, silently downgrading the legacy entity
  (capstone evidence: POLYLINE attempted=2 removed=2 + LWPOLYLINE
  added=2). Fixed by routing on the entity's own "class": AcDb2dPolyline ->
  create_polyline2d_deep (write.entity.polyline2d.deep), AcDb3dPolyline ->
  create_polyline3d; a "polyline"-kind entity of any other class defers
  honestly instead of guessing.

  #119 (ticket point 3): config/operations.v2.json's totals/coverage rollup
  scalars must equal what the operations[] array itself recomputes to --
  totals.total (521), totals.by_engine_tier (233/222), and
  coverage.wired_ops (33) were stale generator snapshots left behind as the
  array grew past them. This file pins the corrected values as a live
  reconciliation, not a hardcoded snapshot, so a future array edit that
  reintroduces drift fails here.

Stdlib only; BOM-tolerant (utf-8-sig, the registry's own encoding).
Discoverable by pytest and ``python -m unittest discover -s tests``.
"""
from __future__ import annotations

import collections
import json
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ir_to_patch  # noqa: E402
import patch_ops  # noqa: E402
from patch_ops import blocks as patch_ops_blocks  # noqa: E402


class TestBlockReferenceLiftsToCreateBlockref(unittest.TestCase):
    """#129b: kind=='block_reference' must map to create_blockref, never the
    undeclared 'insert_block' op id."""

    def test_ir_op_for_maps_block_reference_to_create_blockref(self):
        ent = {"handle": "3", "layer": "0", "class": "AcDbBlockReference",
               "geometry": {"kind": "block_reference", "block_name": "DOOR",
                           "position": [5, 5, 0], "scale": [1, 1, 1], "rotation": 0.0}}
        op = ir_to_patch._op_for(ent)
        self.assertIsNotNone(op)
        self.assertEqual(op["operation"], "create_blockref")
        self.assertNotEqual(op["operation"], "insert_block")
        self.assertEqual(op["args"]["block_name"], "DOOR")
        self.assertEqual(op["args"]["position"], {"x": 5, "y": 5, "z": 0})

    def test_create_blockref_is_a_declared_op_insert_block_is_not(self):
        self.assertIn("create_blockref", patch_ops.NATIVE_WRITE_OP_MAP)
        self.assertEqual(patch_ops.NATIVE_WRITE_OP_MAP["create_blockref"], "write.entity.blockref")
        self.assertNotIn("insert_block", patch_ops.NATIVE_WRITE_OP_MAP)


class TestPolylineFamilySplit(unittest.TestCase):
    """#119: real LWPOLYLINE and the two legacy heavy polyline classes must
    route to their own real write ops, never all collapse into
    create_polyline."""

    def test_lwpolyline_unchanged(self):
        ent = {"handle": "5", "layer": "0", "class": "AcDbPolyline",
               "geometry": {"kind": "lwpolyline", "closed": True,
                           "vertices": [{"point": [0, 0], "bulge": 0.5}, [1, 1]]}}
        op = ir_to_patch._op_for(ent)
        self.assertEqual(op["operation"], "create_polyline")
        self.assertEqual(op["args"]["closed"], 1)

    def test_heavy_2d_polyline_lifts_to_deep_op_not_create_polyline(self):
        ent = {"handle": "9", "layer": "0", "class": "AcDb2dPolyline",
               "geometry": {"kind": "polyline", "closed": False, "elevation": 3.0,
                           "default_start_width": 0.1, "default_end_width": 0.2,
                           "vertices": [{"point": [0, 0, 3.0], "bulge": 0.0,
                                        "start_width": 0.1, "end_width": 0.2}]}}
        op = ir_to_patch._op_for(ent)
        self.assertEqual(op["operation"], "create_polyline2d_deep")
        self.assertNotEqual(op["operation"], "create_polyline")
        self.assertEqual(op["args"]["elevation"], 3.0)
        self.assertEqual(op["args"]["points"][0]["start_width"], 0.1)

    def test_3d_polyline_lifts_to_polyline3d(self):
        ent = {"handle": "10", "layer": "0", "class": "AcDb3dPolyline",
               "geometry": {"kind": "polyline",
                           "vertices": [{"point": [0, 0, 0]}, {"point": [1, 1, 1]}]}}
        op = ir_to_patch._op_for(ent)
        self.assertEqual(op["operation"], "create_polyline3d")
        self.assertEqual(len(op["args"]["points"]), 2)

    def test_unrecognized_class_for_polyline_kind_defers_honestly(self):
        ent = {"handle": "11", "layer": "0", "class": "AcDbSomethingElse",
               "geometry": {"kind": "polyline", "vertices": []}}
        self.assertIsNone(ir_to_patch._op_for(ent))

    def test_polyline_native_ops_are_declared(self):
        self.assertEqual(patch_ops.NATIVE_WRITE_OP_MAP.get("create_polyline2d_deep"),
                         "write.entity.polyline2d.deep")
        self.assertEqual(patch_ops.NATIVE_WRITE_OP_MAP.get("create_polyline3d"),
                         "write.entity.polyline3d")


class TestBuildPatchFromIrBlockDefDependency(unittest.TestCase):
    """#129b block-def dependency: create_blockref must not be emitted for a
    block name the fresh regen seed cannot resolve unless this IR also
    supplies a block_definitions[] entry to synthesize it from."""

    def test_insert_with_block_definitions_gets_create_block_preamble(self):
        ir = {
            "entities": [
                {"handle": "3", "layer": "0", "class": "AcDbBlockReference",
                 "geometry": {"kind": "block_reference", "block_name": "DOOR",
                             "position": [5, 5, 0]}},
            ],
            "block_definitions": [
                {"name": "DOOR", "handle": "1A", "def_entities": [
                    {"handle": "1B", "layer": "0",
                     "geometry": {"kind": "line", "start": [0, 0, 0], "end": [1, 0, 0]}},
                ]},
            ],
        }
        patch, deferred = ir_to_patch.build_patch_from_ir(
            ir, {"staged_path": "s", "original_path": "o"}, "t")
        op_names = [op["operation"] for op in patch["operations"]]
        self.assertEqual(op_names, ["create_block", "append_block_entity", "create_blockref"])
        self.assertEqual(deferred, [])
        self.assertEqual(patch["operations"][0]["args"]["name"], "DOOR")
        self.assertEqual(patch["operations"][2]["args"]["block_name"], "DOOR")

    def test_second_insert_of_same_block_does_not_repeat_the_preamble(self):
        ir = {
            "entities": [
                {"handle": "3", "layer": "0", "class": "AcDbBlockReference",
                 "geometry": {"kind": "block_reference", "block_name": "DOOR", "position": [0, 0, 0]}},
                {"handle": "4", "layer": "0", "class": "AcDbBlockReference",
                 "geometry": {"kind": "block_reference", "block_name": "DOOR", "position": [5, 0, 0]}},
            ],
            "block_definitions": [{"name": "DOOR", "handle": "1A", "def_entities": []}],
        }
        patch, deferred = ir_to_patch.build_patch_from_ir(
            ir, {"staged_path": "s", "original_path": "o"}, "t")
        op_names = [op["operation"] for op in patch["operations"]]
        self.assertEqual(op_names.count("create_block"), 1)
        self.assertEqual(op_names.count("create_blockref"), 2)
        # empty def_entities is itself an honest deferral (content may live
        # via owner_handle instead), not a silently-empty block.
        self.assertEqual(len(deferred), 1)
        self.assertIn("no inlined def_entities", deferred[0]["reason"])

    def test_insert_without_block_definitions_defers_honestly_not_insert_block(self):
        ir = {
            "entities": [
                {"handle": "3", "layer": "0", "class": "AcDbBlockReference",
                 "geometry": {"kind": "block_reference", "block_name": "GHOST", "position": [0, 0, 0]}},
            ],
        }
        patch, deferred = ir_to_patch.build_patch_from_ir(
            ir, {"staged_path": "s", "original_path": "o"}, "t")
        self.assertEqual(patch["operations"], [])
        self.assertEqual(len(deferred), 1)
        self.assertEqual(deferred[0]["kind"], "block_reference")
        self.assertTrue(deferred[0].get("reason"))

    def test_def_entity_of_unsupported_kind_is_deferred_not_dropped(self):
        block_def = {"name": "MIX", "handle": "2A", "def_entities": [
            {"handle": "d1", "layer": "0",
             "geometry": {"kind": "line", "start": [0, 0, 0], "end": [1, 0, 0]}},
            {"handle": "d2", "layer": "0", "geometry": {"kind": "hatch"}},
        ]}
        ops, deferred = patch_ops_blocks.block_def_ops(block_def)
        self.assertEqual([o["operation"] for o in ops], ["create_block", "append_block_entity"])
        self.assertEqual(len(deferred), 1)
        self.assertEqual(deferred[0]["kind"], "hatch")


class TestOperationsRegistryTotalsReconcileWithRecords(unittest.TestCase):
    """#119 ticket point 3: totals/coverage rollup scalars must equal what
    the operations[] array itself recomputes to. declared_coverage catalog_*
    keys are a deliberately separate, historical axis (the frozen 480-op SDK
    catalog census, config/operations.v2.json's own additive_to_v1/
    derived_from provenance) and are exempt -- not covered here."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(_REPO, "config", "operations.v2.json")
        with open(path, encoding="utf-8-sig") as fh:
            cls.registry = json.load(fh)
        cls.ops = cls.registry["operations"]

    def test_totals_total_equals_record_count(self):
        self.assertEqual(self.registry["totals"]["total"], len(self.ops))

    def test_totals_operations_equals_record_count(self):
        self.assertEqual(self.registry["totals"]["operations"], len(self.ops))

    def test_totals_by_status_matches_recomputation(self):
        recomputed = dict(collections.Counter(o.get("status") for o in self.ops))
        self.assertEqual(self.registry["totals"]["by_status"], recomputed)

    def test_totals_by_family_matches_recomputation(self):
        recomputed = dict(collections.Counter(o.get("family") for o in self.ops))
        self.assertEqual(self.registry["totals"]["by_family"], recomputed)

    def test_totals_by_engine_tier_matches_recomputation(self):
        recomputed = dict(collections.Counter(o.get("engine_tier") for o in self.ops))
        self.assertEqual(self.registry["totals"]["by_engine_tier"], recomputed)

    def test_coverage_operation_records_matches_array_length(self):
        self.assertEqual(self.registry["coverage"]["operation_records"], len(self.ops))

    def test_coverage_status_breakdown_matches_recomputation(self):
        recomputed = collections.Counter(o.get("status") for o in self.ops)
        cov = self.registry["coverage"]
        for key in ("implemented", "wired", "stub", "catalogued", "blocked", "deprecated", "unknown"):
            self.assertEqual(cov[key], recomputed.get(key, 0), key)

    def test_coverage_wired_ops_matches_wired_v1_true_count(self):
        recomputed = sum(1 for o in self.ops if o.get("wired_v1") is True)
        self.assertEqual(self.registry["coverage"]["wired_ops"], recomputed)

    def test_coverage_wired_native_plus_managed_equals_wired_ops(self):
        cov = self.registry["coverage"]
        self.assertEqual(cov["wired_native"] + cov["wired_managed"], cov["wired_ops"])


if __name__ == "__main__":
    unittest.main()
