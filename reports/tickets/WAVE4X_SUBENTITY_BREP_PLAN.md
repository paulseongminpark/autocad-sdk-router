# WAVE4X SUBENTITY BREP PLAN

## Scope
Claim file: `reports/tickets/WAVE4X_PANE3_SUBENTITY_BREP_CLAIMS.json`

Claimed ops:
- `edit.subentity.add_paths`
- `edit.subentity.delete_paths`
- `edit.subentity.transform`
- `inspect.assocsurface.topology`

## Goal
Reopen the four claimed hard-blocks only where the SDK already exposes a bounded, testable route.
End state per op must be `implemented` or `hard_blocked` with real evidence.

## Reopen decision
- `inspect.assocsurface.topology` looks feasible as a **read-only** handler via
  `AcDbAssocSurfaceActionBody::{findActionsThatAffectedTopologicalSubentity,`
  `getTopologicalSubentitiesForActionsOnEntity, getSurfacesDirectlyDependentOnObject}`.
- `edit.subentity.*` looks feasible as **staged-write only** if the contract is narrowed to explicit
  `AcDbFullSubentPath` specs supplied by the caller. No editor picks, no raw commands, no original DWG writes.
- Existing safe subset already present and will be reused, not re-claimed:
  `inspect.subentity.color`, `inspect.subentity.markers_at_path`, `inspect.subentity.path_at_marker`.

## Implementation plan
1. **M08G staged subentity helpers + writes**
   - add `AcDbFullSubentPath` parsing helpers for explicit path specs
   - support one-path and `paths[]` forms
   - implement:
     - `edit.subentity.add_paths`
     - `edit.subentity.delete_paths`
     - `edit.subentity.transform`
   - bounded contract:
     - staged copy only (`write_copy`)
     - explicit handle + subentity type/index
     - optional insert-stack handles
     - transform uses existing matrix builder (`translate` / `rotate` / `scale` / `pivot`)
   - runtime payload will emit before/after readback fields where available (`subentPtr`, markers, extents, status codes)

2. **M08KC assoc-surface topology read**
   - include `AcDbAssocSurfaceActionBody.h`
   - add read-only helper serialization for `AcDbSubentId`
   - implement `inspect.assocsurface.topology`
   - result shape:
     - optional `findActionsThatAffectedTopologicalSubentity`
     - `getTopologicalSubentitiesForActionsOnEntity`
     - `getSurfacesDirectlyDependentOnObject`
     - exact status codes + handle arrays + per-action subentity lists

3. **Registry + tests**
   - flip the 4 claimed ops to `implemented`
   - update write/read policy blocks and evidence refs
   - update Wave3 re-audit tests that still expect these ops to remain blocked
   - add/extend source-level tests for real API presence and exact HasOp budgets

4. **Validation**
   - `python -m pytest tests -q`
   - `python tools/cadctl_cli.py registry coverage`
   - `python tools/reconcile_native_registry.py`
   - isolated native build because C++ source changes

## Success criteria
- all 4 claimed ops closed in registry with no `catalogued/stub/unknown/deferred`
- source compiles in isolated native build
- pytest green
- report + ops summary + patch + zip produced
