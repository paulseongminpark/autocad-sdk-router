# CADOS V1 RC1 DWG Safety

- Generated: 2026-06-26T13:24:21.8393523+09:00
- Original DWG modified: False
- Tracked CAD status clean: True
- No write_original default: True
- Operations defaulting to write_original/original write: 0
- Staged CAD files present: 169
- Run CAD files present: 352

## Tracked CAD Files
- tests/fixtures/native_sample.dwg: unchanged_from_HEAD=False, sha256=eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76, bytes=2559361

## Known Golden Inputs
- staging\dwg_20260617_191504\input.dwg: exists=True, sha256=27dbf6b95ff72a89fd53b153891187365b9e8ebc4c05a97cfed307057bf49bc8, bytes=2524981, mtime=2026-06-17T19:15:06.0000000+09:00
- tests\fixtures\native_sample.dwg: exists=True, sha256=eac5d4b13d67d89106e503321412539df7b39b8a7f4e44c033448e9295fe3f76, bytes=2559361, mtime=2026-06-24T15:23:49.9272864+09:00

## Evidence
- python -m pytest tests -q -rs with CADOS_LIVE=1 => 566 passed, 0 skipped
- tests/integration/test_native_graph_router.py asserts golden SHA and size unchanged
- tests/smoke/test_router_inspect_database_graph.py asserts golden SHA and size unchanged
- tests/integration/test_live_arx_pump.py copies golden DWG to runs/m02_pump_test_pytest/input.dwg before live pump
