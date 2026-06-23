# AutoCAD Fallback Policy (M08O)

Status: enforced for fallback work (`M08O-T01`, `M08O-T02`) in
`D:/dev/99_tools/autocad-sdk-router_m08o_fallback`.

## m08o-fallback-raw-command-hard-block

## 1) Hard rule: no direct AutoCAD command injection as agent surface

The following command-style pathways are **hard-blocked** (closure state =
`hard_blocked`) and must never be exposed to operators:

- `command.invoke.coroutine`
- `command.invoke.sync`
- `command.invoke.sync.resbuf`
- `command.queue.post`
- `module.command.lookup`

Rationale:

- These are raw command dispatch APIs (`acedCommand*`, `acedCmd*`, `acedPostCommand*` or
  `module.command` lookup path) and bypass the operation allow-list.
- They are unsafe for agent exposure because they permit arbitrary command entry,
  unbounded side-effects, and non-deterministic command-string routing.
- They are closed as **SAFETY_FORBIDDEN** and documented with explicit evidence refs.

Enforcement in `config/operations.v2.json`:

- `status: "blocked"`
- `blocked_reason` begins with `SAFETY_FORBIDDEN`
- `implementation_strategy: "hard_blocked"`
- `evidence_required: "blocker_ref_and_evidence"`

## 2) COM bootstrap/load fallback policy

For COM-attached/full-AutoCAD fallback execution, only bootstrap/load operations
that are explicit and deterministic are permitted:

- **ARX/DBX modules:** `ARXLOAD` (in script as `arxload` where host allows direct load)
- **Managed DLL/NET adapters:** `NETLOAD`
- **.lsp support adapters:** AutoLISP `load`/`SDKDWGXTRACT`/`QUIT` scripts
- `APPLOAD` may be treated as an equivalent ARX bootstrap helper in attended
  workflows, but raw command-string send paths remain blocked.

This means:

- module registration and execution must be explicit by function and argument contract,
  not by arbitrary command text.
- no new `SendCommand`-style raw command surface is accepted for routing or policy.

Fallback surfaces in code:

- `Invoke-AutoCadRoute` and `Invoke-AccoreScr` generate **AutoLISP** and **NETLOAD** scripts.
- `Invoke-FullAutoCadCadJob` uses deterministic `arxload`/`ARX` + `ARIADNE_NATIVE_JOB`
  staging workflow.
- `Get-AutoLispExtractScr` returns a constrained `.lsp` script that writes one JSON file
  and quits.

## 3) AutoLISP and .NET adapter constraints

- **AutoLISP adapter:** only known, static scripts shipped by router code paths,
  no user-supplied script text.
- **Managed adapter:** only `.NET` command entry points loaded via `NETLOAD` and invoked by
  router-defined command names (e.g. `ARIADNE_CAD_JOB`, `ARIADNE_DWG_GEOM_EXTRACT`,
  `ARIADNE_DWG_DBX_EXTRACT`).

Any fallback proposal must use these adapters or be declared `hard_blocked`.

## 4) Test hooks

The policy is validated by:

- `tests/unit/test_m08_operation_coverage.py`:
  - raw commands are never agent-exposed (`agent_exposed == false`).
  - every blocked op has a `blocker_ref`.
- `tests/unit/test_m08a_catalog_reopen.py`:
  - raw command owner/ticket check.
  - v1 escape still forbidden.
- this ticket's patch artifacts and report files.

## 5) References

- `docs/M08_REMAINING_BATCH_PLAN.md` (Pane B/FALLBACK hard-block target)
- `docs/M08_FAMILY_HANDLER_CONTRACT.md`
- `config/policy.v2.json` (raw-command prohibition)
- `tools/operation_coverage_matrix.py`
- `config/operations.v2.json`
