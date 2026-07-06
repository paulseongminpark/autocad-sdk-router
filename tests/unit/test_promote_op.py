#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CADOS WAVE-0 F2 TEST -- promote_op.py: the promotion harness.

Intent (WHY): PLAN.md PART 2 sec 2.0 legislates every write node against
THREE promotion axes, satisfied atomically. The one hard invariant a
promotion harness can silently violate is RT-FOLD H-R4: a WRITE_OP_MAP entry
with no matching build_job_args arg-branch (or vice versa) -- Python code
that LOOKS wired but silently defaults to empty/wrong args on a real call.
The second hard invariant is the Axis-A gate itself: a promotion must be
REFUSED (never partially applied) unless F1's OWN live classification of
native_op is exactly RUNNABLE -- RUNNABLE_BUT_DEGENERATE (an input-
unvalidated fake success) or an unprobed op must never slip through.

These tests exercise both invariants against SYNTHETIC family modules /
registry / F1-matrix fixtures (tmp_path) -- never the real repo files, so no
tracked source is ever mutated by a test run -- plus a read-only regression
pass against the REAL config/promotion_manifest.json (compute_promotion never
writes, so this is safe).

Discoverable by pytest. Stdlib only (uses pytest fixtures for tmp_path).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
import promote_op as po  # noqa: E402
import probe_reachability as pr  # noqa: E402

_REAL_MANIFEST = _ROOT / "config" / "promotion_manifest.json"
_REAL_OPERATIONS_V2 = _ROOT / "config" / "operations.v2.json"


# --------------------------------------------------------------------------- #
# Fixture builders -- synthetic, self-contained, mirror the real F9 contract
# --------------------------------------------------------------------------- #
def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


_EMPTY_FAMILY_MODULE = '''\
"""synthetic empty family module (mirrors patch_ops.blocks/db contract)."""
from __future__ import annotations

from typing import Any, Dict, Optional

WRITE_OP_MAP: Dict[str, str] = {}


def build_job_args(native_op: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """No native op is wired yet; always None (not our native_op)."""
    return None
'''

_POPULATED_FAMILY_MODULE = '''\
"""synthetic populated family module (mirrors patch_ops.entities contract)."""
from __future__ import annotations

from typing import Any, Dict, Optional

WRITE_OP_MAP: Dict[str, str] = {
    "create_widget": "write.entity.widget",
}


def build_job_args(native_op: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Native job "args" for an entity write op, or None if native_op isn't ours."""
    if native_op == "write.entity.widget":
        out: Dict[str, Any] = {}
        for k in ("size", "layer"):
            if k in args:
                out[k] = args[k]
        return out
    return None
'''

_MISMAPPED_FAMILY_MODULE = '''\
"""synthetic family module with a BAD map write: WRITE_OP_MAP points
create_widget at the WRONG native_op even though build_job_args has a fully
coherent arg branch for the correct one. An arg-branch-only guard cannot
see this defect at all -- it only shows up by cross-checking the map."""
from __future__ import annotations

from typing import Any, Dict, Optional

WRITE_OP_MAP: Dict[str, str] = {
    "create_widget": "write.entity.OTHER",
}


def build_job_args(native_op: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Coherent arg branch for write.entity.widget -- but WRITE_OP_MAP above
    never actually routes create_widget to it."""
    if native_op == "write.entity.widget":
        out: Dict[str, Any] = {}
        for k in ("size", "layer"):
            if k in args:
                out[k] = args[k]
        return out
    return None
'''


def _op_record(op_id: str, status_policy: str = "catalogued_not_runnable") -> dict:
    rec = {"id": op_id, "status": "implemented",
           "policy": {"source": "config/policy.v2.json", "status_policy": status_policy,
                      "default_write_mode": "write_copy", "no_original_write_default": True},
           "evidence_refs": ["config/autocad_native_arx_operation_catalog.json#%s" % op_id]}
    if status_policy != "implemented":
        rec["policy"]["runtime_behavior"] = "not_runnable_until_promoted_to_implemented_or_wired"
    return rec


def _write_operations_v2(path: Path, ops: list) -> None:
    _write(path, json.dumps({"operations": ops}, indent=2))


def _write_matrix(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _matrix_row(op_id: str, cls: str) -> dict:
    return {"schema": pr.MATRIX_SCHEMA, "op_id": op_id, "class": cls}


@pytest.fixture
def env(tmp_path: Path):
    """A disposable {family module, operations.v2.json} tree + a synthetic F1
    matrix, fully isolated from the real repo."""
    fam_dir = tmp_path / "patch_ops"
    empty_path = fam_dir / "empty_family.py"
    populated_path = fam_dir / "populated_family.py"
    _write(empty_path, _EMPTY_FAMILY_MODULE)
    _write(populated_path, _POPULATED_FAMILY_MODULE)

    ops_v2_path = tmp_path / "operations.v2.json"
    _write_operations_v2(ops_v2_path, [
        _op_record("write.entity.gizmo", status_policy="catalogued_not_runnable"),
        _op_record("write.entity.widget", status_policy="implemented"),
        _op_record("write.entity.degenerate_thing", status_policy="catalogued_not_runnable"),
        _op_record("write.entity.unprobed_thing", status_policy="catalogued_not_runnable"),
    ])

    matrix_path = tmp_path / "reachable_matrix.jsonl"
    _write_matrix(matrix_path, [
        _matrix_row("write.entity.gizmo", pr.RUNNABLE),
        _matrix_row("write.entity.degenerate_thing", pr.RUNNABLE_BUT_DEGENERATE),
        # write.entity.unprobed_thing deliberately absent -- never probed.
    ])

    family_files = {"empty": str(empty_path), "populated": str(populated_path)}
    return {
        "family_files": family_files,
        "empty_path": empty_path,
        "populated_path": populated_path,
        "ops_v2_path": ops_v2_path,
        "matrix_path": matrix_path,
        "matrix": po.load_f1_matrix(str(matrix_path)),
    }


def _row(patch_op, native_op, arg_keys, family, ir_kind=None,
         persistence_class="P", risk="low") -> dict:
    return {"patch_op": patch_op, "native_op": native_op, "arg_keys": arg_keys,
            "ir_kind": ir_kind, "persistence_class": persistence_class, "risk": risk,
            "family": family}


# --------------------------------------------------------------------------- #
# f1_gate -- the Axis-A gate, in isolation
# --------------------------------------------------------------------------- #
class TestF1Gate:
    def test_runnable_opens_the_gate(self, env):
        allowed, reason, cls = po.f1_gate("write.entity.gizmo", matrix=env["matrix"])
        assert allowed is True
        assert cls == pr.RUNNABLE
        assert reason == ""

    def test_degenerate_never_opens_the_gate(self, env):
        allowed, reason, cls = po.f1_gate("write.entity.degenerate_thing", matrix=env["matrix"])
        assert allowed is False
        assert cls == pr.RUNNABLE_BUT_DEGENERATE
        assert "not RUNNABLE" in reason

    def test_unprobed_op_never_opens_the_gate(self, env):
        allowed, reason, cls = po.f1_gate("write.entity.unprobed_thing", matrix=env["matrix"])
        assert allowed is False
        assert cls is None
        assert "has not probed" in reason

    def test_other_f1_classes_never_open_the_gate(self, env):
        for cls in (pr.REACHABLE, pr.OPERATION_NOT_IMPLEMENTED, pr.BLOCKED_BY_POLICY,
                    pr.CRASH, pr.ATTENDED_ONLY):
            matrix = {"write.entity.x": {"op_id": "write.entity.x", "class": cls}}
            allowed, _reason, got_cls = po.f1_gate("write.entity.x", matrix=matrix)
            assert allowed is False
            assert got_cls == cls


# --------------------------------------------------------------------------- #
# infer_family
# --------------------------------------------------------------------------- #
class TestInferFamily:
    def test_entity_prefix(self):
        assert po.infer_family("write.entity.line") == "entities"

    def test_block_prefix(self):
        assert po.infer_family("write.block.simple_create") == "blocks"

    def test_layer_prefix_is_tables(self):
        assert po.infer_family("write.layer.create") == "tables"

    def test_unmatched_prefix_falls_back_to_db(self):
        assert po.infer_family("write.xdata.set") == "db"
        assert po.infer_family("write.layout.create") == "db"


# --------------------------------------------------------------------------- #
# compute_promotion / apply_promotion -- the accept criteria's two halves
# --------------------------------------------------------------------------- #
class TestPromoteSyntheticRunnableOp:
    """PLAN.md F2 accept (half 1): promoting a synthetic op writes the exact
    3-axis diff and is reversible."""

    def test_compute_promotion_is_pure_and_reports_the_3_axis_diff(self, env):
        row = _row("create_gizmo", "write.entity.gizmo", ["size", "layer"], "empty")
        before_fam = env["empty_path"].read_text(encoding="utf-8")
        before_ops = env["ops_v2_path"].read_text(encoding="utf-8")

        result = po.compute_promotion(row, matrix=env["matrix"],
                                       operations_v2_path=str(env["ops_v2_path"]),
                                       family_files=env["family_files"])

        assert result.status == po.PROMOTED
        assert result.diff["axis_a"]["changed"] is True
        assert result.diff["axis_a"]["before"]["status_policy"] == "catalogued_not_runnable"
        assert result.diff["axis_a"]["after"]["status_policy"] == "implemented"
        assert result.diff["axis_b_map"]["changed"] is True
        assert result.diff["axis_b_map"]["entry"] == {"create_gizmo": "write.entity.gizmo"}
        assert result.diff["axis_b_args"]["changed"] is True
        assert result.diff["axis_b_args"]["arg_keys"] == ["size", "layer"]
        assert result.diff["axis_c"]["changed"] is False
        # PURE: no file was touched by compute_promotion.
        assert env["empty_path"].read_text(encoding="utf-8") == before_fam
        assert env["ops_v2_path"].read_text(encoding="utf-8") == before_ops

    def test_apply_promotion_writes_map_entry_and_arg_branch_together(self, env):
        row = _row("create_gizmo", "write.entity.gizmo", ["size", "layer"], "empty")
        result = po.apply_promotion(row, matrix=env["matrix"],
                                     operations_v2_path=str(env["ops_v2_path"]),
                                     family_files=env["family_files"])
        assert result.status == po.PROMOTED

        # Axis B: re-import the family module FRESH and prove it is
        # behaviorally coherent, not just textually patched.
        import importlib.util
        spec = importlib.util.spec_from_file_location("_t_empty_family", env["empty_path"])
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.WRITE_OP_MAP["create_gizmo"] == "write.entity.gizmo"
        got_args = mod.build_job_args("write.entity.gizmo", {"size": 3, "layer": "0", "extra": 1})
        assert got_args == {"size": 3, "layer": "0"}

        # Axis A: operations.v2.json flipped + evidence_ref merged.
        doc = json.loads(env["ops_v2_path"].read_text(encoding="utf-8-sig"))
        rec = next(o for o in doc["operations"] if o["id"] == "write.entity.gizmo")
        assert rec["policy"]["status_policy"] == "implemented"
        assert "measure/reachable_matrix.jsonl#write.entity.gizmo" in rec["evidence_refs"]
        assert "runtime_behavior" not in rec["policy"]

    def test_apply_promotion_reverts_if_map_write_resolves_to_the_wrong_native_op(self, env, monkeypatch):
        """End-to-end regression for the map half of the H-R4 guard: simulate
        a hypothetical _insert_map_entry defect that writes the WRONG
        native_op into WRITE_OP_MAP. The arg branch inserted alongside it is
        still perfectly coherent for the REAL native_op -- an arg-branch-only
        guard (the pre-fix behavior) would have accepted this promotion.
        apply_promotion must instead raise and revert BOTH files."""
        row = _row("create_gizmo", "write.entity.gizmo", ["size", "layer"], "empty")
        before_fam = env["empty_path"].read_text(encoding="utf-8")
        before_ops = env["ops_v2_path"].read_text(encoding="utf-8")

        real_insert = po._insert_map_entry

        def _bad_insert(text, patch_op, native_op):
            return real_insert(text, patch_op, native_op + "_WRONG")

        monkeypatch.setattr(po, "_insert_map_entry", _bad_insert)

        with pytest.raises(po.PromotionError, match="WRITE_OP_MAP"):
            po.apply_promotion(row, matrix=env["matrix"], operations_v2_path=str(env["ops_v2_path"]),
                                family_files=env["family_files"])

        # All-or-nothing (RT-FOLD H-R4): both files reverted to pre-promotion bytes.
        assert env["empty_path"].read_text(encoding="utf-8") == before_fam
        assert env["ops_v2_path"].read_text(encoding="utf-8") == before_ops

    def test_apply_promotion_is_reversible(self, env):
        row = _row("create_gizmo", "write.entity.gizmo", ["size", "layer"], "empty")
        before_fam = env["empty_path"].read_text(encoding="utf-8")
        before_ops = env["ops_v2_path"].read_text(encoding="utf-8")

        result = po.apply_promotion(row, matrix=env["matrix"],
                                     operations_v2_path=str(env["ops_v2_path"]),
                                     family_files=env["family_files"])
        assert env["empty_path"].read_text(encoding="utf-8") != before_fam

        po.revert_promotion(result)

        assert env["empty_path"].read_text(encoding="utf-8") == before_fam
        assert env["ops_v2_path"].read_text(encoding="utf-8") == before_ops

    def test_reapplying_after_apply_reports_already_promoted_and_is_idempotent(self, env):
        row = _row("create_gizmo", "write.entity.gizmo", ["size", "layer"], "empty")
        po.apply_promotion(row, matrix=env["matrix"], operations_v2_path=str(env["ops_v2_path"]),
                            family_files=env["family_files"])
        after_first_apply = env["empty_path"].read_text(encoding="utf-8")

        result2 = po.apply_promotion(row, matrix=env["matrix"], operations_v2_path=str(env["ops_v2_path"]),
                                      family_files=env["family_files"])

        assert result2.status == po.ALREADY_PROMOTED
        assert env["empty_path"].read_text(encoding="utf-8") == after_first_apply  # no double-insert


class TestRejectF1NotRunnableOrDegenerate:
    """PLAN.md F2 accept (half 2): promoting an F1-NOT-RUNNABLE or DEGENERATE
    op is REJECTED -- and REJECTED means atomic: no axis is touched at all."""

    def test_degenerate_native_op_is_rejected_and_writes_nothing(self, env):
        row = _row("create_degenerate", "write.entity.degenerate_thing", ["x"], "empty")
        before_fam = env["empty_path"].read_text(encoding="utf-8")
        before_ops = env["ops_v2_path"].read_text(encoding="utf-8")

        result = po.apply_promotion(row, matrix=env["matrix"], operations_v2_path=str(env["ops_v2_path"]),
                                     family_files=env["family_files"])

        assert result.status == po.REJECTED
        assert result.f1_class == pr.RUNNABLE_BUT_DEGENERATE
        assert "RUNNABLE_BUT_DEGENERATE" in result.reason or "not RUNNABLE" in result.reason
        assert result.diff == {}
        assert env["empty_path"].read_text(encoding="utf-8") == before_fam
        assert env["ops_v2_path"].read_text(encoding="utf-8") == before_ops

    def test_unprobed_native_op_is_rejected_and_writes_nothing(self, env):
        row = _row("create_unprobed", "write.entity.unprobed_thing", ["x"], "empty")
        before_fam = env["empty_path"].read_text(encoding="utf-8")

        result = po.apply_promotion(row, matrix=env["matrix"], operations_v2_path=str(env["ops_v2_path"]),
                                     family_files=env["family_files"])

        assert result.status == po.REJECTED
        assert result.f1_class is None
        assert env["empty_path"].read_text(encoding="utf-8") == before_fam

    def test_compute_promotion_rejection_is_pure_too(self, env):
        row = _row("create_degenerate", "write.entity.degenerate_thing", ["x"], "empty")
        result = po.compute_promotion(row, matrix=env["matrix"], operations_v2_path=str(env["ops_v2_path"]),
                                       family_files=env["family_files"])
        assert result.status == po.REJECTED
        assert result._pending is None


class TestConflict:
    def test_patch_op_mapped_to_a_different_native_op_is_a_conflict(self, env):
        # populated_family.py already maps create_widget -> write.entity.OTHER
        # (hand-edited below); ask promote_op to point the SAME patch_op at a
        # DIFFERENT native_op (write.entity.widget, which the matrix marks
        # RUNNABLE) -- the map-entry collision must win as CONFLICT, not a
        # silent overwrite.
        conflicting_path = env["populated_path"]
        text = conflicting_path.read_text(encoding="utf-8")
        text = text.replace('"write.entity.widget"', '"write.entity.OTHER"', 1)
        conflicting_path.write_text(text, encoding="utf-8")

        matrix = {"write.entity.widget": {"op_id": "write.entity.widget", "class": pr.RUNNABLE}}
        row = _row("create_widget", "write.entity.widget", ["size"], "populated")

        result = po.apply_promotion(row, matrix=matrix, operations_v2_path=str(env["ops_v2_path"]),
                                     family_files=env["family_files"])

        assert result.status == po.CONFLICT
        assert "already mapped to" in result.reason


class TestAlreadyPromotedRealControlRows:
    """create_line/create_circle are F9-merged control rows exercised
    against the REAL repo files (read-only -- compute_promotion never
    writes), proving the manifest's declared state matches production."""

    def test_create_line_is_already_promoted_in_the_real_repo(self):
        rows = po.load_manifest(str(_REAL_MANIFEST))
        row = next(r for r in rows if r["patch_op"] == "create_line")
        matrix = po.load_f1_matrix()
        before = _REAL_OPERATIONS_V2.read_text(encoding="utf-8-sig")

        result = po.compute_promotion(row, matrix=matrix)

        assert result.status == po.ALREADY_PROMOTED
        assert result.f1_class == pr.RUNNABLE
        assert _REAL_OPERATIONS_V2.read_text(encoding="utf-8-sig") == before  # untouched


class TestRealManifestPendingRowsNowLiveProbed:
    """The 4 real Tier-1 candidate rows (T1.1/T1.3/T1.4/T1.5) were honestly
    unprobed (=> REJECTED) until the 2026-07-06 full 465-op live sweep
    (sweep_watchdog.ps1 -> measure/reachable_matrix.jsonl, every row
    classification_source=live_probe). Their native ops now carry real
    RUNNABLE evidence, so compute_promotion must compute a promotion --
    while STILL never writing to the real repo (the anti-fabrication
    intent lives on as: promotion requires live RUNNABLE evidence, and
    compute_promotion is pure)."""

    @pytest.mark.parametrize("patch_op", [
        "create_block_def", "create_layout", "set_xdata", "set_xrecord",
    ])
    def test_live_probed_row_promotes_against_real_registry(self, patch_op):
        rows = po.load_manifest(str(_REAL_MANIFEST))
        row = next(r for r in rows if r["patch_op"] == patch_op)
        matrix = po.load_f1_matrix()
        before = _REAL_OPERATIONS_V2.read_text(encoding="utf-8-sig")

        result = po.compute_promotion(row, matrix=matrix)

        assert result.status in (po.PROMOTED, po.ALREADY_PROMOTED)
        assert result.f1_class == pr.RUNNABLE
        assert _REAL_OPERATIONS_V2.read_text(encoding="utf-8-sig") == before


# --------------------------------------------------------------------------- #
# Manifest loading / validation
# --------------------------------------------------------------------------- #
class TestLoadManifest:
    def test_real_manifest_loads_and_validates(self):
        rows = po.load_manifest(str(_REAL_MANIFEST))
        assert len(rows) >= 6
        patch_ops = {r["patch_op"] for r in rows}
        assert {"create_line", "create_circle", "create_block_def",
                "create_layout", "set_xdata", "set_xrecord"} <= patch_ops

    def test_row_missing_required_field_raises(self, tmp_path):
        bad = tmp_path / "bad_manifest.json"
        bad.write_text(json.dumps({"rows": [
            {"patch_op": "x", "native_op": "write.entity.x", "arg_keys": []},
        ]}), encoding="utf-8")
        with pytest.raises(ValueError, match="missing required field"):
            po.load_manifest(str(bad))

    def test_row_invalid_persistence_class_raises(self, tmp_path):
        bad = tmp_path / "bad_manifest2.json"
        bad.write_text(json.dumps({"rows": [
            {"patch_op": "x", "native_op": "write.entity.x", "arg_keys": [],
             "ir_kind": None, "persistence_class": "Z", "risk": "low"},
        ]}), encoding="utf-8")
        with pytest.raises(ValueError, match="persistence_class"):
            po.load_manifest(str(bad))


# --------------------------------------------------------------------------- #
# load_f1_matrix
# --------------------------------------------------------------------------- #
class TestLoadF1Matrix:
    def test_missing_file_returns_empty_dict_not_an_error(self, tmp_path):
        assert po.load_f1_matrix(str(tmp_path / "does_not_exist.jsonl")) == {}

    def test_last_row_wins_for_a_reprobed_op(self, tmp_path):
        path = tmp_path / "m.jsonl"
        _write_matrix(path, [
            _matrix_row("write.entity.x", pr.RUNNABLE_BUT_DEGENERATE),
            _matrix_row("write.entity.x", pr.RUNNABLE),
        ])
        matrix = po.load_f1_matrix(str(path))
        assert matrix["write.entity.x"]["class"] == pr.RUNNABLE


# --------------------------------------------------------------------------- #
# H-R4 unknown-op guard, exercised directly
# --------------------------------------------------------------------------- #
class TestUnknownOpGuard:
    """_verify_axis_b is a TWO-sided guard: the map half (WRITE_OP_MAP[patch_op]
    == native_op) and the arg-branch half (build_job_args(native_op, ...) is
    non-None and arg_keys-shaped). Either half failing alone must raise --
    a coherent arg branch for the right native_op can never paper over a
    WRITE_OP_MAP entry that resolves to the wrong (or no) native_op, and
    vice versa."""

    def test_verify_axis_b_raises_if_arg_branch_is_missing(self, tmp_path):
        # A family module with a map entry but NO matching arg-branch --
        # the exact H-R4 defect this tool must never itself produce, but
        # _verify_axis_b must still catch it if it somehow occurred.
        broken = tmp_path / "broken_family.py"
        _write(broken, _EMPTY_FAMILY_MODULE.replace(
            "WRITE_OP_MAP: Dict[str, str] = {}",
            'WRITE_OP_MAP: Dict[str, str] = {\n    "create_orphan": "write.entity.orphan",\n}'))
        with pytest.raises(po.PromotionError, match="unknown-op guard"):
            po._verify_axis_b(str(broken), "create_orphan", "write.entity.orphan", ["x"])

    def test_verify_axis_b_passes_for_a_coherent_branch(self, tmp_path):
        ok = tmp_path / "ok_family.py"
        _write(ok, _POPULATED_FAMILY_MODULE)
        po._verify_axis_b(str(ok), "create_widget", "write.entity.widget", ["size", "layer"])  # no raise

    def test_verify_axis_b_raises_if_map_points_to_the_wrong_native_op(self, tmp_path):
        # build_job_args("write.entity.widget", ...) is perfectly coherent in
        # isolation -- an arg-branch-only guard (the pre-fix behavior) would
        # pass this straight through. But WRITE_OP_MAP["create_widget"]
        # resolves to "write.entity.OTHER", not "write.entity.widget": a bad
        # map write that must fail regardless of how clean the arg branch is.
        mismapped = tmp_path / "mismapped_family.py"
        _write(mismapped, _MISMAPPED_FAMILY_MODULE)
        with pytest.raises(po.PromotionError, match="WRITE_OP_MAP"):
            po._verify_axis_b(str(mismapped), "create_widget", "write.entity.widget", ["size", "layer"])

    def test_verify_axis_b_raises_if_map_entry_is_missing_entirely(self, tmp_path):
        # patch_op isn't in WRITE_OP_MAP at all (mapped is None), even though
        # native_op's own arg branch is coherent -- same defect class as
        # above, the map key just never landed.
        ok = tmp_path / "ok_family.py"
        _write(ok, _POPULATED_FAMILY_MODULE)
        with pytest.raises(po.PromotionError, match="WRITE_OP_MAP"):
            po._verify_axis_b(str(ok), "create_nonexistent", "write.entity.widget", ["size", "layer"])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
