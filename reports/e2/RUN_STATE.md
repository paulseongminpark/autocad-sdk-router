# E2 Wave 0 run state (disk-first, octorun discipline)

Updated: 2026-07-17 (launch)

## Order (Paul)

S1~S6 전부 진행, Wave 0 = S1 법의학 + S2 합성 생성기 + S3 외부셋 + S4 탐지기 모듈 + S5 배터리 골격.
Fleet: octoloop octavius CLI (fresh-config), worktree-parallel, **main aclaude quota untouched**.
Lanes: sonnet_b/c=opus x3each (sunapse/sunapse-kdw) · sonnet_d/e=opus x5each (junhyuk8987/paulparkhere)
· codex_56terra x4 · grok x5 (pool 3 — starvation precedent). Total 25 packets.

## Canary (before fleet)

- 1 packet, lane sonnet_b + env dial OCTOLOOP_SONNET_B_MODEL=opus → receipt ran_model="opus",
  worker self-identified "claude-opus-4-8", diff = exactly the declared file. **Dial VERIFIED.**
- Known nuisance: worktree cleanup can fail with Windows Permission-denied AFTER the receipt seals
  (exit 1 from octavius run) — receipts are the truth, stale .wt dirs are disk noise (gc later).
- Canary run: LOOP-20260717114809-117wq6v (not merged; canary file lives only in its diff).

## Fleet

- Packets file: reports/e2/wave0_packets.json (25; fileset-disjoint machine-checked by
  reports/e2/wave0_build_packets.py; contracts inlined per delegation rule).
- Assignment: sonnet_d=S1-A..E (forensic) · sonnet_e=S4-A..E (detector modules) ·
  sonnet_b=S2-B/C/D (generator core) · sonnet_c=S2-A/E/F (stats/pack/fidelity) ·
  codex_56terra=S3-B/C/D/E (extset parsers/features) · grok=S5-A/B/C/D + S3-A (battery + fetch tooling).
- Liveness fact (payload-truth): receipts/*.receipt.json count under the runDir printed at launch;
  per-packet diffs under evidence/. NOT the wrapper exit code (see canary nuisance above).
- Terminal vocabulary: success | clean_no_op | blocked | approval_required | exhausted | no_progress.
  Any packet below its card contract after one re-fire = reported PARTIAL, never silently dropped.

## Next obligations

1. On fleet completion: octavius collect --run <id> → verify 25 receipts, review diffs.
2. Merge eligible diffs into main (single-writer: orchestrator session), run selftests post-merge.
3. S1 verdicts (A..E) fold into reports/e2/s1/ — these gate S4 calibration and prereg sealing.
4. Real-data steps deferred by cards: extset real-data validation, staged 1.dwg DXF run of detector v1
   — orchestrator, after merge.

## HARVEST (2026-07-17, runs LOOP-20260717120806-17xckkd + refire LOOP-20260717122756-1exo0ma)

- Fleet run_finished: dispatched 25, runner-failed 0. Receipts: 20 DONE_WITH_CONCERNS + 5 BLOCKED.
- BLOCKED forensics (payload-truth): s1a/s1c/s1d = adapter misclassification (claude CLI stderr
  "no stdin data received in 3s" warning read as error; all declared files delivered — merged).
  s2c-openings = genuine no-output; s5b-transforms-struct = cursor cli-config.json rename race
  (3 simultaneous grok starts — "grok 다중동시 기아" precedent root-caused).
- Merge: 23 diffs @d6e1133 + refire 2 @aac35d0, all `git apply` clean (filesets disjoint by design).
- Spot selftests PASS 6/6: detect/cli (end-to-end), synth/grammar, synth/openings, meta/transforms_rigid,
  meta/transforms_struct, extset/fpc_parse. ezdxf 1.4.3.
- S1 verdicts (reports/e2/s1/*.json): handle_audit CLEAN · entity_census BLINDNESS_CONFIRMED
  (divergent median LINE-share 0.0 vs uniform 0.333) · bbox_units table delivered · sortkey MIXED
  (top-20 Jaccard 0.4–0.7) · censoring: ornith_v0 CAP_CENSORED, live top-tier judges NOT_CENSORED.
- Kernel observability ticket: detached-runner packet errors are returned in-memory only — never
  ledgered (first fleet's 25 instant failures left zero per-node reasons on disk).

## TERMINAL (2026-07-17)

- Fold: **success** — 25/25 cards delivered (23 first pass + 2 refire), spot selftests PASS.
- S3-A REVISED by discovery (Paul correction: "이거 다 내 로컬에 깔려있어"): FloorPlanCAD already local —
  FiftyOne raster export, 5,308 PNG + per-object wall bbox/segmask (samples.json 60MB) at
  `D:\dev\_ariadne\huggingface\datasets\floorplancad` (= `_ariadne\alm\datasets\FloorPlanCAD`).
  cubicasa5k local copy = card stub (no data). Prior fine-tuned models exist:
  `_ariadne\huggingface\models\qwen25_vl_3b_floorplan_{sft,grpo}`. Download step CANCELLED;
  the vector (SVG line-label) variant is the only non-local artifact — acquisition decision = Paul.
- `D:\datasets` junction dangles (pre-Catalog target `_ariadne\harness\runs\alm\datasets`) — repair
  pending approval (drive-root change).
