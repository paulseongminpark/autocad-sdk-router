#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_fragments -- unit tests (offline, temp registry + temp fragment dir only)."""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from merge_fragments import merge_fragments  # noqa: E402


def _base_registry() -> dict:
    return {
        "schema": "test",
        "totals": {
            "operations": 2,
            "by_status": {"implemented": 1, "blocked": 1},
            "by_family": {"alpha": 1, "beta": 1},
            "by_engine_tier": {"tier_a": 1, "tier_b": 1},
        },
        "coverage": {
            "operation_records": 2,
            "implemented": 1,
            "blocked": 1,
            "wired_ops": 99,
        },
        "operations": [
            {
                "id": "existing.one",
                "family": "alpha",
                "status": "implemented",
                "engine_tier": "tier_a",
            },
            {
                "id": "existing.two",
                "family": "beta",
                "status": "blocked",
                "engine_tier": "tier_b",
            },
        ],
    }


class MergeFragmentsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

        self.registry_path = self.tmp_path / "operations.v2.json"
        with self.registry_path.open("w", encoding="utf-8") as f:
            json.dump(_base_registry(), f, indent=2, ensure_ascii=False)
            f.write("\n")

        self.fragments_dir = self.tmp_path / "ops_fragments"
        self.fragments_dir.mkdir()

        # New op -- should be added.
        with (self.fragments_dir / "new_op.json").open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "id": "new.op",
                    "family": "gamma",
                    "status": "implemented",
                    "engine_tier": "tier_a",
                },
                f,
            )

        # Duplicate id (already in registry) -- should be skipped.
        with (self.fragments_dir / "dup_op.json").open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "id": "existing.one",
                    "family": "alpha",
                    "status": "implemented",
                    "engine_tier": "tier_a",
                },
                f,
            )

    def _load_registry(self) -> dict:
        with self.registry_path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)

    def test_dry_run_computes_without_writing(self) -> None:
        before_bytes = self.registry_path.read_bytes()

        result = merge_fragments(self.registry_path, self.fragments_dir, dry_run=True)

        self.assertEqual(result["added"], ["new.op"])
        self.assertEqual(result["skipped"], ["existing.one"])
        self.assertEqual(result["total_ops"], 3)
        self.assertEqual(result["by_status"], {"implemented": 2, "blocked": 1})

        # dry_run must not touch the file on disk at all.
        self.assertEqual(self.registry_path.read_bytes(), before_bytes)

    def test_merge_adds_new_skips_duplicate_and_recomputes_totals(self) -> None:
        result = merge_fragments(self.registry_path, self.fragments_dir, dry_run=False)

        self.assertEqual(result["added"], ["new.op"])
        self.assertEqual(result["skipped"], ["existing.one"])
        self.assertEqual(result["total_ops"], 3)
        self.assertEqual(result["by_status"], {"implemented": 2, "blocked": 1})

        registry = self._load_registry()
        ids = [op["id"] for op in registry["operations"]]
        self.assertEqual(ids, ["existing.one", "existing.two", "new.op"])

        totals = registry["totals"]
        self.assertEqual(totals["operations"], 3)
        self.assertEqual(totals["by_status"], {"implemented": 2, "blocked": 1})
        self.assertEqual(totals["by_family"], {"alpha": 1, "beta": 1, "gamma": 1})
        self.assertEqual(totals["by_engine_tier"], {"tier_a": 2, "tier_b": 1})

        coverage = registry["coverage"]
        self.assertEqual(coverage["operation_records"], 3)
        self.assertEqual(coverage["implemented"], 2)
        self.assertEqual(coverage["blocked"], 1)
        # Fields outside the recompute set must be left untouched.
        self.assertEqual(coverage["wired_ops"], 99)

        # No BOM, ensure_ascii=False, trailing newline.
        raw = self.registry_path.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        self.assertTrue(raw.endswith(b"\n"))

    def test_idempotent_on_second_run(self) -> None:
        first = merge_fragments(self.registry_path, self.fragments_dir, dry_run=False)
        after_first = self.registry_path.read_bytes()

        second = merge_fragments(self.registry_path, self.fragments_dir, dry_run=False)
        after_second = self.registry_path.read_bytes()

        self.assertEqual(second["added"], [])
        self.assertEqual(sorted(second["skipped"]), ["existing.one", "new.op"])
        self.assertEqual(second["total_ops"], first["total_ops"])
        self.assertEqual(second["by_status"], first["by_status"])
        self.assertEqual(after_first, after_second)

        registry = self._load_registry()
        ids = [op["id"] for op in registry["operations"]]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
