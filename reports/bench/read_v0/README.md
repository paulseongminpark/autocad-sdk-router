# ALM-Bench READ v0 run protocol

ALM-Bench READ v0 measures whether an isolated agent can derive factual
answers about a large CAD census IR by writing and running its own Python
over the raw file, rather than by recalling or guessing.

## Scope

- Task set: `bench/read_tasks.json`, schema `ariadne.alm_bench.read.v0`, ids
  `READ-001`..`READ-010` (10 tasks).
- Source IR: `source_ir` field in `read_tasks.json`, a single ~48MB
  `dwg_graph_ir.json` census document (currently
  `D:\dev\99_tools\autocad-sdk-router\runs\e2e_1dwg_R4n_origin_20260709\census\dwg_graph_ir.json`).
- Each task has `id`, `question` (Korean), `rubric`, `gold`, `gold_derivation`,
  `budget_axis`.

## Execution model

Each task is answered by a separate, isolated worker agent (fresh context,
no shared state between workers). A worker receives only:

1. the Korean `question` text for its one task,
2. the `rubric` (e.g. `exact_match`) without the `gold` value,
3. the absolute path to the census IR file.

The worker must derive the answer by writing and executing scripted Python
against the IR file, then write `answer_READ-0NN.json` with:

```json
{"id": "READ-0NN", "answer": ..., "method": "...", "commands": ["..."]}
```

`method` is a short prose description of the derivation approach; `commands`
records the actual command(s)/script invocation(s) run against the IR (not
prose reconstruction after the fact).

## Integrity model

This is honest-agent isolation, not cryptographic isolation. Workers are
**forbidden from reading `bench/`** — the gold answers live in
`bench/read_tasks.json` in the same repo, in the same worktree the worker
operates in, and nothing prevents a worker from opening that file directly.

Given that, v0 integrity rests on two legs:

- **Instruction-level isolation**: the worker's task packet hands over only
  the question, rubric, and IR path — never the repo root, never
  `bench/read_tasks.json`, never the gold value.
- **Method audit**: the orchestrator inspects each worker's recorded
  `commands` (and `method`) for evidence that the answer was computed from
  the IR (e.g. `json.load` + filter/count/aggregate over the actual file)
  rather than copied from a key. An answer with no IR-touching commands, or
  with commands that reference `bench/` paths, is flagged as a key-reading
  violation regardless of whether the numeric answer matches gold.

This means a dishonest or careless worker *could* defeat isolation by reading
`bench/read_tasks.json` directly. v0 accepts this risk (see Known
limitations) rather than sandboxing filesystem access, and instead treats
any such read as a scoring/audit failure when the command trail reveals it.

## Grading

Grading is done by the orchestrator, after all workers finish, in one pass:

1. Load each `answer_READ-0NN.json` alongside the matching task entry from
   `bench/read_tasks.json`.
2. Score the `answer` against `gold` under the task's `rubric` (v0 has only
   `exact_match`: answer must equal gold exactly, after minimal type
   normalization such as int-vs-string-of-int).
3. Audit `method`/`commands` for key-reading violations per the Integrity
   model above. A violation overrides a correct-looking `answer` — the task
   is marked failed on integrity grounds even if the number matches gold.
4. Write per-task and aggregate results to
   `reports/bench/read_v0/scores_v0.json`.

A task's final verdict is therefore the conjunction of "answer matches gold
under rubric" AND "no key-reading violation found in the command trail."

## Known limitations

- **Open-book contamination risk**: gold answers are physically reachable
  from the worker's working directory (`bench/read_tasks.json` is in-repo,
  not held out on a separate host or behind an access boundary). v0
  accepts this and relies on instruction-level isolation plus method audit
  instead of hard sandboxing.
- **Single-shot, no search-budget axis**: every task in v0 carries
  `budget_axis: "single_pass"` — there is no multi-turn/iterative-search
  variant yet, so the bench does not yet measure how agents perform under a
  constrained or extended search budget.
- **Pilot scale**: only 10 READ tasks, all `exact_match` count/lookup
  questions over one IR file. Not yet representative of task or rubric
  diversity (no partial-credit rubrics, no multi-file or cross-IR tasks).
