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

## 구현 노트

- 실제 landed 구현은 작업 지시에 맞춰 `src/Ariadne.AcadNative/families/m08e_handlers.inc` 안에서
  append 대상 BTR로 직접 빌드/append 하는 B1a 형태로 추가했다.
- 미러링 기준 modelspace handler:
  `src/Ariadne.AcadNative/families/m08g_handlers.inc`
  `write.entity.ellipse`, `write.entity.point`, `write.entity.spline`,
  `write.entity.polyline`(LWPOLYLINE), `write.entity.polyline3d`,
  `write.entity.polyline2d.deep`, `write.entity.blockref`.
- `block_reference`는 modelspace `write.entity.blockref`와 같은 block-table lookup을 사용하고,
  참조 대상 이름이 없으면 `BLOCK_NOT_FOUND`로 loud-fail 한다. silent skip은 없다.
- 제약:
  현재 Python append payload(`tools/patch_ops/blocks.py::_def_entity_append_op`)는 spline의
  `control_points`는 보내지만 knot/weight 배열은 보내지 않는다. 그래서 native append는
  knot vector가 같이 온 경우에만 control-point NURBS 경로를 쓰고, 그 외에는
  `write.entity.spline`과 같은 fit-point 경로를 사용한다. 즉 `control_points` 단독 payload는
  정보성 입력으로만 남고 직접적인 NURBS basis 재구성에는 쓰지 못한다.
