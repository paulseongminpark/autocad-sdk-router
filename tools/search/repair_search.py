#!/usr/bin/env python3
"""DFS repair search over post-side IR variants with gate-based pruning."""

from __future__ import annotations

import copy
import json
import os
from typing import Any, Callable, Dict, List, Optional


class RepairCandidate:
    """A single repair transformation candidate (ordering hint only via score)."""

    __slots__ = ("id", "description", "apply", "score")

    def __init__(
        self,
        id: str,
        description: str,
        apply: Callable[[Dict[str, Any]], Dict[str, Any]],
        score: float,
    ) -> None:
        self.id = id
        self.description = description
        self.apply = apply
        self.score = score


def default_gate(
    census_ir: Dict[str, Any],
    post_ir: Dict[str, Any],
    target_def: str,
) -> Dict[str, Any]:
    """Thin wrapper around blockdef_diff for a single definition row."""
    import sys

    _tools = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _tools not in sys.path:
        sys.path.insert(0, _tools)

    import blockdef_diff

    report = blockdef_diff.diff_block_definitions(census_ir, post_ir)
    row = next(
        (r for r in report.get("per_def") or [] if r.get("name") == target_def),
        None,
    )
    if row is None:
        return {"diff0": 0, "a_total": 0, "clean": False}

    diff0 = int(row.get("diff0", 0) or 0)
    a_total = int(row.get("a_total", 0) or 0)
    clean = (
        row.get("missing_side") is None
        and diff0 == a_total
        and int(row.get("modified", 0) or 0) == 0
        and int(row.get("removed", 0) or 0) == 0
        and int(row.get("added", 0) or 0) == 0
    )
    return {"diff0": diff0, "a_total": a_total, "clean": clean}


def dfs_repair_search(
    census_ir: Dict[str, Any],
    post_ir: Dict[str, Any],
    target_def: str,
    candidate_fn: Callable[[Dict[str, Any], str], List[RepairCandidate]],
    gate_fn: Callable[[Dict[str, Any], Dict[str, Any], str], Dict[str, Any]],
    *,
    max_steps: int = 20,
    max_depth: int = 3,
    trace_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Depth-first repair search with gate-only pruning and JSONL tracing."""
    steps_used = 0
    best_diff0 = -1
    best_a_total = 0
    best_ir: Dict[str, Any] = copy.deepcopy(post_ir)
    success = False
    final_ir: Dict[str, Any] = copy.deepcopy(post_ir)
    budget_exhausted = False
    trace_records: List[Dict[str, Any]] = []

    def _record_best(state: Dict[str, Any], verdict: Dict[str, Any]) -> None:
        nonlocal best_diff0, best_a_total, best_ir
        if verdict["diff0"] > best_diff0:
            best_diff0 = verdict["diff0"]
            best_a_total = verdict["a_total"]
            best_ir = copy.deepcopy(state)

    def _gate_eval(
        state: Dict[str, Any],
        *,
        depth: int,
        candidate_id: str,
        description: str,
        parent_step: Optional[int],
        parent_diff0: int,
    ) -> Optional[Dict[str, Any]]:
        nonlocal steps_used, budget_exhausted

        if steps_used >= max_steps:
            budget_exhausted = True
            return None

        steps_used += 1
        step = steps_used
        verdict = gate_fn(census_ir, state, target_def)
        pruned = verdict["diff0"] < parent_diff0
        _record_best(state, verdict)
        record: Dict[str, Any] = {
            "step": step,
            "depth": depth,
            "candidate": candidate_id,
            "description": description,
            "diff0": verdict["diff0"],
            "a_total": verdict["a_total"],
            "clean": verdict["clean"],
            "pruned": pruned,
            "backtracked": pruned,
            "parent_step": parent_step,
        }
        if parent_step is None:
            record.pop("parent_step")
        trace_records.append(record)
        return {
            "step": step,
            "trace_index": len(trace_records) - 1,
            "verdict": verdict,
            "pruned": pruned,
        }

    def _expand(
        state: Dict[str, Any],
        depth: int,
        state_step: int,
        state_diff0: int,
    ) -> bool:
        nonlocal success, final_ir, budget_exhausted

        if success or budget_exhausted or depth >= max_depth:
            return False

        candidates = sorted(
            candidate_fn(state, target_def),
            key=lambda c: c.score,
            reverse=True,
        )

        for candidate in candidates:
            if success or budget_exhausted:
                break

            child = candidate.apply(state)
            child_eval = _gate_eval(
                child,
                depth=depth + 1,
                candidate_id=candidate.id,
                description=candidate.description,
                parent_step=state_step,
                parent_diff0=state_diff0,
            )
            if child_eval is None:
                break

            child_verdict = child_eval["verdict"]
            child_step = child_eval["step"]
            pruned = child_eval["pruned"]
            trace_index = child_eval["trace_index"]

            if child_verdict["clean"]:
                success = True
                final_ir = copy.deepcopy(child)
                return True

            descended = False
            if not pruned:
                descended = _expand(child, depth + 1, child_step, child_verdict["diff0"])

            if not descended:
                trace_records[trace_index]["backtracked"] = True

            if descended:
                return True

        return False

    root_eval = _gate_eval(
        copy.deepcopy(post_ir),
        depth=0,
        candidate_id="__root__",
        description="initial post state",
        parent_step=None,
        parent_diff0=-1,
    )
    if root_eval is not None:
        root_verdict = root_eval["verdict"]
        root_step = root_eval["step"]
        if root_verdict["clean"]:
            success = True
            final_ir = copy.deepcopy(post_ir)
        else:
            _expand(
                copy.deepcopy(post_ir),
                0,
                root_step,
                root_verdict["diff0"],
            )

    if trace_path is not None:
        trace_dir = os.path.dirname(os.path.abspath(trace_path))
        if trace_dir:
            os.makedirs(trace_dir, exist_ok=True)
        with open(trace_path, "w", encoding="utf-8") as trace_file:
            for record in trace_records:
                trace_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    if budget_exhausted or not success:
        success = False
        final_ir = copy.deepcopy(best_ir)

    return {
        "success": success,
        "best_diff0": best_diff0,
        "a_total": best_a_total,
        "steps_used": steps_used,
        "trace_path": trace_path,
        "final_ir": final_ir,
    }
