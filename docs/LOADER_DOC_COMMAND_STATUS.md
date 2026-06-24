# Loader / Doc / Command Status

Wave4X Pane 2 implemented safe typed status handlers for loader and command-stack operations without exposing arbitrary command strings or external module load/unload mutation.

## Safe implemented route

- Native dispatcher: `m08nDispatch`
- Source: `src/Ariadne.AcadNative/families/m08n_handlers.inc`
- Registry: `config/operations.v2.json`
- Implemented operation count change: `457 -> 464`
- Blocked operation count change: `60 -> 53`

## Implemented operations
- `module.command.lookup`
- `module.command.remove_group`
- `module.load`
- `module.load.acad_rx`
- `module.load.by_app`
- `module.load.demand_register`
- `module.unload`

## Preserved safety blockers
- `doc.sendstring`: SAFETY_FORBIDDEN: doc.sendstring is a raw command surface because it queues arbitrary command strings into a document command stream; Wave4X keeps it non-agent-exposed and requires bespoke typed handlers instead.
- `module.entrypoint.define`: SDK_NOT_EXPOSED: entrypoint definition is a compile/link macro/export contract, not a runtime job operation.
- `module.entrypoint.dispatch`: HOST_UNAVAILABLE: acrxEntryPoint dispatch is owned by the AutoCAD loader and cannot be synthesized by the job dispatcher.
- `module.lifecycle.init`: HOST_UNAVAILABLE: On_kInitAppMsg is delivered by the AutoCAD loader during module load and is not a runtime job operation.
- `module.lifecycle.on_load_dwg`: HOST_UNAVAILABLE: On_kLoadDwgMsg is delivered by host document lifecycle dispatch; no controlled attended lifecycle route is available in this worktree.
- `module.lifecycle.on_unload_dwg`: HOST_UNAVAILABLE: On_kUnloadDwgMsg is host-owned document lifecycle dispatch and unavailable to the integration job route.
- `module.lifecycle.other`: HOST_UNAVAILABLE: arbitrary lifecycle message dispatch is host-owned and cannot be simulated safely by the agent job surface.
- `module.lifecycle.unload`: HOST_UNAVAILABLE: On_kUnloadAppMsg is delivered by the loader during module unload; the job dispatcher must not invoke it directly.

## Safety boundary
- No original DWG write.
- No raw AutoCAD command agent surface.
- No arbitrary module load/unload.
- No demand-load registry mutation.
- No canonical deploy or merge.
