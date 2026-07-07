"""cadctl.Cad.run_operation staged-copy envelope truthfulness (no AutoCAD).

Monkeypatches run_job.run_router_cad_job to simulate the router's second-level
staging: cadctl's staged_copy stays pristine; only the router-owned copy mutates
on write_copy. Asserts the returned envelope hashes match on-disk bytes at the
right moments for read vs write_copy.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
import cadctl  # noqa: E402

_REG = _ROOT / "config" / "operations.v2.json"


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ops():
    return json.loads(_REG.read_text(encoding="utf-8-sig")).get("operations", [])


def _first_implemented_op(*, require_write_copy: bool = False):
    for o in _ops():
        if o.get("status") != "implemented":
            continue
        if require_write_copy:
            allowed = set((o.get("write_level") or {}).get("allowed_write_modes") or [])
            if "write_copy" not in allowed:
                continue
        return o
    return None


class _FakeRouterRunJob:
    """Mimics autocad-router.ps1 Invoke-CadJobRoute: copies staged_dwg into its
    own path; mutates only that second copy on write modes."""

    def __init__(self, *, mutate_on_write: bool = True, mutate_in_place: bool = False):
        self.mutate_on_write = mutate_on_write
        self.mutate_in_place = mutate_in_place
        self.calls: list[dict] = []

    def run_router_cad_job(self, staged_dwg, run_dir, operation, *,
                           write_mode="read", job_path=None, timeout=600,
                           intent="dwg"):
        self.calls.append({"staged_dwg": staged_dwg, "write_mode": write_mode})
        os.makedirs(run_dir, exist_ok=True)
        stdout = os.path.join(run_dir, "stdout.txt")
        stderr = os.path.join(run_dir, "stderr.txt")
        Path(stdout).write_text("{}", encoding="utf-8")
        Path(stderr).write_text("", encoding="utf-8")

        if self.mutate_in_place and write_mode in ("write_copy", "write_original", "live_edit"):
            with open(staged_dwg, "ab") as fh:
                fh.write(b"IN-PLACE-MUTATION")
            router_copy = staged_dwg
        else:
            router_own_dir = os.path.join(run_dir, "router_own_stage")
            os.makedirs(router_own_dir, exist_ok=True)
            router_copy = os.path.join(router_own_dir, "input.dwg")
            shutil.copy2(staged_dwg, router_copy)
            if self.mutate_on_write and write_mode in ("write_copy", "write_original", "live_edit"):
                with open(router_copy, "ab") as fh:
                    fh.write(b"MUTATED-BY-SIMULATED-QSAVE")

        result_json = os.path.join(run_dir, "result.json")
        Path(result_json).write_text(json.dumps({"status": "ok"}), encoding="utf-8")

        return {
            "command": ["fake"],
            "exit_code": 0,
            "stdout_path": stdout,
            "stderr_path": stderr,
            "envelope": {"status": "ok"},
            "result_json": result_json,
            "result": {"status": "ok"},
            "staged_used": router_copy,
            "timed_out": False,
            "error": None,
        }


@pytest.fixture
def fixture_dwg(tmp_path):
    p = tmp_path / "src.dwg"
    p.write_bytes(b"FAKE DWG BYTES v1 - unchanged original")
    return p


def test_read_op_envelope_is_truthful(monkeypatch, tmp_path, fixture_dwg):
    op = _first_implemented_op()
    assert op, "registry must contain at least one implemented op"
    op_id = op.get("id") or op.get("operation")

    fake = _FakeRouterRunJob(mutate_on_write=True)
    monkeypatch.setattr(cadctl, "run_job", fake)

    env = cadctl.Cad().run_operation(
        op_id, write_mode="read", dwg_path=str(fixture_dwg), out_dir=str(tmp_path / "out"))

    assert env["status"] == "ok"
    assert env["executed"] is True
    assert env["staged_copy_matches_original"] is True
    assert env["staged_copy_unchanged"] is True
    assert env["original_unchanged"] is True
    assert env["original_sha256_before"] == env["original_sha256_after"]
    assert env["staged_copy_sha256"] == _sha256(fixture_dwg)
    assert env["staged_copy_sha256"] == _sha256(env["staged_copy"])
    assert env["staged_result_sha256"] == env["staged_copy_sha256"]
    assert Path(env["staged_result"]).is_file()


def test_write_copy_op_envelope_is_truthful(monkeypatch, tmp_path, fixture_dwg):
    op = _first_implemented_op(require_write_copy=True)
    if not op:
        pytest.skip("no implemented op allows write_copy in this registry snapshot")
    op_id = op.get("id") or op.get("operation")

    fake = _FakeRouterRunJob(mutate_on_write=True)
    monkeypatch.setattr(cadctl, "run_job", fake)

    env = cadctl.Cad().run_operation(
        op_id, write_mode="write_copy", dwg_path=str(fixture_dwg),
        out_dir=str(tmp_path / "out"))

    assert env["status"] == "ok"
    assert env["executed"] is True
    assert env["staged_copy_matches_original"] is True
    assert env["staged_copy_unchanged"] is True
    assert env["original_unchanged"] is True

    staged_copy = Path(env["staged_copy"])
    staged_result = Path(env["staged_result"])
    assert staged_copy.is_file()
    assert staged_result.is_file()
    assert staged_result != staged_copy

    assert env["staged_copy_sha256"] == _sha256(staged_copy)
    assert env["staged_copy_sha256"] == _sha256(fixture_dwg)
    assert env["staged_result_sha256"] == _sha256(staged_result)
    assert env["staged_result_sha256"] != env["staged_copy_sha256"]


def test_in_place_router_mutation_surfaces_as_safety_error(monkeypatch, tmp_path, fixture_dwg):
    op = _first_implemented_op(require_write_copy=True)
    if not op:
        pytest.skip("no implemented op allows write_copy in this registry snapshot")
    op_id = op.get("id") or op.get("operation")

    fake = _FakeRouterRunJob(mutate_in_place=True)
    monkeypatch.setattr(cadctl, "run_job", fake)

    env = cadctl.Cad().run_operation(
        op_id, write_mode="write_copy", dwg_path=str(fixture_dwg),
        out_dir=str(tmp_path / "out"))

    assert env["status"] == "error"
    assert env["staged_copy_unchanged"] is False
    assert env["original_unchanged"] is True
    assert "staged_copy" in env["reason"]
