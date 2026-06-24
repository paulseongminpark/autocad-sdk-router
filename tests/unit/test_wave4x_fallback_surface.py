#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PS = shutil.which("powershell") or shutil.which("powershell.exe") or shutil.which("pwsh")
SAFE_PS1 = ROOT / "tools" / "fallback_safe_surface.ps1"
ROUTER_PS1 = ROOT / "tools" / "autocad-router.ps1"


def _ps_json(command: str):
    if not PS:
        return None
    proc = subprocess.run(
        [PS, "-NoProfile", "-Command", command],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout)


def test_safe_surface_script_exists():
    assert SAFE_PS1.is_file()


def test_safe_fallback_implemented_allowlist_matches_wave4x_scope():
    if not PS:
        return
    cmd = f". '{SAFE_PS1}'; Get-SafeFallbackImplementedOps | ConvertTo-Json -Compress"
    ops = _ps_json(cmd)
    assert sorted(ops) == sorted([
        "automate.com.get_app",
        "automate.com.get_document",
        "automate.com.get_for_command",
        "automate.com.get_winapp",
        "automate.com.wrapper_for_object",
        "module.load.lisp",
    ])


def test_safe_fallback_blocklist_keeps_raw_command_and_ole_ops_closed():
    if not PS:
        return
    cmd = f". '{SAFE_PS1}'; Get-SafeFallbackStillBlockedOps | ConvertTo-Json -Compress"
    ops = set(_ps_json(cmd))
    for op in {
        "automate.com.send_command",
        "command.invoke.coroutine",
        "command.invoke.sync",
        "command.invoke.sync.resbuf",
        "command.menu.invoke",
        "command.queue.post",
        "embed.ole.frame",
        "module.lifecycle.on_ole_unload",
    }:
        assert op in ops
    assert "automate.com.get_app" not in ops


def test_safe_surface_managed_adapter_map_is_allowlisted_only():
    if not PS:
        return
    cmd = f". '{SAFE_PS1}'; Get-SafeManagedAdapterMap | ConvertTo-Json -Depth 6 -Compress"
    payload = _ps_json(cmd)
    assert payload["managed_cad_job"]["loader"] == "NETLOAD"
    assert payload["managed_cad_job"]["command"] == "ARIADNE_CAD_JOB"
    assert payload["geometry_extract"]["command"] == "ARIADNE_DWG_GEOM_EXTRACT"
    assert payload["objectdbx_extract"]["command"] == "ARIADNE_DWG_DBX_EXTRACT"
    assert payload["managed_cad_job"]["raw_command_exposed"] is False


def test_router_sources_and_invokes_safe_surface():
    text = ROUTER_PS1.read_text(encoding="utf-8")
    assert "fallback_safe_surface.ps1" in text
    assert "Invoke-SafeFallbackOperation -Capabilities $capabilities" in text
