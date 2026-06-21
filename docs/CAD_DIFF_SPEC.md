# CAD_DIFF_SPEC — structural diff between two DWG-graph IRs

`tools/cad_diff.py` computes a **deterministic, engine-neutral** difference
between a *before* and an *after* `ariadne.dwg_graph_ir.v1` document and emits an
`ariadne.cad_diff.v1` report (`schemas/cad_diff.v1.schema.json`). It is the
measurement layer for a staged CAD mutation: feed it the IR extracted *before* a
patch and the IR extracted *after*, and it tells you exactly which entities were
added, removed, or modified — and how.

Standard-library only (Python 3.12). The diff body contains no timestamps and no
randomness; the same pair of IRs always produces byte-identical output.

## Join key

Entities are joined on their **DWG `handle`** — the IR's stable, cross-engine
key (uppercase hex, e.g. `"11935"`). The handle is unique within a drawing's
lifetime and is the same regardless of which engine (ObjectARX / ObjectDBX /
AutoLISP / DXF) produced the IR, so the diff never depends on the producing
engine or on positional matching.

| Membership                         | Change kind |
|------------------------------------|-------------|
| handle in `after` only             | `added`     |
| handle in `before` only            | `removed`   |
| handle in both, ≥1 field changed   | `modified`  |
| handle in both, no field changed   | *unchanged* (counted, not listed) |

The comparison is exact: `diagnostics.comparison_basis == "handle"`. The module
**does not** fall back to geometry/positional matching when handles do not line
up. A drawing whose engine reissued handles is reported truthfully as wholesale
`added` + `removed` rather than faking a positional match (no-fake-success).

Entities with a **missing or empty handle cannot be joined**; they are counted in
`diagnostics.unjoinable_before` / `unjoinable_after` and described in
`diagnostics.warnings`, never silently dropped or guessed.

## Change taxonomy (`classify_change(pre_entity, post_entity) -> list[str]`)

For a handle present in both IRs, these fields are compared and the **sorted set
of changed field names** is returned (empty list = unchanged):

| Field        | Compare         | Notes |
|--------------|-----------------|-------|
| `layer`      | scalar string   | entity moved to a different layer |
| `dxf_name`   | scalar string   | DXF/runtime type changed |
| `bbox`       | structural      | axis-aligned box `[minX,minY,minZ,maxX,maxY,maxZ]` (or `[]`) changed |
| `geometry`   | structural      | geometry payload changed; the specific changed leaves are also returned as `geometry.<key>` (e.g. `geometry.start`, `geometry.end`) |

Structural compares use a canonical form (`_canonical`): dicts are compared by
**sorted keys** and lists element-wise, so two structurally-equal geometries
compare equal regardless of key insertion order. Numbers are compared exactly
(no rounding); a caller needing tolerance can pre-round the IR.

A geometry change yields both the umbrella `"geometry"` token and the localized
`"geometry.<key>"` tokens, so a consumer sees e.g. `["geometry", "geometry.end"]`.

## Output shape (`compute_diff(pre_ir, post_ir) -> dict`)

Conforms `ariadne.cad_diff.v1`. Top-level keys:

| Key               | Meaning |
|-------------------|---------|
| `schema`          | `"ariadne.cad_diff.v1"` |
| `diff_id`         | `diff-<sha256[:16]>` of both IRs' sorted handle→signature — **content-derived, not time-derived** (re-diffing the same pair gives the same id) |
| `before_ref` / `after_ref` | `state_ref` `{kind:"ir", ref, entity_count, sha256?}`; `ref` is the IR's staged `dwg_path` (then `dwg_name`, then `original_path`) |
| `changed_handles` | per-handle change records (see below), sorted by change-kind (`added`,`removed`,`modified`) then handle |
| `summary`         | roll-up (see below) |
| `diagnostics`     | `{comparison_basis:"handle", warnings, errors, unjoinable_before, unjoinable_after, pre/post_coverage_level}` |
| `layer_changes`   | projection: `[{handle, dxf_name, before, after}]` for layer-changed entities |
| `geometry_changes`| projection: `[{handle, dxf_name, changed_keys:[geometry.*]}]` |
| `bbox_changes`    | projection: `[{handle, dxf_name, before, after}]` |

`layer_changes` / `geometry_changes` / `bbox_changes` are extension fields,
permitted by the schema's `additionalProperties: true`.

### `changed_handles[]` record

```jsonc
// added / removed
{ "handle": "ZZZZZ1", "change": "added",   "dxf_name": "CIRCLE", "layer": "NEW" }
// modified — carries field-level deltas
{
  "handle": "11936", "change": "modified", "dxf_name": "LINE", "layer": "DEMO_MOVED",
  "fields": [
    { "field": "layer", "before": "0", "after": "DEMO_MOVED" },
    { "field": "geometry", "before": {…}, "after": {…}, "changed_subfields": ["geometry.end"] },
    { "field": "bbox", "before": [...], "after": [...] }
  ]
}
```

`fields[]` carries one entry per changed **top-level** field with the actual
`before`/`after` values; the localized `geometry.<key>` tokens are echoed under
`changed_subfields` of the `geometry` entry (not duplicated as their own rows).

### `summary`

Carries both the **frozen schema names** and the **CAD OS Layer M02 `created`/
`deleted` aliases** so either vocabulary works:

```jsonc
{
  "added": 1, "removed": 1, "modified": 1, "unchanged": 21745,   // frozen schema
  "entity_count_before": 21747, "entity_count_after": 21747,
  "by_type": { "LINE": {"added":0,"removed":0,"modified":1},
               "CIRCLE": {"added":1,"removed":0,"modified":0} },
  "created_count": 1, "deleted_count": 1,                         // M02 aliases
  "modified_count": 1, "unchanged_count": 21745
}
```

`by_type` is the per-DXF-type net change (added/removed/modified counts keyed by
`dxf_name`).

## Determinism

- Handles are **sorted** before emission; `changed_handles` is re-sorted by
  `(change-kind, handle)`.
- `diff_id` is a SHA-256 of the inputs' canonical signature — **no clock, no UUID**.
- `_canonical` makes dict/list compares order-independent.
- **No timestamp** appears anywhere in the diff body.

Verified: `json.dumps(compute_diff(a,b)) == json.dumps(compute_diff(a,b))`.

## Example

`make_fixture_ir()` (3 entities: LINE `2A7`, CIRCLE `2A8`, INSERT `2A9`) vs a
copy where the LINE's layer is `0 → DEMO_MOVED` and its `geometry.end` shifts,
plus a new CIRCLE `2FF`:

```
summary added/removed/modified/unchanged : 1/0/1/2
by_type : {"CIRCLE":{"added":1,"modified":0,"removed":0},
           "LINE":{"added":0,"modified":1,"removed":0}}
changed_handles:
  2FF  added
  2A7  modified  fields=[bbox, geometry(+geometry.end), layer]
layer_changes    : [{handle:2A7, before:"0", after:"DEMO_MOVED"}]
geometry_changes : [{handle:2A7, changed_keys:["geometry.end"]}]
```

## Public API

| Symbol | Purpose |
|--------|---------|
| `compute_diff(pre_ir, post_ir) -> dict` | the diff (cad_diff.v1) |
| `classify_change(pre_entity, post_entity) -> list[str]` | sorted changed field names |
| `index_entities_by_handle(ir) -> (by_handle, problems)` | join index + unjoinable report |
| `load_ir(path) -> dict` | BOM-tolerant IR load (`utf-8-sig`) |
| `load_diff(path)` / `write_diff(diff, path)` | diff round-trip (write is plain UTF-8) |
| `DIFF_SCHEMA_ID` | `"ariadne.cad_diff.v1"` |

## Invariants honored

- **Read-only**: consumes IR JSON only; never reads, writes, or mutates a DWG.
  (The original golden DWG is never opened by this module — IR extraction is the
  router's job upstream.)
- **No-fake-success**: unjoinable (handle-less) entities are surfaced, not
  matched; if the sibling `ir_builder` is absent the `__main__` self-demo returns
  `NOT_IMPLEMENTED` (exit 2) rather than a fake pass.
- **Stdlib only**, deterministic, schema-conformant (validated against
  `cad_diff.v1` with `jsonschema`).
- **Truthful sibling degradation**: `ir_builder` is imported via
  `_import_optional`; the public diff API works with or without it.

## Self-check

`python tools/cad_diff.py` builds a fixture pair, asserts the added entity shows
as `added`, the layer+geometry change shows as `modified` (with `geometry.end`
localized), identical IRs diff to all-unchanged, and the result is deterministic.
Cross-checked against the **live native_full IR** (`runs/m02_cadctl_rich/
dwg_graph_ir.json`, 21747 entities): self-diff = 0 added / 0 removed / 0 modified
/ 21747 unchanged / 0 unjoinable; a perturbed copy = exactly 1/1/1 with correct
field deltas and projections.
