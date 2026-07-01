#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer WAVE-0 TEST -- extractor_noise_floor (F11): tol-0 determinism probe.

Intent (WHY):
  * PLAN F11 / R4-12: the D-half's "2*tol" perturbation is only a reliable
    discriminator if it sits ABOVE the extractor's OWN run-to-run numeric
    jitter. Before this probe, that jitter was UNMEASURED -- a WAVE-0 blocker.
    These tests prove the tol-0 determinism logic on BOTH sides: the green
    path (two extracts of an unchanged source ARE byte-identical -> PASS) and
    the red path (a real difference IS caught, with the right magnitude and
    the right leaf localized) -- a probe that can only ever say "PASS" would
    be worthless (Rule 9).
  * The two WAVE-0 asserts are logically INDEPENDENT and must be proven
    separately: (1) extract-twice-at-tol-0 == 0 (``assert_extractor_
    deterministic`` -- ANY leaf difference fails this, however small) and
    (2) 2*tol > noise_floor (``assert_tolerance_safe``). A sub-tolerance
    jitter must fail (1) yet still PASS (2); a jitter at/above 2*tol must fail
    both. A single merged "close enough" check would hide exactly the
    regression R4-12 exists to catch.
  * A non-numeric difference (a changed string field, an added/removed
    entity) has no magnitude for ``noise_floor`` to carry -- it must still
    fail BOTH asserts. This guards the specific fake-pass this module's
    docstring calls out: non-numeric drift must never hide behind a reported
    "noise_floor: 0.0".
  * ``extract_twice`` / ``run_live_probe`` (the LIVE path, needs the
    accoreconsole runtime via cadctl.Cad) are exercised here through a stub
    ``cad`` object (dependency injection, not a live CAD process) -- this
    proves the wiring (two calls against the SAME dwg_path into two distinct
    out_dirs, envelope parsing, ok/unavailable propagation) genuinely, and
    proves the tool reports a truthful ``unavailable`` -- never a fake PASS --
    when the router is unreachable (the actual live double-extract itself is
    DONE_NEEDS_RUNTIME; see report.md).

Uses ir_builder.make_fixture_ir() (the same golden 3-entity fixture cad_diff's
own tests use) for the "two extracts of one drawing" scenarios, and small
inline synthetic entities (mirroring test_cad_diff_geometry_basis.py's style)
for the leaf-walker shape test -- kept fully self-contained (no dependency on
any path outside this repo) so the suite stays portable.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _line_entity(handle, start, end, layer="0"):
    """A minimal LINE entity dict -- just the fields this probe reads."""
    return {
        "handle": handle, "class": "AcDbLine", "dxf_name": "LINE",
        "owner_handle": "1F", "space": "model", "layer": layer,
        "bbox": [start[0], start[1], start[2], end[0], end[1], end[2]],
        "geometry": {"kind": "line", "start": list(start), "end": list(end)},
        "source": {"extractor": "test", "decoded": True},
    }


def _ir(entities):
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "entities": entities,
        "diagnostics": {"entity_count": len(entities)},
    }


class _StubCad:
    """Stand-in for cadctl.Cad that writes a PRE-BUILT IR to disk instead of
    driving accoreconsole -- proves extract_twice/run_live_probe's wiring
    (out_dir plumbing, envelope parsing, ok/unavailable propagation) without
    needing the live CAD runtime. One entry of ``ir_by_call`` per expected
    ``inspect()`` call; ``None`` simulates a router that is unavailable.
    """

    def __init__(self, ir_by_call):
        self._ir_by_call = list(ir_by_call)
        self.calls = []

    def inspect(self, dwg_path, out_dir):
        self.calls.append((dwg_path, out_dir))
        ir_doc = self._ir_by_call[len(self.calls) - 1]
        if ir_doc is None:
            return {"schema": "ariadne.cadctl.inspect.v1", "status": "unavailable",
                   "reason": "stub: simulated router unavailable"}
        os.makedirs(out_dir, exist_ok=True)
        ir_path = os.path.join(out_dir, "dwg_graph_ir.json")
        with open(ir_path, "w", encoding="utf-8") as fh:
            json.dump(ir_doc, fh)
        return {"schema": "ariadne.cadctl.inspect.v1", "status": "ok",
               "dwg_graph_ir": ir_path,
               "entity_count": len((ir_doc or {}).get("entities") or [])}


class TestIdenticalExtractsAreZeroNoise(unittest.TestCase):
    """Two extracts of the SAME unchanged drawing -> noise_floor == 0, PASS."""

    def test_fixture_ir_against_itself_is_deterministic(self):
        import ir_builder
        import extractor_noise_floor as enf

        ir_a = ir_builder.make_fixture_ir()
        ir_b = json.loads(json.dumps(ir_a))  # independent deep copy (stdlib)

        report = enf.run_probe(ir_a, ir_b)

        self.assertEqual(report["schema"], enf.NOISE_FLOOR_SCHEMA_ID)
        self.assertEqual(report["noise_floor"], 0.0)
        self.assertTrue(report["extractor_deterministic"])
        self.assertTrue(report["tolerance_safe_2x"])
        self.assertFalse(report["wave0_blocker"])
        self.assertIsNone(report["note"])
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["measurement"]["leaf_count"], 0)
        self.assertEqual(report["measurement"]["entity_count_a"], 3)
        self.assertEqual(report["measurement"]["entity_count_b"], 3)


class TestSubTolJitterFailsDeterminismButIsToleranceSafe(unittest.TestCase):
    """A jitter SMALLER than 2*tol fails assert (1) but still passes assert (2) --
    the two WAVE-0 asserts are independent, not one merged "close enough" check.
    """

    def test_half_tol_shift_is_nonzero_noise_yet_safe(self):
        import ir_builder
        import extractor_noise_floor as enf

        ir_a = ir_builder.make_fixture_ir()
        ir_b = json.loads(json.dumps(ir_a))
        line = next(e for e in ir_b["entities"] if e["handle"] == "2A7")
        end = line["geometry"]["end"]
        shift = enf.DEFAULT_TOLERANCE / 2.0  # 5e-7 -- half the default tolerance
        line["geometry"]["end"] = [end[0], end[1] + shift, end[2]]

        report = enf.run_probe(ir_a, ir_b)

        self.assertFalse(report["extractor_deterministic"],
                         "any leaf difference, however small, must fail determinism")
        self.assertTrue(report["tolerance_safe_2x"],
                        "a sub-(2*tol) jitter must still be tolerance-safe")
        self.assertEqual(report["status"], "FAIL")  # overall still fails (assert 1)
        self.assertAlmostEqual(report["noise_floor"], shift, places=12)
        # the differing leaf must be localized to exactly the mutated coordinate
        worst = report["measurement"]["worst_leaves"]
        self.assertEqual(len(worst), 1)
        self.assertEqual(worst[0]["path"], "geometry.end.1")
        self.assertEqual(worst[0]["handle"], "2A7")
        self.assertIn("WAVE-0", report["note"])


class TestJitterAboveTwiceTolFailsBothAsserts(unittest.TestCase):
    """A jitter AT/ABOVE 2*tol fails determinism AND tolerance-safety."""

    def test_shift_above_2x_tol_is_unsafe(self):
        import ir_builder
        import extractor_noise_floor as enf

        ir_a = ir_builder.make_fixture_ir()
        ir_b = json.loads(json.dumps(ir_a))
        line = next(e for e in ir_b["entities"] if e["handle"] == "2A7")
        end = line["geometry"]["end"]
        shift = enf.DEFAULT_TOLERANCE * 3.0  # 3e-6 -- above 2*default tol (2e-6)
        line["geometry"]["end"] = [end[0], end[1] + shift, end[2]]

        report = enf.run_probe(ir_a, ir_b)

        self.assertFalse(report["extractor_deterministic"])
        self.assertFalse(report["tolerance_safe_2x"])
        self.assertTrue(report["wave0_blocker"])
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("R4-12", report["note"])


class TestNonNumericChangeFailsRegardlessOfMagnitude(unittest.TestCase):
    """A non-numeric leaf change (e.g. layer) has no magnitude for noise_floor
    to carry -- it must NOT hide behind a reported noise_floor of 0.0.
    """

    def test_layer_rename_is_non_deterministic_and_unsafe(self):
        import ir_builder
        import extractor_noise_floor as enf

        ir_a = ir_builder.make_fixture_ir()
        ir_b = json.loads(json.dumps(ir_a))
        for e in ir_b["entities"]:
            if e["handle"] == "2A7":
                e["layer"] = "MOVED"

        measurement = enf.measure_noise_floor(ir_a, ir_b)
        self.assertEqual(measurement["noise_floor"], 0.0,
                         "no numeric leaf changed -- noise_floor alone must not "
                         "be trusted to mean 'identical'")
        self.assertEqual(measurement["non_numeric_leaf_count"], 1)

        self.assertFalse(enf.assert_extractor_deterministic(measurement))
        self.assertFalse(
            enf.assert_tolerance_safe(measurement, tol=1000.0),
            "a huge tol must NOT rescue a non-numeric (unmeasurable) difference",
        )

        report = enf.run_probe(ir_a, ir_b)
        self.assertEqual(report["status"], "FAIL")


class TestAddedEntityIsNonDeterministic(unittest.TestCase):
    """A handle present in only one extract (added/removed) is structural noise."""

    def test_extra_entity_on_one_side_fails_determinism(self):
        import ir_builder
        import extractor_noise_floor as enf

        ir_a = ir_builder.make_fixture_ir()
        ir_b = json.loads(json.dumps(ir_a))
        ir_b["entities"].append({
            "handle": "9FF", "class": "AcDbCircle", "dxf_name": "CIRCLE",
            "owner_handle": "1F", "space": "model", "layer": "0",
            "bbox": [0.0, 0.0, 0.0, 1.0, 1.0, 0.0],
            "geometry": {"kind": "circle", "center": [0.0, 0.0, 0.0], "radius": 1.0},
            "source": {},
        })

        report = enf.run_probe(ir_a, ir_b)
        self.assertFalse(report["extractor_deterministic"])
        self.assertEqual(report["measurement"]["leaf_count"], 1)
        leaf = report["measurement"]["non_numeric_leaves"][0]
        self.assertEqual(leaf["handle"], "9FF")
        self.assertEqual(leaf["kind"], "structural")
        self.assertEqual(report["status"], "FAIL")


class TestToleranceExceedsNoiseBoundary(unittest.TestCase):
    """Direct unit tests of the literal PLAN assert: 2*tol > noise_floor (strict)."""

    def test_exactly_at_boundary_is_not_safe(self):
        import extractor_noise_floor as enf
        # 2*1e-6 == 2e-6 == noise_floor -> NOT strictly greater -> unsafe.
        self.assertFalse(enf.tolerance_exceeds_noise(noise_floor=2e-6, tol=1e-6))

    def test_just_below_boundary_is_safe(self):
        import extractor_noise_floor as enf
        self.assertTrue(enf.tolerance_exceeds_noise(noise_floor=1.9e-6, tol=1e-6))

    def test_just_above_boundary_is_not_safe(self):
        import extractor_noise_floor as enf
        self.assertFalse(enf.tolerance_exceeds_noise(noise_floor=2.1e-6, tol=1e-6))

    def test_zero_noise_is_always_safe(self):
        import extractor_noise_floor as enf
        self.assertTrue(enf.tolerance_exceeds_noise(noise_floor=0.0, tol=1e-6))


class TestDiffLeavesShape(unittest.TestCase):
    """diff_leaves on minimal inline synthetic entities -- exact path/kind/delta,
    decoupled from ir_builder so the leaf-walker's contract is pinned directly.
    """

    def test_identical_entities_produce_no_leaves(self):
        import extractor_noise_floor as enf
        pre = _ir([_line_entity("AAA", (0, 0, 0), (10, 5, 0))])
        post = _ir([_line_entity("AAA", (0, 0, 0), (10, 5, 0))])
        self.assertEqual(enf.diff_leaves(pre, post), [])

    def test_coordinate_shift_localizes_to_exact_leaves(self):
        import extractor_noise_floor as enf
        pre = _ir([_line_entity("AAA", (0, 0, 0), (10, 5, 0))])
        # end.y +0.25 -- the helper derives bbox straight from start/end, so a
        # real entity's bbox shifts right along with its geometry; both leaves
        # must be caught (this mirrors cad_diff.classify_change's own field
        # scope: bbox AND geometry, never just one).
        post = _ir([_line_entity("AAA", (0, 0, 0), (10, 5.25, 0))])
        leaves = enf.diff_leaves(pre, post)
        by_path = {l["path"]: l for l in leaves}
        self.assertEqual(set(by_path), {"geometry.end.1", "bbox.4"})
        for path in ("geometry.end.1", "bbox.4"):
            self.assertEqual(by_path[path]["kind"], "numeric")
            self.assertEqual(by_path[path]["handle"], "AAA")
            self.assertAlmostEqual(by_path[path]["delta"], 0.25, places=12)

    def test_int_vs_float_same_value_is_not_noise(self):
        # A coordinate serialized as `5` (int) on one side and `5.0` (float) on
        # the other MUST NOT register as noise -- JSON int/float formatting is
        # not extractor jitter.
        import extractor_noise_floor as enf
        pre = _ir([_line_entity("AAA", (0, 0, 0), (10, 5, 0))])
        post = json.loads(json.dumps(pre))
        post["entities"][0]["geometry"]["end"][1] = 5.0
        self.assertEqual(enf.diff_leaves(pre, post), [])


class TestMeasureNoiseFloorCounts(unittest.TestCase):
    """measure_noise_floor's entity counts and leaf-count bookkeeping."""

    def test_entity_counts_reported_even_when_identical(self):
        import extractor_noise_floor as enf
        pre = _ir([_line_entity("AAA", (0, 0, 0), (10, 5, 0)),
                  _line_entity("BBB", (0, 0, 0), (1, 1, 0))])
        post = json.loads(json.dumps(pre))
        measurement = enf.measure_noise_floor(pre, post)
        self.assertEqual(measurement["entity_count_a"], 2)
        self.assertEqual(measurement["entity_count_b"], 2)
        self.assertEqual(measurement["leaf_count"], 0)
        self.assertEqual(measurement["numeric_leaf_count"], 0)
        self.assertEqual(measurement["non_numeric_leaf_count"], 0)


class TestWriteReportRoundTrip(unittest.TestCase):
    """write_report + load_ir round-trips a report through disk (UTF-8)."""

    def test_write_then_reload_is_identical(self):
        import extractor_noise_floor as enf
        report = enf.run_probe(_ir([_line_entity("AAA", (0, 0, 0), (10, 5, 0))]),
                               _ir([_line_entity("AAA", (0, 0, 0), (10, 5, 0))]))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "noise_floor_report.json")
            written = enf.write_report(report, path)
            self.assertEqual(written, path)
            self.assertTrue(os.path.isfile(path))
            reloaded = enf.load_ir(path)  # load_ir is a generic BOM-tolerant JSON reader
            self.assertEqual(reloaded, report)


class TestExtractTwiceWiring(unittest.TestCase):
    """extract_twice's LIVE wiring, proven via a stub cad (no accoreconsole)."""

    def test_two_calls_same_dwg_distinct_out_dirs(self):
        import ir_builder
        import extractor_noise_floor as enf

        ir_doc = ir_builder.make_fixture_ir()
        with tempfile.TemporaryDirectory() as tmp:
            stub = _StubCad([ir_doc, json.loads(json.dumps(ir_doc))])
            result = enf.extract_twice("fake.dwg", tmp, cad=stub)

            self.assertEqual(result["status"], "ok")
            self.assertEqual(len(stub.calls), 2)
            (dwg_1, out_1), (dwg_2, out_2) = stub.calls
            self.assertEqual(dwg_1, "fake.dwg")
            self.assertEqual(dwg_2, "fake.dwg")
            self.assertNotEqual(out_1, out_2, "the two runs must land in distinct out_dirs")
            self.assertTrue(result["ir_path_a"] and os.path.isfile(result["ir_path_a"]))
            self.assertTrue(result["ir_path_b"] and os.path.isfile(result["ir_path_b"]))

    def test_router_unavailable_propagates_truthfully(self):
        import extractor_noise_floor as enf
        with tempfile.TemporaryDirectory() as tmp:
            stub = _StubCad([None, None])
            result = enf.extract_twice("fake.dwg", tmp, cad=stub)
            self.assertEqual(result["status"], "unavailable")
            self.assertIsNone(result["ir_path_a"])
            self.assertIsNone(result["ir_path_b"])


class TestRunLiveProbeEndToEnd(unittest.TestCase):
    """run_live_probe composes extract_twice + run_probe -- proven end-to-end
    via the stub cad. The genuinely-external dependency (accoreconsole) is the
    ONLY thing injected away; every other line of production code runs for real.
    """

    def test_identical_stub_extracts_pass(self):
        import ir_builder
        import extractor_noise_floor as enf

        ir_doc = ir_builder.make_fixture_ir()
        with tempfile.TemporaryDirectory() as tmp:
            stub = _StubCad([ir_doc, json.loads(json.dumps(ir_doc))])
            report = enf.run_live_probe("fake.dwg", tmp, cad=stub)
            self.assertEqual(report["schema"], enf.NOISE_FLOOR_SCHEMA_ID)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["noise_floor"], 0.0)
            self.assertEqual(report["extraction"]["status"], "ok")

    def test_router_unavailable_is_reported_not_faked(self):
        """No live runtime reachable -> truthful 'unavailable', NEVER a fake PASS."""
        import extractor_noise_floor as enf
        with tempfile.TemporaryDirectory() as tmp:
            stub = _StubCad([None, None])
            report = enf.run_live_probe("fake.dwg", tmp, cad=stub)
            self.assertEqual(report["status"], "unavailable")
            self.assertNotEqual(report["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
