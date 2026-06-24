#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M02 TEST -- sqlite_ir_store rich tables on the LIVE native_full IR.

Intent (WHY):
  * M02 extends the SQLite store with the rich symbol-table / named-object tables
    (linetypes, text_styles, dim_styles, layouts, xrefs, dictionaries, xrecords,
    block_references, block_definitions, block_table_records). A native_full IR
    carries those sections; the store must materialize them so downstream set-
    based queries (lineage, audits) work. If the rich population drifts, those
    queries silently read empty/wrong tables.
  * The load-bearing invariant remains the ENTITY-COUNT TRUTH GATE: on the live
    golden native_full IR the entities row count must be exactly 21747 -- asserted
    via a real read-only query, not just the build report. The rich tables must
    also match the IR's realized section sizes (layers 70, block_definitions 245,
    layouts 3) -- the cross-engine ground truth.
  * Schema-stability: the rich tables exist regardless of coverage level, so a
    geometry_only IR leaves them EMPTY (not absent). That keeps downstream SQL
    stable. We assert both: full population on native_full, empty-but-present on
    the geometry_only fixture.

The live test loads runs/m02_cadctl_rich/dwg_graph_ir.json when present; if that
15MB artifact is absent the live assertions SKIP with an explicit reason (never
fail). The geometry_only schema-stability test always runs (uses the fixture IR).

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tests.live_fixture_utils import ensure_m02_cadctl_rich_fixture

# The live native_full IR fixture (21747 entities) the M02 contract pins.
_LIVE_IR = os.path.join(_REPO, "runs", "m02_cadctl_rich", "dwg_graph_ir.json")

# Cross-engine ground truth for the golden DWG's native_full IR.
_GOLDEN_TOTAL = 21747
_GOLDEN_LAYERS = 70
_GOLDEN_BLOCK_DEFS = 245
_GOLDEN_BTR = 248
_GOLDEN_LAYOUTS = 3
_GOLDEN_BLOCK_REFS = 2027


# The rich M02 tables that must always exist in the store schema.
_RICH_TABLES = (
    "linetypes", "text_styles", "dim_styles", "layouts", "xrefs",
    "dictionaries", "dictionary_entries", "xrecords", "block_references",
    "block_definitions", "block_table_records",
)


class TestRichSchemaStableOnGeometryOnly(unittest.TestCase):
    """Rich tables exist (but stay empty) for a geometry_only fixture IR."""

    def setUp(self):
        import ir_builder
        import sqlite_ir_store
        self.store = sqlite_ir_store
        self.ir = ir_builder.make_fixture_ir()  # geometry_only
        self._tmp = tempfile.mkdtemp(prefix="ir_store_rich_geo_")
        self.db = os.path.join(self._tmp, "ir.sqlite")
        self.report = self.store.build_store(self.ir, self.db)

    def tearDown(self):
        try:
            for n in os.listdir(self._tmp):
                os.remove(os.path.join(self._tmp, n))
            os.rmdir(self._tmp)
        except OSError:
            pass

    def test_rich_tables_present_in_schema(self):
        conn = sqlite3.connect("file:%s?mode=ro" % self.db, uri=True)
        try:
            names = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        finally:
            conn.close()
        for t in _RICH_TABLES:
            self.assertIn(t, names, "rich table %s missing from store schema" % t)

    def test_rich_tables_empty_for_geometry_only(self):
        # geometry_only IR has no symbol tables/blocks -> rich tables empty, and
        # the store must report them in row_counts (present, value 0).
        for t in ("linetypes", "text_styles", "dim_styles", "layouts", "xrefs",
                  "dictionaries", "xrecords"):
            self.assertEqual(self.report["row_counts"].get(t), 0,
                             "rich table %s should be empty for geometry_only" % t)


class TestRichStoreOnLiveNativeFullIr(unittest.TestCase):
    """build_store on the LIVE native_full IR: 21747 entities + rich counts."""

    def setUp(self):
        if not os.path.isfile(_LIVE_IR):
            ok, reason = ensure_m02_cadctl_rich_fixture(_REPO)
            if not ok:
                self.skipTest(
                    "SKIPPED_FIXTURE: live native_full IR not present: %s (%s)"
                    % (_LIVE_IR, reason)
                )
        import ir_builder
        import sqlite_ir_store
        self.store = sqlite_ir_store
        self.ir = ir_builder.load_ir(_LIVE_IR)
        self.assertEqual(self.ir.get("coverage_level"), "native_full",
                         "live fixture is not native_full")
        self._tmp = tempfile.mkdtemp(prefix="ir_store_rich_live_")
        self.db = os.path.join(self._tmp, "ir.sqlite")
        self.report = self.store.build_store(self.ir, self.db)

    def tearDown(self):
        try:
            for n in os.listdir(getattr(self, "_tmp", "") or ""):
                os.remove(os.path.join(self._tmp, n))
            os.rmdir(self._tmp)
        except (OSError, AttributeError):
            pass

    def test_entities_row_count_is_21747_via_query(self):
        res = self.store.query(self.db, "SELECT COUNT(*) FROM entities")
        self.assertEqual(res["rows"], [(_GOLDEN_TOTAL,)],
                         "entities table row count != 21747 (truth gate)")
        # and the build validation block agrees.
        self.assertTrue(self.report["validation"]["ok"],
                        "store validation.ok False on the live IR")
        self.assertEqual(self.report["row_counts"]["entities"], _GOLDEN_TOTAL)

    def test_rich_counts_match_ground_truth_via_query(self):
        def count(table):
            return self.store.query(self.db, "SELECT COUNT(*) FROM %s" % table)["rows"][0][0]
        self.assertEqual(count("layers"), _GOLDEN_LAYERS, "layers row count drift")
        self.assertEqual(count("block_definitions"), _GOLDEN_BLOCK_DEFS,
                         "block_definitions row count drift")
        self.assertEqual(count("layouts"), _GOLDEN_LAYOUTS, "layouts row count drift")
        self.assertEqual(count("block_references"), _GOLDEN_BLOCK_REFS,
                         "block_references row count drift")
        self.assertEqual(count("block_table_records"), _GOLDEN_BTR,
                         "block_table_records row count drift")

    def test_block_table_records_match_btr_count(self):
        # block_table_records is populated from symbol_tables.block_table_records;
        # the live IR carries 248 of them.
        self.assertEqual(self.report["row_counts"]["block_table_records"],
                         _GOLDEN_BTR)

    def test_by_type_query_matches_entities_by_type(self):
        # A set-based GROUP BY over the store must reproduce the IR's by-type
        # histogram (proves entities landed with their dxf_name intact).
        res = self.store.query(
            self.db,
            "SELECT dxf_name, COUNT(*) FROM entities GROUP BY dxf_name")
        got = {row[0]: row[1] for row in res["rows"]}
        expected = self.ir["diagnostics"]["entities_by_type"]
        self.assertEqual(got, expected,
                         "store GROUP BY dxf_name drifted from IR entities_by_type")
        self.assertEqual(sum(got.values()), _GOLDEN_TOTAL)


if __name__ == "__main__":
    unittest.main()
