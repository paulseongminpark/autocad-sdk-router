#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEST -- entity color_index/true_color wire survival: native graph -> IR -> schema.

Intent (WHY):
  * SBC-20260714-001 PR-A (issues #24 + #28): collectEntitiesFromBlock now emits
    raw ACI color_index (verbatim sentinels -- 0=ByBlock, 256=ByLayer, 1-255=ACI)
    and an optional true_color {r,g,b} for entities with an explicit RGB color.
    This test proves both fields actually survive
    ir_builder.build_ir_from_database_graph's native-graph -> IR lift, which
    historically dropped any raw field it did not explicitly list (see
    _entity_from_native) -- color_index/true_color were exactly such a gap.
  * MTEXT's raw inline color-run codes (\\C<aci>; / \\c<truecolor>;) are already
    preserved verbatim by the pre-existing "text" lift; this test locks that in
    with an assertion rather than new production code.
  * The new optional fields must validate against dwg_graph_ir.v1 both present
    and absent (back-compat: additive schema change must not break older IR).

Discoverable by pytest and ``python -m unittest discover -s tests``.
Stdlib only (plus optional ``jsonschema``, matching test_schemas_v2.py).
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


def _native_entities_with_color():
    """Synthetic entities shaped exactly like collectEntitiesFromBlock's JSON
    (handle/dxf_name/layer/owner_handle/space + color_index/true_color)."""
    return [
        # (a) ByLayer sentinel -- must survive as 256, not resolved/dropped.
        # Also carries the PR #29 display set: color_method + an entity linetype
        # override (dashed HID on a Continuous layer) + ByLayer lineweight (-1).
        {"handle": "100", "dxf_name": "AcDbLine", "layer": "0",
         "owner_handle": "1F", "space": "model", "color_index": 256,
         "color_method": "bylayer", "linetype": "HID", "lineweight": -1,
         "start": [0.0, 0.0, 0.0], "end": [10.0, 0.0, 0.0]},
        # (b) ByBlock sentinel -- must survive as 0, not dropped as falsy.
        # lineweight ByBlock sentinel (-2) rides along.
        {"handle": "101", "dxf_name": "AcDbLine", "layer": "0",
         "owner_handle": "1F", "space": "model", "color_index": 0,
         "color_method": "byblock", "lineweight": -2,
         "start": [0.0, 0.0, 0.0], "end": [0.0, 10.0, 0.0]},
        # (c) explicit ACI color.
        {"handle": "102", "dxf_name": "AcDbLine", "layer": "WALLS",
         "owner_handle": "1F", "space": "model", "color_index": 7,
         "color_method": "byaci",
         "start": [1.0, 1.0, 0.0], "end": [2.0, 2.0, 0.0]},
        # (d) explicit 24-bit RGB (true_color), alongside its raw ACI shadow value.
        {"handle": "103", "dxf_name": "AcDbLine", "layer": "WALLS",
         "owner_handle": "1F", "space": "model", "color_index": 1,
         "color_method": "bycolor", "true_color": {"r": 255, "g": 0, "b": 0},
         "linetype": "Continuous", "lineweight": 50,
         "start": [3.0, 3.0, 0.0], "end": [4.0, 4.0, 0.0]},
        # (e) MTEXT whose raw contents() carries inline color-run codes.
        {"handle": "104", "dxf_name": "AcDbMText", "layer": "0",
         "owner_handle": "1F", "space": "model", "color_index": 256,
         "position": [0.0, 0.0, 0.0], "text": "\\C1;red \\C0;black"},
    ]


def _build_ir(entities):
    import ir_builder
    graph_result = {"entities": entities, "modelspace_entities": len(entities)}
    return ir_builder.build_ir_from_database_graph(graph_result, {"dwg_path": "fake.dwg"})


class TestEntityColorSurvivesNativeLift(unittest.TestCase):
    """color_index/true_color must survive build_ir_from_database_graph verbatim."""

    def setUp(self):
        self.ir = _build_ir(_native_entities_with_color())
        self.entities = {e["handle"]: e for e in self.ir["entities"]}

    def test_bylayer_sentinel_256_survives_verbatim(self):
        self.assertEqual(self.entities["100"].get("color_index"), 256)
        self.assertNotIn("true_color", self.entities["100"])

    def test_byblock_sentinel_0_survives_verbatim(self):
        # 0 is falsy in Python -- a naive `if raw.get("color_index"):` guard
        # would silently drop this sentinel. Must come through as int 0.
        entity = self.entities["101"]
        self.assertIn("color_index", entity)
        self.assertEqual(entity["color_index"], 0)

    def test_explicit_aci_color_survives(self):
        self.assertEqual(self.entities["102"].get("color_index"), 7)

    def test_true_color_rgb_survives(self):
        self.assertEqual(self.entities["103"].get("true_color"),
                          {"r": 255, "g": 0, "b": 0})
        self.assertEqual(self.entities["103"].get("color_index"), 1)

    def test_mtext_raw_inline_color_run_codes_survive(self):
        text = self.entities["104"]["geometry"].get("text", "")
        self.assertEqual(text, "\\C1;red \\C0;black")
        self.assertIn("\\C1;", text)
        self.assertIn("\\C0;", text)

    def test_color_method_survives(self):
        # #24/#28 (PR #29): color_method rides alongside color_index.
        self.assertEqual(self.entities["100"].get("color_method"), "bylayer")
        self.assertEqual(self.entities["101"].get("color_method"), "byblock")
        self.assertEqual(self.entities["102"].get("color_method"), "byaci")
        self.assertEqual(self.entities["103"].get("color_method"), "bycolor")

    def test_linetype_and_lineweight_survive(self):
        # #34 (PR #29): entity linetype NAME + lineweight (1/100 mm or the
        # -1=ByLayer/-2=ByBlock/-3=Default sentinels). The HID override on a
        # Continuous layer is exactly the dashed-lost-to-solid case from the issue.
        self.assertEqual(self.entities["100"].get("linetype"), "HID")
        self.assertEqual(self.entities["100"].get("lineweight"), -1)
        self.assertEqual(self.entities["101"].get("lineweight"), -2)
        self.assertEqual(self.entities["103"].get("linetype"), "Continuous")
        self.assertEqual(self.entities["103"].get("lineweight"), 50)


class TestDisplayAttrsNotIdentityBearing(unittest.TestCase):
    """color/linetype/lineweight are DISPLAY attrs: a recolor/re-linetype must
    diff as a MODIFY of the same entity, so they must NOT enter stable_id."""

    def test_recolor_and_relinetype_keep_stable_id(self):
        base = {"dxf_name": "AcDbLine", "layer": "0", "owner_handle": "1F",
                "space": "model",
                "start": [0.0, 0.0, 0.0], "end": [10.0, 0.0, 0.0]}
        a = dict(base, handle="300", color_index=1, color_method="byaci",
                 linetype="HID", lineweight=50)
        b = dict(base, handle="301", color_index=256, color_method="bylayer",
                 true_color=None, linetype="Continuous", lineweight=-1)
        b = {k: v for k, v in b.items() if v is not None}
        ir = _build_ir([a, b])
        by_handle = {e["handle"]: e for e in ir["entities"]}
        self.assertEqual(by_handle["300"]["stable_id"], by_handle["301"]["stable_id"],
                         "display attrs leaked into stable identity")


class TestEntityColorSchemaConformance(unittest.TestCase):
    """New optional entity fields validate present AND absent (back-compat)."""

    def setUp(self):
        self.jsonschema = _try_import_jsonschema()
        if self.jsonschema is None:
            self.skipTest("SKIPPED_DEP: jsonschema not importable")
        self.schema = _load_schema()

    def _assert_ir_validates(self, ir, msg):
        validator = self.jsonschema.Draft7Validator(self.schema)
        errors = sorted(validator.iter_errors(ir), key=lambda e: list(e.path))
        self.assertEqual(
            errors, [],
            msg + ": " + "; ".join(
                "%s: %s" % ("/".join(str(p) for p in e.path), e.message)
                for e in errors[:10]),
        )

    def test_ir_with_color_index_and_true_color_validates(self):
        ir = _build_ir(_native_entities_with_color())
        self._assert_ir_validates(
            ir, "IR carrying color_index/true_color failed dwg_graph_ir.v1")

    def test_ir_without_color_fields_still_validates(self):
        """Back-compat: an entity carrying neither field (older extractor
        output) must still validate -- the new fields are additive-only."""
        entities = [{"handle": "200", "dxf_name": "AcDbLine", "layer": "0",
                     "owner_handle": "1F", "space": "model",
                     "start": [0.0, 0.0, 0.0], "end": [1.0, 1.0, 0.0]}]
        ir = _build_ir(entities)
        entity = ir["entities"][0]
        self.assertNotIn("color_index", entity)
        self.assertNotIn("true_color", entity)
        self._assert_ir_validates(
            ir, "IR without color fields (back-compat) failed dwg_graph_ir.v1")


if __name__ == "__main__":
    unittest.main()
