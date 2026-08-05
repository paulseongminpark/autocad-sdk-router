#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer F3 TEST -- op_roundtrip_probe.py symbol-table name lookups
must be case-insensitive (AUDIT.md T2, #54).

Intent (WHY):
  DXF/AutoCAD symbol-table names (LAYER, DIMSTYLE, UCS, VIEW, VPORT,
  LINETYPE, TEXTSTYLE, BLOCK) are case-insensitive-unique -- ezdxf's own
  ``Table.has_entry``/``__contains__`` key on ``name.lower()`` (confirmed by
  ``inspect.getsource`` in AUDIT.md's T3 section). If a native write upserts
  onto an existing record whose stored name differs only in case from the
  caller's query name (e.g. ``create_layer(name="wall")`` upserting onto an
  existing ``"WALL"``), the record IS present in post_ir -- but the 8
  ``_X_by_name`` helpers below compared with a case-sensitive ``==``, so a
  successful upsert was reported as STATUS_HOLLOW (not found). This suite
  pins case-insensitive lookup for all 8 helpers, plus confirms an actually
  absent name still returns ``None`` (no false positive).

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib
only.
"""
from __future__ import annotations

import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import op_roundtrip_probe as probe  # noqa: E402


# --------------------------------------------------------------------------- #
# One (helper, ir-builder, stored-name) case per symbol table -- all 8 sites
# AUDIT.md's T2 flagged (op_roundtrip_probe.py:1544,1813,2043,2275,2493,2724,
# 2957,3378).
# --------------------------------------------------------------------------- #

def _ir_with(section: str, key: str, name: str) -> dict:
    return {section: {key: [{"name": name, "probe_marker": True}]}}


_CASES = (
    ("_layer_by_name", lambda name: _ir_with("symbol_tables", "layers", name)),
    ("_dimstyle_by_name", lambda name: _ir_with("symbol_tables", "dim_styles", name)),
    ("_ucs_by_name", lambda name: _ir_with("symbol_tables", "ucs", name)),
    ("_view_by_name", lambda name: _ir_with("symbol_tables", "views", name)),
    ("_vport_by_name", lambda name: _ir_with("symbol_tables", "viewports", name)),
    ("_linetype_by_name", lambda name: _ir_with("symbol_tables", "linetypes", name)),
    ("_textstyle_by_name", lambda name: _ir_with("symbol_tables", "text_styles", name)),
    ("_block_definition_by_name",
     lambda name: {"block_definitions": [{"name": name, "probe_marker": True}]}),
)


class TestSymbolTableLookupIsCaseInsensitive(unittest.TestCase):
    def test_all_eight_helpers_find_a_differently_cased_query(self):
        for func_name, build_ir in _CASES:
            with self.subTest(helper=func_name):
                func = getattr(probe, func_name)
                ir = build_ir("WALL")
                rec = func(ir, "wall")
                self.assertIsNotNone(
                    rec,
                    f"{func_name}: stored name 'WALL' not found by query 'wall' "
                    "(case-insensitive symbol-table lookup expected)",
                )
                self.assertTrue(rec.get("probe_marker"))

    def test_all_eight_helpers_still_find_exact_case_match(self):
        for func_name, build_ir in _CASES:
            with self.subTest(helper=func_name):
                func = getattr(probe, func_name)
                ir = build_ir("WALL")
                rec = func(ir, "WALL")
                self.assertIsNotNone(rec, f"{func_name}: exact-case match regressed")

    def test_all_eight_helpers_return_none_for_absent_name(self):
        for func_name, build_ir in _CASES:
            with self.subTest(helper=func_name):
                func = getattr(probe, func_name)
                ir = build_ir("WALL")
                rec = func(ir, "door")
                self.assertIsNone(
                    rec,
                    f"{func_name}: unrelated name 'door' must not match 'WALL'",
                )

    def test_all_eight_helpers_return_first_match_on_duplicate_names(self):
        # Mirrors _vport_by_name's own documented QUIRK (multiple "*Active"
        # records) -- first match wins, same contract before and after the
        # casefold fix.
        for func_name, build_ir in _CASES:
            with self.subTest(helper=func_name):
                func = getattr(probe, func_name)
                ir = build_ir("WALL")
                # duplicate a second record differing only in case
                section = next(iter(ir.values()))
                section_list = section if isinstance(section, list) else next(iter(section.values()))
                section_list.append({"name": "wall", "probe_marker": "second"})
                rec = func(ir, "wall")
                self.assertEqual(rec.get("probe_marker"), True,
                                  f"{func_name}: must return the FIRST match, not a later duplicate")


if __name__ == "__main__":
    unittest.main()
