#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer W6-LAYERSTATE TEST -- native WRITE/READ family: AcDbLayerStateManager
ops (saved layer states / filters).

Intent (WHY):
  W6-LAYERSTATE fills families/w6_layerstate_handlers.inc with 4 ops built on the
  real AcDbLayerStateManager API (dblstate.h): inspect.layerstates.list,
  write.layerstate.save, write.layerstate.restore, write.layerstate.delete. The
  invariants that carry business meaning and must fail CI if violated:

  1. HASOP <-> DISPATCH PARITY -- every op id w6LayerStateHasOp admits must have
     an `op == "<id>"` branch in w6LayerStateDispatch, and vice versa. Drift =>
     OPERATION_DISPATCH_MISMATCH at runtime.

  2. HASOP LISTS EXACTLY THE 4 IMPLEMENTED OPS -- guards a silent shrink/grow.

  3. STAGED-WRITE PROOF (source-level) -- the write ops legitimately mutate the
     STAGED db (AcDbLayerStateManager bound to ctx.pDb) but must NEVER write the
     ORIGINAL DWG nor drive the command stack: no save()/saveAs()/writeDwgFile/
     _QSAVE and no acedCommand/acedCmd/acedInvoke. All emitted strings route
     through njsonStr (UTF-8 fidelity, required for the 70 Korean layer names in
     the fixture) -- the lossy wideToAscii funnel is never used for output.

  4. NO-FAKE ERROR DISCIPLINE -- handlers surface structured emitNativeError
     codes (MISSING_ARG / LAYERSTATE_NOT_FOUND / *_FAILED) instead of fabricating
     "ok", and every op is admitted by the shared familyHasOp/tryFamilyDispatch
     seam in AriadneNativeJob.cpp (the w6-layerstate registration block).

  Source-level only (no AutoCAD/build needed). Stdlib only.
"""
from __future__ import annotations

import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "w6_layerstate_handlers.inc")
_NATIVE_SRC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "AriadneNativeJob.cpp")

_IMPLEMENTED = [
    "inspect.layerstates.list",
    "write.layerstate.save",
    "write.layerstate.restore",
    "write.layerstate.delete",
]


def _read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _strip_comments(src):
    """Remove // line comments and /* */ block comments so banned-token checks fire
    on real CODE only (the safety header legitimately MENTIONS save()/saveAs()/
    acedCommand to document the prohibition -- same pattern the M08G test uses)."""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"//[^\n]*", " ", src)
    return src


def _hasop_region(src):
    m = re.search(r"static bool w6LayerStateHasOp\(const std::string& op\)\s*\{(.*?)\n\}", src, re.S)
    assert m, "w6LayerStateHasOp not found"
    return m.group(1)


def _dispatch_region(src):
    m = re.search(r"static bool w6LayerStateDispatch\(.*?\)\s*\{(.*)\n\}\s*$", src, re.S)
    assert m, "w6LayerStateDispatch not found"
    return m.group(1)


def _hasop_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _hasop_region(src)))


def _dispatch_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _dispatch_region(src)))


class TestW6LayerStateHandlers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read(_INC)
        cls.code = _strip_comments(cls.src)
        cls.hasop = _hasop_ops(cls.src)
        cls.dispatch = _dispatch_ops(cls.src)

    def test_inc_file_exists(self):
        self.assertTrue(os.path.exists(_INC), f"missing {_INC}")

    def test_signatures_present(self):
        self.assertRegex(self.src, r"bool\s+w6LayerStateHasOp\(const std::string& op\)")
        self.assertRegex(
            self.src,
            r"bool\s+w6LayerStateDispatch\(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r\)",
        )

    def test_hasop_lists_exactly_implemented(self):
        self.assertEqual(
            self.hasop, set(_IMPLEMENTED),
            "w6LayerStateHasOp op set drifted; only_in_src=%s missing_from_src=%s"
            % (sorted(self.hasop - set(_IMPLEMENTED)), sorted(set(_IMPLEMENTED) - self.hasop)),
        )

    def test_implemented_count_is_4(self):
        self.assertEqual(len(_IMPLEMENTED), 4)
        self.assertEqual(len(set(_IMPLEMENTED)), 4, "duplicate op id")
        self.assertEqual(len(self.hasop), 4)

    def test_hasop_dispatch_parity(self):
        missing = sorted(set(_IMPLEMENTED) - self.dispatch)
        self.assertEqual(missing, [], "implemented ops with no dispatch branch: %s" % missing)
        extra = sorted(self.dispatch - self.hasop)
        self.assertEqual(extra, [], "dispatch branches not admitted by HasOp: %s" % extra)

    def test_no_original_dwg_write_or_command_stack(self):
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
                re.search(pat, self.code),
                "w6-layerstate must not contain original-write/command-stack token (in code): %s" % pat,
            )

    def test_uses_real_layer_state_manager_api(self):
        # Positive proof this is a genuine handler (not a fake stub): it drives
        # the real AcDbLayerStateManager API, not a hand-rolled dictionary hack.
        self.assertIn("AcDbLayerStateManager", self.src)
        self.assertIn("dblstate.h", self.src)
        self.assertIn("saveLayerState", self.src)
        self.assertIn("restoreLayerState", self.src)
        self.assertIn("deleteLayerState", self.src)
        self.assertIn("getLayerStateNames", self.src)
        self.assertIn("getLayerStateMask", self.src)
        self.assertIn("getLayerStateLayers", self.src)
        self.assertIn("getLayerStateDescription", self.src)
        self.assertIn("hasLayerState", self.src)

    def test_strings_use_utf8_njsonstr_not_lossy_funnel(self):
        # Korean layer names (the real fixture has 70) must round-trip; output
        # must never go through the lossy wideToAscii() '?' funnel.
        self.assertIn("njsonStr", self.src)
        self.assertNotIn("wideToAscii(", self.code, "must not use the lossy wideToAscii funnel for OUTPUT")

    def test_no_fake_success_error_discipline(self):
        self.assertIn("emitNativeError", self.src)
        self.assertIn("MISSING_ARG", self.src)
        self.assertIn("LAYERSTATE_NOT_FOUND", self.src)
        self.assertIn("LAYERSTATE_SAVE_FAILED", self.src)
        self.assertIn("LAYERSTATE_RESTORE_FAILED", self.src)
        self.assertIn("LAYERSTATE_DELETE_FAILED", self.src)

    def test_save_checks_existence_before_overwrite_refusal(self):
        self.assertIn("hasLayerState", self.src)
        self.assertIn("LAYERSTATE_EXISTS", self.src)

    def test_every_branch_closes_the_json_object(self):
        # This TU's convention: the outer "{...}" is opened once near the top of
        # ariadneNativeJob(); every family branch (success or error) must close it
        # with a trailing "}" (emitNativeError already does; success branches must
        # match). A branch that forgets '}' would corrupt every job's output.
        # Looser structural check, on the comment-stripped view (the header prose
        # legitimately mentions the convention in a comment): every literal
        # \"status\":\"ok\" emission in real code (the C++ string literal escapes
        # its embedded quotes) is immediately followed by a closing '}' before the
        # next statement -- i.e. the ostringstream chain ends in `}";`.
        ok_emissions = [ln for ln in self.code.splitlines() if r'\"status\":\"ok\"' in ln]
        self.assertGreater(len(ok_emissions), 0, "no success emission found")
        for ln in ok_emissions:
            self.assertTrue(ln.rstrip().endswith('}";') or ln.rstrip().endswith('}"'),
                             "success emission does not close the outer JSON object: %r" % ln)


class TestW6LayerStateSeamRegistration(unittest.TestCase):
    """The minimal AriadneNativeJob.cpp registration block (#include + the two
    chain entries) must exist -- this is the ONLY edit this lane makes to the
    shared file, per the parallel-ownership contract."""

    @classmethod
    def setUpClass(cls):
        cls.src = _read(_NATIVE_SRC)

    def test_include_present(self):
        self.assertIn('#include "families/w6_layerstate_handlers.inc"', self.src)

    def test_gate_admits_w6_layerstate(self):
        self.assertIn("w6LayerStateHasOp(op)", self.src)

    def test_dispatcher_routes_to_w6_layerstate(self):
        m = re.search(r"static bool tryFamilyDispatch\(.*?\)\s*\{(.*?)\}", self.src, re.S)
        self.assertIsNotNone(m)
        self.assertIn("w6LayerStateDispatch(op, ctx, r)", m.group(1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
