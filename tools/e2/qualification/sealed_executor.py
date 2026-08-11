"""Single fail-closed boundary for retired host-side E2 executors."""
from __future__ import annotations

from typing import Any


STATUS_BLOCKED = "BLOCKED"
REASON_CODE = "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"


def refusal_receipt(
    *,
    requested_receipt_schema: str,
    experiment_id: object,
    entrypoint: str,
    claim_boundary: str,
) -> dict[str, Any]:
    """Return a deterministic refusal before any input, model, or output access."""

    normalized_experiment_id = (
        experiment_id.strip()
        if isinstance(experiment_id, str) and experiment_id.strip()
        else None
    )
    return {
        "schema": "e2.sealed_execution_refusal.v1",
        "requested_receipt_schema": requested_receipt_schema,
        "status": STATUS_BLOCKED,
        "reason_code": REASON_CODE,
        "reason": (
            "This legacy host runner cannot prove exact qualified-input consumption "
            "or OS confinement. A registered sealed executor is required."
        ),
        "experiment_id": normalized_experiment_id,
        "entrypoint": entrypoint,
        "input_accessed": False,
        "executed": False,
        "terminal_authorized": False,
        "model_runtime_loaded": False,
        "output_accessed": False,
        "outputs": [],
        "claim_boundary": claim_boundary,
    }
