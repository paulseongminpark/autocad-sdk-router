#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""policy_hygiene -- reconcile operations[].policy blocks with policy.v2.json.

For every operation row in config/operations.v2.json, recompute the EXPECTED
embedded policy block from config/policy.v2.json plus the row's top-level
``status`` and ``write_level``. Report drift as structured JSON on stdout;
``--fix`` rewrites only drifted policy blocks back into the registry.

Stdlib only. Reads the registry with encoding='utf-8-sig'. Writes exactly like
tools/merge_fragments.py: open('w', encoding='utf-8'), json.dump(indent=2,
ensure_ascii=False), then f.write('\\n').
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = ROOT / "config" / "policy.v2.json"
DEFAULT_REGISTRY_PATH = ROOT / "config" / "operations.v2.json"

POLICY_SOURCE = "config/policy.v2.json"

LEGACY_POLICY_KEYS = frozenset({
    "write_mode_default",
    "staged_copy_required",
    "write_original_requires_approval",
    "raw_command_dispatch",
    "secrets",
})

STANDARD_STATUS_POLICIES = frozenset({
    "implemented",
    "catalogued_not_runnable",
    "blocked",
})

NON_STANDARD_STATUS_POLICY_MAP = {
    "implemented_read_only": "implemented",
    "implemented_native_read_safe": "implemented",
    "implemented_native_plan_only": "implemented",
    "implemented_v1": "implemented",
    "blocked_not_runnable": "blocked",
}

PRESERVED_RUNTIME_BEHAVIORS = frozenset({
    "hard_blocked_after_wave3_reaudit",
    "hard_blocked_after_wave3_render_plot_reaudit",
    "hard_blocked_after_wave6_sheetset_probe",
    "read_only_introspection",
    "blocked_after_wave3_reaudit",
    "registration_plan_only_no_registry_write",
})

PRESERVED_POLICY_EXTRAS = frozenset({"agent_exposed", "risk_class", "note"})


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def _dump_registry(path: Path, doc: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _is_raw_command(op: Dict[str, Any]) -> bool:
    handler = op.get("handler") or {}
    native_api = handler.get("native_api") or ""
    op_id = op.get("id") or ""
    if any(token in native_api for token in (
        "acedCommand", "acedCmd", "acedInvoke", "acedPostCommand", "sendStringToExecute",
    )):
        return True
    if op_id == "doc.sendstring":
        return True
    if op_id.startswith(("command.invoke", "command.send", "command.queue")):
        return True
    return False


def _is_legacy_policy(policy: Optional[Dict[str, Any]]) -> bool:
    if not policy:
        return True
    return any(key in policy for key in LEGACY_POLICY_KEYS)


def derive_status_policy(op: Dict[str, Any]) -> str:
    """Legislated status_policy from top-level status.

    Top-level ``status`` is the registry's single source of truth for
    runnability (registry honesty reconcile, 2026-07-06); this reconciler must
    never second-guess a promotion with its own evidence heuristics.
    """
    status = op.get("status")
    if status == "blocked":
        return "blocked"
    if status == "implemented":
        return "implemented"
    return {
        "wired": "implemented",
        "catalogued": "catalogued_not_runnable",
        "stub": "catalogued_not_runnable",
        "deprecated": "blocked",
    }.get(status, status)


def derive_runtime_behavior(
    op: Dict[str, Any],
    status_policy: str,
    actual_policy: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    if status_policy == "catalogued_not_runnable":
        return "not_runnable_until_promoted_to_implemented_or_wired"
    if status_policy == "blocked" and _is_raw_command(op):
        return "blocked_raw_command_agent_surface"
    actual_rb = (actual_policy or {}).get("runtime_behavior")
    if actual_rb in PRESERVED_RUNTIME_BEHAVIORS:
        return actual_rb
    return None


def expected_policy(
    op: Dict[str, Any],
    policy_doc: Dict[str, Any],
    *,
    actual_policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Recompute the canonical embedded policy block for one operation row."""
    actual_policy = actual_policy if actual_policy is not None else (op.get("policy") or {})
    write_level = op.get("write_level") or {}
    default_write_mode = (
        write_level.get("default_write_mode")
        or policy_doc.get("default_write_mode")
        or "read"
    )
    no_original_write_default = (
        policy_doc.get("m04_registry_status_policy", {}).get("no_original_write_default", True)
    )
    status_policy = derive_status_policy(op)
    actual_status_policy = actual_policy.get("status_policy")
    if actual_status_policy in NON_STANDARD_STATUS_POLICY_MAP:
        status_policy = NON_STANDARD_STATUS_POLICY_MAP[actual_status_policy]

    policy: Dict[str, Any] = {
        "source": POLICY_SOURCE,
        "status_policy": status_policy,
        "default_write_mode": default_write_mode,
        "no_original_write_default": no_original_write_default,
    }

    allowed_write_modes = write_level.get("allowed_write_modes")
    legacy = _is_legacy_policy(actual_policy)
    if allowed_write_modes is not None and (
        legacy or actual_policy.get("allowed_write_modes") is not None
    ):
        policy["allowed_write_modes"] = list(allowed_write_modes)

    runtime_behavior = derive_runtime_behavior(op, status_policy, actual_policy)
    if runtime_behavior is not None:
        policy["runtime_behavior"] = runtime_behavior

    for extra in PRESERVED_POLICY_EXTRAS:
        if extra in actual_policy:
            policy[extra] = deepcopy(actual_policy[extra])

    return policy


def policy_drift(
    op: Dict[str, Any],
    policy_doc: Dict[str, Any],
) -> List[Dict[str, Any]]:
    actual = op.get("policy") or {}
    expected = expected_policy(op, policy_doc, actual_policy=actual)
    drifts: List[Dict[str, Any]] = []

    if _is_legacy_policy(actual):
        drifts.append({
            "field": "policy",
            "reason": "legacy_v1_policy_shape",
            "actual": actual,
            "expected": expected,
        })
        return drifts

    actual_status_policy = actual.get("status_policy")
    if actual_status_policy not in STANDARD_STATUS_POLICIES:
        drifts.append({
            "field": "status_policy",
            "reason": "nonstandard_status_policy",
            "actual": actual_status_policy,
            "expected": expected.get("status_policy"),
        })

    managed_fields = (
        "source",
        "status_policy",
        "default_write_mode",
        "no_original_write_default",
        "allowed_write_modes",
        "runtime_behavior",
    )
    for field in managed_fields:
        if expected.get(field) != actual.get(field):
            if any(d.get("field") == field for d in drifts):
                continue
            drifts.append({
                "field": field,
                "actual": actual.get(field),
                "expected": expected.get(field),
            })

    for field, value in actual.items():
        if field in expected or field in PRESERVED_POLICY_EXTRAS:
            continue
        if field in LEGACY_POLICY_KEYS:
            continue
        drifts.append({
            "field": field,
            "reason": "unexpected_policy_key",
            "actual": value,
            "expected": None,
        })

    return drifts


def check_registry(
    registry: Dict[str, Any],
    policy_doc: Dict[str, Any],
) -> Dict[str, Any]:
    drift_rows: List[Dict[str, Any]] = []
    for op in registry.get("operations") or []:
        if not isinstance(op, dict):
            continue
        drift = policy_drift(op, policy_doc)
        if drift:
            drift_rows.append({
                "op_id": op.get("id"),
                "status": op.get("status"),
                "drift": drift,
            })

    return {
        "schema": "ariadne.cados.policy_hygiene_report.v1",
        "policy_source": POLICY_SOURCE,
        "registry_operations": len(registry.get("operations") or []),
        "drift_count": len(drift_rows),
        "drift_rows": drift_rows,
    }


def apply_fixes(
    registry: Dict[str, Any],
    policy_doc: Dict[str, Any],
) -> Dict[str, Any]:
    fixed_ops: List[str] = []
    for op in registry.get("operations") or []:
        if not isinstance(op, dict):
            continue
        drift = policy_drift(op, policy_doc)
        if not drift:
            continue
        op["policy"] = expected_policy(op, policy_doc, actual_policy=op.get("policy") or {})
        fixed_ops.append(op.get("id") or "")
    return {
        "fixed_count": len(fixed_ops),
        "fixed_op_ids": fixed_ops,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY_PATH,
        help="Path to config/operations.v2.json",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY_PATH,
        help="Path to config/policy.v2.json",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Rewrite drifted policy blocks in the registry",
    )
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    policy_doc = _load_json(args.policy)
    registry = _load_json(args.registry)

    if args.fix:
        fix_summary = apply_fixes(registry, policy_doc)
        _dump_registry(args.registry, registry)
        report = check_registry(registry, policy_doc)
        report["fix"] = fix_summary
    else:
        report = check_registry(registry, policy_doc)

    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0 if report.get("drift_count", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
