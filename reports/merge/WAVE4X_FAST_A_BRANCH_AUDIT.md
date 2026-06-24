# WAVE4X FAST A Branch Audit

## MERGE_NOW
- cados/w4x-subentity-brep (154a6f6): subentity path and assoc surface topology handlers/tests
- cados/w4x-fallback-com-ole (49244a4): safe COM/OLE metadata and LISP fallback; raw command exposure remains blocked
- cados/w4x-loader-doc-command (ab94832): module load/command typed handlers; doc.sendstring remains hard-blocked
- cados/w4x-loader-doc-r2-lifecycle-entrypoints (c8d6281): lifecycle entrypoint/status handlers; doc.sendstring SAFETY_FORBIDDEN
- cados/w4x-visual-plot (7adc82e): plot.config.settings and plot.engine.run implemented; attended verification debt preserved
- cados/w4x-db-txn-write (36f3817): staged DB txn/write handlers; live.apply_patch deprecated with replacement_ref
- cados/w4x-generic-closure-audit (19c6577): synthetic-operation guard only; no synthetic op added
- cados/w4s-spark2-agent-surface (1cd6182): cadctl --json and explain alias surface

## HOLD_REWORK
- WAVE4S_SPARK1_MICRO_IMPL / cados/w4s-spark1-micro-impl: evidence-only branch at main; keep blocked, do not merge as implementation
- WAVE4S_SPARK3_REGRESSION_AUTOMATION / cados/w4s-spark3-regression-automation: uncommitted worktree-only tests are pinned to pre-merge 457/60 counts and assert m09_allowed true; conflicts with packet rule that M09 remains blocked until user approval
- WAVE4S_SPARK4_EVIDENCE_HARDENING / cados/w4s-spark4-evidence-hardening: uncommitted worktree-only tests are stale, contain an undefined _SOURCE_INDEX helper reference, and assume zero deprecated ops; not safe to transplant without rework
- WAVE4X_VISUAL_ATTENDED / cados/w4x-visual-plot-attended: same code as visual plot branch but attended live run remains pending
- WAVE4X_LIVE_UI_APPLY / cados/w4x-live-ui-apply: plan-only/main-equivalent worktree; no applied code
- cados/w4x-assoc-solver: discovered branch outside packet merge order; not merged in this audit wave

## REJECT
- cados/w4x-generic-closure: contains synthetic bookkeeping operation wave4x.generic_closure.validation_attended_debt; audit branch merged instead
