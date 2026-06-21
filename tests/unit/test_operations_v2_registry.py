#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lane E TEST -- config/operations.v2.json is a valid, additive operation registry.

Intent (WHY):
  * operations.v2.json is the runtime source of truth for *which CAD operations
    exist and whether they are runnable*. It must validate against
    operation_registry.v2 schema, or the no-fake-success status vocabulary it
    encodes is unenforceable.
  * v2 is EXTEND-ONLY over the frozen v1 surface. Every one of the 29 v1 enum ops
    (schemas/cad_job.schema.json #/properties/operation) MUST reappear here with
    status in {implemented, wired}. If a v1 op were dropped, renamed, or demoted
    to a non-runnable status, an operation the live router still dispatches would
    silently lose its registry contract -- a regression the existing 37 tests
    would not catch.
  * Every handler.composed_of / catalog_op_id reference must resolve in
    config/autocad_native_arx_operation_catalog.json. An unresolved reference on
    a *runnable* (implemented/wired) op means the registry promises a handler
    built from a catalog op that does not exist -- a fake-success hole.

Honest exception (encoded, not hidden): the registry today carries ONE unresolved
composed_of ref, on the synthetic *stub* op ``diff.before_after`` ->
``inspect.database.graph`` (a not-yet-catalogued op). Because the op is a stub
(non-runnable, status=stub), this is a forward-declaration, not a fake success.
This test pins that exact known gap so (a) runnable ops stay clean and (b) the
gap cannot silently grow or change identity without turning this test red.

Discoverable by pytest and ``python -m unittest discover -s tests``.
Stdlib only; BOM-tolerant reads (utf-8-sig).
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

_CONFIG = os.path.join(_REPO, "config")
_SCHEMAS = os.path.join(_REPO, "schemas")
_JSON_ENCODING = "utf-8-sig"

_OPERATIONS_V2 = os.path.join(_CONFIG, "operations.v2.json")
_REGISTRY_SCHEMA = os.path.join(_SCHEMAS, "operation_registry.v2.schema.json")
_CATALOG = os.path.join(_CONFIG, "autocad_native_arx_operation_catalog.json")
_V1_CAD_JOB = os.path.join(_SCHEMAS, "cad_job.schema.json")

_RUNNABLE_STATUSES = {"implemented", "wired"}

# The single KNOWN, ALLOWED unresolved composed_of reference: a synthetic *stub*
# op forward-declares a catalog op that is not catalogued yet. Pinned exactly so
# it cannot silently grow. (op_id, status, unresolved_ref)
_KNOWN_UNRESOLVED = {("diff.before_after", "stub", "inspect.database.graph")}


def _load_json(path: str):
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _try_import_jsonschema():
    try:
        import jsonschema  # type: ignore
        return jsonschema
    except Exception:  # pragma: no cover
        return None


def _v1_operation_enum():
    """The 29 frozen v1 operation ids from schemas/cad_job.schema.json."""
    doc = _load_json(_V1_CAD_JOB)
    enum = (((doc.get("properties") or {}).get("operation")) or {}).get("enum")
    assert isinstance(enum, list) and enum, "v1 cad_job.schema.json operation enum missing"
    return list(enum)


def _catalog_op_ids():
    cat = _load_json(_CATALOG)
    ops = cat.get("operations") or []
    return {o.get("op_id") for o in ops if isinstance(o, dict) and o.get("op_id")}


class TestRegistryValidatesAgainstSchema(unittest.TestCase):
    """operations.v2.json conforms to operation_registry.v2 (when jsonschema present)."""

    def test_registry_parses_and_has_operations(self):
        reg = _load_json(_OPERATIONS_V2)
        self.assertEqual(reg.get("schema"), "ariadne.operations_registry.v2")
        self.assertIsInstance(reg.get("operations"), list)
        self.assertGreaterEqual(len(reg["operations"]), 29,
                                "registry must be a superset of the 29 v1 ops")

    def test_registry_validates_against_registry_schema(self):
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


class TestV1OpsPreservedAndWired(unittest.TestCase):
    """Every v1 enum op reappears in v2 with a runnable status; none removed."""

    def setUp(self):
        self.v1 = _v1_operation_enum()
        self.reg = _load_json(_OPERATIONS_V2)
        self.by_id = {o.get("id"): o for o in self.reg["operations"] if isinstance(o, dict)}

    def test_v1_enum_has_29_unique_ops(self):
        # Guards the test's own premise: the v1 surface is the frozen 29.
        self.assertEqual(len(self.v1), 29)
        self.assertEqual(len(set(self.v1)), 29, "v1 operation enum has duplicates")

    def test_every_v1_op_present_in_v2(self):
        missing = [op for op in self.v1 if op not in self.by_id]
        self.assertEqual(missing, [], "v1 ops missing from operations.v2.json: %r" % missing)

    def test_no_v1_op_removed_or_renamed(self):
        # Restated as a set-containment invariant: v1 enum is a subset of v2 ids.
        self.assertTrue(
            set(self.v1).issubset(set(self.by_id.keys())),
            "operations.v2.json dropped/renamed a v1 op (extend-only violated)",
        )

    def test_every_v1_op_is_implemented_or_wired(self):
        bad = [(op, self.by_id[op].get("status"))
               for op in self.v1
               if self.by_id[op].get("status") not in _RUNNABLE_STATUSES]
        self.assertEqual(
            bad, [],
            "v1 ops present but NOT implemented|wired (would fake-fail a live op): %r" % bad,
        )

    def test_v1_op_records_carry_required_fields(self):
        # A runnable v1 op must carry the schema-required handler/host fields so
        # the router can actually dispatch it.
        for op in self.v1:
            rec = self.by_id[op]
            with self.subTest(op=op):
                for req in ("id", "family", "status", "host_eligibility",
                            "write_level", "handler"):
                    self.assertIn(req, rec, "%s missing required field %s" % (op, req))
                self.assertIsInstance(rec["host_eligibility"], list)
                self.assertGreaterEqual(len(rec["host_eligibility"]), 1)


class TestCatalogReferencesResolve(unittest.TestCase):
    """composed_of / catalog_op_id refs resolve in the native ARX catalog."""

    def setUp(self):
        self.reg = _load_json(_OPERATIONS_V2)
        self.catalog_ids = _catalog_op_ids()
        self.assertGreater(len(self.catalog_ids), 0, "catalog has no op_ids")

    def _unresolved(self):
        """Yield (op_id, status, ref) for every catalog/composed_of ref that does
        not resolve in the catalog."""
        out = []
        for o in self.reg["operations"]:
            if not isinstance(o, dict):
                continue
            refs = set()
            cid = o.get("catalog_op_id")
            if cid:
                refs.add(cid)
            for c in (o.get("handler") or {}).get("composed_of") or []:
                refs.add(c)
            for r in refs:
                if r not in self.catalog_ids:
                    out.append((o.get("id"), o.get("status"), r))
        return out

    def test_runnable_ops_have_zero_unresolved_refs(self):
        """The load-bearing gate: NO implemented/wired op may reference a catalog
        op that does not exist. (Stub/blocked forward-decls are handled below.)"""
        unresolved_runnable = [
            (op, st, ref) for (op, st, ref) in self._unresolved()
            if st in _RUNNABLE_STATUSES
        ]
        self.assertEqual(
            unresolved_runnable, [],
            "runnable ops reference catalog ops that do not exist: %r" % unresolved_runnable,
        )

    def test_exact_mapped_catalog_ids_resolve(self):
        # mapping_type == exact means id IS a catalog op_id; it must resolve.
        bad = []
        for o in self.reg["operations"]:
            if isinstance(o, dict) and o.get("mapping_type") == "exact":
                cid = o.get("catalog_op_id")
                if cid and cid not in self.catalog_ids:
                    bad.append((o.get("id"), cid))
        self.assertEqual(bad, [], "exact-mapped ops with unresolvable catalog_op_id: %r" % bad)

    def test_full_unresolved_set_is_exactly_the_known_gap(self):
        """Pin the COMPLETE unresolved set to the one documented stub-op gap.

        This is the no-fake-success guard with teeth: any NEW unresolved ref (or
        a change to the known one's identity/status) turns this red. The known
        gap is a synthetic *stub* op forward-declaring a not-yet-catalogued op,
        which is legitimate -- but only as long as it stays a stub and stays this
        exact ref."""
        actual = set(self._unresolved())
        self.assertEqual(
            actual, _KNOWN_UNRESOLVED,
            "unresolved catalog-ref set drifted from the documented gap.\n"
            "  expected: %r\n  actual:   %r\n"
            "If a NEW op appears, either add its catalog op or (if runnable) this "
            "is a real fake-success bug. If the known stub gap was fixed, update "
            "_KNOWN_UNRESOLVED." % (_KNOWN_UNRESOLVED, actual),
        )
        # And belt-and-suspenders: every member of the known gap is non-runnable.
        for (_op, status, _ref) in actual:
            self.assertNotIn(
                status, _RUNNABLE_STATUSES,
                "a 'known gap' op is actually runnable -- that IS a fake success",
            )


if __name__ == "__main__":
    unittest.main()
