---
role: cad-os-layer
state: working
started: 2026-06-21
last-updated: 2026-06-22T14:51:00+09:00
last-session: sessions/SESSION_2026-06-22_1451.md
canonical-cross-system-bead: D:\dev\_ariadne\_daedalus\HANDOFF\roles\cad-os-layer.md
---

# Role: cad-os-layer

**Summary**: The AutoCAD SDK Router promoted to a CAD operating-system layer (`D:\dev\99_tools\autocad-sdk-router`, own git, main, no remote) — cadctl/MCP → router → native ObjectARX → DWG Graph IR → diff/validate/visual/live-pump. Daedalus (`_ariadne\_daedalus`) consumes it via `external/cad_os/`. Router-local bead; canonical cross-system bead in the Daedalus HANDOFF (kept in sync).

**Current focus**: **M08 = full PASS, committed local (no push)**. Milestones: M02 `dc6bc03`, M03 `9dbc9fc`, M04 `fd3caea`, M05 `e1fdc91`, M06 `ef603b8`, M07 `797a525`, M07A `5db2e6c`, M07B `d1e35b5`+`514289a`. Working tree clean after the M08 commit; golden `27dbf6b9…` READ-ONLY unchanged.

**M08 closure (this session, built BY Claude)**: full operation coverage closure. All **517** registry ops carry the M08 **13-field** taxonomy (0 unknown / 0 missing field / 0 v1-target deferred); v1 operation gate **11/11** (`reports/v1_operation_gate_latest.json`). Status implemented **41** / stub **0** / blocked **2** / catalogued **474** (cadctl `registry coverage` consistent=true). v1-target **43** (41 implemented + 2 hard-blocked: `render.layout`, `live.apply_patch`). Deterministic generator `tools/operation_coverage_matrix.py` → `reports/operation_coverage_full_matrix.json`(+`.md`). **Sweep built 3 native inspect ops** (`inspect.layers`/`inspect.blocks`/`inspect.entities` → `listLayerRecords`/`listBlockDefinitionsDetailed`/`listModelSpaceEntities`), accoreconsole-smoked on staged golden: **70 layers / 245 block defs / 21747 entities == M03 truth**; non-ASCII UTF-8 preserved (code-point verified `U+D3C9`=평, 0 U+FFFD). `live.status` promoted (handler `pumpDispatch`). Native build canonical **.dbx 48128 / .crx 260096 / .arx 268288** (`reports/build_native_m08.log`). pytest **313/3** default, **316/0** `CADOS_LIVE=1`. Tests `tests/unit/test_m08_operation_coverage.py` (17). Evidence `runs/m08_inspect_ops/`.

**Key lesson (M08)**: caught + fixed a risk_class misclassification — `policy.raw_command_dispatch=forbidden` is a SAFETY GUARANTEE carried by safe python ops, NOT a "this op IS a raw command" marker; conflating it wrongly walled off the 4 cadctl/MCP tools (query.entities/validate.ir/patch.dry_run/patch.apply_staged). Fixed: raw_command detected by actual native_api (`acedCommand*`/`command.invoke`) → 5 raw ops, all `catalogued`, **0 agent-exposed** (guard is non-vacuous). Also: the cp949 console mojibake on Korean names is a DISPLAY artifact — on-disk bytes are valid UTF-8 (verify by code-point, never console).

**Next action (SCOPE DECISION OPEN — do NOT auto-proceed to M09)**: Paul questioned whether M08 actually built the ~474 ops / matches the "태초의 계획". Honest truth: this session built only **3 new native ops** (+live.status promo); **474 remain `catalogued` = NOT built**. M08 PASS holds ONLY under the packet *body* acceptance (classify-all + v1-target-only); the bundle `index.md` ("implement OR hard-block, no unclassified") is stricter and NOT met. **The two spec sources contradict.** Paul rejected the structured scope question and wants to **clarify first** — I offered 4 angles (① index-vs-body wording, ② per-family feasible-cheap vs bespoke-heavy breakdown, ③ his baseline intent, ④ was my narrow v1_target a fair cut). **Resolve scope with Paul → then either (A) build feasible reads ~30 more, (B) implement-or-block all 474 [reopens M08, huge], or (C) keep v1-surface + proceed M09.** Honesty first, no fake PASS.

**Blockers**:
| since | blocker | mitigation |
|---|---|---|
| 2026-06-22 | M08 scope ratification OPEN — "build 474 vs classify+v1-surface" undecided; packet index.md (implement-or-block-all) vs body (classify+v1-only) contradict | Paul clarifying; do NOT proceed to M09 until scope set; M08 PASS = packet-body-acceptance only |

**Decisions log** (append-only):
| date | decision | rationale |
|---|---|---|
| 2026-06-22 | M07B = full PASS (firing closed) | reactor/overrule/selmon live counts headless+attended; 3 CADOS_LIVE skips run+pass |
| 2026-06-22 | M08 = full PASS | 13-field taxonomy over 517 ops (0 unknown/missing/deferred), v1 gate 11/11; 3 native inspect ops built+smoked + live.status promoted |
| 2026-06-22 | v1_target = status∈{implemented,blocked} | v1 surface = implemented + first-class hard-blocked; 474 catalogued = future native capability; no feasible v1 read left catalogued after the inspect sweep |
| 2026-06-22 | raw_command by native_api not policy flag | policy.raw_command_dispatch=forbidden is a safety guarantee on SAFE ops; fixed to detect acedCommand*/command.invoke → 5 raw ops catalogued, 0 exposed |
| 2026-06-22 | built inspect.layers/blocks/entities natively | feasible headless reads → honesty requires building (not deferring to non-v1); smoked 70/245/21747 == M03 truth |
| 2026-06-22 | M08 scope SURFACED as open (post-commit) | Paul asked "are all 474 actually built?"; honest NO (3 built); packet index vs body contradict; M08 PASS is body-acceptance only — scope to be ratified before M09 |

**Linked sessions**:
- sessions/SESSION_2026-06-22_1333.md (M07B PARTIAL→full PASS firing close; then M08 full coverage closure)
- sessions/SESSION_2026-06-22_1451.md (M08 committed PASS; scope question OPEN — 474 catalogued not built; Paul clarifying)
