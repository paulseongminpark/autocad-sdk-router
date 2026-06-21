# CAD OS Layer — TAKEOVER (re-entry after CADOS_M02)

**Repo:** `D:\dev\99_tools\autocad-sdk-router` (own git repo, `main`, no push).
**Last packet:** CADOS_M02_V1_COMPLETION_ULTRACODE → **PASS** (15/15 acceptance criteria). Prev: CADOS_M01 (`e18edde`).
**Version:** cad_os_layer_v1.0.0.

## State in one minute

- **Single entrypoint:** `tools/autocad-router.ps1` (11 routes, native cad-job lane). `-Action status` rewrites the published status (allowed for diagnostics).
- **Control plane:** `tools/cadctl_cli.py` → `cadctl.Cad` → `run_job` → router → native `.dbx`/`.crx` → `ir_builder` → `sqlite_ir_store`/`validator`/`cad_diff`/`patch_engine`.
- **Rich IR is live:** `python tools/cadctl_cli.py inspect --dwg <p> --out <dir> --include-rich` → `coverage_level=native_full` IR (21747 truth on the golden). Read-only; stages a copy.
- **Patch is live:** `patch_engine.apply_staged(patch, dwg, out)` → real staged mutation + `cad_diff` + 14/14 `validator` gates + journal; original byte-unchanged.
- **Native binaries:** `.crx` (rich, 190464B) is what `inspect.database.graph` runs on. Canonical `.arx` is stale/lock-held by attended acad.exe; **versioned `Ariadne.AcadNative.live_m02.arx` (190976B)** is the current relink. Rebuild: `tools/build_native_acad.ps1` (lock-resilient).
- **Tests:** `python -m pytest tests -q` (215 pass / 2 skip) OR `python -m unittest discover -s tests` (180 OK / 2 skip). Live tests env-gate on `CADOS_LIVE=1`.

## Golden truth (read-only original)

`staging/dwg_20260617_191504/input.dwg` — 2524981 B, sha256[:16] `27DBF6B95FF72A89`, **21747 modelspace entities** (3-way). by-type: LINE 16276 / INSERT 2027 / POLYLINE 1874 / ARC 753 / HATCH 669 / MTEXT 106 / CIRCLE 33 / TEXT 9.

## M02 partials — all RESOLVED → PASS

- **non-ASCII**: correct Hangul, proven by code points (`X-평면도(기본형)...`); the "mojibake" was a cp949-console display artifact. RETRACTED.
- **visual**: real IR→SVG before/after/overlay + visual_diff (`runs/m02_visual`); `visual_report.build_visual_report`.
- **live ARX pump**: `CADAGENT_PUMP` built + runtime-verified headless (`live.echo/status/list_documents/stop`, 21747); versioned `.arx` carries it.
- **2D/3D polyline geometry**: closed (1874/1874 POLYLINE now carry vertices).

## Remaining M03 depth (within the already-PASS rich IR)

- native hatch boundary geometry (AcDbHatch loops), per-entity xdata (pEnt xData per regapp), extension dictionaries (pEnt extensionDictionary). cadctl/IR are PASS without them.

## Invariants (never violate)

Original DWG READ-ONLY (staged copies only) · no-fake-success (truthful not_implemented/partial) · capture stdout+stderr+exit · stdlib-only Python control layer · don't break the frozen v1 29-op surface · never kill AutoCAD · no push.

See `handoff/NEXT_STEP.md` for the decision; `reports/v1_acceptance_latest.md` for the criterion matrix; `reports/CADOS_M02_V1_COMPLETION_ULTRACODE.md` for the full report.
