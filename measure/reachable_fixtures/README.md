# reachable_fixtures/ — P3b fleet-authored valid-arg fixtures

Each `*.json` here promotes a set of **REACHABLE** ops (dispatcher returns a
structured arg error on `{}`) to **RUNNABLE** by supplying a valid-arg fixture.
`tools/probe_reachability.py` merges every fragment into its `FIXTURES` dict at
import (`_merge_reachable_fixtures`). One fragment per family; filename = the
family slug (e.g. `brep_solids.json`).

## Fragment schema

```json
{
  "family": "<family slug>",
  "fixtures": {
    "<op.id>": {
      "args": { "...": "valid args exercising a NON-DEGENERATE path" },
      "evidence": "src/Ariadne.AcadNative/families/<file>.inc (<op>: <arg keys> — <symbol>)"
    }
  }
}
```

## Authoring rules (hard — a fixture that violates these fails the probe gate)

1. **Never guess args.** Harvest every key from the handler's own arg-key reads
   — read `src/Ariadne.AcadNative/families/<family>.inc` (or `AriadneNativeJob.cpp`)
   and cite the exact read in `evidence`. A blind-guess fixture is rejected.
2. **Non-degeneracy.** The args must drive a code path that DIFFERS from the
   handler's empty-arg (`{}`) defaults — otherwise it games the RUNNABLE
   classifier (a `created:true` that proves nothing). If an op's only honest
   fixture just reproduces the default, leave it out and note why.
3. **Evidence per op**, citing the `.inc` file + the arg-key read (and symbol
   where practical). This mirrors the curated inline `FIXTURES` discipline.
4. **Do not touch** `tools/probe_reachability.py` or another family's fragment
   (disjoint writes — this is why fragments exist).
5. Ops already in the inline curated `FIXTURES` are ignored here (inline wins);
   don't re-author them.

## Verification (orchestrator, not worker)

Workers author fragments; they cannot run accoreconsole. The orchestrator lands
a reviewed fragment then runs:

```
python tools/probe_reachability.py --live --dwg tests/fixtures/native_sample.dwg \
  --ops <this family's op ids> --out measure/_p3b_check.jsonl
```

An op only counts as promoted when its row reports `class: RUNNABLE` with a
non-degenerate result — the probe is the objective oracle, so a bad fixture
simply fails to promote and is re-dispatched.
