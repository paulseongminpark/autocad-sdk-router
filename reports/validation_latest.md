# CADOS_M01 — Validation Capture (golden walking-skeleton run)

- **Captured:** 2026-06-22T00:00:14+09:00
- **Packet:** CADOS_M01_FULL_STACK_ULTRACODE_BUILD
- **Subject IR:** `runs/cados_m01_skeleton_20260621_231144_golden/dwg_graph_ir.json` (golden, 21747 entities, sha16 27DBF6B95FF72A89)
- **Command:** `python tools/cadctl_cli.py validate --ir runs/cados_m01_skeleton_20260621_231144_golden/dwg_graph_ir.json`
- **cadctl exit code:** `0`  · **cadctl status:** `ok`  · **report status:** `pass`
- **validation_id:** `val-529a732aecd9`
- **Verdict:** **PASS** — 6/6 gates pass, 0 failed, 0 skipped

## Gates

| Gate | Status | Required | Expected | Actual |
|------|--------|----------|----------|--------|
| `ir_schema_present` | pass | True | ariadne.dwg_graph_ir.v1 | ariadne.dwg_graph_ir.v1 |
| `entity_count_consistency` | pass | True | 21747 | 21747 |
| `required_artifacts_exist` | pass | True | ["cad_job.json", "cad_result.json", "dwg_graph_ir.json"] | ["cad_job.json", "cad_result.json", "dwg_graph_ir.json"] |
| `no_original_write_evidence` | pass | True | dwg_path != original_path | {"dwg_path": "D:\\dev\\99_tools\\autocad-sdk-router\\staging\\golde... |
| `registry_status_consistency` | pass | True | {"inspect.database.summary": "implemented", "inspect.entity.count":... | {"wired_total": 30, "required_ops_status": {"inspect.database.summa... |
| `run_folder_completeness` | pass | False | ["stdout", "stderr"] | ["stderr.txt", "stdout.txt"] |

## Notes

- Validator executed **LIVE** (not skipped, not fabricated) against the real golden IR. The captured stdout is stored alongside in `validation_latest.json`.
- `entity_count_consistency` gate cross-checked `diagnostics.entity_count == len(entities) == 21747` (and vs `realized_entity_count=21747`).
- `no_original_write_evidence` confirmed extraction ran on a staged copy under `staging/golden/...`, never the read-only original.
- `run_folder_completeness` is an advisory (`required:false`) gate; it passed.
