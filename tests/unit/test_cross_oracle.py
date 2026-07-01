#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer WAVE-0 F1.5 TEST -- cross_oracle: independent-engine multiset re-diff.

Intent (WHY):
  * Every existing roundtrip gate (cad_diff.py's W/D halves) re-reads the STAGED
    file through the SAME native pipeline it was written with -- a single-
    extractor monoculture (H-R29/R4-01): a field the native extractor drops on
    BOTH the pre- and post- read looks like ``diff == 0``, a fake PASS on data
    nobody actually looked at. cross_oracle.compare_multiset is the independent
    check: it certifies a native IR against a DIFFERENT engine's read of the
    SAME staged file. If this module's own field-loss/disagreement detection is
    wrong, F1.5 buys nothing (Rule 9: these tests pin WHY multiset/tripwire/
    not_certified matter, not just that compare_multiset returns a dict).
  * v2-A1 upgraded F1.5 from a >=1-entity spot-check to a FULL per-entity
    multiset re-diff with a HIGHER-PRIORITY tripwire pass -- the four scenarios
    the CADOS WAVE-0 plan mandates (agree/one-field-drift/oracle-populated-
    native-null/unsupported-field) are pinned here exactly, plus additional
    rigor: multiset must be truly ORDER-independent (not a positional list
    compare), the tripwire/disagreement/not_certified PRIORITY order must hold
    when more than one condition fires in a single comparison, a numeric
    tolerance must absorb genuine cross-engine float roundoff without masking
    a real shift, and the known-field registries must not silently drift from
    the JSON schema they are derived from.
  * run_live_cross_oracle (the deferred LIVE leg that wraps
    ``autocad-router.ps1 -Action run -Intent {dwg|dxf}``) is exercised with
    INJECTED fake/real callables so its truthful-degradation control flow --
    never a fake ``ok`` when the router/sibling modules are unavailable -- is
    proven without a live accoreconsole/AutoCAD host.

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

import cross_oracle  # noqa: E402  (sibling tools/ module, path-inserted above)


def _line_entity(handle, layer="0", start=(0.0, 0.0, 0.0), end=(10.0, 0.0, 0.0)):
    """A minimal LINE entity dict -- just the fields cross_oracle reads."""
    return {
        "handle": handle, "class": "AcDbLine", "dxf_name": "LINE",
        "owner_handle": "1F", "space": "model", "layer": layer,
        "bbox": [start[0], start[1], start[2], end[0], end[1], end[2]],
        "geometry": {"kind": "line", "start": list(start), "end": list(end)},
    }


def _ir(*entities):
    return {"schema": cross_oracle.IR_SCHEMA_ID, "entities": list(entities)}


# --------------------------------------------------------------------------- #
# The four mandated scenarios (CADOS WAVE-0 F1.5 v2-A1)
# --------------------------------------------------------------------------- #

class TestCompareMultisetMandatedScenarios(unittest.TestCase):

    def test_agree_returns_ok(self):
        oracle = _ir(_line_entity("2A7"))
        native = _ir(_line_entity("2A7"))
        result = cross_oracle.compare_multiset(oracle, native)
        self.assertEqual(result["status"], cross_oracle.STATUS_OK)
        self.assertEqual(result["exit_code"], cross_oracle.EXIT_OK)
        self.assertEqual(result["tripwires"], [])
        self.assertEqual(result["disagreements"], [])
        self.assertEqual(result["not_certified_fields"], [])

    def test_one_field_multiset_drift_returns_disagreement(self):
        oracle = _ir(_line_entity("2A7", layer="1"))
        native = _ir(_line_entity("2A7", layer="0"))
        result = cross_oracle.compare_multiset(oracle, native)
        self.assertEqual(result["status"], cross_oracle.STATUS_DISAGREEMENT)
        self.assertEqual(result["exit_code"], cross_oracle.EXIT_DISAGREEMENT)
        self.assertEqual(result["tripwires"], [])
        fields = {d["field"] for d in result["disagreements"]}
        self.assertIn("layer", fields)
        layer_diff = next(d for d in result["disagreements"] if d["field"] == "layer")
        values = {vd["value"] for vd in layer_diff["value_diffs"]}
        self.assertEqual(values, {"1", "0"})

    def test_oracle_populated_native_null_is_tripwire(self):
        oracle = _ir(_line_entity("2A7", layer="0"))
        native_entity = _line_entity("2A7", layer="0")
        del native_entity["layer"]  # native drops what the oracle actually saw.
        native = _ir(native_entity)
        result = cross_oracle.compare_multiset(oracle, native)
        self.assertEqual(result["status"], cross_oracle.STATUS_TRIPWIRE)
        self.assertEqual(result["exit_code"], cross_oracle.EXIT_TRIPWIRE)
        self.assertEqual(result["disagreements"], [])
        self.assertEqual(len(result["tripwires"]), 1)
        tw = result["tripwires"][0]
        self.assertEqual(tw["field"], "layer")
        self.assertEqual(tw["oracle_populated_count"], 1)
        self.assertEqual(tw["native_populated_count"], 0)

    def test_unsupported_oracle_field_is_not_certified(self):
        oracle_entity = _line_entity("2A7")
        oracle_entity["unsupported_field"] = "extra"
        oracle = _ir(oracle_entity)
        native = _ir(_line_entity("2A7"))
        result = cross_oracle.compare_multiset(oracle, native)
        self.assertEqual(result["status"], cross_oracle.STATUS_NOT_CERTIFIED)
        self.assertEqual(result["exit_code"], cross_oracle.EXIT_NOT_CERTIFIED)
        self.assertEqual(result["tripwires"], [])
        self.assertEqual(result["disagreements"], [])
        self.assertEqual(len(result["not_certified_fields"]), 1)
        self.assertEqual(result["not_certified_fields"][0]["field"], "unsupported_field")
        self.assertEqual(result["not_certified_fields"][0]["handle"], "2A7")


# --------------------------------------------------------------------------- #
# Additional rigor: order-independence, priority order, tolerance, extensibility
# --------------------------------------------------------------------------- #

class TestCompareMultisetRigor(unittest.TestCase):

    def test_multiset_is_order_independent_across_multiple_entities(self):
        oracle = _ir(_line_entity("A1", layer="0"), _line_entity("A2", layer="1"))
        # Same two layer values as a MULTISET, listed in the opposite order --
        # a positional/list compare would wrongly flag this as changed.
        native_reversed = _ir(_line_entity("A2", layer="1"), _line_entity("A1", layer="0"))
        result = cross_oracle.compare_multiset(oracle, native_reversed)
        self.assertEqual(result["status"], cross_oracle.STATUS_OK)

    def test_multiset_catches_distribution_mismatch_with_equal_totals(self):
        oracle = _ir(_line_entity("A1", layer="0"), _line_entity("A2", layer="1"))
        # Same POPULATED COUNT (2) on both sides, but the value distribution
        # differs ({"0","1"} vs {"0","0"}) -- must still be a disagreement, not
        # masked by the two counts happening to match.
        native_skewed = _ir(_line_entity("A1", layer="0"), _line_entity("A2", layer="0"))
        result = cross_oracle.compare_multiset(oracle, native_skewed)
        self.assertEqual(result["status"], cross_oracle.STATUS_DISAGREEMENT)
        self.assertEqual(result["exit_code"], cross_oracle.EXIT_DISAGREEMENT)

    def test_tripwire_outranks_disagreement_found_on_a_different_field(self):
        oracle = _ir(_line_entity("A1", layer="0", end=(10.0, 0.0, 0.0)))
        native_entity = _line_entity("A1", layer="0", end=(99.0, 0.0, 0.0))
        del native_entity["layer"]  # tripwire on 'layer'
        native = _ir(native_entity)  # disagreement on 'bbox'/'geometry.end'
        result = cross_oracle.compare_multiset(oracle, native)
        self.assertEqual(result["status"], cross_oracle.STATUS_TRIPWIRE)
        self.assertEqual(result["exit_code"], cross_oracle.EXIT_TRIPWIRE)
        self.assertEqual(result["summary"]["tripwire_count"], 1)
        # the geometry shift is real and still surfaced, just not the overall verdict.
        self.assertGreaterEqual(result["summary"]["disagreement_count"], 1)

    def test_geometry_tolerance_absorbs_roundoff_but_not_a_real_shift(self):
        oracle = _ir(_line_entity("A1", end=(10.0, 0.0, 0.0)))
        native_noise = _ir(_line_entity("A1", end=(10.0 + 1e-9, 0.0, 0.0)))
        ok = cross_oracle.compare_multiset(oracle, native_noise)
        self.assertEqual(ok["status"], cross_oracle.STATUS_OK)

        native_shifted = _ir(_line_entity("A1", end=(10.5, 0.0, 0.0)))
        bad = cross_oracle.compare_multiset(oracle, native_shifted)
        self.assertEqual(bad["status"], cross_oracle.STATUS_DISAGREEMENT)

        # tol=0 disables snapping entirely -- even the 1e-9 roundoff must then disagree.
        exact = cross_oracle.compare_multiset(oracle, native_noise, geometry_tolerance=0)
        self.assertEqual(exact["status"], cross_oracle.STATUS_DISAGREEMENT)

    def test_supported_fields_override_widens_active_comparison(self):
        oracle_entity = _line_entity("A1")
        oracle_entity["linetype"] = "DASHED"
        native_entity = _line_entity("A1")
        native_entity["linetype"] = "CONTINUOUS"
        oracle, native = _ir(oracle_entity), _ir(native_entity)

        # 'linetype' is a recognized dwg_graph_ir.v1 entity field the oracle
        # POPULATED, but it is NOT in the default active compare set -- this
        # must be not_certified, NEVER a silent 'ok' that papers over the
        # DASHED/CONTINUOUS mismatch nobody actually compared (the §0.6 v2-A1
        # hole: "recognized by the schema" is not "oracle-certified").
        default_result = cross_oracle.compare_multiset(oracle, native)
        self.assertEqual(default_result["status"], cross_oracle.STATUS_NOT_CERTIFIED)
        self.assertEqual(default_result["exit_code"], cross_oracle.EXIT_NOT_CERTIFIED)
        self.assertEqual(default_result["disagreements"], [])
        not_certified_fields = {f["field"] for f in default_result["not_certified_fields"]}
        self.assertIn("linetype", not_certified_fields)

        # Widening supported_fields to ACTIVELY certify 'linetype' turns the
        # same oracle-populated mismatch into a genuine, compared disagreement
        # -- and it must no longer ALSO show up as not_certified, since it is
        # now part of the active certified set.
        widened = cross_oracle.compare_multiset(
            oracle, native,
            supported_fields={"LINE": {"top": ["layer", "bbox", "linetype"]}})
        self.assertEqual(widened["status"], cross_oracle.STATUS_DISAGREEMENT)
        fields = {d["field"] for d in widened["disagreements"]}
        self.assertIn("linetype", fields)
        self.assertEqual(widened["not_certified_fields"], [])

    def test_certified_fields_for_kind_is_deterministic_and_ordered(self):
        first = cross_oracle.certified_fields_for_kind("LINE")
        second = cross_oracle.certified_fields_for_kind("LINE")
        self.assertEqual(first, second)
        self.assertIn("layer", first)
        self.assertIn("bbox", first)
        self.assertIn("geometry.start", first)


class TestFindUncertifiedOracleFields(unittest.TestCase):

    def test_flags_unknown_top_level_and_geometry_leaf_independently(self):
        ent = _line_entity("A1")
        ent["totally_made_up"] = 1
        ent["geometry"]["also_made_up"] = 2
        findings = cross_oracle.find_uncertified_oracle_fields(_ir(ent))
        fields = {f["field"] for f in findings}
        self.assertEqual(fields, {"totally_made_up", "geometry.also_made_up"})

    def test_recognized_schema_fields_never_flagged(self):
        # Every field a real ir_builder-produced entity carries must be a no-op
        # here even though only a subset is ACTIVELY multiset-compared.
        ent = _line_entity("A1")
        ent["class"] = "AcDbLine"
        ent["owner_handle"] = "1F"
        ent["space"] = "model"
        findings = cross_oracle.find_uncertified_oracle_fields(_ir(ent))
        self.assertEqual(findings, [])

    def test_recognized_but_uncompared_data_field_flagged_when_populated(self):
        """§0.6 v2-A1 hole (codex Layer-3 WEAK finding): 'recognized by the
        dwg_graph_ir.v1 schema' must not silently stand in for 'oracle-
        certified'. linetype/visible are legal schema fields but sit outside
        the DEFAULT active compare set -- if the oracle actually populates
        one, it must be flagged not_certified, not waved through just because
        the key happens to be schema-known. On the pre-fix code this asserts
        {} == {"linetype", "visible"} and fails, because the old scan only
        checked "is this key in _KNOWN_ENTITY_FIELDS at all", never whether it
        was in the ACTIVE certified-compare set."""
        ent = _line_entity("A1")
        ent["linetype"] = "DASHED"
        ent["visible"] = True
        findings = cross_oracle.find_uncertified_oracle_fields(_ir(ent))
        fields = {f["field"] for f in findings}
        self.assertEqual(fields, {"linetype", "visible"})

    def test_identity_and_provenance_fields_remain_exempt_even_when_uncompared(self):
        """Counterpart guard for the fix above: handle/class/owner_handle/
        space/dxf_name/source are ALSO recognized-but-never-actively-compared,
        but they are identifiers/provenance, not DATA an oracle could
        disagree on -- they must stay exempt so the not_certified widening
        above does not over-flag identity plumbing. 'source' is added fresh
        (not merely re-set) so this is a real presence check, not a no-op."""
        ent = _line_entity("A1")
        ent["source"] = {"extractor": "oracle"}
        findings = cross_oracle.find_uncertified_oracle_fields(_ir(ent))
        self.assertEqual(findings, [])


class TestKnownFieldRegistryMatchesSchema(unittest.TestCase):
    """Guards _KNOWN_ENTITY_FIELDS / _KNOWN_GEOMETRY_LEAF_FIELDS against silent
    drift from schemas/dwg_graph_ir.v1.schema.json (Rule 9: a hardcoded registry
    that can drift from its source of truth without failing a test is wrong)."""

    def test_known_entity_and_geometry_fields_match_the_json_schema(self):
        schema_path = os.path.join(_REPO, "schemas", "dwg_graph_ir.v1.schema.json")
        with open(schema_path, "r", encoding="utf-8-sig") as fh:
            schema = json.load(fh)
        defs = schema["$defs"]
        entity_fields = frozenset(defs["entity"]["properties"].keys())
        geometry_fields = frozenset(defs["geometry"]["properties"].keys())
        self.assertEqual(cross_oracle._KNOWN_ENTITY_FIELDS, entity_fields)
        self.assertEqual(cross_oracle._KNOWN_GEOMETRY_LEAF_FIELDS, geometry_fields)


# --------------------------------------------------------------------------- #
# The deferred LIVE leg: run_live_cross_oracle (dependency-injected, no subprocess)
# --------------------------------------------------------------------------- #

class TestRunLiveCrossOracle(unittest.TestCase):

    def test_unknown_engine_is_reported_unavailable(self):
        result = cross_oracle.run_live_cross_oracle("staged.dwg", _ir(), engine="bogus")
        self.assertEqual(result["status"], cross_oracle.STATUS_UNAVAILABLE)
        self.assertEqual(result["exit_code"], cross_oracle.EXIT_UNAVAILABLE)

    def test_router_process_error_is_reported_truthfully_not_faked_ok(self):
        def fake_router_extract(staged, run_dir, *, intent):
            return {"command": None, "exit_code": None,
                    "error": "router entrypoint missing: tools/autocad-router.ps1",
                    "envelope": None}

        def fail_ir_from_extract(extract, summary, source_meta):
            self.fail("ir_from_extract must not be called when the router process itself errored")

        result = cross_oracle.run_live_cross_oracle(
            "staged.dwg", _ir(), engine="accoreconsole",
            router_extract=fake_router_extract, ir_from_extract=fail_ir_from_extract)
        self.assertEqual(result["status"], cross_oracle.STATUS_UNAVAILABLE)
        self.assertEqual(result["exit_code"], cross_oracle.EXIT_UNAVAILABLE)
        self.assertIn("router entrypoint missing", result["reason"])

    def test_router_non_pass_status_is_reported_truthfully_not_faked_ok(self):
        def fake_router_extract(staged, run_dir, *, intent):
            return {"command": ["powershell"], "exit_code": 1, "error": None,
                    "envelope": {"status": "UNAVAILABLE", "selection": {"available": False}}}

        def fail_ir_from_extract(extract, summary, source_meta):
            self.fail("ir_from_extract must not be called when the router did not PASS")

        result = cross_oracle.run_live_cross_oracle(
            "staged.dwg", _ir(), engine="accoreconsole",
            router_extract=fake_router_extract, ir_from_extract=fail_ir_from_extract)
        self.assertEqual(result["status"], cross_oracle.STATUS_UNAVAILABLE)
        self.assertEqual(result["router_status"], "UNAVAILABLE")

    def test_router_pass_without_extract_json_is_reported_truthfully(self):
        # Models today's REAL dxf_fast_secondary shape (run_route.py): PASS, but
        # only aggregate entities_by_type counts -- no per-entity extract_json.
        def fake_router_extract(staged, run_dir, *, intent):
            self.assertEqual(intent, "dxf")
            return {"command": ["powershell"], "exit_code": 0, "error": None,
                    "envelope": {"status": "PASS",
                                 "execution": {"engine_exit_code": 0,
                                               "engine_output": {"status": "ok",
                                                                  "entity_count": 3}}}}

        def fail_ir_from_extract(extract, summary, source_meta):
            self.fail("ir_from_extract must not be called without a per-entity extract_json")

        result = cross_oracle.run_live_cross_oracle(
            "staged.dwg", _ir(), engine="ezdxf",
            router_extract=fake_router_extract, ir_from_extract=fail_ir_from_extract)
        self.assertEqual(result["status"], cross_oracle.STATUS_UNAVAILABLE)
        self.assertEqual(result["exit_code"], cross_oracle.EXIT_UNAVAILABLE)
        self.assertIn("extract_json", result["reason"])

    def test_end_to_end_with_injected_router_and_real_ir_builder_agrees(self):
        """Proves the FULL live-leg plumbing (router envelope -> extract JSON on
        disk -> ir_builder normalization -> compare_multiset) with the router
        subprocess itself faked out and every other piece REAL (no mocks)."""
        import ir_builder  # real sibling module; no subprocess involved.

        extract = {
            "schema": "ariadne.dwg_geometry_extract.v1", "route": "dwg_truth_autocad",
            "status": "ok", "source": {"dwg_name": "staged.dwg", "format": "dwg"},
            "summary": {"modelspace_count": 1, "entities_by_type": {"LINE": 1}},
            "entities": [{
                "handle": "2A7", "object_id": "id-1", "type": "LINE", "layer": "0",
                "geometry": {
                    "kind": "line",
                    "start": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "end": {"x": 10.0, "y": 0.0, "z": 0.0},
                },
            }],
        }

        with tempfile.TemporaryDirectory() as td:
            extract_path = os.path.join(td, "extract_arx.json")
            with open(extract_path, "w", encoding="utf-8") as fh:
                json.dump(extract, fh)

            def fake_router_extract(staged, run_dir, *, intent):
                self.assertEqual(intent, "dwg")
                self.assertEqual(staged, "staged.dwg")
                return {"command": ["powershell", "-File", "autocad-router.ps1"],
                        "exit_code": 0, "error": None,
                        "envelope": {"status": "PASS",
                                     "execution": {"engine_exit_code": 0,
                                                   "engine_output": {
                                                       "status": "ok",
                                                       "winning_engine": "arx",
                                                       "extract_json": extract_path,
                                                   }}}}

            native_ir = ir_builder.build_ir_from_extract(
                extract, extract["summary"],
                {"extractor": "native_fixture", "engine_tier": "native_arx",
                 "route": "dwg_truth_autocad", "dwg_path": "staged.dwg", "byte_size": 0})

            result = cross_oracle.run_live_cross_oracle(
                "staged.dwg", native_ir, engine="accoreconsole",
                router_extract=fake_router_extract,
                ir_from_extract=ir_builder.build_ir_from_extract)

        self.assertEqual(result["status"], cross_oracle.STATUS_OK)
        self.assertEqual(result["exit_code"], cross_oracle.EXIT_OK)
        self.assertEqual(result["engine"], "accoreconsole")
        self.assertEqual(result["intent"], "dwg")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

class TestCli(unittest.TestCase):

    def test_main_compares_two_ir_files_and_writes_out(self):
        with tempfile.TemporaryDirectory() as td:
            oracle_path = os.path.join(td, "oracle.json")
            native_path = os.path.join(td, "native.json")
            out_path = os.path.join(td, "out.json")
            with open(oracle_path, "w", encoding="utf-8") as fh:
                json.dump(_ir(_line_entity("2A7", layer="1")), fh)
            with open(native_path, "w", encoding="utf-8") as fh:
                json.dump(_ir(_line_entity("2A7", layer="0")), fh)

            code = cross_oracle.main(["--oracle-ir", oracle_path, "--native-ir", native_path,
                                      "--out", out_path])

            self.assertEqual(code, cross_oracle.EXIT_DISAGREEMENT)
            self.assertTrue(os.path.exists(out_path))
            with open(out_path, "r", encoding="utf-8") as fh:
                written = json.load(fh)
            self.assertEqual(written["status"], cross_oracle.STATUS_DISAGREEMENT)

    def test_main_staged_dwg_requires_native_ir(self):
        self.assertEqual(cross_oracle.main(["--staged-dwg", "some.dwg"]), 2)

    def test_main_oracle_ir_alone_is_blocked(self):
        self.assertEqual(cross_oracle.main(["--oracle-ir", "a.json"]), 2)

    def test_selftest_passes(self):
        self.assertEqual(cross_oracle._selftest(), 0)


if __name__ == "__main__":
    unittest.main()
