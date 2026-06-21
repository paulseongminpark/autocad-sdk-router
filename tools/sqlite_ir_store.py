#!/usr/bin/env python
"""SQLite IR store for the CAD OS Layer (Lane B2).

Materializes an ``ariadne.dwg_graph_ir.v1`` IR dict (see
schemas/dwg_graph_ir.v1.schema.json) into a queryable SQLite database so
downstream consumers (diff, validation, lineage) can run set-based queries and
bbox/spatial lookups without re-walking the JSON.

stdlib only (Python 3.12). ``sqlite3`` is part of the standard library.

Public surface (INTERFACE CONTRACT):
    build_store(ir: dict, db_path: str) -> dict
        Build the store; returns {"db_path", "row_counts", "capability",
        "validation"}.  capability.rtree_available reflects whether this
        SQLite build supports the R*Tree virtual table.
    query(db_path: str, sql: str) -> {"columns": [...], "rows": [...]}
        Read-only query against an existing store.

Rich tables (M02): a native_full IR carries symbol tables, layouts, xrefs,
named-object dictionaries, xrecords, block definitions and block references
beyond bare entities+layers.  build_store materializes these additively into
dedicated tables (linetypes, text_styles, dim_styles, layouts, xrefs,
dictionaries, dictionary_entries, xrecords, block_references,
block_definitions, block_table_records).  A geometry_only / dxf IR simply
lacks those sections, so the tables are created but stay empty -- the schema
is identical regardless of coverage level, which keeps downstream SQL stable.

No-fake-success: build_store never claims a populated table it could not
build.  rtree absence is reported truthfully (rtree_available=false) and a
plain fallback table is used.  Row-count invariants are validated and surfaced
in the returned ``validation`` block rather than silently passing.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any


SCHEMA_ID = "ariadne.dwg_graph_ir.v1"


# --------------------------------------------------------------------------- #
# bbox helpers
# --------------------------------------------------------------------------- #
def _bbox_bounds(bbox: Any) -> tuple[float, float, float, float] | None:
    """Extract (min_x, min_y, max_x, max_y) from an IR bbox.

    IR bbox is [minX, minY, minZ, maxX, maxY, maxZ]; an empty list means "no
    bbox computed".  Returns None when no usable bbox is present.  Tolerates a
    4-number [minX, minY, maxX, maxY] form defensively.
    """
    if not isinstance(bbox, (list, tuple)):
        return None
    nums = [v for v in bbox if isinstance(v, (int, float))]
    if len(bbox) >= 6 and len(nums) >= 6:
        return (float(bbox[0]), float(bbox[1]), float(bbox[3]), float(bbox[4]))
    if len(bbox) == 4 and len(nums) == 4:
        return (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    return None


def _vertex_point(vertex: Any) -> tuple[float, float, float] | None:
    """Pull an (x, y, z) tuple from a polyline vertex object or bare point."""
    pt = None
    if isinstance(vertex, dict):
        pt = vertex.get("point")
    elif isinstance(vertex, (list, tuple)):
        pt = vertex
    if not isinstance(pt, (list, tuple)) or len(pt) < 2:
        return None
    x = float(pt[0]) if isinstance(pt[0], (int, float)) else 0.0
    y = float(pt[1]) if isinstance(pt[1], (int, float)) else 0.0
    z = float(pt[2]) if len(pt) > 2 and isinstance(pt[2], (int, float)) else 0.0
    return (x, y, z)


def _point_xyz(pt: Any) -> tuple[float | None, float | None, float | None]:
    """Split a [x, y, z] point into 3 columns, tolerating None/short/missing."""
    if not isinstance(pt, (list, tuple)):
        return (None, None, None)
    out = []
    for i in range(3):
        if i < len(pt) and isinstance(pt[i], (int, float)):
            out.append(float(pt[i]))
        else:
            out.append(None)
    return (out[0], out[1], out[2])


def _as_json(value: Any) -> str | None:
    """Stable JSON for a sidecar column; None passes through as SQL NULL."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


# --------------------------------------------------------------------------- #
# DDL
# --------------------------------------------------------------------------- #
def _create_base_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE drawings (
            id            INTEGER PRIMARY KEY,
            source        TEXT,
            dwg_name      TEXT,
            format        TEXT,
            extractor     TEXT,
            engine_tier   TEXT,
            entity_count  INTEGER,
            coverage_level TEXT,
            sha256        TEXT
        );

        CREATE TABLE entities (
            handle        TEXT PRIMARY KEY,
            class         TEXT,
            dxf_name      TEXT,
            layer         TEXT,
            owner_handle  TEXT,
            space         TEXT,
            geometry_kind TEXT,
            bbox_min_x    REAL,
            bbox_min_y    REAL,
            bbox_max_x    REAL,
            bbox_max_y    REAL,
            geometry_json TEXT
        );
        CREATE INDEX idx_entities_dxf_name ON entities(dxf_name);
        CREATE INDEX idx_entities_layer    ON entities(layer);
        CREATE INDEX idx_entities_owner    ON entities(owner_handle);

        CREATE TABLE layers (
            name          TEXT PRIMARY KEY,
            handle        TEXT,
            color_index   INTEGER,
            linetype      TEXT,
            frozen        INTEGER,
            locked        INTEGER,
            off           INTEGER
        );

        CREATE TABLE blocks (
            name          TEXT PRIMARY KEY,
            handle        TEXT,
            is_layout     INTEGER,
            is_anonymous  INTEGER,
            is_xref       INTEGER,
            entity_count  INTEGER
        );

        CREATE TABLE geometry_vertices (
            entity_handle TEXT,
            idx           INTEGER,
            x             REAL,
            y             REAL,
            z             REAL
        );
        CREATE INDEX idx_vertices_handle ON geometry_vertices(entity_handle);

        CREATE TABLE diagnostics (
            key           TEXT PRIMARY KEY,
            value         TEXT
        );
        """
    )


def _create_rich_tables(conn: sqlite3.Connection) -> None:
    """Create the M02 rich symbol-table / named-object tables.

    These are created unconditionally so the store schema is identical across
    coverage levels; a geometry_only / dxf IR simply leaves them empty.  All
    extra IR fields are preserved verbatim in an ``extra_json`` column so no
    record detail is lost when richer engines attach more fields.
    """
    conn.executescript(
        """
        CREATE TABLE linetypes (
            name           TEXT,
            handle         TEXT,
            description    TEXT,
            pattern_length REAL,
            extra_json     TEXT
        );

        CREATE TABLE text_styles (
            name           TEXT,
            handle         TEXT,
            font_file      TEXT,
            big_font_file  TEXT,
            height         REAL,
            width_factor   REAL,
            extra_json     TEXT
        );

        CREATE TABLE dim_styles (
            name           TEXT,
            handle         TEXT,
            extra_json     TEXT
        );

        CREATE TABLE layouts (
            handle                    TEXT,
            name                      TEXT,
            tab_order                 INTEGER,
            block_table_record_handle TEXT,
            plot_settings_ref         TEXT,
            extra_json                TEXT
        );

        CREATE TABLE xrefs (
            handle         TEXT,
            name           TEXT,
            path           TEXT,
            resolved_path  TEXT,
            status         TEXT,
            is_overlay     INTEGER,
            nesting_depth  INTEGER,
            extra_json     TEXT
        );

        CREATE TABLE dictionaries (
            id             INTEGER PRIMARY KEY,
            handle         TEXT,
            name           TEXT,
            owner_handle   TEXT,
            is_hard_owner  INTEGER,
            entry_count    INTEGER,
            extra_json     TEXT
        );

        CREATE TABLE dictionary_entries (
            dictionary_id  INTEGER,
            dictionary_name TEXT,
            key            TEXT,
            value_handle   TEXT
        );
        CREATE INDEX idx_dict_entries_dict ON dictionary_entries(dictionary_id);
        CREATE INDEX idx_dict_entries_value ON dictionary_entries(value_handle);

        CREATE TABLE xrecords (
            handle         TEXT,
            owner_handle   TEXT,
            dictionary     TEXT,
            key            TEXT,
            resbuf_json    TEXT,
            extra_json     TEXT
        );
        CREATE INDEX idx_xrecords_owner ON xrecords(owner_handle);

        CREATE TABLE block_references (
            handle               TEXT,
            block_name           TEXT,
            block_record_handle  TEXT,
            space                TEXT,
            layer                TEXT,
            ins_x                REAL,
            ins_y                REAL,
            ins_z                REAL,
            scale_x              REAL,
            scale_y              REAL,
            scale_z              REAL,
            rotation             REAL,
            is_dynamic           INTEGER,
            attributes_json      TEXT,
            extra_json           TEXT
        );
        CREATE INDEX idx_block_refs_name ON block_references(block_name);
        CREATE INDEX idx_block_refs_handle ON block_references(handle);
        CREATE INDEX idx_block_refs_btr ON block_references(block_record_handle);

        CREATE TABLE block_definitions (
            name           TEXT,
            handle         TEXT,
            entity_count   INTEGER,
            origin_x       REAL,
            origin_y       REAL,
            origin_z       REAL,
            extra_json     TEXT
        );
        CREATE INDEX idx_block_defs_handle ON block_definitions(handle);

        CREATE TABLE block_table_records (
            name           TEXT,
            handle         TEXT,
            is_layout      INTEGER,
            is_anonymous   INTEGER,
            is_xref        INTEGER,
            entity_count   INTEGER,
            source_table   TEXT,
            extra_json     TEXT
        );
        CREATE INDEX idx_btr_handle ON block_table_records(handle);
        """
    )


def _create_bbox_index(conn: sqlite3.Connection) -> bool:
    """Create bbox_index.

    Prefer an R*Tree virtual table ``bbox_index(id, minx, maxx, miny, maxy)``.
    If this SQLite build lacks the rtree module, fall back to a plain table
    ``bbox_index(handle, minx, miny, maxx, maxy)`` and return False.

    Returns True when the R*Tree virtual table was created, else False.
    """
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE bbox_index USING rtree(id, minx, maxx, miny, maxy)"
        )
        # The rtree module can register yet fail on first use on some builds;
        # exercise it once so we fall back deterministically if it is broken.
        conn.execute(
            "INSERT INTO bbox_index(id, minx, maxx, miny, maxy) VALUES (?,?,?,?,?)",
            (-1, 0.0, 0.0, 0.0, 0.0),
        )
        conn.execute("DELETE FROM bbox_index WHERE id = -1")
        # Map rowid -> entity handle (rtree id must be an integer).
        conn.execute(
            "CREATE TABLE bbox_index_map (id INTEGER PRIMARY KEY, handle TEXT)"
        )
        return True
    except sqlite3.OperationalError:
        # Roll back any half-created virtual table state, then build the plain
        # fallback table.
        try:
            conn.execute("DROP TABLE IF EXISTS bbox_index")
        except sqlite3.OperationalError:
            pass
        conn.execute(
            "CREATE TABLE bbox_index ("
            "handle TEXT PRIMARY KEY, minx REAL, miny REAL, maxx REAL, maxy REAL)"
        )
        return False


# --------------------------------------------------------------------------- #
# population
# --------------------------------------------------------------------------- #
def _populate_drawing(conn: sqlite3.Connection, ir: dict) -> int:
    source = ir.get("source") or {}
    diagnostics = ir.get("diagnostics") or {}
    source_repr = (
        source.get("dwg_path")
        or source.get("original_path")
        or source.get("dwg_name")
        or ""
    )
    conn.execute(
        "INSERT INTO drawings "
        "(id, source, dwg_name, format, extractor, engine_tier, entity_count, "
        " coverage_level, sha256) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            1,
            source_repr,
            source.get("dwg_name"),
            source.get("format"),
            source.get("extractor"),
            source.get("engine_tier"),
            int(diagnostics.get("entity_count") or 0),
            ir.get("coverage_level"),
            source.get("sha256"),
        ),
    )
    return 1


def _populate_layers(conn: sqlite3.Connection, ir: dict) -> int:
    layers = (ir.get("symbol_tables") or {}).get("layers") or []
    rows = []
    seen: set[str] = set()
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        name = layer.get("name")
        if name is None or name in seen:
            # Preserve len(layers) == row-count expectation only for unique,
            # named records; duplicates/unnamed are dropped but counted in the
            # validation gate against the realized rows.
            continue
        seen.add(name)
        rows.append(
            (
                name,
                layer.get("handle"),
                layer.get("color_index"),
                layer.get("linetype"),
                1 if layer.get("frozen") else 0,
                1 if layer.get("locked") else 0,
                1 if layer.get("off") else 0,
            )
        )
    conn.executemany(
        "INSERT INTO layers (name, handle, color_index, linetype, frozen, "
        "locked, off) VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    return len(rows)


def _populate_blocks(conn: sqlite3.Connection, ir: dict) -> int:
    btrs = (ir.get("symbol_tables") or {}).get("block_table_records") or []
    rows = []
    seen: set[str] = set()
    for btr in btrs:
        if not isinstance(btr, dict):
            continue
        name = btr.get("name")
        if name is None or name in seen:
            continue
        seen.add(name)
        rows.append(
            (
                name,
                btr.get("handle"),
                1 if btr.get("is_layout") else 0,
                1 if btr.get("is_anonymous") else 0,
                1 if btr.get("is_xref") else 0,
                btr.get("entity_count"),
            )
        )
    conn.executemany(
        "INSERT INTO blocks (name, handle, is_layout, is_anonymous, is_xref, "
        "entity_count) VALUES (?,?,?,?,?,?)",
        rows,
    )
    return len(rows)


def _extra_json(record: dict, mapped: set[str]) -> str | None:
    """JSON of any record keys not pulled into dedicated columns (loss-free)."""
    extra = {k: v for k, v in record.items() if k not in mapped}
    return _as_json(extra) if extra else None


def _populate_linetypes(conn: sqlite3.Connection, ir: dict) -> int:
    arr = (ir.get("symbol_tables") or {}).get("linetypes") or []
    mapped = {"name", "handle", "description", "pattern_length"}
    rows = []
    for rec in arr:
        if not isinstance(rec, dict):
            continue
        rows.append(
            (
                rec.get("name"),
                rec.get("handle"),
                rec.get("description"),
                rec.get("pattern_length"),
                _extra_json(rec, mapped),
            )
        )
    conn.executemany(
        "INSERT INTO linetypes (name, handle, description, pattern_length, "
        "extra_json) VALUES (?,?,?,?,?)",
        rows,
    )
    return len(rows)


def _populate_text_styles(conn: sqlite3.Connection, ir: dict) -> int:
    arr = (ir.get("symbol_tables") or {}).get("text_styles") or []
    mapped = {"name", "handle", "font_file", "big_font_file", "height", "width_factor"}
    rows = []
    for rec in arr:
        if not isinstance(rec, dict):
            continue
        rows.append(
            (
                rec.get("name"),
                rec.get("handle"),
                rec.get("font_file"),
                rec.get("big_font_file"),
                rec.get("height"),
                rec.get("width_factor"),
                _extra_json(rec, mapped),
            )
        )
    conn.executemany(
        "INSERT INTO text_styles (name, handle, font_file, big_font_file, "
        "height, width_factor, extra_json) VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    return len(rows)


def _populate_dim_styles(conn: sqlite3.Connection, ir: dict) -> int:
    arr = (ir.get("symbol_tables") or {}).get("dim_styles") or []
    mapped = {"name", "handle"}
    rows = []
    for rec in arr:
        if not isinstance(rec, dict):
            continue
        rows.append(
            (rec.get("name"), rec.get("handle"), _extra_json(rec, mapped))
        )
    conn.executemany(
        "INSERT INTO dim_styles (name, handle, extra_json) VALUES (?,?,?)",
        rows,
    )
    return len(rows)


def _populate_layouts(conn: sqlite3.Connection, ir: dict) -> int:
    arr = ir.get("layouts") or []
    mapped = {
        "handle", "name", "tab_order", "block_table_record_handle",
        "plot_settings_ref",
    }
    rows = []
    for rec in arr:
        if not isinstance(rec, dict):
            continue
        rows.append(
            (
                rec.get("handle"),
                rec.get("name"),
                rec.get("tab_order"),
                rec.get("block_table_record_handle"),
                rec.get("plot_settings_ref"),
                _extra_json(rec, mapped),
            )
        )
    conn.executemany(
        "INSERT INTO layouts (handle, name, tab_order, "
        "block_table_record_handle, plot_settings_ref, extra_json) "
        "VALUES (?,?,?,?,?,?)",
        rows,
    )
    return len(rows)


def _populate_xrefs(conn: sqlite3.Connection, ir: dict) -> int:
    arr = ir.get("xrefs") or []
    mapped = {
        "handle", "name", "path", "resolved_path", "status", "is_overlay",
        "nesting_depth",
    }
    rows = []
    for rec in arr:
        if not isinstance(rec, dict):
            continue
        rows.append(
            (
                rec.get("handle"),
                rec.get("name"),
                rec.get("path"),
                rec.get("resolved_path"),
                rec.get("status"),
                1 if rec.get("is_overlay") else 0,
                rec.get("nesting_depth"),
                _extra_json(rec, mapped),
            )
        )
    conn.executemany(
        "INSERT INTO xrefs (handle, name, path, resolved_path, status, "
        "is_overlay, nesting_depth, extra_json) VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    return len(rows)


def _populate_dictionaries(conn: sqlite3.Connection, ir: dict) -> tuple[int, int]:
    """Insert dictionaries and their entries. Returns (dict_rows, entry_rows)."""
    arr = ir.get("dictionaries") or []
    mapped = {
        "handle", "name", "owner_handle", "is_hard_owner", "entries",
    }
    dict_rows = []
    entry_rows = []
    for i, rec in enumerate(arr, start=1):
        if not isinstance(rec, dict):
            continue
        name = rec.get("name")
        entries = rec.get("entries") or []
        dict_rows.append(
            (
                i,
                rec.get("handle"),
                name,
                rec.get("owner_handle"),
                1 if rec.get("is_hard_owner") else 0,
                len(entries) if isinstance(entries, list) else 0,
                _extra_json(rec, mapped),
            )
        )
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                entry_rows.append(
                    (i, name, entry.get("key"), entry.get("value_handle"))
                )
    conn.executemany(
        "INSERT INTO dictionaries (id, handle, name, owner_handle, "
        "is_hard_owner, entry_count, extra_json) VALUES (?,?,?,?,?,?,?)",
        dict_rows,
    )
    conn.executemany(
        "INSERT INTO dictionary_entries (dictionary_id, dictionary_name, key, "
        "value_handle) VALUES (?,?,?,?)",
        entry_rows,
    )
    return len(dict_rows), len(entry_rows)


def _populate_xrecords(conn: sqlite3.Connection, ir: dict) -> int:
    arr = ir.get("xrecords") or []
    mapped = {"handle", "owner_handle", "dictionary", "key", "resbuf"}
    rows = []
    for rec in arr:
        if not isinstance(rec, dict):
            continue
        rows.append(
            (
                rec.get("handle"),
                rec.get("owner_handle"),
                rec.get("dictionary"),
                rec.get("key"),
                _as_json(rec.get("resbuf")),
                _extra_json(rec, mapped),
            )
        )
    conn.executemany(
        "INSERT INTO xrecords (handle, owner_handle, dictionary, key, "
        "resbuf_json, extra_json) VALUES (?,?,?,?,?,?)",
        rows,
    )
    return len(rows)


def _populate_block_references(conn: sqlite3.Connection, ir: dict) -> int:
    """Populate block_references from the dedicated index when present, else
    project the INSERT entities (block references carry block_name + insertion
    point + scale + rotation in their geometry)."""
    arr = ir.get("block_references")
    rows = []
    if isinstance(arr, list) and arr:
        mapped = {
            "handle", "block_name", "block_record_handle", "space", "layer",
            "insertion_point", "scale", "rotation", "is_dynamic", "attributes",
        }
        for rec in arr:
            if not isinstance(rec, dict):
                continue
            ix, iy, iz = _point_xyz(rec.get("insertion_point"))
            sx, sy, sz = _point_xyz(rec.get("scale"))
            rows.append(
                (
                    rec.get("handle"),
                    rec.get("block_name"),
                    rec.get("block_record_handle"),
                    rec.get("space"),
                    rec.get("layer"),
                    ix, iy, iz,
                    sx, sy, sz,
                    rec.get("rotation"),
                    1 if rec.get("is_dynamic") else 0,
                    _as_json(rec.get("attributes")),
                    _extra_json(rec, mapped),
                )
            )
    else:
        # Fallback: project INSERT entities (dxf_name == INSERT). The geometry
        # block carries block_name/position/scale/rotation.
        for ent in ir.get("entities") or []:
            if not isinstance(ent, dict) or ent.get("dxf_name") != "INSERT":
                continue
            geom = ent.get("geometry") or {}
            geom = geom if isinstance(geom, dict) else {}
            ix, iy, iz = _point_xyz(geom.get("position"))
            sx, sy, sz = _point_xyz(geom.get("scale"))
            rows.append(
                (
                    ent.get("handle"),
                    geom.get("block_name"),
                    None,
                    ent.get("space"),
                    ent.get("layer"),
                    ix, iy, iz,
                    sx, sy, sz,
                    geom.get("rotation"),
                    0,
                    None,
                    None,
                )
            )
    conn.executemany(
        "INSERT INTO block_references (handle, block_name, block_record_handle, "
        "space, layer, ins_x, ins_y, ins_z, scale_x, scale_y, scale_z, "
        "rotation, is_dynamic, attributes_json, extra_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    return len(rows)


def _populate_block_definitions(conn: sqlite3.Connection, ir: dict) -> int:
    arr = ir.get("block_definitions") or []
    mapped = {"name", "handle", "entity_count", "origin"}
    rows = []
    for rec in arr:
        if not isinstance(rec, dict):
            continue
        ox, oy, oz = _point_xyz(rec.get("origin"))
        rows.append(
            (
                rec.get("name"),
                rec.get("handle"),
                rec.get("entity_count"),
                ox, oy, oz,
                _extra_json(rec, mapped),
            )
        )
    conn.executemany(
        "INSERT INTO block_definitions (name, handle, entity_count, origin_x, "
        "origin_y, origin_z, extra_json) VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    return len(rows)


def _populate_block_table_records(conn: sqlite3.Connection, ir: dict) -> int:
    """Populate block_table_records from symbol_tables.block_table_records when
    present, else fall back to block_definitions[] (records the source)."""
    st_btrs = (ir.get("symbol_tables") or {}).get("block_table_records")
    if isinstance(st_btrs, list) and st_btrs:
        source_table = "symbol_tables.block_table_records"
        arr = st_btrs
    else:
        source_table = "block_definitions"
        arr = ir.get("block_definitions") or []
    mapped = {
        "name", "handle", "is_layout", "is_anonymous", "is_xref",
        "entity_count",
    }
    rows = []
    for rec in arr:
        if not isinstance(rec, dict):
            continue
        rows.append(
            (
                rec.get("name"),
                rec.get("handle"),
                1 if rec.get("is_layout") else 0,
                1 if rec.get("is_anonymous") else 0,
                1 if rec.get("is_xref") else 0,
                rec.get("entity_count"),
                source_table,
                _extra_json(rec, mapped),
            )
        )
    conn.executemany(
        "INSERT INTO block_table_records (name, handle, is_layout, "
        "is_anonymous, is_xref, entity_count, source_table, extra_json) "
        "VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    return len(rows)


def _populate_entities(
    conn: sqlite3.Connection, ir: dict, rtree_available: bool
) -> tuple[int, int, int]:
    """Insert entities, their vertices, and bbox_index rows.

    Returns (entity_rows, vertex_rows, bbox_rows).
    """
    entities = ir.get("entities") or []
    entity_rows = []
    vertex_rows = []
    bbox_rtree_rows = []   # (rowid_int, minx, maxx, miny, maxy)
    bbox_map_rows = []     # (rowid_int, handle)
    bbox_plain_rows = []   # (handle, minx, miny, maxx, maxy)

    seen_handles: set[str] = set()
    next_bbox_id = 1
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        handle = entity.get("handle")
        if handle is None or handle in seen_handles:
            # handle is the PRIMARY KEY / join key; a missing or duplicate
            # handle would corrupt the store, so it is skipped (and the gate
            # will catch any resulting count drift).
            continue
        seen_handles.add(handle)
        geometry = entity.get("geometry") or {}
        bounds = _bbox_bounds(entity.get("bbox"))
        entity_rows.append(
            (
                handle,
                entity.get("class"),
                entity.get("dxf_name"),
                entity.get("layer"),
                entity.get("owner_handle"),
                entity.get("space"),
                geometry.get("kind") if isinstance(geometry, dict) else None,
                bounds[0] if bounds else None,
                bounds[1] if bounds else None,
                bounds[2] if bounds else None,
                bounds[3] if bounds else None,
                json.dumps(geometry, ensure_ascii=False, sort_keys=True),
            )
        )

        if isinstance(geometry, dict):
            for idx, vertex in enumerate(geometry.get("vertices") or []):
                pt = _vertex_point(vertex)
                if pt is not None:
                    vertex_rows.append((handle, idx, pt[0], pt[1], pt[2]))

        if bounds is not None:
            minx, miny, maxx, maxy = bounds
            if rtree_available:
                bbox_rtree_rows.append((next_bbox_id, minx, maxx, miny, maxy))
                bbox_map_rows.append((next_bbox_id, handle))
                next_bbox_id += 1
            else:
                bbox_plain_rows.append((handle, minx, miny, maxx, maxy))

    conn.executemany(
        "INSERT INTO entities "
        "(handle, class, dxf_name, layer, owner_handle, space, geometry_kind, "
        " bbox_min_x, bbox_min_y, bbox_max_x, bbox_max_y, geometry_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        entity_rows,
    )
    conn.executemany(
        "INSERT INTO geometry_vertices (entity_handle, idx, x, y, z) "
        "VALUES (?,?,?,?,?)",
        vertex_rows,
    )
    if rtree_available:
        conn.executemany(
            "INSERT INTO bbox_index (id, minx, maxx, miny, maxy) VALUES (?,?,?,?,?)",
            bbox_rtree_rows,
        )
        conn.executemany(
            "INSERT INTO bbox_index_map (id, handle) VALUES (?,?)",
            bbox_map_rows,
        )
        bbox_count = len(bbox_rtree_rows)
    else:
        conn.executemany(
            "INSERT INTO bbox_index (handle, minx, miny, maxx, maxy) "
            "VALUES (?,?,?,?,?)",
            bbox_plain_rows,
        )
        bbox_count = len(bbox_plain_rows)

    return len(entity_rows), len(vertex_rows), bbox_count


def _populate_diagnostics(conn: sqlite3.Connection, ir: dict) -> int:
    diagnostics = ir.get("diagnostics") or {}
    rows = []
    for key, value in diagnostics.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            stored = value if isinstance(value, str) or value is None else json.dumps(value)
        else:
            stored = json.dumps(value, ensure_ascii=False, sort_keys=True)
        rows.append((str(key), stored))
    conn.executemany(
        "INSERT OR REPLACE INTO diagnostics (key, value) VALUES (?,?)", rows
    )
    return len(rows)


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def build_store(ir: dict, db_path: str) -> dict:
    """Build a SQLite IR store from an ariadne.dwg_graph_ir.v1 dict.

    Creates (overwriting any prior content) the base tables: drawings,
    entities, layers, blocks, geometry_vertices, bbox_index, diagnostics; plus
    the M02 rich tables: linetypes, text_styles, dim_styles, layouts, xrefs,
    dictionaries, dictionary_entries, xrecords, block_references,
    block_definitions, block_table_records. The rich tables are populated from
    a native_full IR; a geometry_only / dxf IR leaves them empty.

    Returns:
        {
          "db_path": str,
          "schema_ok": bool,                # ir["schema"] == expected const
          "row_counts": {table: int, ...},
          "capability": {"rtree_available": bool},
          "validation": {
             "entity_count_match": bool, "expected_entity_count": int,
             "actual_entity_rows": int,
             "layer_count_match": bool, "expected_layer_count": int,
             "actual_layer_rows": int,
             "ok": bool,
          },
        }

    No-fake-success: the validation block reports the realized vs expected row
    counts; a mismatch sets validation.ok = False rather than silently passing.
    """
    if not isinstance(ir, dict):
        raise TypeError("ir must be a dict conforming to ariadne.dwg_graph_ir.v1")

    schema_ok = ir.get("schema") == SCHEMA_ID

    conn = sqlite3.connect(db_path)
    try:
        # Clean slate so a rebuild over an existing path is deterministic.
        for tbl in (
            "drawings", "entities", "layers", "blocks", "geometry_vertices",
            "diagnostics", "bbox_index", "bbox_index_map",
            # M02 rich tables
            "linetypes", "text_styles", "dim_styles", "layouts", "xrefs",
            "dictionaries", "dictionary_entries", "xrecords",
            "block_references", "block_definitions", "block_table_records",
        ):
            conn.execute(f"DROP TABLE IF EXISTS {tbl}")

        _create_base_tables(conn)
        _create_rich_tables(conn)
        rtree_available = _create_bbox_index(conn)

        drawing_rows = _populate_drawing(conn, ir)
        layer_rows = _populate_layers(conn, ir)
        block_rows = _populate_blocks(conn, ir)
        entity_rows, vertex_rows, bbox_rows = _populate_entities(
            conn, ir, rtree_available
        )
        diag_rows = _populate_diagnostics(conn, ir)

        # M02 rich tables (additive; empty for geometry_only / dxf IRs).
        linetype_rows = _populate_linetypes(conn, ir)
        text_style_rows = _populate_text_styles(conn, ir)
        dim_style_rows = _populate_dim_styles(conn, ir)
        layout_rows = _populate_layouts(conn, ir)
        xref_rows = _populate_xrefs(conn, ir)
        dict_rows, dict_entry_rows = _populate_dictionaries(conn, ir)
        xrecord_rows = _populate_xrecords(conn, ir)
        block_ref_rows = _populate_block_references(conn, ir)
        block_def_rows = _populate_block_definitions(conn, ir)
        btr_rows = _populate_block_table_records(conn, ir)
        conn.commit()

        row_counts = {
            "drawings": drawing_rows,
            "entities": entity_rows,
            "layers": layer_rows,
            "blocks": block_rows,
            "geometry_vertices": vertex_rows,
            "bbox_index": bbox_rows,
            "diagnostics": diag_rows,
            "linetypes": linetype_rows,
            "text_styles": text_style_rows,
            "dim_styles": dim_style_rows,
            "layouts": layout_rows,
            "xrefs": xref_rows,
            "dictionaries": dict_rows,
            "dictionary_entries": dict_entry_rows,
            "xrecords": xrecord_rows,
            "block_references": block_ref_rows,
            "block_definitions": block_def_rows,
            "block_table_records": btr_rows,
        }

        diagnostics = ir.get("diagnostics") or {}
        expected_entities = int(diagnostics.get("entity_count") or 0)
        expected_layers = len((ir.get("symbol_tables") or {}).get("layers") or [])
        entity_match = entity_rows == expected_entities
        layer_match = layer_rows == expected_layers
        validation = {
            "entity_count_match": entity_match,
            "expected_entity_count": expected_entities,
            "actual_entity_rows": entity_rows,
            "layer_count_match": layer_match,
            "expected_layer_count": expected_layers,
            "actual_layer_rows": layer_rows,
            "ok": entity_match and layer_match,
        }

        return {
            "db_path": db_path,
            "schema_ok": schema_ok,
            "row_counts": row_counts,
            "capability": {"rtree_available": rtree_available},
            "validation": validation,
        }
    finally:
        conn.close()


def query(db_path: str, sql: str) -> dict:
    """Run a read-only SQL query against an existing IR store.

    Opens the database read-only (mode=ro) so this can never mutate the store.
    Returns {"columns": [...], "rows": [...]} where rows is a list of tuples.
    """
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cur = conn.execute(sql)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = [tuple(r) for r in cur.fetchall()]
        return {"columns": columns, "rows": rows}
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# self-demo
# --------------------------------------------------------------------------- #
def _fixture_ir() -> dict:
    """A tiny inline IR fixture conforming to ariadne.dwg_graph_ir.v1."""
    return {
        "schema": SCHEMA_ID,
        "coverage_level": "geometry_only",
        "source": {
            "dwg_path": "staging/golden/demo/demo.dwg",
            "dwg_name": "demo.dwg",
            "format": "dwg",
            "extractor": "fixture",
            "engine_tier": "dxf",
        },
        "database": {},
        "symbol_tables": {
            "layers": [
                {"name": "0", "handle": "10", "color_index": 7},
                {"name": "WALLS", "handle": "11", "color_index": 1},
            ],
            "block_table_records": [
                {"name": "*Model_Space", "handle": "1F", "is_layout": True},
                {"name": "DOOR", "handle": "A0", "entity_count": 1},
            ],
        },
        "entities": [
            {
                "handle": "2A7", "class": "AcDbLine", "dxf_name": "LINE",
                "owner_handle": "1F", "space": "model", "layer": "0",
                "bbox": [0.0, 0.0, 0.0, 10.0, 0.0, 0.0],
                "geometry": {
                    "kind": "line",
                    "start": [0.0, 0.0, 0.0], "end": [10.0, 0.0, 0.0],
                },
                "source": {"extractor": "fixture", "decoded": True},
            },
            {
                "handle": "2A8", "class": "AcDbPolyline", "dxf_name": "LWPOLYLINE",
                "owner_handle": "1F", "space": "model", "layer": "WALLS",
                "bbox": [0.0, 0.0, 0.0, 5.0, 5.0, 0.0],
                "geometry": {
                    "kind": "lwpolyline", "closed": True,
                    "vertices": [
                        {"point": [0.0, 0.0, 0.0]},
                        {"point": [5.0, 0.0, 0.0]},
                        {"point": [5.0, 5.0, 0.0]},
                    ],
                },
                "source": {"extractor": "fixture", "decoded": True},
            },
        ],
        "diagnostics": {
            "entity_count": 2,
            "count_scope": "modelspace",
            "realized_entity_count": 2,
            "entities_by_type": {"LINE": 1, "LWPOLYLINE": 1},
            "warnings": [],
            "errors": [],
            "coverage": {"sections_present": ["layers", "entities"]},
        },
    }


def _self_demo() -> int:
    import tempfile
    import os

    fd, path = tempfile.mkstemp(suffix=".sqlite", prefix="ir_store_demo_")
    os.close(fd)
    try:
        report = build_store(_fixture_ir(), path)
        result = query(path, "select count(*) from entities")
        report["self_demo_query"] = {
            "sql": "select count(*) from entities",
            "result": result,
        }
        # bbox_index sanity (count rows regardless of rtree vs plain).
        bbox_q = query(path, "select count(*) from bbox_index")
        report["self_demo_bbox_count"] = bbox_q["rows"][0][0] if bbox_q["rows"] else None
        print(json.dumps(report, ensure_ascii=False, indent=2))
        ok = (
            report["validation"]["ok"]
            and result["rows"] == [(2,)]
            and report["row_counts"]["entities"] == 2
            and report["row_counts"]["layers"] == 2
            and report["row_counts"]["geometry_vertices"] == 3
        )
        return 0 if ok else 1
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(_self_demo())
