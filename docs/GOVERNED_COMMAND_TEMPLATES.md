# Governed Command Templates (Lane W5-TMPL)

Status: DESIGN + LIVE PROOF (4 templates shipped: `maintenance.drawing.audit`,
`maintenance.drawing.purge`, `define.assocarray.rectangular`,
`edit.assocarray.explode`). Governed middle path between "no raw command
dispatch, ever" and "arbitrary `acedCommand`/command-string exposure."

**Mid-flight correction (2026-07-06, from the SDK census re-audit
`D:\dev\.build\cados_plan\sdk_census_reaudit_20260706.md`):** team-lead's
original brief for section 4 named `GEOMCONSTRAINT`/`DIMCONSTRAINT`/
`DELCONSTRAINT`/`PARAMETERS` as candidate command mappings for the 23
`constraints_associativity` ops. The census independently re-confirmed this
lane's own finding (section 0/4 below, reached before the census landed):
those commands belong to a different ObjectARX subsystem
(`AcDbAssoc2dConstraintGroup`, the true 2D/3D constraint solver, which the
census found is ALREADY 35 ops strong and unblocked) than what the 23 blocked
ops actually are (`AcDbAssocArray*`/`AcDbAssocSurface*`/generic
`AcDbAssocAction`/`AcDbAssocManager` evaluate entry points). The census
additionally mapped all 23 to specific command equivalents and estimated
16-17/23 reachable via governed templates -- scoped to an **attended
`full_autocad`** host. This lane's own re-investigation (section 4 below)
found the actual headless blocker was a general, root-causable
`accoreconsole` exit-hang bug (fixed), not a fundamental attended-only
limitation -- so at least 2 of those 16-17 (`define.assocarray.rectangular`,
`edit.assocarray.explode`) are now live-verified HEADLESS, not merely
attended-feasible.

## 0. Registry recon (measured, not assumed)

The brief that opened this lane cited "16 runtime_commands ops blocked" and
"23 constraints/DCM-blocked ops." Before designing anything, this lane
re-derived both counts directly from `config/operations.v2.json` (525 ops)
because two prior lanes on this wave (Lane G, Lane I) both found stale/drifted
sub-fields in this exact registry, and "measure, don't assume" is the standing
convention (`dev-validation-and-qa`).

**23 constraints_associativity — CONFIRMED, exact match.** Every op whose
`family == "constraints_associativity"` has a `blocked_reason` beginning
`SAFETY_FORBIDDEN`. Count: 23. This is the family this doc calls "the DCM
family" below (see caveat in section 4 about what "DCM" actually means here).

**16 runtime_commands — NOT reproduced.** Scanning every op whose
`blocked_reason` starts with `SAFETY_FORBIDDEN` and mentions raw
command-string/command-dispatch language (`acedCommand`, `sendStringToExecute`,
`acedMenuCmd`, `AcTcTool::Execute`, `SendCommand`, "command dispatch", "command
surface") yields **10** ops, spread across four families (not one):

| op_id | family | blocked_reason (verbatim) |
|---|---|---|
| `command.invoke.coroutine` | active_document_write_original | raw command dispatch is blocked in M08O fallback policy. Fallbacks are managed/.NET/LISP-only and do not expose direct command strings. |
| `command.invoke.sync` | active_document_write_original | (same as above) |
| `command.invoke.sync.resbuf` | active_document_write_original | (same as above) |
| `doc.sendstring` | active_document_write_original | `AcApDocManager::sendStringToExecute` queues arbitrary raw command strings into an AutoCAD document command stream. Exposing `command_string` as an agent operation would be a raw command surface and may mutate the active user session. |
| `automate.com.get_for_command` | com_activex | command-context COM acquisition exposes raw automation handles in a live command surface. |
| `automate.com.send_command` | com_activex | COM `SendCommand` is raw command-string dispatch and must not be exposed to agents. |
| `command.queue.post` | editor_input | (same M08O text as command.invoke.*) |
| `module.command.lookup` | runtime_commands | (same M08O text as command.invoke.*) |
| `command.menu.invoke` | ui_customization | `acedMenuCmd` executes arbitrary menu/command macros in the active editor; exposing it as an agent API would be a raw command surface and may mutate the user session. |
| `editor.toolpalette.tool_execute` | ui_customization | `AcTcTool::Execute` programmatically fires a tool and may run arbitrary command/mutation behavior in the active editor; no raw tool execution is exposed to agents. |

The `runtime_commands` family itself (26 ops total) additionally contains 7
more `SAFETY_FORBIDDEN` ops that are about **ARX module load/unload**
(`module.load`, `module.load.acad_rx`, `module.load.by_app`,
`module.load.lisp`, `module.unload`, `module.command.remove_group`,
`module.load.demand_register`) — a categorically different hazard (loading
arbitrary native code into the host process) that this lane's template
mechanism does **not** attempt to cover; typed argument slots do nothing to
bound "which DLL gets loaded into AutoCAD."

**This doc proceeds on the measured 10, not the briefed 16.** Flagged to
team-lead as a registry-count correction, not silently substituted. If a
future audit finds 6 more command-dispatch-flavored ops this lane missed, the
category list above is the reproducible query to re-run
(`blocked_reason` regex over `config/operations.v2.json`).

## 1. Threat model

Every op in the table above is blocked for the **same underlying reason**,
stated most explicitly on `doc.sendstring` and `command.queue.post`: AutoCAD's
`acedCommand`/`AcApDocManager::sendStringToExecute`/`acedMenuCmd` family takes
an **arbitrary string** and feeds it to the command interpreter as if a user
had typed it. A string is Turing-complete input to that interpreter: it can
invoke ANY command (including ones with no registry entry at all, no
write-mode gate, no schema, no allow-list membership), chain commands with
`;`/space, embed AutoLISP via `(command ...)`  or `(eval (read ...))`, or drive
`SCRIPT`/`APPLOAD` to pull in more code. Exposing that surface to an agent
would make the ENTIRE governance stack built by this project --
`config/operations.v2.json`'s allow-list, `schemas/cad_job.v2.schema.json`'s
typed `args`, `policy.v2.json`'s write-mode gate, `cad.patch_dry_run` /
`cad.patch_apply_staged`'s staged-copy discipline -- optional. An agent could
just type `"OPEN C:\real\path.dwg\nSAVE\n"` and never touch the allow-list at
all. That is why every one of the 10 ops above is `SAFETY_FORBIDDEN`, not
merely `not_implemented`: this is a deliberate design decision, re-affirmed by
Wave 3's post-merge re-audit (`runtime_behavior` fields cite it directly), not
a capability gap waiting for someone to wire a handler.

**What a template changes, and what it does not.** A small, closed set of
built-in AutoCAD commands (maintenance-class: `AUDIT`, `-PURGE`, ...) are
genuinely useful and have NO agent-safe path today because the only way to
invoke a built-in command is through the forbidden raw-dispatch surface. The
template mechanism resolves this by moving the "which command runs" decision
from **runtime agent input** to **build-time registry authorship**: an agent
never supplies a command string. It supplies a `template_id` (from a
closed, human-curated list) and a small number of **typed argument slots**
(numeric ranges, enums, staged-only paths). The engine renders those slots
into a `.scr` file whose command-token sequence was fixed by whoever wrote the
template entry, not by the calling agent. The agent's only leverage is over
the values that fill pre-declared blanks -- never over which commands run,
how many, or in what order. This is exactly the "prepared statement vs. string
concatenation" pattern applied to AutoCAD's command line.

**Which door this engine actually uses, and why it's the sanctioned one.**
Per the SDK census re-audit (`sdk_census_reaudit_20260706.md` section 1b/3):
raw ObjectARX `acedCommand`/`acedCmd` are **compile-disabled in ObjectARX
2027** (per `docs/M08_FAMILY_HANDLER_CONTRACT.md`'s hard constraints) --
they are not merely policy-forbidden in this registry, they are not even
buildable from this project's native `.inc`/`.cpp` layer. The two doors
Autodesk's own guidance sanctions for command execution are the **AutoLISP
script lane** (`(command "VERB" ...)` inside a `.scr`/`.lsp`, or -- what this
engine actually does -- typing the verb and its answers as literal script
lines, the oldest and most-supported form of the same lane) and **.NET**
`Editor.Command`/`SendStringToExecute`. This engine's `.scr`-via-accoreconsole
mechanism (section 3) IS the sanctioned LISP/script door -- a **narrow,
allow-listed command-string builder** (specific verbs only, e.g. `AUDIT`/
`ARRAYRECT`, assembled from a closed per-template token list, never arbitrary
agent-supplied strings) is architecturally distinct from the already-forbidden
generic raw dispatch (`command.invoke.*`, `doc.sendstring`, etc. -- blocked
precisely because THEY expose an unscoped string, not because the script lane
itself is unsafe).

**What it explicitly does NOT fix**, and why the 23 constraints_associativity
ops mostly stay out of scope even though this doc was asked to estimate their
coverage (section 4): a handful of the 23 are blocked for the SAME
raw-command reason as above, but MOST are blocked because invoking them runs
an **unbounded native solver/evaluator** (`AcDbAssocAction::evaluate`,
`AcDbAssocManager::evaluateTopLevelNetwork`, `AcDbAssocArrayActionBody::
createInstance`, various `AcDbAssocXxxSurfaceActionBody::createInstance`).
Typed argument slots do not bound what a solver callback does once invoked --
argument-injection risk and unbounded-evaluation risk are different threats,
and templating only neutralizes the first. This distinction drives the
section-4 verdict.

## 2. Template schema

Registry file: `config/command_templates.json`. One entry per `template_id`:

```jsonc
{
  "template_id": "maintenance.drawing.audit",   // stable id, agent-facing
  "op_id": "maintenance.drawing.audit",         // paired config/operations.v2.json entry
  "status": "implemented",                       // catalogued | implemented | blocked
  "summary": "Run AUDIT (with optional fix) on the staged drawing.",
  "headless_safe": true,                          // measured, not assumed (section 5)
  "write_mode": {
    "default": "write_copy",
    "allowed": ["read", "write_copy"]              // read == fix=N (report-only); never write_original
  },
  "command_sequence": [                            // FIXED tokens; only {{slot}} placeholders vary
    { "literal": "AUDIT" },
    { "slot": "fix_answer" }
  ],
  "slots": {
    "fix_answer": {
      "type": "enum",
      "values": ["Y", "N"],
      "description": "Answer to AUDIT's 'Fix any errors detected?' prompt.",
      "maps_to_arg": "fix"                          // agent-facing arg name -> internal enum value
    }
  },
  "postconditions": [
    { "kind": "regex_capture", "pattern": "Total errors found\\s+(\\d+)\\s+fixed\\s+(\\d+)",
      "on_stdout": true, "bind": ["errors_found", "errors_fixed"] },
    { "kind": "entity_count_probe", "capture_before": true, "expect_unchanged": true }
    // entity_count_probe also supports expect_baseline+tolerance (AUDIT's
    // real template) and expect_increase (edit.assocarray.explode's real
    // template) -- see config/command_templates.json for the shipped forms.
  ],
  "evidence_refs": ["docs/GOVERNED_COMMAND_TEMPLATES.md#5-live-verification"]
}
```

Every field is mandatory except `evidence_refs` (added post-verification).
`command_sequence` is a list of `{"literal": "<fixed token>"}` or
`{"slot": "<slot name>"}` objects -- **never** a single format string, so
there is no string-interpolation step where a slot value could smuggle extra
script lines. Each `slot` must be declared in `slots` with an explicit
validator type:

| slot type | validation |
|---|---|
| `enum` | value must be a member of `values` (exact string match) |
| `int_range` | integer, `min <= v <= max` |
| `float_range` | float, `min <= v <= max` |
| `name_token` | `^[A-Za-z0-9_\-]{1,255}$` (AutoCAD-safe symbol name; no path separators, no wildcard) |
| `staged_path` | must resolve (via `Path.resolve()`) to a path INSIDE the run's own `staging/` tree; rejects any path outside it (no absolute escape, no `..`) |

**Universal rejection rule (applies to every slot type before its own
validator runs):** any value containing a control character (codepoint < 0x20
or 0x7F), a double or single quote, a semicolon, or a LISP paren (`(` or `)`)
is rejected outright with `INJECTION_REJECTED`, regardless of type. This is
the literal implementation of "no free-text slot ever reaches the command
line" -- even an `enum` or `int_range` slot goes through this gate first, so
a future template author cannot accidentally define a permissive type that
reopens the string-concatenation hole.

`headless_safe` is a template-level flag the engine trusts only after live
measurement (section 5); a template with `headless_safe: false` is refused
by the engine with `ATTENDED_ONLY_TEMPLATE` regardless of write_mode.

## 3. Execution model

Reuses the SAME low-level mechanism `tools/autocad-router.ps1`'s
`Invoke-CadJobRoute`/`Invoke-AccoreScr` already use for every `dwg_truth_autocad`
job (staged-copy discipline, `accoreconsole.exe /i <dwg> /s <script>`,
stdout/stderr capture, timeout+kill) -- reimplemented at the Python layer
in `tools/command_template_engine.py` rather than by adding a new `-Action` to
`autocad-router.ps1`, per this lane's brief ("prefer building on the existing
script/job lanes without touching the router"). Concretely:

1. **Resolve accoreconsole**: `tools/probe_routes.py::_detect_accoreconsole_candidates()`
   + `_cli()` (already the single source of truth every Python tool in this
   repo uses for "where is accoreconsole" -- `probe_reachability.py` imports
   the same module for exactly this). No new resolver logic.
2. **Validate args -> render `.scr`**: `render_script(template, args)` builds
   the literal/slot token list into ASCII `.scr` lines, matching the router's
   own `Encoding ASCII` convention for `.scr`/`.lsp` files (non-ASCII/DWG-path
   safety, same reasoning as the router's staging comment).
3. **Stage**: copy the input DWG to `staging/tmpl_<template_id>_<stamp>/input.dwg`
   (mirrors the router's `staging/dwg_job_<stamp>/input.dwg` naming family),
   ALWAYS -- every template runs against a staged copy, never the caller's
   path directly.
4. **Execute**: `accoreconsole.exe /i <staged_input.dwg> /s <rendered.scr>`,
   `cwd` = the staged file's directory, stdout/stderr redirected to files
   under the run dir, `subprocess.run(..., timeout=...)`; on timeout the
   process is killed and the result is `status: "error"`, `code:
   "ACCORECONSOLE_TIMEOUT"` (never a fake `ok`). The rendered `.scr` ALWAYS
   ends with `_QSAVE` (against the staged copy) before `QUIT`, regardless of
   `write_mode` -- a root-caused fix for a general accoreconsole exit hang,
   not a change to the write_mode contract (see section 5).
5. **Enforce postconditions**: run every entry in the template's
   `postconditions` array against the captured stdout/staged-file state;
   ANY postcondition failing degrades the result to `status: "partial"` (ran,
   but couldn't confirm the declared contract) -- never silently dropped.
6. **Envelope**: emits an `ariadne.autocad_sdk_result.v2`-shaped dict (same
   `schema`/`operation`/`status`/`write_mode`/`host`/`diagnostics`/`error`
   fields used by every other op in this repo, per
   `schemas/cad_result.v2.schema.json`), with `host.execution_host_class =
   "coreconsole"` and an additional (schema-additionalProperties-allowed,
   non-enum) `host.template_lane = "GOVERNED_COMMAND_TEMPLATE"` marker --
   deliberately NOT added to the closed `host.router_lane` enum in
   `schemas/cad_result.v2.schema.json`, to avoid a shared-schema edit for a
   single lane's addition (surgical-edit discipline).

`write_original` is impossible by construction: the engine has no code path
that skips staging, and the template schema's `write_mode.allowed` list is
validated against a closed enum of `["read", "write_copy"]` at template-load
time -- a template author cannot even author a `write_original`-permitting
entry without the loader rejecting the whole registry file.

## 4. DCM / constraints_associativity coverage estimate

**Caveat up front**: the 23 `constraints_associativity` ops reference
`AcDbAssocArrayActionBody`, `AcDbAssocXxxSurfaceActionBody`, and
`AcDbAssocManager` in their `blocked_reason` text -- the **associative
array/surface/network evaluation** subsystem. The commands originally named
as candidate mappings (`GEOMCONSTRAINT`/`DIMCONSTRAINT`/`DELCONSTRAINT`/
`PARAMETERS`) belong to a DIFFERENT ObjectARX class hierarchy
(`AcDbAssoc2dConstraintGroup`, the 2D sketch/parametric Dimensional
Constraint Manager) that does not appear ANYWHERE in these 23 ops' evidence
text, and no op in `config/operations.v2.json` references
`AcDbAssoc2dConstraintGroup` at all (checked: zero matches for
`GEOMCONSTRAINT|DIMCONSTRAINT|DELCONSTRAINT|PARAMETERS` in the registry
file). **The named commands do not map onto these 23 ops.** This lane's own
finding here was independently reproduced by the SDK census re-audit
(`sdk_census_reaudit_20260706.md` section 5), which additionally established
the true DCM/constraint-solver surface is already 35 ops strong and
unblocked -- these 23 are a different subsystem that merely shares its
evaluator plumbing with the constraint solver (hence the shared family name).

The REAL command-level correspondences for the 23 (adopting the census's
mapping, cross-checked against this lane's own class-reference reading --
both agree):

| ops (count) | underlying class | actual built-in command family |
|---|---|---|
| `define.assocarray.{create,path,polar,rectangular}` (4) | `AcDbAssocArrayActionBody::createInstance` | `ARRAYRECT`/`ARRAYPOLAR`/`ARRAYPATH` |
| `edit.assocarray.{explode,item,itemReplace,reset,source,transform}` (6) | same, item ops | `ARRAYEDIT` (Source/Replace/Reset/etc. sub-options) / `EXPLODE` (releases associativity) |
| `define.assocsurface.{blend,extrude,fillet,loft,offset,patch,result,trim}` (8) | `AcDbAssocXxxSurfaceActionBody::createInstance` | `SURFBLEND`/`SURFEXTRUDE`/`SURFFILLET`/`SURFLOFT`/`SURFOFFSET`/`SURFPATCH`/(n/a -- `result` reads a prior action's output, no command)/`SURFTRIM` |
| `edit.assocdata.xref` (1) | `AcDbAssocManager::syncUpWithXrefs` | `XREF`/`-XREF` reload (implicit, not a directly invocable scoped command) |
| `inspect.assocaction.evaluate`, `inspect.assocnetwork.evaluate` (2) | `AcDbAssocAction::evaluate` / `AcDbAssocManager::evaluateTopLevelNetwork` | no dedicated command; `REGEN`/`REGENALL` trigger the same evaluation as a documented side effect, but evaluate *everything*, not one scoped action |
| `inspect.assocsurface.topology` (1) | ASM result traversal | no command surfaces raw topology |
| `repair.assocdata.audit` (1) | `AcDbAssocManager::auditAssociativeData` | NOT the same call as the `AUDIT` command (`AcDbDatabase::audit`) -- superficially similar name, different C++ entry point, not covered by this lane's `AUDIT` template |

**Live attempt #1 -- `REGEN`** (candidate for `inspect.assocaction.evaluate` +
`inspect.assocnetwork.evaluate`). Runs cleanly headless, exit 0, original
unchanged -- but does NOT count as promoting either op: `REGEN` triggers the
EXACT unbounded solver callback path the `blocked_reason` text forbids, and
typed-argument-slot safety does not bound what a solver callback does once
invoked. Correctly NOT promoted, regardless of the section-5 QSAVE fix below
(this is an argument-injection-vs-evaluation-risk distinction, not a
headless-vs-attended one).

**Live attempt #2 -- `ARRAYRECT` (candidate for `define.assocarray.rectangular`)
-- SHIPPED, headless, live-verified.** First pass (`-ARRAYRECT`, the
hyphen-prefixed scripted form used by `-PURGE`) failed immediately: **"알 수
없는 명령" (unknown command)** -- unlike `-PURGE`, `ARRAYRECT` has no
hyphen-prefixed scripted variant; the plain `ARRAYRECT` (no hyphen) IS
accepted headlessly. Second pass (`ARRAYRECT` + bare numeric answers to the
dynamic corner-point prompts) got the array created but with WRONG semantics
(a bare number isn't a valid answer to a "specify opposite corner" point
prompt) AND hung on exit -- this hang turned out to be the SAME general
accoreconsole exit-hang bug found and root-caused for `AUDIT`'s `fix_answer`
(section 5), not anything array-specific: reproduced independently with a
bare `LINE` command and a `LINE`+`COPY` sequence, both with zero
associativity involved. Once fixed (unconditional `_QSAVE` before `QUIT`),
a THIRD pass using ARRAYRECT's explicit `C` (Count) and `S` (Spacing)
sub-options -- never the ambiguous dynamic-corner default -- produced a
fully deterministic, live-verified sequence:
`ARRAYRECT`, `L` (select last), `` (end selection), `C`, `<rows>`, `<cols>`,
`S`, `<row_spacing>`, `<col_spacing>`, `X` (exit grip-edit loop), `_QSAVE`,
`QUIT`. Measured: entity count is UNCHANGED by array creation (21747 before
and after a 3x2 array) -- a modern associative array wraps its source entity
as a SINGLE selectable database object (visually multiplied, but one entity
for `ssget`/`sslength` purposes), confirmed by re-running with NO fresh
entity drawn first (array applied to the drawing's actual pre-existing last
entity: still 21747 -> 21747). Shipped as `define.assocarray.rectangular`
(`config/command_templates.json`), `headless_safe: true`,
live-verified via the real `run_template()` engine (not just the ad-hoc probe
script), original DWG sha256 unchanged throughout. **v1 scope limitation
(documented on the template itself, not hidden)**: selection is via AutoCAD's
`L` (Last-created-entity) option, not an agent-addressable handle; a
handle-based selection slot is a natural follow-up this lane did not build.

**Live attempt #3 -- `EXPLODE` (candidate for `edit.assocarray.explode`) --
SHIPPED, headless, live-verified.** Chained off the ARRAYRECT array created
above (exploding only makes semantic sense against a drawing that actually
contains an array). First pass answered `L` then a blank line to "end
selection," mirroring ARRAYRECT/COPY's pattern -- this was WRONG:
`EXPLODE`'s select-objects sub-loop auto-terminates on a single `L` answer,
so the extra blank line fell through to a fresh, empty `Command:` prompt,
which repeats-last-command (fires `EXPLODE` a SECOND time on garbage
input, `*유효하지 않은 선택*` / invalid selection). Corrected: `EXPLODE`, `L`
only. Measured entity-count delta: 21747 (array, 1 entity) -> 21752 (post-
explode) = **+5, exactly `rows*cols - 1` for the 3x2 array** (the array's
single wrapping entity becomes 6 independent entities, net +5) -- a clean,
fully explained result, not a coincidence. Shipped as
`edit.assocarray.explode`, `headless_safe: true`, live-verified via
`run_template()` chained end-to-end (ARRAYRECT's own staged output DWG fed
as EXPLODE's input), original DWG sha256 unchanged throughout.

**Not attempted this lane**: the `ARRAYEDIT` sub-commands (item/replace/reset/
source, 4 more of the 6 `edit.assocarray.*` ops), the 7 `SURF*` surface
commands, and `XREF` reload for `edit.assocdata.xref`. Each has its own
distinct, unestablished prompt sequence (the ARRAYRECT/EXPLODE investigation
above shows how much iteration nailing ONE command's exact sub-option
sequence took); the QSAVE fix is a NECESSARY condition for all of them to
work headlessly (proven) but not by itself SUFFICIENT (each command's own
prompts still need the same careful measurement this lane did for ARRAYRECT/
EXPLODE). Flagged as a clear, scoped follow-up, not claimed done.

**Verdict: 2 of 23 SHIPPED and live-verified headless**
(`define.assocarray.rectangular`, `edit.assocarray.explode`), materially
better than this lane's own earlier "0 of 23" draft conclusion (before the
QSAVE root cause was found) and a genuine, if partial, confirmation of the
census's ~70% *mechanism* estimate -- just proven headless rather than
attended-only as the census scoped it. 2 more (`inspect.assocaction.evaluate`,
`inspect.assocnetwork.evaluate`) have a headless-runnable command trigger
(`REGEN`) that does NOT resolve their actual risk (unbounded solver
evaluation, an argument-injection-orthogonal concern) and correctly stay
`SAFETY_FORBIDDEN`. The remaining ~19 are either not attempted (11-12 more
`ARRAYEDIT`/`SURF*`/`XREF` candidates, each needing its own prompt-sequence
measurement) or have no command surface / reference a different C++ call
entirely (`inspect.assocsurface.topology`, `define.assocsurface.result`,
`repair.assocdata.audit`).

## 5. Live verification

See `tools/command_template_engine.py` + `tests/unit/test_command_template_engine.py`
(unit-level, mocked/pure-function tests for validation/rendering/postcondition
logic) and the `CADOS_LIVE=1`-gated live certs in the same test file (4
template classes: `TestAuditTemplateLive`, `TestPurgeTemplateLive`,
`TestArrayRectExplodeTemplateLive`, real accoreconsole, staged copy of
`tests/fixtures/native_sample.dwg`, sha256
`eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76` verified
unchanged before/after every live run). Live run artifacts land under
gitignored `runs/` (`w5tmpl_*`, `command_template_*`) and are not committed;
the measured outcome is captured here and in `build_log.md`'s `## Lane
W5-TMPL` section.

All 4 shipped templates ran successfully end-to-end multiple times in `read`
and `write_copy` write modes: `AUDIT` (regex-captured
`errors_found`/`errors_fixed` from the real Korean-locale AutoCAD 2027
console text, entity count probed 21747 before/after -- exact match to the
fixture's documented baseline), `-PURGE` (real named-object deletions
observed and regex-captured -- e.g. a "주석" leader/text/dimstyle style and
an unused layer -- entity count unchanged 21747/21747 both times, confirming
PURGE never touches entities), `ARRAYRECT` (associative array created,
entity count unchanged 21747/21747, confirming an array is one selectable
object regardless of visual row*col count), and `EXPLODE` (chained onto the
ARRAYRECT output, entity count 21747 -> 21752, exactly `rows*cols-1` for a
3x2 array). `accoreconsole /i /s` exit code 0 in every successful run; original DWG
sha256 verified byte-identical before/after in every run, successful or not.

**Root-caused finding, now fixed: accoreconsole hangs on QUIT whenever the
staged DB has unsaved changes.** `AUDIT`'s `fix_answer` slot was originally
speced as `["Y", "N"]`. Live measurement initially found `fix_answer="N"`
made `accoreconsole` hang on process exit -- 4 of 4 trials, alternated
against 4-of-4 clean exits for `"Y"` on the identical DWG/template/machine.
The AUDIT command's own report text and the after-probe entity-count file
were both written correctly (verified on disk) BEFORE the hang in every "N"
trial -- i.e. all real work completed; only the process's own shutdown never
returned, until the engine's timeout+kill fired (`status: "error"`, `code:
"ACCORECONSOLE_TIMEOUT"`, `retryable: true`; original DWG sha256 confirmed
unchanged every time). The initial ship decision (section-4-era) was to
restrict `fix_answer` to `["Y"]` only, treating this as unexplained.

**Further investigation (triggered by the mission-5 DCM pilot work) found
the SAME hang with completely unrelated content**: a bare `LINE` command with
nothing else, and a `LINE`+`COPY` sequence, both hung on `QUIT` identically
-- ruling out "N" specifically as the cause and ruling out session-time
drift too (a plain `AUDIT` fix=`Y` run interleaved between these failures
still succeeded reliably). The actual trigger: **any script that leaves the
in-memory database with an unsaved modification relative to its last save
point hangs `accoreconsole` on `QUIT`** -- most likely `FILEDIA=0`
suppresses file-browser dialogs but not a "save changes?" exit-confirmation
dialog, which a headless Core Console session can never dismiss (no UI
thread, and a `.scr` can only answer command-line prompts, not system
dialogs). Confirmed and fixed by adding an explicit `_QSAVE` immediately
before `QUIT`: fixed the bare `LINE` hang (3.2s, exit 0), the `ARRAYRECT`
grip-edit-loop hang (3.6s, exit 0), AND `AUDIT fix_answer="N"` (4.5s, exit 0)
-- the same one-line fix resolved all three independently-discovered hangs.

**Engine fix applied**: `run_template()` now unconditionally appends
`_QSAVE` before `QUIT` in every rendered `.scr`, regardless of `write_mode`.
This does NOT change the `write_mode` contract with the caller -- `read`
still means the ORIGINAL is never touched and no persistence is
reported/guaranteed; only the throwaway STAGED copy (already gitignored,
already discarded after the run) gets flushed to disk so accoreconsole's
exit path has nothing pending to hang on. `fix_answer`'s shipped enum is now
`["Y", "N"]` again, both live-verified, with a regression test
(`test_audit_fix_n_no_longer_hangs`) pinning that "N" completes well within
its timeout rather than merely "eventually stops timing out."
