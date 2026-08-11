"""Current-status projection keeps capability, proof, and runtime truth apart."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from verification import current_status  # noqa: E402


HEAD = "a" * 40


def _registry_receipt(*, verified: bool = True) -> dict[str, object]:
    return {
        "verified": verified,
        "registry_schema": "ariadne.operations_registry.v2",
        "operation_count": 7,
        "status_histogram": {"implemented": 7},
        "failures": [] if verified else [{"code": "REGISTRY_DRIFT"}],
        "input_digests": {"config/operations.v2.json": "b" * 64},
        "input_set_sha256": "c" * 64,
        "snapshot_consistent": True,
    }


def _mcp_receipt(*, verified: bool = True) -> dict[str, object]:
    return {
        "schema": "cadagent.mcp_surface_verification.v1",
        "verification": "VERIFIED" if verified else "INVALID",
        "tool_count": 19,
        "tool_names": ["cad.status"],
        "failures": [] if verified else [{"code": "SURFACE_DRIFT"}],
    }


def _native_receipt(*, valid: bool = True) -> dict[str, object]:
    return {
        "path": "prebuilt/2027/native_deployment_manifest.json",
        "sha256": "d" * 64,
        "valid": valid,
        "checks": {"artifacts": valid},
        "errors": [] if valid else ["manifest source-tree digest"],
        "artifact_paths": ["one", "two", "three"] if valid else [],
    }


def _revision_binding_receipt(*, verified: bool = True) -> dict[str, object]:
    return {
        "schema": "ariadne.cad_os.revision_path_binding.v1",
        "status": "PASS" if verified else "BLOCKED",
        "repo_root": "test",
        "expected_revision": HEAD,
        "path_count": 1,
        "matched_count": 1 if verified else 0,
        "bindings": [],
        "errors": (
            []
            if verified
            else [{"code": "REVISION_BLOB_DIGEST_MISMATCH"}]
        ),
    }


def _valid_historical_report() -> dict[str, object]:
    return {
        "schema": "ariadne.autocad_router_status.v2",
        "timestamp": "2020-01-01T00:00:00Z",
        "status": "ALL_AVAILABLE",
        "route_count": 1,
        "available_count": 1,
        "routes": [
            {
                "route": "dwg_truth_autocad",
                "available": True,
                "engine": "arx",
            }
        ],
    }


def _build(
    router: Path,
    *,
    expected_revision: str | None = None,
    registry: object | None = None,
    mcp: object | None = None,
    native: object | None = None,
    checkout: object | None = None,
    checkout_end: object | None = None,
    observation: object | None = None,
    revision_binding: object | None = None,
    bind_mcp_context: bool = True,
) -> dict[str, object]:
    registry_value = _registry_receipt() if registry is None else registry
    mcp_value = _mcp_receipt() if mcp is None else mcp
    native_value = _native_receipt() if native is None else native
    checkout_value = (
        {
            "schema": "ariadne.cad_os.checkout_verification.v1",
            "status": "PASS",
            "repo_root": str(router),
            "expected_head": expected_revision,
            "head": expected_revision,
            "clean": True,
            "errors": [],
        }
        if checkout is None
        else checkout
    )
    checkout_end_value = checkout_value if checkout_end is None else checkout_end
    checkout_values = iter((checkout_value, checkout_end_value))
    observation_value = (
        {
            "schema": "ariadne.cad_os.native_source_checkout_observation.v1",
            "status": "PASS",
            "repo_root": str(router),
            "head": HEAD,
            "clean": True,
            "errors": [],
        }
        if observation is None
        else observation
    )
    revision_binding_value = (
        _revision_binding_receipt()
        if revision_binding is None
        else revision_binding
    )

    def return_or_raise(value, *args):
        if isinstance(value, Exception):
            raise value
        if callable(value):
            return value(*args)
        return value

    with (
        patch.object(
            current_status,
            "verify_operation_registry",
            side_effect=lambda _root: return_or_raise(registry_value, _root),
        ),
        patch.object(
            current_status,
            "verify_declared_tool_surface",
            side_effect=lambda _definitions, _dispatch: return_or_raise(
                mcp_value, _definitions, _dispatch
            ),
        ) as mcp_mock,
        patch.object(
            current_status,
            "verify_committed_deployment",
            side_effect=lambda _root, _deploy: return_or_raise(
                native_value, _root, _deploy
            ),
        ),
        patch.object(
            current_status,
            "verify_checkout",
            side_effect=lambda _root, _head, require_clean=True: return_or_raise(
                next(checkout_values), _root, _head, require_clean
            ),
        ) as checkout_mock,
        patch.object(
            current_status,
            "observe_native_source_checkout",
            side_effect=lambda _root: return_or_raise(observation_value, _root),
        ) as observation_mock,
        patch.object(
            current_status,
            "verify_paths_at_revision",
            side_effect=lambda _root, _revision, _digests: return_or_raise(
                revision_binding_value, _root, _revision, _digests
            ),
        ) as revision_binding_mock,
    ):
        result = current_status.build_current_status(
            router,
            expected_revision=expected_revision,
            mcp_definitions=[] if bind_mcp_context else None,
            mcp_dispatch={} if bind_mcp_context else None,
        )
    result["_test_checkout_calls"] = checkout_mock.call_count
    result["_test_observation_calls"] = observation_mock.call_count
    result["_test_mcp_verifier_calls"] = mcp_mock.call_count
    result["_test_revision_binding_calls"] = revision_binding_mock.call_count
    return result


def test_missing_historical_report_does_not_block_projection(tmp_path: Path) -> None:
    result = _build(tmp_path)

    assert result["status"] == "PASS"
    assert result["status_scope"] == "projection_assembly_only"
    assert result["historical_snapshot"]["status"] == "BLOCKED"
    assert result["historical_snapshot"]["observation"] == "MISSING"
    assert result["compatibility"]["routes"] == []
    assert result["runtime_observation"]["status"] == "BLOCKED"
    assert (
        result["runtime_observation"]["reason_code"]
        == "LIVE_OBSERVATION_NOT_RUN"
    )
    assert result["runtime_observation"]["availability"] == "UNKNOWN"


def test_malformed_historical_report_is_typed_not_raised(tmp_path: Path) -> None:
    report = tmp_path / "reports" / "autocad_router_status_latest.json"
    report.parent.mkdir(parents=True)
    report.write_text("{not json", encoding="utf-8")

    result = _build(tmp_path)

    historical = result["historical_snapshot"]
    assert historical["status"] == "BLOCKED"
    assert historical["observation"] == "MALFORMED"
    assert historical["source"]["path"] == str(report.resolve())
    assert historical["source"]["sha256"] is not None


def test_parseable_arbitrary_json_is_not_a_valid_historical_artifact(
    tmp_path: Path,
) -> None:
    report = tmp_path / "reports" / "autocad_router_status_latest.json"
    report.parent.mkdir(parents=True)
    report.write_text("{}", encoding="utf-8")

    result = _build(tmp_path)

    historical = result["historical_snapshot"]
    assert historical["status"] == "BLOCKED"
    assert historical["observation"] == "INVALID"
    assert historical["status_scope"] == "artifact_validation_only"
    assert {error["code"] for error in historical["errors"]} >= {
        "HISTORICAL_SCHEMA_INVALID",
        "HISTORICAL_ROUTES_INVALID",
        "HISTORICAL_ROUTE_COUNT_INVALID",
        "HISTORICAL_AVAILABLE_COUNT_INVALID",
    }


def test_unknown_historical_schema_cannot_publish_compatibility_routes(
    tmp_path: Path,
) -> None:
    report = tmp_path / "reports" / "autocad_router_status_latest.json"
    report.parent.mkdir(parents=True)
    unsupported = _valid_historical_report()
    unsupported["schema"] = "completely.unrelated.v999"
    report.write_text(json.dumps(unsupported), encoding="utf-8")

    result = _build(tmp_path)

    historical = result["historical_snapshot"]
    assert historical["status"] == "BLOCKED"
    assert historical["observation"] == "INVALID"
    assert historical["routes"] == []
    assert {error["code"] for error in historical["errors"]} >= {
        "HISTORICAL_SCHEMA_UNSUPPORTED"
    }
    assert result["compatibility"]["route_count"] == 0


def test_valid_historical_report_pass_is_only_artifact_validation(
    tmp_path: Path,
) -> None:
    report = tmp_path / "reports" / "autocad_router_status_latest.json"
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps(_valid_historical_report()), encoding="utf-8")

    result = _build(tmp_path)

    historical = result["historical_snapshot"]
    assert historical["status"] == "PASS"
    assert historical["observation"] == "PRESENT"
    assert historical["status_scope"] == "artifact_validation_only"
    assert historical["classification"] == "HISTORICAL_UNBOUND"
    assert historical["bound_to_current_revision"] is False


def test_unanchored_checkout_is_observed_but_never_self_verified(tmp_path: Path) -> None:
    result = _build(tmp_path, expected_revision=None)

    anchor = result["anchor"]
    assert anchor["status"] == "BLOCKED"
    assert anchor["verification"] == "UNKNOWN"
    assert anchor["reason_code"] == "EXPECTED_REVISION_NOT_BOUND"
    assert anchor["observed_revision"] == HEAD
    assert result["_test_checkout_calls"] == 0
    assert result["_test_observation_calls"] == 1


def test_clean_checkout_is_verified_only_against_supplied_revision(tmp_path: Path) -> None:
    result = _build(tmp_path, expected_revision=HEAD)

    anchor = result["anchor"]
    assert anchor["status"] == "PASS"
    assert anchor["verification"] == "VERIFIED"
    assert anchor["expected_revision"] == HEAD
    assert anchor["observed_revision"] == HEAD
    assert anchor["boundary_consistent"] is True
    assert result["_test_checkout_calls"] == 2
    assert result["_test_observation_calls"] == 0


def test_dirty_checkout_is_blocked_without_hiding_observed_head(tmp_path: Path) -> None:
    dirty = {
        "schema": "ariadne.cad_os.checkout_verification.v1",
        "status": "BLOCKED",
        "repo_root": str(tmp_path),
        "expected_head": HEAD,
        "head": HEAD,
        "clean": False,
        "errors": [{"code": "WORKTREE_DIRTY"}],
    }

    result = _build(tmp_path, expected_revision=HEAD, checkout=dirty)

    anchor = result["anchor"]
    assert anchor["status"] == "BLOCKED"
    assert anchor["verification"] == "BLOCKED"
    assert anchor["observed_revision"] == HEAD
    assert anchor["clean"] is False
    assert result["_test_checkout_calls"] == 2


def test_anchor_is_revoked_when_checkout_changes_during_projection(
    tmp_path: Path,
) -> None:
    dirty_end = {
        "schema": "ariadne.cad_os.checkout_verification.v1",
        "status": "BLOCKED",
        "repo_root": str(tmp_path),
        "expected_head": HEAD,
        "head": HEAD,
        "clean": False,
        "errors": [{"code": "WORKTREE_DIRTY"}],
    }

    result = _build(
        tmp_path,
        expected_revision=HEAD,
        checkout_end=dirty_end,
    )

    anchor = result["anchor"]
    assert anchor["status"] == "BLOCKED"
    assert anchor["verification"] == "BLOCKED"
    assert anchor["reason_code"] == "CHECKOUT_CHANGED_DURING_PROJECTION"
    assert anchor["boundary_consistent"] is False
    assert anchor["projection_receipts"]["start"]["status"] == "PASS"
    assert anchor["projection_receipts"]["end"]["clean"] is False
    assert anchor["errors"][0]["code"] == "CHECKOUT_CHANGED_DURING_PROJECTION"
    assert result["capability"]["operation_registry"]["status"] == "PASS"
    assert result["_test_checkout_calls"] == 2


def test_registry_mutation_cannot_keep_the_starting_anchor(tmp_path: Path) -> None:
    tracked_registry = tmp_path / "config" / "operations.v2.json"
    tracked_registry.parent.mkdir(parents=True)
    tracked_registry.write_text("committed bytes", encoding="utf-8")

    def checkout_receipt(_root, expected_head, _require_clean):
        clean = tracked_registry.read_text(encoding="utf-8") == "committed bytes"
        return {
            "schema": "ariadne.cad_os.checkout_verification.v1",
            "status": "PASS" if clean else "BLOCKED",
            "repo_root": str(tmp_path),
            "expected_head": expected_head,
            "head": expected_head,
            "clean": clean,
            "errors": [] if clean else [{"code": "WORKTREE_DIRTY"}],
        }

    def mutating_registry_verifier(_root):
        tracked_registry.write_text("mutated bytes", encoding="utf-8")
        return _registry_receipt()

    result = _build(
        tmp_path,
        expected_revision=HEAD,
        registry=mutating_registry_verifier,
        checkout=checkout_receipt,
    )

    assert result["anchor"]["reason_code"] == "CHECKOUT_CHANGED_DURING_PROJECTION"
    assert result["anchor"]["status"] == "BLOCKED"
    assert result["capability"]["operation_registry"]["receipt"]["verified"] is True


def test_registry_receipt_must_bind_to_expected_revision(tmp_path: Path) -> None:
    result = _build(
        tmp_path,
        expected_revision=HEAD,
        revision_binding=_revision_binding_receipt(verified=False),
    )

    registry = result["capability"]["operation_registry"]
    assert result["anchor"]["status"] == "PASS"
    assert result["anchor"]["boundary_consistent"] is True
    assert registry["status"] == "BLOCKED"
    assert registry["verification"] == "BLOCKED"
    assert registry["reason_code"] == "RECEIPT_NOT_BOUND_TO_EXPECTED_REVISION"
    assert registry["receipt"]["verified"] is True
    assert registry["revision_binding"]["status"] == "BLOCKED"
    assert result["_test_revision_binding_calls"] == 1


def test_registry_aba_bytes_fail_real_revision_binding(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Test"],
        check=True,
    )
    registry_path = tmp_path / "config" / "operations.v2.json"
    registry_path.parent.mkdir(parents=True)
    committed = b"committed registry bytes\n"
    mutated = b"mutated but restored bytes\n"
    registry_path.write_bytes(committed)
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "config/operations.v2.json"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-qm", "fixture"],
        check=True,
    )
    head = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    anchor_receipt = {
        "schema": "ariadne.cad_os.checkout_verification.v1",
        "status": "PASS",
        "repo_root": str(tmp_path),
        "expected_head": head,
        "head": head,
        "clean": True,
        "errors": [],
    }

    def aba_registry_verifier(_root):
        registry_path.write_bytes(mutated)
        receipt = _registry_receipt()
        receipt["input_digests"] = {
            "config/operations.v2.json": hashlib.sha256(mutated).hexdigest()
        }
        registry_path.write_bytes(committed)
        return receipt

    with (
        patch.object(
            current_status,
            "verify_operation_registry",
            side_effect=aba_registry_verifier,
        ),
        patch.object(
            current_status,
            "verify_declared_tool_surface",
            return_value=_mcp_receipt(),
        ),
        patch.object(
            current_status,
            "verify_committed_deployment",
            return_value=_native_receipt(),
        ),
        patch.object(
            current_status,
            "verify_checkout",
            return_value=anchor_receipt,
        ),
    ):
        result = current_status.build_current_status(
            tmp_path,
            expected_revision=head,
            mcp_definitions=[],
            mcp_dispatch={},
        )

    assert result["anchor"]["status"] == "PASS"
    assert result["anchor"]["boundary_consistent"] is True
    registry = result["capability"]["operation_registry"]
    assert registry["status"] == "BLOCKED"
    assert registry["reason_code"] == "RECEIPT_NOT_BOUND_TO_EXPECTED_REVISION"
    assert registry["revision_binding"]["errors"][0]["code"] == (
        "REVISION_BLOB_DIGEST_MISMATCH"
    )


def test_final_checkout_verifier_error_revokes_starting_anchor(tmp_path: Path) -> None:
    result = _build(
        tmp_path,
        expected_revision=HEAD,
        checkout_end=RuntimeError("final checkout unavailable"),
    )

    anchor = result["anchor"]
    assert anchor["status"] == "BLOCKED"
    assert anchor["verification"] == "UNKNOWN"
    assert anchor["reason_code"] == "CHECKOUT_CHANGED_DURING_PROJECTION"
    assert anchor["projection_receipts"]["start"]["status"] == "PASS"
    assert anchor["projection_receipts"]["end"] is None
    assert any(
        error["code"] == "CHECKOUT_VERIFICATION_FAILED"
        for error in anchor["errors"]
    )


def test_capability_and_native_proof_are_independent(tmp_path: Path) -> None:
    result = _build(tmp_path, native=_native_receipt(valid=False))

    assert result["capability"]["operation_registry"]["status"] == "PASS"
    assert result["capability"]["mcp_surface"]["status"] == "PASS"
    assert (
        result["capability"]["operation_registry"]["source"]["sha256"]
        == "b" * 64
    )
    assert (
        result["capability"]["mcp_surface"]["source"]["bound_to_source_files"]
        is False
    )
    assert result["proof"]["committed_native"]["status"] == "BLOCKED"
    assert (
        result["proof"]["committed_native"]["source"]["sha256"] == "d" * 64
    )
    assert "overall_status" not in result
    assert "ready" not in result


def test_native_proof_does_not_imply_revision_bound_ci_proof(tmp_path: Path) -> None:
    result = _build(tmp_path, native=_native_receipt(valid=True))

    assert result["proof"]["committed_native"]["status"] == "PASS"
    assert result["proof"]["ci"]["status"] == "BLOCKED"
    assert result["proof"]["ci"]["verification"] == "UNKNOWN"
    assert result["proof"]["ci"]["reason_code"] == "CI_PROOF_NOT_BOUND"
    assert result["proof"]["ci"]["source"] is None


def test_stale_legacy_availability_never_becomes_runtime_truth(tmp_path: Path) -> None:
    report = tmp_path / "reports" / "autocad_router_status_latest.json"
    report.parent.mkdir(parents=True)
    report.write_text(
        json.dumps(
            {
                "schema": "ariadne.autocad_router_status.v2",
                "timestamp": "2020-01-01T00:00:00Z",
                "status": "ALL_AVAILABLE",
                "route_count": 1,
                "available_count": 1,
                "native_modules": {"status": "PASS"},
                "routes": [
                    {"route": "dwg_truth_autocad", "available": True, "engine": "arx"}
                ],
            }
        ),
        encoding="utf-8",
    )

    result = _build(tmp_path)

    historical = result["historical_snapshot"]
    assert historical["classification"] == "HISTORICAL_UNBOUND"
    assert historical["bound_to_current_revision"] is False
    assert result["runtime_observation"]["availability"] == "UNKNOWN"
    assert result["compatibility"]["available_count"] == 1
    assert result["compatibility"]["evidence_class"] == "historical_unbound"
    assert "native_available" not in result


def test_verifier_exceptions_are_contained_in_their_own_sections(tmp_path: Path) -> None:
    result = _build(
        tmp_path,
        registry=RuntimeError("registry boom"),
        mcp=ValueError("mcp boom"),
        native=OSError("native boom"),
        observation=RuntimeError("git boom"),
    )

    assert result["status"] == "PASS"
    assert result["status_scope"] == "projection_assembly_only"
    assert result["anchor"]["verification"] == "UNKNOWN"
    assert result["capability"]["operation_registry"]["status"] == "BLOCKED"
    assert result["capability"]["mcp_surface"]["status"] == "BLOCKED"
    assert result["proof"]["committed_native"]["status"] == "BLOCKED"
    for section in (
        result["anchor"],
        result["capability"]["operation_registry"],
        result["capability"]["mcp_surface"],
        result["proof"]["committed_native"],
    ):
        assert section["errors"]
        assert "RuntimeError(" not in json.dumps(section)


def test_unbound_mcp_context_never_executes_target_module(tmp_path: Path) -> None:
    target = tmp_path / "tools" / "cadagent_mcp.py"
    target.parent.mkdir(parents=True)
    target.write_text("raise RuntimeError('TARGET MODULE EXECUTED')\n", encoding="utf-8")

    result = _build(tmp_path, bind_mcp_context=False)

    mcp = result["capability"]["mcp_surface"]
    assert mcp["status"] == "BLOCKED"
    assert mcp["verification"] == "UNKNOWN"
    assert mcp["errors"][0]["code"] == "MCP_SURFACE_CONTEXT_NOT_BOUND"
    assert result["_test_mcp_verifier_calls"] == 0


def test_historical_string_availability_invalidates_artifact(tmp_path: Path) -> None:
    report = tmp_path / "reports" / "autocad_router_status_latest.json"
    report.parent.mkdir(parents=True)
    report.write_text(
        json.dumps(
            {
                "schema": "ariadne.autocad_router_status.v2",
                "route_count": 1,
                "available_count": 0,
                "routes": [
                    {
                        "route": "dwg_truth_autocad",
                        "available": "false",
                        "engine": "arx",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = _build(tmp_path)

    assert result["historical_snapshot"]["status"] == "BLOCKED"
    assert result["historical_snapshot"]["observation"] == "INVALID"
    assert result["historical_snapshot"]["routes"] == []
    assert result["compatibility"]["available_count"] == 0


def test_historical_declared_counts_must_be_exact_non_bool_integers(
    tmp_path: Path,
) -> None:
    report = tmp_path / "reports" / "autocad_router_status_latest.json"
    report.parent.mkdir(parents=True)
    invalid = _valid_historical_report()
    invalid["route_count"] = True
    invalid["available_count"] = 0
    report.write_text(json.dumps(invalid), encoding="utf-8")

    result = _build(tmp_path)

    historical = result["historical_snapshot"]
    assert historical["status"] == "BLOCKED"
    assert historical["observation"] == "INVALID"
    assert {error["code"] for error in historical["errors"]} >= {
        "HISTORICAL_ROUTE_COUNT_INVALID",
        "HISTORICAL_AVAILABLE_COUNT_MISMATCH",
    }


def test_historical_route_engine_field_is_required_even_when_null_is_valid(
    tmp_path: Path,
) -> None:
    report = tmp_path / "reports" / "autocad_router_status_latest.json"
    report.parent.mkdir(parents=True)
    invalid = _valid_historical_report()
    del invalid["routes"][0]["engine"]
    report.write_text(json.dumps(invalid), encoding="utf-8")

    result = _build(tmp_path)

    historical = result["historical_snapshot"]
    assert historical["status"] == "BLOCKED"
    assert historical["observation"] == "INVALID"
    assert any(
        error["code"] == "HISTORICAL_ROUTE_ENGINE_INVALID"
        for error in historical["errors"]
    )
