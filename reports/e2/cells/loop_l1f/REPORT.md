# E2 loop L1f Phase B numeric evidence

Witness commit citation: `c896068` (git verification not performed because the packet prohibits git).
Sealed `prereg.json` SHA-256: `76AC2A58D74C644A3BF7897325818F1E12151596DC3316BA7CA488BDEB207861`.
Sealed `PREREG_SEALED.csv` SHA-256: `94356AF8F4D219AF65A96825E3A08B29245454EDA1B29B2C3AE83F4B19A8F266`.
Sealed `SEAL_MANIFEST.txt` SHA-256: `2C16BA1E66A2CA491364DD533A914F94592E3EC1558ED35A8A1D02E077F92501`.

This report records executed numeric evidence only. It does not emit a gate verdict.

## Estimator and honest envelope

Revision: `c1v7_two_tier_frozen_surface_non_dilution`. Detection freezes the complete declared surface before canonicalization. Tier-A attenuation uses `q_ratio=Q_clean_support*product_s(1-floor_s); q_reference=Q_clean_span_support*product_ratio_s(1-floor_s)*product_span_s(1-floor_s); floors are per suspicious signal and contain no candidate-count denominator; Tier B affected paths are exactly 0/NONE`.
Measured honest corpus: 400 scenes, 2008 anchors, maximum ratio deviation 1.456323723963341e-13 tau, raw-span/geometry mismatches 0.
O1/O2 status downgrades: 0; coverage losses: 0.

## Property and non-dilution execution

Randomized cases: 630; total with third-fleet regressions: 641; families: 9; strata: 5; third-fleet classes: 11.
Fixed-suspicion cases: 11; executed N-sweep rows: 55 at N={0,3,10,20,40}, with conceptual N-to-infinity formula recorded per case.

## Named regression execution

Seat4 targeted cases: 5; v5 rises: 0.
Seat4 window: 1494 parent cases, 747 v4 known-positive cases, 0 v5 rises within those cases.
Lens1 W000002/B5 cases: 2; both complete frozen surfaces and rule transcripts are in `fleet_probe_results.json`.
Lens2 P5: 2000 parent cases, 50 reproduced v4 known-violation cases, 50 prevented by v5, 44 total v5 rises across the full parent hunt.
P4 reference-confidence loss: 0; status downgrades: 0.
Known-adverse information-limit classifications: 0.

## Replay disclosure

Replay scenes: 400; full per-scene/per-field rows: 218469; all-version zero-delta rows: 32538.
v5 HIGH scenes: 360; HIGH estimates within 5%: 360 (1.000000); minimum cohort-scale HIGH coverage: 0.800000.

## Witness and predicate records

Upward classifications: 90; violations: 0; manual suppressions: 0; unclassified fields: 0; uncovered declared fields: 0.
Executed predicates: 15; counterexamples observed false: 15.
Each witness row contains the complete ordered 18-rule transcript, explicit zero counts, measurements, frozen surface, and a surface-specific generation narrative.

## Read-only and artifact records

Source-manifest mismatches before/after execution: 0.
Original CAD and test surfaces were not accessed. No repository file or Phase-A seal artifact was written.

| Artifact | SHA-256 |
|---|---|
| `PREREG_SEALED.csv` | `94356AF8F4D219AF65A96825E3A08B29245454EDA1B29B2C3AE83F4B19A8F266` |
| `SEAL_MANIFEST.txt` | `2C16BA1E66A2CA491364DD533A914F94592E3EC1558ED35A8A1D02E077F92501` |
| `c1v7_results.json` | `ABE36EBCD79408552C672471933BB8671DF96B9C35E45B9777080904F4ECFCFE` |
| `evidence.xlsx` | `B02673CF7037CF2DE210B119CEA2BEF3F0DABD5977CE2DCF04267C389A13D72A` |
| `feyerabend_c1_v5.py` | `6D1D0AA113AF1045EAA54FE0504032B86AA217251BCDF5454E61CA184164C489` |
| `fleet_probe_results.json` | `1FFE3454E9BFFF3E5743BEB95DACFD78A7DC8D96635FAA04836A2A6B932C7827` |
| `honest_envelope.json` | `272709E1D0DA72E54629264F5174A09F9A5C7E3EF3606673C7316DE3161B3247` |
| `loop_l1f.py` | `461B03EDE7B112DCF32AD2FF5043C88FF307DFCC90F5FFA5C35DCDD2238563C2` |
| `predicate_registry.json` | `BDA4B7C822E78557079C99000737E2A2355C61090808A8DCF379E9566D0A76BE` |
| `prereg.json` | `76AC2A58D74C644A3BF7897325818F1E12151596DC3316BA7CA488BDEB207861` |
| `replay_delta.json` | `0B83EC925075DA43BA10437A3BEA7AA1AE9DDB41C873EB1B167D4C330E9856C0` |
| `witness_classifications.json` | `5CACB35D4267518A77747406E1B3416FE0C367B645DF097B7BADA5652EB68400` |

Complete unabridged case and replay records are in the JSON artifacts; the workbook is a numeric index to those records.

LOOP_COMPLETE: L1f
