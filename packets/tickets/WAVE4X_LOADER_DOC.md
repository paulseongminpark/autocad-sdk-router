# WAVE4X_LOADER_DOC Packet

[WAVE4X LOADER DOC RESULT]
STATUS: PASS_WITH_HARD_BLOCKS
BRANCH: cados/w4x-loader-doc-command
COMMIT: PENDING_LOCAL_COMMIT
IMPLEMENTED_OPS: module.command.lookup, module.command.remove_group, module.load, module.load.acad_rx, module.load.by_app, module.load.demand_register, module.unload
STILL_HARD_BLOCKED_OPS: doc.sendstring, module.entrypoint.define, module.entrypoint.dispatch, module.lifecycle.init, module.lifecycle.on_load_dwg, module.lifecycle.on_unload_dwg, module.lifecycle.other, module.lifecycle.unload
DEPRECATED_OPS: none
NATIVE_BUILD: ok; dbx=54272 bytes; crx=762880 bytes; arx=771584 bytes; LNK4099 Autodesk PDB warnings only
ATTENDED_REQUIRED: no for implemented handlers; yes for any future controlled lifecycle callback route
TESTS: pytest=494 passed, 20 skipped; cadctl_registry_coverage=status ok; operation_count 517; wired_count 464; by_status implemented=464 blocked=53; consistent=true; reconcile_native_registry=dry-run ok; coded=424 flips=0 overlaps=424 conflicts=0 drift=0; operation_coverage_json=valid json; native_build=ok; dbx=54272 bytes; crx=762880 bytes; arx=771584 bytes; LNK4099 Autodesk PDB warnings only
BLOCKERS: doc.sendstring => SAFETY_FORBIDDEN: doc.sendstring is a raw command surface because it queues arbitrary command strings into a document command stream; Wave4X keeps it non-agent-exposed and requires bespoke typed handlers instead. | module.entrypoint.define => SDK_NOT_EXPOSED: entrypoint definition is a compile/link macro/export contract, not a runtime job operation. | module.entrypoint.dispatch => HOST_UNAVAILABLE: acrxEntryPoint dispatch is owned by the AutoCAD loader and cannot be synthesized by the job dispatcher. | module.lifecycle.init => HOST_UNAVAILABLE: On_kInitAppMsg is delivered by the AutoCAD loader during module load and is not a runtime job operation. | module.lifecycle.on_load_dwg => HOST_UNAVAILABLE: On_kLoadDwgMsg is delivered by host document lifecycle dispatch; no controlled attended lifecycle route is available in this worktree. | module.lifecycle.on_unload_dwg => HOST_UNAVAILABLE: On_kUnloadDwgMsg is host-owned document lifecycle dispatch and unavailable to the integration job route. | module.lifecycle.other => HOST_UNAVAILABLE: arbitrary lifecycle message dispatch is host-owned and cannot be simulated safely by the agent job surface. | module.lifecycle.unload => HOST_UNAVAILABLE: On_kUnloadAppMsg is delivered by the loader during module unload; the job dispatcher must not invoke it directly.
NEXT: Pane 1 merge allocator review; no canonical deploy or main merge by this pane
[/WAVE4X LOADER DOC RESULT]
