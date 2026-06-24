# WAVE4X Final A Hardblock Targets

- count: 29
- by code: `{'SAFETY_FORBIDDEN': 27, 'HOST_UNAVAILABLE': 2}`

| operation | family | blocker | agent_exposed | replacement_ref | decision |
|---|---|---|---|---|---|
| `automate.com.send_command` | com_activex | SAFETY_FORBIDDEN | False | typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers | hard_block_likely |
| `command.invoke.coroutine` | active_document_write_original | SAFETY_FORBIDDEN | False | typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers | hard_block_likely |
| `command.invoke.sync` | active_document_write_original | SAFETY_FORBIDDEN | False | typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers | hard_block_likely |
| `command.invoke.sync.resbuf` | active_document_write_original | SAFETY_FORBIDDEN | False | typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers | hard_block_likely |
| `command.menu.invoke` | ui_customization | SAFETY_FORBIDDEN | False | typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers | hard_block_likely |
| `command.queue.post` | editor_input | SAFETY_FORBIDDEN | False | typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers | hard_block_likely |
| `define.assocarray.create` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit | hard_block_likely |
| `define.assocarray.path` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit | hard_block_likely |
| `define.assocarray.polar` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit | hard_block_likely |
| `define.assocarray.rectangular` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit | hard_block_likely |
| `define.assocsurface.blend` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocsurface.topology + repair.assocdata.audit | hard_block_likely |
| `define.assocsurface.extrude` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocsurface.topology + repair.assocdata.audit | hard_block_likely |
| `define.assocsurface.fillet` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocsurface.topology + repair.assocdata.audit | hard_block_likely |
| `define.assocsurface.loft` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocsurface.topology + repair.assocdata.audit | hard_block_likely |
| `define.assocsurface.offset` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocsurface.topology + repair.assocdata.audit | hard_block_likely |
| `define.assocsurface.patch` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocsurface.topology + repair.assocdata.audit | hard_block_likely |
| `define.assocsurface.result` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocsurface.topology + repair.assocdata.audit | hard_block_likely |
| `define.assocsurface.trim` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocsurface.topology + repair.assocdata.audit | hard_block_likely |
| `doc.sendstring` | active_document_write_original | SAFETY_FORBIDDEN | False | typed CAD OS operation handlers only; examples: command.register.define + module.command.lookup + module.command.stack_handle + operation-specific implemented handlers | hard_block_likely |
| `edit.assocarray.explode` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit | hard_block_likely |
| `edit.assocarray.item` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit | hard_block_likely |
| `edit.assocarray.itemReplace` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit | hard_block_likely |
| `edit.assocarray.reset` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit | hard_block_likely |
| `edit.assocarray.source` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit | hard_block_likely |
| `edit.assocarray.transform` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocarray.identify + inspect.assocmanager.state + repair.assocdata.audit | hard_block_likely |
| `embed.ole.frame` | com_activex | HOST_UNAVAILABLE | False | automate.com.wrapper_for_object + automate.com.entity_helpers (metadata-only; no OLE embed/link mutation) | hard_block_likely |
| `inspect.assocaction.evaluate` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocaction.dependencies + inspect.assocaction.requestToEvaluate + inspect.assocmanager.state | hard_block_likely |
| `inspect.assocnetwork.evaluate` | constraints_associativity | SAFETY_FORBIDDEN | False | inspect.assocnetwork.get + inspect.assocnetwork.iterate + inspect.assocmanager.state | hard_block_likely |
| `module.lifecycle.on_ole_unload` | runtime_commands | HOST_UNAVAILABLE | False | module.lifecycle.unload + module.lifecycle.on_unload_dwg (status/evidence only; no OLE unload callback synthesis) | hard_block_likely |
