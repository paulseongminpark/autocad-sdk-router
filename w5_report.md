# Lane W5-ID

## DONE

- Added additive IR entity identity fields `stable_id` and `stable_id_ordinal` in `tools/ir_builder.py`.
- Stable hash inputs: entity kind (`dxf_name` + `geometry.kind`), `layer`, normalized geometry, normalized
  non-volatile attributes (`space`, `layout`, common display attrs when present).
- Float normalization: `1e-6`.
- Volatile exclusions: `handle`, `object_id`, `owner_handle`, `bbox`, auxiliary handle fields,
  per-entity `source`, XDATA, and viewport-managed `center`/`height`/`width`.
- Duplicate rule: identical duplicates share `stable_id`; `stable_id_ordinal` is assigned by sorting the
  duplicate set by `handle` and is only stable while that duplicate set is unchanged.
- Added matcher CLI `tools/ir_identity.py` for pre/post lineage reports.
- Bumped emitted IR version to `1.1.0` and updated the spec/schema accordingly.

## EVIDENCE

- Real pair `mcp_verdict_20260706`:
  - report: `reports/w5_mcp_verdict_identity_report.json`
  - summary: matched `21747`, added `2`, removed `0`, moved `0`, unchanged_handle `21747`
  - note: this pair preserved existing handles; only the two new verdict entities were added
- Real pair `capstone_composed_20260706` churn proof:
  - report: `reports/w5_capstone_regen_identity_report.json`
  - comparison: `census/dwg_graph_ir.json` vs `regen/post/dwg_graph_ir.json`
  - summary: matched `7`, added `0`, removed `21740`, moved `7`, unchanged_handle `0`
  - note: this is the handle-churn scenario; the seven regenerated entities were matched by stable identity,
    not by handle
- Tests:
  - focused identity/schema regressions: `20 passed, 4 skipped`
  - full unit suite: `python -X utf8 -m pytest tests/unit -q --basetemp .pytest_tmp`
    -> `1151 passed, 23 skipped, 0 failed`

## COMMITS

- `git commit` was blocked by sandbox permissions. The worktree points at
  `D:/dev/99_tools/autocad-sdk-router/.git/worktrees/w5_identity`, which is outside this lane's writable roots,
  so no commit could be created honestly.

## FILES

- `tools/ir_builder.py`
- `tools/ir_identity.py`
- `tools/cross_oracle.py`
- `schemas/dwg_graph_ir.v1.schema.json`
- `docs/DWG_GRAPH_IR_SPEC.md`
- `tests/unit/test_ir_identity.py`
- `tests/unit/test_dwg_graph_ir_schema.py`
- `reports/w5_mcp_verdict_identity_report.json`
- `reports/w5_capstone_regen_identity_report.json`
