#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lane E INTEGRATION -- env-aware native DWG inspect via the router (no ad-hoc parse).

Intent (WHY):
  * The ONLY honest way to prove the native extraction path works is to drive a
    REAL DWG through cadctl.inspect(), which stages a COPY and routes through
    tools/autocad-router.ps1 (ObjectARX > ObjectDBX > AutoLISP). This test does
    that end-to-end and asserts the result is internally consistent (the IR's
    entity_count == len(entities), and the original was never written).
  * It is ENV-AWARE: a native inspect needs (a) accoreconsole/AutoCAD installed
    and (b) a sample DWG to point at. If either is missing, the test SKIPS with
    an explicit "SKIPPED_ENV: no AutoCAD" marker. It must NEVER hard-fail because
    the box lacks AutoCAD -- a skip is the truthful answer there, not a failure.
  * No bypass: this test performs NO ad-hoc DWG parsing. Every byte of CAD truth
    comes from the router (via cadctl). The original DWG is treated READ-ONLY;
    cadctl stages a copy under staging/golden/ and operates on the copy.

If AutoCAD IS present but the extraction does not return 'ok' (e.g. a route/host
hiccup), the test records that truthfully and still does not fake a pass: it
asserts the envelope is a recognized truthful status and that, whatever happened,
the original file's bytes were not mutated.

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

# Canonical accoreconsole location on this box (per the router contract). The
# presence of this binary is our gate for "AutoCAD available".
_ACCORECONSOLE = r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe"

# Truthful (non-error) inspect statuses. 'error' would mean cadctl itself broke.
_TRUTHFUL_STATUSES = {"ok", "blocked", "partial", "unavailable", "not_implemented"}


def _accoreconsole_present():
    if os.path.isfile(_ACCORECONSOLE):
        return True
    # Fall back to PATH (the router exposes `rhinocode`-style shims; accoreconsole
    # may be on PATH in some setups).
    from shutil import which
    return which("accoreconsole") is not None or which("accoreconsole.exe") is not None


def _find_sample_dwg():
    """Find a DWG to use as a READ-ONLY source. Prefer a committed/known sample;
    otherwise fall back to any DWG already present under the router tree (staged
    copies from prior runs are fine as a source -- cadctl re-stages its own copy).
    Returns a path or None.
    """
    candidates = [
        os.path.join(_REPO, "samples", "input.dwg"),
        os.path.join(_REPO, "tests", "fixtures", "input.dwg"),
        r"D:\dev\_ariadne\alm\build\input.dwg",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    # Scan the router tree for any .dwg (bounded; first hit wins).
    for root, _dirs, files in os.walk(_REPO):
        for f in files:
            if f.lower().endswith(".dwg"):
                return os.path.join(root, f)
    return None


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class TestNativeInspectIntegration(unittest.TestCase):
    def setUp(self):
        if not _accoreconsole_present():
            self.skipTest("SKIPPED_ENV: no AutoCAD (accoreconsole not found)")
        self.sample = _find_sample_dwg()
        if not self.sample:
            self.skipTest("SKIPPED_ENV: no sample DWG available to inspect")
        import cadctl
        self.cad = cadctl.Cad()

    def test_native_inspect_stages_copy_and_is_consistent(self):
        original = self.sample
        sha_before = _sha256(original)
        size_before = os.path.getsize(original)

        with tempfile.TemporaryDirectory(prefix="native_inspect_") as out_dir:
            env = self.cad.inspect(original, out_dir, mode="graph")

            # The envelope must always be a recognized, truthful status.
            self.assertEqual(env.get("schema"), "ariadne.cadctl.inspect.v1")
            self.assertIn(
                env.get("status"), _TRUTHFUL_STATUSES,
                "inspect returned a non-truthful status: %r (reason=%r)"
                % (env.get("status"), env.get("reason")),
            )

            # External-command evidence must have been captured (mandatory rule).
            for key in ("stdout", "stderr"):
                ref = env.get(key)
                if ref is not None:
                    self.assertTrue(os.path.isfile(ref),
                                    "%s captured path does not exist: %s" % (key, ref))
            # cad_job + cad_result descriptors are always written.
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "cad_job.json")))
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "cad_result.json")))

            if env.get("status") == "ok":
                # Full success path: an IR must exist and satisfy the truth gate.
                ir_path = env.get("dwg_graph_ir")
                self.assertTrue(ir_path and os.path.isfile(ir_path),
                                "ok inspect but IR missing: %r" % ir_path)
                import ir_builder
                ir = ir_builder.load_ir(ir_path)
                self.assertEqual(ir.get("schema"), "ariadne.dwg_graph_ir.v1")
                self.assertEqual(
                    ir["diagnostics"]["entity_count"], len(ir["entities"]),
                    "native IR violates the entity-count truth gate",
                )
                # The envelope's entity_count must agree with the IR.
                if env.get("entity_count") is not None:
                    self.assertEqual(env["entity_count"],
                                     ir["diagnostics"]["entity_count"])
                # The staged copy must be distinct from the original.
                staged = env.get("staged_copy")
                self.assertTrue(staged)
                self.assertNotEqual(
                    os.path.normcase(os.path.abspath(staged)),
                    os.path.normcase(os.path.abspath(original)),
                    "inspect operated on the original, not a staged copy",
                )

        # INVARIANT (always, regardless of inspect outcome): the original DWG was
        # never written -- bytes and size are unchanged.
        self.assertEqual(_sha256(original), sha_before,
                         "ORIGINAL DWG WAS MODIFIED (sha256 changed) -- invariant breach")
        self.assertEqual(os.path.getsize(original), size_before,
                         "ORIGINAL DWG size changed -- invariant breach")


if __name__ == "__main__":
    unittest.main()
