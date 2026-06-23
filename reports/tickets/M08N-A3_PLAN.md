# M08N-A3 PLAN — Native UI / editor / jig / palette command builder

## Scope

Pane 2 / A3 combines M08N-T01 and M08N-T02 into one worktree/branch:

- Worktree: `D:\dev\99_tools\autocad-sdk-router_m08n_a3`
- Branch: `cados/m08n-a3-native-ui`
- Base: `main` at `bcde5b9` or later
- Goal: implementation first. Every A3 operation closes as `implemented`, `hard_blocked`, or `deprecated`; no A3 op may remain `catalogued` if implementable.

## Target operations (73)

### M08N-T01 — jigs and editor interaction (17)

1. `editor.react.events`
2. `input.get.angle`
3. `input.get.corner`
4. `input.get.dist`
5. `input.get.int`
6. `input.get.keyword`
7. `input.get.point`
8. `input.get.real`
9. `input.get.string`
10. `input.initget.constrain`
11. `interact.inputcontext.react`
12. `interact.inputpoint.filter`
13. `interact.inputpoint.monitor`
14. `interact.jig.acquire`
15. `interact.jig.run`
16. `prompt.alert`
17. `prompt.print`

### M08N-T02 — selection, UI, palette, command shell (56)

1. `select.entity.pick`
2. `select.nentity.pick`
3. `select.pickfirst.get`
4. `select.pickfirst.set`
5. `select.ss.addremove`
6. `select.ss.count`
7. `select.ss.free`
8. `select.ssget.interactive`
9. `select.ssget.preview`
10. `command.register.define`
11. `module.ads.register_symbol`
12. `module.class.register_object`
13. `module.command.register_auto`
14. `module.command.register_manual`
15. `module.load.demand_register`
16. `module.register_mdi`
17. `module.register_service`
18. `command.menu.invoke`
19. `editor.command.register`
20. `editor.command.unregister`
21. `editor.menu.add_item`
22. `editor.menu.context`
23. `editor.menu.menubar_get`
24. `editor.palette.add_palette`
25. `editor.palette.create`
26. `editor.palette.create_dockable`
27. `editor.palette.dock`
28. `editor.palette.persist`
29. `editor.palette.style`
30. `editor.statusbar.add_pane`
31. `editor.statusbar.context_menu`
32. `editor.statusbar.get`
33. `editor.statusbar.pane`
34. `editor.statusbar.pane_config`
35. `editor.statusbar.remove_pane`
36. `editor.toolpalette.add_tool`
37. `editor.toolpalette.catalog_item_props`
38. `editor.toolpalette.catalog_manager`
39. `editor.toolpalette.create`
40. `editor.toolpalette.export`
41. `editor.toolpalette.global_init`
42. `editor.toolpalette.group_activate`
43. `editor.toolpalette.group_create`
44. `editor.toolpalette.refresh`
45. `editor.toolpalette.scheme_create`
46. `editor.toolpalette.scheme_register`
47. `editor.toolpalette.stocktool_find`
48. `editor.toolpalette.tool_execute`
49. `editor.toolpalette.tool_set_command`
50. `editor.toolpalette.window_get`
51. `editor.toolpalette.window_show`
52. `editor.toolpaletteset.add_palette`
53. `editor.toolpaletteset.show`
54. `editor.tray.add_item`
55. `editor.tray.item_config`
56. `editor.tray.remove`

## Files to edit

- `src/Ariadne.AcadNative/families/m08n_handlers.inc` — new A3 operation family handlers.
- `src/Ariadne.AcadNative/AriadneNativeJob.cpp` — add the M08N family include and include it in `familyHasOp` / `tryFamilyDispatch`; add only minimal shared includes/helpers if the M08N TU needs them.
- `src/Ariadne.AcadNative/AriadnePalette.cpp` — extend the attended-safe status/palette command surface where useful; no raw command agent surface.
- `tools/build_native_acad.ps1` — add optional isolated output support so A3 build validation never overwrites canonical `.dbx/.crx/.arx` artifacts.
- `tests/unit/test_m08n_handlers.py` — source-contract tests for M08N HasOp/Dispatch parity, attended gates, no original DWG writes, no raw command exposure, registry lifecycle.
- `config/operations.v2.json` — registry promotion for implemented M08N handlers via `tools/reconcile_native_registry.py --families n --apply` (or exact deterministic equivalent).
- Output artifacts: `reports/tickets/M08N-A3.md`, `reports/tickets/M08N-A3.json`, `packets/tickets/M08N-A3.md`, `handoff/tickets/M08N-A3.zip`; patch artifact under `handoff/pr/` if no PR is safely created.

## Implementation approach

1. Create a dedicated `m08n_handlers.inc` in the established M08 family pattern.
2. Implement hostless/source-verifiable operations first:
   - prompt output / alert metadata and prompt-args contract.
   - selection filters and non-interactive `acedSSGet("X", ...)` selection-set lifecycle where possible.
   - pickfirst and selection-set count/add/remove/free with safe `acedSS*` wrappers.
   - command registration lifecycle probes using a fixed safe no-op command, add/lookup/remove, and immediate cleanup.
   - runtime lifecycle introspection: MDI registration, service register/unregister, custom class registration evidence, demand-load registry-plan generation only (no registry writes).
   - input-point monitor/filter/context-reactor install/remove lifecycle where supported by headers; do not consume user input unless explicitly attended.
   - palette/status UI source with an attended-safe command/status surface and structured no-GUI errors under `accoreconsole`.
3. Implement attended editor operations with strict host gates:
   - `acedGetPoint/GetCorner/GetDist/GetAngle/GetReal/GetInt/GetString/GetKword`, `acedInitGet`.
   - `acedEntSel/NEntSel`, selection preview, menu invocation.
   - `AcEdJig` acquire/run via a tiny line jig only under full AutoCAD; if not attended, return `HOST_UNAVAILABLE` / `ATTENDED_ONLY` structured errors.
4. Do not expose arbitrary raw command execution. Any command/menu/tool operation must be either a fixed safe lifecycle probe or a structured attended-only refusal.
5. No `v1_target=false` escape. No fake PASS. If a header/API is absent or unsafe, record a hard blocker with evidence (`SDK_NOT_EXPOSED`, `HOST_UNAVAILABLE`, `SAFETY_FORBIDDEN`, etc.).

## Isolated native build output strategy

- Modify `tools/build_native_acad.ps1` with optional parameters such as `-OutputRoot` and `-TargetSuffix`.
- When `-OutputRoot reports/tickets/native/M08N-A3 -TargetSuffix .m08n_a3` is used:
  - pass `/p:OutDir=<OutputRoot>\bin\x64\Release\` and `/p:IntDir=<OutputRoot>\obj\<project>\x64\Release\` to MSBuild;
  - pass suffixed target names for `.dbx/.crx/.arx` so no canonical artifact in `src/.../bin/x64/Release` is overwritten;
  - keep `.crx/.arx` linked against the isolated `.dbx` import library by sharing the isolated `OutDir`.
- Default script behavior remains unchanged for other lanes.

## Attended AutoCAD needs

Attended tests are optional and only allowed if all safety gates pass:

- dedicated AutoCAD instance, not the user session;
- staged DWG only, never the original;
- unique pipe/channel/env args;
- no AutoCAD process kill;
- no save/write of original DWG.

If gates are not provably safe in this session, run source/static + isolated native build only and mark attended runtime evidence as not run with the exact safety reason.

## Tests / validation

Planned validation commands:

- `python -m pytest tests -q`
- `python tools\cadctl_cli.py registry coverage`
- `python tools\reconcile_native_registry.py --families n --apply` (after handler source is ready)
- Native isolated build, e.g. `powershell -File tools\build_native_acad.ps1 -OutputRoot reports\tickets\native\M08N-A3 -TargetSuffix .m08n_a3`
- Attended AutoCAD smoke only if the attended safety gates above pass.
- Verify operation coverage improves: A3 catalogued count decreases by implemented/hard-blocked/deprecated A3 operations.
- Verify original CAD source files are unmodified.

## Blocker criteria

Allowed hard blockers only with concrete evidence:

- `SDK_NOT_EXPOSED` — header/API absent or no native SDK entry point exists.
- `HOST_UNAVAILABLE` — operation requires live GUI/editor/session and no dedicated attended host is safely available.
- `LICENSE_UNAVAILABLE` — required licensed subsystem is missing.
- `SAFETY_FORBIDDEN` — would expose raw command execution, mutate user session, kill AutoCAD, write original DWG, or alter registry/profile without an approved scope.
- `OBJECT_ENABLER_REQUIRED` — requires a third-party object enabler not present.
- `ORIGINAL_WRITE_FORBIDDEN` — implementation would necessarily write the original DWG.

Complexity, native-only implementation, or bespoke UI implementation is not a blocker.
