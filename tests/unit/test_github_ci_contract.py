from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
REQUIRED_JOBS = {
    "python-tests",
    "mcp-sdk-matrix",
    "powershell-syntax",
    "native-integrity",
}


def _workflow() -> dict:
    assert WORKFLOW.is_file(), "GitHub CI workflow is missing"
    parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _triggers(workflow: dict) -> dict:
    # PyYAML implements YAML 1.1 and therefore parses the YAML 1.2 key `on`
    # as True. GitHub Actions correctly treats the source key as `on`.
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict)
    return triggers


def _run_text(job: dict) -> str:
    steps = job.get("steps")
    assert isinstance(steps, list)
    return "\n".join(
        str(step.get("run", "")) for step in steps if isinstance(step, dict)
    )


def test_ci_runs_on_pull_requests_and_main_pushes() -> None:
    workflow = _workflow()
    triggers = _triggers(workflow)
    assert {"pull_request", "push", "workflow_dispatch"} <= set(triggers)
    assert triggers["push"]["branches"] == ["main"]
    assert workflow["permissions"] == {"contents": "read"}


def test_ci_has_all_four_release_contract_jobs() -> None:
    workflow = _workflow()
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict)
    assert REQUIRED_JOBS <= set(jobs)
    assert "python -m pytest tests -q" in _run_text(jobs["python-tests"])
    assert "test_cadagent_mcp_sdk_matrix.ps1" in _run_text(jobs["mcp-sdk-matrix"])
    assert "System.Management.Automation.Language.Parser" in _run_text(
        jobs["powershell-syntax"]
    )
    assert "test_native_deployment_consumers.py" in _run_text(
        jobs["native-integrity"]
    )


def test_ci_jobs_are_bounded_and_cancel_superseded_runs() -> None:
    workflow = _workflow()
    jobs = workflow["jobs"]
    for name in REQUIRED_JOBS:
        assert jobs[name]["runs-on"] == "windows-latest"
        assert isinstance(jobs[name]["timeout-minutes"], int)
        assert jobs[name]["timeout-minutes"] > 0
    assert workflow["concurrency"]["cancel-in-progress"] is True


def test_ci_uses_minimal_test_dependencies() -> None:
    workflow = _workflow()
    job = workflow["jobs"]["python-tests"]
    run_text = _run_text(job)
    assert "requirements-ci.txt" in run_text
    assert "requirements-full.txt" not in run_text


def test_ci_parses_every_tracked_powershell_file() -> None:
    workflow = _workflow()
    run_text = _run_text(workflow["jobs"]["powershell-syntax"])
    assert "git ls-files -- '*.ps1'" in run_text
    assert "Get-ChildItem tools" not in run_text


def test_ci_verifies_the_committed_native_bundle() -> None:
    workflow = _workflow()
    run_text = _run_text(workflow["jobs"]["native-integrity"])
    assert "test_committed_native_deployment.py" in run_text
