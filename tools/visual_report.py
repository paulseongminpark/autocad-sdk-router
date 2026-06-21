#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visual_report.py -- Lane E visual verification shell for the CAD OS Layer.

Produces an ``ariadne.visual_artifact.v1`` envelope (conforms
``schemas/visual_artifact.v1.schema.json``) describing a derived visual/output
artifact (PNG / PDF / SVG / DXF / diff overlay) for a drawing or IR.

No-fake-success is the governing rule here: this shell NEVER fabricates a visual
PASS. It inspects the router-published status JSON (read-only) to decide whether
a SAFE, read-only render/export route is actually available:

  * If a usable render route exists AND is wired, it would route through it and
    return an ``ok`` artifact. (Today the registry op ``render.layout`` is
    ``blocked`` and there is no read-only raster render of a DWG wired, so this
    path is not taken -- see VISUAL_VERIFICATION_SPEC.md.)
  * Otherwise it returns a PLACEHOLDER artifact with status ``not_implemented``
    (or ``blocked`` when a route exists but is not available), with NO usable
    ``refs`` -- exactly the no-fake-success contract from the schema.

This module performs NO rendering and writes NO image files in this packet.

Hard rules: standard library ONLY; original DWG is a READ-ONLY ``source_ref``;
unavailable producer => explicit not_implemented/blocked, never ``ok``.

Public API:
    VISUAL_SCHEMA_ID
    available_render_routes() -> dict          # read-only status probe
    build_visual_report(source_ref, kind="png", artifact_id=None,
                        out_dir=None, route=None) -> dict   # visual_artifact.v1
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any, Dict, List, Optional

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)
_STATUS_JSON = os.path.join(_ROUTER_HOME, "reports", "autocad_router_status_latest.json")
_OPERATIONS_V2 = os.path.join(_ROUTER_HOME, "config", "operations.v2.json")
_JSON_ENCODING = "utf-8-sig"

VISUAL_SCHEMA_ID = "ariadne.visual_artifact.v1"

# Router routes that can, in principle, produce a visual/vector artifact and are
# SAFE (read-only with respect to the source). Probed against the live status.
_VISUAL_CANDIDATE_ROUTES = (
    "pdf_svg_vector_route",   # PDF/SVG vector extraction + overlay
    "raster_compare_route",   # PNG render comparison (consumes existing renders)
)

# Which artifact kinds each candidate route is competent to emit. Used to decide
# whether a *requested* kind is satisfiable by an available route.
_ROUTE_KINDS = {
    "pdf_svg_vector_route": {"svg", "pdf", "diff_overlay"},
    "raster_compare_route": {"png", "jpg", "diff_overlay"},
}


def _load_json(path: str) -> Optional[Any]:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding=_JSON_ENCODING) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def available_render_routes() -> Dict[str, Any]:
    """
    Read the router-published status JSON (read-only) and report which visual
    candidate routes are available. Also reports the registry status of the DWG
    layout render op (render.layout), which gates native DWG rendering.

    Returns:
      {
        "status_json": <path or None>,
        "status_readable": bool,
        "routes": { route_id: {"available": bool, "kinds": [...]} , ... },
        "render_layout_status": <registry status or None>,
        "any_available": bool
      }
    """
    status = _load_json(_STATUS_JSON)
    out: Dict[str, Any] = {
        "status_json": _STATUS_JSON if os.path.isfile(_STATUS_JSON) else None,
        "status_readable": status is not None,
        "routes": {},
        "render_layout_status": None,
        "any_available": False,
    }

    avail_by_route: Dict[str, bool] = {}
    if isinstance(status, dict):
        for r in status.get("routes", []):
            if isinstance(r, dict) and r.get("route"):
                avail_by_route[r["route"]] = bool(r.get("available"))

    for route_id in _VISUAL_CANDIDATE_ROUTES:
        avail = avail_by_route.get(route_id, False)
        out["routes"][route_id] = {
            "available": avail,
            "kinds": sorted(_ROUTE_KINDS.get(route_id, set())),
        }
        if avail:
            out["any_available"] = True

    reg = _load_json(_OPERATIONS_V2)
    if isinstance(reg, dict):
        for o in reg.get("operations", []):
            if isinstance(o, dict) and o.get("id") == "render.layout":
                out["render_layout_status"] = o.get("status")
                break

    return out


def _route_for_kind(kind: str, probe: Dict[str, Any],
                    forced_route: Optional[str]) -> Optional[str]:
    """Pick an AVAILABLE route competent for the requested kind, or None."""
    candidates = ([forced_route] if forced_route else list(_VISUAL_CANDIDATE_ROUTES))
    for route_id in candidates:
        info = probe["routes"].get(route_id)
        if not info or not info.get("available"):
            continue
        if kind in _ROUTE_KINDS.get(route_id, set()):
            return route_id
    return None


def build_visual_report(source_ref: str,
                        kind: str = "png",
                        artifact_id: Optional[str] = None,
                        out_dir: Optional[str] = None,
                        route: Optional[str] = None) -> Dict[str, Any]:
    """
    Build a visual_artifact.v1 envelope for a requested artifact derived from
    ``source_ref`` (a DWG/IR path -- treated as a READ-ONLY provenance ref).

    This shell does NOT render in this packet. It decides truthfully:
      * If no available route can emit ``kind``  -> status ``not_implemented``.
      * If a route exists but is unavailable      -> status ``blocked``.
      * (An ``ok`` path is wired in code but only taken when a real producer
        exists; today no such producer is wired, so ``ok`` is never returned.)

    ``refs`` is always empty when status != ok (no-fake-success).
    """
    probe = available_render_routes()
    aid = artifact_id or "vis-%s" % uuid.uuid4().hex[:12]

    valid_kinds = {"png", "jpg", "svg", "pdf", "dxf", "dwg_staged", "ir_json",
                   "extract_json", "diff_json", "diff_overlay", "thumbnail",
                   "log", "json", "other"}
    if kind not in valid_kinds:
        return {
            "schema": VISUAL_SCHEMA_ID, "artifact_id": aid, "kind": "other",
            "status": "error", "source_ref": source_ref, "refs": [],
            "diagnostics": {"warnings": ["unknown artifact kind: %s" % kind]},
        }

    chosen = _route_for_kind(kind, probe, route)

    if chosen is not None:
        # A real producer would run here and populate refs. No producer is wired
        # in this packet, so we DO NOT claim ok -- we report not_implemented with
        # the route that *would* have been used, preserving no-fake-success.
        return {
            "schema": VISUAL_SCHEMA_ID,
            "artifact_id": aid,
            "kind": kind,
            "status": "not_implemented",
            "source_ref": source_ref,
            "route": chosen,
            "refs": [],
            "diagnostics": {
                "warnings": [
                    "route '%s' is available and competent for kind '%s', but the "
                    "visual producer is not implemented in this packet" % (chosen, kind),
                ],
            },
            "notes": "render producer not_implemented; no artifact written",
        }

    # No available+competent route. Distinguish blocked (route exists but down)
    # from not_implemented (no route competent for this kind at all).
    route_exists_but_unavailable = any(
        kind in _ROUTE_KINDS.get(rid, set()) and not probe["routes"].get(rid, {}).get("available", False)
        for rid in _VISUAL_CANDIDATE_ROUTES
    )
    status = "blocked" if route_exists_but_unavailable else "not_implemented"
    warn = ("a route competent for kind '%s' exists but is unavailable" % kind
            if status == "blocked"
            else "no wired route can produce kind '%s' for a DWG/IR source" % kind)

    report: Dict[str, Any] = {
        "schema": VISUAL_SCHEMA_ID,
        "artifact_id": aid,
        "kind": kind,
        "status": status,
        "source_ref": source_ref,
        "refs": [],
        "diagnostics": {
            "warnings": [warn],
        },
        "probe": {
            "any_route_available": probe["any_available"],
            "render_layout_status": probe["render_layout_status"],
            "routes": probe["routes"],
        },
    }
    if out_dir:
        report["diagnostics"]["warnings"].append(
            "out_dir=%s supplied but nothing was written (no producer)" % out_dir)
    return report


# --------------------------------------------------------------------------- #
# Self-test (__main__): emit a sample visual_artifact envelope
# --------------------------------------------------------------------------- #

def _selftest() -> int:
    sample_source = os.path.join(_ROUTER_HOME, "staging", "golden", "demo", "input.dwg")
    report = build_visual_report(sample_source, kind="png")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # Contract: envelope is schema-valid in shape, and NEVER claims ok here.
    ok = (
        report["schema"] == VISUAL_SCHEMA_ID
        and report["status"] in ("not_implemented", "blocked")
        and report["refs"] == []
        and isinstance(report["artifact_id"], str)
    )
    # Also exercise the route probe directly.
    probe = available_render_routes()
    print("SELFTEST_OK" if ok else "SELFTEST_FAIL",
          "| status=%s refs=%d | render_layout=%s any_route=%s"
          % (report["status"], len(report["refs"]),
             probe["render_layout_status"], probe["any_available"]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_selftest())
