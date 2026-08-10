from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
for value in (REPO, REPO / "tools"):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

import cadctl  # noqa: E402


def _raw_native_result(
    layer: str = "W1",
    geometry_scope: str = "strict_layer_entities_v1",
    *,
    excluded_curved_source_segments: int = 0,
    excluded_degenerate_source_segments: int = 0,
    excluded_unsupported_entity_templates: int = 0,
) -> dict:
    return {
        "schema": "ariadne.autocad_native_job_result.v1",
        "engine": "native_objectarx",
        "operation": "e2.inspect.xclip_membership",
        "result": {
            "schema": "ariadne.e2.native_xclip_membership_raw.v1",
            "oracle_method": "xclip_polygon_segment_intersection",
            "host_mode": "full_autocad",
            "native_membership_resolved": True,
            "drawing_path": None,
            "geometry_scope": geometry_scope,
            "target_layers": [layer],
            "layer_summary": [
                {
                    "layer": layer,
                    "native_source_entity_templates": 1,
                    "expected_source_segments": 2,
                    "native_visible_source_segments": 1,
                    "clipped_away_source_segments": 1,
                    "excluded_curved_source_segments": excluded_curved_source_segments,
                    "excluded_degenerate_source_segments": excluded_degenerate_source_segments,
                    "excluded_unsupported_entity_templates": excluded_unsupported_entity_templates,
                }
            ],
            "records": [
                {
                    "source_def_handle": "D1",
                    "source_entity_handle": "E1",
                    "source_layer": layer,
                    "lineage_path": [
                        {
                            "source_def_handle": "MS",
                            "insert_entity_handle": "B1",
                            "target_def_handle": "D1",
                            "array_row_index": 0,
                            "array_col_index": 0,
                        }
                    ],
                    "subentity_ordinal": 0,
                    "clip_fragment_ordinal": 0,
                    "active_xclip_handles": [],
                    "p0_world": [0.0, 0.0],
                    "p1_world": [10.0, 0.0],
                }
            ],
        },
        "status": "ok",
    }


def _bind_raw_to_staged(raw: dict, staged_dwg: str) -> dict:
    raw["result"]["drawing_path"] = str(Path(staged_dwg).resolve())
    return raw


def _final_launcher_envelope(operation: str, job_out: Path) -> dict:
    """Compact post-cleanup receipt required before a display PASS."""
    return {
        "schema": "ariadne.cad_os.attended_job_result.v1",
        "phase": "finalized",
        "status": "ok",
        "run_id": job_out.parent.name,
        "operation": operation,
        "read_only_operation": True,
        "staged_save_attempted": False,
        "receipt_authority": "powershell_launcher",
        "recovered_from_launcher_finalization_hang": False,
        "launched_pid": 4242,
        "launched_process_name": "acad",
        "launched_start_time_utc": "2026-08-10T00:00:01.0000000Z",
        "dedicated_instance": True,
        "timed_out": False,
        "launched_pid_closed": True,
        "launched_pid_identity_verified": True,
        "launched_pid_reused": False,
        "pre_existing_pids": [],
        "pre_existing_processes": [],
        "pre_existing_still_alive": [],
        "pre_existing_identity_verified": True,
        "user_session_touched": False,
        "job_out": str(job_out),
        "job_out_present": True,
        "degraded": False,
        "security": {"restored": True},
    }


def _persist_final_launcher_envelope(operation: str, job_out: Path) -> tuple[dict, Path]:
    envelope = _final_launcher_envelope(operation, job_out)
    receipt_path = job_out.parent / "attended_job_final_receipt.json"
    receipt_path.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return envelope, receipt_path


def _successful_attended_result(
    staged_dwg: str,
    run_dir: str,
    operation: str,
    *,
    raw: dict | None = None,
    envelope_mutator=None,
) -> dict:
    run_path = Path(run_dir)
    run_path.mkdir(parents=True, exist_ok=True)
    job_out = run_path / "job_out.json"
    bound = _bind_raw_to_staged(raw or _raw_native_result(), staged_dwg)
    job_out.write_text(json.dumps(bound), encoding="utf-8")
    envelope = _final_launcher_envelope(operation, job_out)
    if envelope_mutator is not None:
        envelope_mutator(envelope)
    final_receipt = run_path / "attended_job_final_receipt.json"
    final_receipt.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "command": ["acad.exe"],
        "exit_code": 0,
        "result": bound,
        "error": None,
        "timed_out": False,
        "envelope": envelope,
        "result_json": str(final_receipt),
        "staged_used": staged_dwg,
        "stdout_path": None,
        "stderr_path": None,
        "degraded": False,
    }


def _source_tree_digest(inputs: list[dict]) -> str:
    """Independent fixture encoding for the documented native source digest."""
    digest = hashlib.sha256()
    for entry in inputs:
        digest.update(
            f"{entry['path']}\0{entry['sha256']}\0{entry['bytes']}\n".encode("utf-8")
        )
    return digest.hexdigest()


def _fake_x64_pe(tag: bytes) -> bytes:
    """Small independent PE32+ DLL fixture; it is structural, never executable."""
    image = bytearray(512)
    image[0:2] = b"MZ"
    image[0x3C:0x40] = (0x80).to_bytes(4, "little")
    image[0x80:0x84] = b"PE\x00\x00"
    image[0x84:0x86] = (0x8664).to_bytes(2, "little")
    image[0x86:0x88] = (1).to_bytes(2, "little")
    image[0x94:0x96] = (0xF0).to_bytes(2, "little")
    image[0x96:0x98] = (0x2000).to_bytes(2, "little")
    image[0x98:0x9A] = (0x20B).to_bytes(2, "little")
    image[0x1C0 : 0x1C0 + len(tag)] = tag
    return bytes(image)


def _git(router: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(router), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout


def _native_source_git_state(router: Path) -> dict:
    """Independent fixture encoding for the native-source Git binding."""
    status = _git(
        router,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        "src/Ariadne.AcadNative",
        "src/Ariadne.AcadNativeDbx",
    )
    status_text = "\n".join(status.splitlines())
    return {
        "available": True,
        "head": _git(router, "rev-parse", "HEAD").strip(),
        "native_source_dirty": bool(status_text),
        "native_source_status_sha256": hashlib.sha256(
            status_text.encode("utf-8")
        ).hexdigest(),
    }


def _prepare_current_native_checkout(router: Path) -> Path:
    """Create a real, clean Git checkout plus a independently hash-bound build.

    The production verifier still recomputes all Git, source, and artifact facts;
    this fixture only supplies the kind of manifest a successful build would emit.
    """
    native_src = router / "src" / "Ariadne.AcadNative"
    dbx_src = router / "src" / "Ariadne.AcadNativeDbx"
    native_bin = native_src / "bin" / "x64" / "Release"
    native_bin.mkdir(parents=True)
    (native_src / "AriadneNativeJob.cpp").write_text("// native source\n", encoding="utf-8")
    (dbx_src / "AriadneDbxEntry.cpp").parent.mkdir(parents=True, exist_ok=True)
    (dbx_src / "AriadneDbxEntry.cpp").write_text("// dbx source\n", encoding="utf-8")
    recipe = router / "tools" / "build_native_acad.ps1"
    recipe.parent.mkdir(parents=True, exist_ok=True)
    recipe.write_text("# fixture native build recipe\n", encoding="utf-8")
    (router / ".gitignore").write_text("bin/\nobj/\n.vs/\nbuild/\n", encoding="utf-8")

    _git(router, "init", "-q")
    _git(router, "add", ".")
    _git(
        router,
        "-c",
        "user.name=Display Membership Test",
        "-c",
        "user.email=display-membership@example.invalid",
        "commit",
        "-qm",
        "fixture checkout",
    )

    artifact_bytes = {
        "Ariadne.AcadNativeDbx.dbx": _fake_x64_pe(b"dbx"),
        "Ariadne.AcadNative.crx": _fake_x64_pe(b"crx"),
        "Ariadne.AcadNative.arx": _fake_x64_pe(b"arx"),
    }
    for leaf, content in artifact_bytes.items():
        (native_bin / leaf).write_bytes(content)

    source_inputs = []
    for path in sorted((native_src / "AriadneNativeJob.cpp", dbx_src / "AriadneDbxEntry.cpp"), key=lambda p: p.as_posix()):
        payload = path.read_bytes()
        source_inputs.append(
            {
                "path": path.relative_to(router).as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
        )
    manifest = {
        "schema": "ariadne.cad_os.native_build_manifest.v1",
        "schema_version": 1,
        "claim_scope": "release_build_integrity_bundle",
        "build_target": "Rebuild",
        "configuration": "Release",
        "platform": "x64",
        "load_bin_dir": str(native_bin.resolve()),
        "checkout": {
            "root": str(router.resolve()),
            "git": _native_source_git_state(router),
        },
        "build_recipe": {
            "path": "tools/build_native_acad.ps1",
            "sha256": hashlib.sha256(recipe.read_bytes()).hexdigest(),
        },
        "source_tree": {
            "algorithm": "sha256",
            "digest": _source_tree_digest(source_inputs),
            "inputs": source_inputs,
        },
        "artifacts": [
            {
                "leaf": leaf,
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
                "current": True,
                "pe_verification": {
                    "verified": True,
                    "machine": "0x8664",
                    "format": "PE32+",
                    "minimum_bytes": 512,
                    "pe_header_offset": 128,
                    "section_count": 1,
                    "optional_header_bytes": 240,
                    "reason": "fixture x64 PE32+ DLL image",
                },
            }
            for leaf, content in artifact_bytes.items()
        ],
        "display_membership": {
            "ready": True,
            "canonical_arx_current": True,
        },
    }
    (native_bin / "native_build_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    assert _git(router, "status", "--porcelain=v1", "--untracked-files=all") == ""
    return native_bin


def test_cadctl_display_membership_is_attended_only_hash_bound_and_original_safe(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    native_bin = _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    calls = []

    def fail_headless(*args, **kwargs):
        raise AssertionError("headless run_job fallback must never be used")

    def fake_attended(staged_dwg, run_dir, operation, args, **kwargs):
        calls.append(
            {
                "staged_dwg": staged_dwg,
                "run_dir": run_dir,
                "operation": operation,
                "args": args,
                **kwargs,
            }
        )
        staged_path = Path(staged_dwg)
        staged_stat = staged_path.stat()
        observed_attributes = getattr(staged_stat, "st_file_attributes", 0)
        assert os.name == "nt"
        assert staged_path.read_bytes() == source.read_bytes()
        assert observed_attributes & stat.FILE_ATTRIBUTE_READONLY
        assert not (
            stat.S_IMODE(staged_stat.st_mode)
            & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
        )
        with pytest.raises(OSError):
            with staged_path.open("r+b") as staged_stream:
                staged_stream.write(b"forbidden-staged-mutation")
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        job_out = run_path / "job_out.json"
        raw = _bind_raw_to_staged(_raw_native_result(), staged_dwg)
        job_out.write_text(json.dumps(raw), encoding="utf-8")
        envelope, final_receipt = _persist_final_launcher_envelope(
            operation, job_out
        )
        return {
            "command": ["acad.exe"],
            "exit_code": 0,
            "stdout_path": str(run_path / "stdout.txt"),
            "stderr_path": str(run_path / "stderr.txt"),
            "envelope": envelope,
            "result_json": str(final_receipt),
            "result": raw,
            "staged_used": staged_dwg,
            "timed_out": False,
            "error": None,
            "degraded": False,
            "degraded_reason": None,
        }

    monkeypatch.setattr(cadctl.run_job, "run_router_cad_job", fail_headless)
    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", fake_attended)

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(out_dir)
    )

    assert result["status"] == "PASS"
    assert result["execution_context"] == "dedicated_full_autocad"
    assert result["original_unchanged"] is True
    assert result["original_sha256_before"] == source_hash
    assert result["original_sha256_after"] == source_hash
    assert calls[0]["operation"] == "e2.inspect.xclip_membership"
    assert calls[0]["args"]["geometry_scope"] == "strict_layer_entities_v1"
    assert calls[0]["native_bin_dir"] == str(native_bin)
    assert Path(calls[0]["staged_dwg"]) != source
    assert Path(calls[0]["staged_dwg"]).read_bytes() == source.read_bytes()

    oracle_path = Path(result["target_population_oracle"])
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    assert oracle["schema"] == "ariadne.e2.target_population_oracle.v1"
    assert oracle["oracle"] == "autocad.native_display_membership.v1"
    assert oracle["status"] == "OBSERVED"
    assert oracle["claim_scope"] == "instrument_observation_only"
    assert oracle["producer_receipt_required"] is True
    assert Path(oracle["producer_receipt_path"]) == Path(result["receipt"])
    assert oracle["downstream_experiment_guard_required"] is True
    assert oracle["drawing_id"] == source_hash
    assert oracle["geometry_scope"] == "strict_layer_entities_v1"
    assert oracle["targets"][0]["native_visible_source_segments"] == 1
    assert len(oracle["targets"][0]["native_visible_segment_ids"]) == 1
    assert len(oracle["targets"][0]["native_visible_segment_ids"][0]) == 64
    assert oracle["evidence"]
    for evidence in oracle["evidence"]:
        evidence_path = Path(evidence["path"])
        assert evidence_path.is_file()
        assert hashlib.sha256(evidence_path.read_bytes()).hexdigest() == evidence["sha256"]

    binding = json.loads(Path(result["binding_evidence"]).read_text(encoding="utf-8"))
    raw_job_out = Path(binding["native_job_out_path"])
    assert binding["native_job_out_sha256"] == hashlib.sha256(raw_job_out.read_bytes()).hexdigest()
    assert binding["native_build_manifest"]["path"] == result["build_manifest_path"]
    assert binding["native_build_manifest"]["sha256"] == result["build_manifest_sha256"]
    assert result["build_manifest_validation"]["before"]["valid"] is True

    receipt_path = Path(result["receipt"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["claim_scope"] == "instrument_observation_only"
    assert receipt["authoritative_completion_marker"] == str(receipt_path)
    launcher_evidence = receipt["attended_final_receipt_evidence"]
    launcher_path = Path(launcher_evidence["path"])
    assert launcher_path == out_dir / "attended" / "attended_job_final_receipt.json"
    assert launcher_evidence["bytes"] == launcher_path.stat().st_size
    assert launcher_evidence["sha256"] == hashlib.sha256(
        launcher_path.read_bytes()
    ).hexdigest()
    assert receipt["final_evidence_sha256"]["source"] == source_hash
    assert receipt["final_evidence_sha256"]["staged_dwg"] == source_hash
    assert receipt["final_evidence_sha256"]["attended_final_receipt"] == (
        launcher_evidence["sha256"]
    )
    assert receipt["staged_read_only_evidence"]["required"] is True
    assert receipt["staged_read_only_evidence"]["before_launch"]["read_only"] is True
    assert receipt["staged_read_only_evidence"]["after_execution"]["read_only"] is True
    assert binding["attended_final_receipt"] == launcher_evidence
    assert receipt["final_evidence_sha256"]["observation_oracle"] == result[
        "target_population_oracle_sha256"
    ]
    receipt_before = receipt_path.read_bytes()
    repeated = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(out_dir)
    )
    assert repeated["status"] == "BLOCKED"
    assert repeated["executed"] is False
    assert repeated["evidence_preserved"] is True
    assert receipt_path.read_bytes() == receipt_before
    assert len(calls) == 1


def test_cadctl_display_membership_binds_linear_scope_and_rejects_native_scope_mismatch(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    native_bin = _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    calls = []

    def fake_attended(staged_dwg, run_dir, operation, args, **kwargs):
        calls.append(args)
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        raw = _raw_native_result(
            geometry_scope=args["geometry_scope"],
            excluded_curved_source_segments=2,
            excluded_degenerate_source_segments=3,
            excluded_unsupported_entity_templates=1,
        )
        _bind_raw_to_staged(raw, staged_dwg)
        job_out = run_path / "job_out.json"
        job_out.write_text(json.dumps(raw), encoding="utf-8")
        envelope, final_receipt = _persist_final_launcher_envelope(
            operation, job_out
        )
        return {
            "result": raw,
            "error": None,
            "timed_out": False,
            "result_json": str(final_receipt),
            "stdout_path": None,
            "stderr_path": None,
            "envelope": envelope,
            "degraded": False,
        }

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", fake_attended)
    out_dir = tmp_path / "linear"
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source),
        ["W1"],
        str(out_dir),
        geometry_scope="linear_segments_v1",
    )

    assert result["status"] == "PASS"
    assert result["geometry_scope"] == "linear_segments_v1"
    assert calls == [{"target_layers": ["W1"], "geometry_scope": "linear_segments_v1"}]
    oracle = json.loads(Path(result["target_population_oracle"]).read_text(encoding="utf-8"))
    binding = json.loads(Path(result["binding_evidence"]).read_text(encoding="utf-8"))
    receipt = json.loads(Path(result["receipt"]).read_text(encoding="utf-8"))
    assert oracle["geometry_scope"] == "linear_segments_v1"
    assert oracle["targets"][0]["excluded_curved_source_segments"] == 2
    assert oracle["targets"][0]["excluded_degenerate_source_segments"] == 3
    assert oracle["targets"][0]["excluded_unsupported_entity_templates"] == 1
    assert binding["geometry_scope"] == "linear_segments_v1"
    assert receipt["geometry_scope"] == "linear_segments_v1"

    def mismatched_scope_attended(staged_dwg, run_dir, operation, args, **kwargs):
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        raw = _bind_raw_to_staged(
            _raw_native_result(geometry_scope="strict_layer_entities_v1"), staged_dwg
        )
        job_out = run_path / "job_out.json"
        job_out.write_text(json.dumps(raw), encoding="utf-8")
        envelope, final_receipt = _persist_final_launcher_envelope(
            operation, job_out
        )
        return {
            "result": raw,
            "error": None,
            "timed_out": False,
            "result_json": str(final_receipt),
            "stdout_path": None,
            "stderr_path": None,
            "envelope": envelope,
            "degraded": False,
        }

    monkeypatch.setattr(
        cadctl.attended_lane, "run_attended_native_job", mismatched_scope_attended
    )
    mismatch = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source),
        ["W1"],
        str(tmp_path / "mismatch"),
        geometry_scope="linear_segments_v1",
    )
    assert mismatch["status"] == "BLOCKED"
    assert "geometry_scope" in mismatch["reason"]


def test_cadctl_display_membership_rejects_unknown_geometry_scope_before_native_run(
    tmp_path: Path
):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"dwg")

    result = cadctl.Cad(router_home=tmp_path / "router").inspect_display_membership(
        str(source),
        ["W1"],
        str(tmp_path / "out"),
        geometry_scope="curve_segments_v1",
    )

    assert result["status"] == "BLOCKED"
    assert result["executed"] is False
    assert result["geometry_scope"] == "curve_segments_v1"


def test_cadctl_display_membership_fails_closed_without_current_native_build(tmp_path: Path):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"dwg")
    result = cadctl.Cad(router_home=tmp_path / "router").inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )
    assert result["status"] == "NEEDS_BUILD"
    assert result["executed"] is False
    assert "manifest" in result["reason"]


def test_cadctl_display_membership_rejects_precleanup_receipt_without_final_launcher_verification(
    tmp_path: Path, monkeypatch
):
    """Raw job_out cannot certify the launcher's cleanup obligations.

    A pre-cleanup receipt deliberately lacks launched-PID closure, user-session
    safety, and security-restoration proof. Even a valid native measurement
    must remain BLOCKED rather than being promoted to the route's top-level PASS.
    """
    router = tmp_path / "router"
    native_bin = _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")

    def fake_precleanup_attended(staged_dwg, run_dir, operation, args, **kwargs):
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        raw = _bind_raw_to_staged(_raw_native_result(), staged_dwg)
        job_out = run_path / "job_out.json"
        job_out.write_text(json.dumps(raw), encoding="utf-8")
        return {
            "command": ["acad.exe"],
            "exit_code": 0,
            "stdout_path": str(run_path / "stdout.txt"),
            "stderr_path": str(run_path / "stderr.txt"),
            "envelope": {
                "schema": "ariadne.cad_os.attended_job_completion.v1",
                "phase": "cleanup_pending",
                "operation": operation,
                "launched_pid": 4242,
                "dedicated_instance": True,
                "timed_out": False,
                "job_out": str(job_out),
                "job_out_present": True,
                "cleanup_wait_sec": 45,
            },
            "result_json": str(run_path / "attended_job_completion.json"),
            "result": raw,
            "staged_used": staged_dwg,
            "timed_out": False,
            "error": None,
            "degraded": False,
            "degraded_reason": None,
        }

    monkeypatch.setattr(
        cadctl.attended_lane, "run_attended_native_job", fake_precleanup_attended
    )
    out_dir = tmp_path / "out"
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(out_dir)
    )

    assert result["status"] == "BLOCKED"
    assert result["executed"] is True
    assert "final" in result["reason"].lower()
    assert "target_population_oracle" not in result


def test_cadctl_display_membership_blocks_nonfresh_attended_artifacts_before_native_run(
    tmp_path: Path, monkeypatch
):
    """The route must reserve a fresh output directory before it can launch.

    An old ``out/attended`` may look like valid evidence, but it is neither a
    fresh producer directory nor an allowable launch target for a new drawing.
    """
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    attended_dir = out_dir / "attended"
    attended_dir.mkdir(parents=True)
    stale_job_out = attended_dir / "job_out.json"
    stale_job_out.write_text(json.dumps(_raw_native_result()), encoding="utf-8")
    stale_final = attended_dir / "attended_job_final_receipt.json"
    stale_final.write_text(
        json.dumps(_final_launcher_envelope("e2.inspect.xclip_membership", stale_job_out)),
        encoding="utf-8",
    )
    stale_job_out_before = stale_job_out.read_bytes()
    stale_final_before = stale_final.read_bytes()
    runner_calls = []

    def should_not_run(*args, **kwargs):
        runner_calls.append((args, kwargs))
        raise AssertionError("a nonfresh output directory must block before native launch")

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", should_not_run)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(out_dir)
    )

    assert result["status"] == "BLOCKED"
    assert result["executed"] is False
    assert "fresh" in result["reason"].lower()
    assert result["evidence_preserved"] is True
    assert runner_calls == []
    assert stale_job_out.read_bytes() == stale_job_out_before
    assert stale_final.read_bytes() == stale_final_before


def test_cadctl_display_membership_blocks_unknown_preexisting_output_child_before_launch(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    unknown = out_dir / "unrelated.txt"
    unknown.write_text("not this job\n", encoding="utf-8")
    runner_calls = []

    def should_not_run(*args, **kwargs):
        runner_calls.append((args, kwargs))
        raise AssertionError("an unknown output child must block before native launch")

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", should_not_run)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(out_dir)
    )

    assert result["status"] == "BLOCKED"
    assert result["executed"] is False
    assert "fresh" in result["reason"].lower()
    assert result["evidence_preserved"] is True
    assert runner_calls == []
    assert unknown.read_text(encoding="utf-8") == "not this job\n"
    assert not (out_dir / "display_membership_receipt.json").exists()


def test_cadctl_display_membership_requires_recovery_authority_evidence(
    tmp_path: Path, monkeypatch
):
    """A Python-authored final receipt is acceptable only when it openly
    records the independent validator's process-identity and helper-closure
    evidence.  It must not be a renamed degraded fallback."""
    router = tmp_path / "router"
    native_bin = _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    raw = _raw_native_result()

    def fake_incomplete_recovery(staged_dwg, run_dir, operation, args, **kwargs):
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        job_out = run_path / "job_out.json"
        _bind_raw_to_staged(raw, staged_dwg)
        job_out.write_text(json.dumps(raw), encoding="utf-8")
        receipt = _final_launcher_envelope(operation, job_out)
        receipt.update({
            "receipt_authority": "python_independent_safety_validator",
            "recovered_from_launcher_finalization_hang": True,
            "powershell_helper_closed": False,
            "launched_pid_identity_verified": True,
            "pre_existing_identity_verified": True,
            "launched_pid_reused": False,
        })
        return {
            "command": ["acad.exe"],
            "exit_code": 0,
            "stdout_path": str(run_path / "stdout.txt"),
            "stderr_path": str(run_path / "stderr.txt"),
            "envelope": receipt,
            "result_json": str(run_path / "attended_job_final_receipt.json"),
            "result": raw,
            "staged_used": staged_dwg,
            "timed_out": False,
            "error": None,
            "degraded": False,
            "degraded_reason": None,
        }

    monkeypatch.setattr(
        cadctl.attended_lane, "run_attended_native_job", fake_incomplete_recovery
    )
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )

    assert result["status"] == "BLOCKED"
    assert "powershell_helper_closed" in result["reason"]


def test_cadctl_display_membership_requires_identity_evidence_for_powershell_receipt(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    raw = _raw_native_result()

    def fake_missing_identity(staged_dwg, run_dir, operation, args, **kwargs):
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        job_out = run_path / "job_out.json"
        _bind_raw_to_staged(raw, staged_dwg)
        job_out.write_text(json.dumps(raw), encoding="utf-8")
        receipt = _final_launcher_envelope(operation, job_out)
        del receipt["launched_start_time_utc"]
        return {
            "command": ["acad.exe"],
            "exit_code": 0,
            "stdout_path": str(run_path / "stdout.txt"),
            "stderr_path": str(run_path / "stderr.txt"),
            "envelope": receipt,
            "result_json": str(run_path / "attended_job_final_receipt.json"),
            "result": raw,
            "staged_used": staged_dwg,
            "timed_out": False,
            "error": None,
            "degraded": False,
            "degraded_reason": None,
        }

    monkeypatch.setattr(
        cadctl.attended_lane, "run_attended_native_job", fake_missing_identity
    )
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )

    assert result["status"] == "BLOCKED"
    assert result["executed"] is True
    assert "launched_start_time_utc" in result["reason"]


def test_cadctl_display_membership_rejects_non_native_or_incomplete_result(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    native_bin = _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"dwg")
    raw = _raw_native_result()
    raw["result"]["host_mode"] = "coreconsole"

    def fake_non_native_attended(staged_dwg, run_dir, operation, args, **kwargs):
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        job_out = run_path / "job_out.json"
        _bind_raw_to_staged(raw, staged_dwg)
        job_out.write_text(json.dumps(raw), encoding="utf-8")
        envelope, final_receipt = _persist_final_launcher_envelope(
            operation, job_out
        )
        return {
            "result": raw,
            "error": None,
            "timed_out": False,
            "envelope": envelope,
            "result_json": str(final_receipt),
            "staged_used": staged_dwg,
            "exit_code": 0,
            "stdout_path": None,
            "stderr_path": None,
            "degraded": False,
            "degraded_reason": None,
        }

    monkeypatch.setattr(
        cadctl.attended_lane,
        "run_attended_native_job",
        fake_non_native_attended,
    )

    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )
    assert result["status"] == "BLOCKED"
    assert result["executed"] is True
    assert "full_autocad" in result["reason"]


def test_cadctl_display_membership_rejects_launcher_receipt_disk_memory_mismatch(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")

    def fake_attended(staged_dwg, run_dir, operation, args, **kwargs):
        result = _successful_attended_result(staged_dwg, run_dir, operation)
        disk_receipt = dict(result["envelope"])
        disk_receipt["launched_pid"] = disk_receipt["launched_pid"] + 1
        Path(result["result_json"]).write_text(
            json.dumps(disk_receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return result

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", fake_attended)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )

    assert result["status"] == "BLOCKED"
    assert result["executed"] is True
    assert "final_receipt_bytes" in result["reason"]
    assert "target_population_oracle" not in result


def test_cadctl_display_membership_requires_a_current_manifest_before_launch(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    (router / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp").write_text(
        "// modified after build\n", encoding="utf-8"
    )
    calls = []

    def should_not_run(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("a stale source tree must block before AutoCAD launch")

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", should_not_run)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )

    assert result["status"] == "NEEDS_BUILD"
    assert result["executed"] is False
    assert "source" in result["reason"].lower()
    assert calls == []


def test_cadctl_display_membership_ignores_unrelated_tracked_status_churn(
    tmp_path: Path, monkeypatch
):
    """A report change must not invalidate a native-source-bound build."""
    router = tmp_path / "router"
    native_bin = _prepare_current_native_checkout(router)
    report = router / "reports" / "autocad_router_status_latest.json"
    report.parent.mkdir(parents=True)
    report.write_text('{"status":"baseline"}\n', encoding="utf-8")
    _git(router, "add", str(report.relative_to(router)))
    _git(
        router,
        "-c",
        "user.name=Display Membership Test",
        "-c",
        "user.email=display-membership@example.invalid",
        "commit",
        "-qm",
        "tracked report baseline",
    )
    manifest_path = native_bin / "native_build_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checkout"]["git"] = _native_source_git_state(router)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    report.write_text('{"status":"unrelated churn"}\n', encoding="utf-8")
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    calls = []

    def fake_attended(staged_dwg, run_dir, operation, args, **kwargs):
        calls.append((staged_dwg, run_dir, operation, args, kwargs))
        run_path = Path(run_dir)
        raw = _bind_raw_to_staged(_raw_native_result(), staged_dwg)
        job_out = run_path / "job_out.json"
        job_out.write_text(json.dumps(raw), encoding="utf-8")
        envelope, final_receipt = _persist_final_launcher_envelope(
            operation, job_out
        )
        return {
            "command": ["acad.exe"],
            "exit_code": 0,
            "result": raw,
            "error": None,
            "timed_out": False,
            "envelope": envelope,
            "result_json": str(final_receipt),
            "stdout_path": None,
            "stderr_path": None,
            "degraded": False,
        }

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", fake_attended)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )

    assert result["status"] == "PASS"
    assert len(calls) == 1


def test_cadctl_display_membership_requires_current_build_recipe_before_launch(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    (router / "tools" / "build_native_acad.ps1").write_text(
        "# changed after native build\n", encoding="utf-8"
    )
    calls = []

    def should_not_run(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("a changed build recipe must block before AutoCAD launch")

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", should_not_run)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )

    assert result["status"] == "NEEDS_BUILD"
    assert result["executed"] is False
    assert "recipe" in result["reason"].lower()
    assert calls == []


def test_cadctl_display_membership_requires_current_canonical_arx_before_launch(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    native_bin = _prepare_current_native_checkout(router)
    manifest_path = native_bin / "native_build_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    arx = next(item for item in manifest["artifacts"] if item["leaf"] == "Ariadne.AcadNative.arx")
    arx["current"] = False
    manifest["display_membership"]["canonical_arx_current"] = False
    manifest["display_membership"]["ready"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    calls = []

    def should_not_run(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("a versioned ARX fallback must not certify canonical freshness")

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", should_not_run)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )

    assert result["status"] == "NEEDS_BUILD"
    assert result["executed"] is False
    assert "canonical" in result["reason"].lower()
    assert calls == []


def test_native_manifest_cannot_certify_hash_matched_non_pe_placeholders(tmp_path: Path):
    router = tmp_path / "router"
    native_bin = _prepare_current_native_checkout(router)
    artifact = native_bin / "Ariadne.AcadNative.arx"
    artifact.write_bytes(b"arx")
    manifest_path = native_bin / "native_build_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    item = next(
        row for row in manifest["artifacts"] if row["leaf"] == artifact.name
    )
    item["bytes"] = artifact.stat().st_size
    item["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    item["pe_verification"]["verified"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    verification = cadctl._verify_native_build_manifest(router, native_bin)

    assert verification["valid"] is False
    assert verification["checks"][f"artifact_pe:{artifact.name}"] is False
    assert any(artifact.name in error for error in verification["errors"])


def test_native_manifest_rejects_a_reparse_artifact_directory(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    native_bin = _prepare_current_native_checkout(router)
    real_check = cadctl._path_reparse_error

    def mark_native_bin(path: Path):
        if Path(path) == native_bin:
            return "simulated native-bin junction"
        return real_check(path)

    monkeypatch.setattr(cadctl, "_path_reparse_error", mark_native_bin)
    verification = cadctl._verify_native_build_manifest(router, native_bin)

    assert verification["valid"] is False
    assert "artifact directory" in verification["errors"][0]


def test_native_source_inventory_rejects_a_reparse_subdirectory(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    native_root = router / "src" / "Ariadne.AcadNative"
    dbx_root = router / "src" / "Ariadne.AcadNativeDbx"
    linked = native_root / "linked-source"
    linked.mkdir(parents=True)
    dbx_root.mkdir(parents=True)
    (native_root / "root.cpp").write_text("// source\n", encoding="utf-8")
    (dbx_root / "dbx.cpp").write_text("// source\n", encoding="utf-8")
    real_reparse = cadctl._is_reparse_point

    monkeypatch.setattr(
        cadctl,
        "_is_reparse_point",
        lambda path: Path(path) == linked or real_reparse(path),
    )

    with pytest.raises(OSError, match="reparse"):
        cadctl._native_source_inputs(router)


def test_cadctl_display_membership_rejects_memory_result_that_differs_from_raw_job_out(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")

    def fake_attended(staged_dwg, run_dir, operation, args, **kwargs):
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        job_out = run_path / "job_out.json"
        raw = _bind_raw_to_staged(_raw_native_result(), staged_dwg)
        job_out.write_text(json.dumps(raw), encoding="utf-8")
        memory_only = _bind_raw_to_staged(_raw_native_result(), staged_dwg)
        memory_only["result"]["records"][0]["p1_world"] = [999.0, 0.0]
        return {
            "command": ["acad.exe"],
            "exit_code": 0,
            "result": memory_only,
            "error": None,
            "timed_out": False,
            "envelope": _final_launcher_envelope(operation, job_out),
            "result_json": str(run_path / "attended_job_final_receipt.json"),
            "staged_used": staged_dwg,
            "stdout_path": None,
            "stderr_path": None,
            "degraded": False,
        }

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", fake_attended)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )

    assert result["status"] == "BLOCKED"
    assert result["executed"] is True
    assert "raw" in result["reason"].lower()
    assert "target_population_oracle" not in result


def test_cadctl_display_membership_rejects_unapproved_output_before_launch(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    approved_temp = tmp_path / "approved-temp"
    approved_temp.mkdir()
    unsafe_out = tmp_path / "unapproved-output"
    calls = []

    def should_not_run(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("unapproved output must block before AutoCAD launch")

    monkeypatch.setenv("TEMP", str(approved_temp))
    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", should_not_run)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(unsafe_out)
    )

    assert result["status"] == "BLOCKED"
    assert result["executed"] is False
    assert "output" in result["reason"].lower()
    assert calls == []
    assert not unsafe_out.exists()


def test_cadctl_display_membership_does_not_claim_execution_when_runner_never_launches(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")

    monkeypatch.setattr(
        cadctl.attended_lane,
        "run_attended_native_job",
        lambda *args, **kwargs: {
            "command": ["powershell", "-File", "run_attended_job.ps1"],
            "exit_code": None,
            "result": None,
            "error": "failed to launch attended runner: access denied",
            "timed_out": False,
            "envelope": None,
            "result_json": None,
            "stdout_path": None,
            "stderr_path": None,
            "degraded": False,
        },
    )
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )

    assert result["status"] == "BLOCKED"
    assert result["executed"] is False
    assert result["attended_command_constructed"] is True
    assert result["attended_launch_observed"] is False
    assert result["attended_launch_evidence"] == "none"


def test_cadctl_display_membership_does_not_pass_when_atomic_evidence_publish_loses_a_race(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")

    def fake_attended(staged_dwg, run_dir, operation, args, **kwargs):
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        job_out = run_path / "job_out.json"
        raw = _bind_raw_to_staged(_raw_native_result(), staged_dwg)
        job_out.write_text(json.dumps(raw), encoding="utf-8")
        return {
            "command": ["acad.exe"],
            "exit_code": 0,
            "result": raw,
            "error": None,
            "timed_out": False,
            "envelope": _final_launcher_envelope(operation, job_out),
            "result_json": str(run_path / "attended_job_final_receipt.json"),
            "staged_used": staged_dwg,
            "stdout_path": None,
            "stderr_path": None,
            "degraded": False,
        }

    def lose_publish_race(*args, **kwargs):
        raise FileExistsError("simulated competing evidence publisher")

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", fake_attended)
    monkeypatch.setattr(cadctl.os, "link", lose_publish_race)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )

    assert result["status"] == "BLOCKED"
    assert result["executed"] is True
    assert result["evidence_write_failed"] is True
    assert "target_population_oracle" not in result


def test_cadctl_display_membership_blocks_manifest_artifact_drift_after_launch(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    native_bin = _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")

    def fake_attended(staged_dwg, run_dir, operation, args, **kwargs):
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        job_out = run_path / "job_out.json"
        raw = _bind_raw_to_staged(_raw_native_result(), staged_dwg)
        job_out.write_text(json.dumps(raw), encoding="utf-8")
        (native_bin / "Ariadne.AcadNative.arx").write_bytes(b"changed-after-launch")
        return {
            "command": ["acad.exe"],
            "exit_code": 0,
            "result": raw,
            "error": None,
            "timed_out": False,
            "envelope": _final_launcher_envelope(operation, job_out),
            "result_json": str(run_path / "attended_job_final_receipt.json"),
            "staged_used": staged_dwg,
            "stdout_path": None,
            "stderr_path": None,
            "degraded": False,
        }

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", fake_attended)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )

    assert result["status"] == "BLOCKED"
    assert result["executed"] is True
    assert "manifest" in result["reason"].lower()
    assert "target_population_oracle" not in result


def test_attended_execution_state_does_not_infer_launch_from_exit_code():
    state = cadctl._attended_execution_state(
        {
            "command": ["powershell", "-File", "run_attended_job.ps1"],
            "exit_code": 2,
            "envelope": None,
        }
    )

    assert state == {
        "command_constructed": True,
        "launch_observed": False,
        "launch_evidence": "none",
    }


def test_strict_evidence_json_rejects_duplicate_keys_and_nonfinite_numbers():
    with pytest.raises(ValueError, match="duplicate"):
        cadctl._strict_json_loads('{"status":"ok","status":"blocked"}')
    with pytest.raises(ValueError, match="non-finite"):
        cadctl._strict_json_loads('{"count":NaN}')


def test_cadctl_display_membership_rejects_native_result_from_another_drawing(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")

    def fake_attended(staged_dwg, run_dir, operation, args, **kwargs):
        result = _successful_attended_result(staged_dwg, run_dir, operation)
        result["result"]["result"]["drawing_path"] = str(
            (tmp_path / "another.dwg").resolve()
        )
        Path(run_dir, "job_out.json").write_text(
            json.dumps(result["result"]), encoding="utf-8"
        )
        return result

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", fake_attended)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )

    assert result["status"] == "BLOCKED"
    assert "drawing_path" in result["reason"]


@pytest.mark.parametrize("boolean_surface", ["launched_pid", "native_counts"])
def test_cadctl_display_membership_rejects_json_booleans_as_integer_evidence(
    tmp_path: Path, monkeypatch, boolean_surface: str
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")

    def fake_attended(staged_dwg, run_dir, operation, args, **kwargs):
        raw = _raw_native_result()
        if boolean_surface == "native_counts":
            summary = raw["result"]["layer_summary"][0]
            summary.update(
                {
                    "native_source_entity_templates": True,
                    "expected_source_segments": True,
                    "native_visible_source_segments": True,
                    "clipped_away_source_segments": False,
                    "excluded_curved_source_segments": False,
                    "excluded_degenerate_source_segments": False,
                    "excluded_unsupported_entity_templates": False,
                }
            )

        def mutate_envelope(envelope: dict) -> None:
            if boolean_surface == "launched_pid":
                envelope["launched_pid"] = True

        return _successful_attended_result(
            staged_dwg,
            run_dir,
            operation,
            raw=raw,
            envelope_mutator=mutate_envelope,
        )

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", fake_attended)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )

    assert result["status"] == "BLOCKED"
    assert result["executed"] is (boolean_surface != "launched_pid")


@pytest.mark.parametrize(
    "malformation", ["numeric_handle", "duplicate_summary", "bad_clip_handle", "bad_point"]
)
def test_cadctl_display_membership_rejects_ambiguous_native_records(
    tmp_path: Path, monkeypatch, malformation: str
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")

    def fake_attended(staged_dwg, run_dir, operation, args, **kwargs):
        raw = _raw_native_result()
        record = raw["result"]["records"][0]
        if malformation == "numeric_handle":
            record["source_entity_handle"] = 123
        elif malformation == "duplicate_summary":
            raw["result"]["layer_summary"].append(
                dict(raw["result"]["layer_summary"][0])
            )
        elif malformation == "bad_clip_handle":
            record["active_xclip_handles"] = [False]
        else:
            record["p0_world"] = [0.0]
        return _successful_attended_result(
            staged_dwg, run_dir, operation, raw=raw
        )

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", fake_attended)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )

    assert result["status"] == "BLOCKED"


def test_failed_final_receipt_cannot_leave_an_independent_pass_oracle(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    original_writer = cadctl._atomic_write_json_no_overwrite

    def fake_attended(staged_dwg, run_dir, operation, args, **kwargs):
        return _successful_attended_result(staged_dwg, run_dir, operation)

    def fail_final_receipt(path, payload, *, before_publish=None):
        if path.name == "display_membership_receipt.json" and payload.get("status") == "PASS":
            raise OSError("simulated final receipt publication failure")
        return original_writer(path, payload, before_publish=before_publish)

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", fake_attended)
    monkeypatch.setattr(cadctl, "_atomic_write_json_no_overwrite", fail_final_receipt)
    out_dir = tmp_path / "out"
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(out_dir)
    )

    oracle = json.loads((out_dir / "target_population_oracle.json").read_text(encoding="utf-8"))
    assert result["status"] == "BLOCKED"
    assert oracle["status"] == "OBSERVED"
    assert oracle["producer_receipt_required"] is True
    assert not (out_dir / "display_membership_receipt.json").exists()


def test_successful_receipt_publish_is_not_retracted_by_temporary_cleanup_failure(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    real_unlink = Path.unlink
    cleanup_failure = {"observed": False}

    def fake_attended(staged_dwg, run_dir, operation, args, **kwargs):
        return _successful_attended_result(staged_dwg, run_dir, operation)

    def fail_after_receipt_publish(path: Path, *args, **kwargs):
        if (
            path.name.startswith(".display_membership_receipt.json.")
            and (path.parent / "display_membership_receipt.json").is_file()
        ):
            cleanup_failure["observed"] = True
            raise OSError("simulated post-publication temporary cleanup failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", fake_attended)
    monkeypatch.setattr(Path, "unlink", fail_after_receipt_publish)
    out_dir = tmp_path / "out"
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(out_dir)
    )

    persisted = json.loads(
        (out_dir / "display_membership_receipt.json").read_text(encoding="utf-8")
    )
    assert cleanup_failure["observed"] is True
    assert result["status"] == "PASS"
    assert persisted["status"] == "PASS"


def test_final_receipt_temporary_inode_is_locked_and_byte_verified_during_publish(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    out_dir = tmp_path / "out"
    real_link = cadctl.os.link
    race = {"blocked": False}

    def fake_attended(staged_dwg, run_dir, operation, args, **kwargs):
        return _successful_attended_result(staged_dwg, run_dir, operation)

    def forge_temporary_before_link(temporary, destination):
        if Path(destination).name == "display_membership_receipt.json":
            try:
                Path(temporary).write_text('{"status":"FORGED"}\n', encoding="utf-8")
            except OSError:
                race["blocked"] = True
        return real_link(temporary, destination)

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", fake_attended)
    monkeypatch.setattr(cadctl.os, "link", forge_temporary_before_link)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(out_dir)
    )

    persisted = json.loads(
        (out_dir / "display_membership_receipt.json").read_text(encoding="utf-8")
    )
    assert race["blocked"] is True
    assert result["status"] == "PASS"
    assert persisted["status"] == "PASS"


@pytest.mark.parametrize(
    "mutated_input",
    ["source", "staged", "staged_writable", "raw_job_out", "launcher_receipt"],
)
def test_final_pass_publication_revalidates_all_bound_inputs(
    tmp_path: Path, monkeypatch, mutated_input: str
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    evidence_paths: dict[str, Path] = {}
    original_writer = cadctl._atomic_write_json_no_overwrite

    def fake_attended(staged_dwg, run_dir, operation, args, **kwargs):
        evidence_paths["staged"] = Path(staged_dwg)
        evidence_paths["raw_job_out"] = Path(run_dir) / "job_out.json"
        evidence_paths["launcher_receipt"] = (
            Path(run_dir) / "attended_job_final_receipt.json"
        )
        return _successful_attended_result(staged_dwg, run_dir, operation)

    def mutate_before_final(path, payload, *, before_publish=None):
        if path.name == "display_membership_receipt.json" and payload.get("status") == "PASS":
            if mutated_input == "staged_writable":
                os.chmod(evidence_paths["staged"], 0o666)
            else:
                target = source if mutated_input == "source" else evidence_paths[mutated_input]
                target.write_bytes(b"changed-after-final-validation")
        return original_writer(path, payload, before_publish=before_publish)

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", fake_attended)
    monkeypatch.setattr(cadctl, "_atomic_write_json_no_overwrite", mutate_before_final)
    out_dir = tmp_path / "out"
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(out_dir)
    )

    assert result["status"] == "BLOCKED"
    assert result["evidence_write_failed"] is True
    assert not (out_dir / "display_membership_receipt.json").exists()
    oracle = json.loads((out_dir / "target_population_oracle.json").read_text(encoding="utf-8"))
    assert oracle["status"] == "OBSERVED"


@pytest.mark.parametrize(
    "mutated_input",
    ["source", "staged", "raw_job_out", "launcher_receipt", "binding", "oracle", "manifest"],
)
def test_final_receipt_holds_evidence_locks_through_the_atomic_commit(
    tmp_path: Path, monkeypatch, mutated_input: str
):
    router = tmp_path / "router"
    native_bin = _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    original_source = source.read_bytes()
    out_dir = tmp_path / "out"
    real_link = cadctl.os.link
    race = {"blocked": False}

    def fake_attended(staged_dwg, run_dir, operation, args, **kwargs):
        return _successful_attended_result(staged_dwg, run_dir, operation)

    def mutate_during_link(temporary, destination):
        destination_path = Path(destination)
        if destination_path.name == "display_membership_receipt.json":
            targets = {
                "source": source,
                "staged": out_dir / "staged" / "input.dwg",
                "raw_job_out": out_dir / "attended" / "job_out.json",
                "launcher_receipt": out_dir
                / "attended"
                / "attended_job_final_receipt.json",
                "binding": out_dir / "display_membership_binding.json",
                "oracle": out_dir / "target_population_oracle.json",
                "manifest": native_bin / "native_build_manifest.json",
            }
            try:
                targets[mutated_input].write_bytes(b"raced-between-guard-and-link")
            except OSError:
                race["blocked"] = True
        return real_link(temporary, destination)

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", fake_attended)
    monkeypatch.setattr(cadctl.os, "link", mutate_during_link)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(out_dir)
    )

    assert race["blocked"] is True
    assert result["status"] == "PASS"
    assert source.read_bytes() == original_source


def test_final_receipt_holds_attended_directory_identity_through_commit(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    _prepare_current_native_checkout(router)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    out_dir = tmp_path / "out"
    moved = out_dir / "attended-raced"
    real_link = cadctl.os.link
    race = {"blocked": False}

    def fake_attended(staged_dwg, run_dir, operation, args, **kwargs):
        return _successful_attended_result(staged_dwg, run_dir, operation)

    def replace_directory_during_link(temporary, destination):
        if Path(destination).name == "display_membership_receipt.json":
            try:
                (out_dir / "attended").rename(moved)
            except OSError:
                race["blocked"] = True
        return real_link(temporary, destination)

    monkeypatch.setattr(cadctl.attended_lane, "run_attended_native_job", fake_attended)
    monkeypatch.setattr(cadctl.os, "link", replace_directory_during_link)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(out_dir)
    )

    if moved.exists() and not (out_dir / "attended").exists():
        moved.rename(out_dir / "attended")
    assert race["blocked"] is True
    assert result["status"] == "PASS"
    assert (out_dir / "attended").is_dir()
