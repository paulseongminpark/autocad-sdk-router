"""Canonical operation execution receipt tests (no CAD runtime required)."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from operation_provenance import (  # noqa: E402
    ExecutionReceiptError,
    build_execution_receipt,
    parse_execution_receipt,
)


OUTER_SCHEMA = "ariadne.cadctl.run_operation.v1"
RECEIPT_SCHEMA = "ariadne.cadctl.operation_execution_receipt.v1"
BASELINE_SHA = "a" * 64
RESULT_SHA = "b" * 64
NATIVE_RESULT_SHA = "c" * 64


def _valid_facts() -> dict[str, object]:
    return {
        "authorized_operation": "modify.entity.common",
        "authorized_write_mode": "write_copy",
        "executed": True,
        "reported_status": "ok",
        "executed_operation": "modify.entity.common",
        "executed_write_mode": "write_copy",
        "router_input_path": r"C:\stage\baseline.dwg",
        "original_path": r"C:\input\source.dwg",
        "original_sha256_before": BASELINE_SHA,
        "original_sha256_after": BASELINE_SHA,
        "baseline_path": r"C:\stage\baseline.dwg",
        "baseline_sha256": BASELINE_SHA,
        "result_path": r"C:\stage\result.dwg",
        "result_sha256": RESULT_SHA,
        "result_kind": "router_working_copy",
        "process_exit_code": 0,
        "engine_exit_code": 0,
        "engine_output_exit_code": 0,
        "native_status": "ok",
        "native_schema": "ariadne.autocad_native_job_result.v1",
        "native_engine": "native_objectarx",
        "native_operation": "modify.entity.common",
        "native_result_source": "file",
        "native_result_is_object": True,
        "native_error_code": None,
        "native_result_path": r"C:\router\runs\result.json",
        "native_result_sha256": NATIVE_RESULT_SHA,
        "router_status": "PASS",
        "router_schema": "ariadne.autocad_router_run.v2",
        "executed_route": "dwg_truth_autocad",
        "router_working_sha256_before": BASELINE_SHA,
        "router_working_sha256_after": RESULT_SHA,
        "timed_out": False,
        "launch_error": None,
        "baseline_sha256_after": BASELINE_SHA,
        "input_kind": "staged_copy",
        "save_command_issued": True,
    }


def _valid_receipt(**updates: object) -> dict[str, object]:
    facts = _valid_facts()
    facts.update(updates)
    return build_execution_receipt(**facts)


def _envelope(receipt: object, *, executed: bool = True, status: str = "ok") -> dict:
    return {
        "schema": OUTER_SCHEMA,
        "executed": executed,
        "status": status,
        "execution_receipt": receipt,
    }


def test_builder_parser_roundtrip_exposes_bound_artifacts() -> None:
    receipt = _valid_receipt()

    assert receipt["schema"] == RECEIPT_SCHEMA
    assert receipt["artifacts"]["baseline"]["unchanged"] is True
    assert receipt["artifacts"]["result"]["kind"] == "router_working_copy"
    parsed = parse_execution_receipt(_envelope(receipt))

    assert parsed is not None
    assert parsed.executed is True
    assert parsed.bound is True
    assert parsed.provenance_verified is True
    assert parsed.outcome_successful is True
    assert parsed.provenance_failure_codes == ()
    assert parsed.outcome_failure_codes == ()
    assert parsed.failure_codes == ()
    assert parsed.baseline is not None
    assert parsed.baseline.path == r"C:\stage\baseline.dwg"
    assert parsed.baseline.sha256 == BASELINE_SHA
    assert parsed.result is not None
    assert parsed.result.path == r"C:\stage\result.dwg"
    assert parsed.result.sha256 == RESULT_SHA
    assert parsed.require_bound_result() is parsed.result
    assert parsed.require_successful_result() is parsed.result


def test_managed_objectarx_result_contract_is_exactly_supported() -> None:
    receipt = _valid_receipt(
        native_schema="ariadne.autocad_sdk_job_result.v1",
        native_engine="managed_objectarx_active_document",
    )
    parsed = parse_execution_receipt(_envelope(receipt))

    assert parsed is not None
    assert parsed.bound is True
    assert parsed.outcome_successful is True
    assert parsed.failure_codes == ()


@pytest.mark.parametrize(
    ("updates", "failure_code", "match_name"),
    [
        (
            {"executed_operation": "modify.entity.transform"},
            "OPERATION_MISMATCH",
            "operation",
        ),
        (
            {"executed_write_mode": "read"},
            "WRITE_MODE_MISMATCH",
            "write_mode",
        ),
        (
            {"router_input_path": r"C:\stage\other.dwg"},
            "ROUTER_INPUT_BASELINE_MISMATCH",
            "router_input_to_baseline",
        ),
    ],
)
def test_authority_or_input_mismatch_fails_closed(
    updates: dict[str, object], failure_code: str, match_name: str
) -> None:
    raw = _valid_receipt(**updates)
    parsed = parse_execution_receipt(_envelope(raw, status="error"))

    assert raw["matches"][match_name] is False
    assert parsed is not None
    assert parsed.bound is False
    assert parsed.outcome_successful is False
    assert failure_code in parsed.failure_codes
    with pytest.raises(ExecutionReceiptError, match="RESULT_NOT_BOUND"):
        parsed.require_bound_result()


def test_missing_result_fails_closed() -> None:
    raw = _valid_receipt(result_path=None, result_sha256=None)
    parsed = parse_execution_receipt(_envelope(raw, status="partial"))

    assert raw["matches"]["result_present"] is False
    assert parsed is not None
    assert parsed.bound is False
    assert parsed.result is None
    assert "RESULT_MISSING" in parsed.failure_codes


@pytest.mark.parametrize(
    ("updates", "failure_code"),
    [
        ({"process_exit_code": 9}, "PROCESS_EXIT_NONZERO"),
        (
            {"engine_exit_code": -17, "engine_output_exit_code": -17},
            "ENGINE_EXIT_NONZERO",
        ),
    ],
)
def test_nonzero_process_or_engine_exit_fails_closed(
    updates: dict[str, object], failure_code: str
) -> None:
    raw = _valid_receipt(**updates)
    parsed = parse_execution_receipt(_envelope(raw, status="error"))

    assert parsed is not None
    assert parsed.bound is True
    assert parsed.outcome_successful is False
    assert failure_code in parsed.failure_codes
    assert parsed.require_bound_result() is parsed.result
    with pytest.raises(ExecutionReceiptError, match="OUTCOME_NOT_SUCCESSFUL"):
        parsed.require_successful_result()


@pytest.mark.parametrize(
    ("native_status", "failure_code"),
    [
        (None, "NATIVE_STATUS_MISSING"),
        ("UNRECOGNIZED_NATIVE_STATUS", "NATIVE_STATUS_UNKNOWN"),
    ],
)
def test_missing_or_unknown_native_status_never_binds_as_ok(
    native_status: str | None, failure_code: str
) -> None:
    raw = _valid_receipt(native_status=native_status)
    parsed = parse_execution_receipt(_envelope(raw, status="error"))

    assert raw["verification"]["bound"] is True
    assert raw["verification"]["outcome_successful"] is False
    assert parsed is not None
    assert parsed.bound is True
    assert parsed.outcome_successful is False
    assert failure_code in parsed.failure_codes
    assert parsed.require_bound_result() is parsed.result
    with pytest.raises(ExecutionReceiptError, match="OUTCOME_NOT_SUCCESSFUL"):
        parsed.require_successful_result()


def test_not_executed_receipt_supports_unresolved_write_authorization() -> None:
    raw = build_execution_receipt(
        authorized_operation="unknown.operation",
        authorized_write_mode=None,
        executed=False,
        reported_status="blocked",
        limitations=("operation was refused before write-mode resolution",),
    )
    parsed = parse_execution_receipt(
        _envelope(raw, executed=False, status="blocked")
    )

    assert raw["authorization"]["write_mode"] is None
    assert parsed is not None
    assert parsed.executed is False
    assert parsed.bound is False
    assert parsed.failure_codes == ("NOT_EXECUTED",)
    assert parsed.limitations == (
        "operation was refused before write-mode resolution",
    )
    with pytest.raises(ExecutionReceiptError, match="RESULT_NOT_BOUND"):
        parsed.require_bound_result()


def test_pre_dispatch_refusal_without_receipt_is_rejected() -> None:
    legacy = {
        "schema": OUTER_SCHEMA,
        "executed": False,
        "status": "blocked",
        "staged_result": r"C:\flat\must-not-be-read.dwg",
        "staged_result_sha256": RESULT_SHA,
    }

    with pytest.raises(ExecutionReceiptError) as exc_info:
        parse_execution_receipt(legacy)
    assert exc_info.value.code == "MISSING_EXECUTION_RECEIPT"


def test_flat_only_executed_envelope_is_rejected() -> None:
    flat_only = {
        "schema": OUTER_SCHEMA,
        "executed": True,
        "status": "ok",
        "staged_copy": r"C:\flat\baseline.dwg",
        "staged_copy_sha256": BASELINE_SHA,
        "staged_result": r"C:\flat\result.dwg",
        "staged_result_sha256": RESULT_SHA,
    }

    with pytest.raises(ExecutionReceiptError) as exc_info:
        parse_execution_receipt(flat_only)
    assert exc_info.value.code == "MISSING_EXECUTION_RECEIPT"


@pytest.mark.parametrize(
    ("field_path", "bad_value", "error_code"),
    [
        (("schema",), "ariadne.cadctl.operation_execution_receipt.v0", "INVALID_RECEIPT_SCHEMA"),
        (("execution", "executed"), 1, "INVALID_TYPE"),
        (("artifacts", "result", "sha256"), "B" * 64, "INVALID_HASH"),
        (("artifacts", "result", "path"), "relative\\result.dwg", "INVALID_PATH"),
    ],
)
def test_malformed_canonical_receipt_is_rejected(
    field_path: tuple[str, ...], bad_value: object, error_code: str
) -> None:
    raw = copy.deepcopy(_valid_receipt())
    target = raw
    for key in field_path[:-1]:
        target = target[key]
    target[field_path[-1]] = bad_value

    with pytest.raises(ExecutionReceiptError) as exc_info:
        parse_execution_receipt(_envelope(raw))
    assert exc_info.value.code == error_code


def test_malformed_outer_status_raises_typed_error() -> None:
    envelope = _envelope(_valid_receipt())
    envelope["status"] = []

    with pytest.raises(ExecutionReceiptError) as exc_info:
        parse_execution_receipt(envelope)
    assert exc_info.value.code == "INVALID_OUTER_STATUS"


def test_outer_status_cannot_promote_an_unbound_receipt() -> None:
    raw = _valid_receipt(executed_operation="different.operation")

    with pytest.raises(ExecutionReceiptError) as exc_info:
        parse_execution_receipt(_envelope(raw, status="ok"))
    assert exc_info.value.code == "OUTER_STATUS_OUTCOME_CONTRADICTION"


def test_provenance_and_outcome_failures_are_separate() -> None:
    outcome_only = _valid_receipt(native_status="error", reported_status="error")
    parsed = parse_execution_receipt(_envelope(outcome_only, status="error"))

    assert parsed is not None
    assert parsed.bound is True
    assert parsed.outcome_successful is False
    assert parsed.provenance_failure_codes == ()
    assert "NATIVE_STATUS_NOT_OK" in parsed.outcome_failure_codes
    assert parsed.require_bound_result() is parsed.result
    with pytest.raises(ExecutionReceiptError, match="OUTCOME_NOT_SUCCESSFUL"):
        parsed.require_successful_result()


@pytest.mark.parametrize(
    ("updates", "failure_code", "is_provenance_failure"),
    [
        ({"baseline_sha256_after": "c" * 64}, "BASELINE_CHANGED", True),
        (
            {"router_working_sha256_before": "c" * 64},
            "ROUTER_WORKING_BEFORE_BASELINE_MISMATCH",
            True,
        ),
        (
            {"router_working_sha256_after": "c" * 64},
            "ROUTER_WORKING_AFTER_RESULT_MISMATCH",
            True,
        ),
        (
            {
                "result_path": r"C:\stage\baseline.dwg",
                "result_sha256": BASELINE_SHA,
                "router_working_sha256_after": BASELINE_SHA,
            },
            "RESULT_BASELINE_PATH_COLLISION",
            True,
        ),
        ({"input_kind": None}, "INPUT_KIND_MISSING", True),
        (
            {"input_kind": "active_document"},
            "INPUT_KIND_NOT_STAGED_COPY",
            True,
        ),
        (
            {"router_schema": "ariadne.autocad_router_run.v1"},
            "ROUTER_SCHEMA_MISMATCH",
            True,
        ),
        (
            {"executed_route": "unrelated_route"},
            "ROUTER_ROUTE_MISMATCH",
            True,
        ),
        ({"router_status": "ok"}, "ROUTER_STATUS_NOT_PASS", False),
        (
            {"save_command_issued": None},
            "SAVE_COMMAND_OBSERVATION_MISSING",
            False,
        ),
    ],
)
def test_boundary_observation_failures_are_classified(
    updates: dict[str, object], failure_code: str, is_provenance_failure: bool
) -> None:
    raw = _valid_receipt(**updates)
    parsed = parse_execution_receipt(_envelope(raw, status="error"))

    assert parsed is not None
    expected_group = (
        parsed.provenance_failure_codes
        if is_provenance_failure
        else parsed.outcome_failure_codes
    )
    assert failure_code in expected_group
    assert parsed.bound is (not is_provenance_failure)
    assert parsed.outcome_successful is False


def test_external_containment_failure_is_owned_by_canonical_builder() -> None:
    raw = _valid_receipt(
        additional_failure_codes=("RESULT_OUTSIDE_STAGING", "RESULT_REPARSE_POINT")
    )
    parsed = parse_execution_receipt(_envelope(raw, status="error"))

    assert raw["verification"]["additional_failure_codes"] == [
        "RESULT_OUTSIDE_STAGING",
        "RESULT_REPARSE_POINT",
    ]
    assert parsed is not None
    assert parsed.bound is False
    assert parsed.provenance_failure_codes == (
        "RESULT_OUTSIDE_STAGING",
        "RESULT_REPARSE_POINT",
    )


def test_receipt_binds_the_real_router_schema_status_and_route() -> None:
    raw = _valid_receipt(
        router_schema="ariadne.autocad_router_run.v2",
        router_status="PASS",
        executed_route="dwg_truth_autocad",
    )
    parsed = parse_execution_receipt(_envelope(raw))

    assert parsed is not None
    assert parsed.provenance_verified is True
    assert parsed.outcome_successful is True
