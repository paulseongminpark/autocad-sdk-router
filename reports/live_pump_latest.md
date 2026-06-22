# Live ARX pump (CADOS_M07B) — latest

**Status: PASS** (headless 17/17 + attended all_ok). Data: `reports/live_pump_latest.json`.

12 ops + `CADAGENT_STATUS`, 4-byte LE length + UTF-8 JSON frames, single main-thread pump.

**M07B pump-gating:** the 5 formerly-`attended_only` ops gate on `hostIsFullAutoCad()`
(host EXE `acad.exe` vs `accoreconsole.exe` — reliable; `acedEditor` is non-null in both
hosts, and the `ARIADNE_CAD_JOB_HOST_MODE` env hint does not propagate, so neither can
gate). Reported `host_mode` derives from the same discriminator (report == gate).

- Attended (acad.exe): `highlight`/`clear` (`AcDbEntity::highlight/unhighlight`) and
  `inspect_selection` (`acedSSGet` pickfirst) **execute for real**; `zoom`/`render` are
  honestly **deferred** (acedCommand cannot run reentrantly inside the modal pump command).
- Headless (accoreconsole): all 5 return `attended_only` (17/17 preserved).

**Headless** `runs/m07_pump_test` 17/17. **Attended** `cados_m07b_attended_20260622_123505`
all_ok (highlight 2/2, clear 2/2). Original golden unchanged; no remote push.
