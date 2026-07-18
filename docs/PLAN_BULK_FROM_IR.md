# PLAN: `write.database.from_ir` — native bulk full-drawing regeneration (Plan C)

Status: **design + setup** (stub at `src/Ariadne.AcadNative/families/m08i_bulk_from_ir.inc.draft`,
NOT in the build). Prereqs landed: batch write lane (#39), sortents gap filed (#38).

## Why

`ir_to_patch.py` already converts a full `dwg_graph_ir.json` into per-entity write
ops ("perfect DWG roundtrip"), and #39's batch lane makes patch-scale application
real (one accoreconsole session per batch). But full regeneration of a large
drawing is a different regime:

| lane | processes | 1.9M-entity estimate |
|---|---|---|
| per-op (`apply_staged` legacy) | 1/op | ~220 days (unusable) |
| batched (#39, 1000 ops/batch) | ~1,900 | ~8–10 h |
| **native bulk (`write.database.from_ir`)** | **1** | **~20–40 min** (extractor-reverse symmetry) |
| ezdxf DXF + SAVEAS (current workaround) | 1 | ~15 min, but with fidelity approximations |

The ezdxf workaround loses/approximates: real MLINE (drawn as polyline), dimension
regeneration, draw order (needs external sortents dump), per-insert ATTRIBs
(fixed in builder v4 but still DXF-mediated), WIPEOUT frame semantics. A native
bulk op removes the whole DXF round trip.

## Op contract (proposed)

```json
{
  "schema": "ariadne.autocad_sdk_job.v2",
  "operation": "write.database.from_ir",
  "write_mode": "write_copy",
  "args": {
    "ir_path": "<dwg_graph_ir.json>",
    "sortents": "honor",          // honor | skip  (#38: IR must carry sortents)
    "attributes": true,             // INSERT attributes[] -> AcDbAttribute
    "wipeouts": true,               // AcDbWipeout builder (already native, f4603fe)
    "start_entity": 0,              // resume offset (journal-driven)
    "progress_every": 10000         // progress lines to stdout for the router
  }
}
```

Target database = the staged DWG accoreconsole opened (`/i staged.dwg`), same
in-place + `_QSAVE` contract as the #39 write-batch lane. The op is registered
like every ARIADNE_NATIVE_JOB op (registry rows in `config/operations.v2.json`,
`autocad_native_arx_operation_catalog.json`, `op_dag.json`), dispatcher family
`m08i`.

## Foundations already in the tree (verified 2026-07-18)

- `inspect.database.dxf_in` / `transform.database.save_as` / `acdb.database.create`
  — native AcDbDatabase lifecycle ops (m08c/m08e dispatch) prove the plumbing.
- `families/m08g_handlers.inc` / `m08h_handlers.inc` — 26 entity-kind native
  write handlers whose arg-building logic (`tools/patch_ops/`) the bulk op
  reuses **in-process** (same JSON arg shapes, no per-op job files).
- native AcDbWipeout builder (commit `f4603fe`).
- `tools/ir_builder.py` kind mapping (`_NATIVE_CLASS_TO_DXF_KIND`) — the
  authoritative IR-kind ↔ native-class table to invert.
- #39 batch lane — the fallback/partial-failure story and the `_QSAVE` +
  marker + timeout-kill lifetime guard to copy.

## Implementation checklist

1. **Extractor side (#38 first):** emit per-BTR `ACAD_SORTENTS` as
   `sortents: [{entity_handle, sort_handle}]` in `inspect.database.graph`
   (AcDbSortentsTable via the BTR extension dictionary). `ir_builder.py`
   passes it through (whitelist!).
2. **Streaming reader:** the Jukjeon IR is 3.1 GB — the job-args DOM parser
   must NOT be used. Add a SAX/pull JSON pass over `entities[]` /
   `block_definitions[]` (rapidjson SAX or a minimal hand-rolled tokenizer;
   the extractor already streams the other direction).
3. **Entity factory:** one `switch(kind)` reusing the m08g/h creation code
   paths (factor the per-kind `AcDbEntity*` builders out of the job handlers
   so job-lane and bulk-lane share them).
4. **Order:** create block defs first (two passes: defs, then def entities,
   then model space in IR order); apply sortents last by writing an
   `AcDbSortentsTable` on the model-space BTR (`setRelativeDrawOrder`), which
   is MORE faithful than the builder-v4 workaround (DB-order bake).
5. **Attributes / wipeouts / xclip:** reuse `appendAttribute`,
   `AcDbWipeout`, `AcDbSpatialFilter` code already present in the module.
6. **Progress + resume:** write `progress.jsonl` (`{done, total, at}`) so the
   router can report; `start_entity` lets a killed run resume after the last
   `_QSAVE` checkpoint (QSAVE every N entities, N≈100k).
7. **Registry + gates:** add rows with `status: "implemented"` ONLY when the
   handler is real (no-fake-success); until then keep this doc + the
   `.inc.draft` out of the build. `assert_native_write_op_map_lockstep` is
   unaffected (this is not a patch op).
8. **Verification:** re-run the Jukjeon pipeline end-to-end and compare with
   builder-v4 output: 64-tile ssget counts, SORTENTS presence, WIPEOUT/ATTRIB
   counts, text-inventory diff (probe scripts from the 2026-07-18 session).

## Non-goals

- Layout/paper-space regeneration (IR is model-space-scoped today, #25 scope).
- Xref re-binding (IR flattens `XR-*$0$` names; keep as flattened blocks).
