# E1 annotation calibration v0

Preregistered inter-annotator agreement method for the E1 def-annotation
round. This document is registered **before** the sonnet blind second pass
is scored against ornith or against the deterministic baseline — metrics,
denominators, bucket edges, and pass/fail verdicts are fixed here so that
none of them can be tuned after the numbers are seen. If a later run wants
to deviate from any definition below, that is a new preregistration
(v1), not a silent edit of v0.

## Sources

All three sources annotate the same DWG block-definition population and
are expected to conform to one shared def-annotation JSON contract:
`{def, role, wall_likelihood in [0,1], wall_line_handles: [...], notes}`.

- **ornith-35B** — `reports/e1/ornith_annot_v0.jsonl`, one JSON object per
  line, payload under the `parsed` key, keyed by `unit_id`. 383 records
  covering 383/384 target defs (1 def has no record — a full abstention,
  counted under coverage delta, not silently dropped).
- **sonnet blind second pass** — task units in `bench/e1_shards/shard_01.jsonl`
  .. `shard_20.jsonl`, 384 def-annotation prompts total (verified: sum of
  lines across all 20 shards = 384). "Blind" means sonnet is given only the
  inline entity projection in each shard's `prompt` field — never ornith's
  `parsed` output — so the two LLM passes are independent draws over the
  same def set. The scored output of this pass (one record per `unit_id`,
  same contract as ornith) is produced by a separate execution packet and
  is not yet materialized as of this preregistration; this doc fixes its
  expected shape (`reports/e1/sonnet_annot_v0.jsonl` or equivalent) so the
  calibration tool has a stable contract to read once it lands.
- **deterministic wall_pairs** — `reports/e1/wall_pairs_v0.json`, schema
  `ariadne.semantic.wall_pairs.v0`, `per_def` dict keyed by def name, each
  value a list of pair-claim objects `{pair: [handleA, handleB], conf,
  angle, gap, overlap_ratio, layers, evidence, kind}`. Totals verified:
  11,544 claims across 407 defs. This source has no `role` or
  `wall_likelihood` field — it only contributes a handle set. Per def, the
  **deterministic handle set** = union of both handles from every pair
  claim listed for that def (empty set for a def with zero claims or a def
  absent from `per_def`).

## Agreement metrics

Four metrics, each with an explicit denominator so abstentions never get
silently folded into either the match or mismatch count.

1. **Role agreement rate** (ornith vs. sonnet only — the deterministic
   source carries no role). Denominator = defs where *both* sources emit a
   non-null `role` from the def-annotation task's fixed Korean role
   vocabulary (5 categories). Abstentions (null/missing role on either
   side) are excluded from this denominator and counted separately under
   coverage delta. Numerator = exact string match after whitespace
   normalization only (strip leading/trailing, collapse internal
   whitespace runs to a single space). No fuzzy or semantic merging of
   near-duplicate labels — a spacing/typo variant of an otherwise-intended
   label counts as a mismatch, because surfacing that drift is itself part
   of what this calibration is for. Rate = numerator / denominator.

2. **wall_likelihood agreement** (ornith vs. sonnet only), computed over
   defs where both emit a non-null `wall_likelihood`:
   - **Pearson correlation r** over the paired values. Reported as
     context, not gated (see thresholds).
   - **Bucket agreement**: each value maps to exactly one of 3 buckets —
     `low = [0.0, 0.3)`, `mid = [0.3, 0.7]`, `high = (0.7, 1.0]` — a
     partition with no double-counted boundary. Agreement = fraction of
     paired defs where both sources land in the same bucket. A 3x3
     confusion table is also emitted (see Output contract) so mismatches
     are visible, not just the aggregate rate.

3. **Handle-set Jaccard vs. deterministic** (EXPLORATORY v0 — no
   threshold). For each def and each LLM source independently, Jaccard =
   `|LLM.wall_line_handles ∩ det_handles| / |LLM.wall_line_handles ∪ det_handles|`.
   Edge cases fixed here to avoid post-hoc judgment calls: both sets empty
   → Jaccard = 1.0 (vacuous agreement); exactly one empty → Jaccard = 0.0.
   `ornith_vs_det` and `sonnet_vs_det` are reported as two separate
   distributions (mean, median, p25, p75, n) — never averaged together,
   since a difference between them is itself a finding.

4. **Coverage delta**: defs where exactly one of {ornith, sonnet} abstains
   (no record, or a record with both `role` and `wall_likelihood` null)
   while the other produces a substantive annotation. Reported as counts
   in each direction (`ornith_only_abstain`, `sonnet_only_abstain`) plus
   `both_abstain` and `both_present`, so the 384-def population is fully
   partitioned and accounted for.

Every ratio above states its own denominator explicitly in the output
contract — none assume the full 384-def population unless that population
is exactly what both sources covered.

## Preregistered thresholds

Stated as commitments now, before any of the four metrics above are
computed on real output:

- **Role agreement**: `>= 0.6` → usable as-is. `< 0.4` → vocabulary
  redesign required before another annotation round. `[0.4, 0.6)` → gray
  zone with no automatic verdict; this doc commits to flagging it for
  manual review rather than rounding it up to "usable" or down to
  "redesign."
- **Likelihood bucket agreement**: `>= 0.7` → usable. Below `0.7` this doc
  does not commit to an automatic "usable" verdict — it is treated as
  **not usable** pending manual review. Pearson r has no committed
  threshold; it is reported alongside bucket agreement as supporting
  context only and must not be used to override the bucket verdict.
- **Handle-set Jaccard (LLM vs. deterministic)**: EXPLORATORY v0 — no
  threshold, no pass/fail verdict of any kind. Report the distribution
  only. This metric must not be used to gate the overall calibration
  PASS/FAIL for this round.

## Output contract

Computation (a separate packet — this doc defines the contract, not the
code) writes:

- `reports/e1/calibration_v0.json`:

```json
{
  "schema": "ariadne.semantic.e1_calibration.v0",
  "pairwise": {
    "role_agreement": {"rate": 0.0, "n_pairs": 0, "n_match": 0, "n_excluded_abstain": 0},
    "wall_likelihood": {
      "pearson_r": 0.0,
      "n_pairs": 0,
      "bucket_agreement": {"rate": 0.0, "n_match": 0, "n_pairs": 0},
      "bucket_confusion": {
        "low": {"low": 0, "mid": 0, "high": 0},
        "mid": {"low": 0, "mid": 0, "high": 0},
        "high": {"low": 0, "mid": 0, "high": 0}
      }
    },
    "handle_jaccard": {
      "ornith_vs_det": {"mean": 0.0, "median": 0.0, "p25": 0.0, "p75": 0.0, "n": 0},
      "sonnet_vs_det": {"mean": 0.0, "median": 0.0, "p25": 0.0, "p75": 0.0, "n": 0}
    },
    "coverage_delta": {"ornith_only_abstain": 0, "sonnet_only_abstain": 0, "both_abstain": 0, "both_present": 0}
  },
  "per_def": [
    {
      "def": "*D300",
      "ornith": {"role": null, "wall_likelihood": null, "wall_line_handles": []},
      "sonnet": {"role": null, "wall_likelihood": null, "wall_line_handles": []},
      "deterministic": {"handles": [], "n_claims": 0},
      "role_match": null,
      "likelihood_bucket_match": null,
      "jaccard_ornith": null,
      "jaccard_sonnet": null
    }
  ],
  "per_def_total": 0,
  "per_def_truncated": false,
  "thresholds_verdict": {
    "role_agreement": "usable | gray_zone | vocabulary_redesign",
    "likelihood_bucket_agreement": "usable | not_usable",
    "handle_jaccard": "exploratory_no_verdict"
  }
}
```

  `per_def` is capped at 500 entries, ordered by ascending def name; if the
  population exceeds 500, `per_def_truncated` is set true and
  `per_def_total` carries the true count so truncation is visible rather
  than silently absorbed into the array length.

- `reports/e1/calibration_v0.md` — a human-readable rollup of the same
  `pairwise` and `thresholds_verdict` numbers, generated alongside the
  JSON by the same computation tool (not authored by hand).
