# W3 C-3 RSI Harness Landing Report

> 본 보고의 탐지기 사다리·모든 val-A/val-B 수치의 유효 범위는 CubiCasa SEG-IR 우주 한정이다. E1 실무 도면 전이는 미검증이다.

- verdict: **PASS** (6/6 mock selftests)
- PREREG_local.json SHA-256: `89968e14ccea9a19eacb1051daf5c6f6d13715192248b74a9e7f2104d24f0476`
- PREREG.csv SHA-256 (canonical evidence prereg): `b5f1f4c049f5bc6c821425bfa2df932617a2bd46b24bd77e38b276a886a771bd`
- telemetry: `wall_seconds=2.0149749999982305, peak_rss_bytes=47517696, peak_vram_bytes=N/A(no_GPU), device=CPU, budget_charge=0.03358291666663717 CPU-min`
- execution boundary: CPU only; GPU calls 0; real val-A label reads 0; val-B/test section reads 0.
- scope: harness build plus mock selftest only. M-13 was **NOT LAUNCHED**.

## Landing

- Deterministic drawing-hash manifest: `D:\runs\e2_program\cells\rsi_harness\rsi_split_manifest.json`
- Manifest SHA-256: `6849e85387a216e63aaf65dbe4b9c00bbe73a81e7a61bfb3015af572822fb21c`
- RSI-public drawings: `138`
- RSI-private drawings: `60` (required minimum: 40)
- Source reader is unbuffered and stops on the closing brace of `frozen.splits.A`; it never reads the following val-B or any test section.
- Candidate authorization is an isolated process plus a canonical absolute-path allowlist; environment variables provide no authority.
- Public and private JSONL ledgers are append-only and independently chained by `previous_row_sha256`/`row_sha256`.
- Candidate cost is recorded per selected device with CPU <=120 min, RTX <=20 min, and 1 RTX-min = 6 CPU-min.
- The path, anomalous-jump, and prediction-schema guards are implemented and exercised.
- The proposer prompt/config remain orchestrator-owned placeholders; resolved calls are hash-sealed and checked against measured model/decoding values on every call.
- Candidate code SHA must be committed to the public ledger before prediction validation or evaluator entry.

## Launch gate

M-13 launch is permitted by this cell only when all six mock selftests PASS. This report does not itself launch M-13.

## Canonical evidence and artifacts

- canonical evidence CSV: `D:\runs\e2_program\cells\rsi_harness\evidence.csv`
- detailed selftest report: `D:\runs\e2_program\cells\rsi_harness\SELFTEST_REPORT.md`
- complete hash list (including both reports): `D:\runs\e2_program\cells\rsi_harness\SHA256SUMS.txt`

| Absolute path | SHA-256 |
|---|---|
| `D:\runs\e2_program\cells\rsi_harness\PREREG_local.json` | `89968e14ccea9a19eacb1051daf5c6f6d13715192248b74a9e7f2104d24f0476` |
| `D:\runs\e2_program\cells\rsi_harness\PREREG.csv` | `b5f1f4c049f5bc6c821425bfa2df932617a2bd46b24bd77e38b276a886a771bd` |
| `D:\runs\e2_program\cells\rsi_harness\rsi_harness.py` | `ac4df5c9acdeb7690d50becb1a245adf2c363a4259df139e54f07f06213db9d1` |
| `D:\runs\e2_program\cells\rsi_harness\selftest_rsi_harness.py` | `c9b963c87ec596cff4202bfe25322be64fcf839bebb03c63a69d369eb464c552` |
| `D:\runs\e2_program\cells\rsi_harness\rsi_split_manifest.json` | `6849e85387a216e63aaf65dbe4b9c00bbe73a81e7a61bfb3015af572822fb21c` |
| `D:\runs\e2_program\cells\rsi_harness\rsi_split_manifest.sha256` | `bf236b647854409c8c5bf3b8397a4c004b293dda291f7fd6c481878e41065671` |
| `D:\runs\e2_program\cells\rsi_harness\rsi_split_manifest.schema.json` | `86568350a72a91f25c39225dba6a6ab920eb51c6f2d35594eecc10076278d276` |
| `D:\runs\e2_program\cells\rsi_harness\candidate_prediction.schema.json` | `8ab1c6f4db9788abaad2768df7bf0064c870ea7793635a925ad34dc0eaa4850d` |
| `D:\runs\e2_program\cells\rsi_harness\candidate_guard_policy.json` | `4ff9651c61d719a3747187b92a90d0f06bb9332deb7334eca57fe17c88cd8a86` |
| `D:\runs\e2_program\cells\rsi_harness\ledger_row.schema.json` | `9b8eb1bd53a8f2aef1c7318f1785ddcb10a96c2ce900a35dda7d805261b56583` |
| `D:\runs\e2_program\cells\rsi_harness\proposer_prompt_template.txt` | `e51f9fdf72e3ecd529b1788f855466593afd008b5844b6599a75b40436497bda` |
| `D:\runs\e2_program\cells\rsi_harness\proposer_prompt_template.schema.json` | `bb9add606a4c29a55f4323a8908734e06554f7c381054d8faaa1017ae2176858` |
| `D:\runs\e2_program\cells\rsi_harness\proposer_config.placeholder.json` | `43fefdf848a44fe9a1c608603ae251759f0aad256834cfb2a67f8c8f8a370a1b` |
| `D:\runs\e2_program\cells\rsi_harness\proposer_config.schema.json` | `26bb166d6b92e38ac2bf471d1401448f857acfe242e1ac3b3bd1faddf38c5855` |
| `D:\runs\e2_program\cells\rsi_harness\public_ledger.jsonl` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `D:\runs\e2_program\cells\rsi_harness\private\private_ledger.jsonl` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `D:\runs\e2_program\cells\rsi_harness\evidence.csv` | `07f7772f21b9ded3f2423615cc3c453f9ba33ca862c513684601eeba1bd6b3ff` |
| `D:\runs\e2_program\cells\rsi_harness\measurement.json` | `3e67aabffb658a5c257e4256fe2ef802e3311da4ce5879dcfb3e9991f91ad9c8` |
