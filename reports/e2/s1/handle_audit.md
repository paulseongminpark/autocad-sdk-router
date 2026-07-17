# E2 S1-A — cited-handle reality audit

**VERDICT: CLEAN**  (live judges only: CLEAN)

Band rule, applied mechanically to each judge's `pct_nonexistent`, overall = worst band:

| pct_nonexistent | band |
|---|---|
| > 5% | INSTRUMENTATION_BUG |
| 1% – 5% | MINOR_NOISE |
| < 1% | CLEAN |

## What was checked

Each judge saw exactly one def per record: the inline projection text in its prompt, with no
filesystem access. This audit takes every handle the judge cited in `wall_line_handles` and asks
whether that handle string appears as a `handle=` token in that same def's projection. A handle
that is absent is one the judge could not have seen — it was fabricated, not misread.

- Projections parsed: **384** defs from 20 shard files, carrying 7539 distinct handles.
- Citations checked: **3264** across 6 judges.
- Nonexistent citations: **0**.

## Per-judge results

| judge | n_records | n_cited | n_distinct | n_nonexistent | pct_nonexistent | band |
|---|---:|---:|---:|---:|---:|---|
| `opus48_max` | 384 | 246 | 246 | 0 | 0.00% | CLEAN |
| `fable5_high` | 384 | 264 | 264 | 0 | 0.00% | CLEAN |
| `sol56_xhigh` | 384 | 166 | 166 | 0 | 0.00% | CLEAN |
| `sonnet5_xhigh` | 384 | 229 | 229 | 0 | 0.00% | CLEAN |
| `grok45_xhigh` | 384 | 314 | 314 | 0 | 0.00% | CLEAN |
| `ornith_v0` | 377 | 2045 | 2045 | 0 | 0.00% | CLEAN |

## Negative control — is this verdict worth believing?

A near-zero fabrication rate is exactly what a *broken* checker would also report, so the number
above means nothing until the instrument is shown able to fail. Every judge's real citations were
re-checked against a different def (each record re-pointed at a different def via half-list rotation). Those are handles the judge
provably never saw, so a working checker must flag nearly all of them.

| judge | n_cited | pct_nonexistent under control |
|---|---:|---:|
| `opus48_max` | 246 | 100.00% |
| `fable5_high` | 264 | 100.00% |
| `sol56_xhigh` | 166 | 100.00% |
| `sonnet5_xhigh` | 229 | 100.00% |
| `grok45_xhigh` | 314 | 100.00% |
| `ornith_v0` | 2045 | 100.00% |

**Control PASSED** (expectation: pct_nonexistent >= 90 for every judge with citations; observed minimum: 100.0%). The checker detects fabricated handles when they are present, so its report that the live runs contain none is a measurement, not a blind spot.

## Kind histogram of cited handles

What the cited handles actually point at in the projection. A judge citing a wall line should be
pointing at LINE or LWPOLYLINE; anything else is a category error the judge made with full sight
of the entity's own kind label.

| judge | `LINE` | `LWPOLYLINE` | `INSERT` | `ARC` | `POINT` | `MTEXT` | `HATCH` | `CIRCLE` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `opus48_max` | 246 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `fable5_high` | 257 | 5 | 2 | 0 | 0 | 0 | 0 | 0 |
| `sol56_xhigh` | 166 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `sonnet5_xhigh` | 194 | 35 | 0 | 0 | 0 | 0 | 0 | 0 |
| `grok45_xhigh` | 308 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| `ornith_v0` | 968 | 1042 | 9 | 20 | 3 | 1 | 1 | 1 |

## Per-def worst offenders

### Global (all judges pooled)

_No def attracted a single nonexistent citation._

### `opus48_max`

_No nonexistent citations._

### `fable5_high`

_No nonexistent citations._

### `sol56_xhigh`

_No nonexistent citations._

### `sonnet5_xhigh`

_No nonexistent citations._

### `grok45_xhigh`

_No nonexistent citations._

### `ornith_v0`

_No nonexistent citations._

## Cross-tabs

### By projection truncation (137/384 defs are truncated)

A projection lists at most 30 entities. Where `entity_count` exceeds that, the judge saw a partial
def. This does not excuse a fabricated handle — the judge cannot cite what it never saw — but it
shows whether fabrication tracks partial sight.

| slice | n_cited | n_nonexistent | pct |
|---|---:|---:|---:|
| truncated defs | 2102 | 0 | 0.00% |
| complete defs | 1162 | 0 | 0.00% |

### By divergence list (full_split=73, soft_split=28)

Defs where the judges split on role. If fabrication concentrated here, judge disagreement would be
an instrumentation artifact rather than genuine interpretive difference.

| slice | n_cited | n_nonexistent | pct |
|---|---:|---:|---:|
| full_split defs | 517 | 0 | 0.00% |
| soft_split defs | 186 | 0 | 0.00% |
| non-divergent defs | 2561 | 0 | 0.00% |

## Data quality

- Load problems: **6** (first 40 in JSON under `data_quality.load_problems`).
- v0 'parsed' payloads that are run receipts or bare {handle,reason} objects are excluded from every denominator, not salvaged.
- `ornith_v0`: 3 def-name mismatches vs projection.

### v0 bare `{handle,reason}` records (excluded from denominators)

| unit_id | handle | exists in projection? |
|---|---|---|
| `defannot-x-0-382` | `7CE8` | True |
| `defannot-x-0-84c1-297` | `7402` | True |
| `defannot-x-0-ba15002700-330` | `6496` | True |

## What this means for the wall-detector campaign

`calibration_v0.json` measured handle-set agreement between ornith v0 and sonnet at Jaccard mean **0.1319**, with **0.682** of def pairs sharing no cited handle at all (n=239). S1-A asked whether that near-total disagreement is an artifact — judges citing handles that were never on the page.

**It is not.** Every cited handle resolves to an entity the judge was actually shown. The judges
are reading the same real entities and disagreeing about which of them are walls. The low Jaccard
is therefore a genuine interpretive split, and downstream stages must treat it as signal to
adjudicate rather than noise to filter out. Handle fabrication is ruled out as an explanation;
it does not follow that the citations are *correct*, only that their referents exist — see the
kind histogram above for whether judges are pointing at plausible wall geometry at all.

---
_Generated by `tools/e2/s1_handle_audit.py` — schema `ariadne.e2_s1_handle_audit.v1`._
