# DWG Graph IR v1 — Specification

`schema`: `ariadne.dwg_graph_ir.v1`
JSON Schema: `schemas/dwg_graph_ir.v1.schema.json` (draft-07)
Status: v1 (CAD OS Layer, Lane A / SCHEMAS). Authored alongside the frozen v1 working surface; does not modify it.

---

## 1. Purpose and position

The DWG Graph IR is the **engine-neutral intermediate representation** of a single DWG/DXF
drawing. Any extraction lane — native ObjectARX (`objectarx_active_document`), ObjectDBX
side-database (`objectdbx_sidedb`), managed `accoremgd`, AutoLISP/`ssget`
(`autolisp_ssget`), or DXF via `ezdxf` — normalizes its output to this one shape so that
downstream consumers (diff, validation, lineage, the Ariadne graph planes) never depend on
*which* engine produced the data.

It is a **graph** in the sense that records are joined by `handle` (the DWG entity/object
handle): entities point at their owning block table record via `owner_handle`; dictionaries,
extension dictionaries, xrecords, and groups reference their targets by handle; block
references resolve to block definitions by name/handle. The handle is the single portable
join key across all sections and across all engines.

Relationship to the existing v1 contracts:

- It is a **superset** of `schemas/dwg_geometry_extract.schema.json`
  (`ariadne.dwg_geometry_extract.v1`). Every geometry `kind` in that contract
  (`line, polyline, arc, circle, block_reference, text, mtext, dimension, hatch,
  unsupported`) is a subset of the IR's `geometry.kind` enum. An extract document can be
  lifted into IR `entities[]` without information loss.
- It is the `output_mode: "ir"` payload referenced by `schemas/cad_result.v2.schema.json`
  via `ir_ref`, and the `before_ref`/`after_ref` (`kind: "ir"`) of
  `schemas/cad_diff.v1.schema.json`.
- It is the subject of the entity-count truth gate in
  `schemas/validation_report.v1.schema.json`.

`additionalProperties` is `true` at object boundaries where a richer engine may attach
extra fields. The contract is the **required** key set plus the **truth gate** (Section 6),
not an exhaustive closed shape.

---

## 2. Top-level document

```jsonc
{
  "schema": "ariadne.dwg_graph_ir.v1",   // required, const
  "ir_version": "1.0.0",                  // optional producer semver
  "coverage_level": "native_full",        // declared completeness tier (Section 5)
  "source": { ... },                      // required — provenance (Section 3)
  "database": { ... },                    // required — drawing-level state (Section 4.1)
  "symbol_tables": { "layers": [ ... ] }, // required — symbol tables (Section 4.2)
  "block_definitions": [ ... ],           // optional — block geometry (Section 4.3)
  "block_references": [ ... ],            // optional — INSERT projection (Section 4.3)
  "xrefs": [ ... ],                       // optional (Section 4.4)
  "dictionaries": [ ... ],                // optional (Section 4.5)
  "extension_dictionaries": [ ... ],      // optional (Section 4.5)
  "xrecords": [ ... ],                    // optional (Section 4.5)
  "groups": [ ... ],                      // optional (Section 4.6)
  "materials": [ ... ],                   // optional (Section 4.6)
  "plot_settings": [ ... ],               // optional (Section 4.6)
  "layouts": [ ... ],                     // optional (Section 4.6)
  "custom_objects": [ ... ],              // optional — proxy/custom (Section 4.7)
  "classes": [ ... ],                     // optional — CLASSES section (Section 4.7)
  "entities": [ ... ],                    // required — flat entity list (Section 4.8)
  "spatial_index": { ... },               // optional — advisory (Section 4.9)
  "diagnostics": { ... }                  // required — self-report + truth gate (Section 6)
}
```

**Required top-level keys**: `schema`, `source`, `database`, `symbol_tables`, `entities`,
`diagnostics`. Everything else is populated as the coverage level allows; absence of an
optional section means "not extracted at this coverage level", which MUST be reflected in
`diagnostics.coverage.sections_skipped`.

---

## 3. `source` — provenance (`$defs.source_descriptor`)

Traces the IR to an exact input and producer. Required so a merged or partial IR can be
audited.

| field | meaning |
|---|---|
| `dwg_path` | Path to the drawing the IR was extracted from. For write/patch flows this is the **staged copy**, never the read-only original. |
| `original_path` | The read-only original, when extraction worked from a staged copy. |
| `dwg_name`, `format` | Display name; `format` ∈ `dwg \| dxf \| dxb \| unknown`. |
| `dwg_version` | DWG format code (e.g. `AC1032` = 2018, `AC1027` = 2013). |
| `byte_size`, `sha256`, `mtime` | Integrity fingerprints of the source bytes. |
| `extractor` | Producing extractor name (`objectarx_active_document`, `objectdbx_sidedb`, `autolisp_ssget`, `accoremgd_managed`, `ezdxf`). |
| `extractor_version` | Extractor build/version. |
| `engine_tier` | API surface used: `native_arx \| objectdbx \| managed \| accoreconsole_lisp \| dxf`. |
| `extracted_at` | ISO-8601 extraction timestamp. |

**Original-DWG safety**: when `original_path` is set, the producer MUST have read from
`dwg_path` (the staged copy) and MUST NOT have written `original_path`. The IR records the
fact of staging; it does not authorize any write.

---

## 4. Sections

### 4.1 `database` — drawing-level state

Drawing-wide settings that scope the whole file.

- `header_vars` — raw DWG/DXF header system variables (`ACADVER`, `DWGCODEPAGE`, `LUNITS`,
  `AUNITS`, `PDMODE`, …). Keys are variable names; values are scalar/array as stored.
- `units` — resolved units: `insunits` (+`insunits_text`), `linear_units` (LUNITS),
  `angular_units` (AUNITS), and precisions.
- `insbase` — `INSBASE` system variable: the insertion base point used when this drawing is
  inserted as a block/xref elsewhere (`$defs.point3`, `[x,y,z]`).
- `extents` — `extmin`/`extmax` (EXTMIN/EXTMAX) and `limmin`/`limmax` (LIMMIN/LIMMAX).
- `ucs` — current UCS origin/axes at extraction time.
- `codepage` — `DWGCODEPAGE`/code page; relevant for non-ASCII layer names (e.g. Korean
  `설비OPEN`).

### 4.2 `symbol_tables` — the DWG symbol tables

`layers` is the **only required** member (it MAY be empty under `geometry_only` coverage);
every other table is present at richer coverage levels.

| table | `$defs` | key fields |
|---|---|---|
| `layers` *(required)* | `layer_record` | `name` (req), `handle`, `color_index`, `true_color`, `linetype`, `lineweight`, `plottable`, `frozen`, `locked`, `off`, `is_xref_dependent` |
| `linetypes` | `linetype_record` | `name` (req), `description`, `pattern_length`, `dash_lengths[]` |
| `text_styles` | `text_style_record` | `name` (req), `font_file`, `big_font_file` (CJK SHX bigfont), `height`, `width_factor`, `oblique_angle` |
| `dim_styles` | `dim_style_record` | `name` (req), `dim_vars{}` (DIMSCALE, DIMTXT, …) |
| `block_table_records` | `block_table_record` | `name` (req), `is_layout`, `is_anonymous`, `is_xref`, `is_xref_overlay`, `has_attribute_definitions`, `origin`, `entity_count` |
| `viewports` | `viewport_record` | `name` (req), `center`, `height`, `width`, `view_target`, `view_direction` (VPORT named configs) |
| `views` | object | named VIEW records |
| `ucs_table` | object | named UCS records |
| `app_ids` | object | registered application IDs (APPID/RegApp) used by XDATA |

`block_table_records` is the **registry** of block table records (`*Model_Space`,
`*Paper_Space`, named blocks, `*U###`/`*D###` anonymous blocks). Their **geometry** lives in
`block_definitions` (Section 4.3) keyed by the same `handle`.

### 4.3 Blocks — definitions and references

- `block_definitions[]` (`$defs.block_definition`) — the geometric/content definition of each
  BTR that owns geometry. `handle` is the BTR handle; `origin`, `bbox`,
  `attribute_definitions[]` (ATTDEF templates). The definition's entities are provided by
  **one of two strategies** (the extractor declares which in `diagnostics.coverage`):
  1. **Inlined** — `def_entities[]` carries the geometry (same `entity` shape as top-level).
  2. **Referenced** — definition entities live in the top-level `entities[]` array with
     `owner_handle == this BTR handle` and `space == "block"`.
- `block_references[]` (`$defs.block_reference`) — an **optional projection** of all `INSERT`
  entities with resolved placement, for consumers that walk instance trees. INSERTs also
  appear in `entities[]`; the projection shares the same `handle`. Fields: `block_name`,
  `block_record_handle`, `space`, `layer`, `insertion_point`, `scale` (X/Y/Z),
  `rotation` (**radians** — see Section 7), `normal` (OCS), `transform` (optional 4×4
  row-major matrix, 16 numbers), `is_dynamic`, `attributes[]` (ATTRIB `tag`/`value`/`handle`).

### 4.4 `xrefs[]` (`$defs.xref_record`)

External reference blocks: `name`, `path` (saved), `resolved_path`, `status`
(`resolved \| unresolved \| unloaded \| unreferenced \| not_found \| orphaned`),
`is_overlay`, `nesting_depth`.

### 4.5 Dictionaries, extension dictionaries, xrecords

- `dictionaries[]` (`$defs.dictionary_record`) — named object dictionaries (`ACAD_GROUP`,
  `ACAD_LAYOUT`, `ACAD_MLINESTYLE`, `ACAD_PLOTSETTINGS`, custom). `entries[]` are
  `key → value_handle` pairs (`$defs.dictionary_entry`). `is_hard_owner` distinguishes
  ownership.
- `extension_dictionaries[]` — per-object extension dictionaries, keyed by `owner_handle`,
  each with its `dictionary_handle` and `entries[]`. This is the app-specific persistent data
  an entity owns.
- `xrecords[]` (`$defs.xrecord_record`) — `XRECORD` objects wherever they live (named dicts,
  extension dicts, NOD). Each carries `handle`, `owner_handle`, owning `dictionary`
  name/path (e.g. `ARIADNE`, `ARIADNE_NATIVE` — matching the wired `write.xrecord.set` /
  `inspect.xrecord.get` defaults), `key`, and a decoded `resbuf[]` (ordered DXF
  group-code/value pairs, `$defs.resbuf_item`).

### 4.6 Named collections

- `groups[]` — `ACAD_GROUP` entries: `name`, `selectable`, `anonymous`, and `members[]`
  (handles of member entities).
- `materials[]` — `ACAD_MATERIAL` render materials.
- `plot_settings[]` — named plot settings (`ACAD_PLOTSETTINGS`) / per-layout plot config
  (paper size, plot area, scale).
- `layouts[]` — `ACAD_LAYOUT` objects: Model + each paper-space layout, with `tab_order`,
  the owning `block_table_record_handle` (the paper-space BTR holding the layout geometry),
  and `plot_settings_ref`.

### 4.7 Custom / proxy objects and classes

- `custom_objects[]` (`$defs.custom_object_record`) — custom/proxy objects and entities
  (`ACAD_PROXY_ENTITY` / `ACAD_PROXY_OBJECT`, live third-party classes). `class_name`,
  `dxf_name`, `app_name` (owning ARX app), `is_proxy` (owning app not loaded → proxy graphics
  only), `decoded` (**true only when natively decoded**), `graphics_only`, `owner_handle`.
  This is the structural **no-fake-success** marker: an object present but not decodable is
  recorded as `decoded: false`, never silently dropped or faked.
- `classes[]` — the DWG `CLASSES` section: registered custom class records
  (`dxf_name`, `cpp_class_name`, `app_name`, proxy flags) so a consumer knows which entity
  classes require which ARX app.

### 4.8 `entities[]` (`$defs.entity`) — the flat entity list

Every entity across model space and all paper-space layouts (and optionally
block-definition geometry, when not inlined under `block_definitions`). This array's
**realized length is the truth-gate numerator** (Section 6).

Required per entity: `handle`, `class`, `dxf_name`, `owner_handle`, `space`, `layer`,
`bbox`, `geometry`, `source`.

| field | meaning |
|---|---|
| `handle` | DWG handle (uppercase hex). Portable join key. |
| `object_id` | Optional engine-local pointer/id (non-portable; `handle` is the portable key). Carries the v1 extract `object_id`. |
| `class` | Runtime class name (`AcDbLine`, `AcDbBlockReference`, …). |
| `dxf_name` | DXF entity name (`LINE`, `LWPOLYLINE`, `INSERT`, `DIMENSION`, …). |
| `owner_handle` | Handle of the owning BTR (model space, paper space, or a block definition). Empty string allowed when the owner is unresolved. |
| `space` | `model \| paper \| block`. |
| `layout` | Layout/tab name when `space == "paper"`. |
| `layer`, `linetype`, `color_index`, `lineweight`, `visible` | Common entity properties. |
| `bbox` | Axis-aligned box `[minX,minY,minZ,maxX,maxY,maxZ]` (`$defs.bbox`); `[]` = no bbox computed. |
| `geometry` | Coordinate payload (`$defs.geometry`, below). |
| `xdata[]` | XDATA blocks per registered app (`$defs.xdata_block`: `app` + `items[]` of resbuf). |
| `extension_dictionary_handle` | Handle of this entity's extension dictionary, if any. |
| `reactors[]` | Handles of persistent reactors attached to the entity. |
| `source{}` | Per-entity provenance: `extractor`, `engine_tier`, `decoded` (false ⇒ `geometry.kind == unsupported`/proxy fallback), `notes`. Lets a merged/partial IR attribute each entity. |

**`geometry`** (`$defs.geometry`) is discriminated by `kind`. Only the fields relevant to a
kind are populated; `additionalProperties: true` allows engine-specific extras (bulge arrays,
OCS normals, spline knots). `kind` enum:

`line, polyline, lwpolyline, arc, circle, ellipse, spline, point, text, mtext,
block_reference, attribute, dimension, leader, hatch, solid, region, viewport, ray, xline,
proxy, unsupported`.

Common geometry fields: `start`, `end`, `center`, `position`, `radius`, `major_axis`,
`minor_ratio`, `start_angle`, `end_angle`, `normal` (OCS), `closed`,
`vertices[]` (each `{point, bulge, start_width, end_width}` for polyline family),
`text`, `height`, `rotation`, `block_name`, `scale`, `dimension_type`, `measurement`,
`control_points[]`, `degree`, `loops[]` (hatch boundaries), `pattern_name`.

`kind == "unsupported"` (or `proxy`) means the extractor **recognized the entity but did not
emit coordinate geometry**. This is a first-class, honest state — paired with
`source.decoded == false` and counted in `diagnostics.coverage.proxy_or_undecoded_count`.

### 4.9 `spatial_index` — advisory

Optional acceleration structure over `entities[]`: `kind`
(`rtree \| grid \| quadtree \| bvh \| none`), `world_bbox`, `nodes[]`. **Advisory only** —
consumers MAY ignore it and build their own index from per-entity `bbox`. It is never the
source of truth for which entities exist.

---

## 5. Coverage levels

`coverage_level` declares the completeness tier of the document. It tells a consumer how much
to trust the absence of a section, and which engine class produced it.

| level | meaning | typical producer |
|---|---|---|
| `native_full` | Full native traversal: header + all symbol tables + block defs + entities + xdata + dictionaries + custom/proxy. | ObjectARX in-process (`objectarx_active_document`) |
| `dbx_full` | Full ObjectDBX side-database traversal (host-less, in `accoreconsole`). | `objectdbx_sidedb` |
| `managed_full` | Full managed (`accoremgd`/`acdbmgd`) traversal. | `accoremgd_managed` |
| `dxf_geometry` | DXF-derived geometry; **no** live runtime objects/proxies, limited dictionaries. | `ezdxf` over a DXF export |
| `geometry_only` | Entities + `bbox` without symbol-table depth; `symbol_tables.layers` may be empty. | quick AutoLISP/`ssget` pass |
| `partial` | Explicitly incomplete — see `diagnostics.errors`. | any aborted/degraded run |

The level is a **promise about what was attempted**, not a quality score. A `geometry_only`
IR with a passing truth gate is fully valid for geometry consumers; it simply does not carry
symbol-table or dictionary depth. Whatever a level omits MUST appear in
`diagnostics.coverage.sections_skipped`.

---

## 6. The entity-count truth gate

The IR's single hardest invariant.

`diagnostics.entity_count` is the **asserted** entity count for the declared
`diagnostics.count_scope`
(`modelspace \| modelspace_and_paperspace \| all_including_block_definitions \| total`).
`diagnostics.realized_entity_count` is the **actual** length of `entities[]` as emitted.

**Gate**: for the matching scope,

```
diagnostics.entity_count == realized_entity_count == len(entities[] in scope)
```

A mismatch is a **hard failure** — it means the extractor claimed a count it did not
materialize. This is checked by `schemas/validation_report.v1.schema.json` as a gate with
`id` e.g. `entity_count_truth`, `expected` = asserted count, `actual` = realized count,
`operator` = `eq`.

`diagnostics.entities_by_type{}` (per-DXF-type counts) MUST sum to `entity_count` for the
matching scope.

**Cross-engine agreement** is the strongest form of the gate. When independent engines extract
the same drawing and assert the same count, each contributing engine is recorded in
`diagnostics.engines[]` (`{extractor, engine_tier, entity_count}`). The production baseline for
this repo is the documented **3-way agreement of 21747 modelspace entities** for the large
production `input.dwg`:

- ObjectARX (`objectarx_active_document`) = 21747
- ObjectDBX (`objectdbx_sidedb`) = 21747
- AutoLISP/`ssget` (`autolisp_ssget`) = 21747
- `entities_by_type` (AutoLISP): LINE 16276, INSERT 2027, POLYLINE 1874, ARC 753, HATCH 669,
  MTEXT 106, CIRCLE 33, TEXT 9 (sums to 21747).

> Note on "golden" selection: the byte-`input.dwg` name has been reused across multiple
> distinct drawings over time. 21747 is the well-attested truth count for the **large
> production drawing**, not for every file historically named `input.dwg` (a 48416-byte early
> sample and a separate 389-entity drawing also exist). When binding a truth-count gate, the
> drawing identity (path + `source.sha256`/`byte_size`) MUST be pinned alongside the count —
> the IR's `source` block exists precisely to make that binding explicit.

`diagnostics.coverage.proxy_or_undecoded_count` accounts for entities present but not natively
decoded; these still count toward `entity_count` (they exist in the drawing) but are flagged so
no consumer mistakes a proxy fallback for a full decode.

---

## 7. How the IR maps to native / managed / DXF extraction

The IR is the **join target** for the router's three extraction families. Each populates the
same shape from a different API surface:

| IR concern | native ObjectARX / ObjectDBX | managed `accoremgd`/`acdbmgd` | DXF (`ezdxf`) |
|---|---|---|---|
| `handle` | `AcDbObject::handle()` / `ObjectId.Handle` | `ObjectId.Handle` | DXF handle group code 5 |
| `entities[]` traversal | iterate `*Model_Space`/`*Paper_Space` BTRs + block defs | `BlockTableRecord` iteration | `modelspace()` / `paperspace()` / `INSERT` blocks |
| `geometry` | per-class native getters (e.g. `AcDbLine::startPoint`) | managed property getters | DXF group codes (10/11/40 …) |
| `symbol_tables` | `acdbHostApplicationServices()->workingDatabase()` tables | `Database.LayerTableId` etc. | DXF `TABLES` section |
| `xdata` / `xrecords` | resbuf walk (`acdbEntGet`/`AcDbXrecord`) | `ResultBuffer` | DXF 1001+ app groups / `XRECORD` objects |
| `custom_objects` | live class info or `AcDbProxyEntity` | managed proxy class info | DXF `CLASSES` + proxy entity data |
| `coverage_level` | `native_full` / `dbx_full` | `managed_full` | `dxf_geometry` |

Rules that keep the mapping honest:

- **Coordinate payloads required for known kinds.** When an engine can decode an entity's
  geometry it MUST emit coordinates (matching the v1
  `tools/validate_dwg_geometry_extract.py` `require_coordinate_payloads` rule). Emitting a
  recognized entity with no coordinates and `kind != unsupported` is invalid.
- **Undecodable ⇒ `unsupported`/`proxy` + `decoded:false`.** DXF and proxy lanes that cannot
  decode a custom class record it as `unsupported`/`proxy`, not as a guessed primitive.
- **DXF lane limits.** `dxf_geometry` coverage legitimately lacks live runtime objects
  (reactors, live overrules, in-session proxies); those sections are `sections_skipped`, not
  faked.
- **Angles.** `rotation`/`start_angle`/`end_angle` are emitted in **radians** by the native
  and managed lanes (consistent with the ObjectARX/`acdbmgd` APIs). A DXF lane that reads
  degrees MUST convert to radians before emitting, or declare the unit in `source.notes`.

---

## 8. Validation checklist (producer self-check)

A producer SHOULD verify before emitting:

1. `schema == "ariadne.dwg_graph_ir.v1"`.
2. Required top-level keys present: `source`, `database`, `symbol_tables`, `entities`,
   `diagnostics`.
3. `symbol_tables.layers` present (possibly empty).
4. Every `entities[]` item has all required fields, and a `geometry.kind` in the enum.
5. **Truth gate**: `diagnostics.entity_count == diagnostics.realized_entity_count ==
   len(entities in count_scope)`; `entities_by_type` sums to `entity_count`.
6. `coverage_level` set, and `diagnostics.coverage.sections_skipped` lists every optional
   section deliberately omitted.
7. Any undecoded/proxy entity has `source.decoded == false`, `geometry.kind ∈
   {unsupported, proxy}`, and is counted in `coverage.proxy_or_undecoded_count`.
8. `source.dwg_path` is a staged copy whenever `source.original_path` is set; the original was
   not written.

---

## 9. Change discipline

- This IR is **v1**. Backward-incompatible changes (removing/renaming a required key, removing
  a `geometry.kind`) require a `dwg_graph_ir.v2.schema.json` authored **alongside** v1, never an
  in-place edit — the same additive rule the CAD OS Layer applies to `cad_job` v1→v2.
- New optional sections / fields / `kind` values are additive and allowed within v1
  (`additionalProperties: true`), provided they do not alter the required set or the truth
  gate.
