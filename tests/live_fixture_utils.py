#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helpers for live CAD OS pytest fixtures.

These helpers intentionally do nothing unless CADOS_LIVE=1. They let a clean
worktree materialize ignored run evidence from the tracked DWG fixture while
preserving the headless default behavior: skip with an explicit reason.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from shutil import which
from typing import Tuple


ACCORECONSOLE = r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe"


def accoreconsole_present() -> bool:
    if os.path.isfile(ACCORECONSOLE):
        return True
    return which("accoreconsole") is not None or which("accoreconsole.exe") is not None


def resolve_golden_dwg(repo: str | Path) -> Path | None:
    repo = Path(repo)
    candidates = [
        repo / "staging" / "dwg_20260617_191504" / "input.dwg",
        repo / "tests" / "fixtures" / "native_sample.dwg",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def ensure_m02_cadctl_rich_fixture(repo: str | Path) -> Tuple[bool, str]:
    """Ensure runs/m02_cadctl_rich/dwg_graph_ir.json exists when live is enabled."""
    repo = Path(repo)
    ir_path = repo / "runs" / "m02_cadctl_rich" / "dwg_graph_ir.json"
    cad_result = repo / "runs" / "m02_cadctl_rich" / "cad_result.json"
    if ir_path.is_file() and cad_result.is_file():
        return True, "present"

    if os.environ.get("CADOS_LIVE") != "1":
        return False, "CADOS_LIVE!=1"
    if not accoreconsole_present():
        return False, "no accoreconsole"

    dwg = resolve_golden_dwg(repo)
    if dwg is None:
        return False, "no golden DWG"

    tools = repo / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))

    try:
        import cadctl
        env = cadctl.Cad().inspect(
            str(dwg),
            str(repo / "runs" / "m02_cadctl_rich"),
            mode="graph",
            include_rich=True,
        )
    except Exception as exc:  # pragma: no cover - live host diagnostics only
        return False, "fixture generation failed: %s" % exc

    if ir_path.is_file() and cad_result.is_file() and env.get("status") == "ok":
        return True, "generated from %s" % dwg
    return False, "fixture generation returned %s: %s" % (
        env.get("status"), env.get("reason") or env.get("result_status"))
