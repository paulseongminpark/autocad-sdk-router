# WAVE4X Fast B Live Apply Policy R2

- status: **PASS**
- decision: `deprecated_safe_replacement`
- replacement_ref: `apply.patch + tools/patch_engine.py::apply_native_staged`
- status_policy: `deprecated`
- allowed_write_modes: `['read']`
- agent_exposed: `False`

## Notes
Deprecated in WAVE4X. live.apply_patch remains policy-denied on the live pump; use apply.patch / patch_engine.apply_staged (or apply_native_staged for a direct native op) on a staged copy.
