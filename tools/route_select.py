#!/usr/bin/env python
"""route_select.py -- thin, read-only intent/operation -> router-route mapper.

Lane B1 (cadctl control surface) helper for the CAD OS Layer.

This module does NOT run the router. It only reads the v2 config files
(config/operations.v2.json + config/capabilities.v2.json) and the v1
capabilities (config/autocad_router_capabilities.json, for the intent_aliases /
intents / fallback_to chain) to answer: "given an operation id or a free-text
intent, which router route should carry it, and what is its fallback chain?".

All reads use encoding="utf-8-sig" because the JSON on this box is BOM-prefixed.
Standard library only.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROUTER_HOME = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROUTER_HOME / "config"

OPERATIONS_V2 = CONFIG_DIR / "operations.v2.json"
CAPABILITIES_V2 = CONFIG_DIR / "capabilities.v2.json"
CAPABILITIES_V1 = CONFIG_DIR / "autocad_router_capabilities.json"

# Operation id prefix (family) -> the canonical DWG route. Every catalogued CAD
# operation in operations.v2.json is a DWG control-plane op, so they all route to
# dwg_truth_autocad; this map exists so a caller can still reason about it
# explicitly rather than hard-coding the string.
_DWG_ROUTE = "dwg_truth_autocad"


def _load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def load_operations() -> dict:
    return _load_json(OPERATIONS_V2)


def load_capabilities_v2() -> dict:
    return _load_json(CAPABILITIES_V2)


def load_capabilities_v1() -> dict:
    return _load_json(CAPABILITIES_V1)


def _v1_route_record(caps_v1: dict, route_id: str) -> dict | None:
    for rec in caps_v1.get("routes", []):
        if rec.get("id") == route_id:
            return rec
    return None


def _fallback_chain(caps_v1: dict, route_id: str) -> list[str]:
    rec = _v1_route_record(caps_v1, route_id)
    if rec:
        return list(rec.get("fallback_to", []) or [])
    return []


def operation_route(operation_id: str) -> dict:
    """Map an operations.v2.json operation id -> its router route.

    Returns {operation, found, route, family, status, engine_tier, router_lane,
             execution_host_class, fallback_chain}.
    'found' is False (and route None) when the operation id is not catalogued.
    """
    ops = load_operations()
    caps_v1 = load_capabilities_v1()
    match = None
    for op in ops.get("operations", []):
        if op.get("id") == operation_id:
            match = op
            break
    if match is None:
        return {
            "operation": operation_id,
            "found": False,
            "route": None,
            "reason": "operation id not present in operations.v2.json",
        }
    handler = match.get("handler") or {}
    return {
        "operation": operation_id,
        "found": True,
        "route": _DWG_ROUTE,
        "family": match.get("family"),
        "status": match.get("status"),
        "engine_tier": match.get("engine_tier"),
        "router_lane": handler.get("router_lane"),
        "execution_host_class": handler.get("execution_host_class"),
        "fallback_chain": _fallback_chain(caps_v1, _DWG_ROUTE),
    }


def intent_route(intent: str) -> dict:
    """Map a free-text intent (e.g. 'dwg', 'dxf', 'step') -> a router route.

    Mirrors the router's Resolve-IntentToRoute precedence using the v1 config:
      1. intent_aliases[intent]
      2. literal route id
      3. any route whose intents[] contains the intent
    Returns {intent, found, route, fallback_chain, reason}.
    """
    caps_v1 = load_capabilities_v1()
    key = (intent or "").strip().lower()

    aliases = caps_v1.get("intent_aliases", {}) or {}
    if key in aliases:
        route = aliases[key]
        return {
            "intent": intent,
            "found": True,
            "route": route,
            "via": "intent_alias",
            "fallback_chain": _fallback_chain(caps_v1, route),
        }

    for rec in caps_v1.get("routes", []):
        if rec.get("id") == key:
            return {
                "intent": intent,
                "found": True,
                "route": rec["id"],
                "via": "literal_route_id",
                "fallback_chain": _fallback_chain(caps_v1, rec["id"]),
            }

    for rec in caps_v1.get("routes", []):
        intents = [str(x).lower() for x in (rec.get("intents") or [])]
        if key in intents:
            return {
                "intent": intent,
                "found": True,
                "route": rec["id"],
                "via": "route_intents",
                "fallback_chain": _fallback_chain(caps_v1, rec["id"]),
            }

    return {
        "intent": intent,
        "found": False,
        "route": None,
        "reason": "intent does not map to any route via aliases, id, or intents",
    }


def capability_routes(capability: str) -> dict:
    """Reverse-index a capability token -> ordered routes (capabilities.v2.json)."""
    caps_v2 = load_capabilities_v2()
    table = caps_v2.get("capability_to_routes", {}) or {}
    routes = table.get(capability)
    return {
        "capability": capability,
        "found": routes is not None,
        "routes": list(routes) if routes else [],
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="route_select: intent/operation -> route (read-only)")
    ap.add_argument("--intent")
    ap.add_argument("--operation")
    ap.add_argument("--capability")
    args = ap.parse_args()
    if args.operation:
        print(json.dumps(operation_route(args.operation), ensure_ascii=False, indent=2))
    elif args.capability:
        print(json.dumps(capability_routes(args.capability), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(intent_route(args.intent or "dwg"), ensure_ascii=False, indent=2))
