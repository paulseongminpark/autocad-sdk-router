"""cadctl.Cad.run_operation staged-copy pre/post snapshot (p6-hardening item 5b, cd-cadctl fix).

No accoreconsole needed: run_job.run_router_cad_job is monkeypatched with a fake
that mimics the REAL router's behavior precisely (confirmed by reading
tools/autocad-router.ps1 Invoke-CadJobRoute, lines ~1054-1063): it stages its OWN
second-level copy under a path distinct from the one cadctl staged, and for
write-mode ops mutates ONLY that second copy (never the path handed to it). This
is why cadctl's own staged copy is always a valid pre-write snapshot, and why the
real post-write result has to come from run_res["staged_used"], not from
re-reading the staged path cadctl made itself.
"""
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


def _first_implemented_op(require_write_copy: bool = False):
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
    """Mimics autocad-router.ps1's Invoke-CadJobRoute: stages its OWN second
    copy (a DIFFERENT path from the `staged_dwg` arg it is given) and, for
    write-mode ops, mutates only that second copy -- exactly like the real
    router's Copy-Item into staging/dwg_job_<stamp>/input.dwg followed by
    _QSAVE on that file alone."""

    def __init__(self, mutate_on_write: bool = True):
        self.mutate_on_write = mutate_on_write
        self.calls = []

    def run_router_cad_job(self, staged_dwg, run_dir, operation, *,
                           write_mode="read", job_path=None, timeout=600,
                           intent="dwg"):
        self.calls.append({"staged_dwg": staged_dwg, "write_mode": write_mode})
        os.makedirs(run_dir, exist_ok=True)
        stdout = os.path.join(run_dir, "stdout.txt")
        stderr = os.path.join(run_dir, "stderr.txt")
        Path(stdout).write_text("{}", encoding="utf-8")
        Path(stderr).write_text("", encoding="utf-8")

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
            "command": ["fake"], "exit_code": 0,
            "stdout_path": stdout, "stderr_path": stderr,
            "envelope": {"status": "ok"},
            "result_json": result_json,
            "result": {"status": "ok"},
            "staged_used": router_copy,
            "timed_out": False, "error": None,
        }


class _NoStagedUsedRunJob:
    """Simulates the router failing before it could stage/report anything
    (e.g. missing entrypoint) -- staged_used comes back None."""

    def run_router_cad_job(self, staged_dwg, run_dir, operation, *,
                           write_mode="read", job_path=None, timeout=600,
                           intent="dwg"):
        os.makedirs(run_dir, exist_ok=True)
        stdout = os.path.join(run_dir, "stdout.txt")
        stderr = os.path.join(run_dir, "stderr.txt")
        Path(stdout).write_text("", encoding="utf-8")
        Path(stderr).write_text("router entrypoint missing", encoding="utf-8")
        return {"command": None, "exit_code": None,
                "stdout_path": stdout, "stderr_path": stderr,
                "envelope": None, "result_json": None, "result": None,
                "staged_used": None, "timed_out": False,
                "error": "router entrypoint missing"}


@pytest.fixture
def fixture_dwg(tmp_path):
    p = tmp_path / "src.dwg"
    p.write_bytes(b"FAKE DWG BYTES v1 - unchanged original")
    return p


def test_write_mode_pre_sha_reflects_staged_copy_before_mutation(monkeypatch, tmp_path, fixture_dwg):
    op = _first_implemented_op(require_write_copy=True)
    if not op:
        pytest.skip("no implemented op allows write_copy in this registry snapshot")
    op_id = op.get("id") or op.get("operation")

    fake = _FakeRouterRunJob(mutate_on_write=True)
    monkeypatch.setattr(cadctl, "run_job", fake)

    cad = cadctl.Cad()
    env = cad.run_operation(op_id, write_mode="write_copy",
                            dwg_path=str(fixture_dwg), out_dir=str(tmp_path / "out"))

    assert env["executed"] is True
    staged_copy = Path(env["staged_copy"])
    assert staged_copy.is_file()

    # the pre-write hash in the record must equal the staged copy's actual
    # (untouched) bytes -- proving the snapshot really is pre-write, not a
    # post-hoc read of a file the router might have mutated in place.
    assert env["staged_copy_sha256"] == _sha256(staged_copy)
    assert env["staged_copy_sha256"] == _sha256(fixture_dwg)

    # the post-write result must be a DIFFERENT file with a DIFFERENT hash --
    # this is the artifact that was previously discarded entirely.
    assert env["staged_result"] is not None
    staged_result = Path(env["staged_result"])
    assert staged_result.is_file()
    assert staged_result != staged_copy
    assert env["staged_result_sha256"] == _sha256(staged_result)
    assert env["staged_result_sha256"] != env["staged_copy_sha256"]

    # the TRUE original is untouched throughout.
    assert env["original_unchanged"] is True
    assert _sha256(fixture_dwg) == env["staged_copy_sha256"]


def test_read_mode_pre_and_post_sha_are_equal(monkeypatch, tmp_path, fixture_dwg):
    op = _first_implemented_op()
    assert op, "registry must contain at least one implemented op"
    op_id = op.get("id") or op.get("operation")

    # mutate_on_write=True proves read-mode itself suppresses the mutation
    # (the fake would mutate if write_mode were write_copy/live_edit).
    fake = _FakeRouterRunJob(mutate_on_write=True)
    monkeypatch.setattr(cadctl, "run_job", fake)

    cad = cadctl.Cad()
    env = cad.run_operation(op_id, write_mode="read",
                            dwg_path=str(fixture_dwg), out_dir=str(tmp_path / "out"))

    assert env["executed"] is True
    assert fake.calls[0]["write_mode"] == "read"
    assert env["staged_result"] is not None
    assert env["staged_result_sha256"] == env["staged_copy_sha256"]


def test_missing_staged_used_reports_none_not_a_fabricated_hash(monkeypatch, tmp_path, fixture_dwg):
    op = _first_implemented_op()
    assert op
    op_id = op.get("id") or op.get("operation")

    monkeypatch.setattr(cadctl, "run_job", _NoStagedUsedRunJob())

    cad = cadctl.Cad()
    env = cad.run_operation(op_id, write_mode="read",
                            dwg_path=str(fixture_dwg), out_dir=str(tmp_path / "out"))

    # the pre-write snapshot is still captured even though the router call
    # itself failed to report anything usable.
    assert env["staged_copy_sha256"] == _sha256(fixture_dwg)
    # no fake success: absent staged_used must never produce a fabricated hash.
    assert env["staged_result"] is None
    assert env["staged_result_sha256"] is None
