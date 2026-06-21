#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CADOS M05 TEST -- packet CLI contract for patch/diff/validator surfaces."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def _patch_doc(dwg_path, out_dir):
    return {
        "schema": "ariadne.cad_patch.v1",
        "patch_id": "m05-cli-test",
        "target_dwg": {
            "staged_path": os.path.join(out_dir, "staged_input.dwg"),
            "original_path": dwg_path,
        },
        "operations": [
            {
                "step_id": "s1",
                "operation": "create_line",
                "args": {
                    "start": [0, 0, 0],
                    "end": [10, 0, 0],
                    "layer": "0",
                },
            }
        ],
        "postconditions": [
            {"subject": "entity_count", "op": "delta_eq", "value": 1}
        ],
        "policy": {"staged_copy": True, "write_mode": "write_copy"},
    }


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, os.path.join(_REPO, "tools", "cadctl_cli.py"), *args],
        cwd=_REPO,
        text=True,
        capture_output=True,
    )


class TestM05PacketCliContract(unittest.TestCase):
    def test_patch_dry_run_accepts_packet_flags_and_writes_plan(self):
        with tempfile.TemporaryDirectory(prefix="m05_dry_") as tmp:
            dwg = os.path.join(tmp, "source.dwg")
            with open(dwg, "wb") as fh:
                fh.write(b"FAKE-DWG")
            patch_path = os.path.join(tmp, "patch.json")
            _write_json(patch_path, _patch_doc(dwg, tmp))
            out_dir = os.path.join(tmp, "run")

            proc = _run_cli(
                "patch", "dry-run",
                "--dwg", dwg,
                "--patch", patch_path,
                "--out", out_dir,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(out.get("schema"), "ariadne.cad_patch.dry_run.v1")
            self.assertEqual(out.get("status"), "planned")
            self.assertEqual(out.get("execution"), "not_implemented")
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "patch.json")))
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "dry_run_plan.json")))

    def test_patch_apply_staged_accepts_packet_flags_and_blocks_missing_dwg(self):
        with tempfile.TemporaryDirectory(prefix="m05_apply_") as tmp:
            missing_dwg = os.path.join(tmp, "missing.dwg")
            patch_path = os.path.join(tmp, "patch.json")
            out_dir = os.path.join(tmp, "run")
            _write_json(patch_path, _patch_doc(missing_dwg, out_dir))

            proc = _run_cli(
                "patch", "apply-staged",
                "--dwg", missing_dwg,
                "--patch", patch_path,
                "--out", out_dir,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(out.get("schema"), "ariadne.cad_patch.result.v1")
            self.assertEqual(out.get("status"), "blocked")
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "patch.json")))
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "journal.json")))
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "result.json")))

    def test_diff_accepts_packet_flags_and_writes_cad_diff(self):
        import ir_builder

        with tempfile.TemporaryDirectory(prefix="m05_diff_") as tmp:
            pre = ir_builder.make_fixture_ir()
            post = copy.deepcopy(pre)
            post["entities"].append({
                "handle": "3FF",
                "class": "AcDbLine",
                "dxf_name": "LINE",
                "owner_handle": "1F",
                "space": "model",
                "layer": "0",
                "bbox": [0, 0, 0, 1, 0, 0],
                "geometry": {"kind": "line", "start": [0, 0, 0], "end": [1, 0, 0]},
            })
            post["diagnostics"]["entity_count"] = len(post["entities"])
            pre_path = os.path.join(tmp, "pre.json")
            post_path = os.path.join(tmp, "post.json")
            out_dir = os.path.join(tmp, "diff")
            _write_json(pre_path, pre)
            _write_json(post_path, post)

            proc = _run_cli(
                "diff",
                "--before", pre_path,
                "--after", post_path,
                "--out", out_dir,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(out.get("schema"), "ariadne.cad_diff.v1")
            self.assertEqual(out["summary"]["added"], 1)
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "cad_diff.json")))


if __name__ == "__main__":
    unittest.main()
