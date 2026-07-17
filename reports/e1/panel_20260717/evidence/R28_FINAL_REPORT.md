---
run_id: ALM_RSI_R0_R28_GROK_20260713
agent: grok
phase: R0
lane_id: R28
status: draft
research_only: true
experiment_executed: false
created_at: 2026-07-13T20:12:44+09:00
source_cutoff: 2026-07-13
---

# FINAL_REPORT — R28 Evaluation / calibration / adversarial tests

## Status
draft — write-first scaffold complete; corpus/web expansion in progress.

## What was read
- `_bootstrap/PROGRAM/01` (R28 question), `04` (evidence policy), `SEEDS/EXPERIMENT_FAMILY_INDEX_HOLD.md` (E08–E16)
- `tools/check_lane.py` (gate contract)
- Domain anchors staged: Guo ICML 2017 ECE; Chen et al. metamorphic survey; Jia/Harman mutation; buildingSMART IFC validation framing

## What was created
- `00_PREFLIGHT.md`, `BRIEF.md`, `90_CROSS_AGENT_QUESTIONS.md`, `FINAL_REPORT.md`
- `ledgers/` SOURCES, CLAIMS, ASSUMPTIONS, UNKNOWNS, CONTRADICTIONS, EXPERIMENT_CANDIDATES (all HOLD)

## Top supported claims
- ECE/reliability diagrams are established ML calibration tools (C28-002)
- Metamorphic testing is a recognized oracle strategy when ground truth is hard (C28-003)
- Local E11–E16 are HOLD families not executed protocols (C28-005)

## Top disputed claims
- Schema-valid IFC as success vs semantic insufficiency (X28-001)
- Accuracy-on-i.i.d. vs project/company shift (X28-002)
- ECE primary vs risk-coverage primary (X28-004)

## Top unknowns
- Quantified held-out gaps (U28-001)
- Valid CAD metamorphic relation catalog (U28-002)
- License-feasible adversarial/company packs (U28-006)

## Top kill risks
- Leaky splits → false progress lock-in
- Schema-only CI → silent semantic failures
- License-irreversible golden sets

## Research saturation assessment
Partial: bootstrap axes covered; local alm/docs and live web pins still thin; several source pins marked NEEDS_WEB_VERIFY.

## Next phase should read
- Local `D:\dev\_ariadne\alm\docs\**` eval/validation mentions
- Autocad-sdk-router validation reports
- buildingSMART IFC4.3 ADD2 exact release notes
- NIST BIM / validation guidance if present in allow paths
- Peer answers to `90_CROSS_AGENT_QUESTIONS.md`

## Integrity statement
**no experiment/code/CAD/DB/Git mutation executed**
research_only: true; experiment_executed: false
