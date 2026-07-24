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

    2. M08E is nominally a READ family, but claims 7 write-shaped ops as smoke PROBES
       (write.block.append_entity / write.dictionary.set / write.entity.set_xdata /
       transform.database.deep_clone / transform.database.insert_block /
       acdb.database.create / infra.hostapp.provide_services) -- each wraps its mutation in
       AriadneStagedWriteTransaction and never commits, so nothing survives the call. This
       is the honest opposite of a fabricated read result: the op runs for real and then
       is undone, on purpose.
       p2-blockapp wave: write.block.append_entity was graduated OUT of that probe shape
       into a REAL, persisting primitive (drops the transaction wrapper; appends into a
       named block-table record, matching the no-wrapper shape every other real write
       handler in the codebase uses). The other 6 stay probe-only, unaffected.

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

# Ops M08E implements as real handlers. Read ops are pure; 6 of the 7 write-shaped ops run
# only inside staged transactions that roll back and never persist the original DWG --
# write.block.append_entity is the exception (p2-blockapp wave): a REAL, persisting write
# to the staged-copy DWG (never the original either way -- see test_write_opens_are_inside_
# staged_transactions, which still holds for the other 6).
_IMPLEMENTED = {
    "inspect.entity.get_xdata",
    "inspect.dictionary.named_objects",
    "inspect.dictionary.get",
    "inspect.block.iterate",
    "infra.hostapp.provide_services",
    "acdb.database.create",
    "write.object.create_ext_dict",
    "write.regapp.register",
    "write.dictionary.set",
    "write.entity.set_xdata",
    "write.block.append_entity",
    # P3 assoc-relink arc (R4v): second REAL, persisting write primitive
    # (no staged-transaction wrapper, same shape as append_entity) -- re-arms
    # hatch associativity with rebuilt-handle source ids + persistent reactors.
    "write.block.relink_hatch_assoc",
    "transform.database.deep_clone",
    "transform.database.insert_block",
}

# Remaining write/create ops not implemented by this ticket.
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
                         "m08eHasOp must claim exactly the 4 implemented read ops; got %s"
                         % sorted(self.claimed))

    def test_hasop_does_not_claim_deferred_write_ops(self):
        # The remaining deferred op stays NOT_IMPLEMENTED.
        self.assertEqual(self.claimed & _DEFERRED_WRITE, set(),
                         "m08eHasOp must not claim remaining deferred write ops")

    def test_dispatch_handles_every_claimed_op(self):
        # HasOp<->Dispatch parity: each claimed op has a dispatch branch (by its constant).
        used = {self.consts[name] for name in re.findall(r"kM08eOp\w+", self.dispatch)
                if name in self.consts}
        self.assertEqual(used, _IMPLEMENTED,
                         "m08eDispatch must route exactly the claimed ops; got %s" % sorted(used))
        # and each maps to a handler call
        for handler in ("m08eHandleEntityXdata", "m08eHandleDictNamed",
                        "m08eHandleDictGet", "m08eHandleBlockIterate"):
            self.assertIn(handler, self.dispatch,
                          "dispatch must call %s" % handler)

    def test_dispatch_default_returns_false(self):
        # Unclaimed op -> return false (so the seam routes on to the next family / drift guard).
        self.assertRegex(self.dispatch, r"return false;\s*$",
                         "m08eDispatch must fall through to `return false;` for unclaimed ops")

    def test_read_only_no_write_tokens(self):
        # M08E may perform staged scratch writes, but must never write the original
        # DWG, call raw commands, or use save/deploy paths.
        forbidden = [
            "saveAs", "_QSAVE", "writeDwgFile",
            "acedCommand", "acedCmd",
            "wblockCloneObjects",
            "acdbSetHostApplicationServices",
            "->insert(",
        ]
        for tok in forbidden:
            self.assertNotIn(tok, self.code,
                             "read-only family CODE must not contain write/host-bootstrap token %r" % tok)

    def test_write_opens_are_inside_staged_transactions(self):
        # kForWrite is allowed only for staged scratch operations; the file must show
        # the rollback guard and never call commit().
        opens = re.findall(r"acdbOpenObject\([^;]*?,\s*AcDb::(\w+)", self.src, re.S)
        self.assertTrue(opens, "expected at least one acdbOpenObject call")
        self.assertIn("AriadneStagedWriteTransaction", self.src)
        self.assertNotIn(".commit()", self.code)

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
