# WAVE4X Final A Hardblock Reimplementation

- status: `PASS`
- base: `cados/wave4x-fast-a-main-ready@f5f950c`
- merged Fast B: `yes` (`cados/wave4x-fast-b-on-fast-a-truth@ec92ee9`)
- operation counts after: implemented 487 / hard_blocked 29 / deprecated 1 / catalogued 0 / stub 0 / unknown 0 / deferred 0
- reimplemented exact blocked operations: `0`
- safe replacements / policy-gated routes attached: `29`
- remaining hardblocks: `29`
- hardblock reason counts: `{'SAFETY_FORBIDDEN': 27, 'HOST_UNAVAILABLE': 2}`
- tests: `546 passed / 20 skipped`; skip audit: live/attended/env 3, missing generated fixture/run artifact 17, unexpected 0
- native build: `ok`
- raw command exposure: `false`
- live.apply_patch: deprecated; replacement `apply.patch + tools/patch_engine.py::apply_native_staged`
- original DWG modified: `false`

## Remaining Hardblocks

- `automate.com.send_command`: SAFETY_FORBIDDEN -> typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers
- `command.invoke.coroutine`: SAFETY_FORBIDDEN -> typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers
- `command.invoke.sync`: SAFETY_FORBIDDEN -> typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers
- `command.invoke.sync.resbuf`: SAFETY_FORBIDDEN -> typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers
- `command.menu.invoke`: SAFETY_FORBIDDEN -> typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers
- `command.queue.post`: SAFETY_FORBIDDEN -> typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers
- `define.assocarray.create`: SAFETY_FORBIDDEN -> inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit
- `define.assocarray.path`: SAFETY_FORBIDDEN -> inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit
- `define.assocarray.polar`: SAFETY_FORBIDDEN -> inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit
- `define.assocarray.rectangular`: SAFETY_FORBIDDEN -> inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit
- `define.assocsurface.blend`: SAFETY_FORBIDDEN -> inspect.assocsurface.topology + repair.assocdata.audit
- `define.assocsurface.extrude`: SAFETY_FORBIDDEN -> inspect.assocsurface.topology + repair.assocdata.audit
- `define.assocsurface.fillet`: SAFETY_FORBIDDEN -> inspect.assocsurface.topology + repair.assocdata.audit
- `define.assocsurface.loft`: SAFETY_FORBIDDEN -> inspect.assocsurface.topology + repair.assocdata.audit
- `define.assocsurface.offset`: SAFETY_FORBIDDEN -> inspect.assocsurface.topology + repair.assocdata.audit
- `define.assocsurface.patch`: SAFETY_FORBIDDEN -> inspect.assocsurface.topology + repair.assocdata.audit
- `define.assocsurface.result`: SAFETY_FORBIDDEN -> inspect.assocsurface.topology + repair.assocdata.audit
- `define.assocsurface.trim`: SAFETY_FORBIDDEN -> inspect.assocsurface.topology + repair.assocdata.audit
- `doc.sendstring`: SAFETY_FORBIDDEN -> typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers
- `edit.assocarray.explode`: SAFETY_FORBIDDEN -> inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit
- `edit.assocarray.item`: SAFETY_FORBIDDEN -> inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit
- `edit.assocarray.itemReplace`: SAFETY_FORBIDDEN -> inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit
- `edit.assocarray.reset`: SAFETY_FORBIDDEN -> inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit
- `edit.assocarray.source`: SAFETY_FORBIDDEN -> inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit
- `edit.assocarray.transform`: SAFETY_FORBIDDEN -> inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit
- `embed.ole.frame`: HOST_UNAVAILABLE -> automate.com.wrapper_for_object + automate.com.entity_helpers (metadata-only; no OLE embed/link mutation)
- `inspect.assocaction.evaluate`: SAFETY_FORBIDDEN -> inspect.assocaction.dependencies + inspect.assocaction.requestToEvaluate + inspect.assocmanager.state
- `inspect.assocnetwork.evaluate`: SAFETY_FORBIDDEN -> inspect.assocnetwork.get + inspect.assocnetwork.iterate + inspect.assocmanager.state
- `module.lifecycle.on_ole_unload`: HOST_UNAVAILABLE -> module.lifecycle.unload + module.lifecycle.on_unload_dwg (status/evidence only; no OLE unload callback synthesis)

## Why No More Exact Implementations

The remaining exact operations are raw command dispatch, associative solver/modeler execution, OLE embed/link lifecycle, or OLE unload callback delivery. For each one, Final A added explicit audit answers in `config/operations.v2.json` and replacement refs to existing typed/read/staged/status operations where feasible. Exact execution remains blocked only under allowed reasons: `SAFETY_FORBIDDEN` or `HOST_UNAVAILABLE`.
