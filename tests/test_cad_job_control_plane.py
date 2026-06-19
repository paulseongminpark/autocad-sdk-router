import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "tools" / "autocad-router.ps1"
COMMANDS = ROOT / "src" / "Ariadne.DwgGeometryExtractor" / "Commands.cs"
JOB_RUNNER = ROOT / "src" / "Ariadne.DwgGeometryExtractor" / "CadJobRunner.cs"
JOB_DTOS = ROOT / "src" / "Ariadne.DwgGeometryExtractor" / "CadJobDtos.cs"
JOB_SCHEMA = ROOT / "schemas" / "cad_job.schema.json"
SDK_CATALOG = ROOT / "config" / "autocad_official_sdk_catalog.json"


def test_router_exposes_cad_job_protocol_and_write_modes():
    text = ROUTER.read_text(encoding="utf-8")

    assert "JobPath" in text
    assert "ARIADNE_CAD_JOB_IN" in text
    assert "ARIADNE_CAD_JOB_OUT" in text
    assert "ARIADNE_CAD_JOB" in text
    assert "write_original" in text
    assert "live_edit" in text
    assert "SDK_OPERATION_NOT_IMPLEMENTED" not in text


def test_autocad_plugin_exposes_cad_job_command():
    commands = COMMANDS.read_text(encoding="utf-8")
    runner = JOB_RUNNER.read_text(encoding="utf-8")
    dtos = JOB_DTOS.read_text(encoding="utf-8")

    assert '[CommandMethod("ARIADNE_CAD_JOB", CommandFlags.Session)]' in commands
    assert "CadJobRunner" in commands
    assert "inspect.database.summary" in runner
    assert "write.layer.create" in runner
    assert "write.entity.line" in runner
    assert "write.xrecord.set" in runner
    assert "CadJobRequest" in dtos
    assert "CadJobResult" in dtos


def test_cad_job_command_locks_document_before_write_operations():
    commands = COMMANDS.read_text(encoding="utf-8")

    command_index = commands.index("public void RunCadJob()")
    lock_index = commands.index("LockDocument()", command_index)
    runner_index = commands.index("runner.Run", command_index)
    assert lock_index < runner_index


def test_write_original_persistence_is_done_by_router_qsave_not_database_saveas():
    commands = COMMANDS.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")

    command_index = commands.index("public void RunCadJob()")
    assert "Database.SaveAs" not in commands[command_index:]
    assert "QSAVE" in router
    assert "write_original" in router


def test_cad_job_schema_documents_supported_operations_and_safety_modes():
    schema = json.loads(JOB_SCHEMA.read_text(encoding="utf-8"))

    assert schema["title"] == "Ariadne AutoCAD SDK Job"
    props = schema["properties"]
    assert props["operation"]["enum"] == [
        "inspect.database.summary",
        "write.layer.create",
        "write.entity.line",
        "write.entity.circle",
        "inspect.entity.count",
        "write.xrecord.set",
        "inspect.xrecord.get",
        "write.xdata.set",
        "inspect.xdata.get",
        "write.block.simple_create",
        "write.block.insert",
        "inspect.block.count",
        "write.layout.create",
        "inspect.layout.list",
        "inspect.xref.list",
        "inspect.runtime.capabilities",
        "live.reactor.enable",
        "inspect.reactor.registry",
        "live.reactor.disable",
        "inspect.overrule.registry",
        "live.overrule.enable",
        "live.overrule.disable",
        "inspect.jig.host_support",
        "live.jig.point_probe",
        "extend.customclass.create",
        "inspect.customclass.count",
        "extend.customobject.create",
        "inspect.customobject.count",
        "inspect.protocol.queryx",
    ]
    assert "write_original" in props["write_mode"]["enum"]
    assert "live_edit" in props["write_mode"]["enum"]
    assert schema["required"] == ["operation"]

    customclass_rule = next(
        rule for rule in schema["allOf"]
        if rule["if"]["properties"]["operation"]["const"] == "extend.customclass.create"
    )
    class_args = customclass_rule["then"]["properties"]["args"]
    assert class_args["required"] == ["center", "size"]
    assert class_args["properties"]["center"]["$ref"] == "#/$defs/point"

    customobject_rule = next(
        rule for rule in schema["allOf"]
        if rule["if"]["properties"]["operation"]["const"] == "extend.customobject.create"
    )
    object_args = customobject_rule["then"]["properties"]["args"]
    assert object_args["required"] == ["key", "value"]
    assert object_args["properties"]["key"]["minLength"] == 1

    xrecord_get_rule = next(
        rule for rule in schema["allOf"]
        if rule["if"]["properties"]["operation"]["const"] == "inspect.xrecord.get"
    )
    assert xrecord_get_rule["then"]["properties"]["args"]["required"] == ["key"]

    circle_rule = next(
        rule for rule in schema["allOf"]
        if rule["if"]["properties"]["operation"]["const"] == "write.entity.circle"
    )
    circle_args = circle_rule["then"]["properties"]["args"]
    assert circle_args["required"] == ["center", "radius"]
    assert circle_args["properties"]["center"]["$ref"] == "#/$defs/point"
    assert circle_args["properties"]["radius"]["exclusiveMinimum"] == 0

    entity_count_rule = next(
        rule for rule in schema["allOf"]
        if rule["if"]["properties"]["operation"]["const"] == "inspect.entity.count"
    )
    assert entity_count_rule["then"]["properties"]["args"]["properties"]["type"]["type"] == "string"

    xdata_set_rule = next(
        rule for rule in schema["allOf"]
        if rule["if"]["properties"]["operation"]["const"] == "write.xdata.set"
    )
    xdata_args = xdata_set_rule["then"]["properties"]["args"]
    assert xdata_args["required"] == ["app", "value"]
    assert xdata_args["properties"]["app"]["minLength"] == 1

    xdata_get_rule = next(
        rule for rule in schema["allOf"]
        if rule["if"]["properties"]["operation"]["const"] == "inspect.xdata.get"
    )
    assert xdata_get_rule["then"]["properties"]["args"]["required"] == ["app"]

    point_probe_rule = next(
        rule for rule in schema["allOf"]
        if rule["if"]["properties"]["operation"]["const"] == "live.jig.point_probe"
    )
    assert point_probe_rule["then"]["properties"]["args"]["required"] == ["point"]
    assert point_probe_rule["then"]["properties"]["args"]["properties"]["point"]["$ref"] == "#/$defs/point"

    block_create_rule = next(
        rule for rule in schema["allOf"]
        if rule["if"]["properties"]["operation"]["const"] == "write.block.simple_create"
    )
    block_args = block_create_rule["then"]["properties"]["args"]
    assert block_args["required"] == ["name"]
    assert block_args["properties"]["name"]["minLength"] == 1

    block_insert_rule = next(
        rule for rule in schema["allOf"]
        if rule["if"]["properties"]["operation"]["const"] == "write.block.insert"
    )
    insert_args = block_insert_rule["then"]["properties"]["args"]
    assert insert_args["required"] == ["name", "position"]
    assert insert_args["properties"]["position"]["$ref"] == "#/$defs/point"

    layout_create_rule = next(
        rule for rule in schema["allOf"]
        if rule["if"]["properties"]["operation"]["const"] == "write.layout.create"
    )
    assert layout_create_rule["then"]["properties"]["args"]["required"] == ["name"]


def test_official_sdk_catalog_has_native_first_full_family_surface():
    catalog = json.loads(SDK_CATALOG.read_text(encoding="utf-8"))

    assert catalog["schema"] == "ariadne.autocad_official_sdk_catalog.v1"
    assert catalog["real_dwg_policy"] == "excluded"
    assert catalog["priority_order"][0] == "native_objectarx_objectdbx"
    family_ids = {family["id"] for family in catalog["families"]}
    assert {
        "runtime_commands",
        "objectdbx_database",
        "entities",
        "blocks_xrefs_clone",
        "geometry_kernel",
        "brep_solids",
        "graphics_system",
        "editor_input",
        "reactors_events",
        "custom_objects_protocols",
        "constraints_associativity",
        "layouts_plot_publish",
        "ui_customization",
        "com_activex",
        "autolisp_visual_lisp",
        "core_console",
        "active_document_write_original",
    }.issubset(family_ids)
    assert catalog["local_sdk_evidence"]["managed_xml_member_total"] > 1000
    assert catalog["local_sdk_evidence"]["native_header_count"] > 100
