#!/usr/bin/env python3
"""Nested block-definition synthesis tests for ir_to_patch."""
from __future__ import annotations

import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ir_to_patch  # noqa: E402


def _insert(block_name: str, x: float = 0.0) -> dict:
    return {
        "handle": "ins_%s_%s" % (block_name, x),
        "layer": "0",
        "class": "AcDbBlockReference",
        "geometry": {"kind": "block_reference", "block_name": block_name, "position": [x, 0, 0]},
    }


def _line(handle: str) -> dict:
    return {
        "handle": handle,
        "layer": "0",
        "geometry": {"kind": "line", "start": [0, 0, 0], "end": [1, 0, 0]},
    }


def _nested_ref(block_name: str, handle: str) -> dict:
    return {
        "handle": handle,
        "layer": "0",
        "geometry": {
            "kind": "block_reference",
            "block_name": block_name,
            "position": [0, 0, 0],
        },
    }


class TestNestedBlockDefinitionSynthesis(unittest.TestCase):
    def _build_patch(self, ir: dict):
        return ir_to_patch.build_patch_from_ir(
            ir, {"staged_path": "s", "original_path": "o"}, "nested")

    def _create_block_names(self, patch: dict):
        return [op["args"]["name"] for op in patch["operations"] if op["operation"] == "create_block"]

    def _step_ids(self, patch: dict):
        return [op["step_id"] for op in patch["operations"]]

    def test_nested_chain_emits_dependency_before_parent(self):
        ir = {
            "entities": [_insert("A")],
            "block_definitions": [
                {"name": "A", "handle": "A1", "def_entities": [_line("A-L1"), _nested_ref("B", "A-R1")]},
                {"name": "B", "handle": "B1", "def_entities": [_line("B-L1")]},
            ],
        }

        patch, deferred = self._build_patch(ir)

        self.assertEqual(self._create_block_names(patch), ["B", "A"])
        self.assertEqual(
            [op["operation"] for op in patch["operations"]],
            ["create_block", "append_block_entity", "create_block", "append_block_entity",
             "create_blockref"],
        )
        self.assertEqual(len(self._step_ids(patch)), len(set(self._step_ids(patch))))
        self.assertTrue(any(d.get("kind") == "block_reference" for d in deferred))

    def test_three_level_chain_emits_deepest_definition_first(self):
        ir = {
            "entities": [_insert("A")],
            "block_definitions": [
                {"name": "A", "handle": "A1", "def_entities": [_line("A-L1"), _nested_ref("B", "A-R1")]},
                {"name": "B", "handle": "B1", "def_entities": [_line("B-L1"), _nested_ref("C", "B-R1")]},
                {"name": "C", "handle": "C1", "def_entities": [_line("C-L1")]},
            ],
        }

        patch, _deferred = self._build_patch(ir)

        self.assertEqual(self._create_block_names(patch), ["C", "B", "A"])
        self.assertEqual(
            [op["operation"] for op in patch["operations"]],
            ["create_block", "append_block_entity",
             "create_block", "append_block_entity",
             "create_block", "append_block_entity",
             "create_blockref"],
        )
        self.assertEqual(len(self._step_ids(patch)), len(set(self._step_ids(patch))))

    def test_cycle_synthesizes_each_definition_once_and_records_note(self):
        ir = {
            "entities": [_insert("A")],
            "block_definitions": [
                {"name": "A", "handle": "A1", "def_entities": [_line("A-L1"), _nested_ref("B", "A-R1")]},
                {"name": "B", "handle": "B1", "def_entities": [_line("B-L1"), _nested_ref("A", "B-R1")]},
            ],
        }

        patch, deferred = self._build_patch(ir)

        self.assertEqual(self._create_block_names(patch), ["B", "A"])
        self.assertEqual(self._create_block_names(patch).count("A"), 1)
        self.assertEqual(self._create_block_names(patch).count("B"), 1)
        cycle_notes = [d for d in deferred if "definition cycle detected at" in d.get("reason", "")]
        self.assertEqual(len(cycle_notes), 1)
        self.assertEqual(cycle_notes[0]["block_name"], "B")
        self.assertEqual(len(self._step_ids(patch)), len(set(self._step_ids(patch))))

    def test_missing_nested_definition_is_deferred_honestly(self):
        ir = {
            "entities": [_insert("A")],
            "block_definitions": [
                {"name": "A", "handle": "A1",
                 "def_entities": [_line("A-L1"), _nested_ref("MISSING", "A-R1")]},
            ],
        }

        patch, deferred = self._build_patch(ir)

        self.assertEqual(self._create_block_names(patch), ["A"])
        self.assertTrue(any(
            d.get("block_name") == "A"
            and d.get("def_entity_index") == 1
            and d.get("kind") == "block_reference"
            and d.get("reason") == "no block_definitions entry for nested block_name 'MISSING'"
            for d in deferred
        ))

    def test_flat_case_keeps_existing_operation_order_and_step_ids(self):
        ir = {
            "entities": [_insert("DOOR")],
            "block_definitions": [
                {"name": "DOOR", "handle": "D1", "def_entities": [_line("D-L1")]},
            ],
        }

        patch, deferred = self._build_patch(ir)

        self.assertEqual(
            [(op["operation"], op["step_id"]) for op in patch["operations"]],
            [("create_block", "bd0_0"), ("append_block_entity", "bd0_1"), ("create_blockref", "e0")],
        )
        self.assertEqual(deferred, [])

    def test_shared_nested_definition_is_emitted_once_across_modelspace_inserts(self):
        ir = {
            "entities": [_insert("A"), _insert("C", x=5.0)],
            "block_definitions": [
                {"name": "A", "handle": "A1", "def_entities": [_line("A-L1"), _nested_ref("B", "A-R1")]},
                {"name": "B", "handle": "B1", "def_entities": [_line("B-L1")]},
                {"name": "C", "handle": "C1", "def_entities": [_line("C-L1"), _nested_ref("B", "C-R1")]},
            ],
        }

        patch, _deferred = self._build_patch(ir)

        self.assertEqual(self._create_block_names(patch), ["B", "A", "C"])
        self.assertEqual(self._create_block_names(patch).count("B"), 1)
        self.assertEqual(
            [(op["operation"], op["step_id"]) for op in patch["operations"]],
            [("create_block", "bd0_0"),
             ("append_block_entity", "bd0_1"),
             ("create_block", "bd0_2"),
             ("append_block_entity", "bd0_3"),
             ("create_blockref", "e0"),
             ("create_block", "bd1_0"),
             ("append_block_entity", "bd1_1"),
             ("create_blockref", "e1")],
        )


if __name__ == "__main__":
    unittest.main()
