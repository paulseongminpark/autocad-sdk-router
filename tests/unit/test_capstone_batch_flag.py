# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.join(os.path.dirname(_THIS_DIR), "..", "tools")
_TOOLS_DIR = os.path.normpath(_TOOLS_DIR)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

frc = importlib.import_module("full_roundtrip_capstone")


class _FakeIrToPatch:
    @staticmethod
    def build_patch_from_ir(filtered_ir, target_dwg, patch_id):
        return ({
            "schema": "ariadne.cad_patch.v1",
            "patch_id": patch_id,
            "target_dwg": target_dwg,
            "operations": [{"operation": "create_line", "args": {}}],
            "postconditions": [{"subject": "entity_count", "op": "delta_ge", "value": 0}],
            "policy": {"staged_copy": True, "write_mode": "write_copy"},
        }, [])


def test_build_arg_parser_batch_size_flag_defaults_to_none_and_parses_int():
    args = frc.build_arg_parser().parse_args(["--out-dir", "/tmp/capstone"])
    assert args.batch_size is None

    args = frc.build_arg_parser().parse_args(
        ["--out-dir", "/tmp/capstone", "--batch-size", "4"]
    )
    assert args.batch_size == 4


def test_run_regen_batch_threads_batch_size_as_batch_options(tmp_path):
    calls = {}

    class _FakePatchEngine:
        @staticmethod
        def apply_staged(patch, dwg_path, out_dir, *, batch_options=None):
            calls["dwg_path"] = dwg_path
            calls["out_dir"] = out_dir
            calls["batch_options"] = batch_options
            return {"status": "ok"}

    result = frc.run_regen_batch(
        {"entities": []},
        "seed.dwg",
        str(tmp_path),
        "pid",
        batch_size=4,
        ir_to_patch_mod=_FakeIrToPatch(),
        patch_engine_mod=_FakePatchEngine(),
    )

    assert calls["dwg_path"] == "seed.dwg"
    assert calls["out_dir"] == str(tmp_path)
    # #47: --batch-size rides the canonical batched lane, with the inspects
    # this driver's verdict depends on forced back to full.
    assert calls["batch_options"] == {
        "enabled": True, "max_ops_per_batch": 4,
        "pre_inspect": "full", "post_inspect": "full",
    }
    assert result["apply_result"]["status"] == "ok"


def test_run_regen_batch_without_batch_size_stays_per_op(tmp_path):
    calls = {}

    class _FakePatchEngine:
        @staticmethod
        def apply_staged(patch, dwg_path, out_dir, *, batch_options=None):
            calls["batch_options"] = batch_options
            return {"status": "ok"}

    frc.run_regen_batch(
        {"entities": []},
        "seed.dwg",
        str(tmp_path),
        "pid",
        batch_size=None,
        ir_to_patch_mod=_FakeIrToPatch(),
        patch_engine_mod=_FakePatchEngine(),
    )

    assert calls["batch_options"] is None


def test_build_regen_summary_reads_batch_fields_from_executor_plan():
    gate = {"gate_status": "ok"}
    batch = {
        "op_count": 3,
        "deferred": [],
        "resolvable_ops": {"implemented": 3},
        "elapsed_seconds": 1.5,
        "seconds_per_op": 0.5,
        "apply_result": {
            "status": "ok", "reason": None,
            "batch": {"plan": {"max_ops_per_batch": 4,
                               "totals": {"batch_count": 2, "op_count": 3}}},
        },
    }

    summary = frc.build_regen_summary(batch, gate)
    assert summary["batch_size"] == 4
    assert summary["batch_count"] == 2

    # per-op runs carry no batch block -> both fields stay None
    summary = frc.build_regen_summary(
        {**batch, "apply_result": {"status": "ok", "reason": None}}, gate)
    assert summary["batch_size"] is None
    assert summary["batch_count"] is None

    summary = frc.build_regen_summary({**batch, "apply_result": None}, gate)
    assert summary["batch_size"] is None
    assert summary["batch_count"] is None
