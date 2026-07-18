# CML 문맥특징 확장 — 실행 보고서

- 실행 시각: 2026-07-18T23:54:50+09:00
- 범위: 기존 6특징 + 도면 단위 이름 비사용 문맥특징, train 학습 → val 평가
- test 접근: 없음(코드가 `train`/`val` 외 split을 거부)
- seed: 7

## 결론

문맥 모델의 val F1은 **0.705367**, 6특징 기준선은 **0.517261**로 Δ_main=+0.188106이다. 판정 band는 **SUPPORT**이며 셔플 대조군은 AUC=0.332029로 **PASS**다.

Occam 판정: **FIXED_CONTEXT_AGGREGATES_REACH_SUPPORT_BAND**.

## val 실측

| 모델 | P@0.5 | R@0.5 | F1@0.5 | ROC-AUC | fit s | val infer s |
|---|---:|---:|---:|---:|---:|---:|
| HistGBDT 6특징 | 0.859644 | 0.369926 | 0.517261 | 0.921456 | 6.797 | 0.232 |
| HistGBDT + 문맥 6종 | 0.824077 | 0.616551 | 0.705367 | 0.967050 | 7.598 | 0.260 |
| 문맥 모델 label shuffle | 0.000000 | 0.000000 | 0.000000 | 0.332029 | 1.602 | 0.036 |

행 수: train 3,862,317, val 353,953; 양성률 train 0.114550, val 0.115117.

## R 튜닝(val 전용)

선택 R=20px (240mm). 선택 규칙: max val F1 at threshold 0.5; tie ROC-AUC; tie smaller R.

| R px | R mm | tune-val F1 | tune-val AUC |
|---:|---:|---:|---:|
| 20 | 240 | 0.700393 | 0.966101 |
| 40 | 480 | 0.689707 | 0.964924 |
| 80 | 960 | 0.675017 | 0.962486 |

## 문맥특징 정의

1. 동결 thickness 대역 안의 평행 이웃 수.
2. overlap 조건을 만족하는 최근접 평행 이웃 gap(px, 없으면 NaN).
3. 선택 반경의 midpoint 선분 밀도(count/πR²).
4. crossing/endpoint/T-junction을 합친 uncapped 정션 차수.
5. 도면 내 선분 길이 경험 백분위.
6. 선택 반경 이웃의 12-bin 각도 히스토그램 정규화 엔트로피.

raw 좌표, handle 문자열, 파일 순번, layer/name은 특징행렬에 넣지 않았다.

## CPU 처리율

소표본 선행 실측: 24개 train 도면, 23,423행을 4.226s에 처리 (5,543.1행/s). 이 선형 외삽의 train 전량 예상은 696.8s (0.1935h)였다.

전량 실측: train 620.829s (6,221.2행/s), val 55.928s (6,328.7행/s). 모든 도면의 base/context 행 정렬 검사는 PASS다.

## 특징 중요도 상위 10

val 100,000행에서 특징별 3회 permutation 후 ROC-AUC 감소 평균이다.

| 순위 | 특징 | 평균 AUC 감소 | 표준편차 |
|---:|---|---:|---:|
| 1 | junction_degree | 0.08615633 | 0.00070563 |
| 2 | nearest_parallel_gap_px | 0.07414748 | 0.00054394 |
| 3 | log10_len | 0.04919182 | 0.00069392 |
| 4 | drawing_length_percentile | 0.03126744 | 0.00027952 |
| 5 | neighbor_angle_entropy_r20 | 0.02750143 | 0.00000486 |
| 6 | sin2t | 0.02231679 | 0.00014622 |
| 7 | radius_density_r20_per_px2 | 0.02141668 | 0.00044266 |
| 8 | parallel_band_neighbor_count | 0.00923019 | 0.00004643 |
| 9 | parallel | 0.00627602 | 0.00008819 |
| 10 | cos2t | 0.00399968 | 0.00011914 |

## 해석 제한

이 셀의 Δ_main은 packet이 요구한 6특징 HistGBDT 대비 고정 문맥 집계의 val 이득이다. GraphSAGE FullEdge−NoMessage의 Δ_context나 test 일반화로 확대하지 않는다. val은 R 선택에 사용됐으므로 최종 held-out 주장도 하지 않는다.

CELL_BLOCKED: evidence.xlsx requires unavailable @oai/artifact-tool runtime
