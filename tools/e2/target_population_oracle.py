"""Shared validator for the authoritative native-display target oracle.

The native route publishes an observation-only oracle and a final receipt.  The
population builder and the downstream experiment guard must apply the same
instance and semantic checks; otherwise a legacy ``status=PASS`` snapshot can
silently become current authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

try:
    from jsonschema import Draft202012Validator
except ImportError:  # fail closed at validation time when the optional dependency is absent
    Draft202012Validator = None  # type: ignore[assignment,misc]


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "e2_target_population_oracle.v1.schema.json"
TARGET_SCHEMA = "ariadne.e2.target_population_oracle.v1"
ORACLE_KIND = "autocad.native_display_membership.v1"
RECEIPT_SCHEMA = "ariadne.cadctl.display_membership.v1"
RECEIPT_OPERATION = "e2.inspect.xclip_membership"
GEOMETRY_SCOPES = frozenset({"strict_layer_entities_v1", "linear_segments_v1"})
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
FINAL_EVIDENCE_KEYS = frozenset(
    {
        "source",
        "staged_dwg",
        "native_job_out",
        "attended_final_receipt",
        "binding",
        "observation_oracle",
        "native_build_manifest",
    }
)


class TargetPopulationContractError(ValueError):
    """A target oracle is not authoritative for downstream use."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_sha256(value: Any) -> str | None:
    text = str(value or "").lower()
    return text if SHA256_RE.fullmatch(text) else None


def _same_path(left: Any, right: Path) -> bool:
    try:
        return Path(str(left)).resolve(strict=True) == right.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return False


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise TargetPopulationContractError(
            "TARGET_ORACLE_EVIDENCE_INVALID", f"{label} is not readable JSON: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise TargetPopulationContractError(
            "TARGET_ORACLE_EVIDENCE_INVALID", f"{label} JSON root must be an object"
        )
    return value


def _schema_errors(oracle: Mapping[str, Any]) -> list[str]:
    try:
        if Draft202012Validator is None:
            raise RuntimeError("jsonschema Draft202012Validator is not importable")
        schema = _read_object(SCHEMA_PATH, "target oracle schema")
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
    except Exception as exc:
        raise TargetPopulationContractError(
            "TARGET_ORACLE_VALIDATOR_UNAVAILABLE",
            f"published target oracle schema cannot be used: {exc}",
        ) from exc
    return [
        error.message
        for error in sorted(
            validator.iter_errors(dict(oracle)), key=lambda error: list(error.path)
        )
    ]


def _fail(reason_code: str, message: str) -> None:
    raise TargetPopulationContractError(reason_code, message)


def validate_target_population_oracle(
    oracle: Mapping[str, Any],
    *,
    oracle_path: Path | None = None,
    source_dwg: Path | None = None,
    expected_source_sha256: str | None = None,
    expected_geometry_scope: str | None = None,
) -> dict[str, Any]:
    """Validate one authoritative oracle and its final producer receipt.

    ``oracle_path`` is optional for consumers that receive an in-memory JSON
    object.  The receipt's target path is still required and is used to prove
    that the object is the exact persisted oracle.  ``source_dwg`` is supplied
    by the population builder; consumers can instead provide the expected
    source SHA from their probe.
    """

    if not isinstance(oracle, Mapping):
        _fail("TARGET_ORACLE_SCHEMA_INVALID", "target oracle must be a JSON object")

    errors = _schema_errors(oracle)
    if errors:
        if oracle.get("status") == "PASS":
            _fail(
                "LEGACY_INCOMPATIBLE_TARGET_ORACLE",
                "legacy target oracle status=PASS or incomplete fields are not "
                "authoritative; v1 requires status=OBSERVED and receipt binding: "
                + "; ".join(errors),
            )
        _fail("TARGET_ORACLE_SCHEMA_INVALID", "target oracle schema validation failed: " + "; ".join(errors))

    geometry_scope = oracle.get("geometry_scope")
    if geometry_scope not in GEOMETRY_SCOPES:
        _fail("TARGET_ORACLE_GEOMETRY_SCOPE_INVALID", "target oracle geometry_scope is required and unknown")
    if expected_geometry_scope is not None and geometry_scope != expected_geometry_scope:
        _fail(
            "TARGET_ORACLE_GEOMETRY_SCOPE_MISMATCH",
            f"target oracle geometry_scope must be {expected_geometry_scope!r}",
        )

    drawing_id = _normalized_sha256(oracle.get("drawing_id"))
    if drawing_id is None:
        _fail("SOURCE_DRAWING_ID_INVALID", "target oracle drawing_id must be a SHA-256")
    expected_source = _normalized_sha256(expected_source_sha256)
    if expected_source is not None and drawing_id != expected_source:
        _fail("SOURCE_DRAWING_ID_MISMATCH", "target oracle drawing_id does not match the expected source SHA-256")
    if expected_source_sha256 is not None and expected_source is None:
        _fail("SOURCE_DRAWING_ID_INVALID", "expected source SHA-256 is malformed")

    evidence = oracle["evidence"]
    checked_evidence: list[dict[str, str]] = []
    binding: dict[str, Any] | None = None
    binding_path: Path | None = None
    for index, record in enumerate(evidence):
        path = Path(str(record["path"])).resolve()
        expected_hash = _normalized_sha256(record["sha256"])
        if expected_hash is None or not path.is_file():
            _fail("TARGET_ORACLE_EVIDENCE_INVALID", f"oracle evidence[{index}] is missing or has an invalid SHA-256")
        observed_hash = _sha256(path)
        if observed_hash != expected_hash:
            _fail("TARGET_ORACLE_EVIDENCE_DRIFTED", f"oracle evidence[{index}] SHA-256 drifted")
        checked_evidence.append({"path": str(path), "sha256": observed_hash})
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict) and payload.get("schema") == "ariadne.e2.native_display_binding.v1":
            if binding is not None:
                _fail("TARGET_ORACLE_EVIDENCE_INVALID", "target oracle contains duplicate native binding evidence")
            binding = payload
            binding_path = path

    if binding is None or binding_path is None:
        _fail("SOURCE_BINDING_EVIDENCE_REQUIRED", "target oracle must include native source binding evidence")
    source_path = Path(str(binding.get("source_path") or "")).resolve()
    source_hash = _normalized_sha256(binding.get("source_sha256"))
    if source_hash != drawing_id or not source_path.is_file() or _sha256(source_path) != drawing_id:
        _fail("SOURCE_DRAWING_BINDING_INVALID", "native source binding path/SHA does not match target oracle drawing_id")
    if binding.get("geometry_scope") != geometry_scope:
        _fail("TARGET_ORACLE_GEOMETRY_SCOPE_MISMATCH", "native source binding geometry_scope disagrees with target oracle")
    if source_dwg is not None:
        source_dwg = source_dwg.resolve(strict=True)
        if source_path != source_dwg or _sha256(source_dwg) != drawing_id:
            _fail("SOURCE_DRAWING_BINDING_INVALID", "target oracle source binding does not match the requested source DWG")

    receipt_path = Path(str(oracle["producer_receipt_path"])).resolve()
    if not receipt_path.is_file():
        _fail("PRODUCER_RECEIPT_REQUIRED", "target oracle producer receipt is missing")
    receipt = _read_object(receipt_path, "producer receipt")
    if (
        receipt.get("schema") != RECEIPT_SCHEMA
        or receipt.get("status") != "PASS"
        or receipt.get("operation") != RECEIPT_OPERATION
        or receipt.get("claim_scope") != "instrument_observation_only"
        or receipt.get("downstream_experiment_guard_required") is not True
        or receipt.get("geometry_scope") != geometry_scope
    ):
        _fail("PRODUCER_RECEIPT_INVALID", "producer receipt does not match the authoritative target-oracle contract")

    receipt_oracle_path = Path(str(receipt.get("target_population_oracle") or "")).resolve()
    if oracle_path is None:
        oracle_path = receipt_oracle_path
    else:
        oracle_path = oracle_path.resolve(strict=True)
    if receipt_oracle_path != oracle_path or not oracle_path.is_file():
        _fail("PRODUCER_RECEIPT_BINDING_INVALID", "producer receipt target oracle path is not exact")
    oracle_hash = _sha256(oracle_path)
    if _normalized_sha256(receipt.get("target_population_oracle_sha256")) != oracle_hash:
        _fail("PRODUCER_RECEIPT_BINDING_INVALID", "producer receipt target oracle SHA-256 is not exact")
    persisted_oracle = _read_object(oracle_path, "persisted target oracle")
    if persisted_oracle != dict(oracle):
        _fail("PRODUCER_RECEIPT_BINDING_INVALID", "in-memory target oracle differs from the persisted oracle")
    if not _same_path(oracle.get("producer_receipt_path"), receipt_path):
        _fail("PRODUCER_RECEIPT_BINDING_INVALID", "target oracle producer_receipt_path is not exact")
    if not _same_path(receipt.get("authoritative_completion_marker"), receipt_path):
        _fail("PRODUCER_RECEIPT_BINDING_INVALID", "producer receipt completion marker is not exact")

    final_evidence = receipt.get("final_evidence_sha256")
    if not isinstance(final_evidence, Mapping) or not FINAL_EVIDENCE_KEYS <= set(final_evidence):
        _fail("PRODUCER_FINAL_EVIDENCE_INVALID", "producer receipt final_evidence_sha256 is incomplete")
    final_hashes = {
        str(key): _normalized_sha256(value) for key, value in final_evidence.items()
    }
    if any(value is None for value in final_hashes.values()):
        _fail("PRODUCER_FINAL_EVIDENCE_INVALID", "producer receipt final_evidence_sha256 contains a malformed hash")
    if final_hashes["source"] != drawing_id or final_hashes["observation_oracle"] != oracle_hash:
        _fail("PRODUCER_FINAL_EVIDENCE_INVALID", "producer receipt final evidence does not bind source/oracle SHA-256")

    def _bound_file(binding_value: Any, label: str) -> Path:
        path = Path(str(binding_value or "")).resolve()
        if not path.is_file():
            _fail("PRODUCER_FINAL_EVIDENCE_INVALID", f"binding file for {label} is missing")
        return path

    staged_path = _bound_file(binding.get("staged_path"), "staged_dwg")
    raw_path = _bound_file(binding.get("native_job_out_path"), "native_job_out")
    attended = binding.get("attended_final_receipt")
    if not isinstance(attended, Mapping):
        _fail("PRODUCER_FINAL_EVIDENCE_INVALID", "binding attended_final_receipt is missing")
    attended_path = _bound_file(attended.get("path"), "attended_final_receipt")
    manifest = binding.get("native_build_manifest")
    if not isinstance(manifest, Mapping):
        _fail("PRODUCER_FINAL_EVIDENCE_INVALID", "binding native_build_manifest is missing")
    manifest_path = _bound_file(manifest.get("path"), "native_build_manifest")
    expected_final_hashes = {
        "source": _sha256(source_path),
        "staged_dwg": _sha256(staged_path),
        "native_job_out": _sha256(raw_path),
        "attended_final_receipt": _sha256(attended_path),
        "binding": _sha256(binding_path),
        "observation_oracle": oracle_hash,
        "native_build_manifest": _sha256(manifest_path),
    }
    if any(final_hashes[key] != value for key, value in expected_final_hashes.items()):
        _fail("PRODUCER_FINAL_EVIDENCE_INVALID", "producer receipt final evidence hash does not match a bound file")

    targets = oracle["targets"]
    seen_target_ids: set[str] = set()
    seen_layers: set[str] = set()
    seen_segment_ids: set[str] = set()
    for index, target in enumerate(targets):
        target_id = str(target["target_id"])
        layer = str(target["layer"])
        ids = target["native_visible_segment_ids"]
        if target_id in seen_target_ids or layer in seen_layers:
            _fail("TARGET_RECORDS_NOT_EXACT", f"target record {index} duplicates target_id or layer")
        seen_target_ids.add(target_id)
        seen_layers.add(layer)
        if len(ids) != target["native_visible_source_segments"]:
            _fail("TARGET_RECORDS_NOT_EXACT", f"target record {index} visible count does not equal stable ID count")
        if seen_segment_ids.intersection(ids):
            _fail("TARGET_RECORDS_NOT_EXACT", f"target record {index} reuses a stable visible segment ID")
        seen_segment_ids.update(ids)
        if target["expected_source_segments"] != (
            target["native_visible_source_segments"] + target["clipped_away_source_segments"]
        ):
            _fail("TARGET_RECORDS_NOT_EXACT", f"target record {index} violates expected=visible+clipped conservation")
        if geometry_scope == "strict_layer_entities_v1" and any(
            target[field] != 0
            for field in (
                "excluded_curved_source_segments",
                "excluded_degenerate_source_segments",
                "excluded_unsupported_entity_templates",
            )
        ):
            _fail("TARGET_RECORDS_NOT_EXACT", f"strict target record {index} contains excluded geometry")

    return {
        "oracle_path": str(oracle_path),
        "oracle_sha256": oracle_hash,
        "producer_receipt_path": str(receipt_path),
        "producer_receipt_sha256": _sha256(receipt_path),
        "source_path": str(source_path),
        "source_sha256": drawing_id,
        "geometry_scope": geometry_scope,
        "target_count": len(targets),
        "visible_segment_count": len(seen_segment_ids),
        "evidence": checked_evidence,
    }
