---
run_id: ALM_RSI_R0_R14_GROK_20260713
agent: grok
phase: R0
lane_id: R14
status: draft
research_only: true
experiment_executed: false
created_at: 2026-07-13T21:42:00+09:00
source_cutoff: 2026-07-13
---

# FINAL_REPORT — R14 Architectural object classification

## Status
`draft` — gate structure complete; CLAIMS/SOURCES densified after local ontology + IFC/Uniclass web reads; OmniClass/bSDD license pins incomplete; **no conclusion forced**.

## What was read
- `_bootstrap/PROGRAM/01_MASTER_RESEARCH_QUESTION_GRAPH.md`, `04_EVIDENCE_AND_CITATION_POLICY.md`, `SEEDS/EXPERIMENT_FAMILY_INDEX_HOLD.md`, CSV templates, `tools/check_lane.py`
- Local: `ALM_Architectural_World_Model_Data_Ontology_Architecture_v0.3.md` (incl. §9.3 adapters, §33 non-goals), `ALM_v0.3_x_PRIMITIVE_TO_SEMANTIC_FACTORY.md` (class contracts), `2026-06-04-plan4-p2-semantics.md`, openings results path noted
- Web/official: Uniclass NBS portal (tables+FAQ); IFC 4.3.2 `IfcWall` + `IfcClassificationReference`; IFC4 ADD2 ClassRef; CSI OmniClass landing (thin); bSDD API docs via search/GitHub (official technical page 403)

## What was created
Under `lanes/R14_arch_object_classification/` only:
- `00_PREFLIGHT.md`, `BRIEF.md`, `90_CROSS_AGENT_QUESTIONS.md`, `FINAL_REPORT.md`
- `ledgers/SOURCES.csv` (15), `CLAIMS.csv` (15), `ASSUMPTIONS.csv` (7), `UNKNOWNS.csv` (8), `CONTRADICTIONS.csv` (5), `EXPERIMENT_CANDIDATES.csv` (5 HOLD)

## Top supported claims
- IFC = OO entities (+PredefinedType); Uniclass = versioned multi-table classification; not isomorphic.
- IFC attaches external codes via `IfcClassificationReference` (facet pattern).
- Local v0.3: DESIGNED `alm:*`, adapters must not judge ontology, **Full IFC replacement delayed**.
- Local factory already exceeds six headline classes (e.g. CurtainWall).
- E05-linked experiments remain HOLD; no experiment executed.

## Top disputed claims
- IFC-as-internal-SoT vs IR-then-project (CTR-001).
- Classification codes as identity vs detachable facets (CTR-003).
- plan4 layer rules as legitimate project adapter vs core pollution (CTR-004).
- Six-class probe vs larger local vocabulary as product enum (CTR-005).

## Top unknowns
- IFC release pin with R18; Uniclass commercial embed terms; OmniClass edition; bSDD offline legality; WallCandidate lifecycle; minimum core set for R01 use cases.

## Top kill risks
- Early IFC-native internal SoT breaking Uniclass/OmniClass procurement paths or causing schema churn.
- Hard bSDD online dependency for air-gapped deploy.
- Baking project layer names into core IR.
- Closed-6 enum ignoring CurtainWall/Opening/etc.
- Ontology judgment inside CAD intake adapters.

## Research saturation assessment
- **Conceptual boundary (IFC vs classification vs adapter):** medium-high for R0.
- **Version-pinned Uniclass tables:** medium (portal versions captured).
- **IFC lexical:** medium (4.3.2 pages fetched).
- **OmniClass depth / bSDD ToS / commercial licenses:** low — explicit gaps.
- **Local concordance metrics:** not validated; honesty preserved.
- Fake completeness avoided; status remains `draft`.

## What next phase should read
1. Locked ontology YAML if/when created (`architectural_classes.yaml` referenced in v0.3).
2. R18 IFC release decision → back-propagate pin into R14 projections.
3. NBS Uniclass terms-of-use beyond FAQ; CSI OmniClass table packages.
4. bSDD ToS + whether dictionary dumps are redistributable offline.
5. Cross-review answers to `90_CROSS_AGENT_QUESTIONS.md` (esp. adapter placement and facet identity).
6. Orchestrator-merged R06/R20 notes — **this lane did not read other `lanes/R*`**.

## Prerequisites this lane demands of others
- R01: use-case priority → core class coverage target.
- R06: canonical IR class/relation contract.
- R18: IFC release + projection policy.
- R20: BOT/ifcOWL/bSDD responsibility split.
- R22/R29: dataset/classification license & deploy.
- R12/R09: primitive/layer evidence feeding adapters.
- R16: Space/opening host semantics for class edges.

## Integrity statement
**no experiment/code/CAD/DB/Git mutation executed**
