# WAVE4X Loader / Doc / Command Result

- Status: `PASS_WITH_HARD_BLOCKS`
- Branch: `cados/w4x-loader-doc-command`
- Claim file: `reports/tickets/WAVE4X_PANE2_LOADER_DOC_CLAIMS.json`
- No original DWG write, no raw command surface, no Ariadne runtime writes, no push, no merge.

## Implemented operations
- `module.command.lookup`: Read-only command-stack lookup contract for bounded ARIADNE command names; never executes command strings.
- `module.command.remove_group`: Bounded ARIADNE_W4X_LOADER_DOC command-group cleanup only; arbitrary group removal is not exposed.
- `module.load`: Read-only current Ariadne native module loaded-status detection; never loads external code.
- `module.load.acad_rx`: Read-only acad.rx file presence/status detection; never mutates autoload files.
- `module.load.by_app`: Read-only registered-app load validation contract; never invokes load-by-app.
- `module.load.demand_register`: Demand-load registration plan validation for bounded Ariadne metadata; never writes registry keys.
- `module.unload`: Read-only unload safety/status contract for the current Ariadne module; never unloads modules.

## Still hard-blocked operations
- `doc.sendstring`: SAFETY_FORBIDDEN: doc.sendstring is a raw command surface because it queues arbitrary command strings into a document command stream; Wave4X keeps it non-agent-exposed and requires bespoke typed handlers instead.
- `module.entrypoint.define`: SDK_NOT_EXPOSED: entrypoint definition is a compile/link macro/export contract, not a runtime job operation.
- `module.entrypoint.dispatch`: HOST_UNAVAILABLE: acrxEntryPoint dispatch is owned by the AutoCAD loader and cannot be synthesized by the job dispatcher.
- `module.lifecycle.init`: HOST_UNAVAILABLE: On_kInitAppMsg is delivered by the AutoCAD loader during module load and is not a runtime job operation.
- `module.lifecycle.on_load_dwg`: HOST_UNAVAILABLE: On_kLoadDwgMsg is delivered by host document lifecycle dispatch; no controlled attended lifecycle route is available in this worktree.
- `module.lifecycle.on_unload_dwg`: HOST_UNAVAILABLE: On_kUnloadDwgMsg is host-owned document lifecycle dispatch and unavailable to the integration job route.
- `module.lifecycle.other`: HOST_UNAVAILABLE: arbitrary lifecycle message dispatch is host-owned and cannot be simulated safely by the agent job surface.
- `module.lifecycle.unload`: HOST_UNAVAILABLE: On_kUnloadAppMsg is delivered by the loader during module unload; the job dispatcher must not invoke it directly.

## Deprecated operations
- None

## Validation
- `pytest`: 494 passed, 20 skipped
- `cadctl_registry_coverage`: status ok; operation_count 517; wired_count 464; by_status implemented=464 blocked=53; consistent=true
- `reconcile_native_registry`: dry-run ok; coded=424 flips=0 overlaps=424 conflicts=0 drift=0
- `operation_coverage_json`: valid json
- `native_build`: ok; dbx=54272 bytes; crx=762880 bytes; arx=771584 bytes; LNK4099 Autodesk PDB warnings only

## Native build
- Isolated worktree build completed. Artifacts remained under `src/Ariadne.AcadNative/bin/x64/Release/`.
- Build output reported `status: ok`; only Autodesk `rxapi.pdb` LNK4099 warnings were emitted.

## Attended requirements
- Implemented handlers are status/introspection or bounded cleanup and do not require attended verification.
- Future lifecycle callback firing would require a controlled attended/full AutoCAD route and remains hard-blocked here.
