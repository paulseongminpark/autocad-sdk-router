#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CADOS WAVE-1 TIER-1 T1 TEST -- 8 new entity write ops wired via F2 promotion.

Intent (WHY): tools/promote_op.py's F2 harness promoted 8 more write.entity.*
ops (create_arc/create_ellipse/create_mpolygon/create_mtext/create_text/
create_polyline/create_dimension/set_entity_xdata) from not_implemented to a
live native handler -- Axis A (config/operations.v2.json status_policy flip,
via the new config/promotion_manifest.json rows) + Axis B
(tools/patch_ops/entities.py WRITE_OP_MAP entry + build_job_args arg-branch),
both gated on F1's live RUNNABLE classification (measure/reachable_matrix.jsonl)
-- never wired on RUNNABLE_BUT_DEGENERATE or an unprobed op. Three of the
eight (create_text/create_polyline/create_dimension) already had a
forward-declared ir_to_patch case (patch_ops.entities.ir_op_for's pre-T1
"Tier 2/3" comments); the other three IR-representable kinds
(arc/ellipse/mtext) get a NEW ir_op_for case as part of this ticket.
create_mpolygon/set_entity_xdata get no ir_to_patch case: 'mpolygon' is not an
ir_builder._EXTRACT_KIND_TO_IR_KIND value (no real IR entity ever carries
geometry.kind=='mpolygon') and xdata is a record-level (non-geometry)
attachment, not a creatable IR kind -- same honest-deferral pattern as the
pre-existing set_xdata/set_xrecord manifest rows.

These tests exercise (1) the WRITE_OP_MAP entry, (2) the build_job_args
arg-branch (RT-FOLD H-R4: a map entry and its arg-branch must cohere), (3) the
ir_to_patch round-trip where one exists (honest None where it does not), and
(4) a read-only regression against the REAL repo files proving every
promotion actually landed and stays idempotent (mirrors test_promote_op.py's
TestAlreadyPromotedRealControlRows pattern).

Discoverable by pytest and ``python -m unittest discover -s tests``.
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

import ir_builder  # noqa: E402
import patch_engine  # noqa: E402
import patch_ops  # noqa: E402
import probe_reachability as pr  # noqa: E402
import promote_op as po  # noqa: E402
from patch_ops import entities  # noqa: E402

# (patch_op, native_op, arg_keys, ir_kind-or-None) for all 8 T1 promotions --
# literal mirror of config/promotion_manifest.json's 8 new rows.
_NEW_OPS = [
    ("create_arc", "write.entity.arc",
     ["center", "radius", "start_angle", "end_angle", "layer"], "arc"),
    ("create_ellipse", "write.entity.ellipse",
     ["center", "normal", "major_axis", "radius_ratio", "start_angle", "end_angle", "layer"], "ellipse"),
    ("create_mpolygon", "write.entity.mpolygon", ["points", "layer"], None),
    ("create_mtext", "write.entity.mtext", ["position", "text", "height", "layer"], "mtext"),
    ("create_text", "write.entity.text", ["position", "text", "height", "layer"], "text"),
    ("create_polyline", "write.entity.polyline", ["points", "closed", "layer"], "lwpolyline"),
    ("create_dimension", "write.entity.dim.rotated",
     ["xline1", "xline2", "dim_line", "dim_text", "rotation", "layer"], "dimension"),
    ("set_entity_xdata", "write.entity.set_xdata", ["app", "value"], None),
]


class TestWriteOpMapEntries(unittest.TestCase):
    """Axis B (map half): every new patch_op resolves to its promoted native_op."""

    def test_each_new_patch_op_is_mapped_in_entities(self):
        for patch_op, native_op, _keys, _ir in _NEW_OPS:
            with self.subTest(patch_op=patch_op):
                self.assertEqual(entities.WRITE_OP_MAP.get(patch_op), native_op)

    def test_aggregate_exposes_the_same_entries(self):
        # patch_ops.NATIVE_WRITE_OP_MAP / patch_engine.NATIVE_WRITE_OP_MAP are
        # the SAME aggregate dict object (test_patch_ops_split.py pins this
        # identity); prove the new entries survive the family-merge unchanged.
        for patch_op, native_op, _keys, _ir in _NEW_OPS:
            with self.subTest(patch_op=patch_op):
                self.assertEqual(patch_ops.NATIVE_WRITE_OP_MAP.get(patch_op), native_op)
                self.assertEqual(patch_engine.NATIVE_WRITE_OP_MAP.get(patch_op), native_op)


class TestBuildJobArgsArgBranch(unittest.TestCase):
    """Axis B (arg-branch half): build_job_args marshals exactly arg_keys[]
    through and drops anything else -- the shape RT-FOLD H-R4 requires (a map
    entry whose branch silently over-copies or defaults is as dangerous as a
    missing branch)."""

    def test_every_arg_key_is_copied_through_and_extras_are_dropped(self):
        for _patch_op, native_op, arg_keys, _ir in _NEW_OPS:
            with self.subTest(native_op=native_op):
                probe_args = {k: ("VALUE:%s" % k) for k in arg_keys}
                probe_args["definitely_not_an_arg_key"] = "must be dropped"
                got = entities.build_job_args(native_op, probe_args)
                self.assertIsNotNone(got, "%s must resolve (H-R4 unknown-op guard)" % native_op)
                self.assertEqual(set(got), set(arg_keys))
                for k in arg_keys:
                    self.assertEqual(got[k], "VALUE:%s" % k)

    def test_missing_keys_are_simply_omitted_not_defaulted(self):
        for _patch_op, native_op, _keys, _ir in _NEW_OPS:
            with self.subTest(native_op=native_op):
                self.assertEqual(entities.build_job_args(native_op, {}), {})

    def test_native_job_doc_end_to_end_via_patch_engine(self):
        # patch_engine._native_job_doc wraps build_job_args' output in the
        # real ariadne.autocad_sdk_job.v2 envelope apply_staged hands to
        # run_job -- prove the whole chain (not just the family module in
        # isolation) resolves for two representative new ops.
        job = patch_engine._native_job_doc(
            "write.entity.arc",
            {"center": {"x": 1.0, "y": 2.0, "z": 0.0}, "radius": 5.0,
             "start_angle": 0.0, "end_angle": 3.14, "layer": "0"})
        self.assertEqual(job["operation"], "write.entity.arc")
        self.assertEqual(job["args"], {"center": {"x": 1.0, "y": 2.0, "z": 0.0}, "radius": 5.0,
                                        "start_angle": 0.0, "end_angle": 3.14, "layer": "0"})

        job2 = patch_engine._native_job_doc(
            "write.entity.set_xdata", {"app": "ARIADNE", "value": "v1", "extra": "drop-me"})
        self.assertEqual(job2["args"], {"app": "ARIADNE", "value": "v1"})


class TestIrToPatchRoundTrip(unittest.TestCase):
    """ir_to_patch case round-trips the IR shape for the 6 IR-representable
    kinds; the 2 non-extractable ops (mpolygon/set_entity_xdata) honestly
    have none."""

    @classmethod
    def setUpClass(cls):
        # arg_keys sourced from the REAL config/promotion_manifest.json row
        # (not re-typed as a second literal) so the "which keys must appear"
        # half of each full-args assertion below can never silently drift
        # from the manifest that is the actual promotion source of truth.
        manifest_path = os.path.join(_REPO, "config", "promotion_manifest.json")
        rows = po.load_manifest(manifest_path)
        cls.arg_keys_by_patch_op = {r["patch_op"]: set(r["arg_keys"]) for r in rows}

    def test_arc_round_trips(self):
        ent = {"handle": "10", "layer": "0",
               "geometry": {"kind": "arc", "center": [1.0, 2.0, 0.0], "radius": 5.0,
                            "start_angle": 0.0, "end_angle": 1.5707963267948966}}
        op = entities.ir_op_for(ent)
        self.assertEqual(op, {"operation": "create_arc",
                              "args": {"center": {"x": 1.0, "y": 2.0, "z": 0.0}, "radius": 5.0,
                                       "start_angle": 0.0, "end_angle": 1.5707963267948966,
                                       "layer": "0"}})
        self.assertIn(op["operation"], entities.WRITE_OP_MAP)

    def test_ellipse_round_trips(self):
        ent = {"handle": "11", "layer": "DIM",
               "geometry": {"kind": "ellipse", "center": [0.0, 0.0, 0.0],
                            "normal": [0.0, 0.0, 1.0], "major_axis": [3.0, 0.0, 0.0],
                            "radius_ratio": 0.5, "start_angle": 0.0, "end_angle": 6.283185307}}
        op = entities.ir_op_for(ent)
        self.assertEqual(op["operation"], "create_ellipse")
        self.assertEqual(op["args"], {"center": {"x": 0.0, "y": 0.0, "z": 0.0},
                                       "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                                       "major_axis": {"x": 3.0, "y": 0.0, "z": 0.0},
                                       "radius_ratio": 0.5, "start_angle": 0.0,
                                       "end_angle": 6.283185307, "layer": "DIM"})
        self.assertIn(op["operation"], entities.WRITE_OP_MAP)

    def test_mtext_round_trips(self):
        ent = {"handle": "12", "layer": "TXT",
               "geometry": {"kind": "mtext", "position": [1.0, 1.0, 0.0],
                            "text": "hello", "height": 3.0}}
        op = entities.ir_op_for(ent)
        self.assertEqual(op, {"operation": "create_mtext",
                              "args": {"position": {"x": 1.0, "y": 1.0, "z": 0.0},
                                       "text": "hello", "height": 3.0, "layer": "TXT"}})
        self.assertIn(op["operation"], entities.WRITE_OP_MAP)

    def test_text_case_predates_t1_but_is_only_now_wired(self):
        # ir_op_for's kind=="text" case was already forward-declared (pre-T1
        # "Tier 2" comment); T1 only completed its Axis A/B, so the operation
        # it always emitted is finally backed by a live native handler.
        ent = {"handle": "13", "layer": "0",
               "geometry": {"kind": "text", "position": [1.0, 2.0, 0.0], "text": "hi", "height": 4.0}}
        op = entities.ir_op_for(ent)
        self.assertEqual(op["operation"], "create_text")
        self.assertIn(op["operation"], entities.WRITE_OP_MAP)
        self.assertEqual(set(op["args"]), self.arg_keys_by_patch_op["create_text"])
        self.assertEqual(op["args"], {"position": {"x": 1.0, "y": 2.0, "z": 0.0},
                                       "text": "hi", "height": 4.0, "layer": "0"})

    def test_text_case_defaults_height_when_ir_omits_it(self):
        # The manifest's arg_keys prove "height" must be present; it can't
        # prove WHAT ir_op_for defaults it to (g.get("height", 2.5)) -- pin
        # that default explicitly since it is real conversion logic.
        ent = {"handle": "13b", "layer": "0",
               "geometry": {"kind": "text", "position": [0.0, 0.0, 0.0], "text": "hi"}}
        op = entities.ir_op_for(ent)
        self.assertEqual(op["args"]["height"], 2.5)

    def test_lwpolyline_case_predates_t1_but_is_only_now_wired(self):
        # vertices -> points conversion: one vertex with an explicit bulge,
        # one relying on the implicit 0.0 default -- and note points carry
        # only x/y/bulge (2D), unlike _pt()'s x/y/z used by line/circle/arc.
        ent = {"handle": "14", "layer": "0",
               "geometry": {"kind": "lwpolyline", "closed": True,
                            "vertices": [{"point": [0, 0], "bulge": 0.5}, {"point": [1, 1]}]}}
        op = entities.ir_op_for(ent)
        self.assertEqual(op["operation"], "create_polyline")
        self.assertIn(op["operation"], entities.WRITE_OP_MAP)
        self.assertEqual(set(op["args"]), self.arg_keys_by_patch_op["create_polyline"])
        self.assertEqual(op["args"], {
            "points": [{"x": 0, "y": 0, "bulge": 0.5}, {"x": 1, "y": 1, "bulge": 0.0}],
            "closed": 1, "layer": "0"})

    def test_lwpolyline_closed_flag_is_coerced_to_int_not_bool(self):
        # int(bool(...)) in ir_op_for -- closed must be 0/1, never True/False
        # (the native job arg is a C int, not a Python bool).
        ent = {"handle": "14b", "layer": "0",
               "geometry": {"kind": "lwpolyline", "closed": False,
                            "vertices": [{"point": [0, 0]}]}}
        op = entities.ir_op_for(ent)
        self.assertEqual(op["args"]["closed"], 0)
        self.assertNotIsInstance(op["args"]["closed"], bool)

    def test_lwpolyline_vertex_without_a_point_is_skipped_not_fabricated(self):
        # "if not p: continue" -- a malformed vertex is dropped, never turned
        # into a fabricated (0, 0) point.
        ent = {"handle": "14c", "layer": "0",
               "geometry": {"kind": "lwpolyline", "closed": False,
                            "vertices": [{"bulge": 0.2}, {"point": [3, 4]}]}}
        op = entities.ir_op_for(ent)
        self.assertEqual(op["args"]["points"], [{"x": 3, "y": 4, "bulge": 0.0}])

    def test_dimension_case_predates_t1_but_is_only_now_wired(self):
        # xline1_point/xline2_point/dim_line_point (IR) -> xline1/xline2/
        # dim_line (native arg names) via _pt(), plus dim_text/rotation.
        ent = {"handle": "15", "layer": "DIM",
               "geometry": {"kind": "dimension", "dim_text": "100", "rotation": 0.0,
                            "xline1_point": [0, 0, 0], "xline2_point": [10, 0, 0],
                            "dim_line_point": [5, 1, 0]}}
        op = entities.ir_op_for(ent)
        self.assertEqual(op["operation"], "create_dimension")
        self.assertIn(op["operation"], entities.WRITE_OP_MAP)
        self.assertEqual(set(op["args"]), self.arg_keys_by_patch_op["create_dimension"])
        self.assertEqual(op["args"], {
            "layer": "DIM", "dim_text": "100", "rotation": 0.0,
            "xline1": {"x": 0, "y": 0, "z": 0}, "xline2": {"x": 10, "y": 0, "z": 0},
            "dim_line": {"x": 5, "y": 1, "z": 0}})

    def test_dimension_case_defers_when_extraction_incomplete(self):
        # Tier-3 honest deferral: if ANY of the three required points is
        # missing, ir_op_for must return None, never fabricate a partial op.
        ent = {"handle": "15b", "layer": "DIM",
               "geometry": {"kind": "dimension", "dim_text": "100",
                            "xline1_point": [0, 0, 0], "xline2_point": [10, 0, 0]}}
        self.assertIsNone(entities.ir_op_for(ent))

    def test_mpolygon_has_no_ir_to_patch_case(self):
        # 'mpolygon' is not an ir_builder._EXTRACT_KIND_TO_IR_KIND value -- no
        # real IR entity ever carries this geometry.kind, so ir_op_for
        # honestly returns None rather than fabricating a case (no-fake-success).
        # This only proves the DISPATCHER has no mpolygon branch; see
        # TestMpolygonNeverProducedByIrBuilder below for the upstream half of
        # this claim (the REAL ir_builder mapping + a realistic extraction).
        ent = {"handle": "16", "layer": "0", "geometry": {"kind": "mpolygon"}}
        self.assertIsNone(entities.ir_op_for(ent))


# A realistic dwg_geometry_extract.v1 payload (mirrors test_ir_builder.py's
# _fake_extract shape -- the repo's established "real extraction fixture"
# pattern) carrying one MPOLYGON entity, as a real accoreconsole extractor
# would emit if/when it ever surfaces this DXF type.
_MPOLYGON_EXTRACT = {
    "schema": "ariadne.dwg_geometry_extract.v1",
    "route": "dwg_truth_autocad",
    "extractor": "test_synthetic",
    "status": "ok",
    "source": {"dwg_name": "fake_mpolygon.dwg", "format": "dwg"},
    "summary": {"modelspace_count": 2, "entities_by_type": {"LINE": 1, "MPOLYGON": 1}},
    "entities": [
        {"handle": "200", "object_id": "o1", "type": "LINE", "layer": "0",
         "geometry": {"kind": "line",
                      "start": {"x": 0, "y": 0, "z": 0}, "end": {"x": 1, "y": 0, "z": 0}}},
        {"handle": "201", "object_id": "o2", "type": "MPOLYGON", "layer": "HATCH",
         "geometry": {"kind": "mpolygon",
                      "loops": [[{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}]]}},
    ],
}

_MPOLYGON_SOURCE_META = {
    "extractor": "test_synthetic", "engine_tier": "accoreconsole_lisp",
    "route": "dwg_truth_autocad", "dwg_path": "staging/golden/test/fake_mpolygon.dwg",
    "original_path": "samples/fake_mpolygon.dwg", "byte_size": 0,
}


class TestMpolygonNeverProducedByIrBuilder(unittest.TestCase):
    """The old test above only proves entities.ir_op_for's DISPATCHER has no
    'mpolygon' branch -- that alone can't back its own comment's claim that
    'no real IR entity ever carries this geometry.kind'. These two tests
    close that gap against the REAL upstream module: ir_builder is what
    actually assigns every IR entity's geometry.kind, so the claim has to be
    proven there, against the real mapping and a realistic extraction."""

    def test_mpolygon_is_not_a_reachable_ir_builder_output_kind(self):
        # Structural proof against the REAL mapping dict (not just a comment):
        # no raw extract kind can ever normalize to IR kind "mpolygon" --
        # "mpolygon" is absent from _EXTRACT_KIND_TO_IR_KIND on both sides.
        self.assertNotIn("mpolygon", ir_builder._EXTRACT_KIND_TO_IR_KIND)
        self.assertNotIn("mpolygon", ir_builder._EXTRACT_KIND_TO_IR_KIND.values())

    def test_a_real_extraction_with_an_mpolygon_entity_normalizes_to_unsupported(self):
        # Run a realistic extract containing an MPOLYGON entity through the
        # REAL build_ir_from_extract, then prove no resulting IR entity
        # carries geometry.kind == "mpolygon" anywhere in the output.
        ir = ir_builder.build_ir_from_extract(
            _MPOLYGON_EXTRACT, summary=None, source_meta=_MPOLYGON_SOURCE_META)

        kinds = [e["geometry"]["kind"] for e in ir["entities"]]
        self.assertNotIn("mpolygon", kinds)

        # The MPOLYGON entity specifically fell through to the honest
        # "unsupported" bucket -- never silently dropped, never mislabeled,
        # and correctly flagged as not decoded (no-fake-success).
        mpolygon_entity = next(e for e in ir["entities"] if e["handle"] == "201")
        self.assertEqual(mpolygon_entity["geometry"]["kind"], "unsupported")
        self.assertFalse(mpolygon_entity["source"]["decoded"])

        # And ir_op_for -- the entity write-op dispatcher -- correctly has no
        # case for what this entity actually became either.
        self.assertIsNone(entities.ir_op_for(mpolygon_entity))


class TestPromotionStuckAgainstRealRepo(unittest.TestCase):
    """Read-only regression against the REAL repo files (mirrors
    test_promote_op.py's TestAlreadyPromotedRealControlRows): proves every T1
    promotion actually landed and stays idempotent."""

    @classmethod
    def setUpClass(cls):
        cls.manifest_path = os.path.join(_REPO, "config", "promotion_manifest.json")
        cls.rows = po.load_manifest(cls.manifest_path)
        cls.matrix = po.load_f1_matrix()
        cls.by_patch_op = {r["patch_op"]: r for r in cls.rows}

    def test_every_new_row_is_already_promoted(self):
        for patch_op, native_op, _keys, _ir in _NEW_OPS:
            with self.subTest(patch_op=patch_op):
                row = self.by_patch_op[patch_op]
                self.assertEqual(row["native_op"], native_op)
                result = po.compute_promotion(row, matrix=self.matrix)
                self.assertEqual(result.status, po.ALREADY_PROMOTED)
                self.assertEqual(result.f1_class, pr.RUNNABLE)

    def test_compute_promotion_never_writes(self):
        # compute_promotion is pure; run it for every new row and confirm the
        # real tracked files are untouched (paranoia check -- a promotion tool
        # that mutates on a read-only call would silently corrupt every future
        # dry-run gate check).
        ops_v2 = os.path.join(_REPO, "config", "operations.v2.json")
        fam = os.path.join(_REPO, "tools", "patch_ops", "entities.py")
        with open(ops_v2, "r", encoding="utf-8-sig") as fh:
            before_ops = fh.read()
        with open(fam, "r", encoding="utf-8") as fh:
            before_fam = fh.read()

        for patch_op, _native_op, _keys, _ir in _NEW_OPS:
            po.compute_promotion(self.by_patch_op[patch_op], matrix=self.matrix)

        with open(ops_v2, "r", encoding="utf-8-sig") as fh:
            self.assertEqual(fh.read(), before_ops)
        with open(fam, "r", encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before_fam)


class TestSetEntityXdataIsDatabaseLevelNotEntityLevel(unittest.TestCase):
    """set_entity_xdata's native handler (m08eHandleEntitySetXdata in
    src/Ariadne.AcadNative/families/m08e_handlers.inc) calls
    setDatabaseXdata(ctx.pDb, app, value) -- a DATABASE-level call with no
    entity handle argument anywhere in its shape. The patch_op name
    ("set_ENTITY_xdata") overpromises per-entity targeting; renaming it is out
    of scope (a structural registry/manifest change, not a description-text
    fix), so this closes the gap with explicit docs instead:
      (a) set_xdata (native_op write.xdata.set, still F1-pending/REJECTED)
          and set_entity_xdata (native_op write.entity.set_xdata, promoted)
          are two genuinely distinct ops that must never collide.
      (b) config/operations.v2.json's write.entity.set_xdata record now
          states DATABASE-level scope explicitly in both "summary" and
          "handler.native_api" (which previously and wrongly claimed
          AcDbObject::setXData, an entity-level API this handler never
          calls) -- see the description-text-only diff for this ticket.
      (c) a tripwire: the moment set_entity_xdata's arg shape grows beyond
          {app, value} (e.g. an entity "handle"), THIS test fails, forcing
          whoever makes that change to also revisit the DATABASE-level
          semantics docs in patch_ops/entities.py and the registry above."""

    @classmethod
    def setUpClass(cls):
        manifest_path = os.path.join(_REPO, "config", "promotion_manifest.json")
        cls.by_patch_op = {r["patch_op"]: r for r in po.load_manifest(manifest_path)}
        ops_v2_path = os.path.join(_REPO, "config", "operations.v2.json")
        with open(ops_v2_path, "r", encoding="utf-8-sig") as fh:
            cls.ops_v2_doc = json.load(fh)

    def _op_record(self, op_id):
        return next(o for o in self.ops_v2_doc["operations"] if o["id"] == op_id)

    def test_set_xdata_and_set_entity_xdata_are_distinct_manifest_rows(self):
        # (a) Both exist as real, independent manifest rows with distinct
        # native_op targets -- never the same op wearing two patch_op names.
        xdata_row = self.by_patch_op["set_xdata"]
        entity_xdata_row = self.by_patch_op["set_entity_xdata"]
        self.assertEqual(xdata_row["native_op"], "write.xdata.set")
        self.assertEqual(entity_xdata_row["native_op"], "write.entity.set_xdata")
        self.assertNotEqual(xdata_row["native_op"], entity_xdata_row["native_op"])

    def test_no_key_collision_in_the_aggregate_write_op_map(self):
        # (a) set_entity_xdata is wired today; set_xdata is honestly not yet
        # promoted (F1-pending -- see test_promote_op.py::
        # TestRealManifestPendingRowsAllRejected). If/when set_xdata IS wired,
        # it must land under its OWN "set_xdata" key with its OWN native_op
        # (write.xdata.set), never overwrite or alias onto set_entity_xdata's
        # entry in the merged patch_ops.NATIVE_WRITE_OP_MAP/patch_engine one
        # (same aggregate dict object -- test_patch_ops_split.py pins that).
        self.assertEqual(patch_ops.NATIVE_WRITE_OP_MAP.get("set_entity_xdata"),
                          "write.entity.set_xdata")
        self.assertNotEqual(patch_ops.NATIVE_WRITE_OP_MAP.get("set_xdata"),
                             "write.entity.set_xdata")
        self.assertNotEqual(patch_engine.NATIVE_WRITE_OP_MAP.get("set_xdata"),
                             "write.entity.set_xdata")

    def test_registry_summary_and_native_api_document_database_level_scope(self):
        # (b) The registry description text for write.entity.set_xdata must
        # say DATABASE-level explicitly and must no longer claim the
        # entity-level AcDbObject::setXData API this handler never calls.
        rec = self._op_record("write.entity.set_xdata")
        summary = rec.get("summary", "")
        native_api = rec.get("handler", {}).get("native_api", "")
        self.assertIn("DATABASE-level", summary)
        self.assertIn("setDatabaseXdata", native_api)
        self.assertIn("DATABASE-level", native_api)
        self.assertNotIn("AcDbObject::setXData(const resbuf* xdata)", native_api)

    def test_set_entity_xdata_arg_shape_tripwire_no_entity_handle_arg(self):
        # (c) TRIPWIRE: write.entity.set_xdata accepts EXACTLY {app, value}
        # today -- no entity handle. If a future change adds a "handle" (or
        # any entity-targeting) arg key here, THIS ASSERTION MUST FAIL,
        # forcing the change's author to update the DATABASE-level semantics
        # docstring in patch_ops/entities.py and the registry summary/
        # native_api text above BEFORE loosening this assertion.
        row = self.by_patch_op["set_entity_xdata"]
        self.assertEqual(
            set(row["arg_keys"]), {"app", "value"},
            "write.entity.set_xdata's arg_keys changed beyond {app, value} -- if an "
            "entity handle was added, this op is no longer purely DATABASE-level; update "
            "the semantics docstring in patch_ops/entities.py and the registry summary/"
            "native_api for write.entity.set_xdata in config/operations.v2.json before "
            "changing this assertion.")

        probe = entities.build_job_args(
            "write.entity.set_xdata", {"app": "A", "value": "V", "handle": "1A2B"})
        self.assertEqual(
            set(probe), {"app", "value"},
            "build_job_args now passes a key beyond {app, value} through for "
            "write.entity.set_xdata -- see the assertion message above.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
