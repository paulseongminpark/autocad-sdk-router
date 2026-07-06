#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CADOS Wave-0 F8 TEST -- reconcile_native_registry FOUR-surface vocab lockstep
+ the H-5/H-6 repoints it exists to keep honest.

Intent (WHY):
  F8 extends tools/reconcile_native_registry.py to keep FOUR op-id vocab
  surfaces in lockstep on every promotion:
    1. config/operations.v2.json          (the registry)
    2. families/*.inc HasOp gates + kAriadneNativeOperationTable (the native
       dispatcher's full live-admission gate; see all_coded_ops())
    3. tools/patch_engine.OP_REGISTRY_MAP   (declared patch-op -> registry id)
    4. tools/patch_ops.NATIVE_WRITE_OP_MAP  (patch-op -> registry id w/ a LIVE
       native write handler)

  Two concrete bugs motivated this (both fixed in this same node):
    H-5: set_layer's live handler mapped to write.layer.create, which only
         ENSURES a layer exists and silently ignores 'handle' -- an active
         fake-success (it never reassigns an existing entity's layer).
         Repointed at the real relayer modify.entity.common.
    H-6: OP_REGISTRY_MAP pointed move_entity/delete_entity at
         write.entity.modify / write.entity.delete -- ids that exist NOWHERE
         in the registry (a dangling target). Repointed at the real,
         resolvable ids modify.entity.transform / modify.entity.explode.

  This module proves both fixes with:
    - a synthetic-doc unit test per check_vocab_lockstep violation class
      (dangling_target / no_live_hasop / not_implemented / missing_evidence_ref),
    - a live cross-check that the REAL patch_engine/patch_ops vocab is in
      lockstep with the REAL registry + native dispatcher gate (0 violations),
    - a negative control reproducing the OLD (pre-fix) OP_REGISTRY_MAP values
      against the live registry, proving check_vocab_lockstep WOULD have
      caught the original H-6 bug,
    - a two-sided mock-dispatcher test for H-5 (set_layer really reassigns an
      entity's layer via the new mapping; the OLD create-only mapping FAILS
      the identical check).

  The two-sided test's "re-extract and confirm layer==X" step is mocked with
  a pure-Python mirror of the two relevant AriadneNativeJob.cpp branches (no
  accoreconsole/AutoCAD runtime in this sandbox -- Rule 12, no fake pass). The
  REAL live-runtime proof already exists and is wired at
  tools/probe_modify.py::run_probe_common (R1) / tests/unit/test_probe_modify.py;
  it has not yet been executed against a live AutoCAD host in this
  environment. Deferred command (CADOS F8 build_log):
    python tools/probe_modify.py --fixture tests/fixtures/native_sample.dwg \
        --out runs/probe_modify/<ts>/result.json

Stdlib only. Discoverable by pytest and ``python -m unittest discover -s tests``.
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

import reconcile_native_registry as rnr  # noqa: E402


# --------------------------------------------------------------------------- #
# Synthetic registry/coded_ops fixtures -- isolated from the live 517-op
# registry so each violation class is tested in isolation.
# --------------------------------------------------------------------------- #

def _op(op_id, status="implemented", evidence_refs=None):
    return {
        "id": op_id,
        "status": status,
        "evidence_refs": evidence_refs if evidence_refs is not None else ["some/evidence:ref"],
    }


def _doc(*ops):
    return {"operations": list(ops)}


class TestCheckVocabLockstepSynthetic(unittest.TestCase):
    """One violation class per test, fully isolated via injected external_vocab
    (no dependency on the live patch_engine/patch_ops import)."""

    def test_clean_mapping_no_violations(self):
        doc = _doc(_op("modify.entity.common"))
        coded_ops = {"modify.entity.common"}
        vocab = {"fake_surface": {"set_layer": "modify.entity.common"}}
        self.assertEqual(rnr.check_vocab_lockstep(doc, coded_ops, vocab), [])

    def test_dangling_target_when_id_missing_from_registry(self):
        # Reproduces the exact H-6 bug shape: OP_REGISTRY_MAP pointing at an
        # id that is not in the registry AT ALL.
        doc = _doc(_op("write.entity.line"))
        coded_ops = {"write.entity.line"}
        vocab = {"patch_engine.OP_REGISTRY_MAP": {"delete_entity": "write.entity.delete"}}
        violations = rnr.check_vocab_lockstep(doc, coded_ops, vocab)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["problem"], "dangling_target")
        self.assertEqual(violations[0]["target"], "write.entity.delete")

    def test_no_live_hasop_when_id_not_admitted_by_dispatcher(self):
        # The id EXISTS, is implemented, and is evidenced in the registry --
        # but no family HasOp gate (nor kAriadneNativeOperationTable) admits
        # it. This is the "in registry but not dispatchable" half of H-6.
        doc = _doc(_op("modify.entity.common"))
        coded_ops = set()  # nothing coded -- the dispatcher would refuse it live
        vocab = {"patch_ops.NATIVE_WRITE_OP_MAP": {"set_layer": "modify.entity.common"}}
        violations = rnr.check_vocab_lockstep(doc, coded_ops, vocab)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["problem"], "no_live_hasop")

    def test_not_implemented_status_flagged(self):
        doc = _doc(_op("modify.entity.common", status="stub"))
        coded_ops = {"modify.entity.common"}
        vocab = {"patch_ops.NATIVE_WRITE_OP_MAP": {"set_layer": "modify.entity.common"}}
        violations = rnr.check_vocab_lockstep(doc, coded_ops, vocab)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["problem"], "not_implemented")

    def test_missing_evidence_ref_fails(self):
        # Literal F8 acceptance: "a promotion missing evidence_ref FAILS".
        doc = _doc(_op("modify.entity.common", evidence_refs=[]))
        coded_ops = {"modify.entity.common"}
        vocab = {"patch_ops.NATIVE_WRITE_OP_MAP": {"set_layer": "modify.entity.common"}}
        violations = rnr.check_vocab_lockstep(doc, coded_ops, vocab)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["problem"], "missing_evidence_ref")

    def test_violations_accumulate_when_multiple_problems_present(self):
        doc = _doc(_op("modify.entity.common", status="catalogued", evidence_refs=[]))
        coded_ops = set()  # also not admitted
        vocab = {"patch_ops.NATIVE_WRITE_OP_MAP": {"set_layer": "modify.entity.common"}}
        violations = rnr.check_vocab_lockstep(doc, coded_ops, vocab)
        problems = {v["problem"] for v in violations}
        self.assertEqual(problems, {"no_live_hasop", "not_implemented", "missing_evidence_ref"})

    def test_two_surfaces_checked_independently(self):
        doc = _doc(_op("write.entity.line"), _op("modify.entity.common"))
        coded_ops = {"write.entity.line", "modify.entity.common"}
        vocab = {
            "patch_engine.OP_REGISTRY_MAP": {"create_line": "write.entity.line"},
            "patch_ops.NATIVE_WRITE_OP_MAP": {"set_layer": "modify.entity.common"},
        }
        self.assertEqual(rnr.check_vocab_lockstep(doc, coded_ops, vocab), [])


class TestPromotionEvidenceNeverEmpty(unittest.TestCase):
    """Accept: 'coverage test passes after any promotion'. evidence_for() is
    the ONLY place this tool's own --apply flip loop sources evidence_refs
    from; pin that it never returns empty tests/evidence_refs/dispatcher_symbol
    for any family letter, so a real promotion this tool performs can never
    trip missing_evidence_ref on its own output."""

    def test_evidence_for_never_empty(self):
        for letter in ("a", "g", "kc", "zzz"):
            ev = rnr.evidence_for(letter)
            self.assertTrue(ev["tests"])
            self.assertTrue(ev["evidence_refs"])
            self.assertTrue(ev["dispatcher_symbol"])


class TestNativeOperationTableOps(unittest.TestCase):
    """H-6 support: ariadneNativeJob() gates on
    `findAriadneNativeOp(op) OR familyHasOp(op)` (AriadneNativeJob.cpp) -- the
    pre-M08 kAriadneNativeOperationTable is HALF of the live dispatch gate,
    not covered by any family's HasOp. all_coded_ops() must include it or
    every legacy create_line/create_circle/write.layer.create-style id would
    spuriously read as "not admitted"."""

    def test_table_parses_nonempty_and_has_the_legacy_ops(self):
        ops = rnr.native_operation_table_ops()
        self.assertGreaterEqual(len(ops), 39)  # same floor test_m08b_dispatcher_table.py pins
        for legacy_op in ("write.entity.line", "write.entity.circle", "write.layer.create"):
            self.assertIn(legacy_op, ops)

    def test_all_coded_ops_is_the_union(self):
        table_ops = rnr.native_operation_table_ops()
        family_ops = set()
        for info in rnr.discover_families(None).values():
            family_ops |= info["ops"]
        combined = rnr.all_coded_ops()
        self.assertTrue(table_ops <= combined)
        self.assertTrue(family_ops <= combined)
        self.assertEqual(combined, table_ops | family_ops)


class TestVocabLockstepLiveRepo(unittest.TestCase):
    """The real proof: after the H-5/H-6 fixes, the ACTUAL patch_engine /
    patch_ops vocab is in lockstep with the ACTUAL registry + native
    dispatcher gate. Also a negative control proving check_vocab_lockstep
    would have caught the pre-fix bug."""

    @classmethod
    def setUpClass(cls):
        cls.doc = rnr._load_reg()
        cls.coded_ops = rnr.all_coded_ops()

    def test_live_vocab_is_in_lockstep(self):
        violations = rnr.check_vocab_lockstep(self.doc, self.coded_ops)
        self.assertEqual(violations, [], "patch_engine/patch_ops vocab drifted from the "
                                          "live registry/dispatcher gate: %r" % violations)

    def test_old_broken_op_registry_map_would_have_been_caught(self):
        # The PRE-H-6 values, reproduced as a literal historical oracle (never
        # actually assigned back onto patch_engine -- this only proves the
        # CHECKER has teeth against the exact bug class it was built for).
        old_vocab = {
            "patch_engine.OP_REGISTRY_MAP (pre-H-6, historical)": {
                "set_layer": "write.entity.modify",
                "move_entity": "write.entity.modify",
                "delete_entity": "write.entity.delete",
            },
        }
        violations = rnr.check_vocab_lockstep(self.doc, self.coded_ops, old_vocab)
        targets = {v["target"] for v in violations}
        self.assertEqual(targets, {"write.entity.modify", "write.entity.delete"})
        self.assertTrue(all(v["problem"] == "dangling_target" for v in violations))

    def test_new_h6_targets_exist_admitted_implemented_evidenced(self):
        by_id = {o["id"]: o for o in self.doc["operations"]}
        for reg_id in ("modify.entity.common", "modify.entity.transform", "modify.entity.explode"):
            self.assertIn(reg_id, by_id, "%s missing from the live registry" % reg_id)
            self.assertIn(reg_id, self.coded_ops, "%s not admitted by the live dispatcher gate" % reg_id)
            rec = by_id[reg_id]
            self.assertEqual(rec.get("status"), "implemented")
            self.assertTrue(rec.get("evidence_refs"))

    def test_old_dangling_ids_genuinely_do_not_exist(self):
        # Confirms H-6's premise: these ids are not a typo for something that
        # exists under a different status -- they are absent outright.
        by_id = {o["id"]: o for o in self.doc["operations"]}
        self.assertNotIn("write.entity.modify", by_id)
        self.assertNotIn("write.entity.delete", by_id)


class TestOpRegistryMapResolvesLive(unittest.TestCase):
    """H-6 acceptance, against the REAL tools/patch_engine module (not a
    synthetic double): every OP_REGISTRY_MAP value resolves live."""

    @classmethod
    def setUpClass(cls):
        import patch_engine
        cls.pe = patch_engine
        cls.doc = rnr._load_reg()
        cls.by_id = {o["id"]: o for o in cls.doc["operations"]}
        cls.coded_ops = rnr.all_coded_ops()

    def test_every_op_registry_map_value_resolves(self):
        for patch_op, reg_id in self.pe.OP_REGISTRY_MAP.items():
            with self.subTest(patch_op=patch_op, reg_id=reg_id):
                self.assertIn(reg_id, self.by_id, "%s -> %s is a dangling target" % (patch_op, reg_id))
                self.assertIn(reg_id, self.coded_ops,
                              "%s -> %s is not admitted by any live dispatch gate" % (patch_op, reg_id))
                self.assertEqual(self.by_id[reg_id].get("status"), "implemented")

    def test_move_and_delete_repointed_off_the_dangling_ids(self):
        self.assertEqual(self.pe.OP_REGISTRY_MAP["move_entity"], "modify.entity.transform")
        self.assertEqual(self.pe.OP_REGISTRY_MAP["delete_entity"], "modify.entity.explode")
        self.assertNotIn(self.pe.OP_REGISTRY_MAP["move_entity"], ("write.entity.modify",))
        self.assertNotIn(self.pe.OP_REGISTRY_MAP["delete_entity"], ("write.entity.delete",))


# --------------------------------------------------------------------------- #
# H-5 two-sided test: mocked dispatch mirror (no live AutoCAD in this
# sandbox -- see module docstring for the deferred live-runtime command).
# --------------------------------------------------------------------------- #

def _mock_native_dispatch(world, native_op, job_args):
    """Pure-Python mirror of the two relevant AriadneNativeJob.cpp branches,
    faithful to src/Ariadne.AcadNative/AriadneNativeJob.cpp
    ("write.layer.create") and families/m08g_handlers.inc
    ("modify.entity.common"). Used ONLY to prove set_layer's build_job_args
    wiring actually changes (or, for the old mapping, fails to change) an
    entity's layer -- NOT a substitute for the live CAD runtime."""
    world.setdefault("layers", set())
    if native_op == "write.layer.create":
        # AriadneNativeJob.cpp: only ensures a layer named 'name' exists;
        # 'handle' is never read by this branch at all.
        name = job_args.get("name") or "ARIADNE_P2"
        world["layers"].add(name)
        return {"status": "ok", "result": {"created": True, "name": name}}
    if native_op == "modify.entity.common":
        # m08g_handlers.inc: resolve 'handle', then AcDbEntity::setLayer.
        handle = job_args.get("handle")
        entity = (world.get("entities") or {}).get(handle)
        if entity is None:
            return {"status": "error", "result": {"modified": False}}
        set_layer = job_args.get("set_layer")
        layer_set = False
        if set_layer:
            world["layers"].add(set_layer)
            entity["layer"] = set_layer
            layer_set = True
        return {"status": "ok", "result": {"modified": True, "layer_set": layer_set}}
    return {"status": "error", "result": {}}


def _original_tables_build_job_args(native_op, args):
    """The OLD (pre-H-5) patch_ops.tables.build_job_args, reproduced as a
    literal historical oracle -- this is what set_layer used to route
    through before H-5 repointed it to patch_ops.entities/modify.entity.common."""
    if native_op == "write.layer.create":
        out = {}
        name = args.get("name") or args.get("layer")
        if name is not None:
            out["name"] = name
        if "color_index" in args:
            out["color_index"] = args["color_index"]
        return out
    return None


class TestSetLayerTwoSided(unittest.TestCase):
    """H-5 acceptance: (a) set_layer{handle,layer="X"} on an entity on layer
    "Y" -> re-extract -> layer=="X"; (b) NEGATIVE control -- the OLD
    create-only mapping MUST FAIL this test."""

    def setUp(self):
        import patch_ops
        self.patch_ops = patch_ops

    @staticmethod
    def _world():
        return {"entities": {"2A": {"layer": "Y"}}, "layers": {"Y"}}

    def test_a_new_relayer_reassigns_the_entitys_layer(self):
        world = self._world()
        native_op = self.patch_ops.NATIVE_WRITE_OP_MAP["set_layer"]
        self.assertEqual(native_op, "modify.entity.common", "H-5 repoint regressed")
        job_args = self.patch_ops.build_job_args(native_op, {"handle": "2A", "layer": "X"})
        self.assertEqual(job_args, {"handle": "2A", "set_layer": "X"})
        res = _mock_native_dispatch(world, native_op, job_args)
        self.assertEqual(res["status"], "ok")
        self.assertTrue(res["result"]["layer_set"])
        self.assertEqual(world["entities"]["2A"]["layer"], "X")

    def test_b_negative_control_old_create_only_mapping_fails(self):
        world = self._world()
        old_native_op = "write.layer.create"  # set_layer's mapping before H-5
        old_job_args = _original_tables_build_job_args(old_native_op, {"handle": "2A", "layer": "X"})
        # The bug, made concrete: 'handle' never even makes it into the job.
        self.assertNotIn("handle", old_job_args)
        res = _mock_native_dispatch(world, old_native_op, old_job_args)
        # The op self-reports "ok" (a layer named X now exists) -- that IS
        # the fake-success: it never touched entity 2A.
        self.assertEqual(res["status"], "ok")
        self.assertNotEqual(world["entities"]["2A"]["layer"], "X",
                            "OLD create-only set_layer mapping must NOT reassign the entity's "
                            "layer -- if this assertion fails, H-5 has regressed back to the "
                            "fake-success behavior")
        self.assertEqual(world["entities"]["2A"]["layer"], "Y")


class TestMainDryRunAgainstLiveRepo(unittest.TestCase):
    """End-to-end: reconcile_native_registry.main() in dry-run mode (no
    --apply, never writes) against the live repo exits 0 now that H-5/H-6 are
    fixed -- the CLI-level regression guard for this ticket."""

    def test_dry_run_exits_zero(self):
        old_argv = sys.argv
        try:
            sys.argv = ["reconcile_native_registry.py"]
            rc = rnr.main()
        finally:
            sys.argv = old_argv
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
