#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline guard for ANNOTATION SCALE native READ family scaffolding."""
from __future__ import annotations

import json
import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "annoscale_read.inc")
_FRAGMENT = os.path.join(_REPO, "reports", "ops_fragments", "nat.annoscale.json")
_OP_IDS = {"inspect.annoscale.list", "inspect.entity.annoscale.contexts"}
_DISPATCHER = "annoscaleReadDispatch"


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def _ops_in_inc(src: str) -> set[str]:
    return set(re.findall(r'op == "([^"]+)"', src))


class TestAnnoscaleInc(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.src = _read_text(_INC)
        cls.hasop_ops = _ops_in_inc(cls.src)

    def test_inc_file_exists(self) -> None:
        self.assertTrue(os.path.exists(_INC), f"missing inc: {_INC}")

    def test_signatures_present(self) -> None:
        self.assertRegex(self.src, r"bool\s+annoscaleReadHasOp\(const std::string& op\)")
        self.assertRegex(
            self.src,
            r"bool\s+annoscaleReadDispatch\(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r\)",
        )

    def test_hasop_declares_exact_ops(self) -> None:
        self.assertEqual(self.hasop_ops, _OP_IDS, "annoscaleReadHasOp op set drifted")

    def test_hasop_dispatch_parity(self) -> None:
        dispatch_ops = _ops_in_inc(self.src.split("annoscaleReadDispatch", 1)[-1])
        self.assertEqual(
            dispatch_ops,
            self.hasop_ops,
            "dispatch branches and HasOp op set do not match: %r" % (self.hasop_ops ^ dispatch_ops),
        )

    def test_dispatch_is_read_only(self) -> None:
        self.assertIn("AcDb::kForRead", self.src, "missing kForRead usage in read family")
        self.assertNotIn("AcDb::kForWrite", self.src, "read family must not use kForWrite")


class TestAnnoscaleFragment(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.src = _read_text(_FRAGMENT)
        cls.fragment = json.loads(cls.src)
        with open(_INC, "r", encoding="utf-8-sig") as f:
            cls.inc_src = f.read()
        cls.inc_ops = _ops_in_inc(cls.inc_src)

    def test_fragment_file_exists(self) -> None:
        self.assertTrue(os.path.exists(_FRAGMENT), f"missing fragment: {_FRAGMENT}")

    def test_fragment_is_array(self) -> None:
        self.assertIsInstance(self.fragment, list, "fragment must be a JSON array")

    def test_fragment_keys_valid(self) -> None:
        required = {"id", "family", "status", "host_eligibility", "write_level", "handler"}
        for entry in self.fragment:
            self.assertIsInstance(entry, dict, "each fragment entry must be an object")
            missing = sorted(required - set(entry))
            self.assertEqual(missing, [], f"{entry.get('id')} missing required keys: {missing}")

            wl = entry.get("write_level", {})
            self.assertEqual(wl.get("default_write_mode"), "read")
            self.assertEqual(wl.get("allowed_write_modes"), ["read"])

            self.assertEqual(
                entry.get("handler", {}).get("router_lane"),
                "ARIADNE_NATIVE_JOB",
                f"{entry.get('id')} must route via ARIADNE_NATIVE_JOB",
            )
            self.assertEqual(
                entry.get("handler", {}).get("dispatcher_symbol"),
                _DISPATCHER,
                f"{entry.get('id')} dispatcher_symbol must be {_DISPATCHER}",
            )

    def test_no_write_original(self) -> None:
        for entry in self.fragment:
            ops = set(entry.get("write_level", {}).get("allowed_write_modes", []))
            self.assertNotIn("write_original", ops, f"{entry.get('id')} must not allow write_original")

    def test_fragment_ops_declared_in_inc(self) -> None:
        fragment_ops = {entry.get("id") for entry in self.fragment if isinstance(entry, dict)}
        self.assertEqual(fragment_ops, _OP_IDS, "fragment IDs must match inc declarations")
        self.assertTrue(fragment_ops.issubset(self.inc_ops), "every fragment op-id must be declared in .inc")


if __name__ == "__main__":
    unittest.main(verbosity=2)
