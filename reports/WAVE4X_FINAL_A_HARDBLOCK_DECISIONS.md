# WAVE4X Final A Hardblock Decisions

- reimplemented exact blocked ops: 0
- replaced with safe routes / explicit policy refs: 29
- remaining hardblocks: 29

## Decisions

- `automate.com.send_command`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers`
- `command.invoke.coroutine`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers`
- `command.invoke.sync`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers`
- `command.invoke.sync.resbuf`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers`
- `command.menu.invoke`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers`
- `command.queue.post`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers`
- `define.assocarray.create`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- `define.assocarray.path`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- `define.assocarray.polar`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- `define.assocarray.rectangular`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- `define.assocsurface.blend`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocsurface.topology + repair.assocdata.audit`
- `define.assocsurface.extrude`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocsurface.topology + repair.assocdata.audit`
- `define.assocsurface.fillet`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocsurface.topology + repair.assocdata.audit`
- `define.assocsurface.loft`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocsurface.topology + repair.assocdata.audit`
- `define.assocsurface.offset`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocsurface.topology + repair.assocdata.audit`
- `define.assocsurface.patch`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocsurface.topology + repair.assocdata.audit`
- `define.assocsurface.result`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocsurface.topology + repair.assocdata.audit`
- `define.assocsurface.trim`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocsurface.topology + repair.assocdata.audit`
- `doc.sendstring`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers`
- `edit.assocarray.explode`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- `edit.assocarray.item`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- `edit.assocarray.itemReplace`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- `edit.assocarray.reset`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- `edit.assocarray.source`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- `edit.assocarray.transform`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit`
- `embed.ole.frame`: `HOST_UNAVAILABLE`, agent_exposed=false, replacement=`automate.com.wrapper_for_object + automate.com.entity_helpers (metadata-only; no OLE embed/link mutation)`
- `inspect.assocaction.evaluate`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocaction.dependencies + inspect.assocaction.requestToEvaluate + inspect.assocmanager.state`
- `inspect.assocnetwork.evaluate`: `SAFETY_FORBIDDEN`, agent_exposed=false, replacement=`inspect.assocnetwork.get + inspect.assocnetwork.iterate + inspect.assocmanager.state`
- `module.lifecycle.on_ole_unload`: `HOST_UNAVAILABLE`, agent_exposed=false, replacement=`module.lifecycle.unload + module.lifecycle.on_unload_dwg (status/evidence only; no OLE unload callback synthesis)`
