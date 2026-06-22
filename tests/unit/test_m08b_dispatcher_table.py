#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08B-T01 TEST -- native OperationSpec dispatcher core.

Intent (WHY):
  M08B-T01 converts the ARIADNE_NATIVE_JOB `if (op == ...)` chain into a TABLE-GATED
  dispatcher. `kAriadneNativeOperationTable` is the authoritative registry of the
  ops the native module implements; an op_id absent from it returns a structured
  OPERATION_NOT_IMPLEMENTED -- the honest contract the 474 catalogued ops (and the
  M08 family tickets that will build them) depend on.

  The load-bearing invariant is table<->handler PARITY: every table op_id has a
  handler branch and every handler branch is registered in the table. If they drift
  (a family ticket adds a handler but forgets the table, or registers an op_id it
  never handles), dispatch silently misroutes -- a catalogued op could read as
  "implemented", or an implemented op could read as NOT_IMPLEMENTED. This test fails
  CI on that drift. It is source-level (no AutoCAD/build needed); the native build
  (tools/build_native_acad.ps1) separately proves the change compiles + links.

Stdlib only. Discoverable by pytest and unittest.
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


def _table_ops(src):
    m = re.search(r"kAriadneNativeOperationTable\[\]\s*=\s*\{(.*?)\};", src, re.S)
    assert m, "kAriadneNativeOperationTable not found in source"
    return re.findall(r'\{\s*"([^"]+)"\s*,\s*"[^"]+"\s*\}', m.group(1))


def _dispatcher_region(src):
    # ONLY the ARIADNE_NATIVE_JOB dispatcher body -- not the separate live-pump
    # dispatcher (which has its own op== chain further down).
    start = src.index("static void ariadneNativeJob()")
    end = src.index("static bool readCommandArg", start)
    return src[start:end]


def _handler_ops(src):
    return re.findall(r'op == "([^"]+)"', _dispatcher_region(src))


class TestM08BDispatcherTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read()
        cls.table = _table_ops(cls.src)
        cls.handlers = _handler_ops(cls.src)

    def test_table_nonempty(self):
        self.assertGreaterEqual(len(self.table), 39,
                                "dispatch table must register the native ops (>=39)")

    def test_table_has_no_duplicates(self):
        self.assertEqual(len(self.table), len(set(self.table)),
                         "duplicate op_id in dispatch table")

    def test_table_handler_parity(self):
        # THE invariant. Drift in either direction = silent misroute.
        t, h = set(self.table), set(self.handlers)
        self.assertEqual(t, h,
                         "table<->handler drift; only_in_table=%s only_in_handlers=%s"
                         % (sorted(t - h), sorted(h - t)))

    def test_structured_not_implemented_is_table_gated(self):
        region = _dispatcher_region(self.src)
        # the gate runs inside the dispatcher, before handling
        self.assertIn("findAriadneNativeOp(op)", region,
                      "dispatcher must gate on the operation table")
        self.assertIn("OPERATION_NOT_IMPLEMENTED", region,
                      "unknown op must return structured OPERATION_NOT_IMPLEMENTED")
        # helpers exist
        self.assertIn("const AriadneOperationSpec* findAriadneNativeOp", self.src)
        self.assertIn("void emitNativeError", self.src)

    def test_error_envelope_has_machine_stable_codes(self):
        self.assertIn(r'\"error_code\"', self.src, "error envelope must emit a machine-stable error_code field")
        for code in ("OPERATION_NOT_IMPLEMENTED", "NO_WORKING_DATABASE", "OPERATION_DISPATCH_MISMATCH"):
            self.assertIn(code, self.src, "missing structured error_code: %s" % code)

    def test_generic_unsupported_else_removed(self):
        # the former catch-all is replaced by the structured drift guard
        region = _dispatcher_region(self.src)
        self.assertNotIn('"unsupported operation"', region,
                         "generic 'unsupported operation' else must be replaced by structured codes")
        self.assertIn("OPERATION_DISPATCH_MISMATCH", region,
                      "final else must be the defensive drift guard")


if __name__ == "__main__":
    unittest.main(verbosity=2)
