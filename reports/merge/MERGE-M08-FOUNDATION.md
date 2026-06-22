# MERGE-M08-FOUNDATION — merge record

- **Role:** merge_executor (single-writer to main)
- **Date:** 2026-06-22
- **Scope:** M08A foundation (M08A-T01, M08A-T02). The packet's 6 named MERGE tickets cover the family waves
  (READ/WRITE/VISLIVE/NATIVE/FALLBACK) + FINAL; the M08A-T02 DAG defines foundation as a pre-merge wave — this
  record covers that foundation pre-merge to main.

## Merged (dependency order)

1. **PR #1** `cados/M08A-T01` → main (reopen catalog + ban v1_target escape). MERGED 2026-06-22T07:51:08Z.
2. **PR #2** `cados/M08A-T02` → main (execution DAG + ticket inventory). Base retargeted `cados/M08A-T01`→`main`,
   then merged. MERGED 2026-06-22T07:51:13Z.

main HEAD = **c554f23** (GitHub merge commit; parents `85bfbb0` = PR #1 merge of `b7a201e`, and `88a6b95` =
PR #2 tip). Foundation commits `5c4fed2` / `b7a201e` / `ecf9637` / `88a6b95` are all reachable from main.

## Rejected

- none.

## Post-merge gate (runbook)

- `python -m pytest tests/unit -q` → **266 passed** (incl. 18 frozen coverage + 11 M08A reopen tests).
- registry coverage consistent (asserted by `test_registry_cadctl_consistent`): unknown 0, stub 0, implemented ≥41.
- `operation_coverage_matrix` → v1 **GATE PASS = True**; **closure_gate_pass = False** (honest, catalogued 474).
- by_status on main: implemented 41 · blocked 2 · catalogued 474 · stub 0 · unknown 0.

## REJECT_IF audit (all clear)

- original DWG changed: NO · secrets staged: NO · raw command agent-exposed: NO (raw ops tagged
  `deprecated_raw_command`, not exposed) · existing 29 frozen ops regress: NO (v1 gate True) ·
  catalogued/stub/unknown increased without explanation: NO (catalogued stable 474 — reopen is additive scoping,
  not implementation) · ticket report missing: NO · tests fail: NO.

## State after merge

- Foundation (reopened catalog + owner_tickets + DAG + closure_gate) is the base on main for all family lanes.
- `closure_gate` honestly False until the 474 catalogued ops are implemented across M08B-O (M09 blocked until M08R).

[MERGE-M08-FOUNDATION RESULT]
STATUS: PASS
MERGED: PR #1 (cados/M08A-T01), PR #2 (cados/M08A-T02)
REJECTED: none
TESTS: pytest tests/unit -q = 266 passed; v1 gate PASS; closure_gate honestly False (catalogued 474)
MAIN_COMMIT: c554f23
NEXT: M08B (native dispatcher/serializer/lock infra) in a build-capable checkout — then family waves READ→...→NATIVE
[/MERGE-M08-FOUNDATION RESULT]
