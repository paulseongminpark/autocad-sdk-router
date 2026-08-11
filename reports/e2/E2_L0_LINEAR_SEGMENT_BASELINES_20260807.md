상태: **RETRACTED**

# E2 L0 선형 선분 기준선 보고서 — 객체 성능 판정 철회

## 결론

이 보고서가 2026-08-07에 발표한 객체 수준 AP, PR-AUC, 정밀도, 재현율, F1과 confusion matrix는 모두 철회한다. W1/W2가 벽 레이어라는 사용자 제공 사실은 레이어 수준 양성 앵커일 뿐이다. 그런데 당시 파이프라인은 W1/W2 밖의 7,189개 선분을 전부 `non_wall` 객체 정답으로 만들었다. **7,189개는 음성 정답이 아니다.**

따라서 Rules·GBDT·GNN이 7,430개 선분에 점수를 낸 실행 사실은 남지만, 그 점수를 완전한 이진 정답과 비교한 성능 해석은 무효다. 현재 계약에서는 독립적인 객체별 양성·음성 정답과 레이어 순도·벽 완전성이 확인되기 전까지 객체 AUPRC를 `BLOCKED: LABEL_COMPLETENESS_UNKNOWN`으로 둔다.

## 철회하는 주장

다음 수치는 과거 실행을 식별하기 위한 역사 기록일 뿐, 모델 성능이나 모델 간 우열의 근거로 사용해서는 안 된다.

| arm | 철회된 AP | 철회된 PR-AUC | 철회된 TP / FP / FN / TN @ 0.5 |
|---|---:|---:|---:|
| Rules | 0.0347858913941951 | 0.033565566392345314 | 1 / 148 / 240 / 7041 |
| GBDT | 0.09120953320362332 | 0.089615549265129 | 27 / 140 / 214 / 7049 |
| GNN | 0.09020507732184094 | 0.08919834100725822 | 82 / 520 / 159 / 6669 |

위 AP·PR-AUC·confusion matrix는 모두 철회한다. `241 wall / 7,189 non-wall`이라는 이진 truth 자체가 성립하지 않으므로, 수치가 재현되더라도 과학적으로 유효해지지 않는다.

## 여전히 유효한 관측 증거

철회 사유는 AutoCAD 관측 경로나 원본 무결성 실패가 아니라 라벨 의미의 과잉 확장이다. 다음 사실은 성능 주장과 분리해 관측·계보 증거로 남긴다.

- 원본 DWG `D:\runs\e2_program\l0_gold_1dwg\l0_gold.dwg`의 SHA-256은 `14eb65eb292d8a07f38ab5662dcafe9761c6185bc5ff0c8a9a008be15b598961`였고, 실행 전후 동일했다.
- WorldIR 선형 후보는 9,351개, 네이티브 표시 선형 후보는 7,512개, 두 경로의 안정 ID 교집합은 7,430개였다.
- W1/W2에 속한 표시 선분 241개가 모델 입력 모집단까지 보존된 것은 관측 경로 회복 증거다.
- WorldIR-only 1,921개와 native-only 82개는 모델 실행 전에 격리됐다. 이 불일치는 별도의 계측 범위 문제이며 객체 라벨을 제공하지 않는다.
- Rules·GBDT·GNN은 같은 7,430개 안정 ID에 점수를 반환했다. 이는 실행·커버리지 증거이지 정확도 증거가 아니다.

## 현재의 올바른 라벨 계약

현재 교정 도면에서 사용하는 정보는 다음처럼 제한한다.

- W1/W2 소속 선분: `layer_anchor=POSITIVE_UNLABELED`, `object_label=UNKNOWN`
- 그 밖의 선분: `layer_anchor=UNKNOWN`, `object_label=UNKNOWN`
- 알려진 객체 양성 gold: 0개
- 알려진 객체 음성 gold: 0개
- 객체 수준 AP·PR-AUC·confusion matrix: `BLOCKED: LABEL_COMPLETENESS_UNKNOWN`

이 계약은 “벽 레이어와 관련된 양성 단서가 있다”와 “각 객체가 벽이다”를 분리한다. W1/W2 내부의 보조선·기호 가능성과 W1/W2 밖의 다른 벽 가능성을 모두 열어 둔다.

## 성능 평가를 다시 허용하는 조건

객체 성능 평가는 다음 네 조건을 모두 만족한 새 정답 묶음에서만 재개한다.

1. 각 평가 객체에 독립적으로 판정한 `wall` 또는 `non_wall` 정답이 있다.
2. W1/W2 내부 순도와 W1/W2 밖 벽의 존재를 별도로 감사한다.
3. 모델·규칙·임계값·입력 해시를 정답 공개 전에 동결한다.
4. 같은 객체 집합을 모든 모델 팔이 소비하고, 평가기는 원시 정답과 예측에서 지표를 다시 계산한다.

그 전까지 보고할 수 있는 것은 W1/W2 레이어 발견 순위, 알려진 레이어 앵커의 입력 보존율, 모델 점수 분포, 기권률, 개입 안정성과 하류 구조 일관성이다. 이것들을 객체 정확도로 바꾸어 말하지 않는다.

## 역사 아티팩트

아래 파일은 철회된 2026-08-07 실행을 재현하고 오류 원인을 추적하기 위한 역사 증거로만 보존한다.

- population receipt: `D:\runs\e2_program\l0_detector_baseline\population_20260807_v2\detector_population_receipt.json`
- model receipt: `D:\runs\e2_program\l0_detector_baseline\baselines_20260807_v2\model_arm_receipt.json`
- metrics: `D:\runs\e2_program\l0_detector_baseline\baselines_20260807_v2\segment_metrics.json`
- predictions: `D:\runs\e2_program\l0_detector_baseline\baselines_20260807_v2\baseline_predictions.json`

이 파일들의 해시와 수치는 과거 코드가 무엇을 계산했는지를 증명한다. 그러나 잘못된 음성 라벨 가정을 정당화하지 않으며, 현재 기준선이나 배포 성능으로 승격할 수 없다.
