"""Assemble CADAgent's read-only current-status projection.

The projection deliberately keeps five different questions separate:

* ``anchor``: is this exact checkout bound to an independently supplied revision?
* ``capability``: are the operation registry and MCP declaration surfaces coherent?
* ``proof``: do the committed native artifacts match this source tree?
* ``runtime_observation``: what was observed from a live AutoCAD runtime now?
* ``historical_snapshot``: what did the legacy router report claim when written?

The top-level ``status`` only reports that this projection was assembled.  It is
never an aggregate readiness verdict.  No AutoCAD/router probe is run here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .git_state import (
    observe_native_source_checkout,
    verify_checkout,
    verify_paths_at_revision,
)
from .mcp_surface import verify_declared_tool_surface
from .native_integrity import verify_committed_deployment
from .operation_registry import verify_operation_registry


STATUS_SCHEMA = "ariadne.cadctl.status.v2"
LEGACY_STATUS_SCHEMA = "ariadne.cadctl.status.v1"
HISTORICAL_REPORT_RELATIVE_PATH = Path("reports/autocad_router_status_latest.json")
COMMITTED_NATIVE_RELATIVE_PATH = Path("prebuilt/2027")
SUPPORTED_HISTORICAL_SCHEMAS = frozenset({"ariadne.autocad_router_status.v2"})
_EXACT_SHA_RE = re.compile(r"[0-9a-f]{40}")


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not permitted: {value}")


def _reject_duplicate_json_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _strict_json_loads(value: str) -> object:
    return json.loads(
        value,
        object_pairs_hook=_reject_duplicate_json_object,
        parse_constant=_reject_json_constant,
    )


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return path.absolute()


def _source(path: Path, raw: bytes | None = None) -> dict[str, object]:
    resolved = _safe_resolve(path)
    if raw is None:
        try:
            raw = path.read_bytes()
        except OSError:
            raw = None
    return {
        "path": str(resolved),
        "sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
    }


def _exception_error(code: str, exc: Exception) -> dict[str, str]:
    return {
        "code": code,
        "exception_type": type(exc).__name__,
        "message": str(exc),
    }


def _receipt_dict(receipt: object) -> dict[str, object]:
    to_dict = getattr(receipt, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
    else:
        value = receipt
    if not isinstance(value, Mapping):
        raise TypeError("verifier receipt must be a mapping or expose to_dict()")
    return dict(value)


def _anchor_projection(
    router_home: Path,
    expected_revision: str | None,
) -> dict[str, object]:
    source = {"kind": "git_checkout", "path": str(router_home)}
    if expected_revision is None:
        try:
            receipt = _receipt_dict(observe_native_source_checkout(router_home))
        except Exception as exc:  # containment boundary for status transport
            return {
                "status": "BLOCKED",
                "verification": "UNKNOWN",
                "reason_code": "CHECKOUT_OBSERVATION_FAILED",
                "expected_revision": None,
                "observed_revision": "UNKNOWN",
                "clean": "UNKNOWN",
                "source": source,
                "receipt": None,
                "errors": [_exception_error("CHECKOUT_OBSERVATION_FAILED", exc)],
            }
        return {
            "status": "BLOCKED",
            "verification": "UNKNOWN",
            "reason_code": "EXPECTED_REVISION_NOT_BOUND",
            "expected_revision": None,
            "observed_revision": receipt.get("head", "UNKNOWN"),
            "clean": "UNKNOWN",
            "native_source_dirty": receipt.get("native_source_dirty", "UNKNOWN"),
            "source": source,
            "receipt": receipt,
            "errors": [
                {
                    "code": "EXPECTED_REVISION_NOT_BOUND",
                    "message": (
                        "no independent expected revision was supplied; the observed "
                        "HEAD is not accepted as its own anchor"
                    ),
                }
            ],
        }

    try:
        receipt = _receipt_dict(
            verify_checkout(router_home, expected_revision, require_clean=True)
        )
    except Exception as exc:  # containment boundary for status transport
        return {
            "status": "BLOCKED",
            "verification": "UNKNOWN",
            "reason_code": "CHECKOUT_VERIFICATION_FAILED",
            "expected_revision": expected_revision,
            "observed_revision": "UNKNOWN",
            "clean": "UNKNOWN",
            "source": source,
            "receipt": None,
            "errors": [_exception_error("CHECKOUT_VERIFICATION_FAILED", exc)],
        }
    passed = receipt.get("status") == "PASS"
    return {
        "status": "PASS" if passed else "BLOCKED",
        "verification": "VERIFIED" if passed else "BLOCKED",
        "reason_code": None if passed else "CHECKOUT_NOT_VERIFIED",
        "expected_revision": expected_revision,
        "observed_revision": receipt.get("head", "UNKNOWN"),
        "clean": receipt.get("clean", "UNKNOWN"),
        "source": source,
        "receipt": receipt,
        "errors": list(receipt.get("errors") or []),
    }


def _finalize_revision_anchor(
    start: Mapping[str, object],
    end: Mapping[str, object],
) -> dict[str, object]:
    """Bind a revision claim only when both projection boundaries are identical."""

    start_receipt = start.get("receipt")
    end_receipt = end.get("receipt")
    receipts_match = start_receipt == end_receipt
    both_pass = start.get("status") == end.get("status") == "PASS"
    if receipts_match and both_pass:
        finalized = dict(end)
        finalized["boundary_consistent"] = True
        finalized["boundary_scope"] = "checkout_start_end_only"
        finalized["projection_receipts"] = {
            "start": start_receipt,
            "end": end_receipt,
        }
        return finalized

    if start.get("status") != "PASS":
        finalized = dict(start)
        finalized["boundary_consistent"] = False
        finalized["boundary_scope"] = "checkout_start_end_only"
        finalized["projection_receipts"] = {
            "start": start_receipt,
            "end": end_receipt,
        }
        return finalized

    boundary_error = {
        "code": "CHECKOUT_CHANGED_DURING_PROJECTION",
        "message": (
            "the final checkout receipt was not the same clean PASS receipt "
            "observed before projection assembly"
        ),
    }
    end_errors = end.get("errors")
    if not isinstance(end_errors, list):
        end_errors = []
    return {
        "status": "BLOCKED",
        "verification": (
            "UNKNOWN" if end.get("verification") == "UNKNOWN" else "BLOCKED"
        ),
        "reason_code": "CHECKOUT_CHANGED_DURING_PROJECTION",
        "expected_revision": start.get("expected_revision"),
        "observed_revision": end.get("observed_revision", "UNKNOWN"),
        "clean": end.get("clean", "UNKNOWN"),
        "source": start.get("source"),
        "receipt": end_receipt,
        "boundary_consistent": False,
        "boundary_scope": "checkout_start_end_only",
        "projection_receipts": {
            "start": start_receipt,
            "end": end_receipt,
        },
        "errors": [boundary_error, *end_errors],
    }


def _registry_projection(
    router_home: Path,
    expected_revision: str | None,
) -> dict[str, object]:
    source_path = router_home / "config" / "operations.v2.json"
    try:
        receipt = _receipt_dict(verify_operation_registry(router_home))
    except Exception as exc:  # containment boundary for status transport
        return {
            "status": "BLOCKED",
            "verification": "UNKNOWN",
            "source": _source(source_path),
            "receipt": None,
            "errors": [_exception_error("OPERATION_REGISTRY_VERIFIER_FAILED", exc)],
        }
    verified = receipt.get("verified") is True
    input_digests = receipt.get("input_digests")
    registry_digest = (
        input_digests.get("config/operations.v2.json")
        if isinstance(input_digests, Mapping)
        else None
    )
    projection = {
        "status": "PASS" if verified else "BLOCKED",
        "verification": "VERIFIED" if verified else "BLOCKED",
        "verification_scope": receipt.get("verification_scope"),
        "limitations": list(receipt.get("limitations") or []),
        "limitation_codes": list(receipt.get("limitation_codes") or []),
        "reason_code": None if verified else "OPERATION_REGISTRY_NOT_VERIFIED",
        "source": {
            "path": str(_safe_resolve(source_path)),
            "sha256": registry_digest,
            "binding": "operation_registry_verifier_input_snapshot",
        },
        "receipt": receipt,
        "revision_binding": None,
        "bound_to_expected_revision": False,
        "errors": list(receipt.get("failures") or []),
    }
    if expected_revision is None:
        return projection
    try:
        binding = _receipt_dict(
            verify_paths_at_revision(
                router_home,
                expected_revision,
                input_digests if isinstance(input_digests, Mapping) else {},
            )
        )
    except Exception as exc:  # containment boundary for status transport
        projection.update(
            {
                "status": "BLOCKED",
                "verification": "BLOCKED",
                "reason_code": "RECEIPT_NOT_BOUND_TO_EXPECTED_REVISION",
                "revision_binding": None,
                "errors": [
                    *projection["errors"],
                    _exception_error("REVISION_PATH_BINDING_FAILED", exc),
                ],
            }
        )
        return projection
    projection["revision_binding"] = binding
    if binding.get("status") == "PASS":
        projection["bound_to_expected_revision"] = True
        return projection
    binding_errors = binding.get("errors")
    if not isinstance(binding_errors, list):
        binding_errors = []
    projection.update(
        {
            "status": "BLOCKED",
            "verification": "BLOCKED",
            "reason_code": "RECEIPT_NOT_BOUND_TO_EXPECTED_REVISION",
            "bound_to_expected_revision": False,
            "errors": [
                *projection["errors"],
                {
                    "code": "RECEIPT_NOT_BOUND_TO_EXPECTED_REVISION",
                    "message": (
                        "operation-registry input digests do not bind to the "
                        "independently expected revision"
                    ),
                },
                *binding_errors,
            ],
        }
    )
    return projection


def _mcp_source_receipt(router_home: Path) -> dict[str, object]:
    paths = (
        router_home / "tools" / "cadagent_mcp.py",
        router_home / "tools" / "verification" / "mcp_surface.py",
    )
    files = [_source(path) for path in paths]
    aggregate = hashlib.sha256()
    complete = True
    for item in files:
        digest = item["sha256"]
        if not isinstance(digest, str):
            complete = False
            continue
        aggregate.update(f"{item['path']}\0{digest}\n".encode("utf-8"))
    return {
        "binding": "caller_supplied_in_memory_contract",
        "source_files_observed": files,
        "bound_to_source_files": False,
        "input_set_sha256": aggregate.hexdigest() if complete else None,
    }


def _mcp_projection(
    router_home: Path,
    definitions: object | None,
    dispatch: object | None,
) -> dict[str, object]:
    source = _mcp_source_receipt(router_home)
    if definitions is None and dispatch is None:
        return {
            "status": "BLOCKED",
            "verification": "UNKNOWN",
            "source": source,
            "receipt": None,
            "errors": [
                {
                    "code": "MCP_SURFACE_CONTEXT_NOT_BOUND",
                    "message": (
                        "the current MCP process did not supply its in-memory "
                        "tool definitions and dispatch table"
                    ),
                }
            ],
        }
    try:
        if definitions is None or dispatch is None:
            raise ValueError(
                "mcp_definitions and mcp_dispatch must be supplied together"
            )
        receipt = _receipt_dict(
            verify_declared_tool_surface(definitions, dispatch)
        )
    except Exception as exc:  # containment boundary for status transport
        return {
            "status": "BLOCKED",
            "verification": "UNKNOWN",
            "source": source,
            "receipt": None,
            "errors": [_exception_error("MCP_SURFACE_VERIFIER_FAILED", exc)],
        }
    verified = receipt.get("verification") == "VERIFIED"
    return {
        "status": "PASS" if verified else "BLOCKED",
        "verification": "VERIFIED" if verified else "BLOCKED",
        "source": source,
        "receipt": receipt,
        "errors": list(receipt.get("failures") or []),
    }


def _native_proof_projection(router_home: Path) -> dict[str, object]:
    deploy_dir = router_home / COMMITTED_NATIVE_RELATIVE_PATH
    manifest = deploy_dir / "native_deployment_manifest.json"
    try:
        receipt = _receipt_dict(
            verify_committed_deployment(router_home, deploy_dir)
        )
    except Exception as exc:  # containment boundary for status transport
        return {
            "status": "BLOCKED",
            "verification": "UNKNOWN",
            "source": _source(manifest),
            "receipt": None,
            "errors": [_exception_error("NATIVE_PROOF_VERIFIER_FAILED", exc)],
        }
    verified = receipt.get("valid") is True
    return {
        "status": "PASS" if verified else "BLOCKED",
        "verification": "VERIFIED" if verified else "BLOCKED",
        "verification_scope": receipt.get("verification_scope"),
        "limitation_codes": list(receipt.get("limitation_codes") or []),
        "source": {
            "path": str(_safe_resolve(manifest)),
            "sha256": receipt.get("sha256"),
            "binding": "native_integrity_verifier_receipt",
        },
        "receipt": receipt,
        "errors": list(receipt.get("errors") or []),
    }


def _ci_proof_projection() -> dict[str, object]:
    return {
        "status": "BLOCKED",
        "verification": "UNKNOWN",
        "reason_code": "CI_PROOF_NOT_BOUND",
        "source": None,
        "receipt": None,
        "errors": [
            {
                "code": "CI_PROOF_NOT_BOUND",
                "message": (
                    "no revision-bound CI receipt consumer is configured for "
                    "cad.status"
                ),
            }
        ],
    }


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_historical_report(
    raw: Mapping[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Validate the minimal legacy artifact contract without promoting its claims."""

    errors: list[dict[str, object]] = []
    schema = raw.get("schema")
    if not isinstance(schema, str) or not schema:
        errors.append(
            {
                "code": "HISTORICAL_SCHEMA_INVALID",
                "message": "schema must be a non-empty string",
            }
        )
    elif schema not in SUPPORTED_HISTORICAL_SCHEMAS:
        errors.append(
            {
                "code": "HISTORICAL_SCHEMA_UNSUPPORTED",
                "message": f"unsupported historical report schema: {schema}",
            }
        )

    routes_claim = raw.get("routes")
    normalized: list[dict[str, object]] = []
    routes_valid = isinstance(routes_claim, list)
    if not routes_valid:
        errors.append(
            {
                "code": "HISTORICAL_ROUTES_INVALID",
                "message": "routes must be a list of route objects",
            }
        )
        route_rows: list[object] = []
    else:
        route_rows = routes_claim

    for index, row in enumerate(route_rows):
        if not isinstance(row, Mapping):
            errors.append(
                {
                    "code": "HISTORICAL_ROUTE_ROW_INVALID",
                    "index": index,
                    "message": "route row must be an object",
                }
            )
            routes_valid = False
            continue
        route = row.get("route")
        available = row.get("available")
        engine = row.get("engine")
        row_valid = True
        if not isinstance(route, str) or not route:
            errors.append(
                {
                    "code": "HISTORICAL_ROUTE_NAME_INVALID",
                    "index": index,
                    "message": "route must be a non-empty string",
                }
            )
            row_valid = False
        if not isinstance(available, bool):
            errors.append(
                {
                    "code": "HISTORICAL_ROUTE_AVAILABILITY_INVALID",
                    "index": index,
                    "message": "available must be a JSON boolean",
                }
            )
            row_valid = False
        if "engine" not in row or (
            engine is not None and not isinstance(engine, str)
        ):
            errors.append(
                {
                    "code": "HISTORICAL_ROUTE_ENGINE_INVALID",
                    "index": index,
                    "message": "engine must be a string or null",
                }
            )
            row_valid = False
        if row_valid:
            normalized.append(
                {"route": route, "available": available, "engine": engine}
            )
        else:
            routes_valid = False

    route_count = raw.get("route_count")
    if not _is_plain_int(route_count):
        errors.append(
            {
                "code": "HISTORICAL_ROUTE_COUNT_INVALID",
                "message": "route_count must be a non-boolean integer",
            }
        )
    elif routes_valid and route_count != len(normalized):
        errors.append(
            {
                "code": "HISTORICAL_ROUTE_COUNT_MISMATCH",
                "declared": route_count,
                "computed": len(normalized),
                "message": "route_count does not match the validated route rows",
            }
        )

    available_count = raw.get("available_count")
    computed_available = sum(
        1 for route in normalized if route["available"] is True
    )
    if not _is_plain_int(available_count):
        errors.append(
            {
                "code": "HISTORICAL_AVAILABLE_COUNT_INVALID",
                "message": "available_count must be a non-boolean integer",
            }
        )
    elif routes_valid and available_count != computed_available:
        errors.append(
            {
                "code": "HISTORICAL_AVAILABLE_COUNT_MISMATCH",
                "declared": available_count,
                "computed": computed_available,
                "message": (
                    "available_count does not match validated available routes"
                ),
            }
        )
    return normalized, errors


def _historical_projection(router_home: Path) -> dict[str, object]:
    report_path = router_home / HISTORICAL_REPORT_RELATIVE_PATH
    source = _source(report_path)
    try:
        raw_bytes = report_path.read_bytes()
    except FileNotFoundError:
        return {
            "status": "BLOCKED",
            "status_scope": "artifact_validation_only",
            "observation": "MISSING",
            "classification": "HISTORICAL_UNBOUND",
            "bound_to_current_revision": False,
            "freshness": "UNVERIFIED",
            "source": source,
            "routes": [],
            "route_count": 0,
            "available_count": 0,
            "errors": [{"code": "HISTORICAL_REPORT_MISSING"}],
        }
    except OSError as exc:
        return {
            "status": "BLOCKED",
            "status_scope": "artifact_validation_only",
            "observation": "UNREADABLE",
            "classification": "HISTORICAL_UNBOUND",
            "bound_to_current_revision": False,
            "freshness": "UNVERIFIED",
            "source": source,
            "routes": [],
            "route_count": 0,
            "available_count": 0,
            "errors": [_exception_error("HISTORICAL_REPORT_UNREADABLE", exc)],
        }
    source = _source(report_path, raw_bytes)
    try:
        parsed = _strict_json_loads(raw_bytes.decode("utf-8-sig"))
        if not isinstance(parsed, Mapping):
            raise TypeError("historical report root must be an object")
        raw = dict(parsed)
    except (UnicodeError, ValueError, TypeError) as exc:
        return {
            "status": "BLOCKED",
            "status_scope": "artifact_validation_only",
            "observation": "MALFORMED",
            "classification": "HISTORICAL_UNBOUND",
            "bound_to_current_revision": False,
            "freshness": "UNVERIFIED",
            "source": source,
            "routes": [],
            "route_count": 0,
            "available_count": 0,
            "errors": [_exception_error("HISTORICAL_REPORT_MALFORMED", exc)],
        }
    routes, validation_errors = _validate_historical_report(raw)
    if validation_errors:
        return {
            "status": "BLOCKED",
            "status_scope": "artifact_validation_only",
            "observation": "INVALID",
            "classification": "HISTORICAL_UNBOUND",
            "bound_to_current_revision": False,
            "freshness": "UNVERIFIED",
            "source": source,
            "schema_claim": raw.get("schema"),
            "routes": [],
            "route_count": 0,
            "available_count": 0,
            "declared_route_count": raw.get("route_count"),
            "declared_available_count": raw.get("available_count"),
            "errors": validation_errors,
        }
    source_revision = next(
        (
            value
            for key in ("source_revision", "git_head", "revision")
            if isinstance((value := raw.get(key)), str)
            and _EXACT_SHA_RE.fullmatch(value)
        ),
        None,
    )
    return {
        "status": "PASS",
        "status_scope": "artifact_validation_only",
        "observation": "PRESENT",
        "classification": "HISTORICAL_UNBOUND",
        "bound_to_current_revision": False,
        "freshness": "UNVERIFIED",
        "source": source,
        "source_revision_claim": source_revision,
        "schema_claim": raw.get("schema"),
        "status_claim": raw.get("status"),
        "timestamp_claim": raw.get("timestamp"),
        "router_home_claim": raw.get("router_home"),
        "native_modules_status_claim": (
            raw.get("native_modules", {}).get("status")
            if isinstance(raw.get("native_modules"), Mapping)
            else None
        ),
        "routes": routes,
        "route_count": len(routes),
        "available_count": sum(1 for route in routes if route["available"] is True),
        "declared_route_count": raw.get("route_count"),
        "declared_available_count": raw.get("available_count"),
        "errors": [],
    }


def _compatibility_projection(historical: Mapping[str, object]) -> dict[str, object]:
    routes = historical.get("routes")
    if not isinstance(routes, list):
        routes = []
    return {
        "source": "historical_snapshot",
        "evidence_class": "historical_unbound",
        "route_count": historical.get("route_count", 0),
        "available_count": historical.get("available_count", 0),
        "routes": routes,
        "note": (
            "compatibility route fields are historical claims; they are not a "
            "current runtime observation"
        ),
    }


def build_legacy_status(router_home: str | Path) -> dict[str, object]:
    """Return the exact v1 shape as a clearly unbound historical adapter."""

    root = _safe_resolve(Path(router_home))
    historical = _historical_projection(root)
    source = historical.get("source")
    status_path = source.get("path") if isinstance(source, Mapping) else str(
        root / HISTORICAL_REPORT_RELATIVE_PATH
    )
    if historical.get("status") != "PASS":
        observation = historical.get("observation")
        errors = historical.get("errors")
        reason = (
            f"published router status JSON not found: {status_path}"
            if observation == "MISSING"
            else f"historical router status artifact is {str(observation).lower()}"
        )
        return {
            "schema": LEGACY_STATUS_SCHEMA,
            "status": "unavailable" if observation == "MISSING" else "error",
            "reason": reason,
            "status_json_path": status_path,
            "route_count": 0,
            "available_count": 0,
            "native_available": False,
            "routes": [],
            "evidence_class": "historical_unbound",
            "bound_to_current_revision": False,
            "historical_validation": {
                "status": historical.get("status"),
                "observation": observation,
                "errors": list(errors) if isinstance(errors, list) else [],
            },
            "note": (
                "v1 compatibility view of an unbound historical router report; "
                "not a live probe"
            ),
        }

    routes = historical.get("routes")
    if not isinstance(routes, list):
        routes = []
    native_status = historical.get("native_modules_status_claim")
    return {
        "schema": LEGACY_STATUS_SCHEMA,
        "status": "ok",
        "router_status": historical.get("status_claim"),
        "router_status_schema": historical.get("schema_claim"),
        "status_json_path": status_path,
        "router_home": historical.get("router_home_claim"),
        "timestamp": historical.get("timestamp_claim"),
        "route_count": historical.get("route_count", len(routes)),
        "available_count": historical.get("available_count", 0),
        "unavailable": [row["route"] for row in routes if not row["available"]],
        "native_available": str(native_status).upper() == "PASS",
        "native_modules_status": native_status,
        "routes": routes,
        "evidence_class": "historical_unbound",
        "bound_to_current_revision": False,
        "historical_validation": {
            "status": "PASS",
            "observation": historical.get("observation"),
            "source": source,
        },
        "note": (
            "v1 compatibility view of an unbound historical router report; "
            "not a live probe"
        ),
    }


def build_current_status(
    router_home: str | Path,
    *,
    expected_revision: str | None = None,
    mcp_definitions: object | None = None,
    mcp_dispatch: object | None = None,
) -> dict[str, object]:
    """Return a deterministic, read-only projection of independently typed facts."""

    root = _safe_resolve(Path(router_home))
    anchor_start = _anchor_projection(root, expected_revision)
    historical = _historical_projection(root)
    operation_registry = _registry_projection(root, expected_revision)
    mcp_surface = _mcp_projection(
        root,
        mcp_definitions,
        mcp_dispatch,
    )
    committed_native = _native_proof_projection(root)
    ci_proof = _ci_proof_projection()
    anchor = anchor_start
    if expected_revision is not None:
        anchor_end = _anchor_projection(root, expected_revision)
        anchor = _finalize_revision_anchor(anchor_start, anchor_end)
    return {
        "schema": STATUS_SCHEMA,
        "status": "PASS",
        "status_scope": "projection_assembly_only",
        "router_home": str(root),
        "anchor": anchor,
        "capability": {
            "operation_registry": operation_registry,
            "mcp_surface": mcp_surface,
        },
        "proof": {
            "committed_native": committed_native,
            "ci": ci_proof,
        },
        "runtime_observation": {
            "status": "BLOCKED",
            "observation": "NOT_RUN",
            "availability": "UNKNOWN",
            "reason_code": "LIVE_OBSERVATION_NOT_RUN",
            "source": None,
            "reason": (
                "cad.status is read-only and did not start AutoCAD, Core Console, "
                "or the router status probe"
            ),
        },
        "historical_snapshot": historical,
        "compatibility": _compatibility_projection(historical),
    }


__all__ = [
    "LEGACY_STATUS_SCHEMA",
    "STATUS_SCHEMA",
    "build_current_status",
    "build_legacy_status",
]
