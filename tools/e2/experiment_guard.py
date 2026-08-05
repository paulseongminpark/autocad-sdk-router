#!/usr/bin/env python3
"""Fail-closed instrument qualification for E2 CAD experiments.

The guard answers one question: may an experiment use the proposed observation
pipeline to support its claim?  It deliberately does not run a model.  A
caller must obtain READY from a probe output before starting the experiment.

This is a runtime decision module, not an inventory.  It reads the existing
AutoCAD operation registry for implementation status, selects the smallest
known-sufficient pipeline, and verifies the resulting IR's measured coverage.
Unknown observables and incomplete adapters never degrade to a weaker route.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


READY = "READY"
NEEDS_PROBE = "NEEDS_PROBE"
NEEDS_TOOL = "NEEDS_TOOL"
NEEDS_BUILD = "NEEDS_BUILD"
REDESIGN = "REDESIGN"
BLOCKED = "BLOCKED"

EXIT_CODES = {
    READY: 0,
    NEEDS_PROBE: 20,
    NEEDS_TOOL: 21,
    NEEDS_BUILD: 22,
    REDESIGN: 23,
    BLOCKED: 24,
}

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OPERATIONS_PATH = _REPO_ROOT / "config" / "operations.v2.json"


# These are verified observation profiles, not claims that an executable can
# read every possible DWG object.  Probe verification below remains mandatory.
_PIPELINES: dict[str, dict[str, Any]] = {
    "database_summary": {
        "rank": 10,
        "operations": ["inspect.database.summary"],
        "provides": {
            "database_counts",
            "drawing_units",
            "modelspace_entity_count",
        },
    },
    "native_graph": {
        "rank": 20,
        "operations": ["inspect.database.graph"],
        "provides": {
            "database_counts",
            "drawing_units",
            "modelspace_entity_count",
            "modelspace_geometry",
            "layer_provenance",
            "block_definitions",
            "nested_insert_graph",
            "hatch_boundary_loops",
            "layouts",
            "xrefs",
            "dictionaries",
            "xrecords",
            "entity_xdata",
            "utf8_text",
        },
    },
    "native_graph_worldir_segments": {
        "rank": 30,
        "operations": ["inspect.database.graph"],
        "local_modules": [
            "tools/e2/instruments/dwg_graph_to_worldir.py",
            "tools/e2/instruments/worldir_oracle.py",
        ],
        "provides": {
            "nested_insert_world_segments",
            "world_lineage",
            "silent_drop_detection",
            "xclip_preservation",
            "source_document_identity",
            "native_display_membership",
            "model_input_membership",
        },
    },
}

# Known gaps must be explicit.  They are not treated as unknown tokens because
# the next action is already known and actionable.
_BUILD_GAPS = {
    "nested_insert_world_geometry": "rich_graph_to_worldir",
    "array_expanded_world_geometry": "rich_graph_to_worldir",
}

_TOOL_GAPS = {
    "proxy_object_geometry": "object_enabler_or_vendor_sdk",
    "vendor_custom_wall_semantics": "object_enabler_or_vendor_sdk",
}

_KNOWN_OBSERVABLES = set().union(
    *[profile["provides"] for profile in _PIPELINES.values()],
    _BUILD_GAPS,
    _TOOL_GAPS,
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _operation_records() -> dict[str, dict[str, Any]]:
    payload = _load_json(_OPERATIONS_PATH)
    return {
        str(item.get("id")): item
        for item in payload.get("operations", [])
        if isinstance(item, dict) and item.get("id")
    }


def _ordered_unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _result(status: str, **fields: Any) -> dict[str, Any]:
    return {
        "schema": "ariadne.e2.experiment_guard.v1",
        "status": status,
        "exit_code": EXIT_CODES[status],
        "selected_pipeline": None,
        "selected_operations": [],
        "candidate_accepted": False,
        "rejected_candidates": [],
        "missing_tools": [],
        "missing_builds": [],
        "unverified_observables": [],
        **fields,
    }


def _transition(base: Mapping[str, Any], status: str, **updates: Any) -> dict[str, Any]:
    """Carry a decision forward while replacing status-specific evidence."""
    fields = {
        key: value
        for key, value in base.items()
        if key not in {"schema", "status", "exit_code", *updates.keys()}
    }
    fields.update(updates)
    return _result(status, **fields)


def qualify(
    *,
    required_observables: Iterable[str],
    candidate: str = "auto",
    conclusion: str = "exploratory",
    operation_records: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Plan an observation pipeline, but never return READY without a probe."""
    required = _ordered_unique(required_observables)
    if not required:
        return _result(
            REDESIGN,
            required_observables=[],
            conclusion=conclusion,
            reason_code="NO_OBSERVABLES_DECLARED",
            reason="The experiment did not declare what the instrument must observe.",
        )

    unknown = sorted(set(required) - _KNOWN_OBSERVABLES)
    if unknown:
        return _result(
            NEEDS_TOOL,
            required_observables=required,
            conclusion=conclusion,
            unverified_observables=unknown,
            reason_code="UNKNOWN_OBSERVABLE",
            reason="No verified local instrument profile covers every requested observable.",
        )

    missing_tools = sorted({_TOOL_GAPS[item] for item in required if item in _TOOL_GAPS})
    if missing_tools:
        return _result(
            NEEDS_TOOL,
            required_observables=required,
            conclusion=conclusion,
            missing_tools=missing_tools,
            unverified_observables=[item for item in required if item in _TOOL_GAPS],
            reason_code="EXTERNAL_CAPABILITY_REQUIRED",
            reason="The requested object semantics require a provider-specific capability.",
        )

    missing_builds = sorted({_BUILD_GAPS[item] for item in required if item in _BUILD_GAPS})
    if missing_builds:
        return _result(
            NEEDS_BUILD,
            required_observables=required,
            conclusion=conclusion,
            missing_builds=missing_builds,
            unverified_observables=[item for item in required if item in _BUILD_GAPS],
            reason_code="ADAPTER_REQUIRED",
            reason="The source and oracle exist, but their verified runtime adapter is missing.",
        )

    required_set = set(required)
    eligible = [
        (name, profile)
        for name, profile in _PIPELINES.items()
        if required_set <= profile["provides"]
    ]
    eligible.sort(key=lambda item: (item[1]["rank"], item[0]))
    if not eligible:
        return _result(
            REDESIGN,
            required_observables=required,
            conclusion=conclusion,
            unverified_observables=required,
            reason_code="NO_SUFFICIENT_PIPELINE",
            reason="No current pipeline can preserve all requested observables.",
        )

    requested_candidate = str(candidate or "auto")
    candidate_accepted = requested_candidate == "auto"
    rejected: list[str] = []
    selected_name, selected_profile = eligible[0]
    if requested_candidate != "auto":
        profile = _PIPELINES.get(requested_candidate)
        if profile is not None and required_set <= profile["provides"]:
            selected_name, selected_profile = requested_candidate, profile
            candidate_accepted = True
        else:
            rejected.append(requested_candidate)

    records = dict(operation_records) if operation_records is not None else _operation_records()
    unavailable_ops = [
        op_id
        for op_id in selected_profile["operations"]
        if not records.get(op_id) or records[op_id].get("status") != "implemented"
    ]
    if unavailable_ops:
        return _result(
            NEEDS_BUILD,
            required_observables=required,
            conclusion=conclusion,
            rejected_candidates=rejected,
            missing_builds=unavailable_ops,
            reason_code="OPERATION_NOT_IMPLEMENTED",
            reason="The selected pipeline contains a registry operation that is not implemented.",
        )

    missing_modules = [
        relative
        for relative in selected_profile.get("local_modules", [])
        if not (_REPO_ROOT / relative).is_file()
    ]
    if missing_modules:
        return _result(
            NEEDS_BUILD,
            required_observables=required,
            conclusion=conclusion,
            rejected_candidates=rejected,
            missing_builds=missing_modules,
            reason_code="LOCAL_MODULE_MISSING",
            reason="The selected pipeline's verified local implementation is incomplete.",
        )

    return _result(
        NEEDS_PROBE,
        required_observables=required,
        conclusion=conclusion,
        selected_pipeline=selected_name,
        selected_operations=list(selected_profile["operations"]),
        candidate_accepted=candidate_accepted,
        rejected_candidates=rejected,
        reason_code="LIVE_PROBE_REQUIRED",
        reason="The pipeline is sufficient on paper; a matching live probe must prove coverage.",
    )


def _coverage(ir: Mapping[str, Any]) -> Mapping[str, Any]:
    diagnostics = ir.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        return {}
    coverage = diagnostics.get("coverage")
    return coverage if isinstance(coverage, Mapping) else {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_sha256(value: Mapping[str, Any]) -> str:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def _normalized_sha256(value: Any) -> str | None:
    """Return a canonical SHA-256 value only when its form is exact."""

    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    return candidate if _SHA256_HEX.fullmatch(candidate) else None


def _independent_oracle_receipt_ok(receipt: Mapping[str, Any] | None) -> bool:
    if not isinstance(receipt, Mapping) or receipt.get("status") != "PASS":
        return False
    evidence = receipt.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return False
    for record in evidence:
        if not isinstance(record, Mapping):
            return False
        path = Path(str(record.get("path", "")))
        expected = str(record.get("sha256", "")).lower()
        if len(expected) != 64 or not path.is_file() or _sha256(path) != expected:
            return False
    return True


def _stable_segment_id(segment: Mapping[str, Any]) -> str:
    return str(
        segment.get("placed_uid")
        or segment.get("lineage_id")
        or segment.get("handle")
        or ""
    )


def _target_population_check(
    world: Mapping[str, Any],
    target_oracle: Mapping[str, Any] | None,
    model_input: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Compare native-display truth, WorldIR lineage and the actual model population."""

    if target_oracle is None:
        return {
            "status": NEEDS_BUILD,
            "reason_code": "NATIVE_DISPLAY_ORACLE_REQUIRED",
            "reason": (
                "Build or supply a hash-bound AutoCAD native-display membership oracle; "
                "the WorldIR XCLIP implementation cannot certify itself."
            ),
            "missing_builds": ["autocad.native_display_membership.v1"],
            "target_population": {},
        }
    if (
        not isinstance(target_oracle, Mapping)
        or target_oracle.get("schema") != "ariadne.e2.target_population_oracle.v1"
        or target_oracle.get("oracle") != "autocad.native_display_membership.v1"
        or not _independent_oracle_receipt_ok(target_oracle)
    ):
        return {
            "status": NEEDS_PROBE,
            "reason_code": "TARGET_POPULATION_ORACLE_INVALID",
            "reason": "A hash-bound AutoCAD native-display target oracle is required.",
            "target_population": {},
        }
    if not isinstance(model_input, Mapping) or not isinstance(model_input.get("segments"), list):
        return {
            "status": NEEDS_PROBE,
            "reason_code": "MODEL_INPUT_RECEIPT_REQUIRED",
            "reason": "The exact model-input IR must be supplied before the model command may run.",
            "target_population": {},
        }
    evidence_payload_sha256 = {
        "world_ir": _payload_sha256(world),
        "target_population_oracle": _payload_sha256(target_oracle),
        "model_input_ir": _payload_sha256(model_input),
    }

    drawing_id = str(world.get("drawing_id") or "")
    oracle_drawing_id = str(target_oracle.get("drawing_id") or "")
    model_drawing_id = str(model_input.get("drawing_id") or "")
    if (
        not drawing_id
        or drawing_id == "unknown"
        or drawing_id != oracle_drawing_id
        or drawing_id != model_drawing_id
    ):
        return {
            "status": BLOCKED,
            "reason_code": "SOURCE_SCOPE_UNRESOLVED",
            "reason": "WorldIR, native-display oracle and model input do not identify the same drawing.",
            "target_population": {},
            "evidence_payload_sha256": evidence_payload_sha256,
        }

    targets = target_oracle.get("targets")
    if not isinstance(targets, list) or not targets:
        return {
            "status": NEEDS_PROBE,
            "reason_code": "VACUOUS_TARGET_POPULATION",
            "reason": "The native-display oracle declared no target populations.",
            "target_population": {},
            "evidence_payload_sha256": evidence_payload_sha256,
        }

    conservation = world.get("conservation_ledger")
    entries = conservation.get("entity_entries") if isinstance(conservation, Mapping) else None
    world_segments = world.get("segments")
    if not isinstance(entries, list) or not isinstance(world_segments, list):
        return {
            "status": NEEDS_BUILD,
            "reason_code": "TARGET_LINEAGE_MISSING",
            "reason": "WorldIR lacks per-entity target lineage required for layer-level conservation.",
            "target_population": {},
            "evidence_payload_sha256": evidence_payload_sha256,
        }

    world_visible_by_layer: dict[str, int] = {}
    for entry in entries:
        if not isinstance(entry, Mapping) or "source_layer" not in entry:
            return {
                "status": NEEDS_BUILD,
                "reason_code": "TARGET_LINEAGE_MISSING",
                "reason": "A WorldIR entity ledger entry has no source_layer.",
                "target_population": {},
                "evidence_payload_sha256": evidence_payload_sha256,
            }
        layer = str(entry.get("source_layer") or "")
        visible = entry.get("visible_source_segments")
        if not isinstance(visible, int) or visible < 0:
            return {
                "status": NEEDS_BUILD,
                "reason_code": "TARGET_LINEAGE_MISSING",
                "reason": "A WorldIR entity ledger entry has invalid visible-source accounting.",
                "target_population": {},
                "evidence_payload_sha256": evidence_payload_sha256,
            }
        world_visible_by_layer[layer] = world_visible_by_layer.get(layer, 0) + visible

    world_ids_by_layer: dict[str, set[str]] = {}
    world_seen_ids: set[str] = set()
    for segment in world_segments:
        if not isinstance(segment, Mapping) or "source_layer" not in segment:
            return {
                "status": NEEDS_BUILD,
                "reason_code": "TARGET_LINEAGE_MISSING",
                "reason": "A WorldIR segment has no source_layer.",
                "target_population": {},
                "evidence_payload_sha256": evidence_payload_sha256,
            }
        segment_id = _stable_segment_id(segment)
        if not segment_id:
            return {
                "status": NEEDS_BUILD,
                "reason_code": "TARGET_LINEAGE_MISSING",
                "reason": "A WorldIR segment has no stable placed identity.",
                "target_population": {},
                "evidence_payload_sha256": evidence_payload_sha256,
            }
        if segment_id in world_seen_ids:
            return {
                "status": NEEDS_BUILD,
                "reason_code": "TARGET_LINEAGE_MISSING",
                "reason": "WorldIR contains duplicate stable placed identities.",
                "target_population": {},
                "evidence_payload_sha256": evidence_payload_sha256,
            }
        world_seen_ids.add(segment_id)
        layer = str(segment.get("source_layer") or "")
        world_ids_by_layer.setdefault(layer, set()).add(segment_id)

    model_ids_by_layer: dict[str, set[str]] = {}
    model_seen_ids: set[str] = set()
    for segment in model_input["segments"]:
        if not isinstance(segment, Mapping):
            return {
                "status": NEEDS_PROBE,
                "reason_code": "MODEL_INPUT_RECEIPT_INVALID",
                "reason": "A model-input segment is not an object.",
                "target_population": {},
                "evidence_payload_sha256": evidence_payload_sha256,
            }
        segment_id = _stable_segment_id(segment)
        layer = str(segment.get("source_layer", segment.get("layer", "")) or "")
        if not segment_id or not layer:
            return {
                "status": NEEDS_PROBE,
                "reason_code": "MODEL_INPUT_RECEIPT_INVALID",
                "reason": "Every model-input segment needs a stable placed identity and source layer.",
                "target_population": {},
                "evidence_payload_sha256": evidence_payload_sha256,
            }
        if segment_id in model_seen_ids:
            return {
                "status": NEEDS_PROBE,
                "reason_code": "MODEL_INPUT_RECEIPT_INVALID",
                "reason": "The model-input receipt contains duplicate stable placed identities.",
                "target_population": {},
                "evidence_payload_sha256": evidence_payload_sha256,
            }
        model_seen_ids.add(segment_id)
        model_ids_by_layer.setdefault(layer, set()).add(segment_id)

    summary: dict[str, dict[str, Any]] = {}
    seen_targets: set[str] = set()
    seen_native_ids: set[str] = set()
    lost = False
    disagreement = False
    positive_native_targets = 0
    for target in targets:
        if not isinstance(target, Mapping):
            return {
                "status": NEEDS_PROBE,
                "reason_code": "TARGET_POPULATION_ORACLE_INVALID",
                "reason": "Every native-display target must be an object.",
                "target_population": {},
                "evidence_payload_sha256": evidence_payload_sha256,
            }
        target_id = str(target.get("target_id") or "")
        layer = str(target.get("layer") or "")
        native_visible = target.get("native_visible_source_segments")
        native_id_values = target.get("native_visible_segment_ids")
        if (
            not target_id
            or target_id in seen_targets
            or not layer
            or not isinstance(native_visible, int)
            or native_visible < 0
            or not isinstance(native_id_values, list)
            or any(not isinstance(item, str) or not item for item in native_id_values)
            or len(native_id_values) != len(set(native_id_values))
            or native_visible != len(native_id_values)
        ):
            return {
                "status": NEEDS_PROBE,
                "reason_code": "TARGET_POPULATION_ORACLE_INVALID",
                "reason": (
                    "Target ids, layers, native visible counts and unique stable segment ids "
                    "must be complete and consistent."
                ),
                "target_population": {},
                "evidence_payload_sha256": evidence_payload_sha256,
            }
        seen_targets.add(target_id)
        native_ids = set(native_id_values)
        if native_ids & seen_native_ids:
            return {
                "status": NEEDS_PROBE,
                "reason_code": "TARGET_POPULATION_ORACLE_INVALID",
                "reason": "A native-visible stable segment identity appears in multiple targets.",
                "target_population": {},
                "evidence_payload_sha256": evidence_payload_sha256,
            }
        seen_native_ids.update(native_ids)
        if native_visible > 0:
            positive_native_targets += 1
        world_visible = world_visible_by_layer.get(layer, 0)
        world_ids = world_ids_by_layer.get(layer, set())
        model_ids = model_ids_by_layer.get(layer, set())
        native_missing_from_world = native_ids - world_ids
        world_missing_from_native = world_ids - native_ids
        missing_ids = native_ids - model_ids
        extra_ids = model_ids - native_ids
        if native_visible > 0 and (not model_ids or missing_ids):
            lost = True
        if native_visible != world_visible or native_missing_from_world or world_missing_from_native:
            disagreement = True
        if extra_ids:
            lost = True
        summary[target_id] = {
            "layer": layer,
            "native_visible_source_segments": native_visible,
            "world_visible_source_segments": world_visible,
            "world_emitted_segments": len(world_ids),
            "model_input_segments": len(model_ids),
            "native_missing_from_worldir_segments": len(native_missing_from_world),
            "worldir_missing_from_native_segments": len(world_missing_from_native),
            "missing_model_input_segments": len(missing_ids),
            "extra_model_input_segments": len(extra_ids),
        }

    if positive_native_targets == 0:
        return {
            "status": NEEDS_PROBE,
            "reason_code": "VACUOUS_TARGET_POPULATION",
            "reason": "The oracle did not exercise a visible target population.",
            "target_population": summary,
            "evidence_payload_sha256": evidence_payload_sha256,
        }
    if lost:
        return {
            "status": BLOCKED,
            "reason_code": "TARGET_POPULATION_LOST",
            "reason": "A native-visible target is absent or changed in the exact model-input population.",
            "target_population": summary,
            "evidence_payload_sha256": evidence_payload_sha256,
        }
    if disagreement:
        return {
            "status": BLOCKED,
            "reason_code": "XCLIP_ORACLE_DISAGREEMENT",
            "reason": "WorldIR visibility accounting disagrees with the independent AutoCAD display oracle.",
            "target_population": summary,
            "evidence_payload_sha256": evidence_payload_sha256,
        }
    return {
        "status": READY,
        "reason_code": "TARGET_POPULATION_PRESERVED",
        "reason": "Every native-visible target is preserved from WorldIR lineage into model input.",
        "target_population": summary,
        "evidence_payload_sha256": evidence_payload_sha256,
    }


def _native_graph_observable_ok(observable: str, ir: Mapping[str, Any]) -> bool:
    coverage = _coverage(ir)
    present = set(coverage.get("sections_present") or [])
    status = coverage.get("section_status") or {}

    if observable == "database_counts":
        return isinstance(ir.get("database"), Mapping) and isinstance(coverage.get("counts"), Mapping)
    if observable == "drawing_units":
        return isinstance(ir.get("database"), Mapping)
    if observable == "modelspace_entity_count":
        return bool(coverage.get("match")) and isinstance(ir.get("entities"), list)
    if observable == "modelspace_geometry":
        return (
            ir.get("coverage_level") == "native_full"
            and "entities" in present
            and bool(coverage.get("match"))
            and isinstance(ir.get("entities"), list)
        )
    if observable == "layer_provenance":
        tables = ir.get("symbol_tables")
        return (
            isinstance(tables, Mapping)
            and isinstance(tables.get("layers"), list)
            and status.get("layers") == "implemented"
        )
    if observable == "block_definitions":
        return isinstance(ir.get("block_definitions"), list) and "block_definitions" in present
    if observable == "nested_insert_graph":
        return (
            isinstance(ir.get("block_definitions"), list)
            and isinstance(ir.get("block_references"), list)
            and "block_definitions" in present
        )
    if observable == "hatch_boundary_loops":
        return "hatch_loops" in present and status.get("hatch_loops") == "implemented"
    if observable == "layouts":
        return isinstance(ir.get("layouts"), list) and "layouts" in present
    if observable == "xrefs":
        return isinstance(ir.get("xrefs"), list) and "xrefs" in present
    if observable == "dictionaries":
        return isinstance(ir.get("dictionaries"), list) and "dictionaries" in present
    if observable == "xrecords":
        return isinstance(ir.get("xrecords"), list) and "xrecords" in present
    if observable == "entity_xdata":
        return "xdata" in present and status.get("xdata") == "implemented"
    if observable == "utf8_text":
        return isinstance(ir.get("entities"), list) and ir.get("coverage_level") == "native_full"
    return False


def verify_probe(
    decision: Mapping[str, Any],
    probe_output: Mapping[str, Any],
    *,
    allow_empty: bool = False,
    independent_oracle_receipt: Mapping[str, Any] | None = None,
    target_population_oracle: Mapping[str, Any] | None = None,
    model_input_output: Mapping[str, Any] | None = None,
    expected_source_sha256: str | None = None,
) -> dict[str, Any]:
    """Promote NEEDS_PROBE to READY only when measured coverage is adequate."""
    base = dict(decision)
    if base.get("status") != NEEDS_PROBE or not base.get("selected_pipeline"):
        return base

    pipeline = base["selected_pipeline"]
    required = list(base.get("required_observables") or [])

    if pipeline == "native_graph_worldir_segments":
        source_identity_evidence: dict[str, str] | None = None
        adapter_ledger = probe_output.get("adapter_ledger")
        if not isinstance(adapter_ledger, Mapping) or not adapter_ledger.get("balance_ok"):
            return _transition(
                base,
                NEEDS_BUILD,
                unverified_observables=required,
                reason_code="ADAPTER_LEDGER_FAILED",
                reason="The rich-graph adapter did not prove source/adapted/excluded balance.",
            )
        conservation = probe_output.get("conservation_ledger")
        expected = conservation.get("expected_segment_instances") if isinstance(conservation, Mapping) else None
        visible = conservation.get("visible_source_segment_instances") if isinstance(conservation, Mapping) else None
        clipped = conservation.get("clipped_away_segment_instances") if isinstance(conservation, Mapping) else None
        emitted = conservation.get("emitted_segment_instances") if isinstance(conservation, Mapping) else None
        fragments = conservation.get("clip_generated_fragment_instances") if isinstance(conservation, Mapping) else None
        if (
            probe_output.get("oracle") != "worldir.oracle.v1"
            or probe_output.get("status") != "PASS"
            or not isinstance(conservation, Mapping)
            or not conservation.get("conservation_ok")
            or not all(isinstance(value, int) and value >= 0 for value in (expected, visible, clipped, emitted, fragments))
            or expected != visible + clipped
            or emitted != visible + fragments
        ):
            return _transition(
                base,
                NEEDS_PROBE,
                unverified_observables=required,
                reason_code="WORLDIR_CONSERVATION_FAILED",
                reason=(
                    "WorldIR did not prove both source-segment clipping balance and visible-fragment balance."
                ),
            )
        segments = probe_output.get("segments")
        unverified: list[str] = []
        if "nested_insert_world_segments" in required and (
            not isinstance(segments, list)
            or not segments
            or int(conservation.get("reachable_insert_placements", 0)) <= 0
        ):
            unverified.append("nested_insert_world_segments")
        if "world_lineage" in required and (
            not isinstance(segments, list)
            or not segments
            or any(not segment.get("lineage_id") for segment in segments if isinstance(segment, Mapping))
        ):
            unverified.append("world_lineage")
        if unverified:
            return _transition(
                base,
                NEEDS_PROBE,
                unverified_observables=unverified,
                reason_code="WORLDIR_PROBE_INADEQUATE",
                reason="The WorldIR probe did not exercise every requested property.",
            )
        if "source_document_identity" in required:
            expected_source = _normalized_sha256(expected_source_sha256)
            if expected_source is None:
                return _transition(
                    base,
                    NEEDS_PROBE,
                    unverified_observables=["source_document_identity"],
                    reason_code="SOURCE_DOCUMENT_BINDING_REQUIRED",
                    reason=(
                        "source_document_identity requires an explicit, well-formed "
                        "SHA-256 computed from the source or staged DWG."
                    ),
                )
            drawing_id = _normalized_sha256(probe_output.get("drawing_id"))
            if drawing_id is None:
                return _transition(
                    base,
                    NEEDS_PROBE,
                    unverified_observables=["source_document_identity"],
                    reason_code="SOURCE_DOCUMENT_IDENTITY_UNRESOLVED",
                    reason="The WorldIR probe lacks a well-formed SHA-256 drawing identity.",
                )
            if drawing_id != expected_source:
                return _transition(
                    base,
                    NEEDS_PROBE,
                    unverified_observables=["source_document_identity"],
                    reason_code="SOURCE_DOCUMENT_IDENTITY_MISMATCH",
                    reason="The WorldIR probe drawing identity does not match the hashed source or staged DWG.",
                )
            source_identity_evidence = {
                "expected_source_sha256": expected_source,
                "verified_probe_drawing_id": drawing_id,
            }
        if {"native_display_membership", "model_input_membership"} & set(required):
            target_check = _target_population_check(
                probe_output,
                target_population_oracle,
                model_input_output,
            )
            if target_check["status"] != READY:
                return _transition(
                    base,
                    target_check["status"],
                    unverified_observables=[
                        item
                        for item in ("native_display_membership", "model_input_membership")
                        if item in required
                    ],
                    reason_code=target_check["reason_code"],
                    reason=target_check["reason"],
                    missing_builds=target_check.get("missing_builds", []),
                    target_population=target_check["target_population"],
                    evidence_payload_sha256=target_check.get("evidence_payload_sha256", {}),
                    **(
                        {"source_document_identity": source_identity_evidence}
                        if source_identity_evidence is not None
                        else {}
                    ),
                )
        if base.get("conclusion") in {"absence", "impossibility"} and not _independent_oracle_receipt_ok(independent_oracle_receipt):
            return _transition(
                base,
                NEEDS_PROBE,
                reason_code="INDEPENDENT_ORACLE_REQUIRED",
                reason="An absence or impossibility claim requires a hash-bound second observation receipt.",
                **(
                    {"source_document_identity": source_identity_evidence}
                    if source_identity_evidence is not None
                    else {}
                ),
            )
        return _transition(
            base,
            READY,
            coverage_level="world_segments_verified",
            probe_schema=probe_output.get("oracle"),
            reason_code="INSTRUMENT_QUALIFIED",
            reason="Adapter balance plus XCLIP-aware source and fragment conservation passed.",
            **(
                {"target_population": target_check["target_population"]}
                if {"native_display_membership", "model_input_membership"} & set(required)
                else {}
            ),
            **(
                {"evidence_payload_sha256": target_check["evidence_payload_sha256"]}
                if {"native_display_membership", "model_input_membership"} & set(required)
                else {}
            ),
            **(
                {"source_document_identity": source_identity_evidence}
                if source_identity_evidence is not None
                else {}
            ),
        )

    if pipeline == "database_summary":
        return _transition(
            base,
            NEEDS_BUILD,
            unverified_observables=required,
            reason_code="SUMMARY_PROBE_VALIDATOR_MISSING",
            reason="The counts-only route has no qualified probe validator yet.",
        )

    if probe_output.get("schema") != "ariadne.dwg_graph_ir.v1":
        return _transition(
            base,
            NEEDS_BUILD,
            unverified_observables=required,
            reason_code="WRONG_PROBE_SCHEMA",
            reason="The probe did not produce the native DWG Graph IR contract.",
        )

    diagnostics = probe_output.get("diagnostics") or {}
    if diagnostics.get("errors"):
        return _transition(
            base,
            NEEDS_PROBE,
            unverified_observables=required,
            reason_code="PROBE_ERRORS",
            reason="The native probe reported extraction errors.",
        )

    entities = probe_output.get("entities")
    if not allow_empty and isinstance(entities, list) and not entities:
        return _transition(
            base,
            NEEDS_PROBE,
            unverified_observables=required,
            reason_code="VACUOUS_PROBE",
            reason="An empty extraction cannot qualify a non-empty observation path.",
        )

    unverified = [
        observable
        for observable in required
        if not _native_graph_observable_ok(observable, probe_output)
    ]
    if unverified:
        return _transition(
            base,
            NEEDS_BUILD,
            unverified_observables=unverified,
            reason_code="PROBE_COVERAGE_GAP",
            reason="The selected operation ran, but its measured output did not cover every requirement.",
        )

    if base.get("conclusion") in {"absence", "impossibility"} and not _independent_oracle_receipt_ok(independent_oracle_receipt):
        return _transition(
            base,
            NEEDS_PROBE,
            reason_code="INDEPENDENT_ORACLE_REQUIRED",
            reason="An absence or impossibility claim requires a hash-bound second observation receipt.",
        )

    return _transition(
        base,
        READY,
        coverage_level=probe_output.get("coverage_level"),
        probe_schema=probe_output.get("schema"),
        reason_code="INSTRUMENT_QUALIFIED",
        reason="Every requested observable is present in the measured native_full probe.",
    )


def _parse_requirements(values: Iterable[str]) -> list[str]:
    flattened: list[str] = []
    for value in values:
        flattened.extend(piece.strip() for piece in value.split(","))
    return _ordered_unique(flattened)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Qualify an E2 experiment observation pipeline.")
    parser.add_argument("--require", action="append", default=[], help="Observable token; repeat or comma-separate.")
    parser.add_argument("--candidate", default="auto", choices=["auto", *_PIPELINES])
    parser.add_argument(
        "--conclusion",
        default="exploratory",
        choices=["exploratory", "direction_changing", "absence", "impossibility"],
    )
    parser.add_argument("--probe-ir", type=Path, help="Actual probe output to verify.")
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--independent-oracle-receipt", type=Path)
    parser.add_argument("--target-population-oracle", type=Path)
    parser.add_argument("--model-input-ir", type=Path)
    args = parser.parse_args(argv)

    decision = qualify(
        required_observables=_parse_requirements(args.require),
        candidate=args.candidate,
        conclusion=args.conclusion,
    )
    if args.probe_ir is not None and decision["status"] == NEEDS_PROBE:
        probe = _load_json(args.probe_ir)
        decision = verify_probe(
            decision,
            probe,
            allow_empty=args.allow_empty,
            independent_oracle_receipt=(
                _load_json(args.independent_oracle_receipt)
                if args.independent_oracle_receipt is not None
                else None
            ),
            target_population_oracle=(
                _load_json(args.target_population_oracle)
                if args.target_population_oracle is not None
                else None
            ),
            model_input_output=(
                _load_json(args.model_input_ir)
                if args.model_input_ir is not None
                else None
            ),
        )
    print(json.dumps(decision, indent=2, ensure_ascii=False))
    return int(decision["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
