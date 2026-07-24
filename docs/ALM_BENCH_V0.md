# ALM Bench v0 — READ tasks

## Purpose

A machine-gradable bank of READ tasks (understanding queries) over a
round-trip-verified DWG graph IR. Every gold answer is **computed by a
generator script from the IR itself** — never hand-typed — so the gold
answer bank cannot be fabricated or drift from the source data.

- **Provenance**: each task set records the exact IR it was generated
  from in the top-level `source_ir` field of `bench/read_tasks.json`.
- **Grading**: every task uses `rubric: "exact_match"` — the candidate's
  answer must equal `gold` exactly (string/int equality after trimming
  whitespace).
- **Report format**: report results as a success-vs-budget curve. The
  `budget_axis` field on each task is `"single_pass"` for v0 (every task
  is answerable by one pass over the IR); the baseline is a single-shot
  read of the IR followed by one answer per task, with no retries or
  tool-call budget beyond that pass.

## How to regenerate

```
python bench/generate_read_tasks.py \
  --ir <absolute path to dwg_graph_ir.json> \
  --out bench/read_tasks.json
```

Regenerating against the same IR file reproduces `bench/read_tasks.json`
byte-for-byte (stable key sort, trailing newline, no hand edits).

## Task table

| id | question | gold_derivation |
|---|---|---|
| READ-001 | 모델스페이스(entities) 엔티티는 총 몇 개입니까? | `count(entities where space == 'model')` |
| READ-002 | 모델스페이스 엔티티 중 DIMENSION(dxf_name)은 몇 개입니까? | `count(entities where space == 'model' and dxf_name == 'DIMENSION')` |
| READ-003 | 모델스페이스 엔티티 중 TEXT(dxf_name)는 몇 개입니까? | `count(entities where space == 'model' and dxf_name == 'TEXT')` |
| READ-004 | block_definitions 목록에 있는 블록 정의는 총 몇 개입니까? | `len(block_definitions)` |
| READ-005 | 이름이 정규식 ^\*D\d+$ 패턴과 일치하는 block_definitions는 몇 개입니까? | `count(block_definitions where regex('^\*D\d+$').match(name))` |
| READ-006 | 모든 block_definitions의 def_entities를 합산하면 총 몇 개입니까? | `sum(len(bd.def_entities) for bd in block_definitions)` |
| READ-007 | 모든 block_definitions의 def_entities 중 dxf_name이 HATCH인 항목은 몇 개입니까? | `sum(count(de in bd.def_entities where de.dxf_name == 'HATCH') for bd in block_definitions)` |
| READ-008 | 모델스페이스 entities에서 서로 다른 dxf_name 값은 몇 종류입니까? | `len(set(e.dxf_name for e in entities where space == 'model'))` |
| READ-009 | block_references 목록에 있는 블록 참조는 총 몇 개입니까? | `len(block_references)` |
| READ-010 | entity_count가 가장 큰 block_definition의 이름은 무엇입니까? (동률이면 사전순으로 가장 앞선 이름) | `min(sorted(name for bd in block_definitions where bd.entity_count == max(entity_count)))` |
