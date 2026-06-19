import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIVE_DBX_PROJECT = ROOT / "src" / "Ariadne.AcadNativeDbx" / "Ariadne.AcadNativeDbx.dbx.vcxproj"
NATIVE_ARX_PROJECT = ROOT / "src" / "Ariadne.AcadNative" / "Ariadne.AcadNative.arx.vcxproj"
NATIVE_CRX_PROJECT = ROOT / "src" / "Ariadne.AcadNative" / "Ariadne.AcadNative.crx.vcxproj"
NATIVE_ARX_ENTRY = ROOT / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
NATIVE_DBX_API = ROOT / "src" / "Ariadne.AcadNativeDbx" / "AriadneDbxApi.h"
NATIVE_DBX_ENTRY = ROOT / "src" / "Ariadne.AcadNativeDbx" / "AriadneDbxEntry.cpp"
BUILD_NATIVE = ROOT / "tools" / "build_native_acad.ps1"
ROUTER = ROOT / "tools" / "autocad-router.ps1"


def _native_command_registration(text: str, command: str) -> str:
    pattern = re.compile(
        r"acedRegCmds->addCommand\([^;]*?_T\(\""
        + re.escape(command)
        + r"\"\)[^;]*?\);",
        re.DOTALL,
    )
    match = pattern.search(text)
    assert match is not None, f"{command} registration not found"
    return match.group(0)


def test_p1_custom_entity_core_is_objectdbx_project():
    text = NATIVE_DBX_PROJECT.read_text(encoding="utf-8")

    assert "dbx.props" in text
    assert "arx.props" not in text
    assert "<TargetName>Ariadne.AcadNativeDbx</TargetName>" in text
    assert 'ClCompile Include="AriadneDbxEntry.cpp"' in text
    assert 'ClCompile Include="..\\Ariadne.AcadNative\\AriadneProbe.cpp"' in text
    assert 'ClInclude Include="..\\Ariadne.AcadNative\\AriadneProbe.h"' in text


def test_native_build_script_builds_dbx_crx_and_arx_in_order():
    text = BUILD_NATIVE.read_text(encoding="utf-8")

    dbx_index = text.index("Ariadne.AcadNativeDbx.dbx.vcxproj")
    crx_index = text.index("Ariadne.AcadNative.crx.vcxproj")
    arx_index = text.index("Ariadne.AcadNative.arx.vcxproj")
    assert dbx_index < crx_index < arx_index
    assert "MSBuild.exe" in text
    assert "Ariadne.AcadNativeDbx.dbx" in text
    assert "Ariadne.AcadNative.crx" in text
    assert "Ariadne.AcadNative.arx" in text


def test_native_build_script_verifies_artifacts_under_requested_platform_and_configuration():
    text = BUILD_NATIVE.read_text(encoding="utf-8")

    bin_assignment = re.search(r"(?m)^\$bin\s*=\s*(.+)$", text)
    assert bin_assignment is not None
    assert "$Platform" in bin_assignment.group(1)
    assert "$Configuration" in bin_assignment.group(1)
    assert "bin\\x64\\Release" not in bin_assignment.group(1)


def test_arx_shell_loads_dbx_core_before_registering_job_command():
    text = NATIVE_ARX_ENTRY.read_text(encoding="utf-8")

    load_index = text.index("Ariadne.AcadNativeDbx.dbx")
    command_index = text.index("acedRegCmds->addCommand")
    assert load_index < command_index
    assert "acrxLoadModule" in text
    assert "acrxUnloadModule" in text


def test_native_job_command_registration_is_modal_session_command():
    text = NATIVE_ARX_ENTRY.read_text(encoding="utf-8")

    registration = _native_command_registration(text, "ARIADNE_NATIVE_JOB")
    assert "ACRX_CMD_MODAL" in registration
    assert "ACRX_CMD_SESSION" in registration


def test_native_session_job_locks_current_document_for_write_work():
    text = NATIVE_ARX_ENTRY.read_text(encoding="utf-8")

    assert '#include "acdocman.h"' in text
    assert "lockDocument" in text
    assert "unlockDocument" in text
    assert "AcAp::kWrite" in text
    assert text.index("lockDocument") < text.index("const std::string job =")


def test_arx_shell_keeps_editor_command_out_of_dbx_core():
    arx_project = NATIVE_ARX_PROJECT.read_text(encoding="utf-8")
    dbx_project = NATIVE_DBX_PROJECT.read_text(encoding="utf-8")

    assert "AriadneNativeJob.cpp" in arx_project
    assert "AriadneNativeJob.cpp" not in dbx_project


def test_core_console_command_shell_builds_as_crx():
    text = NATIVE_CRX_PROJECT.read_text(encoding="utf-8")

    assert "<TargetExt>.crx</TargetExt>" in text
    assert "<TargetName>Ariadne.AcadNative</TargetName>" in text
    assert "Ariadne.AcadNativeDbx.lib" in text
    assert 'ClCompile Include="AriadneNativeJob.cpp"' in text
    assert "AriadneProbe.cpp" not in text


def test_router_exposes_native_p1_job_lane():
    text = ROUTER.read_text(encoding="utf-8")

    assert "ARIADNE_NATIVE_JOB" in text
    assert "Ariadne.AcadNativeDbx.dbx" in text
    assert "Ariadne.AcadNative.crx" in text
    assert "extend.customclass.create" in text
    assert "inspect.customclass.count" in text
    assert "write.layer.create" in text
    assert "write.entity.line" in text
    assert "write.entity.circle" in text
    assert "inspect.entity.count" in text
    assert "write.xrecord.set" in text
    assert "inspect.xrecord.get" in text
    assert "write.xdata.set" in text
    assert "inspect.xdata.get" in text
    assert "write.block.simple_create" in text
    assert "write.block.insert" in text
    assert "inspect.block.count" in text
    assert "write.layout.create" in text
    assert "inspect.layout.list" in text
    assert "inspect.xref.list" in text
    assert "inspect.runtime.capabilities" in text
    assert "live.reactor.enable" in text
    assert "inspect.reactor.registry" in text
    assert "live.reactor.disable" in text
    assert "inspect.overrule.registry" in text
    assert "live.overrule.enable" in text
    assert "live.overrule.disable" in text
    assert "inspect.jig.host_support" in text
    assert "live.jig.point_probe" in text
    assert "extend.customobject.create" in text
    assert "inspect.customobject.count" in text
    assert "inspect.protocol.queryx" in text


def test_native_job_dispatcher_exposes_p2_batch1_database_crud():
    text = NATIVE_ARX_ENTRY.read_text(encoding="utf-8")

    assert 'op == "write.layer.create"' in text
    assert 'op == "write.entity.line"' in text
    assert 'op == "write.entity.circle"' in text
    assert 'op == "inspect.entity.count"' in text
    assert 'op == "write.xrecord.set"' in text
    assert 'op == "inspect.xrecord.get"' in text
    assert 'op == "write.xdata.set"' in text
    assert 'op == "inspect.xdata.get"' in text
    assert "appendLine" in text
    assert "appendCircle" in text
    assert "countModelSpaceEntitiesByType" in text
    assert "setXrecord" in text
    assert "getXrecord" in text
    assert "setDatabaseXdata" in text
    assert "getDatabaseXdata" in text


def test_native_job_dispatcher_exposes_p2_batch2_block_layout_xref_ops():
    text = NATIVE_ARX_ENTRY.read_text(encoding="utf-8")

    assert 'op == "write.block.simple_create"' in text
    assert 'op == "write.block.insert"' in text
    assert 'op == "inspect.block.count"' in text
    assert 'op == "write.layout.create"' in text
    assert 'op == "inspect.layout.list"' in text
    assert 'op == "inspect.xref.list"' in text
    assert "createSimpleBlock" in text
    assert "insertBlockReference" in text
    assert "countBlockDefinitions" in text
    assert "createLayout" in text
    assert "listLayouts" in text
    assert "listXrefs" in text


def test_native_job_dispatcher_exposes_p2_batch3_host_bound_capability_ops():
    text = NATIVE_ARX_ENTRY.read_text(encoding="utf-8")

    assert 'op == "inspect.runtime.capabilities"' in text
    assert 'op == "live.reactor.enable"' in text
    assert 'op == "inspect.reactor.registry"' in text
    assert 'op == "live.reactor.disable"' in text
    assert 'op == "inspect.overrule.registry"' in text
    assert 'op == "live.overrule.enable"' in text
    assert 'op == "live.overrule.disable"' in text
    assert 'op == "inspect.jig.host_support"' in text
    assert 'op == "live.jig.point_probe"' in text
    assert "runtimeCapabilitiesJson" in text
    assert "enableEditorReactor" in text
    assert "disableEditorReactor" in text
    assert "reactorRegistryJson" in text
    assert "overruleRegistryJson" in text
    assert "enableObjectOverrule" in text
    assert "disableObjectOverrule" in text
    assert "jigHostSupportJson" in text
    assert "runLineJigProbe" in text


def test_full_autocad_native_job_lane_uses_profile_env_and_live_runner():
    router = ROUTER.read_text(encoding="utf-8")
    native = NATIVE_ARX_ENTRY.read_text(encoding="utf-8")

    assert "Invoke-FullAutoCadCadJob" in router
    assert "ARIADNE_NATIVE_JOB_MAILBOX" in router
    assert "$jobFwd" in router
    assert "$resultFwd" in router
    assert "full_autocad_native_job_mailbox.txt" in router
    assert "ariadne-write-mailbox" in router
    assert "ariadne-arx-list" in router
    assert "ARIADNE.ACADNATIVE.ARX" in router
    assert "full_autocad_native_job" in router
    assert "Wait-NativeCadJobResult" in router
    assert "ExpectedOperation" in router
    assert "Wait-FullAutoCadIdle" in router
    assert "Wait-PathExists" in router
    assert "FULL_AUTOCAD_BUSY_BEFORE_SEND" in router
    assert "full_autocad_native_job_done.txt" in router
    assert "ariadne-write-done" in router
    assert "done_after" in router
    assert "idle_after" in router
    assert "vl-catch-all-apply ''arxload" in router

    assert "readJobPathSetting" in native
    assert "ariadneNativeJobArgs" in native
    assert "ariadneNativeJobMailbox" in native
    assert "readMailboxSetting" in native
    assert "readCommandArg" in native
    assert "acedGetEnv" in native
    assert native.index("acedGetEnv") < native.index("_wgetenv")
    assert "ARIADNE_CAD_JOB_HOST_MODE" in native
    assert "jobHostMode" in native


def test_native_job_command_does_not_print_full_json_to_autocad_console():
    native = NATIVE_ARX_ENTRY.read_text(encoding="utf-8")

    assert 'ARIADNE_NATIVE_JOB result written' in native
    assert 'ARIADNE_NATIVE_JOB result: %hs' not in native


def test_router_status_probes_native_modules_and_coreconsole_load():
    text = ROUTER.read_text(encoding="utf-8")

    assert "native_modules" in text
    assert "Test-NativeAcadModules" in text
    assert "coreconsole_load" in text
    assert "DBXLOAD_OK" in text
    assert "CRXLOAD_OK" in text


def test_p1_dbx_core_registers_custom_object_and_protocol_extension():
    project = NATIVE_DBX_PROJECT.read_text(encoding="utf-8")
    api = NATIVE_DBX_API.read_text(encoding="utf-8")
    entry = NATIVE_DBX_ENTRY.read_text(encoding="utf-8")

    assert "AriadneRecord.cpp" in project
    assert "AriadneProtocol.cpp" in project
    assert "ariadneCreateRecordObject" in api
    assert "ariadneIsRecordObject" in api
    assert "ariadneProbeProtocolAvailable" in api
    assert "AriadneRecord::rxInit" in entry
    assert "ariadneRegisterProbeProtocol" in entry
    assert "ariadneUnregisterProbeProtocol" in entry
