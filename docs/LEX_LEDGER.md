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


### [LEX-0008] orphan-assoc quotient (derived flag folds without sources)

- **observation**: 1.dwg carries 66 hatches with `is_associative=true` and NO boundary source refs (3-way probe 2026-07-10: `getAssocObjIds` 0/66, `getAssocObjIdsAt` 0/66, LibreDWG DXF no group 97/330); replaying the flag measured job `True` -> saved `False` for all 66 (R4r, `runs/e2e_1dwg_R4r_assoc_20260710`) -- the engine RESETS a sourceless associative flag on save, so the original state is unreachable by any legitimate write path.
- **rule**: `is_associative` is a DERIVED flag, meaningful only when `assoc_source_handles` exist. Canonical hatch comparison drops the flag on BOTH sides when a hatch has no source refs; hatches WITH real sources keep the flag and additionally compare the handle payload. Adjudicated in band: R4r remeasured 26,893/27,130 = 0.991264 vs prereg 26,900 band [26,890, 26,910]; +59 of the assoc-66 folded, the 7 remainder overlap the loops-mismatch class.
- **substitute_verifier**: visual gate (associativity has no render effect) + `assoc_source_handles` round-trip whenever the field exists.
- **status**: legislated
- **refs**: `tools/blockdef_diff.py::_canonical_hatch_geometry`, `docs/ASSOC_ORPHAN_FINDING.md` falsifier (c), `reports/interior100/R4r_remeasure_lex0008.json`. Implementation-gap closure (R4s, 2026-07-10): the R4r fold sat inside the `pattern_definitions`-gated path, missing 3 SOLID orphan-assoc pairs; the fold moved to `_canonical_entity` covering EVERY hatch (law unchanged) — `reports/interior100/R4s_remeasure_angle_branch.json`. **Observation correction (2026-07-10 evening, R4u)**: the 3-way probe underlying this observation is retracted — both ObjectARX probes flew the stale 2026-07-09 prebuilt crx (predates the `getAssocObjIdsAt` emission code entirely; both probe census IRs contain ZERO `assoc_source_handles` occurrences), see `docs/ASSOC_ORPHAN_FINDING.md` retraction header. R4u's census (first flight of the emission code) reads 66/66 flagged hatches WITH per-loop sources, all 77 refs resolving in-def. The RULE stands unchanged and is exactly what surfaced the unmasked residue honestly: hatches WITH real sources keep the flag and compare the payload — which is why R4u measured −66 (census now has sources; the rebuild does not re-link). The 1.dwg fold population for this quotient is empty under the corrected extractor; the law remains for genuinely sourceless flags. Payload comparison semantics are refined by LEX-0011.

### [LEX-0009] angle principal-branch quotient (circle-valued numerals)

- **observation**: two residual families measured on R4s (`reports/interior100/loops_residue_analysis_R4s.json` + dissection) are the SAME figure written on different branches of the circle: (a) all 16 residual ellipse pairs — census start/end params on the `[-pi, pi)` branch vs rebuild on `[0, 2*pi)` (sample: `-pi/2 -> ~0` vs `3*pi/2 -> 2*pi`, dense point sampling equal); (b) 4 DASH hatches whose census row angle is `6.28318...` (a 2*pi-branch authoring vintage, census carries `{0.0 x62, 2*pi x4}`) re-reported by the predefined-name replay at `0.0`.
- **rule**: angles are circle-valued equivalence classes mod `2*pi`. Canonical form: ellipse arcs fold to `start in [0, 2*pi)` + `end = start + sweep` with `sweep in (0, 2*pi]` (a full ellipse stays full); hatch pattern row angles fold to the principal branch `[0, 2*pi)` on the shared 6dp grid. REAL angular differences (sweep, family direction) still mismatch. Adjudicated: prereg 26,916 band [26,914, 26,918] (`prereg_R4s_angle_branch.json`, registered before the run) — R4s measured exactly 26,916/27,130 = 0.992112, guards 4/4 (name-map, population, per-def no-regression, band).
- **substitute_verifier**: dense point sampling of both parameterizations (`tools/loops_residue_analysis.py` point-cloud lane); contract tests `tests/unit/test_blockdef_diff.py` (fold + real-difference-survives + full-sweep guard).
- **status**: legislated
- **refs**: `tools/blockdef_diff.py::_canonical_ellipse_geometry`, `tools/blockdef_diff.py::_canonical_hatch_geometry` (row angle), `reports/interior100/R4s_remeasure_angle_branch.json`, `reports/interior100/prereg_R4s_angle_branch.json`

### [LEX-0010] loop cycle-notation quotient — hypothesis REFUTED at population level (negative result, preserved)

- **observation**: recon on def `X-...$0$111a` suggested the residual mass was HATCH `loops` cycle notation (rotation/direction/order). Full-population dissection (R4s, `tools/loops_residue_analysis.py`) refuted it: only 7/209 residual pairs are loops-only, ALL 7 point-cloud geometry-DIFFERENT (max-NN >= 1e-3, real boundary differences); a rotation×direction×order canonical form folds 0 residual pairs. The quotient itself is sound but bites nothing: census-side collision test merged 16 true notation variants with 0 geometry collisions.
- **rule**: none legislated — loop cycle canonicalization stays OUT of the measurer (a quotient that folds no residue adds blind-spot risk for zero benefit). The true residual composition is: 154 H3 pattern-vintage clobber (REAL replay defect: batch-shared per-NAME `.pat` forces the seed vintage onto a 4-vintage census population — repair, not legislation), 25 lwpolyline vertex-z loss (REAL replay defect), 16+4+3 angle-branch/assoc-gap (folded by LEX-0009/0008), 7 loops real-geometry, 28 removed-side.
- **substitute_verifier**: n/a (rejection); the analysis tool + collision-test lane remain available if a future replay path emits rotated loop notation.
- **status**: rejected
- **refs**: `tools/loops_residue_analysis.py`, `reports/interior100/loops_residue_analysis_R4s.{json,md}`

### [LEX-0011] assoc source-handle payload compares as per-loop cardinality (handle identity is not rebuild-stable)

- **observation**: R4u (`runs/e2e_1dwg_R4u_lwz_20260710`, first flight of the loop-local emission code after the stale-deploy repair) measured census `assoc_source_handles` populated for 66/66 flagged hatches — all 77 loop-source refs resolve to real in-def entities (63 lwpolyline + 14 spline, 0 unresolved), retracting the orphan claim (`docs/ASSOC_ORPHAN_FINDING.md`). Raw handle strings can never match across census and rebuild: the rebuilt drawing mints fresh handles (`new_handle` per append result), so comparing handle VALUES punishes even a perfect re-link — the same category of rebuild-unstable identity already legislated for `*D` cache names (LEX-0001) and anonymous block names (name-map).
- **rule**: canonical hatch form replaces `assoc_source_handles` VALUES with the per-loop source CARDINALITY list (order-aligned to `loops[]`); `is_associative` keeps LEX-0008 semantics (dropped only when sourceless on both sides). A hatch re-linked to the wrong-but-same-count sources still fingerprint-matches — that residual risk is carried by the substitute verifier, not the fingerprint.
- **substitute_verifier**: post-flight assoc audit joining BOTH IRs: paired census/post hatches must both carry the flag, per-loop counts must match, and the resolved source-entity KIND multiset per loop must match census (spline/lwpolyline mix distinguishes wrong-source relinks); plus the append-op `source_handle` → result `new_handle` ledger makes the exact census→post correspondence checkable.
- **status**: candidate (legislates on R4v in-band adjudication)
- **refs**: `reports/interior100/R4u_remeasure_lwz.json` (unmasked −66), `reports/interior100/prereg_R4u_lwz_reflight.json` forensics, probe `assoc_source_resolve_probe.py` 2026-07-10; implementation lands with the R4v relink arc (`docs/ASSOC_RELINK_DESIGN.md`).
