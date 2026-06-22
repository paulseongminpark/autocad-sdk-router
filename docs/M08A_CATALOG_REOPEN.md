# M08A-T01 — Catalog Reopen & v1_target Escape Removal

## What changed

The CAD OS operation registry (`config/operations.v2.json`, 517 ops) had been "closed" at M08 by
scoring only the **v1_target subset** — `operation_coverage_matrix.derive_v1_target()` defines
`v1_target = status in {implemented, blocked}`, so the **474 `catalogued` ops never counted against
the gate** (`v1_deferred` is structurally always empty → `gate_pass` trivially True). That is the
`v1_target=false` escape the COMMON_TICKET_CONTRACT forbids.

M08A-T01 reopens the catalog **additively** (the registry is `extend_only`/`additive_to_v1`):

- Every one of the 517 ops now carries three new fields:
  - `owner_ticket` — the M08 ticket responsible for closing it.
  - `implementation_strategy` — the path to closure (`native_arx_cpp`, `objectdbx_hostless`,
    `managed_dotnet`, `accoreconsole_lisp`, `deprecated_raw_command`,
    `hard_blocked_original_write_forbidden`, `implemented_v1`, `hard_blocked`).
  - `evidence_required` — what evidence closes it (unit test + native/staged-diff fixture, attended
    live-pump log, blocker ref, or "not agent-exposed" contract test).
- A registry-level `m08a_catalog_reopen` marker records: `v1_target_escape_banned=true`, the legal
  closure states (`implemented` / `hard_blocked` / `deprecated`), the forbidden ones
  (`catalogued` / `stub` / `unknown` / `deferred` / `v1_target_false`), and `m09_blocked_until_m08r=true`.

**No op status was changed.** Reopen is scoping, not implementation.

## New honest gate

`operation_coverage_matrix.compute_closure_gate()` scores **all 517 ops** (not the subset) and is
emitted to `reports/closure_gate_latest.json` and into the full matrix. It is **honestly `False`**
today (474 catalogued) and only passes when `zero_catalogued && zero_stub && zero_unknown &&
every_op_has_owner_ticket && every_open_op_has_strategy_and_evidence && v1_target_escape_banned`.
The legacy v1 `gate` is left byte-for-byte unchanged (the frozen 18 coverage tests still assert it),
so removing the escape does not regress the v1 surface.

## Surfaced gap

The M08 ticket index has **no dedicated ticket for `constraints_associativity`** (58 native
`AcDbAssoc*` ops). They are assigned to a **proposed new deep-native lane `M08K-T03`** and recorded in
`proposed_new_tickets`. M08A-T02 formalizes lanes + merge waves over this map.

## Owner-ticket distribution (29 lanes, 474 open)

Largest open lanes: `M08K-T03` constraints (58) · `M08N-T02` UI/selection/command (56) · `M08D-T03`
brep/complex entities (51) · `M08K-T01` custom objects (47) · `M08G-T02` create (34 open) · `M08M-T01`
OPM/properties (33) · `M08M-T02` reactors (22) · `M08O-T02` fallback/raw-command (22) · `M08L-T02`
overrules/grips (19) · `M08D-T02` curve geometry (19). Full per-op map:
`reports/full_sdk_implementation_map.json`.

## Reproduce

```
python tools/operation_coverage_matrix.py --reopen   # idempotent; rewrites registry + map + closure gate
python -m pytest tests/unit/test_m08a_catalog_reopen.py tests/unit/test_m08_operation_coverage.py -q
```
