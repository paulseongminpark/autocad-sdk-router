#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fast B attended visual harness install/safety tests."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PS1 = REPO / "tools" / "attended" / "run_attended_visual_plot.ps1"
CLIENT = REPO / "tools" / "attended" / "attended_visual_client.py"
PLAN = REPO / "reports" / "tickets" / "WAVE4X_VISUAL_ATTENDED_PLAN.md"


def test_visual_attended_harness_files_exist():
    assert PS1.exists()
    assert CLIENT.exists()
    assert PLAN.exists()


def test_visual_attended_harness_enforces_dedicated_instance_staging_and_unique_pipe():
    src = PS1.read_text(encoding="utf-8", errors="replace")
    for token in [
        "Get-Process acad",
        "pre_existing_acad_pids",
        "staging\\attended_visual\\",
        "Get-FileHash",
        "ariadne-cadagent-visual-plot-",
        "CADAGENT_PUMP",
        "Stop-Process -Id $launchedPid",
        "original_dwg_modified",
    ]:
        assert token in src


def test_visual_attended_client_drives_real_plot_ops():
    src = CLIENT.read_text(encoding="utf-8", errors="replace")
    for token in [
        'call("live.status")',
        'call("plot.config.settings")',
        'call("plot.engine.run")',
        'call("live.stop")',
        "plot_engine_created",
        "host_full_autocad",
    ]:
        assert token in src


def test_visual_attended_plan_documents_safety_contract():
    text = PLAN.read_text(encoding="utf-8", errors="replace")
    for token in [
        "Dedicated AutoCAD instance",
        "Staged DWG",
        "No Original Write",
        "Unique Live Channel",
        "plot.config.settings",
        "plot.engine.run",
    ]:
        assert token in text
