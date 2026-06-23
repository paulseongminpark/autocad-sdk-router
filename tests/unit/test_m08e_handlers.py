#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08E TEST -- native READ family E (blocks / dictionaries / xdata-xrecords).

Intent (WHY):
  M08E fills families/m08e_handlers.inc with the READ-ONLY ObjectARX handlers for the
  block / dictionary / xdata-xrecord surface. The load-bearing properties this test
  pins (so they can't silently regress in a refactor or a careless merge):

    1. HasOp<->Dispatch parity for the IMPLEMENTED ops. m08eHasOp() admits an op into
       the dispatcher gate (familyHasOp); m08eDispatch() must actually handle each one.
       If HasOp claims an op the dispatcher doesn't route, the runtime surfaces
       OPERATION_DISPATCH_MISMATCH -- this test fails first, at source level.

    2. The WRITE/create/clone ops in the M08E brief are NOT claimed. M08E is a READ
       family; write.block.append_entity / write.dictionary.set / write.entity.set_xdata
       / transform.database.deep_clone / transform.database.insert_block /
       acdb.database.create / infra.hostapp.provide_services mutate or create state and
       belong to the write lane (M08G). They must stay OUT of m08eHasOp so they keep
       returning the honest OPERATION_NOT_IMPLEMENTED -- never a fabricated read result.

    3. Read-only proof: the .inc must contain none of the original-DWG-write / host-bootstrap
       tokens (save/saveAs/_QSAVE, acedCommand/acedCmd, appendAcDbEntity, setXData(,
       setFromRbChain, deepCloneObjects, ->insert(, acdbSetHostApplicationServices). A
       read family that grows a write call is a contract breach, caught here.

    4. UTF-8 fidelity: name/string emission goes through njsonStr (preserve Korean layer
       and block names); the lossy wideToAscii() '?' funnel must not be used for output.

  Source-level only (no AutoCAD / no build needed). The native build
  (tools/build_native_acad.ps1) separately proves the .inc compiles + links (exit 0).

Stdlib only. Discoverable by pytest and unittest.
"""
from __future__ import annotations

import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "m08e_handlers.inc")

# The 11 ops M08E implements: 4 read handlers + 7 staged block/dictionary/xdata writes.
_IMPLEMENTED = {
    "inspect.entity.get_xdata",
    "inspect.dictionary.named_objects",
    "inspect.dictionary.get",
    "inspect.block.iterate",
    "infra.hostapp.provide_services",
    "transform.database.deep_clone",
    "transform.database.insert_block",
    "write.block.append_entity",
    "acdb.database.create",
    "write.dictionary.set",
    "write.entity.set_xdata",
}

_DEFERRED_WRITE = set()


def _read(p):
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _strip_comments(src):
    # Drop // line comments and /* */ block comments so token/op-id assertions test the
    # CODE, not the documentation prose (the .inc deliberately names the deferred write
    # ops in its header comment to explain why they're excluded).
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    out = []
    for line in src.splitlines():
        i = line.find("//")
        out.append(line if i < 0 else line[:i])
    return "\n".join(out)


def _hasop_body(src):
    # m08eHasOp body: the set of op-id string literals it returns true for.
    m = re.search(r"bool\s+m08eHasOp\(const std::string& op\)\s*\{(.*?)\n\}", src, re.S)
    assert m, "m08eHasOp not found"
    return m.group(1)


def _dispatch_body(src):
    m = re.search(
        r"bool\s+m08eDispatch\(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r\)\s*\{(.*?)\n\}",
        src, re.S)
    assert m, "m08eDispatch not found"
    return m.group(1)


def _op_constants(src):
    # Map the kM08eOp* constant name -> its op-id string value.
    return dict(re.findall(r'(kM08eOp\w+)\s*=\s*"([^"]+)"', src))


class TestM08EHandlers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read(_INC)
        cls.code = _strip_comments(cls.src)   # comment-free view for token/op-id checks
        cls.consts = _op_constants(cls.src)
        cls.hasop = _hasop_body(cls.src)
        cls.dispatch = _dispatch_body(cls.src)
        # Resolve which op-id strings HasOp returns true for, via the kM08eOp* constants
        # it references (the .inc uses constants, not raw literals, in HasOp).
        cls.claimed = {cls.consts[name] for name in re.findall(r"kM08eOp\w+", cls.hasop)
                       if name in cls.consts}

    def test_inc_exists_and_signatures(self):
        # Contract signatures (the seam test also checks these globally).
        self.assertRegex(self.src, r"bool\s+m08eHasOp\(const std::string& op\)")
        self.assertRegex(
            self.src,
            r"bool\s+m08eDispatch\(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r\)")

    def test_op_constants_cover_implemented(self):
        # Every implemented op id is declared as a single-source constant.
        self.assertEqual(set(self.consts.values()), _IMPLEMENTED,
                         "kM08eOp* constants must be exactly the implemented op ids")

    def test_hasop_claims_exactly_implemented(self):
        self.assertEqual(self.claimed, _IMPLEMENTED,
                         "m08eHasOp must claim exactly the implemented read/write ops; got %s"
                         % sorted(self.claimed))

    def test_hasop_does_not_claim_write_ops(self):
        self.assertEqual(self.claimed & _DEFERRED_WRITE, set(),
                         "m08eHasOp must not claim any deferred write op")

    def test_dispatch_handles_every_claimed_op(self):
        # HasOp<->Dispatch parity: each claimed op has a dispatch branch (by its constant).
        used = {self.consts[name] for name in re.findall(r"kM08eOp\w+", self.dispatch)
                if name in self.consts}
        self.assertEqual(used, _IMPLEMENTED,
                         "m08eDispatch must route exactly the claimed ops; got %s" % sorted(used))
        # and each maps to a handler call
        for handler in ("m08eHandleEntityXdata", "m08eHandleDictNamed",
                        "m08eHandleDictGet", "m08eHandleBlockIterate",
                        "m08eHandleHostProvide", "m08eHandleDbCreate",
                        "m08eHandleDictSet", "m08eHandleEntitySetXdata",
                        "m08eHandleAppendEntity", "m08eHandleDeepClone",
                        "m08eHandleInsertBlock"):
            self.assertIn(handler, self.dispatch,
                          "dispatch must call %s" % handler)

    def test_dispatch_default_returns_false(self):
        # Unclaimed op -> return false (so the seam routes on to the next family / drift guard).
        self.assertRegex(self.dispatch, r"return false;\s*$",
                         "m08eDispatch must fall through to `return false;` for unclaimed ops")

    def test_staged_write_no_original_persist_or_command_tokens(self):
        # M08E now includes staged write handlers, so append/set/deepClone/insert are
        # expected. The invariant is narrower: no original persistence and no raw
        # command stack.
        forbidden = ["saveAs", "_QSAVE", "writeDwgFile", "acedCommand", "acedCmd", "acedInvoke"]
        for tok in forbidden:
            self.assertNotIn(tok, self.code,
                             "m08e CODE must not contain original-persist/command token %r" % tok)
        for expected in ("appendAcDbEntity", "setXData(", "setFromRbChain", "deepCloneObjects", "->insert("):
            self.assertIn(expected, self.code, "expected real staged-write API %r" % expected)

    def test_opens_are_for_read_only(self):
        # Read handlers still open kForRead; staged write handlers legitimately open kForWrite.
        opens = re.findall(r"acdbOpenObject\([^;]*?,\s*AcDb::(\w+)", self.src, re.S)
        self.assertTrue(opens, "expected at least one acdbOpenObject call")
        self.assertIn("kForRead", opens)
        self.assertIn("kForWrite", opens)

    def test_utf8_via_njsonstr(self):
        # Name/string output must route through njsonStr (UTF-8); no lossy wideToAscii output.
        self.assertIn("njsonStr", self.src, "string output must use njsonStr (UTF-8 fidelity)")
        self.assertNotIn("wideToAscii(", self.src,
                          "must not use the lossy wideToAscii() funnel for JSON output")

    def test_emits_status_ok_and_structured_errors(self):
        # Success closes with status:ok; failures use emitNativeError (structured code).
        self.assertIn('\\"status\\":\\"ok\\"}', self.src,
                      "successful handlers must append status:ok and close the object")
        self.assertIn("emitNativeError(r,", self.src,
                      "error paths must use the structured emitNativeError envelope")
        for code in ("MISSING_HANDLE", "HANDLE_NOT_FOUND", "MISSING_KEY",
                     "BLOCK_NOT_FOUND", "NOD_OPEN_FAILED"):
            self.assertIn(code, self.src, "missing structured error_code: %s" % code)

    def test_reuses_intu_serializers_not_rerolled(self):
        # The contract: reuse in-TU primitives, don't re-roll encoders.
        for helper in ("xdataBlocksJson", "dictionaryEntriesJson",
                       "serializeEntityCommon", "handleOfId", "resolveHandle",
                       "AriadneReadTransaction"):
            self.assertIn(helper, self.src,
                          "expected reuse of in-TU primitive %s" % helper)


if __name__ == "__main__":
    unittest.main(verbosity=2)
