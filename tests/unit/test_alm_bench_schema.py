from __future__ import annotations

import io
import json
import os

import pytest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_BENCH_PATH = os.path.join(_REPO, "bench", "read_tasks.json")

_EXPECTED_IDS = ["READ-%03d" % i for i in range(1, 11)]


@pytest.fixture(scope="module")
def bench() -> dict:
    with io.open(_BENCH_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_schema_and_source_ir(bench: dict) -> None:
    assert bench["schema"] == "ariadne.alm_bench.read.v0"
    assert isinstance(bench["source_ir"], str)
    assert bench["source_ir"] != ""


def test_task_ids_are_the_expected_ten_in_order(bench: dict) -> None:
    tasks = bench["tasks"]
    assert len(tasks) == 10
    ids = [t["id"] for t in tasks]
    assert ids == _EXPECTED_IDS
    assert len(set(ids)) == len(ids)


def test_each_task_has_well_formed_fields(bench: dict) -> None:
    for task in bench["tasks"]:
        assert isinstance(task["question"], str)
        assert task["question"] != ""
        assert isinstance(task["gold"], (int, str))
        assert isinstance(task["gold_derivation"], str)
        assert task["gold_derivation"] != ""
        assert task["rubric"] == "exact_match"
