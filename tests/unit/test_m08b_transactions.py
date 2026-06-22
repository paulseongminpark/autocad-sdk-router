#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08B-T03 TEST -- transaction / document-lock / handle-resolver wrappers.

Intent (WHY):
  M08B-T03 gives the family/write tickets safe scoped DB access. The two load-bearing
  safety contracts:
    1. "failure rolls back" -- the staged-write transaction must ABORT (not commit) on
       any uncommitted scope exit. RAII encodes this: the destructor calls
       abortTransaction() guarded by !mCommitted. If someone later "fixes" the dtor to
       commit-on-destruct, staged failures would silently persist -- this test fails CI.
    2. "no original write" -- none of these wrappers may call save()/saveAs(); they work
       on the router-staged in-memory db only. A wrapper that gained a save() call would
       write the original -- this test fails CI.
  Source-level (no AutoCAD needed); the native build separately proves they compile+link
  against the ObjectARX AcTransactionManager API.

Stdlib only.
"""
from __future__ import annotations

import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_SRC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "AriadneNativeJob.cpp")


def _read():
    with open(_SRC, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _balanced_after(src, anchor):
    i = src.index(anchor)
    b = src.index("{", i)
    depth, j = 0, b
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[b:j + 1]
        j += 1
    raise AssertionError("unbalanced")


class TestM08BTransactions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read()

    def test_dbtrans_included(self):
        self.assertRegex(self.src, r'#include\s+"dbtrans\.h"')

    def test_wrappers_and_resolver_exist(self):
        self.assertIn("class AriadneReadTransaction", self.src)
        self.assertIn("class AriadneStagedWriteTransaction", self.src)
        self.assertIn("class AriadneDocumentWriteLock", self.src)  # the doc-lock wrapper (kept)
        self.assertRegex(self.src, r"bool\s+resolveHandle\(AcDbDatabase\* pDb, const std::string& hexHandle, AcDbObjectId& out\)")

    def test_staged_write_rolls_back_on_uncommitted_exit(self):
        body = _balanced_after(self.src, "class AriadneStagedWriteTransaction")
        # destructor: aborts iff not committed
        self.assertIn("abortTransaction", body, "staged-write must abort uncommitted txns (rollback)")
        self.assertIn("!mCommitted", body, "abort must be guarded by the uncommitted flag")
        # commit() goes through endTransaction and only then marks committed
        self.assertIn("endTransaction", body)
        self.assertRegexpMatches = self.assertRegex
        self.assertRegex(body, r"mCommitted\s*=\s*true")

    def test_read_txn_ends_on_scope_exit(self):
        body = _balanced_after(self.src, "class AriadneReadTransaction")
        self.assertIn("startTransaction", body)
        self.assertIn("endTransaction", body)

    def test_no_original_write_in_wrappers(self):
        for cls in ("class AriadneReadTransaction",
                    "class AriadneStagedWriteTransaction"):
            body = _balanced_after(self.src, cls)
            self.assertNotIn("saveAs", body, f"{cls} must not write the original (saveAs)")
            self.assertNotIn("->save(", body, f"{cls} must not write the original (save)")

    def test_resolver_uses_handle_and_getobjectid(self):
        m = re.search(r"bool\s+resolveHandle\([^)]*\)\s*\{", self.src)
        self.assertIsNotNone(m)
        body = _balanced_after(self.src, "bool resolveHandle(AcDbDatabase* pDb")
        self.assertIn("AcDbHandle", body)
        self.assertIn("getAcDbObjectId", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
