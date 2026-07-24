# val-B 배치 러너 실전 회계 결합 수리 보고

## 완료 판정과 경계

- 수리 대상: `D:\runs\e2_program\cells\valb_batch_prep\valb_batch_runner.py`
- 수리 전 SHA-256: `cfcabe4b057a8f66bc410871f0b377ffe8169e2d7b9cf457cb177cac024227f8`
- 수리 후 SHA-256: `e9edba8b20ed772633f1afa5ecbfc811b28167782795a7611398bf85646b12e9`
- 합성 selftest: **PASS** (`exit 0`)
- val-A 전 팔 rehearsal: **PASS** (`exit 0`)
- `--run-valb`: **실행 0회**
- val-B feature·label·도면 데이터 읽기: **0 bytes**
- canonical ledger 변경: **0 bytes**
- 봉인 평가기 변경: **없음**
- Git 명령: **0회**
- 서브에이전트: **0회**

이번 패킷은 실행기를 수리하고 합성/val-A 경로만 검증했다. canonical amendment3 파일
`D:\dev\99_tools\autocad-sdk-router\reports\e2\prereg_r2_v1_amendment3.json`은 현재 존재하지 않으며,
새 amendment3 봉인과 별도 실행 승인 전까지 production은 의도대로 fail-closed다.

## 수리 diff 요지

1. **신뢰 런처 실물 검증**
   - `E2_VALB_AMENDMENT3_PATH`가 위 canonical 절대경로와 일치하는지 확인한다.
   - amendment3 실제 파일 SHA-256을 `E2_VALB_AMENDMENT3_SHA256`과 byte-for-byte 대조한다.
   - parent `D:\dev\99_tools\autocad-sdk-router\reports\e2\prereg_r2_v1.json` 실제 SHA-256을
     고정값 `fc93dad9232cfd877802c1d53996357eccc710daff8cfb2cf7c865bf7f78bcd2` 및 amendment3 필드와
     모두 대조한다.
   - `E2_VALB_WAVE_ID`, amendment3 top-level `wave_id`, launch binding `wave_id`를 삼중 대조한다.
   - runner/evaluator/output-schema/method-manifest/cohort SHA, canonical ledger 절대경로,
     previous-ledger SHA, ordinary batch count `0`, series count, full method-ID tuple,
     one-shot nonce SHA를 launch binding에 강제한다.
   - authorization 뒤 파일 교체를 막기 위해 같은 파일들을 ledger lock 안에서 다시 해시한다.

2. **canonical ledger 단일 트랜잭션**
   - Windows `msvcrt.locking`으로 ledger의 첫 `2,147,483,647` bytes를 비차단 배타 잠금한다.
   - 같은 잠금 안에서 UTF-8 JSONL/query-index 연속성, 실제 previous-ledger SHA,
     동일 wave ordinary batch 사용량 `0`, cohort 유일성, nonce 미사용을 먼저 검사한다.
   - 잠금을 feature/geometry open 전부터 최종 append/fsync까지 유지한다.
   - 성공과 실패 모두 정확히 한 JSONL 행을 단일 `os.write`로 append한다. 행에는 `wave_id`,
     `query_index`, `series_count`, full `method_ids`, `features_read`, `labels_read`,
     prediction-bundle SHA, response/failure SHA, previous-ledger SHA가 포함된다.

3. **one-shot과 실패 의미론**
   - production roster는 actual clean incumbent 1 bundle + 2-hop 3 seeds + GNN-A 3 seeds로 고정하고,
     method/seed `series_count=9`를 검증한다.
   - model artifact SHA를 역직렬화 전에 확인하고, full method-ID tuple의 split/code/resolver/
     calibration/aggregation/adapter/evaluator/environment/output-schema 구성요소를 봉인값과 대조한다.
   - 내부 prediction bundle은 외부 반출 없이 경계 안에서 SHA-256만 계산한 뒤 truth 단계로 간다.
   - 첫 val-B feature/geometry open부터 접촉 상태를 보수적으로 `features_read=1`로 기록하며,
     이후 어떤 실패도 ledger 실패 행을 남긴 뒤 `GOVERNANCE_STOP` (`exit 3`)으로 종료한다.
     자동 재시도 코드는 없다.

4. **selftest 확장**
   - 임시 absolute mock prereg, method manifest, amendment3, ledger만 사용해 실제 launch-binding 검증을 통과시켰다.
   - mock ledger에서 성공 행, 접촉 전 실패 행, 접촉 후 실패 행을 각각 검증했다.
   - previous SHA mismatch, ordinary batch 재사용, cohort 재사용, nonce 재사용을 각각 차단했다.
   - mock 행의 `features_read/labels_read=1`은 회계 상태 전이를 시험하기 위한 논리 시뮬레이션이며,
     실제 val-B 파일 읽기는 없었다. selftest 실제 label-read 카운터는 `0`이다.

## 봉인 대상 식별자

| 항목 | 값 |
|---|---|
| runner SHA-256 | `e9edba8b20ed772633f1afa5ecbfc811b28167782795a7611398bf85646b12e9` |
| output schema SHA-256 | `f7a7395649971ed10b5cf4ea4d2483188d1cde0b305e9623c8b0f2c77ea2a9b0` |
| launch binding schema | `e2.valb_batch.launch_binding.v1` |
| production ledger schema | `e2.valb_batch.production_ledger.v1` |
| parent prereg_r2 SHA-256 | `fc93dad9232cfd877802c1d53996357eccc710daff8cfb2cf7c865bf7f78bcd2` |
| sealed evaluator SHA-256 | `85481aa49f6cf62307588e73ea502160079f1172de8f5f927a1a7c23bb5ef1de` |
| canonical ledger pre-hash | `955337d9ec48329e4f55a2ef949700fb5b8d868734d48227a368df25a324443a` |
| production series count | `9` |

미래 production 실행에는 `E2_VALB_EXECUTION_APPROVAL=SEPARATELY_APPROVED`,
`E2_VALB_AMENDMENT3_PATH`, `E2_VALB_AMENDMENT3_SHA256`, `E2_VALB_WAVE_ID`,
`E2_VALB_ONESHOT_NONCE`가 모두 필요하다. nonce는 64자리 소문자 hex 원문이며 amendment3에는
그 SHA-256을 봉인한다. 이 환경변수들의 형식만으로는 승인되지 않고 위 실물 대조 전건이 통과해야 한다.

## 합성 selftest 재실행

실행 명령:

```text
python -B D:\runs\e2_program\cells\valb_batch_prep\valb_batch_runner.py --selftest
```

결과: **PASS**, `exit 0`, stderr 없음.

| 팔 | pooled AUPRC | pooled F1@0.5 | ECE-10 scalar |
|---|---:|---:|---:|
| clean | 0.6791666666666667 | 0.7500000000000000 | 0.37916666666666665 |
| twohop | 0.9833333333333334 | 0.8888888888888888 | 0.2833333333333334 |
| gnn | 1.0000000000000000 | 1.0000000000000000 | 0.15666666666666665 |

추가 PASS 플래그: `AMENDMENT_FILE_PARENT_WAVE_BINDING_OK`,
`EXCLUSIVE_MOCK_LEDGER_TRANSACTION_OK`, `FAILURE_ROW_APPEND_OK`,
`GOVERNANCE_STOP_AFTER_CONTACT_OK`, `ONE_SHOT_NONCE_PRECHECK_OK`,
`ORDINARY_BATCH_ZERO_PRECHECK_OK`, `PREVIOUS_LEDGER_SHA256_PRECHECK_OK`,
`CANONICAL_LEDGER_SHA256_UNCHANGED`, `LABELS_READ_0`, `MOCK_LEDGER_ONLY`.

## val-A 전 팔 rehearsal 재실행

실행 명령:

```text
python -B D:\runs\e2_program\cells\valb_batch_prep\valb_batch_runner.py --rehearsal-vala
```

결과: **PASS**, `exit 0`, stderr 없음, `clean_sentinel_ok=true`.

| 팔 | pooled AUPRC | pooled F1@0.5 | ECE-10 scalar |
|---|---:|---:|---:|
| clean | 0.8329182652051369 | 0.7076768244225896 | 0.007564865682138727 |
| twohop | 0.8740823342431078 | 0.7606481401105724 | 0.007834294812870441 |
| gnn | 0.9747595485618247 | 0.8699947067726992 | 0.029286547746897634 |

| 대조 | delta AUPRC | delta F1 | CI95 low | CI95 high | SE boot |
|---|---:|---:|---:|---:|---:|
| gnn_minus_clean | 0.14184128335668778 | 0.16231788235010958 | 0.13515139396653160 | 0.14874730744624215 | 0.0034637438605417356 |
| gnn_minus_twohop | 0.10067721431871690 | 0.10934656666212683 | 0.09539842446997406 | 0.10600992625247060 | 0.0027068698876921045 |
| twohop_minus_clean | 0.041164069037970874 | 0.052971315687982745 | 0.03695336660713701 | 0.045739010156633245 | 0.0022656858931419427 |

### 기록 수치 재현표

| 팔·지표 | SoT 기록치 | 수리 후 rehearsal | 절대차 | 허용오차 | 판정 |
|---|---:|---:|---:|---:|---|
| clean AUPRC | 0.8329182652051369 | 0.8329182652051369 | 0 | 1e-6 | PASS |
| clean F1 | 0.7076768244225898 | 0.7076768244225896 | 2.22e-16 | 1e-6 | PASS |
| twohop AUPRC | 0.8740823342431078 | 0.8740823342431078 | 0 | 1e-6 | PASS |
| twohop F1 | 0.7606481401105724 | 0.7606481401105724 | 0 | 1e-6 | PASS |
| twohop ECE-10 | 0.007834294812870441 | 0.007834294812870441 | 0 | 1e-6 | PASS |
| GNN AUPRC | 0.9747595485618247 | 0.9747595485618247 | 0 | 1e-6 | PASS |
| GNN F1 | 0.8699947067726992 | 0.8699947067726992 | 0 | 1e-6 | PASS |
| GNN ECE-10 | 0.029286547746897634 | 0.029286547746897634 | 0 | 1e-6 | PASS |

## 텔레메트리

최종 runner bytes에 대해 PowerShell `System.Diagnostics.Process`로 stdout/stderr를 메모리에 유지한 채 측정했다.

| 모드 | exit | wall_seconds | peak_rss_bytes | device |
|---|---:|---:|---:|---|
| `--selftest` | 0 | 5.314412 | 747806720 | CPU synthetic path |
| `--rehearsal-vala` | 0 | 184.262021 | 1754562560 | NVIDIA GeForce RTX 5070 Ti |

환경: Python `3.12.10`, NumPy `1.26.4`, scikit-learn `1.9.0`, joblib `1.5.3`,
PyTorch `2.11.0+cu128`, CUDA runtime `12.8`.

## canonical ledger 불변 증명

대상: `D:\runs\e2_program\cells\w2_09_valb\valb_ledger.jsonl` (`565` bytes).
내용을 파싱하거나 표시하지 않고 SHA-256만 전후 산출했다.

| 시점 | SHA-256 |
|---|---|
| 수리 전 | `955337d9ec48329e4f55a2ef949700fb5b8d868734d48227a368df25a324443a` |
| 확장 selftest 후 | `955337d9ec48329e4f55a2ef949700fb5b8d868734d48227a368df25a324443a` |
| 최종 val-A rehearsal 후 | `955337d9ec48329e4f55a2ef949700fb5b8d868734d48227a368df25a324443a` |

따라서 canonical ledger 바이트는 불변이다. 모든 ledger append 시험은 종료 시 삭제된 임시 mock ledger에서만 수행했다.

REPAIR_COMPLETE
