from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools.verification import operation_registry as operation_registry_module
from tools.verification.operation_registry import (
    OperationRegistryReceipt,
    verify_operation_registry,
)


REPO = Path(__file__).resolve().parents[2]

EXPECTED_INTERNAL_NATIVE_OPERATION_PURPOSES = {
    "e2.inspect.xclip_membership": {
        "native_family": "experiment_oracle",
        "reason": "experiment_oracle",
        "dedicated_public_surface": "cad.inspect_display_membership",
    },
    "extend.deep_native.firing_selftest": {
        "native_family": "extend",
        "reason": "internal_verification_harness",
        "dedicated_public_surface": None,
    },
    "inspect.deep_native.firing_report": {
        "native_family": "inspect",
        "reason": "internal_verification_readout",
        "dedicated_public_surface": None,
    },
    "inspect.selection.monitor.registry": {
        "native_family": "live",
        "reason": "internal_capability_probe",
        "dedicated_public_surface": "inspect.runtime.capabilities",
    },
    "live.selection.monitor.disable": {
        "native_family": "live",
        "reason": "internal_runtime_probe",
        "dedicated_public_surface": "inspect.runtime.capabilities",
    },
    "live.selection.monitor.enable": {
        "native_family": "live",
        "reason": "internal_runtime_probe",
        "dedicated_public_surface": "inspect.runtime.capabilities",
    },
}


def _copy_verification_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "router"
    files = (
        "config/operations.v2.json",
        "config/autocad_native_arx_operation_catalog.json",
        "schemas/operation_registry.v2.schema.json",
        "schemas/cad_job.schema.json",
        "src/Ariadne.AcadNative/AriadneNativeJob.cpp",
        "tools/patch_engine.py",
        "tools/reconcile_native_registry.py",
    )
    for relative in files:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / relative, destination)
    shutil.copytree(
        REPO / "src" / "Ariadne.AcadNative" / "families",
        root / "src" / "Ariadne.AcadNative" / "families",
    )
    shutil.copytree(
        REPO / "tools" / "patch_ops",
        root / "tools" / "patch_ops",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return root


def test_property_count_is_one_public_read_only_registry_atom_with_current_evidence() -> None:
    registry = json.loads(
        (REPO / "config" / "operations.v2.json").read_text(encoding="utf-8-sig")
    )
    v1_schema = json.loads(
        (REPO / "schemas" / "cad_job.schema.json").read_text(encoding="utf-8-sig")
    )
    policy = json.loads(
        (REPO / "config" / "policy.v2.json").read_text(encoding="utf-8-sig")
    )

    records = [
        operation
        for operation in registry["operations"]
        if operation["id"] == "inspect.probe.property_count"
    ]

    assert records == [
        {
            "id": "inspect.probe.property_count",
            "family": "inspect",
            "status": "implemented",
            "engine_tier": "objectdbx_capable",
            "host_eligibility": [
                "dbx",
                "coreconsole",
                "arx_adapter",
                "full_autocad",
            ],
            "execution_context": "in_process_host",
            "write_level": {
                "default_write_mode": "read",
                "allowed_write_modes": ["read"],
                "dwg_persisted": False,
                "original_write_default": False,
            },
            "handler": {
                "router_lane": "ARIADNE_NATIVE_JOB",
                "dispatcher_symbol": "ariadneProbePropertyCount",
                "execution_host_class": "dbx",
                "composed_of": [
                    "inspect.entity.properties",
                    "inspect.property.by_name",
                ],
            },
            "mapping_type": "synthetic",
            "catalog_op_id": None,
            "input_schema": "schemas/cad_job.v2.schema.json#/allOf",
            "output_schema": "schemas/cad_result.v2.schema.json",
            "summary": (
                "Reports the registered AcRxProperty count for a transient "
                "AriadneProbe without mutating a drawing."
            ),
            "evidence_refs": [
                "docs/LIVE_JOB_ARGUMENT_CONTRACT.md#job_outjson-the-result",
                "reports/opm_property_latest.json#headless_proof",
                "reports/native_smoke_latest.json#headless_channel_smoke",
                "tests/unit/test_operation_registry_verifier.py::test_probe_property_count_native_source_and_result_shape",
            ],
            "phase_batch": "P2 Batch 3 Host-Bound Capability Contracts",
            "target_family_first_class": False,
            "wired_v1": False,
            "operation": "inspect.probe.property_count",
            "hosts": ["dbx", "coreconsole", "arx_adapter", "full_autocad"],
            "engines": ["objectdbx_capable"],
            "schema_refs": {
                "input": "schemas/cad_job.v2.schema.json#/allOf",
                "output": "schemas/cad_result.v2.schema.json",
            },
            "policy": {
                "source": "config/policy.v2.json",
                "status_policy": "implemented",
                "default_write_mode": "read",
                "no_original_write_default": True,
            },
            "tests": [
                "tests/unit/test_operation_registry_verifier.py::test_probe_property_count_native_source_and_result_shape"
            ],
            "notes": (
                "Headless proof reports property_count=1 for the Size property; "
                "the OPM panel itself remains attended-only."
            ),
            "owner_ticket": "M08C-T01",
            "implementation_strategy": "implemented_v1",
            "evidence_required": "existing_tests_and_evidence_refs",
        }
    ]
    assert "inspect.probe.property_count" not in (
        v1_schema["properties"]["operation"]["enum"]
    )
    assert policy["write_levels"]["read"]["applies_to_default"].count(
        "inspect.probe.property_count"
    ) == 1


def test_probe_property_count_native_source_and_result_shape() -> None:
    native_source = (
        REPO / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    ).read_text(encoding="utf-8")
    dbx_source = (
        REPO / "src" / "Ariadne.AcadNativeDbx" / "AriadneDbxEntry.cpp"
    ).read_text(encoding="utf-8")

    branch_start = native_source.index(
        'else if (op == "inspect.probe.property_count")'
    )
    branch_end = native_source.index("\n    else if (", branch_start + 1)
    branch = native_source[branch_start:branch_end]
    helper_start = dbx_source.index("int ariadneProbePropertyCount()")
    helper_end = dbx_source.index("\n}\n", helper_start) + 2
    helper = dbx_source[helper_start:helper_end]

    assert "const int pc = ariadneProbePropertyCount();" in branch
    assert '\\"property_count\\":' in branch
    assert '\\"property\\":\\"Size\\"' in branch
    assert '\\"opm_registration\\":' in branch
    assert '\\"panel_display\\":\\"attended_only\\"' in branch
    assert '\\"status\\":\\"' in branch
    assert "pc >= 0 ? \"ok\" : \"error\"" in branch
    assert 'find(ACRX_T("Size"))' in helper
    assert "AriadneProbe probe;" in helper
    assert "return found;" in helper


def test_internal_native_product_contract_is_exact_and_visible_in_receipt() -> None:
    contract = operation_registry_module.INTERNAL_NATIVE_OPERATION_PURPOSES
    receipt = verify_operation_registry(REPO)

    assert {
        operation_id: purpose.to_dict()
        for operation_id, purpose in contract.items()
    } == EXPECTED_INTERNAL_NATIVE_OPERATION_PURPOSES
    assert receipt.internal_native_operation_count == 6
    assert receipt.internal_native_operation_names == tuple(
        sorted(EXPECTED_INTERNAL_NATIVE_OPERATION_PURPOSES)
    )
    assert receipt.limitations == (
        "inspect.probe.property_count host eligibility includes dbx and "
        "arx_adapter, but current runtime evidence covers only coreconsole "
        "and full_autocad",
        "operation registry verification compares the declared operation vocabulary "
        "only; dispatch targets, handler execution, and semantic success require "
        "independent runtime evidence",
    )
    assert receipt.limitation_codes == (
        "property_count_runtime_evidence_host_subset",
        "dispatch_target_identity_not_proven",
        "handler_execution_not_proven",
        "source_not_compiled_or_executed",
    )
    assert receipt.verification_scope == "static_operation_vocabulary_parity"
    assert not any(
        operation_id in failure.detail
        for failure in receipt.failures
        if failure.code == "NATIVE_OPERATION_NOT_CLASSIFIED"
        for operation_id in EXPECTED_INTERNAL_NATIVE_OPERATION_PURPOSES
    )


def test_internal_native_contract_drift_is_a_typed_failure(tmp_path: Path) -> None:
    root = _copy_verification_fixture(tmp_path)
    source_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = source_path.read_text(encoding="utf-8")
    needle = '{ "inspect.deep_native.firing_report", "inspect" }'
    assert needle in source
    source_path.write_text(
        source.replace(
            needle,
            '{ "inspect.deep_native.firing_report", "live" }',
            1,
        ),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    assert "INTERNAL_NATIVE_OPERATION_CONTRACT_MISMATCH" in {
        failure.code for failure in receipt.failures
    }


def test_internal_native_registry_overlap_is_a_typed_failure(tmp_path: Path) -> None:
    root = _copy_verification_fixture(tmp_path)
    source_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = source_path.read_text(encoding="utf-8")
    needle = "static const AriadneOperationSpec kAriadneInternalOperationTable[] = {"
    assert needle in source
    source_path.write_text(
        source.replace(
            needle,
            needle + '\n    { "inspect.probe.property_count", "inspect" },',
            1,
        ),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    assert "INTERNAL_NATIVE_OPERATION_OVERLAP" in {
        failure.code for failure in receipt.failures
    }


def test_internal_native_duplicate_id_is_a_typed_failure(tmp_path: Path) -> None:
    root = _copy_verification_fixture(tmp_path)
    source_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = source_path.read_text(encoding="utf-8")
    needle = '{ "live.selection.monitor.enable", "live" },'
    assert needle in source
    source_path.write_text(
        source.replace(needle, needle + "\n    " + needle, 1),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    assert "INTERNAL_NATIVE_OPERATION_DUPLICATE" in {
        failure.code for failure in receipt.failures
    }


def test_property_count_missing_from_registry_is_a_native_classification_failure(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    registry_path = root / "config" / "operations.v2.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    registry["operations"] = [
        operation
        for operation in registry["operations"]
        if operation["id"] != "inspect.probe.property_count"
    ]
    registry["totals"]["operations"] -= 1
    registry["totals"]["by_status"]["implemented"] -= 1
    registry["totals"]["by_family"]["inspect"] -= 1
    registry["totals"]["by_engine_tier"]["objectdbx_capable"] -= 1
    registry["totals"]["total"] -= 1
    registry["coverage"]["operation_records"] -= 1
    registry["coverage"]["implemented"] -= 1
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    receipt = verify_operation_registry(root)
    failures = [
        failure
        for failure in receipt.failures
        if failure.code == "NATIVE_OPERATION_NOT_CLASSIFIED"
    ]

    assert receipt.verified is False
    assert len(failures) == 1
    assert "inspect.probe.property_count" in failures[0].detail


def test_live_registry_receipt_exposes_consistent_schema_and_status_histogram() -> None:
    receipt = verify_operation_registry(REPO)

    assert isinstance(receipt, OperationRegistryReceipt)
    assert receipt.verified is True
    assert receipt.registry_schema == "ariadne.operations_registry.v2"
    assert receipt.operation_count == sum(receipt.status_histogram.values()) == 552
    assert receipt.status_histogram == {"blocked": 62, "implemented": 490}
    assert receipt.status_vocabulary == frozenset(
        {"implemented", "wired", "stub", "catalogued", "deprecated", "blocked"}
    )
    assert receipt.failures == ()


def test_live_registry_receipt_exposes_extend_only_catalog_and_family_relations() -> None:
    receipt = verify_operation_registry(REPO)

    assert receipt.native_catalog_count == 480
    assert receipt.v1_operation_count == receipt.v1_runnable_count == 29
    assert receipt.native_family_count == 16
    assert receipt.native_catalog_count <= receipt.operation_count
    assert receipt.v1_operation_count <= receipt.operation_count
    assert receipt.verified is True


def test_receipt_binds_exact_input_digests_and_serializes_stably(tmp_path: Path) -> None:
    root = _copy_verification_fixture(tmp_path)

    first = verify_operation_registry(root)
    second = verify_operation_registry(root)

    expected_registry_digest = hashlib.sha256(
        (root / "config" / "operations.v2.json")
        .read_bytes()
        .replace(b"\r\n", b"\n")
    ).hexdigest()
    assert first.input_digests["config/operations.v2.json"] == expected_registry_digest
    assert {
        "config/operations.v2.json",
        "schemas/operation_registry.v2.schema.json",
        "config/autocad_native_arx_operation_catalog.json",
        "schemas/cad_job.schema.json",
        "src/Ariadne.AcadNative/AriadneNativeJob.cpp",
        "tools/patch_engine.py",
        "tools/patch_ops/__init__.py",
        "tools/patch_ops/entities.py",
        "tools/patch_ops/blocks.py",
        "tools/patch_ops/tables.py",
        "tools/patch_ops/db.py",
    } <= set(first.input_digests)
    assert "tools/reconcile_native_registry.py" not in first.input_digests
    assert all(
        len(digest) == 64 and digest == digest.lower()
        for digest in first.input_digests.values()
    )
    assert len(first.input_set_sha256) == 64
    assert first.snapshot_consistent is True
    first_json = json.dumps(first.to_dict(), sort_keys=True, separators=(",", ":"))
    second_json = json.dumps(second.to_dict(), sort_keys=True, separators=(",", ":"))
    assert first_json == second_json


def test_registry_verifier_reads_every_source_from_safe_handle_snapshots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _copy_verification_fixture(tmp_path)

    def forbidden_path_read(_path: Path) -> bytes:
        raise AssertionError("verification must not path-check then read by pathname")

    monkeypatch.setattr(Path, "read_bytes", forbidden_path_read)

    receipt = verify_operation_registry(root)

    assert receipt.verified is True, [failure.to_dict() for failure in receipt.failures]
    assert receipt.snapshot_consistent is True


def test_input_snapshot_drift_is_a_typed_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    registry_path = (root / "config" / "operations.v2.json").resolve()
    original_capture = operation_registry_module._capture_input_snapshot
    original = registry_path.read_bytes()
    changed = False

    def change_after_starting_snapshot(path: Path):
        nonlocal changed
        snapshot = original_capture(path)
        if not changed:
            changed = True
            registry_path.write_bytes(original + b"\n")
        return snapshot

    monkeypatch.setattr(
        operation_registry_module,
        "_capture_input_snapshot",
        change_after_starting_snapshot,
    )

    receipt = verify_operation_registry(root)

    assert changed is True
    assert receipt.snapshot_consistent is False
    assert receipt.verified is False
    assert "INPUT_SNAPSHOT_CHANGED" in {
        failure.code for failure in receipt.failures
    }
    assert receipt.input_digests["config/operations.v2.json"] != hashlib.sha256(
        registry_path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()


def test_same_bytes_registry_identity_replacement_is_typed_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    registry_path = root / "config" / "operations.v2.json"
    original = registry_path.read_bytes()
    original_capture = operation_registry_module._capture_input_snapshot
    replaced = False

    def capture_then_replace_identity(path: Path):
        nonlocal replaced
        snapshot = original_capture(path)
        if not replaced:
            replaced = True
            replacement = registry_path.with_suffix(".replacement")
            replacement.write_bytes(original)
            os.replace(replacement, registry_path)
        return snapshot

    monkeypatch.setattr(
        operation_registry_module,
        "_capture_input_snapshot",
        capture_then_replace_identity,
    )

    receipt = verify_operation_registry(root)

    assert replaced is True
    assert receipt.input_digests["config/operations.v2.json"] == hashlib.sha256(
        original.replace(b"\r\n", b"\n")
    ).hexdigest()
    assert receipt.snapshot_consistent is False
    assert receipt.verified is False
    assert "INPUT_SNAPSHOT_CHANGED" in {
        failure.code for failure in receipt.failures
    }


def test_input_snapshot_rejects_a_reparse_parent(tmp_path: Path) -> None:
    root = _copy_verification_fixture(tmp_path)
    config = root / "config"
    external_config = tmp_path / "external-config"
    config.rename(external_config)
    if os.name == "nt":
        linked = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(config), str(external_config)],
            check=False,
            capture_output=True,
            text=True,
        )
        if linked.returncode != 0:
            pytest.skip("directory junctions are unavailable: " + linked.stderr)
    else:
        os.symlink(external_config, config, target_is_directory=True)

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    assert receipt.snapshot_consistent is False
    assert receipt.failures[0].code == "INPUT_SNAPSHOT_FAILED"
    assert "reparse" in receipt.failures[0].detail or "symlink" in receipt.failures[0].detail


def test_family_gate_drift_is_not_hidden_by_the_discovered_family_count(tmp_path: Path) -> None:
    root = _copy_verification_fixture(tmp_path)
    source_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = source_path.read_text(encoding="utf-8")
    needle = " || m08nHasOp(op)"
    assert needle in source
    source_path.write_text(source.replace(needle, "", 1), encoding="utf-8")

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    assert "NATIVE_FAMILY_GATE_MISMATCH" in {failure.code for failure in receipt.failures}


def test_patch_vocabulary_missing_map_cannot_become_empty_set_pass(tmp_path: Path) -> None:
    root = _copy_verification_fixture(tmp_path)
    (root / "tools" / "patch_engine.py").write_text(
        "raise RuntimeError('synthetic patch vocabulary import failure')\n",
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    assert "PATCH_VOCAB_PARSE_FAILED" in {failure.code for failure in receipt.failures}


def test_patch_vocabulary_syntax_error_returns_a_typed_failure(tmp_path: Path) -> None:
    root = _copy_verification_fixture(tmp_path)
    (root / "tools" / "patch_engine.py").write_text(
        "this is not valid Python !!!\n",
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    assert "PATCH_VOCAB_PARSE_FAILED" in {failure.code for failure in receipt.failures}


def test_patch_aggregate_rejects_a_family_that_is_not_imported(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    init_path = root / "tools" / "patch_ops" / "__init__.py"
    source = init_path.read_text(encoding="utf-8")
    import_line = "from . import blocks, db, entities, tables"
    assert import_line in source
    init_path.write_text(
        source.replace(import_line, "from . import blocks, db, tables", 1),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure
        for failure in receipt.failures
        if failure.code == "PATCH_VOCAB_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "relative imports" in failures[0].detail


@pytest.mark.parametrize(
    ("replacement", "detail"),
    [
        (
            "from . import blocks, db, entities, tables, xdata",
            "relative imports",
        ),
        (
            "from . import blocks as block_family, db, entities, tables",
            "aliases",
        ),
        (
            "if True:\n    from . import blocks, db, entities, tables",
            "top-level",
        ),
        (
            "from . import blocks, db, entities, tables, blocks",
            "duplicate",
        ),
    ],
)
def test_patch_aggregate_rejects_noncanonical_relative_import_bindings(
    tmp_path: Path,
    replacement: str,
    detail: str,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    init_path = root / "tools" / "patch_ops" / "__init__.py"
    source = init_path.read_text(encoding="utf-8")
    import_line = "from . import blocks, db, entities, tables"
    assert import_line in source
    init_path.write_text(
        source.replace(import_line, replacement, 1),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "PATCH_VOCAB_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert detail in failures[0].detail


@pytest.mark.parametrize(
    ("needle", "replacement", "detail"),
    [
        (
            "_FAMILIES = (entities, blocks, tables, db)",
            "_FAMILIES = (entities, blocks, tables)",
            "_FAMILIES",
        ),
        (
            "    **db.WRITE_OP_MAP,\n",
            "",
            "NATIVE_WRITE_OP_MAP",
        ),
    ],
)
def test_patch_aggregate_rejects_family_tuple_or_map_drift(
    tmp_path: Path,
    needle: str,
    replacement: str,
    detail: str,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    init_path = root / "tools" / "patch_ops" / "__init__.py"
    source = init_path.read_text(encoding="utf-8")
    assert needle in source
    init_path.write_text(source.replace(needle, replacement, 1), encoding="utf-8")

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "PATCH_VOCAB_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert detail in failures[0].detail


def test_patch_aggregate_build_job_args_must_iterate_the_exact_family_tuple(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    init_path = root / "tools" / "patch_ops" / "__init__.py"
    source = init_path.read_text(encoding="utf-8")
    loop = "for fam in _FAMILIES:"
    assert loop in source
    init_path.write_text(
        source.replace(loop, "for fam in ():", 1),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "PATCH_VOCAB_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "aggregate build_job_args" in failures[0].detail


def test_patch_family_map_is_bound_to_actual_build_job_args_branches(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    family_path = root / "tools" / "patch_ops" / "entities.py"
    source = family_path.read_text(encoding="utf-8")
    needle = 'if native_op == "write.entity.line":'
    assert needle in source
    family_path.write_text(
        source.replace(needle, 'if native_op == "ghost.entity.line":', 1),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "PATCH_FAMILY_DISPATCH_MISMATCH"
    ]
    assert len(failures) == 1
    assert "write.entity.line" in failures[0].detail
    assert "ghost.entity.line" in failures[0].detail


def test_patch_family_build_job_args_cannot_be_rebound_after_definition(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    family_path = root / "tools" / "patch_ops" / "blocks.py"
    source = family_path.read_text(encoding="utf-8")
    family_path.write_text(
        source + "\nbuild_job_args = lambda native_op, args: None\n",
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "PATCH_VOCAB_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "build_job_args" in failures[0].detail
    assert "rebound" in failures[0].detail


def test_patch_aggregate_cannot_rebind_a_family_dispatch_function(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    aggregate_path = root / "tools" / "patch_ops" / "__init__.py"
    source = aggregate_path.read_text(encoding="utf-8")
    aggregate_path.write_text(
        source + "\nblocks.build_job_args = lambda native_op, args: None\n",
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "PATCH_VOCAB_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "blocks.build_job_args" in failures[0].detail
    assert "rebound" in failures[0].detail


def test_unparseable_native_source_returns_a_typed_failure(tmp_path: Path) -> None:
    root = _copy_verification_fixture(tmp_path)
    family_path = (
        root / "src" / "Ariadne.AcadNative" / "families" / "m08c_handlers.inc"
    )
    source = family_path.read_text(encoding="utf-8")
    assert "bool m08cHasOp(" in source
    family_path.write_text(
        source.replace("bool m08cHasOp(", "int m08cHasOp(", 1),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    assert "NATIVE_FAMILY_PARSE_FAILED" in {
        failure.code for failure in receipt.failures
    }


def test_commented_cpp_operation_tokens_are_not_live_operations(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    native_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    native_source = native_path.read_text(encoding="utf-8")
    table_needle = (
        "static const AriadneOperationSpec kAriadneNativeOperationTable[] = {"
    )
    assert table_needle in native_source
    native_path.write_text(
        native_source.replace(
            table_needle,
            table_needle + '\n    // { "commented.public", "inspect" },',
            1,
        ),
        encoding="utf-8",
    )

    family_path = (
        root / "src" / "Ariadne.AcadNative" / "families" / "m08c_handlers.inc"
    )
    family_source = family_path.read_text(encoding="utf-8")
    hasop_needle = "bool m08cHasOp(const std::string& op)"
    assert hasop_needle in family_source
    body_open = family_source.index("{", family_source.index(hasop_needle))
    family_source = (
        family_source[: body_open + 1]
        + '\n    // return op == "commented.family";'
        + family_source[body_open + 1 :]
    )
    family_path.write_text(family_source, encoding="utf-8")

    receipt = verify_operation_registry(root)

    assert receipt.verified is True, [failure.to_dict() for failure in receipt.failures]
    assert not any(
        "commented.public" in failure.detail
        or "commented.family" in failure.detail
        for failure in receipt.failures
    )


def test_unreachable_cpp_operation_branch_blocks_source_inference(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    family_path = (
        root / "src" / "Ariadne.AcadNative" / "families" / "m08c_handlers.inc"
    )
    source = family_path.read_text(encoding="utf-8")
    hasop_needle = "bool m08cHasOp(const std::string& op)"
    body_open = source.index("{", source.index(hasop_needle))
    family_path.write_text(
        source[: body_open + 1]
        + '\n    if (false) { return op == "ghost.unreachable"; }'
        + source[body_open + 1 :],
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure
        for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "not one direct return expression" in failures[0].detail


def test_unreachable_family_gate_call_blocks_source_inference(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    native_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = native_path.read_text(encoding="utf-8")
    family_needle = "static bool familyHasOp(const std::string& op)"
    body_open = source.index("{", source.index(family_needle))
    native_path.write_text(
        source[: body_open + 1]
        + "\n    if (false) { m08cHasOp(op); }"
        + source[body_open + 1 :],
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure
        for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "familyHasOp() is not one direct return expression" in failures[0].detail


def test_native_family_hasop_must_match_actual_dispatch_branches(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    family_path = (
        root / "src" / "Ariadne.AcadNative" / "families" / "w6_dynblk_handlers.inc"
    )
    source = family_path.read_text(encoding="utf-8")
    branch = (
        "    if (op == kW6dOpDynSetProperty)\n"
        "        return w6dHandleSetDynProperty(ctx, r);\n"
    )
    assert branch in source
    family_path.write_text(source.replace(branch, "", 1), encoding="utf-8")

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_DISPATCH_MISMATCH"
    ]
    assert len(failures) == 1
    assert "write.dynblock.property" in failures[0].detail


def test_native_family_direct_dispatch_branch_must_handle_the_operation(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    family_path = (
        root / "src" / "Ariadne.AcadNative" / "families" / "w6_dynblk_handlers.inc"
    )
    source = family_path.read_text(encoding="utf-8")
    handler_return = "return w6dHandleSetDynProperty(ctx, r);"
    assert handler_return in source
    family_path.write_text(
        source.replace(handler_return, "return false;", 1),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "declines a declared operation" in failures[0].detail


def test_native_family_direct_dispatch_branch_rejects_integer_zero_terminal(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    family_path = (
        root / "src" / "Ariadne.AcadNative" / "families" / "w6_dynblk_handlers.inc"
    )
    source = family_path.read_text(encoding="utf-8")
    handler_return = "return w6dHandleSetDynProperty(ctx, r);"
    assert handler_return in source
    family_path.write_text(
        source.replace(handler_return, "return 0;", 1),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "exact supported handled return" in failures[0].detail


def test_unreachable_native_family_dispatch_branch_is_not_counted(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    family_path = (
        root / "src" / "Ariadne.AcadNative" / "families" / "w6_dynblk_handlers.inc"
    )
    source = family_path.read_text(encoding="utf-8")
    branch = (
        "    if (op == kW6dOpDynSetProperty)\n"
        "        return w6dHandleSetDynProperty(ctx, r);\n"
    )
    assert branch in source
    family_path.write_text(
        source.replace(
            branch,
            "    if (false) {\n" + branch + "    }\n",
            1,
        ),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "unreachable conditional branch" in failures[0].detail


def test_m08d_nested_operation_branch_rejects_an_unsupported_outer_guard(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    family_path = (
        root / "src" / "Ariadne.AcadNative" / "families" / "m08d_handlers.inc"
    )
    source = family_path.read_text(encoding="utf-8")
    branch_start = '            if (op == "inspect.vertex.point") {'
    following_branch = (
        '            if (op == "inspect.loop.type" || op == "inspect.loop.face") {'
    )
    assert branch_start in source
    assert following_branch in source
    source = source.replace(
        branch_start,
        "            if (0 == 1) {\n" + branch_start,
        1,
    )
    source = source.replace(
        following_branch,
        "            }\n" + following_branch,
        1,
    )
    family_path.write_text(source, encoding="utf-8")

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "unsupported outer guard" in failures[0].detail


def test_m08l_dispatch_helper_literals_are_part_of_family_dispatch_parity(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    family_path = (
        root / "src" / "Ariadne.AcadNative" / "families" / "m08l_handlers.inc"
    )
    source = family_path.read_text(encoding="utf-8")
    branch = 'installOp == "overrule.grip.install"'
    assert branch in source
    family_path.write_text(
        source.replace(branch, 'installOp == "ghost.overrule.grip.install"', 1),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_DISPATCH_MISMATCH"
    ]
    assert len(failures) == 1
    assert "overrule.grip.install" in failures[0].detail
    assert "ghost.overrule.grip.install" in failures[0].detail


def test_family_hasop_and_dispatch_chains_have_exact_ordered_parity(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    native_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = native_path.read_text(encoding="utf-8")
    needle = "        || w6dynblkDispatch(op, ctx, r)   // w6-dynblk\n"
    assert needle in source
    native_path.write_text(source.replace(needle, "", 1), encoding="utf-8")

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_DISPATCH_CHAIN_MISMATCH"
    ]
    assert len(failures) == 1
    assert "w6dynblk" in failures[0].detail


@pytest.mark.parametrize(
    ("function_name", "table_name"),
    [
        ("findAriadneNativeOp", "kAriadneNativeOperationTable"),
        ("findAriadneInternalOp", "kAriadneInternalOperationTable"),
    ],
)
def test_native_operation_table_lookup_body_is_part_of_the_authority_contract(
    tmp_path: Path,
    function_name: str,
    table_name: str,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    native_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = native_path.read_text(encoding="utf-8")
    signature = (
        "static const AriadneOperationSpec* " + function_name
        + "(const std::string& op)\n{"
    )
    assert signature in source
    body_start = source.index(signature) + len(signature)
    body_end = source.index("\n}", body_start)
    replacement = (
        signature
        + "\n    (void)op;\n    return &"
        + table_name
        + "[0];"
    )
    source = source[: source.index(signature)] + replacement + source[body_end:]
    native_path.write_text(source, encoding="utf-8")

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert function_name in failures[0].detail
    assert "canonical table lookup" in failures[0].detail


def test_native_operation_table_count_is_part_of_the_authority_contract(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    native_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = native_path.read_text(encoding="utf-8")
    count = (
        "static const size_t kAriadneNativeOperationCount =\n"
        "    sizeof(kAriadneNativeOperationTable) / "
        "sizeof(kAriadneNativeOperationTable[0]);"
    )
    assert count in source
    native_path.write_text(source.replace(count, (
        "static const size_t kAriadneNativeOperationCount = 1;"
    ), 1), encoding="utf-8")

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "kAriadneNativeOperationCount" in failures[0].detail


def test_known_operation_predicate_is_bound_to_both_tables_and_family_gate(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    native_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = native_path.read_text(encoding="utf-8")
    canonical = (
        "static bool isAriadneNativeOperationKnown(const std::string& op)\n"
        "{\n"
        "    return findAriadneNativeOp(op) != nullptr\n"
        "        || findAriadneInternalOp(op) != nullptr\n"
        "        || familyHasOp(op);\n"
        "}"
    )
    assert canonical in source
    native_path.write_text(
        source.replace(
            canonical,
            "static bool isAriadneNativeOperationKnown(const std::string& op)\n"
            "{\n"
            "    (void)op;\n"
            "    return true;\n"
            "}",
            1,
        ),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "isAriadneNativeOperationKnown" in failures[0].detail


def test_duplicate_cpp_constant_declarations_block_source_resolution(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    family_path = (
        root / "src" / "Ariadne.AcadNative" / "families" / "w6_dynblk_handlers.inc"
    )
    source = family_path.read_text(encoding="utf-8")
    declaration = (
        'static const char* const kW6dOpDynSetProperty = "write.dynblock.property";'
    )
    assert declaration in source
    family_path.write_text(
        source.replace(declaration, declaration + "\n" + declaration, 1),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "duplicate" in failures[0].detail
    assert "kW6dOpDynSetProperty" in failures[0].detail


def test_later_local_cpp_constant_cannot_override_file_scope_hasop_constant(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    family_path = (
        root / "src" / "Ariadne.AcadNative" / "families" / "w6_dynblk_handlers.inc"
    )
    source = family_path.read_text(encoding="utf-8")
    dispatch_open = (
        "static bool w6dynblkDispatch(const std::string& op, "
        "const AriadneJobCtx& ctx, std::ostringstream& r)\n{"
    )
    assert dispatch_open in source
    local = (
        '\n    static const char* const kW6dOpDynSetProperty = "ghost.local";'
    )
    family_path.write_text(
        source.replace(dispatch_open, dispatch_open + local, 1),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "duplicate" in failures[0].detail
    assert "kW6dOpDynSetProperty" in failures[0].detail


def test_preprocessor_disabled_hasop_term_is_not_inferred_as_live(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    family_path = (
        root / "src" / "Ariadne.AcadNative" / "families" / "w6_dynblk_handlers.inc"
    )
    source = family_path.read_text(encoding="utf-8")
    term = "        || op == kW6dOpDynSetProperty;"
    assert term in source
    family_path.write_text(
        source.replace(term, "#if 0\n" + term + "\n#endif", 1),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "unsupported preprocessor directive" in failures[0].detail


@pytest.mark.parametrize(
    ("table_name", "removed_row"),
    [
        ("kAriadneNativeOperationTable", '{ "inspect.database.summary", "objectdbx_database" },'),
        ("kAriadneInternalOperationTable", '{ "inspect.selection.monitor.registry", "live" },'),
    ],
)
def test_preprocessor_hidden_duplicate_operation_table_is_rejected(
    tmp_path: Path,
    table_name: str,
    removed_row: str,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    native_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = native_path.read_text(encoding="utf-8")
    declaration = f"static const AriadneOperationSpec {table_name}[] = {{"
    start = source.index(declaration)
    end = source.index("};", start) + 2
    canonical_table = source[start:end]
    assert removed_row in canonical_table
    live_table = canonical_table.replace(removed_row, "", 1)
    mutated = (
        source[:start]
        + "#if 0\n"
        + canonical_table
        + "\n#endif\n"
        + live_table
        + source[end:]
    )
    native_path.write_text(mutated, encoding="utf-8")

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "operation authority" in failures[0].detail


def test_conditional_family_include_cannot_hide_an_unknown_live_source(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    native_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = native_path.read_text(encoding="utf-8")
    include = '#include "families/w6_dynblk_handlers.inc"'
    assert include in source
    native_path.write_text(
        source.replace(
            include,
            "#if 0\n"
            + include
            + '\n#endif\n#include "families/hidden_dynblk.inc"',
            1,
        ),
        encoding="utf-8",
    )
    canonical_path = (
        root / "src" / "Ariadne.AcadNative" / "families" / "w6_dynblk_handlers.inc"
    )
    hidden_path = canonical_path.with_name("hidden_dynblk.inc")
    hidden_source = canonical_path.read_text(encoding="utf-8")
    hidden_path.write_text(
        hidden_source.replace("write.dynblock.property", "ghost.dynblock.property"),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "operation authority" in failures[0].detail


@pytest.mark.parametrize(
    "replacement",
    [
        "",
        "#define ARIADNE_M08D_BREP 0",
        "#undef ARIADNE_M08D_BREP",
    ],
)
def test_brep_guard_requires_one_unconditional_enabled_definition(
    tmp_path: Path,
    replacement: str,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    family_path = (
        root / "src" / "Ariadne.AcadNative" / "families" / "m08d_handlers.inc"
    )
    source = family_path.read_text(encoding="utf-8")
    definition = "#define ARIADNE_M08D_BREP 1"
    assert definition in source
    family_path.write_text(
        source.replace(definition, replacement, 1),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "ARIADNE_M08D_BREP" in failures[0].detail


def test_legacy_operation_tables_match_actual_top_level_dispatch_branches(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    native_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = native_path.read_text(encoding="utf-8")
    branch = 'else if (op == "inspect.selection.monitor.registry") {'
    assert branch in source
    native_path.write_text(
        source.replace(
            branch,
            'else if (op == "ghost.selection.monitor.registry") {',
            1,
        ),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_LEGACY_DISPATCH_MISMATCH"
    ]
    assert len(failures) == 1
    assert "inspect.selection.monitor.registry" in failures[0].detail
    assert "ghost.selection.monitor.registry" in failures[0].detail


def test_legacy_dispatch_branch_must_have_a_reachable_handler_body(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    native_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = native_path.read_text(encoding="utf-8")
    branch = (
        'else if (op == "inspect.selection.monitor.registry") {\n'
        '        r << "\\\"result\\\":" << selectionMonitorRegistryJson(jobHostMode) << ","\n'
        '          << "\\\"status\\\":\\\"ok\\\"}";\n'
        "    }"
    )
    assert branch in source
    native_path.write_text(
        source.replace(
            branch,
            'else if (op == "inspect.selection.monitor.registry") {}',
            1,
        ),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_FAMILY_PARSE_FAILED"
    ]
    assert len(failures) == 1
    assert "empty legacy dispatch branch" in failures[0].detail


def test_public_admission_scope_cannot_widen_to_internal_operations(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    native_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = native_path.read_text(encoding="utf-8")
    public_case = (
        "case AriadneOperationAdmissionScope::PublicOnly:\n"
        "        return publicOperation;"
    )
    assert public_case in source
    native_path.write_text(
        source.replace(
            public_case,
            "case AriadneOperationAdmissionScope::PublicOnly:\n"
            "        return publicOperation || internalOperation;",
            1,
        ),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_ADMISSION_CONTRACT_MISMATCH"
    ]
    assert len(failures) == 1
    assert "PublicOnly" in failures[0].detail


def test_native_entrypoints_are_bound_to_their_exact_admission_scopes(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    native_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = native_path.read_text(encoding="utf-8")
    public_call = (
        "ariadneNativeJobWithScope(AriadneOperationAdmissionScope::PublicOnly);"
    )
    assert public_call in source
    native_path.write_text(
        source.replace(
            public_call,
            "ariadneNativeJobWithScope("
            "AriadneOperationAdmissionScope::PublicOrDiagnosticInternal);",
            1,
        ),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_ADMISSION_CONTRACT_MISMATCH"
    ]
    assert len(failures) == 1
    assert "ariadneNativeJob" in failures[0].detail


def test_native_entrypoint_scope_must_be_the_actual_call_argument(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    native_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = native_path.read_text(encoding="utf-8")
    public_call = (
        "ariadneNativeJobWithScope(AriadneOperationAdmissionScope::PublicOnly);"
    )
    assert public_call in source
    native_path.write_text(
        source.replace(
            public_call,
            'const char* unusedScope = '
            '"AriadneOperationAdmissionScope::PublicOnly";\n'
            "    ariadneNativeJobWithScope("
            "static_cast<AriadneOperationAdmissionScope>(1));",
            1,
        ),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_ADMISSION_CONTRACT_MISMATCH"
    ]
    assert len(failures) == 1
    assert "ariadneNativeJob" in failures[0].detail


def test_native_entrypoint_must_call_the_admission_bound_target(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    native_path = root / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
    source = native_path.read_text(encoding="utf-8")
    public_call = (
        "ariadneNativeJobWithScope(AriadneOperationAdmissionScope::PublicOnly);"
    )
    assert public_call in source
    native_path.write_text(
        source.replace(
            public_call,
            "alwaysAdmit(AriadneOperationAdmissionScope::PublicOnly);",
            1,
        ),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure for failure in receipt.failures
        if failure.code == "NATIVE_ADMISSION_CONTRACT_MISMATCH"
    ]
    assert len(failures) == 1
    assert "ariadneNativeJob" in failures[0].detail


def test_missing_jsonschema_does_not_break_core_cadctl_import(
    tmp_path: Path,
) -> None:
    script = r"""
import importlib.abc
import json
import sys

class BlockJsonSchema(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "jsonschema" or fullname.startswith("jsonschema."):
            raise ImportError("jsonschema intentionally unavailable")
        return None

sys.meta_path.insert(0, BlockJsonSchema())
import cadctl

cad = cadctl.Cad(sys.argv[1])
registry = cad.registry_list()
status = cad.status(schema_version=2)
print(json.dumps({
    "registry_status": registry["status"],
    "projection_status": status["status"],
    "capability_status": status["capability"]["operation_registry"]["status"],
    "capability_error": status["capability"]["operation_registry"]["errors"][0]["code"],
}))
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(REPO), str(REPO / "tools")))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", script, str(REPO)],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result == {
        "registry_status": "ok",
        "projection_status": "PASS",
        "capability_status": "BLOCKED",
        "capability_error": "REGISTRY_SCHEMA_VALIDATION_UNAVAILABLE",
    }


def test_schema_cannot_silently_redefine_the_operation_status_vocabulary(tmp_path: Path) -> None:
    root = _copy_verification_fixture(tmp_path)
    schema_path = root / "schemas" / "operation_registry.v2.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["$defs"]["operation"]["properties"]["status"]["enum"][-1] = "banished"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    registry_path = root / "config" / "operations.v2.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    for operation in registry["operations"]:
        if operation["status"] == "blocked":
            operation["status"] = "banished"
    registry["totals"]["by_status"]["banished"] = registry["totals"]["by_status"].pop(
        "blocked"
    )
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    assert "REGISTRY_STATUS_VOCABULARY_MISMATCH" in {
        failure.code for failure in receipt.failures
    }


def test_malformed_registry_returns_a_typed_failure_instead_of_empty_pass(tmp_path: Path) -> None:
    root = _copy_verification_fixture(tmp_path)
    (root / "config" / "operations.v2.json").write_text("{", encoding="utf-8")

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    assert receipt.operation_count == 0
    assert receipt.status_histogram == {}
    assert {failure.code for failure in receipt.failures} == {"REGISTRY_PARSE_FAILED"}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda text: text.replace(
            "{", '{"schema":"synthetic.duplicate",', 1
        ),
        lambda text: text.replace(
            '"totals":', '"synthetic_non_finite":NaN,"totals":', 1
        ),
        lambda text: text.replace(
            '"totals":', '"synthetic_non_finite":Infinity,"totals":', 1
        ),
    ],
    ids=["duplicate-key", "nan", "infinity"],
)
def test_registry_json_is_strict(tmp_path: Path, mutate) -> None:
    root = _copy_verification_fixture(tmp_path)
    registry_path = root / "config" / "operations.v2.json"
    source = registry_path.read_text(encoding="utf-8-sig")
    registry_path.write_text(mutate(source), encoding="utf-8")

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    assert {failure.code for failure in receipt.failures} == {"REGISTRY_PARSE_FAILED"}


def test_declared_totals_must_match_the_observed_registry(tmp_path: Path) -> None:
    root = _copy_verification_fixture(tmp_path)
    registry_path = root / "config" / "operations.v2.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    registry["totals"]["operations"] += 1
    registry["totals"]["by_status"]["implemented"] += 1
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    receipt = verify_operation_registry(root)
    codes = {failure.code for failure in receipt.failures}

    assert receipt.verified is False
    assert "REGISTRY_OPERATION_TOTAL_MISMATCH" in codes
    assert "REGISTRY_STATUS_HISTOGRAM_MISMATCH" in codes


def test_v1_operations_must_remain_present_and_runnable(tmp_path: Path) -> None:
    root = _copy_verification_fixture(tmp_path)
    v1_path = root / "schemas" / "cad_job.schema.json"
    v1_schema = json.loads(v1_path.read_text(encoding="utf-8"))
    v1_schema["properties"]["operation"]["enum"].append("synthetic.v1.missing")
    v1_path.write_text(json.dumps(v1_schema), encoding="utf-8")

    registry_path = root / "config" / "operations.v2.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    existing_v1_id = v1_schema["properties"]["operation"]["enum"][0]
    existing_v1 = next(
        operation for operation in registry["operations"] if operation["id"] == existing_v1_id
    )
    previous_status = existing_v1["status"]
    assert previous_status in {"implemented", "wired"}
    existing_v1["status"] = "blocked"
    existing_v1["blocked_reason"] = "synthetic verifier probe"
    registry["totals"]["by_status"][previous_status] -= 1
    registry["totals"]["by_status"]["blocked"] += 1
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    receipt = verify_operation_registry(root)
    codes = {failure.code for failure in receipt.failures}

    assert receipt.verified is False
    assert receipt.v1_runnable_count < receipt.v1_operation_count
    assert "V1_EXTEND_ONLY_VIOLATION" in codes
    assert "V1_OPERATION_NOT_RUNNABLE" in codes


def test_native_catalog_ids_must_resolve_to_registry_classifications(tmp_path: Path) -> None:
    root = _copy_verification_fixture(tmp_path)
    catalog_path = root / "config" / "autocad_native_arx_operation_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    catalog["operations"][0]["op_id"] = "synthetic.catalog.orphan"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    assert "NATIVE_CATALOG_NOT_CLASSIFIED" in {
        failure.code for failure in receipt.failures
    }


def test_patch_vocabulary_targets_must_resolve_to_live_native_operations(tmp_path: Path) -> None:
    root = _copy_verification_fixture(tmp_path)
    patch_engine_path = root / "tools" / "patch_engine.py"
    source = patch_engine_path.read_text(encoding="utf-8")
    needle = '"create_line": "write.entity.line"'
    assert needle in source
    patch_engine_path.write_text(
        source.replace(needle, '"create_line": "synthetic.native.missing"', 1),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    assert "PATCH_NATIVE_VOCAB_DRIFT" in {failure.code for failure in receipt.failures}


def test_native_operations_must_be_classified_in_the_registry(tmp_path: Path) -> None:
    root = _copy_verification_fixture(tmp_path)
    family_path = (
        root
        / "src"
        / "Ariadne.AcadNative"
        / "families"
        / "m08c_handlers.inc"
    )
    source = family_path.read_text(encoding="utf-8")
    needle = 'return op == "infra.hostapp.get_services"'
    assert needle in source
    family_path.write_text(
        source.replace(
            needle,
            'return op == "synthetic.unclassified.native_op" || '
            'op == "infra.hostapp.get_services"',
            1,
        ),
        encoding="utf-8",
    )

    receipt = verify_operation_registry(root)

    assert receipt.verified is False
    failures = [
        failure
        for failure in receipt.failures
        if failure.code == "NATIVE_OPERATION_NOT_CLASSIFIED"
    ]
    assert len(failures) == 1
    assert "synthetic.unclassified.native_op" in failures[0].detail


def test_patch_vocabulary_static_parse_does_not_write_bytecode_into_router_home(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    monkeypatch.setattr(sys, "dont_write_bytecode", False)

    receipt = verify_operation_registry(root)

    assert receipt.verified is True
    assert list(root.rglob("*.pyc")) == []


def test_verifier_never_executes_router_python_or_mutates_process_import_state(
    tmp_path: Path,
) -> None:
    root = _copy_verification_fixture(tmp_path)
    marker = root / "TOP_LEVEL_EXECUTED"
    payload = (
        "\n__import__('pathlib').Path(" + repr(str(marker))
        + ").write_text('executed', encoding='utf-8')\n"
    )
    for relative in (
        "tools/reconcile_native_registry.py",
        "tools/patch_engine.py",
        "tools/patch_ops/entities.py",
    ):
        path = root / relative
        path.write_text(path.read_text(encoding="utf-8") + payload, encoding="utf-8")

    stdout_before = sys.stdout
    path_before = list(sys.path)
    modules_before = dict(sys.modules)
    bytecode_before = sys.dont_write_bytecode

    receipt = verify_operation_registry(root)

    assert receipt.failures == ()
    assert not marker.exists()
    assert sys.stdout is stdout_before
    assert sys.path == path_before
    assert sys.modules == modules_before
    assert sys.dont_write_bytecode is bytecode_before


def test_reconciliation_adapter_reads_patch_vocab_without_executing_router_python(
    tmp_path: Path,
) -> None:
    from tools import reconcile_native_registry

    root = _copy_verification_fixture(tmp_path)
    marker = root / "RECONCILE_TOP_LEVEL_EXECUTED"
    payload = (
        "\n__import__('pathlib').Path(" + repr(str(marker))
        + ").write_text('executed', encoding='utf-8')\n"
    )
    for relative in ("tools/patch_engine.py", "tools/patch_ops/entities.py"):
        path = root / relative
        path.write_text(path.read_text(encoding="utf-8") + payload, encoding="utf-8")

    vocabulary = reconcile_native_registry._load_external_vocab(router_home=root)

    assert not marker.exists()
    assert vocabulary["patch_engine.OP_REGISTRY_MAP"]["create_line"] == (
        "write.entity.line"
    )
    assert vocabulary["patch_ops.NATIVE_WRITE_OP_MAP"]["create_line"] == (
        "write.entity.line"
    )


def test_public_seam_works_outside_repo_with_only_tools_on_pythonpath(
    tmp_path: Path,
) -> None:
    script = """
import json
from pathlib import Path
from verification.operation_registry import verify_operation_registry

receipt = verify_operation_registry(Path(__import__('sys').argv[1]))
print(json.dumps({
    'verified': receipt.verified,
    'families': receipt.native_family_count,
    'internal': receipt.internal_native_operation_count,
    'failures': [failure.code for failure in receipt.failures],
}))
raise SystemExit(0)
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO / "tools")
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [sys.executable, "-c", script, str(REPO)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout) == {
        "verified": True,
        "families": 16,
        "internal": 6,
        "failures": [],
    }
