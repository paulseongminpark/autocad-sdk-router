#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools.night import build_ornith_queue
from tools.night import ornith_night_runner


def _tiny_ir() -> dict:
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "block_definitions": [
            {
                "name": "SMALL_SYMBOL",
                "entity_count": 2,
                "def_entities": [
                    {"handle": "S1", "dxf_name": "LINE", "layer": "0"},
                    {"handle": "S2", "dxf_name": "TEXT", "layer": "0", "text": "x"},
                ],
            },
            {
                "name": "WALL_PART",
                "entity_count": 5,
                "def_entities": [
                    {
                        "handle": "A1",
                        "dxf_name": "LINE",
                        "layer": "A-WALL",
                        "geometry": {"kind": "line", "start": [0, 0, 0], "end": [10, 0, 0]},
                    },
                    {
                        "handle": "A2",
                        "dxf_name": "LINE",
                        "layer": "A-WALL",
                        "geometry": {"kind": "line", "start": [0, 1, 0], "end": [10, 1, 0]},
                    },
                    {"handle": "H1", "dxf_name": "HATCH", "layer": "A-FILL", "geometry": {"pattern_name": "H3", "loops": [{}, {}]}},
                    {"handle": "T1", "dxf_name": "TEXT", "layer": "A-ANNO", "text": "거실"},
                    {"handle": "C1", "dxf_name": "CIRCLE", "layer": "A-SYM", "geometry": {"radius": 2}},
                ],
            },
        ],
    }


class TestOrnithQueueBuilder(unittest.TestCase):
    def test_queue_builder_writes_one_valid_unit_for_min_entities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ir_path = os.path.join(tmp, "dwg_graph_ir.json")
            out_path = os.path.join(tmp, "queue.jsonl")
            with open(ir_path, "w", encoding="utf-8-sig") as fh:
                json.dump(_tiny_ir(), fh, ensure_ascii=False)

            count = build_ornith_queue.build_queue_file(ir_path, out_path, min_entities=5)

            self.assertEqual(count, 1)
            with open(out_path, "r", encoding="utf-8") as fh:
                lines = [json.loads(line) for line in fh if line.strip()]
            self.assertEqual(len(lines), 1)
            unit = lines[0]
            self.assertEqual(unit["kind"], "def_annotation")
            self.assertEqual(unit["unit_id"], "defannot-wall-part-1")
            self.assertIn("dxf_name histogram", unit["prompt"])
            self.assertIn("LINE=2", unit["prompt"])

    def test_prompt_is_inline_and_contains_def_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prompt = build_ornith_queue.build_units(_tiny_ir(), min_entities=5)[0]["prompt"]
            self.assertIn("Definition name: WALL_PART", prompt)
            self.assertIn("dxf_name histogram: ", prompt)
            self.assertIn("LINE layer=A-WALL handle=A1", prompt)
            self.assertNotIn(tmp, prompt)
            self.assertNotIn("dwg_graph_ir.json", prompt)


class TestOrnithRunnerHelpers(unittest.TestCase):
    def test_resume_filter_skips_ids_already_in_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipts = os.path.join(tmp, "receipts.jsonl")
            with open(receipts, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"unit_id": "u1", "ok": True}) + "\n")
                fh.write(json.dumps({"heartbeat": True, "done": 1, "failed": 0}) + "\n")
            completed = ornith_night_runner.read_completed_unit_ids(receipts)
            pending = ornith_night_runner.filter_pending_units(
                [{"unit_id": "u1"}, {"unit_id": "u2"}],
                completed,
            )
            self.assertEqual(pending, [{"unit_id": "u2"}])

    def test_json_extraction_helper_parses_noisy_text(self) -> None:
        text = "prefix\n```json\n{\"def\":\"WALL_PART\",\"wall_likelihood\":0.75}\n```\nsuffix"
        obj = ornith_night_runner.extract_json_object(text)
        self.assertEqual(obj["def"], "WALL_PART")
        self.assertEqual(obj["wall_likelihood"], 0.75)


if __name__ == "__main__":
    unittest.main()
