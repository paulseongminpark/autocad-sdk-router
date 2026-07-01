#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer F5 TEST -- diff-scope legislation, diff_id basis/scope hashing,
handle-independent geometry-basis diff_id (RT-FOLD R4-06), and v2-A5 per-quantity
tolerance.

Intent (WHY):
  * [R4-06] Before this fix, ``_deterministic_diff_id`` hashed ONLY the
    handle-keyed signature of both IRs, no matter which ``comparison_basis`` ran
    -- so the SAME IR pair under ``basis="handle"`` and ``basis="geometry"``
    collided on ONE id (a basis-collision), and -- the dual defect -- the
    geometry-basis id was itself keyed by HANDLE, so a regenerated drawing whose
    engine reissues every handle produced a DIFFERENT id on every run even
    though nothing about the geometry changed, making the ledger key noise
    (VF12/G8 reconciliation meaningless). We pin both halves: two bases over the
    identical IR pair MUST diverge, and two independent regen runs of the same
    source MUST land on the identical geometry-basis id, while the handle-basis
    id stays exactly as handle-sensitive as it always was (it is NOT supposed to
    be regen-reproducible; that is what makes it "handle-basis").
  * [F5 scope] Which entities are even eligible for a diff is legislated in
    ``config/diff_scope.json``, not implicit. ``modelspace_entities_only``
    (default) excludes non-modelspace entities; ``full_database`` includes
    every space and additionally subtracts a caller-supplied
    ``seed_baseline_mask`` so a blank-seed's default symbol-table/block-def
    records (H-R18) never pollute the diff -- without the mask, a seed record
    that gets reissued a fresh handle on regen would show up as a FALSE
    added+removed pair even though nothing meaningful changed.
  * [v2-A5] A single ``tol=1e-6`` cannot be right for a length, an angle
    (radians), and a large-site-scale coordinate all at once. Per-quantity
    tolerances must be genuinely independent (a huge coordinate on one field
    must never loosen a sibling angle field's tolerance) and "large coordinate"
    relative scaling must actually engage (a proportional-noise coordinate
    shift at large magnitude must not false-fail).

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only
(plus optional jsonschema).
"""
from __future__ import annotations

import copy
import json
import math
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SCHEMAS = os.path.join(_REPO, "schemas")
_CONFIG = os.path.join(_REPO, "config")
_JSON_ENCODING = "utf-8-sig"


def _load_json(path):
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _try_import_jsonschema():
    try:
        import jsonschema  # type: ignore
        return jsonschema
    except Exception:  # pragma: no cover
        return None


def _base_ir():
    import ir_builder
    return ir_builder.make_fixture_ir()


def _relabel_handles(ir, prefix):
    """Deep copy ``ir`` with every entity handle replaced -- simulates one
    independent 'regen' run of an engine that reissues handles on rebuild."""
    out = copy.deepcopy(ir)
    for i, e in enumerate(out["entities"]):
        e["handle"] = "%s%d" % (prefix, i)
    return out


def _insert_entity(handle, position, rotation, layer="0"):
    """A minimal INSERT-shaped entity carrying both a length field (position)
    and an angle field (rotation) -- just enough for the per-quantity/large-
    coordinate boundary tests to exercise both kinds on one entity."""
    return {
        "handle": handle, "class": "AcDbBlockReference", "dxf_name": "INSERT",
        "owner_handle": "1", "space": "model", "layer": layer,
        "bbox": [position[0] - 1, position[1] - 1, 0.0,
                 position[0] + 1, position[1] + 1, 0.0],
        "geometry": {"kind": "block_reference", "position": list(position),
                     "rotation": rotation, "block_name": "X"},
        "source": {"extractor": "test", "decoded": True},
    }


def _ir(entities):
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "entities": entities,
        "diagnostics": {"entity_count": len(entities)},
    }


class TestDiffIdBasisDistinct(unittest.TestCase):
    """[R4-06 basis-collision] The SAME IR pair under a different comparison_basis
    must never collide on one diff_id."""

    def test_diff_id_basis_distinct(self):
        import cad_diff
        pre = _base_ir()
        post = copy.deepcopy(pre)  # identical -- basis is the only variable
        d_handle = cad_diff.compute_diff(pre, post, comparison_basis="handle")
        d_geometry = cad_diff.compute_diff(pre, post, comparison_basis="geometry")
        self.assertEqual(d_handle["diagnostics"]["comparison_basis"], "handle")
        self.assertEqual(d_geometry["diagnostics"]["comparison_basis"], "geometry")
        self.assertNotEqual(d_handle["diff_id"], d_geometry["diff_id"])


class TestDiffIdGeometryReproducible(unittest.TestCase):
    """[R4-06 dual defect] The geometry-basis diff_id must be handle-INDEPENDENT:
    two independent regen runs of the same source (fresh handles each run) must
    reproduce the IDENTICAL diff_id; the handle-basis path is unaffected (it
    stays exactly as handle-sensitive as ever -- that IS its contract)."""

    def test_diff_id_geometry_reproducible(self):
        import cad_diff
        source = _base_ir()
        regen_a = _relabel_handles(source, "A")
        regen_b = _relabel_handles(source, "B")
        self.assertNotEqual(
            [e["handle"] for e in regen_a["entities"]],
            [e["handle"] for e in regen_b["entities"]],
            "test fixture bug: the two regen runs must actually use different handles",
        )

        diff_a = cad_diff.compute_diff(source, regen_a, comparison_basis="geometry")
        diff_b = cad_diff.compute_diff(source, regen_b, comparison_basis="geometry")

        # both regen runs are geometrically identical to source -> zero changes,
        # and (the R4-06 fix) the SAME diff_id despite the disjoint handle sets.
        self.assertEqual(diff_a["summary"]["modified"], 0)
        self.assertEqual(diff_a["summary"]["added"], 0)
        self.assertEqual(diff_a["summary"]["removed"], 0)
        self.assertEqual(diff_a["diff_id"], diff_b["diff_id"])

    def test_handle_basis_unaffected_by_regen_fix(self):
        import cad_diff
        source = _base_ir()
        regen_a = _relabel_handles(source, "A")
        regen_b = _relabel_handles(source, "B")

        # under comparison_basis="handle" the SAME source vs two DIFFERENTLY
        # handled regens are legitimately different comparisons (that is the
        # handle-basis join's actual contract) -- the R4-06 fix must not touch
        # this; it stays exactly as handle-sensitive as before.
        diff_a = cad_diff.compute_diff(source, regen_a, comparison_basis="handle")
        diff_b = cad_diff.compute_diff(source, regen_b, comparison_basis="handle")
        self.assertNotEqual(diff_a["diff_id"], diff_b["diff_id"])
        # and re-running the identical (source, regen_a) pair is still
        # byte-for-byte deterministic (unchanged pre-existing guarantee).
        diff_a2 = cad_diff.compute_diff(source, regen_a, comparison_basis="handle")
        self.assertEqual(
            json.dumps(diff_a, sort_keys=True, ensure_ascii=False),
            json.dumps(diff_a2, sort_keys=True, ensure_ascii=False),
        )


class TestPerQuantityToleranceBoundary(unittest.TestCase):
    """v2-A5: per-quantity tolerances (length/angle/scale/large-coordinate) +
    unit/extent scaling, with fixtures deliberately near quantization buckets."""

    def test_bucket_edge_within_tolerance_not_false_fail(self):
        """Two coordinates 4e-7 apart (well within the 1e-6 length tolerance),
        straddling an INTEGER multiple of tol -- a naive floor()/truncation
        bucketer would split them into adjacent buckets (a false-fail); the
        round()-based grid this module uses must not."""
        import cad_diff
        tol = cad_diff.DEFAULT_GEOMETRY_TOLERANCE  # 1e-6
        v1 = 5.0                 # exactly on a tol grid line: v1/tol == 5_000_000
        v2 = 5.0 - 0.4 * tol      # 4e-7 away -- within tol, but crosses that grid line
        self.assertLess(abs(v1 - v2), tol)
        # sanity: this really would be a false-fail under naive floor bucketing,
        # proving the fixture is a genuine near-bucket-edge case, not a trivial one.
        self.assertNotEqual(math.floor(v1 / tol), math.floor(v2 / tol))

        pre = _ir([_insert_entity("AAA", (v1, 0.0, 0.0), 0.0)])
        post = _ir([_insert_entity("ZZZ", (v2, 0.0, 0.0), 0.0)])  # rehandled too
        diff = cad_diff.compute_diff(pre, post, comparison_basis="geometry")
        self.assertEqual(diff["summary"]["modified"], 0)
        self.assertEqual(diff["summary"]["added"], 0)
        self.assertEqual(diff["summary"]["removed"], 0)
        self.assertEqual(diff["summary"]["unchanged"], 1)

    def test_large_coordinate_angle_error_not_false_pass(self):
        """A real angular error (1e-6 rad, 1000x the 1e-9 angle tolerance) on an
        entity whose COORDINATE is far past the large-coordinate threshold
        (2e7) must still be DETECTED. If large-coordinate relative scaling ever
        leaked from the "length" kind into "angle" (a plausible implementation
        bug), the scaled tolerance at that magnitude (~0.02) would swallow this
        error and false-PASS it as unchanged."""
        import cad_diff
        large = 2.0e7
        angle_delta = 1e-6
        profile = cad_diff.default_tolerance_profile()
        self.assertGreater(angle_delta, profile["angle"],
                           "fixture bug: angle_delta must exceed the real angle tolerance")
        # if (incorrectly) evaluated against the large-coordinate length tolerance
        # at this magnitude, this same delta would read as "within tolerance".
        leaked_tolerance = cad_diff._effective_tolerance("length", large, profile)
        self.assertLess(angle_delta, leaked_tolerance,
                        "fixture bug: angle_delta must be a false-pass risk under kind leakage")

        pre = _ir([_insert_entity("AAA", (large, 0.0, 0.0), 0.0)])
        post = _ir([_insert_entity("ZZZ", (large, 0.0, 0.0), angle_delta)])
        diff = cad_diff.compute_diff(pre, post, comparison_basis="geometry")
        self.assertEqual(diff["summary"]["modified"], 1,
                         "false-PASS: a real angular error was swallowed by large-coordinate scaling")
        self.assertEqual(diff["summary"]["unchanged"], 0)

    def test_large_coordinate_length_noise_not_false_fail(self):
        """The mirror case: proportional roundtrip noise on the SAME
        large-magnitude coordinate (5mm noise on a 20,000km position -- far
        above the fixed 1e-6 absolute tolerance, but within the large-coordinate
        relative tolerance at that scale) must NOT false-fail. This proves the
        large-coordinate widening actually engages, not just that it stays out
        of angle's way."""
        import cad_diff
        large = 2.0e7
        noise = 0.005  # 5mm -- >> 1e-6 absolute, << large-coordinate scaled tol (~0.02)
        profile = cad_diff.default_tolerance_profile()
        scaled_tol = cad_diff._effective_tolerance("length", large, profile)
        self.assertGreater(noise, profile["length"])
        self.assertLess(noise, scaled_tol)

        pre = _ir([_insert_entity("AAA", (large, 0.0, 0.0), 0.0)])
        post = _ir([_insert_entity("ZZZ", (large + noise, 0.0, 0.0), 0.0)])
        diff = cad_diff.compute_diff(pre, post, comparison_basis="geometry")
        self.assertEqual(diff["summary"]["modified"], 0,
                         "false-FAIL: proportional noise on a large coordinate was flagged as a change")
        self.assertEqual(diff["summary"]["unchanged"], 1)


class TestLargeCoordinateFalsePass(unittest.TestCase):
    """[F5 tolerance rigor, defect 1] codex Layer-3 WEAK finding: before this
    fix, ``_effective_tolerance``'s large-coordinate widening was re-derived
    PER-SCALAR from each value's own magnitude during hashing
    (``tol = magnitude * rel_tol``), so ``value / tol`` collapsed to the
    constant ``1 / rel_tol`` for every magnitude past the threshold -- two
    genuinely different large coordinates (e.g. 2e7 vs 3e7) quantized onto the
    SAME grid point and hashed as the "same" fingerprint, silently swallowing
    a real ~1e7-unit edit as unchanged. The fix resolves ONE shared tolerance
    from the whole drawing's extent (``_resolve_tolerance_profile``) instead
    of re-deriving it per scalar, and matches leftovers pairwise
    (``abs(a - b) <= tol``) rather than by fingerprint hash."""

    def test_2e7_vs_3e7_reported_modified(self):
        import cad_diff
        pre = _ir([_insert_entity("AAA", (2.0e7, 0.0, 0.0), 0.0)])
        post = _ir([_insert_entity("ZZZ", (3.0e7, 0.0, 0.0), 0.0)])  # rehandled too
        diff = cad_diff.compute_diff(pre, post, comparison_basis="geometry")
        self.assertEqual(diff["summary"]["modified"], 1,
                         "false-PASS: two genuinely different large coordinates "
                         "(2e7 vs 3e7) collapsed onto the same fingerprint bucket")
        self.assertEqual(diff["summary"]["unchanged"], 0)
        self.assertEqual(diff["summary"]["added"], 0)
        self.assertEqual(diff["summary"]["removed"], 0)

    def test_other_large_coordinate_pair_also_detected(self):
        """A second, independent magnitude pair -- proves the fix isn't a
        one-off coincidence tuned to exactly 2e7/3e7."""
        import cad_diff
        pre = _ir([_insert_entity("AAA", (5.0e7, 0.0, 0.0), 0.0)])
        post = _ir([_insert_entity("ZZZ", (8.0e7, 0.0, 0.0), 0.0)])
        diff = cad_diff.compute_diff(pre, post, comparison_basis="geometry")
        self.assertEqual(diff["summary"]["modified"], 1)
        self.assertEqual(diff["summary"]["unchanged"], 0)


class TestHalfBucketBoundaryPairwise(unittest.TestCase):
    """[F5 tolerance rigor, defect 2] codex Layer-3 WEAK finding:
    ``round(value / tol)`` is not a true within-tolerance equivalence -- two
    values within tolerance of each other can straddle a rounding-grid
    half-integer boundary and hash to DIFFERENT buckets, false-failing
    geometry that is genuinely unchanged. The fix replaces bucket-hash
    equality with a direct pairwise ``abs(a - b) <= tol`` compare
    (``_geometry_within_tolerance``) for anything that doesn't byte-exact
    match at tier 1 -- a direct threshold compare has no grid to straddle."""

    def test_half_bucket_straddle_within_tolerance_is_equal(self):
        import cad_diff
        tol = cad_diff.DEFAULT_GEOMETRY_TOLERANCE  # 1e-6
        n = 5_000_000
        # a/tol and b/tol straddle the (n - 0.5) half-integer round() boundary
        # (round(a/tol) == n-1, round(b/tol) == n) even though |a-b| is only
        # 0.4*tol -- well within tolerance. A naive hash-bucket join reports
        # these as DIFFERENT; a genuine tolerant compare must not.
        a = (n - 0.5 - 0.2) * tol
        b = (n - 0.5 + 0.2) * tol
        self.assertLess(abs(a - b), tol)
        self.assertAlmostEqual(abs(a - b), 0.4 * tol, places=12)
        self.assertNotEqual(
            round(a / tol), round(b / tol),
            "fixture bug: a and b must actually straddle a round()-bucket "
            "boundary to exercise the half-bucket defect")

        pre = _ir([_insert_entity("AAA", (a, 0.0, 0.0), 0.0)])
        post = _ir([_insert_entity("ZZZ", (b, 0.0, 0.0), 0.0)])  # rehandled too
        diff = cad_diff.compute_diff(pre, post, comparison_basis="geometry")
        self.assertEqual(diff["summary"]["modified"], 0,
                         "false-FAIL: two values only 0.4*tol apart (well within "
                         "tolerance) were reported as changed because they "
                         "straddled a rounding-grid boundary")
        self.assertEqual(diff["summary"]["unchanged"], 1)

    def test_values_two_tol_apart_are_reported_modified(self):
        """Mirror sanity check: a real difference (2*tol, well beyond
        tolerance) must still be detected -- the fix must not over-widen
        matching into swallowing genuine edits."""
        import cad_diff
        tol = cad_diff.DEFAULT_GEOMETRY_TOLERANCE
        v1 = 5.0
        v2 = 5.0 + 2 * tol
        pre = _ir([_insert_entity("AAA", (v1, 0.0, 0.0), 0.0)])
        post = _ir([_insert_entity("ZZZ", (v2, 0.0, 0.0), 0.0)])
        diff = cad_diff.compute_diff(pre, post, comparison_basis="geometry")
        self.assertEqual(diff["summary"]["modified"], 1)
        self.assertEqual(diff["summary"]["unchanged"], 0)


def _ratio_entity(handle, key, value, layer="0"):
    """A minimal entity carrying a single dimensionless-ratio geometry leaf
    (``scale``/``bulge``/``minor_ratio``) -- just enough to exercise the
    scale/relative-tolerance band classification (``_quantity_kind``)."""
    return {
        "handle": handle, "class": "AcDbEntity", "dxf_name": "TESTENT",
        "owner_handle": "1", "space": "model", "layer": layer,
        "bbox": [], "geometry": {"kind": "ratio_test", key: value},
        "source": {"extractor": "test", "decoded": True},
    }


class TestScaleRatioToleranceClassification(unittest.TestCase):
    """[F5 tolerance rigor, defect 3] "scale tolerance exists but is
    untested": ``scale``/``bulge``/``minor_ratio`` are dimensionless ratios
    and must be classified/compared under the tight "scale" tolerance band
    (1e-9), not silently fall through to the far looser "length" default
    (1e-6) -- a fall-through false-PASSes a real ratio edit that is bigger
    than the scale tolerance but smaller than the length tolerance.
    ``minor_ratio`` (an ELLIPSE's minor/major axis ratio, see
    ``dwg_graph_ir.v1.schema.json``) was missing from ``_SCALE_KEYS`` before
    this fix and fell through to "length"."""

    def test_keys_classified_as_scale_kind(self):
        import cad_diff
        for key in ("scale", "bulge", "minor_ratio"):
            self.assertEqual(cad_diff._quantity_kind(key), "scale", key)

    def test_ratio_edit_between_scale_and_length_tolerance_is_modified(self):
        """A delta bigger than the scale tolerance (1e-9) but comfortably
        smaller than the length tolerance (1e-6) must register as a change
        for each ratio key -- if a key fell through to "length" this edit
        would false-pass as unchanged (as ``minor_ratio`` did before this fix)."""
        import cad_diff
        profile = cad_diff.default_tolerance_profile()
        delta = 3e-7
        self.assertGreater(delta, profile["scale"])
        self.assertLess(delta, profile["length"])
        for key in ("scale", "bulge", "minor_ratio"):
            pre = _ir([_ratio_entity("AAA", key, 1.0)])
            post = _ir([_ratio_entity("ZZZ", key, 1.0 + delta)])
            diff = cad_diff.compute_diff(pre, post, comparison_basis="geometry")
            self.assertEqual(diff["summary"]["modified"], 1,
                             "false-PASS: a %r delta of %.1e was swallowed by a "
                             "looser tolerance kind" % (key, delta))
            self.assertEqual(diff["summary"]["unchanged"], 0, key)

    def test_ratio_noise_within_scale_tolerance_is_unchanged(self):
        """Mirror case: noise smaller than the scale tolerance must NOT
        register -- proves the scale tolerance actually applies (not that any
        difference at all gets flagged)."""
        import cad_diff
        profile = cad_diff.default_tolerance_profile()
        noise = profile["scale"] * 0.1
        for key in ("scale", "bulge", "minor_ratio"):
            pre = _ir([_ratio_entity("AAA", key, 1.0)])
            post = _ir([_ratio_entity("ZZZ", key, 1.0 + noise)])
            diff = cad_diff.compute_diff(pre, post, comparison_basis="geometry")
            self.assertEqual(diff["summary"]["modified"], 0, key)
            self.assertEqual(diff["summary"]["unchanged"], 1, key)


class TestDiffScopeLegislation(unittest.TestCase):
    """config/diff_scope.json legislates {modelspace_entities_only|full_database}."""

    def test_identical_irs_zero_diff_both_scopes(self):
        pre = _base_ir()
        pre["entities"].append(_insert_entity("P01", (0.0, 0.0, 0.0), 0.0))
        pre["entities"][-1]["space"] = "paper"
        post = copy.deepcopy(pre)

        import cad_diff
        for scope in (cad_diff.MODELSPACE_ENTITIES_ONLY, cad_diff.FULL_DATABASE):
            diff = cad_diff.compute_diff(pre, post, diff_scope=scope)
            self.assertEqual(diff["summary"]["added"], 0, scope)
            self.assertEqual(diff["summary"]["removed"], 0, scope)
            self.assertEqual(diff["summary"]["modified"], 0, scope)
            self.assertEqual(diff["diagnostics"]["diff_scope"], scope)

    def test_modelspace_scope_excludes_non_model_space_entities(self):
        import cad_diff
        pre = _base_ir()
        post_new_paper_entity = copy.deepcopy(pre)
        paper_ent = _insert_entity("P02", (0.0, 0.0, 0.0), 0.0)
        paper_ent["space"] = "paper"
        post_new_paper_entity["entities"].append(paper_ent)

        d_modelspace = cad_diff.compute_diff(
            pre, post_new_paper_entity, diff_scope=cad_diff.MODELSPACE_ENTITIES_ONLY)
        d_full = cad_diff.compute_diff(
            pre, post_new_paper_entity, diff_scope=cad_diff.FULL_DATABASE)

        self.assertEqual(d_modelspace["summary"]["added"], 0,
                         "a new paperspace entity leaked into modelspace_entities_only")
        self.assertEqual(d_full["summary"]["added"], 1,
                         "full_database must see the new paperspace entity")

    def test_default_scope_is_modelspace_entities_only(self):
        import cad_diff
        pre = _base_ir()
        diff = cad_diff.compute_diff(pre, copy.deepcopy(pre))
        self.assertEqual(diff["diagnostics"]["diff_scope"], cad_diff.MODELSPACE_ENTITIES_ONLY)

    def test_invalid_diff_scope_raises(self):
        import cad_diff
        pre = _base_ir()
        with self.assertRaises(ValueError):
            cad_diff.compute_diff(pre, copy.deepcopy(pre), diff_scope="not_a_real_scope")


class TestSeedBaselineMask(unittest.TestCase):
    """full_database subtracts a seed_baseline_mask (H-R18) -- a blank-seed's
    default records must never register as noise, even when the regenerating
    engine reissues their handle."""

    def test_full_database_mask_excludes_reissued_seed_record(self):
        import cad_diff
        pre = _base_ir()
        seed_record = {
            "handle": "SEED1", "class": "AcDbLayerTableRecord", "dxf_name": "LAYER_DEF",
            "owner_handle": "", "space": "model", "layer": "0", "bbox": [],
            "geometry": {"kind": "unsupported"},
            "source": {"extractor": "test", "decoded": False},
        }
        pre["entities"].append(seed_record)
        post = copy.deepcopy(pre)
        # simulate the seed record being reissued a fresh handle on regen ...
        for e in post["entities"]:
            if e["handle"] == "SEED1":
                e["handle"] = "SEED1-REGEN"
        # ... alongside one genuine new modelspace entity.
        post["entities"].append(_insert_entity("NEW1", (5.0, 5.0, 0.0), 0.0))

        mask = [{"dxf_name": "LAYER_DEF", "layer": "0"}]  # wildcard: no "geometry" key

        # Without the mask: the reissued seed handle IS noise (added+removed).
        d_nomask = cad_diff.compute_diff(pre, post, diff_scope=cad_diff.FULL_DATABASE)
        nomask_handles = {r["handle"] for r in d_nomask["changed_handles"]}
        self.assertIn("SEED1", nomask_handles)
        self.assertIn("SEED1-REGEN", nomask_handles)

        # With the mask: the seed churn is excluded; the genuine entity remains visible.
        d_masked = cad_diff.compute_diff(pre, post, diff_scope=cad_diff.FULL_DATABASE,
                                         seed_baseline_mask=mask)
        masked_handles = {r["handle"] for r in d_masked["changed_handles"]}
        self.assertNotIn("SEED1", masked_handles)
        self.assertNotIn("SEED1-REGEN", masked_handles)
        by_handle_change = {(r["handle"], r["change"]) for r in d_masked["changed_handles"]}
        self.assertIn(("NEW1", "added"), by_handle_change)
        self.assertGreaterEqual(d_masked["diagnostics"]["seed_baseline_excluded_before"], 1)
        self.assertGreaterEqual(d_masked["diagnostics"]["seed_baseline_excluded_after"], 1)

    def test_mask_ignored_under_modelspace_scope(self):
        """A mask only makes sense for full_database; modelspace scope silently
        ignores it rather than erroring (seed records never live in modelspace,
        so masking under that scope would be a no-op by construction)."""
        import cad_diff
        pre = _base_ir()
        post = copy.deepcopy(pre)
        mask = [{"dxf_name": "LINE", "layer": "0"}]  # would otherwise mask fixture's own LINE
        diff = cad_diff.compute_diff(pre, post, diff_scope=cad_diff.MODELSPACE_ENTITIES_ONLY,
                                     seed_baseline_mask=mask)
        self.assertNotIn("seed_baseline_excluded_before", diff["diagnostics"])
        self.assertEqual(diff["summary"]["unchanged"], len(pre["entities"]))


class TestDiffScopeConfigShape(unittest.TestCase):
    """config/diff_scope.json exists on disk, parses, and legislates both scopes."""

    def test_config_file_shape(self):
        cfg = _load_json(os.path.join(_CONFIG, "diff_scope.json"))
        self.assertEqual(cfg.get("default_scope"), "modelspace_entities_only")
        self.assertEqual(cfg.get("freeze_scope"), "full_database")
        self.assertIn("modelspace_entities_only", cfg.get("scopes", {}))
        self.assertIn("full_database", cfg.get("scopes", {}))
        self.assertEqual(
            sorted(cfg.get("valid_scopes", [])),
            ["full_database", "modelspace_entities_only"],
        )

    def test_load_diff_scope_config_matches_file(self):
        import cad_diff
        cfg = cad_diff.load_diff_scope_config()
        on_disk = _load_json(os.path.join(_CONFIG, "diff_scope.json"))
        self.assertEqual(cfg.get("default_scope"), on_disk.get("default_scope"))
        self.assertEqual(cfg.get("freeze_scope"), on_disk.get("freeze_scope"))


class TestFullDatabaseDiffSchemaConforms(unittest.TestCase):
    """A full_database-scope, geometry-basis diff still conforms to cad_diff.v1
    (the new diagnostics/scope fields are schema-extension fields)."""

    def test_validates_against_schema(self):
        jsonschema = _try_import_jsonschema()
        if jsonschema is None:
            self.skipTest("SKIPPED_DEP: jsonschema not importable")
        import cad_diff
        pre = _base_ir()
        post = _relabel_handles(pre, "R")
        diff = cad_diff.compute_diff(pre, post, comparison_basis="geometry",
                                     diff_scope=cad_diff.FULL_DATABASE)
        schema = _load_json(os.path.join(_SCHEMAS, "cad_diff.v1.schema.json"))
        jsonschema.Draft7Validator.check_schema(schema)
        validator = jsonschema.Draft7Validator(schema)
        errors = sorted(validator.iter_errors(diff), key=lambda e: list(e.path))
        self.assertEqual(
            errors, [],
            "full_database geometry-basis diff does not conform to cad_diff.v1: "
            + "; ".join("%s: %s" % ("/".join(str(p) for p in e.path), e.message)
                       for e in errors[:8]),
        )


if __name__ == "__main__":
    unittest.main()
