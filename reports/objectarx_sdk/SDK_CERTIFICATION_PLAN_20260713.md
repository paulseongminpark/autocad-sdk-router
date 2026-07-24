# ObjectARX SDK Full-Coverage Certification — Execution Plan

**Owner:** aclaude · **Mandate:** Paul ultracode 2026-07-13 ("실제 제공하는 모든 기능 빌드 + 정합성 검증 + GitHub. 미연결된 것도. 찾은 문제 다 해결").
**Advisory basis:** codex gpt-5.6-sol xhigh (`CODEX_SOL_ADVICE_20260713.md`), verified.
**SoT for this arc.** Supersedes ad-hoc framing in `PHASE0_DOSSIER_20260713.md`.

## Corrected truth model (P0 — DONE, see `P0_TRUTH_MODEL_REPAIR_20260713.md`)

- **551** ops = **489 implemented** + **62 blocked** (0 catalogued/stub/unknown). GATE PASS.
- Native family live-gate = **435** ops / **16** families + pre-M08 table. Drift-locked
  by `tests/unit/test_reconcile_family_gate_parity.py`. Full suite: 1191 unit OK.

## The mandate is a THREE-LANE certification program (sol), not "551 headless PASS"

Verification vocabulary — **PASS_HEADLESS / PASS_ATTENDED / PASS_LIFECYCLE**. NO
`PASS_WITH_DEFERRAL`: an attended-only op must pass an attended test; a lifecycle
event must pass a lifecycle test. Each PASS needs: correct host + build ID + registry
rev · empty/invalid→structured error + no mutation · valid exec · semantic assertion ·
original hash unchanged · (writes) staged pre/post delta + persistence · no
dialog/timeout/crash · evidence artifact.

## The 62-op "unwired" gap — decomposed by family × host × sol verdict

| family | n | host split | verdict | lane |
|---|---|---|---|---|
| constraints_associativity | 23 | 14 arx + 9 dbx | assocarray/DCM **YES headless** (evaluateTopLevelNetwork client-initiated); assocsurface gates on ASM | **P4 headless** |
| runtime_commands | 16 | 14 arx + 2 core | NOT job-dispatchable — `acrxEntryPoint`/load-unload callbacks | **P5 reclassify** kind=module_event, dispatchable=false + lifecycle harness |
| com_activex | 9 | 7 arx + 2 full | live COM **NO headless** — full acad.exe + STA + msg pump | **P5 attended** (or re-express AcDb-equivalent as separate op) |
| active_document_write_original | 4 | 3 core + 1 arx | writes ORIGINAL — router invariant FORBIDS (PROTECTED_PATHS) | **stays blocked by design** (or re-express as staged-copy op) |
| brep_solids | 4 | arx | edit.subentity.* interactive selection | **P5 attended** (ASM boolean itself is headless — these are the subentity-pick ops) |
| layouts_plot_publish | 2 | arx | headless plot **YES in CRX** (BACKGROUNDPLOT=0, AcPlPlotInfoValidator) | **P4 headless (CRX)** |
| ui_customization | 2 | arx | CUI/menu — attended | **P5 attended** |
| live | 1 | full | live.jig.point_probe — the 1 genuine attended crash | **P5 attended** |
| editor_input | 1 | arx | editor prompt | **P5 attended** |

**Real headless-buildable gap ≈ 25** (constraints 23 + plot 2). The other ~37 are
reclassify (16), attended (18), or policy-forbidden-by-design (4 write_original).
Forcing all 62 headless = the exact error sol warned against.

## Critical path

- **P0 — truth model** — ✅ DONE.
- **P1 — CRASH re-probe on current build** — IN FLIGHT (sweep v2 `b9tyvha1x` →
  `measure/reachable_matrix_20260713.jsonl`). Lane I evidence
  (`reports/lane_i_router_fix_resolution.json`) already proved **33/34 historical
  CRASH were pre-fix router artifacts**; only `live.jig.point_probe` is a genuine
  attended crash. Partial sweep (165/489) shows CRASH=2 — confirming. On land:
  triage any residual crash (one op / accoreconsole proc, stack-hash), fill numbers.
- **P2 — DEPRIORITIZED (architectural hygiene, NOT a functionality gap).** Measured
  2026-07-13: the sweep shows custom_objects_protocols **59/63 RUNNABLE headless (0
  CRASH — the 4 Jul-6 crashes are gone post router-fix)** and geometry_kernel largely
  RUNNABLE. So `host_class=arx_adapter` is a conservative registry LABEL, not a
  runtime incapacity — these ops already run in accoreconsole. Re-tiering into the
  .dbx Object Enabler is host-agnosticism cleanup, not a coverage/headless win, so it
  ranks below P3/P4/P5 (the genuine gaps). Original P2 text retained below for when
  hygiene is scheduled:
- **P2 (hygiene, deferred) — CRX/DBX/ARX boundary + 2 re-tiers** (custom_objects_protocols 57 arx→dbx,
  geometry_kernel 16 arx→dbx). **Do NOT dual-compile a family `.inc` into both CRX
  and DBX** (ODR/double-rxInit). C ABI across the DLL boundary; `AriadneDbxEntry.cpp:112`
  is the correct narrow-C-ABI pattern. Import audit.
- **P3 — typed arg schemas + fixtures + semantic oracles** → promote REACHABLE→RUNNABLE
  (sweep-sized), split DEGENERATE into ZERO_ARG_BY_CONTRACT vs INVALIDLY_DEFAULTED.
  Biggest bulk; fleet-decomposable per family once sweep lands.
- **P4 — close headless gaps** — constraints_associativity 23 + layouts_plot_publish 2.
- **P5 — full-acad + lifecycle lanes** — runtime_commands 16 reclassify + lifecycle
  harness; com_activex 9 / ui 2 / brep subentity 4 / live 1 / editor 1 attended lane.
- **P6 — full matrix certification + soak + packaging + GitHub** — source-only safest
  (registry/handlers/tests/schemas/build scripts). SDK via env/property-sheet, never
  hardcode `C:\ObjectARX 2027`; gitignore SDK headers/libs/PDBs/host DLLs. Binary
  release needs code-sign + legal review.

## Build & freshness (verified 2026-07-13)

- **Toolchain present**: `C:\ObjectARX 2027` SDK + VS2026 Community + `tools/build_native_acad.ps1`
  (builds `.dbx` → `.crx`/`.arx`, Release/x64, isolated OutDir). P2/P4/P5 build work is
  executable, not blocked.
- **FM2 freshness CLEARED for the headless path**: prebuilt `Ariadne.AcadNative.crx`
  = 2026-07-11 02:36 (== newest CRX source m08e_handlers.inc); prebuilt
  `Ariadne.AcadNativeDbx.dbx` = 2026-06-26 (built AFTER newest DBX source 2026-06-23 —
  DBX is a thin stable class-init shim, handlers live in the .crx). So sweep v2's
  results reflect the CURRENT headless build. (ARX = 2026-07-09, slightly behind, but
  irrelevant to the headless CRX/DBX sweep.)
- P6 will require a fresh full rebuild to stamp the canonical module SHA-256 into every
  cert artifact — do it AFTER sweep v2 lands (rebuilding mid-sweep would invalidate it).
- custom_objects_protocols is **63** ops (not 57): 58 arx_adapter (41 `native_arx_only`,
  16 `managed_also`, 1 lisp) + 5 dbx. geometry_kernel is **25** (16 arx + 9 dbx). The
  P2 re-tier is therefore a per-op **capability audit** (which arx ops are truly
  dbx-capable), NOT a blind "move 57→dbx" — the registry's own `native_arx_only` tier
  says 41 genuinely need ARX. Resolve the sol-57 vs registry-41 discrepancy by audit.

## Non-goals / guardrails

- Original `*.dwg` stays READ-ONLY (PROTECTED_PATHS). No `write_original` enablement.
- No fake PASS; live-probe availability only. Every number cites its producing run.
- No dual-compile of `.inc`. No manual ASM init (let Core Console load the modeler).
