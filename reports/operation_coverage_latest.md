# CADOS_M01 - Operation Coverage

- **Generated:** 2026-06-22T00:02:38+09:00
- **Source:** `config/operations.v2.json` (`ariadne.operations_registry.v2` v2.0.0)
- **Schema:** `ariadne.cad_os.operation_coverage.v1`

## Headline

- **Catalogued ops:** **480** across **16** catalog families (sum check: map=480, family-heads=480, both == 480).
- **First-class registry ops modeled:** 40 - **implemented 30 / stub 8 / blocked 2**.
- **Implemented = 30** = 29 v1-wired ops + 1 synthetic native op (`inspect.database.graph`, built into `Ariadne.AcadNative.crx`).
- **Route availability:** router `ALL_AVAILABLE`, **11/11** routes, native_modules PASS, coreconsole_load PASS.

## Catalog by family (480 total)

| Family | Catalogued ops |
|--------|----------------|
| `custom_objects_protocols` | 63 |
| `constraints_associativity` | 58 |
| `entities` | 56 |
| `brep_solids` | 54 |
| `com_activex` | 49 |
| `ui_customization` | 39 |
| `editor_input` | 27 |
| `runtime_commands` | 26 |
| `geometry_kernel` | 25 |
| `reactors_events` | 22 |
| `objectdbx_database` | 21 |
| `symbol_tables_dictionaries` | 16 |
| `graphics_system` | 9 |
| `active_document_write_original` | 8 |
| `blocks_xrefs_clone` | 5 |
| `layouts_plot_publish` | 2 |
| **TOTAL** | **480** |

## Implemented op status (30)

- v1-wired (29): all `implemented`. Route classes - native/ObjectDBX/CoreConsole: 29, managed .NET: 1.
- New synthetic native op this packet: `inspect.database.graph` (`wired_v1=false`; implemented in `.crx`, smoked directly via accoreconsole+.scr; router-wiring deferred to M02).

### 29 v1 wired ops

| Op | Status | Engine tier | Host class |
|----|--------|-------------|------------|
| `inspect.database.summary` | implemented | managed_also | dbx |
| `write.layer.create` | implemented | objectdbx_capable | dbx |
| `write.entity.line` | implemented | objectdbx_capable | dbx |
| `write.entity.circle` | implemented | objectdbx_capable | dbx |
| `inspect.entity.count` | implemented | objectdbx_capable | dbx |
| `write.xrecord.set` | implemented | objectdbx_capable | dbx |
| `inspect.xrecord.get` | implemented | objectdbx_capable | dbx |
| `write.xdata.set` | implemented | objectdbx_capable | dbx |
| `inspect.xdata.get` | implemented | objectdbx_capable | dbx |
| `write.block.simple_create` | implemented | objectdbx_capable | dbx |
| `write.block.insert` | implemented | objectdbx_capable | dbx |
| `inspect.block.count` | implemented | objectdbx_capable | dbx |
| `write.layout.create` | implemented | objectdbx_capable | dbx |
| `inspect.layout.list` | implemented | objectdbx_capable | dbx |
| `inspect.xref.list` | implemented | objectdbx_capable | dbx |
| `inspect.runtime.capabilities` | implemented | accoreconsole_lisp_also | coreconsole |
| `live.reactor.enable` | implemented | native_arx_only | arx_adapter |
| `inspect.reactor.registry` | implemented | accoreconsole_lisp_also | coreconsole |
| `live.reactor.disable` | implemented | native_arx_only | arx_adapter |
| `inspect.overrule.registry` | implemented | accoreconsole_lisp_also | coreconsole |
| `live.overrule.enable` | implemented | native_arx_only | arx_adapter |
| `live.overrule.disable` | implemented | native_arx_only | arx_adapter |
| `inspect.jig.host_support` | implemented | accoreconsole_lisp_also | coreconsole |
| `live.jig.point_probe` | implemented | native_arx_only | full_autocad |
| `extend.customclass.create` | implemented | native_arx_only | arx_adapter |
| `inspect.customclass.count` | implemented | native_arx_only | arx_adapter |
| `extend.customobject.create` | implemented | native_arx_only | arx_adapter |
| `inspect.customobject.count` | implemented | native_arx_only | arx_adapter |
| `inspect.protocol.queryx` | implemented | native_arx_only | arx_adapter |

## Stub ops (8 - catalogued/phased, no destructive behavior)

- `inspect.layers`
- `inspect.blocks`
- `inspect.entities`
- `query.entities`
- `apply.patch`
- `validate.patch`
- `diff.before_after`
- `live.status`

## Blocked ops (2 - safety shells, deferred by design)

- `render.layout` - Layout/plot render to image. Plot/publish is host-bound (full AutoCAD) and not headless-safe.
- `live.apply_patch` - Apply a patch to the live active document. Requires full_autocad + explicit write_original approval.

## Route availability detail

- `ALL_AVAILABLE`, route_count 11 / available_count 11 (native_modules PASS, coreconsole_load PASS).
- Native ObjectARX extract (`geometry_native`) live and proven on the golden (21747). 10 Python engines available. 1 managed .NET handler present.
- `inspect.database.graph` is implemented + smoked at 3 and 291706 entities but NOT yet routable via cadctl/router (needs `autocad-router.ps1` native allow-list edit - M02).

## Evidence

- `config/operations.v2.json`
- `reports/autocad_router_status_latest.json`
- `reports/walking_skeleton_latest.json`
- `reports/native_graph_smoke_latest.json`
- `reports/build_native_latest.log`
- `docs/OPERATION_REGISTRY_SPEC.md`
