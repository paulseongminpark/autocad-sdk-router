# Wave3 Integrated Implement Unfinished

- Status: `PASS`
- Generated: `2026-06-23T23:37:33+09:00`
- Branch: `cados/wave3-integrate-and-build-unfinished`
- Counts before: `{'implemented': 451, 'blocked': 11, 'catalogued': 55}`
- Counts after: `{'implemented': 457, 'blocked': 60}`
- Closure gate: `True`
- Raw command agent exposure: `0`
- Original DWG modified: `no`

## Merged
- `cados/wave3-pane2-heavy-native-30`: merged
- `cados/wave3-pane6-native-custom`: merged
- `cados/wave3-pane8-opm-reactors`: merged
- `cados/wave3-pane4-fallback-lowrisk`: already_up_to_date
- `cados/wave3-pane3-visual-live`: merged
- `cados/wave3-pane9-live-editor-ui`: merged

## Reviewed Not Merged
- `cados/wave3-pane10-mixed-burndown`: not_merged_raw_sendstring_surface_reviewed_and_blocked
- `cados/wave3-pane5-generic-30`: not_merged_reaudited_and_reimplemented_or_blocked_in_integration

## Implemented From Unfinished
- `config.assoceval.callback`
- `config.constraint.globalCallback`
- `inspect.subentity.color`
- `inspect.subentity.markers_at_path`
- `inspect.subentity.path_at_marker`
- `module.command.flags`
- `overrule.dimstyle.install`
- `extend.object_enabler.demand_register`

## Accepted Hard Blocks
- `automate.com.get_app`: SAFETY_FORBIDDEN
- `automate.com.get_document`: SAFETY_FORBIDDEN
- `automate.com.get_for_command`: SAFETY_FORBIDDEN
- `automate.com.get_winapp`: SAFETY_FORBIDDEN
- `automate.com.send_command`: SAFETY_FORBIDDEN
- `automate.com.wrapper_for_object`: SAFETY_FORBIDDEN
- `define.assocarray.create`: SAFETY_FORBIDDEN
- `define.assocarray.path`: SAFETY_FORBIDDEN
- `define.assocarray.polar`: SAFETY_FORBIDDEN
- `define.assocarray.rectangular`: SAFETY_FORBIDDEN
- `define.assocsurface.blend`: SAFETY_FORBIDDEN
- `define.assocsurface.extrude`: SAFETY_FORBIDDEN
- `define.assocsurface.fillet`: SAFETY_FORBIDDEN
- `define.assocsurface.loft`: SAFETY_FORBIDDEN
- `define.assocsurface.offset`: SAFETY_FORBIDDEN
- `define.assocsurface.patch`: SAFETY_FORBIDDEN
- `define.assocsurface.result`: SAFETY_FORBIDDEN
- `define.assocsurface.trim`: SAFETY_FORBIDDEN
- `edit.assocarray.explode`: SAFETY_FORBIDDEN
- `edit.assocarray.item`: SAFETY_FORBIDDEN
- `edit.assocarray.itemReplace`: SAFETY_FORBIDDEN
- `edit.assocarray.reset`: SAFETY_FORBIDDEN
- `edit.assocarray.source`: SAFETY_FORBIDDEN
- `edit.assocarray.transform`: SAFETY_FORBIDDEN
- `edit.assocdata.xref`: SAFETY_FORBIDDEN
- `edit.subentity.add_paths`: SAFETY_FORBIDDEN
- `edit.subentity.delete_paths`: SAFETY_FORBIDDEN
- `edit.subentity.transform`: SAFETY_FORBIDDEN
- `embed.ole.frame`: HOST_UNAVAILABLE
- `inspect.assocaction.evaluate`: SAFETY_FORBIDDEN
- `inspect.assocnetwork.evaluate`: SAFETY_FORBIDDEN
- `inspect.assocsurface.topology`: SAFETY_FORBIDDEN
- `module.command.remove_group`: SAFETY_FORBIDDEN
- `module.entrypoint.define`: SDK_NOT_EXPOSED
- `module.entrypoint.dispatch`: HOST_UNAVAILABLE
- `module.lifecycle.init`: HOST_UNAVAILABLE
- `module.lifecycle.on_load_dwg`: HOST_UNAVAILABLE
- `module.lifecycle.on_ole_unload`: HOST_UNAVAILABLE
- `module.lifecycle.on_unload_dwg`: HOST_UNAVAILABLE
- `module.lifecycle.other`: HOST_UNAVAILABLE
- `module.lifecycle.unload`: HOST_UNAVAILABLE
- `module.load`: SAFETY_FORBIDDEN
- `module.load.acad_rx`: SAFETY_FORBIDDEN
- `module.load.by_app`: SAFETY_FORBIDDEN
- `module.load.lisp`: SAFETY_FORBIDDEN
- `module.unload`: SAFETY_FORBIDDEN
- `repair.assocdata.audit`: SAFETY_FORBIDDEN
- `ui.subentity.highlight`: HOST_UNAVAILABLE
- `plot.config.settings`: SAFETY_FORBIDDEN
- `plot.engine.run`: HOST_UNAVAILABLE

## Validation
- `python -m pytest tests -q`: `487 passed, 20 skipped`
- `tools/build_native_acad.ps1`: `status ok`, canonical `.dbx/.crx/.arx` relink
- JSON reports: valid
- Remaining catalogued/stub/unknown/deferred: `0`
