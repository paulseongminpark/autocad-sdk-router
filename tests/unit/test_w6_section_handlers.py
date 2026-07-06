#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer W6-SECTION TEST -- native AcDbSection read + create family.

Intent (WHY):
  CADOS wave 6 census P2 found AcDbSection/AcDbSectionSettings at ZERO catalog/
  registry coverage despite brep_solids being the strongest catalogued family
  (R3_coverage.md finding G0 / tools/catalog_completeness.py's
  KNOWN_UNCATALOGUED_DISPOSITIONS seeding "section" -> author). W6-SECTION closes
  that gap with families/w6_section_handlers.inc. The invariants that carry
  business meaning and must fail CI if violated:

  1. HASOP <-> DISPATCH PARITY -- every op id w6sectionHasOp admits must have an
     `op == "<id>"` branch in w6sectionDispatch (mirrors test_m08h_handlers.py's
     own parity test, same drift risk: a catalogued op reading as "implemented"
     with no handler, or a live handler dead because the gate rejects it).
  2. HASOP LISTS EXACTLY THE IMPLEMENTED SET -- guards a silent shrink/grow.
  3. NO SILENT DISPATCH FALL-THROUGH -- an op HasOp admits but no if-branch
     matches must surface OPERATION_DISPATCH_MISMATCH (the same coherent-seam
     guard every other M08x family carries), never a bare `return false` that
     would look like "not my op" to the caller.
  4. STAGED-WRITE SAFETY (source-level) -- write.entity.section appends into the
     staged in-memory model space ONLY; it must never persist the original DWG
     nor drive the command stack (no save/saveAs/_QSAVE/writeDwgFile/acedCommand/
     acedCmd/acedInvoke in executable code -- comments are allowed to mention them
     to explain the ban). write.section.generate2d never appends anything to
     ctx.pDb at all (its probe AcDb3dSolid/AcDbSection are transient, deleted
     before return) -- a stronger invariant than "staged only".
  5. ARG VALIDATION -- write.entity.section must surface MISSING_ARG when fewer
     than 2 points are given, not construct a degenerate AcDbSection.
  6. STRINGS -- UTF-8 fidelity via njsonStr/utf8ToWide; no lossy wideToAscii.

  Source-level only (no AutoCAD/build needed) for the parity/safety/string
  invariants above -- matches every sibling M08x family test's own convention
  (the native build is the separate, authoritative link gate,
  tools/build_native_acad.ps1). A SEPARATE fixture/env-gated live class at the
  bottom of this file re-derives the create->reopen->inspect round trip this
  wave's own live smoke already proved by hand
  (runs/w6_section_live_smoke/), so a future regression is caught by pytest
  too, not just a one-off manual run.

Stdlib only. Discoverable by pytest and ``python -m unittest discover -s tests``.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "w6_section_handlers.inc")

_IMPLEMENTED = [
    "inspect.section.objects",
    "write.entity.section",
    "write.section.generate2d",
]


def _read():
    with open(_INC, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _strip_comments(src):
    """Remove C++ // line and /* */ block comments so banned-CODE-token scans do
    not trip on prose. The safety/contract comments legitimately MENTION
    save()/saveAs()/acedCommand to explain why they are forbidden; the ban is on
    executable code."""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"//[^\n]*", " ", src)
    return src


def _hasop_region(src):
    m = re.search(r"static bool w6sectionHasOp\(const std::string& op\)\s*\{(.*?)\n\}", src, re.S)
    assert m, "w6sectionHasOp not found"
    return m.group(1)


def _dispatch_region(src):
    m = re.search(r"static bool w6sectionDispatch\(.*?\)\s*\{(.*)\n\}\s*$", src, re.S)
    assert m, "w6sectionDispatch not found"
    return m.group(1)


def _hasop_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _hasop_region(src)))


def _dispatch_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _dispatch_region(src)))


class TestW6SectionHandlers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read()
        cls.hasop = _hasop_ops(cls.src)
        cls.dispatch = _dispatch_ops(cls.src)

    def test_inc_file_exists(self):
        self.assertTrue(os.path.exists(_INC), f"missing {_INC}")

    def test_signatures_present(self):
        self.assertRegex(self.src, r"bool\s+w6sectionHasOp\(const std::string& op\)")
        self.assertRegex(
            self.src,
            r"bool\s+w6sectionDispatch\(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r\)",
        )

    def test_hasop_lists_exactly_implemented(self):
        self.assertEqual(
            self.hasop, set(_IMPLEMENTED),
            "w6sectionHasOp op set drifted; only_in_src=%s missing_from_src=%s"
            % (sorted(self.hasop - set(_IMPLEMENTED)), sorted(set(_IMPLEMENTED) - self.hasop)),
        )

    def test_implemented_count(self):
        self.assertEqual(len(_IMPLEMENTED), 3)
        self.assertEqual(len(set(_IMPLEMENTED)), 3, "duplicate op id in the implemented list")
        self.assertEqual(len(self.hasop), 3)

    def test_hasop_dispatch_parity(self):
        missing = sorted(set(_IMPLEMENTED) - self.dispatch)
        self.assertEqual(missing, [], "implemented ops with no dispatch branch: %s" % missing)
        extra = sorted(self.dispatch - self.hasop)
        self.assertEqual(extra, [], "dispatch branches not admitted by HasOp: %s" % extra)

    def test_no_silent_dispatch_fallthrough(self):
        # Every sibling M08x family ends its Dispatch with an
        # OPERATION_DISPATCH_MISMATCH guard instead of a bare `return false`
        # once HasOp has already admitted the op -- a HasOp/Dispatch drift must
        # surface as a diagnostic error, not look like "not my op" to the caller.
        self.assertIn("OPERATION_DISPATCH_MISMATCH", self.src,
                      "must guard against a HasOp/Dispatch drift with a diagnostic error")

    def test_staged_write_no_original_persist_tokens(self):
        code = _strip_comments(self.src)
        banned = [
            r"\bsaveAs\b",
            r"\bsave\s*\(",
            r"_QSAVE",
            r"\bwriteDwgFile\b",
            r"\bacedCommand\b",
            r"\bacedCmd\b",
            r"\bacedInvoke\b",
        ]
        for pat in banned:
            self.assertIsNone(
                re.search(pat, code),
                "W6-SECTION must not contain original-persist/command-stack token: %s" % pat,
            )

    def test_write_entity_section_appends_to_staged_model_space(self):
        self.assertIn("appendAcDbEntity", self.src, "write.entity.section must append entities")
        self.assertIn("AcDb::kForWrite", self.src, "must open model space kForWrite")

    def test_generate2d_never_appends_its_probe_entities(self):
        # The measurement op's transient AcDb3dSolid/AcDbSection probe pair must
        # be delete()'d, never appended to ctx.pDb -- a stronger invariant than
        # "staged only" (it never touches the database at all).
        m = re.search(
            r'if \(op == "write\.section\.generate2d"\) \{(.*?)\n    \}\n\n    // HasOp admitted',
            self.src, re.S,
        )
        self.assertIsNotNone(m, "write.section.generate2d branch not found")
        branch = m.group(1)
        self.assertNotIn("appendAcDbEntity", branch,
                         "generate2d must never append its transient probe entities")
        self.assertIn("delete pSolid", branch, "must delete the transient probe solid")
        self.assertIn("delete pSection", branch, "must delete the transient probe section")

    def test_strings_use_utf8_njsonstr_not_lossy_funnel(self):
        self.assertIn("njsonStr", self.src, "string emission must route through njsonStr")
        self.assertNotIn("wideToAscii(", self.src, "must not use the lossy wideToAscii funnel")
        self.assertIn("utf8ToWide", self.src, "entity name must use utf8ToWide for UTF-8 fidelity")

    def test_arg_validation(self):
        self.assertIn("MISSING_ARG", self.src,
                      "write.entity.section must validate its required points array")

    def test_acdbsection_classes_present(self):
        for cls in ("AcDbSection", "AcDb3dSolid"):
            self.assertIn(cls, self.src, "missing class %s" % cls)
        self.assertIn("generateSectionGeometry", self.src)
        self.assertIn("createBox", self.src)

    def test_state_enum_round_trip_names(self):
        # The three AcDbSection::State values must all be named both ways
        # (string -> enum for write.entity.section's "state" arg, enum -> string
        # for inspect.section.objects's "state" field).
        for name in ("kPlane", "kBoundary", "kVolume"):
            self.assertIn(name, self.src, "missing AcDbSection::State value %s" % name)
        for word in ('"plane"', '"boundary"', '"volume"'):
            self.assertIn(word, self.src, "missing state name literal %s" % word)


class TestW6SectionRegistry(unittest.TestCase):
    """The operations.v2.json records this family's ops must carry (ADD-only --
    no existing record touched)."""

    @classmethod
    def setUpClass(cls):
        reg_path = os.path.join(_REPO, "config", "operations.v2.json")
        with open(reg_path, "r", encoding="utf-8-sig") as f:
            reg = json.load(f)
        cls.by_id = {o.get("id"): o for o in reg["operations"] if isinstance(o, dict)}

    def test_records_present(self):
        for op_id in _IMPLEMENTED:
            self.assertIn(op_id, self.by_id, "%s missing from operations.v2.json" % op_id)

    def test_read_and_write_ops_implemented_native_job(self):
        for op_id in ("inspect.section.objects", "write.entity.section", "write.section.generate2d"):
            rec = self.by_id[op_id]
            self.assertEqual(rec.get("status"), "implemented",
                             "%s expected status=implemented" % op_id)
            self.assertEqual(rec["handler"].get("router_lane"), "ARIADNE_NATIVE_JOB",
                             "%s must route through the native ObjectARX job lane" % op_id)
            self.assertEqual(rec["handler"].get("dispatcher_symbol"), "w6sectionDispatch")

    def test_write_entity_section_is_write_copy_only(self):
        rec = self.by_id["write.entity.section"]
        self.assertEqual(rec["write_level"]["default_write_mode"], "write_copy")
        self.assertEqual(rec["write_level"]["allowed_write_modes"], ["write_copy"])
        self.assertNotIn("write_original", rec["write_level"]["allowed_write_modes"])


class TestW6SectionLiveRoundTrip(unittest.TestCase):
    """ENV-GATED (CADOS_LIVE=1): create -> reopen -> inspect against a staged
    copy of tests/fixtures/native_sample.dwg via the real router + native .crx.
    SKIPS (never fails) when accoreconsole or the fixture is unavailable -- the
    same convention tests/integration/test_native_graph_router.py uses. This is
    the automated re-derivation of the manual live smoke this wave already ran
    (runs/w6_section_live_smoke/)."""

    _FIXTURE = os.path.join(_REPO, "tests", "fixtures", "native_sample.dwg")
    _ACCORECONSOLE = r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe"

    @classmethod
    def _live_enabled(cls):
        return (os.environ.get("CADOS_LIVE") == "1"
                and os.path.isfile(cls._ACCORECONSOLE)
                and os.path.isfile(cls._FIXTURE))

    def setUp(self):
        if not self._live_enabled():
            reasons = []
            if os.environ.get("CADOS_LIVE") != "1":
                reasons.append("CADOS_LIVE!=1")
            if not os.path.isfile(self._ACCORECONSOLE):
                reasons.append("no accoreconsole")
            if not os.path.isfile(self._FIXTURE):
                reasons.append("no fixture")
            self.skipTest("SKIPPED_ENV: live w6-section round trip disabled (%s)" % ", ".join(reasons))
        sys.path.insert(0, _REPO)
        sys.path.insert(0, os.path.join(_REPO, "tools"))
        import run_job  # noqa: E402  (import here so the module import itself never
                                       # fails the headless suite when tools/ deps differ)
        self.run_job = run_job

    @staticmethod
    def _sha256(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def test_create_reopen_inspect_round_trip(self):
        sha_before = self._sha256(self._FIXTURE)
        with tempfile.TemporaryDirectory(prefix="w6_section_live_") as tmp:
            staged = os.path.join(tmp, "staged_input.dwg")
            with open(self._FIXTURE, "rb") as src, open(staged, "wb") as dst:
                dst.write(src.read())

            baseline = self.run_job.run_router_cad_job(
                staged, os.path.join(tmp, "step1"), "inspect.section.objects",
                intent="dwg", write_mode="read", timeout=180,
            )
            self.assertEqual(baseline["exit_code"], 0, baseline.get("error"))
            self.assertIsNotNone(baseline["result"], "no result from inspect.section.objects baseline")
            self.assertEqual(baseline["result"].get("count"), 0,
                             "fresh fixture should carry no AcDbSection entities yet")

            job = {
                "schema": "ariadne.autocad_sdk_job.v1",
                "operation": "write.entity.section",
                "write_mode": "write_copy",
                "points": [{"x": 0.0, "y": -500.0, "z": 0.0}, {"x": 0.0, "y": 500.0, "z": 0.0}],
                "vertical_dir": {"x": 0.0, "y": 0.0, "z": 1.0},
                "name": "W6SectionRoundTrip",
                "state": "boundary",
                "layer": "0",
            }
            job_path = os.path.join(tmp, "job_write_section.json")
            with open(job_path, "w", encoding="utf-8") as f:
                json.dump(job, f)

            created = self.run_job.run_router_cad_job(
                staged, os.path.join(tmp, "step2"), "write.entity.section",
                intent="dwg", write_mode="write_copy", job_path=job_path, timeout=180,
            )
            self.assertEqual(created["exit_code"], 0, created.get("error"))
            self.assertIsNotNone(created["result"], "no result from write.entity.section")
            self.assertTrue(created["result"].get("created"),
                            "write.entity.section did not report created:true")
            self.assertEqual(created["result"].get("class"), "AcDbSection")

            reopen_target = created["staged_used"] or staged
            reopened = self.run_job.run_router_cad_job(
                reopen_target, os.path.join(tmp, "step3"), "inspect.section.objects",
                intent="dwg", write_mode="read", timeout=180,
            )
            self.assertEqual(reopened["exit_code"], 0, reopened.get("error"))
            sections = (reopened["result"] or {}).get("sections") or []
            self.assertEqual(len(sections), 1, "reopen must find exactly the one created section")
            self.assertEqual(sections[0].get("name"), "W6SectionRoundTrip")
            self.assertEqual(sections[0].get("state"), "boundary")
            self.assertEqual(sections[0].get("handle"), created["result"].get("handle"))

        sha_after = self._sha256(self._FIXTURE)
        self.assertEqual(sha_before, sha_after, "original fixture DWG must stay byte-identical")


if __name__ == "__main__":
    unittest.main(verbosity=2)
