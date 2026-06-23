# Wave3 Pane 6 Demand-Register Re-Audit

Scope: `extend.object_enabler.demand_register`.

Decision: implemented as safe registration-plan introspection, not as install-time mutation.

The exact install-time registry write is not exposed from the CAD OS runtime job surface. The implementation in `src/Ariadne.AcadNative/families/m08k_handlers.inc` reports the ObjectARX demand-load registration plan, current module registration context, and canonical registry keys/values without calling registry mutation APIs.

Safety properties:
- no `RegSetValue`, `SHSetValue`, or `RegCreateKey`
- no deploy-time registry write
- no original DWG write
- no raw command surface

Evidence:
- `tests/unit/test_m08k_handlers.py` requires `extend.object_enabler.demand_register` in `m08kHasOp`.
- `tests/unit/test_m08k_handlers.py` requires the `registration_plan_only` mode marker.
- `tests/unit/test_m08k_handlers.py` bans registry write APIs in the handler source.
