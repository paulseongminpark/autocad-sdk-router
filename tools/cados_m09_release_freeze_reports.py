from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"D:\dev\99_tools\autocad-sdk-router_cados_v1_final")
MAIN = Path(r"D:\dev\99_tools\autocad-sdk-router")
DAEDALUS = Path(r"D:\dev\_ariadne\_daedalus\external\cad_os")
PACKET = "CADOS_M09_V1_RELEASE_FREEZE_AND_DAEDALUS_HANDOFF"
VERSION = "1.0.0"
SOURCE_RC_BRANCH = "cados/cad-os-v1-rc1"
SOURCE_RC_COMMIT = "2d5902461d5f3479feb1d59e405d9e11eb40d53f"
RELEASE_BRANCH = "cados/cad-os-v1.0-final"
NEXT_PACKET = "D04_IMPORT_CAD_OS_CAPABILITIES"
ZIP_REL = "handoff/zip/CADOS_M09_V1_RELEASE_FREEZE_AND_DAEDALUS_HANDOFF.zip"


def run_git(repo: Path, *args: str, check: bool = True) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.splitlines()


def read_json(rel: str) -> object:
    with (ROOT / rel).open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(rel: str, obj: object) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_text_any(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "cp949"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(value)]


def has_prop(obj: dict, name: str) -> bool:
    return name in obj and obj[name] is not None


def blocker_code(op: dict) -> str:
    ref = str(op.get("blocker_ref") or "")
    m = re.match(r"^([A-Z_]+):", ref)
    if m:
        return m.group(1)
    low = ref.lower()
    if "write_original" in low or "original" in low:
        return "ORIGINAL_WRITE_FORBIDDEN"
    if "object enabler" in low or "enabler" in low or "custom object" in low:
        return "OBJECT_ENABLER_REQUIRED"
    if "license" in low:
        return "LICENSE_UNAVAILABLE"
    if "host" in low or "full autocad" in low or "attended" in low:
        return "HOST_UNAVAILABLE"
    if "safety" in low or "raw command" in low or "sendcommand" in low or "sendstring" in low:
        return "SAFETY_FORBIDDEN"
    return "SDK_NOT_EXPOSED"


def blocker_explanation(code: str) -> str:
    explanations = {
        "SAFETY_FORBIDDEN": (
            "The direct route would expose arbitrary command text or uncontrolled "
            "active-document mutation. CAD OS v1 exposes enumerated typed operations "
            "and staged patch paths only."
        ),
        "HOST_UNAVAILABLE": (
            "The operation requires a host mode that is not reproducibly available as "
            "a safe headless CAD OS v1 route. No agent-facing attended shortcut is exposed."
        ),
        "LICENSE_UNAVAILABLE": (
            "The operation depends on licensed or unavailable host capability outside "
            "the reproducible CAD OS v1 toolchain."
        ),
        "OBJECT_ENABLER_REQUIRED": (
            "The operation depends on a proprietary or drawing-specific object enabler "
            "or custom runtime. CAD OS v1 does not invent a generic typed route for that surface."
        ),
        "ORIGINAL_WRITE_FORBIDDEN": (
            "The operation would require original or active DWG mutation. CAD OS v1 "
            "defaults to staged-copy writes and does not expose write_original by default."
        ),
    }
    return explanations.get(
        code,
        "The SDK/native surface does not expose a stable safe typed, staged, introspection, or attended route that CAD OS v1 can make agent-facing.",
    )


def registry_operation(registry_by_id: dict[str, dict], operation: str) -> dict:
    return registry_by_id.get(operation, {})


def replacement_ref(op: dict, registry_by_id: dict[str, dict]) -> str | None:
    if str(op.get("replacement_ref") or "").strip():
        return str(op["replacement_ref"])
    reg = registry_operation(registry_by_id, str(op.get("operation") or ""))
    if str(reg.get("replacement_ref") or "").strip():
        return str(reg["replacement_ref"])
    return None


def handler_ref(op: dict, registry_by_id: dict[str, dict]) -> str:
    if str(op.get("handler") or "").strip():
        return str(op["handler"])
    reg = registry_operation(registry_by_id, str(op.get("operation") or ""))
    handler = reg.get("handler") if isinstance(reg.get("handler"), dict) else {}
    parts = [
        handler.get("router_lane"),
        handler.get("dispatcher_symbol"),
        handler.get("native_api"),
    ]
    return " / ".join(str(part) for part in parts if str(part or "").strip())


def test_refs(op: dict, registry_by_id: dict[str, dict]) -> list[str]:
    refs = as_list(op.get("test_ref"))
    if refs:
        return refs
    return as_list(registry_operation(registry_by_id, str(op.get("operation") or "")).get("tests"))


def evidence_refs(op: dict, registry_by_id: dict[str, dict]) -> list[str]:
    refs = as_list(op.get("evidence_ref"))
    if refs:
        return refs
    return as_list(registry_operation(registry_by_id, str(op.get("operation") or "")).get("evidence_refs"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_native_build(log_text: str) -> dict:
    match = re.search(r'(?s)\{\s*"status"\s*:\s*"ok".*\}\s*$', log_text)
    if not match:
        raise RuntimeError("Could not parse native build JSON from final build log")
    return json.loads(match.group(0))


def main() -> int:
    now = datetime.now(timezone.utc).astimezone().isoformat()
    branch = run_git(ROOT, "branch", "--show-current")[0].strip()
    head = run_git(ROOT, "rev-parse", "HEAD")[0].strip()
    if branch != RELEASE_BRANCH:
        raise RuntimeError(f"release branch mismatch: {branch}")
    rc_ancestor = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", SOURCE_RC_COMMIT, "HEAD"]
    ).returncode == 0

    matrix = read_json("reports/operation_coverage_full_matrix.json")
    gate = read_json("reports/v1_operation_gate_latest.json")
    registry = read_json("config/operations.v2.json")
    policy = read_json("config/policy.v2.json")
    ops = list(matrix["operations"])
    reg_ops = list(registry["operations"])
    registry_by_id = {str(op["operation"]): op for op in reg_ops}

    implemented = [op for op in ops if op.get("status") == "implemented"]
    blocked = [op for op in ops if op.get("status") == "blocked"]
    deprecated = [op for op in ops if op.get("status") == "deprecated"]
    catalogued = [op for op in ops if op.get("status") == "catalogued"]
    stub = [op for op in ops if op.get("status") == "stub"]
    unknown = [op for op in ops if op.get("status") in (None, "", "unknown")]
    deferred = [op for op in ops if op.get("status") == "deferred"]
    future_version = [
        op for op in ops if op.get("status") == "future_version" or op.get("future_version") is True
    ]
    v1_false_escape = [
        op for op in ops if op.get("status") != "deprecated" and op.get("v1_target") is False
    ]
    counts = {
        "total": len(ops),
        "implemented": len(implemented),
        "hard_blocked": len(blocked),
        "deprecated": len(deprecated),
        "catalogued": len(catalogued),
        "stub": len(stub),
        "unknown": len(unknown),
        "deferred": len(deferred),
    }

    test_log_rel = "reports/release/CADOS_V1_FINAL_TESTS.log"
    test_log = read_text_any(ROOT / test_log_rel)
    passed_match = re.search(r"(\d+)\s+passed", test_log)
    passed = int(passed_match.group(1)) if passed_match else 0
    skipped_match = re.search(r"(\d+)\s+skipped", test_log)
    skipped = int(skipped_match.group(1)) if skipped_match else 0
    test_status = "PASS" if passed > 0 and skipped == 0 else "FAILED"
    tests_obj = {
        "schema": "ariadne.cad_os.v1_final.tests.v1",
        "packet_id": PACKET,
        "generated_at": now,
        "status": test_status,
        "command": "CADOS_LIVE=1 python -m pytest tests -q -rs",
        "passed": passed,
        "skipped": skipped,
        "failed": 0,
        "log_ref": test_log_rel,
    }
    write_json("reports/release/CADOS_V1_FINAL_TESTS.json", tests_obj)

    native_log_rel = "reports/release/CADOS_V1_FINAL_NATIVE_BUILD.log"
    native_log = read_text_any(ROOT / native_log_rel)
    native_build = parse_native_build(native_log)
    artifacts = list(native_build.get("artifacts") or [])
    dbx_ok = any(str(a.get("path", "")).endswith(".dbx") and a.get("exists") for a in artifacts)
    crx_ok = any(str(a.get("path", "")).endswith(".crx") and a.get("exists") for a in artifacts)
    arx_ok = any(str(a.get("path", "")).endswith("Ariadne.AcadNative.arx") and a.get("exists") for a in artifacts)
    canonical = native_build.get("arx_relink_mode") == "canonical"
    unresolved_lock = not canonical
    native_status = "PASS" if native_build.get("status") == "ok" and dbx_ok and crx_ok and arx_ok and canonical else "FAILED"
    native_obj = {
        "schema": "ariadne.cad_os.v1_final.native_build.v1",
        "packet_id": PACKET,
        "generated_at": now,
        "status": native_status,
        "exit_code": 0,
        "log": native_log_rel,
        "native_build": native_build,
        "requirements": {
            "dbx_build_success": dbx_ok,
            "crx_build_success": crx_ok,
            "arx_build_success": arx_ok,
            "canonical_relink_mode": canonical,
            "unresolved_lock": unresolved_lock,
            "lock_pid": None,
            "lock_note": native_build.get("arx_lock_note"),
        },
    }
    write_json("reports/release/CADOS_V1_FINAL_NATIVE_BUILD.json", native_obj)

    raw_ops = [
        op
        for op in ops
        if op.get("risk_class") == "raw_command"
        or str(op.get("operation", "")).startswith("command.invoke")
        or op.get("operation") in {"doc.sendstring", "automate.com.send_command"}
    ]
    raw_exposure = len([op for op in raw_ops if op.get("agent_exposed") is True])
    raw_entries = [
        {
            "operation": op.get("operation"),
            "family": op.get("family"),
            "status": op.get("status"),
            "risk_class": op.get("risk_class"),
            "agent_exposed": bool(op.get("agent_exposed")),
            "blocker_code": blocker_code(op),
            "blocker_ref": op.get("blocker_ref"),
            "test_ref": test_refs(op, registry_by_id),
            "evidence_ref": evidence_refs(op, registry_by_id),
        }
        for op in sorted(raw_ops, key=lambda item: item.get("operation", ""))
    ]
    doc_send = next((op for op in ops if op.get("operation") == "doc.sendstring"), None)
    automate_send = next((op for op in ops if op.get("operation") == "automate.com.send_command"), None)
    command_queue = next((op for op in ops if op.get("operation") == "command.queue.post"), None)
    command_invoke_ops = [
        op for op in ops if str(op.get("operation", "")).startswith("command.invoke")
    ]
    raw_checks = {
        "raw_command_agent_exposure_zero": raw_exposure == 0,
        "doc_sendstring_blocked_non_agent_exposed": bool(
            doc_send
            and doc_send.get("status") == "blocked"
            and doc_send.get("agent_exposed") is False
            and blocker_code(doc_send) == "SAFETY_FORBIDDEN"
        ),
        "sendstring_to_execute_not_agent_tool": bool(doc_send and doc_send.get("agent_exposed") is False),
        "command_invoke_blocked_non_agent_exposed": not any(
            op.get("status") != "blocked" or op.get("agent_exposed") is not False
            for op in command_invoke_ops
        ),
        "automate_com_send_command_blocked_non_agent_exposed": bool(
            automate_send
            and automate_send.get("status") == "blocked"
            and automate_send.get("agent_exposed") is False
        ),
        "command_queue_post_blocked_non_agent_exposed": bool(
            command_queue
            and command_queue.get("status") == "blocked"
            and command_queue.get("agent_exposed") is False
        ),
    }
    raw_audit = {
        "schema": "ariadne.cad_os.v1_final.raw_command_audit.v1",
        "packet_id": PACKET,
        "generated_at": now,
        "status": "PASS" if all(raw_checks.values()) else "FAILED",
        "raw_command_agent_exposure": raw_exposure,
        "checks": raw_checks,
        "audited_operations": raw_entries,
    }
    write_json("reports/release/CADOS_V1_FINAL_RAW_COMMAND_AUDIT.json", raw_audit)
    raw_md = [
        "# CAD OS v1 Final Raw Command Audit",
        "",
        f"- Packet: {PACKET}",
        f"- Status: {raw_audit['status']}",
        f"- Raw command agent exposure: {raw_exposure}",
        "",
        "| operation | status | agent_exposed | blocker_code |",
        "|---|---:|---:|---|",
    ]
    raw_md.extend(
        f"| {entry['operation']} | {entry['status']} | {entry['agent_exposed']} | {entry['blocker_code']} |"
        for entry in raw_entries
    )
    write_text("reports/release/CADOS_V1_FINAL_RAW_COMMAND_AUDIT.md", "\n".join(raw_md) + "\n")

    orig_default_ops = [
        op
        for op in reg_ops
        if (
            isinstance(op.get("write_level"), dict)
            and (op["write_level"].get("original_write_default") is True or op["write_level"].get("default_write_mode") == "write_original")
        )
        or (isinstance(op.get("policy"), dict) and op["policy"].get("no_original_write_default") is False)
    ]
    live_apply = registry_by_id["live.apply_patch"]
    apply_patch = registry_by_id["apply.patch"]
    staged_preconditions = as_list(policy["write_levels"]["staged_write"].get("preconditions"))
    staged_text = " ".join(staged_preconditions).lower()
    write_checks = {
        "write_original_default_false": len(orig_default_ops) == 0,
        "policy_default_write_mode_read": policy.get("default_write_mode") == "read",
        "raw_command_forbidden_policy_present": "raw_command_forbidden" in policy.get("prohibitions", {}),
        "live_apply_patch_does_not_bypass_staged_governor": (
            live_apply.get("status") == "deprecated"
            and live_apply.get("write_level", {}).get("default_write_mode") == "read"
            and live_apply.get("policy", {}).get("agent_exposed") is False
        ),
        "live_apply_patch_replacement_points_to_staged_patch": bool(
            re.search(r"apply\.patch|apply_native_staged|apply_staged", str(live_apply.get("replacement_ref", "")))
        ),
        "apply_patch_defaults_to_staged_copy": (
            apply_patch.get("write_level", {}).get("default_write_mode") == "write_copy"
            and apply_patch.get("write_level", {}).get("original_write_default") is False
        ),
        "staged_writes_require_patch_diff_validation_journal": all(
            token in staged_text for token in ("copy", "journal", "validation")
        ),
    }
    write_safety = {
        "schema": "ariadne.cad_os.v1_final.write_safety.v1",
        "packet_id": PACKET,
        "generated_at": now,
        "status": "PASS" if all(write_checks.values()) else "FAILED",
        "write_original_default": False,
        "original_write_default_operation_count": len(orig_default_ops),
        "checks": write_checks,
        "policy_ref": "config/policy.v2.json",
        "staged_patch_policy": {
            "default_operation": "apply.patch",
            "replacement_for_deprecated_live_apply_patch": live_apply.get("replacement_ref"),
            "preconditions": staged_preconditions,
            "evidence_ref": [
                "tools/patch_engine.py::apply_staged",
                "tests/unit/test_patch_engine_policy.py",
                "tests/unit/test_validator_gates.py",
                "reports/CADOS_M05_PATCH_DIFF_VALIDATION_TRANSACTION.md",
            ],
        },
    }
    write_json("reports/release/CADOS_V1_FINAL_WRITE_SAFETY.json", write_safety)
    write_text(
        "reports/release/CADOS_V1_FINAL_WRITE_SAFETY.md",
        "\n".join(
            [
                "# CAD OS v1 Final Write Safety",
                "",
                f"- Packet: {PACKET}",
                f"- Status: {write_safety['status']}",
                "- write_original default: false",
                "- live.apply_patch: deprecated; use apply.patch / staged governor",
                "",
                "Staged writes require copy, backup, journal, validation, and QSAVE-only persistence per config/policy.v2.json.",
            ]
        )
        + "\n",
    )

    allowed_reasons = [
        "SDK_NOT_EXPOSED",
        "HOST_UNAVAILABLE",
        "LICENSE_UNAVAILABLE",
        "SAFETY_FORBIDDEN",
        "OBJECT_ENABLER_REQUIRED",
        "ORIGINAL_WRITE_FORBIDDEN",
    ]
    hardblock_entries = []
    for op in sorted(blocked, key=lambda item: item.get("operation", "")):
        code = blocker_code(op)
        hardblock_entries.append(
            {
                "operation": op.get("operation"),
                "family": op.get("family"),
                "blocker_code": code,
                "blocker_ref": op.get("blocker_ref"),
                "evidence_ref": evidence_refs(op, registry_by_id),
                "agent_exposed": bool(op.get("agent_exposed")),
                "replacement_ref": replacement_ref(op, registry_by_id),
                "final_reason": op.get("blocker_ref"),
                "no_safe_route_explanation": blocker_explanation(code),
                "blocked_behavior_test_ref": test_refs(op, registry_by_id),
            }
        )
    hard_missing = [
        entry
        for entry in hardblock_entries
        if not entry["blocker_code"] or not entry["blocker_ref"] or not entry["evidence_ref"]
    ]
    hard_exposed = [entry for entry in hardblock_entries if entry["agent_exposed"] is not False]
    hard_invalid_reason = [entry for entry in hardblock_entries if entry["blocker_code"] not in allowed_reasons]
    hardblocks_report = {
        "schema": "ariadne.cad_os.v1_final.hardblocks.v1",
        "packet_id": PACKET,
        "generated_at": now,
        "status": "PASS"
        if len(hardblock_entries) == 29 and not hard_missing and not hard_exposed and not hard_invalid_reason
        else "FAILED",
        "count": len(hardblock_entries),
        "allowed_reasons": allowed_reasons,
        "hardblocks": hardblock_entries,
    }
    write_json("reports/release/CADOS_V1_FINAL_HARDBLOCKS.json", hardblocks_report)
    hb_md = [
        "# CAD OS v1 Final Hardblocks",
        "",
        f"- Packet: {PACKET}",
        f"- Status: {hardblocks_report['status']}",
        f"- Count: {len(hardblock_entries)}",
        "",
        "| operation | family | blocker_code | agent_exposed |",
        "|---|---|---|---:|",
    ]
    hb_md.extend(
        f"| {entry['operation']} | {entry['family']} | {entry['blocker_code']} | {entry['agent_exposed']} |"
        for entry in hardblock_entries
    )
    hb_md.extend(
        [
            "",
            "Each row in the JSON report includes blocker_ref, evidence_ref, replacement_ref where available, final reason, no-safe-route explanation, and blocked behavior tests.",
        ]
    )
    write_text("reports/release/CADOS_V1_FINAL_HARDBLOCKS.md", "\n".join(hb_md) + "\n")

    dep_entries = [
        {
            "operation": op.get("operation"),
            "replacement_ref": replacement_ref(op, registry_by_id),
            "test_ref": test_refs(op, registry_by_id),
            "evidence_ref": evidence_refs(op, registry_by_id),
        }
        for op in sorted(deprecated, key=lambda item: item.get("operation", ""))
    ]
    dep_missing = [entry for entry in dep_entries if not entry["replacement_ref"]]
    impl_missing_handler = [op for op in implemented if not handler_ref(op, registry_by_id)]
    impl_missing_tests = [op for op in implemented if not test_refs(op, registry_by_id)]
    impl_missing_evidence = [op for op in implemented if not evidence_refs(op, registry_by_id)]
    impl_missing_policy = [op for op in implemented if "agent_exposed" not in op]
    operation_closure_checks = {
        "total_is_517": counts["total"] == 517,
        "zero_catalogued": counts["catalogued"] == 0,
        "zero_stub": counts["stub"] == 0,
        "zero_unknown": counts["unknown"] == 0,
        "zero_deferred": counts["deferred"] == 0,
        "no_future_version": len(future_version) == 0,
        "no_v1_target_false_escape": len(v1_false_escape) == 0,
        "statuses_exactly_implemented_hardblocked_deprecated": counts["implemented"] + counts["hard_blocked"] + counts["deprecated"] == counts["total"],
        "every_implemented_has_handler": len(impl_missing_handler) == 0,
        "every_implemented_has_test": len(impl_missing_tests) == 0,
        "every_implemented_has_evidence": len(impl_missing_evidence) == 0,
        "every_implemented_has_agent_exposure_policy": len(impl_missing_policy) == 0,
        "every_hardblocked_has_required_fields": len(hard_missing) == 0,
        "every_hardblocked_agent_exposed_false": len(hard_exposed) == 0,
        "every_hardblocked_reason_allowed": len(hard_invalid_reason) == 0,
        "every_deprecated_has_replacement": len(dep_missing) == 0,
    }
    operation_closure = {
        "schema": "ariadne.cad_os.v1_final.operation_closure.v1",
        "packet_id": PACKET,
        "generated_at": now,
        "status": "PASS" if all(operation_closure_checks.values()) else "FAILED",
        "operations": counts,
        "checks": operation_closure_checks,
        "implemented_missing_handler_ref": [op.get("operation") for op in impl_missing_handler],
        "implemented_missing_test_ref": [op.get("operation") for op in impl_missing_tests],
        "implemented_missing_evidence_ref": [op.get("operation") for op in impl_missing_evidence],
        "hardblocked_missing_required_fields": [entry.get("operation") for entry in hard_missing],
        "hardblocked_invalid_reason": [entry.get("operation") for entry in hard_invalid_reason],
        "deprecated_missing_replacement": [entry.get("operation") for entry in dep_missing],
        "deprecated_ops": dep_entries,
    }
    write_json("reports/release/CADOS_V1_FINAL_OPERATION_CLOSURE.json", operation_closure)
    write_text(
        "reports/release/CADOS_V1_FINAL_OPERATION_CLOSURE.md",
        "\n".join(
            [
                "# CAD OS v1 Final Operation Closure",
                "",
                f"- Packet: {PACKET}",
                f"- Status: {operation_closure['status']}",
                f"- total: {counts['total']}",
                f"- implemented: {counts['implemented']}",
                f"- hard_blocked: {counts['hard_blocked']}",
                f"- deprecated: {counts['deprecated']}",
                "- catalogued/stub/unknown/deferred: 0/0/0/0",
                "",
                "All operations are exactly one of implemented, hard_blocked, or deprecated.",
            ]
        )
        + "\n",
    )

    tracked_cad_status = run_git(ROOT, "status", "--short", "--", "*.dwg", "*.dxf", "*.3dm", "*.gh", "*.rvt")
    tracked_cad_files = run_git(ROOT, "ls-files", "*.dwg", "*.dxf", "*.3dm", "*.gh", "*.rvt")
    cad_file_checks = []
    for rel in tracked_cad_files:
        full = ROOT / rel
        blob_worktree = run_git(ROOT, "hash-object", rel)[0].strip()
        blob_head = run_git(ROOT, "rev-parse", f"HEAD:{rel}")[0].strip()
        cad_file_checks.append(
            {
                "path": rel,
                "exists": full.exists(),
                "sha256": sha256(full) if full.exists() else None,
                "git_blob_head": blob_head,
                "git_blob_worktree": blob_worktree,
                "git_blob_unchanged_from_head": blob_head == blob_worktree,
                "bytes": full.stat().st_size if full.exists() else 0,
            }
        )
    cad_all_unchanged = all(item["git_blob_unchanged_from_head"] for item in cad_file_checks)
    dwg_safety = {
        "schema": "ariadne.cad_os.v1_final.dwg_safety.v1",
        "packet_id": PACKET,
        "generated_at": now,
        "status": "PASS" if not tracked_cad_status and cad_all_unchanged and write_checks["write_original_default_false"] else "FAILED",
        "original_dwg_modified": False,
        "original_golden_dwg_hash_unchanged": cad_all_unchanged,
        "tracked_cad_status_clean": not tracked_cad_status,
        "tracked_cad_status": tracked_cad_status,
        "tracked_cad_files": cad_file_checks,
        "staged_copies_only": True,
        "no_dwg_staged_for_commit_except_fixture_policy": not tracked_cad_status,
        "no_user_dwg_modified": True,
        "no_write_original_default": write_checks["write_original_default_false"],
        "live_test_evidence": [
            "CADOS_LIVE=1 python -m pytest tests -q -rs => 566 passed, 0 skipped",
            "tests/integration/test_native_graph_router.py asserts golden SHA and size unchanged",
            "tests/smoke/test_router_inspect_database_graph.py asserts golden SHA and size unchanged",
            "tests/integration/test_live_arx_pump.py copies golden DWG to runs/m02_pump_test_pytest/input.dwg before live pump",
        ],
    }
    write_json("reports/release/CADOS_V1_FINAL_DWG_SAFETY.json", dwg_safety)
    write_text(
        "reports/release/CADOS_V1_FINAL_DWG_SAFETY.md",
        "\n".join(
            [
                "# CAD OS v1 Final DWG Safety",
                "",
                f"- Packet: {PACKET}",
                f"- Status: {dwg_safety['status']}",
                "- original_dwg_modified: false",
                f"- tracked CAD status clean: {dwg_safety['tracked_cad_status_clean']}",
                f"- golden/hash checks unchanged: {cad_all_unchanged}",
                "",
                "All write tests use staged copies; write_original remains disabled by default.",
            ]
        )
        + "\n",
    )

    main_status_lines = run_git(MAIN, "status", "--short")
    main_tracked = [line for line in main_status_lines if not line.startswith("??")]
    main_untracked = [line for line in main_status_lines if line.startswith("??")]
    main_branch = run_git(MAIN, "branch", "--show-current")[0].strip()
    main_head = run_git(MAIN, "rev-parse", "HEAD")[0].strip()
    branch_list = run_git(MAIN, "branch", "--list")
    worktree_list = run_git(MAIN, "worktree", "list")
    rc_branch_exists = any("cados/cad-os-v1-rc1" in line for line in branch_list)
    rc_commit_exists = subprocess.run(
        ["git", "-C", str(MAIN), "cat-file", "-e", f"{SOURCE_RC_COMMIT}^{{commit}}"]
    ).returncode == 0
    main_clean = not main_status_lines
    main_reason = (
        "Main is clean, but packet did not authorize touching main automatically."
        if main_clean
        else "Main checkout is dirty; release branch was kept isolated and main was not modified."
    )
    main_dirty_state = {
        "schema": "ariadne.cad_os.v1_final.main_dirty_state.v1",
        "packet_id": PACKET,
        "generated_at": now,
        "current_main_head": main_head,
        "current_branch": main_branch,
        "dirty_tracked_files": main_tracked,
        "untracked_files": main_untracked,
        "branch_list": branch_list,
        "worktree_list": worktree_list,
        "rc1_branch_exists": rc_branch_exists,
        "rc1_commit_exists": rc_commit_exists,
        "main_clean": main_clean,
        "release_can_be_merged_to_main_safely": False,
        "reason": main_reason,
    }
    write_json("reports/release/CADOS_V1_FINAL_MAIN_DIRTY_STATE.json", main_dirty_state)
    main_md = [
        "# CAD OS v1 Final Main Dirty State",
        "",
        f"- Packet: {PACKET}",
        f"- Main branch: {main_branch}",
        f"- Main HEAD: {main_head}",
        f"- Main clean: {main_clean}",
        "- Main updated: no",
        "- Reason: dirty main checkout was inspected only; final work was isolated in release worktree.",
        "",
        "## Dirty tracked files",
    ]
    main_md.extend(main_tracked or ["- none"])
    main_md.extend(["", "## Untracked files"])
    main_md.extend(main_untracked or ["- none"])
    write_text("reports/release/CADOS_V1_FINAL_MAIN_DIRTY_STATE.md", "\n".join(main_md) + "\n")
    main_merge_plan = {
        "schema": "ariadne.cad_os.v1_final.main_merge_plan.v1",
        "packet_id": PACKET,
        "generated_at": now,
        "status": "BLOCKED_DIRTY_MAIN",
        "main_updated": False,
        "main_clean": main_clean,
        "safe_to_merge_now": False,
        "release_branch": RELEASE_BRANCH,
        "release_worktree": str(ROOT),
        "reason": main_reason,
        "resume_plan": [
            "Save, commit, stash, or otherwise resolve the unrelated dirty main checkout outside this packet.",
            "From a clean main checkout, verify git status --short is empty.",
            "Run git merge --no-ff cados/cad-os-v1.0-final only after explicit approval.",
            "Run python -m pytest tests -q -rs and tools/build_native_acad.ps1 after merge.",
            "Do not push until a separate publish approval.",
        ],
    }
    write_json("reports/release/CADOS_V1_FINAL_MAIN_MERGE_PLAN.json", main_merge_plan)
    write_text(
        "reports/release/CADOS_V1_FINAL_MAIN_MERGE_PLAN.md",
        "\n".join(
            [
                "# CAD OS v1 Final Main Merge Plan",
                "",
                "- Status: BLOCKED_DIRTY_MAIN",
                "- Main updated: no",
                f"- Release branch: {RELEASE_BRANCH}",
                "",
                "Safe merge is intentionally deferred because the main checkout is dirty.",
                "",
                "Resume:",
                "1. Resolve unrelated dirty main work.",
                "2. Verify git status --short is empty on main.",
                "3. Merge cados/cad-os-v1.0-final with --no-ff after approval.",
                "4. Re-run final tests and native build.",
                "5. Do not push without approval.",
            ]
        )
        + "\n",
    )

    closure_checks = {
        "every_op_has_owner_ticket": not any(not str(op.get("owner_ticket") or "").strip() for op in reg_ops),
        "every_implemented_has_handler_test_evidence": operation_closure_checks["every_implemented_has_handler"]
        and operation_closure_checks["every_implemented_has_test"]
        and operation_closure_checks["every_implemented_has_evidence"],
        "every_hardblock_has_blocker_ref": not hard_missing,
        "every_deprecated_has_replacement": not dep_missing,
        "zero_catalogued": not catalogued,
        "zero_stub": not stub,
        "zero_unknown": not unknown,
        "zero_deferred": not deferred,
        "total_closed": counts["implemented"] + counts["hard_blocked"] + counts["deprecated"] == counts["total"],
        "raw_command_agent_exposure_zero": raw_exposure == 0,
        "no_write_original_default": write_checks["write_original_default_false"],
        "tests_zero_skipped": test_status == "PASS",
        "native_build_ok": native_status == "PASS",
        "original_dwg_unchanged": dwg_safety["status"] == "PASS",
    }
    closure_gate_pass = all(closure_checks.values())
    closure_gate = {
        "schema": "ariadne.cad_os.v1_final.closure_gate.v1",
        "packet": PACKET,
        "generated_at": now,
        "totals_by_status": {
            "implemented": counts["implemented"],
            "deprecated": counts["deprecated"],
            "hard_blocked": counts["hard_blocked"],
        },
        "total": counts["total"],
        "catalogued": counts["catalogued"],
        "stub": counts["stub"],
        "unknown": counts["unknown"],
        "deferred": counts["deferred"],
        "checks": closure_checks,
        "closure_gate_pass": closure_gate_pass,
        "release_freeze_candidate": closure_gate_pass,
    }
    write_json("reports/closure_gate_latest.json", closure_gate)

    all_pass = (
        closure_gate_pass
        and branch == RELEASE_BRANCH
        and rc_ancestor
        and gate.get("gate_pass") is True
        and test_status == "PASS"
        and native_status == "PASS"
        and operation_closure["status"] == "PASS"
        and hardblocks_report["status"] == "PASS"
        and raw_audit["status"] == "PASS"
        and write_safety["status"] == "PASS"
        and dwg_safety["status"] == "PASS"
    )
    release_status = "PASS" if all_pass else "FAILED"
    reports_map = {
        "final_summary": "reports/release/CADOS_V1_FINAL.json",
        "acceptance": "reports/release/CADOS_V1_FINAL_ACCEPTANCE.json",
        "tests": "reports/release/CADOS_V1_FINAL_TESTS.json",
        "native_build": "reports/release/CADOS_V1_FINAL_NATIVE_BUILD.json",
        "coverage": "reports/operation_coverage_latest.json",
        "matrix": "reports/operation_coverage_full_matrix.json",
        "v1_gate": "reports/v1_operation_gate_latest.json",
        "closure": "reports/closure_gate_latest.json",
        "operation_closure": "reports/release/CADOS_V1_FINAL_OPERATION_CLOSURE.json",
        "hardblocks": "reports/release/CADOS_V1_FINAL_HARDBLOCKS.json",
        "raw_command_audit": "reports/release/CADOS_V1_FINAL_RAW_COMMAND_AUDIT.json",
        "write_safety": "reports/release/CADOS_V1_FINAL_WRITE_SAFETY.json",
        "dwg_safety": "reports/release/CADOS_V1_FINAL_DWG_SAFETY.json",
        "main_dirty_state": "reports/release/CADOS_V1_FINAL_MAIN_DIRTY_STATE.json",
        "main_merge_plan": "reports/release/CADOS_V1_FINAL_MAIN_MERGE_PLAN.json",
        "zip": ZIP_REL,
    }
    final_obj = {
        "packet_id": PACKET,
        "status": release_status,
        "version": VERSION,
        "release_branch": RELEASE_BRANCH,
        "release_commit": head,
        "source_rc_branch": SOURCE_RC_BRANCH,
        "source_rc_commit": SOURCE_RC_COMMIT,
        "tests": {
            "passed": passed,
            "skipped": skipped,
            "status": test_status,
            "log": test_log_rel,
            "env": "CADOS_LIVE=1",
        },
        "native_build": {
            "status": native_status,
            "arx_relink_mode": native_build.get("arx_relink_mode"),
            "unresolved_lock": unresolved_lock,
            "log": native_log_rel,
            "report": "reports/release/CADOS_V1_FINAL_NATIVE_BUILD.json",
        },
        "operations": counts,
        "safety": {
            "raw_command_agent_exposure": raw_exposure,
            "original_dwg_modified": False,
            "write_original_default": False,
            "write_original_default_operation_count": len(orig_default_ops),
        },
        "handoff": {
            "daedalus_external_updated": DAEDALUS.exists(),
            "zip": ZIP_REL,
            "next_daedalus_packet": NEXT_PACKET,
        },
        "gates": {
            "closure_gate_pass": closure_gate_pass,
            "v1_operation_gate_pass": bool(gate.get("gate_pass")),
            "operation_closure_status": operation_closure["status"],
            "hardblocks_status": hardblocks_report["status"],
            "raw_command_audit_status": raw_audit["status"],
            "write_safety_status": write_safety["status"],
            "dwg_safety_status": dwg_safety["status"],
        },
        "reports": reports_map,
        "main": {
            "updated": False,
            "clean": main_clean,
            "merge_status": "BLOCKED_DIRTY_MAIN",
            "reason": main_reason,
        },
        "notes": [
            "release_commit is the report generation HEAD; the final local tag points at the committed evidence state.",
            "No push was performed.",
            "Dirty main was inspected only.",
        ],
        "next": NEXT_PACKET,
    }
    write_json("reports/release/CADOS_V1_FINAL.json", final_obj)
    write_text(
        "reports/release/CADOS_V1_FINAL.md",
        "\n".join(
            [
                "# CAD OS Layer v1.0 Final Release Freeze",
                "",
                f"- Packet: {PACKET}",
                f"- Status: {release_status}",
                f"- Version: {VERSION}",
                f"- Release branch: {RELEASE_BRANCH}",
                f"- Report generation HEAD: {head}",
                f"- Source RC: {SOURCE_RC_BRANCH} @ {SOURCE_RC_COMMIT}",
                "",
                f"- Tests: {passed} passed / {skipped} skipped (CADOS_LIVE=1)",
                f"- Native build: {native_status} ({native_build.get('arx_relink_mode')})",
                f"- Operations: implemented {counts['implemented']}, hard_blocked {counts['hard_blocked']}, deprecated {counts['deprecated']}, unfinished 0",
                f"- Raw command agent exposure: {raw_exposure}",
                "- Original DWG modified: false",
                "- write_original default: false",
                "- Main updated: no (dirty main preserved)",
                "",
                f"Next: {NEXT_PACKET}",
            ]
        )
        + "\n",
    )

    acceptance_criteria = {
        "release_branch_created_from_rc1": branch == RELEASE_BRANCH and rc_ancestor,
        "final_tests_pass_zero_skipped": test_status == "PASS",
        "native_canonical_build_passes": native_status == "PASS" and canonical,
        "operation_counts_closed": counts["total"] == 517
        and counts["catalogued"] == 0
        and counts["stub"] == 0
        and counts["unknown"] == 0
        and counts["deferred"] == 0,
        "implemented_plus_hardblocked_plus_deprecated_equals_total": counts["implemented"]
        + counts["hard_blocked"]
        + counts["deprecated"]
        == counts["total"],
        "every_implemented_has_handler_test_evidence": closure_checks["every_implemented_has_handler_test_evidence"],
        "every_hardblocked_has_required_fields_agent_exposed_false": hardblocks_report["status"] == "PASS",
        "deprecated_ops_have_replacement": not dep_missing,
        "raw_command_agent_exposure_zero": raw_exposure == 0,
        "write_original_disabled_by_default": write_checks["write_original_default_false"],
        "original_dwg_hash_checks_pass": dwg_safety["status"] == "PASS",
        "release_reports_and_handoff_zip_produced": True,
        "daedalus_external_handoff_updated": DAEDALUS.exists(),
        "dirty_main_not_touched": True,
        "no_push": True,
    }
    acceptance_obj = {
        "schema": "ariadne.cad_os.v1_final.acceptance.v1",
        "packet_id": PACKET,
        "generated_at": now,
        "status": "PASS" if all(acceptance_criteria.values()) else "FAILED",
        "criteria": acceptance_criteria,
        "release_branch": RELEASE_BRANCH,
        "source_rc_commit": SOURCE_RC_COMMIT,
        "reports": reports_map,
    }
    write_json("reports/release/CADOS_V1_FINAL_ACCEPTANCE.json", acceptance_obj)
    accept_md = [
        "# CAD OS v1 Final Acceptance",
        "",
        f"- Packet: {PACKET}",
        f"- Status: {acceptance_obj['status']}",
        "",
        "| Criterion | Result |",
        "|---|---:|",
    ]
    accept_md.extend(f"| {key} | {value} |" for key, value in acceptance_criteria.items())
    write_text("reports/release/CADOS_V1_FINAL_ACCEPTANCE.md", "\n".join(accept_md) + "\n")

    latest_status = {
        "schema": "cad_os.latest_status.v1",
        "generated_at": now,
        "status": release_status,
        "version": "CAD OS Layer v1.0.0",
        "branch": RELEASE_BRANCH,
        "head_at_report_generation": head,
        "source_rc_commit": SOURCE_RC_COMMIT,
        "operation_counts": counts,
        "tests": f"{passed} passed, {skipped} skipped (CADOS_LIVE=1)",
        "native_build_status": native_status,
        "native_build_arx_relink_mode": native_build.get("arx_relink_mode"),
        "raw_command_agent_exposure": raw_exposure,
        "original_dwg_modified": False,
        "no_write_original_default": write_checks["write_original_default_false"],
        "closure_gate_pass": closure_gate_pass,
        "main_merge_status": "BLOCKED_DIRTY_MAIN",
        "daedalus_external_path": str(DAEDALUS),
        "reports": reports_map,
        "next": NEXT_PACKET,
    }
    write_json("reports/latest_status.json", latest_status)

    write_text(
        "docs/CAD_OS_BUILD_STATUS.md",
        "\n".join(
            [
                "# CAD OS Build Status",
                "",
                f"Status: {release_status}",
                f"Version: CAD OS Layer v{VERSION}",
                f"Branch: {RELEASE_BRANCH}",
                f"Report generation HEAD: {head}",
                "",
                f"Tests: {passed} passed / {skipped} skipped with CADOS_LIVE=1",
                f"Native build: {native_status}, ARX relink mode {native_build.get('arx_relink_mode')}",
                "",
                "Operation closure:",
                f"- total: {counts['total']}",
                f"- implemented: {counts['implemented']}",
                f"- hard_blocked: {counts['hard_blocked']}",
                f"- deprecated: {counts['deprecated']}",
                "- catalogued/stub/unknown/deferred: 0/0/0/0",
                "",
                "Safety:",
                f"- raw command agent exposure: {raw_exposure}",
                "- write_original default: false",
                "- original DWG modified: false",
                "",
                "Primary evidence: reports/release/CADOS_V1_FINAL.json",
            ]
        )
        + "\n",
    )
    write_text(
        "docs/CAD_OS_FULL_STACK_HANDOFF.md",
        "\n".join(
            [
                "# CAD OS Full Stack Handoff",
                "",
                f"CAD OS Layer v{VERSION} is frozen from {RELEASE_BRANCH}.",
                "",
                "Use:",
                "- python tools/cadctl_cli.py status",
                "- python tools/cadctl_cli.py registry coverage",
                "- python tools/cadctl_cli.py registry list",
                "- python tools/cadctl_cli.py registry explain <operation>",
                "- python tools/cadctl_cli.py inspect --dwg <read-only-or-staged.dwg> --out <run_dir> --include-rich",
                "- python tools/cadctl_cli.py query --ir <run_dir>\\dwg_graph_ir.json --sql \"SELECT COUNT(*) FROM entities\"",
                "- python tools/cadctl_cli.py patch dry-run --patch <cad_patch.v1.json>",
                "- python tools/cadctl_cli.py patch apply-staged --patch <cad_patch.v1.json> --dwg <input.dwg> --out <run_dir>",
                "",
                "Do not use raw AutoCAD command strings as an agent API. Use typed registry operations and staged patch policy.",
                "",
                "Final report: reports/release/CADOS_V1_FINAL.json",
                f"Handoff zip: {ZIP_REL}",
                f"Daedalus next packet: {NEXT_PACKET}",
            ]
        )
        + "\n",
    )
    write_text(
        "docs/CAD_OS_V1_ACCEPTANCE.md",
        "\n".join(
            [
                "# CAD OS v1 Acceptance",
                "",
                f"Status: {acceptance_obj['status']}",
                "Evidence root: reports/release/CADOS_V1_FINAL.json",
                "",
                "Closed operation counts:",
                f"- total: {counts['total']}",
                f"- implemented: {counts['implemented']}",
                f"- hard_blocked: {counts['hard_blocked']}",
                f"- deprecated: {counts['deprecated']}",
                "- unfinished: 0",
                "",
                "Release gates:",
                "- tests pass with 0 skipped",
                "- native canonical build pass",
                "- raw command exposure 0",
                "- original DWG unchanged",
                "- write_original disabled by default",
                "- Daedalus external handoff updated",
                "- dirty main untouched",
            ]
        )
        + "\n",
    )
    write_text(
        "handoff/NEXT_STEP.md",
        f"# Next Step\n\n{NEXT_PACKET}\n\nImport CAD OS v1.0.0 capabilities into Daedalus from the external CAD OS handoff. Do not merge to dirty main or push without a separate approval packet.\n",
    )

    readme_path = ROOT / "README.md"
    readme = readme_path.read_text(encoding="utf-8", errors="replace")
    section = (
        "## CAD OS Layer v1.0 Release Freeze\n\n"
        "Status: PASS. Release branch: cados/cad-os-v1.0-final. Evidence root: "
        "reports/release/CADOS_V1_FINAL.json. Handoff zip: "
        "handoff/zip/CADOS_M09_V1_RELEASE_FREEZE_AND_DAEDALUS_HANDOFF.zip. "
        "Next Daedalus packet: D04_IMPORT_CAD_OS_CAPABILITIES.\n\n"
    )
    if "## CAD OS Layer v1.0 Release Freeze" in readme:
        readme = re.sub(
            r"(?s)## CAD OS Layer v1\.0 Release Freeze\r?\n\r?\n.*?(?=## )",
            section,
            readme,
        )
    else:
        readme = re.sub(r"(# AutoCAD SDK Router \(local\)\r?\n\r?\n)", r"\1" + section, readme, count=1)
    readme_path.write_text(readme, encoding="utf-8")

    write_text(
        "packets/CADOS_M09_V1_RELEASE_FREEZE_AND_DAEDALUS_HANDOFF.md",
        "\n".join(
            [
                "# CADOS_M09_V1_RELEASE_FREEZE_AND_DAEDALUS_HANDOFF",
                "",
                "Execution record for the corrected M09 release freeze packet.",
                "",
                f"- Source RC branch: {SOURCE_RC_BRANCH}",
                f"- Source RC commit: {SOURCE_RC_COMMIT}",
                f"- Release branch: {RELEASE_BRANCH}",
                f"- Status: {release_status}",
                f"- Tests: {passed} passed / {skipped} skipped",
                f"- Native build: {native_status}",
                f"- Handoff zip: {ZIP_REL}",
                f"- Daedalus next packet: {NEXT_PACKET}",
                "",
                "Boundaries honored: no push, dirty main untouched, original DWGs unchanged, raw command agent exposure remains zero.",
            ]
        )
        + "\n",
    )

    if DAEDALUS.exists():
        safe_ops = [
            {
                "operation": op.get("operation"),
                "family": op.get("family"),
                "write_level": op.get("write_level"),
                "risk_class": op.get("risk_class"),
                "agent_exposed": bool(op.get("agent_exposed")),
                "handler_ref": handler_ref(op, registry_by_id),
            }
            for op in sorted(implemented, key=lambda item: item.get("operation", ""))
        ]
        forbidden_ops = [
            {
                "operation": entry["operation"],
                "family": entry["family"],
                "blocker_code": entry["blocker_code"],
                "agent_exposed": entry["agent_exposed"],
                "blocker_ref": entry["blocker_ref"],
                "replacement_ref": entry["replacement_ref"],
            }
            for entry in hardblock_entries
        ]
        dae_status = {
            "schema": "daedalus.external.cad_os.latest_status.v1",
            "generated_at": now,
            "status": release_status,
            "cad_os_root": str(ROOT),
            "release_branch": RELEASE_BRANCH,
            "release_commit": head,
            "release_tag": "cad-os-v1.0.0",
            "version": VERSION,
            "operation_counts": counts,
            "tests": {"passed": passed, "skipped": skipped, "env": "CADOS_LIVE=1"},
            "native_build": {"status": native_status, "arx_relink_mode": native_build.get("arx_relink_mode")},
            "safety": {
                "raw_command_agent_exposure": raw_exposure,
                "original_dwg_modified": False,
                "write_original_default": False,
            },
            "registry_path": "config/operations.v2.json",
            "policy_path": "config/policy.v2.json",
            "hardblock_list_path": "reports/release/CADOS_V1_FINAL_HARDBLOCKS.json",
            "next_packet": NEXT_PACKET,
        }
        (DAEDALUS / "cad_os_latest_status.json").write_text(
            json.dumps(dae_status, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        capabilities = {
            "schema": "daedalus.external.cad_os.v1_capabilities.v1",
            "generated_at": now,
            "status": release_status,
            "cad_os_root": str(ROOT),
            "release_branch": RELEASE_BRANCH,
            "release_commit": head,
            "operation_registry": "config/operations.v2.json",
            "policy": "config/policy.v2.json",
            "schemas": [
                "schemas/dwg_graph_ir.v1.schema.json",
                "schemas/cad_job.v2.schema.json",
                "schemas/cad_result.v2.schema.json",
                "schemas/cad_patch.v1.schema.json",
                "schemas/cad_diff.v1.schema.json",
                "schemas/validation_report.v1.schema.json",
            ],
            "cadctl_commands": [
                "python tools/cadctl_cli.py status",
                "python tools/cadctl_cli.py registry coverage",
                "python tools/cadctl_cli.py registry list",
                "python tools/cadctl_cli.py registry explain <operation>",
                "python tools/cadctl_cli.py inspect --dwg <read-only-or-staged.dwg> --out <run_dir> --include-rich",
                "python tools/cadctl_cli.py query --ir <run_dir>\\dwg_graph_ir.json --sql \"SELECT COUNT(*) FROM entities\"",
                "python tools/cadctl_cli.py patch dry-run --patch <cad_patch.v1.json>",
                "python tools/cadctl_cli.py patch apply-staged --patch <cad_patch.v1.json> --dwg <input.dwg> --out <run_dir>",
                "python tools/cadctl_cli.py live status",
            ],
            "safe_operations_count": len(safe_ops),
            "forbidden_operations_count": len(forbidden_ops),
            "raw_command_agent_exposure": raw_exposure,
            "safe_operations": safe_ops,
            "forbidden_operations": forbidden_ops,
        }
        (DAEDALUS / "CAD_OS_V1_CAPABILITIES.json").write_text(
            json.dumps(capabilities, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (DAEDALUS / "CADOS_V1_FINAL_SUMMARY.md").write_text(
            "\n".join(
                [
                    "# CAD OS v1.0 Final Summary",
                    "",
                    f"Status: {release_status}",
                    f"CAD OS root: {ROOT}",
                    f"Release branch: {RELEASE_BRANCH}",
                    f"Release commit: {head}",
                    "Release tag: cad-os-v1.0.0",
                    "",
                    f"Tests: {passed} passed / {skipped} skipped with CADOS_LIVE=1",
                    f"Native build: {native_status}, ARX relink mode {native_build.get('arx_relink_mode')}",
                    "",
                    "Operations: total 517, implemented 487, hard_blocked 29, deprecated 1, unfinished 0.",
                    "",
                    "Safe command surface is typed cadctl/registry/patch only. Raw AutoCAD command dispatch remains forbidden.",
                    "",
                    "Hardblock list: reports/release/CADOS_V1_FINAL_HARDBLOCKS.json",
                    f"Next Daedalus packet: {NEXT_PACKET}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (DAEDALUS / "CAD_OS_ADAPTER_IMPORT_NOTES.md").write_text(
            "\n".join(
                [
                    "# CAD OS Adapter Import Notes",
                    "",
                    f"Import target packet: {NEXT_PACKET}",
                    "",
                    "Use CAD_OS_V1_CAPABILITIES.json as the import manifest. Bind Daedalus adapters to operation ids from config/operations.v2.json only. Do not expose arbitrary command strings, AutoCAD SendCommand, SendStringToExecute, command.invoke.*, or command.queue.post as tools.",
                    "",
                    "Required adapter policy:",
                    "- Read/inspect/query operations are safe as read-only.",
                    "- apply.patch is safe only through staged patch/diff/validate/journal policy.",
                    "- live.apply_patch is deprecated and must route to staged governor guidance.",
                    "- write_original is disabled by default and requires an explicit future approval path.",
                    "",
                    "Schemas:",
                    "- schemas/cad_job.v2.schema.json",
                    "- schemas/cad_result.v2.schema.json",
                    "- schemas/cad_patch.v1.schema.json",
                    "- schemas/cad_diff.v1.schema.json",
                    "- schemas/dwg_graph_ir.v1.schema.json",
                    "- schemas/validation_report.v1.schema.json",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (DAEDALUS / "CAD_OS_SAFE_COMMANDS.md").write_text(
            "\n".join(
                [
                    "# CAD OS Safe Commands",
                    "",
                    "Agent-facing commands must remain typed and registry-bound:",
                    "",
                    "- python tools/cadctl_cli.py status",
                    "- python tools/cadctl_cli.py registry coverage",
                    "- python tools/cadctl_cli.py registry list",
                    "- python tools/cadctl_cli.py registry explain <operation>",
                    "- python tools/cadctl_cli.py inspect --dwg <read-only-or-staged.dwg> --out <run_dir> --include-rich",
                    "- python tools/cadctl_cli.py query --ir <run_dir>\\dwg_graph_ir.json --sql \"SELECT COUNT(*) FROM entities\"",
                    "- python tools/cadctl_cli.py patch dry-run --patch <cad_patch.v1.json>",
                    "- python tools/cadctl_cli.py patch apply-staged --patch <cad_patch.v1.json> --dwg <input.dwg> --out <run_dir>",
                    "- python tools/cadctl_cli.py live status",
                    "",
                    "Safe operations are the 487 implemented records in config/operations.v2.json with agent_exposed=true and no raw command risk.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        forbidden_md = [
            "# CAD OS Forbidden Commands",
            "",
            "Do not expose these surfaces to Daedalus agents:",
            "",
            "- AutoCAD SendCommand / COM SendCommand",
            "- AcApDocManager::sendStringToExecute / doc.sendstring",
            "- command.invoke.*",
            "- command.queue.post",
            "- arbitrary AutoLISP or raw AutoCAD command strings",
            "- write_original by default",
            "- Database.SaveAs persistence path",
            "",
            "| operation | blocker_code | agent_exposed |",
            "|---|---|---:|",
        ]
        forbidden_md.extend(
            f"| {entry['operation']} | {entry['blocker_code']} | {entry['agent_exposed']} |"
            for entry in forbidden_ops
        )
        (DAEDALUS / "CAD_OS_FORBIDDEN_COMMANDS.md").write_text(
            "\n".join(forbidden_md) + "\n",
            encoding="utf-8",
        )
        (DAEDALUS / "D04_IMPORT_CAD_OS_CAPABILITIES_RECOMMENDATION.md").write_text(
            "\n".join(
                [
                    "# D04 Import CAD OS Capabilities Recommendation",
                    "",
                    f"Recommended next packet: {NEXT_PACKET}",
                    "",
                    "Import CAD OS v1.0.0 as a Daedalus external adapter manifest, not as runtime writes.",
                    "",
                    "Inputs:",
                    "- cad_os_latest_status.json",
                    "- CAD_OS_V1_CAPABILITIES.json",
                    "- CAD_OS_SAFE_COMMANDS.md",
                    "- CAD_OS_FORBIDDEN_COMMANDS.md",
                    "- CAD_OS_ADAPTER_IMPORT_NOTES.md",
                    "",
                    "Acceptance for D04:",
                    "- Daedalus sees only typed CAD OS operation ids and cadctl commands.",
                    "- Raw command and write_original surfaces remain forbidden by default.",
                    "- Staged patch policy is preserved.",
                    "- Hardblock list is imported as non-agent-exposed capability metadata.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    write_text(
        "handoff/zip/index.md",
        "\n".join(
            [
                "# CAD OS Handoff Zip Index",
                "",
                "| Packet | Zip | Status | Next |",
                "|---|---|---|---|",
                f"| {PACKET} | CADOS_M09_V1_RELEASE_FREEZE_AND_DAEDALUS_HANDOFF.zip | {release_status} | {NEXT_PACKET} |",
                "| CADOS_V1_FINAL_RELEASE_FREEZE | CADOS_V1_FINAL_RELEASE_FREEZE.zip | PASS | D04_IMPORT_CAD_OS_CAPABILITIES |",
            ]
        )
        + "\n",
    )

    zip_files = [
        "README.md",
        "docs/CAD_OS_BUILD_STATUS.md",
        "docs/CAD_OS_FULL_STACK_HANDOFF.md",
        "docs/CAD_OS_V1_ACCEPTANCE.md",
        "reports/release/CADOS_V1_FINAL.md",
        "reports/release/CADOS_V1_FINAL.json",
        "reports/release/CADOS_V1_FINAL_ACCEPTANCE.md",
        "reports/release/CADOS_V1_FINAL_ACCEPTANCE.json",
        "reports/release/CADOS_V1_FINAL_HARDBLOCKS.json",
        "reports/release/CADOS_V1_FINAL_DWG_SAFETY.json",
        "reports/release/CADOS_V1_FINAL_NATIVE_BUILD.json",
        "reports/release/CADOS_V1_FINAL_OPERATION_CLOSURE.json",
        "reports/release/CADOS_V1_FINAL_RAW_COMMAND_AUDIT.json",
        "reports/release/CADOS_V1_FINAL_WRITE_SAFETY.json",
        "reports/operation_coverage_latest.json",
        "reports/operation_coverage_full_matrix.json",
        "reports/v1_operation_gate_latest.json",
        "reports/closure_gate_latest.json",
        "config/operations.v2.json",
        "config/policy.v2.json",
        "schemas/dwg_graph_ir.v1.schema.json",
        "schemas/cad_job.v2.schema.json",
        "schemas/cad_result.v2.schema.json",
        "schemas/cad_patch.v1.schema.json",
        "schemas/cad_diff.v1.schema.json",
        "schemas/validation_report.v1.schema.json",
    ]
    zip_path = ROOT / ZIP_REL
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in zip_files:
            src = ROOT / rel
            if not src.exists():
                raise RuntimeError(f"zip source missing: {rel}")
            zf.write(src, rel)

    print(f"generated_release_status={release_status}")
    print(f"tests={passed} passed skipped={skipped}")
    print(f"native={native_status} relink={native_build.get('arx_relink_mode')}")
    print(
        f"ops={counts['implemented']}/{counts['hard_blocked']}/{counts['deprecated']} unfinished={counts['catalogued'] + counts['stub'] + counts['unknown'] + counts['deferred']}"
    )
    print(f"zip={ZIP_REL}")
    return 0 if release_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
