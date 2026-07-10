# E1 golden review protocol v0

Protocol for minting a human-reviewed GOLDEN label set for E1 wall-annotation
over the 384 block definitions of one apartment floor plan DWG, from three
imperfect, independently-produced annotation sources. The GOLDEN set is the
reference Paul reviews and signs off on; it is not itself an annotation
source — it is the arbiter other sources get scored against.

## Inputs

Three sources, all keyed by definition name (`*D<N>`):

1. **ornith** — `reports/e1/ornith_annot_v0.jsonl`. 383 defs (one missing
   from the 384-def population). One JSON object per line:
   `{"unit_id", "parsed": {"def", "role", "wall_likelihood", "wall_line_handles", "notes"}}`.
   Produced by the ornith-35B model in a single pass.

2. **sonnet** — `bench/e1_shards/shard_01.jsonl` .. `shard_20.jsonl`. Same
   answer contract as ornith (`def`/`role`/`wall_likelihood`/`wall_line_handles`/`notes`),
   produced blind (no access to ornith's output) in a second pass, sharded
   20-wide across the def population.

3. **wall_pairs** — `reports/e1/wall_pairs_v0.json` (`per_def` map keyed by
   def name to a list of `wall_pair_candidate` claims). 11,544 claims total
   across the 384 defs, deterministic — each claim carries `pair` (two
   entity handles), `gap`, `overlap_ratio`, `angle`, `conf`, and `layers`,
   produced by `wall_pairs.py` geometric parallel-line-pair detection with no
   model in the loop. A def with an empty list is a `wall_pairs` claim of
   "no wall pair found here," not a missing record.

All three sources are imperfect: ornith and sonnet can hallucinate role or
miscount wall likelihood from the projection alone; wall_pairs is
deterministic but geometry-only, so it can both miss real walls (gap/overlap
thresholds too strict) and false-positive on parallel non-wall lines (e.g.
dimension extension lines, as seen in `*D295`/`*D300` projections). None of
the three is ground truth. GOLDEN is what Paul's review produces, not any
one input source.

## Sampling rule

Review is disagreement-first: defs where the three sources disagree most
are reviewed before defs where they agree, because agreement is not
evidence of correctness (all three can share the same blind spot) but
disagreement is a reliable signal of where a human judgment call is needed.

For each def, compute a **disagreement score** in [0, 3]:

- **+1** if ornith and sonnet `role` differ (non-wall-role strings compared
  after trim/casefold; treat semantically-equivalent role labels — e.g. the
  Korean role vocabulary variants already present in the sources — as equal
  only if they map to the same coarse bucket: wall-bearing vs. non-wall).
- **+1** if `|ornith.wall_likelihood - sonnet.wall_likelihood| >= 0.3`.
- **+1** if wall_likelihood-implied wall/non-wall (threshold 0.5) disagrees
  with wall_pairs-implied wall/non-wall (def has >=1 `wall_pair_candidate`
  with `conf >= 0.5`), for either ornith or sonnet (counts once, not twice,
  if both disagree with wall_pairs).

Defs missing from a source (e.g. the 1 def absent from ornith's 383) score
their missing-source component as maximal disagreement (that component
contributes its point automatically) — missing data is itself a disagreement
worth surfacing, not a reason to skip the def.

Sort all 384 defs descending by disagreement score, ties broken by def name
ascending (`*D<N>` numeric order) for reproducibility. Paul reviews from the
top of this ordering. There is no fixed sample-size cutoff in v0 — review
continues until Paul stops or a review budget is set in a later revision;
whatever prefix has been reviewed at any point is a valid, usable GOLDEN
slice, since the ordering guarantees the highest-value defs are always
reviewed first.

## Review unit format

One review unit = one definition, rendered as a single side-by-side block
so Paul never has to cross-reference files by hand:

```
=== <def> (disagreement_score=<0-3>) ===
[inline projection]
  entity_count, dxf_name histogram, layer histogram, bbox,
  sampled entities (handle/layer/geometry) — the same projection text
  that was fed to ornith and sonnet as their only input.

[ornith]
  role=<role> wall_likelihood=<0.0-1.0>
  wall_line_handles=[{handle, reason}, ...]
  notes=<notes>
  (or "MISSING" if def absent from ornith source)

[sonnet]
  role=<role> wall_likelihood=<0.0-1.0>
  wall_line_handles=[{handle, reason}, ...]
  notes=<notes>
  (or "MISSING" if def absent from sonnet shards)

[wall_pairs]
  N claims: for each — pair=(handle_a, handle_b) gap=<v> overlap_ratio=<v>
  angle=<v> conf=<v> layers=[...]
  (or "0 claims" if per_def list is empty)
```

The inline projection is included verbatim (not summarized) because it is
the only geometry context available without opening the DWG — it is the
same text ornith and sonnet were prompted with, so Paul is judging the
sources on the same evidence they had, not on privileged information.

## Decision vocabulary

Exactly one decision per review unit, chosen from:

- **wall_def** — the definition's primary content is one or more real
  structural/partition wall lines; a wall-detection pipeline should treat
  this def as a wall source.
- **partial_wall_def** — the definition mixes wall geometry with
  non-wall content (dimension cache, symbol, furniture, etc.), such that
  only some of its entities are wall lines; a wall-detection pipeline must
  filter within this def rather than accept or reject it wholesale.
- **non_wall_def** — no entity in this definition is a wall line (e.g. pure
  dimension block, symbol block, furniture block); the def should be
  excluded from wall detection entirely.
- **needs_geometry_view** — the inline projection and all three sources
  together are insufficient to decide; Paul must open the live DWG (or a
  rendered view) before a decision is possible. This is a valid terminal
  decision for v0 — it defers the def rather than forcing a guess, and the
  def stays open until a follow-up pass resolves it with the extra view.
- **corrupt_projection** — the inline projection itself is malformed,
  truncated, or internally inconsistent (e.g. bbox does not match any
  sampled entity, entity_count mismatches the sample list) such that no
  source's answer can be trusted; this flags a pipeline bug upstream of
  annotation, not a wall/non-wall judgment.

## Storage contract

Golden labels are appended, never rewritten, to:

```
reports/e1/golden/golden_v0.jsonl
```

One JSON object per line, one line per reviewed def:

```json
{"def": "*D300", "decision": "wall_def", "reviewer": "paul", "ts": "<ISO-8601>", "notes": "<free text>"}
```

Field contract:

- `def` — exact def name string (`*D<N>`), matching the key used across all
  three input sources.
- `decision` — exactly one of the five values in the Decision vocabulary.
- `reviewer` — reviewer identity string (`"paul"` for the human review pass
  this protocol governs; a future automated or second-reviewer pass uses
  its own identifier so provenance is never ambiguous).
- `ts` — timestamp of the decision, ISO-8601, UTC.
- `notes` — free-text rationale; required to be non-empty when `decision`
  is `needs_geometry_view` or `corrupt_projection` (the reason the def could
  not be decided is itself the useful signal), optional otherwise.

Append-only means: re-reviewing a def already in the file adds a new line
rather than editing the old one; the current golden label for a def is the
**last** line in the file matching that `def`, so consumers must scan to
end-of-file per key rather than assume the first match wins. No line is
ever deleted or mutated in place — corrections are new appended decisions,
preserving the full review history for audit.
