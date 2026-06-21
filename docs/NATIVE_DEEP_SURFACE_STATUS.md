# Native Deep-Surface Status Matrix (CADOS_M07)

Per-surface honest status. **implemented** = compiles AND has real registration + evidence.
**attended_blocked** = needs a GUI/interactive editor/viewport/MFC surface that headless
accoreconsole cannot exercise (exact reason given). **design_only** = scaffold exists but is
not registered/wired. No surface is marked implemented without evidence.

Source of truth: `src/Ariadne.AcadNative/AriadneNativeJob.cpp` (.arx/.crx single TU) +
`src/Ariadne.AcadNative/AriadneProbe.{h,cpp}` (custom entity, compiled into the `.dbx`) +
`src/Ariadne.AcadNativeDbx/{AriadneRecord,AriadneProtocol}.{h,cpp}`. Codified by
`tests/unit/test_pump_shutdown_and_deep_native_source.py`.

| # | Surface | Status | Registered | Host | Evidence / Exact blocker |
|---|---|---|---|---|---|
| 1 | Custom entity lifecycle (`AriadneProbe : AcDbEntity`) | **implemented** | yes | headless+attended | `AriadneProbe.h:22` `ACRX_DECLARE_MEMBERS`; `rxInit` in `AriadneDbxEntry.cpp:68`; ops `extend.customclass.create` / `inspect.customclass.count` |
| 2 | worldDraw / viewportDraw custom rendering | **implemented** | yes | headless callback / attended pixels | `AriadneProbe::subWorldDraw` (`AriadneProbe.cpp:148`, `mode->geometry().circle` marker) + `subGetGeomExtents:156` + `subTransformBy:165`. Callback compiles into the `.dbx` and round-trips headless. **Pixel** verification (viewport regen) is attended-only. |
| 3 | AcRxProperty / OPM (Properties palette) read/write | **attended_blocked** | no | attended only | No `AcRxProperty` code. Registration is headless-feasible but the OPM Properties **panel** is MFC GUI absent in accoreconsole; deferred to a dedicated attended packet. |
| 4 | Object overrules (`AcDbObjectOverrule`) | **implemented** | yes | headless+attended | `AriadneObjectOverrule` (`AriadneNativeJob.cpp:1606`); `AcRxOverrule::addOverrule(AcDbEntity::desc())` + `setIsOverruling`; ops `live.overrule.enable/disable`, `inspect.overrule.registry`; fixtures `job_overrule_enable/disable.json` |
| 5 | Persistent editor reactors (`AcEditorReactor`) | **implemented** | yes | headless register / attended fire | `AriadneEditorReactor` (`:1557`, `commandWillStart`/`commandEnded` counters); `acedEditor->addReactor`; ops `live.reactor.enable/disable`; disabled on unload. Callbacks fire only under an interactive editor. |
| 6 | Editor jigs (`AcEdJig`) | **implemented (host-gated)** | yes | attended for drag | `AriadneLineJig` (`:1695`); `runLineJigProbe` returns `supported:false` + reason for coreconsole, runs only under `full_autocad`; op `live.jig.point_probe`. Class compiles + registered; interactive drag attended-only. |
| 7 | Selection monitor | **attended_blocked** | no | attended only | No selection-monitor code. Needs the interactive pick stream; `acedEditor` is null headless so callbacks never fire. Registration would mirror reactor #5 but live events are attended-only; deferred. |
| 8 | Palette / status-bar UI | **attended_blocked** | no | attended only | No palette/status code. `CAcUiDockControlBar` / `AcApStatusBar` are MFC GUI on acad.exe's UI thread; accoreconsole has no MFC main window or message pump. |
| 9 | Custom object serialization / filer versioning | **implemented** | yes | headless | `AriadneRecord : AcDbObject`; `dwgOut` writes `kAriadneRecordVersion`(=1) int16 + value; `dwgIn` returns `Acad::eMakeMeProxy` on newer; dxf mirrors. Headless save+reload roundtrip. |
| 10 | Protocol extensions (`AcRxObject` protocol) | **implemented** | yes | headless | `AriadneProbeProtocol : AcRxObject` (`AriadneProtocol.h:6`); `AriadneProbe::desc()->addX(AriadneProbeProtocol::desc(),…)` (`AriadneProtocol.cpp:26`) registered in `AriadneDbxEntry.cpp`; op `inspect.protocol.queryx` (`AriadneNativeJob.cpp:2920`) reports `probe_protocol_available`. |

## Summary counts

- **implemented:** 7 (custom entity, worldDraw, overrules, reactors, jigs[host-gated], filer versioning, protocol extensions)
- **attended_blocked:** 3 (AcRxProperty/OPM, selection monitor, palette/status UI)
- **design_only:** 0

## Correction of the M07 design-stream miscount

An M07 workflow design stream initially scored worldDraw and protocol-extensions as
not-implemented because it grepped only `AriadneNativeJob.cpp` and missed `AriadneProbe.cpp`
(which holds `subWorldDraw`) and `AriadneProtocol.cpp` (which registers the protocol via
`addX`). Ground-truth verification of the whole `src/` tree corrected both to **implemented**,
now codified by `test_custom_entity_worlddraw_present` + `test_protocol_extension_registered`.

## Why headless cannot prove the 3 attended_blocked surfaces

accoreconsole is a batch DB host: no graphics system, no Properties palette, no interactive
selection, no MFC UI. Surfaces that intrinsically require any of those (3, 7, 8) can only be
proven inside attended `acad.exe`. The user's `acad.exe` (PID 49460) has no automation channel
from this session and must not be disrupted, so attended proof is recorded as blocked, never
faked. The honest path forward is a dedicated attended packet that loads the `.arx` into a
disposable AutoCAD instance the agent is permitted to drive.

## Deliberate decision: no risky new native stubs

AcRxProperty and selection-monitor headless **registration** stubs were NOT added: their
ObjectARX 2027 signatures are unverified (the relevant `inc` headers are not at the canonical
path), their function is attended-GUI-only regardless, and Rule 2/3 + no-fake-success favor an
honest hard-block over a build-breaking stub. The substantial M07 native advance is the live
pump expansion (5 new ops + `CADAGENT_STATUS`), fully headless-verified.
