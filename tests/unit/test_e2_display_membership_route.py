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
            "envelope": {"status": "ok", "dedicated_instance": True},
            "result_json": str(run_path / "attended_job_result.json"),
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


def test_cadctl_display_membership_uses_exact_job_out_in_degraded_attended_mode(
    tmp_path: Path, monkeypatch
):
    """The attended runner deliberately exposes only the inner payload when
    its PowerShell bookkeeping envelope is late.  The display route must read
    the exact native outer envelope from job_out.json, not invent one or reject
    a completed CAD measurement merely because optional bookkeeping lagged.
    """
    router = tmp_path / "router"
    native_bin = router / "src" / "Ariadne.AcadNative" / "bin" / "x64" / "Release"
    native_bin.mkdir(parents=True)
    (native_bin / "Ariadne.AcadNativeDbx.dbx").write_bytes(b"dbx")
    (native_bin / "Ariadne.AcadNative.arx").write_bytes(b"arx")
    source = tmp_path / "source.dwg"
    source.write_bytes(b"immutable-dwg-payload")

    def fake_degraded_attended(staged_dwg, run_dir, operation, args, **kwargs):
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
            "envelope": {"status": "ok", "degraded": True},
            "result_json": str(run_path / "attended_job_result.json"),
            "result": raw["result"],
            "staged_used": staged_dwg,
            "timed_out": False,
            "error": None,
            "degraded": True,
            "degraded_reason": "optional bookkeeping envelope was late",
        }

    monkeypatch.setattr(
        cadctl.attended_lane, "run_attended_native_job", fake_degraded_attended
    )
    out_dir = tmp_path / "out"
    result = cadctl.Cad(router_home=router).inspect_display_membership(
        str(source), ["W1"], str(out_dir)
    )

    assert result["status"] == "PASS"
    assert result["degraded"] is True
    assert result["attended_result_ref"] == str(out_dir / "attended" / "job_out.json")
    assert Path(result["target_population_oracle"]).is_file()


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
            "envelope": {"status": "ok"},
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
