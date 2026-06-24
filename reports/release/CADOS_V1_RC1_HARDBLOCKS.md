# CADOS V1 RC1 Hardblocks

- status: **PASS**
- count: **29**
- all_agent_exposed_false: `True`
- allowed_codes: `HOST_UNAVAILABLE, SAFETY_FORBIDDEN`

## Operations
### automate.com.send_command
- family: `com_activex`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE3_REMAINING_HARDBLOCK_REAUDIT.md#automate.com.send_command`
- agent_exposed: `False`
- replacement_ref: `typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact SDK operation is raw command string or macro dispatch. A typed safe implementation would be a different operation; CAD OS exposes operation-specific typed handlers instead of a generic raw command API.
- no read/status subset: Executing or queueing a command string has no read-only subset. Command metadata/status is covered by implemented typed operations such as command.register.define, module.command.lookup, and module.command.stack_handle.
- no staged route: Running arbitrary command text on a staged copy bypasses operation schemas and typed handlers, and could still perform unbounded side effects inside the AutoCAD command processor.
- no attended route: A dedicated attended host would still expose arbitrary command text to an editor command stream. Host isolation does not convert raw command dispatch into a bounded operation.
- no policy-gated replacement: A policy-gated generic command route would still expose raw command semantics. The replacement is typed CAD OS operations and operation-specific handlers, not command-string execution.

### command.invoke.coroutine
- family: `active_document_write_original`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#command-invoke-coroutine`
- agent_exposed: `False`
- replacement_ref: `typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact SDK operation is raw command string or macro dispatch. A typed safe implementation would be a different operation; CAD OS exposes operation-specific typed handlers instead of a generic raw command API.
- no read/status subset: Executing or queueing a command string has no read-only subset. Command metadata/status is covered by implemented typed operations such as command.register.define, module.command.lookup, and module.command.stack_handle.
- no staged route: Running arbitrary command text on a staged copy bypasses operation schemas and typed handlers, and could still perform unbounded side effects inside the AutoCAD command processor.
- no attended route: A dedicated attended host would still expose arbitrary command text to an editor command stream. Host isolation does not convert raw command dispatch into a bounded operation.
- no policy-gated replacement: A policy-gated generic command route would still expose raw command semantics. The replacement is typed CAD OS operations and operation-specific handlers, not command-string execution.

### command.invoke.sync
- family: `active_document_write_original`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#command-invoke-sync`
- agent_exposed: `False`
- replacement_ref: `typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact SDK operation is raw command string or macro dispatch. A typed safe implementation would be a different operation; CAD OS exposes operation-specific typed handlers instead of a generic raw command API.
- no read/status subset: Executing or queueing a command string has no read-only subset. Command metadata/status is covered by implemented typed operations such as command.register.define, module.command.lookup, and module.command.stack_handle.
- no staged route: Running arbitrary command text on a staged copy bypasses operation schemas and typed handlers, and could still perform unbounded side effects inside the AutoCAD command processor.
- no attended route: A dedicated attended host would still expose arbitrary command text to an editor command stream. Host isolation does not convert raw command dispatch into a bounded operation.
- no policy-gated replacement: A policy-gated generic command route would still expose raw command semantics. The replacement is typed CAD OS operations and operation-specific handlers, not command-string execution.

### command.invoke.sync.resbuf
- family: `active_document_write_original`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#command-invoke-sync-resbuf`
- agent_exposed: `False`
- replacement_ref: `typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact SDK operation is raw command string or macro dispatch. A typed safe implementation would be a different operation; CAD OS exposes operation-specific typed handlers instead of a generic raw command API.
- no read/status subset: Executing or queueing a command string has no read-only subset. Command metadata/status is covered by implemented typed operations such as command.register.define, module.command.lookup, and module.command.stack_handle.
- no staged route: Running arbitrary command text on a staged copy bypasses operation schemas and typed handlers, and could still perform unbounded side effects inside the AutoCAD command processor.
- no attended route: A dedicated attended host would still expose arbitrary command text to an editor command stream. Host isolation does not convert raw command dispatch into a bounded operation.
- no policy-gated replacement: A policy-gated generic command route would still expose raw command semantics. The replacement is typed CAD OS operations and operation-specific handlers, not command-string execution.

### command.menu.invoke
- family: `ui_customization`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#command-menu-invoke`
- agent_exposed: `False`
- replacement_ref: `typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact SDK operation is raw command string or macro dispatch. A typed safe implementation would be a different operation; CAD OS exposes operation-specific typed handlers instead of a generic raw command API.
- no read/status subset: Executing or queueing a command string has no read-only subset. Command metadata/status is covered by implemented typed operations such as command.register.define, module.command.lookup, and module.command.stack_handle.
- no staged route: Running arbitrary command text on a staged copy bypasses operation schemas and typed handlers, and could still perform unbounded side effects inside the AutoCAD command processor.
- no attended route: A dedicated attended host would still expose arbitrary command text to an editor command stream. Host isolation does not convert raw command dispatch into a bounded operation.
- no policy-gated replacement: A policy-gated generic command route would still expose raw command semantics. The replacement is typed CAD OS operations and operation-specific handlers, not command-string execution.

### command.queue.post
- family: `editor_input`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#command-queue-post`
- agent_exposed: `False`
- replacement_ref: `typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact SDK operation is raw command string or macro dispatch. A typed safe implementation would be a different operation; CAD OS exposes operation-specific typed handlers instead of a generic raw command API.
- no read/status subset: Executing or queueing a command string has no read-only subset. Command metadata/status is covered by implemented typed operations such as command.register.define, module.command.lookup, and module.command.stack_handle.
- no staged route: Running arbitrary command text on a staged copy bypasses operation schemas and typed handlers, and could still perform unbounded side effects inside the AutoCAD command processor.
- no attended route: A dedicated attended host would still expose arbitrary command text to an editor command stream. Host isolation does not convert raw command dispatch into a bounded operation.
- no policy-gated replacement: A policy-gated generic command route would still expose raw command semantics. The replacement is typed CAD OS operations and operation-specific handlers, not command-string execution.

### define.assocarray.create
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocarray-create`
- agent_exposed: `False`
- replacement_ref: `inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact assoc-array operation invokes layout creation, item replacement, reset, transform, or explode semantics that rely on AcDbAssocArrayActionBody evaluation. The solver-free typed subset is implemented as separate read/status/audit operations.
- no read/status subset: Read/status coverage exists separately through inspect.assocarray.identify, inspect.assocmanager.state, and related assoc network inspection. Reclassifying this mutating op as read-only would hide implementation debt.
- no staged route: A staged copy prevents original DWG writes but does not make associative layout evaluation bounded or solver-free; the evaluator may recompute dependencies and generated geometry.
- no attended route: A dedicated attended host does not remove the unsafe evaluator semantics; the blocker is solver execution, not only host availability.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocarray.identify, inspect.assocmanager.state, and repair.assocdata.audit; the mutating array operation itself remains blocked.

### define.assocarray.path
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocarray-path`
- agent_exposed: `False`
- replacement_ref: `inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact assoc-array operation invokes layout creation, item replacement, reset, transform, or explode semantics that rely on AcDbAssocArrayActionBody evaluation. The solver-free typed subset is implemented as separate read/status/audit operations.
- no read/status subset: Read/status coverage exists separately through inspect.assocarray.identify, inspect.assocmanager.state, and related assoc network inspection. Reclassifying this mutating op as read-only would hide implementation debt.
- no staged route: A staged copy prevents original DWG writes but does not make associative layout evaluation bounded or solver-free; the evaluator may recompute dependencies and generated geometry.
- no attended route: A dedicated attended host does not remove the unsafe evaluator semantics; the blocker is solver execution, not only host availability.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocarray.identify, inspect.assocmanager.state, and repair.assocdata.audit; the mutating array operation itself remains blocked.

### define.assocarray.polar
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocarray-polar`
- agent_exposed: `False`
- replacement_ref: `inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact assoc-array operation invokes layout creation, item replacement, reset, transform, or explode semantics that rely on AcDbAssocArrayActionBody evaluation. The solver-free typed subset is implemented as separate read/status/audit operations.
- no read/status subset: Read/status coverage exists separately through inspect.assocarray.identify, inspect.assocmanager.state, and related assoc network inspection. Reclassifying this mutating op as read-only would hide implementation debt.
- no staged route: A staged copy prevents original DWG writes but does not make associative layout evaluation bounded or solver-free; the evaluator may recompute dependencies and generated geometry.
- no attended route: A dedicated attended host does not remove the unsafe evaluator semantics; the blocker is solver execution, not only host availability.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocarray.identify, inspect.assocmanager.state, and repair.assocdata.audit; the mutating array operation itself remains blocked.

### define.assocarray.rectangular
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocarray-rectangular`
- agent_exposed: `False`
- replacement_ref: `inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact assoc-array operation invokes layout creation, item replacement, reset, transform, or explode semantics that rely on AcDbAssocArrayActionBody evaluation. The solver-free typed subset is implemented as separate read/status/audit operations.
- no read/status subset: Read/status coverage exists separately through inspect.assocarray.identify, inspect.assocmanager.state, and related assoc network inspection. Reclassifying this mutating op as read-only would hide implementation debt.
- no staged route: A staged copy prevents original DWG writes but does not make associative layout evaluation bounded or solver-free; the evaluator may recompute dependencies and generated geometry.
- no attended route: A dedicated attended host does not remove the unsafe evaluator semantics; the blocker is solver execution, not only host availability.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocarray.identify, inspect.assocmanager.state, and repair.assocdata.audit; the mutating array operation itself remains blocked.

### define.assocsurface.blend
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocsurface-blend`
- agent_exposed: `False`
- replacement_ref: `inspect.assocsurface.topology + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact associative-surface operation enters ASM/modeler action-body creation or result mutation. The safe typed subset is implemented as inspect.assocsurface.topology and staged assoc-data audit.
- no read/status subset: Read-only topology/status coverage is already implemented as inspect.assocsurface.topology. The blocked operation cannot be relabeled as that subset without faking the requested modeler action.
- no staged route: A staged copy contains the blast radius but still invokes the associative modeler/evaluator and can create or recompute complex surface bodies outside a bounded CAD OS contract.
- no attended route: Attended/full AutoCAD would supply a host, but the unresolved risk is unbounded ASM/evaluator execution rather than headless-host absence.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocsurface.topology and repair.assocdata.audit; the modeler action body operation remains blocked.

### define.assocsurface.extrude
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocsurface-extrude`
- agent_exposed: `False`
- replacement_ref: `inspect.assocsurface.topology + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact associative-surface operation enters ASM/modeler action-body creation or result mutation. The safe typed subset is implemented as inspect.assocsurface.topology and staged assoc-data audit.
- no read/status subset: Read-only topology/status coverage is already implemented as inspect.assocsurface.topology. The blocked operation cannot be relabeled as that subset without faking the requested modeler action.
- no staged route: A staged copy contains the blast radius but still invokes the associative modeler/evaluator and can create or recompute complex surface bodies outside a bounded CAD OS contract.
- no attended route: Attended/full AutoCAD would supply a host, but the unresolved risk is unbounded ASM/evaluator execution rather than headless-host absence.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocsurface.topology and repair.assocdata.audit; the modeler action body operation remains blocked.

### define.assocsurface.fillet
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocsurface-fillet`
- agent_exposed: `False`
- replacement_ref: `inspect.assocsurface.topology + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact associative-surface operation enters ASM/modeler action-body creation or result mutation. The safe typed subset is implemented as inspect.assocsurface.topology and staged assoc-data audit.
- no read/status subset: Read-only topology/status coverage is already implemented as inspect.assocsurface.topology. The blocked operation cannot be relabeled as that subset without faking the requested modeler action.
- no staged route: A staged copy contains the blast radius but still invokes the associative modeler/evaluator and can create or recompute complex surface bodies outside a bounded CAD OS contract.
- no attended route: Attended/full AutoCAD would supply a host, but the unresolved risk is unbounded ASM/evaluator execution rather than headless-host absence.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocsurface.topology and repair.assocdata.audit; the modeler action body operation remains blocked.

### define.assocsurface.loft
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocsurface-loft`
- agent_exposed: `False`
- replacement_ref: `inspect.assocsurface.topology + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact associative-surface operation enters ASM/modeler action-body creation or result mutation. The safe typed subset is implemented as inspect.assocsurface.topology and staged assoc-data audit.
- no read/status subset: Read-only topology/status coverage is already implemented as inspect.assocsurface.topology. The blocked operation cannot be relabeled as that subset without faking the requested modeler action.
- no staged route: A staged copy contains the blast radius but still invokes the associative modeler/evaluator and can create or recompute complex surface bodies outside a bounded CAD OS contract.
- no attended route: Attended/full AutoCAD would supply a host, but the unresolved risk is unbounded ASM/evaluator execution rather than headless-host absence.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocsurface.topology and repair.assocdata.audit; the modeler action body operation remains blocked.

### define.assocsurface.offset
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocsurface-offset`
- agent_exposed: `False`
- replacement_ref: `inspect.assocsurface.topology + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact associative-surface operation enters ASM/modeler action-body creation or result mutation. The safe typed subset is implemented as inspect.assocsurface.topology and staged assoc-data audit.
- no read/status subset: Read-only topology/status coverage is already implemented as inspect.assocsurface.topology. The blocked operation cannot be relabeled as that subset without faking the requested modeler action.
- no staged route: A staged copy contains the blast radius but still invokes the associative modeler/evaluator and can create or recompute complex surface bodies outside a bounded CAD OS contract.
- no attended route: Attended/full AutoCAD would supply a host, but the unresolved risk is unbounded ASM/evaluator execution rather than headless-host absence.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocsurface.topology and repair.assocdata.audit; the modeler action body operation remains blocked.

### define.assocsurface.patch
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocsurface-patch`
- agent_exposed: `False`
- replacement_ref: `inspect.assocsurface.topology + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact associative-surface operation enters ASM/modeler action-body creation or result mutation. The safe typed subset is implemented as inspect.assocsurface.topology and staged assoc-data audit.
- no read/status subset: Read-only topology/status coverage is already implemented as inspect.assocsurface.topology. The blocked operation cannot be relabeled as that subset without faking the requested modeler action.
- no staged route: A staged copy contains the blast radius but still invokes the associative modeler/evaluator and can create or recompute complex surface bodies outside a bounded CAD OS contract.
- no attended route: Attended/full AutoCAD would supply a host, but the unresolved risk is unbounded ASM/evaluator execution rather than headless-host absence.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocsurface.topology and repair.assocdata.audit; the modeler action body operation remains blocked.

### define.assocsurface.result
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocsurface-result`
- agent_exposed: `False`
- replacement_ref: `inspect.assocsurface.topology + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact associative-surface operation enters ASM/modeler action-body creation or result mutation. The safe typed subset is implemented as inspect.assocsurface.topology and staged assoc-data audit.
- no read/status subset: Read-only topology/status coverage is already implemented as inspect.assocsurface.topology. The blocked operation cannot be relabeled as that subset without faking the requested modeler action.
- no staged route: A staged copy contains the blast radius but still invokes the associative modeler/evaluator and can create or recompute complex surface bodies outside a bounded CAD OS contract.
- no attended route: Attended/full AutoCAD would supply a host, but the unresolved risk is unbounded ASM/evaluator execution rather than headless-host absence.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocsurface.topology and repair.assocdata.audit; the modeler action body operation remains blocked.

### define.assocsurface.trim
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#define-assocsurface-trim`
- agent_exposed: `False`
- replacement_ref: `inspect.assocsurface.topology + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact associative-surface operation enters ASM/modeler action-body creation or result mutation. The safe typed subset is implemented as inspect.assocsurface.topology and staged assoc-data audit.
- no read/status subset: Read-only topology/status coverage is already implemented as inspect.assocsurface.topology. The blocked operation cannot be relabeled as that subset without faking the requested modeler action.
- no staged route: A staged copy contains the blast radius but still invokes the associative modeler/evaluator and can create or recompute complex surface bodies outside a bounded CAD OS contract.
- no attended route: Attended/full AutoCAD would supply a host, but the unresolved risk is unbounded ASM/evaluator execution rather than headless-host absence.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocsurface.topology and repair.assocdata.audit; the modeler action body operation remains blocked.

### doc.sendstring
- family: `active_document_write_original`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/tickets/WAVE4X_LOADER_DOC_R2.md#doc.sendstring`
- agent_exposed: `False`
- replacement_ref: `typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact SDK operation is raw command string or macro dispatch. A typed safe implementation would be a different operation; CAD OS exposes operation-specific typed handlers instead of a generic raw command API.
- no read/status subset: Executing or queueing a command string has no read-only subset. Command metadata/status is covered by implemented typed operations such as command.register.define, module.command.lookup, and module.command.stack_handle.
- no staged route: Running arbitrary command text on a staged copy bypasses operation schemas and typed handlers, and could still perform unbounded side effects inside the AutoCAD command processor.
- no attended route: A dedicated attended host would still expose arbitrary command text to an editor command stream. Host isolation does not convert raw command dispatch into a bounded operation.
- no policy-gated replacement: A policy-gated generic command route would still expose raw command semantics. The replacement is typed CAD OS operations and operation-specific handlers, not command-string execution.

### edit.assocarray.explode
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#edit-assocarray-explode`
- agent_exposed: `False`
- replacement_ref: `inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact assoc-array operation invokes layout creation, item replacement, reset, transform, or explode semantics that rely on AcDbAssocArrayActionBody evaluation. The solver-free typed subset is implemented as separate read/status/audit operations.
- no read/status subset: Read/status coverage exists separately through inspect.assocarray.identify, inspect.assocmanager.state, and related assoc network inspection. Reclassifying this mutating op as read-only would hide implementation debt.
- no staged route: A staged copy prevents original DWG writes but does not make associative layout evaluation bounded or solver-free; the evaluator may recompute dependencies and generated geometry.
- no attended route: A dedicated attended host does not remove the unsafe evaluator semantics; the blocker is solver execution, not only host availability.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocarray.identify, inspect.assocmanager.state, and repair.assocdata.audit; the mutating array operation itself remains blocked.

### edit.assocarray.item
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#edit-assocarray-item`
- agent_exposed: `False`
- replacement_ref: `inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact assoc-array operation invokes layout creation, item replacement, reset, transform, or explode semantics that rely on AcDbAssocArrayActionBody evaluation. The solver-free typed subset is implemented as separate read/status/audit operations.
- no read/status subset: Read/status coverage exists separately through inspect.assocarray.identify, inspect.assocmanager.state, and related assoc network inspection. Reclassifying this mutating op as read-only would hide implementation debt.
- no staged route: A staged copy prevents original DWG writes but does not make associative layout evaluation bounded or solver-free; the evaluator may recompute dependencies and generated geometry.
- no attended route: A dedicated attended host does not remove the unsafe evaluator semantics; the blocker is solver execution, not only host availability.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocarray.identify, inspect.assocmanager.state, and repair.assocdata.audit; the mutating array operation itself remains blocked.

### edit.assocarray.itemReplace
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#edit-assocarray-itemReplace`
- agent_exposed: `False`
- replacement_ref: `inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact assoc-array operation invokes layout creation, item replacement, reset, transform, or explode semantics that rely on AcDbAssocArrayActionBody evaluation. The solver-free typed subset is implemented as separate read/status/audit operations.
- no read/status subset: Read/status coverage exists separately through inspect.assocarray.identify, inspect.assocmanager.state, and related assoc network inspection. Reclassifying this mutating op as read-only would hide implementation debt.
- no staged route: A staged copy prevents original DWG writes but does not make associative layout evaluation bounded or solver-free; the evaluator may recompute dependencies and generated geometry.
- no attended route: A dedicated attended host does not remove the unsafe evaluator semantics; the blocker is solver execution, not only host availability.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocarray.identify, inspect.assocmanager.state, and repair.assocdata.audit; the mutating array operation itself remains blocked.

### edit.assocarray.reset
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#edit-assocarray-reset`
- agent_exposed: `False`
- replacement_ref: `inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact assoc-array operation invokes layout creation, item replacement, reset, transform, or explode semantics that rely on AcDbAssocArrayActionBody evaluation. The solver-free typed subset is implemented as separate read/status/audit operations.
- no read/status subset: Read/status coverage exists separately through inspect.assocarray.identify, inspect.assocmanager.state, and related assoc network inspection. Reclassifying this mutating op as read-only would hide implementation debt.
- no staged route: A staged copy prevents original DWG writes but does not make associative layout evaluation bounded or solver-free; the evaluator may recompute dependencies and generated geometry.
- no attended route: A dedicated attended host does not remove the unsafe evaluator semantics; the blocker is solver execution, not only host availability.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocarray.identify, inspect.assocmanager.state, and repair.assocdata.audit; the mutating array operation itself remains blocked.

### edit.assocarray.source
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#edit-assocarray-source`
- agent_exposed: `False`
- replacement_ref: `inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact assoc-array operation invokes layout creation, item replacement, reset, transform, or explode semantics that rely on AcDbAssocArrayActionBody evaluation. The solver-free typed subset is implemented as separate read/status/audit operations.
- no read/status subset: Read/status coverage exists separately through inspect.assocarray.identify, inspect.assocmanager.state, and related assoc network inspection. Reclassifying this mutating op as read-only would hide implementation debt.
- no staged route: A staged copy prevents original DWG writes but does not make associative layout evaluation bounded or solver-free; the evaluator may recompute dependencies and generated geometry.
- no attended route: A dedicated attended host does not remove the unsafe evaluator semantics; the blocker is solver execution, not only host availability.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocarray.identify, inspect.assocmanager.state, and repair.assocdata.audit; the mutating array operation itself remains blocked.

### edit.assocarray.transform
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#edit-assocarray-transform`
- agent_exposed: `False`
- replacement_ref: `inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: The exact assoc-array operation invokes layout creation, item replacement, reset, transform, or explode semantics that rely on AcDbAssocArrayActionBody evaluation. The solver-free typed subset is implemented as separate read/status/audit operations.
- no read/status subset: Read/status coverage exists separately through inspect.assocarray.identify, inspect.assocmanager.state, and related assoc network inspection. Reclassifying this mutating op as read-only would hide implementation debt.
- no staged route: A staged copy prevents original DWG writes but does not make associative layout evaluation bounded or solver-free; the evaluator may recompute dependencies and generated geometry.
- no attended route: A dedicated attended host does not remove the unsafe evaluator semantics; the blocker is solver execution, not only host availability.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocarray.identify, inspect.assocmanager.state, and repair.assocdata.audit; the mutating array operation itself remains blocked.

### embed.ole.frame
- family: `com_activex`
- blocker_code: `HOST_UNAVAILABLE`
- blocker_ref: `reports/WAVE3_REMAINING_HARDBLOCK_REAUDIT.md#embed.ole.frame`
- agent_exposed: `False`
- replacement_ref: `automate.com.wrapper_for_object + automate.com.entity_helpers (metadata-only; no OLE embed/link mutation)`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: AcDbOle2Frame embedding/linking requires a live OLE client item/server and payload contract. Existing COM metadata routes do not create or mutate OLE frame entities.
- no read/status subset: Metadata-only COM/ObjectId routes are implemented separately. No controlled OLE frame fixture/payload contract exists to prove a bounded AcDbOle2Frame introspection subset for this exact op.
- no staged route: Embedding or linking OLE into a staged copy still requires live OLE server state and binary payload handling outside CAD OS typed patch contracts.
- no attended route: A controlled attended OLE route has not been proven available and would need a dedicated OLE client item harness; no user AutoCAD session may be touched.
- no policy-gated replacement: Policy-gated replacement is metadata-only through automate.com.wrapper_for_object and automate.com.entity_helpers; OLE embed/link mutation remains blocked.

### inspect.assocaction.evaluate
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#inspect-assocaction-evaluate`
- agent_exposed: `False`
- replacement_ref: `inspect.assocaction.dependencies + inspect.assocaction.requestToEvaluate + inspect.assocmanager.state`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: AcDbAssocAction::evaluate runs a single action evaluator callback. CAD OS implements safe typed inspection around the network, not evaluator execution.
- no read/status subset: Read/status coverage exists through inspect.assocaction.dependencies, inspect.assocaction.requestToEvaluate, and inspect.assocmanager.state. Calling this operation name without evaluating would be a fake PASS.
- no staged route: A staged copy avoids original writes but still executes arbitrary action/network callbacks and dependency recomputation.
- no attended route: A dedicated AutoCAD instance still runs the same evaluator/callback graph; host isolation does not bound user-defined or object-enabler behavior.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocaction.dependencies, inspect.assocaction.requestToEvaluate, and inspect.assocmanager.state; evaluator execution remains blocked.

### inspect.assocnetwork.evaluate
- family: `constraints_associativity`
- blocker_code: `SAFETY_FORBIDDEN`
- blocker_ref: `reports/WAVE4X_FINAL_A_HARDBLOCK_DECISIONS.md#inspect-assocnetwork-evaluate`
- agent_exposed: `False`
- replacement_ref: `inspect.assocnetwork.get + inspect.assocnetwork.iterate + inspect.assocmanager.state`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: AcDbAssocManager::evaluateTopLevelNetwork runs the top-level network evaluator. CAD OS implements safe typed inspection around the network, not evaluator execution.
- no read/status subset: Read/status coverage exists through inspect.assocnetwork.get, inspect.assocnetwork.iterate, and inspect.assocmanager.state. Calling this operation name without evaluating would be a fake PASS.
- no staged route: A staged copy avoids original writes but still executes arbitrary action/network callbacks and dependency recomputation.
- no attended route: A dedicated AutoCAD instance still runs the same evaluator/callback graph; host isolation does not bound user-defined or object-enabler behavior.
- no policy-gated replacement: Policy-gated replacement exists through inspect.assocnetwork.get, inspect.assocnetwork.iterate, and inspect.assocmanager.state; evaluator execution remains blocked.

### module.lifecycle.on_ole_unload
- family: `runtime_commands`
- blocker_code: `HOST_UNAVAILABLE`
- blocker_ref: `reports/WAVE3_REMAINING_HARDBLOCK_REAUDIT.md#module.lifecycle.on_ole_unload`
- agent_exposed: `False`
- replacement_ref: `module.lifecycle.unload + module.lifecycle.on_unload_dwg (status/evidence only; no OLE unload callback synthesis)`
- non_agent_exposure_test: `tests/unit/test_wave4x_final_a_hardblock_contract.py`
- no typed safe route: On_kOleUnloadAppMsg is a host-delivered OLE lifecycle callback. Synthesizing it would fake or interfere with AutoCAD loader/OLE state.
- no read/status subset: Safe lifecycle status/evidence is implemented through module.lifecycle.unload and module.lifecycle.on_unload_dwg; this OLE-specific callback has no read-only invocation subset.
- no staged route: A staged drawing copy does not create an OLE unload lifecycle event; the callback is tied to host app unload state.
- no attended route: A dedicated instance cannot safely force OLE unload callback delivery without an OLE in-use payload and controlled host lifecycle harness.
- no policy-gated replacement: Policy-gated replacement is lifecycle status evidence through module.lifecycle.unload and module.lifecycle.on_unload_dwg; OLE unload callback synthesis remains blocked.
