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
4. Real-data steps deferred by cards: FloorPlanCAD/CubiCasa download (D:\mirror\extsets), staged 1.dwg
   DXF run of detector v1 — orchestrator, after merge.
