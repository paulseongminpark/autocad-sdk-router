#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_engine stale-supported-op-list TEST -- registry lockstep for apply_staged.

Intent (WHY):
  * patch_engine.apply_staged used to trust patch_ops.NATIVE_WRITE_OP_MAP as a
    hand-maintained supported-op allow-list. As config/operations.v2.json grew
    across waves, that list could drift: refuse ops the registry marks live, or
    trust entries the registry no longer implements. A silent drift here is worse
    than refusing to apply -- it is a fake-success / false-refusal hazard on the
    ONLY sanctioned staged-write path.
  * The fix derives the supported native-op truth from registry rows
    (status==implemented AND handler.router_lane==ARIADNE_NATIVE_JOB) and fails
    LOUDLY when patch_ops cites a dangling or non-live target. These tests are
    the tripwire so that drift cannot recur without breaking CI.

Discoverable by pytest and ``python -m unittest discover -s tests``. Stdlib only.
BOM-tolerant registry reads (utf-8-sig), matching tools/patch_engine.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_OPERATIONS_V2 = os.path.join(_REPO, "config", "operations.v2.json")
_JSON_ENCODING = "utf-8-sig"
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PATCH_SCHEMA_ID = "ariadne.cad_patch.v1"


def _load_registry_rows():
    with open(_OPERATIONS_V2, "r", encoding=_JSON_ENCODING) as fh:
        doc = json.load(fh)
    return doc.get("operations", [])


def _registry_native_job_implemented_ids():
    """Independent oracle: same row filter patch_engine uses (not imported)."""
    ids = set()
    for op in _load_registry_rows():
        if not isinstance(op, dict):
            continue
        oid = op.get("id")
        if not oid:
            continue
        handler = op.get("handler") or {}
        if (handler.get("router_lane") == "ARIADNE_NATIVE_JOB"
                and op.get("status") == "implemented"):
            ids.add(oid)
    return ids


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _good_patch(staged, original):
    return {
        "schema": PATCH_SCHEMA_ID,
        "patch_id": "stale-ops-test-0001",
        "target_dwg": {"staged_path": staged, "original_path": original},
        "operations": [
            {"step_id": "s1", "operation": "create_line",
             "args": {"start": [0, 0, 0], "end": [10, 0, 0], "layer": "0"}},
        ],
        "postconditions": [{"subject": "entity_count", "op": "delta_eq", "value": 1}],
        "policy": {"staged_copy": True, "write_mode": "write_copy"},
    }


class TestNativeWriteOpMapRegistryLockstep(unittest.TestCase):
    def setUp(self):
        import patch_engine
        self.pe = patch_engine

    def test_supported_native_targets_match_live_registry(self):
        """FAIL if patch_ops map drifts from config/operations.v2.json again."""
        live_native = _registry_native_job_implemented_ids()
        by_id = {o.get("id"): o for o in _load_registry_rows() if o.get("id")}
        stale = []
        for patch_op, native_op in sorted(self.pe.NATIVE_WRITE_OP_MAP.items()):
            rec = by_id.get(native_op)
            if rec is None:
                stale.append("%r -> %r (dangling)" % (patch_op, native_op))
            elif native_op not in live_native:
                handler = rec.get("handler") or {}
                stale.append(
                    "%r -> %r (status=%r router_lane=%r)"
                    % (patch_op, native_op, rec.get("status"),
                       handler.get("router_lane")))
        self.assertEqual(stale, [],
                         "NATIVE_WRITE_OP_MAP drifts from live registry:\n  "
                         + "\n  ".join(stale))

    def test_assert_lockstep_matches_registry_helper(self):
        live = self.pe.registry_native_job_implemented_op_ids()
        self.pe.assert_native_write_op_map_lockstep()
        for native_op in self.pe.NATIVE_WRITE_OP_MAP.values():
            self.assertIn(native_op, live)

    def test_lockstep_raises_on_synthetic_stale_map(self):
        with self.assertRaises(self.pe.PatchEngineRegistryError) as ctx:
            self.pe.assert_native_write_op_map_lockstep(
                {"fake_patch_op": "definitely.not.a.registry.op.id"})
        self.assertIn("dangling", str(ctx.exception).lower())


class TestApplyStagedUnknownOpRefusal(unittest.TestCase):
    def setUp(self):
        import patch_engine
        self.pe = patch_engine

    def test_resolve_refuses_unknown_patch_operation(self):
        patch = _good_patch("a/staged.dwg", "b/orig.dwg")
        patch["operations"] = [{"operation": "not_a_real_patch_op_xyz", "args": {}}]
        rec, err = self.pe._resolve_native_write_op(patch)
        self.assertIsNone(rec)
        self.assertIsNotNone(err)
        self.assertIn("unknown patch operation", err)

    def test_apply_staged_not_implemented_for_unknown_patch_op(self):
        with tempfile.TemporaryDirectory(prefix="patch_unknown_") as tmp:
            original = os.path.join(tmp, "orig.dwg")
            with open(original, "wb") as fh:
                fh.write(b"FAKE-DWG-BYTES")
            sha_before = _sha256(original)
            out_dir = os.path.join(tmp, "run")
            patch = _good_patch(os.path.join(out_dir, "staged_input.dwg"), original)
            patch["operations"] = [{"operation": "not_a_real_patch_op_xyz",
                                    "args": {}}]
            res = self.pe.apply_staged(patch, original, out_dir)
            self.assertEqual(res["status"], "not_implemented")
            self.assertIn("unknown patch operation", res.get("reason", ""))
            self.assertEqual(_sha256(original), sha_before,
                             "original DWG touched on unknown-op refusal path")


if __name__ == "__main__":
    unittest.main()
