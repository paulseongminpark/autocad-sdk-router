---
run_id: ALM_RSI_R0_R16_CLAUDE_20260713
agent: claude
phase: R0
lane_id: R16
status: draft
research_only: true
experiment_executed: false
created_at: 2026-07-13T11:42:00Z
source_cutoff: 2026-07-13
---

# R16 FINAL REPORT — Space / boundary / host / opening reconstruction from DWG 2D

## Status
draft (PASS-2). Gate-required files complete; ledgers populated with real claims/sources. Web exact-version
verification partial — items carry NEEDS_WEB_VERIFY. No local ALM-docs deep-read completed this run (see saturation).

## What was read
- `_bootstrap/**` charter, evidence policy, vocabulary, templates; `tools/check_lane.py` (gate contract).
- Prior-knowledge base for IFC 4.3.2.0 / ISO 16739-1:2024 space-boundary, void/fill, spatial-containment model.
- Prior-knowledge base for CGAL arrangement, GEOS/Shapely polygonize, ezdxf, IfcOpenShell, ACA AEC objects,
  and the raster floor-plan parsing literature (Raster-to-Vector ICCV2017, CubiCasa5K).
- NOT deep-read this run: `D:\dev\_ariadne\alm\docs\**` local corpus (status UNKNOWN, flagged U04/C11).

## What was created
- `00_PREFLIGHT.md`, `BRIEF.md` (12 sections), `90_CROSS_AGENT_QUESTIONS.md` (7 questions), this `FINAL_REPORT.md`.
- `ledgers/` : SOURCES.csv, CLAIMS.csv, ASSUMPTIONS.csv, UNKNOWNS.csv, CONTRADICTIONS.csv, EXPERIMENT_CANDIDATES.csv.

## Top supported claims (KNOWN/LIKELY)
- C01/C02/C12: The reconstruction **target** is standardized by IFC — IfcSpace, IfcRelSpaceBoundary(1st/2nd),
  IfcOpeningElement + IfcRelVoidsElement + IfcRelFillsElement, IfcRelContainedInSpatialStructure/IfcRelAggregates.
  R16's problem is *derivation*, not schema invention.
- C03: Generic DWG carries no space topology; spaces must be reconstructed from geometry+annotation.
- C04/C05: Planar-arrangement / face-extraction on wall centerlines (after double-line→centerline) is the core
  room-recovery primitive; a polygonize (GEOS) variant is the non-GPL alternative.
- C07: Wall-hosted openings recover via gap-in-wall + door/window block + swing-arc, bound to host wall by
  spatial containment.

## Top disputed claims (DISPUTED/UNKNOWN)
- C08/X03: Hatch/poché as a room-fill or boundary signal — reliability is drawing-dependent, disputed.
- C06/X05: Raster-CNN parsers transferring to native vector DWG — unproven; rasterize→CNN→back-project is a
  live competing baseline (see Q6).
- C09/KR1: 2nd-level type-A/B space boundaries from 2D-only — under-constrained; feasibility disputed (see Q4).

## Top unknowns
- U01: Room-recovery accuracy on messy production DWGs (gaps/overshoots/noise).
- U02: Opening recall on block-free (gap-only) drawings.
- U03: Feasibility of 2nd-level SB from 2D + recoverable wall thickness.
- U04: Actual state of local ALM corpus (IMPLEMENTED/DESIGNED/PROPOSED/UNKNOWN) — not classified this run.
- U05: Engine/license choice (CGAL GPL vs GEOS LGPL vs hand-rolled DCEL).

## Top kill risks
- KR1: 2nd-level type-A/B SB unrecoverable from 2D → fall back to 1st-level scope.
- KR2: Open-plan / zoned spaces have no wall boundary → arrangement recall collapses.
- KR3: CGAL arrangement is GPL → incompatible with closed product without commercial license or GEOS swap.
- KR4: Messy geometry makes arrangement brittle without heavy pre-cleaning.
- KR5: Opening recovery fails on gap-only drawings lacking blocks.

## Research saturation assessment
- Schema/target axis (IFC): **high** — well-standardized, low residual uncertainty.
- Core algorithm axis (arrangement/centerline/polygonize): **medium** — primitive identified; robustness on
  real data unmeasured (correctly deferred to HOLD experiments, not run).
- Local corpus axis: **low** — ALM docs not deep-read; C11/U04 remain UNKNOWN. Highest-value next action.
- Learning-vs-symbolic axis: **low-medium** — competing baselines named, no evidence to adjudicate (Q6/E01).
- Exact-version anchoring: **partial** — several tool versions carry NEEDS_WEB_VERIFY.
Honest gaps recorded rather than papered over; status kept `draft`.

## What the next phase must read
- `D:\dev\_ariadne\alm\docs\**` — classify local space/boundary/opening implementation status (resolve U04/C11).
- IFC 4.3.2.0 IfcRelSpaceBoundary / IfcRelVoidsElement / IfcRelFillsElement entity pages (confirm ConnectionGeometry
  requirements for 2D-derived boundaries — Q1).
- CGAL 6.x Arrangement_on_surface_2 license + GEOS/Shapely polygonize as non-GPL alternative (resolve U05/KR3).
- CubiCasa5K + Raster-to-Vector repos/licenses for the rasterize→CNN→back-project baseline question (Q6/E01).

## Compliance statement
**No experiment / code / CAD / DB / Git mutation executed.** Research-only. No DWG/DXF/IFC/3DM created,
converted, or modified. No AutoCAD/Rhino/Grasshopper launched. No package install/build/test run. No DB write.
No git command run. All writes confined to `./lanes/R16_space_boundary_opening/`. No other lane folder read.
No subagents used.
