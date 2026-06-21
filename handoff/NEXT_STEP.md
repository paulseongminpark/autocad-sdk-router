# NEXT_STEP — after CADOS_M01 (PASS)

CADOS_M01 closed **PASS**: the CAD OS Layer has a working
extract → IR → SQLite → query → validate walking skeleton (21,747-entity golden,
6/6 gates), a native `inspect.database.graph` op smoked directly, and Operation
Registry v2 (30 implemented / 8 stub / 2 blocked over a 480-op catalog). Deferrals
D1–D5 are documented in `handoff\TAKEOVER.md`.

Two candidate next packets. **A is recommended** because the walking skeleton
already passes, so the highest-leverage move is to let a consumer use the CAD OS
through `cadctl` and surface real requirements, rather than deepening native
coverage before there is a consumer pulling on it.

---

## Option A — `D04_IMPORT_CAD_OS_CAPABILITIES` (RECOMMENDED)

**Goal:** Daedalus consumes the CAD OS Layer through `cadctl` as a capability
provider — i.e. the control plane above this router calls the cadctl CLI / IR
contract instead of touching AutoCAD or DWGs directly. Prove the integration on
the existing golden (21,747 entities) end to end.

**Why now:** the walking skeleton is PASS, so the contract surface
(`cadctl_cli.py` + `dwg_graph_ir.v1` + `validation_report.v1`) is ready to be
imported. A real consumer will tell us which ops actually matter next (informs
how to prioritize M02's native work), instead of guessing.

**First steps:**
1. Read the Daedalus capability-registry contract (`project_daedalus_os` /
   `project_cad_os_layer` memories + the Daedalus packet sequence — currently at
   P02 PARTIAL, P03 next) and decide how CAD OS registers as a capability.
2. Map cadctl's agent-facing CLI (`status | inspect | query | validate |
   registry list | registry coverage`) onto Daedalus capability descriptors.
3. Wire a thin Daedalus → `cadctl_cli.py` adapter (no AutoCAD/DWG direct access;
   IR + validation report are the interface).
4. Run the golden through Daedalus → cadctl → IR → validate and assert the same
   21,747 / 6-of-6 result the walking skeleton produced.
5. Honest closeout: handoff zip + index, deferrals preserved.

**Non-goals:** do **not** relink the `.arx`, router-wire the native graph op, or
fix non-ASCII fidelity here — those belong to Option B / M02.

---

## Option B — `CADOS_M02_NATIVE_IR_COMPLETION`

**Goal:** Finish the native IR path that M01 deliberately left at the edge:
router-wire the native `inspect.database.graph` op, relink the `.arx`, fix
non-ASCII fidelity, and implement more native ops.

**Scope (closes M01 deferrals):**
- **D2:** add `inspect.database.graph` to the `autocad-router.ps1` native
  allow-list so it is routable via cadctl/router (not just direct accoreconsole).
- **D1:** relink `Ariadne.AcadNative.arx` once AutoCAD is **not** holding the file
  (no live `acad.exe` lock); confirm against `reports\build_native_latest.log`.
- **D3:** widen the ASCII funnel — preserve UTF-8 `dxf_name` / `layer` /
  `block_name` (e.g. Korean "설비OPEN") instead of `acharToAscii` → `?`; vendor a
  JSON lib if needed.
- **D4:** implement the next tranche of native ops beyond the current 30, driven
  by the Operation Registry v2 stub/blocked list.

**First steps:**
1. Confirm no `acad.exe` lock, then `dotnet build` the native module and verify
   the on-disk `.arx` relinks clean (resolves D1).
2. Add the native op to the router allow-list; route it through cadctl and smoke
   on the 3-entity and golden drawings (resolves D2).
3. Replace `acharToAscii` with a UTF-8-preserving path; re-smoke on a drawing
   containing non-ASCII layer/block names; assert bytes preserved (resolves D3).
4. Pick the next native ops from `config\operations.v2.json` (stub → implemented)
   with tests; keep zero regression on the 120-test suite.

**Non-goals:** Daedalus integration (that is Option A); live ARX named-pipe write
pump (still design-only per D5).

---

## Recommendation

Take **Option A** next. The walking skeleton PASS means the CAD OS contract is
ready to be *consumed*; importing it into Daedalus exercises the real interface
and tells us which native ops M02 should prioritize. Hold Option B (M02) until a
consumer has pulled on the contract — or pick B first only if non-ASCII fidelity
(D3) or a routable native graph op (D2) becomes an immediate blocker.
