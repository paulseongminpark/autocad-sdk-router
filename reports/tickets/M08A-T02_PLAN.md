# M08A-T02 — PLAN (plan-mode artifact)

TICKET: M08A-T02 — Generate execution DAG and ticket inventory
BRANCH: cados/M08A-T02 (off cados/M08A-T01 — depends on T01's reopened registry/map)
WORKTREE: D:\dev\99_tools\autocad-sdk-router_M08A-T02
DEPENDS_ON: M08A-T01

## Goal

Over the M08A-T01 implementation map (`reports/full_sdk_implementation_map.json`), generate the operation
execution DAG and the ticket inventory: assign every op a parallel lane and every lane a merge wave.

## Constraints

- CHANGE_ONLY: `reports/` `docs/` `packets/tickets/` `handoff/tickets/`  → NO code, NO config, NO tools.
- Generator runs as a throwaway (outside the worktree, in /tmp); only the generated reports + docs + ticket
  bookkeeping are committed.
- Must not change any op or the registry. Reports must parse (valid JSON).

## Lanes (phase groups) → merge waves (from the 6 MERGE tickets)

- foundation: M08A → pre-merge (prerequisite)
- infra:      M08B → pre-merge (prerequisite for all families)
- READ:       M08C, M08D, M08E, M08F → MERGE-M08-READ
- WRITE:      M08G, M08H            → MERGE-M08-WRITE (after READ)
- VISLIVE:    M08I, M08J            → MERGE-M08-VISLIVE (after relevant D/G gates)
- NATIVE:     M08K, M08L, M08M, M08N → MERGE-M08-NATIVE (after infra)
- FALLBACK:   M08O                  → MERGE-M08-FALLBACK (after infra)
- FINAL:      M08P, M08Q, M08R      → MERGE-M08-FINAL (after all)

Wave order: foundation → infra → READ → {WRITE, VISLIVE, NATIVE, FALLBACK} → FINAL.

## Ticket DAG (DEPENDS_ON from 03_TICKET_INDEX + the proposed M08K-T03)

A-T01←main; A-T02←A-T01; B-T0x←A; C-T0x←B; D-T01←B, D-T02/3/4←D-T01; E-T0x←B,D; F-T01←C,D,E,
F-T02←F-T01; G-T01←B,D,E, G-T02/3←G-T01; H-T0x←G; I-T01←D,G, I-T02←I-T01; J-T01←B,M07B, J-T02←J-T01,
J-T03←J,G; K-T01←B, K-T02←K-T01, K-T03(proposed)←B; L-T01←K, L-T02←K,L; M-T01/2←K; N-T01/2←J; O-T0x←B;
P-T01←(C..O merged), P-T02←P-T01; Q-T0x←P; R-T01←Q.

## Outputs

- `reports/operation_execution_dag.json` — nodes=tickets (lane, wave, depends, op_count, open), edges=deps,
  merge_waves with order + members + wave deps.
- `reports/ticket_inventory.json` — per-ticket inventory: lane, merge_wave, depends_on, op_count, open/impl/
  blocked, families, strategies; + per-op lane/wave index; + validation block.
- `docs/M08A_EXECUTION_DAG.md` — human summary (wave order, lane table).
- `reports/tickets/M08A-T02.{md,json}` · `packets/tickets/M08A-T02.md` · `handoff/tickets/M08A-T02.zip`.

## Validate

- every op (517) has a lane AND a merge wave.
- every lane has a merge dependency (a merge wave it belongs to).
- both reports parse as JSON.
- DAG is acyclic; every non-root ticket has ≥1 dependency.
