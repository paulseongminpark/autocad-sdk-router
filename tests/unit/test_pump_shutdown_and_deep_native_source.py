#!/usr/bin/env python
"""Source-level compile-time guards for the M07 live pump + deep-native surface.

WHY a source-presence test is legitimate here: the live ARX pump, the editor
reactor / object overrule / jig, and the custom-object filer all require a real
AutoCAD (attended editor loop or accoreconsole DB host) to *execute*. A headless
CI box cannot exercise them. A source-presence assertion is therefore the
correct compile-time guard -- it fails loudly if someone deletes a registered
surface, renames a shutdown call, or ships the pump without the write guard,
even when no AutoCAD is available to run it.

This complements (does NOT duplicate) tests/test_native_arx_dbx_contract.py /
tests/integration/test_live_arx_pump.py. Here we pin:
  * (#3) the safe-shutdown invariants of the pump + module unload, and
  * (#4) the deep-native surfaces' presence + the M07 pump ops.

All M07 pump-op strings below were integrated and headless-verified in
runs/m07_pump_test (CADAGENT_STATUS + live.active_document / live.inspect_entity
/ live.apply_patch[disabled] / 5 attended_only ops), so the tier that was an
xfail-strict tripwire during authoring is now promoted to unconditional guards.

Pure stdlib + pytest. No AutoCAD, no subprocess.
"""
from __future__ import annotations

from pathlib import Path

import pytest

# tests/unit/<thisfile> -> repo root is parents[2]
ROOT = Path(__file__).resolve().parents[2]
ARX_ENTRY = ROOT / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
DBX_RECORD_CPP = ROOT / "src" / "Ariadne.AcadNativeDbx" / "AriadneRecord.cpp"
DBX_RECORD_H = ROOT / "src" / "Ariadne.AcadNativeDbx" / "AriadneRecord.h"


def _read(p: Path) -> str:
    assert p.is_file(), f"source file missing: {p}"
    return p.read_text(encoding="utf-8-sig")


@pytest.fixture(scope="module")
def arx_src() -> str:
    return _read(ARX_ENTRY)


@pytest.fixture(scope="module")
def dbx_record_src() -> str:
    return _read(DBX_RECORD_CPP) + "\n" + _read(DBX_RECORD_H)


# ========================================================================== #
# #3  Safe-shutdown contract
# ========================================================================== #
def test_pump_closes_pipe_resources(arx_src: str):
    """ariadneCadAgentPump must release every Win32 handle it opens."""
    assert "CreateNamedPipeW" in arx_src
    assert "DisconnectNamedPipe" in arx_src
    assert "CloseHandle" in arx_src
    assert "FlushFileBuffers" in arx_src
    # CloseHandle must appear at least twice: the event AND the pipe handle.
    assert arx_src.count("CloseHandle") >= 2


def test_pump_io_is_timeout_bounded(arx_src: str):
    """Overlapped I/O + WaitForSingleObject(timeout) => self-terminating pump."""
    assert "FILE_FLAG_OVERLAPPED" in arx_src
    assert "WaitForSingleObject" in arx_src
    assert "ERROR_IO_PENDING" in arx_src
    assert "CancelIo" in arx_src


def test_module_unload_drains_deep_native_and_unloads(arx_src: str):
    """kUnloadAppMsg must disable reactor + overrule, drop the command group,
    and unload the dbx module -- the documented clean-unload sequence."""
    idx_unload = arx_src.index("kUnloadAppMsg")
    tail = arx_src[idx_unload:]
    assert "disableEditorReactor" in tail
    assert "disableObjectOverrule" in tail
    assert 'removeGroup(_T("ARIADNE_NATIVE"))' in tail
    assert "acrxUnloadModule" in tail
    # ordering: reactor/overrule torn down BEFORE the module is unloaded.
    assert tail.index("disableEditorReactor") < tail.index("acrxUnloadModule")
    assert tail.index("disableObjectOverrule") < tail.index("acrxUnloadModule")


def test_pump_frame_length_guard_present(arx_src: str):
    """The 0-length / >1MiB hard-stop guard must be in the read loop."""
    assert "(1u << 20)" in arx_src
    assert "n == 0" in arx_src


def test_pump_thread_safety_statement_present(arx_src: str):
    """The §3 thread-safety answer (no worker thread) must be documented."""
    assert "worker thread never touches AcDb" in arx_src
    assert "gPumpServing" in arx_src


# ========================================================================== #
# #4  Deep-native compile-presence -- registered surfaces
# ========================================================================== #
def test_object_overrule_surface_present(arx_src: str):
    assert "class AriadneObjectOverrule : public AcDbObjectOverrule" in arx_src
    assert "AcRxOverrule::addOverrule" in arx_src
    assert "setIsOverruling" in arx_src
    assert 'op == "live.overrule.enable"' in arx_src
    assert 'op == "live.overrule.disable"' in arx_src


def test_editor_reactor_surface_present(arx_src: str):
    assert "class AriadneEditorReactor : public AcEditorReactor" in arx_src
    assert "addReactor" in arx_src
    assert "removeReactor" in arx_src
    assert 'op == "live.reactor.enable"' in arx_src
    assert 'op == "live.reactor.disable"' in arx_src


def test_editor_jig_surface_present_and_host_gated(arx_src: str):
    """AcEdJig is implemented but its drag loop is correctly attended-only."""
    assert "class AriadneLineJig : public AcEdJig" in arx_src
    assert 'op == "live.jig.point_probe"' in arx_src
    assert "AcEdJig drag requires the full AutoCAD editor interaction loop" in arx_src


def test_custom_entity_worlddraw_present():
    """AriadneProbe : AcDbEntity with a real subWorldDraw render callback
    (custom_entity_lifecycle + worldDraw_rendering). Compiles into the .dbx;
    headless save/reload roundtrips the entity, pixel render is attended-only."""
    probe_h = (ROOT / "src" / "Ariadne.AcadNative" / "AriadneProbe.h").read_text(encoding="utf-8-sig")
    probe_cpp = (ROOT / "src" / "Ariadne.AcadNative" / "AriadneProbe.cpp").read_text(encoding="utf-8-sig")
    assert "class AriadneProbe : public AcDbEntity" in probe_h
    assert "subWorldDraw(AcGiWorldDraw" in probe_h
    assert "AriadneProbe::subWorldDraw" in probe_cpp
    assert "geometry().circle" in probe_cpp


def test_protocol_extension_registered():
    """AriadneProbeProtocol : AcRxObject registered via addX on AriadneProbe::desc()
    and exposed as the inspect.protocol.queryx pump/job op."""
    proto_cpp = (ROOT / "src" / "Ariadne.AcadNativeDbx" / "AriadneProtocol.cpp").read_text(encoding="utf-8-sig")
    arx = ARX_ENTRY.read_text(encoding="utf-8-sig")
    assert "AriadneProbe::desc()->addX(AriadneProbeProtocol::desc()" in proto_cpp
    assert 'op == "inspect.protocol.queryx"' in arx


def test_custom_object_filer_versioning_present(dbx_record_src: str):
    """AriadneRecord : AcDbObject with a versioned filer that proxies on a
    newer on-disk version -- 'custom object serialization / filer versioning'."""
    assert "ACRX_DXF_DEFINE_MEMBERS" in dbx_record_src
    assert "kAriadneRecordVersion" in dbx_record_src
    assert "dwgOutFields" in dbx_record_src
    assert "dwgInFields" in dbx_record_src
    assert "dxfOutFields" in dbx_record_src
    assert "dxfInFields" in dbx_record_src
    assert "writeInt16" in dbx_record_src
    assert "readInt16" in dbx_record_src
    assert "Acad::eMakeMeProxy" in dbx_record_src


def test_arx_is_single_translation_unit_owner(arx_src: str):
    """All new native pump code lands in AriadneNativeJob.cpp (the single .arx TU)."""
    assert "CADAGENT_PUMP" in arx_src
    assert "ariadneCadAgentPump" in arx_src
    assert "acrxEntryPoint" in arx_src


# ========================================================================== #
# #4b  M07 pump ops -- integrated + headless-verified (runs/m07_pump_test).
#      (These were xfail-strict tripwires during authoring; promoted to
#       unconditional guards now that the strings are wired and proven.)
# ========================================================================== #
def test_m07_pump_status_command_added(arx_src: str):
    assert "CADAGENT_STATUS" in arx_src
    assert "ariadneCadAgentStatus" in arx_src


def test_m07_pump_live_active_document_op_added(arx_src: str):
    assert '"live.active_document"' in arx_src


def test_m07_pump_live_inspect_entity_op_added(arx_src: str):
    assert '"live.inspect_entity"' in arx_src


def test_m07_pump_apply_patch_is_write_guarded(arx_src: str):
    """§5: live.apply_patch exists AND is gated (no live save / no off-thread
    write). The 'disabled' status + 'attended_only' token are the refusal markers."""
    assert '"live.apply_patch"' in arx_src
    assert "attended_only" in arx_src
    assert "use the M05 staged-patch governor" in arx_src


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
