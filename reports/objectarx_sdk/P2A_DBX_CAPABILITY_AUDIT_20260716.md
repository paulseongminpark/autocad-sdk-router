# P2A -- arx->dbx capability audit (static)

Generated: 2026-07-16T09:09:07  |  audited: 88 ops (custom_objects_protocols + geometry_kernel)

| verdict | count |
|---|---|
| asm_boundary_review | 1 |
| dbx_capable | 87 |

**Mismatches vs current engine_tier: 57**

| op | engine_tier (current) | audit verdict | evidence |
|---|---|---|---|
| compute.geometry.circarc | native_arx_only | dbx_capable | - |
| compute.geometry.compositecurve | native_arx_only | dbx_capable | - |
| compute.geometry.curve.closest | native_arx_only | dbx_capable | - |
| compute.geometry.curve.eval | native_arx_only | dbx_capable | - |
| compute.geometry.curve.intersect | native_arx_only | dbx_capable | - |
| compute.geometry.curve.sample | native_arx_only | dbx_capable | - |
| compute.geometry.elliparc | native_arx_only | dbx_capable | - |
| compute.geometry.lineseg | native_arx_only | dbx_capable | - |
| compute.geometry.matrix.build | native_arx_only | dbx_capable | - |
| compute.geometry.matrix.compose | native_arx_only | dbx_capable | - |
| compute.geometry.nurbcurve | native_arx_only | dbx_capable | - |
| compute.geometry.point.distance | native_arx_only | dbx_capable | - |
| compute.geometry.point.transform | native_arx_only | dbx_capable | - |
| compute.geometry.scale.build | native_arx_only | dbx_capable | - |
| compute.geometry.surface.nurb | native_arx_only | dbx_capable | - |
| compute.geometry.tolerance | native_arx_only | dbx_capable | - |
| extend.customclass.declare | native_arx_only | dbx_capable | - |
| extend.customclass.define | native_arx_only | dbx_capable | - |
| extend.customclass.define_cons | native_arx_only | dbx_capable | - |
| extend.customclass.define_dxf | native_arx_only | dbx_capable | - |
| extend.customclass.define_nocons | native_arx_only | dbx_capable | - |
| extend.customclass.rxinit | native_arx_only | dbx_capable | - |
| extend.customclass.unregister | native_arx_only | dbx_capable | - |
| extend.customentity.db_defaults | native_arx_only | dbx_capable | - |
| extend.customentity.define | native_arx_only | dbx_capable | - |
| extend.customentity.draw_viewport | native_arx_only | dbx_capable | - |
| extend.customentity.draw_world | native_arx_only | dbx_capable | - |
| extend.customentity.explode | native_arx_only | dbx_capable | - |
| extend.customentity.geom_extents | native_arx_only | dbx_capable | - |
| extend.customentity.grips | native_arx_only | dbx_capable | - |
| extend.customentity.intersect | native_arx_only | dbx_capable | - |
| extend.customentity.list | native_arx_only | dbx_capable | - |
| extend.customentity.osnap | native_arx_only | dbx_capable | - |
| extend.customentity.stretch | native_arx_only | dbx_capable | - |
| extend.customentity.subentpaths | native_arx_only | dbx_capable | - |
| extend.customentity.transform | native_arx_only | dbx_capable | - |
| extend.customobject.deepclone | native_arx_only | dbx_capable | - |
| extend.customobject.define | native_arx_only | dbx_capable | - |
| extend.customobject.embedded | native_arx_only | dbx_capable | - |
| extend.customobject.partial_undo | native_arx_only | dbx_capable | - |
| extend.customobject.version | native_arx_only | dbx_capable | - |
| extend.customobject.wblockclone | native_arx_only | dbx_capable | - |
| extend.module.entrypoint | native_arx_only | dbx_capable | - |
| extend.object_enabler.register_classes | native_arx_only | dbx_capable | - |
| extend.osnap.custom_mode | native_arx_only | dbx_capable | - |
| extend.protocol.attach | native_arx_only | dbx_capable | - |
| extend.protocol.declare | native_arx_only | dbx_capable | - |
| extend.protocol.detach | native_arx_only | dbx_capable | - |
| extend.protocol.query | native_arx_only | dbx_capable | - |
| extend.service.register | native_arx_only | dbx_capable | - |
| inspect.runtime.cast | native_arx_only | dbx_capable | - |
| inspect.runtime.desc | native_arx_only | dbx_capable | - |
| inspect.runtime.isa | native_arx_only | dbx_capable | - |
| inspect.runtime.iskindof | native_arx_only | dbx_capable | - |
| overrule.dimstyle.install | native_arx_only | dbx_capable | - |
| overrule.object.install | native_arx_only | dbx_capable | - |
| overrule.queryx.install | native_arx_only | dbx_capable | - |

Honest scope: static necessary-not-sufficient; helper taint 1 level; link/runtime proof = P2C dbx import audit + build.
