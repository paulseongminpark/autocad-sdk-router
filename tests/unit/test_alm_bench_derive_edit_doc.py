#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for docs/ALM_BENCH_V0_DERIVE_EDIT.md structure."""

from __future__ import annotations

import re
from pathlib import Path

DOC_PATH = Path(__file__).resolve().parents[2] / "docs" / "ALM_BENCH_V0_DERIVE_EDIT.md"

REQUIRED_HEADERS = [
    "# ALM-Bench v0 — DERIVE / EDIT / CHECK task-family spec",
    "## Grading principles",
    "## Family: DERIVE",
    "## Family: EDIT",
    "## Family: CHECK",
    "## Adversarial variants",
    "## Budget axes",
    "## Open items",
]

TASK_ID_PATTERN = re.compile(r"\b(?:DERIVE-0\d\d|EDIT-0\d\d|CHECK-0\d\d)\b")


def _read_doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_doc_exists():
    assert DOC_PATH.is_file()


def test_doc_contains_all_required_section_headers():
    content = _read_doc()
    for header in REQUIRED_HEADERS:
        assert header in content, f"missing header: {header}"


def test_doc_contains_at_least_nine_task_id_sketches():
    content = _read_doc()
    ids = TASK_ID_PATTERN.findall(content)
    assert len(ids) >= 9, f"found only {len(ids)} task-id sketches: {ids}"


def test_doc_cites_ipss_5_of_5():
    content = _read_doc()
    assert "IPSS 5/5" in content
