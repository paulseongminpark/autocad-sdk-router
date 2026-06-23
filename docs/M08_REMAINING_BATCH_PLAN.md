# M08 Remaining — Batched Execution Plan (catalogued 353 → 0)

> State at authoring: main `71b5990`. implemented **162** / blocked 2 / catalogued **353** (517 total).
> Done: READ wave (C/D/E, 84) + WRITE wave (G/H, 37) + reconciles. closure_gate **False**; M09 blocked.
> Method invariant (proven on READ+WRITE): seam-ext (shared `AriadneNativeJob.cpp` wiring, 1 PR) →
> parallel family teammates (own-worktree + ABSOLUTE paths, one `.inc` each) → combined-TU integration
> build → one-PR-per-family → merge orchestrator → `tools/reconcile_native_registry.py` → post-merge gate.

## The decisive variable: host strategy (NOT all "same method")

The remaining 353 split by `engine_tier` / `risk_class` into FOUR strategies. Only Strategy-1 fits the
hostless `.inc` teammate fan-out that READ/WRITE used.

| strategy | how | count (approx) | closes as |
|---|---|---|---|
| **S1 hostless-native** | `.inc` teammate (objectdbx_capable + native_arx that links in accoreconsole/DBX) | ~120–170 | implemented |
| **S2 managed/.NET + accoreconsole** | managed plane / NETLOAD / `.scr` (plot, some doc/overrule/reactor) | ~44 | implemented or hard_blocked |
| **S3 attended full-AutoCAD** | needs a running GUI or the M07B live pump (jigs, palette, grips, OPM-UI, COM, live-apply, doc.*) | ~120–150 | implemented-via-live-pump **or** hard_blocked("attended-only") |
| **S4 hard_block** | never agent-exposable (raw_command `command.invoke.*`) | 5 | deprecated/blocked |

`engine_tier` of the 353: native_arx_only 202 · objectdbx_capable 91 · managed_also 44 · lisp 16.
`risk_class`: read_safe 236 · staged_write 70 · live_edit 42 · raw_command 5.

**Closure math:** catalogued→0 is reached by `implemented` OR `hard_blocked`(+blocker_ref) OR `deprecated`.
So S3/S4 ops that cannot be done autonomously still CLOSE — honestly — via `hard_block`. The wave's job
is to maximize real implementations (S1+feasible S2) and honestly hard_block the rest.

## Remaining inventory by ticket (catalogued)

| ticket | ops | dominant tier | strategy | notes |
|---|---|---|---|---|
| M08K-T01 custom object/entity lifecycle | 45 | native_arx 38 | S1 (mostly) | custom AcDbObject/Entity create/read/roundtrip, class reg/unload — DBX-resident, hostless-feasible |
| M08K-T03 constraints/associativity (AcDbAssoc*) | 58 | objectdbx 39 | S1 (mostly) | DB-resident assoc actions/constraints — hostless read+create feasible (index-gap ticket) |
| M08L-T01 WorldDraw/viewportDraw | 8 | native_arx 8 | S1/S3 | drive AcGiWorldDraw collector hostless (feasible) vs viewport (attended) |
| M08L-T02 overrules/grips/graphics invalidation | 19 | managed 15 | S2/S3 | overrules register hostless but fire in-app; grips attended |
| M08M-T01 OPM properties | 33 | native_arx 29 | S1/S3 | property protocol read = hostless; Properties-palette = attended |
| M08M-T02 reactors | 22 | managed 13 | S1/S3 | DB reactors fire hostless (in-txn); editor reactors attended |
| M08N-T01 jigs + editor interaction | 17 | native_arx 10 | S3 | jigs/acedGet* need the editor — attended |
| M08N-T02 selection/UI/palette/command shell | 56 | native_arx 46 | S3 | command registration hostless; firing/UI attended |
| M08I-T01 render/plot export | 2 | managed 2 | S2 | plot to PDF via accoreconsole `-plot`/NETLOAD feasible |
| M08J-T03 doc.* (active document) | 5 | managed 4 | S3 | active-document ops — attended; doc.sendstring → S4-ish |
| M08O-T01 COM bootstrap/load fallback | 16 | native_arx 9 | S3 | COM needs running acad (out-of-proc server) — attended |
| M08O-T02 AutoLISP/.NET fallback adapters | 22 | native_arx 18 | S1/S4 | 5 raw_command → hard_block; rest = LISP/.NET adapters |
| **deferred READ leftovers** (M08B-T03, M08C-T01/02/03, M08D-T03, M08E-T01/03) | 27 | mixed | S1/disposition | some never-attempted-but-feasible (db metadata, xrefs, ext symbol tables); some ASM/attended |
| **deferred WRITE leftovers** (M08G-T02/03, M08H-T01) | 23 | objectdbx 20 | S1/disposition | ASM-modeler solids (hard_block) + host/style-bound (retry or block) |

## Execution batches (sequenced; each ends merged+reconciled, 0 open PR)

### Batch A1 — NATIVE-K (highest hostless yield) ⟵ recommended first
- **Scope:** M08K-T01 (45) + M08K-T03 (58) = **103 ops**.
- **Units:** `m08k_handlers.inc` (custom objects) + `m08kx_handlers.inc` (constraints) → **2 teammates**.
- **Method:** seam-ext (wire m08k/m08kx) → 2 parallel teammates (own-worktree+abs, implement hostless-feasible + honest-defer attended) → integration build → 2 PR → merge → reconcile.
- **Expected:** large implemented yield (custom-object roundtrip + assoc read/create are DBX-resident).

### Batch A2 — NATIVE-L/M (graphics/overrule/OPM/reactor)
- **Scope:** M08L (27) + M08M (55) = **82 ops**.
- **Units:** `m08l_handlers.inc` + `m08m_handlers.inc` → 2 teammates (split M if needed).
- **Expected:** moderate yield (worldDraw collector, DB reactors, property-protocol reads = S1); defer grips/palette/editor-reactors (S3) with "attended" blocker.

### Batch A3 — NATIVE-N (editor/UI/selection/command)
- **Scope:** M08N-T01 (17) + M08N-T02 (56) = **73 ops**, mostly S3 attended.
- **Units:** `m08n_handlers.inc` → 1–2 teammates: implement the few hostless (command registration, selection-filter construction, highlight-by-id) + hard_block-candidate the interactive rest.
- **Expected:** LOW implemented yield, HIGH honest-defer→hard_block. (This is where the attended-policy decision below bites hardest.)

### Batch B — VISLIVE + FALLBACK (managed/lisp/COM/raw)
- **Scope:** M08I-T01 (2) + M08J-T03 (5) + M08O-T01 (16) + M08O-T02 (22) = **45 ops**.
- **Method:** NOT a native `.inc` fan-out. Direct disposition: accoreconsole/NETLOAD plot (S2 impl), LISP/.NET adapters (S2 impl where feasible), **hard_block the 5 raw_command** (S4), hard_block COM/doc-attended (S3) with blockers.

### Batch C — deferred-disposition sweep (READ 27 + WRITE 23 = 50)
- One honest pass over every READ/WRITE leftover: **retry-implement** the now-feasible hostless ones (db-metadata, xrefs/layouts, ext symbol tables, host/style-bound writes), **hard_block** the genuinely infeasible (ASM-modeler solids, attended) with blocker_ref. Drives the READ/WRITE remainder → 0.

### Batch D — closure gate (M08P/Q/R) ⟵ only when catalogued/stub/unknown/deferred = 0
- M08P-T01 merge closure matrix, M08P-T02 evidence audit, M08Q-T01 golden regression, M08Q-T02 scale/stress, M08R-T01 RC freeze. Then — and only then — M09.

## Decision required (gates how much closes autonomously vs. needs you)

**Attended ops (S3, ~120–150: jigs, palette, grips, OPM-UI, COM, live-apply, doc.*).** These cannot be
implemented hostless by autonomous teammates. Pick the disposition policy:

- **(P-block) hard_block now** — close them as `blocked` with blocker_ref "requires attended full-AutoCAD
  host; not hostless/agent-feasible". Fast, honest, reaches catalogued→0 without you at the GUI. Native
  apex for these stays a documented future-attended item.
- **(P-live) implement via the M07B live pump** — the ones the existing CADAGENT_PUMP (named-pipe to a
  running AutoCAD) can reach get real implementations in attended sessions you run; the rest hard_block.
  Higher real coverage, but needs your attended AutoCAD time per session.
- **(P-mix, recommended)** — auto-implement all S1+S2 now (Batches A/B/C), hard_block pure-interactive
  S3 (jigs/palette/grips/UI), and shortlist the *live-pump-reachable* S3 (some reactors/selection/live
  read) for one optional attended session. Maximizes autonomous closure, reserves your GUI time for only
  the ops that genuinely benefit.

## Recommended order
A1 → A2 → A3 → B → C → (apply attended policy) → D. A1 first: biggest hostless-native payoff, lowest risk,
same proven method.
