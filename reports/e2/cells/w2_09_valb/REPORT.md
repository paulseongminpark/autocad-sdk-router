# W2-09 — val 격리 분할과 청정 incumbent

## 실행 경계

- 허용 입력 분할: `train, val`
- test 분할 읽기: `0`
- 서브에이전트 사용: `0`
- CPU 상한: `24 h`; 누적 보수 청구: `2.018484 h`
- 성공 실행 process CPU: `0.401150 h`; 실패/closeout 포함 시도 수: `2`
- val-B 실제 질의: `1`회, cohort=`retrospective_arm`
- 결과 해석 판정은 출력하지 않고 수치와 구간만 기록한다.

## 분할 설계

수리된 val 396도면을 봉인된 기하 family 정의로 묶고, salted family hash 순서에서 도면 수가 적은 쪽으로 결정적으로 배정했다. 라벨은 분할에 사용하지 않았다.

| 항목 | val-A (DEV) | val-B (ADJ) |
|---|---:|---:|
| 도면 | 198 | 198 |
| family | 198 | 198 |
| 행 | 167556 | 181544 |

- family 교차 수: `0`
- split manifest content hash: `5e16541d7191ad01c57a9cee72172f63112ed68590dd371aff5bf0aaaab8e07b`
- val-A drawing-list SHA-256: `4905890378c4dc3958bcd04876dd4e78f9c8cba0d1511b7c23117b8f12f6a6f7`
- val-B drawing-list SHA-256: `69df162feaab7012b1705e948c535c5a5dc90a4198965b9595c0c155295f45fb`

## 재적합과 선택

- 지역6: sklearn HistGBDT 기본 파라미터 1개 후보를 train에 적합하고 val-A에만 기록한 뒤, 최종 3개 seed 모델을 train+val-A로 재적합했다.
- 문맥12: 반경 `[20.0, 40.0, 80.0]`를 train→val-A 3-seed 평균 primary AUPRC로 선택; 선택 반경=`20px`; 최종 모델은 train+val-A로 재적합했다.
- F1 threshold: `0.5` (고정; val-B 선택 없음).
- val-A 최종 점수는 최종 적합 집합에 포함된 cohort의 수치다.

## A/B 수치 (3-seed 확률 평균)

| 모델 | val-A AUPRC | val-A F1 | val-B AUPRC | val-B F1 | A-B ΔAUPRC | A-B ΔF1 |
|---|---:|---:|---:|---:|---:|---:|
| clean local6 | 0.68350622 | 0.52013554 | 0.67892645 | 0.51794210 | +0.00457977 | +0.00219345 |
| clean context12 | 0.83761597 | 0.70919665 | 0.83302268 | 0.70369543 | +0.00459328 | +0.00550121 |
| legacy context12 (LEGACY-SEEN) | 0.83531369 | 0.70940819 | 0.83268077 | 0.70566217 | +0.00263292 | +0.00374602 |

## family-cluster bootstrap (10,000)

같은 cohort 안의 모델 대조는 동일 family multiplicity로 paired resampling했다. 서로 겹치지 않는 A/B 대조는 각 cohort의 family를 독립 resampling했다.

| 대조 (left-right) | ΔAUPRC | AUPRC 95% CI | ΔF1 | F1 95% CI |
|---|---:|---:|---:|---:|
| `clean_local6_A_minus_B` | +0.00457977 | [-0.00982553, +0.01887983] | +0.00219345 | [-0.01184463, +0.01594089] |
| `clean_context12_A_minus_B` | +0.00459328 | [-0.00620262, +0.01563986] | +0.00550121 | [-0.00751698, +0.01884393] |
| `legacy_context12_A_minus_B` | +0.00263292 | [-0.00822610, +0.01363081] | +0.00374602 | [-0.00896521, +0.01666047] |
| `valA_clean_context12_minus_local6` | +0.15410975 | [+0.14688169, +0.16166919] | +0.18906110 | [+0.18068219, +0.19829943] |
| `valB_clean_context12_minus_local6` | +0.15409624 | [+0.14629389, +0.16165787] | +0.18575334 | [+0.17597309, +0.19561693] |
| `valB_legacy_context12_minus_clean_context12` | -0.00034192 | [-0.00092602, +0.00025845] | +0.00196674 | [+0.00026765, +0.00363662] |

## score-only 및 장부

공개 `score-valb` 경로의 반환 키는 `primary_auprc`, `f1`, `failure_code`뿐이다. 회고 batch도 행 단위 라벨·오류를 반환하지 않았고, 모든 모델/seed 예측을 한 cohort로 묶어 장부 1행에 기록했다.

- 등록 failure code: `OK, PREDICTION_FILE_MISSING, PREDICTION_FORMAT_INVALID, SPLIT_MANIFEST_MISMATCH, ROW_COUNT_MISMATCH, NONFINITE_PREDICTION, PROBABILITY_OUT_OF_RANGE, QUERY_LIMIT_REACHED, COHORT_ALREADY_QUERIED, INTERNAL_EVALUATION_ERROR`
- ledger SHA-256: `955337d9ec48329e4f55a2ef949700fb5b8d868734d48227a368df25a324443a`

## 청정 incumbent

- artifact: `clean_incumbent.joblib`
- artifact SHA-256: `a0f37c1ab89d64773a7adbea871425a7f1bcc945e0b83ccea969e15d54ea1dcc`
- manifest content hash: `fbe7ed716f81165d1017ae695f2b142a0e89412494df5db846c0431395eddc84`
- split manifest content hash: `5e16541d7191ad01c57a9cee72172f63112ed68590dd371aff5bf0aaaab8e07b`

## selftest 전문

```text
SELFTEST_BEGIN
split_generation_repeat_count=2
split_deterministic=1
manifest_hash_first=5e16541d7191ad01c57a9cee72172f63112ed68590dd371aff5bf0aaaab8e07b
manifest_hash_second=5e16541d7191ad01c57a9cee72172f63112ed68590dd371aff5bf0aaaab8e07b
val_A_drawing_count=198
val_B_drawing_count=198
family_crossing_count=0
score_only_exact_key_contract=1
score_only_response_keys=primary_auprc,f1,failure_code
score_only_row_data_returned=0
temporary_ledger_append_ok=1
persistent_valb_ledger_unchanged=1
test_split_reads=0
subagents_used=0
honest_verdict=PASS
SELFTEST_END
```

## 산출물 해시

| 파일 | SHA-256 |
|---|---|
| `w2_09_valb.py` | `85481aa49f6cf62307588e73ea502160079f1172de8f5f927a1a7c23bb5ef1de` |
| `split_manifest.json` | `8aad64eeda77df55296fc711c21d7befdeada7fe379aeafec81fd1691aea044f` |
| `retrospective_results.json` | `8b37aa67f61ae63eb08c4d46aac5d14eebedd5be717b2ab313136713d5de68e0` |
| `clean_incumbent.joblib` | `a0f37c1ab89d64773a7adbea871425a7f1bcc945e0b83ccea969e15d54ea1dcc` |
| `clean_incumbent_manifest.json` | `7f5ee863dc0de5a657442df4970253b735dac920eabcbf85f47908e2bace7263` |
| `valb_ledger.jsonl` | `955337d9ec48329e4f55a2ef949700fb5b8d868734d48227a368df25a324443a` |
| `evidence.xlsx` | `ed110ef3c997760e753f161ebc2163fdeafc33545d18d5f339f162b5d443cebf` |

## 미해결

- 이 셀의 추가 val-B 접근: `0`회.
- 웨이브 절대 장부 상한 잔여: `11`회; 실제 개방은 후속 거버넌스 대상.
- test 소비권: `0`.

CELL_COMPLETE: w2_09