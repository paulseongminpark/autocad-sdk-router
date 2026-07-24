"""XDATA replay op synthesis for IR -> patch Pass B."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


REGAPP_OP = "write.regapp.register"
XDATA_OP = "modify.entity.xdata"

REASON_DANGLING_1005 = "dangling 1005 handle"
REASON_BINARY_1004 = "binary xdata excluded by design"
REASON_UNBALANCED_1002 = "unbalanced 1002 braces"
REASON_LONG_STRING = "string xdata exceeds 255 chars"
REASON_TARGET_HANDLE = "target handle not remapped"
REASON_EMPTY_GROUP = "no replayable xdata rows"
REASON_MISSING_APP = "missing xdata app"


def _rows_for(group: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = group.get("rows")
    if rows is None:
        rows = group.get("items")
    return rows if isinstance(rows, list) else []


def _brace_balance_ok(rows: List[Dict[str, Any]]) -> bool:
    depth = 0
    for row in rows:
        if not isinstance(row, dict) or row.get("code") != 1002:
            continue
        value = row.get("value")
        if value == "{":
            depth += 1
        elif value == "}":
            depth -= 1
            if depth < 0:
                return False
        else:
            return False
    return depth == 0


def _defer_group(entity_index: int, old_handle: Any, group_index: int,
                 app: Any, reason: str) -> Dict[str, Any]:
    return {
        "index": entity_index,
        "handle": old_handle,
        "xdata_index": group_index,
        "app": app,
        "reason": reason,
    }


def _defer_row(entity_index: int, old_handle: Any, group_index: int,
               app: str, row_index: int, row: Dict[str, Any],
               reason: str) -> Dict[str, Any]:
    return {
        "index": entity_index,
        "handle": old_handle,
        "xdata_index": group_index,
        "app": app,
        "row_index": row_index,
        "code": row.get("code"),
        "value": row.get("value"),
        "reason": reason,
    }


def build_xdata_ops(ir_doc: Dict[str, Any],
                    handle_map: Dict[Any, Any]) -> Tuple[List[Dict[str, Any]],
                                                         List[Dict[str, Any]]]:
    """Build Pass B RegApp/XDATA ops from extracted per-entity xdata.

    ``handle_map`` is the only source of target handles. Source handles are
    never emitted verbatim for either the xdata target or 1005 soft pointers.
    """
    ops: List[Dict[str, Any]] = []
    deferred: List[Dict[str, Any]] = []
    app_names: List[str] = []
    seen_apps = set()
    groups: List[Tuple[int, Dict[str, Any], int, Dict[str, Any], str]] = []

    for entity_index, ent in enumerate(ir_doc.get("entities") or []):
        if not isinstance(ent, dict):
            continue
        for group_index, group in enumerate(ent.get("xdata") or []):
            if not isinstance(group, dict):
                continue
            app = group.get("app")
            if not isinstance(app, str) or not app:
                deferred.append(_defer_group(
                    entity_index, ent.get("handle"), group_index, app,
                    REASON_MISSING_APP))
                continue
            if app not in seen_apps:
                seen_apps.add(app)
                app_names.append(app)
            groups.append((entity_index, ent, group_index, group, app))

    for app in app_names:
        ops.append({"operation": REGAPP_OP, "args": {"app": app}})

    for entity_index, ent, group_index, group, app in groups:
        old_handle = ent.get("handle")
        target_handle = handle_map.get(old_handle)
        if not target_handle:
            deferred.append(_defer_group(
                entity_index, old_handle, group_index, app,
                REASON_TARGET_HANDLE))
            continue

        rows = _rows_for(group)
        if not _brace_balance_ok(rows):
            deferred.append(_defer_group(
                entity_index, old_handle, group_index, app,
                REASON_UNBALANCED_1002))
            continue

        out_rows: List[Dict[str, Any]] = []
        for row_index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            code = row.get("code")
            if code == 1004:
                deferred.append(_defer_row(
                    entity_index, old_handle, group_index, app, row_index,
                    row, REASON_BINARY_1004))
                continue

            out_row = dict(row)
            if code == 1005:
                source_ref = row.get("value")
                mapped_ref = handle_map.get(source_ref)
                if not mapped_ref:
                    deferred.append(_defer_row(
                        entity_index, old_handle, group_index, app, row_index,
                        row, REASON_DANGLING_1005))
                    continue
                out_row["value"] = mapped_ref

            if isinstance(out_row.get("value"), str) and len(out_row["value"]) > 255:
                deferred.append(_defer_row(
                    entity_index, old_handle, group_index, app, row_index,
                    out_row, REASON_LONG_STRING))
                continue

            out_rows.append(out_row)

        if not out_rows:
            deferred.append(_defer_group(
                entity_index, old_handle, group_index, app,
                REASON_EMPTY_GROUP))
            continue

        ops.append({
            "operation": XDATA_OP,
            "args": {
                "handle": target_handle,
                "app_name": app,
                "values": out_rows,
            },
        })

    return ops, deferred
