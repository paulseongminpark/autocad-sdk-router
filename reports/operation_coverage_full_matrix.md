# CAD OS — Full Operation Coverage Matrix (M08)

- packet: `CADOS_M08_FULL_OPERATION_COVERAGE_CLOSURE`
- generated_from: `config/operations.v2.json`
- total operations: **517** · implemented 41 · stub 0 · blocked 2 · catalogued 474 · deprecated 0 · **unknown 0**
- v1-target: **43** (implemented 41 · blocked 2 · **deferred 0**)
- agent-exposed ops: 41

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
| read | 20 | 0 | 0 | 33 | 20 |
| query | 1 | 0 | 0 | 0 | 1 |
| write_patch | 7 | 0 | 0 | 13 | 7 |
| validate_diff | 3 | 0 | 0 | 0 | 3 |
| render_visual | 0 | 0 | 1 | 11 | 1 |
| live | 6 | 0 | 1 | 0 | 7 |
| native_only | 4 | 0 | 0 | 417 | 4 |

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
| diff.before_after | diff | implemented | read_safe | read | True | cad_diff.compute_diff |  |
| extend.customclass.create | extend | implemented | live_edit | live_edit | True | createCustomEntity |  |
| extend.customobject.create | extend | implemented | live_edit | live_edit | True | createCustomObject |  |
| write.entity.circle | geometry_kernel | implemented | staged_write | write_copy | True | appendCircle |  |
| write.entity.line | geometry_kernel | implemented | staged_write | write_copy | True | appendLine |  |
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
| inspect.database.summary | objectdbx_database | implemented | read_safe | read | True | InspectDatabaseSummary |  |
| patch.apply_staged | patch | implemented | read_safe | read | True | patch_engine.dry_run_plan |  |
| patch.dry_run | patch | implemented | read_safe | read | True | patch_engine.dry_run_plan |  |
| query.entities | query | implemented | read_safe | read | True | sqlite_ir_store.query |  |
| inspect.xrecord.get | symbol_tables_dictionaries | implemented | read_safe | read | True | getXrecord |  |
| write.layer.create | symbol_tables_dictionaries | implemented | staged_write | write_copy | True | createLayer |  |
| write.xrecord.set | symbol_tables_dictionaries | implemented | staged_write | write_copy | True | setXrecord |  |
| validate.ir | validate | implemented | read_safe | read | True | validator.validate_target |  |
| validate.patch | validate | implemented | read_safe | read | True | validator.validate_target |  |
| write.block.insert | write | implemented | staged_write | write_copy | True | insertBlockReference |  |
| write.block.simple_create | write | implemented | staged_write | write_copy | True | createSimpleBlock |  |
| write.layout.create | write | implemented | staged_write | write_copy | True | createLayout |  |
| write.xdata.set | write | implemented | staged_write | write_copy | True | setDatabaseXdata |  |

> Full 517-operation detail (all 13 fields per op) is in `reports/operation_coverage_full_matrix.json` — this table lists only the 43 v1-target ops. The 474 catalogued ops are classified future-version native capability (v1_target=false), not omitted.
