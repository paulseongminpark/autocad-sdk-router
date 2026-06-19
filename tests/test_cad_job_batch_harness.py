import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "run_cad_job_batch.ps1"
BATCH_FIXTURE = ROOT / "test_native" / "p2_stateful_batch.json"


def test_p2_stateful_batch_fixture_uses_ordered_single_dwg_block_sequence():
    batch = json.loads(BATCH_FIXTURE.read_text(encoding="utf-8"))

    assert batch["schema"] == "ariadne.autocad_sdk_job_batch.v1"
    assert batch["execution"]["mode"] == "sequential"
    assert batch["execution"]["parallel"] is False
    assert batch["execution"]["host_bound"] is True
    assert batch["execution"]["write_mode"] == "write_original"

    variables = batch["variables"]
    assert variables["dwg"] == "test_native/native_job_batch2_working.dwg"
    assert variables["block_name"] == "ARIADNE_P2_STATEFUL_BLOCK"

    steps = batch["steps"]
    assert [step["operation"] for step in steps] == [
        "write.block.simple_create",
        "write.block.insert",
        "inspect.block.count",
    ]
    assert {step["input_path"] for step in steps} == {"${dwg}"}

    job_names = [step["job"]["args"]["name"] for step in steps]
    assert job_names == ["${block_name}", "${block_name}", "${block_name}"]
    assert steps[1]["job"]["args"]["position"] == {"x": 25.0, "y": 35.0, "z": 0.0}


def test_batch_harness_declares_cross_process_sequential_execution():
    text = HARNESS.read_text(encoding="utf-8")

    assert "System.Threading.Mutex" in text
    assert "WaitOne" in text
    assert "ReleaseMutex" in text
    assert "Start-Job" not in text
    assert "Start-ThreadJob" not in text
    assert "ForEach-Object -Parallel" not in text
    assert "Start-Process" not in text

    action_index = text.index("-Action 'run'")
    intent_index = text.index("-Intent 'dwg'", action_index)
    input_index = text.index("-InputPath $inputPath", intent_index)
    operation_index = text.index("-Operation $operation", input_index)
    job_index = text.index("-JobPath $jobPath", operation_index)
    assert action_index < intent_index < input_index < operation_index < job_index
    assert "-WriteMode $writeMode" in text


def test_batch_harness_invokes_fake_router_in_fixture_order_without_autocad(tmp_path):
    fake_router = tmp_path / "fake-router.ps1"
    call_log = tmp_path / "router-calls.jsonl"
    fake_router.write_text(
        """
param(
  [string]$Action,
  [string]$Intent,
  [string]$InputPath,
  [string]$Operation,
  [string]$JobPath,
  [string]$WriteMode
)

$job = Get-Content -LiteralPath $JobPath -Raw -Encoding UTF8 | ConvertFrom-Json
$entry = [ordered]@{
  action = $Action
  intent = $Intent
  input_path = $InputPath
  operation = $Operation
  job_operation = "$($job.operation)"
  write_mode = $WriteMode
  block_name = "$($job.args.name)"
  job_path = $JobPath
}
$entry | ConvertTo-Json -Depth 16 -Compress | Add-Content -LiteralPath $env:CAD_BATCH_CALL_LOG -Encoding UTF8
exit 0
""".lstrip(),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["CAD_BATCH_CALL_LOG"] = str(call_log)

    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(HARNESS),
            "-BatchPath",
            str(BATCH_FIXTURE),
            "-RouterPath",
            str(fake_router),
            "-RootPath",
            str(ROOT),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr + result.stdout

    calls = [json.loads(line) for line in call_log.read_text(encoding="utf-8-sig").splitlines()]
    assert [call["operation"] for call in calls] == [
        "write.block.simple_create",
        "write.block.insert",
        "inspect.block.count",
    ]
    assert [call["job_operation"] for call in calls] == [call["operation"] for call in calls]
    assert {call["action"] for call in calls} == {"run"}
    assert {call["intent"] for call in calls} == {"dwg"}
    assert {call["write_mode"] for call in calls} == {"write_original"}
    assert {call["input_path"] for call in calls} == {
        str(ROOT / "test_native" / "native_job_batch2_working.dwg")
    }
    assert {call["block_name"] for call in calls} == {"ARIADNE_P2_STATEFUL_BLOCK"}


def test_batch_harness_fails_when_router_json_reports_route_nonzero(tmp_path):
    fake_router = tmp_path / "fake-router.ps1"
    fake_router.write_text(
        """
param(
  [string]$Action,
  [string]$Intent,
  [string]$InputPath,
  [string]$Operation,
  [string]$JobPath,
  [string]$WriteMode
)

[ordered]@{
  status = "ROUTE_NONZERO"
  execution = [ordered]@{
    engine_exit_code = -3
    engine_output = [ordered]@{ status = "native_cad_job_failed" }
  }
} | ConvertTo-Json -Depth 16
exit 0
""".lstrip(),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(HARNESS),
            "-BatchPath",
            str(BATCH_FIXTURE),
            "-RouterPath",
            str(fake_router),
            "-RootPath",
            str(ROOT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "FAILED"
    assert payload["failed_step"] == 1
    assert payload["results"][0]["router_status"] == "ROUTE_NONZERO"
    assert payload["results"][0]["router_engine_exit_code"] == -3
