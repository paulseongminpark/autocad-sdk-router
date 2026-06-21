#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lane E TEST -- sqlite_ir_store: row-count truth gate, query round-trip, rtree report.

Intent (WHY):
  * build_store materializes the IR into SQLite so downstream set-based queries
    don't re-walk JSON. The load-bearing invariant is the ENTITY-COUNT TRUTH
    GATE: the realized ``entities`` row count must equal the IR's
    diagnostics.entity_count. A store that silently drops/dupes entities would
    make every downstream count (diff, validation) wrong; this test fails the
    moment that desyncs.
  * A read-only query must round-trip the data back (count + a specific row),
    proving the store is queryable and the rows landed -- not just that some
    table exists.
  * rtree capability must be REPORTED truthfully (rtree_available true/false).
    No-fake-success: the store must not claim a spatial index it could not build;
    whichever path is taken, bbox_index must hold the bbox-bearing rows.

Built from ir_builder.make_fixture_ir() so the store test tracks the real
producer's output, not a hand-rolled shape that could drift.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only
(sqlite3 is stdlib).
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


class _StoreTestBase(unittest.TestCase):
    def setUp(self):
        import ir_builder
        import sqlite_ir_store
        self.ir_builder = ir_builder
        self.store = sqlite_ir_store
        self.ir = ir_builder.make_fixture_ir()
        self.entity_count = self.ir["diagnostics"]["entity_count"]
        self._tmp = tempfile.mkdtemp(prefix="ir_store_test_")
        self.db_path = os.path.join(self._tmp, "ir.sqlite")
        self.report = self.store.build_store(self.ir, self.db_path)

    def tearDown(self):
        try:
            for n in os.listdir(self._tmp):
                os.remove(os.path.join(self._tmp, n))
            os.rmdir(self._tmp)
        except OSError:
            pass


class TestBuildStoreEntityCount(_StoreTestBase):
    """entities row count == IR diagnostics.entity_count (truth gate)."""

    def test_entities_row_count_equals_entity_count(self):
        # Direct SQL count -- the authoritative realized row count.
        result = self.store.query(self.db_path, "SELECT COUNT(*) FROM entities")
        rows = result["rows"]
        self.assertEqual(rows, [(self.entity_count,)],
                         "entities table row count != IR entity_count")

    def test_build_report_row_count_matches(self):
        self.assertEqual(self.report["row_counts"]["entities"], self.entity_count)

    def test_build_validation_block_ok(self):
        v = self.report["validation"]
        self.assertTrue(v["ok"], "store validation.ok is False: %r" % v)
        self.assertTrue(v["entity_count_match"])
        self.assertEqual(v["expected_entity_count"], self.entity_count)
        self.assertEqual(v["actual_entity_rows"], self.entity_count)

    def test_schema_ok_flag(self):
        # build_store records whether ir.schema matched the expected const.
        self.assertTrue(self.report["schema_ok"],
                        "store did not recognize the IR schema const")


class TestQueryRoundTrip(_StoreTestBase):
    """A read-only query returns the data that was stored."""

    def test_query_specific_entity_round_trips(self):
        # Pick a real handle from the fixture and prove it round-trips with its
        # dxf_name and layer intact.
        first = self.ir["entities"][0]
        handle = first["handle"]
        res = self.store.query(
            self.db_path,
            "SELECT handle, dxf_name, layer FROM entities WHERE handle = '%s'"
            % handle.replace("'", "''"),
        )
        self.assertEqual(res["columns"], ["handle", "dxf_name", "layer"])
        self.assertEqual(len(res["rows"]), 1, "handle %s not found in store" % handle)
        got_handle, got_dxf, got_layer = res["rows"][0]
        self.assertEqual(got_handle, handle)
        self.assertEqual(got_dxf, first["dxf_name"])
        self.assertEqual(got_layer, first["layer"])

    def test_distinct_layers_round_trip(self):
        # The store's layer set must match the IR's distinct entity layers.
        ir_layers = {e["layer"] for e in self.ir["entities"]}
        res = self.store.query(self.db_path, "SELECT DISTINCT layer FROM entities")
        store_layers = {r[0] for r in res["rows"]}
        self.assertEqual(store_layers, ir_layers)

    def test_query_is_read_only(self):
        # The query path opens mode=ro; a write must be rejected by SQLite,
        # proving queries cannot mutate the store.
        with self.assertRaises(sqlite3.OperationalError):
            self.store.query(self.db_path, "DELETE FROM entities")


class TestRtreeCapabilityReported(_StoreTestBase):
    """rtree capability is reported; bbox rows land whichever path is taken."""

    def test_capability_block_has_rtree_flag(self):
        cap = self.report.get("capability", {})
        self.assertIn("rtree_available", cap)
        self.assertIsInstance(cap["rtree_available"], bool)

    def test_bbox_index_holds_bbox_bearing_rows(self):
        # Every fixture entity carries a computed bbox, so bbox_index row-count
        # must equal entity_count regardless of rtree vs plain fallback. This is
        # the no-fake-success check: the store can't claim a spatial index it
        # didn't populate.
        bbox_rows = self.report["row_counts"]["bbox_index"]
        self.assertEqual(
            bbox_rows, self.entity_count,
            "bbox_index row count (%d) != entity_count (%d)"
            % (bbox_rows, self.entity_count),
        )
        # And the table is actually queryable.
        res = self.store.query(self.db_path, "SELECT COUNT(*) FROM bbox_index")
        self.assertEqual(res["rows"], [(self.entity_count,)])

    def test_rtree_path_creates_map_table_only_when_available(self):
        # Consistency: if rtree was reported available, the rowid->handle map
        # table must exist; if not, it must be absent. (No half-built state.)
        rtree = self.report["capability"]["rtree_available"]
        conn = sqlite3.connect("file:%s?mode=ro" % self.db_path, uri=True)
        try:
            names = {
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
                ).fetchall()
            }
        finally:
            conn.close()
        if rtree:
            self.assertIn("bbox_index_map", names,
                          "rtree reported available but bbox_index_map missing")
        else:
            self.assertNotIn("bbox_index_map", names,
                             "rtree reported unavailable but a map table exists")


if __name__ == "__main__":
    unittest.main()
