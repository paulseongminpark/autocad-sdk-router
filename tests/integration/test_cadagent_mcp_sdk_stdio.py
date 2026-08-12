#!/usr/bin/env python3
"""Real stdio contract for the official MCP SDK CADAgent host.

The test uses only nonexistent input paths and temporary output directories.
It verifies MCP framing, structured failures, and argument binding without
opening or modifying a DWG.
"""
from __future__ import annotations

import asyncio
import importlib.metadata
import inspect
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import cadagent_mcp  # noqa: E402
import cadagent_mcp_sdk  # noqa: E402


def _field(value: Any, camel_name: str, snake_name: str) -> Any:
    """Read one MCP model field across the v1/v2 Python spellings."""
    if hasattr(value, snake_name):
        return getattr(value, snake_name)
    return getattr(value, camel_name)


def _tool_schema(tool: Any) -> dict[str, Any]:
    return tool.model_dump(by_alias=True)["inputSchema"]


def test_adapter_callable_preserves_absent_and_null_without_var_kwargs():
    captured: list[dict[str, Any]] = []

    def capture(arguments: dict[str, Any]) -> dict[str, Any]:
        captured.append(arguments)
        return arguments

    callable_ = cadagent_mcp_sdk._make_adapter_callable(
        "cad.test", ["value", "legacy_value"], capture)
    parameters = inspect.signature(callable_).parameters.values()
    assert all(parameter.kind is not inspect.Parameter.VAR_KEYWORD for parameter in parameters)

    assert callable_(value="present") == {"value": "present"}
    assert callable_(value=None) == {"value": None}
    assert callable_(legacy_value="legacy") == {"legacy_value": "legacy"}
    assert captured == [
        {"value": "present"},
        {"value": None},
        {"legacy_value": "legacy"},
    ]


def test_dispatch_exception_becomes_a_structured_error_payload():
    def boom(_arguments: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("intentional adapter regression probe")

    payload = cadagent_mcp_sdk._call_handler("cad.test", boom, {})
    assert payload["ok"] is False
    assert payload["status"] == "error"
    assert "tool execution error" in payload["error"]


async def _exercise_persistent_stdio() -> None:
    from mcp import ClientSession, types
    from mcp.client.stdio import StdioServerParameters, stdio_client

    # stdio_client does not reliably inherit PYTHONPATH on every SDK version.
    # Passing the complete environment makes the same test work against the
    # isolated v2 target as well as the system v1 installation.
    server_env = dict(os.environ)
    server_env.setdefault("PYTHONUTF8", "1")
    server_env.setdefault("PYTHONIOENCODING", "utf-8")
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(_TOOLS / "cadagent_mcp.py"), "--serve"],
        cwd=str(_ROOT),
        env=server_env,
    )

    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            initialized = await session.initialize()
            server_info = _field(initialized, "serverInfo", "server_info")
            assert server_info.name == cadagent_mcp.SERVER_NAME
            assert server_info.version
            if importlib.metadata.version("mcp").split(".", 1)[0] == "2":
                # MCPServer v2 accepts the CADAgent version in its public
                # constructor; FastMCP v1 does not expose that argument.
                assert server_info.version == cadagent_mcp.SERVER_VERSION
            await session.send_notification(types.InitializedNotification())
            await session.send_ping()

            listed = await session.list_tools()
            expected_schemas = {
                definition["name"]: definition["inputSchema"]
                for definition in cadagent_mcp._TOOLS
            }
            actual_schemas = {tool.name: _tool_schema(tool) for tool in listed.tools}
            assert len(actual_schemas) == 19
            assert "cad.inspect_display_membership" in actual_schemas
            assert actual_schemas == expected_schemas

            resources = await session.list_resources()
            templates = await session.list_resource_templates()
            assert list(resources.resources) == []
            assert list(_field(templates, "resourceTemplates", "resource_templates")) == []

            for name in sorted(expected_schemas):
                result = await session.call_tool(name, {})
                payload = _field(result, "structuredContent", "structured_content")
                assert isinstance(payload, dict), name
                assert "ok" in payload, name
                assert _field(result, "isError", "is_error") is (payload["ok"] is False), name

            # The documented direct-script server runs as ``__main__``.  Its
            # v2 status projection must still bind handlers to this exact
            # cadagent_mcp.py module rather than trusting handler metadata.
            status_v2 = await session.call_tool(
                "cad.status", {"schema_version": 2}
            )
            status_v2_payload = _field(
                status_v2, "structuredContent", "structured_content"
            )
            assert _field(status_v2, "isError", "is_error") is False
            assert status_v2_payload["ok"] is True
            assert status_v2_payload["result"]["capability"]["mcp_surface"][
                "verification"
            ] == "VERIFIED"

            # Exercise the adapter through a real ClientSession rather than
            # its private callable.  The legacy names must reach the existing
            # handler and return its structured blocked envelope, not an SDK
            # argument-validation error.  The nonexistent input is deliberate:
            # no DWG is opened, while cadctl still records the received mode in
            # an artifact under this temporary directory.
            with tempfile.TemporaryDirectory(prefix="cadagent-mcp-wire-") as tmp:
                tmp_path = Path(tmp)
                missing_dwg = tmp_path / "does-not-exist.dwg"

                legacy_out = tmp_path / "legacy-alias"
                legacy = await session.call_tool(
                    "cad.inspect_drawing",
                    {"dwg_path": str(missing_dwg), "out_dir": str(legacy_out)},
                )
                legacy_payload = _field(legacy, "structuredContent", "structured_content")
                assert _field(legacy, "isError", "is_error") is False
                assert legacy_payload["ok"] is True
                assert legacy_payload["result"]["schema"] == "ariadne.cadctl.inspect.v1"
                assert legacy_payload["result"]["status"] == "blocked"
                assert legacy_payload["result"]["reason"] == "input DWG not found"

                # `mode` omitted is mapped by the handler to its default
                # ``graph`` value.  An explicit JSON null must instead survive
                # the SDK binder and reach that handler as None.  cadctl's
                # blocked-input job preserves the observable downstream mode:
                # graph -> IR, None -> extract.
                omitted_out = tmp_path / "mode-omitted"
                omitted = await session.call_tool(
                    "cad.inspect_drawing",
                    {"dwg": str(missing_dwg), "out": str(omitted_out)},
                )
                null_out = tmp_path / "mode-null"
                explicit_null = await session.call_tool(
                    "cad.inspect_drawing",
                    {"dwg": str(missing_dwg), "out": str(null_out), "mode": None},
                )
                for label, result in (("omitted", omitted), ("explicit null", explicit_null)):
                    payload = _field(result, "structuredContent", "structured_content")
                    assert _field(result, "isError", "is_error") is False, label
                    assert payload["ok"] is True, label
                    assert payload["result"]["status"] == "blocked", label

                omitted_job = json.loads(
                    (omitted_out / "cad_job.json").read_text(encoding="utf-8")
                )
                null_job = json.loads(
                    (null_out / "cad_job.json").read_text(encoding="utf-8")
                )
                assert omitted_job["output_mode"] == "ir"
                assert null_job["output_mode"] == "extract"

                # The PR66 tool must be callable through the same generated
                # adapter in both SDK majors.  Its legacy path aliases stay
                # accepted without leaking into the advertised closed schema.
                display_out = tmp_path / "display-membership-alias"
                display = await session.call_tool(
                    "cad.inspect_display_membership",
                    {
                        "dwg_path": str(missing_dwg),
                        "target_layers": ["W1"],
                        "out_dir": str(display_out),
                    },
                )
                display_payload = _field(
                    display, "structuredContent", "structured_content"
                )
                assert _field(display, "isError", "is_error") is False
                assert display_payload["ok"] is True
                assert display_payload["result"]["status"] == "BLOCKED"
                assert display_payload["result"]["geometry_scope"] == (
                    "strict_layer_entities_v1"
                )

                # Omission selects the handler default above; explicit null is
                # preserved and rejected by the handler as a structured error.
                display_null = await session.call_tool(
                    "cad.inspect_display_membership",
                    {
                        "dwg_path": str(missing_dwg),
                        "target_layers": ["W1"],
                        "geometry_scope": None,
                    },
                )
                display_null_payload = _field(
                    display_null, "structuredContent", "structured_content"
                )
                assert _field(display_null, "isError", "is_error") is True
                assert display_null_payload["ok"] is False
                assert "geometry_scope" in display_null_payload["error"]

            # The SDK owns this behavior: unlike the retired private handle_rpc
            # shim, an unregistered tool is a CallToolResult error rather than
            # a raw JSON-RPC -32601 response.
            unknown = await session.call_tool("cad.does_not_exist", {})
            assert _field(unknown, "isError", "is_error") is True
            assert _field(unknown, "structuredContent", "structured_content") is None
            assert any(
                getattr(content, "text", "").startswith("Unknown tool:")
                for content in unknown.content
            )


def test_official_mcp_sdk_persistent_stdio_contract():
    asyncio.run(_exercise_persistent_stdio())
