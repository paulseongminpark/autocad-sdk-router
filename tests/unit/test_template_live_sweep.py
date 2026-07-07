#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for tools/template_live_sweep.py (governed-template live-proof driver).

WHY:
  The orchestrator runs accoreconsole live sweeps on a machine with AutoCAD;
  CI and local dev must prove the driver plan/resume/refusal contracts without
  touching CAD. These tests use synthetic fragment dirs under tmp_path and
  monkeypatch cadctl for the --live code path.

Stdlib + pytest only. No accoreconsole, no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import template_live_sweep as tls  # noqa: E402
import command_template_engine as cte  # noqa: E402


def _minimal_template(tid: str, *, headless_safe: bool = True, allowed=("read", "write_copy")):
  """Minimal governed template record accepted by load_templates."""
  return {
      "template_id": tid,
      "summary": f"Test template {tid}",
      "headless_safe": headless_safe,
      "write_mode": {"default": "read", "allowed": list(allowed)},
      "command_sequence": [
          {"literal": "AUDIT"},
          {"slot": "fix_answer"},
      ],
      "slots": {
          "fix_answer": {
              "type": "enum",
              "values": ["Y", "N"],
              "default": "Y",
          },
      },
      "postconditions": [
          {
              "kind": "entity_count_probe",
              "expect_unchanged": True,
              "required": False,
          },
      ],
  }


def _write_json(path: Path, doc) -> None:
    path.write_text(json.dumps(doc), encoding="utf-8")


def _synthetic_registry(tmp_path: Path, fragments: dict[str, list]) -> Path:
    """Build config/command_templates.json + command_templates.d/*.json."""
    config = tmp_path / "config"
    config.mkdir(parents=True)
    base = config / "command_templates.json"
    _write_json(base, {"templates": [_minimal_template("base.audit")]})
    frag_dir = config / "command_templates.d"
    frag_dir.mkdir()
    for name, templates in fragments.items():
        _write_json(frag_dir / name, {"templates": templates})
    return tmp_path


def test_plan_generation_emits_one_row_per_fragment_template(tmp_path):
    """Plan mode enumerates .d fragments and validates against merged registry."""
    router = _synthetic_registry(tmp_path, {
        "alpha.json": [_minimal_template("define.alpha")],
        "beta.json": [_minimal_template("define.beta")],
    })
    rows = tls.run_plan(router_home=router)

    assert len(rows) == 2
    tids = {r["template_id"] for r in rows}
    assert tids == {"define.alpha", "define.beta"}
    for row in rows:
        assert row["schema"] == tls.PLAN_SCHEMA
        assert row["validation_status"] == "ok"
        assert row["validation_reason"] is None
        assert row["sample_args"] == {"fix_answer": "Y"}
        assert row["required_args"] == []
        assert row["expected_assertions"]
        assert row["file"].startswith("command_templates.d/")


def test_malformed_template_refused_in_plan(tmp_path):
    """write_original in a fragment must refuse validation (cadctl contract)."""
    evil = _minimal_template("evil.write_original", allowed=("read", "write_original"))
    router = _synthetic_registry(tmp_path, {"evil.json": [evil]})
    rows = tls.run_plan(router_home=router)

    assert len(rows) == 1
    row = rows[0]
    assert row["template_id"] == "evil.write_original"
    assert row["validation_status"] == "refused"
    assert "write_original" in (row["validation_reason"] or "")
    assert row["sample_args"] is None or row["validation_status"] == "refused"


def test_resume_skip_does_not_reinvoke_cadctl(monkeypatch, tmp_path):
    """--live is resumable: an existing envelope file skips cadctl execution."""
    router = _synthetic_registry(tmp_path, {
        "one.json": [_minimal_template("sweep.one")],
    })
    dwg = tmp_path / "fixture.dwg"
    dwg.write_bytes(b"FAKE_DWG_FOR_RESUME_TEST")
    out_dir = tmp_path / "envelopes"
    out_dir.mkdir()

    prebuilt = {
        "schema": tls.ENVELOPE_SCHEMA,
        "template_id": "sweep.one",
        "status": "ok",
        "exit_code": 0,
        "original_unchanged": True,
        "original_sha256": tls.sha256_file(dwg),
        "evidence_paths": {"envelope": "preexisting"},
        "resumed": False,
    }
    env_path = tls.envelope_path(out_dir, "sweep.one")
    env_path.write_text(json.dumps(prebuilt), encoding="utf-8")

    calls: list[str] = []

    class _FakeCad:
        def __init__(self, _router_home):
            pass

        def run_command_template(self, template_id, slots, dwg=None):
            calls.append(template_id)
            raise AssertionError("must not execute when envelope already exists")

    envelopes, exit_code = tls.run_live(
        dwg, out_dir,
        router_home=router,
        cad_factory=lambda rh: _FakeCad(rh),
    )

    assert calls == []
    assert len(envelopes) == 1
    assert envelopes[0]["resumed"] is True
    assert exit_code == 0


def test_live_path_monkeypatch_cadctl(monkeypatch, tmp_path):
    """--live delegates to cadctl.Cad.run_command_template (same code path)."""
    router = _synthetic_registry(tmp_path, {
        "live.json": [_minimal_template("sweep.live", headless_safe=True)],
    })
    dwg = tmp_path / "fixture.dwg"
    dwg.write_bytes(b"FAKE_DWG_FOR_LIVE_MONKEYPATCH")
    out_dir = tmp_path / "live_out"

    calls: list[dict] = []

    class _FakeCad:
        def __init__(self, router_home):
            self.router_home = router_home

        def run_command_template(self, template_id, slots, dwg=None):
            calls.append({
                "template_id": template_id,
                "slots": slots,
                "dwg": dwg,
            })
            return {
                "schema": "ariadne.cadctl.run_command_template.v1",
                "template_id": template_id,
                "status": "ok",
                "executed": True,
                "staged_copy": str(tmp_path / "staged" / "input.dwg"),
                "original_unchanged": True,
                "stdout": str(tmp_path / "stdout.txt"),
            }

    envelopes, exit_code = tls.run_live(
        dwg, out_dir,
        router_home=router,
        cad_factory=lambda rh: _FakeCad(rh),
    )

    assert len(calls) == 1
    assert calls[0]["template_id"] == "sweep.live"
    assert calls[0]["slots"] == {"fix_answer": "Y"}
    assert calls[0]["dwg"] == str(dwg)

    assert len(envelopes) == 1
    env = envelopes[0]
    assert env["status"] == "ok"
    assert env["exit_code"] == 0
    assert env["original_unchanged"] is True
    assert env["evidence_paths"]["stdout"]
    assert tls.envelope_path(out_dir, "sweep.live").is_file()
    assert exit_code == 0


def test_live_refusal_maps_to_exit_code_2(monkeypatch, tmp_path):
    """cadctl blocked/not_found statuses are refusals (sweep exit 2)."""
    router = _synthetic_registry(tmp_path, {
        "blocked.json": [_minimal_template("sweep.blocked")],
    })
    dwg = tmp_path / "fixture.dwg"
    dwg.write_bytes(b"FAKE_DWG")
    out_dir = tmp_path / "refusal_out"

    class _FakeCad:
        def __init__(self, _router_home):
            pass

        def run_command_template(self, template_id, slots, dwg=None):
            return {
                "status": "blocked",
                "reason": "ATTENDED_ONLY_TEMPLATE",
                "executed": False,
            }

    envelopes, exit_code = tls.run_live(
        dwg, out_dir,
        router_home=router,
        cad_factory=lambda rh: _FakeCad(rh),
    )

    assert envelopes[0]["exit_code"] == 2
    assert exit_code == 2


def test_derive_sample_args_staged_path_honest_note():
    """staged_path slots cannot be derived offline -- null + honest note."""
    template = {
        "command_sequence": [{"literal": "RECOVER"}, {"slot": "recover_target_path"}],
        "slots": {
            "recover_target_path": {"type": "staged_path"},
        },
    }
    sample, note = tls.derive_sample_args(template)
    assert sample is None
    assert note is not None
    assert "staged_path" in note


def test_status_to_exit_code_matrix():
    assert tls.status_to_exit_code("ok") == 0
    assert tls.status_to_exit_code("blocked") == 2
    assert tls.status_to_exit_code("not_found") == 2
    assert tls.status_to_exit_code("error") == 1
    assert tls.status_to_exit_code("ok", original_unchanged=False) == 1
