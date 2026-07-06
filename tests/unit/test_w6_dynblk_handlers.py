#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer W6-DYNBLK TEST -- native dynamic block reference property family.

Intent (WHY):
  W6-DYNBLK fills families/w6_dynblk_handlers.inc with the ObjectARX handlers for dynamic
  block REFERENCE properties (AcDbDynBlockReference / AcDbDynBlockReferenceProperty,
  dbdynblk.h) -- the #1 P1 excellence candidate from sdk_census_reaudit_20260706.md: reading
  and setting the visibility state/distance/flip/lookup value actually configured on an
  INSERTED dynamic block (door/window/furniture families), previously zero-coverage. The
  load-bearing properties this test pins (so they can't silently regress):

    1. HasOp<->Dispatch parity for the 3 implemented ops. w6dynblkHasOp() admits an op into
       the dispatcher gate (familyHasOp); w6dynblkDispatch() must actually handle each one.

    2. write.dynblock.property is a REAL, PERSISTING primitive (no AriadneStagedWriteTransaction
       wrapper) -- verified live (tests/integration/test_w6_dynblk_live.py) via a fresh-process
       reopen of the staged DWG showing the new value survived, plus a real bbox change proving
       the dynamic block's evaluation graph actually re-ran. This source test instead pins the
       STRUCTURAL absence of the staged-rollback wrapper for this op and the presence of the
       honesty guards (PROPERTY_READ_ONLY / UNSUPPORTED_PROPERTY_TYPE / VALUE_NOT_ALLOWED) that
       make "no fake success" true even when the underlying SDK's setValue() would otherwise
       silently no-op on an invalid value without an error.

    3. Read-only proof for the two inspect ops: no original-DWG-write / host-bootstrap tokens.

    4. UTF-8 fidelity: name/string emission goes through njsonStr (Korean property names/values,
       e.g. 문 크기/경첩/열림각 in the live test's Autodesk sample, must round-trip); the lossy
       wideToAscii() '?' funnel must not be used for output.

    5. Dynamic block AUTHORING is out of scope (census-confirmed SDK-wide impossibility, not a
       CADOS gap) -- this family must not reference any authoring-only symbol
       (BlockRepresentationManager / EvaluationGraph construction).

  Source-level only (no AutoCAD / no build needed). The native build
  (tools/build_native_acad.ps1) separately proves the .inc compiles + links (exit 0); the live
  integration test separately proves the runtime behavior against a real dynamic block.

Stdlib only. Discoverable by pytest and unittest.
"""
from __future__ import annotations

import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "w6_dynblk_handlers.inc")
_JOB_CPP = os.path.join(_REPO, "src", "Ariadne.AcadNative", "AriadneNativeJob.cpp")

_IMPLEMENTED = {
    "inspect.dynblock.references",
    "inspect.dynblock.properties",
    "write.dynblock.property",
}


def _read(p):
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _strip_comments(src):
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    out = []
    for line in src.splitlines():
        i = line.find("//")
        out.append(line if i < 0 else line[:i])
    return "\n".join(out)


def _hasop_body(src):
    m = re.search(r"bool\s+w6dynblkHasOp\(const std::string& op\)\s*\{(.*?)\n\}", src, re.S)
    assert m, "w6dynblkHasOp not found"
    return m.group(1)


def _dispatch_body(src):
    m = re.search(
        r"bool\s+w6dynblkDispatch\(const std::string& op, const AriadneJobCtx& ctx, "
        r"std::ostringstream& r\)\s*\{(.*?)\n\}",
        src, re.S)
    assert m, "w6dynblkDispatch not found"
    return m.group(1)


def _op_constants(src):
    return dict(re.findall(r'(kW6dOp\w+)\s*=\s*"([^"]+)"', src))


class TestW6DynblkHandlers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read(_INC)
        cls.code = _strip_comments(cls.src)
        cls.consts = _op_constants(cls.src)
        cls.hasop = _hasop_body(cls.src)
        cls.dispatch = _dispatch_body(cls.src)
        cls.claimed = {cls.consts[name] for name in re.findall(r"kW6dOp\w+", cls.hasop)
                       if name in cls.consts}

    def test_inc_exists_and_signatures(self):
        self.assertRegex(self.src, r"bool\s+w6dynblkHasOp\(const std::string& op\)")
        self.assertRegex(
            self.src,
            r"bool\s+w6dynblkDispatch\(const std::string& op, const AriadneJobCtx& ctx, "
            r"std::ostringstream& r\)")

    def test_op_constants_cover_implemented(self):
        self.assertEqual(set(self.consts.values()), _IMPLEMENTED,
                         "kW6dOp* constants must be exactly the implemented op ids")

    def test_hasop_claims_exactly_implemented(self):
        self.assertEqual(self.claimed, _IMPLEMENTED,
                         "w6dynblkHasOp must claim exactly the 3 implemented ops; got %s"
                         % sorted(self.claimed))

    def test_dispatch_handles_every_claimed_op(self):
        used = {self.consts[name] for name in re.findall(r"kW6dOp\w+", self.dispatch)
                if name in self.consts}
        self.assertEqual(used, _IMPLEMENTED,
                         "w6dynblkDispatch must route exactly the claimed ops; got %s" % sorted(used))
        for handler in ("w6dHandleDynReferences", "w6dHandleDynProperties",
                        "w6dHandleSetDynProperty"):
            self.assertIn(handler, self.dispatch, "dispatch must call %s" % handler)

    def test_dispatch_default_returns_false(self):
        self.assertRegex(self.dispatch, r"return false;\s*$",
                         "w6dynblkDispatch must fall through to `return false;` for unclaimed ops")

    def test_seam_registration_in_job_cpp(self):
        # The shared TU must #include this family and OR it into both gates -- the
        # concurrent-lane "// w6-dynblk" delimited block (see the file header contract).
        job_src = _read(_JOB_CPP)
        self.assertIn('#include "families/w6_dynblk_handlers.inc"', job_src)
        self.assertIn("w6dynblkHasOp(op)", job_src)
        self.assertIn("w6dynblkDispatch(op, ctx, r)", job_src)

    def test_no_original_dwg_write_tokens(self):
        # This family never writes the ORIGINAL DWG, calls raw commands, or authors a
        # dynamic block's parameter/action graph (out of scope, SDK-wide impossible).
        forbidden = [
            "saveAs", "_QSAVE", "writeDwgFile",
            "acedCommand", "acedCmd",
            "acdbSetHostApplicationServices",
            "BlockRepresentationManager", "EvaluationGraph",
        ]
        for tok in forbidden:
            self.assertNotIn(tok, self.code,
                             "family CODE must not contain forbidden token %r" % tok)

    def test_write_op_has_no_staged_rollback_wrapper(self):
        # write.dynblock.property is a REAL, persisting write (matches write.entity.line/
        # write.block.append_entity's no-wrapper shape) -- it must not roll back via
        # AriadneStagedWriteTransaction, and must report staged_rolled_back:false.
        self.assertNotIn("AriadneStagedWriteTransaction", self.code)
        self.assertIn('"staged_rolled_back\\":false', self.src)

    def test_honesty_guards_present(self):
        for code in ("MISSING_HANDLE", "HANDLE_NOT_FOUND", "NOT_A_BLOCK_REFERENCE",
                     "NOT_A_DYNAMIC_BLOCK", "PROPERTY_NOT_FOUND", "PROPERTY_READ_ONLY",
                     "UNSUPPORTED_PROPERTY_TYPE", "VALUE_NOT_ALLOWED", "BLOCK_NOT_FOUND"):
            self.assertIn(code, self.src, "missing structured error_code: %s" % code)
        self.assertIn("emitNativeError(r,", self.src)

    def test_emits_status_ok(self):
        self.assertIn('\\"status\\":\\"ok\\"}', self.src,
                      "successful handlers must append status:ok")

    def test_utf8_via_njsonstr(self):
        self.assertIn("njsonStr", self.src, "string output must use njsonStr (UTF-8 fidelity)")
        self.assertNotIn("wideToAscii(", self.src,
                         "must not use the lossy wideToAscii() funnel for JSON output")

    def test_reuses_intu_serializers_not_rerolled(self):
        for helper in ("njsonStr", "handleOf", "handleOfId", "resolveHandle",
                       "AriadneReadTransaction", "emitNativeError", "jsonFindString",
                       "jsonFindNumber", "utf8ToWide", "acharToAscii", "kJsonDoublePrecision"):
            self.assertIn(helper, self.src, "expected reuse of in-TU primitive %s" % helper)

    def test_uses_public_dbdynblk_api_only(self):
        # The census confirms dynamic block AUTHORING is impossible via any public API --
        # this family must only touch the documented read/set-property surface.
        self.assertIn('#include "dbdynblk.h"', self.src)
        for api in ("AcDbDynBlockReference", "AcDbDynBlockReferenceProperty",
                    "isDynamicBlock", "getBlockProperties", "dynamicBlockTableRecord",
                    "setValue", "getAllowedValues"):
            self.assertIn(api, self.src, "expected use of documented API %s" % api)


if __name__ == "__main__":
    unittest.main(verbosity=2)
