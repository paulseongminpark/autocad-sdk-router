# CADOS M05 Patch Diff Validation Transaction

Packet: `CADOS_M05_PATCH_DIFF_VALIDATION_TRANSACTION`  
Status: `PASS`  
Executed from: `D:\dev\99_tools\autocad-sdk-router`  
Run directory: `runs/m05_patch_create_line`  
Generated: 2026-06-22T05:25:00+09:00

## Scope

M05 was limited to the CAD OS v1 completion gate. It did not enter Daedalus/Ariadne app integration, did not write the original DWG, and did not push to any remote.

## Packet Commands Executed

```powershell
python tools\cadctl_cli.py patch dry-run --dwg staging\dwg_20260617_191504\input.dwg --patch runs\m05_patch_create_line\patch_input.json --out runs\m05_patch_create_line\dry_run
python tools\cadctl_cli.py patch apply-staged --dwg staging\dwg_20260617_191504\input.dwg --patch runs\m05_patch_create_line\patch_input.json --out runs\m05_patch_create_line
python tools\cadctl_cli.py diff --before runs\m05_patch_create_line\pre\dwg_graph_ir.json --after runs\m05_patch_create_line\post\dwg_graph_ir.json --out runs\m05_diff_check
python tools\validator.py --run runs\m05_patch_create_line --out reports\validation_latest.json
```

## Patch

- Patch id: `m05-create-line-20260622`
- Operation smoked: `create_line`
- Native op: `write.entity.line`
- Registry pipeline ops promoted to `implemented`: `apply.patch`, `diff.before_after`, `validate.patch`
- Dry run: `runs/m05_patch_create_line/dry_run/dry_run_plan.json`
- Staged apply result: `runs/m05_patch_create_line/result.json`
- Staged input: `runs/m05_patch_create_line/staged_input.dwg`
- Staged output: `runs/m05_patch_create_line/staged_output.dwg`

Supported staged native patch ops are currently:

- `create_line`
- `create_circle`
- `create_layer`
- `set_layer` as layer-table creation support

Unsupported mutation ops continue to return structured `not_implemented` or `blocked`; no unsupported op is reported as pass.

## Diff

- Diff ref: `reports/patch_diff_latest.json`
- CLI diff ref: `runs/m05_diff_check/cad_diff.json`
- Added: `1`
- Removed: `0`
- Modified: `0`
- Entity count before: `21747`
- Entity count after: `21748`
- Added type: `LINE`

## Validation

- Validation ref: `reports/validation_latest.json`
- Status: `pass`
- Gates: `14 / 14`
- Failed: `0`
- Blocked: `0`
- Skipped: `0`
- Subject IR: `runs/m05_patch_create_line/post/dwg_graph_ir.json`

The validator now resolves `post/dwg_graph_ir.json` automatically for `--run <run_dir>` patch runs, so the packet command validates the post-apply IR, patch policy, diff, journal, staged artifacts, and original hash evidence in one invocation.

## Journal And Safety

- Journal ref: `reports/journal_latest.json`
- Original source used as read-only input: `staging/dwg_20260617_191504/input.dwg`
- Original SHA256 before: `27dbf6b95ff72a89fd53b153891187365b9e8ebc4c05a97cfed307057bf49bc8`
- Original SHA256 after: `27dbf6b95ff72a89fd53b153891187365b9e8ebc4c05a97cfed307057bf49bc8`
- Original modified: `no`
- Remote push: `no`

## Code And Config Changes

- `tools/cadctl_cli.py`: added packet-compatible `patch dry-run --dwg --patch --out`, `patch apply-staged --dwg --patch --out`, and `diff --before --after --out`.
- `tools/cadctl.py`: added `patch_apply_staged(...)` wrapper over `patch_engine.apply_staged`.
- `tools/patch_engine.py`: corrected dry-run registry mapping for `create_line` to `write.entity.line`.
- `tools/validator.py`: made `--run` / `validate_target(run_dir=...)` discover patch-run post IR under `post/dwg_graph_ir.json`.
- `config/operations.v2.json`: promoted `apply.patch`, `diff.before_after`, and `validate.patch` to `implemented` with M05 evidence refs.

## Tests

- `python -m pytest tests\unit\test_m05_cli_contract.py -q` -> `3 passed`
- `python -m pytest tests\unit\test_m05_cli_contract.py tests\unit\test_patch_engine.py tests\unit\test_patch_engine_policy.py tests\unit\test_cad_diff.py tests\unit\test_validator_gates.py tests\unit\test_cadctl.py tests\unit\test_operation_registry_v2.py -q` -> `99 passed`
- `python -m pytest tests\unit\test_operation_registry_v2.py -q` -> `15 passed`
- `CADOS_LIVE=1 python -m pytest -q` -> `255 passed in 75.40s`
- `python -m unittest discover -s tests -p "test*.py"` -> `Ran 218 tests in 19.388s, OK (skipped=3)`

## Required Output

```text
[CADOS M05 RESULT]
STATUS: PASS
PATCH:
- supported_ops: create_line, create_circle, create_layer, set_layer
- staged_apply: PASS (runs/m05_patch_create_line/result.json)
- dry_run: PASS (runs/m05_patch_create_line/dry_run/dry_run_plan.json)
DIFF:
- status: PASS (+1 LINE, 0 removed, 0 modified)
- diff_ref: reports/patch_diff_latest.json
VALIDATION:
- status: PASS (14/14 gates)
- validation_ref: reports/validation_latest.json
DWG SAFETY:
- original_hash_before: 27dbf6b95ff72a89fd53b153891187365b9e8ebc4c05a97cfed307057bf49bc8
- original_hash_after: 27dbf6b95ff72a89fd53b153891187365b9e8ebc4c05a97cfed307057bf49bc8
- original_modified: no
TESTS:
- python -m pytest tests\unit\test_m05_cli_contract.py -q -> 3 passed
- python -m pytest tests\unit\test_m05_cli_contract.py tests\unit\test_patch_engine.py tests\unit\test_patch_engine_policy.py tests\unit\test_cad_diff.py tests\unit\test_validator_gates.py tests\unit\test_cadctl.py tests\unit\test_operation_registry_v2.py -q -> 99 passed
- CADOS_LIVE=1 python -m pytest -q -> 255 passed in 75.40s
- python -m unittest discover -s tests -p "test*.py" -> Ran 218 tests in 19.388s, OK (skipped=3)
BLOCKERS:
- none
NEXT:
- CADOS_M06_VISUAL_BATCH_GOLDEN_REGRESSION
[/CADOS M05 RESULT]
```
