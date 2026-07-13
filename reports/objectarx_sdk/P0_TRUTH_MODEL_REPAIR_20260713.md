# P0 — Truth-model repair (ObjectARX SDK certification arc)

**Status: PASS** · 2026-07-13 · owner: aclaude (Paul ultracode mandate)
Follows codex gpt-5.6-sol xhigh advice (`CODEX_SOL_ADVICE_20260713.md`), critical-path step P0.

## What was wrong (two truth-model defects)

1. **`tools/reconcile_native_registry.py`** — `RE_FAMFILE = r'^m08([a-z]+)_handlers\.inc$'`
   discovered only the 11 `m08*` family `.inc` files. The 5 non-m08 families that
   `familyHasOp()` in `AriadneNativeJob.cpp:6163` admits all the same
   (`w6_layerstate` 4, `w6_dynblk` 3, `w6_section` 3, `materials_read` 3,
   `annoscale_read` 2 = **15 ops**) were silently dropped from `all_coded_ops()`,
   under-counting the native live-gate universe **420 → should be 435** and
   leaving `check_vocab_lockstep` able to falsely report `no_live_hasop` for any
   patch surface pointing at one (latent; not yet active because no patch op maps
   to those 15 today).

2. **`tools/operation_coverage_matrix.py`** — `catalog_total_ops: 480` /
   `catalog_classified_ops: 480` were hardcoded stale snapshots (pre-M08/w6/w7),
   plus a `"517-operation"` render string and a `474`/`517` comment. The real
   registry total is **551** (FM9: unsourced number in a generated artifact).

## Fix (surgical; derive, don't hardcode)

- `reconcile_native_registry.py`: generalized `_hasop_body`/`parse_family` to take
  the gate-fn name; added `_NON_M08_FAMILIES` (the 5 explicit non-m08 gates);
  `discover_families()` now yields all **16** families; main() label uses per-family
  `info["label"]`. `evidence_for()` untouched — the 15 non-m08 ops are all already
  `implemented`, so they never produce a flip (no wrong-path evidence synthesis).
- `operation_coverage_matrix.py`: `catalog_total_ops`/`classified`/`unclassified`
  now derive from `t["total"]`/`t["unknown"]`; render string + comments de-hardcoded.

## Lock (make future drift a hard failure)

- New `tests/unit/test_reconcile_family_gate_parity.py` (3 tests): asserts the
  reconcile family-gate set == `familyHasOp()` gate calls in the .cpp, floors the
  family count at 16, and checks every non-m08 gate body parses to a non-empty set.

## Evidence (commands + outputs)

- `python tools/reconcile_native_registry.py` → `TOTALS: coded=435 flips=0
  overlaps=435 conflicts=0 drift=0`; VOCAB LOCKSTEP OK; EXIT 0.
- `python tools/operation_coverage_matrix.py` → `total: 551 implemented: 489
  blocked: 62 catalogued: 0 stub: 0 unknown: 0`; GATE PASS: True. Regenerated
  `reports/operation_coverage_latest.json`: `catalog_total_ops: 551`,
  `catalog_classified_ops: 551`, `catalog_unclassified_ops: 0`, `consistent: True`.
- `python -m unittest discover -s tests/unit` → **Ran 1191 tests OK (skipped=6)**.

## Corrected truth model (foundation for P1–P6)

- **551** ops total = **489 implemented** + **62 blocked** (0 catalogued/stub/unknown).
- The "62 blocked" ARE the unwired gap (com_activex, runtime_commands,
  constraints_associativity, etc.) — Paul's "미연결된 것도 다 하라" target.
- Reconciles exactly with sol's independently-derived "489 declared implemented".
- Native family live-gate = **435** ops across **16** families + the pre-M08
  `kAriadneNativeOperationTable`.
- risk_class: read_safe 366 · staged_write 129 · live_edit 50 · raw_command 6.

## Deferred to later P-steps (not P0 blockers)

- sol's "compiled `OperationDescriptor` tables > source-scraping" — robustness
  upgrade; the parity test now guards the scraping approach, so numbers are correct
  and drift-locked. Revisit as hardening.
- Catalog fields `kind` / `dispatchable` / `verification_lane` — folded into P5
  (runtime_commands 16 → `kind=module_event, dispatchable=false`).
- `reports/registry_coverage_latest.json` "37" stale snapshot — separate artifact;
  superseded by `operation_coverage_latest.json` (now 551-correct).
