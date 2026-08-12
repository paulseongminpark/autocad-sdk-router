"""Verify the declared CADAgent MCP tool surface without running handlers."""

from __future__ import annotations

import hashlib
import inspect
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any


_CADAGENT_MODULE_NAMES = ("cadagent_mcp", "tools.cadagent_mcp", "__main__")
_CADAGENT_MODULE_PATH = (Path(__file__).resolve().parents[1] / "cadagent_mcp.py")


REQUIRED_CAD_TOOL_DELEGATES: Mapping[str, str] = MappingProxyType(
    {
        "cad.status": "cadctl.Cad.status",
        "cad.inspect_drawing": "cadctl.Cad.inspect",
        "cad.query_entities": "cadctl.Cad.query",
        "cad.get_entity": "cadctl.Cad.query",
        "cad.validate_ir": "validator.validate_target",
        "cad.registry_status": "cadctl.Cad.registry_coverage",
        "cad.registry_explain": "cadctl.Cad.registry_explain",
        "cad.patch_dry_run": "cadctl.Cad.patch_dry_run",
        "cad.patch_apply_staged": "patch_engine.apply_staged",
        "cad.anchor_set": "cadctl.Cad.anchor_set",
        "cad.anchor_get": "cadctl.Cad.anchor_get",
        "cad.anchor_list": "cadctl.Cad.anchor_list",
        "cad.anchor_clear": "cadctl.Cad.anchor_clear",
        "cad.diff_before_after": "cadctl.Cad.diff_before_after",
        "cad.visual_report": "cadctl.Cad.visual_report",
        "cad.live_status": "cadctl.Cad.live_status",
        "cad.run_operation": "cadctl.Cad.run_operation",
        "cad.inspect_display_membership": "cadctl.Cad.inspect_display_membership",
        "cad.run_command_template": "cadctl.Cad.run_command_template",
    }
)
REQUIRED_CAD_TOOLS = frozenset(REQUIRED_CAD_TOOL_DELEGATES)

# Independent public compatibility contract. The digest covers the complete
# JSON input schema, including required fields, nested types and whether extra
# properties are accepted. Handler names bind each declaration to the wrapper
# that implements it without importing or executing any handler here.
MCP_TOOL_CONTRACT_V1: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        "cad.status": (
            "c7c665608ac8a02b6355ddd780d80c50dff8b4c625a04ff3010ea4ea002b0e49",
            "_tool_status",
        ),
        "cad.inspect_drawing": (
            "1bdf82e55af84f01d2b1432c222c3444acd43a48f5d05a755d64d327555a96a3",
            "_tool_inspect_drawing",
        ),
        "cad.query_entities": (
            "882ed2425451ff09414e028304446be6013cf0b78bafb19eb3e93abe5b8c4751",
            "_tool_query_entities",
        ),
        "cad.get_entity": (
            "1168d5599bc3bea9bbcda51b2c4a19f73acce570db027a6ebbc63805569bcf3a",
            "_tool_get_entity",
        ),
        "cad.validate_ir": (
            "4739e8105aaf831ad49adc734007a6e269efc2f894ae9ee3a899b424c51c4f43",
            "_tool_validate_ir",
        ),
        "cad.registry_status": (
            "99334726611ccf58a148b0814696bfa6fe08c1b2d027e946beccf5a74331c9aa",
            "_tool_registry_status",
        ),
        "cad.registry_explain": (
            "25aead617ac59581a74943af1b956e6b55eb3e2695936d029ed562c787d74a3e",
            "_tool_registry_explain",
        ),
        "cad.patch_dry_run": (
            "eeaff4c30a3bfea128beb4343458e0d217fbf6b5a250ff4f2f776caf42a89401",
            "_tool_patch_dry_run",
        ),
        "cad.patch_apply_staged": (
            "fabd0dd36b470766708a3edd5c1793416f492d6e32c3b78cc6de4c80708f923c",
            "_tool_patch_apply_staged",
        ),
        "cad.anchor_set": (
            "628608236c83431084c24c9452db8f9c3505b19bcc7371142f08c04c7126b672",
            "_tool_anchor_set",
        ),
        "cad.anchor_get": (
            "05f0de79d48e29f41d02ab0371fb916be8d737e45c0377ea78b770df71b3f9f9",
            "_tool_anchor_get",
        ),
        "cad.anchor_list": (
            "3d3ec6592c5fb9611e936701053a82bd974a92318e7e32b8d1026bda33eef878",
            "_tool_anchor_list",
        ),
        "cad.anchor_clear": (
            "8429d7153122b1774d5b09581d39ff3f094803ae58c58be3940de3583c448fd1",
            "_tool_anchor_clear",
        ),
        "cad.diff_before_after": (
            "eb97905d7ade3aa7d3a37c9a63ef5ad6e3b0110d9357a1d7a18d0dba087fa8e9",
            "_tool_diff_before_after",
        ),
        "cad.visual_report": (
            "3a068a8fc82e029df18434e80c0845b79e175a9111edc3ed0f9e5d8b2d358f66",
            "_tool_visual_report",
        ),
        "cad.live_status": (
            "99334726611ccf58a148b0814696bfa6fe08c1b2d027e946beccf5a74331c9aa",
            "_tool_live_status",
        ),
        "cad.run_operation": (
            "e7e397b2b9e104052978abbc8da7efed1a945798e8c3eff069fcfe7380674759",
            "_tool_run_operation",
        ),
        "cad.inspect_display_membership": (
            "9999566e76336f645c2e34dc06574d72f11c491a39225f70a1a975e37d49bece",
            "_tool_inspect_display_membership",
        ),
        "cad.run_command_template": (
            "2955384c1f37dc6e87b22a19aaa4efd6a859e0042d9a3155f5e4a0f4a87ea6a3",
            "_tool_run_command_template",
        ),
    }
)


def _input_schema_digest(input_schema: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        input_schema,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _failure(code: str, **details: Any) -> dict[str, Any]:
    return {"code": code, **details}


def _canonical_handler_module(definitions: object) -> object | None:
    """Find the loaded CADAgent module that owns this exact declaration list.

    The dispatch table is the value under review, so handler metadata must not
    choose its own authority module.  Declaration-list identity gives the
    verifier an independent route back to the already-loaded product module.
    """

    matches = [
        module
        for name in _CADAGENT_MODULE_NAMES
        if (module := sys.modules.get(name)) is not None
        and getattr(module, "_TOOLS", None) is definitions
        and isinstance(getattr(module, "__file__", None), str)
        and Path(module.__file__).resolve() == _CADAGENT_MODULE_PATH
    ]
    return matches[0] if len(matches) == 1 else None


def verify_declared_tool_surface(
    definitions: object,
    dispatch: object,
) -> dict[str, Any]:
    """Return a deterministic receipt for the static MCP declaration seam."""

    failures: list[dict[str, Any]] = []
    names: list[str] = []

    if isinstance(definitions, Sequence) and not isinstance(
        definitions, (str, bytes, bytearray)
    ):
        normalized_definitions = definitions
    else:
        normalized_definitions = ()
        failures.append(
            _failure(
                "INVALID_DEFINITIONS",
                actual_type=type(definitions).__name__,
            )
        )

    if isinstance(dispatch, Mapping):
        normalized_dispatch = dispatch
    else:
        normalized_dispatch = {}
        failures.append(
            _failure(
                "INVALID_DISPATCH",
                actual_type=type(dispatch).__name__,
            )
        )

    for index, definition in enumerate(normalized_definitions):
        if not isinstance(definition, Mapping):
            failures.append(_failure("INVALID_TOOL_DEFINITION", index=index))
            continue
        name = definition.get("name")
        if not isinstance(name, str) or not name:
            failures.append(_failure("INVALID_TOOL_NAME", index=index))
            continue
        names.append(name)
        if not name.startswith("cad."):
            failures.append(_failure("INVALID_TOOL_NAMESPACE", name=name))

        delegate = definition.get("delegates_to")
        if not isinstance(delegate, str) or not delegate.strip():
            failures.append(_failure("MISSING_DELEGATE", name=name))
        elif name in REQUIRED_CAD_TOOL_DELEGATES:
            expected_delegate = REQUIRED_CAD_TOOL_DELEGATES[name]
            if delegate != expected_delegate:
                failures.append(
                    _failure(
                        "DELEGATE_MISMATCH",
                        name=name,
                        expected=expected_delegate,
                        actual=delegate,
                    )
                )

        input_schema = definition.get("inputSchema")
        if not isinstance(input_schema, Mapping) or input_schema.get("type") != "object":
            failures.append(_failure("INVALID_INPUT_SCHEMA", name=name))
        elif name in MCP_TOOL_CONTRACT_V1:
            expected_digest, _expected_handler = MCP_TOOL_CONTRACT_V1[name]
            try:
                actual_digest = _input_schema_digest(input_schema)
            except (TypeError, ValueError) as exc:
                failures.append(
                    _failure(
                        "INVALID_INPUT_SCHEMA",
                        name=name,
                        reason=type(exc).__name__,
                    )
                )
            else:
                if actual_digest != expected_digest:
                    failures.append(
                        _failure(
                            "INPUT_SCHEMA_CONTRACT_MISMATCH",
                            name=name,
                            expected_sha256=expected_digest,
                            actual_sha256=actual_digest,
                        )
                    )

    duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
    if duplicates:
        failures.append(_failure("DUPLICATE_TOOL_NAME", names=duplicates))

    declared = frozenset(names)
    if declared != REQUIRED_CAD_TOOLS:
        failures.append(
            _failure(
                "REQUIRED_TOOL_SET_MISMATCH",
                missing=sorted(REQUIRED_CAD_TOOLS - declared),
                extra=sorted(declared - REQUIRED_CAD_TOOLS),
            )
        )

    handler_module = _canonical_handler_module(definitions)
    if handler_module is None:
        failures.append(_failure("HANDLER_AUTHORITY_UNBOUND"))

    dispatched_names: list[str] = []
    for name, handler in normalized_dispatch.items():
        if not isinstance(name, str) or not name:
            failures.append(
                _failure(
                    "INVALID_DISPATCH_NAME",
                    actual_type=type(name).__name__,
                )
            )
            continue
        dispatched_names.append(name)
        if not callable(handler):
            failures.append(_failure("NON_CALLABLE_DISPATCH", name=name))
        elif name in MCP_TOOL_CONTRACT_V1:
            _expected_digest, expected_handler = MCP_TOOL_CONTRACT_V1[name]
            actual_handler = getattr(handler, "__name__", None)
            canonical_handler = (
                getattr(handler_module, expected_handler, None)
                if handler_module is not None
                else None
            )
            if (
                not inspect.isfunction(handler)
                or handler is not canonical_handler
            ):
                failures.append(
                    _failure(
                        "DISPATCH_HANDLER_MISMATCH",
                        name=name,
                        expected=expected_handler,
                        actual=actual_handler,
                    )
                )
    dispatched = frozenset(dispatched_names)
    if declared != dispatched:
        failures.append(
            _failure(
                "DECLARATION_DISPATCH_MISMATCH",
                missing_dispatch=sorted(declared - dispatched),
                undeclared_dispatch=sorted(dispatched - declared),
            )
        )

    failures.sort(key=lambda item: (str(item.get("code")), str(item)))
    return {
        "schema": "cadagent.mcp_surface_verification.v1",
        "contract": "cadagent.mcp_tool_contract.v1",
        "verification": "INVALID" if failures else "VERIFIED",
        "tool_count": len(declared),
        "tool_names": sorted(declared),
        "failures": failures,
    }
