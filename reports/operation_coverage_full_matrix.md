# CAD OS — Full Operation Coverage Matrix (M08)

- packet: `CADOS_M08_FULL_OPERATION_COVERAGE_CLOSURE`
- generated_from: `config/operations.v2.json`
- total operations: **517** · implemented 451 · stub 0 · blocked 10 · catalogued 56 · deprecated 0 · **unknown 0**
- v1-target: **461** (implemented 451 · blocked 10 · **deferred 0**)
- agent-exposed ops: 451

## Gate

| check | pass |
|---|---|
| all_classified | PASS |
| zero_unknown | PASS |
| zero_missing_field | PASS |
| zero_untested_implemented | PASS |
| zero_v1_target_deferred | PASS |
| every_blocked_has_blocker_ref | PASS |
| no_agent_exposed_raw_command | PASS |
| no_original_write_default | PASS |
| existing_29_frozen | PASS |
| v1_target_implemented_or_blocked | PASS |
| gate_pass | PASS |

## Coverage by family group (M08 families)

| group | implemented | stub | blocked | catalogued | v1_target |
|---|---|---|---|---|---|
| read | 53 | 0 | 0 | 0 | 53 |
| query | 1 | 0 | 0 | 0 | 1 |
| write_patch | 16 | 0 | 3 | 1 | 19 |
| validate_diff | 3 | 0 | 0 | 0 | 3 |
| render_visual | 12 | 0 | 0 | 0 | 12 |
| live | 6 | 0 | 1 | 0 | 7 |
| native_only | 360 | 0 | 6 | 55 | 366 |

## Risk class distribution

| risk_class | count |
|---|---|
| read_safe | 349 |
| staged_write | 113 |
| live_edit | 50 |
| raw_command | 5 |

## v1-target operations (the v1 surface — all implemented or hard-blocked)

| operation | family | status | risk_class | write_level | agent_exposed | handler | blocker_ref |
|---|---|---|---|---|---|---|---|
| command.invoke.coroutine | active_document_write_original | blocked | raw_command | live_edit | False | acedCommandC(AcEdCoroutineCallback, void*, int r | SAFETY_FORBIDDEN: raw command dispatch is blocked in M08O fa |
| command.invoke.sync | active_document_write_original | blocked | raw_command | live_edit | False | acedCommandS(int rtype, ...) | SAFETY_FORBIDDEN: raw command dispatch is blocked in M08O fa |
| command.invoke.sync.resbuf | active_document_write_original | blocked | raw_command | live_edit | False | acedCmdS(const resbuf* rb, bool, AcApDocument*) | SAFETY_FORBIDDEN: raw command dispatch is blocked in M08O fa |
| extend.object_enabler.demand_register | custom_objects_protocols | blocked | read_safe | read | False | Registry keys under HKLM\SOFTWARE\Autodesk\Objec | HARD_BLOCKED_SAFETY_CANONICAL_DEPLOY_PANE1_ONLY: demand-load |
| command.queue.post | editor_input | blocked | raw_command | live_edit | False | acedPostCommand / acedPostCommandPrompt() | SAFETY_FORBIDDEN: raw command dispatch is blocked in M08O fa |
| live.apply_patch | live | blocked | live_edit | live_edit | False |  | Requires full_autocad live_edit host + explicit write_origin |
| module.command.lookup | runtime_commands | blocked | raw_command | read | False | acedRegCmds->lookupCmd2(...) via acedCmdLookup2( | SAFETY_FORBIDDEN: raw command dispatch is blocked in M08O fa |
| module.load.demand_register | runtime_commands | blocked | read_safe | read | False | Registry: HKLM\…\R<ver>\<prodkey>\Applications\< | SAFETY_FORBIDDEN: ObjectARX demand-load registration require |
| command.menu.invoke | ui_customization | blocked | read_safe | read | False | acedMenuCmd(const ACHAR*) | SAFETY_FORBIDDEN: acedMenuCmd executes arbitrary menu/comman |
| editor.toolpalette.tool_execute | ui_customization | blocked | read_safe | read | False | AcTcTool::Execute(int nFlag, HWND, POINT, DWORD  | SAFETY_FORBIDDEN: AcTcTool::Execute programmatically fires a |
| doc.current | active_document_write_original | implemented | read_safe | read | True | m08nDispatch |  |
| doc.lock | active_document_write_original | implemented | read_safe | read | True | m08nDispatch |  |
| doc.new | active_document_write_original | implemented | staged_write | write_copy | True | m08nDispatch |  |
| doc.syncopen | active_document_write_original | implemented | read_safe | read | True | m08nDispatch |  |
| apply.patch | apply | implemented | staged_write | write_copy | True | patch_engine.apply_staged |  |
| infra.hostapp.provide_services | blocks_xrefs_clone | implemented | read_safe | read | True | m08eDispatch |  |
| inspect.block.iterate | blocks_xrefs_clone | implemented | read_safe | read | True | m08eDispatch |  |
| transform.database.deep_clone | blocks_xrefs_clone | implemented | live_edit | live_edit | True | m08eDispatch |  |
| transform.database.insert_block | blocks_xrefs_clone | implemented | staged_write | write_copy | True | m08eDispatch |  |
| write.block.append_entity | blocks_xrefs_clone | implemented | staged_write | write_copy | True | m08eDispatch |  |
| compute.brep.line_containment | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| compute.brep.massprops | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| compute.brep.perimeter | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| compute.brep.point_containment | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| compute.brep.surface_area | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| compute.brep.volume | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.brep.bounds | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.brep.changed | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.brep.from_entity | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.brep.from_subentpath | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.brep.owner | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.brep.solid_roundtrip | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.brep.validate | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.brep.validation_level | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.edge.curve | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.edge.curve_as_nurb | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.edge.curve_type | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.edge.orientation | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.edge.vertices | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.face.area | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.face.orientation | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.face.shell | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.face.surface | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.face.surface_as_nurb | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.face.surface_as_trimmed_nurbs | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.face.surface_type | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.loop.face | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.loop.type | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.shell.complex | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.shell.type | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.subentity.class_id | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.subentity.geom_extents | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.subentity.ptr | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.vertex.point | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| traverse.brep.complexes | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| traverse.brep.edges | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| traverse.brep.faces | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| traverse.brep.shells | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| traverse.brep.vertices | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| traverse.complex.shells | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| traverse.edge.loops | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| traverse.face.loops | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| traverse.loop.edges | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| traverse.loop.vertices | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| traverse.shell.faces | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| traverse.vertex.edges | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| traverse.vertex.loops | brep_solids | implemented | read_safe | read | True | m08dDispatch |  |
| automate.com.bridge_objectid | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| automate.com.entity_helpers | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| automate.com.hold_objectref | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| automate.com.lock_document | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| automate.com.objectid_from_iunknown | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| automate.property.set | com_activex | implemented | staged_write | write_copy | True | m08mDispatch |  |
| extend.members.facet_provider | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| extend.opm.define_property | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| extend.opm.define_property2 | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| extend.opm.dialog_property | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| extend.opm.enum_property | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| extend.opm.get_dispid | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| extend.opm.get_manager | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| extend.opm.map_category | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| extend.opm.per_instance_source | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| extend.opm.property_expander | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| extend.opm.property_expression | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| extend.opm.property_extension | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| extend.opm.register_provider | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| extend.property.category | com_activex | implemented | live_edit | live_edit | True | m08mDispatch |  |
| extend.property.com_name | com_activex | implemented | live_edit | live_edit | True | m08mDispatch |  |
| extend.property.default_value | com_activex | implemented | live_edit | live_edit | True | m08mDispatch |  |
| extend.property.define | com_activex | implemented | live_edit | live_edit | True | m08mDispatch |  |
| extend.property.define_collection | com_activex | implemented | live_edit | live_edit | True | m08mDispatch |  |
| extend.property.define_dictionary | com_activex | implemented | live_edit | live_edit | True | m08mDispatch |  |
| extend.property.define_indexed | com_activex | implemented | live_edit | live_edit | True | m08mDispatch |  |
| extend.property.describe | com_activex | implemented | live_edit | live_edit | True | m08mDispatch |  |
| extend.property.display_as | com_activex | implemented | live_edit | live_edit | True | m08mDispatch |  |
| extend.property.enum_tag | com_activex | implemented | live_edit | live_edit | True | m08mDispatch |  |
| extend.property.expose_to_com | com_activex | implemented | live_edit | live_edit | True | m08mDispatch |  |
| extend.property.filepath | com_activex | implemented | live_edit | live_edit | True | m08mDispatch |  |
| extend.property.flags | com_activex | implemented | live_edit | live_edit | True | m08mDispatch |  |
| extend.property.localize_name | com_activex | implemented | live_edit | live_edit | True | m08mDispatch |  |
| extend.property.overrule | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| extend.property.refers_to | com_activex | implemented | live_edit | live_edit | True | m08mDispatch |  |
| extend.property.units | com_activex | implemented | live_edit | live_edit | True | m08mDispatch |  |
| inspect.entity.properties | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| inspect.members.promoted | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| inspect.property.by_name | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| inspect.property.is_readonly | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| inspect.property.metadata | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| inspect.value.to_string | com_activex | implemented | read_safe | read | True | m08mDispatch |  |
| config.assocmanager.evalDisabler | constraints_associativity | implemented | read_safe | read | True | m08kcDispatch |  |
| define.assocaction.addDependency | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.assocaction.create | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.assocaction.valueParam | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.assocdependency.attach | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.assocgeomdependency.subent | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.assocnetwork.addAction | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.assocvaluedependency.value | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.constraint.addGeometry | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.constraint.autoConstrain | constraints_associativity | implemented | live_edit | live_edit | True | m08kcDispatch |  |
| define.constraint.dimensional.angle | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.constraint.dimensional.distance | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.constraint.dimensional.radiusDiameter | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.constraint.geometric | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.constraint.group | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.dimassoc.geometryDriven | constraints_associativity | implemented | live_edit | live_edit | True | m08kcDispatch |  |
| define.georef.subent | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.parameter.merge | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.parameter.variable | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.perssubentid.resolve | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| edit.assocnetwork.removeAction | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| edit.constraint.delete | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| inspect.assocaction.dependencies | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| inspect.assocaction.requestToEvaluate | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| inspect.assocarray.identify | constraints_associativity | implemented | read_safe | read | True | m08kcDispatch |  |
| inspect.assocmanager.state | constraints_associativity | implemented | read_safe | read | True | m08kcDispatch |  |
| inspect.assocnetwork.get | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| inspect.assocnetwork.iterate | constraints_associativity | implemented | read_safe | read | True | m08kcDispatch |  |
| inspect.constraint.dimensional.value | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| inspect.constraint.enumerate | constraints_associativity | implemented | read_safe | read | True | m08kcDispatch |  |
| inspect.constraint.node | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| inspect.constraint.status | constraints_associativity | implemented | read_safe | read | True | m08kcDispatch |  |
| inspect.parameter.evaluate | constraints_associativity | implemented | read_safe | read | True | m08kcDispatch |  |
| extend.customclass.declare | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customclass.define | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customclass.define_cons | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customclass.define_dxf | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customclass.define_nocons | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customclass.rxinit | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customclass.unregister | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.db_defaults | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.define | custom_objects_protocols | implemented | live_edit | live_edit | True | m08kDispatch |  |
| extend.customentity.draw_viewport | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.draw_world | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.explode | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.geom_extents | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.grips | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.intersect | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.list | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.osnap | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.stretch | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.subentpaths | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.transform | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customobject.deepclone | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customobject.define | custom_objects_protocols | implemented | live_edit | live_edit | True | m08kDispatch |  |
| extend.customobject.embedded | custom_objects_protocols | implemented | live_edit | live_edit | True | m08kDispatch |  |
| extend.customobject.filer_dwgin | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customobject.filer_dwgout | custom_objects_protocols | implemented | staged_write | write_copy | True | m08kDispatch |  |
| extend.customobject.filer_dxfin | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customobject.filer_dxfout | custom_objects_protocols | implemented | staged_write | write_copy | True | m08kDispatch |  |
| extend.customobject.partial_undo | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customobject.version | custom_objects_protocols | implemented | live_edit | live_edit | True | m08kDispatch |  |
| extend.customobject.wblockclone | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.module.entrypoint | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.object_enabler.build | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.object_enabler.register_classes | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.osnap.custom_mode | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.protocol.attach | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.protocol.declare | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.protocol.detach | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.protocol.query | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.service.register | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| inspect.proxy.detect | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| inspect.runtime.cast | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| inspect.runtime.desc | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| inspect.runtime.isa | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| inspect.runtime.iskindof | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| overrule.applicable | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| overrule.drawable.install | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| overrule.geometry.install | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| overrule.global.enable | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| overrule.grip.install | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| overrule.highlight.install | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| overrule.highlightstate.install | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| overrule.install | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| overrule.object.install | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| overrule.osnap.install | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| overrule.properties.install | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| overrule.query.has | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| overrule.queryx.install | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| overrule.remove | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| overrule.subentity.install | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| overrule.transform.install | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| overrule.visibility.install | custom_objects_protocols | implemented | read_safe | read | True | m08lDispatch |  |
| diff.before_after | diff | implemented | read_safe | read | True | cad_diff.compute_diff |  |
| editor.react.events | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| input.get.angle | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| input.get.corner | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| input.get.dist | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| input.get.int | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| input.get.keyword | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| input.get.point | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| input.get.real | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| input.get.string | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| input.initget.constrain | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| interact.inputcontext.react | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| interact.inputpoint.filter | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| interact.inputpoint.monitor | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| interact.jig.acquire | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| interact.jig.run | editor_input | implemented | live_edit | live_edit | True | m08nDispatch |  |
| prompt.alert | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| prompt.print | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| select.entity.pick | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| select.nentity.pick | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| select.pickfirst.get | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| select.pickfirst.set | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| select.ss.addremove | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| select.ss.count | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| select.ss.free | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| select.ssget.interactive | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| select.ssget.preview | editor_input | implemented | read_safe | read | True | m08nDispatch |  |
| inspect.curve.protocol | entities | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.entity.common | entities | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.entity.geomextents | entities | implemented | read_safe | read | True | m08dDispatch |  |
| inspect.entity.osnap | entities | implemented | read_safe | read | True | m08dDispatch |  |
| modify.curve.offset | entities | implemented | read_safe | read | True | m08gDispatch |  |
| modify.curve.split | entities | implemented | read_safe | read | True | m08gDispatch |  |
| modify.curve.to_spline | entities | implemented | read_safe | read | True | m08gDispatch |  |
| modify.entity.common | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| modify.entity.copy_transformed | entities | implemented | read_safe | read | True | m08gDispatch |  |
| modify.entity.explode | entities | implemented | read_safe | read | True | m08gDispatch |  |
| write.entity.arc | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.attribdef | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.attribute | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.blockref | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.body | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.dim.aligned | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.dim.angular2line | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.dim.angular3pt | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.dim.arc | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.dim.diametric | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.dim.ordinate | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.dim.radial | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.dim.radiallarge | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.dim.rotated | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.ellipse | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.face | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.hatch | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.leader | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.minsert | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.mleader | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.mline | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.mpolygon | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.mtext | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.nurbsurface | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.polyfacemesh | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.polygonmesh | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.polyline2d | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.polyline3d | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.rasterimage | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.ray | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.region | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.shape | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.solid2d | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.solid3d.extrude | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.solid3d.loft | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.solid3d.primitive | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.solid3d.revolve | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.solid3d.sweep | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.spline | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.subdmesh | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.surface | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.table | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.text | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.trace | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.wipeout | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.xline | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| extend.customclass.create | extend | implemented | live_edit | live_edit | True | createCustomEntity |  |
| extend.customobject.create | extend | implemented | live_edit | live_edit | True | createCustomObject |  |
| compute.entity.intersect | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.geometry.circarc | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.geometry.compositecurve | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.geometry.curve.closest | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.geometry.curve.eval | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.geometry.curve.intersect | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.geometry.curve.sample | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.geometry.elliparc | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.geometry.lineseg | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.geometry.matrix.build | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.geometry.matrix.compose | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.geometry.nurbcurve | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.geometry.point.distance | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.geometry.point.transform | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.geometry.scale.build | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.geometry.surface.nurb | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.geometry.tolerance | geometry_kernel | implemented | read_safe | read | True | m08dDispatch |  |
| compute.solid3d.interference | geometry_kernel | implemented | staged_write | write_copy | True | m08dDispatch |  |
| modify.entity.solid3d.boolean | geometry_kernel | implemented | staged_write | write_copy | True | m08gDispatch |  |
| modify.entity.transform | geometry_kernel | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.circle | geometry_kernel | implemented | staged_write | write_copy | True | appendCircle |  |
| write.entity.line | geometry_kernel | implemented | staged_write | write_copy | True | appendLine |  |
| write.entity.point | geometry_kernel | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.polyline | geometry_kernel | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.tolerance | geometry_kernel | implemented | staged_write | write_copy | True | m08gDispatch |  |
| inspect.entity.grips | graphics_system | implemented | read_safe | read | True | m08lDispatch |  |
| render.context.query | graphics_system | implemented | read_safe | read | True | m08lDispatch |  |
| render.draw.viewportgeom | graphics_system | implemented | read_safe | read | True | m08lDispatch |  |
| render.draw.worldgeom | graphics_system | implemented | read_safe | read | True | m08lDispatch |  |
| render.drawable.def | graphics_system | implemented | read_safe | read | True | m08lDispatch |  |
| render.entity.worlddraw_override | graphics_system | implemented | read_safe | read | True | m08lDispatch |  |
| render.facedata.attach | graphics_system | implemented | read_safe | read | True | m08lDispatch |  |
| render.polyline.helper | graphics_system | implemented | read_safe | read | True | m08lDispatch |  |
| render.traits.set | graphics_system | implemented | read_safe | read | True | m08lDispatch |  |
| inspect.block.count | inspect | implemented | read_safe | read | True | countBlockDefinitions |  |
| inspect.blocks | inspect | implemented | read_safe | read | True | listBlockDefinitionsDetailed |  |
| inspect.customclass.count | inspect | implemented | read_safe | read | True | countCustomEntities |  |
| inspect.customobject.count | inspect | implemented | read_safe | read | True | countCustomObjects |  |
| inspect.database.graph | inspect | implemented | read_safe | read | True | collectModelSpaceGraph + collectDatabaseGraph |  |
| inspect.entities | inspect | implemented | read_safe | read | True | listModelSpaceEntities |  |
| inspect.entity.count | inspect | implemented | read_safe | read | True | countModelSpaceEntitiesByType |  |
| inspect.jig.host_support | inspect | implemented | read_safe | read | True | jigHostSupportJson |  |
| inspect.layers | inspect | implemented | read_safe | read | True | listLayerRecords |  |
| inspect.layout.list | inspect | implemented | read_safe | read | True | listLayouts |  |
| inspect.overrule.registry | inspect | implemented | read_safe | read | True | overruleRegistryJson |  |
| inspect.protocol.queryx | inspect | implemented | read_safe | read | True | protocolQueryX |  |
| inspect.reactor.registry | inspect | implemented | read_safe | read | True | reactorRegistryJson |  |
| inspect.runtime.capabilities | inspect | implemented | read_safe | read | True | runtimeCapabilitiesJson |  |
| inspect.xdata.get | inspect | implemented | read_safe | read | True | getDatabaseXdata |  |
| inspect.xref.list | inspect | implemented | read_safe | read | True | listXrefs |  |
| plot.config.settings | layouts_plot_publish | implemented | live_edit | live_edit | True | AcDbPlotSettings / AcPlPlotConfig / AcPlPlotConf |  |
| plot.engine.run | layouts_plot_publish | implemented | read_safe | read | True | AcPlPlotEngine: beginPlot/beginDocument/beginPag |  |
| live.jig.point_probe | live | implemented | live_edit | live_edit | True | runLineJigProbe |  |
| live.overrule.disable | live | implemented | live_edit | live_edit | True | disableObjectOverrule |  |
| live.overrule.enable | live | implemented | live_edit | live_edit | True | enableObjectOverrule |  |
| live.reactor.disable | live | implemented | live_edit | live_edit | True | disableEditorReactor |  |
| live.reactor.enable | live | implemented | live_edit | live_edit | True | enableEditorReactor |  |
| live.status | live | implemented | read_safe | read | True | pumpDispatch |  |
| infra.hostapp.get_services | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| infra.hostapp.set_working_db | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.database.dxf_in | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.database.flush_input | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.database.read_dwg | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.database.read_dwg_handle | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.database.summary | objectdbx_database | implemented | read_safe | read | True | InspectDatabaseSummary |  |
| inspect.database.summaryinfo | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.database.sysvar | objectdbx_database | implemented | staged_write | write_copy | True | m08cDispatch |  |
| inspect.object.handle | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.object.id | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.object.open | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| transaction.manager.get_object | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| transaction.manager.start | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| transform.database.dxf_out | objectdbx_database | implemented | staged_write | write_copy | True | m08cDispatch |  |
| transform.database.save_as | objectdbx_database | implemented | staged_write | write_copy | True | m08cDispatch |  |
| transform.database.save_as_simple | objectdbx_database | implemented | staged_write | write_copy | True | m08cDispatch |  |
| write.object.cancel | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| write.object.close | objectdbx_database | implemented | staged_write | write_copy | True | m08cDispatch |  |
| write.object.downgrade_open | objectdbx_database | implemented | staged_write | write_copy | True | m08cDispatch |  |
| write.object.upgrade_open | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| patch.apply_staged | patch | implemented | read_safe | read | True | patch_engine.dry_run_plan |  |
| patch.dry_run | patch | implemented | read_safe | read | True | patch_engine.dry_run_plan |  |
| query.entities | query | implemented | read_safe | read | True | sqlite_ir_store.query |  |
| react.config.disable_namespace | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.database.attach | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.database.monitor | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.docmanager.attach | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.docmanager.monitor | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.editor.command_monitor | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.editor.dwg_lifecycle | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.editor.input_monitor | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.editor.lisp_monitor | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.editor.sysvar_monitor | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.entity.monitor | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.linker.attach | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.linker.monitor | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.longtx.attach | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.longtx.monitor | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.object.attach_transient | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.object.detach_transient | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.object.monitor | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.persistent.attach | reactors_events | implemented | live_edit | live_edit | True | m08mDispatch |  |
| react.persistent.detach | reactors_events | implemented | live_edit | live_edit | True | m08mDispatch |  |
| react.rxevent.attach | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| react.rxevent.monitor | reactors_events | implemented | read_safe | read | True | m08mDispatch |  |
| render.layout | render | implemented | read_safe | read | True |  |  |
| command.register.define | runtime_commands | implemented | read_safe | read | True | m08nDispatch |  |
| module.ads.register_symbol | runtime_commands | implemented | read_safe | read | True | m08nDispatch |  |
| module.app.accessor | runtime_commands | implemented | read_safe | read | True | m08nDispatch |  |
| module.class.register_object | runtime_commands | implemented | staged_write | write_copy | True | m08nDispatch |  |
| module.command.register_auto | runtime_commands | implemented | read_safe | read | True | m08nDispatch |  |
| module.command.register_manual | runtime_commands | implemented | read_safe | read | True | m08nDispatch |  |
| module.command.stack_handle | runtime_commands | implemented | read_safe | read | True | m08nDispatch |  |
| module.register_mdi | runtime_commands | implemented | read_safe | read | True | m08nDispatch |  |
| module.register_service | runtime_commands | implemented | read_safe | read | True | m08nDispatch |  |
| acdb.database.create | symbol_tables_dictionaries | implemented | read_safe | read | True | m08eDispatch |  |
| inspect.dictionary.get | symbol_tables_dictionaries | implemented | read_safe | read | True | m08eDispatch |  |
| inspect.dictionary.named_objects | symbol_tables_dictionaries | implemented | read_safe | read | True | m08eDispatch |  |
| inspect.entity.get_xdata | symbol_tables_dictionaries | implemented | read_safe | read | True | m08eDispatch |  |
| inspect.object.ext_dict | symbol_tables_dictionaries | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.symboltable.block | symbol_tables_dictionaries | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.symboltable.layers | symbol_tables_dictionaries | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.xrecord.get | symbol_tables_dictionaries | implemented | read_safe | read | True | getXrecord |  |
| transform.database.wblock | symbol_tables_dictionaries | implemented | read_safe | read | True | m08cDispatch |  |
| transform.database.wblock_clone | symbol_tables_dictionaries | implemented | live_edit | live_edit | True | m08cDispatch |  |
| write.dictionary.set | symbol_tables_dictionaries | implemented | staged_write | write_copy | True | m08eDispatch |  |
| write.entity.set_xdata | symbol_tables_dictionaries | implemented | staged_write | write_copy | True | m08eDispatch |  |
| write.layer.create | symbol_tables_dictionaries | implemented | staged_write | write_copy | True | createLayer |  |
| write.object.create_ext_dict | symbol_tables_dictionaries | implemented | staged_write | write_copy | True | m08eDispatch |  |
| write.regapp.register | symbol_tables_dictionaries | implemented | staged_write | write_copy | True | m08eDispatch |  |
| write.xrecord.set | symbol_tables_dictionaries | implemented | staged_write | write_copy | True | setXrecord |  |
| editor.command.register | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.command.unregister | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.menu.add_item | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.menu.context | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.menu.menubar_get | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.palette.add_palette | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.palette.create | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.palette.create_dockable | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.palette.dock | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.palette.persist | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.palette.style | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.statusbar.add_pane | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.statusbar.context_menu | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.statusbar.get | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.statusbar.pane | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.statusbar.pane_config | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.statusbar.remove_pane | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpalette.add_tool | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpalette.catalog_item_props | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpalette.catalog_manager | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpalette.create | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpalette.export | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpalette.global_init | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpalette.group_activate | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpalette.group_create | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpalette.refresh | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpalette.scheme_create | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpalette.scheme_register | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpalette.stocktool_find | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpalette.tool_set_command | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpalette.window_get | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpalette.window_show | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpaletteset.add_palette | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.toolpaletteset.show | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.tray.add_item | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.tray.item_config | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| editor.tray.remove | ui_customization | implemented | read_safe | read | True | m08nDispatch |  |
| validate.ir | validate | implemented | read_safe | read | True | validator.validate_target |  |
| validate.patch | validate | implemented | read_safe | read | True | validator.validate_target |  |
| write.block.insert | write | implemented | staged_write | write_copy | True | insertBlockReference |  |
| write.block.simple_create | write | implemented | staged_write | write_copy | True | createSimpleBlock |  |
| write.layout.create | write | implemented | staged_write | write_copy | True | createLayout |  |
| write.xdata.set | write | implemented | staged_write | write_copy | True | setDatabaseXdata |  |

> Full 517-operation detail (all 13 fields per op) is in `reports/operation_coverage_full_matrix.json` — this table lists only the 461 v1-target ops. The 56 catalogued ops are classified future-version native capability (v1_target=false), not omitted.
