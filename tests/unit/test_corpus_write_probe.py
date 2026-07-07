#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for tools/corpus_write_probe.py (synthetic, no AutoCAD).

WHY: the corpus write prober is a safety gate for production drawings -- these
tests pin sha-guard refusal, envelope shape, resumability, original-unchanged
detection, and unsupported-op refusal using a monkeypatched patch_engine so no
native host is required.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import corpus_batch  # noqa: E402
import corpus_write_probe as probe  # noqa: E402


PATCH_SCHEMA_ID = "ariadne.cad_patch.v1"
NATIVE_MAP = {"create_layer": "write.layer.create", "create_line": "write.entity.line"}


def _fake_patch_engine(*, dry_status="planned", apply_status="ok", original_unchanged=True,
                       staged_bytes=b"STAGED-MUTATED", reason=None):
    """Minimal patch_engine stand-in for run_probe_file."""

    def dry_run_plan(patch):
        guards_ok = patch.get("policy", {}).get("write_mode") != "write_original"
        return {
            "status": "rejected" if dry_status == "rejected" or not guards_ok else dry_status,
            "guards_ok": guards_ok,
            "notes": [],
        }

    def apply_staged(patch, dwg_path, out_dir):
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        staged_out = Path(out_dir) / "staged_output.dwg"
        staged_out.write_bytes(staged_bytes)
        orig_proof = {"unchanged": original_unchanged, "sha256_before": "abc", "sha256_after": "abc"}
        if not original_unchanged:
            orig_proof["sha256_after"] = "mutated"
        return {
            "status": apply_status,
            "reason": reason,
            "original_unchanged": orig_proof,
            "staged_output": str(staged_out),
            "artifacts": [{"kind": "dwg_staged", "ref": str(staged_out)}],
            "diff_summary": {"layers_added": 1} if apply_status == "ok" else None,
        }

    return SimpleNamespace(
        PATCH_SCHEMA_ID=PATCH_SCHEMA_ID,
        NATIVE_WRITE_OP_MAP=dict(NATIVE_MAP),
        dry_run_plan=dry_run_plan,
        apply_staged=apply_staged,
    )


def _entry(ordinal: int, path: Path, sha: str | None = None) -> corpus_batch.CorpusEntry:
    return corpus_batch.CorpusEntry(
        ordinal=ordinal,
        source_path=str(path),
        expected_sha256=sha,
        input_kind="manifest",
    )


def test_resolve_patch_op_rejects_unsupported():
    with pytest.raises(ValueError, match="unsupported op"):
        probe.resolve_patch_op("create_hatch", NATIVE_MAP)


def test_resolve_patch_op_rejects_write_original():
    with pytest.raises(ValueError, match="NEVER permitted"):
        probe.resolve_patch_op("write_original", NATIVE_MAP)


def test_load_sample_entries_takes_first_n_rows_in_order(tmp_path):
    manifest = tmp_path / "manifest.json"
    paths = []
    for i in range(5):
        p = tmp_path / ("f%d.dwg" % i)
        p.write_bytes(b"x%d" % i)
        paths.append(str(p))
    manifest.write_text(json.dumps([{"path": p} for p in paths]), encoding="utf-8")

    sample = probe.load_sample_entries(manifest, 2)

    assert [e.ordinal for e in sample] == [0, 1]
    assert [e.source_path for e in sample] == paths[:2]


def test_build_envelope_shape():
    env = probe.build_envelope(
        ordinal=3,
        source_path="C:/a.dwg",
        source_sha256="deadbeef",
        sha_match=True,
        op="create_layer",
        dry_run_status="planned",
        apply_status="ok",
        original_unchanged=True,
        staged_result_sha256="cafe",
        error_class=None,
    )
    assert env["schema"] == probe.ENVELOPE_SCHEMA
    assert set(env) >= {
        "ordinal",
        "source_path",
        "source_sha256",
        "sha_match",
        "op",
        "dry_run_status",
        "apply_status",
        "original_unchanged",
        "staged_result_sha256",
        "error_class",
    }


def test_sha_guard_refuses_drift_without_apply(tmp_path):
    dwg = tmp_path / "sample.dwg"
    dwg.write_bytes(b"same-bytes")
    actual_sha = probe._sha256_file(dwg)
    entry = _entry(0, dwg, sha="0" * 64)
    pe = _fake_patch_engine()
    with mock.patch.object(pe, "apply_staged", wraps=pe.apply_staged) as apply_mock:
        env = probe.run_probe_file(entry, "create_layer", tmp_path / "case", patch_engine=pe)
    apply_mock.assert_not_called()
    assert env["error_class"] == "sha_mismatch"
    assert env["sha_match"] is False
    assert env["apply_status"] is None
    assert actual_sha != "0" * 64


def test_run_probe_file_success_envelope(tmp_path):
    dwg = tmp_path / "sample.dwg"
    dwg.write_bytes(b"source-bytes")
    sha = probe._sha256_file(dwg)
    entry = _entry(0, dwg, sha=sha)
    pe = _fake_patch_engine(staged_bytes=b"mutated-staged")
    env = probe.run_probe_file(entry, "create_layer", tmp_path / "case", patch_engine=pe)
    assert env["error_class"] is None
    assert env["apply_status"] == "ok"
    assert env["dry_run_status"] == "planned"
    assert env["original_unchanged"] is True
    assert env["staged_result_sha256"] == probe._sha256_file(
        tmp_path / "case" / "patch_apply" / "staged_output.dwg"
    )


def test_original_unchanged_assertion_fires_on_simulated_mutation(tmp_path):
    dwg = tmp_path / "sample.dwg"
    dwg.write_bytes(b"source-bytes")
    sha = probe._sha256_file(dwg)
    entry = _entry(0, dwg, sha=sha)
    pe = _fake_patch_engine(original_unchanged=False)
    env = probe.run_probe_file(entry, "create_layer", tmp_path / "case", patch_engine=pe)
    assert env["error_class"] == "original_mutated"
    assert env["original_unchanged"] is False
    assert probe.aggregate_exit_code([env]) == probe.EXIT_FAILURE


def test_resume_skips_existing_envelope(tmp_path):
    manifest = tmp_path / "manifest.json"
    dwg = tmp_path / "a.dwg"
    dwg.write_bytes(b"dwg")
    sha = probe._sha256_file(dwg)
    manifest.write_text(json.dumps([{"path": str(dwg), "sha256": sha}]), encoding="utf-8")
    out_dir = tmp_path / "run"
    pe = _fake_patch_engine()

    first_envs, _ = probe.run_probe(
        manifest_path=str(manifest),
        sample=1,
        out_dir=str(out_dir),
        patch_op="create_layer",
        patch_engine=pe,
    )
    assert first_envs[0]["error_class"] is None

    with mock.patch.object(pe, "apply_staged") as apply_mock:
        second_envs, code = probe.run_probe(
            manifest_path=str(manifest),
            sample=1,
            out_dir=str(out_dir),
            patch_op="create_layer",
            patch_engine=pe,
        )
    apply_mock.assert_not_called()
    assert second_envs[0].get("resumed") is True
    assert code == probe.EXIT_OK


def test_main_unsupported_op_exits_safety(tmp_path, capsys):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("[]", encoding="utf-8")
    code = probe.main(
        [
            "--manifest",
            str(manifest),
            "--sample",
            "1",
            "--out-dir",
            str(tmp_path / "out"),
            "--op",
            "create_hatch",
        ]
    )
    assert code == probe.EXIT_SAFETY
    assert "unsupported op" in capsys.readouterr().err.lower()


def test_aggregate_exit_code_prioritizes_safety(tmp_path):
    ok = probe.build_envelope(
        ordinal=0,
        source_path="a",
        source_sha256="x",
        sha_match=True,
        op="create_layer",
        dry_run_status="planned",
        apply_status="ok",
        original_unchanged=True,
        staged_result_sha256="y",
        error_class=None,
    )
    fail = probe.build_envelope(
        ordinal=1,
        source_path="b",
        source_sha256="x",
        sha_match=True,
        op="create_layer",
        dry_run_status="planned",
        apply_status="partial",
        original_unchanged=True,
        staged_result_sha256=None,
        error_class="apply_failed",
    )
    safety = probe.build_envelope(
        ordinal=2,
        source_path="c",
        source_sha256="x",
        sha_match=False,
        op="create_layer",
        dry_run_status=None,
        apply_status=None,
        original_unchanged=None,
        staged_result_sha256=None,
        error_class="sha_mismatch",
    )
    assert probe.aggregate_exit_code([ok, fail]) == probe.EXIT_FAILURE
    assert probe.aggregate_exit_code([ok, safety, fail]) == probe.EXIT_SAFETY
