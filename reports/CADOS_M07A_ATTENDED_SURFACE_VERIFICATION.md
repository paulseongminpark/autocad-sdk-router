# CADOS_M07A — Attended-Surface Remainder (Result, in progress)

**Status: PARTIAL_PASS (implementation phase complete + build-verified; attended GUI run pending).**
Closes the M07 attended residue on the IMPLEMENTATION side; the attended GUI verification
(OPM panel screenshot, worldDraw pixels, live firing) + pump-gating + palette integration are
the next focused step (now unblocked — acad.exe PID 49460 was closed by the user). No fake PASS.
Original golden DWG unchanged. No remote push.

## What this packet did (verified)

- **Selection monitor — IMPLEMENTED + build-verified.** `AriadneSelectionMonitor : AcEditorReactor`
  (`pickfirstModified`, aced.h:541) + enable/disable + ops `live.selection.monitor.enable/disable` +
  `inspect.selection.monitor.registry` + `selectionMonitorRegistryJson` + `selection_monitor` capability
  + clean-unload. Registration is `acedEditor`-gated (headless `registered:false`; events attended).
  Canonical `.crx` 236544. `inspect.runtime.capabilities` (fresh `.crx`, headless) returns
  `selection_monitor:{implemented:true, registered:false, live_events:attended_only}`.
- **AcRxProperty / OPM "Size" — IMPLEMENTED + build-verified.** The original imperative-builder plan
  did NOT compile (`AcRxMemberCollectionBuilder` private ctor). Correct wiring = the
  `ACRX_DXF_DEFINE_MEMBERS_WITH_PROPERTIES` class macro (rxboiler.h:289) + a file-local property class
  (`AriadneSizeProperty : AcRxProperty`, backed by `AriadneProbe::size()/setSize()`) + a `makeMembers`
  callback. Read/write idiom: `value = d` / `rxvalue_cast<double>` (rxvalue.h). **Make-or-break risk
  RESOLVED: `AcRxValueType::Desc<double>::value()` links** (the canonical `.dbx` 48128 builds clean).
  Two build errors found+fixed (C2248 protected `operator delete` → forwarding delete; missing export
  body → added). Headless proof op `inspect.probe.property_count` added. **OPM panel display is
  attended-only (pending the attended run).**
- **acad.exe lock resolved.** PID 49460 (open since 2026-06-18) locked the canonical `.dbx`; the build
  versioned-bypasses the `.arx` only. The user closed it → **clean canonical rebuild**
  (`arx_relink_mode:"canonical"`): `.dbx` 48128, `.crx`/`.arx` 236544, all link clean.
- **pytest 285 passed, 3 skipped, 0 failed** (incl. the selection-monitor source guard). Golden sha
  `27dbf6b9…` unchanged.

## Designed + drafted (by 3 parallel design agents; ready to integrate/run)

- **Palette / status UI = FEASIBLE** (att-visual). Linchpin: the `.crx`/`.arx` already link
  `acui26`/`adui26`/`acad` libs (arx.props), so no toolchain change. Clean path = a separate
  `AriadnePalette.cpp` added ONLY to `arx.vcxproj` (never the `.crx` TU), `acedEditor!=nullptr`-guarded,
  lazy `CAdUiPaletteSet` creation. Full command draft provided. NOT yet integrated.
- **Pump-gating C++** (att-live): gate the 5 attended pump ops (`highlight/clear/zoom/render/inspect_selection`)
  on `acedEditor!=nullptr && hostMode=="full_autocad"` → real execution (`acedSSGet`, `AcDbEntity::highlight`,
  `acedCommandS _.ZOOM`, `REGENALL`) else the headless `attended_only` stub. Preserves headless honesty.
  NOT yet integrated.
- **Attended harness + SAFETY = GO** (att-live): a dedicated `acad.exe /b startup.scr` (arxload `.dbx`+`.arx`,
  unique `\\.\pipe\ariadne_attended_<rand>`, `full_autocad`) is provably isolated from any other session
  (PID gate + unique-pipe-owner gate + teardown-only-launched-PID gate; zero COM). Full launcher + pipe
  client + 3 gates drafted. NOT yet run.

## Honest pending (the attended GUI run — next step)

- OPM "Size" panel VISIBLE + editable on a probe (screenshot).
- worldDraw circle marker rendered in a viewport (screenshot).
- selection-monitor / reactor / overrule / jig FIRING (live counts) in a real editor.
- pump-gated highlight/zoom/render/selection executing (after pump-gating integration).
- palette shown (after palette integration).
- Custom-op job channel: `ARIADNE_CAD_JOB_IN` env did not drive a custom op via direct accoreconsole
  launch (job defaulted to `inspect.runtime.capabilities`); the `ARIADNE_NATIVE_JOB_ARGS` prompt path or
  the router's staged-job path is the mechanism to finalize for driving `extend.customclass.create` /
  `inspect.probe.property_count` headless.

## Evidence

- Canonical build JSON (this session): `.dbx` 48128, `.crx`/`.arx` 236544, `arx_relink_mode:canonical`.
- `runs/m07a_property_count/` (job channel exercised; fresh `.crx` confirmed live via capabilities).
- `runs/m07_pump_test/` (M07 pump 17/17 still green).
- Packet: `packets/CADOS_M07A_ATTENDED_SURFACE_VERIFICATION.md`.
- pytest 285 passed / 3 skipped.

NEXT: integrate pump-gating + palette (drafts ready) → single attended run (dedicated acad.exe, 3 gates) →
capture OPM/worldDraw/firing evidence → finalize matrix (selection_monitor + acrxproperty_opm → implemented;
palette → implemented; attended surfaces → verified-with-evidence) → commit + reports.
