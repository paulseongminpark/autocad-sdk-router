#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fast B attended live-UI harness install/safety tests."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PS1 = REPO / "tools" / "attended" / "run_attended_live_ui.ps1"
CLIENT = REPO / "tools" / "attended" / "attended_live_ui_client.py"


def test_live_ui_attended_harness_files_exist():
    assert PS1.exists()
    assert CLIENT.exists()


def test_live_ui_harness_enforces_dedicated_instance_staging_and_unique_pipe():
    src = PS1.read_text(encoding="utf-8", errors="replace")
    for token in [
        "Get-Process acad",
        "pre_existing_acad_pids",
        "staging\\attended_live_ui\\",
        "Get-FileHash",
        "ariadne-cadagent-live-ui-",
        "CADAGENT_PUMP",
        "Stop-Process -Id $launchedPid",
        "original_dwg_modified",
    ]:
        assert token in src


def test_live_ui_client_drives_safe_toolpalette_and_subentity_ops():
    src = CLIENT.read_text(encoding="utf-8", errors="replace")
    for token in [
        '"editor.toolpalette.tool_execute"',
        '"ui.subentity.highlight"',
        "tool_execute_invoked",
        "raw_command_agent_surface",
        "highlight_status",
        "marker_count",
    ]:
        assert token in src
