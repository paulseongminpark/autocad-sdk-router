# LEX Ledger

## Purpose

This is the measurement-contract precedent ledger for DWG round-trip fidelity.

Every decision about "which notational differences count as equivalent, and
under what substitute verification" is a precedent. Precedents legislated
once must not be re-litigated ad hoc in scattered prose (reports, code
comments, chat) — they live here, itemized, so future work can cite an id
instead of re-deriving the same conclusion.

**Append-only.** New entries are appended at the end; existing entries are
never rewritten. If an entry's status changes (e.g. a `candidate` becomes
`legislated`, or a `legislated` rule is later `retracted`), the status
transition is logged in-place on that entry (update the `status` field and
note the transition in `refs` or observation, keeping the original facts
intact) — the entry's id and original observation are never deleted or
reworded.

## Schema

Each entry uses the following fields, in order:

- `id` — stable identifier, `LEX-NNNN`, monotonically increasing, never reused.
- `title` — short name for the precedent.
- `observation` — the measured fact that motivated this entry, citing the
  producing run/artifact.
- `rule` — the legislated equivalence/exclusion this entry establishes, or
  the hypothesis this entry rejects.
- `substitute_verifier` — what still verifies the aspect this rule
  excludes/quotients away (or `n/a` if the entry is a rejection with no
  legislated rule).
- `status` — one of: `candidate` | `legislated` | `rejected` | `retracted`.
- `refs` — files/commits/runs that back this entry.

## Entries

### [LEX-0001] *D derived-cache exclusion

- **observation**: `*D` anonymous blocks are per-dimension rendered caches; a rebuild's dimensions mint fresh `*D` names, so name-matched def compare is a category error (`runs/e2e_1dwg_R4n_origin_20260709 interior_diff.json` `derived_cache_excluded`: `a_def_count 113`, `b_def_count 113`).
- **rule**: exclude `^\*D\d+$` defs from name-matched interior compare, account them honestly in `totals.derived_cache_excluded`.
- **substitute_verifier**: L5 `dim_semantic_gate` verifies the dimension entities themselves (113/113).
- **status**: legislated
- **refs**: `tools/blockdef_diff.py`, `dim_semantic_gate.json`

### [LEX-0002] hatch scale-baking equivalence

- **observation**: original hatches extract `pattern_type=1` with rows scale-BAKED (measured base `[14135,-7335]`, offset `[-300,~0]` at scale `300`) while `.pat` replay rebuilds extract `pattern_type=2` with UNIT rows (base `[47.1167,-24.45]`, offset `[-1,~0]`) — `a = b * scale`, identical render (R4l residue analysis).
- **rule**: canonical form divides type-1 rows by `pattern_scale` and drops `pattern_type` (provenance, not geometry).
- **substitute_verifier**: visual gate lane.
- **status**: legislated
- **refs**: `tools/blockdef_diff.py::_canonical_hatch_geometry`

### [LEX-0003] serialization quantization

- **observation**: `.pat` replay serializes at `%.10g` causing ~3e-11 residue vs full doubles (measured).
- **rule**: quantize canonical pattern rows at `1e-6` in unit pattern space after normalization.
- **substitute_verifier**: quantization grid is far coarser than noise and far finer than any real pattern difference (documented in code comment).
- **status**: legislated
- **refs**: `tools/blockdef_diff.py::_q`

### [LEX-0004] phase-carrier equivalence (base-baked vs HPORIGIN)

- **observation**: per-hatch pattern phase lives EITHER baked in row base points (originals: 233/233 residual pairs differ by one common per-hatch base vector, census `pattern_origin [0,0]`) OR in the HPORIGIN field over zero-phase rows (rebased-`.pat` replay) — same rendered lattice, two carriers (`runs/e2e_1dwg_R4n_origin_20260709` census probe, 2026-07-09; fix commit `5014d1b`).
- **rule**: canonical rows carry intra-pattern structure only (rebased against `rows[0].base`); effective phase folds to `pattern_phase = base1/divisor + pattern_origin/scale`; `pattern_origin` dropped after folding. A REAL phase difference still mismatches after folding.
- **substitute_verifier**: visual gate lane + old-vs-new pairwise transition census equal->unequal 0/258.
- **status**: legislated
- **refs**: `tools/blockdef_diff.py`, `tools/patch_engine.py`, `tools/patch_ops/blocks.py`, commit `5014d1b`

### [LEX-0005] origin-field replay hypothesis — REJECTED (negative result, preserved)

- **observation**: hypothesis "replaying the census `pattern_origin` field through `setOriginPoint` will collapse the hatch phase residue" was implemented and flown as R4n; headline landed EXACTLY equal to R4m (`26,818/27,130 = 0.9884998`, identical residual composition per def), refuting the hypothesis and exposing the true mechanism (row-base baking + seed-shared `.pat`, see LEX-0004).
- **rule**: none legislated — the value of this entry is the preserved refutation: a repair claim is proven only by end-to-end headline movement, never by the commit's existence.
- **substitute_verifier**: n/a
- **status**: rejected
- **refs**: `runs/e2e_1dwg_R4m_wipeout_20260709`, `runs/e2e_1dwg_R4n_origin_20260709`


### [LEX-0006] population control before any cross-run claim

- **observation**: R4o landed 32,545/32,551 = 0.9998 and briefly read as a breakthrough; population forensics showed only 91/294 def-name overlap with R4n and a 245-vs-407 census mismatch, and `identity.json` proved the run had executed against `tests/fixtures/native_sample.dwg` (launch omitted `--dwg`; capstone default), not `1.dwg` (`runs/e2e_1dwg_R4o_phase_20260709`, 2026-07-09).
- **rule**: no cross-run fidelity claim (record, ratchet, prereg adjudication) is admissible until source identity (sha256) AND def-population identity are verified; a launch that omits the source argument is an invalid run regardless of how good its numbers look.
- **substitute_verifier**: `tools/population_forensics.py` (re-keys per_def rows onto the census side, reports transitions + key diagnosis) + `identity.json` sha check.
- **status**: legislated
- **refs**: `reports/interior100/population_forensics_R4nR4o.md`, `runs/e2e_1dwg_R4o_phase_20260709/identity.json`, commit `8124edd`

### [LEX-0007] phase arc closed; DASH/assoc overlap explains the residual plateau

- **observation**: R4p measured the true phase-loss mechanism split in two: (D1a) predefined-name patterns (DASH x66) lost their per-hatch phase because the origin fold read rows from the serialized entity (predefined jobs never carry `pattern_definitions`), while custom H3/H1 carriage succeeded 182/182; (D2) the canonical divisor trusted `pattern_type` (type-1 => baked) but predefined replays store type-1 UNIT rows. After the two-site repair (commit `d261e44`), R4q round-trips phase physically (job -> `setOriginPoint` -> DWG -> extracted IR, canonical geometry diff of a surviving DASH pair = `is_associative` ONLY). Headline moved only +3 (26,834/27,130) because DASH 66 and assoc 66 overlap in 63 hatches: phase repair cannot fold a pair that still differs on `is_associative`.
- **rule**: the remaining hatch residue is legislated as the ASSOC class (66 = 59+4+3 by field combo); phase is no longer an open mechanism on 1.dwg. Next admissible lever is associative re-link (docs/ASSOC_RELINK_DESIGN.md), predicted fold ~ +66.
- **substitute_verifier**: canonical field-level pair diff (geometry keys) on surviving pairs; `tools/residue_tail_report.py` field-combo census.
- **status**: legislated
- **refs**: `runs/e2e_1dwg_R4p_phase_20260709`, `runs/e2e_1dwg_R4q_dashphase_20260709`, commits `d261e44`, `reports/interior100/residue_tail_R4p.json`
