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


def _operation_table_ops(src, table_name):
    m = re.search(r"%s\[\]\s*=\s*\{(.*?)\};" % re.escape(table_name), src, re.S)
    assert m, "%s not found in source" % table_name
    return re.findall(r'\{\s*"([^"]+)"\s*,\s*"[^"]+"\s*\}', m.group(1))


def _table_ops(src):
    return _operation_table_ops(src, "kAriadneNativeOperationTable")


def _internal_table_ops(src):
    return _operation_table_ops(src, "kAriadneInternalOperationTable")


def _dispatcher_region(src):
    # ONLY the ARIADNE_NATIVE_JOB dispatcher body -- not the separate live-pump
    # dispatcher (which has its own op== chain further down).
    start = src.index("static std::string ariadneNativeJobResult(")
    end = src.index("static bool readCommandArg", start)
    return src[start:end]


def _function_region(src, declaration):
    start = src.index(declaration)
    opening = src.index("{", start)
    depth = 0
    for index in range(opening, len(src)):
        if src[index] == "{":
            depth += 1
        elif src[index] == "}":
            depth -= 1
            if depth == 0:
                return src[start : index + 1]
    raise AssertionError("unterminated function: %s" % declaration)


def _handler_ops(src):
    return re.findall(r'op == "([^"]+)"', _dispatcher_region(src))


class TestM08BDispatcherTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read()
        cls.table = _table_ops(cls.src)
        cls.internal_table = _internal_table_ops(cls.src)
        cls.handlers = _handler_ops(cls.src)

    def test_table_nonempty(self):
        self.assertGreaterEqual(len(self.table), 39,
                                "dispatch table must register the native ops (>=39)")

    def test_table_has_no_duplicates(self):
        self.assertEqual(len(self.table), len(set(self.table)),
                         "duplicate op_id in dispatch table")

    def test_public_and_internal_tables_classify_internal_opcodes_exactly(self):
        expected_internal = {
            "live.selection.monitor.enable",
            "live.selection.monitor.disable",
            "inspect.selection.monitor.registry",
            "extend.deep_native.firing_selftest",
            "inspect.deep_native.firing_report",
            "e2.inspect.xclip_membership",
        }
        public = set(self.table)
        internal = set(self.internal_table)
        self.assertEqual(len(self.internal_table), len(expected_internal))
        self.assertEqual(internal, expected_internal)
        self.assertTrue(public.isdisjoint(internal))
        self.assertNotIn("inspect.probe.property_count", internal)
        self.assertIn("inspect.probe.property_count", public)

    def test_table_handler_parity(self):
        # THE invariant. Drift in either direction = silent misroute.
        t, h = set(self.table) | set(self.internal_table), set(self.handlers)
        self.assertEqual(t, h,
                         "public+internal table<->handler drift; only_in_tables=%s only_in_handlers=%s"
                         % (sorted(t - h), sorted(h - t)))

    def test_e2_read_only_bootstrap_remains_internally_admitted(self):
        self.assertIn("e2.inspect.xclip_membership", self.internal_table)
        admission = self.src[
            self.src.index("static bool isAriadneNativeOperationAdmitted") :
            self.src.index("// route op to its owning family module")
        ]
        self.assertIn("findAriadneNativeOp(op)", admission)
        self.assertIn("findAriadneInternalOp(op)", admission)
        self.assertIn("familyHasOp(op)", admission)
        self.assertIn('else if (op == "e2.inspect.xclip_membership")', self.src)
        self.assertIn(
            "immutableJob, host, openedDocument->database()", self.src
        )

    def test_command_entrypoints_apply_least_privilege_admission_scopes(self):
        admission = _function_region(
            self.src, "static bool isAriadneNativeOperationAdmitted"
        )
        self.assertIn("AriadneOperationAdmissionScope::PublicOnly", admission)
        self.assertIn(
            "AriadneOperationAdmissionScope::PublicOrDiagnosticInternal",
            admission,
        )
        self.assertIn("AriadneOperationAdmissionScope::E2ReadOnlyOnly", admission)
        self.assertIn('op != "e2.inspect.xclip_membership"', admission)
        self.assertIn('op == "e2.inspect.xclip_membership"', admission)

        generic = _function_region(self.src, "static void ariadneNativeJob()")
        self.assertIn(
            "ariadneNativeJobWithScope(AriadneOperationAdmissionScope::PublicOnly)",
            generic,
        )

        args = _function_region(self.src, "static void ariadneNativeJobArgs()")
        diagnostic_call = (
            r"ariadneNativeJobWithScope\s*\(\s*"
            r"AriadneOperationAdmissionScope::PublicOrDiagnosticInternal\s*\)"
        )
        self.assertEqual(len(re.findall(diagnostic_call, args)), 2)

        mailbox = _function_region(self.src, "static void ariadneNativeJobMailbox()")
        self.assertRegex(mailbox, diagnostic_call)

        read_only = _function_region(
            self.src, "static void ariadneNativeJobArgsReadOnly()"
        )
        self.assertIn("AriadneOperationAdmissionScope::E2ReadOnlyOnly", read_only)
        self.assertNotIn('operation != "e2.inspect.xclip_membership"', read_only)

        dispatcher = _dispatcher_region(self.src)
        self.assertIn("OPERATION_NOT_ADMITTED_FOR_CONTEXT", dispatcher)

    def test_structured_not_implemented_is_table_gated(self):
        region = _dispatcher_region(self.src)
        # Unknown and context-forbidden operations are rejected separately before handling.
        self.assertIn("isAriadneNativeOperationKnown(op)", region,
                      "dispatcher must reject operations absent from every table")
        self.assertIn("isAriadneNativeOperationAdmitted(op, admissionScope)", region,
                      "dispatcher must enforce the entrypoint admission scope")
        self.assertIn("OPERATION_NOT_IMPLEMENTED", region,
                      "unknown op must return structured OPERATION_NOT_IMPLEMENTED")
        self.assertIn("OPERATION_NOT_ADMITTED_FOR_CONTEXT", region,
                      "known but forbidden op must return a structured context error")
        # helpers exist
        self.assertIn("const AriadneOperationSpec* findAriadneNativeOp", self.src)
        self.assertIn("const AriadneOperationSpec* findAriadneInternalOp", self.src)
        self.assertIn("void emitNativeError", self.src)

    def test_error_envelope_has_machine_stable_codes(self):
        self.assertIn(r'\"error_code\"', self.src, "error envelope must emit a machine-stable error_code field")
        for code in (
            "OPERATION_NOT_IMPLEMENTED",
            "OPERATION_NOT_ADMITTED_FOR_CONTEXT",
            "NO_WORKING_DATABASE",
            "OPERATION_DISPATCH_MISMATCH",
        ):
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
