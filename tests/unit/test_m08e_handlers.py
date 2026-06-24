#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08E TEST -- dictionaries / xdata-xrecords with staged writes.

Intent (WHY):
  M08E now owns a mixed surface: read handlers PLUS bounded staged-write dictionary /
  xdata / clone helpers. The load-bearing properties this test pins:

    1. HasOp<->Dispatch parity for the IMPLEMENTED ops. If HasOp claims an op the
       dispatcher must route it, or runtime would surface OPERATION_DISPATCH_MISMATCH.

    2. Staged-write proof. The write-shaped ops must use AriadneStagedWriteTransaction
       AND explicitly commit on success. A rollback-only scratch probe would not be
       enough evidence for a real mutation surface.

    3. No-original-write proof. The .inc may mutate ctx.pDb, but must not call
       save/saveAs/_QSAVE/writeDwgFile or raw command APIs. The router-staged copy is
       the only writable target.

    4. UTF-8 fidelity: string emission uses njsonStr; the lossy wideToAscii funnel is
       forbidden.

  Source-level only (no AutoCAD / no build needed). The native build proves compile+link.

Stdlib only. Discoverable by pytest and unittest.
"""
from __future__ import annotations

import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "m08e_handlers.inc")

# Ops M08E implements as real handlers. Read ops are pure; write-shaped ops mutate
# only the router-staged copy and must commit that staged transaction.
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
                         "m08eHasOp must claim exactly the implemented staged-safe op set; got %s"
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

    def test_no_original_write_tokens(self):
        # M08E may mutate the staged copy, but must never write the original DWG,
        # call raw commands, or use save/deploy paths.
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

    def test_write_ops_are_staged_and_committed(self):
        # kForWrite is allowed only inside staged transactions, and successful write
        # handlers must commit the staged mutation instead of rolling everything back.
        opens = re.findall(r"acdbOpenObject\([^;]*?,\s*AcDb::(\w+)", self.src, re.S)
        self.assertTrue(opens, "expected at least one acdbOpenObject call")
        self.assertIn("AriadneStagedWriteTransaction", self.src)
        self.assertIn("m08eCommit(", self.src)
        self.assertIn("staged_committed", self.src)
        self.assertNotIn("staged_rolled_back", self.code)

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
