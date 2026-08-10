from __future__ import annotations

import hashlib
import json
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
        "dedicated_instance": True,
        "timed_out": False,
        "launched_pid_closed": True,
        "user_session_touched": False,
        "job_out": str(job_out),
        "job_out_present": True,
        "degraded": False,
        "security": {"restored": True},
    }


def test_cadctl_display_membership_is_attended_only_hash_bound_and_original_safe(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    native_bin = router / "src" / "Ariadne.AcadNative" / "bin" / "x64" / "Release"
    native_bin.mkdir(parents=True)
    (native_bin / "Ariadne.AcadNativeDbx.dbx").write_bytes(b"dbx")
    (native_bin / "Ariadne.AcadNative.arx").write_bytes(b"arx")
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
    native_bin = router / "src" / "Ariadne.AcadNative" / "bin" / "x64" / "Release"
    native_bin.mkdir(parents=True)
    (native_bin / "Ariadne.AcadNativeDbx.dbx").write_bytes(b"dbx")
    (native_bin / "Ariadne.AcadNative.arx").write_bytes(b"arx")
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
    assert "Ariadne.AcadNative.arx" in result["reason"]


def test_cadctl_display_membership_rejects_precleanup_receipt_without_final_launcher_verification(
    tmp_path: Path, monkeypatch
):
    """Raw job_out cannot certify the launcher's cleanup obligations.

    A pre-cleanup receipt deliberately lacks launched-PID closure, user-session
    safety, and security-restoration proof. Even a valid native measurement
    must remain BLOCKED rather than being promoted to the route's top-level PASS.
    """
    router = tmp_path / "router"
    native_bin = router / "src" / "Ariadne.AcadNative" / "bin" / "x64" / "Release"
    native_bin.mkdir(parents=True)
    (native_bin / "Ariadne.AcadNativeDbx.dbx").write_bytes(b"dbx")
    (native_bin / "Ariadne.AcadNative.arx").write_bytes(b"arx")
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


def test_cadctl_display_membership_blocks_stale_attended_artifacts_before_popen(
    tmp_path: Path, monkeypatch
):
    """The staged copy can be new while ``out/attended`` is old evidence.

    In that case the route must be BLOCKED; it must never reuse a valid-looking
    old final receipt or start PowerShell/AutoCAD against the new staged DWG.
    """
    router = tmp_path / "router"
    native_bin = router / "src" / "Ariadne.AcadNative" / "bin" / "x64" / "Release"
    native_bin.mkdir(parents=True)
    (native_bin / "Ariadne.AcadNativeDbx.dbx").write_bytes(b"dbx")
    (native_bin / "Ariadne.AcadNative.arx").write_bytes(b"arx")
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    out_dir = tmp_path / "out"
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
    popen_calls = []

    def fail_popen(*args, **kwargs):
        popen_calls.append(args)
        raise AssertionError("stale attended artifacts must block before Popen")

    monkeypatch.setattr(cadctl.attended_lane.subprocess, "Popen", fail_popen)
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(out_dir)
    )

    assert result["status"] == "BLOCKED"
    assert result["executed"] is True
    assert "reserved producer artifacts" in result["reason"]
    assert popen_calls == []
    assert stale_job_out.read_bytes() == stale_job_out_before
    assert stale_final.read_bytes() == stale_final_before


def test_cadctl_display_membership_requires_recovery_authority_evidence(
    tmp_path: Path, monkeypatch
):
    """A Python-authored final receipt is acceptable only when it openly
    records the independent validator's process-identity and helper-closure
    evidence.  It must not be a renamed degraded fallback."""
    router = tmp_path / "router"
    native_bin = router / "src" / "Ariadne.AcadNative" / "bin" / "x64" / "Release"
    native_bin.mkdir(parents=True)
    (native_bin / "Ariadne.AcadNativeDbx.dbx").write_bytes(b"dbx")
    (native_bin / "Ariadne.AcadNative.arx").write_bytes(b"arx")
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")
    raw = _raw_native_result()

    def fake_incomplete_recovery(staged_dwg, run_dir, operation, args, **kwargs):
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        receipt = _final_launcher_envelope(operation, run_path / "job_out.json")
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


def test_cadctl_display_membership_rejects_non_native_or_incomplete_result(
    tmp_path: Path, monkeypatch
):
    router = tmp_path / "router"
    native_bin = router / "src" / "Ariadne.AcadNative" / "bin" / "x64" / "Release"
    native_bin.mkdir(parents=True)
    (native_bin / "Ariadne.AcadNativeDbx.dbx").write_bytes(b"dbx")
    (native_bin / "Ariadne.AcadNative.arx").write_bytes(b"arx")
    source = tmp_path / "source.dwg"
    source.write_bytes(b"dwg")
    raw = _raw_native_result()
    raw["result"]["host_mode"] = "coreconsole"

    monkeypatch.setattr(
        cadctl.attended_lane,
        "run_attended_native_job",
        lambda staged_dwg, run_dir, operation, args, **kwargs: {
            "result": raw,
            "error": None,
            "timed_out": False,
            "envelope": _final_launcher_envelope(operation, Path(run_dir) / "job_out.json"),
            "result_json": None,
            "staged_used": staged_dwg,
            "exit_code": 0,
            "stdout_path": None,
            "stderr_path": None,
            "degraded": False,
            "degraded_reason": None,
        },
    )

    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(tmp_path / "out")
    )
    assert result["status"] == "BLOCKED"
    assert result["executed"] is True
    assert "full_autocad" in result["reason"]
    assert "target_population_oracle" not in result
