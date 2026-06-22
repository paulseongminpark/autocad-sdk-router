#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08B-T02 TEST -- generic serializers + UTF-8 JSON writer.

Intent (WHY):
  M08B-T02 provides the reusable serialization primitives the M08 family tickets
  (C-F) build on: njsonStr() (the canonical UTF-8 JSON-string writer) and the
  generic AcDbObject/AcDbEntity serializers. The load-bearing property is UTF-8
  FIDELITY: every emitted string must route through the lossless acharToAscii()/
  wideToUtf8() path, never the lossy wideToAscii() '?' funnel -- otherwise a Korean
  layer like "설비OPEN" serializes to "????" and the DWG Graph IR silently corrupts
  non-ASCII content. These source-level assertions fail CI if a primitive is
  removed or re-routed through the lossy funnel; runtime UTF-8 fidelity is proven by
  test_non_ascii_fidelity.py and the native build links the helpers.

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


def _fn_body(src, signature_re):
    """Return the brace-balanced body following the first signature match."""
    m = re.search(signature_re, src)
    assert m, f"signature not found: {signature_re}"
    i = src.index("{", m.end())
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
        j += 1
    raise AssertionError("unbalanced braces")


class TestM08BSerializers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read()

    def test_utf8_writer_three_overloads(self):
        for sig in (r"std::string\s+njsonStr\(const ACHAR\*",
                    r"std::string\s+njsonStr\(const std::wstring&",
                    r"std::string\s+njsonStr\(const std::string&"):
            self.assertRegex(self.src, sig, f"missing njsonStr overload: {sig}")

    def test_generic_object_and_entity_serializers_exist(self):
        self.assertIn("serializeObjectCommon(AcDbObject* pObj)", self.src)
        self.assertIn("serializeEntityCommon(AcDbEntity* pEnt)", self.src)

    def test_njsonStr_achar_routes_through_utf8_not_lossy(self):
        body = _fn_body(self.src, r"std::string\s+njsonStr\(const ACHAR\* s\)")
        self.assertIn("acharToAscii", body, "ACHAR njsonStr must use the UTF-8 acharToAscii path")
        self.assertNotIn("wideToAscii", body, "njsonStr must NOT use the lossy wideToAscii funnel")

    def test_wide_overload_uses_lossless_utf8(self):
        body = _fn_body(self.src, r"std::string\s+njsonStr\(const std::wstring& s\)")
        self.assertIn("wideToUtf8", body)
        self.assertNotIn("wideToAscii", body)

    def test_entity_serializer_emits_utf8_layer_and_props(self):
        body = _fn_body(self.src, r"std::string\s+serializeEntityCommon\(AcDbEntity\* pEnt\)")
        # layer/linetype go through the UTF-8 writer; the lossy funnel must not appear
        self.assertIn("njsonStr(pEnt->layer())", body)
        self.assertIn("color_index", body)
        self.assertNotIn("wideToAscii", body)

    def test_resbuf_string_path_uses_canonical_writer(self):
        body = _fn_body(self.src, r"std::string\s+resbufItemJson\(const resbuf\* rb\)")
        self.assertIn("njsonStr(rb->resval.rstring)", body,
                      "resbuf string value must route through njsonStr (UTF-8 writer)")

    def test_generic_serializers_no_lossy_funnel(self):
        # none of the new generic serializers may reintroduce wideToAscii
        for sig in (r"std::string\s+serializeObjectCommon\(AcDbObject\* pObj\)",
                    r"std::string\s+serializeEntityCommon\(AcDbEntity\* pEnt\)"):
            self.assertNotIn("wideToAscii", _fn_body(self.src, sig))


if __name__ == "__main__":
    unittest.main(verbosity=2)
