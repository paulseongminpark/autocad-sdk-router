from __future__ import annotations

import copy
import os
import subprocess
import sys
import types
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cadagent_mcp  # noqa: E402
from verification.mcp_surface import (  # noqa: E402
    REQUIRED_CAD_TOOL_DELEGATES,
    REQUIRED_CAD_TOOLS,
    verify_declared_tool_surface,
)


EXPECTED_TOOLS = frozenset(
    {
        "cad.status",
        "cad.inspect_drawing",
        "cad.query_entities",
        "cad.get_entity",
        "cad.validate_ir",
        "cad.registry_status",
        "cad.registry_explain",
        "cad.patch_dry_run",
        "cad.patch_apply_staged",
        "cad.anchor_set",
        "cad.anchor_get",
        "cad.anchor_list",
        "cad.anchor_clear",
        "cad.diff_before_after",
        "cad.visual_report",
        "cad.live_status",
        "cad.run_operation",
        "cad.run_command_template",
        "cad.inspect_display_membership",
    }
)


def test_declared_mcp_surface_is_verified_through_one_interface() -> None:
    receipt = verify_declared_tool_surface(cadagent_mcp._TOOLS, cadagent_mcp._DISPATCH)

    assert REQUIRED_CAD_TOOLS == EXPECTED_TOOLS
    assert receipt["verification"] == "VERIFIED"
    assert receipt["tool_count"] == 19
    assert frozenset(receipt["tool_names"]) == EXPECTED_TOOLS
    assert receipt["failures"] == []


def test_declared_input_schemas_are_valid_json_schema() -> None:
    for definition in cadagent_mcp._TOOLS:
        Draft202012Validator.check_schema(definition["inputSchema"])


def test_status_description_does_not_promote_historical_router_snapshot() -> None:
    definition = next(
        item for item in cadagent_mcp._TOOLS if item["name"] == "cad.status"
    )
    description = definition["description"]

    assert "checkout anchor" in description
    assert "declared capabilities" in description
    assert "proof with explicit binding metadata" in description
    assert "historical snapshots separately" in description
    assert "optionally adds an exact revision anchor" in description
    assert "does not run a live" in description
    assert "route_count/available/native" not in description


def test_declaration_dispatch_drift_is_invalid() -> None:
    dispatch = dict(cadagent_mcp._DISPATCH)
    dispatch.pop("cad.status")

    receipt = verify_declared_tool_surface(cadagent_mcp._TOOLS, dispatch)

    assert receipt["verification"] == "INVALID"
    assert "DECLARATION_DISPATCH_MISMATCH" in {
        failure["code"] for failure in receipt["failures"]
    }


def test_delegate_mapping_is_the_single_exact_product_contract() -> None:
    definitions = copy.deepcopy(cadagent_mcp._TOOLS)
    definitions[0]["delegates_to"] = "fake.module.handler"

    receipt = verify_declared_tool_surface(definitions, cadagent_mcp._DISPATCH)

    assert REQUIRED_CAD_TOOLS == frozenset(REQUIRED_CAD_TOOL_DELEGATES)
    assert receipt["verification"] == "INVALID"
    assert "DELEGATE_MISMATCH" in {
        failure["code"] for failure in receipt["failures"]
    }


def test_dispatch_values_must_be_callable_without_executing_handlers() -> None:
    class MustNotRun:
        def __call__(self, _arguments):
            raise AssertionError("surface verification executed a handler")

    dispatch = dict(cadagent_mcp._DISPATCH)
    dispatch["cad.status"] = MustNotRun()
    dispatch["cad.query_entities"] = None

    receipt = verify_declared_tool_surface(cadagent_mcp._TOOLS, dispatch)

    assert receipt["verification"] == "INVALID"
    failures = [
        failure
        for failure in receipt["failures"]
        if failure["code"] == "NON_CALLABLE_DISPATCH"
    ]
    assert failures == [{"code": "NON_CALLABLE_DISPATCH", "name": "cad.query_entities"}]


def test_each_tool_schema_is_bound_to_the_versioned_public_contract() -> None:
    mutations = []

    missing_required = copy.deepcopy(cadagent_mcp._TOOLS)
    inspect = next(
        item for item in missing_required if item["name"] == "cad.inspect_drawing"
    )
    inspect["inputSchema"]["required"].remove("dwg")
    mutations.append(missing_required)

    renamed_property = copy.deepcopy(cadagent_mcp._TOOLS)
    inspect = next(
        item for item in renamed_property if item["name"] == "cad.inspect_drawing"
    )
    inspect["inputSchema"]["properties"]["drawing"] = inspect["inputSchema"][
        "properties"
    ].pop("dwg")
    mutations.append(renamed_property)

    widened = copy.deepcopy(cadagent_mcp._TOOLS)
    status = next(item for item in widened if item["name"] == "cad.status")
    status["inputSchema"]["additionalProperties"] = True
    mutations.append(widened)

    for definitions in mutations:
        receipt = verify_declared_tool_surface(definitions, cadagent_mcp._DISPATCH)

        assert receipt["verification"] == "INVALID"
        assert "INPUT_SCHEMA_CONTRACT_MISMATCH" in {
            failure["code"] for failure in receipt["failures"]
        }


def test_dispatch_handler_identity_is_bound_without_executing_handlers() -> None:
    dispatch = dict(cadagent_mcp._DISPATCH)
    dispatch["cad.status"], dispatch["cad.query_entities"] = (
        dispatch["cad.query_entities"],
        dispatch["cad.status"],
    )

    receipt = verify_declared_tool_surface(cadagent_mcp._TOOLS, dispatch)

    assert receipt["verification"] == "INVALID"
    mismatches = [
        failure
        for failure in receipt["failures"]
        if failure["code"] == "DISPATCH_HANDLER_MISMATCH"
    ]
    assert {failure["name"] for failure in mismatches} == {
        "cad.status",
        "cad.query_entities",
    }


def test_dispatch_handler_metadata_cannot_spoof_function_identity() -> None:
    def forged_status(_arguments):
        raise AssertionError("surface verification executed a forged handler")

    forged_status.__name__ = "_tool_status"
    forged_status.__module__ = cadagent_mcp.__name__
    dispatch = dict(cadagent_mcp._DISPATCH)
    dispatch["cad.status"] = forged_status

    receipt = verify_declared_tool_surface(cadagent_mcp._TOOLS, dispatch)

    assert receipt["verification"] == "INVALID"
    assert {
        failure["code"] for failure in receipt["failures"]
    } >= {"DISPATCH_HANDLER_MISMATCH"}


def test_dispatch_handler_cannot_choose_a_different_authority_module() -> None:
    forged_module = types.ModuleType("spec_review_fake_handlers")

    def forged_status(_arguments):
        raise AssertionError("surface verification executed a forged handler")

    forged_status.__name__ = "_tool_status"
    forged_status.__module__ = forged_module.__name__
    forged_module._tool_status = forged_status
    sys.modules[forged_module.__name__] = forged_module
    try:
        dispatch = dict(cadagent_mcp._DISPATCH)
        dispatch["cad.status"] = forged_status

        receipt = verify_declared_tool_surface(cadagent_mcp._TOOLS, dispatch)
    finally:
        sys.modules.pop(forged_module.__name__, None)

    assert receipt["verification"] == "INVALID"
    assert {
        failure["code"] for failure in receipt["failures"]
    } >= {"DISPATCH_HANDLER_MISMATCH"}


def test_malformed_inputs_return_structured_invalid_receipts() -> None:
    malformed_definitions = verify_declared_tool_surface([None, "not-a-mapping"], {})
    missing_definitions = verify_declared_tool_surface(None, cadagent_mcp._DISPATCH)
    malformed_dispatch = verify_declared_tool_surface(cadagent_mcp._TOOLS, None)

    for receipt in (malformed_definitions, missing_definitions, malformed_dispatch):
        assert receipt["schema"] == "cadagent.mcp_surface_verification.v1"
        assert receipt["verification"] == "INVALID"

    assert [
        failure
        for failure in malformed_definitions["failures"]
        if failure["code"] == "INVALID_TOOL_DEFINITION"
    ] == [
        {"code": "INVALID_TOOL_DEFINITION", "index": 0},
        {"code": "INVALID_TOOL_DEFINITION", "index": 1},
    ]
    assert "INVALID_DEFINITIONS" in {
        failure["code"] for failure in missing_definitions["failures"]
    }
    assert "INVALID_DISPATCH" in {
        failure["code"] for failure in malformed_dispatch["failures"]
    }


def test_cadagent_mcp_imports_from_package_and_script_pythonpaths(
    tmp_path: Path,
) -> None:
    cases = (
        (ROOT, "tools.cadagent_mcp"),
        (TOOLS, "cadagent_mcp"),
    )
    for pythonpath, module_name in cases:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(pythonpath)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import importlib, sys; "
                    "module = importlib.import_module(sys.argv[1]); "
                    "print(len(module._TOOLS))"
                ),
                module_name,
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert completed.returncode == 0, (
            f"{module_name} via {pythonpath}: {completed.stdout}{completed.stderr}"
        )
        assert completed.stdout.strip() == "19"


def test_duplicate_or_malformed_declaration_is_invalid() -> None:
    definitions = copy.deepcopy(cadagent_mcp._TOOLS)
    definitions.append(copy.deepcopy(definitions[0]))
    definitions[1]["delegates_to"] = ""
    definitions[2]["inputSchema"] = {"type": "string"}

    receipt = verify_declared_tool_surface(definitions, cadagent_mcp._DISPATCH)

    assert receipt["verification"] == "INVALID"
    codes = {failure["code"] for failure in receipt["failures"]}
    assert {
        "DUPLICATE_TOOL_NAME",
        "MISSING_DELEGATE",
        "INVALID_INPUT_SCHEMA",
    } <= codes
