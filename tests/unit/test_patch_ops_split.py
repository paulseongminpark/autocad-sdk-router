#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer F9 TEST -- patch_ops family split: aggregate == pre-split map.

Intent (WHY -- this pins the PLAN F9 refactor's one hard invariant):
  patch_engine.NATIVE_WRITE_OP_MAP and ir_to_patch._op_for used to be a single
  if/elif chain each; PLAN F9 split them by family (entities/blocks/tables/db)
  under tools/patch_ops/ so parallel writers touch disjoint files. A split like
  this has exactly one way to silently break: the aggregate drifts from what
  the pre-split code produced (a family module claims the wrong op_id, or two
  families both claim the same op_id and shadow each other in the merge). These
  tests pin the pre-split behavior as a literal oracle so a future family-module
  edit that changes what patch_engine/ir_to_patch emit for the currently-wired
  ops fails loudly here, not downstream in a live AutoCAD apply.

Stdlib only. Discoverable by pytest and ``python -m unittest discover -s tests``.

CADOS F8 / H-5 update: set_layer's pinned target below was corrected from
write.layer.create to modify.entity.common. The pre-split value
(write.layer.create) was an active fake-success -- it only ensured a layer
existed and silently ignored 'handle', never reassigning an existing entity's
layer. This oracle now pins the CORRECTED post-H-5 shape (the real relayer),
not the original pre-split bug; the F9 partition invariants below (aggregate
== per-family union, families disjoint) still hold unchanged.

WAVE-1 TIER-1 T1 update (tools/promote_op.py F2 promotion): 8 more entity ops
(create_arc/create_ellipse/create_mpolygon/create_mtext/create_text/
create_polyline/create_dimension/set_entity_xdata) went from not_implemented
to a live native handler -- see config/promotion_manifest.json and
tests/unit/test_promote_op.py for the F1-RUNNABLE gate each one cleared. The
oracle below is extended to the new post-promotion ground truth; this file's
invariants (aggregate == per-family union, families disjoint) are unaffected.

T3a-batch2 update: 4 more entity ops (create_spline/create_dimension_aligned/
create_dimension_radial/create_dimension_diametric) were already native-
REACHABLE (measure/reachable_matrix.jsonl: registry_status=implemented,
class=REACHABLE) but had no patch_ops.WRITE_OP_MAP entry at all -- this is the
first patch-level wiring for these four. Oracle extended accordingly; same
invariants unaffected.

T3a-batch3 update: create_dimension_ordinate (write.entity.dim.ordinate) and
create_leader (write.entity.leader) were already native-REACHABLE (measure/
reachable_matrix.jsonl) but had no patch_ops.WRITE_OP_MAP entry -- same
two-part gap as T3a-batch2's four ops. Oracle extended accordingly; same
invariants unaffected.

w3-wbug update: create_mline (write.entity.mline) gains its first-ever
patch_ops wiring alongside a real native bugfix (the handler never checked
ObjectARX ErrorStatus at all, so a failing appendSeg still reported a fake
success with a geometrically-empty MLINE -- see m08g_handlers.inc). Oracle
extended accordingly; same invariants unaffected.

w3-dimarc update: create_dimension_arc (write.entity.dim.arc, AcDbArcDimension)
was already native-REACHABLE (measure/reachable_matrix.jsonl) but had no
patch_ops.WRITE_OP_MAP entry -- same two-part gap (patch_ops wiring +
collectModelSpaceGraph read branch) as every T3a-batch* dimension subtype
above. Oracle extended accordingly; same invariants unaffected.

w3-ang2 update: create_dimension_angular2line (write.entity.dim.angular2line,
AcDb2LineAngularDimension) was already native-REACHABLE (measure/
reachable_matrix.jsonl) but had no patch_ops.WRITE_OP_MAP entry -- same
two-part gap (patch_ops wiring + collectModelSpaceGraph read branch) as
every T3a-batch*/w3-dimarc dimension subtype above. Oracle extended
accordingly; same invariants unaffected.

w3-ang3 update: create_dimension_angular3pt (write.entity.dim.angular3pt,
AcDb3PointAngularDimension) was already native-REACHABLE (measure/
reachable_matrix.jsonl) but had no patch_ops.WRITE_OP_MAP entry -- same
two-part gap (patch_ops wiring + collectModelSpaceGraph read branch) as
every T3a-batch*/w3-dimarc/w3-ang2 dimension subtype above. Oracle extended
accordingly; same invariants unaffected.

w3-mleader update: create_mleader (write.entity.mleader, AcDbMLeader) was
already native-REACHABLE (measure/reachable_matrix.jsonl) but had no
patch_ops.WRITE_OP_MAP entry -- same two-part gap (patch_ops wiring +
collectModelSpaceGraph read branch) as create_leader before it. Oracle
extended accordingly; same invariants unaffected.

w3-poly2d update: create_polyline2d (write.entity.polyline2d) was already
native-REACHABLE (measure/reachable_matrix.jsonl) but had no patch_ops.
WRITE_OP_MAP entry -- UNLIKE every prior batch above, it needed NO NEW
collectModelSpaceGraph read branch at all: write.entity.polyline2d is an
alias for write.entity.polyline in m08g_handlers.inc (same AcDbPolyline/
LWPOLYLINE code path, already read). Oracle extended accordingly; same
invariants unaffected.

w3-poly3d update: create_polyline3d (write.entity.polyline3d, AcDb3d
Polyline) was already native-REACHABLE (measure/reachable_matrix.jsonl) but
had no patch_ops.WRITE_OP_MAP entry -- like w3-poly2d, needed NO NEW
collectModelSpaceGraph read branch (AcDb3dPolyline's read branch pre-dates
any wired create op for it, T3a). Oracle extended accordingly; same
invariants unaffected.

w3-pmesh update: create_polygonmesh (write.entity.polygonmesh, AcDbPolygon
Mesh) was already native-REACHABLE (measure/reachable_matrix.jsonl) but had
NEITHER a patch_ops.WRITE_OP_MAP entry NOR a collectModelSpaceGraph read
branch (unlike w3-poly2d/w3-poly3d, AcDbPolygonMesh had never been read
before this batch). Oracle extended accordingly; same invariants unaffected.

w3-pfmesh update: create_polyfacemesh (write.entity.polyfacemesh, AcDbPoly
FaceMesh) was already native-REACHABLE (measure/reachable_matrix.jsonl) but
had NEITHER a patch_ops.WRITE_OP_MAP entry NOR a collectModelSpaceGraph read
branch -- same two-part gap as w3-pmesh just above. A live create-only probe
(direct patch_engine.apply_staged call) de-risked the attended-only trap
first (net modelspace +1, class=AcDbPolyFaceMesh, original DWG byte-
identical) before the read branch + rebuild were invested in. Oracle extended
accordingly; same invariants unaffected.
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

# The pre-split NATIVE_WRITE_OP_MAP, pinned as a literal oracle (set_layer
# corrected per CADOS F8/H-5; 8 new entries added per WAVE-1 TIER-1 T1 -- see
# module docstring above).
_ORIGINAL_NATIVE_WRITE_OP_MAP = {
    "create_line": "write.entity.line",
    "create_circle": "write.entity.circle",
    "set_layer": "modify.entity.common",
    "create_layer": "write.layer.create",
    "create_arc": "write.entity.arc",
    "create_ellipse": "write.entity.ellipse",
    "create_mpolygon": "write.entity.mpolygon",
    "create_mtext": "write.entity.mtext",
    "create_text": "write.entity.text",
    "create_polyline": "write.entity.polyline",
    "create_dimension": "write.entity.dim.rotated",
    "set_entity_xdata": "write.entity.set_xdata",
    "create_spline": "write.entity.spline",
    "create_dimension_aligned": "write.entity.dim.aligned",
    "create_dimension_radial": "write.entity.dim.radial",
    "create_dimension_diametric": "write.entity.dim.diametric",
    "create_dimension_ordinate": "write.entity.dim.ordinate",
    "create_leader": "write.entity.leader",
    "create_mline": "write.entity.mline",
    "create_dimension_arc": "write.entity.dim.arc",
    "create_dimension_angular2line": "write.entity.dim.angular2line",
    "create_dimension_angular3pt": "write.entity.dim.angular3pt",
    "create_mleader": "write.entity.mleader",
    "create_polyline2d": "write.entity.polyline2d",
    "create_polyline3d": "write.entity.polyline3d",
    "create_polygonmesh": "write.entity.polygonmesh",
    "create_polyfacemesh": "write.entity.polyfacemesh",
}


def _original_native_job_doc(native_op, args):
    """The pre-split _native_job_doc if/elif chain, reproduced as an oracle."""
    job = {
        "schema": "ariadne.autocad_sdk_job.v2",
        "operation": native_op,
        "write_mode": "write_copy",
        "policy": {"write_mode": "write_copy", "require_staged_copy": True,
                   "save": True, "lock_document": True},
        "source_agent": "patch_engine",
        "args": {},
    }
    if native_op == "write.entity.line":
        for k in ("start", "end", "layer"):
            if k in args:
                job["args"][k] = args[k]
    elif native_op == "write.entity.circle":
        for k in ("center", "radius", "layer"):
            if k in args:
                job["args"][k] = args[k]
    elif native_op == "write.layer.create":
        name = args.get("name") or args.get("layer")
        if name is not None:
            job["args"]["name"] = name
        if "color_index" in args:
            job["args"]["color_index"] = args["color_index"]
    elif native_op == "modify.entity.common":
        # set_layer's corrected (post-H-5) shape: 'handle' resolves the
        # target entity, 'layer' becomes the native 'set_layer' field.
        if "handle" in args:
            job["args"]["handle"] = args["handle"]
        if "layer" in args:
            job["args"]["set_layer"] = args["layer"]
    return job


def _pt(arr):
    if not arr:
        return None
    return {"x": arr[0], "y": arr[1], "z": arr[2] if len(arr) > 2 else 0.0}


def _original_op_for(ent):
    """The pre-split ir_to_patch._op_for if-chain, reproduced as an oracle."""
    g = ent.get("geometry") or {}
    kind = g.get("kind")
    layer = ent.get("layer")
    if kind == "line":
        return {"operation": "create_line",
                "args": {"start": _pt(g.get("start")), "end": _pt(g.get("end")), "layer": layer}}
    if kind == "circle":
        return {"operation": "create_circle",
                "args": {"center": _pt(g.get("center")), "radius": g.get("radius"), "layer": layer}}
    if kind == "block_reference":
        return {"operation": "insert_block",
                "args": {"name": g.get("block_name"), "position": _pt(g.get("position"))}}
    if kind == "text":
        return {"operation": "create_text",
                "args": {"position": _pt(g.get("position")), "text": g.get("text"),
                         "height": g.get("height", 2.5), "layer": layer}}
    if kind in ("lwpolyline", "polyline"):
        points = []
        for v in (g.get("vertices") or []):
            p = v.get("point") if isinstance(v, dict) else v
            if not p:
                continue
            points.append({"x": p[0], "y": p[1],
                           "bulge": (v.get("bulge", 0.0) if isinstance(v, dict) else 0.0)})
        return {"operation": "create_polyline",
                "args": {"points": points, "closed": int(bool(g.get("closed"))), "layer": layer}}
    if kind == "dimension":
        need = ("xline1_point", "xline2_point", "dim_line_point")
        if all(g.get(x) for x in need):
            return {"operation": "create_dimension",
                    "args": {"layer": layer, "dim_text": g.get("dim_text", ""),
                             "rotation": g.get("rotation", 0.0),
                             "xline1": _pt(g["xline1_point"]), "xline2": _pt(g["xline2_point"]),
                             "dim_line": _pt(g["dim_line_point"])}}
        return None
    return None


class TestNativeWriteOpMapAggregate(unittest.TestCase):
    def setUp(self):
        import patch_engine
        import patch_ops
        self.pe = patch_engine
        self.ops = patch_ops

    def test_aggregate_equals_pre_split_map(self):
        self.assertEqual(self.pe.NATIVE_WRITE_OP_MAP, _ORIGINAL_NATIVE_WRITE_OP_MAP)

    def test_patch_engine_and_patch_ops_expose_the_same_map(self):
        self.assertIs(self.pe.NATIVE_WRITE_OP_MAP, self.ops.NATIVE_WRITE_OP_MAP)

    def test_family_write_op_maps_are_disjoint(self):
        # Load-bearing invariant: if two families ever claim the same op_id,
        # the dict-merge in patch_ops/__init__.py would silently let one
        # shadow the other. Prove every op_id in the aggregate came from
        # exactly one family.
        from patch_ops import blocks, db, entities, tables
        families = {"entities": entities.WRITE_OP_MAP, "blocks": blocks.WRITE_OP_MAP,
                    "tables": tables.WRITE_OP_MAP, "db": db.WRITE_OP_MAP}
        seen = {}
        for fam_name, m in families.items():
            for op_id in m:
                self.assertNotIn(op_id, seen,
                                 "%s claimed by both %s and %s" % (op_id, seen.get(op_id), fam_name))
                seen[op_id] = fam_name
        self.assertEqual(set(seen), set(self.pe.NATIVE_WRITE_OP_MAP))


class TestNativeJobDocByteIdentical(unittest.TestCase):
    """_native_job_doc must still produce exactly what the pre-split if/elif
    chain produced, for every wired native_op (the roundtrip the packet gates
    on) plus one unrecognized native_op (falls through to empty args)."""

    def setUp(self):
        import patch_engine
        self.pe = patch_engine

    def test_wired_ops_byte_identical_to_pre_split_oracle(self):
        cases = [
            ("write.entity.line", {"start": [0, 0, 0], "end": [10, 0, 0], "layer": "0"}),
            ("write.entity.circle", {"center": [1, 2, 0], "radius": 5, "layer": "DIM"}),
            ("write.layer.create", {"name": "WALLS", "color_index": 3}),  # create_layer's args shape
            ("modify.entity.common", {"handle": "2A", "layer": "DOORS"}),  # set_layer's args shape (F8/H-5)
        ]
        for native_op, args in cases:
            with self.subTest(native_op=native_op, args=args):
                self.assertEqual(self.pe._native_job_doc(native_op, args),
                                 _original_native_job_doc(native_op, args))

    def test_unrecognized_native_op_falls_through_to_empty_args(self):
        got = self.pe._native_job_doc("write.entity.unknown", {"whatever": 1})
        self.assertEqual(got, _original_native_job_doc("write.entity.unknown", {"whatever": 1}))
        self.assertEqual(got["args"], {})


class TestIrOpForByteIdentical(unittest.TestCase):
    """ir_to_patch._op_for must still produce exactly what the pre-split
    if-chain produced, for every kind it ever handled."""

    def setUp(self):
        import ir_to_patch
        self.mod = ir_to_patch

    def test_every_original_kind_branch_byte_identical(self):
        fixture = [
            {"handle": "1", "layer": "0",
             "geometry": {"kind": "line", "start": [0, 0, 0], "end": [1, 1, 0]}},
            {"handle": "2", "layer": "DIM",
             "geometry": {"kind": "circle", "center": [0, 0, 0], "radius": 2.5}},
            {"handle": "3", "layer": "0",
             "geometry": {"kind": "block_reference", "block_name": "DOOR", "position": [5, 5, 0]}},
            {"handle": "4", "layer": "TXT",
             "geometry": {"kind": "text", "position": [1, 1, 0], "text": "hi", "height": 3.0}},
            {"handle": "5", "layer": "0",
             "geometry": {"kind": "lwpolyline", "closed": True,
                          "vertices": [{"point": [0, 0], "bulge": 0.5}, [1, 1]]}},
            {"handle": "6", "layer": "DIM",
             "geometry": {"kind": "dimension", "dim_text": "100",
                          "xline1_point": [0, 0, 0], "xline2_point": [10, 0, 0],
                          "dim_line_point": [5, 1, 0]}},
            {"handle": "7", "layer": "DIM", "geometry": {"kind": "dimension"}},  # no geometry -> deferred
            {"handle": "8", "layer": "0", "geometry": {"kind": "hatch"}},  # unregenerable -> deferred
        ]
        for ent in fixture:
            with self.subTest(handle=ent["handle"], kind=ent["geometry"]["kind"]):
                self.assertEqual(self.mod._op_for(ent), _original_op_for(ent))

    def test_build_patch_from_ir_end_to_end_counts(self):
        # 1 regenerable + 2 deferred (a 'dimension' w/o extracted geometry, and
        # the unregenerable 'hatch' kind) over a small fixture.
        fixture = [
            {"handle": "1", "layer": "0", "geometry": {"kind": "line", "start": [0, 0, 0], "end": [1, 1, 0]}},
            {"handle": "7", "layer": "DIM", "geometry": {"kind": "dimension"}},
            {"handle": "8", "layer": "0", "geometry": {"kind": "hatch"}},
        ]
        patch, deferred = self.mod.build_patch_from_ir(
            {"entities": fixture}, {"staged_path": "s", "original_path": "o"}, "t")
        self.assertEqual(len(patch["operations"]), 1)
        self.assertEqual(len(deferred), 2)


if __name__ == "__main__":
    unittest.main()
