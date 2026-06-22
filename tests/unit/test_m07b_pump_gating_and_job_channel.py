#!/usr/bin/env python
"""CADOS_M07B compile-time source guards: pump-gating, the env-file job channel,
and the attended palette TU.

WHY source-presence: the gated pump ops (real highlight / selection / honest
zoom-deferral), the ARIADNE_NATIVE_JOB_ARGS env-file channel, and the
ARIADNE_PALETTE command all require a full AutoCAD editor to *execute*. A headless
CI box cannot run them, so a source-presence assertion is the correct compile-time
guard: it fails loudly if someone deletes the host gate, reverts the channel to
interactive-only prompts, or leaks the MFC-free palette into the headless .crx.

Pairs with tests/unit/test_pump_shutdown_and_deep_native_source.py (M07/M07A).
Pure stdlib + pytest. No AutoCAD, no subprocess.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ARX_ENTRY = ROOT / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
PALETTE_CPP = ROOT / "src" / "Ariadne.AcadNative" / "AriadnePalette.cpp"
ARX_VCXPROJ = ROOT / "src" / "Ariadne.AcadNative" / "Ariadne.AcadNative.arx.vcxproj"
CRX_VCXPROJ = ROOT / "src" / "Ariadne.AcadNative" / "Ariadne.AcadNative.crx.vcxproj"


def _read(p: Path) -> str:
    assert p.is_file(), f"source file missing: {p}"
    return p.read_text(encoding="utf-8-sig")


@pytest.fixture(scope="module")
def arx_src() -> str:
    return _read(ARX_ENTRY)


# ========================================================================== #
# Pump-gating: the 5 formerly-stub ops now gate on a full editor.
# ========================================================================== #
def test_pump_gate_variable_present(arx_src: str):
    """The gate is the host EXE discriminator (acad.exe vs accoreconsole.exe).
    acedEditor is non-null in BOTH hosts, so it cannot gate; the host exe name is
    reliable even if the host_mode env hint is not propagated into the process."""
    assert "static bool hostIsFullAutoCad()" in arx_src
    assert 'GetModuleFileNameW(NULL' in arx_src
    assert '_wcsicmp(base.c_str(), L"acad.exe")' in arx_src
    assert "const bool attendedHost = hostIsFullAutoCad();" in arx_src
    # report == gate: host_mode derives from the same discriminator
    assert 'const std::string hostMode = attendedHost ? "full_autocad" : "coreconsole";' in arx_src


def test_pump_selection_real_path(arx_src: str):
    """inspect_selection reads the pickfirst set via acedSSGet under the gate,
    and still returns attended_only when !attendedHost."""
    assert "acedSSGet(_T(\"_I\")" in arx_src
    assert "acedSSLength" in arx_src
    assert "acedSSName" in arx_src
    assert "acedSSFree" in arx_src
    assert "acdbGetObjectId" in arx_src
    # honest stub retained for the headless branch
    assert "accoreconsole has no interactive editor" in arx_src


def test_pump_highlight_real_path(arx_src: str):
    """highlight/clear call the command-free AcDbEntity display methods under the
    gate (safe inside the modal pump command)."""
    assert "pEnt->highlight() == Acad::eOk" in arx_src
    assert "pEnt->unhighlight() == Acad::eOk" in arx_src
    assert 'op == "live.highlight_handles"' in arx_src
    assert 'op == "live.clear_highlight"' in arx_src
    assert "jsonFindStringArray" in arx_src


def test_pump_zoom_render_honestly_deferred(arx_src: str):
    """zoom/render are NOT faked: under a live editor they return 'deferred' with
    the acedCommand-reentrancy reason (the pump is itself a modal command)."""
    assert "deferred" in arx_src
    assert "acedCommand cannot be invoked reentrantly from the pump loop" in arx_src


def test_pump_handles_array_parser_present(arx_src: str):
    assert "std::vector<std::string> jsonFindStringArray" in arx_src


# ========================================================================== #
# ARIADNE_NATIVE_JOB_ARGS env-file channel (non-interactive, reproducible).
# ========================================================================== #
def test_job_args_env_file_channel(arx_src: str):
    assert "readArgsFileSetting" in arx_src
    assert 'acedGetEnv(_T("ARIADNE_NATIVE_JOB_ARGS")' in arx_src
    assert '_wgetenv(L"ARIADNE_NATIVE_JOB_ARGS")' in arx_src
    # reads job_in/job_out/host_mode from the args file, non-interactively
    assert 'jsonFindString(spec, "job_in", in)' in arx_src
    assert 'jsonFindString(spec, "job_out", out)' in arx_src
    assert "utf8ToWide" in arx_src
    # interactive prompts kept ONLY as the documented fallback
    assert "Documented fallback: interactive prompts" in arx_src


# ========================================================================== #
# Attended palette TU: MFC-free, arx-only, headless .crx must NOT see it.
# ========================================================================== #
def test_palette_tu_exists_and_mfc_free():
    src = _read(PALETTE_CPP)
    assert 'extern "C" void ariadneRegisterPaletteCommand()' in src
    assert "ARIADNE_PALETTE" in src
    assert "acedAlert" in src
    # MFC-free skeleton: no MFC headers / no palette-set instantiation pulled into
    # this ObjectARX module (a comment may *reference* CAdUiPaletteSet as the
    # deferred enhancement; what matters is it is never included or instantiated).
    assert "afxwin" not in src.lower()
    assert "#include <afx" not in src.lower()
    assert "new CAdUiPaletteSet" not in src


def test_palette_registration_is_arx_only(arx_src: str):
    """The registration call is wrapped in #ifndef ARIADNE_NATIVE_CRX so the
    headless module neither links nor registers the palette."""
    assert "#ifndef ARIADNE_NATIVE_CRX" in arx_src
    assert "ariadneRegisterPaletteCommand();" in arx_src
    assert 'extern "C" void ariadneRegisterPaletteCommand();' in arx_src


def test_deep_native_firing_ops_present(arx_src: str):
    """M07B firing self-test: enable + FIRE reactor/overrule/selection-monitor with
    no acedCommand reentrancy (overrule via acdbOpenObject, selmon via acedSSSetFirst),
    + a firing_report op that reads all three registries."""
    assert 'op == "extend.deep_native.firing_selftest"' in arx_src
    assert 'op == "inspect.deep_native.firing_report"' in arx_src
    assert "enableEditorReactor" in arx_src
    assert "enableObjectOverrule" in arx_src
    assert "enableSelectionMonitor" in arx_src
    assert "acedSSSetFirst(NULL, ss)" in arx_src
    assert "findFirstProbe" in arx_src
    assert "reactorRegistryJson" in arx_src
    assert "overruleRegistryJson" in arx_src
    assert "selectionMonitorRegistryJson" in arx_src


def test_palette_in_arx_project_not_crx_project():
    arx = _read(ARX_VCXPROJ)
    crx = _read(CRX_VCXPROJ)
    assert "AriadnePalette.cpp" in arx, "palette TU must be in the .arx project"
    assert "AriadnePalette.cpp" not in crx, "palette TU must NOT be in the headless .crx project"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
