# CADOS M06 Visual Batch Golden Regression

Packet: `CADOS_M06_VISUAL_BATCH_GOLDEN_REGRESSION`  
Status: `PASS`  
Executed from: `D:\dev\99_tools\autocad-sdk-router`  
Run directory: `runs/m06_visual_batch_golden`  
Generated: 2026-06-22T05:22:29+09:00

## Scope

M06 was limited to the CAD OS v1 completion gate. It did not enter Daedalus/Ariadne app integration, did not write the original DWG, and did not push to any remote.

## Packet Commands Executed

```powershell
python tools\cados_m06.py visual --before runs\m05_patch_create_line\pre\dwg_graph_ir.json --after runs\m05_patch_create_line\post\dwg_graph_ir.json --diff runs\m05_patch_create_line\cad_diff.json --out runs\m06_visual_batch_golden\visual
python tools\cados_m06.py batch --manifest runs\m06_visual_batch_golden\batch_manifest.json --out runs\m06_visual_batch_golden\batch
python tools\cados_m06.py golden --manifest tests\golden\golden_manifest.json --expected tests\golden\expected_counts.json --out runs\m06_visual_batch_golden\golden
python tools\cados_m06.py perf --artifact small:ir:runs\m05_patch_create_line\pre\dwg_graph_ir.json --artifact golden21747:ir:runs\m03_rich_ir\dwg_graph_ir.json --artifact large291706:json:runs\native_graph_20260621_234158\result_scale_graph.json --out runs\m06_visual_batch_golden\performance
```

## Visual

- Status: `PASS`
- Route: `ir_svg`
- Verification ref: `reports/visual_verification_latest.json`
- Before SVG: `runs/m06_visual_batch_golden/visual/before.svg`
- After SVG: `runs/m06_visual_batch_golden/visual/after.svg`
- Overlay SVG: `runs/m06_visual_batch_golden/visual/overlay.svg`
- Visual diff: `runs/m06_visual_batch_golden/visual/visual_diff.json`
- Created handles highlighted: `1919C`

PNG/PDF plotting is not claimed. The available implemented route for M06 is real IR-to-SVG rendering with before/after/overlay plus JSON diff evidence.

## Batch

- Status: `PASS`
- Manifest: `runs/m06_visual_batch_golden/batch_manifest.json`
- Successes: `4`
- Failures: `0`
- Quarantine: `0`
- Read-only DWG inspect fixture: `staging/dwg_20260617_191504/input.dwg`

## Golden

- Status: `PASS`
- Manifest: `tests/golden/golden_manifest.json`
- Expected counts: `tests/golden/expected_counts.json`
- Fixture count: `1`
- Golden entity count: `21747`

## Performance

- Status: `PASS`
- Small/golden IR artifacts were parsed and measured.
- Large fixture evidence: `runs/native_graph_20260621_234158/result_scale_graph.json` (49113314 bytes; paired summary records 291706 modelspace entities).

## Reports

- `reports/visual_verification_latest.json`
- `reports/batch_latest.json`
- `reports/golden_regression_latest.json`
- `reports/performance_latest.json`
- `reports/review_latest.json`
- `runs/m06_visual_batch_golden/review/review_report.md`
- `runs/m06_visual_batch_golden/review/review_report.html`

## Safety

- Original source used only as read-only staging fixture: `staging/dwg_20260617_191504/input.dwg`
- Original SHA256 after M06: `27dbf6b95ff72a89fd53b153891187365b9e8ebc4c05a97cfed307057bf49bc8`
- Original modified: `no`
- Remote push: `no`

## Tests

- `python -m pytest tests\unit\test_cados_m06_runner.py tests\unit\test_visual_report.py tests\test_cad_job_batch_harness.py tests\smoke\test_cadctl_rich_ir.py -q` -> `28 passed in 1.35s`
- `python -m pytest tests\unit\test_cados_m06_runner.py tests\unit\test_visual_report.py tests\unit\test_m05_cli_contract.py tests\unit\test_validator_gates.py tests\unit\test_patch_engine.py tests\unit\test_patch_engine_policy.py tests\unit\test_cad_diff.py tests\unit\test_cadctl.py tests\unit\test_operation_registry_v2.py tests\test_cad_job_batch_harness.py tests\smoke\test_cadctl_rich_ir.py -q` -> `127 passed in 2.78s`
- `CADOS_LIVE=1 python -m pytest -q` -> `260 passed in 74.84s`
- `python -m unittest discover -s tests -p "test*.py"` -> `Ran 223 tests in 18.823s, OK (skipped=3)`

## Required Output

```text
[CADOS M06 RESULT]
STATUS: PASS
VISUAL:
- status: PASS
- artifacts: runs/m06_visual_batch_golden/visual/before.svg, runs/m06_visual_batch_golden/visual/after.svg, runs/m06_visual_batch_golden/visual/overlay.svg, runs/m06_visual_batch_golden/visual/visual_diff.json
BATCH:
- status: PASS
- manifest: runs/m06_visual_batch_golden/batch_manifest.json
- successes: 4
- failures: 0
GOLDEN:
- status: PASS
- fixtures: tests/golden/golden_manifest.json, tests/golden/expected_counts.json
PERFORMANCE:
- status: PASS
- large_fixture: runs/native_graph_20260621_234158/result_scale_graph.json
REPORTS:
- reports/visual_verification_latest.json
- reports/batch_latest.json
- reports/golden_regression_latest.json
- reports/performance_latest.json
- reports/CADOS_M06_VISUAL_BATCH_GOLDEN_REGRESSION.md
- tests: focused 28 passed; combined 127 passed; full pytest 260 passed; unittest 223 OK skipped=3
BLOCKERS:
- none
NEXT:
- CADOS_M07_LIVE_ARX_AND_DEEP_NATIVE_SURFACE
[/CADOS M06 RESULT]
```
