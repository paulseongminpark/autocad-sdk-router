#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lane E SMOKE -- the deterministic CLI walking skeleton (query + validate).

Intent (WHY):
  * This is the end-to-end proof that the CAD OS Layer's *deterministic* spine
    works without AutoCAD: write a fixture IR, then drive cadctl_cli as a real
    subprocess for ``query`` (IR -> SQLite -> SQL round-trip) and ``validate``
    (deterministic gates). Both MUST exit 0. If the skeleton can't walk on a
    canned IR, nothing built on top can be trusted.
  * Subprocess (not in-process) is deliberate: it exercises the actual CLI entry
    point, argument parsing, and exit-code contract a caller/script would hit.
  * Deterministic: uses ir_builder.make_fixture_ir() -- no DWG, no AutoCAD, no
    network. Re-runnable with identical results.

The CLI's exit-code contract: truthful answers (ok / blocked / not_implemented /
unavailable / partial) all exit 0; only a cadctl-side 'error' exits 1. A
fixture-IR query+validate is the 'ok' path, so exit 0 is required here.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

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

_CLI = os.path.join(_REPO, "tools", "cadctl_cli.py")


def _run_cli(args, cwd):
    """Run cadctl_cli.py as a subprocess; return (exit_code, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, _CLI] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestWalkingSkeleton(unittest.TestCase):
    def setUp(self):
        # Build a fixture IR on disk that the CLI subprocess will operate on.
        import ir_builder
        self.tmp = tempfile.mkdtemp(prefix="walking_skeleton_")
        self.ir_path = os.path.join(self.tmp, "dwg_graph_ir.json")
        ir_builder.write_ir(ir_builder.make_fixture_ir(), self.ir_path)
        self.assertTrue(os.path.isfile(self.ir_path))

    def tearDown(self):
        try:
            for root, _dirs, files in os.walk(self.tmp, topdown=False):
                for f in files:
                    os.remove(os.path.join(root, f))
                os.rmdir(root)
        except OSError:
            pass

    def test_cli_query_exits_zero_and_round_trips(self):
        code, out, err = _run_cli(
            ["query", "--ir", self.ir_path, "--sql", "SELECT COUNT(*) FROM entities"],
            cwd=self.tmp,
        )
        self.assertEqual(code, 0, "cadctl query exited %d\nstderr:\n%s" % (code, err))
        payload = json.loads(out)
        self.assertEqual(payload["status"], "ok",
                         "query status not ok: %r" % payload.get("status"))
        # The fixture IR has 3 entities; the round-trip must report 3.
        self.assertEqual(payload["rows"], [[3]])

    def test_cli_validate_exits_zero(self):
        code, out, err = _run_cli(["validate", "--ir", self.ir_path], cwd=self.tmp)
        self.assertEqual(code, 0, "cadctl validate exited %d\nstderr:\n%s" % (code, err))
        payload = json.loads(out)
        self.assertEqual(payload["status"], "ok",
                         "validate envelope status not ok: %r" % payload.get("status"))
        # The deterministic report must be embedded and carry the truth gate.
        report = payload["report"]
        self.assertEqual(report["schema"], "ariadne.validation_report.v1")
        count_gate = next(g for g in report["gates"]
                          if g["id"] == "entity_count_consistency")
        self.assertEqual(count_gate["status"], "pass")

    def test_cli_validate_is_deterministic_across_runs(self):
        # Two subprocess invocations must yield the same gate verdicts.
        def verdicts():
            code, out, _err = _run_cli(["validate", "--ir", self.ir_path], cwd=self.tmp)
            self.assertEqual(code, 0)
            rep = json.loads(out)["report"]
            return [(g["id"], g["status"]) for g in rep["gates"]]
        self.assertEqual(verdicts(), verdicts(),
                         "CLI validate is not deterministic across subprocess runs")

    def test_cli_query_missing_ir_is_blocked_but_exits_zero(self):
        # A missing IR is a TRUTHFUL 'blocked' answer -> still exit 0 (not a
        # cadctl-side failure). This pins the exit-code contract.
        missing = os.path.join(self.tmp, "no_such_ir.json")
        code, out, _err = _run_cli(
            ["query", "--ir", missing, "--sql", "SELECT 1"], cwd=self.tmp,
        )
        self.assertEqual(code, 0, "blocked answer should exit 0, got %d" % code)
        self.assertEqual(json.loads(out)["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
