# M08A-T01 — PLAN (plan-mode artifact)

TICKET: M08A-T01 — Reopen catalog and remove v1_target escape
BRANCH: cados/M08A-T01
WORKTREE: D:\dev\99_tools\autocad-sdk-router_M08A-T01
DEPENDS_ON: current main (b2b8fa2)

## Problem (ground truth)

Registry `config/operations.v2.json` has **517 ops**: implemented 41, blocked 2, **catalogued 474**, stub 0, unknown 0.
The "M08 PASS" closed only a **v1_target subset**: `operation_coverage_matrix.derive_v1_target()` defines
`v1_target = status in {implemented, blocked}`, so the 474 catalogued ops are structurally excluded from the gate
(`v1_deferred` is always empty → `gate_pass` trivially True). The docstring admits this is "future-version native
capability ... NOT v1 targets." **This is the `v1_target=false` escape** the COMMON_TICKET_CONTRACT forbids.

## Goal

Reopen all catalogued ops into scope; give every op an `owner_ticket`, `implementation_strategy`, `evidence_required`;
ban the v1_target escape as a closure (add an honest full-coverage closure gate that fails while catalogued/stub > 0);
generate `reports/full_sdk_implementation_map.json`; record that M09 is blocked until M08R.

## Constraints

- CHANGE_ONLY: `config/` `reports/` `docs/` `tools/operation_coverage_matrix.py` `tests/unit/test_m08a_*`
- ADDITIVE only (`extend_only:true`, `additive_to_v1:true`). Do NOT change any op `status`. Do NOT touch any other tool.
- `config/operations.v2.json`: preserve BOM (utf-8-sig) + indent=2 + no trailing newline.
- Must NOT break the 18 existing tests in `test_m08_operation_coverage.py` (NOT in CHANGE_ONLY). In particular
  `test_gate_passes` requires every key in the `gate` dict to be True → I must add a SEPARATE `closure_gate`, never
  mutate the v1 `gate`.
- No original DWG write. No secrets. No fake PASS.

## Files to edit

1. `tools/operation_coverage_matrix.py` (ADD, do not break existing):
   - `OWNER_TICKET_RULES`: deterministic (family, id-prefix/keyword) → owner_ticket map covering all 42 tickets.
   - `assign_owner_ticket(op)`, `impl_strategy(op)`, `evidence_required(op)`.
   - `reopen_registry(doc)`: write `owner_ticket`/`implementation_strategy`/`evidence_required` into every op (additive).
   - `build_sdk_implementation_map(doc)`: emit `reports/full_sdk_implementation_map.json`.
   - `closure_gate(...)`: honest full-coverage gate (zero_catalogued/stub/unknown/deferred, every_op_has_owner_ticket,
     every_catalogued_has_strategy_and_evidence, m09_blocked_until_m08r). Emitted into the matrix + a new
     `reports/closure_gate_latest.json`. Does NOT feed the legacy `gate`.
   - CLI `--reopen` path that mutates the registry + writes the map (idempotent, deterministic).
2. `config/operations.v2.json`: +3 additive fields per op (via `--reopen`).
3. `reports/full_sdk_implementation_map.json`, `reports/closure_gate_latest.json` (generated).
4. `tests/unit/test_m08a_catalog_reopen.py`: assert every op has owner_ticket/strategy/evidence; closure_gate is
   honestly False while catalogued>0; v1 escape banned (no closure with catalogued>0); existing 18 tests still pass;
   raw-command ops close as deprecated strategy; m09_blocked_until_m08r True.
5. `docs/`: short note `docs/M08A_CATALOG_REOPEN.md` documenting the reopen + mapping + the surfaced gap.

## Owner-ticket mapping (family + id-prefix → ticket)

- objectdbx_database: inspect/infra/transform/write→C-T01; transaction.*→B-T03
- inspect (impl): C-T01 (already implemented)
- symbol_tables_dictionaries: layer/linetype/textstyle/blockrecord→C-T02; dimstyle/ucs/view/vport/regapp→C-T03;
  xrecord/xdata/dict/acdb→E-T03
- entities: inspect.*→D-T01; inspect.curve→D-T02; write.{dim,leader,text,mtext,table,mleader}→H-T01; write.hatch→H-T02;
  other write.*→G-T02; modify.*→G-T03
- geometry_kernel: compute.*→D-T02; write.*→G-T02; modify.*→G-T03
- brep_solids: inspect/traverse/compute→D-T03; edit.*→G-T03
- blocks_xrefs_clone: →E-T01; xref/layout→E-T02
- layouts_plot_publish: plot.*→I-T01
- render: →I-T01 ; diff: →I-T02 ; graphics_system: render.draw/context→L-T01; grips→L-T02
- live: →J-T01/J-T02 (mostly implemented)
- custom_objects_protocols: extend.*→K-T01; inspect.*→K-T01; overrule.*→L-T02
- constraints_associativity: **NO ticket in index → GAP → propose new lane M08K-T03-constraints (deep native).**
- com_activex: →O-T01 (OPM-tagged ids→M-T01)
- ui_customization: editor.*→N-T02 (OPM/property ids→M-T01)
- editor_input: input/prompt/interact→N-T01; select→N-T02; command.queue→deprecated(raw)
- runtime_commands: module.*→O-T02; command.register→N-T02
- reactors_events: react.*→M-T02
- active_document_write_original: command.invoke.*→deprecated(raw); doc.*→J-T03
- write/extend/validate/patch/apply/query (all implemented): natural ticket, strategy=implemented_v1

## implementation_strategy / evidence_required

- status implemented → `implemented_v1` / existing tests+evidence_refs
- status blocked → `hard_blocked` / blocker_ref + evidence
- raw-command op → `deprecated_raw_command` / contract test that it is NOT agent-exposed
- write_original op → `hard_blocked_original_write_forbidden` / safety blocker
- else by engine_tier: native_arx_only→`native_arx_cpp`; objectdbx_capable→`objectdbx_hostless`;
  managed_also→`managed_dotnet`; accoreconsole_lisp_also→`accoreconsole_lisp`
- evidence_required by write_level: read→unit_test+native_extraction_fixture; write_copy→unit_test+staged_diff(original
  unchanged); live_edit→attended_live_pump_log

## Validate

- `python tools/operation_coverage_matrix.py --reopen` runs clean, idempotent.
- `python -m pytest tests/unit/test_m08_operation_coverage.py tests/unit/test_m08a_catalog_reopen.py -q` → all pass.
- 0 ops without owner_ticket; closure_gate honestly False (catalogued=474); v1 `gate` still True (back-compat).

## Outputs

reports/tickets/M08A-T01.{md,json} · handoff/tickets/M08A-T01.zip · packets/tickets/M08A-T01.md · commit on
cados/M08A-T01 · PR (gh available) else handoff/pr/M08A-T01.patch.
