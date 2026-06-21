# CADOS_M02_V1_COMPLETION_ULTRACODE — Result Report

**STATUS: PARTIAL_PASS** (12/15 acceptance criteria full PASS; 3 honest host-dependent partials — no fake success)
**Previous:** CADOS_M01 (`e18edde`). **Version:** cad_os_layer_v0.2.0. **Push:** none.

## What landed (live-verified, inline)

1. **Native rich DWG Graph IR** — extended the ObjectARX `inspect.database.graph` op with `collectDatabaseGraph` (symbol tables incl. rich layers, block table records + block definitions, layouts, xrefs, named-object dictionary + xrecords, database meta), plus INSERT scale/rotation/block-record-handle. `.crx` rebuilt (190464 B). **Truth gate: 21747 == 21747** on the golden, by-type matches exactly.
2. **Router-wired** (`D2` resolved) — added `inspect.database.graph` + `inspect.database.summary` to `Test-NativeP1CadJobOperation`; the op routes through the existing native `.dbx`/`.crx` cad-job lane. Verified via `cadctl inspect --include-rich`, not direct `.scr` only.
3. **UTF-8 fidelity fix** (`D3` code-fixed) — `wideToUtf8`/`acharToUtf8` (`WideCharToMultiByte(CP_UTF8)`); ASCII byte-identical, non-ASCII lossless. **Honest finding:** native ARX *and* managed extractor produce **identical** cp949 mojibake → the residual is **upstream accoreconsole load-time code-page decode**, cross-engine confirmed — this **disproves M01's claim** that `geometry_native` preserved bytes. (PARTIAL, M03 path documented.)
4. **`ir_builder.build_ir_from_database_graph`** — native rich result → `coverage_level=native_full` IR; **jsonschema-valid**; real DXF type names; geometry lifted; block_references projection.
5. **cadctl read surface** — `inspect --include-rich` (native_full), `query` (sqlite, count 21747), `validate`, `registry list|coverage|explain`. Live-proven end-to-end.
6. **Patch vertical slice (marquee)** — `patch_engine.apply_staged`: stage copy → pre-inspect → native `write.entity.line` (write_copy) → post-inspect → `cad_diff.compute_diff` → validator → journal. **Live: +1 LINE (21747→21748), 14/14 validation gates pass, original DWG byte-unchanged** (`runs/m02_patch_live2`).
7. **Validator** — 14 deterministic gates (IR schema/count, cad_diff schema, diff-expected-changes, no-unrelated-changes, patch-policy, staged-copy-used, journal-present, original-dwg-unchanged, no-fake-success...). Made patch-aware where inspect-oriented gates misfired (integration seam fixed inline).
8. **`.arx` versioned relink** (`D1` resolved) — `Ariadne.AcadNative.live_m02.arx` (190976 B) relinks with the rich-IR code; `build_native_acad.ps1` now auto-falls-back to a versioned target on lock; AutoCAD never killed.
9. **Operation Registry v2** — 43 ops, `{implemented:34, stub:7, blocked:2}`, fully consistent; `inspect.database.graph`/`query.entities`/`patch.apply_staged` implemented with evidence refs.
10. **Tests** — pytest **215 passed / 2 skipped**, unittest **180 OK / 2 skipped** (live/integration env-gated, skip with reason).

## Workflow orchestration (ultracode)

Keystone (native C++ + router + ir_builder + cadctl rich read) built + live-verified **inline** (can't delegate a live msbuild+accoreconsole loop). The breadth (cad_diff, patch_engine, validator, sqlite rich, mcp, visual, registry, docs + the full test suite) fanned out across a **9-agent workflow** (all Opus), contract-pinned to the real `native_full` IR; then integrated + adversarially verified + the cross-lane validation seam fixed inline.

## Honest partials (no fake)

- **crit 5 non-ASCII** — upstream accoreconsole cp949 decode (hard external; cross-engine confirmed). M03: DXF/ezdxf name cross-source.
- **crit 9 visual** — Core Console cannot render DWG→PDF/PNG on this host → `build_visual_report` returns `NOT_IMPLEMENTED` with evidence (no fake artifact). Full visual PASS needs a real render (M03).
- **crit 10 live ARX pump** — design + versioned `.arx`; runtime blocked (cannot safely load into attended `acad.exe` PID 49460). Exact blocker + M03 next-command recorded.

## Evidence

`reports/{v1_acceptance_latest,operation_coverage_latest,patch_diff_latest,validation_latest,visual_verification_latest,rich_ir_latest,walking_skeleton_latest,native_graph_smoke_latest,live_pump_latest}.{json,md}`; live runs `runs/m02_cadctl_rich/`, `runs/m02_patch_live2/`.

## Next

**D04_IMPORT_CAD_OS_CAPABILITIES** (recommended — the read+patch+registry stack is ready for Daedalus consumption) **or** **CADOS_M03_NATIVE_IR_COMPLETION** (rich-IR depth + non-ASCII + visual + live pump).
