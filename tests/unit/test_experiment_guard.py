#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import hashlib
from pathlib import Path

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_E2 = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "tools", "e2"))
if _TOOLS_E2 not in sys.path:
    sys.path.insert(0, _TOOLS_E2)

import experiment_guard as guard
import run_guarded_experiment as guarded_runner


def _rich_ir(*, include_hatch=True, entity_count=3, proxy_status="partial"):
    sections = [
        "entities",
        "database",
        "symbol_tables",
        "block_table_records",
        "block_definitions",
        "layouts",
        "xrefs",
        "dictionaries",
        "xrecords",
        "xdata",
    ]
    if include_hatch:
        sections.append("hatch_loops")
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "coverage_level": "native_full",
        "database": {},
        "symbol_tables": {"layers": [{"name": "0"}]},
        "block_definitions": [{"name": "WALL"}],
        "block_references": [{"block_name": "WALL"}],
        "layouts": [],
        "xrefs": [],
        "dictionaries": [],
        "xrecords": [],
        "entities": [{"dxf_name": "LINE", "layer": "0"}] * entity_count,
        "diagnostics": {
            "entity_count": entity_count,
            "realized_entity_count": entity_count,
            "warnings": [],
            "errors": [],
            "coverage": {
                "modelspace_count_from_native": entity_count,
                "realized_entity_count": entity_count,
                "match": True,
                "sections_present": sections,
                "sections_skipped": ["groups"],
                "section_status": {
                    **{name: "implemented" for name in sections},
                    "layers": "implemented",
                    "proxy_objects": proxy_status,
                },
                "counts": {"hatch_loops": 2 if include_hatch else 0},
                "proxy_or_undecoded_count": 0,
            },
        },
    }


def test_counts_only_claim_selects_summary_and_needs_live_probe():
    result = guard.qualify(
        required_observables=["database_counts", "drawing_units"],
        candidate="auto",
    )
    assert result["status"] == guard.NEEDS_PROBE
    assert result["selected_pipeline"] == "database_summary"


def test_rich_claim_rejects_summary_and_selects_native_graph():
    result = guard.qualify(
        required_observables=[
            "modelspace_geometry",
            "block_definitions",
            "nested_insert_graph",
            "hatch_boundary_loops",
            "layer_provenance",
        ],
        candidate="database_summary",
    )
    assert result["status"] == guard.NEEDS_PROBE
    assert result["selected_pipeline"] == "native_graph"
    assert result["candidate_accepted"] is False
    assert "database_summary" in result["rejected_candidates"]


def test_unknown_observable_never_degrades_to_a_weaker_tool():
    result = guard.qualify(
        required_observables=["vendor_custom_wall_semantics"],
        candidate="auto",
    )
    assert result["status"] == guard.NEEDS_TOOL
    assert result["selected_pipeline"] is None


def test_missing_rich_graph_to_worldir_bridge_is_needs_build():
    result = guard.qualify(
        required_observables=["nested_insert_world_geometry"],
        candidate="auto",
    )
    assert result["status"] == guard.NEEDS_BUILD
    assert result["selected_pipeline"] is None
    assert "rich_graph_to_worldir" in result["missing_builds"]


def _worldir_probe(*, adapter_balance=True, conservation=True, inserts=1):
    return {
        "oracle": "worldir.oracle.v1",
        "status": "PASS",
        "drawing_id": "probe",
        "input_mode": "definition_graph",
        "segments": [{"lineage_id": "L1", "p0_world": [0, 0], "p1_world": [1, 0]}],
        "adapter_ledger": {
            "scope": "LINE_POLYLINE_ARC_INSERT",
            "source_entity_templates": 3,
            "adapted_entity_templates": 3 if adapter_balance else 2,
            "explicitly_excluded_entity_templates": 0,
            "excluded_by_dxf_name": {},
            "balance_ok": adapter_balance,
        },
        "conservation_ledger": {
            "reachable_insert_placements": inserts,
            "expected_segment_instances": 1,
            "visible_source_segment_instances": 1 if conservation else 0,
            "clipped_away_segment_instances": 0,
            "clip_generated_fragment_instances": 0,
            "emitted_segment_instances": 1 if conservation else 0,
            "conservation_delta": 0 if conservation else 1,
            "conservation_ok": conservation,
        },
        "failure_ledger": [],
    }


def test_supported_nested_world_segments_selects_adapter_oracle_pipeline():
    result = guard.qualify(
        required_observables=["nested_insert_world_segments", "world_lineage"],
        candidate="auto",
    )
    assert result["status"] == guard.NEEDS_PROBE
    assert result["selected_pipeline"] == "native_graph_worldir_segments"


def test_worldir_probe_with_both_ledgers_opens_supported_segment_experiment():
    decision = guard.qualify(
        required_observables=[
            "nested_insert_world_segments",
            "world_lineage",
            "silent_drop_detection",
        ],
        candidate="auto",
    )
    result = guard.verify_probe(decision, _worldir_probe())
    assert result["status"] == guard.READY
    assert result["coverage_level"] == "world_segments_verified"


def test_worldir_probe_with_adapter_imbalance_stays_closed():
    decision = guard.qualify(
        required_observables=["nested_insert_world_segments"], candidate="auto")
    result = guard.verify_probe(decision, _worldir_probe(adapter_balance=False))
    assert result["status"] == guard.NEEDS_BUILD
    assert result["reason_code"] == "ADAPTER_LEDGER_FAILED"


def test_worldir_probe_accepts_explicit_xclip_balance():
    decision = guard.qualify(
        required_observables=["nested_insert_world_segments", "xclip_preservation"],
        candidate="auto",
    )
    probe = _worldir_probe()
    probe["conservation_ledger"].update({
        "expected_segment_instances": 9,
        "visible_source_segment_instances": 1,
        "clipped_away_segment_instances": 8,
        "emitted_segment_instances": 1,
        "clip_generated_fragment_instances": 0,
    })

    result = guard.verify_probe(decision, probe)

    assert result["status"] == guard.READY


def test_worldir_probe_rejects_missing_clip_accounting():
    decision = guard.qualify(
        required_observables=["nested_insert_world_segments"], candidate="auto"
    )
    probe = _worldir_probe()
    del probe["conservation_ledger"]["visible_source_segment_instances"]

    result = guard.verify_probe(decision, probe)

    assert result["status"] == guard.NEEDS_PROBE
    assert result["reason_code"] == "WORLDIR_CONSERVATION_FAILED"


def test_native_full_probe_opens_rich_experiment():
    requirements = [
        "modelspace_geometry",
        "block_definitions",
        "nested_insert_graph",
        "hatch_boundary_loops",
        "layer_provenance",
    ]
    decision = guard.qualify(required_observables=requirements, candidate="auto")
    result = guard.verify_probe(decision, _rich_ir())
    assert result["status"] == guard.READY
    assert result["selected_pipeline"] == "native_graph"
    assert result["coverage_level"] == "native_full"


def test_claimed_hatch_observation_fails_when_probe_omits_hatch_loops():
    decision = guard.qualify(
        required_observables=["hatch_boundary_loops"], candidate="auto")
    result = guard.verify_probe(decision, _rich_ir(include_hatch=False))
    assert result["status"] == guard.NEEDS_BUILD
    assert "hatch_boundary_loops" in result["unverified_observables"]


def test_empty_probe_cannot_be_called_ready_by_default():
    decision = guard.qualify(
        required_observables=["modelspace_geometry"], candidate="auto")
    result = guard.verify_probe(decision, _rich_ir(entity_count=0))
    assert result["status"] == guard.NEEDS_PROBE
    assert result["reason_code"] == "VACUOUS_PROBE"


def test_impossibility_claim_requires_an_independent_oracle():
    decision = guard.qualify(
        required_observables=["modelspace_geometry"],
        candidate="auto",
        conclusion="impossibility",
    )
    result = guard.verify_probe(decision, _rich_ir())
    assert result["status"] == guard.NEEDS_PROBE
    assert result["reason_code"] == "INDEPENDENT_ORACLE_REQUIRED"


def test_absence_claim_accepts_only_hash_bound_independent_receipt(tmp_path: Path):
    evidence = tmp_path / "oracle.json"
    evidence.write_text('{"count": 3}', encoding="utf-8")
    receipt = {
        "status": "PASS",
        "evidence": [
            {
                "path": str(evidence),
                "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            }
        ],
    }
    decision = guard.qualify(
        required_observables=["modelspace_geometry"],
        candidate="auto",
        conclusion="absence",
    )

    accepted = guard.verify_probe(
        decision,
        _rich_ir(),
        independent_oracle_receipt=receipt,
    )
    evidence.write_text('{"count": 4}', encoding="utf-8")
    rejected = guard.verify_probe(
        decision,
        _rich_ir(),
        independent_oracle_receipt=receipt,
    )

    assert accepted["status"] == guard.READY
    assert rejected["status"] == guard.NEEDS_PROBE
    assert rejected["reason_code"] == "INDEPENDENT_ORACLE_REQUIRED"


def test_proxy_geometry_is_not_promoted_from_partial_identity_coverage():
    result = guard.qualify(
        required_observables=["proxy_object_geometry"], candidate="auto")
    assert result["status"] == guard.NEEDS_TOOL
    assert "object_enabler_or_vendor_sdk" in result["missing_tools"]


def test_guarded_runner_does_not_execute_without_probe():
    calls = []

    def fake_runner(command, check=False):
        calls.append(command)
        raise AssertionError("experiment command must not run")

    result = guarded_runner.run_guarded(
        required_observables=["modelspace_geometry"],
        command=["python", "model.py"],
        runner=fake_runner,
    )
    assert result["guard"]["status"] == guard.NEEDS_PROBE
    assert result["executed"] is False
    assert calls == []


def test_guarded_runner_executes_only_after_ready_probe():
    calls = []

    class Completed:
        returncode = 7

    def fake_runner(command, check=False):
        calls.append(command)
        return Completed()

    result = guarded_runner.run_guarded(
        required_observables=["modelspace_geometry", "block_definitions"],
        command=["python", "model.py"],
        probe_output=_rich_ir(),
        runner=fake_runner,
    )
    assert result["guard"]["status"] == guard.READY
    assert result["executed"] is True
    assert result["command_exit_code"] == 7
    assert calls == [["python", "model.py"]]


def test_guarded_runner_never_executes_known_build_gap():
    calls = []

    def fake_runner(command, check=False):
        calls.append(command)
        raise AssertionError("experiment command must not run")

    result = guarded_runner.run_guarded(
        required_observables=["nested_insert_world_geometry"],
        command=["python", "model.py"],
        probe_output=_rich_ir(),
        runner=fake_runner,
    )
    assert result["guard"]["status"] == guard.NEEDS_BUILD
    assert result["executed"] is False
    assert calls == []
