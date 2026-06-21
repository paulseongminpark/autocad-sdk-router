#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visual_report.py -- Lane E visual verification for the CAD OS Layer.

Produces an ``ariadne.visual_artifact.v1`` envelope (conforms
``schemas/visual_artifact.v1.schema.json``) describing a derived visual/output
artifact (PNG / PDF / SVG / DXF / diff overlay) for a drawing or IR.

No-fake-success is the governing rule: this module NEVER fabricates a visual
PASS. A claimed visual ``ok`` REQUIRES a real artifact file on disk. When a
render cannot be produced, the envelope records ``not_implemented`` / ``blocked``
with NO usable ``refs``.

What changed in M02 (this lane)
-------------------------------
Earlier this module was a pure *shell* that only read the router status JSON and
always returned ``not_implemented``. It now ATTEMPTS a real render and reports
honestly:

  * ``available_render_routes()`` probes, in addition to the two safe vector/
    compare candidate routes, two genuine DWG render paths:
      - ``accoreconsole_plot``  -- drive accoreconsole headless with a staged
        copy + a ``-PLOT`` script to "DWG To PDF.pc3". Reported ``attemptable``
        when the engine exists, with the empirically-observed caveat that this
        Core Console host does NOT reliably emit a file on this box (see below).
      - ``full_autocad_com``    -- full AutoCAD (acad.exe) running -> its COM
        ``AcadApplication`` exposes ``Plot.PlotToFile`` (Core Console does not).
        A genuine render route, but it touches the LIVE user session, so it is
        GATED behind an explicit ``allow_full_autocad=True`` opt-in and is never
        driven silently.

  * ``build_visual_report(source_ref, kind=...)`` for a raster/pdf kind will, by
    default, ACTUALLY RUN the accoreconsole staged-copy plot attempt (real
    subprocess; stdout/stderr/exit captured into the run dir; original DWG never
    touched -- only a ``shutil.copy2`` staged copy is written/plotted). If a real
    output file appears it returns ``status="ok"`` with populated ``refs``
    (path + byte_size + sha256). If no file appears it returns
    ``not_implemented`` with the captured evidence paths and an explicit reason.

Empirical finding on THIS machine (accoreconsole 2027, kor locale)
------------------------------------------------------------------
Three headless render paths were probed against the golden staged copy:
  * ``EXPORTPDF`` / ``-EXPORTPDF``  -> Unknown command in Core Console.
  * ``-PLOT`` prompt-chain          -> command + device + paper accepted, but the
    post-paper keyword prompts desync under the Korean locale / version-specific
    prompt order, so no PDF is emitted.
  * AutoLISP COM ``PlotToFile``     -> ``vlax-get-acad-object`` returns nil
    (Core Console has no ActiveX automation server), so COM plotting is impossible
    from accoreconsole.
=> From Core Console alone a reliable read-only DWG->PDF/PNG render is NOT
   achievable here; ``build_visual_report`` therefore attempts, captures
   evidence, and returns ``not_implemented`` (NO fake artifact). A real artifact
   requires full AutoCAD COM (``allow_full_autocad=True`` while acad.exe runs) or
   a native PlotEngine ARX module (out of this lane's scope).

Hard rules: standard library ONLY; original DWG is a READ-ONLY ``source_ref``;
unavailable / unproduced producer => explicit not_implemented/blocked, never
``ok``; every external command's stdout+stderr+exit captured into the run dir.

Public API (signatures preserved):
    VISUAL_SCHEMA_ID
    available_render_routes() -> dict
    build_visual_report(source_ref, kind="png", artifact_id=None,
                        out_dir=None, route=None, *,
                        attempt_render=True, allow_full_autocad=False,
                        timeout=180) -> dict   # visual_artifact.v1
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)
_STATUS_JSON = os.path.join(_ROUTER_HOME, "reports", "autocad_router_status_latest.json")
_OPERATIONS_V2 = os.path.join(_ROUTER_HOME, "config", "operations.v2.json")
_CAPABILITIES = os.path.join(_ROUTER_HOME, "config", "autocad_router_capabilities.json")
_RUNS_DIR = os.path.join(_ROUTER_HOME, "runs")
_STAGING_DIR = os.path.join(_ROUTER_HOME, "staging")
_JSON_ENCODING = "utf-8-sig"

VISUAL_SCHEMA_ID = "ariadne.visual_artifact.v1"

# Default headless plotter device. "DWG To PDF.pc3" ships with AutoCAD and was
# confirmed present on this box (kor profile). Output is a PDF.
_PLOT_DEVICE = "DWG To PDF.pc3"
_PLOT_PAPER = "ANSI A (8.50 x 11.00 Inches)"

# Router routes that can, in principle, produce a visual/vector artifact and are
# SAFE (read-only with respect to the source). Probed against the live status.
_VISUAL_CANDIDATE_ROUTES = (
    "pdf_svg_vector_route",   # PDF/SVG vector extraction + overlay
    "raster_compare_route",   # PNG render comparison (consumes existing renders)
)

# Which artifact kinds each candidate route is competent to emit.
_ROUTE_KINDS = {
    "pdf_svg_vector_route": {"svg", "pdf", "diff_overlay"},
    "raster_compare_route": {"png", "jpg", "diff_overlay"},
}

# Render routes that genuinely turn a DWG into an image/pdf (distinct from the
# vector/compare candidate routes above). Kinds they can emit.
_RENDER_ROUTE_KINDS = {
    "accoreconsole_plot": {"pdf"},
    "full_autocad_com": {"pdf"},
}


# --------------------------------------------------------------------------- #
# small stdlib helpers
# --------------------------------------------------------------------------- #

def _load_json(path: str) -> Optional[Any]:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding=_JSON_ENCODING) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _sha256(path: str) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _accoreconsole_engine() -> Optional[str]:
    """Read the DWG route's engine_path from capabilities (read-only). Returns
    the accoreconsole exe path if it exists on disk, else None."""
    caps = _load_json(_CAPABILITIES)
    engine = None
    if isinstance(caps, dict):
        for r in caps.get("routes", []):
            if isinstance(r, dict) and r.get("id") == "dwg_truth_autocad":
                engine = r.get("engine_path")
                break
    if engine and os.path.isfile(engine):
        return engine
    return None


def _full_autocad_running() -> bool:
    """True if a full AutoCAD process (acad.exe) is running. Pure stdlib via
    `tasklist` (Windows). Read-only; touches nothing."""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq acad.exe", "/NH"],
            capture_output=True, text=True, timeout=15,
        )
        return "acad.exe" in (out.stdout or "")
    except (OSError, subprocess.SubprocessError):
        return False


def available_render_routes() -> Dict[str, Any]:
    """
    Read-only probe of which visual/render routes are available.

    Reports:
      * the two SAFE vector/compare candidate routes (from the router status
        JSON): ``pdf_svg_vector_route`` and ``raster_compare_route``;
      * the registry status of ``render.layout`` (gates native DWG rendering);
      * two genuine DWG render routes:
          - ``accoreconsole_plot``: ``attemptable`` when the engine exists.
            NOTE ``verified=False`` -- on this box Core Console does not reliably
            emit a PDF (EXPORTPDF unknown; -PLOT prompt desync; no COM). The
            attempt still runs in ``build_visual_report`` and reports honestly.
          - ``full_autocad_com``: ``available`` when acad.exe is running (real
            COM PlotToFile route), but ``gated=True`` -- only driven with an
            explicit ``allow_full_autocad=True`` opt-in (it touches the live
            user session), so ``attemptable`` stays False unless opted in.

    Returns:
      {
        "status_json": <path or None>, "status_readable": bool,
        "routes": { route_id: {"available": bool, "kinds": [...]} , ... },
        "render_layout_status": <registry status or None>,
        "any_available": bool,                 # any safe candidate route up
        "render_routes": { "accoreconsole_plot": {...}, "full_autocad_com": {...} },
        "any_render_attemptable": bool         # any DWG->image route we may try
      }
    """
    status = _load_json(_STATUS_JSON)
    out: Dict[str, Any] = {
        "status_json": _STATUS_JSON if os.path.isfile(_STATUS_JSON) else None,
        "status_readable": status is not None,
        "routes": {},
        "render_layout_status": None,
        "any_available": False,
        "render_routes": {},
        "any_render_attemptable": False,
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

    # ---- genuine DWG render routes -----------------------------------------
    engine = _accoreconsole_engine()
    out["render_routes"]["accoreconsole_plot"] = {
        "engine": engine,
        "engine_present": engine is not None,
        # We can ATTEMPT it whenever the engine exists; we do NOT claim it is
        # verified to produce a file on this host (empirically it does not).
        "attemptable": engine is not None,
        "verified": False,
        "kinds": sorted(_RENDER_ROUTE_KINDS["accoreconsole_plot"]),
        "device": _PLOT_DEVICE,
        "note": ("accoreconsole headless -PLOT to PDF; on this box it does not "
                 "reliably emit a file (EXPORTPDF unknown / -PLOT prompt desync "
                 "under kor locale / no ActiveX COM in Core Console)."),
    }

    acad_up = _full_autocad_running()
    out["render_routes"]["full_autocad_com"] = {
        "acad_running": acad_up,
        # A real route, but gated: only attempted with allow_full_autocad=True,
        # because it drives the user's live AutoCAD session.
        "available": acad_up,
        "gated": True,
        "attemptable": False,  # never auto-attempted; opt-in only
        "kinds": sorted(_RENDER_ROUTE_KINDS["full_autocad_com"]),
        "note": ("full AutoCAD COM Plot.PlotToFile; touches the live session, so "
                 "only driven with explicit allow_full_autocad=True."),
    }

    out["any_render_attemptable"] = bool(
        out["render_routes"]["accoreconsole_plot"]["attemptable"]
    )
    return out


def _route_for_kind(kind: str, probe: Dict[str, Any],
                    forced_route: Optional[str]) -> Optional[str]:
    """Pick an AVAILABLE *candidate* (vector/compare) route competent for the
    requested kind, or None. (Render routes are handled separately.)"""
    candidates = ([forced_route] if forced_route else list(_VISUAL_CANDIDATE_ROUTES))
    for route_id in candidates:
        info = probe["routes"].get(route_id)
        if not info or not info.get("available"):
            continue
        if kind in _ROUTE_KINDS.get(route_id, set()):
            return route_id
    return None


# --------------------------------------------------------------------------- #
# Real render attempt: accoreconsole headless -PLOT on a STAGED COPY
# --------------------------------------------------------------------------- #

def _stage_copy(source_dwg: str, run_dir: str) -> str:
    """Copy the source DWG into run_dir as a writable staged copy. The ORIGINAL
    is never written. Returns the staged copy path."""
    os.makedirs(run_dir, exist_ok=True)
    staged = os.path.join(run_dir, "input.dwg")
    shutil.copy2(source_dwg, staged)
    try:
        os.chmod(staged, 0o666)
    except OSError:
        pass
    return staged


def _write_plot_scr(scr_path: str, out_pdf_fwd: str) -> None:
    """Write a headless -PLOT script targeting DWG To PDF.pc3 -> a PDF file.

    Prompt-chain note: this is the canonical detailed -PLOT sequence. It is known
    to be locale-fragile (see module docstring); we write it, run it, and let the
    caller verify the output file truthfully rather than trust the exit code.
    """
    lines = [
        "FILEDIA", "0", "CMDECHO", "0", "BACKGROUNDPLOT", "0",
        "-PLOT",
        "Y",                 # Detailed plot configuration? Yes
        "",                  # layout (current)
        _PLOT_DEVICE,        # output device
        _PLOT_PAPER,         # paper size
        "N",                 # plot upside down? No
        "E",                 # plot area: Extents
        "Y",                 # fit to paper? Yes
        "C",                 # center the plot
        "Y",                 # plot with plot styles? Yes
        "",                  # plot style table name (none)
        "Y",                 # plot with lineweights? Yes
        "N",                 # plot paperspace last? No
        "N",                 # hide paperspace objects? No
        out_pdf_fwd,         # output file
        "N",                 # save changes to page setup? No
        "Y",                 # proceed with plot? Yes
        "QUIT", "",
    ]
    with open(scr_path, "w", encoding="ascii", newline="\n") as fh:
        fh.write("\n".join(lines))


def _attempt_accoreconsole_plot(source_dwg: str, run_dir: str,
                                timeout: int) -> Dict[str, Any]:
    """
    REAL attempt: stage a copy of ``source_dwg``, drive accoreconsole headless
    with a -PLOT script to a PDF under ``run_dir``. Capture stdout/stderr/exit.

    Returns a dict:
      {"produced": bool, "pdf_path": str|None, "exit_code": int|None,
       "stdout_path": str, "stderr_path": str, "scr_path": str,
       "staged_dwg": str, "timed_out": bool, "reason": str}
    NEVER raises for an expected failure; reports it.
    """
    res: Dict[str, Any] = {
        "produced": False, "pdf_path": None, "exit_code": None,
        "stdout_path": "", "stderr_path": "", "scr_path": "",
        "staged_dwg": "", "timed_out": False, "reason": "",
    }
    engine = _accoreconsole_engine()
    if engine is None:
        res["reason"] = "accoreconsole engine not present"
        return res

    os.makedirs(run_dir, exist_ok=True)
    staged = _stage_copy(source_dwg, run_dir)
    res["staged_dwg"] = staged

    out_pdf = os.path.join(run_dir, "out.pdf")
    out_pdf_fwd = out_pdf.replace("\\", "/")
    scr_path = os.path.join(run_dir, "plot.scr")
    _write_plot_scr(scr_path, out_pdf_fwd)
    res["scr_path"] = scr_path

    stdout_path = os.path.join(run_dir, "accoreconsole_plot_stdout.txt")
    stderr_path = os.path.join(run_dir, "accoreconsole_plot_stderr.txt")
    res["stdout_path"] = stdout_path
    res["stderr_path"] = stderr_path

    try:
        with open(stdout_path, "wb") as so, open(stderr_path, "wb") as se:
            proc = subprocess.run(
                [engine, "/i", staged, "/s", scr_path],
                cwd=run_dir, stdout=so, stderr=se, timeout=timeout,
            )
        res["exit_code"] = proc.returncode
    except subprocess.TimeoutExpired:
        res["timed_out"] = True
        res["reason"] = "accoreconsole timed out after %ss" % timeout
        return res
    except (OSError, subprocess.SubprocessError) as exc:
        res["reason"] = "accoreconsole launch failed: %s" % exc
        return res

    # Truth check: did a real, non-empty PDF appear? Exit code is NOT trusted.
    if os.path.isfile(out_pdf) and os.path.getsize(out_pdf) > 0:
        res["produced"] = True
        res["pdf_path"] = out_pdf
        res["reason"] = "accoreconsole -PLOT produced a PDF"
    else:
        res["reason"] = ("accoreconsole ran (exit=%s) but produced no PDF file "
                         "(headless -PLOT did not emit output on this host)"
                         % res["exit_code"])
    return res


def _ok_artifact(aid: str, kind: str, source_ref: str, route: str,
                 pdf_path: str, run_dir: str,
                 extra_diag: Dict[str, Any]) -> Dict[str, Any]:
    """Build an ``ok`` visual_artifact.v1 with a REAL ref (size + sha256)."""
    size = None
    try:
        size = os.path.getsize(pdf_path)
    except OSError:
        size = None
    ref: Dict[str, Any] = {"ref": pdf_path, "media_type": "application/pdf"}
    if size is not None:
        ref["byte_size"] = size
    digest = _sha256(pdf_path)
    if digest:
        ref["sha256"] = digest
    return {
        "schema": VISUAL_SCHEMA_ID,
        "artifact_id": aid,
        "kind": kind,
        "status": "ok",
        "source_ref": source_ref,
        "route": route,
        "media_type": "application/pdf",
        "refs": [ref],
        "run_dir": run_dir,
        "diagnostics": {"exit_code": extra_diag.get("exit_code"), "warnings": []},
        "notes": "real render produced via %s" % route,
    }


def build_visual_report(source_ref: str,
                        kind: str = "png",
                        artifact_id: Optional[str] = None,
                        out_dir: Optional[str] = None,
                        route: Optional[str] = None,
                        *,
                        attempt_render: bool = True,
                        allow_full_autocad: bool = False,
                        timeout: int = 180) -> Dict[str, Any]:
    """
    Build a visual_artifact.v1 envelope for an artifact derived from
    ``source_ref`` (a DWG/IR path -- a READ-ONLY provenance ref).

    Behavior (no-fake-success throughout):
      * For a raster/pdf ``kind`` (png/jpg/pdf), when ``attempt_render`` is True
        and accoreconsole is present, this ACTUALLY RUNS a headless -PLOT on a
        STAGED COPY of ``source_ref`` (the original is never written), capturing
        stdout/stderr/exit into a run dir. If a real PDF file is produced it
        returns ``status="ok"`` with populated ``refs`` (path/size/sha256). If no
        file is produced it returns ``not_implemented`` with the captured
        evidence paths and an explicit reason. (On this host, accoreconsole does
        not emit a file -- see module docstring -- so this yields a truthful
        ``not_implemented``, never a fake ok.)
      * ``full_autocad_com`` (real COM PlotToFile) is only attempted when
        ``allow_full_autocad=True`` AND acad.exe is running; it is reported as an
        available-but-gated route otherwise, and never driven silently.
      * For vector kinds (svg/pdf via the vector route) with an available
        candidate route but no wired producer -> ``not_implemented`` naming the
        route that would be used.
      * If a candidate route competent for ``kind`` exists but is unavailable ->
        ``blocked``.

    ``refs`` is always empty when status != ok.
    """
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

    probe = available_render_routes()
    render_kinds = {"png", "jpg", "pdf"}

    # ---- real render attempt for raster/pdf kinds --------------------------
    if kind in render_kinds:
        src_present = isinstance(source_ref, str) and os.path.isfile(source_ref)
        run_dir = out_dir or os.path.join(
            _RUNS_DIR, "visual_report_%s" % time.strftime("%Y%m%d_%H%M%S"))

        # (a) gated full-AutoCAD COM route: only when explicitly opted in.
        fa = probe["render_routes"].get("full_autocad_com", {})
        if allow_full_autocad and fa.get("acad_running") and src_present:
            fa_res = _attempt_full_autocad_plot(source_ref, run_dir, timeout)
            if fa_res.get("produced") and fa_res.get("pdf_path"):
                art = _ok_artifact(aid, kind, source_ref, "full_autocad_com",
                                   fa_res["pdf_path"], run_dir,
                                   {"exit_code": fa_res.get("exit_code")})
                if kind in ("png", "jpg"):
                    art.setdefault("diagnostics", {}).setdefault(
                        "warnings", []).append(
                        "requested %s; produced PDF (vector plot device); "
                        "rasterize downstream if a bitmap is required" % kind)
                return art
            # opted-in but failed -> fall through to honest not_implemented,
            # carrying the COM evidence.
            probe.setdefault("_full_autocad_attempt", fa_res)

        # (b) accoreconsole staged-copy plot attempt (default path).
        if attempt_render and src_present and \
                probe["render_routes"]["accoreconsole_plot"]["attemptable"]:
            acc = _attempt_accoreconsole_plot(source_ref, run_dir, timeout)
            if acc.get("produced") and acc.get("pdf_path"):
                art = _ok_artifact(aid, kind, source_ref, "accoreconsole_plot",
                                   acc["pdf_path"], run_dir,
                                   {"exit_code": acc.get("exit_code")})
                if kind in ("png", "jpg"):
                    art.setdefault("diagnostics", {}).setdefault(
                        "warnings", []).append(
                        "requested %s; produced PDF (plot device); rasterize "
                        "downstream if a bitmap is required" % kind)
                return art

            # No file produced -> truthful not_implemented WITH evidence.
            diag_warn = [
                "render attempt ran but produced no artifact: %s"
                % acc.get("reason", "unknown"),
            ]
            fa_att = probe.get("_full_autocad_attempt")
            if fa_att:
                diag_warn.append("full_autocad_com attempt: %s"
                                 % fa_att.get("reason", "unknown"))
            elif fa.get("acad_running") and not allow_full_autocad:
                diag_warn.append(
                    "full AutoCAD (acad.exe) is running: a real COM PlotToFile "
                    "render is possible but GATED -- pass allow_full_autocad=True "
                    "to drive the live session.")
            return {
                "schema": VISUAL_SCHEMA_ID,
                "artifact_id": aid,
                "kind": kind,
                "status": "not_implemented",
                "source_ref": source_ref,
                "route": "accoreconsole_plot",
                "refs": [],
                "run_dir": run_dir,
                "diagnostics": {
                    "exit_code": acc.get("exit_code"),
                    "warnings": diag_warn,
                },
                "evidence": {
                    "staged_dwg": acc.get("staged_dwg"),
                    "scr": acc.get("scr_path"),
                    "stdout": acc.get("stdout_path"),
                    "stderr": acc.get("stderr_path"),
                    "timed_out": acc.get("timed_out"),
                },
                "probe": {
                    "render_layout_status": probe["render_layout_status"],
                    "render_routes": probe["render_routes"],
                },
                "notes": ("accoreconsole headless render attempted on a staged "
                          "copy; no file emitted -> not_implemented (no fake)."),
            }

        # render kind, but the attempt was not run. Be precise about WHY:
        #   - source not an existing file, or
        #   - attempt_render=False (caller opted out of the real attempt), or
        #   - no engine present on this host.
        acc_attemptable = probe["render_routes"]["accoreconsole_plot"]["attemptable"]
        if not src_present:
            reason = "source_ref is not an existing file: %s" % source_ref
        elif not attempt_render:
            reason = ("caller opted out (attempt_render=False); an accoreconsole "
                      "route is %s on this host"
                      % ("attemptable" if acc_attemptable else "not present"))
        else:
            reason = "no attemptable DWG render route on this host"
        return {
            "schema": VISUAL_SCHEMA_ID,
            "artifact_id": aid,
            "kind": kind,
            "status": "not_implemented",
            "source_ref": source_ref,
            "refs": [],
            "diagnostics": {"warnings": [reason]},
            "probe": {
                "render_layout_status": probe["render_layout_status"],
                "render_routes": probe["render_routes"],
            },
            "notes": "render not attempted: %s" % reason,
        }

    # ---- non-raster kinds: vector/compare candidate-route reporting --------
    chosen = _route_for_kind(kind, probe, route)
    if chosen is not None:
        # A vector producer would run here. None is wired in this lane, so we do
        # NOT claim ok -- report not_implemented naming the route that would run.
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
                    "vector producer is not implemented in this lane" % (chosen, kind),
                ],
            },
            "notes": "vector producer not_implemented; no artifact written",
        }

    route_exists_but_unavailable = any(
        kind in _ROUTE_KINDS.get(rid, set())
        and not probe["routes"].get(rid, {}).get("available", False)
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
        "diagnostics": {"warnings": [warn]},
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
# Gated full-AutoCAD COM plot (opt-in only; touches the live session)
# --------------------------------------------------------------------------- #

def _attempt_full_autocad_plot(source_dwg: str, run_dir: str,
                               timeout: int) -> Dict[str, Any]:
    """
    GATED real render: drive the RUNNING full AutoCAD via COM to open a STAGED
    COPY as a side document, plot it to PDF with DWG To PDF.pc3, then close it.
    Only invoked when ``allow_full_autocad=True``. Uses a PowerShell COM bridge
    (stdlib subprocess); stdout/stderr/exit captured into the run dir. The user's
    ACTIVE document is never modified -- we open and plot a separate staged copy.

    Returns the same shape as _attempt_accoreconsole_plot.

    HONESTY: opening a doc into the user's live GUI session can disturb focus and
    may be refused by AutoCAD if it is mid-command. This is best-effort and
    reports truthfully; a missing output file => produced False.
    """
    res: Dict[str, Any] = {
        "produced": False, "pdf_path": None, "exit_code": None,
        "stdout_path": "", "stderr_path": "", "scr_path": "",
        "staged_dwg": "", "timed_out": False, "reason": "",
    }
    os.makedirs(run_dir, exist_ok=True)
    staged = _stage_copy(source_dwg, run_dir)
    res["staged_dwg"] = staged
    out_pdf = os.path.join(run_dir, "out_full_autocad.pdf")

    staged_fwd = staged.replace("\\", "/")
    out_fwd = out_pdf.replace("\\", "/")
    ps = r"""
$ErrorActionPreference='Stop'
try {
  $app = [Runtime.InteropServices.Marshal]::GetActiveObject('AutoCAD.Application')
} catch {
  Write-Output 'NO_ACTIVE_AUTOCAD'; exit 11
}
try {
  $docs = $app.Documents
  $doc  = $docs.Open('%s', $true)   # read-only open of the staged copy
} catch {
  Write-Output ('OPEN_FAILED: ' + $_.Exception.Message); exit 12
}
try {
  $lay = $doc.ModelSpace.Layout
  try { $lay.ConfigName = 'DWG To PDF.pc3' } catch {}
  try { $lay.PlotType = 1 } catch {}        # acExtents
  try { $lay.CenterPlot = $true } catch {}
  try { $lay.StandardScale = 0 } catch {}   # acScaleToFit
  $plot = $doc.Plot
  try { $doc.SetVariable('BACKGROUNDPLOT', 0) } catch {}
  $ok = $plot.PlotToFile('%s', 'DWG To PDF.pc3')
  Write-Output ('PLOTTOFILE=' + $ok)
} catch {
  Write-Output ('PLOT_FAILED: ' + $_.Exception.Message)
} finally {
  try { $doc.Close($false) } catch {}
}
""" % (staged_fwd, out_fwd)

    ps_path = os.path.join(run_dir, "full_autocad_plot.ps1")
    with open(ps_path, "w", encoding="utf-8") as fh:
        fh.write(ps)
    res["scr_path"] = ps_path
    stdout_path = os.path.join(run_dir, "full_autocad_plot_stdout.txt")
    stderr_path = os.path.join(run_dir, "full_autocad_plot_stderr.txt")
    res["stdout_path"] = stdout_path
    res["stderr_path"] = stderr_path

    try:
        with open(stdout_path, "wb") as so, open(stderr_path, "wb") as se:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-File", ps_path],
                cwd=run_dir, stdout=so, stderr=se, timeout=timeout,
            )
        res["exit_code"] = proc.returncode
    except subprocess.TimeoutExpired:
        res["timed_out"] = True
        res["reason"] = "full AutoCAD COM plot timed out after %ss" % timeout
        return res
    except (OSError, subprocess.SubprocessError) as exc:
        res["reason"] = "full AutoCAD COM bridge failed to launch: %s" % exc
        return res

    if os.path.isfile(out_pdf) and os.path.getsize(out_pdf) > 0:
        res["produced"] = True
        res["pdf_path"] = out_pdf
        res["reason"] = "full AutoCAD COM PlotToFile produced a PDF"
    else:
        res["reason"] = ("full AutoCAD COM plot ran (exit=%s) but produced no "
                         "PDF (open/plot may have been refused by the live "
                         "session)" % res["exit_code"])
    return res


# --------------------------------------------------------------------------- #
# Self-test (__main__)
# --------------------------------------------------------------------------- #

def _selftest() -> int:
    # Prefer the real golden staged copy if present; else a non-existent demo
    # path (which exercises the truthful "source missing" branch).
    golden = os.path.join(_STAGING_DIR, "dwg_20260617_191504", "input.dwg")
    sample_source = golden if os.path.isfile(golden) else os.path.join(
        _ROUTER_HOME, "staging", "golden", "demo", "input.dwg")

    probe = available_render_routes()

    # Default behavior: do NOT run a multi-minute render inside the self-test;
    # exercise the truthful decision path (attempt_render=False) so the self-test
    # is fast and deterministic. A separate --render flag drives the real attempt.
    do_render = "--render" in sys.argv
    report = build_visual_report(sample_source, kind="pdf",
                                 attempt_render=do_render)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # Contract: schema-valid shape; status in the truthful set; if not ok then
    # refs empty; if ok then a real ref exists on disk.
    status_ok = report["status"] in ("ok", "not_implemented", "blocked", "error")
    if report["status"] == "ok":
        refs_ok = (len(report["refs"]) >= 1
                   and os.path.isfile(report["refs"][0]["ref"]))
    else:
        refs_ok = report["refs"] == []
    ok = (
        report["schema"] == VISUAL_SCHEMA_ID
        and status_ok
        and refs_ok
        and isinstance(report["artifact_id"], str)
    )
    rr = probe["render_routes"]
    print("SELFTEST_OK" if ok else "SELFTEST_FAIL",
          "| status=%s refs=%d | render_layout=%s | accoreconsole=%s "
          "full_autocad_com=%s any_render_attemptable=%s"
          % (report["status"], len(report["refs"]),
             probe["render_layout_status"],
             rr["accoreconsole_plot"]["attemptable"],
             rr["full_autocad_com"]["available"],
             probe["any_render_attemptable"]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_selftest())
