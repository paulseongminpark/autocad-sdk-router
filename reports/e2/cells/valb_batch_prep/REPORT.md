# val-B 배치 러너 구축 보고

## 완료 상태와 실행 경계

- 구축 산출물: `D:\runs\e2_program\cells\valb_batch_prep\valb_batch_runner.py`
- 합성 selftest: **PASS** (`exit 0`)
- val-A 전 팔 rehearsal: **PASS** (`exit 0`)
- val-B 실개봉 실행: **0회** — 구현만 완료했고 실행하지 않았다.
- val-B feature·라벨·도면 파일 읽기: **0 bytes**
- test 읽기: **0회**
- Git 명령: **0회**
- 서브에이전트: **0회**
- 모든 실행·입력 경로는 절대경로를 사용했다.

`--run-valb`는 amendment3 봉인과 별도 실행 승인이 모두 생기기 전에는 실행 금지다. 코드도 이 조건을 주석·문서화하고, 두 승인 환경변수가 없으면 데이터 경계 전에 fail-closed 한다. 이 구축 패킷에서는 `--selftest`와 `--rehearsal-vala`만 실행했다.

## 구현 계약

러너는 봉인 평가기 `D:\runs\e2_program\cells\w2_09_valb\w2_09_valb.py`를 수정하지 않는 독립 파일이다. 외부 prediction/logit/probability 파일 입력은 없으며, 미래 실개봉 입력은 팔별 artifact 절대경로·기대 SHA-256·seed만 담은 단일 method manifest다. 전 artifact SHA를 모두 검증한 뒤에만 역직렬화하고, 모든 예측의 공통 행 우주·유한성·범위를 검증한 뒤에만 truth 단계가 열린다.

고정 출력 top-level 키는 아래 8개뿐이다.

1. `clean`
2. `twohop`
3. `gnn`
4. `gnn_minus_clean`
5. `gnn_minus_twohop`
6. `twohop_minus_clean`
7. `clean_sentinel_ok`
8. `integrity_flags`

팔별 키는 `pooled_auprc, pooled_f1_at_05, ece10_scalar`, 대조별 키는 `delta_auprc, delta_f1, ci95_low, ci95_high, se_boot`로 고정했다. bootstrap은 동일 family multiplicity를 전 팔에 적용하는 paired family-cluster 방식, 10,000 replicates, seed 43이다. 행·도면·family·ECE bin 단위 값과 raw prediction은 출력하거나 파일에 기록하지 않는다.

청정 팔 aggregation은 artifact에 동결된 규칙을 따른다. val-A rehearsal의 protocol-matched clean triplet은 seed별 pooled metric의 산술평균이고, 미래 val-B의 실제 `clean_incumbent.joblib` bundle은 세 seed 확률 산술평균이다. 후자의 숨은 청정 score가 AUPRC `0.83302268`, F1 `0.70369543`와 각각 절대오차 `1e-6` 이내로 일치한 뒤에만 challenger를 채점·방출한다. 불일치 시 challenger와 전 대조 필드는 `null`로 유지된다.

## 합성 selftest

실행 명령:

```text
python D:\runs\e2_program\cells\valb_batch_prep\valb_batch_runner.py --selftest
```

수기 고정 truth와 세 팔·세 seed synthetic artifact를 임시로 생성해 artifact SHA 검증 → 내부 예측 재생성 → point metric/ECE → 10,000회 paired bootstrap → 고정 schema 집계 전 경로를 통과했다. 임시 fixture는 종료 시 제거됐다.

| 팔 | pooled AUPRC | pooled F1@0.5 | ECE-10 scalar |
|---|---:|---:|---:|
| clean | 0.6791666666666667 | 0.7500000000000000 | 0.37916666666666665 |
| twohop | 0.9833333333333334 | 0.8888888888888888 | 0.2833333333333334 |
| gnn | 1.0000000000000000 | 1.0000000000000000 | 0.15666666666666665 |

| 대조 | delta AUPRC | delta F1 | CI95 low | CI95 high | SE boot |
|---|---:|---:|---:|---:|---:|
| gnn_minus_clean | 0.3208333333333333 | 0.2500000000000000 | 0.0000000000000000 | 0.5089285714285714 | 0.17914696722592735 |
| gnn_minus_twohop | 0.016666666666666607 | 0.11111111111111116 | 0.0000000000000000 | 0.1071428571428571 | 0.02853878413236298 |
| twohop_minus_clean | 0.3041666666666667 | 0.13888888888888884 | 0.0000000000000000 | 0.4027777777777777 | 0.15649644252691144 |

Selftest assertions:

- `labels_read=0`: PASS
- 실제 데이터 경로 사용: 0
- 경로 인자 `D:\sealed\val-B\manifest.json` 사전 차단: PASS (`exit 2`, filesystem 접근 전)
- artifact SHA mismatch가 label 단계 전에 차단됨: PASS
- 외부 prediction 입력 부재/거부: PASS
- 고정 top-level·팔·대조 키 일치: PASS
- `clean_sentinel_ok=true`: PASS

## val-A 전 팔 rehearsal

최종 코드 바이트에 대한 실행 명령:

```text
python D:\runs\e2_program\cells\valb_batch_prep\valb_batch_runner.py --rehearsal-vala
```

동결 lineage:

- clean DEV control: `D:\runs\e2_program\cells\w2_02_twohop\models\twohop_removed_seed_{17,29,43}.joblib`
- twohop: `D:\runs\e2_program\cells\gnn_formal\ckpt\control_twohop_full_seed_{17,29,43}.joblib`
- GNN-A: `D:\runs\e2_program\cells\gnn_formal\ckpt\GNN_A_no_pretrain_seed_{17,29,43}.pt`
- split SoT: `D:\runs\e2_program\cells\w2_09_valb\split_manifest.json`, content hash `5e16541d7191ad01c57a9cee72172f63112ed68590dd371aff5bf0aaaab8e07b`
- graph config SHA-256: `56911f4633979a3fe00fd56be2d0a39ac06757ed255ed49ed18ca20ba9d4ac49`

팔별 최종 집계:

| 팔 | pooled AUPRC | pooled F1@0.5 | ECE-10 scalar |
|---|---:|---:|---:|
| clean | 0.8329182652051369 | 0.7076768244225896 | 0.007564865682138727 |
| twohop | 0.8740823342431078 | 0.7606481401105724 | 0.007834294812870441 |
| gnn | 0.9747595485618247 | 0.8699947067726992 | 0.029286547746897634 |

paired family-cluster 대조:

| 대조 | delta AUPRC | delta F1 | CI95 low | CI95 high | SE boot |
|---|---:|---:|---:|---:|---:|
| gnn_minus_clean | 0.14184128335668778 | 0.16231788235010958 | 0.13515139396653160 | 0.14874730744624215 | 0.0034637438605417356 |
| gnn_minus_twohop | 0.10067721431871690 | 0.10934656666212683 | 0.09539842446997406 | 0.10600992625247060 | 0.0027068698876921045 |
| twohop_minus_clean | 0.041164069037970874 | 0.052971315687982745 | 0.03695336660713701 | 0.045739010156633245 | 0.0022656858931419427 |

기록치 재현:

| 팔·지표 | SoT 기록치 | rehearsal | 절대차 | 허용오차 | 판정 |
|---|---:|---:|---:|---:|---|
| clean AUPRC | 0.8329182652051369 | 0.8329182652051369 | 0 | 1e-6 | PASS |
| clean F1 | 0.7076768244225898 | 0.7076768244225896 | 2.22e-16 | 1e-6 | PASS |
| twohop AUPRC | 0.8740823342431078 | 0.8740823342431078 | 0 | 1e-6 | PASS |
| twohop F1 | 0.7606481401105724 | 0.7606481401105724 | 0 | 1e-6 | PASS |
| twohop ECE-10 | 0.007834294812870441 | 0.007834294812870441 | 0 | 1e-6 | PASS |
| GNN AUPRC | 0.9747595485618247 | 0.9747595485618247 | 0 | 1e-6 | PASS |
| GNN F1 | 0.8699947067726992 | 0.8699947067726992 | 0 | 1e-6 | PASS |
| GNN ECE-10 | 0.029286547746897634 | 0.029286547746897634 | 0 | 1e-6 | PASS |

`gnn_minus_twohop`의 CI와 SE도 `gnn_formal`의 동결 paired-bootstrap 수치와 일치했다. `twohop_minus_clean`은 이 러너가 동일 seed-43 multiplicity에서 새로 계산한 사전지정 대조다. W2-02의 별도 실행과 point delta는 동일하고, bootstrap CI 끝점의 미세한 차이는 동일 난수 count matrix의 family-column 귀속 순서가 W2-02의 manifest 순서와 이 러너/gnn_formal의 정렬 family 순서로 달랐기 때문이다.

Rehearsal integrity flags:

```text
ARTIFACT_SHA256_OK
BOOTSTRAP_10000_SEED_43
COMMON_ROW_UNIVERSE_OK
EXTERNAL_PREDICTIONS_REJECTED
LABELS_READ_VALA_ONLY
OUTPUT_SCHEMA_EXACT
REPORT_TARGETS_WITHIN_1E6
```

## 무결성·환경 증거

- 봉인 평가기 SHA-256 (변경 없음): `85481aa49f6cf62307588e73ea502160079f1172de8f5f927a1a7c23bb5ef1de`
- canonical val-B ledger SHA-256 (변경 없음): `955337d9ec48329e4f55a2ef949700fb5b8d868734d48227a368df25a324443a`
- runner SHA-256: `cfcabe4b057a8f66bc410871f0b377ffe8169e2d7b9cf457cb177cac024227f8`
- Python: `3.12.10`
- NumPy: `1.26.4`
- scikit-learn: `1.9.0`
- joblib: `1.5.3`
- PyTorch: `2.11.0+cu128`
- CUDA runtime: `12.8`
- local device: `NVIDIA GeForce RTX 5070 Ti`

이 보고서의 수치는 val-A 또는 자체 합성 fixture에서만 산출했다. val-B 실데이터 수치, 행, 도면, feature, 라벨, bin 또는 prediction은 읽거나 새로 방출하지 않았다.

PREP_COMPLETE
