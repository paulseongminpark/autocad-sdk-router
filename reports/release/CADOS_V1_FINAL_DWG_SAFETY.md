# CADOS V1 Final DWG Safety

- Generated: 2026-06-26T13:55:15.9209821+09:00
- Original DWG modified: False
- Tracked CAD status clean: True
- No write_original default: True
- Operations defaulting to write_original/original write: 0

## Tracked CAD Files
- tests/fixtures/native_sample.dwg: unchanged_from_HEAD=False, sha256=eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76, bytes=2559361

## Known Golden Inputs
- staging\dwg_20260617_191504\input.dwg: exists=False, sha256=, bytes=0, mtime=
- tests\fixtures\native_sample.dwg: exists=True, sha256=eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76, bytes=2559361, mtime=2026-06-26T13:47:15.7724613+09:00

## Evidence
- CADOS_LIVE=1 python -m pytest tests -q -rs => 566 passed, 0 skipped
- tests/integration/test_native_graph_router.py asserts golden SHA and size unchanged
- tests/smoke/test_router_inspect_database_graph.py asserts golden SHA and size unchanged
- tests/integration/test_live_arx_pump.py copies golden DWG to runs/m02_pump_test_pytest/input.dwg before live pump
