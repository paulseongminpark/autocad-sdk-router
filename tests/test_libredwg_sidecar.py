import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def load_tool(name):
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_finds_libredwg_from_env_bin(tmp_path, monkeypatch):
    probe_routes = load_tool("probe_routes")
    bin_dir = tmp_path / "libredwg" / "bin"
    bin_dir.mkdir(parents=True)
    exe = bin_dir / "dwgread.exe"
    exe.write_text("", encoding="utf-8")

    monkeypatch.setenv("ARIADNE_LIBREDWG_BIN_DIR", str(bin_dir))

    assert probe_routes._cli(probe_routes.LIBREDWG_CANDIDATES) == str(exe)


def test_capabilities_keep_legacy_dwg_truth_aliases():
    caps = json.loads((ROOT / "config" / "autocad_router_capabilities.json").read_text(encoding="utf-8"))

    assert caps["intent_aliases"]["batch_extract"] == "dwg_truth_autocad"
    assert caps["intent_aliases"]["db_read"] == "dwg_truth_autocad"
    assert caps["intent_aliases"]["native_sdk_validate"] == "dwg_truth_autocad"


def test_run_route_libredwg_sidecar_writes_json_and_dxf(tmp_path):
    run_route = load_tool("run_route")
    input_path = tmp_path / "input.dwg"
    input_path.write_bytes(b"fake dwg")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    dwgread = bin_dir / "dwgread.exe"
    dwgread.write_text("", encoding="utf-8")

    calls = []

    def fake_runner(cmd, capture_output, text, timeout, check):
        calls.append(cmd)
        output_path = Path(cmd[cmd.index("-o") + 1])
        output_path.write_text('{"ok": true}' if "JSON" in cmd else "0\nEOF\n", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="fake stdout", stderr="")

    result = run_route.run_libredwg_sidecar(
        input_path=str(input_path),
        run_root=str(tmp_path / "runs"),
        libredwg_bin=str(bin_dir),
        runner=fake_runner,
        stamp="20260616_000000",
    )

    assert result["status"] == "ok"
    assert result["sidecar_process"] is True
    assert result["json_output"].endswith("libredwg_extract.json")
    assert result["dxf_output"].endswith("libredwg_export.dxf")
    assert Path(result["json_output"]).exists()
    assert Path(result["dxf_output"]).exists()
    assert [cmd[cmd.index("-O") + 1] for cmd in calls] == ["JSON", "DXF"]
