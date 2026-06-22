# M08A-T02 — Execution DAG & Ticket Inventory

Generated over the M08A-T01 implementation map (`reports/full_sdk_implementation_map.json`). Every one of the
517 ops carries a **lane** (phase group) and a **merge wave**; every lane belongs to a merge wave; the ticket
dependency graph is acyclic. Machine artifacts: `reports/operation_execution_dag.json`,
`reports/ticket_inventory.json`.

## Merge wave order

```
foundation (M08A) → infra (M08B) → MERGE-M08-READ → { MERGE-M08-WRITE,
                                                       MERGE-M08-VISLIVE,
                                                       MERGE-M08-NATIVE,
                                                       MERGE-M08-FALLBACK } → MERGE-M08-FINAL
```

- WRITE depends on READ (per MERGE-M08-WRITE "after read merge").
- VISLIVE depends on READ-family gates (D/G).
- NATIVE and FALLBACK depend only on infra (M08B) → can run in parallel worktrees once B lands.
- FINAL gates all family merges (P/Q/R closure).

## Op load per wave (where the work actually is)

| wave | lanes | ops |
|---|---|--:|
| foundation | M08A | 0 |
| infra | M08B | 2 |
| MERGE-M08-READ | M08C, M08D, M08E, M08F | 130 |
| MERGE-M08-WRITE | M08G, M08H | 71 |
| MERGE-M08-VISLIVE | M08I, M08J | 16 |
| **MERGE-M08-NATIVE** | **M08K, M08L, M08M, M08N** | **260** |
| MERGE-M08-FALLBACK | M08O | 38 |
| MERGE-M08-FINAL | M08P, M08Q, M08R | 0 |

**Half the registry (260 ops) is in the NATIVE wave** — custom objects/overrules/OPM/reactors/jigs — the
deep-native, attended-AutoCAD-build work. READ (130) and FALLBACK/WRITE are the more automatable front.

## Dependency wrinkle (carried from M08A-T01)

Implementation tickets do not merge to main (only MERGE tickets do), but downstream tickets consume upstream
outputs. Until a wave's MERGE ticket runs, a dependent ticket's worktree must branch off its **dependency
branch**, not `main` (as M08A-T02 here branched off `cados/M08A-T01`). The MERGE waves are the points where
work re-bases onto main.
