#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed vacuous-census guard (measured: R3 blank-document race, 2026-07-08)."""
from __future__ import annotations

import json
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import full_roundtrip_capstone as frc


def test_vacuous_true_on_empty_graph():
    assert frc.census_extraction_vacuous({"entities": [], "block_definitions": []})
    assert frc.census_extraction_vacuous({})


def test_vacuous_false_with_entities_or_defs():
    assert not frc.census_extraction_vacuous(
        {"entities": [{"dxf_name": "LINE"}], "block_definitions": []})
    assert not frc.census_extraction_vacuous(
        {"entities": [], "block_definitions": [{"name": "B"}]})


def _fake_census_fn(sequence):
    """Each call writes the next IR from `sequence` into its census dir."""
    calls = {"n": 0, "dirs": []}

    def fake(staged_path, original_path, census_dir):
        ir = sequence[min(calls["n"], len(sequence) - 1)]
        calls["n"] += 1
        calls["dirs"].append(census_dir)
        os.makedirs(census_dir, exist_ok=True)
        ir_path = os.path.join(census_dir, "dwg_graph_ir.json")
        with open(ir_path, "w", encoding="utf-8") as fh:
            json.dump(ir, fh)
        return {"ok": True, "ir_path": ir_path}

    fake.calls = calls
    return fake


_EMPTY = {"entities": [], "block_definitions": []}
_FULL = {"entities": [{"dxf_name": "LINE"}], "block_definitions": []}


def test_first_attempt_nonempty_returns_immediately(tmp_path):
    fn = _fake_census_fn([_FULL])
    census, ir, attempts, vacuous = frc.run_census_with_vacuous_retry(
        "s", "o", str(tmp_path), pause_seconds=0, census_fn=fn)
    assert census["ok"] and ir == _FULL and attempts == 1 and not vacuous
    assert fn.calls["dirs"][0].endswith("census")


def test_transient_empty_recovers_on_retry(tmp_path):
    fn = _fake_census_fn([_EMPTY, _EMPTY, _FULL])
    census, ir, attempts, vacuous = frc.run_census_with_vacuous_retry(
        "s", "o", str(tmp_path), retries=2, pause_seconds=0, census_fn=fn)
    assert attempts == 3 and not vacuous and ir == _FULL
    assert fn.calls["dirs"][1].endswith("census_retry1")
    assert fn.calls["dirs"][2].endswith("census_retry2")


def test_persistent_empty_is_vacuous_fail(tmp_path):
    fn = _fake_census_fn([_EMPTY])
    census, ir, attempts, vacuous = frc.run_census_with_vacuous_retry(
        "s", "o", str(tmp_path), retries=2, pause_seconds=0, census_fn=fn)
    assert vacuous and attempts == 3 and ir == _EMPTY


def test_allow_empty_accepts_first_empty(tmp_path):
    fn = _fake_census_fn([_EMPTY])
    census, ir, attempts, vacuous = frc.run_census_with_vacuous_retry(
        "s", "o", str(tmp_path), retries=2, pause_seconds=0,
        allow_empty=True, census_fn=fn)
    assert not vacuous and attempts == 1 and ir == _EMPTY


def test_census_failure_returned_without_retry(tmp_path):
    def failing(staged_path, original_path, census_dir):
        return {"ok": False, "reason": "native job failed"}

    census, ir, attempts, vacuous = frc.run_census_with_vacuous_retry(
        "s", "o", str(tmp_path), retries=2, pause_seconds=0, census_fn=failing)
    assert not census["ok"] and ir is None and attempts == 1 and not vacuous
