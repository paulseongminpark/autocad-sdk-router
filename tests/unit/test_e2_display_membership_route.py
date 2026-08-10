from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


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
                    "p0_world": [0.0, 0.0],
                    "p1_world": [10.0, 0.0],
                }
            ],
        },
        "status": "ok",
    }


def _final_launcher_envelope(operation: str, job_out: Path) -> dict:
    """Compact post-cleanup receipt required before a display PASS."""
    return {
        "schema": "ariadne.cad_os.attended_job_result.v1",
        "phase": "finalized",
        "status": "ok",
        "run_id": job_out.parent.name,
        "operation": operation,
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


def _source_tree_digest(inputs: list[dict]) -> str:
    """Independent fixture encoding for the documented native source digest."""
    digest = hashlib.sha256()
    for entry in inputs:
        digest.update(
            f"{entry['path']}\0{entry['sha256']}\0{entry['bytes']}\n".encode("utf-8")
        )
    return digest.hexdigest()


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
        "Ariadne.AcadNativeDbx.dbx": b"dbx",
        "Ariadne.AcadNative.crx": b"crx",
        "Ariadne.AcadNative.arx": b"arx",
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
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        job_out = run_path / "job_out.json"
        raw = _raw_native_result()
        job_out.write_text(json.dumps(raw), encoding="utf-8")
        return {
            "command": ["acad.exe"],
            "exit_code": 0,
            "stdout_path": str(run_path / "stdout.txt"),
            "stderr_path": str(run_path / "stderr.txt"),
            "envelope": _final_launcher_envelope(operation, job_out),
            "result_json": str(run_path / "attended_job_final_receipt.json"),
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
    assert oracle["status"] == "PASS"
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
        (run_path / "job_out.json").write_text(json.dumps(raw), encoding="utf-8")
        return {
            "result": raw,
            "error": None,
            "timed_out": False,
            "result_json": str(run_path / "job_out.json"),
            "stdout_path": None,
            "stderr_path": None,
            "envelope": _final_launcher_envelope(operation, run_path / "job_out.json"),
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
        raw = _raw_native_result(geometry_scope="strict_layer_entities_v1")
        (run_path / "job_out.json").write_text(json.dumps(raw), encoding="utf-8")
        return {
            "result": raw,
            "error": None,
            "timed_out": False,
            "result_json": str(run_path / "job_out.json"),
            "stdout_path": None,
            "stderr_path": None,
            "envelope": _final_launcher_envelope(operation, run_path / "job_out.json"),
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
        raw = _raw_native_result()
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
        job_out.write_text(json.dumps(raw), encoding="utf-8")
        return {
            "result": raw,
            "error": None,
            "timed_out": False,
            "envelope": _final_launcher_envelope(operation, job_out),
            "result_json": str(run_path / "attended_job_final_receipt.json"),
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
        raw = _raw_native_result()
        job_out = run_path / "job_out.json"
        job_out.write_text(json.dumps(raw), encoding="utf-8")
        return {
            "command": ["acad.exe"],
            "exit_code": 0,
            "result": raw,
            "error": None,
            "timed_out": False,
            "envelope": _final_launcher_envelope(operation, job_out),
            "result_json": str(run_path / "attended_job_final_receipt.json"),
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
        raw = _raw_native_result()
        job_out.write_text(json.dumps(raw), encoding="utf-8")
        memory_only = _raw_native_result()
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
        raw = _raw_native_result()
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
        raw = _raw_native_result()
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
