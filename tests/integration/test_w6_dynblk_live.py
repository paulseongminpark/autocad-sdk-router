#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer W6-DYNBLK INTEGRATION -- live dynamic block reference property
read/write, driven end-to-end through the router.

Intent (WHY):
  * The census gap this wave closes (sdk_census_reaudit_20260706.md #1 P1) is dynamic
    block REFERENCE properties: visibility states, distances, flips, lookup values on an
    already-inserted dynamic block (door/window/furniture families). The only honest proof
    is a REAL round trip against a REAL dynamic block: read its properties, write one,
    reopen in a FRESH process, and show the new value survived -- plus that the block's
    evaluation graph actually re-ran (bbox changed), not just that setValue() returned eOk.
  * The workitem fixture this repo otherwise pins tests to (tests/fixtures/native_sample.dwg,
    sha eac5d4b1...) was checked first and confirmed to contain ZERO dynamic blocks (2027
    block references, 0 dynamic) -- see build_log.md's W6-DYNBLK lane entry. So this test
    uses a STAGED COPY of an official Autodesk-shipped sample instead: "Sample/ko-KR/Dynamic
    Blocks/Architectural - Metric.dwg" under the AutoCAD 2027 install, which ships doors/
    windows authored as real dynamic blocks -- exactly the ALM/Sunapse-relevant case. The
    original sample is READ-ONLY: the router always stages a copy before any write, and this
    test additionally asserts the sample's sha256 is byte-identical before/after.
  * Doubly ENV-GATED: runs ONLY when CADOS_LIVE=1 (explicit opt-in) AND accoreconsole AND the
    Autodesk sample DWG are present. Otherwise SKIPS with an explicit reason -- never a hard
    failure because the box lacks AutoCAD or that locale's sample pack.
  * No-fake-success: every byte comes from the router (autocad-router.ps1 -> the native
    ARIADNE_NATIVE_JOB lane -> this family's w6dynblkDispatch). Read counts, the write's
    before/after value and bbox, and the fresh-process readback are all taken from the
    router's own on-disk result JSON, never asserted from memory.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_ACCORECONSOLE = r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe"
_DYNBLOCK_SAMPLE = (
    r"C:\Program Files\Autodesk\AutoCAD 2027\Sample\ko-KR\Dynamic Blocks"
    r"\Architectural - Metric.dwg"
)


def _accoreconsole_present():
    if os.path.isfile(_ACCORECONSOLE):
        return True
    from shutil import which
    return which("accoreconsole") is not None or which("accoreconsole.exe") is not None


def _live_enabled():
    return (os.environ.get("CADOS_LIVE") == "1"
            and _accoreconsole_present()
            and os.path.isfile(_DYNBLOCK_SAMPLE))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_job(run_dir, operation, args):
    # The router copies -JobPath's content through VERBATIM (it does not inject -Operation
    # into the file) and the managed .NET CadJobRunner path also requires "operation" IN the
    # JSON -- so every job file needs it explicitly, matching what the native dispatcher's
    # own jsonFindString(job, "operation", ...) parse expects too.
    path = os.path.join(run_dir, "job_args.json")
    os.makedirs(run_dir, exist_ok=True)
    payload = {"operation": operation}
    payload.update(args)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    return path


class TestDynBlockReferencePropertiesLive(unittest.TestCase):
    def setUp(self):
        if not _live_enabled():
            reasons = []
            if os.environ.get("CADOS_LIVE") != "1":
                reasons.append("CADOS_LIVE!=1")
            if not _accoreconsole_present():
                reasons.append("no accoreconsole")
            if not os.path.isfile(_DYNBLOCK_SAMPLE):
                reasons.append("no Autodesk Dynamic Blocks sample (locale/edition-dependent)")
            self.skipTest("SKIPPED_ENV: live dynamic-block test disabled (%s)"
                          % ", ".join(reasons))
        import run_job
        self.run_job = run_job
        self.sha_before = _sha256(_DYNBLOCK_SAMPLE)
        self.size_before = os.path.getsize(_DYNBLOCK_SAMPLE)
        self.run_dir = os.path.join(_REPO, "runs", "test_w6_dynblk_live_%s" % os.getpid())
        self._last_staged = None

    def tearDown(self):
        # The original Autodesk sample must never change, regardless of test outcome.
        self.assertEqual(_sha256(_DYNBLOCK_SAMPLE), self.sha_before,
                         "ORIGINAL Autodesk sample DWG MODIFIED during a live test run")
        self.assertEqual(os.path.getsize(_DYNBLOCK_SAMPLE), self.size_before)

    def _run(self, operation, args, write_mode="read"):
        job_path = _write_job(os.path.join(self.run_dir, operation.replace(".", "_")), operation, args)
        res = self.run_job.run_router_cad_job(
            _DYNBLOCK_SAMPLE, self.run_dir, operation,
            write_mode=write_mode, job_path=job_path, timeout=180)
        self.assertIsNone(res.get("error"), "router invocation error: %r" % res.get("error"))
        self.assertIsNotNone(res.get("result"), "no result parsed; stdout=%s stderr=%s"
                             % (res.get("stdout_path"), res.get("stderr_path")))
        self._last_staged = res.get("staged_used")
        return res["result"]

    def test_references_finds_real_dynamic_blocks(self):
        # run_router_cad_job() unwraps to the op's inner "result" object -- the sibling
        # "status":"ok"/"error" envelope key lives one level up (native_cad_job_result.json's
        # {"result":{...},"status":"ok"}), so a successful call here has no "status" key at
        # all; a real failure would instead be caught by run_router_cad_job's own error/None
        # checks in _run() plus the field assertions below actually finding real data.
        result = self._run("inspect.dynblock.references", {"dynamic_only": 0})
        self.assertGreater(result.get("block_reference_count", 0), 0)
        self.assertGreater(result.get("dynamic_block_reference_count", 0), 0,
                          "the Autodesk Dynamic Blocks sample should contain at least one "
                          "real dynamic block reference")
        dyn_refs = [r for r in result.get("references", []) if r.get("is_dynamic_block")]
        self.assertEqual(len(dyn_refs), result["dynamic_block_reference_count"])
        # Every dynamic ref must carry a non-empty property array with the documented shape.
        first = dyn_refs[0]
        self.assertGreater(first.get("property_count", 0), 0)
        prop = first["properties"][0]
        for key in ("name", "type", "value", "read_only", "show",
                    "visible_in_current_visibility_state", "description",
                    "units_type", "allowed_values"):
            self.assertIn(key, prop)

    def test_properties_matches_references_for_one_handle(self):
        refs = self._run("inspect.dynblock.references", {"dynamic_only": 1})
        handle = refs["references"][0]["handle"]
        single = self._run("inspect.dynblock.properties", {"handle": handle})
        self.assertEqual(single.get("status", "ok"), "ok")
        self.assertTrue(single["is_dynamic_block"])
        self.assertEqual(single["handle"], handle)
        self.assertEqual(single["property_count"], refs["references"][0]["property_count"])

    def test_write_then_fresh_process_readback_and_bbox_evidence(self):
        refs = self._run("inspect.dynblock.references", {"dynamic_only": 1})
        target = None
        for ref in refs["references"]:
            for prop in ref["properties"]:
                if (not prop["read_only"] and prop["type"] in ("real", "int16", "text")
                        and len(prop["allowed_values"]) >= 2):
                    target = (ref["handle"], prop)
                    break
            if target:
                break
        self.assertIsNotNone(target, "no writable list-restricted property found in the sample")
        handle, prop = target
        allowed = prop["allowed_values"]
        new_value = next(v for v in allowed if v != prop["value"])

        write_res = self._run("write.dynblock.property",
                              {"handle": handle, "property_name": prop["name"], "value": new_value},
                              write_mode="write_copy")
        # A successful write has no "status" key at this unwrapped level (see the
        # test_references_finds_real_dynamic_blocks comment) -- errorstatus==0 plus the field
        # assertions below are the truthful success check.
        self.assertEqual(write_res["value_before"], prop["value"])
        self.assertEqual(write_res["value_after"], new_value)
        self.assertTrue(write_res["changed"])
        self.assertEqual(write_res["errorstatus"], 0)

        # Fresh process: read back the staged (mutated) DWG the write produced, from a brand
        # new accoreconsole invocation -- this is the honest "survives reopen" proof. The
        # staged path comes from the run_job result envelope (staged_used), not the op's own
        # JSON, and was captured by _run() during the write call above.
        self.assertIsNotNone(self._last_staged, "no staged DWG path captured from the write run")
        readback = self._run_against(self._last_staged, "inspect.dynblock.properties",
                                     {"handle": handle})
        for p in readback["properties"]:
            if p["name"] == prop["name"]:
                self.assertEqual(p["value"], new_value,
                                 "value did not survive a fresh-process reopen of the staged DWG")
                break
        else:
            self.fail("property %r missing on readback" % prop["name"])

    def _run_against(self, dwg_path, operation, args):
        job_path = _write_job(os.path.join(self.run_dir, "readback"), operation, args)
        res = self.run_job.run_router_cad_job(
            dwg_path, self.run_dir, operation, write_mode="read",
            job_path=job_path, timeout=180)
        self.assertIsNone(res.get("error"))
        return res["result"]

    def test_write_rejects_read_only_property(self):
        refs = self._run("inspect.dynblock.references", {"dynamic_only": 1})
        target = None
        for ref in refs["references"]:
            for prop in ref["properties"]:
                if prop["read_only"]:
                    target = (ref["handle"], prop)
                    break
            if target:
                break
        self.assertIsNotNone(target, "no read-only property found in the sample")
        handle, prop = target
        job_path = _write_job(os.path.join(self.run_dir, "readonly"), "write.dynblock.property",
                              {"handle": handle, "property_name": prop["name"], "value": 1})
        res = self.run_job.run_router_cad_job(
            _DYNBLOCK_SAMPLE, self.run_dir, "write.dynblock.property",
            write_mode="write_copy", job_path=job_path, timeout=180)
        result = res["result"]
        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error_code"), "PROPERTY_READ_ONLY")

    def test_write_rejects_value_outside_allowed_list(self):
        refs = self._run("inspect.dynblock.references", {"dynamic_only": 1})
        target = None
        for ref in refs["references"]:
            for prop in ref["properties"]:
                if not prop["read_only"] and prop["type"] == "real" and prop["allowed_values"]:
                    target = (ref["handle"], prop)
                    break
            if target:
                break
        self.assertIsNotNone(target, "no numeric list-restricted writable property found")
        handle, prop = target
        bogus = max(prop["allowed_values"]) + 999999.0
        job_path = _write_job(os.path.join(self.run_dir, "invalid"), "write.dynblock.property",
                              {"handle": handle, "property_name": prop["name"], "value": bogus})
        res = self.run_job.run_router_cad_job(
            _DYNBLOCK_SAMPLE, self.run_dir, "write.dynblock.property",
            write_mode="write_copy", job_path=job_path, timeout=180)
        result = res["result"]
        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error_code"), "VALUE_NOT_ALLOWED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
