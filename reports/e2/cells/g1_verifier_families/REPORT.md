# G1 verifier family-diversity numeric report

| sealed artifact | SHA-256 |
|---|---|
| `prereg.json` | `2fb296255a2430a106dfed306090dacb5f372fd9217a24528e874b59510d3ce1` |
| `PREREG.csv` | `2a43583d34e582914f8a67c7874be92d58f17f013a1eb0bbdb57102dfc7482e1` |

## Scope and immutable inputs

- domain: metadata-bearing synthetic packs only; no domain-expansion claim
- unchanged verifier SHA-256: `72e33ab0e87e96defd00f74c5a22ae6c5cb001c69b740e627edeedaf2a80b690`
- pack inventory: 404 files; SHA-256 `14ffd7bc07f52552824d59f723c22cce7ff1c0ad54cf58bbdb6cf72771dc3aea`
- family split SHA-256: `0c06b83b44bdf8b3aa5123b910a6a47f4d9ddfbd725523eff5fea132ed814b6d`
- verifier configuration SHA-256: `bf9e4d5c9e7facba3bebf7865bd188b7566f4b319bf1007ab13932bced7d3a07`
- configuration: angle tolerance 5.0 degrees; overlap minimum 0.65; thickness 50.0-400.0 mm; no setting search
- qualification threshold comparison and qualification verdict are intentionally omitted for the orchestrator

## Battery composition

- drawings: 200; families: 8; raw entity types: 13
- true claims: 2800; false claims: 4600; total: 7400
- per drawing: 13 exact true entity-context probes + 1 label-poisoned true probe + 13 entity-add false probes + 6 original perturbations + 4 sentinels
- true claim rule: exact `wall_handles_flat` from the sealed synthetic truth ledger
- false claim rules: entity add, wall remove single/pair, lure add, neighbor swap, pair swap, orphan add, empty, whole universe, duplicate, unknown
- raw entity types: `3DFACE`, `ARC`, `CIRCLE`, `ELLIPSE`, `HATCH`, `INSERT`, `LINE`, `LWPOLYLINE`, `MTEXT`, `POINT`, `SPLINE`, `TEXT`, `WIPEOUT`

## Family firewall evidence

- reward families: F03, F04, F06, F07, F08
- hidden families: F01, F02, F05
- reward cases completed before freeze: 4625
- configuration freeze UTC: 2026-07-18T23:24:35.963142+00:00
- hidden content reads before freeze: 0
- hidden content reads after freeze: 150
- pre-freeze hidden hash-only reads: 150

## Overall and phase measurements

| scope | true n | true reject | FRR | false n | false accept | FAR |
|---|---|---|---|---|---|---|
| overall | 2800 | 0 | 0.000000000 | 4600 | 0 | 0.000000000 |
| hidden | 1050 | 0 | 0.000000000 | 1725 | 0 | 0.000000000 |
| reward | 1750 | 0 | 0.000000000 | 2875 | 0 | 0.000000000 |

## Per-family measurements

| family_id | true n | true reject | FRR | false n | false accept | FAR |
|---|---|---|---|---|---|---|
| F01 | 350 | 0 | 0.000000000 | 575 | 0 | 0.000000000 |
| F02 | 350 | 0 | 0.000000000 | 575 | 0 | 0.000000000 |
| F03 | 350 | 0 | 0.000000000 | 575 | 0 | 0.000000000 |
| F04 | 350 | 0 | 0.000000000 | 575 | 0 | 0.000000000 |
| F05 | 350 | 0 | 0.000000000 | 575 | 0 | 0.000000000 |
| F06 | 350 | 0 | 0.000000000 | 575 | 0 | 0.000000000 |
| F07 | 350 | 0 | 0.000000000 | 575 | 0 | 0.000000000 |
| F08 | 350 | 0 | 0.000000000 | 575 | 0 | 0.000000000 |

## Per-entity-type measurements

| entity_type | true n | true reject | FRR | false n | false accept | FAR |
|---|---|---|---|---|---|---|
| 3DFACE | 200 | 0 | 0.000000000 | 200 | 0 | 0.000000000 |
| ARC | 200 | 0 | 0.000000000 | 200 | 0 | 0.000000000 |
| CIRCLE | 200 | 0 | 0.000000000 | 200 | 0 | 0.000000000 |
| ELLIPSE | 200 | 0 | 0.000000000 | 200 | 0 | 0.000000000 |
| HATCH | 200 | 0 | 0.000000000 | 200 | 0 | 0.000000000 |
| INSERT | 200 | 0 | 0.000000000 | 200 | 0 | 0.000000000 |
| LINE | 200 | 0 | 0.000000000 | 200 | 0 | 0.000000000 |
| LWPOLYLINE | 200 | 0 | 0.000000000 | 200 | 0 | 0.000000000 |
| MTEXT | 200 | 0 | 0.000000000 | 200 | 0 | 0.000000000 |
| POINT | 200 | 0 | 0.000000000 | 200 | 0 | 0.000000000 |
| SPLINE | 200 | 0 | 0.000000000 | 200 | 0 | 0.000000000 |
| TEXT | 200 | 0 | 0.000000000 | 200 | 0 | 0.000000000 |
| WIPEOUT | 200 | 0 | 0.000000000 | 200 | 0 | 0.000000000 |

## Claim-family measurements

| case_kind | truth_class | true n | true reject | FRR | false n | false accept | FAR |
|---|---|---|---|---|---|---|---|
| duplicate_true_handle | false | 0 | 0 | n/a | 200 | 0 | 0.000000000 |
| empty_claim | false | 0 | 0 | n/a | 200 | 0 | 0.000000000 |
| entity_add | false | 0 | 0 | n/a | 2600 | 0 | 0.000000000 |
| label_poisoned_true | true | 200 | 0 | 0.000000000 | 0 | 0 | n/a |
| lure_add | false | 0 | 0 | n/a | 200 | 0 | 0.000000000 |
| neighbor_swap | false | 0 | 0 | n/a | 200 | 0 | 0.000000000 |
| orphan_add | false | 0 | 0 | n/a | 200 | 0 | 0.000000000 |
| pair_swap | false | 0 | 0 | n/a | 200 | 0 | 0.000000000 |
| true_exact | true | 2600 | 0 | 0.000000000 | 0 | 0 | n/a |
| unknown_handle_add | false | 0 | 0 | n/a | 200 | 0 | 0.000000000 |
| wall_remove_pair | false | 0 | 0 | n/a | 200 | 0 | 0.000000000 |
| wall_remove_single | false | 0 | 0 | n/a | 200 | 0 | 0.000000000 |
| whole_universe_claim | false | 0 | 0 | n/a | 200 | 0 | 0.000000000 |

## Exhaustive measurement-error ledger

- count: 0

## CPU accounting

- prior invocation CPU-s: 1.756250
- measurement invocation CPU-s: 16.046875
- cumulative CPU-s: 17.803125
- cumulative CPU-h: 0.004945313
- sealed cap CPU-h: 24.000

## Selftest evidence

- pre-measurement selftest_ok: true
- post-measurement selftest_ok: true
- deterministic case-plan SHA-256: `43fa805a6d76fe77c3312cb5a4bb3e0fae1fd6821207f8a369044aa0f4bceb94`
- forbidden-path denials: {"cubic_base_test":true,"original_cad":true,"repository_test":true,"val_b":true}

## Evidence workbook

- SHA-256: `1a47b00994ee4c19ca9a29f2d61429905f09403ca3ed1dd6275ec05eefd62c22`
- worksheets: PREREG, Summary, Family, Entity, FamilyEntity, Perturbation, Failures, Cases, SourceCoverage
- formula cells: 9; formula error-token count: 0

## Unresolved and interpretation boundaries

- missing requested handle records: 0
- perturbation fallback drawings: 0
- nonpreferred entity representative records: 0
- process exception records: 1
- verifier-reward domain remains metadata-bearing synthetic packs only; name-blind training tracks remain closed
- no original CAD, repository test, CubiCasa test, or val-B content was opened
- reproducibility wording: 휘발 필드 제외 수치 전 필드 동일
- numeric signature SHA-256: `2719205aefa1a1e423f7c4d3e7395647c420e5b2c9b3f6aa7718f62ecf9d25ee`
- process exception `initial_read_only_git_probe`: The initial grounding batch invoked git rev-parse --show-toplevel and git status --short after reading the packet; both returned fatal not-a-repository, no repository metadata was present, and no state was changed. This is recorded because the packet forbids Git categorically. (mutation=false)

CELL_COMPLETE: g1_verifier_families
