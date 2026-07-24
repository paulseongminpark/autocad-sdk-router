# -*- coding: utf-8 -*-
"""S5-B — structural metamorphic transforms for DXF drawings.

Public API
----------
explode(dxf_in, dxf_out) -> handle_map
    Flatten every top-level modelspace INSERT into world-space entities.
    One INSERT nesting level per pass; loop to fixpoint (max 16 iterations).
    handle_map: old deepest-entity handle -> new exploded entity handle
    (keeps truth ledgers comparable across the structural transform).

rename_layers(dxf_in, dxf_out, scheme, seed) -> layer_map
    scheme 'shuffle'   : permute existing layer names (geometry untouched)
    scheme 'anonymize' : rename to L001, L002, ... (geometry untouched)
    layer_map: old_name -> new_name (bijective over the renamed set)

Originals are READ-ONLY: always write to dxf_out (must differ from dxf_in).

SEGMENT-IR v1 (shared contract — exact keys, version field required)::

    {"ir":"seg.v1","drawing_id":"str","units":"mm|unknown","scale_mm_per_unit":null,
     "segments":[{"sid":"s0001","handle":"8B52 or null","pts":[[x1,y1],[x2,y2]],
                  "layer":"str","kind":"line|poly-edge|arc-chord",
                  "label":"wall|opening|other|unknown",
                  "source":"native|synth|floorplancad|cubicasa"}]}

TRUTH-LEDGER v1 (shared contract — exact keys)::

    {"truth":"wall.v1","drawing_id":"str",
     "walls":[{"id":"w1","axis":[[x,y],[x,y]],"thickness":240.0,"layer":"WALL",
               "handles":["h1","h2"]}],
     "openings":[{"id":"o1","wall_id":"w1","span_along_axis":[t0,t1],
                  "type":"door|window"}],
     "wall_handles_flat":["h1","h2"]}

This module does not emit SEG-IR / truth ledgers — it only mutates DXF
structure (INSERT explode / layer names) so sibling cards can remap handles.
"""

from __future__ import annotations

import argparse
import random
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import ezdxf

_MAX_EXPLODE_ITERS = 16
_SCHEMES = ("shuffle", "anonymize")


def _as_path(p: Any) -> Path:
    return Path(p).resolve()


def _refuse_inplace(dxf_in: Path, dxf_out: Path) -> None:
    if dxf_in == dxf_out:
        raise ValueError(
            "in-place transform refused: dxf_out must differ from dxf_in "
            "(write to an explicit staging path)"
        )


def _source_handle(entity: Any) -> Optional[str]:
    """Deepest source-entity handle for an exploded copy, if available."""
    src = getattr(entity, "source_of_copy", None)
    if src is None:
        return None
    try:
        if not getattr(src, "is_alive", True):
            return None
        if not src.dxf.hasattr("handle"):
            return None
        h = src.dxf.handle
        return str(h) if h is not None else None
    except Exception:
        return None


def _explode_one_level(
    msp: Any,
    handle_map: Dict[str, str],
) -> int:
    """Explode every current top-level INSERT once. Return count exploded."""
    inserts = [e for e in msp if e.dxftype() == "INSERT"]
    if not inserts:
        return 0
    n = 0
    for ins in list(inserts):
        if not getattr(ins, "is_alive", True):
            continue
        try:
            new_ents = list(ins.explode())
        except Exception:
            # XREF / unloadable / non-explodable INSERT — leave in place
            continue
        n += 1
        for e in new_ents:
            # Nested INSERTs are not deepest leaves; map them on a later pass
            # when *their* contents explode into primitives.
            if e.dxftype() == "INSERT":
                continue
            old_h = _source_handle(e)
            if old_h is None:
                continue
            try:
                new_h = str(e.dxf.handle)
            except Exception:
                continue
            handle_map[old_h] = new_h
    return n


def explode(dxf_in: Any, dxf_out: Any) -> Dict[str, str]:
    """Flatten modelspace INSERTs to world-space entities; write dxf_out.

    Loops to fixpoint (no remaining modelspace INSERTs) or ``_MAX_EXPLODE_ITERS``.

    Returns
    -------
    handle_map : dict[str, str]
        old deepest block-entity handle -> new modelspace entity handle
    """
    src = _as_path(dxf_in)
    dst = _as_path(dxf_out)
    _refuse_inplace(src, dst)
    if not src.is_file():
        raise FileNotFoundError(f"dxf_in not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.readfile(str(src))
    msp = doc.modelspace()
    handle_map: Dict[str, str] = {}

    for _ in range(_MAX_EXPLODE_ITERS):
        exploded = _explode_one_level(msp, handle_map)
        if exploded == 0:
            break

    doc.saveas(str(dst))
    return handle_map


def _collect_layer_names(doc: "ezdxf.document.Drawing") -> List[str]:
    """Sorted unique layer names from the layer table + entity references."""
    names: Set[str] = set()
    for layer in doc.layers:
        names.add(str(layer.dxf.name))
    for block in doc.blocks:
        for e in block:
            try:
                if e.dxf.hasattr("layer"):
                    names.add(str(e.dxf.layer))
            except Exception:
                continue
    # Stable order for deterministic anonymize / shuffle base permutation
    return sorted(names)


def _build_layer_map(names: Sequence[str], scheme: str, seed: int) -> Dict[str, str]:
    scheme = str(scheme).lower().strip()
    if scheme not in _SCHEMES:
        raise ValueError(f"unknown scheme {scheme!r}; expected one of {_SCHEMES}")
    names = list(names)
    if scheme == "anonymize":
        return {old: f"L{i:03d}" for i, old in enumerate(names, start=1)}
    # shuffle: permute the name set among itself
    rng = random.Random(int(seed))
    shuffled = list(names)
    rng.shuffle(shuffled)
    return {old: new for old, new in zip(names, shuffled)}


def _rename_layer_table(doc: "ezdxf.document.Drawing", layer_map: Dict[str, str]) -> None:
    """Apply layer_map to the layer table via two-phase temps (collision-safe)."""
    # Only rename entries that exist and actually change.
    changes = [
        (old, new)
        for old, new in layer_map.items()
        if old != new and doc.layers.has_entry(old)
    ]
    if not changes:
        return

    temps: List[Tuple[str, str, str]] = []  # (old, tmp, new)
    for i, (old, new) in enumerate(changes):
        tmp = f"__S5B_TMP_{i}__"
        # Guard against pathological collision with a real layer name
        while doc.layers.has_entry(tmp) or tmp in layer_map.values():
            tmp = f"__S5B_TMP_{i}_{random.randrange(1 << 20)}__"
        doc.layers.duplicate_entry(old, tmp)
        doc.layers.remove(old)
        temps.append((old, tmp, new))

    for _old, tmp, new in temps:
        if doc.layers.has_entry(new):
            # Target already exists (identity-ish shuffle residue or reserved):
            # drop the temp; entities already point at `new`.
            doc.layers.remove(tmp)
        else:
            doc.layers.duplicate_entry(tmp, new)
            doc.layers.remove(tmp)

    # AutoCAD requires layer "0" to exist
    if not doc.layers.has_entry("0"):
        doc.layers.add("0")


def _remap_entity_layers(doc: "ezdxf.document.Drawing", layer_map: Dict[str, str]) -> None:
    for block in doc.blocks:
        for e in block:
            try:
                if not e.dxf.hasattr("layer"):
                    continue
                old = str(e.dxf.layer)
                new = layer_map.get(old)
                if new is not None and new != old:
                    e.dxf.layer = new
            except Exception:
                continue


def rename_layers(
    dxf_in: Any,
    dxf_out: Any,
    scheme: str,
    seed: int = 0,
) -> Dict[str, str]:
    """Rename layers per scheme; write dxf_out; return bijective layer_map.

    Geometry (coordinates, entity types, handles) is left untouched.
    """
    src = _as_path(dxf_in)
    dst = _as_path(dxf_out)
    _refuse_inplace(src, dst)
    if not src.is_file():
        raise FileNotFoundError(f"dxf_in not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.readfile(str(src))
    names = _collect_layer_names(doc)
    layer_map = _build_layer_map(names, scheme, seed)

    # Entity refs first so they never briefly point at deleted table entries,
    # then rebuild the table (two-phase for shuffle collisions).
    _remap_entity_layers(doc, layer_map)
    _rename_layer_table(doc, layer_map)

    doc.saveas(str(dst))
    return layer_map


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _world_line_count(doc: "ezdxf.document.Drawing") -> int:
    return sum(1 for e in doc.modelspace() if e.dxftype() == "LINE")


def _world_insert_count(doc: "ezdxf.document.Drawing") -> int:
    return sum(1 for e in doc.modelspace() if e.dxftype() == "INSERT")


def _assert_bijective(m: Dict[str, str], label: str) -> None:
    keys = list(m.keys())
    vals = list(m.values())
    if len(keys) != len(set(keys)):
        raise AssertionError(f"{label}: non-unique keys")
    if len(vals) != len(set(vals)):
        raise AssertionError(f"{label}: non-unique values (not injective)")
    if len(keys) != len(vals):
        raise AssertionError(f"{label}: key/value length mismatch")


def _build_fixture(path: Path) -> Dict[str, str]:
    """Temp DXF: block INSERT of 2 LINEs + 1 direct LINE. Return key handles."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # mm
    if not doc.layers.has_entry("WALL"):
        doc.layers.add("WALL")
    if not doc.layers.has_entry("DOOR"):
        doc.layers.add("DOOR")

    blk = doc.blocks.new("S5B_BLK")
    bl1 = blk.add_line((0.0, 0.0), (100.0, 0.0), dxfattribs={"layer": "WALL"})
    bl2 = blk.add_line((0.0, 0.0), (0.0, 50.0), dxfattribs={"layer": "DOOR"})

    msp = doc.modelspace()
    ins = msp.add_blockref("S5B_BLK", (1000.0, 2000.0), dxfattribs={"layer": "0"})
    direct = msp.add_line((0.0, 0.0), (5.0, 5.0), dxfattribs={"layer": "WALL"})

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(path))

    # Re-read to get stable handles as written
    doc2 = ezdxf.readfile(str(path))
    blk2 = doc2.blocks.get("S5B_BLK")
    block_lines = [e for e in blk2 if e.dxftype() == "LINE"]
    block_lines.sort(key=lambda e: str(e.dxf.handle))
    msp2 = doc2.modelspace()
    inserts = [e for e in msp2 if e.dxftype() == "INSERT"]
    directs = [e for e in msp2 if e.dxftype() == "LINE"]
    assert len(block_lines) == 2
    assert len(inserts) == 1
    assert len(directs) == 1
    return {
        "block_line_a": str(block_lines[0].dxf.handle),
        "block_line_b": str(block_lines[1].dxf.handle),
        "insert": str(inserts[0].dxf.handle),
        "direct": str(directs[0].dxf.handle),
    }


def run_selftest() -> int:
    print("S5-B transforms_struct selftest starting")
    with tempfile.TemporaryDirectory(prefix="s5b_struct_") as td:
        td_path = Path(td)
        src = td_path / "fixture.dxf"
        handles = _build_fixture(src)
        print(f"fixture: {src}")
        print(f"  handles={handles}")

        # --- explode ---
        exploded = td_path / "exploded.dxf"
        hmap = explode(src, exploded)
        doc_x = ezdxf.readfile(str(exploded))
        n_lines = _world_line_count(doc_x)
        n_ins = _world_insert_count(doc_x)
        print(f"explode: world_lines={n_lines} inserts={n_ins} handle_map={hmap}")
        assert n_lines == 3, f"expected 3 world LINEs, got {n_lines}"
        assert n_ins == 0, f"expected 0 INSERTs after explode, got {n_ins}"
        for key in ("block_line_a", "block_line_b"):
            old = handles[key]
            assert old in hmap, f"handle_map missing deepest handle {old} ({key})"
            assert hmap[old] != old, f"handle_map identity for {old}"
        # Direct modelspace line was not exploded from a block — not required
        # in handle_map; both deepest block leaves must be present.
        assert len(hmap) >= 2, f"handle_map incomplete: {hmap}"
        world_handles = {str(e.dxf.handle) for e in doc_x.modelspace()}
        for new_h in hmap.values():
            assert new_h in world_handles, f"mapped handle {new_h} not in modelspace"
        print("PASS explode: 3 world entities + complete handle_map")

        # --- rename (anonymize) ---
        renamed = td_path / "renamed.dxf"
        lmap = rename_layers(exploded, renamed, "anonymize", seed=7)
        print(f"rename anonymize layer_map={lmap}")
        _assert_bijective(lmap, "anonymize layer_map")
        doc_r = ezdxf.readfile(str(renamed))
        assert _world_line_count(doc_r) == 3
        assert _world_insert_count(doc_r) == 0
        # geometry untouched: same endpoint multiset (handles may differ? no —
        # rename must preserve handles)
        before_eps = sorted(
            (
                (float(e.dxf.start.x), float(e.dxf.start.y),
                 float(e.dxf.end.x), float(e.dxf.end.y), str(e.dxf.handle))
                for e in doc_x.modelspace() if e.dxftype() == "LINE"
            )
        )
        after_eps = sorted(
            (
                (float(e.dxf.start.x), float(e.dxf.start.y),
                 float(e.dxf.end.x), float(e.dxf.end.y), str(e.dxf.handle))
                for e in doc_r.modelspace() if e.dxftype() == "LINE"
            )
        )
        assert before_eps == after_eps, "rename must not alter geometry/handles"
        print("PASS rename anonymize: bijective layer_map, geometry intact")

        # --- rename (shuffle) on original fixture ---
        shuffled = td_path / "shuffled.dxf"
        lmap2 = rename_layers(src, shuffled, "shuffle", seed=99)
        print(f"rename shuffle layer_map={lmap2}")
        _assert_bijective(lmap2, "shuffle layer_map")
        # shuffle permutes within the same name set
        assert set(lmap2.keys()) == set(lmap2.values()), (
            f"shuffle must permute names in-place: {lmap2}"
        )
        print("PASS rename shuffle: bijective permutation")

    print("S5-B transforms_struct selftest ALL PASS")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="S5-B structural DXF transforms")
    p.add_argument("--selftest", action="store_true", help="run built-in selftest")
    p.add_argument("--dxf-in", type=str, default=None)
    p.add_argument("--dxf-out", type=str, default=None)
    p.add_argument("--op", type=str, default=None, choices=["explode", "rename"])
    p.add_argument("--scheme", type=str, default="anonymize", choices=list(_SCHEMES))
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(list(argv) if argv is not None else None)

    if args.selftest:
        return run_selftest()

    if not args.dxf_in or not args.dxf_out or not args.op:
        p.error("--dxf-in, --dxf-out, and --op are required unless --selftest")

    if args.op == "explode":
        hmap = explode(args.dxf_in, args.dxf_out)
        print(hmap)
        return 0

    lmap = rename_layers(args.dxf_in, args.dxf_out, args.scheme, args.seed)
    print(lmap)
    return 0


if __name__ == "__main__":
    sys.exit(main())
