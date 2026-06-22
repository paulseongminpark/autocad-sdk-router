[PACKET]
PACKET_ID=CADOS_M07A_ATTENDED_SURFACE_VERIFICATION
PROJECT=autocad-sdk-router
ROOT=D:\dev\99_tools\autocad-sdk-router
TARGET_AGENT=aclaude (parallel subagents)
MODE=parallel-subagents (worktree-isolated)
ROLE=@executor
EXECUTION_SCOPE=Implement + attended-verify the M07 attended-only deep-native surfaces
PREVIOUS_PACKET=CADOS_M07_LIVE_ARX_AND_DEEP_NATIVE_SURFACE
AUTHORED_BY=aclaude (M07 remainder)

GOAL:
- Close the M07 attended residue: the surfaces headless accoreconsole cannot verify.
- IMPLEMENT the genuinely-implementable ones (AcRxProperty/OPM registration; palette/status command; worldDraw is already coded).
- ATTENDED-VERIFY each surface in a DEDICATED, agent-launched AutoCAD — or hard-block with exact evidence.
- No fake PASS. No original DWG write. Do not touch the user's running acad.exe (PID 49460). No remote push.

CONTEXT (already true at HEAD; verified by the M07 audit):
- M07 committed (router 03fdcd7). Live ARX pump = 12 ops + CADAGENT_STATUS, headless 17/17.
- Deep-native committed matrix: 7 implemented / 3 attended_blocked / 0 design_only.
  - implemented (headless-provable): custom entity (AriadneProbe), worldDraw CALLBACK (AriadneProbe::subWorldDraw circle), object overrules, persistent reactors, editor jigs (host-gated), filer versioning (AriadneRecord), protocol extensions.
  - NEW this remainder (already built, .crx 236544, capability live): selection monitor (AriadneSelectionMonitor : AcEditorReactor, pickfirstModified; registration acedEditor-gated, events attended).
  - attended_blocked (this packet's targets): AcRxProperty/OPM PANEL, palette/status UI, worldDraw PIXEL render, attended live-pump proof, attended FIRING of reactor/overrule/jig/selection-monitor.
- Native sources: src/Ariadne.AcadNative/{AriadneNativeJob.cpp (.arx/.crx), AriadneProbe.{h,cpp}}; src/Ariadne.AcadNativeDbx/{AriadneRecord,AriadneProtocol,AriadneDbxEntry}.* (.dbx). Build: tools/build_native_acad.ps1 (lock-resilient; AutoCAD NOT killed).
- Confirmed ObjectARX 2027 signatures (use verbatim):
  - AcRxProperty ctor: `AcRxProperty(const ACHAR* name, const AcRxValueType& type, const AcRxObject* owner=NULL)` (rxprop.h:135); overrides `subGetValue(const AcRxObject*, AcRxValue&) const` (151), `subSetValue(AcRxObject*, const AcRxValue&) const` (167).
  - Value type: `AcRxValueType::Desc<double>::value()` (rxvaluetype.h:385). Start with ONE read/write double property "AriadneSize" backed by AriadneProbe::size()/setSize() (lowest risk — double is a fundamental value type). Optionally add a read-only AcGePoint3d "AriadneCenter" only if the AcGe value type resolves cleanly.
  - Member builder: `AcRxMemberCollectionBuilder` (rxmember.h:330) `.add(AcRxMember*)`. Register on `AriadneProbe::desc()` in AriadneDbxEntry.cpp kInitAppMsg AFTER `acrxBuildClassHierarchy()`; tear down in kUnloadAppMsg.
  - AcEditorReactor selection signal: `pickfirstModified()` (aced.h:541) — already used by AriadneSelectionMonitor.

READ_ALLOW:
- D:\dev\99_tools\autocad-sdk-router\**
- D:\dev\_ariadne\_daedalus\external\cad_os\**
- AutoCAD 2027 install + ObjectARX 2027 SDK + MSBuild toolchain paths (build/test).
- C:\ObjectARX 2027\inc\** (header signatures), C:\ObjectARX 2027\samples\** (patterns).

CHANGE_ONLY (each subagent works in its OWN git worktree; disjoint file ownership — see ASSIGNMENTS):
- D:\dev\99_tools\autocad-sdk-router\{src,tools,tests,reports,runs,docs,staging,packets,handoff}\**
- (lead merges; subagents do NOT push, do NOT cross into another subagent's owned files)

DO_NOT_CHANGE / HARD SAFETY (NON-NEGOTIABLE):
- The user's running acad.exe (PID 49460): never attach to it, never send it a command, never close it.
  - DO NOT use `New-Object -ComObject AutoCAD.Application` (may attach to PID 49460).
  - The ONLY allowed attended channel: `Start-Process` a NEW acad.exe with a startup script that arxloads the .dbx+.crx and runs CADAGENT_PUMP on a UNIQUELY-named pipe (e.g. ARIADNE_PUMP_PIPE=\\.\pipe\ariadne_attended_<agent>_<rand>); then drive THAT pipe only. The pipe is created by your launched instance, so commands can never reach PID 49460. Record the launched PID; only ever quit that PID.
  - If you cannot confine automation to your own launched PID, or cannot launch a separate instance, STATUS=BLOCKED with the exact reason. Never risk the user's session for a PASS.
- Original golden DWG (staging\dwg_20260617_191504\input.dwg) and any original *.dwg: READ-ONLY. Use a blank new doc or a staged copy. Verify the golden sha256 (27DBF6B95FF72A89FD53B153891187365B9E8EBC4C05A97CFED307057BF49BC8) unchanged at the end.
- No original write, no live save of any original, no remote push, no secrets.
- Do not mark an unverified or unavailable surface as PASS. attended_blocked WITH evidence is an acceptable, honest outcome.

ASSIGNMENTS (3 parallel subagents, disjoint write sets, worktree-isolated):

  AGENT ATT-OPM  (owns src/Ariadne.AcadNativeDbx/** + tests for it)
  - Implement AcRxProperty "AriadneSize" (read/write double -> AriadneProbe::size()/setSize()) registered via AcRxMemberCollectionBuilder on AriadneProbe::desc() in AriadneDbxEntry.cpp (after acrxBuildClassHierarchy); declare in AriadneDbxApi.h; unregister on unload.
  - Add a headless proof: an exported `ariadneProbePropertyCount()` (or an inspect op) that enumerates registered properties via AcRxMemberQueryEngine -> prove count>=1 headless (registration is headless-provable even though the OPM PANEL is not).
  - Build (tools/build_native_acad.ps1). Headless-confirm property registration (>=1).
  - ATTENDED: in a dedicated launched acad.exe, create an AriadneProbe (extend.customclass.create via the pump or a command), open Properties (OPM), confirm "AriadneSize" shows and is editable (screenshot + read-back the value via the property). Or BLOCK with exact reason.

  AGENT ATT-VISUAL  (owns src/Ariadne.AcadNative/AriadneProbe.{h,cpp} + a palette command file + its tests)
  - worldDraw PIXEL: AriadneProbe::subWorldDraw already draws a circle. ATTENDED: create an AriadneProbe, REGEN/zoom, screenshot the viewport, confirm the circle marker renders. Or BLOCK.
  - Palette/status UI: assess feasibility for AutoCAD 2027; if feasible, add an attended-only command (e.g. ARIADNE_PALETTE) registered ONLY when acedEditor!=nullptr (full_autocad), guarded so it never compiles/loads into the coreconsole path destructively. ATTENDED: run it, screenshot the palette/status pane. If MFC/UI cannot be safely built or shown, BLOCK with exact reason (this is an acceptable honest outcome).
  - NOTE: keep palette code out of the headless coreconsole code path; if it cannot build cleanly into the existing .crx/.arx without pulling MFC UI libs, mark palette attended_blocked-by-toolchain with evidence and do NOT break the existing build.

  AGENT ATT-LIVE  (owns runs/** attended harness + reports for the attended pump/firing; does NOT edit native source)
  - Build the dedicated-instance attended harness (Start-Process acad.exe /b startup.scr -> arxload dbx+crx -> CADAGENT_PUMP on a unique pipe; pipe client).
  - ATTENDED live-pump: prove echo/status/list_documents in a REAL editor, AND that the 5 attended-only ops actually DO the thing in attended (highlight_handles, clear_highlight, zoom_to_handles, render_view, inspect_selection) rather than returning the headless attended_only stub. (Note: the current pump returns attended_only for these unconditionally; record whether attended host should instead execute them — propose the gating change as a draft for the lead, do NOT edit native source in this agent.)
  - ATTENDED FIRING: enable reactor + overrule + selection-monitor + run a jig in the dedicated editor; confirm callbacks fire (commandWillStart count>0, pickfirstModified count>0 after a pickfirst selection, overrule open/close>0, jig point acquired). Read counts via inspect.*.registry. Or BLOCK per surface.
  - Verify golden sha unchanged; quit ONLY the launched PID.

BUNDLE (each agent):
1. Confirm clean worktree + read the M07 reports + the confirmed signatures above.
2. Implement your owned surface (ATT-OPM, ATT-VISUAL) or build the harness (ATT-LIVE).
3. Build (lock-resilient). Headless-prove what is headless-provable.
4. Attempt the attended verification via a DEDICATED launched acad.exe + unique pipe. Capture evidence (pump responses, registry counts, screenshots, COM-free).
5. Verify golden sha unchanged. Quit only your launched PID.
6. Return a structured verdict: per-surface VERIFIED(+evidence) | IMPLEMENTED-HEADLESS(+attended BLOCKED w/ reason) | BLOCKED(+exact reason). No fake PASS.

ACCEPTANCE (packet-level, lead-merged):
- AcRxProperty/OPM: registration implemented + headless-proven; OPM panel display VERIFIED attended or BLOCKED w/ evidence.
- worldDraw pixel: VERIFIED attended (screenshot) or BLOCKED w/ evidence.
- palette/status UI: implemented + VERIFIED attended, or BLOCKED-by-toolchain w/ evidence (acceptable).
- attended live-pump + attended firing (reactor/overrule/jig/selection-monitor): VERIFIED w/ counts/evidence or BLOCKED w/ exact reason.
- Existing build + tests stay green (no regression). Golden DWG unchanged. PID 49460 untouched. No push.

FINAL_RESPONSE_FORMAT (each agent returns; lead synthesizes):
```txt
[CADOS M07A AGENT RESULT: <agent>]
SURFACE: <name>
IMPLEMENTED: yes/no (files, build result)
HEADLESS PROOF: <evidence or n/a>
ATTENDED: VERIFIED | BLOCKED
  - dedicated_pid: <pid or none>  (PID 49460 untouched: yes)
  - evidence: <pump responses / registry counts / screenshot path>
  - blocker (if blocked): <exact reason>
GOLDEN UNCHANGED: yes/no
NEXT: <merge note for lead>
[/CADOS M07A AGENT RESULT]
```
[/PACKET]
