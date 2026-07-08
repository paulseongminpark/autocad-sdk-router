---
role: rhino-sdk-parity
state: working
started: 2026-07-06
last-updated: 2026-07-07T08:30:00+09:00
last-session: sessions/SESSION_2026-07-07_0830.md
---

# Role: rhino-sdk-parity

**Summary**: Bring the Rhino/Grasshopper SDK stack to parity with the AutoCAD SDK Router (CADOS) across 7 parity axes.

**Current state**: M0, M1, M2, M3A, M4 COMPLETE and pushed. M3B–M6 remain.

## Completed milestones

| Milestone | Status | Content | Branch |
|-----------|--------|---------|--------|
| M0 — Risk fix + census | COMPLETE | 5 repos under Paul-owned remotes with content pushed | N/A (merged to main) |
| M1 — Operation registry v0 | COMPLETE | 119 ops (34 impl_unverified + 85 catalogued), schema, build/registry tools | `rh/m1-registry` |
| M2 — Headless truth lane (read) | COMPLETE | `rhino3dm_extract.py`, IR spec, 7 tests, real .3dm extractions | `rh/m2-readlane` |
| M3A — Staged-write for .3dm files | COMPLETE | `rhino3dm_stage.py`, spec, 6 tests passing, copy-to-staging + diff + apply-back | `rh/m3a-staged-write` |
| M4 — MCP governance wrapper | COMPLETE | `rhinoagent_mcp.py` (proxy with allow-list + write-mode validation), 11 tests passing | `main` (merged) |

## GitHub repos (all pushed)

| Repo | URL |
|------|-----|
| rhino-bridge-core | `paulseongminpark/rhino-bridge-core` |
| rhino-bridge-rhp | `paulseongminpark/rhino-bridge-rhp` |
| rhino-bridge-component | `paulseongminpark/rhino-bridge-component` |
| rhino-sdk-router (main + branches) | `paulseongminpark/rhino-sdk-router` |
| rhino-grasshopper-mcp | `paulseongminpark/rhino-grasshopper-mcp` |
| grasshopper-mcp | `paulseongminpark/grasshopper-mcp` |
| daedalus (daedalus/corpus-batch) | `paulseongminpark/daedalus` |

## 7-Axis status (updated)

| Axis | Status | Delta since audit |
|------|--------|-------------------|
| 1. Operation registry | PARTIAL | M1: 119 ops, but no allow-list/write-mode gate |
| 2. Governed MCP (5 runtimes) | PARTIAL (3/5) | M4: governance wrapper built, but Pi/Hermes unwired |
| 3. Originals READ-ONLY + staged-write | PARTIAL | M3A: staged-write for .3dm files; M4: governance wrapper enforces it |
| 4. Live availability probing | PARTIAL | M1: registry schema check added; no per-op probe matrix |
| 5. Headless truth lane | PARTIAL+ | M2: rhino3dm_extract.py + 7 tests; GH_IO structural inspection not built |
| 6. Test gate | PARTIAL | M1+M2+M3A+M4: ~26 tests across 4 modules; no C# tests, no CI |
| 7. GitHub remote | COMPLETE | All repos pushed, main has M1+M2+M3A+M4 |

## Next actions (prioritized)

| Priority | Action | Axis | Effort |
|----------|--------|------|--------|
| P0 | M3B: Staged-write for live canvas (.gh save/modify/restore) | 3 | 1.5–2 weeks (hardest design) |
| P1 | M5: Live-probe matrix + register governed MCP across all 5 runtimes | 4, 2 | 3–4 days |
| P2 | M6: Unified test gate + C# test project + CI | 6 | 1–1.5 weeks |

## Source paths (on disk)

- `D:\dev\_agent_workspace\02_rhino-mcp\RhinoBridgePlugin.Core\`
- `D:\dev\_agent_workspace\02_rhino-mcp\RhinoBridgePlugin.Rhp\`
- `D:\dev\_agent_workspace\02_rhino-mcp\RhinoBridgePlugin\`
- `D:\dev\_agent_workspace\02_rhino-mcp\rhino-grasshopper-mcp\`
- `D:\dev\_agent_workspace\02_rhino-mcp\grasshopper-mcp\`
- `D:\dev\99_tools\rhino-sdk-router\wt\rh_m1\`
- `D:\dev\99_tools\rhino-sdk-router\wt\rh_m2\`
- `D:\dev\99_tools\rhino-sdk-router\wt\rh_m3a\`
- `D:\dev\99_tools\rhino-sdk-router\wt\rh_m4\`
- `D:\dev\99_tools\rhino-sdk-router\wt\d_corpus\`

## Audit references

- Full audit: `D:\dev\99_tools\rhino-sdk-router\docs\RHINO_SDK_PARITY_AUDIT_20260706.md`
- 7-axis summary: `D:\dev\.build\cados_plan\pi_out\pi_rhino_audit.md`
