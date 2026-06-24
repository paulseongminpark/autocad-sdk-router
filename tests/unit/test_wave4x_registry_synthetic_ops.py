#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / "config" / "operations.v2.json"

_EXACT_FORBIDDEN = {
    "wave4x.generic_closure.validation_attended_debt",
}

_ID_PATTERNS = [
    re.compile(r"^wave\d", re.IGNORECASE),
    re.compile(r"\.generic_closure\.", re.IGNORECASE),
]
_FAMILY_PATTERNS = [
    re.compile(r"^wave\d", re.IGNORECASE),
    re.compile(r"^ticket", re.IGNORECASE),
]


def _ops():
    return json.loads(REGISTRY.read_text(encoding="utf-8-sig"))["operations"]


def test_no_wave_or_ticket_bookkeeping_ops_in_registry():
    bad = []
    for op in _ops():
        op_id = op.get("id", "")
        family = op.get("family", "")
        if op_id in _EXACT_FORBIDDEN:
            bad.append((op_id, family, "exact_forbidden"))
            continue
        if any(p.search(op_id) for p in _ID_PATTERNS):
            bad.append((op_id, family, "id_pattern"))
            continue
        if any(p.search(family) for p in _FAMILY_PATTERNS):
            bad.append((op_id, family, "family_pattern"))
    assert bad == [], bad


def test_audited_wave4x_synthetic_op_is_absent_from_registry():
    ids = {op["id"] for op in _ops()}
    assert "wave4x.generic_closure.validation_attended_debt" not in ids
