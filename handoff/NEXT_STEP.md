# NEXT STEP - CAD OS Wave4X FINAL B

Status: PASS

1. Merge `cados/wave4x-final-b-skipped-test-execution` with the final integration branch.
2. Keep `CADOS_LIVE=1` for release-candidate validation when rerunning the full suite.
3. Preserve `runs/m02_cadctl_rich/` and the generated native graph run as golden evidence for future smoke/unit reuse.
4. Do not reintroduce the stale timestamped native graph fixture path; resolve via `runs/m02_cadctl_rich/cad_result.json -> result_ref`.
