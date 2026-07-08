#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""anon_block_probe -- gap map for block references naming undefined block defs.

EXP-C: R3b deferred ~320 nested block references naming anonymous dynamic-block
definitions ('*U172', '*U144', ...) that are absent from the IR's
block_definitions[] section, so nested synthesis cannot rebuild them. This
tool measures the exact gap: which names are referenced but undefined, from
where, and whether the IR carries any trace of them at all. It is a measurer,
not a gate -- it always exits 0 when it can read the IR (findings live in the
report, not in the exit code).

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

SCHEMA = "ariadne.anon_block_probe.v1"
MAX_REFERENCED_FROM_SAMPLES = 5
_JSON_ENCODING = "utf-8-sig"

_FINDINGS_HYPOTHESES = (
    "(H1) extractor skips anonymous defs",
    "(H2) anonymous defs live under a different IR section",
    "(H3) dynamic-block instances materialize per-insert and only the *U name is recorded",
)


def load_ir(path: str) -> Dict[str, Any]:
    """Load an IR JSON document (BOM-tolerant, matches sibling tools)."""
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _block_ref_name(entity: Any) -> Any:
    """Return geometry.block_name if entity is a block_reference, else None."""
    if not isinstance(entity, dict):
        return None
    geometry = entity.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("kind") != "block_reference":
        return None
    return geometry.get("block_name") or None


def analyze(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Compute referenced-vs-defined block name gap map for one IR document."""
    entities = ir.get("entities") or []
    block_definitions = ir.get("block_definitions") or []

    defined_names: List[str] = [
        bd["name"] for bd in block_definitions if isinstance(bd, dict) and bd.get("name")
    ]
    defined_set = set(defined_names)

    referenced_names: Dict[str, int] = {}
    referenced_from: Dict[str, List[str]] = {}

    def record(name: str, origin: str) -> None:
        referenced_names[name] = referenced_names.get(name, 0) + 1
        samples = referenced_from.setdefault(name, [])
        if len(samples) < MAX_REFERENCED_FROM_SAMPLES:
            samples.append(origin)

    for entity in entities:
        if not isinstance(entity, dict) or entity.get("space") != "model":
            continue
        name = _block_ref_name(entity)
        if name:
            record(name, "modelspace")

    for bd in block_definitions:
        if not isinstance(bd, dict):
            continue
        parent_name = bd.get("name") or "?"
        for def_entity in bd.get("def_entities") or []:
            name = _block_ref_name(def_entity)
            if name:
                record(name, parent_name)

    undefined: Dict[str, Dict[str, Any]] = {}
    for name, count in referenced_names.items():
        if name in defined_set:
            continue
        undefined[name] = {
            "references": count,
            "referenced_from": referenced_from.get(name, []),
            "anonymous": name.startswith("*"),
        }

    anonymous_defined_count = sum(1 for name in defined_names if name.startswith("*"))
    undefined_total_refs = sum(info["references"] for info in undefined.values())

    return {
        "schema": SCHEMA,
        "referenced_names": referenced_names,
        "defined_names": defined_names,
        "undefined": undefined,
        "anonymous_defined_count": anonymous_defined_count,
        "summary": {
            "undefined_total_refs": undefined_total_refs,
            "undefined_unique": len(undefined),
            "all_undefined_anonymous": all(info["anonymous"] for info in undefined.values()),
        },
    }


def render_markdown(result: Dict[str, Any]) -> str:
    """Render the undefined table (sorted by references desc) + findings section."""
    summary = result["summary"]
    lines = [
        "# anon_block_probe report",
        "",
        "- schema: %s" % result["schema"],
        "- undefined_unique: %d" % summary["undefined_unique"],
        "- undefined_total_refs: %d" % summary["undefined_total_refs"],
        "- all_undefined_anonymous: %s" % summary["all_undefined_anonymous"],
        "- anonymous_defined_count: %d" % result["anonymous_defined_count"],
        "",
        "## Undefined block references",
        "",
        "| name | references | anonymous | referenced_from |",
        "|---|---|---|---|",
    ]

    ordered = sorted(
        result["undefined"].items(), key=lambda kv: kv[1]["references"], reverse=True
    )
    for name, info in ordered:
        origins = ", ".join(info["referenced_from"])
        lines.append("| %s | %d | %s | %s |" % (name, info["references"], info["anonymous"], origins))

    lines.extend(
        [
            "",
            "## Findings -- root-cause hypotheses",
            "",
        ]
    )
    lines.extend("- %s" % hypothesis for hypothesis in _FINDINGS_HYPOTHESES)
    lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe a dwg_graph_ir.v1 IR for block references naming "
                     "undefined (often anonymous) block definitions."
    )
    parser.add_argument("--ir", required=True, help="Path to a dwg_graph_ir.v1 JSON document")
    parser.add_argument("--out-json", help="Optional path to write the result JSON")
    parser.add_argument("--out-md", help="Optional path to write the result Markdown")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.ir):
        print("error: IR file not found: %s" % args.ir, file=sys.stderr)
        return 3

    ir = load_ir(args.ir)
    result = analyze(ir)

    if args.out_json:
        with open(args.out_json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)

    if args.out_md:
        with open(args.out_md, "w", encoding="utf-8") as fh:
            fh.write(render_markdown(result))

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
