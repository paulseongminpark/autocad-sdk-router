#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEST -- tools/build_from_ir.py: the IR -> DXF regenerator's defect regressions.

Intent (WHY):
  Every test in the "issue regression" classes below pins ONE defect the HDC 267
  / Okpo 16 round-trip campaign found and fixed (GitHub issues #49, #51, #53,
  #54, #55, #56, #58, #59, #60). The campaign's fixes live on a collaborator's
  machine; these tests are what stops the SAME defect from being reintroduced
  here. Each test therefore asserts the OBSERVABLE end state (reload the written
  DXF and read it back), not the code path taken -- a fix that only works
  in-memory is not a fix, because the pipeline's next step is DXF -> DWG.

  Field names come from the IR schema of record (tools/ir_builder.py,
  schemas/dwg_graph_ir.v1.schema.json), not from the issue snippets.

Discoverable by pytest and ``python -m unittest discover -s tests``.
Requires ezdxf (declared in requirements-full.txt, used across tools/e2).
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ezdxf  # noqa: E402

from tools.build_from_ir import BuildReport, build_dxf_from_ir  # noqa: E402
from tools.ir_builder import make_fixture_ir  # noqa: E402


# --- helpers ------------------------------------------------------------------

def _reload(doc):
    """Write the drawing to DXF text and read it back -- the trip that matters."""
    stream = io.StringIO()
    doc.write(stream)
    stream.seek(0)
    return ezdxf.read(stream)


def _ir(entities=None, *, symbol_tables=None, block_definitions=None):
    """A minimal dwg_graph_ir.v1-shaped document (only the keys the builder reads)."""
    tables = {"layers": [{"name": "0"}]}
    if symbol_tables:
        tables.update(symbol_tables)
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "ir_version": "test",
        "coverage_level": "native_full",
        "source": {"dwg_name": "synthetic.dwg"},
        "database": {"header_vars": {}},
        "symbol_tables": tables,
        "block_definitions": block_definitions or [],
        "block_references": [],
        "entities": entities or [],
        "diagnostics": {"entity_count": len(entities or [])},
    }


def _ent(kind, geometry, *, handle="1A", layer="0", space="model", **top_level):
    ent = {
        "handle": handle,
        "class": "AcDbEntity",
        "dxf_name": kind.upper(),
        "owner_handle": "1F",
        "space": space,
        "layer": layer,
        "bbox": None,
        "geometry": dict(geometry, kind=kind),
        "source": {"extractor": "test", "engine_tier": "test", "route": "test",
                   "decoded": True},
    }
    ent.update(top_level)
    return ent


class PublicApiTest(unittest.TestCase):
    """The contract the rest of the pipeline codes against."""

    def test_returns_drawing_and_report(self):
        doc, report = build_dxf_from_ir(make_fixture_ir())
        self.assertIsInstance(report, BuildReport)
        self.assertEqual(report.added["line"], 1)
        self.assertEqual(report.added["circle"], 1)
        self.assertEqual(report.added["block_reference"], 1)
        self.assertEqual(report.total_added, 3)
        self.assertEqual(dict(report.errors), {})
        self.assertIn("0", doc.layers)

    def test_out_path_writes_a_readable_dxf(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "sub", "rebuilt.dxf")
            _, report = build_dxf_from_ir(make_fixture_ir(), out)
            self.assertTrue(os.path.isfile(out))
            again = ezdxf.readfile(out)
            self.assertEqual(len(list(again.modelspace())), report.total_added)

    def test_roundtrip_kind_counts_match_the_ir(self):
        """BUNDLE 5: build -> reload -> per-kind counts equal the IR's own."""
        ir = make_fixture_ir()
        doc, report = build_dxf_from_ir(ir)
        want = {}
        for ent in ir["entities"]:
            want[ent["dxf_name"]] = want.get(ent["dxf_name"], 0) + 1
        got = {}
        for entity in _reload(doc).modelspace():
            got[entity.dxftype()] = got.get(entity.dxftype(), 0) + 1
        self.assertEqual(got, want)
        self.assertEqual(report.total_skipped, 0)

    def test_unrebuildable_kind_is_counted_with_a_reason(self):
        """ACIS-backed geometry cannot come back from IR -- it must still be counted."""
        _, report = build_dxf_from_ir(_ir([_ent("region", {})]))
        self.assertEqual(report.total_added, 0)
        self.assertEqual(report.skipped["region:acis_binary_not_in_ir"], 1)

    def test_unknown_kind_is_counted_not_dropped(self):
        """#55's lesson: an unrecognized type string must never vanish silently."""
        _, report = build_dxf_from_ir(_ir([_ent("some_future_kind", {})]))
        self.assertEqual(report.skipped["some_future_kind:unrecognized_kind"], 1)

    def test_symbol_tables_are_rebuilt(self):
        ir = _ir(symbol_tables={
            "layers": [{"name": "0"}, {"name": "WALLS", "color_index": 3,
                                       "linetype": "DASHED", "lineweight": 25}],
            "linetypes": [{"name": "DASHED", "pattern_length": 0.6,
                           "dash_lengths": [0.4, -0.2], "description": "dashed"}],
            "text_styles": [{"name": "NOTES", "font_file": "romans.shx",
                             "width_factor": 0.8}],
        })
        doc, report = build_dxf_from_ir(ir)
        reloaded = _reload(doc)
        self.assertIn("WALLS", reloaded.layers)
        self.assertEqual(reloaded.layers.get("WALLS").dxf.color, 3)
        self.assertEqual(reloaded.layers.get("WALLS").dxf.linetype, "DASHED")
        self.assertIn("DASHED", reloaded.linetypes)
        self.assertEqual(reloaded.styles.get("NOTES").dxf.font, "romans.shx")
        self.assertEqual(report.added["table:layer"], 2)


class Issue60DefpointsCasingTest(unittest.TestCase):
    """#60: ezdxf pre-creates 'Defpoints'; the original's 'DEFPOINTS' must win."""

    def _uppercase_defpoints_ir(self):
        return _ir(
            [_ent("point", {"position": [1.0, 2.0, 0.0]}, layer="DEFPOINTS")],
            symbol_tables={"layers": [{"name": "0"},
                                      {"name": "DEFPOINTS", "color_index": 3}]},
        )

    def test_layer_table_keeps_the_original_casing(self):
        doc, report = build_dxf_from_ir(self._uppercase_defpoints_ir())
        reloaded = _reload(doc)
        names = [layer.dxf.name for layer in reloaded.layers]
        self.assertIn("DEFPOINTS", names)
        self.assertNotIn("Defpoints", names)
        # The record must be the IR's own, not an attribute-less stand-in: a
        # discarded-then-implicitly-recreated layer loses its color.
        self.assertEqual(reloaded.layers.get("DEFPOINTS").dxf.color, 3)
        self.assertEqual(report.added["table:layer_recased"], 1)

    def test_entity_lands_on_the_original_layer_name(self):
        doc, _ = build_dxf_from_ir(self._uppercase_defpoints_ir())
        points = list(_reload(doc).modelspace().query("POINT"))
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].dxf.layer, "DEFPOINTS")


class Issue54DimstylePruneTest(unittest.TestCase):
    """#54: case-sensitive prune deleted the dimstyle 213 dimensions referenced."""

    def _uppercase_standard_ir(self):
        return _ir(
            [_ent("dimension", {"xline1_point": [0.0, 0.0, 0.0],
                                "xline2_point": [10.0, 0.0, 0.0],
                                "dim_line_point": [5.0, 5.0, 0.0],
                                "measurement": 10.0, "rotation": 0.0},
                  layer="DIMS")],
            symbol_tables={"dim_styles": [{"name": "STANDARD",
                                           "dim_vars": {"DIMTXT": 3.75}}]},
        )

    def test_referenced_uppercase_standard_survives(self):
        doc, report = build_dxf_from_ir(self._uppercase_standard_ir())
        reloaded = _reload(doc)
        self.assertIn("STANDARD", reloaded.dimstyles)
        # ezdxf recreates a missing "Standard" on load, so table membership
        # alone cannot detect the wrongful prune -- the IR's own dim_vars can.
        self.assertEqual(reloaded.dimstyles.get("STANDARD").dxf.dimtxt, 3.75)
        self.assertEqual(report.added["table:prune_dimstyle_std"], 0)

    def test_dimension_reference_resolves_after_reload(self):
        doc, _ = build_dxf_from_ir(self._uppercase_standard_ir())
        reloaded = _reload(doc)
        dims = list(reloaded.modelspace().query("DIMENSION"))
        self.assertEqual(len(dims), 1)
        self.assertIn(dims[0].dxf.dimstyle, reloaded.dimstyles)


class Issue58ShapeFileStyleTest(unittest.TestCase):
    """#58: a shape-file STYLE record named STANDARD overwrote text style Standard."""

    def _shape_record_ir(self):
        return _ir(symbol_tables={"text_styles": [
            {"name": "Standard", "font_file": "arial.ttf", "is_shape_file": False},
            {"name": "STANDARD", "font_file": "SYMBOL", "is_shape_file": True},
            {"name": "", "font_file": "ltypeshp.shx", "is_shape_file": True},
        ]})

    def test_text_style_font_is_not_corrupted_by_a_shape_record(self):
        doc, _ = build_dxf_from_ir(self._shape_record_ir())
        self.assertEqual(_reload(doc).styles.get("Standard").dxf.font, "arial.ttf")

    def test_shape_records_are_restored_as_shx_entries(self):
        doc, report = build_dxf_from_ir(self._shape_record_ir())
        reloaded = _reload(doc)
        self.assertIsNotNone(reloaded.styles.find_shx("SYMBOL"))
        self.assertIsNotNone(reloaded.styles.find_shx("ltypeshp.shx"))
        self.assertEqual(report.added["table:shape_file"], 2)


class Issue51BlockDimensionInlineTest(unittest.TestCase):
    """#51: inlining block-internal dimensions orphans *D -> purge kills INSERTs.

    Adopted design: inline OFF by default (the *D definition is preserved and
    the DIMENSION entity points at it), with inline available as an option for
    the drawings whose DWG conversion fails with rc53.
    """

    def _ir_with_block_dimension(self):
        dim = _ent("dimension", {"xline1_point": [0.0, 0.0, 0.0],
                                 "xline2_point": [10.0, 0.0, 0.0],
                                 "dim_line_point": [5.0, 5.0, 0.0],
                                 "measurement": 10.0, "rotation": 0.0},
                   handle="D1", layer="DIMS", space="block",
                   dim_block_name="*D1")
        return _ir(
            [_ent("block_reference", {"position": [0.0, 0.0, 0.0],
                                      "block_name": "FRAME"}, handle="I1")],
            symbol_tables={"layers": [{"name": "0"}, {"name": "DIMS"}]},
            block_definitions=[
                {"name": "*D1", "def_entities": [
                    _ent("line", {"start": [0.0, 5.0, 0.0], "end": [10.0, 5.0, 0.0]},
                         handle="L1", layer="DIMS", space="block"),
                    _ent("line", {"start": [0.0, 0.0, 0.0], "end": [0.0, 5.0, 0.0]},
                         handle="L2", layer="DIMS", space="block"),
                ]},
                {"name": "FRAME", "def_entities": [dim]},
            ],
        )

    def test_default_keeps_the_dimension_and_its_anonymous_block(self):
        doc, report = build_dxf_from_ir(self._ir_with_block_dimension())
        reloaded = _reload(doc)
        self.assertIn("*D1", reloaded.blocks)
        frame = reloaded.blocks.get("FRAME")
        self.assertEqual([e.dxftype() for e in frame], ["DIMENSION"])
        self.assertEqual(frame[0].dxf.geometry, "*D1")
        self.assertEqual(report.added["dim_inlined"], 0)
        self.assertEqual(len(list(reloaded.modelspace().query("INSERT"))), 1)

    def test_inline_option_expands_the_anonymous_block_contents(self):
        doc, report = build_dxf_from_ir(self._ir_with_block_dimension(),
                                        inline_block_dims=True)
        reloaded = _reload(doc)
        frame = reloaded.blocks.get("FRAME")
        self.assertEqual([e.dxftype() for e in frame], ["LINE", "LINE"])
        self.assertEqual(report.added["dim_inlined"], 1)
        self.assertIn("*D1", reloaded.blocks)


if __name__ == "__main__":
    unittest.main()
