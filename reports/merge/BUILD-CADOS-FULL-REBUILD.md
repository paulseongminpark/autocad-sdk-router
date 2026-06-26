# BUILD RECORD — CADOS FULL REBUILD

- **Generated at:** `2026-06-26T15:27:03.8700238+09:00`
- **Router root:** `D:/dev/99_tools/autocad-sdk-router`
- **HEAD commit:** `bc0832ab86bae410a89c8913294b5d7531e9f47b`
- **Scope:** CAD OS full native + managed rebuild from the **current working tree**, plus a READ-ONLY verification suite. No git mutation, no source edits.

---

## 1. Preflight — GO

| Gate | Result |
|------|--------|
| `go` | **true** |
| MSBuild | `C:/Program Files/Microsoft Visual Studio/2026/Community/MSBuild/Current/Bin/amd64/MSBuild.exe` |
| ObjectARX SDK | `C:/ObjectARX 2027` (FOUND) |
| AutoCAD running | **false** (canonical `.arx` not locked → no LNK1104, no `live_*.arx` bypass) |
| Source clean except m08l | **true** |

**Pre-build native artifacts (all match known baseline):**
crx=667136 @ 2026-06-23 20:37:27 (baseline 667136 @ 20:37 MATCH); arx=676352 @ 2026-06-23 20:37:31 (baseline 676352 @ 20:37 MATCH); dbx=48128 @ 2026-06-22 11:09:45 (baseline 48128 @ 2026-06-22 11:09 MATCH). The `.dbx` is located at `src/Ariadne.AcadNative/bin/x64/Release/Ariadne.AcadNativeDbx.dbx`; the sibling `src/Ariadne.AcadNativeDbx/bin/x64/Release/` has NO `.dbx` copy (expected).

**Notes (verbatim):**

GO=true. All gating inputs present.

STEP 1 MSBuild: FOUND at expected path C:/Program Files/Microsoft Visual Studio/2026/Community/MSBuild/Current/Bin/amd64/MSBuild.exe (no fallback search needed).

STEP 2 ObjectARX SDK: FOUND at C:/ObjectARX 2027.

STEP 3 AutoCAD: NOT running (Get-Process acad returned nothing). So the canonical Ariadne.AcadNative.arx is NOT locked -- the build can write the canonical .arx directly; no LNK1104 / no live_*.arx relink expected this run.

STEP 4 Source state (git diff -w --numstat -- src): EXACTLY ONE real (-w nonzero) content change, as required: src/Ariadne.AcadNative/families/m08l_handlers.inc shows '0\t173' (173 lines removed, 0 added) -- the intentional, correct removal of plot.config.settings + plot.engine.run handlers + AcPl includes (registry hard-blocked SAFETY_FORBIDDEN/HOST_UNAVAILABLE; AcPl* does not link headless). DO NOT revert. NO other src .inc/.cpp/.h shows any -w nonzero change. The remaining dirty src files are pure core.autocrlf LF->CRLF noise (git emitted 12 'LF will be replaced by CRLF' warnings for .vcxproj/.cpp/.h/.cs files, all 0\t0 under -w) -- ignored per instructions.

STEP 5 Pre-build native artifacts (all three EXACTLY match known baseline):
- Ariadne.AcadNative.crx: 667136 bytes @ 2026-06-23 20:37:27 (baseline 667136 @ 20:37) MATCH
- Ariadne.AcadNative.arx: 676352 bytes @ 2026-06-23 20:37:31 (baseline 676352 @ 20:37) MATCH
- Ariadne.AcadNativeDbx.dbx: 48128 bytes @ 2026-06-22 11:09:45 (baseline 48128 @ 2026-06-22 11:09) MATCH

The .dbx is in src/Ariadne.AcadNative/bin/x64/Release/ (the AcadNative Release dir), NOT in src/Ariadne.AcadNativeDbx/bin/x64/Release/ which has no .dbx -- this is the expected layout; the 'MISSING' line and the PS exit code 1 are just from probing the empty second location and are not a problem.

CAD router / code-review PreToolUse hook reminders are non-applicable: this task is read-only build-input inspection (Test-Path / Get-Item / git diff), no CAD file parse/extract/generate, no commit/PR. All operations were strictly READ-ONLY; no file edits, no git mutation.

---

## 2. Native build — OK

- **Status:** `ok`
- **dbx_exit:** 0 · **crx_exit:** 0
- **arx_mode:** `canonical` (AutoCAD not running → canonical `.arx` relinked normally; no LNK1104 lock, no versioned `live_*.arx` bypass)
- **newer_than_baseline:** true
- **Toolchain:** VS2026 MSBuild 18.6.3, Release x64, build chain `.dbx → .crx → .arx`, `$LASTEXITCODE=0`
- **Warnings:** benign LNK4099 only (missing `rxapi.pdb` from Autodesk-shipped `rxapi.lib`)

| Artifact | Bytes | Mtime |
|----------|------:|-------|
| Ariadne.AcadNativeDbx.dbx | 54272 | 2026-06-26 15:20:44 |
| Ariadne.AcadNative.crx | 756224 | 2026-06-26 15:20:48 |
| Ariadne.AcadNative.arx | 764416 | 2026-06-26 15:20:51 |

**Summary (verbatim):** CAD OS native rebuild from CURRENT WORKING TREE succeeded. The combined-TU .crx integration build (all m08*.inc in one translation unit — first full build of integrated HEAD) linked clean with no symbol collisions or headless-link failures. Build chain .dbx -> .crx -> .arx all Release x64 via VS2026 MSBuild 18.6.3, $LASTEXITCODE=0. arx_relink_mode="canonical" (AutoCAD not running, so the canonical .arx relinked normally — no LNK1104 lock, no versioned live_*.arx bypass needed). Only warnings were benign LNK4099 (missing rxapi.pdb from Autodesk-shipped rxapi.lib). All three artifacts freshly written 2026-06-26 15:20, after baselines (crx/arx baseline 2026-06-23 20:37, dbx 2026-06-22) -> newer_than_baseline=true. SIZE vs BASELINE (all GREW, consistent with the full integrated handler set): dbx 48128 -> 54272 (+6144 / +12.8%); crx 667136 -> 756224 (+89088 / +13.4%); arx 676352 -> 764416 (+88064 / +13.0%). The working-tree m08l_handlers.inc (plot handlers removed) was built as-is; no source edited, no git ops. No failure to report.

---

## 3. Native artifact — pre vs post

Pre = baseline before this rebuild; Post = live on disk, re-stat confirmed at `2026-06-26T15:27` (sizes/mtimes identical to the build output above).

| Artifact | Pre bytes | Pre mtime | Post bytes | Post mtime | Δ bytes | Δ % |
|----------|----------:|-----------|-----------:|------------|--------:|----:|
| Ariadne.AcadNativeDbx.dbx | 48128 | 2026-06-22 11:09:45 | 54272 | 2026-06-26 15:20:44 | +6144 | +12.8% |
| Ariadne.AcadNative.crx | 667136 | 2026-06-23 20:37:27 | 756224 | 2026-06-26 15:20:48 | +89088 | +13.4% |
| Ariadne.AcadNative.arx | 676352 | 2026-06-23 20:37:31 | 764416 | 2026-06-26 15:20:51 | +88064 | +13.0% |

Path: all three at `src/Ariadne.AcadNative/bin/x64/Release/`. All artifacts grew, consistent with the full integrated handler set.

---

## 4. Managed build — OK

- **Status:** `ok` · **exit:** 0

**Detail (verbatim):** Build succeeded. dotnet 10.0.300 found at C:\Program Files\dotnet\dotnet.exe. Ran: dotnet build "D:/dev/99_tools/autocad-sdk-router/src/Ariadne.DwgGeometryExtractor/Ariadne.DwgGeometryExtractor.csproj" -c Release. Result: 0 errors ("오류 0개"), 3 warnings ("경고 3개"), elapsed 00:00:02.15. The 3 warnings are all MSB3277 reference-version conflicts (Microsoft.VisualBasic 10.0.0.0 vs 10.1.0.0, plus AutoCAD 2027 interop DLLs like AdWindows.dll/AcWindows.dll resolved against acmgd) — non-fatal, build still completed. Note: Korean console output appeared as cp949 mojibake but the underlying data is intact (verified via UTF-8 grep of the persisted log: "빌드했습니다." + "오류 0개"). No source edited, no git commit. Output DLL: D:\dev\99_tools\autocad-sdk-router\src\Ariadne.DwgGeometryExtractor\bin\Release\net10.0-windows\Ariadne.DwgGeometryExtractor.dll

---

## 5. Verification (READ-ONLY)

### 5.1 pytest — PASS
Ran from D:/dev/99_tools/autocad-sdk-router: C:/Users/PAUL/AppData/Local/Programs/Python/Python312/python.exe -m pytest tests -q

Final summary line: "504 passed, 3 skipped in 48.74s"
Exit code: 0 (verified via a second run, EXIT_CODE=0)

Matches the expected "504 passed, 3 skipped", exit 0. No failures. The 3 skipped tests are expected/pre-existing skips. READ-ONLY verification only; no files modified.

### 5.2 closure — PASS
Registry closure intact (READ-ONLY, no writes). Parsed D:/dev/99_tools/autocad-sdk-router/config/operations.v2.json with utf-8-sig; "operations" array has 517 records. PER-RECORD status counts: implemented=457, blocked=60, catalogued=0, stub=0, unknown=0, deprecated=0 -> sum(catalogued+stub+unknown+deprecated)=0 so per-record closure_gate=True. Embedded totals.by_status agrees exactly: {implemented:457, blocked:60}. closure_gate_latest.json reports: catalogued=0, stub=0, unknown=0, deprecated=0, closure_gate_pass=true, m09_allowed=true (also m09_blocked_until_m08r=true, all six checks true: every_op_has_owner_ticket, every_open_op_has_strategy_and_evidence, zero_catalogued, zero_stub, zero_unknown, v1_target_escape_banned). All three sources (per-record scan, embedded totals, gate report) converge. Expected vs actual: implemented 457==457, blocked 60==60, closure buckets 0==0. PASS.

### 5.3 native_smoke — PASS (golden 21747)
Freshly-built native .crx loads headless and returns valid JSON with GOLDEN MATCH 21747. Binary freshness: Ariadne.AcadNative.crx built 2026-06-26 15:20:48 (D:\dev\99_tools\autocad-sdk-router\src\Ariadne.AcadNative\bin\x64\Release\), smoke run ~3 min later — genuinely the new binary.

PROOF LAYER 1 (documented headless pytest, router native path): set CADOS_LIVE=1; ran `python -m pytest tests/smoke/test_router_inspect_database_graph.py -v -rs` -> 5 passed in 19.46s. The env-gated live test TestInspectDatabaseGraphLive::test_native_inspect_rich_is_consistent_and_safe shows PASSED (NOT skipped; -rs reported zero skip reasons). That test only passes if cadctl.inspect routes through accoreconsole loading the fresh .crx and the native_full IR equals 21747.

PROOF LAYER 2 (direct cadctl.inspect, real envelope captured to rule out a truthful-but-degraded status): drove cadctl.Cad().inspect(golden, out_dir, mode="graph", include_rich=True). Result: ENVELOPE_STATUS='ok' (not partial/unavailable), ENVELOPE_ENTITY_COUNT=21747, IR schema=ariadne.dwg_graph_ir.v1, IR coverage_level='native_full', IR diagnostics.entity_count=21747, len(entities)=21747. Golden 21747 matched THREE ways (envelope == IR diag == len). Truth gate (diag==len) True. Elapsed 14.5s (real accoreconsole launch). IR written to runs\native_smoke_freshcrx_62220\dwg_graph_ir.json.

PROOF LAYER 3 (AutoLISP-level load via documented diag_crx_after_build.scr, independent of the Python harness): drove accoreconsole with the diag .scr against a blank staging DWG -> CRXLOAD_OK (no CRXLOAD_ERROR) for Ariadne.AcadNative.crx, DBXLOAD_OK for its .dbx, and both 'ariadne.acadnative.crx' + 'ariadne.acadnativedbx.dbx' resident in the live (arx) module list.

ORIGINAL-SAFETY (no-fake / READ-ONLY contract honored): all work on staging copies (staging\golden\20260626_152544_448\input.dwg + test_native\blank.dwg). Original fixture/golden input.dwg sha256 AND byte-size verified UNCHANGED before/after. No ad-hoc parsing — every CAD byte came through the router's native ObjectARX/.crx path.

accoreconsole 2027 present at C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe. Note: the task-named tests/integration/test_native_inspect_database_graph.py asserts internal consistency + original-unchanged but does NOT pin 21747; the smoke test (tests/smoke/test_router_inspect_database_graph.py, _GOLDEN_TOTAL=21747) is the one that pins the golden count, so I exercised that plus a direct-drive capture for the explicit numeric proof.

---

## 6. FOLLOW-UP — commit the working-tree m08l change

**File:** `src/Ariadne.AcadNative/families/m08l_handlers.inc`

The working-tree `m08l_handlers.inc` removed the `plot.config.settings` + `plot.engine.run` handlers (and the `AcPl*` includes) — `0 added / 173 removed`. Those plot ops are **registry hard-blocked** (SAFETY_FORBIDDEN / HOST_UNAVAILABLE) and `AcPl*` does not link headless, so the removal is the intentional, correct change.

This change was **BUILT** into the deployed native artifacts (crx 756224 / arx 764416 / dbx 54272 @ 2026-06-26 15:20) but is **still UNCOMMITTED**. HEAD is currently `bc0832ab86bae410a89c8913294b5d7531e9f47b`, which does **not** correspond to the binary on disk.

> **It SHOULD be committed so HEAD matches the deployed binary.** This build record performs NO git mutation by instruction; the commit is a deliberate follow-up step.
