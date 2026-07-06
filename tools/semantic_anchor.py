#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""semantic_anchor.py -- read-only semantic-anchor census over extracted IR.

WHY:
  * Wave 5's anchor_ops module reads and writes the ARIADNE_ANCHOR envelope for
    one known app. This module is the broader semantic READ view: scan an
    already-extracted dwg_graph_ir.v1 document (or one entity dict) and surface
    all XDATA / extension-dictionary payloads as a clean per-entity map without
    touching AutoCAD or a DWG.
  * The result is truthful and read-only. If an entity has no XDATA/xdict, it is
    simply absent from the anchors map; if the whole input has none, callers get
    an honest empty-but-ok result.
"""
from __future__ import annotations

from typing import Any, Dict, List


def _as_entities(ir: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(ir.get("entities"), list):
        return [ent for ent in ir["entities"] if isinstance(ent, dict)]
    if isinstance(ir, dict):
        return [ir]
    return []


def _item_value(item: Any) -> Any:
    if isinstance(item, dict) and "value" in item:
        return item.get("value")
    return item


def _item_key(item: Any) -> Any:
    if not isinstance(item, dict):
        return None
    key = item.get("key")
    if isinstance(key, str) and key:
        return key
    value = item.get("value")
    if isinstance(value, str) and value:
        return value
    return None


def _normalize_items(items: Any) -> Any:
    if not isinstance(items, list) or not items:
        return []

    can_pair = len(items) % 2 == 0
    if can_pair:
        mapping: Dict[str, Any] = {}
        for idx in range(0, len(items), 2):
            key = _item_key(items[idx])
            if not isinstance(key, str) or not key:
                can_pair = False
                break
            mapping[key] = _item_value(items[idx + 1])
        if can_pair:
            return mapping

    return [_item_value(item) for item in items]


def _extension_dicts_by_owner(ir: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for block in ir.get("extension_dictionaries") or []:
        if not isinstance(block, dict):
            continue
        owner = block.get("owner_handle")
        if not isinstance(owner, str) or not owner:
            continue
        out.setdefault(owner, []).append(block)
    return out


def _xrecords_by_handle(ir: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for xrecord in ir.get("xrecords") or []:
        if not isinstance(xrecord, dict):
            continue
        handle = xrecord.get("handle")
        if isinstance(handle, str) and handle:
            out[handle] = xrecord
    return out


def read_semantic_anchors(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Return a normalized semantic-anchor census for an IR or one entity."""
    entities = _as_entities(ir if isinstance(ir, dict) else {})
    xdicts_by_owner = _extension_dicts_by_owner(ir if isinstance(ir, dict) else {})
    xrecords = _xrecords_by_handle(ir if isinstance(ir, dict) else {})

    anchors: Dict[str, Dict[str, Any]] = {}
    appids_seen: List[str] = []

    for entity in entities:
        handle = entity.get("handle")
        if not isinstance(handle, str) or not handle:
            continue

        entity_anchors: Dict[str, Any] = {}

        for block in entity.get("xdata") or []:
            if not isinstance(block, dict):
                continue
            appid = block.get("app")
            if not isinstance(appid, str) or not appid:
                continue
            entity_anchors[appid] = _normalize_items(block.get("items"))
            if appid not in appids_seen:
                appids_seen.append(appid)

        for block in xdicts_by_owner.get(handle, []):
            for entry in block.get("entries") or []:
                if not isinstance(entry, dict):
                    continue
                appid = entry.get("key")
                value_handle = entry.get("value_handle")
                if not isinstance(appid, str) or not appid:
                    continue
                xrecord = xrecords.get(value_handle) if isinstance(value_handle, str) else None
                items = xrecord.get("items") if isinstance(xrecord, dict) else None
                entity_anchors[appid] = _normalize_items(items)
                if appid not in appids_seen:
                    appids_seen.append(appid)

        if entity_anchors:
            anchors[handle] = entity_anchors

    return {
        "ok": True,
        "anchors": anchors,
        "appids_seen": appids_seen,
        "summary": {
            "entities_with_anchors": len(anchors),
            "total_anchors": sum(len(apps) for apps in anchors.values()),
        },
    }
