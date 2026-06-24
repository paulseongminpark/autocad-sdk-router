# WAVE4X Final B Skipped Test Execution

- status: **PASS**
- skips_before: **20**
- skips_after: **0**
- final_xml: `reports/WAVE4X_FINAL_B_SKIP_FINAL.xml`

## Fixtures created
- `staging/dwg_20260617_191504/input.dwg (copied from repo golden source into this worktree)`
- `runs/m02_cadctl_rich/cad_job.json`
- `runs/m02_cadctl_rich/cad_result.json`
- `runs/m02_cadctl_rich/dwg_graph_ir.json`
- `runs/dwg_truth_autocad_cad_job_20260624_150300/native_cad_job_result.json`

## Live tests run
- ran: `True`
- env: `CADOS_LIVE=1`
- result: 11 passed in targeted live rerun; 562 passed in full CADOS_LIVE=1 suite
- `tests/integration/test_live_arx_pump.py::TestLiveArxPumpRoundTrip::test_pump_echo_status_list_stop`
- `tests/integration/test_native_graph_router.py::TestNativeGraphStagedWriteLive::test_staged_line_write_is_truthful_and_protects_original`
- `tests/smoke/test_router_inspect_database_graph.py::TestInspectDatabaseGraphLive::test_native_inspect_rich_is_consistent_and_safe`

## Attended tests
- ran: `False`
- result: No skipped pytest gate required dedicated full AutoCAD attended UI. All baseline skips were fixture-gated or CADOS_LIVE-gated headless tests.
