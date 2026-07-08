# Append Kind Extension Design

## Goal

Extend `write.block.append_entity` beyond `{line,circle,arc,text}` for the deferred
block-definition kinds that already have modelspace create handlers:
`spline`, `lwpolyline`, `ellipse`, `point`, `polyline`, and `block_reference`.

The orchestrator compiles the CRX after merge with `tools/build_native_acad.ps1`.
This task does not build locally.

## Design Options

### B1a: Extend `m08eBuildEntityForAppend` with shared per-kind builders

Score:

- Geometry parity risk: 4/10
- Native code size: 6/10
- Ownership / DB pitfalls: 8/10
- Extensibility to hatch later: 5/10

Notes:

- Best-case parity is good only if `m08e` and the modelspace create path can truly share
  one geometry builder.
- Under this task's file limits, the certified create logic lives in `m08g_handlers.inc`
  and cannot be refactored in-place, so B1a trends toward copy-paste drift.
- Ownership is simple because entities are appended directly into the target block.

### B1b: Reuse the existing modelspace create ops, then clone into the target block

Score:

- Geometry parity risk: 8/10
- Native code size: 7/10
- Ownership / DB pitfalls: 5/10
- Extensibility to hatch later: 8/10

Notes:

- Geometry is produced by the already certified `write.entity.*` handlers, so there is no
  duplicate per-kind construction logic in `m08e`.
- The main risk is ownership cleanup: create in modelspace, clone into the target BTR, then
  erase the temporary source entity.
- This scales to future appendable kinds with only one new mapping layer as long as a
  certified modelspace creator already exists.

## Decision

Choose **B1b**.

Reason:

- It is the only option that avoids copy-paste geometry drift within the allowed file scope.
- It reuses the exact certified modelspace create code path already trusted by the 375/375
  roundtrip evidence.
- The ownership work is contained and mechanical compared with maintaining duplicate
  entity-construction branches over time.

## Backtrack Trigger

Switch to B1a if native testing after merge shows that the create-then-clone path cannot
reliably preserve block ownership semantics for nested `block_reference` entities, or if a
kind that must remain geometry-identical proves impossible to express through the certified
modelspace creator.
