"""Official MCP Python SDK adapter for :mod:`cadagent_mcp`.

The CADAgent tool catalogue predates the SDK and deliberately retains a few
legacy argument aliases.  The SDK derives its runtime argument binder from a
callable signature, while the advertised schema must remain the exact existing
``inputSchema``.  This module bridges those two contracts without making the
legacy aliases visible in ``tools/list``.
"""
from __future__ import annotations

import copy
import json
import keyword
import warnings
from typing import Any, Callable, Dict, Iterable, Tuple


class _Missing:
    """Private default which distinguishes an omitted key from JSON ``null``."""


_MISSING = _Missing()

# These aliases are already accepted by the CADAgent handlers.  They cannot be
# placed in _TOOLS because tools/list must preserve the published schemas
# exactly. ``cad.inspect_display_membership`` uses the same hidden path aliases
# as the older inspection tools while keeping the closed schema unchanged.
_LEGACY_ALIASES: Dict[str, Tuple[str, ...]] = {
    "cad.inspect_drawing": ("dwg_path", "out_dir"),
    "cad.query_entities": ("ir_path",),
    "cad.get_entity": ("ir_path",),
    "cad.validate_ir": ("ir_path",),
    "cad.registry_explain": ("operation", "id"),
    "cad.patch_apply_staged": ("dwg", "out"),
    "cad.anchor_set": ("dwg_path", "out_dir"),
    "cad.anchor_get": ("ir_path",),
    "cad.anchor_list": ("ir_path",),
    "cad.anchor_clear": ("dwg_path", "out_dir"),
    "cad.diff_before_after": ("pre_ir_path", "pre", "post_ir_path", "post"),
    "cad.visual_report": ("source", "ir", "dwg"),
    "cad.run_operation": ("operation", "id", "dwg_path", "out_dir"),
    "cad.run_command_template": ("dwg_path",),
    "cad.inspect_display_membership": ("dwg_path", "out_dir"),
}


def _parameter_names(tool_name: str, definition: Dict[str, Any]) -> list[str]:
    """Return schema keys plus legacy aliases, preserving first occurrence."""
    schema = definition["inputSchema"]
    names = list(schema.get("properties", {}).keys())
    names.extend(alias for alias in _LEGACY_ALIASES.get(tool_name, ()) if alias not in names)
    for name in names:
        if not isinstance(name, str) or not name.isidentifier() or keyword.iskeyword(name):
            raise ValueError("MCP adapter cannot expose invalid Python parameter %r for %s" %
                             (name, tool_name))
    return names


def _make_adapter_callable(
    tool_name: str,
    parameter_names: Iterable[str],
    dispatch: Callable[[Dict[str, Any]], Any],
) -> Callable[..., Any]:
    """Build an explicit keyword-only callable for the SDK's Pydantic binder.

    Deliberately do not use ``**kwargs``: Pydantic's generated binder treats a
    synthetic var-keyword parameter as a required ``kwargs`` field.  Each value
    instead has an ``Any`` annotation and a private missing sentinel, so omitted
    optional values are not accidentally converted to ``None``.
    """
    names = list(parameter_names)
    for name in names:
        if not name.isidentifier() or keyword.iskeyword(name):
            raise ValueError("MCP adapter cannot expose invalid Python parameter %r for %s" %
                             (name, tool_name))

    if names:
        signature = ", ".join("%s: Any = _MISSING" % name for name in names)
        values = ", ".join("%r: %s" % (name, name) for name in names)
        source = "def adapter(*, %s):\n    return _dispatch({%s})\n" % (signature, values)
    else:
        source = "def adapter():\n    return _dispatch({})\n"

    def invoke(values: Dict[str, Any]) -> Any:
        # Pydantic may copy default values; isinstance is intentionally used
        # rather than identity so all missing-sentinel instances are removed.
        arguments = {
            name: value for name, value in values.items()
            if not isinstance(value, _Missing)
        }
        return dispatch(arguments)

    namespace: Dict[str, Any] = {
        "Any": Any,
        "_MISSING": _MISSING,
        "_dispatch": invoke,
    }
    exec(compile(source, "<cadagent MCP adapter %s>" % tool_name, "exec"), namespace)
    adapter = namespace["adapter"]
    adapter.__name__ = "adapter_" + tool_name.replace(".", "_")
    adapter.__qualname__ = adapter.__name__
    adapter.__doc__ = "SDK adapter for %s" % tool_name
    return adapter


def _call_handler(
    tool_name: str,
    handler: Callable[[Dict[str, Any]], Dict[str, Any]],
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    """Run a legacy handler without allowing an exception to escape MCP."""
    try:
        payload = handler(arguments)
    except Exception as exc:  # noqa: BLE001 - MCP must return a model-readable failure.
        return {
            "ok": False,
            "status": "error",
            "error": "tool execution error: %r" % exc,
            "tool": tool_name,
        }
    if isinstance(payload, dict):
        return payload
    return {
        "ok": False,
        "status": "error",
        "error": "tool handler returned %s instead of a dict" % type(payload).__name__,
        "tool": tool_name,
    }


def _call_tool_result(types: Any, payload: Dict[str, Any]) -> Any:
    """Return the same structured envelope for success and truthful failure."""
    return types.CallToolResult(
        content=[types.TextContent(
            type="text",
            text=json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        )],
        structuredContent=payload,
        isError=(payload.get("ok") is False),
    )


def _sdk_symbols() -> tuple[Any, Any, Any, str]:
    """Load the official high-level server from either supported SDK major."""
    try:
        from mcp import types
        from mcp.server import MCPServer
        from mcp.server.mcpserver.tools import Tool
    except ImportError:
        try:
            from mcp import types
            from mcp.server.fastmcp import FastMCP
            from mcp.server.fastmcp.tools import Tool
        except ImportError as exc:
            raise RuntimeError(
                "CADAgent requires the official MCP Python SDK; install requirements.txt "
                "for v1 or use the isolated v2 matrix target."
            ) from exc
        return FastMCP, Tool, types, "v1"
    return MCPServer, Tool, types, "v2"


def _sdk_tool(
    module: Any,
    definition: Dict[str, Any],
    tool_class: Any,
    types: Any,
) -> Any:
    tool_name = definition["name"]
    handler = module._DISPATCH[tool_name]

    def dispatch(arguments: Dict[str, Any]) -> Any:
        payload = _call_handler(tool_name, handler, arguments)
        return _call_tool_result(types, payload)

    callable_ = _make_adapter_callable(
        tool_name,
        _parameter_names(tool_name, definition),
        dispatch,
    )
    # Tool.from_function correctly builds its runtime Pydantic binder from the
    # explicit callable above.  The public schema is then restored exactly to
    # the pre-SDK contract, excluding only hidden legacy aliases.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tool = tool_class.from_function(
            callable_,
            name=tool_name,
            description=definition.get("description", ""),
            structured_output=False,
        )
    tool.parameters = copy.deepcopy(definition["inputSchema"])
    return tool


def build_server(module: Any) -> Any:
    """Create the same tool surface under system SDK v1 or isolated SDK v2."""
    server_class, tool_class, types, generation = _sdk_symbols()
    tools = [_sdk_tool(module, definition, tool_class, types) for definition in module._TOOLS]
    if generation == "v2":
        return server_class(module.SERVER_NAME, version=module.SERVER_VERSION, tools=tools)
    # FastMCP v1 does not offer a public server-version constructor argument.
    return server_class(module.SERVER_NAME, tools=tools)


def serve_stdio(module: Any) -> int:
    """Run the official SDK's persistent stdio transport."""
    build_server(module).run(transport="stdio")
    return 0
