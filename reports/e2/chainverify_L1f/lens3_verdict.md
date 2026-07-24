# lens3 verdict — 5차 사슬 검증 L1f Phase B (c1v7) · 회계/replay 완전성/술어 진본성

- **판정: CONFIRM**
- 좌석: lens3 (fable 좌석 3, 시야 = 장부)
- 일시: 2026-07-19 · 작업 디렉토리: `D:\runs\e2_program\chainverify_L1f\lens3_work\`
- 기본 자세는 REFUTE 시도였다. 아래의 모든 재계산은 그 자세로 수행되었고, **장부의 어떤 숫자도 재구성에 실패하지 않았다.**

## 판정 요약

REPORT.md가 주장하는 모든 카운트·비율·해시를 원시 JSON 아티팩트에서 독립 재구성했다.
**수치 불일치: 0건.** (불일치 목록 = §7, 명기: 0)

REFUTE 시 요구되는 결함 class 구분(기존 회귀/신규)은 **해당 없음** — 실증된 봉인 조문 위반이 없다.
단, 판정을 저해하지 않는 비수치 관찰 5건(§8)과 lens1/합성 좌석에 넘기는 교차확인 플래그 1건(§8-N4)을 기록한다.

## 1. 봉인 불변 (표적 1) — PASS

세 봉인 파일의 SHA-256을 직접 재계산해 인용값과 대조했다. 산출: `s1_seals.py` → `s1_seals_out.json`.

| 파일 | 재계산 SHA-256 | task.md 인용 | REPORT.md 인용 | SEAL_MANIFEST 내부 기록 |
|---|---|---|---|---|
| `prereg.json` | `76AC2A58…BDEB207861` | 일치 | 일치 | 일치 |
| `PREREG_SEALED.csv` | `94356AF8…4F4B19A8F266` | 일치 | 일치 | 일치 |
| `SEAL_MANIFEST.txt` | `2C16BA1E…2E077F92501` | (task.md 미인용) | 일치 | (자기 자신) |

- task.md는 봉인 해시 2건(prereg·CSV)+git 증인 커밋을 인용하고, 셋째 해시(SEAL_MANIFEST)는 REPORT.md와 `c1v7_results.json`의 seal 블록에 있다. 세 파일 모두 재계산 일치.
- CSV 내용 동치(봉인 조문 `seal_governance.sealed_tabular_artifact.content_equivalence`): CSV는 정확히 2행 — `runtime_reason` 1건 + `canonical_prereg_json` 1건이며, **내장 JSON을 파싱한 객체가 `prereg.json` 파싱 객체와 완전 동일**(`json_record_equals_prereg: true`).
- Phase B가 봉인을 건드리지 않았다는 주장은 파일 수준에서 확증된다. (git 증인 커밋 `c896068` 검증은 패킷상 seat4 소관 — §9)

## 2. replay 완전성 (표적 2) — PASS, 표본 아닌 전수

`replay_delta.json`(228MB)을 스트리밍 파서로 전수 감사했다. 산출: `s2_replay_audit.py` → `s2_replay_totals.json`, 장면별 `s2_scene_summary.jsonl`.

- **행 수 218,469 = 실재**. 두 독립 방법 일치:
  ① 스트리밍 파싱 행 카운트 218,469 (`rows_transcript`),
  ② 키 문자열 `"v1_to_v4_equal"` 정확 카운트 218,469 (경계 중복 보정 후; 초기 218,470은 내 청크 경계 이중계산 버그였고 보정 후 정확 일치).
- **산식(장면×필드 전개) 독립 재구성**: 각 장면의 v1/v4/v5 출력 객체 3개에서 JSON 경로(`$/a/b/0` 문법)의 합집합을 내가 다시 전개 → 400장면 전부에서 **전개 집합 == 기록된 행 집합** (누락 0, 잉여 0, `expansion_reconstruction_exact: true`). 장면별 `field_row_count` == 행 수 == 내 전개 수, 400/400.
- 코호트 소계: c1_original 200장면 102,800행 + l1b 200장면 115,669행 = 218,469 ✓ (코호트 헤더 값과도 일치).
- **zero-delta 32,538 회계**: 기록 불리언 기준 32,538 **그리고** 내 독립 재계산(노드-국소 동등성) 기준 32,538 — 동수. (c1_original 14,700 + l1b 17,838)
- **v1/v4/v5 3판 델타 행마다 실림**: 218,469행 전수에서 세 버전 기술자(present/kind/size) + 세 동등 플래그 + 세 numeric delta 필드 모두 존재 (`rows_missing_version_descriptor: 0`).
- 행 내용 재계산(전수): present/kind/size 불일치 0 · 동등 플래그 불일치 0 · 동등 플래그 추이성 위반 0 · numeric delta 값 불일치 0 (부호 규약 = 뒤판−앞판, 판별 표 12,322표 만장일치) · `relative_error` 재계산 400/400 일치.
- 다이제스트: 장면당 4개(입력 장면 + v1/v4/v5) × 400 = **1,600개 전부** `sha256(json.dumps(obj, sort_keys=True, separators=(',',':')))` 재계산 일치.
- 봉인 조문 대조: `sealed_bands.cohort_replay_delta_disclosure` — "full_unabridged_per_scene_per_field_delta_transcript", "zero_delta_rows_must_be_included", 코호트 l1b 200/c1_original 200 — 전부 실측과 부합.

## 3. 코호트 밴드 재계산 (표적 3) — PASS

raw 레코드(각 장면의 v5 출력: `unit_status`·`relative_error`·`scale_kappa`)에서 독립 재계산. 산출: `s3_bands.py` → `s3_bands_out.json` (입력: `s2_band_rows.jsonl`).

- **HIGH 360/400** 재계산 일치. **HIGH 중 5% 이내 360/360** (최대 상대오차 3.11e-15 — 한계 0.05의 10^13분의 1 수준), 비율 1.000000 ≥ 조문 `high_accuracy.minimum_fraction` 0.95 ✓.
- **코호트×스케일 8셀 coverage**: c1_original 4스케일 전부 1.0, l1b 4스케일 전부 0.8 → **최소 0.800000** = REPORT 주장과 일치, 전 셀 ≥ 조문 `high_coverage_per_scale.minimum_fraction` 0.6 ✓. 스케일 집합 {0.001, 0.01, 1, 1000} = 봉인 스케일과 일치.
- **O1/O2 무손실**(조문 `legitimate_scene_no_loss`, 허용 0/0): `honest_envelope.json`의 O1/O2 원시 v4/v5 출력에서 상태 강등을 직접 재비교 → 강등 0, coverage 손실 0. (O2는 v4 unit_status LOW → v5 HIGH로 오히려 상승 — 강등 아님.)
- 정직 봉투 재집계: 장면별 원시 레코드 400건에서 최대 ratio 편차 = **1.4563237239633405e-13 τ** (봉인 한계값과 자릿수까지 동일), raw-span/기하 불일치 합 0, 앵커 합 2008 (l1b 1108 + c0 900) — replay 입력 장면의 앵커 수 합과도 일치. 장면 ID 집합은 replay와 완전 동일.
- **바이트 결속(보너스)**: 봉투 400장면 전부의 `frozen_surface_digest`가 **replay 입력 장면 anchors 직렬화의 SHA-256과 400/400 일치** (`s7b_envelope_binding.py` → `s7b_out.json`) — 봉투와 replay가 같은 원시 표면을 본다는 것이 바이트 수준으로 증명됨. O1/O2 input_surface_digest도 재계산 일치.

## 4. 회귀 회계 (표적 4) — PASS, 전 카운트 재구성

산출: `s4_counts.py`→`s4_counts_out.json`, `s4b_pass2.py`→`s4b_out.json`, `s4c_pass3.py`→`s4c_out.json`, `s4d_taudit.py`→`s4d_taudit_out.json`.

**630/641/9/5/11** (c1v7_results.json property_test, 원시 case_manifest 641행에서):
- 무작위 630 = `stratum` 필드 보유 행 수 (스트라텀 5종 합 105+105+210+105+105=630, 조문 5 strata 전부 비공백 ✓).
- 3함대 회귀 11 = 무-stratum 행, case_id `REG::CE-A…REG::D4` — **봉인 조문의 11개 class 목록과 집합 일치**.
- 지정 9패밀리 각 70건 (`family_counts` 필드 == 무작위행 재집계, 조문 `designated_9_families` 전부 포함) ✓. 총 641 ✓. property seed 20260719 == 봉인 seed ✓.
- 봉인 사본 대조: c1v7 내 `sealed_configuration` 객체 == `prereg.json` 파싱 객체 **완전 동일**.

**5프로브/747/1494** (fleet_probe_results.json seat4 블록, 스트리밍 전수):
- targeted_five: 5케이스, v4 상승 5/v5 상승 0 — 블록 카운터와 **내 before→after 재계산** 모두 일치.
- window_747: parent 1,494 전수 카운트 ✓, known-positive 747 (ID 목록 747개와 케이스 플래그 일치) ✓, **내 v4 상승 재계산이 known-positive 소속과 1,494케이스 전수에서 완전 일치(불일치 0)** — "747 양성" 자체가 재현됨. v5 상승: 전 1,494케이스에서 0 ✓.

**2000/50/44** (lens2 P5, 스트리밍 전수):
- parent 2,000 ✓. v4 위반(=v4.classification=violation) 50 ✓. **v5 상승 — 내 독립 재계산 44** == 블록 카운터 44 == REPORT ✓. 50건의 known-violation 중 v5 상승 0(전부 차단) ✓, 그중 info-limit 인증 0 ✓.
- 각 케이스의 `increases` 필드(5개 추적 필드별 상승 불리언)와 내 재계산 상승 집합이 **전 블록 전수에서 완전 일치** (`increase_sets_match_everywhere: true` — manifest 641·P5 2000·window 1494·t5 5·3함대 11·lens1 2·P4·T_B 포함).

**90/0/0** (witness_classifications.json 전수):
- 분류 90, violation 0, 수동 억제 0, 미분류 필드 0, 미커버 선언 필드 0 ✓.
- 90건 전부: 18규칙 순서가 estimator의 `complete_detection_rule_order`와 정확히 일치, 규칙별 관측수(0 포함) 명시 딕셔너리가 transcript와 90/90 일치, 장면별 생성 내러티브 존재 90/90, `field_events` 합 **395** == 요약 필드 ✓.
- 직렬화 무결성: `post_serialization_sha256`·`witness_serialization_sha256`(문자열 SHA) 각 90/90, `honest_generation_spec_digest` 90/90 재계산 일치. 분류 배열 다이제스트 == 파일 기록 == c1v7 요약 기록.
- **분류 ID 폐쇄**: 상승이 실재하는 케이스가 참조하는 classification_id 합집합(= manifest 46 + P5 44) == **witness 90개 ID와 정확히 집합 일치** (여집합 0/0). 상승-증인 장부가 닫혀 있다.

**15/15** — §5. **55행** (non_dilution):
- 11케이스 × N∈{0,3,10,20,40} = 55행 전수 ✓ (케이스별 N집합 5/5, 11/11). Tier A 2 + Tier B 9 = 11 (c1v7 `registered_Tier_A_kind_count` 2 + `enumerated_Tier_B_path_case_count` 9와 일치).
- **penalty 재계산**: penalty = q(matched_clean) − q(with_S)를 95개 값 전수 재계산 → 불일치 0. Tier A 플로어(케이스 봉인 플로어, 후보수 무관) 대비 전 N에서 위반 0 (20/20). Tier B 행 75개: 해당 경로 점수 정확 0·상태 정확 NONE 위반 0. fixed_S 바이트 불변: 55행 전부 `fixed_S_digest` == 표면 재해시, sweep 내 단일값.
- **T_A/T_C/T_S** (`s4d_taudit_out.json`): 전 N에서 v5 해당 경로 0.0/NONE 유지(위반 0), 의심 신호 잔존 0손실. 대조군 v4는 N=0→40에서 0.42→0.96(T_A reference)으로 **희석 공격에 뚫리는 모습까지 데이터로 실림** — v5 비희석의 실증 대비.
- **P4 무손실**: v5 reference 1.0→1.0, 강등 0 (재계산). 대조 v4는 1.0→0.375 — 봉인 조문 `ratio_absent_handle_neutrality.mandatory_regression`의 금지 시나리오("1.0 to 0.375")가 v4에서 정확히 재현되고 v5에서 제거됨.
- 알려진-역경 info-limit 0 (named 회귀 스코프 — §8-N4 참조), GRID 무손실 0/0, 요약 3원 일치 (REPORT == c1v7 요약 == fleet 요약).

**다이제스트 사슬**: 이름-쌍 다이제스트 7,102건 재계산 **불일치 0**. 케이스 다이제스트 = 자기제외 SHA로 P5 2000/2000·window 1494/1494·3함대 11/11·t5 5/5·lens1 2/2 검증; 블록 다이제스트 = 케이스 다이제스트 목록 SHA로 P5·window·manifest(641)·non_dilution·third_fleet 검증.

## 5. 술어 진본성 (표적 5) — PASS, 15/15 실제 재실행

산출: `s5_predicates.py` → `s5_predicates_out.json`. 기록(`observed_counterexample_result_false`)을 믿지 않고, 15개 술어 각각을 공표된 `predicate_expression` 의미로 **독립 구현**해 레지스트리의 반례 입력에 실행했다.

- **반례 15/15 전부 False 재현** (위성립 15/15). 평가기 오류 0.
- 구조: 9 승계 + 6 확장 = 15 ✓, 조문 요구 6필드 전 항목 존재 ✓, `counterexample_execution_transcript` 15건 파싱 결과가 registry 항목과 15/15 동일 ✓, c1v7 내장 사본 == 레지스트리 파일 ✓.
- 반례 주석 문언: 봉인 조문의 의무 주석과 **14/15 문자 단위 일치**; 1건(continuous_tau_attenuation)은 ASCII 음역(§8-N1).
- **현실 평가(보너스)**: 데이터-수준 술어 11종을 이 함대가 재계산한 실제 증거에 적용 → 11/11 True (나머지 4종은 의미론-수준이라 N/A 명시). 예: seal_content_match를 실제 재계산 해시로 평가 → True; tier_B_hard_block을 T-스윕 실측(0/NONE)으로 평가 → True.

## 6. 아티팩트 SHA + evidence.xlsx (표적 6) — PASS

- **REPORT.md 표의 12행 SHA-256 전부 재계산 일치** (`s1_seals_out.json`, §1과 동일 실행).
- **evidence.xlsx 대 JSON 대조**: 요구 표본 ≥50셀을 크게 초과한 **668셀 결합 검증, 수치 불일치 0** (`s6_xlsx_dump.py`→`s6_xlsx_dump.json`, `s6b_compare.py`→`s6b_compare_out.json` 661셀 + `s7_final_checks.py`→`s7_final_out.json` 7셀). 시트별: NUMBERS 37 · ENVELOPE 12 · PROPERTY 16 · NON_DILUTION 55 · REGRESSIONS 12 · WITNESS 451(90행 전수) · REPLAY 29 · SELFTEST 45 · FILES 11.
- REPLAY 시트의 코호트×버전 6행은 replay 재스트리밍으로 버전별 HIGH를 재계산해 대조(l1b 160/160/160, c0 0/200/200) — v1이 c0에서 HIGH 0이던 것이 v4/v5에서 200으로 회복된 이력까지 수치 일치. 유일한 표기 차이는 §8-N3.

## 7. 불일치 목록

**수치·해시·카운트 불일치: 0건.**

## 8. 비저해 관찰 (판정 불변, 기록 목적)

- **N1 · 주석 음역 1건**: 술어 `continuous_tau_attenuation`의 반례 주석이 조문 "…finite 1↔0 jump at τ±ε…" 대비 레지스트리 "…finite 1-to-0 jump at tau plus or minus epsilon…"으로 ASCII 음역됨. 의미 동일, 수치 무관. (`s5_predicates_out.json` annotation_diffs)
- **N2 · prereg tau 리터럴 절단**: 조문의 tau `value` 0.048790164169432는 정의식 ln(1.05)의 배정밀도 값 0.04879016416943204보다 4.16e-17 작게 인쇄된 절단 리터럴 (envelope·estimator는 정확값 사용). 정의식이 규범이므로 무해. (`s7_final_out.json` tau)
- **N3 · 0/0 표기 관례**: REPLAY 시트 c1_original·v1 행의 high_accuracy가 0으로 기록 — HIGH 0건이라 분모 0(미정의)을 0으로 인코딩한 관례. 같은 행 high_count=0은 내 재계산과 일치. (`s6b_compare_out.json` 유일 항목)
- **N4 · "Known-adverse information-limit classifications: 0"의 스코프 (lens1·합성 좌석 교차확인 플래그)**: 이 0은 named 4차-함대 회귀(seat4·lens1·lens2 블록) 스코프에서 원시 재집계로 정확하다(P5 known-violation 50건 중 info-limit 0 포함). 다만 **3함대 class 회귀 3건 — CE-A(W000000)·CE-B(W000001)·CE-E(W000002) — 는 v5 상승(NONE→HIGH)이 존재하며 information_limit_record로 인증**되어 있다(`s4c_out.json` tf_risen; xlsx WITNESS 시트에 scope=third_fleet로 공개; 90건 폐쇄 집합의 일부). 봉인 조문상 관측-동치 증인이 성립하면 info-limit 인증은 gate 위반이 아니고(`perturbation_monotonicity.classification.information_limit_record.gate: false`), 세 건 모두 `exact_all_field_equality: true`로 기록돼 있다 — 즉 **회계상 불일치는 아니다**. 그러나 그 증인의 의미론적 정당성 실질 판단은 내 시야(장부) 밖이므로, REPORT 문장을 "3함대 포함 전 역경 0"으로 읽을 위험과 함께 lens1(증인 시야)·합성 좌석에 교차확인을 플래그한다.
- **N5 · 미해독 다이제스트 구성 4종**: suspicion 블록 내부의 `frozen_surface_digest`(7,159회)·`surface_digest`(10,769회)·`observation_digest`(2,000회)와 manifest 행·P4의 `case_digest`는 인접 명명 규칙으로 기저를 찾지 못해 구성 방식을 재현하지 못했다(사양 미공표; 시도 기록 `s7_final_out.json`·`s7b_out.json`). 이름-쌍이 성립하는 7,102건과 문자열-SHA·사슬 다이제스트는 전부 검증됐으므로 회계 결론에 영향 없음 — 문서화 공백으로만 기록.

## 9. 검증 경계 (하지 않은 것)

- git 증인 커밋 `c896068`의 실존·시점 검증 — 패킷상 git 금지, **seat4 소관** (읽기 전용 git 허용 좌석).
- 추정기 3판(v1/v4/v5)을 입력 장면에 **재실행해 출력 자체를 재생성**하는 것 — lens1(증인)·lens2(산식) 소관. 내 확증 범위는 "공표된 출력·행·카운트·다이제스트가 상호·내부 정합하고 전수 재구성 가능하다"까지다.
- 원본 CAD·test 표면 접근 없음. `cells\loop_l1f\` 기존 파일 수정 없음(작성은 lens3_work·본 verdict만). git 명령 0회, 서브에이전트 0회.

**이상 기록 (환경 오염, 데이터 무영향)**: 검증 세션 중(2026-07-19 08:15:18) `cells\loop_l1f\__pycache__\feyerabend_c1_v5.cpython-312.pyc`가 생성된 것을 종료 점검에서 발견했다. 내 스크립트는 셀 모듈을 import하지 않으며(lens3_work의 전 스크립트가 감사 가능), 생성 주체는 미상(백그라운드 인덱서 또는 병행 프로세스 추정). 영향 평가: ① pyc 헤더의 소스 mtime/size가 현재 `feyerabend_c1_v5.py`와 일치하는 표준 캐시이고, ② 소스 SHA-256은 봉인값 `6D1D0AA1…4164C489` 그대로이며, ③ **세션 종료 시점에 12개 아티팩트 SHA 전면 재검증 결과 불일치 0** (`s1_seals.py` 재실행) — 기존 파일 무변조 확증. 원본 영역 삭제는 내 권한 밖이므로 삭제하지 않고 오케스트레이터에 정리(캐시 제거)를 위임한다.

## 10. 재현 절차

```
cd D:\runs\e2_program\chainverify_L1f\lens3_work
python s1_seals.py            # 봉인 3파일 + 12아티팩트 SHA + CSV 동치
python s2_replay_audit.py     # replay 218,469행 전수 감사 (스트리밍)
python s3_bands.py            # 코호트 밴드 + 정직 봉투 재집계
python s4_counts.py           # 회귀 회계 1차 (카운트·다이제스트)
python s4b_pass2.py           # 상승 재계산·증인 심층·ID 폐쇄
python s4c_pass3.py           # increases 대조·penalty/플로어·3함대 상승 식별
python s4d_taudit.py          # T_A/T_C/T_S 희석 스윕 하드블록 전수
python s5_predicates.py       # 술어 15 반례 실제 재실행
python s6_xlsx_dump.py && python s6b_compare.py   # xlsx 668셀 대조
python s7_final_checks.py && python s7b_envelope_binding.py  # 각주 증거
```
(python = `C:\Users\PAUL\AppData\Local\Programs\Python\Python312\python.exe`, numpy 불요·stdlib만 사용)

— lens3 종료. 판정 = **CONFIRM**, 수치 불일치 0, 신규/회귀 결함 class 실증 없음.
