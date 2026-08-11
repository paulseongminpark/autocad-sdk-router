"""Canonical, filesystem-free provenance for ``Cad.run_operation``.

This module owns the nested execution receipt shape.  Callers supply facts they
have already observed; this module only validates, compares, and serializes
those facts.  In particular, it never opens a path or imports a CAD runtime.
"""

from __future__ import annotations

import ntpath
import posixpath
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any


OUTER_SCHEMA = "ariadne.cadctl.run_operation.v1"
RECEIPT_SCHEMA = "ariadne.cadctl.operation_execution_receipt.v1"
ROUTER_SCHEMA = "ariadne.autocad_router_run.v2"
ROUTER_ROUTE = "dwg_truth_autocad"
NATIVE_SCHEMA = "ariadne.autocad_native_job_result.v1"
NATIVE_ENGINE = "native_objectarx"
MANAGED_SCHEMA = "ariadne.autocad_sdk_job_result.v1"
MANAGED_ENGINE = "managed_objectarx_active_document"
_RESULT_CONTRACTS = {
    (NATIVE_SCHEMA, NATIVE_ENGINE),
    (MANAGED_SCHEMA, MANAGED_ENGINE),
}

_HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
_FAILURE_CODE_RE = re.compile(r"[A-Z][A-Z0-9_]*\Z")
_KNOWN_STATUSES = {
    "ok",
    "not_found",
    "blocked",
    "not_implemented",
    "partial",
    "error",
    "unavailable",
}
_RESULT_KINDS = {"router_working_copy", "native_output"}


class ExecutionReceiptError(ValueError):
    """A canonical execution receipt is absent, malformed, or untrustworthy."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True, slots=True)
class ArtifactView:
    """Immutable path-and-digest view of one observed artifact."""

    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    """Immutable typed view of a validated canonical receipt."""

    executed: bool
    bound: bool
    provenance_verified: bool
    outcome_successful: bool
    baseline: ArtifactView | None
    result: ArtifactView | None
    provenance_failure_codes: tuple[str, ...]
    outcome_failure_codes: tuple[str, ...]
    failure_codes: tuple[str, ...]
    limitations: tuple[str, ...]

    def require_bound_result(self) -> ArtifactView:
        """Return the result only when every provenance check is bound."""

        if not self.bound or not self.provenance_verified or self.result is None:
            codes = ", ".join(self.failure_codes) or "RESULT_NOT_BOUND"
            raise ExecutionReceiptError(
                "RESULT_NOT_BOUND",
                f"canonical result is not provenance-bound ({codes})",
            )
        return self.result

    def require_successful_result(self) -> ArtifactView:
        """Return the result only when provenance and execution outcome pass."""

        result = self.require_bound_result()
        if not self.outcome_successful:
            codes = ", ".join(self.outcome_failure_codes) or "OUTCOME_NOT_SUCCESSFUL"
            raise ExecutionReceiptError(
                "OUTCOME_NOT_SUCCESSFUL",
                f"canonical result outcome is not successful ({codes})",
            )
        return result


def build_execution_receipt(
    *,
    authorized_operation: str,
    authorized_write_mode: str | None,
    executed: bool,
    reported_status: str | None,
    executed_operation: str | None = None,
    executed_write_mode: str | None = None,
    router_input_path: str | None = None,
    original_path: str | None = None,
    original_sha256_before: str | None = None,
    original_sha256_after: str | None = None,
    baseline_path: str | None = None,
    baseline_sha256: str | None = None,
    result_path: str | None = None,
    result_sha256: str | None = None,
    result_kind: str | None = None,
    process_exit_code: int | None = None,
    engine_exit_code: int | None = None,
    native_status: str | None = None,
    native_schema: str | None = None,
    native_engine: str | None = None,
    native_operation: str | None = None,
    native_result_source: str | None = None,
    native_result_is_object: bool | None = None,
    native_error_code: str | None = None,
    native_result_path: str | None = None,
    native_result_sha256: str | None = None,
    router_status: str | None = None,
    router_schema: str | None = None,
    executed_route: str | None = None,
    timed_out: bool | None = None,
    launch_error: str | None = None,
    engine_output_exit_code: int | None = None,
    baseline_sha256_after: str | None = None,
    input_kind: str | None = None,
    save_command_issued: bool | None = None,
    router_working_sha256_before: str | None = None,
    router_working_sha256_after: str | None = None,
    additional_failure_codes: Sequence[str] = (),
    limitations: Sequence[str] = (),
) -> dict[str, object]:
    """Build one canonical receipt from already-observed execution facts."""

    authorized_operation = _required_string(
        authorized_operation, "authorized_operation"
    )
    authorized_write_mode = _optional_string(
        authorized_write_mode, "authorized_write_mode"
    )
    executed = _required_bool(executed, "executed")
    reported_status = _optional_string(reported_status, "reported_status")
    executed_operation = _optional_string(
        executed_operation, "executed_operation"
    )
    executed_write_mode = _optional_string(
        executed_write_mode, "executed_write_mode"
    )
    router_input_path = _optional_path(router_input_path, "router_input_path")
    original_path = _optional_path(original_path, "original_path")
    baseline_path = _optional_path(baseline_path, "baseline_path")
    result_path = _optional_path(result_path, "result_path")
    result_kind = _optional_string(result_kind, "result_kind")

    original_sha256_before = _optional_hash(
        original_sha256_before, "original_sha256_before", canonicalize=True
    )
    original_sha256_after = _optional_hash(
        original_sha256_after, "original_sha256_after", canonicalize=True
    )
    baseline_sha256 = _optional_hash(
        baseline_sha256, "baseline_sha256", canonicalize=True
    )
    baseline_sha256_after = _optional_hash(
        baseline_sha256_after, "baseline_sha256_after", canonicalize=True
    )
    result_sha256 = _optional_hash(
        result_sha256, "result_sha256", canonicalize=True
    )
    router_working_sha256_before = _optional_hash(
        router_working_sha256_before,
        "router_working_sha256_before",
        canonicalize=True,
    )
    router_working_sha256_after = _optional_hash(
        router_working_sha256_after,
        "router_working_sha256_after",
        canonicalize=True,
    )

    process_exit_code = _optional_int(process_exit_code, "process_exit_code")
    engine_exit_code = _optional_int(engine_exit_code, "engine_exit_code")
    engine_output_exit_code = _optional_int(
        engine_output_exit_code, "engine_output_exit_code"
    )
    native_status = _optional_string(native_status, "native_status")
    native_schema = _optional_string(native_schema, "native_schema")
    native_engine = _optional_string(native_engine, "native_engine")
    native_operation = _optional_string(native_operation, "native_operation")
    native_result_source = _optional_string(
        native_result_source, "native_result_source"
    )
    native_result_is_object = _optional_bool(
        native_result_is_object, "native_result_is_object"
    )
    native_error_code = _optional_string(native_error_code, "native_error_code")
    native_result_path = _optional_path(native_result_path, "native_result_path")
    native_result_sha256 = _optional_hash(
        native_result_sha256, "native_result_sha256", canonicalize=True
    )
    router_status = _optional_string(router_status, "router_status")
    router_schema = _optional_string(router_schema, "router_schema")
    executed_route = _optional_string(executed_route, "executed_route")
    timed_out = _optional_bool(timed_out, "timed_out")
    launch_error = _optional_string(launch_error, "launch_error")
    input_kind = _optional_string(input_kind, "input_kind")
    save_command_issued = _optional_bool(
        save_command_issued, "save_command_issued"
    )
    external_failures = _failure_code_list(
        additional_failure_codes, "additional_failure_codes"
    )
    limitation_list = _string_list(limitations, "limitations")

    baseline_unchanged = _equal_if_present(
        baseline_sha256, baseline_sha256_after
    )
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "authorization": {
            "operation": authorized_operation,
            "write_mode": authorized_write_mode,
        },
        "execution": {
            "executed": executed,
            "operation": executed_operation,
            "write_mode": executed_write_mode,
            "router_input_path": router_input_path,
            "reported_status": reported_status,
            "router_status": router_status,
            "router_schema": router_schema,
            "executed_route": executed_route,
            "native_status": native_status,
            "native_schema": native_schema,
            "native_engine": native_engine,
            "native_operation": native_operation,
            "native_result_source": native_result_source,
            "native_result_is_object": native_result_is_object,
            "native_error_code": native_error_code,
            "native_result_path": native_result_path,
            "native_result_sha256": native_result_sha256,
            "process_exit_code": process_exit_code,
            "engine_exit_code": engine_exit_code,
            "engine_output_exit_code": engine_output_exit_code,
            "timed_out": timed_out,
            "launch_error": launch_error,
            "input_kind": input_kind,
            "save_command_issued": save_command_issued,
            "router_working_sha256_before": router_working_sha256_before,
            "router_working_sha256_after": router_working_sha256_after,
        },
        "artifacts": {
            "original": {
                "path": original_path,
                "sha256_before": original_sha256_before,
                "sha256_after": original_sha256_after,
            },
            "baseline": {
                "path": baseline_path,
                "sha256": baseline_sha256,
                "sha256_after": baseline_sha256_after,
                "unchanged": baseline_unchanged,
            },
            "result": {
                "path": result_path,
                "sha256": result_sha256,
                "kind": result_kind,
            },
        },
        "matches": {},
        "verification": {},
        "limitations": limitation_list,
    }
    receipt["matches"] = _expected_matches(receipt)
    provenance_failures, outcome_failures = _computed_failure_code_groups(receipt)
    provenance_failures = _stable_unique(
        [*provenance_failures, *external_failures]
    )
    outcome_failures = _stable_unique(outcome_failures)
    all_failures = [*provenance_failures, *outcome_failures]
    bound = executed and not provenance_failures
    outcome_successful = bound and not outcome_failures
    receipt["verification"] = {
        "bound": bound,
        "provenance_verified": bound,
        "outcome_successful": outcome_successful,
        "additional_failure_codes": external_failures,
        "provenance_failure_codes": provenance_failures,
        "outcome_failure_codes": outcome_failures,
        "failure_codes": all_failures,
    }
    return receipt


def parse_execution_receipt(
    envelope: Mapping[str, object],
) -> ExecutionReceipt:
    """Parse only the canonical nested receipt from a run-operation envelope.

    Every envelope, including a pre-dispatch refusal, must carry a valid
    canonical receipt. Flat compatibility aliases are never consulted.
    """

    if not isinstance(envelope, Mapping):
        raise ExecutionReceiptError("INVALID_ENVELOPE", "envelope must be a mapping")
    if envelope.get("schema") != OUTER_SCHEMA:
        raise ExecutionReceiptError(
            "INVALID_OUTER_SCHEMA", f"expected outer schema {OUTER_SCHEMA!r}"
        )
    outer_executed = envelope.get("executed")
    if type(outer_executed) is not bool:
        raise ExecutionReceiptError(
            "INVALID_OUTER_EXECUTED", "outer executed must be a boolean"
        )
    outer_status = envelope.get("status")
    if type(outer_status) is not str or outer_status not in _KNOWN_STATUSES:
        raise ExecutionReceiptError(
            "INVALID_OUTER_STATUS", "outer status must be a known status"
        )

    if "execution_receipt" not in envelope:
        raise ExecutionReceiptError(
            "MISSING_EXECUTION_RECEIPT",
            "envelope has no canonical execution_receipt",
        )

    raw = envelope["execution_receipt"]
    if not isinstance(raw, Mapping):
        raise ExecutionReceiptError(
            "MALFORMED_EXECUTION_RECEIPT", "execution_receipt must be a mapping"
        )
    receipt = _validate_receipt(raw)
    execution = raw["execution"]
    assert isinstance(execution, Mapping)
    if execution["executed"] is not outer_executed:
        raise ExecutionReceiptError(
            "EXECUTED_FLAG_MISMATCH",
            "outer executed disagrees with execution_receipt.execution.executed",
        )
    if receipt.outcome_successful and outer_status != "ok":
        raise ExecutionReceiptError(
            "OUTER_STATUS_OUTCOME_CONTRADICTION",
            "a successful execution outcome requires outer status ok",
        )
    if not receipt.outcome_successful and outer_status == "ok":
        raise ExecutionReceiptError(
            "OUTER_STATUS_OUTCOME_CONTRADICTION",
            "an unsuccessful execution outcome cannot be promoted to outer status ok",
        )
    return receipt


def _validate_receipt(raw: Mapping[str, object]) -> ExecutionReceipt:
    _expect_keys(
        raw,
        {
            "schema",
            "authorization",
            "execution",
            "artifacts",
            "matches",
            "verification",
            "limitations",
        },
        "execution_receipt",
    )
    if raw["schema"] != RECEIPT_SCHEMA:
        raise ExecutionReceiptError(
            "INVALID_RECEIPT_SCHEMA", f"expected receipt schema {RECEIPT_SCHEMA!r}"
        )

    authorization = _mapping(raw["authorization"], "authorization")
    _expect_keys(authorization, {"operation", "write_mode"}, "authorization")
    _required_string(authorization["operation"], "authorization.operation")
    _optional_string(authorization["write_mode"], "authorization.write_mode")

    execution = _mapping(raw["execution"], "execution")
    _expect_keys(
        execution,
        {
            "executed",
            "operation",
            "write_mode",
            "router_input_path",
            "reported_status",
            "router_status",
            "router_schema",
            "executed_route",
            "native_status",
            "native_schema",
            "native_engine",
            "native_operation",
            "native_result_source",
            "native_result_is_object",
            "native_error_code",
            "native_result_path",
            "native_result_sha256",
            "process_exit_code",
            "engine_exit_code",
            "engine_output_exit_code",
            "timed_out",
            "launch_error",
            "input_kind",
            "save_command_issued",
            "router_working_sha256_before",
            "router_working_sha256_after",
        },
        "execution",
    )
    _required_bool(execution["executed"], "execution.executed")
    for key in (
        "operation",
        "write_mode",
        "reported_status",
        "router_status",
        "native_status",
        "native_schema",
        "native_engine",
        "native_operation",
        "native_result_source",
        "native_error_code",
        "launch_error",
        "input_kind",
    ):
        _optional_string(execution[key], f"execution.{key}")
    _optional_path(execution["router_input_path"], "execution.router_input_path")
    _optional_path(execution["native_result_path"], "execution.native_result_path")
    for key in ("process_exit_code", "engine_exit_code", "engine_output_exit_code"):
        _optional_int(execution[key], f"execution.{key}")
    _optional_bool(execution["timed_out"], "execution.timed_out")
    _optional_bool(
        execution["save_command_issued"], "execution.save_command_issued"
    )
    _optional_bool(
        execution["native_result_is_object"],
        "execution.native_result_is_object",
    )
    for key in (
        "router_working_sha256_before",
        "router_working_sha256_after",
        "native_result_sha256",
    ):
        _optional_hash(execution[key], f"execution.{key}")

    artifacts = _mapping(raw["artifacts"], "artifacts")
    _expect_keys(artifacts, {"original", "baseline", "result"}, "artifacts")
    original = _mapping(artifacts["original"], "artifacts.original")
    baseline = _mapping(artifacts["baseline"], "artifacts.baseline")
    result = _mapping(artifacts["result"], "artifacts.result")
    _expect_keys(
        original, {"path", "sha256_before", "sha256_after"}, "artifacts.original"
    )
    _expect_keys(
        baseline,
        {"path", "sha256", "sha256_after", "unchanged"},
        "artifacts.baseline",
    )
    _expect_keys(result, {"path", "sha256", "kind"}, "artifacts.result")
    _optional_path(original["path"], "artifacts.original.path")
    _optional_path(baseline["path"], "artifacts.baseline.path")
    _optional_path(result["path"], "artifacts.result.path")
    _optional_string(result["kind"], "artifacts.result.kind")
    for owner, values, keys in (
        ("original", original, ("sha256_before", "sha256_after")),
        ("baseline", baseline, ("sha256", "sha256_after")),
        ("result", result, ("sha256",)),
    ):
        for key in keys:
            _optional_hash(values[key], f"artifacts.{owner}.{key}")
    _optional_bool(baseline["unchanged"], "artifacts.baseline.unchanged")
    if baseline["unchanged"] != _equal_if_present(
        baseline["sha256"], baseline["sha256_after"]
    ):
        raise ExecutionReceiptError(
            "INVALID_BASELINE_UNCHANGED",
            "artifacts.baseline.unchanged does not match its digests",
        )

    expected_matches = _expected_matches(raw)
    matches = _mapping(raw["matches"], "matches")
    _expect_keys(matches, set(expected_matches), "matches")
    if dict(matches) != expected_matches:
        raise ExecutionReceiptError(
            "INVALID_MATCHES", "matches do not equal the receipt's observed facts"
        )

    limitation_list = _string_list(raw["limitations"], "limitations", require_list=True)
    verification = _mapping(raw["verification"], "verification")
    _expect_keys(
        verification,
        {
            "bound",
            "provenance_verified",
            "outcome_successful",
            "additional_failure_codes",
            "provenance_failure_codes",
            "outcome_failure_codes",
            "failure_codes",
        },
        "verification",
    )
    bound = _required_bool(verification["bound"], "verification.bound")
    provenance_verified = _required_bool(
        verification["provenance_verified"],
        "verification.provenance_verified",
    )
    outcome_successful = _required_bool(
        verification["outcome_successful"],
        "verification.outcome_successful",
    )
    external_failures = _failure_code_list(
        verification["additional_failure_codes"],
        "verification.additional_failure_codes",
        require_list=True,
    )
    provenance_failures = _failure_code_list(
        verification["provenance_failure_codes"],
        "verification.provenance_failure_codes",
        require_list=True,
    )
    outcome_failures = _failure_code_list(
        verification["outcome_failure_codes"],
        "verification.outcome_failure_codes",
        require_list=True,
    )
    failures = _failure_code_list(
        verification["failure_codes"],
        "verification.failure_codes",
        require_list=True,
    )
    expected_provenance, expected_outcome = _computed_failure_code_groups(raw)
    expected_provenance = _stable_unique(
        [*expected_provenance, *external_failures]
    )
    expected_outcome = _stable_unique(expected_outcome)
    expected_failures = [*expected_provenance, *expected_outcome]
    expected_bound = bool(execution["executed"]) and not expected_provenance
    expected_outcome_successful = expected_bound and not expected_outcome
    if (
        provenance_failures != expected_provenance
        or outcome_failures != expected_outcome
        or failures != expected_failures
    ):
        raise ExecutionReceiptError(
            "INVALID_FAILURE_CODES",
            "verification.failure_codes do not match the observed facts",
        )
    if (
        bound is not expected_bound
        or provenance_verified is not expected_bound
        or outcome_successful is not expected_outcome_successful
    ):
        raise ExecutionReceiptError(
            "INVALID_VERIFICATION",
            "bound/provenance_verified do not match the observed facts",
        )

    return ExecutionReceipt(
        executed=bool(execution["executed"]),
        bound=bound,
        provenance_verified=provenance_verified,
        outcome_successful=outcome_successful,
        baseline=_artifact_view(baseline),
        result=_artifact_view(result),
        provenance_failure_codes=tuple(provenance_failures),
        outcome_failure_codes=tuple(outcome_failures),
        failure_codes=tuple(failures),
        limitations=tuple(limitation_list),
    )


def _expected_matches(receipt: Mapping[str, object]) -> dict[str, bool | None]:
    authorization = _mapping(receipt["authorization"], "authorization")
    execution = _mapping(receipt["execution"], "execution")
    artifacts = _mapping(receipt["artifacts"], "artifacts")
    original = _mapping(artifacts["original"], "artifacts.original")
    baseline = _mapping(artifacts["baseline"], "artifacts.baseline")
    result = _mapping(artifacts["result"], "artifacts.result")
    return {
        "operation": _equal_if_present(
            authorization["operation"], execution["operation"]
        ),
        "native_operation": _equal_if_present(
            authorization["operation"], execution["native_operation"]
        ),
        "write_mode": _equal_if_present(
            authorization["write_mode"], execution["write_mode"]
        ),
        "router_input_to_baseline": _paths_equal_if_present(
            execution["router_input_path"], baseline["path"]
        ),
        "baseline_to_original": _equal_if_present(
            baseline["sha256"], original["sha256_before"]
        ),
        "original_unchanged": _equal_if_present(
            original["sha256_before"], original["sha256_after"]
        ),
        "result_present": result["path"] is not None and result["sha256"] is not None,
    }


def _computed_failure_code_groups(
    receipt: Mapping[str, object],
) -> tuple[list[str], list[str]]:
    authorization = _mapping(receipt["authorization"], "authorization")
    execution = _mapping(receipt["execution"], "execution")
    artifacts = _mapping(receipt["artifacts"], "artifacts")
    original = _mapping(artifacts["original"], "artifacts.original")
    baseline = _mapping(artifacts["baseline"], "artifacts.baseline")
    result = _mapping(artifacts["result"], "artifacts.result")
    matches = _expected_matches(receipt)
    provenance_failures: list[str] = []
    outcome_failures: list[str] = []

    if execution["executed"] is not True:
        provenance_failures.append("NOT_EXECUTED")
        if execution["reported_status"] == "ok":
            outcome_failures.append("STATUS_EXECUTION_CONTRADICTION")
        return provenance_failures, outcome_failures

    if authorization["write_mode"] is None:
        provenance_failures.append("AUTHORIZED_WRITE_MODE_MISSING")
    if execution["operation"] is None:
        provenance_failures.append("EXECUTED_OPERATION_MISSING")
    elif matches["operation"] is not True:
        provenance_failures.append("OPERATION_MISMATCH")
    if execution["write_mode"] is None:
        provenance_failures.append("EXECUTED_WRITE_MODE_MISSING")
    elif matches["write_mode"] is not True:
        provenance_failures.append("WRITE_MODE_MISMATCH")
    if execution["router_input_path"] is None:
        provenance_failures.append("ROUTER_INPUT_MISSING")
    elif matches["router_input_to_baseline"] is not True:
        provenance_failures.append("ROUTER_INPUT_BASELINE_MISMATCH")

    _append_status_failure(
        outcome_failures, "REPORTED_STATUS", execution["reported_status"]
    )
    _append_router_status_failure(outcome_failures, execution["router_status"])
    _append_status_failure(
        outcome_failures, "NATIVE_STATUS", execution["native_status"]
    )
    _append_exit_failure(
        outcome_failures, "PROCESS_EXIT", execution["process_exit_code"]
    )
    _append_exit_failure(
        outcome_failures, "ENGINE_EXIT", execution["engine_exit_code"]
    )
    _append_exit_failure(
        outcome_failures,
        "ENGINE_OUTPUT_EXIT",
        execution["engine_output_exit_code"],
    )
    if (
        execution["engine_exit_code"] is not None
        and execution["engine_output_exit_code"] is not None
        and execution["engine_exit_code"] != execution["engine_output_exit_code"]
    ):
        outcome_failures.append("ENGINE_EXIT_MISMATCH")
    if execution["timed_out"] is None:
        outcome_failures.append("TIMEOUT_OBSERVATION_MISSING")
    elif execution["timed_out"] is True:
        outcome_failures.append("TIMED_OUT")
    if execution["launch_error"] is not None:
        outcome_failures.append("LAUNCH_ERROR")
    if execution["input_kind"] is None:
        provenance_failures.append("INPUT_KIND_MISSING")
    elif execution["input_kind"] != "staged_copy":
        provenance_failures.append("INPUT_KIND_NOT_STAGED_COPY")
    if execution["router_schema"] is None:
        provenance_failures.append("ROUTER_SCHEMA_MISSING")
    elif execution["router_schema"] != ROUTER_SCHEMA:
        provenance_failures.append("ROUTER_SCHEMA_MISMATCH")
    if execution["executed_route"] is None:
        provenance_failures.append("ROUTER_ROUTE_MISSING")
    elif execution["executed_route"] != ROUTER_ROUTE:
        provenance_failures.append("ROUTER_ROUTE_MISMATCH")
    if execution["native_result_source"] is None:
        provenance_failures.append("NATIVE_RESULT_SOURCE_MISSING")
    elif execution["native_result_source"] != "file":
        provenance_failures.append("NATIVE_RESULT_SOURCE_NOT_FILE")
    if execution["native_result_path"] is None:
        provenance_failures.append("NATIVE_RESULT_PATH_MISSING")
    if execution["native_result_sha256"] is None:
        provenance_failures.append("NATIVE_RESULT_SHA_MISSING")
    if execution["native_schema"] is None:
        provenance_failures.append("NATIVE_SCHEMA_MISSING")
    elif execution["native_schema"] not in {
        schema for schema, _ in _RESULT_CONTRACTS
    }:
        provenance_failures.append("NATIVE_SCHEMA_MISMATCH")
    if execution["native_engine"] is None:
        provenance_failures.append("NATIVE_ENGINE_MISSING")
    elif execution["native_engine"] not in {
        engine for _, engine in _RESULT_CONTRACTS
    }:
        provenance_failures.append("NATIVE_ENGINE_MISMATCH")
    if (
        execution["native_schema"] is not None
        and execution["native_engine"] is not None
        and (
            execution["native_schema"],
            execution["native_engine"],
        ) not in _RESULT_CONTRACTS
    ):
        provenance_failures.append("NATIVE_RESULT_CONTRACT_MISMATCH")
    if execution["native_operation"] is None:
        provenance_failures.append("NATIVE_OPERATION_MISSING")
    elif matches["native_operation"] is not True:
        provenance_failures.append("NATIVE_OPERATION_MISMATCH")
    if execution["native_status"] == "ok":
        if execution["native_result_is_object"] is None:
            provenance_failures.append("NATIVE_RESULT_OBJECT_OBSERVATION_MISSING")
        elif execution["native_result_is_object"] is not True:
            provenance_failures.append("NATIVE_RESULT_NOT_OBJECT")
    if (
        execution["native_status"] == "ok"
        and execution["native_error_code"] is not None
    ):
        outcome_failures.append("NATIVE_ERROR_CONTRADICTION")

    if original["path"] is None:
        provenance_failures.append("ORIGINAL_PATH_MISSING")
    if original["sha256_before"] is None:
        provenance_failures.append("ORIGINAL_SHA_BEFORE_MISSING")
    if original["sha256_after"] is None:
        provenance_failures.append("ORIGINAL_SHA_AFTER_MISSING")
    elif matches["original_unchanged"] is not True:
        provenance_failures.append("ORIGINAL_CHANGED")

    if baseline["path"] is None:
        provenance_failures.append("BASELINE_PATH_MISSING")
    if baseline["sha256"] is None:
        provenance_failures.append("BASELINE_SHA_MISSING")
    elif matches["baseline_to_original"] is not True:
        provenance_failures.append("BASELINE_ORIGINAL_MISMATCH")
    if baseline["sha256_after"] is None:
        provenance_failures.append("BASELINE_SHA_AFTER_MISSING")
    elif baseline["unchanged"] is not True:
        provenance_failures.append("BASELINE_CHANGED")

    if result["path"] is None or result["sha256"] is None:
        provenance_failures.append("RESULT_MISSING")
    elif _paths_equal_if_present(result["path"], baseline["path"]) is True:
        provenance_failures.append("RESULT_BASELINE_PATH_COLLISION")
    if result["kind"] is None:
        provenance_failures.append("RESULT_KIND_MISSING")
    elif result["kind"] not in _RESULT_KINDS:
        provenance_failures.append("RESULT_KIND_UNKNOWN")
    if execution["router_working_sha256_before"] is None:
        provenance_failures.append("ROUTER_WORKING_SHA_BEFORE_MISSING")
    elif execution["router_working_sha256_before"] != baseline["sha256"]:
        provenance_failures.append("ROUTER_WORKING_BEFORE_BASELINE_MISMATCH")
    if execution["router_working_sha256_after"] is None:
        provenance_failures.append("ROUTER_WORKING_SHA_AFTER_MISSING")
    elif (
        result["kind"] == "router_working_copy"
        and execution["router_working_sha256_after"] != result["sha256"]
    ):
        provenance_failures.append("ROUTER_WORKING_AFTER_RESULT_MISMATCH")

    save_issued = execution["save_command_issued"]
    if save_issued is None:
        outcome_failures.append("SAVE_COMMAND_OBSERVATION_MISSING")
    else:
        if authorization["write_mode"] == "write_copy" and save_issued is False:
            outcome_failures.append("SAVE_COMMAND_NOT_ISSUED")
        if authorization["write_mode"] == "read" and save_issued is True:
            outcome_failures.append("UNEXPECTED_SAVE_COMMAND")
    return provenance_failures, outcome_failures


def _append_status_failure(failures: list[str], prefix: str, value: object) -> None:
    if value is None:
        failures.append(f"{prefix}_MISSING")
    elif value not in _KNOWN_STATUSES:
        failures.append(f"{prefix}_UNKNOWN")
    elif value != "ok":
        failures.append(f"{prefix}_NOT_OK")


def _append_router_status_failure(failures: list[str], value: object) -> None:
    if value is None:
        failures.append("ROUTER_STATUS_MISSING")
    elif value != "PASS":
        failures.append("ROUTER_STATUS_NOT_PASS")


def _append_exit_failure(failures: list[str], prefix: str, value: object) -> None:
    if value is None:
        failures.append(f"{prefix}_MISSING")
    elif value != 0:
        failures.append(f"{prefix}_NONZERO")


def _artifact_view(artifact: Mapping[str, object]) -> ArtifactView | None:
    path = artifact["path"]
    digest = artifact["sha256"]
    if isinstance(path, str) and isinstance(digest, str):
        return ArtifactView(path=path, sha256=digest)
    return None


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ExecutionReceiptError("INVALID_TYPE", f"{field} must be a mapping")
    return value


def _expect_keys(value: Mapping[str, object], expected: set[str], field: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ExecutionReceiptError(
            "INVALID_KEYS", f"{field} keys differ; missing={missing}, extra={extra}"
        )


def _required_string(value: object, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise ExecutionReceiptError(
            "INVALID_TYPE", f"{field} must be a non-empty string"
        )
    return value


def _optional_string(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _required_string(value, field)


def _required_bool(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise ExecutionReceiptError("INVALID_TYPE", f"{field} must be a boolean")
    return value


def _optional_bool(value: object, field: str) -> bool | None:
    if value is None:
        return None
    return _required_bool(value, field)


def _optional_int(value: object, field: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int:
        raise ExecutionReceiptError("INVALID_TYPE", f"{field} must be an integer")
    return value


def _optional_hash(
    value: object, field: str, *, canonicalize: bool = False
) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        raise ExecutionReceiptError(
            "INVALID_HASH", f"{field} must be a lowercase SHA-256 string"
        )
    candidate = value.lower() if canonicalize else value
    if not _HASH_RE.fullmatch(candidate):
        raise ExecutionReceiptError(
            "INVALID_HASH", f"{field} must be a lowercase SHA-256 string"
        )
    return candidate


def _optional_path(value: object, field: str) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not value.strip() or "\x00" in value:
        raise ExecutionReceiptError(
            "INVALID_PATH", f"{field} must be a non-empty absolute path"
        )
    if not (
        PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute()
    ):
        raise ExecutionReceiptError(
            "INVALID_PATH", f"{field} must be an absolute path"
        )
    return value


def _string_list(
    value: object, field: str, *, require_list: bool = False
) -> list[str]:
    if require_list and type(value) is not list:
        raise ExecutionReceiptError("INVALID_TYPE", f"{field} must be a list")
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ExecutionReceiptError("INVALID_TYPE", f"{field} must be a sequence")
    result = [_required_string(item, f"{field} item") for item in value]
    if len(result) != len(set(result)):
        raise ExecutionReceiptError("INVALID_VALUE", f"{field} contains duplicates")
    return result


def _failure_code_list(
    value: object, field: str, *, require_list: bool = False
) -> list[str]:
    result = _string_list(value, field, require_list=require_list)
    if any(not _FAILURE_CODE_RE.fullmatch(code) for code in result):
        raise ExecutionReceiptError(
            "INVALID_FAILURE_CODE", f"{field} contains a non-canonical code"
        )
    return result


def _equal_if_present(left: object, right: object) -> bool | None:
    if left is None or right is None:
        return None
    return left == right


def _paths_equal_if_present(left: object, right: object) -> bool | None:
    if left is None or right is None:
        return None
    assert isinstance(left, str) and isinstance(right, str)
    if PureWindowsPath(left).is_absolute() or PureWindowsPath(right).is_absolute():
        return ntpath.normcase(ntpath.normpath(left)) == ntpath.normcase(
            ntpath.normpath(right)
        )
    return posixpath.normpath(left) == posixpath.normpath(right)


def _stable_unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))


__all__ = [
    "ArtifactView",
    "ExecutionReceipt",
    "ExecutionReceiptError",
    "build_execution_receipt",
    "parse_execution_receipt",
]
