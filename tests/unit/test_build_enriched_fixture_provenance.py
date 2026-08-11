from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace


_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import build_enriched_fixture as builder  # noqa: E402
from operation_provenance import build_execution_receipt  # noqa: E402


def _canonical_envelope(operation: str, write_mode: str, baseline: Path,
                        result_path: Path, native_result: dict, sha256: str) -> dict:
    return {
        "schema": "ariadne.cadctl.run_operation.v1",
        "status": "ok",
        "executed": True,
        "result": native_result,
        "execution_receipt": build_execution_receipt(
            authorized_operation=operation,
            authorized_write_mode=write_mode,
            executed=True,
            reported_status="ok",
            executed_operation=operation,
            executed_write_mode=write_mode,
            router_input_path=str(baseline),
            original_path=str(baseline),
            original_sha256_before="a" * 64,
            original_sha256_after="a" * 64,
            baseline_path=str(baseline),
            baseline_sha256="a" * 64,
            baseline_sha256_after="a" * 64,
            result_path=str(result_path),
            result_sha256=sha256,
            result_kind="router_working_copy",
            process_exit_code=0,
            engine_exit_code=0,
            engine_output_exit_code=0,
            native_status="ok",
            native_schema="ariadne.autocad_native_job_result.v1",
            native_engine="native_objectarx",
            native_operation=operation,
            native_result_source="file",
            native_result_is_object=True,
            native_error_code=None,
            native_result_path=str(result_path) + ".native-result.json",
            native_result_sha256="c" * 64,
            router_status="PASS",
            router_schema="ariadne.autocad_router_run.v2",
            executed_route="dwg_truth_autocad",
            timed_out=False,
            input_kind="staged_copy",
            save_command_issued=(write_mode == "write_copy"),
            router_working_sha256_before="a" * 64,
            router_working_sha256_after=sha256,
        ),
    }


def test_run_chain_uses_only_canonical_bound_result_path_and_sha(tmp_path, monkeypatch):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"source")
    run_dir = tmp_path / "run"
    output = tmp_path / "fixtures" / "enriched.dwg"
    manifest_path = tmp_path / "measure" / "manifest.json"
    output.parent.mkdir()
    manifest_path.parent.mkdir()
    chain_result = tmp_path / "canonical-result.dwg"
    chain_result.write_bytes(b"canonical-result")
    commands = []

    monkeypatch.setattr(
        builder,
        "_CHAIN",
        [{"ref": "solid_a", "op": "write.entity.solid3d.primitive", "args": {}}],
    )
    monkeypatch.setattr(builder, "_REPO", str(tmp_path))
    monkeypatch.setattr(builder, "_RUN_DIR", str(run_dir))
    monkeypatch.setattr(builder, "_OUT_DWG", str(output))
    monkeypatch.setattr(builder, "_MANIFEST", str(manifest_path))
    monkeypatch.setattr(builder, "_PROBE", str(tmp_path / "probe_reachability.py"))

    def fake_run(cmd, **kwargs):
        commands.append(list(cmd))
        operation = cmd[cmd.index("--probe-one") + 1]
        baseline = Path(cmd[cmd.index("--dwg") + 1]).resolve()
        out_dir = Path(cmd[cmd.index("--out-dir") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        if operation == "inspect.database.graph":
            read_result = baseline.with_name("router_read_result.dwg")
            read_result.write_bytes(baseline.read_bytes())
            native_result = {
                "entities": [
                    {
                        "handle": "S1",
                        "dxf_name": "AcDb3dSolid",
                        "layer": builder._LAYER,
                        "xdata": [{"app": "ARIADNE_P3B_TAIL"}],
                    },
                    {
                        "handle": "L1",
                        "dxf_name": "AcDbLine",
                        "layer": builder._LAYER,
                        "start": [1.0, 2.0, 0.0],
                    },
                    {
                        "handle": "L2",
                        "dxf_name": "AcDbLine",
                        "layer": builder._LAYER,
                        "start": [0.0, 0.0, 0.0],
                    },
                    {
                        "handle": "C1",
                        "dxf_name": "AcDbCircle",
                        "layer": builder._LAYER,
                    },
                ]
            }
            envelope = _canonical_envelope(
                operation, "read", baseline, read_result, native_result, "e" * 64
            )
        else:
            envelope = _canonical_envelope(
                operation,
                "write_copy",
                baseline,
                chain_result.resolve(),
                {"created": True, "handle": "S1"},
                "d" * 64,
            )
        (out_dir / "probe_result.json").write_text(
            json.dumps(envelope), encoding="utf-8"
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(builder.subprocess, "run", fake_run)

    assert builder.run_chain(str(source)) == 0

    harvest_cmd = commands[1]
    assert harvest_cmd[harvest_cmd.index("--dwg") + 1] == str(chain_result.resolve())
    assert output.read_bytes() == chain_result.read_bytes()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["steps"][0]["staged_result_sha256"] == "d" * 64


def test_run_chain_rejects_executed_success_without_receipt(tmp_path, monkeypatch):
    source = tmp_path / "source.dwg"
    source.write_bytes(b"source")
    run_dir = tmp_path / "run"
    monkeypatch.setattr(
        builder,
        "_CHAIN",
        [{"ref": "solid_a", "op": "write.entity.solid3d.primitive", "args": {}}],
    )
    monkeypatch.setattr(builder, "_REPO", str(tmp_path))
    monkeypatch.setattr(builder, "_RUN_DIR", str(run_dir))
    monkeypatch.setattr(builder, "_PROBE", str(tmp_path / "probe_reachability.py"))

    def fake_run(cmd, **kwargs):
        out_dir = Path(cmd[cmd.index("--out-dir") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "probe_result.json").write_text(
            json.dumps({"status": "ok", "executed": True, "result": {"handle": "S1"}}),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(builder.subprocess, "run", fake_run)

    assert builder.run_chain(str(source)) == 1
