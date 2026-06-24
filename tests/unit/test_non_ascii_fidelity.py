#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lock the non-ASCII (Hangul) layer-name fidelity of the native_full IR.

Intent (WHY):
  An earlier diagnosis claimed the CJK (Korean) layer names in the native_full
  IR were "mojibake" / upstream-corrupted at the accoreconsole boundary. That
  diagnosis was WRONG and is RETRACTED. The native ObjectARX ``acharToUtf8`` /
  ``wideToUtf8`` path emits CORRECT Hangul, byte-for-byte identical to an
  independent LibreDWG -> ezdxf(cp949) read (68 == 68 non-ASCII layers, same
  set). The thing that *looked* broken was a cp949 CONSOLE-DISPLAY artifact:
  piping UTF-8 Hangul through a cp949 Windows terminal renders garbage, but the
  bytes on disk are intact Unicode.

  This test makes that fact load-bearing and regression-proof. It reads the
  live native_full IR and proves, at the DATA level (never via terminal
  rendering):
    * Real Hangul is present (some layer name has a char in U+AC00..U+D7A3).
    * NO layer name contains U+FFFD (the replacement char) -- i.e. there was no
      real decode loss. A genuine cp949 decode failure would leave U+FFFD; its
      total absence is the proof the conversion did not drop bytes.
    * The specific proven-golden layer "X-평면도(기본형)$0$TEXT" is present in
      ``symbol_tables.layers`` -- pinned by EXACT CODE POINTS, not by a
      source-file string literal that a mis-encoded editor could mangle.
    * Every layer name round-trips through UTF-8 encode/decode losslessly --
      i.e. the strings are valid, fully-formed Unicode, not surrogate junk.

  If any assertion here fails, either the IR producer regressed the UTF-8
  conversion or the fixture changed -- both are real signals, not cosmetics.

Dual-runnable: discoverable by both pytest and
``python -m unittest discover -s tests``. Stdlib only. Reads the BOM-tolerant
IR with ``utf-8-sig`` (PowerShell may emit a UTF-8 BOM).
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tests.live_fixture_utils import ensure_m02_cadctl_rich_fixture

# Live native_full IR (golden, 21747 entities). Read-only fixture.
_IR_PATH = os.path.join(_REPO, "runs", "m02_cadctl_rich", "dwg_graph_ir.json")

# Hangul syllables block: U+AC00..U+D7A3.
_HANGUL_LO = 0xAC00
_HANGUL_HI = 0xD7A3

# The Unicode replacement character U+FFFD -- presence == real decode loss.
_REPLACEMENT = "�"

# Proven-golden layer name, defined by EXACT CODE POINTS so this source file's
# own encoding can never mangle the expectation. Decodes to:
#   "X-평면도(기본형)$0$TEXT"
_GOLDEN_LAYER_CODEPOINTS = (
    0x0058, 0x002D,           # "X-"
    0xD3C9, 0xBA74, 0xB3C4,   # "평면도"
    0x0028,                   # "("
    0xAE30, 0xBCF8, 0xD615,   # "기본형"
    0x0029,                   # ")"
    0x0024, 0x0030, 0x0024,   # "$0$"
    0x0054, 0x0045, 0x0058, 0x0054,  # "TEXT"
)
_GOLDEN_LAYER = "".join(chr(cp) for cp in _GOLDEN_LAYER_CODEPOINTS)


def _has_hangul(s):
    return any(_HANGUL_LO <= ord(c) <= _HANGUL_HI for c in s)


class TestNonAsciiLayerFidelity(unittest.TestCase):
    """Native_full IR preserves Korean layer names as correct UTF-8 Hangul."""

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(_IR_PATH):
            ok, reason = ensure_m02_cadctl_rich_fixture(_REPO)
            if not ok:
                raise unittest.SkipTest(
                    "SKIPPED_FIXTURE: native_full IR not present at %s (%s)"
                    % (_IR_PATH, reason)
                )
        with open(_IR_PATH, "r", encoding="utf-8-sig") as fh:
            cls.ir = json.load(fh)
        symtabs = cls.ir.get("symbol_tables") or {}
        cls.layers = symtabs.get("layers") or []
        cls.layer_names = [
            ly.get("name") for ly in cls.layers if isinstance(ly.get("name"), str)
        ]

    def test_layers_present(self):
        """Sanity: the fixture actually carries layer records to test."""
        self.assertTrue(
            self.layer_names,
            "native_full IR has no symbol_tables.layers names to verify",
        )

    def test_some_layer_name_is_hangul(self):
        """At least one layer name contains real Hangul (U+AC00..U+D7A3).

        If the conversion had ASCII-funnelled or stripped CJK, no name would
        contain any Hangul syllable -- so this is the positive proof that real
        Korean survived into the IR.
        """
        hangul_layers = [n for n in self.layer_names if _has_hangul(n)]
        self.assertTrue(
            hangul_layers,
            "no layer name contains any Hangul (U+AC00..U+D7A3); "
            "expected Korean layer names to be preserved",
        )

    def test_no_replacement_char_in_any_layer_name(self):
        """NO layer name may contain U+FFFD -- absence proves no decode loss.

        A genuine cp949->Unicode decode failure substitutes U+FFFD for the
        bytes it could not map. Zero U+FFFD across all names is the hard proof
        the native acharToUtf8 path lost nothing. This is the assertion that
        directly RETRACTS the prior "mojibake/corrupted" claim.
        """
        offenders = [n for n in self.layer_names if _REPLACEMENT in n]
        self.assertEqual(
            offenders,
            [],
            "found U+FFFD replacement char in layer name(s) -> real decode "
            "loss (reported by code point, not terminal rendering): %r"
            % [[hex(ord(c)) for c in n] for n in offenders],
        )

    def test_golden_hangul_layer_present(self):
        """The proven-golden layer 'X-평면도(기본형)$0$TEXT' is present.

        Pinned by exact code points (see _GOLDEN_LAYER_CODEPOINTS) so the
        expectation is independent of this file's on-disk encoding.
        """
        self.assertIn(
            _GOLDEN_LAYER,
            self.layer_names,
            "proven-golden Hangul layer absent. Expected code points %r; "
            "present layer name code points: %r"
            % (
                [hex(cp) for cp in _GOLDEN_LAYER_CODEPOINTS],
                [[hex(ord(c)) for c in n] for n in self.layer_names],
            ),
        )

    def test_every_layer_name_roundtrips_utf8(self):
        """Every layer name is well-formed Unicode (UTF-8 encode/decode is a
        lossless identity).

        Surrogate junk or malformed strings would raise or change on round
        trip; a clean identity for all names proves they are fully-formed
        UTF-8-encodable Unicode.
        """
        for n in self.layer_names:
            with self.subTest(layer=ascii(n)):
                self.assertEqual(
                    n.encode("utf-8").decode("utf-8"),
                    n,
                    "layer name failed UTF-8 round-trip: %r"
                    % [hex(ord(c)) for c in n],
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
