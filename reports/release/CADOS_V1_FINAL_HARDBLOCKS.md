# CAD OS v1 Final Hardblocks

- Packet: CADOS_M09_V1_RELEASE_FREEZE_AND_DAEDALUS_HANDOFF
- Status: PASS
- Count: 29

| operation | family | blocker_code | agent_exposed |
|---|---|---|---:|
| automate.com.send_command | com_activex | SAFETY_FORBIDDEN | False |
| command.invoke.coroutine | active_document_write_original | SAFETY_FORBIDDEN | False |
| command.invoke.sync | active_document_write_original | SAFETY_FORBIDDEN | False |
| command.invoke.sync.resbuf | active_document_write_original | SAFETY_FORBIDDEN | False |
| command.menu.invoke | ui_customization | SAFETY_FORBIDDEN | False |
| command.queue.post | editor_input | SAFETY_FORBIDDEN | False |
| define.assocarray.create | constraints_associativity | SAFETY_FORBIDDEN | False |
| define.assocarray.path | constraints_associativity | SAFETY_FORBIDDEN | False |
| define.assocarray.polar | constraints_associativity | SAFETY_FORBIDDEN | False |
| define.assocarray.rectangular | constraints_associativity | SAFETY_FORBIDDEN | False |
| define.assocsurface.blend | constraints_associativity | SAFETY_FORBIDDEN | False |
| define.assocsurface.extrude | constraints_associativity | SAFETY_FORBIDDEN | False |
| define.assocsurface.fillet | constraints_associativity | SAFETY_FORBIDDEN | False |
| define.assocsurface.loft | constraints_associativity | SAFETY_FORBIDDEN | False |
| define.assocsurface.offset | constraints_associativity | SAFETY_FORBIDDEN | False |
| define.assocsurface.patch | constraints_associativity | SAFETY_FORBIDDEN | False |
| define.assocsurface.result | constraints_associativity | SAFETY_FORBIDDEN | False |
| define.assocsurface.trim | constraints_associativity | SAFETY_FORBIDDEN | False |
| doc.sendstring | active_document_write_original | SAFETY_FORBIDDEN | False |
| edit.assocarray.explode | constraints_associativity | SAFETY_FORBIDDEN | False |
| edit.assocarray.item | constraints_associativity | SAFETY_FORBIDDEN | False |
| edit.assocarray.itemReplace | constraints_associativity | SAFETY_FORBIDDEN | False |
| edit.assocarray.reset | constraints_associativity | SAFETY_FORBIDDEN | False |
| edit.assocarray.source | constraints_associativity | SAFETY_FORBIDDEN | False |
| edit.assocarray.transform | constraints_associativity | SAFETY_FORBIDDEN | False |
| embed.ole.frame | com_activex | HOST_UNAVAILABLE | False |
| inspect.assocaction.evaluate | constraints_associativity | SAFETY_FORBIDDEN | False |
| inspect.assocnetwork.evaluate | constraints_associativity | SAFETY_FORBIDDEN | False |
| module.lifecycle.on_ole_unload | runtime_commands | HOST_UNAVAILABLE | False |

Each row in the JSON report includes blocker_ref, evidence_ref, replacement_ref where available, final reason, no-safe-route explanation, and blocked behavior tests.
