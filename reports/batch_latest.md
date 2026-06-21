# Batch Latest

Updated: 2026-06-22T05:22:29+09:00
Status: `PASS`
Manifest: `runs\m06_visual_batch_golden\batch_manifest.json`

## Results

- `m03_native_full_ir`: `PASS` (ir_validate, 150.562 ms)
- `m05_patch_pre_ir`: `PASS` (ir_validate, 156.258 ms)
- `m05_patch_post_ir`: `PASS` (ir_validate, 177.223 ms)
- `golden_staging_dwg_readonly_inspect`: `PASS` (dwg_inspect_validate, 12965.086 ms)

## Summary

- successes: `4`
- failures: `0`
- quarantine entries: `0`

The DWG fixture batch item used `staging/dwg_20260617_191504/input.dwg` as a read-only staging fixture and wrote outputs under `runs/m06_visual_batch_golden/batch/`.
