# RSI Harness Mock Selftest Report

- verdict: **PASS**
- passed: `6/6`
- canonical evidence: `D:\runs\e2_program\cells\rsi_harness\evidence.csv`
- split manifest SHA-256: `6849e85387a216e63aaf65dbe4b9c00bbe73a81e7a61bfb3015af572822fb21c`
- telemetry: `wall_seconds=2.0149749999982305, peak_rss_bytes=47517696, peak_vram_bytes=N/A(no_GPU), device=CPU, budget_charge=0.03358291666663717 CPU-min`
- GPU use: `0`; real val-A labels: `not read/not required`.

| Part | Contract | Verdict | Evidence |
|---:|---|---|---|
| 1 | Process path guard blocks RSI-private, val-B, and test reads | **PASS** | `{"blocked":["RSI-private","test","val-B"],"environment_decoys_ignored":true,"policy_sha256":"4ff9651c61d719a3747187b92a90d0f06bb9332deb7334eca57fe17c88cd8a86","process_boundary":true,"reasons":{"RSI-private":"PATH_GUARD_DENY: protected path name for read: D:\\runs\\e2_program\\cells\\rsi_harness\\private\\mock_private_labels.json","test":"PATH_GUARD_DENY: protected path name for read: D:\\runs\\e2_program\\test\\mock_test_labels.json","val-B":"PATH_GUARD_DENY: protected path name for read: D:\\runs\\e2_program\\cells\\w2_09_valb\\mock_valb_labels.npz"}}` |
| 2 | Anomalous public jump >=0.02 forces revalidation | **PASS** | `{"flags":[false,false,true],"scores":[0.5,0.515,0.535],"threshold":0.02,"triggered_at_index":2}` |
| 3 | Prediction schema/row-count/range guard rejects malformed output | **PASS** | `{"rejected_cases":{"range":"PREDICTION_OUT_OF_RANGE:0","row_count":"PREDICTION_ROW_COUNT_MISMATCH","schema":"PREDICTION_SCHEMA_ID_INVALID"}}` |
| 4 | Drawing-hash split is byte-for-byte deterministic | **PASS** | `{"first_sha256":"6849e85387a216e63aaf65dbe4b9c00bbe73a81e7a61bfb3015af572822fb21c","identical_bytes":true,"second_sha256":"6849e85387a216e63aaf65dbe4b9c00bbe73a81e7a61bfb3015af572822fb21c","source_bytes_consumed_each_run":10246,"source_file_bytes":193164,"source_section":"frozen.splits.A only","stopped_before_following_section":true}` |
| 5 | RSI-private contains at least 40 drawings | **PASS** | `{"minimum_met":true,"minimum_required":40,"private_drawing_count":60}` |
| 6 | Commit-then-evaluate rejects pre-commit evaluator entry | **PASS** | `{"budget_charge_cpu_minutes":0.25,"candidate_sha256":"d958f96ec4eaea458b1c354bc172a9dd004d72cc4a3959e08bd7ad475de5468d","config_sha256":"f8e79596ca80ec6b8a79736492ab43858286a93ecfccbd95ea80cf2e93f8c68a","device":"cpu","evaluator_calls_during_violation":0,"mock_public_decision":"keep","private_chain_rows":1,"private_released_after_completion":true,"private_unreleased_before_completion":true,"prompt_sha256":"4c6dd6c252fc2cc148f1e2631b27a02654462b91504e40b1680e6cfb3dd87b0f","public_chain_rows":4,"valid_commit_sequence":2,"valid_evaluation_sequence":3,"violation_rejected":true}` |

## M-13 gate

All six mock checks passed. The harness gate is open, but M-13 was not launched by this cell.
