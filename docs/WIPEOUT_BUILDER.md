# Wipeout Builder

`write.block.append_entity` supports `entity.kind="wipeout"` through the native
`AcDbWipeout` path in `src/Ariadne.AcadNative/families/m08e_handlers.inc`.

## Recipe

1. Force-load `acismobj26.dbx` once with `acrxDynamicLinker->loadModule`.
   If the load fails, emit `WIPEOUT_MODULE_UNAVAILABLE`; do not rely on
   demand-loading.
2. Ensure `ACAD_IMAGE_DICT` exists via
   `AcDbRasterImageDef::imageDictionary/createImageDictionary`.
3. Reuse `ARIADNE_WIPEOUT_DEF` if present. Otherwise store a fileless
   placeholder `AcDbRasterImageDef` in the image dictionary with `setAt`.
   The certified plain wipeout path reports a 1x1 image size from the engine.
4. Create `AcDbWipeout`, call `setDatabaseDefaults`, then
   `setImageDefId(defId)`.
5. Apply `setOrientation(origin, u_vector, v_vector)` from the IR.
6. Apply `setClipBoundary(clip_boundary_type, clip_boundary)` with IR pixel
   points unchanged, except that an open boundary is closed by repeating the
   first point.
7. Append into the target `AcDbBlockTableRecord` exactly like the other
   `write.block.append_entity` kinds. If `appendAcDbEntity` returns
   `eInvalidInput` or `eNoClassId`, emit `WIPEOUT_BTR_APPEND_UNPROVEN`.

## Traps

- `acismobj26.dbx` must be loaded before image definitions or wipeouts are
  created; otherwise `setAt` or append can return `eNoClassId`.
- `AcDbWipeout::createImageDefinition()` is not enough. The wipeout must point
  at a database-resident image definition through `setImageDefId`.
- Open polygon clip boundaries are rejected with `eInvalidInput`; repeat the
  first point when the last point differs.
- Appending a wipeout into a named BTR is not certified yet. The builder tries
  the same BTR append used by other kinds, but it fails loudly for the known
  unproven statuses and never falls back to modelspace.
- `frame_on` is read from existing wipeouts, but there is no public per-entity
  setter available here. The builder preserves the default and does not invent
  a substitute.

## Live Certification Plan

Run a single-operation live probe for `write.block.append_entity` with a
`wipeout` payload against a staged DWG. Confirm that the new entity is present
in the target block record and that its orientation, clip boundary, image
definition, and handle survive post-inspection. Only after that live cert
passes should the orchestrator flip Python emission in `tools/patch_ops/blocks.py`.
