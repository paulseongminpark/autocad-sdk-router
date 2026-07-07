#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Staged-write corpus prober -- prove original untouched + staged write on a sample.

WHY: single-fixture write proofs do not scale to production drawings. This CLI
samples rows from a corpus manifest (same {path, sha256} shape as
tools/corpus_batch.py), drives patch_engine.dry_run_plan then apply_staged per
file, and emits per-file envelopes the orchestrator can aggregate. Sampling is
deterministic: the first N manifest rows in file order (not random, not sorted
by path) so reruns are comparable.

Hard rules: write_original is NEVER permitted; only patch ops with a live entry
in patch_engine.NATIVE_WRITE_OP_MAP are accepted; the source DWG byte-sha must
match the manifest when sha256 is present and must remain unchanged after apply.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import corpus_batch  # noqa: E402

ENVELOPE_FILE = "write_probe_envelope.json"
ENVELOPE_SCHEMA = "ariadne.corpus_write_probe.result.v1"
DEFAULT_PATCH_OP = "create_layer"
PROBE_LAYER_PREFIX = "ARIADNE_WPROBE_"

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_SAFETY = 2

SAFETY_ERROR_CLASSES = frozenset({"sha_mismatch", "safety_refusal", "unsupported_op"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: str | Path) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _json_dump(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _safe_name(value: str) -> str:
    cooked = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value.strip())
    cooked = cooked.strip("._")
    return cooked or "unnamed"


def probe_layer_name(ordinal: int) -> str:
    """Probe-unique layer name for create_layer writes (safe on any drawing)."""
    return "%s%04d" % (PROBE_LAYER_PREFIX, ordinal)


def load_sample_entries(manifest_path: str | Path, sample: int) -> List[corpus_batch.CorpusEntry]:
    """Return the first ``sample`` manifest rows in deterministic file order."""
    if sample < 1:
        raise ValueError("--sample must be >= 1")
    entries = corpus_batch.load_manifest_entries(manifest_path)
    if not entries:
        raise ValueError("manifest has no rows")
    return entries[:sample]


def resolve_patch_op(op: str, native_map: Dict[str, str]) -> str:
    """Resolve ``op`` to a patch-op id; refuse write_original and unknown ops."""
    raw = (op or "").strip()
    if not raw:
        raise ValueError("op must be a non-empty patch operation id")
    lowered = raw.lower()
    if lowered in ("write_original", "live_edit"):
        raise ValueError("write_original is NEVER permitted for corpus write probe")
    if raw in native_map:
        return raw
    reverse = {native: patch for patch, native in native_map.items()}
    if raw in reverse:
        return reverse[raw]
    raise ValueError(
        "unsupported op %r (supported patch ops: %s)"
        % (raw, ", ".join(sorted(native_map)))
    )


def build_probe_args(patch_op: str, ordinal: int) -> Dict[str, Any]:
    """Minimal safe args for the default probe op (create_layer) and close cousins."""
    if patch_op == "create_layer":
        return {"name": probe_layer_name(ordinal)}
    if patch_op == "create_line":
        return {
            "start": [0.0, 0.0, 0.0],
            "end": [1.0, 0.0, 0.0],
            "layer": "0",
        }
    # trivially small geometry on layer 0 for other entity create_* ops
    if patch_op.startswith("create_"):
        name = probe_layer_name(ordinal)
        if patch_op in ("create_dimstyle", "create_linetype", "create_textstyle",
                        "create_ucs", "create_view", "create_vport"):
            return {"name": name}
    raise ValueError("no safe probe args builder for patch op %r" % patch_op)


def build_probe_patch(
    patch_op: str,
    ordinal: int,
    dwg_path: str,
    apply_out_dir: str,
    *,
    patch_schema_id: str,
) -> Dict[str, Any]:
    """Build a cad_patch.v1 document that always targets a staged copy."""
    args = build_probe_args(patch_op, ordinal)
    postconditions: List[Dict[str, Any]]
    if patch_op == "create_layer":
        postconditions = [{"subject": "layer_exists", "op": "exists", "value": args["name"]}]
    elif patch_op.startswith("create_"):
        postconditions = [{"subject": "entity_count", "op": "delta_eq", "value": 1}]
    else:
        postconditions = []
    return {
        "schema": patch_schema_id,
        "patch_id": "corpus_write_probe/%04d/%s" % (ordinal, patch_op),
        "target_dwg": {
            "original_path": os.path.abspath(dwg_path),
            "staged_path": os.path.join(apply_out_dir, "staged_input.dwg"),
        },
        "operations": [{"step_id": "probe", "operation": patch_op, "args": args}],
        "postconditions": postconditions,
        "policy": {"staged_copy": True, "write_mode": "write_copy"},
    }


def should_resume_skip(envelope_path: str | Path) -> bool:
    """Skip when a prior envelope exists (resumable runs)."""
    envelope_path = Path(envelope_path)
    if not envelope_path.is_file():
        return False
    try:
        payload = json.loads(envelope_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(payload, dict) and payload.get("schema") == ENVELOPE_SCHEMA


def build_envelope(
    *,
    ordinal: int,
    source_path: str,
    source_sha256: Optional[str],
    sha_match: Optional[bool],
    op: str,
    dry_run_status: Optional[str],
    apply_status: Optional[str],
    original_unchanged: Optional[bool],
    staged_result_sha256: Optional[str],
    error_class: Optional[str],
    reason: Optional[str] = None,
    resumed: bool = False,
) -> Dict[str, Any]:
    env: Dict[str, Any] = {
        "schema": ENVELOPE_SCHEMA,
        "ordinal": ordinal,
        "source_path": source_path,
        "source_sha256": source_sha256,
        "sha_match": sha_match,
        "op": op,
        "dry_run_status": dry_run_status,
        "apply_status": apply_status,
        "original_unchanged": original_unchanged,
        "staged_result_sha256": staged_result_sha256,
        "error_class": error_class,
        "finished_at": _now_iso(),
    }
    if reason:
        env["reason"] = reason
    if resumed:
        env["resumed"] = True
    return env


def _staged_output_path(apply_result: Dict[str, Any], apply_out_dir: str) -> Optional[str]:
    extra = apply_result.get("staged_output")
    if isinstance(extra, str) and os.path.isfile(extra):
        return extra
    for artifact in apply_result.get("artifacts") or []:
        if not isinstance(artifact, dict):
            continue
        if artifact.get("kind") == "dwg_staged":
            ref = artifact.get("ref")
            if isinstance(ref, str) and ref.endswith("staged_output.dwg") and os.path.isfile(ref):
                return ref
    candidate = os.path.join(apply_out_dir, "staged_output.dwg")
    if os.path.isfile(candidate):
        return candidate
    return None


def _probe_effect_ok(
    source_sha256: Optional[str],
    staged_result_sha256: Optional[str],
    apply_result: Dict[str, Any],
) -> bool:
    """True when the staged artifact differs from the source and/or reports a diff."""
    if source_sha256 and staged_result_sha256 and staged_result_sha256 != source_sha256:
        return True
    diff_summary = apply_result.get("diff_summary")
    if isinstance(diff_summary, dict) and diff_summary:
        added = diff_summary.get("added") or diff_summary.get("entities_added")
        changed = diff_summary.get("changed") or diff_summary.get("entities_changed")
        if added or changed:
            return True
        if any(diff_summary.get(k) for k in ("layer_added", "layers_added", "records_added")):
            return True
    if apply_result.get("status") == "ok":
        # apply_staged only reaches ok after a real mutation path; byte change is
        # the primary signal when diff_summary is absent (sibling unavailable).
        return bool(
            source_sha256
            and staged_result_sha256
            and staged_result_sha256 != source_sha256
        )
    return False


def run_probe_file(
    entry: corpus_batch.CorpusEntry,
    patch_op: str,
    case_dir: Path,
    *,
    patch_engine: Any,
) -> Dict[str, Any]:
    """Probe one manifest row; returns the per-file envelope dict."""
    source_path = entry.source_path
    source_sha = _sha256_file(source_path)
    expected = entry.expected_sha256
    sha_match: Optional[bool]
    if expected:
        sha_match = bool(source_sha and source_sha.lower() == expected.lower())
        if not sha_match:
            return build_envelope(
                ordinal=entry.ordinal,
                source_path=source_path,
                source_sha256=source_sha,
                sha_match=False,
                op=patch_op,
                dry_run_status=None,
                apply_status=None,
                original_unchanged=None,
                staged_result_sha256=None,
                error_class="sha_mismatch",
                reason="manifest sha256 drift (expected %s, got %s)"
                % (expected, source_sha),
            )
    else:
        sha_match = None

    if not source_sha:
        return build_envelope(
            ordinal=entry.ordinal,
            source_path=source_path,
            source_sha256=None,
            sha_match=sha_match,
            op=patch_op,
            dry_run_status=None,
            apply_status=None,
            original_unchanged=None,
            staged_result_sha256=None,
            error_class="unreadable",
            reason="unable to read source file for sha256",
        )

    apply_out_dir = str(case_dir / "patch_apply")
    patch = build_probe_patch(
        patch_op,
        entry.ordinal,
        source_path,
        apply_out_dir,
        patch_schema_id=patch_engine.PATCH_SCHEMA_ID,
    )

    if patch.get("policy", {}).get("write_mode") == "write_original":
        return build_envelope(
            ordinal=entry.ordinal,
            source_path=source_path,
            source_sha256=source_sha,
            sha_match=sha_match,
            op=patch_op,
            dry_run_status=None,
            apply_status=None,
            original_unchanged=None,
            staged_result_sha256=None,
            error_class="safety_refusal",
            reason="write_original is NEVER permitted",
        )

    dry = patch_engine.dry_run_plan(patch)
    dry_status = dry.get("status")
    if dry_status == "rejected" or not dry.get("guards_ok"):
        return build_envelope(
            ordinal=entry.ordinal,
            source_path=source_path,
            source_sha256=source_sha,
            sha_match=sha_match,
            op=patch_op,
            dry_run_status=dry_status,
            apply_status=None,
            original_unchanged=None,
            staged_result_sha256=None,
            error_class="dry_run_rejected",
            reason="; ".join(dry.get("notes") or []) or "dry_run_plan rejected",
        )

    apply_result = patch_engine.apply_staged(patch, source_path, apply_out_dir)
    apply_status = apply_result.get("status")
    orig = apply_result.get("original_unchanged") or {}
    original_unchanged = orig.get("unchanged")
    staged_path = _staged_output_path(apply_result, apply_out_dir)
    staged_sha = _sha256_file(staged_path) if staged_path else None

    if original_unchanged is False:
        return build_envelope(
            ordinal=entry.ordinal,
            source_path=source_path,
            source_sha256=source_sha,
            sha_match=sha_match,
            op=patch_op,
            dry_run_status=dry_status,
            apply_status=apply_status,
            original_unchanged=False,
            staged_result_sha256=staged_sha,
            error_class="original_mutated",
            reason="original DWG byte-sha changed during apply",
        )

    after_source_sha = _sha256_file(source_path)
    if after_source_sha != source_sha:
        return build_envelope(
            ordinal=entry.ordinal,
            source_path=source_path,
            source_sha256=source_sha,
            sha_match=sha_match,
            op=patch_op,
            dry_run_status=dry_status,
            apply_status=apply_status,
            original_unchanged=False,
            staged_result_sha256=staged_sha,
            error_class="original_mutated",
            reason="source file sha256 changed after apply (expected %s, got %s)"
            % (source_sha, after_source_sha),
        )

    if apply_status != "ok":
        return build_envelope(
            ordinal=entry.ordinal,
            source_path=source_path,
            source_sha256=source_sha,
            sha_match=sha_match,
            op=patch_op,
            dry_run_status=dry_status,
            apply_status=apply_status,
            original_unchanged=original_unchanged,
            staged_result_sha256=staged_sha,
            error_class="apply_failed",
            reason=apply_result.get("reason") or ("apply_staged status %r" % apply_status),
        )

    if not _probe_effect_ok(source_sha, staged_sha, apply_result):
        return build_envelope(
            ordinal=entry.ordinal,
            source_path=source_path,
            source_sha256=source_sha,
            sha_match=sha_match,
            op=patch_op,
            dry_run_status=dry_status,
            apply_status=apply_status,
            original_unchanged=True,
            staged_result_sha256=staged_sha,
            error_class="probe_no_effect",
            reason="staged result identical to source or no diff evidence",
        )

    return build_envelope(
        ordinal=entry.ordinal,
        source_path=source_path,
        source_sha256=source_sha,
        sha_match=sha_match if sha_match is not None else True,
        op=patch_op,
        dry_run_status=dry_status,
        apply_status=apply_status,
        original_unchanged=True,
        staged_result_sha256=staged_sha,
        error_class=None,
    )


def aggregate_exit_code(envelopes: Sequence[Dict[str, Any]]) -> int:
    """0 clean, 2 if any sha/safety refusal, else 1 on any other failure."""
    if not envelopes:
        return EXIT_FAILURE
    any_safety = False
    any_failure = False
    for env in envelopes:
        if env.get("error_class") in SAFETY_ERROR_CLASSES:
            any_safety = True
        elif env.get("error_class") is not None:
            any_failure = True
        elif env.get("apply_status") != "ok":
            any_failure = True
    if any_safety:
        return EXIT_SAFETY
    if any_failure:
        return EXIT_FAILURE
    return EXIT_OK


def run_probe(
    *,
    manifest_path: str,
    sample: int,
    out_dir: str,
    patch_op: str,
    patch_engine: Any,
    force: bool = False,
) -> Tuple[List[Dict[str, Any]], int]:
    entries = load_sample_entries(manifest_path, sample)
    native_map = dict(patch_engine.NATIVE_WRITE_OP_MAP)
    resolved_op = resolve_patch_op(patch_op, native_map)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    envelopes: List[Dict[str, Any]] = []
    for entry in entries:
        stem = _safe_name(Path(entry.source_path).stem)
        case_dir = out / ("%04d_%s" % (entry.ordinal, stem))
        case_dir.mkdir(parents=True, exist_ok=True)
        envelope_path = case_dir / ENVELOPE_FILE
        if not force and should_resume_skip(envelope_path):
            payload = json.loads(envelope_path.read_text(encoding="utf-8"))
            payload["resumed"] = True
            envelopes.append(payload)
            continue
        envelope = run_probe_file(entry, resolved_op, case_dir, patch_engine=patch_engine)
        _json_dump(envelope, envelope_path)
        envelopes.append(envelope)
    return envelopes, aggregate_exit_code(envelopes)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prove staged-write correctness on a deterministic manifest sample "
            "(first N rows). Original DWGs stay read-only; write_original is refused."
        )
    )
    parser.add_argument("--manifest", required=True, help="JSON list of {path, sha256?} rows")
    parser.add_argument(
        "--sample",
        type=int,
        required=True,
        help="number of manifest rows to probe (first N rows in file order)",
    )
    parser.add_argument("--out-dir", required=True, help="output directory for per-file envelopes")
    parser.add_argument(
        "--op",
        default=DEFAULT_PATCH_OP,
        help=(
            "patch op id (default: %s -> write.layer.create with %s<ordinal> layer)"
            % (DEFAULT_PATCH_OP, PROBE_LAYER_PREFIX)
        ),
    )
    parser.add_argument("--force", action="store_true", help="re-run even when an envelope exists")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    import patch_engine  # local import for CLI and test injection symmetry

    try:
        resolve_patch_op(args.op, patch_engine.NATIVE_WRITE_OP_MAP)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_SAFETY
    _, code = run_probe(
        manifest_path=args.manifest,
        sample=args.sample,
        out_dir=args.out_dir,
        patch_op=args.op,
        patch_engine=patch_engine,
        force=args.force,
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
