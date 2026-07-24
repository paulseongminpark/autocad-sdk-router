---
run_id: ALM_RSI_R0_R12_CODEX_20260713
agent: codex
phase: R0
lane_id: R12
status: complete
research_only: true
experiment_executed: false
created_at: 2026-07-13T19:33:57+09:00
source_cutoff: 2026-07-13
---

# R12 final report

## Status

Complete for an R0 broad evidence map; no final architecture or model choice was made. External coverage is strongest for vector floor-plan panoptic recognition and weak for native DWG/3DM, multi-view sets, MEP and enterprise deployment.

## What was read

- `_bootstrap/PROGRAM/00` through `08`, all `_bootstrap/SEEDS/`, relevant `_bootstrap/TEMPLATES/`, and `tools/check_lane.py`.
- Local designs `ALM_v0.3_x_PRIMITIVE_TO_SEMANTIC_FACTORY.md` v0.3_x (2026-06-10) and `ALM_Architectural_World_Model_Data_Ontology_Architecture_v0.2.md` (2026-06-09).
- Local source/spec artifacts for DWG Graph IR 1.1.0, `ariadne.semantic.wall_pairs.v0`, and centerline topology v1; a bounded protected-file-excluding census of `rhino-gh`.
- FloorPlanCAD arXiv:2105.07147v2/ICCV 2021 source and official project website/repository commit `2052d21c4c02b6fbe730a415b8609d2e904587b3`.
- Panoptic Segmentation arXiv:1801.00868v3/CVPR 2019.

## What was created

Four required Markdown files and six UTF-8 CSV ledgers under this lane only: 9 sources, 20 atomic claims, 8 assumptions, 10 unknowns, 5 contradictions, and 5 HOLD experiment candidates.

## Top supported claims

- Vector-CAD annotations can and do store semantic labels and instance IDs separately at line granularity.
- Semantic and instance tasks are distinct output problems but can be learned as one panoptic task; contract separation does not force model separation.
- Layer equality is not a universal semantic/grouping oracle, and cross-vendor template matching is brittle in FloorPlanCAD.
- Local DWG IR has implemented source signals for block definitions/references/groups, while local wall-pair code implements only deterministic candidate generation.
- A source-explicit group is authoring evidence, not automatic proof of architectural identity.

## Top disputed claims

- Strict role-first-then-group sequencing versus joint/iterative inference remains disputed.
- Partitioned instance IDs versus overlapping/nested candidate groups depends on the canonical IR and use case.
- Source blocks may deserve strong prior weight, but their semantic precision is unknown.
- Deterministic geometric rules are reproducible, but their cross-project recall and calibration are unknown.

## Top unknowns

- Legally usable, project-held-out native CAD ground truth with primitive roles and instance membership.
- The minimum role vocabulary and whether roles are exclusive, multi-label or relation-scoped.
- Tolerance/neighborhood policies across units, views, disciplines and large coordinates.
- Metrics and cost weights that expose catastrophic false merges rather than average them away.
- How cross-view entity resolution and revision lineage should constrain grouping.

## Top kill risks

- FloorPlanCAD annotations are CC BY-NC 4.0 and the project disclaims ownership of underlying drawings.
- False merge can corrupt identity, quantities, host/topology and IFC projection downstream.
- A partition-only IR can erase stuff, shared evidence, nesting and alternative hypotheses.
- Source flattening can destroy observed membership and transform lineage before semantic recovery.
- Quadratic candidate graphs or aggressive pruning can make deployment infeasible or silently lose recall.

## Research saturation assessment

R0 is **partial but honest**. The core separation question reached a stable envelope: separate role and membership assertions, evidence and gates; allow shared/joint inference. More broad web search is unlikely to remove the main uncertainty because production decisions require licensed native-DWG/3DM corpora and domain-held-out measurements. Literature coverage is not saturated for newer vector-graph models, MEP/detail drawings, or native CAD grouping standards. Those gaps are recorded rather than replaced with a winner claim.

## What the next phase must read

Read `ledgers/CLAIMS.csv` and `ledgers/CONTRADICTIONS.csv` first, then BRIEF sections 6, 9 and 10, followed by source records S002/S003/S004 and local records S007/S008. R1 should challenge R12-C04, C12, C18 and C19 and obtain independent license review of R12-C20. Any later experiment requires explicit approval of a candidate ID and prerequisites from R02/R03/R05/R07/R11/R14/R22/R23/R28.

Explicit confirmation: **no experiment/code/CAD/DB/Git mutation executed**. The only executed Python command was the user-mandated structural lane gate; no product build/test/benchmark was run.

