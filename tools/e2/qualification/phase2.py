"""Fail-closed boundary for the retired unsealed phase-2 model jury.

The historical implementation mixed qualification evidence, model execution,
review-queue generation, and scientific claims in one host process.  A normal
Windows process cannot prove that the model consumed only the qualified source,
model, checkpoint, and independent gold.  Until the registered OS-confined
executor exists, every public phase-2 entry point returns the same terminal
BLOCKED receipt without importing or constructing a model runtime.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping


STATUS_BLOCKED = "BLOCKED"
REASON_CODE = "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def build_model_assisted_report(
    spec: Mapping[str, Any], run_dir: Path
) -> dict[str, Any]:
    """Persist a terminal refusal; never import, construct, or run a model jury."""

    if not isinstance(spec, Mapping):
        raise TypeError("phase-2 spec must be a JSON object")
    experiment_id = spec.get("experiment_id")
    if not isinstance(experiment_id, str) or not experiment_id.strip():
        raise ValueError("phase-2 experiment_id must be a non-empty string")
    run_dir = Path(run_dir)
    receipt_path = run_dir / "phase2_receipt.json"
    source = spec.get("source")
    requested_source = dict(source) if isinstance(source, Mapping) else None
    receipt = {
        "schema": "e2.phase2_receipt.v1",
        "status": STATUS_BLOCKED,
        "reason_code": REASON_CODE,
        "reason": (
            "The former phase-2 host runner cannot prove independent gold authority, "
            "exact model/checkpoint bytes, or confined input consumption. A registered "
            "OS-confined sealed executor is required before any model jury may run."
        ),
        "experiment_id": experiment_id,
        "requested_source": requested_source,
        "executed": False,
        "terminal_authorized": False,
        "model_runtime_loaded": False,
        "jury_constructed": False,
        "outputs": [],
        "claim_boundary": "instrument evidence only; no model score or wall-quality claim",
    }
    _write_json_atomic(receipt_path, receipt)
    return {
        **receipt,
        "run_dir": str(run_dir.resolve()),
        "receipt": str(receipt_path.resolve()),
    }
