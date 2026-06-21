#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M02 TEST -- operations.v2.json totals/status consistency (expanded).

Intent (WHY):
  * operations.v2.json is the runtime source of truth for WHICH CAD ops exist and
    whether they are runnable. M02 EXPANDED it (more implemented ops). Two things
    must hold for the no-fake-success status vocabulary to mean anything:
      (1) the declared roll-up ``totals.by_status`` MUST equal the per-record
          counts -- a declared count that lies about the records is itself a
          fake-success surface; and
      (2) every frozen v1 enum op (the 29) must still be present with a runnable
          status (extend-only). A dropped/demoted v1 op silently breaks a live
          router dispatch.
  * inspect.database.graph -- the native_full database-graph op the whole M02
    rich path depends on -- must be PRESENT and status=='implemented' (it has a
    live .crx handler + evidence). If it were catalogued/stub, the rich IR path
    would be claiming an unwired op.
  * The registry must parse with a BOM (utf-8-sig) -- the file on this box is
    BOM-prefixed -- and conform to operation_registry.v2 (when jsonschema present).

This EXTENDS the existing test_operations_v2_registry.py (which pins v1 presence
and the catalog-ref gap) with the M02-specific totals/inspect.database.graph
assertions; it does not duplicate the catalog-resolution tests.

Discoverable by pytest and ``python -m unittest discover -s tests``.
Stdlib only; BOM-tolerant reads (utf-8-sig).
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from collections import Counter

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_CONFIG = os.path.join(_REPO, "config")
_SCHEMAS = os.path.join(_REPO, "schemas")
_JSON_ENCODING = "utf-8-sig"

_OPERATIONS_V2 = os.path.join(_CONFIG, "operations.v2.json")
_REGISTRY_SCHEMA = os.path.join(_SCHEMAS, "operation_registry.v2.schema.json")
_V1_CAD_JOB = os.path.join(_SCHEMAS, "cad_job.schema.json")
_CATALOG = os.path.join(_CONFIG, "autocad_native_arx_operation_catalog.json")

_RUNNABLE = {"implemented", "wired"}
_M04_ALLOWED_STATUSES = {
    "implemented", "wired", "stub", "catalogued", "deprecated", "blocked",
}


def _load_json(path):
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _try_import_jsonschema():
    try:
        import jsonschema  # type: ignore
        return jsonschema
    except Exception:  # pragma: no cover
        return None


class TestRegistryParsesWithBom(unittest.TestCase):
    def test_parses_utf8_sig(self):
        # The contract explicitly notes config JSON may carry a UTF-8 BOM; a plain
        # utf-8 read would choke. utf-8-sig must succeed and yield the registry.
        reg = _load_json(_OPERATIONS_V2)
        self.assertEqual(reg.get("schema"), "ariadne.operations_registry.v2")
        self.assertIsInstance(reg.get("operations"), list)
        self.assertGreaterEqual(len(reg["operations"]), 29)


class TestTotalsMatchRecords(unittest.TestCase):
    """Declared totals.by_status equals the per-record status histogram."""

    def setUp(self):
        self.reg = _load_json(_OPERATIONS_V2)
        self.ops = [o for o in self.reg["operations"] if isinstance(o, dict)]

    def test_totals_present(self):
        totals = self.reg.get("totals")
        self.assertIsInstance(totals, dict, "registry has no totals block")
        self.assertIn("by_status", totals)

    def test_total_operations_count_matches(self):
        totals = self.reg.get("totals") or {}
        if "operations" in totals:
            self.assertEqual(totals["operations"], len(self.ops),
                             "totals.operations != number of operation records")

    def test_by_status_counts_match_records(self):
        declared = self.reg.get("totals", {}).get("by_status") or {}
        counted = Counter(o.get("status") for o in self.ops)
        # Every declared status count must equal the realized record count; and
        # there must be no realized status the declaration omits.
        self.assertEqual(
            dict(declared), dict(counted),
            "totals.by_status drifted from the per-record counts.\n"
            "  declared: %r\n  counted : %r" % (dict(declared), dict(counted)),
        )

    def test_no_record_carries_unknown_status(self):
        bad = [(o.get("id"), o.get("status")) for o in self.ops
               if o.get("status") not in _M04_ALLOWED_STATUSES]
        self.assertEqual(bad, [], "operation records with unknown status: %r" % bad)

    def test_catalog_union_is_classified(self):
        catalog = _load_json(_CATALOG)
        catalog_ids = {o.get("op_id") for o in catalog.get("operations", [])
                       if isinstance(o, dict) and o.get("op_id")}
        registry_ids = {o.get("id") for o in self.ops if o.get("id")}
        # M04 makes operations.v2 authoritative for the 480 native catalog plus
        # the router synthetic/wired surface. Every catalog op_id must now have
        # one classified registry record (exact-mapped wired ids count once).
        missing = sorted(catalog_ids - registry_ids)
        self.assertEqual(missing, [], "catalog op_ids missing from operations.v2: %r" % missing[:20])
        self.assertGreaterEqual(
            len(self.ops), len(catalog_ids),
            "registry must classify at least the full native catalog",
        )

    def test_every_operation_has_m04_metadata(self):
        required = {
            "operation", "family", "status", "hosts", "engines", "write_level",
            "handler", "schema_refs", "policy", "tests", "evidence_refs", "notes",
        }
        missing = []
        for op in self.ops:
            absent = sorted(k for k in required if k not in op)
            if absent:
                missing.append((op.get("id"), absent))
        self.assertEqual(missing, [], "operations missing M04 metadata: %r" % missing[:20])


class TestInspectDatabaseGraphImplemented(unittest.TestCase):
    """inspect.database.graph (the native_full op) is present + implemented."""

    def setUp(self):
        self.reg = _load_json(_OPERATIONS_V2)
        self.by_id = {o.get("id"): o for o in self.reg["operations"]
                      if isinstance(o, dict)}

    def test_present(self):
        self.assertIn("inspect.database.graph", self.by_id,
                      "inspect.database.graph missing from the registry")

    def test_status_implemented(self):
        rec = self.by_id["inspect.database.graph"]
        self.assertEqual(
            rec.get("status"), "implemented",
            "inspect.database.graph must be 'implemented' (the rich IR path "
            "depends on a live native handler), got %r" % rec.get("status"))

    def test_carries_required_handler_fields(self):
        rec = self.by_id["inspect.database.graph"]
        for req in ("id", "family", "status", "host_eligibility",
                    "write_level", "handler"):
            self.assertIn(req, rec, "inspect.database.graph missing %s" % req)
        self.assertIsInstance(rec["host_eligibility"], list)
        self.assertGreaterEqual(len(rec["host_eligibility"]), 1)


class TestFrozenV1OpsStillPresent(unittest.TestCase):
    """All 29 frozen v1 enum ops remain in v2 with a runnable status."""

    def setUp(self):
        doc = _load_json(_V1_CAD_JOB)
        enum = (((doc.get("properties") or {}).get("operation")) or {}).get("enum")
        self.assertIsInstance(enum, list)
        self.v1 = list(enum)
        self.reg = _load_json(_OPERATIONS_V2)
        self.by_id = {o.get("id"): o for o in self.reg["operations"]
                      if isinstance(o, dict)}

    def test_v1_surface_is_29(self):
        self.assertEqual(len(self.v1), 29)
        self.assertEqual(len(set(self.v1)), 29)

    def test_every_v1_op_present_and_runnable(self):
        missing = [op for op in self.v1 if op not in self.by_id]
        self.assertEqual(missing, [], "v1 ops missing from v2: %r" % missing)
        bad = [(op, self.by_id[op].get("status")) for op in self.v1
               if self.by_id[op].get("status") not in _RUNNABLE]
        self.assertEqual(
            bad, [],
            "v1 ops present but not implemented|wired (M02 must stay extend-only): %r"
            % bad)

    def test_native_write_ops_for_patch_engine_are_implemented(self):
        # patch_engine's NATIVE_WRITE_OP_MAP targets these three; they must be
        # implemented or apply_staged would be promising an unwired write.
        for op in ("write.entity.line", "write.entity.circle", "write.layer.create"):
            self.assertIn(op, self.by_id, "native write op %s missing" % op)
            self.assertEqual(self.by_id[op].get("status"), "implemented",
                             "native write op %s not implemented" % op)


class TestRegistryConformsToSchema(unittest.TestCase):
    def test_validates_against_registry_schema(self):
        jsonschema = _try_import_jsonschema()
        if jsonschema is None:
            self.skipTest("SKIPPED_DEP: jsonschema not importable")
        schema = _load_json(_REGISTRY_SCHEMA)
        jsonschema.Draft7Validator.check_schema(schema)
        reg = _load_json(_OPERATIONS_V2)
        validator = jsonschema.Draft7Validator(schema)
        errors = sorted(validator.iter_errors(reg), key=lambda e: list(e.path))
        self.assertEqual(
            errors, [],
            "operations.v2.json does not conform to operation_registry.v2: "
            + "; ".join("%s: %s" % ("/".join(str(p) for p in e.path), e.message)
                       for e in errors[:12]),
        )


if __name__ == "__main__":
    unittest.main()
