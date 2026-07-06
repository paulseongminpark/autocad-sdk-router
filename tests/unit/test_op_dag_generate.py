#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CADOS WAVE-0 F0.5 TEST -- op_dag.json completeness + acyclicity.

Intent (WHY):
  v2-A3 (CRITICAL): "the full op DAG is not an enumerated artifact" until this
  node exists, and it is only trustworthy as a WAVE-0 gate if two properties
  hold: (1) the emitted node set is EXACTLY the catalogue set
  (config/operations.v2.json operations[].id) -- a missing or invented op_id
  would silently break every downstream T1+ work item that cites an op_id
  row by id; (2) the predecessors[] graph is a genuine DAG (no cycles) -- a
  cyclic "dependency" is not schedulable by any T1+ wiring wave. These tests
  assert both against the DETERMINISTIC generator (tools.op_dag_generate) and
  separately assert the committed config/op_dag.json artifact is not stale
  (structurally identical to a fresh rebuild from the same registry).

Stdlib only; BOM-tolerant (utf-8-sig) reads. Discoverable by pytest and
unittest.
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

import op_dag_generate as odg  # noqa: E402

_OP_DAG_JSON = os.path.join(_REPO, "config", "op_dag.json")
_OPERATIONS_V2 = os.path.join(_REPO, "config", "operations.v2.json")
_REQUIRED_NODE_FIELDS = ("op_id", "predecessors", "arg_keys", "target_files",
                          "acceptance_test_id", "persistence_class")
_VALID_PCLASS = {"P", "D", "R", "L", "NON_GOAL"}


def _load_registry():
    with open(_OPERATIONS_V2, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _catalogue_ids():
    return {o["id"] for o in _load_registry()["operations"]}


class TestOpDagBuild(unittest.TestCase):
    """Exercises tools/op_dag_generate.build_dag() directly (in-memory), the
    same pattern test_m08_operation_coverage.py uses for
    operation_coverage_matrix.build_matrix()."""

    @classmethod
    def setUpClass(cls):
        cls.dag = odg.build_dag()
        cls.nodes = cls.dag["nodes"]
        cls.by_id = {n["op_id"]: n for n in cls.nodes}
        cls.catalogue = _catalogue_ids()

    # -- the two audited invariants the packet requires --------------------

    def test_node_set_equals_catalogue_set(self):
        node_ids = set(self.by_id)
        missing = sorted(self.catalogue - node_ids)
        invented = sorted(node_ids - self.catalogue)
        self.assertEqual(node_ids, self.catalogue,
                          "op_dag node set must equal the operations.v2.json catalogue set "
                          "exactly (missing=%r invented=%r)" % (missing, invented))
        self.assertEqual(len(self.nodes), len(self.catalogue), "no duplicate op_id nodes")
        # w3-dimstyle adds one new op (write.dimstyle.create) -- 517 -> 518.
        # w3-ltts adds two more (write.linetype.create, write.textstyle.create)
        # -- 518 -> 519 -> 520. P10 adds a fourth (modify.entity.xdata) --
        # 520 -> 521. p4-poly2d adds a fifth (write.entity.polyline2d.deep) --
        # 521 -> 522. p9-tables2 adds three more (write.ucs.create,
        # write.view.create, write.vport.create) -- 522 -> 523 -> 524 -> 525.
        # W6-DYNBLK adds three more (inspect.dynblock.references,
        # inspect.dynblock.properties, write.dynblock.property) --
        # 525 -> 526 -> 527 -> 528.
        self.assertEqual(len(self.nodes), 528, "operations.v2.json is currently 528 ops; a "
                                                "count drift here means the catalogue changed "
                                                "underneath this test, not a generator bug")

    def test_no_cycles(self):
        acyclic, cycle = odg.topo_check(
            self.by_id.keys(),
            {n["op_id"]: n["predecessors"] for n in self.nodes},
        )
        self.assertTrue(acyclic, f"cycle detected in predecessors graph: {cycle}")

    def test_audit_block_agrees_with_direct_checks(self):
        audit = self.dag["audit"]
        self.assertTrue(audit["node_set_equals_catalogue_set"])
        self.assertEqual(audit["missing_from_dag"], [])
        self.assertEqual(audit["invented_op_ids"], [])
        self.assertTrue(audit["acyclic"])
        self.assertIsNone(audit["cycle_example"])

    # -- structural sanity of every row -------------------------------------

    def test_every_node_has_required_fields_in_order(self):
        for n in self.nodes:
            self.assertEqual(tuple(n.keys()), _REQUIRED_NODE_FIELDS,
                              f"{n.get('op_id')} field set/order does not match the packet schema")

    def test_predecessors_reference_only_catalogued_ids(self):
        bad = [(n["op_id"], p) for n in self.nodes for p in n["predecessors"] if p not in self.by_id]
        self.assertEqual(bad, [], f"predecessors reference non-catalogued op_id: {bad[:10]}")

    def test_predecessors_never_self_reference(self):
        bad = [n["op_id"] for n in self.nodes if n["op_id"] in n["predecessors"]]
        self.assertEqual(bad, [])

    def test_persistence_class_values_valid(self):
        bad = [(n["op_id"], n["persistence_class"]) for n in self.nodes
               if n["persistence_class"] not in _VALID_PCLASS]
        self.assertEqual(bad, [])

    def test_acceptance_test_id_present_for_every_node(self):
        # every op in operations.v2.json carries a non-empty tests[] (also
        # asserted independently by test_m08_operation_coverage.py's
        # zero_untested_implemented gate), so this must never be None.
        missing = [n["op_id"] for n in self.nodes if not n["acceptance_test_id"]]
        self.assertEqual(missing, [])

    def test_target_files_all_exist_on_disk(self):
        missing = [(n["op_id"], rel) for n in self.nodes for rel in n["target_files"]
                   if not os.path.isfile(os.path.join(_REPO, rel))]
        self.assertEqual(missing, [], f"target_files must resolve to real files: {missing[:10]}")

    def test_target_files_are_sorted_and_deduped(self):
        bad = [n["op_id"] for n in self.nodes
               if n["target_files"] != sorted(set(n["target_files"]))]
        self.assertEqual(bad, [])

    def test_predecessors_are_sorted_and_deduped(self):
        bad = [n["op_id"] for n in self.nodes
               if n["predecessors"] != sorted(set(n["predecessors"]))]
        self.assertEqual(bad, [])

    # -- ground-truth spot checks (real registry signals, not fabricated) --

    def test_blocked_ops_are_non_goal_and_vice_versa(self):
        blocked_ids = {o["id"] for o in _load_registry()["operations"] if o.get("status") == "blocked"}
        self.assertGreater(len(blocked_ids), 0, "expected real blocked ops in the fixture corpus")
        non_goal_ids = {n["op_id"] for n in self.nodes if n["persistence_class"] == "NON_GOAL"}
        self.assertEqual(blocked_ids, non_goal_ids,
                          "NON_GOAL must correspond exactly to status=='blocked' (SS2.6: "
                          "60 hard-blocked ops are NON-GOAL)")

    def test_known_arg_key_ops_match_schema_ground_truth(self):
        # write.entity.line/circle carry a REAL per-op args schema in
        # schemas/cad_job.v2.schema.json -- ground truth, not derived.
        self.assertEqual(self.by_id["write.entity.line"]["arg_keys"], ["end", "layer", "start"])
        self.assertEqual(self.by_id["write.entity.circle"]["arg_keys"],
                          ["center", "layer", "radius"])
        self.assertEqual(self.by_id["write.block.insert"]["arg_keys"], ["name", "position"])

    def test_arg_keys_empty_when_no_schema_authored(self):
        # an arbitrary op with no if/then block in cad_job.v2.schema.json must
        # get an honest [] rather than a guessed key set.
        self.assertEqual(self.by_id["inspect.database.summary"]["arg_keys"], [])

    def test_composed_of_edges_survive_into_predecessors(self):
        # spot-check real authored handler.composed_of edges (operations.v2.json)
        # show up in the generated predecessors.
        self.assertIn("write.entity.blockref", self.by_id["write.block.insert"]["predecessors"])
        self.assertIn("transform.database.insert_block",
                       self.by_id["write.block.insert"]["predecessors"])
        self.assertIn("inspect.entity.get_xdata", self.by_id["inspect.xdata.get"]["predecessors"])

    def test_python_wired_ops_include_patch_engine_target_file(self):
        # tools/patch_engine.NATIVE_WRITE_OP_MAP wires exactly these native
        # op_ids today; each must list tools/patch_engine.py as a target file.
        import patch_engine
        for native_op in set(patch_engine.NATIVE_WRITE_OP_MAP.values()):
            self.assertIn("tools/patch_engine.py", self.by_id[native_op]["target_files"],
                          f"{native_op} is wired in NATIVE_WRITE_OP_MAP but missing patch_engine.py")


class TestOpDagArtifactFresh(unittest.TestCase):
    """The committed config/op_dag.json must not drift from the generator."""

    @staticmethod
    def _normalize_report_targets(doc):
        """Report citations are evidence churn, not DAG-structure churn.

        op_dag's stable contract is the node/predecessor/arg/test/code-file
        shape. Evidence refs under reports/ change whenever a registry lane
        adds fresh proof, and config/op_dag.json is intentionally regenerated
        later by the orchestrator rather than by every registry-only lane.
        """
        out = json.loads(json.dumps(doc))
        for node in out.get("nodes", []):
            node["target_files"] = [
                p for p in (node.get("target_files") or [])
                if not p.startswith("reports/")
            ]
        return out

    def test_artifact_exists(self):
        self.assertTrue(os.path.isfile(_OP_DAG_JSON),
                         "config/op_dag.json must exist -- run tools/op_dag_generate.py")

    def test_artifact_matches_fresh_build(self):
        with open(_OP_DAG_JSON, "r", encoding="utf-8") as f:
            on_disk = json.load(f)
        fresh = odg.build_dag()
        self.assertEqual(self._normalize_report_targets(on_disk),
                         self._normalize_report_targets(fresh),
                          "config/op_dag.json is stale relative to config/operations.v2.json -- "
                          "re-run: python tools/op_dag_generate.py")


if __name__ == "__main__":
    unittest.main(verbosity=2)
