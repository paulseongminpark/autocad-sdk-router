"""Read-only verification of the CADAgent operation registry."""

from __future__ import annotations

import json
import hashlib
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from . import file_snapshot as _file_snapshot
from .operation_sources import (
    NativeAdmissionContractMismatch,
    OperationSourceParseError,
    PatchFamilyDispatchMismatch,
    _strip_cpp_comments,
    check_vocab_lockstep,
    discover_patch_family_module_names,
    parse_native_sources,
    parse_patch_vocabularies,
    patch_family_module_names,
)


REGISTRY_SCHEMA_ID = "ariadne.operations_registry.v2"
NATIVE_CATALOG_SCHEMA_ID = "ariadne.autocad_native_arx_operation_catalog.v1"
RUNNABLE_STATUSES = frozenset({"implemented", "wired"})
OPERATION_STATUSES = frozenset(
    {"implemented", "wired", "stub", "catalogued", "deprecated", "blocked"}
)


@dataclass(frozen=True)
class InternalNativeOperationPurpose:
    native_family: str
    reason: str
    dedicated_public_surface: str | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "native_family": self.native_family,
            "reason": self.reason,
            "dedicated_public_surface": self.dedicated_public_surface,
        }


INTERNAL_NATIVE_OPERATION_PURPOSES: Mapping[
    str, InternalNativeOperationPurpose
] = MappingProxyType({
    "e2.inspect.xclip_membership": InternalNativeOperationPurpose(
        native_family="experiment_oracle",
        reason="experiment_oracle",
        dedicated_public_surface="cad.inspect_display_membership",
    ),
    "extend.deep_native.firing_selftest": InternalNativeOperationPurpose(
        native_family="extend",
        reason="internal_verification_harness",
        dedicated_public_surface=None,
    ),
    "inspect.deep_native.firing_report": InternalNativeOperationPurpose(
        native_family="inspect",
        reason="internal_verification_readout",
        dedicated_public_surface=None,
    ),
    "inspect.selection.monitor.registry": InternalNativeOperationPurpose(
        native_family="live",
        reason="internal_capability_probe",
        dedicated_public_surface="inspect.runtime.capabilities",
    ),
    "live.selection.monitor.disable": InternalNativeOperationPurpose(
        native_family="live",
        reason="internal_runtime_probe",
        dedicated_public_surface="inspect.runtime.capabilities",
    ),
    "live.selection.monitor.enable": InternalNativeOperationPurpose(
        native_family="live",
        reason="internal_runtime_probe",
        dedicated_public_surface="inspect.runtime.capabilities",
    ),
})
PROPERTY_COUNT_RUNTIME_EVIDENCE_LIMITATION = (
    "inspect.probe.property_count host eligibility includes dbx and arx_adapter, "
    "but current runtime evidence covers only coreconsole and full_autocad"
)
STATIC_DECLARATION_PARITY_LIMITATION = (
    "operation registry verification compares the declared operation vocabulary "
    "only; dispatch targets, handler execution, and semantic success require "
    "independent runtime evidence"
)
STATIC_VOCABULARY_LIMITATION_CODES = (
    "dispatch_target_identity_not_proven",
    "handler_execution_not_proven",
    "source_not_compiled_or_executed",
)


@dataclass(frozen=True)
class OperationRegistryFailure:
    code: str
    source: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "source": self.source, "detail": self.detail}


@dataclass(frozen=True)
class OperationRegistryReceipt:
    verified: bool
    registry_schema: str | None
    operation_count: int
    status_histogram: Mapping[str, int]
    failures: tuple[OperationRegistryFailure, ...]
    native_catalog_count: int = 0
    v1_operation_count: int = 0
    v1_runnable_count: int = 0
    native_family_count: int = 0
    internal_native_operation_count: int = 0
    internal_native_operation_names: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    limitation_codes: tuple[str, ...] = ()
    status_vocabulary: frozenset[str] = frozenset()
    input_digests: Mapping[str, str] = field(default_factory=dict)
    input_set_sha256: str | None = None
    snapshot_consistent: bool = False
    verification_scope: str = "static_operation_vocabulary_parity"

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic, JSON-serializable receipt value."""

        return {
            "verified": self.verified,
            "registry_schema": self.registry_schema,
            "operation_count": self.operation_count,
            "status_histogram": dict(sorted(self.status_histogram.items())),
            "failures": [failure.to_dict() for failure in self.failures],
            "native_catalog_count": self.native_catalog_count,
            "v1_operation_count": self.v1_operation_count,
            "v1_runnable_count": self.v1_runnable_count,
            "native_family_count": self.native_family_count,
            "internal_native_operation_count": self.internal_native_operation_count,
            "internal_native_operation_names": list(
                self.internal_native_operation_names
            ),
            "limitations": list(self.limitations),
            "limitation_codes": list(self.limitation_codes),
            "status_vocabulary": sorted(self.status_vocabulary),
            "input_digests": dict(sorted(self.input_digests.items())),
            "input_set_sha256": self.input_set_sha256,
            "snapshot_consistent": self.snapshot_consistent,
            "verification_scope": self.verification_scope,
        }


@dataclass(frozen=True)
class _OperationInputSnapshot:
    sources: Mapping[str, bytes]
    digests: Mapping[str, str]
    aggregate_sha256: str
    captured: _file_snapshot.ImmutableFileSnapshot


_FIXED_INPUT_PATHS = (
    "config/operations.v2.json",
    "schemas/operation_registry.v2.schema.json",
    "config/autocad_native_arx_operation_catalog.json",
    "schemas/cad_job.schema.json",
    "src/Ariadne.AcadNative/AriadneNativeJob.cpp",
    "tools/patch_engine.py",
    "tools/patch_ops/__init__.py",
)
_FAMILY_INCLUDE_RE = re.compile(
    r'^\s*#\s*include\s+"(families/[A-Za-z0-9_.-]+\.inc)"\s*$',
    re.MULTILINE,
)


def _declared_family_source_paths(native_job: bytes) -> tuple[str, ...]:
    try:
        text = native_job.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise OperationSourceParseError(
            f"AriadneNativeJob.cpp is not UTF-8: {exc}"
        ) from exc
    stripped = _strip_cpp_comments(text)
    includes = tuple(match.group(1) for match in _FAMILY_INCLUDE_RE.finditer(stripped))
    if not includes or len(includes) != len(set(includes)):
        raise OperationSourceParseError(
            "native family include declarations are empty or duplicated"
        )
    return tuple(
        f"src/Ariadne.AcadNative/{relative}" for relative in includes
    )


def _capture_input_snapshot(root: Path) -> _OperationInputSnapshot:
    relative_paths = set(_FIXED_INPUT_PATHS)
    discovery = _file_snapshot.capture_files(
        root,
        (
            "src/Ariadne.AcadNative/AriadneNativeJob.cpp",
            "tools/patch_ops/__init__.py",
        ),
    )
    discovered_family_paths = _declared_family_source_paths(
        discovery.files[
            "src/Ariadne.AcadNative/AriadneNativeJob.cpp"
        ].content
    )
    relative_paths.update(discovered_family_paths)
    discovered_module_names = discover_patch_family_module_names(
        discovery.files["tools/patch_ops/__init__.py"].content
    )
    for module_name in discovered_module_names:
        relative_path = f"tools/patch_ops/{module_name}.py"
        relative_paths.add(relative_path)

    captured = _file_snapshot.capture_files(root, tuple(sorted(relative_paths)))
    sources = MappingProxyType({
        path: item.content for path, item in captured.files.items()
    })
    captured_module_names = discover_patch_family_module_names(
        sources["tools/patch_ops/__init__.py"]
    )
    if captured_module_names != discovered_module_names:
        raise _file_snapshot.SnapshotCaptureError(
            "patch module declarations changed while the authoritative input "
            "snapshot was being assembled"
        )
    captured_family_paths = _declared_family_source_paths(
        sources["src/Ariadne.AcadNative/AriadneNativeJob.cpp"]
    )
    if captured_family_paths != discovered_family_paths:
        raise _file_snapshot.SnapshotCaptureError(
            "native family include declarations changed while the authoritative "
            "input snapshot was being assembled"
        )
    digests = {
        path: hashlib.sha256(
            source if b"\0" in source else source.replace(b"\r\n", b"\n")
        ).hexdigest()
        for path, source in sources.items()
    }
    aggregate = hashlib.sha256()
    for path, digest in digests.items():
        aggregate.update(f"{path}\0{digest}\n".encode("utf-8"))
    return _OperationInputSnapshot(
        sources=sources,
        digests=MappingProxyType(digests),
        aggregate_sha256=aggregate.hexdigest(),
        captured=captured,
    )


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not permitted: {value}")


def _reject_duplicate_json_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _parse_json_bytes(source: bytes) -> object:
    return json.loads(
        source.decode("utf-8-sig", errors="strict"),
        object_pairs_hook=_reject_duplicate_json_object,
        parse_constant=_reject_json_constant,
    )


def _parse_native_snapshot(snapshot: _OperationInputSnapshot):
    family_sources = {
        path: source
        for path, source in snapshot.sources.items()
        if path.startswith("src/Ariadne.AcadNative/families/")
        and path.endswith(".inc")
    }
    return parse_native_sources(
        snapshot.sources["src/Ariadne.AcadNative/AriadneNativeJob.cpp"],
        family_sources,
    )


def _parse_patch_snapshot(snapshot: _OperationInputSnapshot):
    patch_ops_init = snapshot.sources["tools/patch_ops/__init__.py"]
    patch_family_sources = {
        module_name: snapshot.sources[f"tools/patch_ops/{module_name}.py"]
        for module_name in patch_family_module_names(patch_ops_init)
    }
    return parse_patch_vocabularies(
        snapshot.sources["tools/patch_engine.py"],
        patch_ops_init,
        patch_family_sources,
    )


def verify_operation_registry(router_home: str | Path) -> OperationRegistryReceipt:
    """Verify registry structure and declared status totals without writing files."""

    root = Path(os.path.abspath(str(router_home)))
    registry_path = root / "config" / "operations.v2.json"
    schema_path = root / "schemas" / "operation_registry.v2.schema.json"
    failures: list[OperationRegistryFailure] = []

    try:
        snapshot = _capture_input_snapshot(root)
    except (OSError, UnicodeError, OperationSourceParseError) as exc:
        return OperationRegistryReceipt(
            verified=False,
            registry_schema=None,
            operation_count=0,
            status_histogram={},
            failures=(OperationRegistryFailure(
                code="INPUT_SNAPSHOT_FAILED",
                source=str(root),
                detail=f"{type(exc).__name__}: {exc}",
            ),),
        )

    try:
        registry = _parse_json_bytes(snapshot.sources["config/operations.v2.json"])
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return OperationRegistryReceipt(
            verified=False,
            registry_schema=None,
            operation_count=0,
            status_histogram={},
            failures=(OperationRegistryFailure(
                code="REGISTRY_PARSE_FAILED",
                source=str(registry_path),
                detail=f"{type(exc).__name__}: {exc}",
            ),),
            input_digests=snapshot.digests,
            input_set_sha256=snapshot.aggregate_sha256,
            snapshot_consistent=True,
        )

    if not isinstance(registry, dict):
        return OperationRegistryReceipt(
            verified=False,
            registry_schema=None,
            operation_count=0,
            status_histogram={},
            failures=(OperationRegistryFailure(
                code="REGISTRY_NOT_OBJECT",
                source=str(registry_path),
                detail="registry root must be a JSON object",
            ),),
            input_digests=snapshot.digests,
            input_set_sha256=snapshot.aggregate_sha256,
            snapshot_consistent=True,
        )

    registry_schema = registry.get("schema")
    if registry_schema != REGISTRY_SCHEMA_ID:
        failures.append(OperationRegistryFailure(
            code="REGISTRY_SCHEMA_ID_MISMATCH",
            source=str(registry_path),
            detail=f"expected {REGISTRY_SCHEMA_ID!r}, got {registry_schema!r}",
        ))

    status_vocabulary: frozenset[str] = frozenset()
    try:
        import jsonschema

        schema = _parse_json_bytes(
            snapshot.sources["schemas/operation_registry.v2.schema.json"]
        )
        status_enum = (
            (((schema.get("$defs") or {}).get("operation") or {}).get("properties") or {})
            .get("status", {})
            .get("enum")
            if isinstance(schema, dict)
            else None
        )
        if isinstance(status_enum, list) and all(
            isinstance(status, str) for status in status_enum
        ):
            status_vocabulary = frozenset(status_enum)
        if status_vocabulary != OPERATION_STATUSES:
            failures.append(OperationRegistryFailure(
                code="REGISTRY_STATUS_VOCABULARY_MISMATCH",
                source=str(schema_path),
                detail=(f"expected={sorted(OPERATION_STATUSES)!r}; "
                        f"observed={sorted(status_vocabulary)!r}"),
            ))
        jsonschema.Draft7Validator.check_schema(schema)
        schema_errors = sorted(
            jsonschema.Draft7Validator(schema).iter_errors(registry),
            key=lambda error: tuple(error.absolute_path),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ImportError) as exc:
        failures.append(OperationRegistryFailure(
            code="REGISTRY_SCHEMA_VALIDATION_UNAVAILABLE",
            source=str(schema_path),
            detail=f"{type(exc).__name__}: {exc}",
        ))
        schema_errors = []
    except Exception as exc:  # jsonschema.SchemaError has version-specific types
        failures.append(OperationRegistryFailure(
            code="REGISTRY_SCHEMA_INVALID",
            source=str(schema_path),
            detail=f"{type(exc).__name__}: {exc}",
        ))
        schema_errors = []

    for error in schema_errors:
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        failures.append(OperationRegistryFailure(
            code="REGISTRY_SCHEMA_VIOLATION",
            source=f"{registry_path}:{location}",
            detail=error.message,
        ))

    operations = registry.get("operations")
    if not isinstance(operations, list):
        operations = []
        failures.append(OperationRegistryFailure(
            code="REGISTRY_OPERATIONS_NOT_LIST",
            source=str(registry_path),
            detail="operations must be a list",
        ))

    status_histogram = Counter(
        operation.get("status") if isinstance(operation.get("status"), str) else "<invalid>"
        for operation in operations
        if isinstance(operation, dict)
    )
    if "<invalid>" in status_histogram:
        failures.append(OperationRegistryFailure(
            code="REGISTRY_STATUS_INVALID",
            source=str(registry_path),
            detail="every operation status must be a string",
        ))
    unknown_statuses = set(status_histogram) - OPERATION_STATUSES - {"<invalid>"}
    if unknown_statuses:
        failures.append(OperationRegistryFailure(
            code="REGISTRY_STATUS_UNKNOWN",
            source=str(registry_path),
            detail=f"unknown operation statuses: {sorted(unknown_statuses)!r}",
        ))

    declared_totals = registry.get("totals")
    if not isinstance(declared_totals, dict):
        failures.append(OperationRegistryFailure(
            code="REGISTRY_TOTALS_MISSING",
            source=str(registry_path),
            detail="totals must be an object",
        ))
    else:
        if declared_totals.get("operations") != len(operations):
            failures.append(OperationRegistryFailure(
                code="REGISTRY_OPERATION_TOTAL_MISMATCH",
                source=str(registry_path),
                detail=(f"declared={declared_totals.get('operations')!r}; "
                        f"observed={len(operations)}"),
            ))
        if declared_totals.get("by_status") != dict(status_histogram):
            failures.append(OperationRegistryFailure(
                code="REGISTRY_STATUS_HISTOGRAM_MISMATCH",
                source=str(registry_path),
                detail=(f"declared={declared_totals.get('by_status')!r}; "
                        f"observed={dict(status_histogram)!r}"),
            ))

    registry_ids = [
        operation.get("id")
        for operation in operations
        if isinstance(operation, dict) and isinstance(operation.get("id"), str)
    ]
    registry_id_set = set(registry_ids)
    if len(registry_ids) != len(registry_id_set):
        failures.append(OperationRegistryFailure(
            code="REGISTRY_DUPLICATE_OPERATION_ID",
            source=str(registry_path),
            detail="operation ids must be unique",
        ))

    catalog_path = root / "config" / "autocad_native_arx_operation_catalog.json"
    catalog_ids: set[str] = set()
    native_catalog_count = 0
    try:
        catalog = _parse_json_bytes(
            snapshot.sources["config/autocad_native_arx_operation_catalog.json"]
        )
        if not isinstance(catalog, dict):
            raise ValueError("native catalog root must be a JSON object")
        if catalog.get("schema") != NATIVE_CATALOG_SCHEMA_ID:
            failures.append(OperationRegistryFailure(
                code="NATIVE_CATALOG_SCHEMA_ID_MISMATCH",
                source=str(catalog_path),
                detail=(f"expected {NATIVE_CATALOG_SCHEMA_ID!r}, "
                        f"got {catalog.get('schema')!r}"),
            ))
        catalog_operations = catalog.get("operations")
        if not isinstance(catalog_operations, list):
            raise ValueError("native catalog operations must be a list")
        native_catalog_count = len(catalog_operations)
        catalog_id_list = [
            operation.get("op_id")
            for operation in catalog_operations
            if isinstance(operation, dict) and isinstance(operation.get("op_id"), str)
        ]
        catalog_ids = set(catalog_id_list)
        if len(catalog_id_list) != native_catalog_count:
            failures.append(OperationRegistryFailure(
                code="NATIVE_CATALOG_OPERATION_ID_INVALID",
                source=str(catalog_path),
                detail="every native catalog operation must have a string op_id",
            ))
        if len(catalog_id_list) != len(catalog_ids):
            failures.append(OperationRegistryFailure(
                code="NATIVE_CATALOG_DUPLICATE_OPERATION_ID",
                source=str(catalog_path),
                detail="native catalog op_ids must be unique",
            ))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        failures.append(OperationRegistryFailure(
            code="NATIVE_CATALOG_PARSE_FAILED",
            source=str(catalog_path),
            detail=f"{type(exc).__name__}: {exc}",
        ))

    missing_catalog_ids = sorted(catalog_ids - registry_id_set)
    if missing_catalog_ids:
        failures.append(OperationRegistryFailure(
            code="NATIVE_CATALOG_NOT_CLASSIFIED",
            source=str(registry_path),
            detail=f"catalog ids absent from registry: {missing_catalog_ids!r}",
        ))

    unresolved_references: list[tuple[str | None, str]] = []
    resolvable_ids = catalog_ids | registry_id_set
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        references: set[str] = set()
        catalog_op_id = operation.get("catalog_op_id")
        if isinstance(catalog_op_id, str) and catalog_op_id:
            references.add(catalog_op_id)
        handler = operation.get("handler")
        if isinstance(handler, dict):
            composed_of = handler.get("composed_of")
            if isinstance(composed_of, list):
                references.update(
                    reference for reference in composed_of
                    if isinstance(reference, str) and reference
                )
        for reference in references:
            if reference not in resolvable_ids:
                unresolved_references.append((operation.get("id"), reference))
    if unresolved_references:
        failures.append(OperationRegistryFailure(
            code="REGISTRY_NATIVE_REFERENCE_UNRESOLVED",
            source=str(registry_path),
            detail=f"unresolved catalog/composition references: {unresolved_references!r}",
        ))

    v1_path = root / "schemas" / "cad_job.schema.json"
    v1_operations: list[str] = []
    v1_runnable_count = 0
    try:
        v1_schema = _parse_json_bytes(snapshot.sources["schemas/cad_job.schema.json"])
        if not isinstance(v1_schema, dict):
            raise ValueError("v1 CAD job schema root must be a JSON object")
        enum = (((v1_schema.get("properties") or {}).get("operation") or {}).get("enum"))
        if (
            not isinstance(enum, list)
            or not enum
            or not all(isinstance(item, str) for item in enum)
        ):
            raise ValueError("v1 operation enum must be a non-empty string list")
        v1_operations = list(enum)
        if len(v1_operations) != len(set(v1_operations)):
            failures.append(OperationRegistryFailure(
                code="V1_OPERATION_ENUM_DUPLICATE",
                source=str(v1_path),
                detail="v1 operation enum must contain unique ids",
            ))
        by_id = {
            operation.get("id"): operation
            for operation in operations
            if isinstance(operation, dict) and isinstance(operation.get("id"), str)
        }
        missing_v1 = sorted(set(v1_operations) - registry_id_set)
        if missing_v1:
            failures.append(OperationRegistryFailure(
                code="V1_EXTEND_ONLY_VIOLATION",
                source=str(registry_path),
                detail=f"v1 operation ids absent from registry: {missing_v1!r}",
            ))
        v1_runnable_count = sum(
            1 for operation_id in v1_operations
            if operation_id in by_id and by_id[operation_id].get("status") in RUNNABLE_STATUSES
        )
        non_runnable_v1 = sorted(
            (operation_id, by_id[operation_id].get("status"))
            for operation_id in v1_operations
            if operation_id in by_id and by_id[operation_id].get("status") not in RUNNABLE_STATUSES
        )
        if non_runnable_v1:
            failures.append(OperationRegistryFailure(
                code="V1_OPERATION_NOT_RUNNABLE",
                source=str(registry_path),
                detail=f"v1 operations are not implemented/wired: {non_runnable_v1!r}",
            ))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        failures.append(OperationRegistryFailure(
            code="V1_OPERATION_SCHEMA_PARSE_FAILED",
            source=str(v1_path),
            detail=f"{type(exc).__name__}: {exc}",
        ))

    native_family_count = 0
    internal_native_operation_names: tuple[str, ...] = ()
    native_facts = None
    try:
        native_facts = _parse_native_snapshot(snapshot)
        native_family_count = len(native_facts.families)
        internal_native_operation_names = tuple(
            sorted(native_facts.internal_table_operations)
        )
        runtime_family_gates = frozenset(native_facts.runtime_family_gates)
        discovered_family_gates = native_facts.discovered_family_gates
        if runtime_family_gates != discovered_family_gates:
            failures.append(OperationRegistryFailure(
                code="NATIVE_FAMILY_GATE_MISMATCH",
                source=str(root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"),
                detail=(
                    "runtime-only={0!r}; discovered-only={1!r}".format(
                        sorted(runtime_family_gates - discovered_family_gates),
                        sorted(discovered_family_gates - runtime_family_gates),
                    )
                ),
            ))
        expected_dispatchers = tuple(
            gate.removesuffix("HasOp") + "Dispatch"
            for gate in native_facts.runtime_family_gates
        )
        if native_facts.runtime_family_dispatchers != expected_dispatchers:
            failures.append(OperationRegistryFailure(
                code="NATIVE_FAMILY_DISPATCH_CHAIN_MISMATCH",
                source=str(root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"),
                detail=(
                    f"expected={expected_dispatchers!r}; "
                    f"observed={native_facts.runtime_family_dispatchers!r}"
                ),
            ))
        family_dispatch_mismatches = {
            family: {
                "hasop_only": sorted(info.operations - info.dispatch_operations),
                "dispatch_only": sorted(info.dispatch_operations - info.operations),
            }
            for family, info in native_facts.families.items()
            if info.operations != info.dispatch_operations
        }
        if family_dispatch_mismatches:
            failures.append(OperationRegistryFailure(
                code="NATIVE_FAMILY_DISPATCH_MISMATCH",
                source=str(root / "src" / "Ariadne.AcadNative" / "families"),
                detail=f"HasOp/Dispatch mismatches: {family_dispatch_mismatches!r}",
            ))
        legacy_table_operations = (
            native_facts.native_table_operations
            | native_facts.internal_table_operations
        )
        if legacy_table_operations != native_facts.legacy_dispatch_operations:
            failures.append(OperationRegistryFailure(
                code="NATIVE_LEGACY_DISPATCH_MISMATCH",
                source=str(root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"),
                detail=(
                    "table-only={0!r}; dispatch-only={1!r}".format(
                        sorted(
                            legacy_table_operations
                            - native_facts.legacy_dispatch_operations
                        ),
                        sorted(
                            native_facts.legacy_dispatch_operations
                            - legacy_table_operations
                        ),
                    )
                ),
            ))
        unresolved_family_identifiers = {
            family: info.unresolved
            for family, info in native_facts.families.items()
            if info.unresolved
        }
        if unresolved_family_identifiers:
            failures.append(OperationRegistryFailure(
                code="NATIVE_FAMILY_IDENTIFIER_UNRESOLVED",
                source=str(root / "src" / "Ariadne.AcadNative" / "families"),
                detail=f"unresolved HasOp identifiers: {unresolved_family_identifiers!r}",
            ))
        if native_facts.duplicate_native_table_operations:
            failures.append(OperationRegistryFailure(
                code="NATIVE_OPERATION_TABLE_DUPLICATE",
                source=str(root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"),
                detail=(
                    "duplicate public native operation ids: "
                    f"{list(native_facts.duplicate_native_table_operations)!r}"
                ),
            ))
        if native_facts.duplicate_internal_table_operations:
            failures.append(OperationRegistryFailure(
                code="INTERNAL_NATIVE_OPERATION_DUPLICATE",
                source=str(root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"),
                detail=(
                    "duplicate internal native operation ids: "
                    f"{list(native_facts.duplicate_internal_table_operations)!r}"
                ),
            ))
        expected_internal_families = {
            operation_id: purpose.native_family
            for operation_id, purpose in INTERNAL_NATIVE_OPERATION_PURPOSES.items()
        }
        observed_internal_families = dict(
            native_facts.internal_table_operation_families
        )
        if observed_internal_families != expected_internal_families:
            failures.append(OperationRegistryFailure(
                code="INTERNAL_NATIVE_OPERATION_CONTRACT_MISMATCH",
                source=str(root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"),
                detail=(
                    f"expected={dict(sorted(expected_internal_families.items()))!r}; "
                    f"observed={dict(sorted(observed_internal_families.items()))!r}"
                ),
            ))
        public_table_overlap = sorted(
            native_facts.native_table_operations
            & native_facts.internal_table_operations
        )
        registry_overlap = sorted(
            registry_id_set & native_facts.internal_table_operations
        )
        if public_table_overlap or registry_overlap:
            failures.append(OperationRegistryFailure(
                code="INTERNAL_NATIVE_OPERATION_OVERLAP",
                source=str(root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"),
                detail=(
                    f"public-table-overlap={public_table_overlap!r}; "
                    f"registry-overlap={registry_overlap!r}"
                ),
            ))
    except NativeAdmissionContractMismatch as exc:
        failures.append(OperationRegistryFailure(
            code="NATIVE_ADMISSION_CONTRACT_MISMATCH",
            source=str(root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"),
            detail=str(exc),
        ))
    except (OSError, UnicodeError, OperationSourceParseError) as exc:
        failures.append(OperationRegistryFailure(
            code="NATIVE_FAMILY_PARSE_FAILED",
            source=str(root / "src" / "Ariadne.AcadNative" / "families"),
            detail=f"{type(exc).__name__}: {exc}",
        ))

    patch_vocabulary = None
    try:
        patch_vocabulary = _parse_patch_snapshot(snapshot)
    except PatchFamilyDispatchMismatch as exc:
        failures.append(OperationRegistryFailure(
            code="PATCH_FAMILY_DISPATCH_MISMATCH",
            source=str(root / "tools" / "patch_ops"),
            detail=str(exc),
        ))
    except (OSError, UnicodeError, OperationSourceParseError) as exc:
        failures.append(OperationRegistryFailure(
            code="PATCH_VOCAB_PARSE_FAILED",
            source=str(root / "tools"),
            detail=f"{type(exc).__name__}: {exc}",
        ))

    if native_facts is not None:
        coded_ops = native_facts.coded_operations
        unclassified_native_ops = sorted(set(coded_ops) - registry_id_set)
        if unclassified_native_ops:
            failures.append(OperationRegistryFailure(
                code="NATIVE_OPERATION_NOT_CLASSIFIED",
                source=str(root / "config" / "operations.v2.json"),
                detail=(
                    "native dispatcher operations absent from registry: "
                    f"{unclassified_native_ops!r}"
                ),
            ))
        if patch_vocabulary is not None:
            vocab_violations = check_vocab_lockstep(
                registry,
                coded_ops,
                patch_vocabulary,
            )
            if vocab_violations:
                failures.append(OperationRegistryFailure(
                    code="PATCH_NATIVE_VOCAB_DRIFT",
                    source=str(root / "tools"),
                    detail=f"lockstep violations: {vocab_violations!r}",
                ))

    try:
        ending_snapshot = _capture_input_snapshot(root)
        snapshot_consistent = (
            ending_snapshot.aggregate_sha256 == snapshot.aggregate_sha256
            and set(ending_snapshot.sources) == set(snapshot.sources)
            and snapshot.captured.same_generation_as(ending_snapshot.captured)
        )
        snapshot_detail = (
            "operation-registry input path set or bytes changed during verification"
        )
    except (OSError, UnicodeError, OperationSourceParseError) as exc:
        snapshot_consistent = False
        snapshot_detail = (
            "operation-registry inputs became unreadable during verification: "
            f"{type(exc).__name__}: {exc}"
        )
    if not snapshot_consistent:
        failures.append(OperationRegistryFailure(
            code="INPUT_SNAPSHOT_CHANGED",
            source=str(root),
            detail=snapshot_detail,
        ))

    return OperationRegistryReceipt(
        verified=not failures,
        registry_schema=registry_schema if isinstance(registry_schema, str) else None,
        operation_count=len(operations),
        status_histogram=dict(sorted(status_histogram.items())),
        failures=tuple(failures),
        native_catalog_count=native_catalog_count,
        v1_operation_count=len(v1_operations),
        v1_runnable_count=v1_runnable_count,
        native_family_count=native_family_count,
        internal_native_operation_count=len(internal_native_operation_names),
        internal_native_operation_names=internal_native_operation_names,
        limitations=(
            PROPERTY_COUNT_RUNTIME_EVIDENCE_LIMITATION,
            STATIC_DECLARATION_PARITY_LIMITATION,
        ),
        limitation_codes=(
            "property_count_runtime_evidence_host_subset",
            *STATIC_VOCABULARY_LIMITATION_CODES,
        ),
        status_vocabulary=status_vocabulary,
        input_digests=snapshot.digests,
        input_set_sha256=snapshot.aggregate_sha256,
        snapshot_consistent=snapshot_consistent,
    )
