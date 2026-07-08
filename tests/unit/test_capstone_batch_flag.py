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


def test_build_arg_parser_batch_size_flag_defaults_to_none_and_parses_int():
    args = frc.build_arg_parser().parse_args(["--out-dir", "/tmp/capstone"])
    assert args.batch_size is None

    args = frc.build_arg_parser().parse_args(
        ["--out-dir", "/tmp/capstone", "--batch-size", "4"]
    )
    assert args.batch_size == 4


def test_run_regen_batch_threads_batch_size_to_apply_staged(tmp_path):
    calls = {}

    class _FakeIrToPatch:
        @staticmethod
        def build_patch_from_ir(filtered_ir, target_dwg, patch_id):
            return ({
                "schema": frc.patch_engine_mod.PATCH_SCHEMA_ID if hasattr(frc, "patch_engine_mod") else "ariadne.cad_patch.v1",
                "patch_id": patch_id,
                "target_dwg": target_dwg,
                "operations": [{"operation": "create_line", "args": {}}],
                "postconditions": [{"subject": "entity_count", "op": "delta_ge", "value": 0}],
                "policy": {"staged_copy": True, "write_mode": "write_copy"},
            }, [])

    class _FakePatchEngine:
        @staticmethod
        def apply_staged(patch, dwg_path, out_dir, batch_size=None):
            calls["patch"] = patch
            calls["dwg_path"] = dwg_path
            calls["out_dir"] = out_dir
            calls["batch_size"] = batch_size
            return {"status": "ok", "batch_size": batch_size, "batch_count": 1}

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
    assert calls["batch_size"] == 4
    assert result["apply_result"]["batch_size"] == 4


def test_build_regen_summary_carries_batch_fields_and_null_when_absent():
    gate = {"gate_status": "ok"}
    batch = {
        "op_count": 3,
        "deferred": [],
        "resolvable_ops": {"implemented": 3},
        "elapsed_seconds": 1.5,
        "seconds_per_op": 0.5,
        "apply_result": {"status": "ok", "reason": None, "batch_size": 4, "batch_count": 2},
    }

    summary = frc.build_regen_summary(batch, gate)
    assert summary["batch_size"] == 4
    assert summary["batch_count"] == 2

    summary = frc.build_regen_summary({**batch, "apply_result": None}, gate)
    assert summary["batch_size"] is None
    assert summary["batch_count"] is None
