"""E2 synth / messiness module (CARD S2-D).

Adds progressive "mess" to a SAVED synthetic wall DXF while keeping the
wall AXIS geometry (the truth) invariant -- only the *representation* of
walls, and the surrounding clutter, is disturbed.

Contract (inline, do not import the grammar module):

    messify(dxf_in, dxf_out, seed, level, ledger) -> (new_ledger, handle_map)

TRUTH-LEDGER v1 (shared, exact keys):
    {"truth":"wall.v1","drawing_id":"str",
     "walls":[{"id":"w1","axis":[[x,y],[x,y]],"thickness":240.0,
               "layer":"WALL","handles":["h1","h2"]}],
     "openings":[{"id":"o1","wall_id":"w1","span_along_axis":[t0,t1],
                  "type":"door|window"}],
     "wall_handles_flat":["h1","h2"]}

Messiness levels (cumulative):
    level 1 : convert a fraction of wall LINEs to LWPOLYLINE (same geometry).
              The ledger FOLLOWS the representation change -- handle_map maps
              old->new handles, and new_ledger's per-wall `handles` and the
              flat `wall_handles_flat` are rewritten to the new handles.
    level 2 : + wrap a random non-wall room cluster into a block definition
              and INSERT it, nested one deep (outer block -> INSERT -> inner
              block). Walls are never wrapped.
    level 3 : + jitter non-wall clutter, duplicate short line fragments, and
              add a solid hatch patch on layer 'INSUL'.

Invariant: wall AXIS geometry is never altered. Levels 2/3 only add or move
NON-wall entities; walls are identified by their (post-level-1) handles and
are excluded from every mutating operation.

ezdxf is ALLOWED for this card (stdlib otherwise).
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
import tempfile

import ezdxf


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #

def _ensure_layer(doc, name, color=7):
    """Create a layer if the table does not already have it."""
    if name not in doc.layers:
        doc.layers.new(name, dxfattribs={"color": color})


def _entity_by_handle(doc, handle):
    """Return the entity for a DXF handle, or None if absent."""
    return doc.entitydb.get(handle)


def _line_points(entity):
    """2D endpoints of a LINE."""
    s, e = entity.dxf.start, entity.dxf.end
    return [(s.x, s.y), (e.x, e.y)]


def _entity_points_xy(entity):
    """2D vertex list for a LINE or LWPOLYLINE, else None."""
    t = entity.dxftype()
    if t == "LINE":
        return _line_points(entity)
    if t == "LWPOLYLINE":
        return [(p[0], p[1]) for p in entity.get_points(format="xy")]
    return None


def _copy_entity_into(block, entity):
    """Copy a supported clutter entity into `block`. Returns True on success.

    Only a handful of primitive types are handled -- anything else is left in
    place (caller must not delete it)."""
    t = entity.dxftype()
    layer = entity.dxf.layer
    if t == "LINE":
        s, e = entity.dxf.start, entity.dxf.end
        block.add_line((s.x, s.y), (e.x, e.y), dxfattribs={"layer": layer})
        return True
    if t == "LWPOLYLINE":
        pts = [(p[0], p[1]) for p in entity.get_points(format="xy")]
        block.add_lwpolyline(pts, format="xy",
                             dxfattribs={"layer": layer,
                                         "closed": bool(entity.closed)})
        return True
    if t == "CIRCLE":
        c = entity.dxf.center
        block.add_circle((c.x, c.y), entity.dxf.radius,
                         dxfattribs={"layer": layer})
        return True
    if t == "ARC":
        c = entity.dxf.center
        block.add_arc((c.x, c.y), entity.dxf.radius,
                      entity.dxf.start_angle, entity.dxf.end_angle,
                      dxfattribs={"layer": layer})
        return True
    return False


# --------------------------------------------------------------------------- #
# ledger remap
# --------------------------------------------------------------------------- #

def _remap_ledger_handles(ledger, handle_map, wall_handle_set):
    """Rewrite every ledger handle through handle_map (identity if absent) and
    refresh the mutable wall-handle set to the post-remap handles."""
    for wall in ledger.get("walls", []):
        wall["handles"] = [handle_map.get(h, h) for h in wall.get("handles", [])]
    ledger["wall_handles_flat"] = [
        handle_map.get(h, h) for h in ledger.get("wall_handles_flat", [])
    ]
    wall_handle_set.clear()
    wall_handle_set.update(ledger["wall_handles_flat"])


# --------------------------------------------------------------------------- #
# level 1 : LINE -> LWPOLYLINE for a fraction of wall lines
# --------------------------------------------------------------------------- #

def _level1_convert(doc, msp, ledger, wall_handle_set, handle_map, rng,
                    fraction=0.5):
    """Convert a deterministic fraction (>=1 if any exist) of wall LINE
    entities into geometrically-identical LWPOLYLINEs, updating the ledger."""
    convertible = []
    for h in ledger.get("wall_handles_flat", []):
        e = _entity_by_handle(doc, h)
        if e is not None and e.dxftype() == "LINE":
            convertible.append(h)

    rng.shuffle(convertible)
    if not convertible:
        return
    k = max(1, round(fraction * len(convertible)))
    chosen = convertible[:k]

    for h in chosen:
        line = _entity_by_handle(doc, h)
        s, e = line.dxf.start, line.dxf.end
        layer = line.dxf.layer
        lw = msp.add_lwpolyline(
            [(s.x, s.y), (e.x, e.y)],
            format="xy",
            dxfattribs={"layer": layer, "const_width": 0.0, "closed": False},
        )
        new_h = lw.dxf.handle
        msp.delete_entity(line)
        handle_map[h] = new_h

    _remap_ledger_handles(ledger, handle_map, wall_handle_set)


# --------------------------------------------------------------------------- #
# level 2 : wrap a room cluster into a nested block + INSERT
# --------------------------------------------------------------------------- #

def _unique_block_name(doc, base):
    name = base
    while name in doc.blocks:
        name += "_x"
    return name


def _level2_blocks(doc, msp, wall_handle_set, rng, seed):
    """Create an inner block of room-cluster clutter, wrap it inside an outer
    block (nested one deep), and INSERT the outer block into modelspace.

    Existing non-wall clutter (if any) is moved into the inner block to
    genuinely "wrap a room cluster"; walls are never touched."""
    _ensure_layer(doc, "FURN", color=3)

    inner_name = _unique_block_name(doc, "NOISE_INNER_%d" % seed)
    outer_name = _unique_block_name(doc, "NOISE_OUTER_%d" % seed)

    inner = doc.blocks.new(name=inner_name)

    # generated room-cluster furniture -> guarantees a non-empty cluster
    bx, by = rng.uniform(0.0, 5000.0), rng.uniform(0.0, 5000.0)
    inner.add_lwpolyline(
        [(bx, by), (bx + 600, by), (bx + 600, by + 400), (bx, by + 400),
         (bx, by)],
        format="xy",
        dxfattribs={"layer": "FURN", "closed": True},
    )
    inner.add_line((bx, by), (bx + 600, by + 400), dxfattribs={"layer": "FURN"})

    # wrap a random subset of existing non-wall clutter (if present)
    non_wall = [e for e in msp if e.dxf.handle not in wall_handle_set]
    rng.shuffle(non_wall)
    take = non_wall[: len(non_wall) // 2]
    for e in take:
        if _copy_entity_into(inner, e):
            msp.delete_entity(e)

    # outer block nests the inner block one deep
    outer = doc.blocks.new(name=outer_name)
    outer.add_blockref(inner_name, (0.0, 0.0))
    outer.add_circle((bx + 300, by + 200), 50.0, dxfattribs={"layer": "FURN"})

    # INSERT the outer block into modelspace
    msp.add_blockref(outer_name, (rng.uniform(0.0, 1000.0),
                                  rng.uniform(0.0, 1000.0)))
    return outer_name, inner_name


# --------------------------------------------------------------------------- #
# level 3 : jitter clutter, duplicate short fragments, hatch patch
# --------------------------------------------------------------------------- #

def _jitter_entity(entity, dx, dy):
    """Translate a supported non-wall entity in-place; skip unsupported."""
    try:
        entity.translate(dx, dy, 0.0)
        return True
    except (AttributeError, TypeError, NotImplementedError):
        return False


def _level3_clutter(doc, msp, wall_handle_set, rng):
    """Jitter non-wall modelspace clutter, add short duplicate fragments
    (derived from existing segments -- walls read-only), and add a solid
    hatch patch on layer 'INSUL'. Walls are never modified."""
    _ensure_layer(doc, "DEBRIS", color=1)
    _ensure_layer(doc, "INSUL", color=2)

    # 1) jitter non-wall clutter in modelspace (walls skipped)
    for e in list(msp):
        if e.dxf.handle in wall_handle_set:
            continue
        _jitter_entity(e, rng.uniform(-5.0, 5.0), rng.uniform(-5.0, 5.0))

    # 2) duplicate short fragments -- source segments read-only (incl. walls)
    sources = []
    for e in list(msp):
        pts = _entity_points_xy(e)
        if pts and len(pts) >= 2:
            sources.append((pts[0], pts[1]))
    rng.shuffle(sources)
    for (s, en) in sources[:3]:
        ox, oy = rng.uniform(-3.0, 3.0), rng.uniform(-3.0, 3.0)
        f = 0.15  # short fragment = leading 15% of the segment
        msp.add_line(
            (s[0] + ox, s[1] + oy),
            (s[0] + (en[0] - s[0]) * f + ox, s[1] + (en[1] - s[1]) * f + oy),
            dxfattribs={"layer": "DEBRIS"},
        )

    # 3) solid hatch patch on layer INSUL
    hx, hy = rng.uniform(0.0, 4000.0), rng.uniform(0.0, 4000.0)
    hatch = msp.add_hatch(dxfattribs={"layer": "INSUL"})
    hatch.set_solid_fill(color=2)
    hatch.paths.add_polyline_path(
        [(hx, hy), (hx + 300, hy), (hx + 300, hy + 300), (hx, hy + 300)],
        is_closed=True,
    )


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #

def messify(dxf_in, dxf_out, seed, level, ledger):
    """Add level-graded mess to a saved synth DXF.

    Parameters
    ----------
    dxf_in  : path to a saved synth DXF (never mutated in place).
    dxf_out : path to write the messy DXF.
    seed    : int -- deterministic RNG seed.
    level   : 1, 2 or 3 (cumulative).
    ledger  : TRUTH-LEDGER v1 dict for `dxf_in`.

    Returns
    -------
    (new_ledger, handle_map)
        new_ledger : deep copy of `ledger` with handles remapped to the new
                     representation (axes untouched).
        handle_map : {old_handle: new_handle} for every converted wall entity.
    """
    import random

    rng = random.Random(seed)
    doc = ezdxf.readfile(dxf_in)
    msp = doc.modelspace()

    new_ledger = copy.deepcopy(ledger)
    handle_map = {}
    wall_handle_set = set(new_ledger.get("wall_handles_flat", []))

    if level >= 1:
        _level1_convert(doc, msp, new_ledger, wall_handle_set, handle_map, rng)
    if level >= 2:
        _level2_blocks(doc, msp, wall_handle_set, rng, seed)
    if level >= 3:
        _level3_clutter(doc, msp, wall_handle_set, rng)

    doc.saveas(dxf_out)
    return new_ledger, handle_map


# --------------------------------------------------------------------------- #
# selftest -- self-contained, builds its own fixture in the OS temp dir
# --------------------------------------------------------------------------- #

def _build_min_fixture(path):
    """Build a minimal R2018 ASCII DXF with 2 wall LINEs (inline, no grammar
    import) and return the matching TRUTH-LEDGER v1 dict."""
    doc = ezdxf.new("R2018")
    _ensure_layer(doc, "WALL", color=7)
    msp = doc.modelspace()

    axis1 = [[0.0, 0.0], [4000.0, 0.0]]
    axis2 = [[4000.0, 0.0], [4000.0, 3000.0]]

    l1 = msp.add_line(tuple(axis1[0]), tuple(axis1[1]),
                      dxfattribs={"layer": "WALL"})
    l2 = msp.add_line(tuple(axis2[0]), tuple(axis2[1]),
                      dxfattribs={"layer": "WALL"})
    h1, h2 = l1.dxf.handle, l2.dxf.handle

    doc.saveas(path)

    ledger = {
        "truth": "wall.v1",
        "drawing_id": "selftest",
        "walls": [
            {"id": "w1", "axis": axis1, "thickness": 240.0, "layer": "WALL",
             "handles": [h1]},
            {"id": "w2", "axis": axis2, "thickness": 240.0, "layer": "WALL",
             "handles": [h2]},
        ],
        "openings": [
            {"id": "o1", "wall_id": "w1", "span_along_axis": [0.4, 0.55],
             "type": "door"},
        ],
        "wall_handles_flat": [h1, h2],
    }
    return ledger


def _approx_pts(a, b, tol=1e-6):
    if len(a) != len(b):
        return False
    return all(math.isclose(ax, bx, abs_tol=tol) and
               math.isclose(ay, by, abs_tol=tol)
               for (ax, ay), (bx, by) in zip(a, b))


def _check_level(base_dxf, base_ledger, level, tmpdir):
    seed = 4242
    out = os.path.join(tmpdir, "messy_L%d.dxf" % level)
    new_ledger, handle_map = messify(base_dxf, out, seed, level, base_ledger)

    orig_flat = base_ledger["wall_handles_flat"]
    new_flat = new_ledger["wall_handles_flat"]

    assert len(orig_flat) == len(new_flat), "flat handle count changed"

    # every position that changed MUST be explained by handle_map
    changed = 0
    for o, n in zip(orig_flat, new_flat):
        if o != n:
            changed += 1
            assert handle_map.get(o) == n, \
                "changed handle %s->%s not covered by handle_map" % (o, n)
    # every handle_map entry must be a genuine old->new change reflected in ledger
    for o, n in handle_map.items():
        assert o in orig_flat, "handle_map key %s not an original handle" % o
        assert n in new_flat, "handle_map value %s not in new ledger" % n
        assert o != n, "handle_map identity entry %s" % o
    assert changed == len(handle_map), \
        "changed positions (%d) != handle_map size (%d)" % (changed, len(handle_map))
    assert len(handle_map) >= 1, "level %d converted nothing" % level

    # axes unchanged in ledger
    orig_axes = {w["id"]: w["axis"] for w in base_ledger["walls"]}
    for w in new_ledger["walls"]:
        assert w["axis"] == orig_axes[w["id"]], \
            "axis mutated for %s" % w["id"]

    # DXF geometry for each wall must still match its axis (same geometry),
    # and old handles must be gone / converted entities present as LWPOLYLINE
    doc = ezdxf.readfile(out)
    for w in new_ledger["walls"]:
        axis = w["axis"]
        for h in w["handles"]:
            e = _entity_by_handle(doc, h)
            assert e is not None, "wall handle %s missing in output" % h
            assert e.dxftype() in ("LINE", "LWPOLYLINE"), \
                "wall %s became %s" % (w["id"], e.dxftype())
            pts = _entity_points_xy(e)
            assert _approx_pts(pts, [tuple(p) for p in axis]), \
                "wall %s geometry drifted: %s vs %s" % (w["id"], pts, axis)
    # converted old handles must no longer resolve to a wall LINE
    for old_h in handle_map:
        assert _entity_by_handle(doc, old_h) is None, \
            "old handle %s still present after conversion" % old_h

    # at least one converted entity is now an LWPOLYLINE
    converted_types = [_entity_by_handle(doc, h).dxftype()
                       for h in handle_map.values()]
    assert "LWPOLYLINE" in converted_types, "no LWPOLYLINE produced"

    # structural checks per level
    block_names = [b.name for b in doc.blocks]
    have_noise_block = any(str(n).startswith("NOISE_OUTER_") for n in block_names)
    inserts = [e for e in doc.modelspace() if e.dxftype() == "INSERT"]
    hatches = [e for e in doc.modelspace()
               if e.dxftype() == "HATCH" and e.dxf.layer == "INSUL"]

    if level >= 2:
        assert have_noise_block, "level>=2 produced no NOISE_OUTER block"
        assert inserts, "level>=2 produced no INSERT"
        # nested one deep: outer block must contain an INSERT of inner block
        outer = [n for n in block_names if str(n).startswith("NOISE_OUTER_")][0]
        outer_layout = doc.blocks.get(outer)
        nested = [e for e in outer_layout if e.dxftype() == "INSERT"]
        assert nested, "outer NOISE block has no nested INSERT"
    if level >= 3:
        assert hatches, "level>=3 produced no INSUL hatch"

    print("  L%d OK: converted=%d handle_map=%s inserts=%d insul_hatch=%d walls_ok=%d"
          % (level, len(handle_map), handle_map, len(inserts), len(hatches),
             len(new_ledger["walls"])))
    return True


def _selftest():
    tmpdir = tempfile.mkdtemp(prefix="s2d_noise_")
    print("selftest tmpdir: %s" % tmpdir)
    base_dxf = os.path.join(tmpdir, "base.dxf")
    base_ledger = _build_min_fixture(base_dxf)
    print("built minimal fixture: 2 wall LINEs, handles=%s"
          % base_ledger["wall_handles_flat"])

    ok = True
    for level in (1, 2, 3):
        try:
            _check_level(base_dxf, base_ledger, level, tmpdir)
        except AssertionError as exc:
            ok = False
            print("  L%d FAIL: %s" % (level, exc))

    # confirm the base fixture was never mutated in place (truth of source)
    src = ezdxf.readfile(base_dxf)
    src_lines = [e for e in src.modelspace() if e.dxftype() == "LINE"]
    assert len(src_lines) == 2, "source fixture mutated in place!"
    print("source fixture intact: %d LINEs" % len(src_lines))

    print("SELFTEST %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _main(argv=None):
    ap = argparse.ArgumentParser(description="E2 synth messiness module (S2-D)")
    ap.add_argument("--selftest", action="store_true",
                    help="build a fixture in OS temp and run messify L1..3")
    ap.add_argument("--in", dest="dxf_in", help="input synth DXF")
    ap.add_argument("--out", dest="dxf_out", help="output messy DXF")
    ap.add_argument("--ledger", help="path to input TRUTH-LEDGER v1 JSON")
    ap.add_argument("--ledger-out", help="path to write remapped ledger JSON")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--level", type=int, default=1, choices=(1, 2, 3))
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    if not (args.dxf_in and args.dxf_out and args.ledger):
        ap.error("non-selftest run requires --in, --out and --ledger")

    with open(args.ledger, "r", encoding="utf-8") as fh:
        ledger = json.load(fh)
    new_ledger, handle_map = messify(args.dxf_in, args.dxf_out, args.seed,
                                     args.level, ledger)
    if args.ledger_out:
        with open(args.ledger_out, "w", encoding="utf-8") as fh:
            json.dump(new_ledger, fh, indent=2)
    print(json.dumps({"handle_map": handle_map,
                      "walls": len(new_ledger["walls"])}))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
