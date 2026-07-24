#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""resolve_entity_color.py -- ByLayer color post-processor for dwg_graph_ir.v1.

Workaround for the extraction gap tracked in issue #24: the native model-space
graph extractor (``collectModelSpaceGraph``) emits per-entity geometry + layer +
handle but NOT per-entity color (``color_index`` / ``true_color``). Only
layer-level color survives (``symbol_tables.layers[].color_index``). Consumers
that need a color per entity therefore see nothing on the entity itself.

Until the native emitter is fixed to serialize ``AcDbEntity::colorIndex()``,
this tool recovers the *ByLayer* color: it joins each entity's ``layer`` to its
layer record's ``color_index`` and attaches a ``resolved_color`` block. This is
correct for the common ByLayer case (the vast majority of real drawings) and is
explicitly marked ``source: "bylayer"`` so callers know explicit per-entity
overrides / ByBlock colors are NOT reconstructable from the IR (that needs the
native fix in #24).

Applied to top-level ``entities[]`` and to nested
``block_definitions[].def_entities``.

RGB is emitted best-effort: if ``ezdxf`` is importable its ACI palette is used;
otherwise only the authoritative integer ``color_index`` is written (``rgb`` is
null). No hard dependency is added.

Usage:
    python tools/resolve_entity_color.py <dwg_graph_ir.json> [-o <out.json>]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

DEFAULT_ACI = 7  # white/black -- AutoCAD's default when a layer color is unknown

try:  # optional: exact AutoCAD ACI -> RGB palette
    import ezdxf.colors as _ezcolors  # type: ignore
except Exception:  # pragma: no cover - ezdxf is optional
    _ezcolors = None


def _layer_color_map(ir: Dict[str, Any]) -> Dict[str, int]:
    """Return {layer_name: color_index} from symbol_tables.layers."""
    st = ir.get("symbol_tables") or {}
    layers = st.get("layers")
    if isinstance(layers, dict):
        layers = layers.get("records") or list(layers.values())
    out: Dict[str, int] = {}
    for rec in layers or []:
        if isinstance(rec, dict) and rec.get("name") is not None:
            out[str(rec["name"])] = rec.get("color_index")
    return out


def _rgb_hex(aci: Optional[int]) -> Optional[str]:
    if aci is None or aci in (0, 256) or _ezcolors is None:
        return None
    try:
        c = _ezcolors.aci2rgb(int(aci))
        return "#%02X%02X%02X" % (c.r, c.g, c.b)
    except Exception:
        return None


def _annotate(entity: Dict[str, Any], layer_color: Dict[str, int]) -> None:
    layer = str(entity.get("layer", "") or "")
    aci = layer_color.get(layer)
    if aci is None:
        aci = DEFAULT_ACI
    entity["resolved_color"] = {
        "color_index": aci,
        "rgb": _rgb_hex(aci),
        "source": "bylayer",  # native did not export per-entity color; see issue #24
        "layer": layer,
    }


def resolve_bylayer_color(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Attach ``resolved_color`` (ByLayer) to every entity + block-def entity.

    Mutates and returns ``ir``. Pure aside from the in-place annotation --
    no I/O, independently unit-testable.
    """
    layer_color = _layer_color_map(ir)
    n_ent = n_def = 0
    for ent in ir.get("entities", []) or []:
        if isinstance(ent, dict):
            _annotate(ent, layer_color); n_ent += 1
    for bref in ir.get("block_references", []) or []:
        if isinstance(bref, dict):
            _annotate(bref, layer_color)
    for blk in ir.get("block_definitions", []) or []:
        if isinstance(blk, dict):
            for de in blk.get("def_entities", []) or []:
                if isinstance(de, dict):
                    _annotate(de, layer_color); n_def += 1
    diag = ir.setdefault("diagnostics", {})
    diag["color_recovery"] = {
        "method": "layer_color_index_bylayer_join",
        "issue": 24,
        "note": ("native graph extractor did not export per-entity color; "
                 "values are the entity layer's color_index (ByLayer). Explicit "
                 "per-entity overrides / ByBlock are unknown -- needs the native fix."),
        "rgb_palette": "ezdxf.colors.aci2rgb" if _ezcolors else None,
        "entities": n_ent,
        "def_entities": n_def,
    }
    return ir


def _load(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ir", help="path to dwg_graph_ir.json")
    ap.add_argument("-o", "--out", default=None,
                    help="output path (default: <ir>_color.json next to the input)")
    args = ap.parse_args(argv)

    ir = _load(args.ir)
    if ir.get("schema") != "ariadne.dwg_graph_ir.v1":
        sys.stderr.write("warning: unexpected schema %r (expected ariadne.dwg_graph_ir.v1)\n"
                         % ir.get("schema"))
    resolve_bylayer_color(ir)

    out = args.out or (os.path.splitext(args.ir)[0] + "_color.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(ir, fh, ensure_ascii=False)
    rec = ir["diagnostics"]["color_recovery"]
    print("wrote %s (entities=%d, def_entities=%d, rgb=%s)"
          % (out, rec["entities"], rec["def_entities"], bool(rec["rgb_palette"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
