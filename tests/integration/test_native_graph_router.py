#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M02 INTEGRATION -- live native graph + staged write via the router.

Intent (WHY):
  * The only fully honest proof of the M02 write path is to drive a REAL native
    staged mutation end-to-end: patch_engine.apply_staged copies the golden DWG,
    runs the native inspect.database.graph (pre), applies a native write op
    (write.entity.line, write_copy), inspects again (post), diffs, validates, and
    journals -- all on staged copies. This test does exactly that when a live host
    is available, and asserts the result is truthful AND the original is untouched.
  * It is doubly ENV-GATED: it runs ONLY when CADOS_LIVE=1 (explicit opt-in) AND
    accoreconsole + the golden DWG are present. Otherwise it SKIPS with an explicit
    reason. It must NEVER hard-fail the headless suite because the box lacks
    AutoCAD -- a skip is the truthful answer, never a failure.
  * No-fake-success / no-bypass: every CAD byte comes from the router (via
    patch_engine -> run_job -> autocad-router.ps1). The original DWG's sha256 is
    asserted unchanged regardless of the apply outcome; a proven original change
    is the only thing that fails this test.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_ACCORECONSOLE = r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe"
_GOLDEN_DWG = os.path.join(_REPO, "staging", "dwg_20260617_191504", "input.dwg")

PATCH_SCHEMA_ID = "ariadne.cad_patch.v1"
_TRUTHFUL = {"ok", "blocked", "partial", "unavailable", "not_implemented"}


def _accoreconsole_present():
    if os.path.isfile(_ACCORECONSOLE):
        return True
    from shutil import which
    return which("accoreconsole") is not None or which("accoreconsole.exe") is not None


def _live_enabled():
    return (os.environ.get("CADOS_LIVE") == "1"
            and _accoreconsole_present()
            and os.path.isfile(_GOLDEN_DWG))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class TestNativeGraphStagedWriteLive(unittest.TestCase):
    def setUp(self):
        if not _live_enabled():
            reasons = []
            if os.environ.get("CADOS_LIVE") != "1":
                reasons.append("CADOS_LIVE!=1")
            if not _accoreconsole_present():
                reasons.append("no accoreconsole")
            if not os.path.isfile(_GOLDEN_DWG):
                reasons.append("no golden DWG")
            self.skipTest("SKIPPED_ENV: live native graph/staged-write disabled (%s)"
                          % ", ".join(reasons))
        import patch_engine
        self.pe = patch_engine

    def test_staged_line_write_is_truthful_and_protects_original(self):
        sha_before = _sha256(_GOLDEN_DWG)
        size_before = os.path.getsize(_GOLDEN_DWG)
        out_dir = os.path.join(
            _REPO, "runs", "test_native_graph_router_%s" % os.getpid())
        patch = {
            "schema": PATCH_SCHEMA_ID,
            "patch_id": "itest-line-%s" % os.getpid(),
            "target_dwg": {
                "staged_path": os.path.join(out_dir, "staged_input.dwg"),
                "original_path": _GOLDEN_DWG,
            },
            "operations": [
                {"step_id": "s1", "operation": "create_line",
                 "args": {"start": {"x": 0, "y": 0, "z": 0},
                          "end": {"x": 1000, "y": 0, "z": 0}, "layer": "0"}},
            ],
            "postconditions": [{"subject": "entity_count", "op": "delta_eq",
                                "value": 1}],
            "policy": {"staged_copy": True, "write_mode": "write_copy"},
        }
        try:
            res = self.pe.apply_staged(patch, _GOLDEN_DWG, out_dir)
        finally:
            pass

        # Whatever happened (the host may be busy), the status must be truthful
        # and the ORIGINAL must be byte-identical.
        self.assertIn(res.get("status"), _TRUTHFUL,
                      "apply_staged returned a non-truthful status: %r"
                      % res.get("status"))
        self.assertEqual(_sha256(_GOLDEN_DWG), sha_before,
                         "ORIGINAL golden DWG MODIFIED during staged write")
        self.assertEqual(os.path.getsize(_GOLDEN_DWG), size_before)

        # original_unchanged proof must never assert the original changed.
        proof = res.get("original_unchanged")
        if isinstance(proof, dict):
            self.assertNotEqual(proof.get("unchanged"), False,
                                "original_unchanged proof says the original changed")

        # On a fully successful apply the diff must show the +1 line we added.
        if res.get("status") == "ok":
            summ = res.get("diff_summary") or {}
            added = summ.get("added", summ.get("created_count"))
            self.assertIsNotNone(added, "ok apply but no diff summary added count")
            self.assertGreaterEqual(added, 1,
                                    "ok apply but the diff shows no added entity")
            # a journal must record the run.
            journal = res.get("journal")
            self.assertTrue(journal and os.path.isfile(journal),
                            "ok apply but no journal.json")


if __name__ == "__main__":
    unittest.main()
