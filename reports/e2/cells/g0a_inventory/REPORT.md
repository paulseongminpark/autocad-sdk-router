# G0-A Non-label Inventory Report

- Protocol status: `INVALID_PROTOCOL_BREACH`
- Snapshot UTC: `2026-07-18T17:13:48+00:00`
- Collection elapsed seconds: `35.094313`
- Write scope: this cell directory only; repository writes and Git commands were not used by the collector.
- Model execution, model comparison, threshold selection, and label-statistic calculation: not performed.

## Collection method

- CubiCasa: filenames and byte sizes only; drawing IDs are filename-derived and only their canonical sorted-list SHA-256 is emitted.
- Gen2: manifests are parsed; DXF/truth artifacts are hashed but their contents are not parsed.
- Family ledgers: only `family_audit` and `repaired_split_hash` values are selectively decoded from their source JSON.
- Corpora and in-flight cells: recursive filename, extension, size, report-marker, and elapsed-field census only.
- Environment: Python facts, torch import attempt, `nvidia-smi` query, bounded SSH hostname probe, and Docker image listing; no benchmark.

## Data inventory summary

| Source | Files/drawings | Total bytes | Metadata hash/status |
|---|---:|---:|---|
| CubiCasa train | 4200 | 326558595 | `7d4a0662a9e10f6570b8188a18bb464c16992b0ae875770f41e0c64c51e8ccfc` |
| CubiCasa val | 400 | 29907030 | `b38e6078cc37e17b58a83e18b78ba49a350c0083055e1d3be1e3011e85538dd6` |
| CubiCasa test | 400 | 31691693 | `0b955b7b98955fd48f4fa0b39dcc0064f856691b07ac9e942bfcf5714d13558e` |
| gen2 full pack | 150 | — | root `115fe18acaba7c474319cca86b004a7b90e5ba6d0e4dc03ec9eae44c25241c28`; mismatches 0 |
| C0 scenes | 200 | 14942202 | FOUND |
| L1 scenes | 200 | 14668510 | FOUND |

## Code landing

- `tools/e2` files hashed: 69
- gnn_trainer: `ABSENT`
- qwen_trainer: `ABSENT`
- raster_trainer: `ABSENT`
- rl_harness: `ABSENT`

## Unlabeled corpus census

- ArchCAD: FOUND; files 205504; bytes 9874167331
- FloorPlanCAD: FOUND; files 10630; bytes 454847042
- Zenodo10K: FOUND; files 1654; bytes 14260986093
- pseudo-12k: FOUND; files 22; bytes 3922945924

## Environment summary

- Python: `3.12.10`
- torch import: `True`
- RTX 5070 Ti recognized by nvidia-smi: `True`
- DGX SSH hostname probe reachable: `True`
- Docker images transcribed: 9

## NOT_FOUND

- None

## Unresolved

- protocol breach: Discovery search exposed snippets from synthetic gen2 truth JSON before collector execution; no model score, threshold, or label statistic was computed, and no collected value depends on those snippets.

## Protocol breaches

- Discovery search exposed snippets from synthetic gen2 truth JSON before collector execution; no model score, threshold, or label statistic was computed, and no collected value depends on those snippets.

CELL_INVALID: g0a
