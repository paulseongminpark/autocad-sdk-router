# lens3 — replay 3판 무결·공개 완전성 (chainverify_L1d, 3차 함대)

- 좌석: lens3 (replay 3판 무결·공개 완전성)
- 대상: L1d 산출 `D:\runs\e2_program\cells\loop_l1d\` 의 v1/v2/v3 코호트 replay, REPORT 델타 표,
  replay_delta.json 공개 완전성, 소스 manifest
- 재계산 위치: `D:\runs\e2_program\chainverify_L1d\lens3_work\` (lens3_replay.py · lens3_followup.py ·
  lens3_results.json). 기존 산출물 전부 READ-ONLY 준수, loop_l1d.py 재실행 없음(산출물 덮어쓰기 방지),
  git·서브에이전트·CAD·test 접근 없음.

## 1. 방법 — 무엇이 독립이고 무엇이 공유인가

- **공유(검증 대상 그 자체)**: 세 추정기 소스 v1 `cells\feyerabend_c1\feyerabend_c1.py` ·
  v2 `cells\loop_l1c\feyerabend_c1_v2.py` · v3 `cells\loop_l1d\feyerabend_c1_v3.py`. 이들의 산술을
  같은 머신(Python 3.12.10, numpy 1.26.4)에서 재실행하는 것이 이 좌석의 정의다.
- **독립(내 코드)**: 장면 로딩·평가 하네스(버전별 신선 로드, loop_l1d의 row_integrity에 불의존),
  집계(coverage/accuracy/relerr — statistics.median 기반 자체 구현), corruption 상승 카운터,
  전(全) leaf 평탄화 diff(비트 단위, 허용오차 없음), manifest/SHA 재계산, REPORT 표 축자 대조.
- 판정 원칙: 불일치·불확실 발견 시 REFUTE. 아래 수치는 전부 lens3_work 산출물에서 인용.

## 2. R1 — replay 3판 무결 (독립 재실행 vs 저장 산출물)

2코호트 × 3판 = 6조합, 각 200장면을 내 하네스로 재평가하고 저장 rows와 장면 단위 전 필드 대조:

| 조합 | 내 rows | 저장 rows | 불일치 |
| --- | --- | --- | --- |
| c1_original_200 / v1 (`feyerabend_c1\results.json`) | 200 | 200 | 0 |
| c1_original_200 / v2 (`loop_l1c\c1v4_results.json` v1_replay) | 200 | 200 | 0 |
| c1_original_200 / v3 (`loop_l1d\c1v5_results.json`) | 200 | 200 | 0 |
| l1b_200 / v1 (`loop_l1b\c1v3_results.json`) | 200 | 200 | 0 |
| l1b_200 / v2 (`loop_l1c\c1v4_results.json`) | 200 | 200 | 0 |
| l1b_200 / v3 (`loop_l1d\c1v5_results.json`) | 200 | 200 | 0 |

전 조합 **비트 단위 일치**(부동소수 포함 dict 완전 동일). replay_delta.json에 기록된
`rows_digest` 6종도 저장 rows의 canonical SHA-256 재계산과 전부 일치. prereg의 재현성 문언
"휘발 필드 제외 수치 전 필드 동일"은 rows 층위에서 최강 형태(비트 동일)로 성립.

## 3. R2 — REPORT 델타 표 독립 재계산

내 자체 집계(추정기 aggregate 코드 불사용)로 REPORT "코호트 replay 델타 전문"을 재현:

- l1b_200: v1=v2=v3 모두 HIGH coverage 0.8 (160/200), HIGH accuracy 1.0, relerr median
  2.220446049250313e-16 / max 3.1086244689504383e-15, unit {HIGH:160, LOW:40}, status {LOW:200} — REPORT와 일치.
- c1_original_200: v1·v2 coverage 0 / accuracy null, v3 coverage 1.0 / accuracy 1.0,
  unit {HIGH:200}, status {HIGH:100, LOW:100}, relerr median 2.220446049250313e-16 /
  max 4.440892098500626e-16 — REPORT와 일치.
- per-scale(4 scale × 3판 × 2코호트): 장면 50/scale, l1b HIGH 40/scale(0.8), c1 v3 HIGH 50/scale(1.0),
  per-scale relerr median/max 전부 REPORT 수치와 일치. 봉인 밴드(HIGH coverage ≥0.60/scale,
  HIGH 정확도 ≥0.95)는 v3 c1에서 4 scale 전부 1.0/1.0으로 충족.

## 4. R3 — 26→0→0, v2의 160, invariants

내 자체 상승 카운터(after > before + 1e-15, status rank 상승)로 전 조합 × 4 corruption × 5 추적
필드를 재집계 — replay_delta.json의 corruption_upward 및 REPORT 표와 **전 셀 일치**. 핵심 수치:

| 항목 | 내 재계산 | 기록 | id 집합 대조 |
| --- | --- | --- | --- |
| C1 single_outlier status upward: v1/v2/v3 | 26/0/0 | 26/0/0 | 26개 id 완전 일치 |
| C1 single_outlier reference upward: v1/v2/v3 | 26/0/0 | 26/0/0 | 26개 id 완전 일치 |
| L1b 전 corruption 추적 상승 합: v1/v2/v3 | 0/160/0 | 0/160/0 | — |
| **v2 l1b stale_override reference_confidence** | **160** | **160** | **160개 id 완전 일치** |

- v1 진단에는 reference_confidence_score 필드 자체가 없어 null — REPORT의 null 표기와 부합.
- **"L1c 시야 밖 소급 발견" 프레이밍 검증**: `cells\loop_l1c\REPORT.md`의 C1v4 upward counts는
  `{confidence_score, reference_status, status, unit_status}` 4필드로, reference_confidence_score가
  추적 필드에 없었다. 즉 160은 L1c 당시 측정 범위 밖이었고 L1d가 소급 공개한 것이 맞다.

## 5. R4 — 공개 완전성: 전 leaf 은닉 변화 스윕

v1→v3·v2→v3 × 2코호트에서 row 전체를 leaf 단위로 평탄화해 비트 단위 diff(허용오차 0) 후,
공개 목록(수치 20 + 범주 4 필드)과 대조:

- **공개 24필드의 changed-scene 카운트**: 내 카운트가 replay_delta.json·REPORT와 허용오차 규약
  적용 시 전부 일치 (l1b: conf 40·ref_conf 200, c1: conf 200·ref_conf 200·status 100·unit 200·ref 100).
- **공개 목록 밖에서 값이 변한 leaf의 전수 분류** (은폐 후보 → 판정):
  1. *허용오차 이하 float 노이즈*: l1b confidence_score 72장면, |Δ| ≤ 5.462e-14 — 델타 산출이 선언한
     `numeric_equal`(rel 1e-12, abs 1e-15)가 거르는 범위. 합산 경로 차이의 최종 비트 요동. 실질 0.
  2. *anchor_model.status/unit_status/reference_status* (c1 100/200/100장면): 최상위 동명 공개 필드의
     행내 미러 — 변한 장면 집합이 최상위와 **완전 동일**함을 확인. 중복이지 은폐 아님.
  3. *corruption_diagnostics.\**: 버전이 바뀌었으니 가상 교란 측정치(before/after)가 달라진 것.
     행동 요약(상승 카운트+transition id)은 replay_delta에 버전·종류·필드별로 전량 공개돼 있고
     §4에서 내 재계산과 일치. 원자료도 공개 아티팩트 3종에 전량 존재. 은폐 아님.
  4. *confidence_score_bin / pair_label_permutation digest*: 공개된 score·model의 결정적 파생값.
  5. *스키마 증분*: v3 신설 경로(denominator_policy·n_candidate_* 등, v1 대비 73경로) ·
     v2 전용 경로 7종(reference_guard 계열, v3에서 소멸) — 값 비교가 성립하지 않는 구조 차이로
     "공통 필드" 공개 범위 밖이 정의상 맞다. 아티팩트에 그대로 노출돼 있음.
- **판정: replay_delta.json에 없는 실질적 은폐 변화 0.**

주의 2건 (은폐 아님, 독해 주의):
- REPORT 델타 표의 l1b confidence_score "median 1 → 1"은 `.12g` 포맷이 before median
  0.9999999999999818을 "1"로 렌더한 것. 실제로는 40장면이 0.2667→1.0으로 **상승**했다(전부 up,
  unit_status는 LOW 유지). replay_delta.json은 분포(min 0.2667→1.0)·changed id 40개를 그대로
  공개하므로 완전성은 성립하나, REPORT 표만 읽으면 방향이 안 보인다. 이 상승은 정상 장면의
  버전 간 변화로, 봉인 밴드(교란 단조성·L1b corruption 상승 0)의 규율 대상이 아니다.
- l1b anchor_model.reference_confidence_score는 200장면 전부 변화(up 40 / down 160,
  after 범위 0.0~1.0) — 역시 분포·id로 공개됨. reference_status는 {LOW:200}으로 3판 불변.
  오케스트레이터 요약 문구 "L1b 정상 수치 불변"은 coverage/accuracy/relerr/status 층위에서 참이고
  (내 재계산 일치), score 층위 변화는 REPORT 본문·replay_delta가 명시 공개한다.

## 6. R5 — 소스 manifest·산출물 SHA 재계산

- **소스 manifest**: loop_l1d가 정의한 14 read-only 파일 + 2 장면 디렉토리(각 200파일, 파일별
  SHA-256)를 내 코드로 전량 재해시·동일 canonical 구조로 digest 재계산 →
  `d3ec35395fffa168a9d0bf246ba9bbd07dcea4e4033117bd6b3dbba1286f0c16` — REPORT의 before/after
  digest와 **일치**. 저장된 manifest도 before==after, mismatch 0. 즉 run 당시의 소스가 지금도
  바이트 동일하고, run 전후로도 불변이었다.
- **산출물 SHA**: REPORT "산출물 SHA" 8종(c1v5_results, evidence, evidence_sealed,
  feyerabend_c1_v3, fleet_probe_results, loop_l1d, prereg, replay_delta) 전부 현재 파일과 일치.
- **repo↔runs 사본**: repo `tools\e2\cells\{feyerabend_c1, feyerabend_c1_v2, feyerabend_c1_v3,
  loop_l1d}.py` 4종이 runs 사본과 SHA 동일 — 함대가 리뷰한 소스와 replay가 실행한 소스가 같다.
- **c1v5 내부 기록**: estimator/original/v2 SHA 기록이 실제 파일과 일치, invariants·manifest가
  replay_delta와 동일 사본, baseline_live_integrity 4종 mismatch 0.
- **시각**: prereg 18:43:31.368Z(READ-ONLY) → sealed workbook 18:44:15.647Z(READ-ONLY) →
  estimator 19:01:22 → 산출물 19:07:35 (2026-07-18). REPORT에 기록된 mtime과 현재 파일시스템이
  틱 단위로 일치, 선후관계(봉인 선행)도 성립. (위조·역산 심층은 seat4 시야.)

## 7. R6 — selftest·600종·함대 probe 재실행

`run_selftests`를 내 프로세스에서 재실행:

- 13/13 관측, transcript가 REPORT 코드블록과 **축자 일치**.
- property 600종: seed 20260719, family counts 9종 일치, upward 0, cases digest
  `f03048a5…` 일치 (600케이스 전체의 canonical 해시이므로 케이스 단위 재현 입증).
- fleet_probe_results.json의 probes(P0·B1~B4·O1~O3·B4 정보한계)·54종 sweep·observed_metrics·
  property_600 블록이 내 재실행 결과와 **dict 단위 완전 일치**.

## 8. R7 — REPORT 전사 무결

fleet_probe_results.json·replay_delta.json에서 REPORT 표를 재렌더(fmt `.12g`·동일 직렬화)해 대조:
probe 표 36행 + corruption 상승 표 24행 + 공통 필드 델타 표 96행 = **156행 전부 REPORT에 축자
존재, 누락 0**. 표가 JSON과 다른 값을 싣는 경로 없음.

## 9. 한계 (판정에 미포함인 이유 포함)

- 같은 머신·같은 Python에서의 재현이다. 교차 플랫폼 비트 동일성은 주장하지 않는다(원 주장도
  그 주장을 하지 않음).
- 추정기 소스 자체는 공유물이다 — 이 좌석은 산술 재현·공개 완전성을 판정하며, v3 의미론의
  정당성(포화·coverage 1.0·경계 거동)은 lens1/lens2/seat4의 시야다.
- evidence.xlsx는 SHA 대조까지만(위 §6). sealed workbook 위조·역산 검증은 seat4 계약.

## 10. 종합

lens3 계약 4항목 전부 성립: ① v1/v2/v3 replay 독립 재실행 — 6조합 1,200장면 비트 단위 재현
② 델타 표 전수 대조 — 집계·상승 카운트(26→0→0, v2 l1b stale_override reference_confidence 160
포함) 수치·id 집합 일치, 160의 "L1c 시야 밖" 성격 실증 ③ 공개 완전성 — 전 leaf 스윕에서
replay_delta.json 밖 실질 은폐 변화 0 (노이즈·미러·파생·진단·스키마로 전수 분류 완료)
④ 소스 manifest·산출물 SHA·repo 사본 재계산 전부 일치. REFUTE 사유 미발견.

VERDICT: CONFIRM
