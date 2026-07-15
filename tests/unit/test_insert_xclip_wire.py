#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEST -- block-reference XCLIP wire survival: native graph -> IR -> schema.

Intent (WHY):
  * Issues #27 + #33 (PR #29 field shape): collectEntitiesFromBlock extracts the
    AcDbSpatialFilter (ACAD_FILTER/SPATIAL) hung off a clipped INSERT's own
    extension dictionary and emits a nested "xclip" object carrying the boundary
    in THREE spaces -- verbatim clip space ("boundary"), block-local
    ("boundary_block", what a consumer like ezdxf set_block_clipping_path needs),
    and WCS ("boundary_wcs") -- plus the clip->block 4x4 ("inv_block_xform").
    This test proves the xclip survives ir_builder.build_ir_from_database_graph's
    native-graph -> IR lift (_entity_from_native drops any raw field it does not
    list) and that xclip is NOT identity-bearing (a re-clip must read as a
    MODIFY, not delete+create).
  * The new "xclip" field must validate against dwg_graph_ir.v1 both present and
    absent (additive schema change must not break older IR).

Hermetic: stdlib only (plus optional jsonschema, matching test_schemas_v2.py).
No native build, no AutoCAD, no real DWG.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))  # tests/unit -> tests -> repo
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SCHEMAS_DIR = os.path.join(_REPO, "schemas")
_JSON_ENCODING = "utf-8-sig"  # config/schema JSON on this box carries a UTF-8 BOM


def _load_schema():
    with open(os.path.join(_SCHEMAS_DIR, "dwg_graph_ir.v1.schema.json"),
              "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _try_import_jsonschema():
    try:
        import jsonschema  # type: ignore
        return jsonschema
    except Exception:  # pragma: no cover - environment without jsonschema
        return None


_XCLIP = {
    "enabled": True,
    "inverted": False,
    "elevation": 0.0,
    "front_clip": 0.0,
    "back_clip": 0.0,
    "normal": [0.0, 0.0, 1.0],
    # 2-point rectangular window, VERBATIM clip space (not expanded)...
    "boundary": [[0.0, 0.0], [100.0, 50.0]],
    # ...expanded to 4 corners in clip space, then transformed to block-local
    # (#33). Identity transform here, so corners == the expanded window.
    "boundary_block": [[0.0, 0.0], [100.0, 0.0], [100.0, 50.0], [0.0, 50.0]],
    "boundary_wcs": [[0.0, 0.0, 0.0], [100.0, 50.0, 0.0]],
    "inv_block_xform": [1.0, 0.0, 0.0, 0.0,
                        0.0, 1.0, 0.0, 0.0,
                        0.0, 0.0, 1.0, 0.0,
                        0.0, 0.0, 0.0, 1.0],
}


def _native_block_refs():
    """Two block references with IDENTICAL content except that handle 200 is
    XCLIP-clipped and 201 is not (and their handles differ). Shaped exactly like
    collectEntitiesFromBlock's AcDbBlockReference JSON."""
    base = {
        "dxf_name": "AcDbBlockReference", "layer": "0", "owner_handle": "1F",
        "space": "model", "block_name": "DESK", "block_record_handle": "7A",
        "position": [10.0, 20.0, 0.0], "scale": [1.0, 1.0, 1.0], "rotation": 0.0,
    }
    clipped = dict(base, handle="200", xclip=json.loads(json.dumps(_XCLIP)))
    unclipped = dict(base, handle="201")
    return [clipped, unclipped]


def _build_ir(entities):
    import ir_builder
    graph_result = {"entities": entities, "modelspace_entities": len(entities)}
    return ir_builder.build_ir_from_database_graph(graph_result, {"dwg_path": "fake.dwg"})


class TestXclipSurvivesNativeLift(unittest.TestCase):
    def setUp(self):
        self.ir = _build_ir(_native_block_refs())
        self.entities = {e["handle"]: e for e in self.ir["entities"]}

    def test_xclip_survives_verbatim(self):
        self.assertEqual(self.entities["200"].get("xclip"), _XCLIP)

    def test_xclip_boundary_spaces_all_present(self):
        # #33: all three boundary spaces + the clip->block matrix must survive.
        xc = self.entities["200"]["xclip"]
        self.assertEqual(xc["boundary"], _XCLIP["boundary"])
        self.assertEqual(xc["boundary_block"], _XCLIP["boundary_block"])
        self.assertEqual(xc["boundary_wcs"], _XCLIP["boundary_wcs"])
        self.assertEqual(len(xc["inv_block_xform"]), 16)

    def test_unclipped_block_reference_has_no_xclip_key(self):
        self.assertNotIn("xclip", self.entities["201"])

    def test_xclip_is_not_identity_bearing(self):
        # 200 (clipped) and 201 (unclipped) are identical in every non-excluded
        # field; xclip + handle are excluded from stable identity, so a re-clip
        # must not change the stable_id (diffs as MODIFY, not delete+create).
        self.assertEqual(self.entities["200"]["stable_id"],
                         self.entities["201"]["stable_id"])


class TestXclipSchemaConformance(unittest.TestCase):
    def setUp(self):
        self.jsonschema = _try_import_jsonschema()
        if self.jsonschema is None:
            self.skipTest("SKIPPED_DEP: jsonschema not importable")
        self.schema = _load_schema()

    def _assert_validates(self, ir, msg):
        validator = self.jsonschema.Draft7Validator(self.schema)
        errors = sorted(validator.iter_errors(ir), key=lambda e: list(e.path))
        self.assertEqual(
            errors, [],
            msg + ": " + "; ".join(
                "%s: %s" % ("/".join(str(p) for p in e.path), e.message)
                for e in errors[:10]),
        )

    def test_ir_with_and_without_clip_validates(self):
        # Mixed batch: one clipped block ref + one unclipped -> both shapes must
        # validate under the additive dwg_graph_ir.v1 clip property.
        self._assert_validates(
            _build_ir(_native_block_refs()),
            "IR with block_reference clip failed dwg_graph_ir.v1")


if __name__ == "__main__":
    unittest.main()
