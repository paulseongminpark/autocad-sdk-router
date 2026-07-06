#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""semantic_anchor.py -- deterministic unit tests for semantic anchor census.

Intent (WHY):
  * The semantic-anchor read view must normalize real IR-side XDATA and
    extension-dictionary shapes without any AutoCAD dependency.
  * These tests pin the exact fixture shapes the IR builder already emits:
    entity.xdata blocks, entity.extension_dictionary_handle references, the
    top-level extension_dictionaries section, and top-level xrecords.
"""
from __future__ import annotations

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import semantic_anchor  # noqa: E402


def _fixture_ir():
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "extension_dictionaries": [
            {
                "owner_handle": "2B0",
                "dictionary_handle": "ED1",
                "entries": [{"key": "ARIADNE_META", "value_handle": "XR1"}],
            }
        ],
        "xrecords": [
            {
                "handle": "XR1",
                "owner_handle": "ED1",
                "key": "ARIADNE_META",
                "item_count": 4,
                "items": [
                    {"code": 300, "value": "topic"},
                    {"code": 1, "value": "door"},
                    {"code": 300, "value": "score"},
                    {"code": 90, "value": 0.98},
                ],
            }
        ],
        "entities": [
            {
                "handle": "2A7",
                "xdata": [
                    {
                        "app": "ARIADNE_TAGS",
                        "items": [
                            {"code": 1000, "value": "topic"},
                            {"code": 1000, "value": "window"},
                            {"code": 1000, "value": "floor"},
                            {"code": 1070, "value": 3},
                        ],
                    },
                    {
                        "app": "RAW_TRACE",
                        "items": [
                            {"code": 1000, "value": "alpha"},
                            {"code": 1040, "value": 1.25},
                            {"code": 1070, "value": 7},
                        ],
                    },
                ],
            },
            {
                "handle": "2B0",
                "extension_dictionary_handle": "ED1",
            },
            {
                "handle": "2C9",
            },
        ],
    }


def test_read_semantic_anchors_normalizes_xdata_and_extension_dictionary():
    out = semantic_anchor.read_semantic_anchors(_fixture_ir())

    assert out["ok"] is True
    assert out["anchors"] == {
        "2A7": {
            "ARIADNE_TAGS": {"topic": "window", "floor": 3},
            "RAW_TRACE": ["alpha", 1.25, 7],
        },
        "2B0": {
            "ARIADNE_META": {"topic": "door", "score": 0.98},
        },
    }
    assert out["appids_seen"] == ["ARIADNE_TAGS", "RAW_TRACE", "ARIADNE_META"]
    assert out["summary"] == {"entities_with_anchors": 2, "total_anchors": 3}


def test_read_semantic_anchors_accepts_single_entity_dict():
    entity = _fixture_ir()["entities"][0]

    out = semantic_anchor.read_semantic_anchors(entity)

    assert out["ok"] is True
    assert out["anchors"] == {
        "2A7": {
            "ARIADNE_TAGS": {"topic": "window", "floor": 3},
            "RAW_TRACE": ["alpha", 1.25, 7],
        }
    }
    assert out["appids_seen"] == ["ARIADNE_TAGS", "RAW_TRACE"]
    assert out["summary"] == {"entities_with_anchors": 1, "total_anchors": 2}


def test_read_semantic_anchors_empty_but_ok_when_no_anchors_present():
    out = semantic_anchor.read_semantic_anchors({"entities": [{"handle": "9F1"}]})

    assert out["ok"] is True
    assert out["anchors"] == {}
    assert out["appids_seen"] == []
    assert out["summary"] == {"entities_with_anchors": 0, "total_anchors": 0}
