#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M02 TEST -- visual_report: real, deterministic IR->SVG render.

Intent (WHY -- the visual lane must be a GENUINE pass, never theater):
  * render_ir_to_svg draws the EXTRACTED IR geometry to a real SVG. The picture
    IS the verification: it shows exactly the geometry that landed in
    dwg_graph_ir.v1, so a correct render is evidence the extraction is sound. The
    tests therefore parse the produced SVG as XML (it must be well-formed) and
    assert the expected number of drawable elements for a known fixture -- a
    render that silently dropped or invented geometry would change that count
    (Rule 9: the assertion can fail when the renderer's behavior regresses).
  * build_visual_report must produce REAL artifact files on disk (no-fake-
    success): before.svg always, and after.svg/overlay.svg/visual_diff.json when
    a post IR + diff are supplied. status "ok" REQUIRES the files to exist and be
    non-empty -- we stat every ref.
  * The overlay must highlight the diff's created/modified handles in RED. We
    pin this on a one-added-LINE patch: the created handle's <g> must be present
    in the after/overlay drawing, carry class "hl", and use the red stroke -- and
    must NOT be present in before.svg (which is the pre-patch state).
  * Determinism: rendering the same IR to the same path twice yields byte-
    identical SVG (no timestamps, fixed-precision numbers, input-order emit). A
    non-deterministic visual artifact can't be a stable contract.
  * available_render_routes must advertise ir_svg as available+implemented and
    accoreconsole_plot as NOT implemented (honest about the host).

Built on ir_builder.make_fixture_ir() so the renderer is exercised against
genuine producer output (3 entities: LINE 2A7 / CIRCLE 2A8 / INSERT 2A9).

Discoverable by pytest and ``python -m unittest discover -s tests``. Dual-runnable
(``python tests/unit/test_visual_report.py``). Stdlib only.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SVG_NS = "{http://www.w3.org/2000/svg}"


def _read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def _fixture_ir():
    import ir_builder
    return ir_builder.make_fixture_ir()


def _entity_groups(svg_path):
    """Parse an SVG and return its drawable entity groups (<g class=ent|hl>)."""
    root = ET.parse(svg_path).getroot()
    return [g for g in root.findall(".//%sg" % _SVG_NS)
            if g.get("class") in ("ent", "hl")]


def _post_with_added_line(pre, handle="2FF"):
    """Deep-copy the fixture IR and append one new LINE (a 'created' entity)."""
    post = json.loads(json.dumps(pre))
    post["entities"].append({
        "handle": handle, "class": "AcDbLine", "dxf_name": "LINE",
        "owner_handle": "1F", "space": "model", "layer": "ARIADNE_PROBE",
        "bbox": [0.0, 0.0, 0.0, 5.0, 5.0, 0.0],
        "geometry": {"kind": "line", "start": [0.0, 0.0, 0.0],
                     "end": [5.0, 5.0, 0.0]},
        "source": {"extractor": "test", "decoded": True},
    })
    post["diagnostics"]["entity_count"] = len(post["entities"])
    return post


def _diff_added(handle="2FF"):
    return {
        "schema": "ariadne.cad_diff.v1",
        "diff_id": "test-added-%s" % handle,
        "changed_handles": [
            {"handle": handle, "change": "added", "dxf_name": "LINE",
             "layer": "ARIADNE_PROBE"}
        ],
        "summary": {"created_count": 1, "modified_count": 0, "deleted_count": 0,
                    "added": 1, "removed": 0, "modified": 0},
    }


class TestRenderIrToSvg(unittest.TestCase):
    """render_ir_to_svg makes a well-formed SVG with the expected drawables."""

    def setUp(self):
        import visual_report
        self.vr = visual_report
        self.ir = _fixture_ir()

    def test_produces_wellformed_svg_file(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "fixture.svg")
            meta = self.vr.render_ir_to_svg(self.ir, out)
            self.assertTrue(os.path.isfile(out))
            self.assertGreater(os.path.getsize(out), 0)
            # parses as XML => well-formed; root is an <svg>.
            root = ET.parse(out).getroot()
            self.assertTrue(root.tag.endswith("svg"))
            self.assertIn("viewBox", root.attrib)
            self.assertEqual(meta["path"], out)
            self.assertEqual(len(meta["viewbox"]), 4)

    def test_expected_drawable_element_count(self):
        # Fixture = LINE + CIRCLE + INSERT. The renderer emits one <g> per
        # rendered entity: LINE(1 <line>), CIRCLE(1 <circle>), INSERT(crosshair
        # 2 <line> + 1 <text> label = 3 leaves). So 3 entity groups, and
        # element_count counts leaf elements (>= 3, and exactly 5 here).
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "fixture.svg")
            meta = self.vr.render_ir_to_svg(self.ir, out)
            groups = _entity_groups(out)
            self.assertEqual(len(groups), 3,
                             "expected one <g> per fixture entity (LINE/CIRCLE/INSERT)")
            handles = {g.get("data-handle") for g in groups}
            self.assertEqual(handles, {"2A7", "2A8", "2A9"})
            # leaf count is deterministic for this fixture.
            self.assertEqual(meta["element_count"], 5)

    def test_line_circle_arc_kinds_render_correct_tags(self):
        # A focused IR with one LINE, one CIRCLE, one ARC -> <line>, <circle>,
        # <path> (the arc). Verifies the per-kind emitter dispatch.
        ir = {
            "schema": "ariadne.dwg_graph_ir.v1",
            "source": {}, "database": {"header_vars": {}},
            "symbol_tables": {"layers": []},
            "diagnostics": {"entity_count": 3, "warnings": [], "errors": [],
                            "coverage": {}},
            "entities": [
                {"handle": "L", "class": "AcDbLine", "dxf_name": "LINE",
                 "owner_handle": "", "space": "model", "layer": "0",
                 "bbox": [0, 0, 0, 10, 0, 0],
                 "geometry": {"kind": "line", "start": [0, 0, 0], "end": [10, 0, 0]},
                 "source": {"decoded": True}},
                {"handle": "C", "class": "AcDbCircle", "dxf_name": "CIRCLE",
                 "owner_handle": "", "space": "model", "layer": "0",
                 "bbox": [3, 3, 0, 7, 7, 0],
                 "geometry": {"kind": "circle", "center": [5, 5, 0], "radius": 2},
                 "source": {"decoded": True}},
                {"handle": "A", "class": "AcDbArc", "dxf_name": "ARC",
                 "owner_handle": "", "space": "model", "layer": "0",
                 "bbox": [0, 0, 0, 4, 4, 0],
                 "geometry": {"kind": "arc", "center": [2, 2, 0], "radius": 2,
                              "start_angle": 0.0, "end_angle": 1.5708},
                 "source": {"decoded": True}},
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "lca.svg")
            self.vr.render_ir_to_svg(ir, out)
            txt = _read_text(out)
            self.assertIn("<line ", txt)
            self.assertIn("<circle ", txt)
            self.assertIn("<path ", txt)  # the arc

    def test_highlight_handles_stroke_red(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "hi.svg")
            self.vr.render_ir_to_svg(self.ir, out, highlight_handles={"2A7"})
            txt = _read_text(out)
            self.assertIn("#e00000", txt, "highlighted entity not stroked red")
            # the highlighted entity's group carries class 'hl'.
            groups = _entity_groups(out)
            hl = [g for g in groups if g.get("class") == "hl"]
            self.assertEqual([g.get("data-handle") for g in hl], ["2A7"])

    def test_render_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            a = os.path.join(td, "a.svg")
            b = os.path.join(td, "b.svg")
            self.vr.render_ir_to_svg(self.ir, a)
            self.vr.render_ir_to_svg(self.ir, b)
            self.assertEqual(_read_bytes(a), _read_bytes(b),
                             "render_ir_to_svg is not byte-deterministic")

    def test_empty_bbox_entities_skipped_for_extent(self):
        # A vertex-less polyline with an empty bbox carries no extent and no
        # coordinate geometry; it must not crash and contributes no drawable.
        ir = {
            "schema": "ariadne.dwg_graph_ir.v1",
            "source": {}, "database": {"header_vars": {}},
            "symbol_tables": {"layers": []},
            "diagnostics": {"entity_count": 2, "warnings": [], "errors": [],
                            "coverage": {}},
            "entities": [
                {"handle": "L", "class": "AcDbLine", "dxf_name": "LINE",
                 "owner_handle": "", "space": "model", "layer": "0",
                 "bbox": [0, 0, 0, 10, 0, 0],
                 "geometry": {"kind": "line", "start": [0, 0, 0], "end": [10, 0, 0]},
                 "source": {"decoded": True}},
                {"handle": "P", "class": "AcDb2dPolyline", "dxf_name": "POLYLINE",
                 "owner_handle": "", "space": "model", "layer": "0",
                 "bbox": [],
                 "geometry": {"kind": "polyline"},  # no vertices, no bbox
                 "source": {"decoded": True}},
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "e.svg")
            self.vr.render_ir_to_svg(ir, out)  # must not raise
            ET.parse(out)  # well-formed
            groups = _entity_groups(out)
            # only the LINE produced a drawable group.
            self.assertEqual({g.get("data-handle") for g in groups}, {"L"})


class TestBuildVisualReportRealArtifacts(unittest.TestCase):
    """build_visual_report writes real files and returns status ok."""

    def _write(self, td, pre, post=None, diff=None):
        pre_p = os.path.join(td, "pre.json")
        with open(pre_p, "w", encoding="utf-8") as fh:
            json.dump(pre, fh)
        post_p = diff_p = None
        if post is not None:
            post_p = os.path.join(td, "post.json")
            with open(post_p, "w", encoding="utf-8") as fh:
                json.dump(post, fh)
        if diff is not None:
            diff_p = os.path.join(td, "diff.json")
            with open(diff_p, "w", encoding="utf-8") as fh:
                json.dump(diff, fh)
        return pre_p, post_p, diff_p

    def setUp(self):
        import visual_report
        self.vr = visual_report

    def test_before_only_is_ok_with_real_file(self):
        with tempfile.TemporaryDirectory() as td:
            pre_p, _, _ = self._write(td, _fixture_ir())
            outd = os.path.join(td, "out")
            rep = self.vr.build_visual_report(pre_p, out_dir=outd)
            self.assertEqual(rep["schema"], "ariadne.visual_artifact.v1")
            self.assertEqual(rep["status"], "ok")
            self.assertEqual(rep["route"], "ir_svg")
            roles = {r.get("role") for r in rep["refs"]}
            self.assertIn("before", roles)
            for r in rep["refs"]:
                self.assertTrue(os.path.isfile(r["ref"]),
                                "ref file missing: %s" % r["ref"])
                self.assertGreater(r.get("byte_size", 0), 0)
                self.assertIn("sha256", r)

    def test_overlay_run_writes_all_four_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            pre = _fixture_ir()
            post = _post_with_added_line(pre, "2FF")
            pre_p, post_p, diff_p = self._write(td, pre, post, _diff_added("2FF"))
            outd = os.path.join(td, "out")
            rep = self.vr.build_visual_report(
                pre_p, post_ir_path=post_p, diff_path=diff_p, out_dir=outd)
            self.assertEqual(rep["status"], "ok")
            self.assertEqual(rep["kind"], "diff_overlay")
            # all four artifacts exist on disk and are non-empty.
            for f in ("before.svg", "after.svg", "overlay.svg", "visual_diff.json"):
                p = os.path.join(outd, f)
                self.assertTrue(os.path.isfile(p), "missing artifact %s" % f)
                self.assertGreater(os.path.getsize(p), 0)
            roles = {r.get("role") for r in rep["refs"]}
            self.assertTrue({"before", "after", "overlay", "visual_diff"} <= roles)

    def test_overlay_highlights_created_handle_red(self):
        with tempfile.TemporaryDirectory() as td:
            pre = _fixture_ir()
            post = _post_with_added_line(pre, "2FF")
            pre_p, post_p, diff_p = self._write(td, pre, post, _diff_added("2FF"))
            outd = os.path.join(td, "out")
            self.vr.build_visual_report(
                pre_p, post_ir_path=post_p, diff_path=diff_p, out_dir=outd)

            before_txt = _read_text(os.path.join(outd, "before.svg"))
            overlay_txt = _read_text(os.path.join(outd, "overlay.svg"))
            # created handle NOT in before (pre-patch state).
            self.assertNotIn('data-handle="2FF"', before_txt)
            # created handle present in overlay, as a red 'hl' group.
            self.assertIn('data-handle="2FF"', overlay_txt)
            self.assertIn("#e00000", overlay_txt)
            groups = _entity_groups(os.path.join(outd, "overlay.svg"))
            hl = [g for g in groups if g.get("class") == "hl"]
            self.assertEqual([g.get("data-handle") for g in hl], ["2FF"],
                             "overlay must highlight exactly the created handle")

    def test_after_has_one_more_drawable_than_before(self):
        with tempfile.TemporaryDirectory() as td:
            pre = _fixture_ir()
            post = _post_with_added_line(pre, "2FF")
            pre_p, post_p, diff_p = self._write(td, pre, post, _diff_added("2FF"))
            outd = os.path.join(td, "out")
            self.vr.build_visual_report(
                pre_p, post_ir_path=post_p, diff_path=diff_p, out_dir=outd)
            nb = len(_entity_groups(os.path.join(outd, "before.svg")))
            na = len(_entity_groups(os.path.join(outd, "after.svg")))
            self.assertEqual(na - nb, 1,
                             "after should have exactly one more drawable (the added LINE)")

    def test_visual_diff_json_counts(self):
        with tempfile.TemporaryDirectory() as td:
            pre = _fixture_ir()
            post = _post_with_added_line(pre, "2FF")
            pre_p, post_p, diff_p = self._write(td, pre, post, _diff_added("2FF"))
            outd = os.path.join(td, "out")
            self.vr.build_visual_report(
                pre_p, post_ir_path=post_p, diff_path=diff_p, out_dir=outd)
            vd = json.loads(_read_text(os.path.join(outd, "visual_diff.json")))
            self.assertEqual(vd["counts"],
                             {"created": 1, "modified": 0, "deleted": 0})
            self.assertEqual(vd["highlighted_handles_present_in_after"], ["2FF"])
            # the three artifact paths are recorded.
            self.assertEqual(set(vd["artifacts"].keys()),
                             {"before", "after", "overlay"})

    def test_build_is_deterministic_same_out_dir(self):
        with tempfile.TemporaryDirectory() as td:
            pre = _fixture_ir()
            post = _post_with_added_line(pre, "2FF")
            pre_p, post_p, diff_p = self._write(td, pre, post, _diff_added("2FF"))
            outd = os.path.join(td, "out")
            self.vr.build_visual_report(
                pre_p, post_ir_path=post_p, diff_path=diff_p, out_dir=outd)
            h1 = {f: _read_bytes(os.path.join(outd, f))
                  for f in ("before.svg", "after.svg", "overlay.svg",
                            "visual_diff.json")}
            self.vr.build_visual_report(
                pre_p, post_ir_path=post_p, diff_path=diff_p, out_dir=outd)
            h2 = {f: _read_bytes(os.path.join(outd, f))
                  for f in ("before.svg", "after.svg", "overlay.svg",
                            "visual_diff.json")}
            for f in h1:
                self.assertEqual(h1[f], h2[f],
                                 "%s not byte-deterministic on re-render" % f)

    def test_bad_source_ref_is_error_no_fake(self):
        with tempfile.TemporaryDirectory() as td:
            bad = os.path.join(td, "nope.json")
            rep = self.vr.build_visual_report(bad, out_dir=os.path.join(td, "o"))
            self.assertEqual(rep["status"], "error")
            self.assertEqual(rep["refs"], [], "error must carry no refs (no-fake-success)")


class TestAvailableRenderRoutes(unittest.TestCase):

    def setUp(self):
        import visual_report
        self.probe = visual_report.available_render_routes()

    def test_ir_svg_available_and_implemented(self):
        r = self.probe["routes"]["ir_svg"]
        self.assertTrue(r["available"])
        self.assertTrue(r["implemented"])
        self.assertEqual(self.probe["default_route"], "ir_svg")
        self.assertTrue(self.probe["any_available"])

    def test_accoreconsole_plot_is_honest_not_implemented(self):
        r = self.probe["routes"]["accoreconsole_plot"]
        # honest: it is NOT implemented on this host (never claims to emit a file).
        self.assertFalse(r["implemented"])
        self.assertEqual(r.get("status"), "not_implemented")


if __name__ == "__main__":
    unittest.main()
