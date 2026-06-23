# CAD OS — Full Operation Coverage Matrix (M08)

- packet: `CADOS_M08_FULL_OPERATION_COVERAGE_CLOSURE`
- generated_from: `config/operations.v2.json`
- total operations: **517** · implemented 219 · stub 0 · blocked 2 · catalogued 296 · deprecated 0 · **unknown 0**
- v1-target: **221** (implemented 219 · blocked 2 · **deferred 0**)
- agent-exposed ops: 219

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
| read | 34 | 0 | 0 | 19 | 34 |
| query | 1 | 0 | 0 | 0 | 1 |
| write_patch | 8 | 0 | 0 | 12 | 8 |
| validate_diff | 3 | 0 | 0 | 0 | 3 |
| render_visual | 0 | 0 | 1 | 11 | 1 |
| live | 6 | 0 | 1 | 0 | 7 |
| native_only | 167 | 0 | 0 | 254 | 167 |

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
| live.apply_patch | live | blocked | live_edit | live_edit | False |  | Requires full_autocad live_edit host + explicit write_origin |
| render.layout | render | blocked | read_safe | read | False |  | Requires full_autocad plot/publish host; no headless render  |
| apply.patch | apply | implemented | staged_write | write_copy | True | patch_engine.apply_staged |  |
| inspect.block.iterate | blocks_xrefs_clone | implemented | read_safe | read | True | m08eDispatch |  |
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
| config.assocmanager.evalDisabler | constraints_associativity | implemented | read_safe | read | True | m08kcDispatch |  |
| define.assocaction.addDependency | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.assocaction.create | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.assocaction.valueParam | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.assocdependency.attach | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.assocgeomdependency.subent | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.assocnetwork.addAction | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
| define.assocvaluedependency.value | constraints_associativity | implemented | staged_write | write_copy | True | m08kcDispatch |  |
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
| extend.customentity.explode | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.geom_extents | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.intersect | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.list | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.subentpaths | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customentity.transform | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customobject.deepclone | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customobject.filer_dwgin | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.customobject.filer_dwgout | custom_objects_protocols | implemented | staged_write | write_copy | True | m08kDispatch |  |
| extend.customobject.version | custom_objects_protocols | implemented | live_edit | live_edit | True | m08kDispatch |  |
| extend.customobject.wblockclone | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.module.entrypoint | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.object_enabler.build | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
| extend.object_enabler.register_classes | custom_objects_protocols | implemented | read_safe | read | True | m08kDispatch |  |
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
| diff.before_after | diff | implemented | read_safe | read | True | cad_diff.compute_diff |  |
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
| write.entity.blockref | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
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
| write.entity.minsert | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.mtext | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.polygonmesh | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.polyline2d | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.polyline3d | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.ray | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.region | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.solid2d | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.spline | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.text | entities | implemented | staged_write | write_copy | True | m08hDispatch |  |
| write.entity.trace | entities | implemented | staged_write | write_copy | True | m08gDispatch |  |
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
| modify.entity.transform | geometry_kernel | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.circle | geometry_kernel | implemented | staged_write | write_copy | True | appendCircle |  |
| write.entity.line | geometry_kernel | implemented | staged_write | write_copy | True | appendLine |  |
| write.entity.point | geometry_kernel | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.polyline | geometry_kernel | implemented | staged_write | write_copy | True | m08gDispatch |  |
| write.entity.tolerance | geometry_kernel | implemented | staged_write | write_copy | True | m08gDispatch |  |
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
| live.jig.point_probe | live | implemented | live_edit | live_edit | True | runLineJigProbe |  |
| live.overrule.disable | live | implemented | live_edit | live_edit | True | disableObjectOverrule |  |
| live.overrule.enable | live | implemented | live_edit | live_edit | True | enableObjectOverrule |  |
| live.reactor.disable | live | implemented | live_edit | live_edit | True | disableEditorReactor |  |
| live.reactor.enable | live | implemented | live_edit | live_edit | True | enableEditorReactor |  |
| live.status | live | implemented | read_safe | read | True | pumpDispatch |  |
| infra.hostapp.get_services | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.database.summary | objectdbx_database | implemented | read_safe | read | True | InspectDatabaseSummary |  |
| inspect.database.summaryinfo | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.database.sysvar | objectdbx_database | implemented | staged_write | write_copy | True | m08cDispatch |  |
| inspect.object.handle | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.object.id | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.object.open | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| write.object.cancel | objectdbx_database | implemented | read_safe | read | True | m08cDispatch |  |
| patch.apply_staged | patch | implemented | read_safe | read | True | patch_engine.dry_run_plan |  |
| patch.dry_run | patch | implemented | read_safe | read | True | patch_engine.dry_run_plan |  |
| query.entities | query | implemented | read_safe | read | True | sqlite_ir_store.query |  |
| inspect.dictionary.get | symbol_tables_dictionaries | implemented | read_safe | read | True | m08eDispatch |  |
| inspect.dictionary.named_objects | symbol_tables_dictionaries | implemented | read_safe | read | True | m08eDispatch |  |
| inspect.entity.get_xdata | symbol_tables_dictionaries | implemented | read_safe | read | True | m08eDispatch |  |
| inspect.object.ext_dict | symbol_tables_dictionaries | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.symboltable.block | symbol_tables_dictionaries | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.symboltable.layers | symbol_tables_dictionaries | implemented | read_safe | read | True | m08cDispatch |  |
| inspect.xrecord.get | symbol_tables_dictionaries | implemented | read_safe | read | True | getXrecord |  |
| transform.database.wblock | symbol_tables_dictionaries | implemented | read_safe | read | True | m08cDispatch |  |
| write.layer.create | symbol_tables_dictionaries | implemented | staged_write | write_copy | True | createLayer |  |
| write.xrecord.set | symbol_tables_dictionaries | implemented | staged_write | write_copy | True | setXrecord |  |
| validate.ir | validate | implemented | read_safe | read | True | validator.validate_target |  |
| validate.patch | validate | implemented | read_safe | read | True | validator.validate_target |  |
| write.block.insert | write | implemented | staged_write | write_copy | True | insertBlockReference |  |
| write.block.simple_create | write | implemented | staged_write | write_copy | True | createSimpleBlock |  |
| write.layout.create | write | implemented | staged_write | write_copy | True | createLayout |  |
| write.xdata.set | write | implemented | staged_write | write_copy | True | setDatabaseXdata |  |

> Full 517-operation detail (all 13 fields per op) is in `reports/operation_coverage_full_matrix.json` — this table lists only the 221 v1-target ops. The 296 catalogued ops are classified future-version native capability (v1_target=false), not omitted.
