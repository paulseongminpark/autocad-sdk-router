# DWG Graph IR v1 — Specification

`schema`: `ariadne.dwg_graph_ir.v1`
JSON Schema: `schemas/dwg_graph_ir.v1.schema.json` (draft-07)
Status: v1 (CAD OS Layer, Lane A / SCHEMAS). Authored alongside the frozen v1 working surface; does not modify it.
Producer: `tools/ir_builder.py` — `build_ir_from_extract(...)` (geometry_only) and `build_ir_from_database_graph(...)` (native_full).
Current producer version: `1.1.0`

> **M02 state (this doc is implementation-true, not aspirational).** The IR is produced at **two**
> coverage levels today. A live **`native_full`** IR exists at
> `runs/m02_cadctl_rich/dwg_graph_ir.json` (15.7 MB, **21747** entities) — Section 10 documents
> exactly which sections are IMPLEMENTED vs PARTIAL/deferred against that artifact. The
> `geometry_only` builder is unchanged from M01. Sections 1–9 describe the *full v1 schema surface*;
> Section 10 states *what an M02 native_full IR actually carries*. Where they differ, Section 10 is
> the live truth.

---

## Version history

| version | change | compatibility |
|---|---|---|
| `1.1.0` | Add additive entity identity fields `stable_id` and `stable_id_ordinal`; document float normalization (`1e-6`) and viewport-managed exclusions (`center/height/width`). | Backward-compatible minor bump; existing consumers still read the v1 schema/id unchanged. |
| `1.0.0` | Initial producer version for the documented v1 graph IR surface. | Baseline. |

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
| `stable_id` | Additive content hash over entity kind, layer, normalized geometry payload, and normalized non-volatile attributes. Volatile fields such as `handle`, owner/auxiliary handles, per-entity provenance, XDATA, and AutoCAD-managed viewport display fields are excluded. Floats are normalized at `1e-6` before hashing. |
| `stable_id_ordinal` | Deterministic duplicate disambiguator within one emitted entity list: entities that share the same `stable_id` are ordered by `handle` and assigned ordinals `0..n-1`. The ordinal is only stable while that duplicate set is unchanged. |
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
| `clip{}` | XCLIP spatial-filter clip on a clipped `AcDbBlockReference` (INSERT): `enabled`, `inverted`, `elevation`, `front_clip`, `back_clip`, `normal`, `boundary` (2D vertices in the block reference's ECS). Emitted only when the INSERT is XCLIP-clipped (`ACAD_FILTER`/`SPATIAL` on the block reference's own extension dictionary). Display/visibility attribute — excluded from `stable_id`. |
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

#### Stable entity identity

`stable_id` is intentionally **not** a handle alias. It is a canonical SHA-256 hash of:

- entity kind (`dxf_name` + `geometry.kind`)
- `layer`
- normalized `geometry`
- normalized non-volatile attributes (`space`, `layout`, common display attributes when present)

Normalization rules:

- Floats are rounded to `1e-6` before hashing so save/reopen noise does not churn identity.
- `bbox` is excluded because it is derived from geometry.
- Handle-bearing fields are excluded: `handle`, `owner_handle`, `object_id`, `block_record_handle`,
  `dim_block_handle`, `extension_dictionary_handle`, reactor handles, nested attribute handles, and
  similar auxiliary handles.
- Per-entity provenance (`source`) and XDATA are excluded because they are not stable identity inputs.
- The viewport-managed trio discovered in the capstone regen evidence —
  `center`, `height`, `width` (the same fields named by
  `tools/full_roundtrip_capstone.py::VPORT_MANAGED_FIELDS`) — is excluded from `viewport`
  geometry hashing because AutoCAD rewrites that display state on its own.

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

---

## 10. M02 `native_full` IR — what is actually populated (implementation-true)

This section pins the *realized* native_full IR shape against the live artifact, so a consumer
knows exactly which sections to trust and which are still partial/deferred. It is not a wish list.

**Reference artifact** (read-only): `runs/m02_cadctl_rich/dwg_graph_ir.json`
(`schema = ariadne.dwg_graph_ir.v1`, `ir_version = 1.1.0`, `coverage_level = native_full`).
Produced by `cadctl.Cad().inspect(dwg, out_dir, mode="graph", include_rich=True)` →
`run_job.run_router_cad_job(staged, run_dir, "inspect.database.graph", write_mode="read")` →
`ir_builder.build_ir_from_database_graph(result, source_meta)`. The native job result it consumes
is `runs/dwg_truth_autocad_cad_job_20260622_012807/native_cad_job_result.json` (its `.result`
object). The native graph op **is router-wired** in M02 (`autocad-router.ps1`
`Test-NativeP1CadJobOperation` allow-list, line 152 — closes M01 carry-forward D2).

### 10.1 The truth gate, measured

```
diagnostics.entity_count == len(entities) == 21747          (PASS — holds by construction)
native result.modelspace_entities == 21747                  (cross-checked; coverage.match == true)
*Model_Space block_table_record.entity_count == 21747
entities_by_type (sum == 21747):
  LINE 16276 · INSERT 2027 · POLYLINE 1874 · ARC 753 · HATCH 669 · MTEXT 106 · CIRCLE 33 · TEXT 9
```

The producer never fakes this: `build_ir_from_database_graph` sets
`diagnostics.entity_count = len(entities)` (realized length is the numerator) and records a
warning + `coverage.match = false` if the native asserted `modelspace_entities` disagrees. For
this artifact they agree exactly.

> **Golden-identity caveat (load-bearing).** `21747` is the truth count for the **large production
> drawing** pinned by `source.original_path = staging/dwg_20260617_191504/input.dwg`,
> `byte_size = 2524981`, `sha256 = 27dbf6b95ff…`. The name `input.dwg` has been reused for other,
> smaller drawings (a 48416-byte sample; a separate 389-entity drawing; the native op was also
> smoked directly at 3 and 291706 entities). A truth-count gate MUST pin drawing identity
> (`source.sha256`/`byte_size`) alongside the number — that is what `source` exists for.

### 10.2 Section-by-section coverage (against the live artifact)

`diagnostics.coverage.section_status` carries the native collector's own honest per-section flags.
Realized state for the reference IR:

| IR section | native_full status | realized in the artifact |
|---|---|---|
| `entities[]` | **IMPLEMENTED** | 21747 entities, each with `handle/class/dxf_name/owner_handle/space/layer/bbox/geometry/source` |
| `symbol_tables.layers` | **IMPLEMENTED** | 70 layer records (`handle, name, color_index, frozen, off, locked, plottable, is_xref_dependent`) |
| `symbol_tables.linetypes` | **IMPLEMENTED** | 15 |
| `symbol_tables.text_styles` | **IMPLEMENTED** | 4 |
| `symbol_tables.dim_styles` | **IMPLEMENTED** | 4 |
| `symbol_tables.viewports` | **IMPLEMENTED** | 1 |
| `symbol_tables.app_ids` | **IMPLEMENTED** | 9 registered APPIDs |
| `symbol_tables.block_table_records` | **IMPLEMENTED** | 248 BTRs (`*Model_Space` carries `entity_count: 21747`) |
| `block_definitions[]` | **IMPLEMENTED** | 245 |
| `block_references[]` | **IMPLEMENTED** (projection) | 2027 — `ir_builder` projects every `INSERT` (`block_name, block_record_handle, insertion_point, scale, rotation`) |
| `layouts[]` | **IMPLEMENTED** | 3 (Model + 2 paper) |
| `xrefs[]` | **IMPLEMENTED** | 0 (this drawing binds no xrefs — a true zero, not skipped) |
| `dictionaries[]` | **IMPLEMENTED** | NOD + named dicts; `coverage.counts.dictionary_entries = 16` |
| `xrecords[]` | **PARTIAL** | 2 decoded; `section_status.xrecords = "partial"` (resbuf decode is best-effort) |
| `database.header_vars` | **IMPLEMENTED** (carried through) | native `database` object passed through verbatim |
| per-entity `xdata[]` | **PARTIAL → M03** | **0** entities carry `xdata` today; `section_status.xdata = "partial"`. The XDATA *write/read ops* (`write.xdata.set`/`inspect.xdata.get`) are wired, but per-entity XDATA is **not yet folded into the graph IR**. |
| per-entity `extension_dictionary_handle` | **PARTIAL → M03** | **0** entities carry it; `section_status.extension_dictionaries = "skipped"`. |
| 2D/3D polyline **vertex geometry** | **PARTIAL → M03** | **0** of 1874 `POLYLINE` entities carry `geometry.vertices`. The native `AcDbPolyline` (`LWPOLYLINE`) family emits vertices via `_geometry_from_native_entity`, but the legacy `AcDb2dPolyline`/`AcDb3dPolyline` vertex walk (separate `VERTEX` sub-entities) is **not yet collected** — `POLYLINE` entities currently carry `kind: "polyline"` with `decoded: true` but no vertex array. |
| `groups` / `materials` / `plot_settings` / `proxy_objects` | **SKIPPED / PARTIAL** | listed in `coverage.sections_skipped` (`extension_dictionaries, groups, materials, plot_settings`) and/or `section_status.proxy_objects = "partial"` — honest absence, never faked. |

`diagnostics.coverage.sections_present` for the artifact:
`["entities","database","symbol_tables","block_table_records","block_definitions","layouts","xrefs","dictionaries","xrecords"]`.
`diagnostics.coverage.sections_skipped`:
`["extension_dictionaries","groups","materials","plot_settings"]`.

### 10.3 The cp949 non-ASCII (Hangul) layer names — FIXED + VERIFIED

> **RETRACTION (load-bearing).** An earlier revision of this section claimed 68 of 70 layer names
> were "mojibake" / "upstream-corrupted at accoreconsole load time." **That diagnosis was WRONG and
> is retracted with evidence.** The non-ASCII (Korean / Hangul) layer names in the reference IR are
> **CORRECT** UTF-8. The thing that looked like corruption was a **cp949 CONSOLE-DISPLAY artifact**
> (piping the IR's UTF-8 Hangul through a cp949 Windows terminal renders garbage), **not** any
> corruption of the bytes on disk. The `wideToUtf8` / `acharToUtf8` native path is correct.

**Stated honestly, verified by code points.** 68 of 70 layer names in the reference IR carry real
Hangul (a character in U+AC00..U+D7A3). The proven-golden layer is
`X-평면도(기본형)$0$TEXT`, whose code points are exactly
`U+0058 U+002D U+D3C9 U+BA74 U+B3C4 U+0028 U+AE30 U+BCF8 U+D615 U+0029 U+0024 U+0030 U+0024`
(`X-평면도(기본형)$0$`) + `TEXT`. It classifies as `{HANGUL}` with **zero U+FFFD** replacement
characters. Block names inside `block_reference.block_name` carry the same correct Hangul.

What was proven, and how:

- **The UTF-8 conversion is fixed and verified.** Zero layer names contain the `?` ASCII-funnel
  character (the M01-era D3 `?`-funnel symptom is gone) **and** zero contain the U+FFFD replacement
  character — the total absence of U+FFFD is the hard proof that the cp949→Unicode decode lost
  nothing (a genuine decode failure would leave U+FFFD). Every layer name round-trips through UTF-8
  encode/decode as a lossless identity, i.e. the strings are fully-formed Unicode, not surrogate
  junk. The router/`ir_builder` JSON is emitted UTF-8 (`write_ir` uses `ensure_ascii=False`) and read
  back with `encoding="utf-8-sig"`.
- **The DWG format path is well-understood.** The source drawing is AC1032 with
  `$DWGCODEPAGE = ANSI_949` (cp949). accoreconsole/ObjectARX loads those code-page-encoded names into
  Unicode `ACHAR`, and the `WideCharToMultiByte(CP_UTF8)` (`wideToUtf8` / `acharToUtf8`) conversion in
  the native collector preserves them exactly. No re-decoding at the accoreconsole boundary is
  required; the names are already correct Hangul when they reach the IR.
- **Cross-engine corroboration (68 == 68).** The native ObjectARX (`acharToUtf8`) path and an
  **independent** LibreDWG → ezdxf(cp949) read produce **IDENTICAL** Hangul — the same 68 non-ASCII
  layer names, character-for-character (68 == 68, identical set). Two independent decode paths
  agreeing is the strongest evidence the result is the true source string, not a per-extractor
  artifact.
- **Consumer rule:** `handle` remains the portable join key (it always is), but joining on
  layer/block **name** is now safe for CJK drawings too — the names are correct Unicode. There is no
  outstanding non-ASCII corruption to work around; the prior "M03 re-decode" item is **closed as
  not-needed**.

This fidelity is locked by `tests/unit/test_non_ascii_fidelity.py`, which asserts (against the live
native_full IR, by code point — never by terminal rendering) that real Hangul is present, that no
layer name contains U+FFFD, that the specific golden layer `X-평면도(기본형)$0$TEXT` is present, and
that every layer name round-trips through UTF-8 losslessly.

### 10.4 Producer contract for native_full (`build_ir_from_database_graph`)

- Native `dxf_name` is the **runtime class name** (`AcDbLine`, `AcDb2dPolyline`, …);
  `_NATIVE_CLASS_TO_DXF_KIND` maps it back to the `(dxf_name, geometry.kind)` pair the schema wants.
  An unmapped class passes through as `class == native name`, `dxf_name == native name`,
  `geometry.kind == "unsupported"`, `source.decoded == false` — counted in
  `coverage.proxy_or_undecoded_count` (no-fake-success).
- `block_references[]` is a **convenience projection** of the INSERT entities, not an independent
  source of truth; every INSERT also appears in `entities[]` under the same `handle`.
- `database`, `symbol_tables`, `block_definitions`, `layouts`, `xrefs`, `dictionaries`, `xrecords`
  are carried through from the native result largely verbatim (the schema is additive), with
  `symbol_tables.layers` guaranteed present (possibly empty).
- The builder is **stdlib-only** and reads BOM-tolerant (`load_native_graph_result` uses
  `utf-8-sig`).
