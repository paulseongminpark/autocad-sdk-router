# Wave3 Pane 5 Associativity Re-Audit

Scope: re-audit of the Pane 5 AcDbAssoc solver/modeler/callback operations after Wave3 merge.

Rule applied: Pane hard-blocks were not accepted blindly. Each operation was checked for a feasible safe status, registration, callback, or introspection implementation before accepting a hard block.

## Reversed To Implemented

### config.assoceval.callback

Decision: implemented.

Implementation: `src/Ariadne.AcadNative/families/m08kc_handlers.inc` uses `AcDbAssocManager::getGlobalEvaluationCallbacks(callbacks, orders)` as a read-only callback inventory. It does not add, remove, or invoke callbacks.

Evidence: `tests/unit/test_wave3_pane5_assoc_reaudit.py` and `tests/unit/test_m08kc_handlers.py`.

### config.constraint.globalCallback

Decision: implemented.

Implementation: `src/Ariadne.AcadNative/families/m08kc_handlers.inc` reads `AcDbAssoc2dConstraintGroup::globalCallback()` and reports callback/status flags. It does not install or execute a callback.

Evidence: `tests/unit/test_wave3_pane5_assoc_reaudit.py` and `tests/unit/test_m08kc_handlers.py`.

## Accepted Hard Blocks

The remaining Pane 5 AcDbAssoc array, surface, evaluation, xref, audit, and solver-execution operations remain hard-blocked after re-audit with `SAFETY_FORBIDDEN`.

Reason: executing or mutating the associative solver/modeler graph can change constraint state, geometry dependencies, evaluation order, or host-owned callback execution. The integration pass implemented the safe read/status/callback-introspection subset instead of exposing solver execution as an agent tool.

Evidence: `tests/unit/test_wave3_pane5_assoc_reaudit.py` verifies the implemented callback subset and requires each remaining hard block to carry `SAFETY_FORBIDDEN` plus this report reference.
