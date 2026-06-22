# Session Handoff

- **Saved**: 2026-06-22 13:33 KST (+09:00)
- **By**: /save (skill v2)
- **From cwd**: D:\dev\99_tools\autocad-sdk-router
- **Project**: autocad-sdk-router (CAD OS Layer)
- **Agent**: Claude Code — Opus 4.8 (1M context)
- **Roles touched this session**: [cad-os-layer]

---

## TL;DR (next session: read this first)

- **What** — CADOS_M07B packet executed → initially PARTIAL_PASS → **resolved to full PASS**. Attended GUI verification + native deploy closure + deep-native firing residual closed + skipped tests run.
- **Why** — M07B required dedicated-instance attended AutoCAD verification (OPM/worldDraw/live pump) and live reactor/overrule/selmon firing counts; PARTIAL was carrying an un-captured firing residual + 3 env-gated skips. User: "partial pass 해소해. 정직하게, 정확하게, skipped 된 test 도 진행해."
- **Where stuck / next action** — Nothing stuck. M07B is a clean full PASS, committed local (no push). Next packet = **CADOS_M08_FULL_OPERATION_COVERAGE_CLOSURE** (NOT yet started — awaits user confirmation).

---

## §0 Resume Path

> CAD OS Layer (`D:\dev\99_tools\autocad-sdk-router`, own git, main, no remote). M07B = **full PASS** committed `514289a` (router) + daedalus `7d13875`. Golden `27dbf6b9…` READ-ONLY unchanged. Working tree CLEAN. Deep native = 10 impl/verified, 0 attended_blocked; firing closed (reactor 1/1, overrule 2/3, selmon 1/1 — headless AND attended). pytest 295/3 default, 298/0 under `CADOS_LIVE=1`. Next is **CADOS_M08_FULL_OPERATION_COVERAGE_CLOSURE** — do NOT start without Paul's go. Bundle SoT: `D:\dev\_ariadne\alm\docs\CADOS_COMPLETION_PACKET_BUNDLE_M03_TO_FINAL\` (M08–M10 remain). Baseline: 517 ops, none yet carry the M08 13-field taxonomy (37 impl / 4 stub / 2 blocked / 474 catalogued). Verify before any claim: `cd D:\dev\99_tools\autocad-sdk-router; git log --oneline -3; python -m pytest -q` (and `$env:CADOS_LIVE=1` for the 3 live tests). Constraints persist: no fake PASS, no original-DWG write, no push. Do NOT jump to Daedalus integration before the v1 gate (M09) closes.

---

## §A Prompt Engineering Layer

### A.1 User profile (observed)
- Paul (paulseongminpark). Korean-primary. Direct-command = execute immediately (no extra confirmation) except irreversible ops.
- Demands honesty over green-washing: "정직하게, 정확하게", "skipped 된 test 도 진행해". No fake PASS.
- Wants parallelism where independent ("모두 병렬로") and wants the *reasoning* ("뭐가 문제였고, 어떻게 할 것인지 설명").

### A.2 Behavioral feedback received
- Resolve PARTIAL honestly — run the skipped tests too, don't hide them. (apply-when: any packet ending in PARTIAL/skip)
- Explain problem + plan before/with execution. (apply-when: non-trivial fix)

### A.3 Bootstrap continuation prompt
- See §0. Next concrete action: await Paul's go on M08; if go, read `CADOS_M08_*` packet from the bundle SoT and baseline the 517-op taxonomy.

---

## §B Context Engineering Layer

### B.1 Files modified (this session — all committed)
- `src/Ariadne.AcadNative/AriadneNativeJob.cpp` — host-EXE gate `hostIsFullAutoCad()`; pump-gating 5 attended ops; `ARIADNE_NATIVE_JOB_ARGS` env-file channel; 2 firing ops (`extend.deep_native.firing_selftest`, `inspect.deep_native.firing_report`); palette registration under `#ifndef ARIADNE_NATIVE_CRX`.
- `src/Ariadne.AcadNative/AriadnePalette.cpp` (NEW) — MFC-free `ARIADNE_PALETTE`; `extern "C" ariadneRegisterPaletteCommand()`.
- `src/Ariadne.AcadNative/Ariadne.AcadNative.arx.vcxproj` — add AriadnePalette.cpp (arx only, not crx).
- `tests/unit/test_m07b_pump_gating_and_job_channel.py` (NEW, 10 source-guard tests incl. firing-ops presence).
- `tools/attended/run_attended_m07b.ps1` (NEW) — dedicated acad.exe harness, 3 safety gates, PrintWindow screenshot.
- `runs/m07b_native_smoke/run_native_smoke.ps1`, `runs/m07b_firing/run_firing.ps1` (NEW) — channel drivers.
- Reports/docs/handoff/Daedalus-external — flipped to M07B PASS (see §B.8 commits; full list in role bead).

### B.2 Files referenced
- `D:\dev\_ariadne\alm\docs\CADOS_M07B_ATTENDED_GUI_VERIFICATION_AND_NATIVE_DEPLOY.md` — the source packet.
- `D:\dev\_ariadne\_daedalus\HANDOFF\roles\cad-os-layer.md` — canonical cross-system role bead (already updated this session, last-updated 2026-06-22T13:10).

### B.3 Decisions made
- **Firing capture is host-independent** (overrule/reactor/selmon = DB/editor level) → captured in BOTH headless and attended; no GUI dependency. Reversible: no (proven mechanism).
- **Bypass one-op-per-session limit via TWO input channels** (`ARIADNE_NATIVE_JOB_ARGS` cmd1 + `ARIADNE_NATIVE_JOB_MAILBOX` cmd2) so reactor `commandWillStart` fires on cmd2's start. Reversible: yes (could add a multi-op frame later).
- **Overrule fired via `acdbOpenObject`, selmon via `acedSSSetFirst`** — no `acedCommand` reentrancy needed inside the modal pump. Reversible: no (architectural).
- **Run the 3 CADOS_LIVE-gated tests under `CADOS_LIVE=1`** rather than leave skipped — honest closure. Default run stays 295/3 (honest env-gates), explicit `CADOS_LIVE=1` → 298/0.
- **M07B = full PASS** (not PARTIAL) — firing residual closed + skips run. Reversible: no.

### B.4 Open questions
- Start M08 now? — proposed: NO, await Paul. (blocker: M08 not requested this exchange.)

### B.5 Constraints introduced (carry-forward, HARD)
- H: No fake PASS. H: Original golden DWG (`staging/dwg_20260617_191504/input.dwg`, sha `27dbf6b9…`) READ-ONLY (copy only). H: No remote push. H: Do not kill / reuse user's AutoCAD; dedicated instance only, 3 safety gates. H: No `write_original` default; no raw-command agent API; zero-COM preferred; never mark unavailable ops PASS; never hide skipped checks.

### B.6 Task state snapshot
- M07B packet: COMPLETED (full PASS, committed). All 13 internal tasks done.
- M08: NOT STARTED.

### B.7 Code in progress
- None. All edits committed; build canonical; tree clean.

### B.8 External state changed (irreversible-ish)
- Router commits (main, **NO push**): `d1e35b5` (M07B attended+deploy) → `514289a` (firing residual → full PASS).
- Daedalus external commits (**NO push**): `b761185` (import M07B handoff) → `7d13875` (firing closed → full PASS).
- Native build artifacts rebuilt canonical: `.dbx` 48128 / `.crx` 250368 / `.arx` 258048.
- Memory updated: `project_cad_os_layer.md` (PASS + firing closed).

---

## §C Harness Engineering Layer

### C.1 cwd
- This session: `D:\dev\99_tools\autocad-sdk-router`. Next recommended: same (CAD OS work) — own git repo, build/tests/runs all rooted here.

### C.2 MCP servers required
- None required for next step. (Router work is local PowerShell + native build + pytest; CAD ops go through `tools/autocad-router.ps1`.)

### C.3 Hooks expected
- PreToolUse(PowerShell): CAD router enforcement reminder (advisory; fires on CAD-file/lib detection).
- PostToolUse(Bash): Ariadne emit (detached fire-and-forget) — use Write/PowerShell tools to avoid latency.

### C.4 Environment / external services
- AutoCAD 2027 (`acad.exe` attended; `accoreconsole.exe` headless) at `C:\Program Files\Autodesk\AutoCAD 2027\`. Attended harness launches a DEDICATED instance only.
- Native build via `tools/build_native_acad.ps1` (canonical relink; versioned `.arx` lock-bypass if acad.exe holds it).
- `CADOS_LIVE=1` env gate enables the 3 live-AutoCAD pytest tests.

### C.5 Skills / plugins assumed
- `/save`, `/prime` (HANDOFF loop). superpowers (verification-before-completion).

### C.6 Permission notes
- Default. No push without explicit ask.

### C.7 Credentials needed
- None for next step. (Never read/print .env/token/key/.pem.)

---

## §D Reasoning chain (rejected alternatives)

| Decision | Chosen | Rejected alt | Why rejected |
|---|---|---|---|
| Gate attended ops | host-EXE `hostIsFullAutoCad()` (GetModuleFileNameW(NULL) basename == acad.exe) | `acedEditor != nullptr` | acedEditor is non-null in accoreconsole too → broke headless 17/17 |
| Gate attended ops (2) | host-EXE name | `ARIADNE_CAD_JOB_HOST_MODE` env hint | env hint does not propagate into attended acad.exe |
| Fire reactor | 2nd command via MAILBOX channel | acedCommand inside pump | pump is modal blocking — acedCommand reentrancy illegal |
| Fire overrule/selmon | acdbOpenObject / acedSSSetFirst | drive via GUI pick | needs human; not headless-capturable; host-dependent |
| Close skips | run under CADOS_LIVE=1 | leave 3 skipped | user explicitly required skipped tests run |

### §E Live snapshots (volatile state, at save time)
```yaml
git_router:
  branch: main
  HEAD: 514289a103e68ce19c20b28049d50596aeb9e239
  dirty: false
git_daedalus:
  HEAD: 7d138752ef56171a96e9df266541e956c68e434b
golden_dwg:
  path: staging/dwg_20260617_191504/input.dwg
  sha256: 27dbf6b95ff72a89fd53b153891187365b9e8ebc4c05a97cfed307057bf49bc8
  modified: false
native_build:
  dbx: 48128
  crx: 250368
  arx: 258048
tests:
  default: "295 passed / 3 skipped"
  cados_live_1: "298 passed / 0 skipped"
```

### §F Tool output cache (re-fetch handles)
| Operation | Source/handle | Re-fetch cost | Re-fetch via |
|---|---|---|---|
| firing counts | `reports/firing_latest.json`, `runs/m07b_firing/seq{0,1}_out.json` | medium (needs native run) | `runs/m07b_firing/run_firing.ps1 -Mode headless` |
| attended proof | `runs/cados_m07b_attended_20260622_123505/` (+ screenshots/acad_window.png) | high (needs dedicated acad.exe) | `tools/attended/run_attended_m07b.ps1` |
| op coverage baseline | `reports/registry_coverage_latest.json` | cheap | `python cadctl registry coverage` |
| v1 acceptance | `reports/v1_acceptance_latest.json` | cheap | read file |

### §G Negative space (intentional non-actions)
- Intentionally deferred: docked `CAdUiPaletteSet` palette (MFC) — kept palette MFC-free for build stability.
- Intentionally deferred: `live.zoom_to_handles` / `live.render_view` real execution — honestly "deferred" (acedCommand reentrancy inside modal pump).
- Out of scope: M08 (not requested); Daedalus integration (gated behind M09 v1 freeze).
- Not pushed: both repos local-only (no remote configured / no push per constraint).

### §H Skill runtime state (mid-skill resume)
```yaml
in_progress_skill: null
step: n/a
state: M07B complete; /save running at session end
resume_command: n/a
```

---

## §Z Notes / gotchas
- `acedEditor` is non-null in accoreconsole — cannot be used to discriminate attended vs headless. Use host-EXE name.
- JOB dispatcher key is `"operation"`; pump frame key is `"op"`. Mixing them → `operation:""` / "unsupported".
- Attended screenshot: client must connect to pump BEFORE screenshot (else connect window lost); use `PrintWindow(HWND)` (not SetForegroundWindow) to beat the Windows foreground-lock.
- One args-file = one op per session — use ARGS + MAILBOX two-channel to get a 2nd command boundary.
- selmon registry text must NOT say "callbacks never fire" — contradicts the live count (=1); corrected.

---

## How to Resume
1. Open fresh session at: `D:\dev\99_tools\autocad-sdk-router`
2. `/prime` (auto-bootstrap) — OR — read this file's §0
3. Verify §E live snapshots still match (`git log --oneline -3`; golden sha; `python -m pytest -q`)
4. §H is null — no mid-skill resume.
