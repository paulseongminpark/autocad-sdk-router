# CADOS V1 RC1 Hardblocks

- Generated: 2026-06-26T13:24:21.9222332+09:00
- Count: 29
- Expected count: 29
- All agent_exposed=false: True
- Every blocked op has blocker_ref: True

## command.invoke.coroutine
- blocker_code: strings.
- blocker_ref: SAFETY_FORBIDDEN: raw command dispatch is blocked in M08O fallback policy. Fallbacks are managed/.NET/LISP-only and do not expose direct command strings.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#command.invoke.coroutine; docs/FALLBACK_POLICY.md; docs/M08_REMAINING_BATCH_PLAN.md#m08o-fallback-raw-command-hard-block; reports/tickets/WAVE4X_FALLBACK.md; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#command-invoke-coroutine; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#command-invoke-coroutine; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## command.invoke.sync
- blocker_code: strings.
- blocker_ref: SAFETY_FORBIDDEN: raw command dispatch is blocked in M08O fallback policy. Fallbacks are managed/.NET/LISP-only and do not expose direct command strings.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#command.invoke.sync; docs/FALLBACK_POLICY.md; docs/M08_REMAINING_BATCH_PLAN.md#m08o-fallback-raw-command-hard-block; reports/tickets/WAVE4X_FALLBACK.md; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#command-invoke-sync; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#command-invoke-sync; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## command.invoke.sync.resbuf
- blocker_code: strings.
- blocker_ref: SAFETY_FORBIDDEN: raw command dispatch is blocked in M08O fallback policy. Fallbacks are managed/.NET/LISP-only and do not expose direct command strings.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#command.invoke.sync.resbuf; docs/FALLBACK_POLICY.md; docs/M08_REMAINING_BATCH_PLAN.md#m08o-fallback-raw-command-hard-block; reports/tickets/WAVE4X_FALLBACK.md; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#command-invoke-sync-resbuf; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#command-invoke-sync-resbuf; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## doc.sendstring
- blocker_code: instead.
- blocker_ref: SAFETY_FORBIDDEN: doc.sendstring uses AcApDocManager::sendStringToExecute to enqueue command text into an AutoCAD document command stream. R2 rechecked internal-only gating and rejected an agent operation because even policy-gated arbitrary command strings would be a raw command surface; safe bespoke typed handlers must be implemented instead.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#doc.sendstring; tests/unit/test_m08o_fallback.py::TestM08OFallback::test_doc_sendstring_is_safety_blocked_not_agent_exposed; reports/tickets/WAVE3_PANE10_MIXED.md#doc-sendstring-safety-rejected; docs/FALLBACK_POLICY.md; reports/tickets/WAVE4X_LOADER_DOC.md#doc-sendstring; reports/tickets/WAVE4X_LOADER_DOC_OPS.json#doc.sendstring; tests/unit/test_m08_doc_lifecycle.py; reports/tickets/WAVE4X_LOADER_DOC_R2.md#doc.sendstring; reports/tickets/WAVE4X_LOADER_DOC_R2_OPS.json#doc.sendstring; tests/unit/test_doc_sendstring_safety.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#doc-sendstring; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#doc-sendstring; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## automate.com.send_command
- blocker_code: agents.
- blocker_ref: SAFETY_FORBIDDEN: COM SendCommand is raw command-string dispatch and must not be exposed to agents.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#automate.com.send_command; reports/WAVE3_REMAINING_HARDBLOCK_REAUDIT.md#automate.com.send_command; docs/FALLBACK_POLICY.md; reports/tickets/WAVE4X_FALLBACK.md; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#automate-com-send_command; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#automate-com-send_command; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## embed.ole.frame
- blocker_code: available.
- blocker_ref: HOST_UNAVAILABLE: AcDbOle2Frame embedding/linking requires a live OLE client item and attended host context; no controlled OLE route or staged payload contract is available.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#embed.ole.frame; reports/WAVE3_REMAINING_HARDBLOCK_REAUDIT.md#embed.ole.frame; docs/FALLBACK_POLICY.md; reports/tickets/WAVE4X_FALLBACK.md; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#embed-ole-frame; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#embed-ole-frame; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## define.assocarray.create
- blocker_code: operation.
- blocker_ref: SAFETY_FORBIDDEN: AcDbAssocArrayActionBody::createInstance performs associative array layout/evaluation. CAD OS currently exposes only read-only identify for arrays; creating layout is not a solver-free operation.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#define.assocarray.create; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#define.assocarray.create; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocarray-create; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#define-assocarray-create; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## define.assocarray.path
- blocker_code: evaluation.
- blocker_ref: SAFETY_FORBIDDEN: path associative array creation relies on AcDbAssocArrayActionBody::createInstance and path layout evaluation.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#define.assocarray.path; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#define.assocarray.path; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocarray-path; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#define-assocarray-path; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## define.assocarray.polar
- blocker_code: evaluation.
- blocker_ref: SAFETY_FORBIDDEN: polar associative array creation relies on AcDbAssocArrayActionBody::createInstance and parameter layout evaluation.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#define.assocarray.polar; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#define.assocarray.polar; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocarray-polar; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#define-assocarray-polar; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## define.assocarray.rectangular
- blocker_code: evaluation.
- blocker_ref: SAFETY_FORBIDDEN: rectangular associative array creation relies on AcDbAssocArrayActionBody::createInstance and parameter layout evaluation.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#define.assocarray.rectangular; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#define.assocarray.rectangular; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocarray-rectangular; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#define-assocarray-rectangular; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## define.assocsurface.blend
- blocker_code: action.
- blocker_ref: SAFETY_FORBIDDEN: AcDbAssocBlendSurfaceActionBody::createInstance enters ASM associative surface creation/modeler evaluation. CAD OS has no bounded, solver-free staged handler for this modeler action.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#define.assocsurface.blend; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#define.assocsurface.blend; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocsurface-blend; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#define-assocsurface-blend; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## define.assocsurface.extrude
- blocker_code: action.
- blocker_ref: SAFETY_FORBIDDEN: AcDbAssocExtrudedSurfaceActionBody::createInstance enters ASM associative surface creation/modeler evaluation. CAD OS has no bounded, solver-free staged handler for this modeler action.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#define.assocsurface.extrude; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#define.assocsurface.extrude; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocsurface-extrude; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#define-assocsurface-extrude; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## define.assocsurface.fillet
- blocker_code: action.
- blocker_ref: SAFETY_FORBIDDEN: AcDbAssocFilletSurfaceActionBody::createInstance enters ASM associative surface creation/modeler evaluation. CAD OS has no bounded, solver-free staged handler for this modeler action.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#define.assocsurface.fillet; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#define.assocsurface.fillet; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocsurface-fillet; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#define-assocsurface-fillet; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## define.assocsurface.loft
- blocker_code: action.
- blocker_ref: SAFETY_FORBIDDEN: AcDbAssocLoftedSurfaceActionBody::createInstance enters ASM associative surface creation/modeler evaluation. CAD OS has no bounded, solver-free staged handler for this modeler action.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#define.assocsurface.loft; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#define.assocsurface.loft; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocsurface-loft; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#define-assocsurface-loft; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## define.assocsurface.offset
- blocker_code: action.
- blocker_ref: SAFETY_FORBIDDEN: AcDbAssocOffsetSurfaceActionBody::createInstance enters ASM associative surface creation/modeler evaluation. CAD OS has no bounded, solver-free staged handler for this modeler action.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#define.assocsurface.offset; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#define.assocsurface.offset; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocsurface-offset; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#define-assocsurface-offset; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## define.assocsurface.patch
- blocker_code: action.
- blocker_ref: SAFETY_FORBIDDEN: AcDbAssocPatchSurfaceActionBody::createInstance enters ASM associative surface creation/modeler evaluation. CAD OS has no bounded, solver-free staged handler for this modeler action.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#define.assocsurface.patch; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#define.assocsurface.patch; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocsurface-patch; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#define-assocsurface-patch; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## define.assocsurface.result
- blocker_code: drawings.
- blocker_ref: SAFETY_FORBIDDEN: associative surface result extraction depends on a prior ASM/evaluator-created action body result. CAD OS has no solver-free implementation that can honestly produce the result for arbitrary drawings.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#define.assocsurface.result; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#define.assocsurface.result; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocsurface-result; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#define-assocsurface-result; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## define.assocsurface.trim
- blocker_code: action.
- blocker_ref: SAFETY_FORBIDDEN: AcDbAssocTrimSurfaceActionBody::createInstance enters ASM associative surface creation/modeler evaluation. CAD OS has no bounded, solver-free staged handler for this modeler action.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#define.assocsurface.trim; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#define.assocsurface.trim; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocsurface-trim; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#define-assocsurface-trim; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## edit.assocarray.explode
- blocker_code: operation.
- blocker_ref: SAFETY_FORBIDDEN: associative array explode mutates the staged database through array action body expansion and is not exposed as a bounded CAD OS operation.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#edit.assocarray.explode; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#edit.assocarray.explode; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#edit-assocarray-explode; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#edit-assocarray-explode; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## edit.assocarray.item
- blocker_code: exists.
- blocker_ref: SAFETY_FORBIDDEN: associative array item edits require item locator/layout evaluation and can trigger array body recomputation; no bounded solver-free agent handler exists.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#edit.assocarray.item; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#edit.assocarray.item; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#edit-assocarray-item; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#edit-assocarray-item; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## edit.assocarray.itemReplace
- blocker_code: exists.
- blocker_ref: SAFETY_FORBIDDEN: associative array item replacement requires source-item substitution and array body recomputation; no bounded solver-free agent handler exists.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#edit.assocarray.itemReplace; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#edit.assocarray.itemReplace; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#edit-assocarray-itemReplace; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#edit-assocarray-itemReplace; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## edit.assocarray.reset
- blocker_code: agents.
- blocker_ref: SAFETY_FORBIDDEN: resetArrayItems performs array re-layout/evaluation and is intentionally not exposed to agents.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#edit.assocarray.reset; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#edit.assocarray.reset; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#edit-assocarray-reset; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#edit-assocarray-reset; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## edit.assocarray.source
- blocker_code: evaluator.
- blocker_ref: SAFETY_FORBIDDEN: source entity edits on associative arrays require action body recomputation and can mutate layout through the evaluator.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#edit.assocarray.source; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#edit.assocarray.source; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#edit-assocarray-source; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#edit-assocarray-source; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## edit.assocarray.transform
- blocker_code: exists.
- blocker_ref: SAFETY_FORBIDDEN: transformBy on associative array action bodies can trigger layout/evaluator semantics; no bounded solver-free agent handler exists.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#edit.assocarray.transform; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#edit.assocarray.transform; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#edit-assocarray-transform; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#edit-assocarray-transform; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## inspect.assocaction.evaluate
- blocker_code: semantics.
- blocker_ref: SAFETY_FORBIDDEN: AcDbAssocAction::evaluate is the native associative solver entry. Exposing it as an agent operation would run arbitrary evaluation callbacks and mutate the staged database outside CAD OS bounded semantics.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#inspect.assocaction.evaluate; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#inspect.assocaction.evaluate; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#inspect-assocaction-evaluate; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#inspect-assocaction-evaluate; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## inspect.assocnetwork.evaluate
- blocker_code: code.
- blocker_ref: SAFETY_FORBIDDEN: AcDbAssocManager::evaluateTopLevelNetwork is the top-level associative solver. Exposing it as an agent operation would run arbitrary network evaluation/callback code.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#inspect.assocnetwork.evaluate; reports/WAVE3_PANE5_ASSOCIATIVITY_REAUDIT.md#inspect.assocnetwork.evaluate; tests/unit/test_wave3_pane5_assoc_reaudit.py; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#inspect-assocnetwork-evaluate; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#inspect-assocnetwork-evaluate; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## command.queue.post
- blocker_code: strings.
- blocker_ref: SAFETY_FORBIDDEN: raw command dispatch is blocked in M08O fallback policy. Fallbacks are managed/.NET/LISP-only and do not expose direct command strings.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#command.queue.post; docs/FALLBACK_POLICY.md; docs/M08_REMAINING_BATCH_PLAN.md#m08o-fallback-raw-command-hard-block; reports/tickets/WAVE4X_FALLBACK.md; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#command-queue-post; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#command-queue-post; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## module.lifecycle.on_ole_unload
- blocker_code: surface.
- blocker_ref: HOST_UNAVAILABLE: On_kOleUnloadAppMsg is a host lifecycle callback and cannot be triggered safely from the CAD OS job surface.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#module.lifecycle.on_ole_unload; reports/WAVE3_REMAINING_HARDBLOCK_REAUDIT.md#module.lifecycle.on_ole_unload; docs/FALLBACK_POLICY.md; reports/tickets/WAVE4X_FALLBACK.md; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#module-lifecycle-on_ole_unload; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#module-lifecycle-on_ole_unload; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

## command.menu.invoke
- blocker_code: session.
- blocker_ref: SAFETY_FORBIDDEN: acedMenuCmd executes arbitrary menu/command macros in the active editor; exposing it as an agent API would be a raw command surface and may mutate the user session.
- evidence_ref: config/autocad_native_arx_operation_catalog.json#command.menu.invoke; src/Ariadne.AcadNative/families/m08n_handlers.inc:m08nHasOp excludes raw/registry-mutating op; reports/tickets/M08N-A3_PLAN.md#Blocker criteria; research/native_arx/editor-delta.md#Operation catalog (PART 1); research/native_arx/ui-customization.md#Operation catalog; docs/FALLBACK_POLICY.md; reports/tickets/WAVE4X_FALLBACK.md; reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#command-menu-invoke; reports/WAVE4X_FINAL_A_HARDBLOCK_REIMPLEMENTATION.md#command-menu-invoke; tests/unit/test_wave4x_final_a_hardblock_contract.py
- agent_exposed: False
- replacement_ref: 
- explanation: Hard-blocked for CAD OS v1 because the registry evidence does not provide a safe typed, staged, introspection, or attended route that preserves the no-raw-command and no-original-write-default gates. The operation remains non-agent-exposed until a future packet supplies a safe replacement with tests and evidence.

