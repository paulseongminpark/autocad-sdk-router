#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import entity_identity  # type: ignore


def _entity(handle: str, geometry: dict, bbox=None, xdata=None, extension_dictionary_handle=None):
    return {
        "handle": handle,
        "dxf_name": "LINE",
        "layer": "0",
        "geometry": geometry,
        "bbox": bbox or [0, 0, 0, 1, 1, 0],
        **({"xdata": xdata} if xdata is not None else {}),
        **({"extension_dictionary_handle": extension_dictionary_handle} if extension_dictionary_handle else {}),
    }


class TestEntityIdentityKey(unittest.TestCase):
    def test_key_is_deterministic(self):
        entity = {
            "handle": "1A2",
            "dxf_name": "LINE",
            "layer": "0",
            "geometry": {"kind": "line", "start": {"x": 1, "y": 2, "z": 0}, "end": {"x": 2, "y": 2, "z": 0}},
            "bbox": [1, 1, 0, 2, 2, 0],
            "extension_dictionary_handle": "ED100",
            "xdata": [{"app": "ARIADNE_ANCHOR", "items": [{"code": 1000, "value": "v1"}]}],
        }

        self.assertEqual(
            entity_identity.entity_identity_key(entity),
            entity_identity.entity_identity_key(dict(entity)),
        )


class TestVerifyIdentityStability(unittest.TestCase):
    def test_buckets_stable_drifted_added_removed(self):
        before = [
            _entity(
                "AA",
                {"kind": "line", "start": {"x": 0, "y": 0, "z": 0}, "end": {"x": 10, "y": 0, "z": 0}},
                bbox=[0, 0, 0, 10, 0, 0],
            ),
            _entity(
                "BB",
                {"kind": "line", "start": {"x": 0, "y": 0, "z": 0}, "end": {"x": 5, "y": 0, "z": 0}},
                bbox=[0, 0, 0, 5, 0, 0],
            ),
            _entity("CC", {"kind": "point", "position": {"x": 1, "y": 1, "z": 0}}, bbox=[1, 1, 0, 1, 1, 0]),
        ]

        after = [
            _entity(
                "AA",
                {"kind": "line", "start": {"x": 0, "y": 0, "z": 0}, "end": {"x": 10, "y": 0, "z": 0}},
                bbox=[0, 0, 0, 10, 0, 0],
            ),
            _entity(
                "BB",
                {"kind": "line", "start": {"x": 0, "y": 0, "z": 0}, "end": {"x": 8, "y": 0, "z": 0}},
                bbox=[0, 0, 0, 8, 0, 0],
            ),
            _entity("DD", {"kind": "arc", "center": {"x": 2, "y": 2, "z": 0}, "radius": 3}, bbox=[0, 0, 0, 3, 3, 0]),
        ]

        result = entity_identity.verify_identity_stability(before, after)

        stable_key = entity_identity.entity_identity_key(before[0])
        drifted_key = entity_identity.entity_identity_key(before[1])

        self.assertFalse(result["ok"])
        self.assertEqual(result["stable"], [stable_key])
        self.assertEqual(result["drifted"], [{"key": drifted_key, "before": before[1], "after": after[1]}])
        self.assertEqual(result["added"], [entity_identity.entity_identity_key(after[2])])
        self.assertEqual(result["removed"], [entity_identity.entity_identity_key(before[2])])
        self.assertEqual(result["summary"], {
            "stable_n": 1,
            "drifted_n": 1,
            "added_n": 1,
            "removed_n": 1,
        })
