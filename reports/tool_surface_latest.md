# Tool Surface Latest

- status: PASS
- cadctl commands: status --json, inspect --include-rich, query, get-entity, validate, registry list, registry coverage, registry explain, patch dry-run, patch apply-staged, diff --before/--after, visual, live status
- router explain: PASS (`inspect.database.graph`)
- get-entity evidence: handle `11935`, row_count 1
- M05 patch apply-staged: PASS (`runs/m05_patch_create_line/result.json`)
- M05 diff: PASS (`runs/m05_diff_check/cad_diff.json`)
- M05 validator --run: PASS (`reports/validation_latest.json`)
