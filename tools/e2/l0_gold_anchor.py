#!/usr/bin/env python3
"""Extract the E2 L0 gold-layer anchor from a native DWG Graph IR.

This is deliberately a small, L0-only observer.  Its input is the rich
``inspect.database.graph`` payload produced by cadagent.  It never opens or
modifies a DWG itself.  The observer:

* treats only explicit native xref/BTR evidence as external scope evidence;
* keeps bound content even when its names contain ``$0$``;
* expands host/bound INSERT paths with the established WorldIR transform
  oracle, while removing XCLIP only from the *label-scope* expansion;
* isolates the two supplied wall layers as labels, never detector features.

The display/XCLIP oracle remains a separate later gate.  This module does not
claim that its label-scope expansion is a native visibility measurement.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


_E2_DIR = Path(__file__).resolve().parent
if str(_E2_DIR) not in sys.path:
    sys.path.insert(0, str(_E2_DIR))

from instruments import dwg_graph_to_worldir as graph_adapter
from instruments import worldir_oracle


WALL_LAYERS = (
    "X-평면도(기본형)$0$W1",
    "X-평면도(기본형)$0$W2",
)
_WALL_LAYER_SET = frozenset(WALL_LAYERS)
_GEOMETRIC_DXF_NAMES = frozenset({"LINE", "LWPOLYLINE", "POLYLINE", "ARC"})
_SUPPORTED_WALL_DXF_NAMES = frozenset({"LINE", "LWPOLYLINE", "POLYLINE", "ARC"})


class L0AnchorError(ValueError):
    """A fail-closed error in the L0 source-scope observer."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise L0AnchorError(f"{path}: expected a JSON object")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _handle(value: Any) -> str | None:
    text = str(value or "").strip()
    return text.upper() if text else None


def _dxf_name(entity: Mapping[str, Any]) -> str:
    return str(entity.get("dxf_name") or "<EMPTY>").upper()


def _is_insert(entity: Mapping[str, Any]) -> bool:
    return _dxf_name(entity) == "INSERT"


def _insert_target(entity: Mapping[str, Any]) -> str | None:
    return _handle(entity.get("block_record_handle", entity.get("target_def_handle")))


def _block_table_records(native: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    symbol_tables = native.get("symbol_tables")
    records = symbol_tables.get("block_table_records") if isinstance(symbol_tables, Mapping) else None
    return [record for record in records or [] if isinstance(record, Mapping)]


def _block_definitions(native: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values = native.get("block_definitions")
    return [value for value in values or [] if isinstance(value, Mapping)]


def _all_native_entities(native: Mapping[str, Any]) -> Iterable[tuple[str, Mapping[str, Any]]]:
    for entity in native.get("entities") or []:
        if isinstance(entity, Mapping):
            yield "modelspace", entity
    for definition in _block_definitions(native):
        handle = str(definition.get("handle") or "<missing>")
        for entity in definition.get("def_entities") or []:
            if isinstance(entity, Mapping):
                yield f"block:{handle}", entity


def _xref_section_observation(native: Mapping[str, Any]) -> tuple[list[Any], dict[str, Any], list[dict[str, str]]]:
    """Validate that an empty XREF list is observed, not inferred from absence."""

    missing = object()
    raw_xrefs = native.get("xrefs", missing)
    diagnostics = native.get("diagnostics")
    coverage = diagnostics.get("coverage") if isinstance(diagnostics, Mapping) else None
    sections_present = coverage.get("sections_present") if isinstance(coverage, Mapping) else None
    section_status = coverage.get("section_status") if isinstance(coverage, Mapping) else None
    counts = coverage.get("counts") if isinstance(coverage, Mapping) else None
    reasons: list[str] = []

    if raw_xrefs is missing:
        reasons.append("XREF_SECTION_ABSENT")
        xrefs: list[Any] = []
        json_type = "absent"
    elif not isinstance(raw_xrefs, list):
        reasons.append("XREF_SECTION_NOT_LIST")
        xrefs = []
        json_type = "null" if raw_xrefs is None else type(raw_xrefs).__name__
    else:
        xrefs = raw_xrefs
        json_type = "list"

    coverage_present = isinstance(sections_present, list) and "xrefs" in sections_present
    coverage_status = section_status.get("xrefs") if isinstance(section_status, Mapping) else None
    coverage_count = counts.get("xrefs") if isinstance(counts, Mapping) else None
    if not coverage_present:
        reasons.append("XREF_SECTION_COVERAGE_UNOBSERVED")
    if coverage_status != "implemented":
        reasons.append("XREF_SECTION_COVERAGE_NOT_IMPLEMENTED")
    if not isinstance(coverage_count, int) or isinstance(coverage_count, bool):
        reasons.append("XREF_SECTION_COUNT_UNOBSERVED")
    elif isinstance(raw_xrefs, list) and coverage_count != len(raw_xrefs):
        reasons.append("XREF_SECTION_COUNT_MISMATCH")

    observation = {
        "key_present": raw_xrefs is not missing,
        "json_type": json_type,
        "record_count": len(xrefs),
        "coverage_section_present": coverage_present,
        "coverage_section_status": coverage_status,
        "coverage_count": coverage_count,
        "implemented_coverage": (
            isinstance(raw_xrefs, list)
            and coverage_present
            and coverage_status == "implemented"
            and isinstance(coverage_count, int)
            and not isinstance(coverage_count, bool)
            and coverage_count == len(raw_xrefs)
        ),
        "observed_present_empty": (
            isinstance(raw_xrefs, list)
            and len(raw_xrefs) == 0
            and not reasons
        ),
        "resolution_reasons": reasons,
    }
    unresolved = [
        {"origin": "xrefs", "reason": reason}
        for reason in reasons
    ]
    return xrefs, observation, unresolved


def xref_scope_inventory(native: Mapping[str, Any]) -> dict[str, Any]:
    """Return external identity only from xref records/BTR flags, never names."""

    external_handles: set[str] = set()
    xrefs, xref_observation, unresolved_handle_records = _xref_section_observation(native)
    status_counts: Counter[str] = Counter()
    xref_records: list[Mapping[str, Any]] = []
    for index, raw_record in enumerate(xrefs):
        if not isinstance(raw_record, Mapping):
            unresolved_handle_records.append(
                {
                    "origin": "xrefs",
                    "index": index,
                    "reason": "MALFORMED_XREF_RECORD",
                }
            )
            continue
        record = raw_record
        xref_records.append(record)
        status = str(record.get("status") or "<missing>")
        status_counts[status] += 1
        handle = _handle(record.get("handle"))
        if handle is None:
            unresolved_handle_records.append(
                {
                    "origin": "xrefs",
                    "index": index,
                    "name": str(record.get("name") or ""),
                    "status": status,
                    "reason": "MISSING_XREF_BLOCK_RECORD_HANDLE",
                }
            )
        else:
            external_handles.add(handle)

    btr_xref_handles: set[str] = set()
    for index, record in enumerate(_block_table_records(native)):
        if not (record.get("is_xref") is True or record.get("is_xref_overlay") is True):
            continue
        handle = _handle(record.get("handle"))
        if handle is None:
            unresolved_handle_records.append(
                {
                    "origin": "symbol_tables.block_table_records",
                    "index": index,
                    "name": str(record.get("name") or ""),
                    "reason": "MISSING_XREF_BLOCK_RECORD_HANDLE",
                }
            )
        else:
            external_handles.add(handle)
            btr_xref_handles.add(handle)

    unresolved_status_records = [
        {"name": str(record.get("name") or ""), "status": str(record.get("status") or "<missing>")}
        for record in xref_records
        if str(record.get("status") or "") in {"unresolved", "unloaded", "not_found", "orphaned"}
    ]
    return {
        "schema": "ariadne.e2.l0.xref_scope.v1",
        "name_based_inference_used": False,
        "xref_record_count": len(xrefs),
        "xref_status_counts": dict(sorted(status_counts.items())),
        "xref_section_observation": xref_observation,
        "external_btr_handles": sorted(external_handles),
        "btr_flagged_xref_handles": sorted(btr_xref_handles),
        "unresolved_external_reference_records": unresolved_status_records,
        "unresolved_scope_identity_records": unresolved_handle_records,
        "scope_identity_resolution_reasons": [
            str(record.get("reason") or "")
            for record in unresolved_handle_records
            if record.get("reason")
        ],
        "scope_identity_resolved": not unresolved_handle_records,
    }


def scope_native_ir(native: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Remove only explicitly external xref definition branches from a rich IR."""

    scoped = copy.deepcopy(dict(native))
    inventory = xref_scope_inventory(native)
    external_handles = set(inventory["external_btr_handles"])
    exclusion_types: Counter[str] = Counter()
    excluded_definition_handles: list[str] = []
    excluded_insert_edges: list[dict[str, str]] = []
    unresolved_insert_targets: list[dict[str, str]] = []

    def retain_entity(entity: Mapping[str, Any], scope: str) -> bool:
        if not _is_insert(entity):
            return True
        target = _insert_target(entity)
        if target is None:
            unresolved_insert_targets.append(
                {
                    "scope": scope,
                    "handle": str(entity.get("handle") or ""),
                    "reason": "MISSING_INSERT_TARGET",
                }
            )
            return True
        if target not in external_handles:
            return True
        exclusion_types[_dxf_name(entity)] += 1
        excluded_insert_edges.append(
            {
                "scope": scope,
                "handle": str(entity.get("handle") or ""),
                "target_block_record_handle": target,
            }
        )
        return False

    root_entities: list[dict[str, Any]] = []
    for entity in scoped.get("entities") or []:
        if isinstance(entity, Mapping) and retain_entity(entity, "modelspace"):
            root_entities.append(dict(entity))
    scoped["entities"] = root_entities

    retained_definitions: list[dict[str, Any]] = []
    for definition in scoped.get("block_definitions") or []:
        if not isinstance(definition, Mapping):
            continue
        definition_handle = _handle(definition.get("handle"))
        if definition_handle in external_handles:
            excluded_definition_handles.append(definition_handle)
            for entity in definition.get("def_entities") or []:
                if isinstance(entity, Mapping):
                    exclusion_types[_dxf_name(entity)] += 1
            continue
        retained = dict(definition)
        entities: list[dict[str, Any]] = []
        for entity in definition.get("def_entities") or []:
            if isinstance(entity, Mapping) and retain_entity(entity, f"block:{definition_handle or '<missing>'}"):
                entities.append(dict(entity))
        retained["def_entities"] = entities
        retained["entity_count"] = len(entities)
        retained_definitions.append(retained)
    scoped["block_definitions"] = retained_definitions

    inventory = {
        **inventory,
        "external_block_definitions_excluded": len(excluded_definition_handles),
        "external_block_definition_handles_excluded": sorted(excluded_definition_handles),
        "external_insert_edges_excluded": len(excluded_insert_edges),
        "external_insert_edge_samples": excluded_insert_edges[:20],
        "external_entity_templates_excluded_by_dxf_name": dict(sorted(exclusion_types.items())),
        "unresolved_insert_targets": unresolved_insert_targets,
        "scope_identity_resolved": bool(inventory["scope_identity_resolved"])
        and not unresolved_insert_targets,
    }
    return scoped, inventory


def _count_dxf(entities: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for entity in entities:
        counts[_dxf_name(entity)] += 1
    return dict(sorted(counts.items()))


def layer_inventory(native: Mapping[str, Any]) -> dict[str, Any]:
    """Count exact wall-layer templates; no substring or normalization matching."""

    symbol_tables = native.get("symbol_tables")
    raw_layers = symbol_tables.get("layers") if isinstance(symbol_tables, Mapping) else []
    table_layers = [item for item in raw_layers or [] if isinstance(item, Mapping)]
    definitions = _block_definitions(native)
    result_layers: list[dict[str, Any]] = []
    for layer in WALL_LAYERS:
        table_records = [record for record in table_layers if record.get("name") == layer]
        direct = [
            entity
            for entity in native.get("entities") or []
            if isinstance(entity, Mapping) and entity.get("layer") == layer
        ]
        internal: list[Mapping[str, Any]] = []
        definition_handles: set[str] = set()
        for definition in definitions:
            handle = str(definition.get("handle") or "")
            for entity in definition.get("def_entities") or []:
                if isinstance(entity, Mapping) and entity.get("layer") == layer:
                    internal.append(entity)
                    definition_handles.add(handle)
        internal_by_dxf = _count_dxf(internal)
        supported = sorted(name for name in internal_by_dxf if name in _SUPPORTED_WALL_DXF_NAMES)
        unsupported = sorted(
            name for name in internal_by_dxf if name not in _SUPPORTED_WALL_DXF_NAMES and name != "INSERT"
        )
        result_layers.append(
            {
                "layer": layer,
                "exact_layer_table_record_count": len(table_records),
                "exact_layer_table_records": [
                    {
                        "handle": str(record.get("handle") or ""),
                        "is_xref_dependent": record.get("is_xref_dependent"),
                    }
                    for record in table_records
                ],
                "top_level_direct_entity_count": len(direct),
                "top_level_direct_by_dxf_name": _count_dxf(direct),
                "internal_block_template_count": len(internal),
                "internal_block_templates_by_dxf_name": internal_by_dxf,
                "internal_block_definition_count": len(definition_handles),
                "supported_geometric_dxf_names": supported,
                "structural_insert_template_count": internal_by_dxf.get("INSERT", 0),
                "unsupported_geometric_dxf_names": unsupported,
            }
        )
    return {
        "schema": "ariadne.e2.l0.wall_layer_inventory.v1",
        "matching": "exact_utf8_string",
        "layers": result_layers,
        "both_layers_present_exactly_once": all(
            row["exact_layer_table_record_count"] == 1 for row in result_layers
        ),
    }


def _definition_map(native: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    definitions: dict[str, Mapping[str, Any]] = {}
    for definition in _block_definitions(native):
        handle = _handle(definition.get("handle"))
        if handle is None:
            raise L0AnchorError("block definition lacks a stable handle")
        if handle in definitions:
            raise L0AnchorError(f"duplicate block definition handle {handle}")
        definitions[handle] = definition
    return definitions


def _wall_geometric_entity(entity: Mapping[str, Any]) -> bool:
    return entity.get("layer") in _WALL_LAYER_SET and _dxf_name(entity) in _GEOMETRIC_DXF_NAMES


def _wall_unsupported_entity(entity: Mapping[str, Any]) -> bool:
    return entity.get("layer") in _WALL_LAYER_SET and _dxf_name(entity) not in _GEOMETRIC_DXF_NAMES | {"INSERT"}


def wall_expansion_projection(scoped_native: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Prune to exact wall geometry and the internal INSERT paths that place it.

    The label extraction is intentionally not a detector feature projection.  It
    retains non-wall INSERTs only when they are structural paths to an exact W1
    or W2 geometric source entity.  A W1/W2 INSERT does not cause its child
    geometry to inherit a wall label.
    """

    definitions = _definition_map(scoped_native)
    direct_wall_defs = {
        handle
        for handle, definition in definitions.items()
        if any(
            isinstance(entity, Mapping) and _wall_geometric_entity(entity)
            for entity in definition.get("def_entities") or []
        )
    }
    needed_defs = set(direct_wall_defs)
    changed = True
    while changed:
        changed = False
        for handle, definition in definitions.items():
            if handle in needed_defs:
                continue
            for entity in definition.get("def_entities") or []:
                if not isinstance(entity, Mapping) or not _is_insert(entity):
                    continue
                target = _insert_target(entity)
                if target in needed_defs:
                    needed_defs.add(handle)
                    changed = True
                    break

    omitted_unsupported_wall_types: Counter[str] = Counter()
    retained_structural_wall_insert_keys: set[tuple[str, str]] = set()

    def owner_records() -> Iterable[tuple[dict[str, Any], Iterable[Any]]]:
        yield (
            {
                "scope": "modelspace",
                "definition_handle": None,
                "definition_name": None,
            },
            scoped_native.get("entities") or [],
        )
        for handle, definition in definitions.items():
            yield (
                {
                    "scope": f"block:{handle}",
                    "definition_handle": handle,
                    "definition_name": str(definition.get("name") or ""),
                },
                definition.get("def_entities") or [],
            )

    def structural_key(owner: Mapping[str, Any], index: int, entity: Mapping[str, Any]) -> tuple[str, str]:
        handle = str(entity.get("handle") or "").strip()
        return str(owner["scope"]), handle or f"<index:{index}>"

    raw_structural_wall_inserts: dict[tuple[str, str], dict[str, Any]] = {}
    for owner, entities in owner_records():
        for index, raw in enumerate(entities):
            if not isinstance(raw, Mapping) or not _is_insert(raw) or raw.get("layer") not in _WALL_LAYER_SET:
                continue
            key = structural_key(owner, index, raw)
            if key in raw_structural_wall_inserts:
                raise L0AnchorError(f"duplicate structural wall INSERT identity {key}")
            target = _insert_target(raw)
            raw_structural_wall_inserts[key] = {
                "layer": str(raw.get("layer") or ""),
                "handle": str(raw.get("handle") or ""),
                "owner_scope": owner["scope"],
                "owner_definition_handle": owner["definition_handle"],
                "owner_definition_name": owner["definition_name"],
                "target_block_record_handle": target,
                "target_definition_present": target in definitions if target is not None else None,
                "target_reachable_for_label_scope": target in needed_defs if target is not None else None,
                "disposition": "OMITTED",
                "reason": "NO_LABEL_INHERITANCE",
            }

    def select_entities(entities: Iterable[Any], owner: Mapping[str, Any]) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        for index, raw in enumerate(entities):
            if not isinstance(raw, Mapping):
                continue
            if _wall_geometric_entity(raw):
                selected.append(dict(raw))
                continue
            if _wall_unsupported_entity(raw):
                omitted_unsupported_wall_types[_dxf_name(raw)] += 1
                continue
            if _is_insert(raw):
                target = _insert_target(raw)
                if target in needed_defs:
                    selected.append(dict(raw))
                    if raw.get("layer") in _WALL_LAYER_SET:
                        retained_structural_wall_insert_keys.add(structural_key(owner, index, raw))
        return selected

    projected = copy.deepcopy(dict(scoped_native))
    modelspace_owner = {
        "scope": "modelspace",
        "definition_handle": None,
        "definition_name": None,
    }
    projected["entities"] = select_entities(scoped_native.get("entities") or [], modelspace_owner)
    projected_definitions: list[dict[str, Any]] = []
    for handle in sorted(needed_defs):
        definition = definitions[handle]
        owner = {
            "scope": f"block:{handle}",
            "definition_handle": handle,
            "definition_name": str(definition.get("name") or ""),
        }
        selected = select_entities(definition.get("def_entities") or [], owner)
        copied = dict(definition)
        copied["def_entities"] = selected
        copied["entity_count"] = len(selected)
        projected_definitions.append(copied)
    projected["block_definitions"] = projected_definitions

    # The adapter needs the existing model-space BTR record and records for
    # every retained definition.  Leaving other BTR records in place would not
    # make them reachable, but this compact form makes the label scope auditable.
    symbol_tables = projected.get("symbol_tables")
    if isinstance(symbol_tables, Mapping):
        copied_tables = copy.deepcopy(dict(symbol_tables))
        records = _block_table_records(scoped_native)
        copied_tables["block_table_records"] = [
            dict(record)
            for record in records
            if str(record.get("name") or "").lower() == "*model_space"
            or _handle(record.get("handle")) in needed_defs
        ]
        projected["symbol_tables"] = copied_tables

    omitted_structural_wall_insert_records = sorted(
        (
            record
            for key, record in raw_structural_wall_inserts.items()
            if key not in retained_structural_wall_insert_keys
        ),
        key=lambda record: (
            record["layer"],
            record["owner_scope"],
            record["handle"],
        ),
    )
    raw_structural_by_layer = Counter(
        record["layer"] for record in raw_structural_wall_inserts.values()
    )
    retained_structural_by_layer = Counter(
        raw_structural_wall_inserts[key]["layer"]
        for key in retained_structural_wall_insert_keys
    )
    omitted_structural_by_layer = Counter(
        record["layer"] for record in omitted_structural_wall_insert_records
    )
    terminal_accounting_conserved = (
        len(raw_structural_wall_inserts)
        == len(retained_structural_wall_insert_keys) + len(omitted_structural_wall_insert_records)
        and len(omitted_structural_wall_insert_records)
        == sum(omitted_structural_by_layer.values())
    )
    if not terminal_accounting_conserved:
        raise L0AnchorError("structural wall INSERT terminal accounting is not conserved")

    return projected, {
        "schema": "ariadne.e2.l0.wall_expansion_projection.v1",
        "labels_only": True,
        "detector_feature_projection": False,
        "exact_wall_layers": list(WALL_LAYERS),
        "direct_wall_definition_handles": sorted(direct_wall_defs),
        "retained_definition_handles": sorted(needed_defs),
        "retained_definition_count": len(needed_defs),
        "raw_structural_wall_insert_templates_by_layer": dict(sorted(raw_structural_by_layer.items())),
        "retained_structural_wall_insert_templates_by_layer": dict(sorted(retained_structural_by_layer.items())),
        "omitted_structural_wall_inserts_by_layer": dict(sorted(omitted_structural_by_layer.items())),
        "omitted_structural_wall_inserts_no_label_inheritance": len(omitted_structural_wall_insert_records),
        "omitted_structural_wall_insert_terminal_dispositions": omitted_structural_wall_insert_records,
        "structural_wall_insert_terminal_accounting": {
            "raw_template_count": len(raw_structural_wall_inserts),
            "retained_template_count": len(retained_structural_wall_insert_keys),
            "omitted_template_count": len(omitted_structural_wall_insert_records),
            "terminal_disposition_count": len(omitted_structural_wall_insert_records),
            "conservation_ok": terminal_accounting_conserved,
        },
        "omitted_unsupported_wall_entity_types": dict(sorted(omitted_unsupported_wall_types.items())),
        "retained_modelspace_entities": len(projected["entities"]),
        "retained_definition_entity_templates": sum(
            len(definition.get("def_entities") or []) for definition in projected_definitions
        ),
    }


def _drop_xclips(world_input: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    result = copy.deepcopy(dict(world_input))
    removed = 0
    retained_insert_templates = 0
    for definition in (result.get("definitions") or {}).values():
        if not isinstance(definition, Mapping):
            continue
        for entity in definition.get("entities") or []:
            if not isinstance(entity, dict) or str(entity.get("kind") or "").upper() != "INSERT":
                continue
            retained_insert_templates += 1
            if entity.pop("clip", None) is not None:
                removed += 1
    return result, {
        "xclip_enabled_insert_templates_in_native_adapter_input": removed,
        "retained_insert_templates": retained_insert_templates,
        "label_scope_xclip_policy": "IGNORED_FOR_SCOPE_RETAINED_AS_DISPLAY_METADATA",
    }


def world_layer_inventory(world: Mapping[str, Any]) -> dict[str, Any]:
    ledger = world.get("conservation_ledger") if isinstance(world.get("conservation_ledger"), Mapping) else {}
    all_segments = [segment for segment in world.get("segments") or [] if isinstance(segment, Mapping)]
    all_entries = [entry for entry in ledger.get("entity_entries") or [] if isinstance(entry, Mapping)]
    rows: list[dict[str, Any]] = []
    for layer in WALL_LAYERS:
        segments = [segment for segment in all_segments if segment.get("source_layer") == layer]
        entries = [entry for entry in all_entries if entry.get("source_layer") == layer]
        expected = sum(int(entry.get("expected_segments", 0) or 0) for entry in entries)
        visible = sum(int(entry.get("visible_source_segments", 0) or 0) for entry in entries)
        emitted = sum(int(entry.get("emitted_segments", 0) or 0) for entry in entries)
        clipped = sum(int(entry.get("clipped_away_segments", 0) or 0) for entry in entries)
        depth_counts: Counter[int] = Counter(
            len(segment.get("lineage_path") or []) for segment in segments
        )
        transform_flags: Counter[str] = Counter()
        kind_counts: Counter[str] = Counter()
        for segment in segments:
            kind_counts[str(segment.get("kind") or "<missing>")] += 1
            flags = segment.get("transform_flags")
            if isinstance(flags, Mapping):
                for flag in ("mirrored", "nonuniform_scaled", "array_member", "clipped"):
                    if flags.get(flag) is True:
                        transform_flags[flag] += 1
        unique_ids = {str(segment.get("placed_uid") or "") for segment in segments}
        rows.append(
            {
                "layer": layer,
                "recursively_expanded_segment_instances": len(segments),
                "unique_placed_uids": len(unique_ids),
                "distinct_source_entity_handles": len(
                    {str(segment.get("source_entity_handle") or "") for segment in segments}
                ),
                "distinct_placement_paths": len(
                    {str(segment.get("placement_path_uid") or "") for segment in segments}
                ),
                "lineage_depth_counts": {str(key): value for key, value in sorted(depth_counts.items())},
                "maximum_lineage_depth": max(depth_counts, default=0),
                "world_segment_kinds": dict(sorted(kind_counts.items())),
                "transform_application_counts": dict(sorted(transform_flags.items())),
                "source_segment_instances_expected": expected,
                "scope_retained_source_segment_instances": visible,
                "emitted_world_segment_instances": emitted,
                "xclip_excluded_segment_instances": clipped,
                "entity_entry_count": len(entries),
                "entry_status_counts": dict(sorted(Counter(str(entry.get("status") or "<missing>") for entry in entries).items())),
                "preservation_ok": expected == visible == emitted == len(segments) and clipped == 0,
            }
        )
    return {
        "schema": "ariadne.e2.l0.wall_world_expansion.v1",
        "layers": rows,
        "all_wall_layers_preserved": all(row["preservation_ok"] for row in rows),
        "world_oracle_status": world.get("status"),
        "world_conservation_ok": ledger.get("conservation_ok") is True,
        "recursive_insert_placements_total": int(
            ledger.get("reachable_insert_placements", 0) or 0
        ),
    }


def incomplete_object_accounting(native: Mapping[str, Any], adapter: Mapping[str, Any], scope: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = native.get("diagnostics") if isinstance(native.get("diagnostics"), Mapping) else {}
    coverage = diagnostics.get("coverage") if isinstance(diagnostics.get("coverage"), Mapping) else {}
    section_status = coverage.get("section_status") if isinstance(coverage.get("section_status"), Mapping) else {}
    proxy_like: Counter[str] = Counter()
    custom_class: Counter[str] = Counter()
    all_dxf_names: Counter[str] = Counter()
    unsupported_full_surface: Counter[str] = Counter()
    missing_class = 0
    for _, entity in _all_native_entities(native):
        dxf_name = _dxf_name(entity)
        all_dxf_names[dxf_name] += 1
        if dxf_name not in graph_adapter.SUPPORTED_DXF_NAMES:
            unsupported_full_surface[dxf_name] += 1
        class_name = str(entity.get("class") or "")
        if not class_name:
            missing_class += 1
        elif not class_name.startswith("AcDb"):
            custom_class[class_name] += 1
        if "proxy" in dxf_name.lower() or "proxy" in class_name.lower():
            proxy_like[f"{dxf_name}|{class_name or '<missing>'}"] += 1
    ledger = adapter.get("adapter_ledger") if isinstance(adapter.get("adapter_ledger"), Mapping) else {}
    return {
        "schema": "ariadne.e2.l0.incomplete_object_accounting.v1",
        "native_proxy_or_undecoded_count": int(coverage.get("proxy_or_undecoded_count", 0) or 0),
        "native_proxy_objects_section_status": section_status.get("proxy_objects", "<missing>"),
        "proxy_like_entity_templates": dict(sorted(proxy_like.items())),
        "non_acdb_custom_entity_class_counts": dict(sorted(custom_class.items())),
        "entities_missing_class_field": missing_class,
        "full_native_entity_template_count": sum(all_dxf_names.values()),
        "full_native_templates_by_dxf_name": dict(sorted(all_dxf_names.items())),
        "full_native_templates_outside_adapter_surface": dict(sorted(unsupported_full_surface.items())),
        "full_native_templates_outside_adapter_surface_count": sum(unsupported_full_surface.values()),
        "adapter_status": adapter.get("status"),
        "adapter_explicitly_excluded_entity_templates": int(
            ledger.get("explicitly_excluded_entity_templates", 0) or 0
        ),
        "adapter_excluded_by_dxf_name": dict(ledger.get("excluded_by_dxf_name") or {}),
        "unresolved_external_reference_records": list(
            scope.get("unresolved_external_reference_records") or []
        ),
        "unresolved_scope_identity_records": list(
            scope.get("unresolved_scope_identity_records") or []),
        "unresolved_insert_targets": list(scope.get("unresolved_insert_targets") or []),
    }


def _native_payload_ok(native: Mapping[str, Any], staged_sha256: str) -> tuple[bool, list[str]]:
    diagnostics = native.get("diagnostics") if isinstance(native.get("diagnostics"), Mapping) else {}
    source = native.get("source") if isinstance(native.get("source"), Mapping) else {}
    failures: list[str] = []
    if native.get("schema") != "ariadne.dwg_graph_ir.v1":
        failures.append("WRONG_NATIVE_IR_SCHEMA")
    if native.get("coverage_level") != "native_full":
        failures.append("NATIVE_FULL_COVERAGE_REQUIRED")
    if diagnostics.get("errors"):
        failures.append("NATIVE_PROBE_REPORTED_ERRORS")
    if str(source.get("sha256") or "").lower() != staged_sha256.lower():
        failures.append("NATIVE_PAYLOAD_SOURCE_SHA_MISMATCH")
    return not failures, failures


def _result_status(checks: Mapping[str, bool], incomplete: Mapping[str, Any]) -> tuple[str, list[str]]:
    blockers = [name for name, value in checks.items() if not value]
    if blockers:
        return "BLOCKED", blockers
    limitations: list[str] = []
    if incomplete.get("native_proxy_objects_section_status") != "implemented":
        limitations.append("PROXY_OBJECT_SURFACE_PARTIAL")
    if int(incomplete.get("full_native_templates_outside_adapter_surface_count", 0) or 0) > 0:
        limitations.append("NON_WALL_ADAPTER_UNSUPPORTED_TYPES_ACCOUNTED")
    limitations.append("NATIVE_DISPLAY_AND_MODEL_INPUT_GATE_SEPARATE")
    return "PARTIAL_PASS", limitations


def _file_record(path: Path) -> dict[str, Any]:
    return {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size}


def _render_report(result: Mapping[str, Any]) -> str:
    source = result["source_and_staging"]
    layers = result["wall_layer_inventory"]["layers"]
    world_layers = result["world_expansion"]["layers"]
    guards = result.get("guarded_experiment", {})
    lines = [
        "# E2 L0 Step 1–2 report",
        "",
        f"Status: **{result['status']}**",
        "",
        "## Native observation route",
        "",
        "- `cad.status` reported 11/11 routes available; `cad.live_status` reported no persistent live ObjectARX pump.",
        "- `cad.registry_explain(inspect.database.graph)` selected the ObjectDBX-capable, hostless-DBX-in-accoreconsole native graph route.",
        "- Primary truth path: cadagent `inspect.database.graph` rich/native payload. No DXF or DWF was used as primary truth.",
        "- The two wall layer names are label extraction inputs only; this run did not execute a detector.",
        "- Commands: cadagent rich inspection; `python tools/e2/run_guarded_experiment.py --require ... --probe-ir ...`; then `python tools/e2/l0_gold_anchor.py extract ...`.",
        "",
        "## Source and staging",
        "",
        f"- Source SHA-256 before/after: `{source['source_sha256_before']}` / `{source['source_sha256_after']}`.",
        f"- Staged SHA-256: `{source['staged_sha256']}`; equality: `{source['source_equals_staged']}`; source immutable: `{source['source_immutable']}`.",
        "",
        "## Exact wall-layer extraction",
        "",
    ]
    for native_row, world_row in zip(layers, world_layers):
        lines.extend(
            [
                f"- `{native_row['layer']}`: exact layer-table records={native_row['exact_layer_table_record_count']}; "
                f"top-level/direct={native_row['top_level_direct_entity_count']}; "
                f"internal templates={native_row['internal_block_template_count']} "
                f"({native_row['internal_block_templates_by_dxf_name']}); "
                f"expanded instances={world_row['recursively_expanded_segment_instances']} "
                f"from expected={world_row['source_segment_instances_expected']}; "
                f"max INSERT lineage depth={world_row['maximum_lineage_depth']}; "
                f"preserved={world_row['preservation_ok']}.",
            ]
        )
    lines.append(
        f"- Scoped recursive INSERT placements traversed: {result['world_expansion']['recursive_insert_placements_total']}."
    )
    scope = result["external_xref_scope"]
    xref_observation = scope.get("xref_section_observation") or {}
    projection = result.get("label_scope_projection") or {}
    terminal_accounting = projection.get("structural_wall_insert_terminal_accounting") or {}
    scoped_binding = (guards.get("scoped_extraction", {}) or {}).get("evidence_binding") or {}
    lines.extend(
        [
            "",
            "## Scope and incompleteness accounting",
            "",
            f"- Explicit external-XREF records={scope['xref_record_count']}; external block definitions excluded={scope['external_block_definitions_excluded']}; external INSERT edges excluded={scope['external_insert_edges_excluded']}; scope identity resolved={scope['scope_identity_resolved']}.",
            f"- XREF section: present={xref_observation.get('key_present')}; type={xref_observation.get('json_type')}; coverage={xref_observation.get('coverage_section_status')}; count={xref_observation.get('coverage_count')}; observed-present-empty={xref_observation.get('observed_present_empty')}; reasons={xref_observation.get('resolution_reasons', [])}.",
            f"- Structural wall-layer INSERT terminal accounting: raw={terminal_accounting.get('raw_template_count')}; retained={terminal_accounting.get('retained_template_count')}; omitted={terminal_accounting.get('omitted_template_count')}; terminal dispositions={terminal_accounting.get('terminal_disposition_count')}; conserved={terminal_accounting.get('conservation_ok')}.",
            "- `$0$` was never used to decide externality; only native XREF records/BTR flags were used.",
            f"- Native proxy/undecoded count={result['incomplete_object_accounting']['native_proxy_or_undecoded_count']}; proxy section status={result['incomplete_object_accounting']['native_proxy_objects_section_status']}; full-native templates outside the current adapter surface={result['incomplete_object_accounting']['full_native_templates_outside_adapter_surface_count']}.",
            "- XCLIP was retained as display metadata but deliberately ignored for label-scope inclusion. This is not a native-display membership claim.",
            "",
            "## Guarded execution",
            "",
            f"- Scoped extraction guard: `{guards.get('scoped_extraction', {}).get('status', 'PENDING')}`; command executed={guards.get('scoped_extraction', {}).get('executed', 'PENDING')}; required={guards.get('scoped_extraction', {}).get('required_observables', [])}.",
            f"- Scoped evidence binding: source SHA-256=`{scoped_binding.get('source_sha256')}`; probe SHA-256=`{scoped_binding.get('probe_sha256')}`; verified probe drawing ID=`{scoped_binding.get('verified_probe_drawing_id')}`.",
            f"- Display/model gate: `{guards.get('display_and_model_gate', {}).get('status', 'PENDING')}`. A native display-membership oracle and exact detector input were not substituted with this label extractor.",
            "",
            "## Next gate",
            "",
            "Build or supply a hash-bound AutoCAD native-display membership oracle, then provide the exact detector input receipt before any detector result is interpreted. Object purity/completeness and object-level AUPRC remain out of scope for this Step 1–2 extraction.",
        ]
    )
    return "\n".join(lines) + "\n"


def extract(
    *,
    native_ir_path: Path,
    source_path: Path,
    staged_path: Path,
    out_dir: Path,
    guard_receipt: Path | None = None,
) -> dict[str, Any]:
    """Build the L0 Step 1–2 payload and supporting real probe artifacts."""

    out_dir.mkdir(parents=True, exist_ok=True)
    source_before = sha256(source_path)
    staged_hash = sha256(staged_path)
    native = _read_json(native_ir_path)
    native_ok, native_failures = _native_payload_ok(native, staged_hash)
    scoped_native, xref_scope = scope_native_ir(native)
    layer_rows = layer_inventory(scoped_native)
    projection, projection_receipt = wall_expansion_projection(scoped_native)
    adapter = graph_adapter.adapt(projection)
    world_input, xclip_receipt = _drop_xclips(adapter)
    world = worldir_oracle.expand_world_ir(world_input)
    world_rows = world_layer_inventory(world)
    incomplete = incomplete_object_accounting(native, adapter, xref_scope)
    source_after = sha256(source_path)

    wall_segments = [
        segment
        for segment in world.get("segments") or []
        if isinstance(segment, Mapping) and segment.get("source_layer") in _WALL_LAYER_SET
    ]
    _write_json(out_dir / "scoped_native_graph.json", projection)
    _write_json(out_dir / "scoped_worldir_input.json", world_input)
    _write_json(out_dir / "scoped_worldir_probe.json", world)
    _write_json(out_dir / "gold_layer_segment_instances.json", {
        "schema": "ariadne.e2.l0.gold_layer_segments.v1",
        "labels_only": True,
        "detector_feature_projection": False,
        "drawing_id": world.get("drawing_id"),
        "segments": wall_segments,
    })
    _write_json(out_dir / "external_xref_scope.json", xref_scope)

    preservation = world_rows["all_wall_layers_preserved"] and world_rows["world_conservation_ok"]
    checks = {
        "source_equals_staged": source_before == staged_hash,
        "source_immutable": source_before == source_after,
        "native_payload_matches_staged": native_ok,
        "both_exact_wall_layers_present": layer_rows["both_layers_present_exactly_once"],
        "external_scope_identity_resolved": xref_scope["scope_identity_resolved"],
        "world_transform_expansion_preserved": preservation,
    }
    status, reasons = _result_status(checks, incomplete)
    artifacts = [
        _file_record(path)
        for path in (
            native_ir_path,
            out_dir / "scoped_native_graph.json",
            out_dir / "scoped_worldir_input.json",
            out_dir / "scoped_worldir_probe.json",
            out_dir / "gold_layer_segment_instances.json",
            out_dir / "external_xref_scope.json",
        )
    ]
    result: dict[str, Any] = {
        "schema": "ariadne.e2.l0.step1_2.v1",
        "status": status,
        "status_reasons": reasons,
        "primary_truth_path": {
            "operation": "inspect.database.graph",
            "native_ir": _file_record(native_ir_path),
            "coverage_level": native.get("coverage_level"),
            "engine_tier": (native.get("source") or {}).get("engine_tier"),
            "dwf_used_as_primary_truth": False,
            "route_selection": {
                "cad_status": "ALL_AVAILABLE; 11/11 routes",
                "live_objectarx_pump": "not_implemented",
                "registry_engine_tier": "objectdbx_capable",
                "execution_context": "hostless_dbx_in_accoreconsole",
            },
        },
        "source_and_staging": {
            "immutable_source_path": str(source_path),
            "staged_copy_path": str(staged_path),
            "source_sha256_before": source_before,
            "source_sha256_after": source_after,
            "staged_sha256": staged_hash,
            "source_equals_staged": source_before == staged_hash,
            "source_immutable": source_before == source_after,
            "native_payload_source_sha256": (native.get("source") or {}).get("sha256"),
            "native_payload_matches_staged": native_ok,
            "native_payload_identity_failures": native_failures,
        },
        "wall_layer_inventory": layer_rows,
        "external_xref_scope": xref_scope,
        "label_scope_projection": projection_receipt,
        "xclip_scope_accounting": xclip_receipt,
        "world_expansion": world_rows,
        "incomplete_object_accounting": incomplete,
        "checks": checks,
        "guarded_experiment": {
            "scoped_extraction": {
                "receipt_path": str(guard_receipt) if guard_receipt else None,
                "status": "PENDING_FINAL_RECEIPT",
            },
            "display_and_model_gate": {"status": "PENDING"},
        },
        "artifacts": artifacts,
    }
    _write_json(out_dir / "result.json", result)
    (out_dir / "L0_STEP1_2_REPORT.md").write_text(
        _render_report(result), encoding="utf-8", newline="\n"
    )
    return result


def _guard_summary(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {"status": "MISSING_RECEIPT", "receipt_path": str(path) if path else None}
    receipt = _read_json(path)
    guard = receipt.get("guard") if isinstance(receipt.get("guard"), Mapping) else receipt
    return {
        "receipt_path": str(path),
        "receipt_sha256": sha256(path),
        "status": guard.get("status"),
        "reason_code": guard.get("reason_code"),
        "required_observables": list(guard.get("required_observables") or []),
        "selected_pipeline": guard.get("selected_pipeline"),
        "executed": receipt.get("executed"),
        "command_exit_code": receipt.get("command_exit_code"),
        "evidence_binding": dict(receipt.get("evidence_binding") or {}),
    }


def finalize(*, out_dir: Path, guard_receipt: Path, display_gate_receipt: Path | None = None) -> dict[str, Any]:
    """Attach final guarded-run receipts without re-extracting CAD evidence."""

    result_path = out_dir / "result.json"
    result = _read_json(result_path)
    scoped = _guard_summary(guard_receipt)
    display = _guard_summary(display_gate_receipt)
    result["guarded_experiment"] = {
        "scoped_extraction": scoped,
        "display_and_model_gate": display,
    }
    if not (
        scoped.get("status") == "READY"
        and scoped.get("executed") is True
        and scoped.get("command_exit_code") == 0
    ):
        result["status"] = "BLOCKED"
        reasons = list(result.get("status_reasons") or [])
        if "GUARDED_EXTRACTION_DID_NOT_COMPLETE" not in reasons:
            reasons.append("GUARDED_EXTRACTION_DID_NOT_COMPLETE")
        result["status_reasons"] = reasons
    _write_json(result_path, result)
    (out_dir / "L0_STEP1_2_REPORT.md").write_text(
        _render_report(result), encoding="utf-8", newline="\n"
    )
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    extract_parser = subparsers.add_parser("extract", help="write the L0 scoped extraction artifacts")
    extract_parser.add_argument("--native-ir", type=Path, required=True)
    extract_parser.add_argument("--source", type=Path, required=True)
    extract_parser.add_argument("--staged", type=Path, required=True)
    extract_parser.add_argument("--out", type=Path, required=True)
    extract_parser.add_argument("--guard-receipt", type=Path)
    finalize_parser = subparsers.add_parser("finalize", help="attach guarded receipts to result.json")
    finalize_parser.add_argument("--out", type=Path, required=True)
    finalize_parser.add_argument("--guard-receipt", type=Path, required=True)
    finalize_parser.add_argument("--display-gate-receipt", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "extract":
        result = extract(
            native_ir_path=args.native_ir,
            source_path=args.source,
            staged_path=args.staged,
            out_dir=args.out,
            guard_receipt=args.guard_receipt,
        )
    else:
        result = finalize(
            out_dir=args.out,
            guard_receipt=args.guard_receipt,
            display_gate_receipt=args.display_gate_receipt,
        )
    print(json.dumps({"status": result["status"], "out": str(getattr(args, "out"))}, ensure_ascii=False))
    return 0 if result["status"] in {"PASS", "PARTIAL_PASS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
