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

    Creates (overwriting any prior content) the tables: drawings, entities,
    layers, blocks, geometry_vertices, bbox_index, diagnostics.

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
        ):
            conn.execute(f"DROP TABLE IF EXISTS {tbl}")

        _create_base_tables(conn)
        rtree_available = _create_bbox_index(conn)

        drawing_rows = _populate_drawing(conn, ir)
        layer_rows = _populate_layers(conn, ir)
        block_rows = _populate_blocks(conn, ir)
        entity_rows, vertex_rows, bbox_rows = _populate_entities(
            conn, ir, rtree_available
        )
        diag_rows = _populate_diagnostics(conn, ir)
        conn.commit()

        row_counts = {
            "drawings": drawing_rows,
            "entities": entity_rows,
            "layers": layer_rows,
            "blocks": block_rows,
            "geometry_vertices": vertex_rows,
            "bbox_index": bbox_rows,
            "diagnostics": diag_rows,
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
