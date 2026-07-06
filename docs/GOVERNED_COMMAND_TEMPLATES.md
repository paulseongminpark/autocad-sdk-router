# Governed Command Templates (Lane W5-TMPL)

Status: DESIGN + PARTIAL LIVE PROOF. Governed middle path between "no raw
command dispatch, ever" and "arbitrary `acedCommand`/command-string exposure."

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
    { "kind": "entity_count_sane", "against_fixture_baseline": 21747, "tolerance": 0 }
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
   (mirrors the router's `staging/dwg_job_<stamp>/input.dwg` naming family)
   UNLESS `write_mode == "read"`, in which case the staged copy is still made
   (AUDIT/PURGE never run against a path the caller directly controls) but no
   `_QSAVE` line is appended.
4. **Execute**: `accoreconsole.exe /i <staged_input.dwg> /s <rendered.scr>`,
   `cwd` = the staged file's directory, stdout/stderr redirected to files
   under the run dir, `subprocess.run(..., timeout=...)`; on timeout the
   process is killed and the result is `status: "error"`, `code:
   "ACCORECONSOLE_TIMEOUT"` (never a fake `ok`).
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
array/surface/network evaluation** subsystem. The commands this lane's brief
named as candidate mappings (`GEOMCONSTRAINT`, `DIMCONSTRAINT`,
`DELCONSTRAINT`, `PARAMETERS`/`-PARAMETERS`) belong to a DIFFERENT ObjectARX
class hierarchy (`AcDbAssoc2dConstraintGroup`, the 2D sketch/parametric
Dimensional Constraint Manager) that does not appear ANYWHERE in these 23
ops' evidence text, and no op in `config/operations.v2.json` references
`AcDbAssoc2dConstraintGroup` at all (checked: zero matches for
`GEOMCONSTRAINT|DIMCONSTRAINT|DELCONSTRAINT|PARAMETERS` in the registry file).
**The named commands do not map onto these 23 ops.** This is surfaced here
rather than silently substituted, per the same "measure the premise" standard
applied to the "16" count in section 0.

The REAL command-level correspondences for the 23 (by class, not by the
briefed command names):

| ops (count) | underlying class | actual built-in command family |
|---|---|---|
| `define.assocarray.{create,path,polar,rectangular}` (4) | `AcDbAssocArrayActionBody::createInstance` | `ARRAYRECT`/`ARRAYPOLAR`/`ARRAYPATH` |
| `edit.assocarray.{explode,item,itemReplace,reset,source,transform}` (6) | same, item ops | `ARRAYEDIT` (Source/Replace/Reset/etc. sub-options) |
| `define.assocsurface.{blend,extrude,fillet,loft,offset,patch,result,trim}` (8) | `AcDbAssocXxxSurfaceActionBody::createInstance` | `SURFBLEND`/`EXTRUDE`/`FILLETEDGE`/`LOFT`/`SURFOFFSET`/`SURFPATCH`/(n/a -- `result` reads a prior action's output, no command)/`SURFTRIM` |
| `edit.assocdata.xref` (1) | `AcDbAssocManager::syncUpWithXrefs` | `XREF`/`-XREF` reload |
| `inspect.assocaction.evaluate`, `inspect.assocnetwork.evaluate` (2) | `AcDbAssocAction::evaluate` / `AcDbAssocManager::evaluateTopLevelNetwork` | no dedicated command; `REGEN`/`REGENALL` trigger the same evaluation as a documented side effect |
| `inspect.assocsurface.topology` (1) | ASM result traversal | no command surfaces raw topology |
| `repair.assocdata.audit` (1) | `AcDbAssocManager::auditAssociativeData` | NOT the same call as the `AUDIT` command (`AcDbDatabase::audit`) -- superficially similar name, different C++ entry point, not covered by this lane's `AUDIT` template |

**Live attempt #1 -- `REGEN` (candidate for `inspect.assocaction.evaluate` +
`inspect.assocnetwork.evaluate`).** `REGEN` takes no arguments and prompts
nothing, so it is trivially headless-scriptable; ran it as a one-off (not a
shipped template -- see verdict below) against a staged copy of
`tests/fixtures/native_sample.dwg`, reusing the same
`command_template_engine.py` staging/accoreconsole-invocation helpers as the
real templates. Result (measured, no `_QSAVE` in this probe): **`accoreconsole
/i <staged> /s <script>` exits 0, stdout shows `REGEN` -> "모형 재생성 중."
("Regenerating model.") with no further prompts, and the ORIGINAL's sha256 is
unchanged.** But per the section-1 distinction, this does **not** count as
"promoting" the 2 ops: `REGEN`'s whole documented purpose is to force
re-evaluation of the associative network, i.e. it triggers the EXACT solver
callback path the `blocked_reason` text calls out as forbidden
("running arbitrary evaluation callbacks... outside CAD OS bounded
semantics"). A template around `REGEN` would let an agent trigger unbounded
solver evaluation on ANY staged drawing at will -- typed-argument-slot safety
does not bound "what the solver does," so wrapping it in a template does not
resolve the actual SAFETY_FORBIDDEN rationale. Measured, then correctly NOT
promoted.

**Live attempt #2 -- `ARRAYEDIT`/`-ARRAYRECT` (candidate for the 10
`assocarray.*` ops).** NOT attempted live. `-ARRAYRECT`'s scripted prompt
sequence (selection set, row/column/level counts, spacing, then an
associative-array "grip edit" context that in the AutoCAD 2016+ UI normally
exits via a dedicated `X`/Enter or a right-click "Exit array editing" command
with an unconfirmed script-mode token) is not established in this repo or
its docs, and guessing the exact prompt count risks a hung accoreconsole
process consuming a live-AutoCAD test cycle for a family (unbounded array
solver evaluation) that would fail the SAME section-1 test as `REGEN` even
if it ran cleanly. Given the ceiling is already known (array creation invokes
`AcDbAssocArrayActionBody::createInstance`, the literal class named in all 4
`define.assocarray.*` `blocked_reason` strings), spending a live cycle to
prove the mechanics would not change the verdict. Reported honestly as
**not attempted**, not as a false pass.

**Verdict: 0 of 23 template-coverable in a way that changes the safety
verdict.** 2 of 23 (`inspect.assocaction.evaluate`,
`inspect.assocnetwork.evaluate`) have a headless-runnable command trigger
(`REGEN`, live-verified) but templating it does not neutralize the
underlying risk, so they stay `SAFETY_FORBIDDEN`. The remaining 21 require
either unbounded solver evaluation (array/surface creation, xref sync) or
have no command surface at all (`inspect.assocsurface.topology`,
`define.assocsurface.result`) or reference a different C++ call than what a
template could stand in for (`repair.assocdata.audit`). This is a genuine
"0 proved out" deliverable, per the brief's own acceptance of that outcome.

## 5. Live verification

See `tools/command_template_engine.py` + `tests/unit/test_command_template_engine.py`
(unit-level, mocked/pure-function tests for validation/rendering/postcondition
logic) and the `CADOS_LIVE=1`-gated live cert in the same test file (real
accoreconsole, staged copy of `tests/fixtures/native_sample.dwg`, sha256
`eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76` verified
unchanged before/after every live run). Live run artifacts land under
gitignored `runs/` (`w5tmpl_*`, `command_template_*`) and are not committed;
the measured outcome is captured here and in `build_log.md`'s `## Lane
W5-TMPL` section.

Both templates ran successfully end-to-end multiple times in `read` and
`write_copy` write modes: `AUDIT` (regex-captured `errors_found`/`errors_fixed`
from the real Korean-locale AutoCAD 2027 console text, entity count probed
21747 before/after -- exact match to the fixture's documented baseline) and
`-PURGE` (real named-object deletions observed and regex-captured -- e.g. a
"주석" leader/text/dimstyle style and an unused layer -- entity count
unchanged 21747/21747 both times, confirming PURGE never touches entities).
`accoreconsole /i /s` exit code 0 in every successful run; original DWG
sha256 verified byte-identical before/after in every run, successful or not.

**A real, reproducible finding, not a script bug**: `AUDIT`'s `fix_answer`
slot was originally speced as an enum of `["Y", "N"]`. Live measurement found
`fix_answer="N"` makes `accoreconsole` hang on process exit -- **4 of 4
trials**, alternated against 4-of-4 clean exits for `"Y"` on the identical
DWG/template/machine, ruling out generic system-load flakiness as the
explanation. In every "N" trial the AUDIT command's own report text AND the
after-probe LISP's entity-count file were both written correctly (verified on
disk) BEFORE the hang -- i.e. all real work completes; only the
`accoreconsole.exe` process's own shutdown sequence never returns, until the
engine's timeout+kill fires (`status: "error"`, `code:
"ACCORECONSOLE_TIMEOUT"`, `retryable: true`; original DWG sha256 confirmed
unchanged in every one of these trials too). Root cause not established --
this is inside AutoCAD Core Console itself, not in this lane's script
generation (the "Y" and "N" `.scr` files are byte-identical apart from the one
character). **`fix_answer`'s shipped enum is `["Y"]` only** until root-caused;
this is a measured constraint, not a design choice, and reopening `"N"` needs
its own investigation (start by isolating whether the hang is about the
literal value `"N"` or about answering with whatever the prompt's bracketed
default is, since `<N>` was AUDIT's own default here).
