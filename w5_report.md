# Lane W5-HYG Report

DONE

- contradictions found: 27
- flipped: 27
- remains-gated: 0
- hard exclusion verified: `automate.property.set` still `catalogued_not_runnable`

EVIDENCE

- `reports/lane_i_router_fix_resolution.json`: measured Lane I router-fix re-probe source for all 27 flips.
- `python tools/crash34_host_crosscheck.py`: regenerated `reports/crash34_host_eligibility_crosscheck.{json,md}` with `resolved_by_router_fix: 33` and `expected_crash: 1`.
- `python -c "import json; json.load(open('config/operations.v2.json',encoding='utf-8-sig'))"`: parse OK.
- `python tools/cadctl_cli.py registry coverage`: `"consistent": true`, `wired_count: 465`, `operation_count: 525`.
- `python -m pytest tests/unit -q`: `1143 passed, 23 skipped, 0 failed`.

COMMITS

- `a9d1eb7` `Lane W5: checkpoint contradiction scope`
- `ca0d89b` `Lane W5: reconcile router-fix registry hygiene`

FILES

- `config/operations.v2.json`
- `reports/crash34_host_eligibility_crosscheck.json`
- `reports/crash34_host_eligibility_crosscheck.md`
- `tests/unit/test_op_dag_generate.py`
- `build_log.md`
- `w5_report.md`
