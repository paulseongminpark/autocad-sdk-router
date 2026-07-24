# lens3 공시 — 공개·술어 실행 무결 시야 (4차 함대, L1e)

- 좌석: lens3 (사슬 검증단, 공개·술어 실행 무결)
- 일자: 2026-07-19
- 대상: L1e 루프 종결 주장 중 lens3 계약 4항 — ① replay_delta.json 101,828행 완전성(독립 재실행 대조) ② 코호트 밴드·O1/O2 재계산 ③ predicate_registry 반례 전 술어 독립 재실행 ④ 26→0 등 이전 티켓 유지
- 방법: 모든 기존 산출물 READ-ONLY. 재계산·스크립트·결과는 전부 `D:\runs\e2_program\chainverify_L1e\lens3_work\` (s0~s6 스크립트 + 동명 JSON 결과). git 명령 0회, 서브에이전트 0회, 원본 CAD·test surface 미접근. 실행 인터프리터: Python 3.12 (`s0_inventory.json`에 버전 기록).
- 작업 폴더 주의: lens3_work에는 내 세션 이전부터 존재한 타 산출 파일(`verify_replay_full.py`, `verify_o1o2_predicates.py`, `recon_*.py`, `replay_check_results.json`, `o1o2_predicates_results.json`)이 있다. **이 평결은 그 파일들을 읽지도 쓰지도 않았고, 오직 s0~s6 스크립트와 그 JSON 결과에만 근거한다.**

## 0. 검증 기반 고정 (s0)

내가 감사한 바이트가 REPORT가 주장하는 바이트인지 먼저 고정했다.

- L1e 산출물 10종(REPORT §산출물 SHA-256 표의 전 항목 + prereg.json)의 SHA-256을 재계산 → **10/10 REPORT 표와 일치**. 특히 `replay_delta.json = 39850C1F…`, `predicate_registry.json = C006B97E…`, `prereg.json = EF1E9802…`(봉인 기대값과 동일), `PREREG_SEALED.csv = 4AA741C4…`.
- 추정기 모듈 사슬 검증: replay가 쓰는 v1/v3는 repo 파일이 아니라 v4 모듈 속성(`V4.V3`, `V4.ORIGINAL`)이다. 라이브 로드로 추적한 결과 V4 → repo `feyerabend_c1_v3.py`(경로 일치) → run 영역 사본 `cells\feyerabend_c1\feyerabend_c1.py`(v1)·`cells\loop_l1c\feyerabend_c1_v2.py`(v2). **run 영역 v1·v2 사본은 repo 원본과 SHA-256 byte-동일** (v1 `633C5EE1…`, v2 `5F6F2EEE…`) — 사슬에 별도 코드 삽입 없음.

## 1. 계약 ① — replay 전문 공개 101,828행 완전성

### 1-a. 공개 파일 전수 재계수 (s1 — 표본이 아니라 전수)

| 항목 | 주장 | 재계수 | 판정 |
| --- | --- | --- | --- |
| 장면 수 | 400 (L1b 200 + C1 200) | 400 (200+200, scene_id 전건 유일) | 일치 |
| per-scene per-field 행 | 101,828 | 101,828 (l1b 51,528 + c1 50,300) | 일치 |
| 0-델타 행 포함 | 38,640 포함 | 38,640 (l1b 20,040 + c1 18,600) — 내 기준으로 재판정(equal13∧equal34) | 일치 |
| 저장 equal 플래그 3종×101,828 | — | 전수 재계산, 불일치 **0** | 일치 |
| 저장 numeric delta 3종 | — | 전수 재계산, 불일치 **0** | 일치 |
| 필드 커버리지 | 전 필드 공개 | 장면마다 v1/v3/v4 `complete_version_rows`를 **내 독립 flatten**으로 평탄화한 경로 합집합 == 공개 행 경로 집합, 400/400 장면, 누락·유령 행 0, 중복 경로 0 | 일치 |

### 1-b. 독립 재실행 (s2 — 계약의 핵심)

내 자체 장면 로더로 두 코호트 400 장면을 읽고, v1/v3/v4 세 추정기로 **전 장면을 라이브 재평가**한 뒤, 내 자체 flatten·계수기로 행을 재생산했다.

- 라이브 총 행 수 **101,828**, 라이브 0-델타 **38,640** — 주장 수치를 독립 재생산.
- 장면×버전 1,200개 결과 행 전부: 내 라이브 행 == 공개 `complete_version_rows` (dict 정확 일치 1,200/1,200), canonical SHA-256 digest 일치 1,200/1,200, 코호트별 `rows_digest` 6종 일치, v1/v3/v4 aggregate 스냅샷 재계산 일치 6/6.
- 휘발 필드: **0개** — REPORT의 "휘발 필드 제외 수치 전 필드 동일"보다 강한 결과(전 필드 동일)로 성립.
- `baseline_live_integrity`(과거 저장 v1/v3 결과 대비): mismatch 0, stored digest == live digest — 파일 내 기록과 라이브 재현이 정합.

**판정: ① 성립.** 101,828행은 실재하고, 0-델타가 실제로 포함되어 있으며, 필드 커버리지가 완전하고, 전문이 독립 재실행으로 재생산된다.

## 2. 계약 ② — 코호트 밴드·O1/O2 재계산

### 2-a. 코호트 HIGH 밴드 (s3)

s2의 내 라이브 평가 결과에서 scale별로 독립 집계(상대오차는 `abs(est−truth)/truth`로 내가 재계산):

| cohort | scale | n | HIGH_n | coverage | accuracy_5pct | 판정 |
| --- | --- | --- | --- | --- | --- | --- |
| l1b | 0.001/0.01/1/1000 | 50×4 | 40×4 | **0.8** | **1.0** | REPORT와 정확 일치 |
| c1_original | 0.001/0.01/1/1000 | 50×4 | 50×4 | **1.0** | **1.0** | REPORT와 정확 일치 |

- 주장 "L1b 0.8/1.0 · C1 1.0/1.0" 8행 전부 성립.
- REPORT의 HIGH_relerr_max 열(≈1e-15 급)은 공개 행의 `relative_error` 필드 최대값과 **8/8 정확 일치**(그 필드는 s2에서 라이브 재생산 증명됨). 내 독립 공식과의 차이는 최대 **5.33e-17**(부동소수 표현 잡음, 판정 임계 0.05 대비 15자릿수 아래) — 실질 차이 없음.

### 2-b. O1/O2 무손실 (s3)

O1(정직 혼합 단위)·O2(낡은 라벨) 프로브 anchors를 loop_l1e.py의 리터럴 파라미터에서 **재구성**해 v1·v4로 라이브 스냅샷:

- status/unit_status/reference_status 3필드 기준 downgrade **0**, display_per_raw 소실(coverage loss) **0** — 주장과 일치.
- 내 라이브 스냅샷 == fleet_probe_results.json 저장 관측(v1/v3/v4 × O1/O2 전부 일치). 저장 카운트(fleet)·c1v6 요약 카운트 모두 {0, 0}으로 3중 정합.

**판정: ② 성립.**

## 3. 계약 ③ — 술어 9종 반례 실행 false 관측

2계층 + 양성 대조로 재실행했다 (s4):

- **계층 A (독립 구현)**: 공개 술어식 9종을 내가 다시 구현하고, registry에 기록된 반례 입력을 그대로 투입 → **9/9 false**.
- **계층 B (실제 코드)**: loop_l1e.py의 실제 술어 함수 9종에 동일 입력 → **9/9 false**. `build_predicate_registry()`를 라이브 재실행 → 산출 registry가 공개본과 정확 일치.
- **양성 대조군** (항진식/항위식 사멸 확인): 각 술어에 충족 입력(가능한 곳은 내가 검증한 실측값 — coverage 0.8, accuracy 1.0 + relerr 1e-15급, 101828==101828∧포함, 1767==1767∧violation 0, 손실 0/0, prereg 실 SHA 등) → **9/9 true**. 술어가 constant-false도 아니고 반례에 항복하지 않는 것도 아님을 양방향으로 확인.
- **사본 정합**: predicate_registry.json == REPORT 내장 ```text 블록 9행 == registry 내부 transcript == c1v6_results.json 내장 블록 (4중 일치).
- **봉인**: prereg.json SHA-256 == 봉인 기대값 `EF1E9802…` (seal_content_match 양성 대조가 곧 라이브 봉인 검사); 반례의 "changed" digest는 봉인 바이트+`b"changed"`에서 정확 재현.

**판정: ③ 성립.** "반례 실행으로 false 관측"은 기록이 아니라 재실행으로 성립한다.

## 4. 계약 ④ — 26→0 등 이전 티켓 유지

### 4-a. 26→0 티켓 (C1 single_outlier)

1~3차 함대가 고정한 티켓: C1 코호트 200장면에서 single_outlier 교란 시 v1이 status 26·reference_status 26 상승, v2/v3에서 0. L1e에서의 유지를 **s2가 라이브 동일성을 증명한 행**(1,200/1,200 byte-동일 → 라이브 값과 등가)의 corruption 전이로 재계수:

| 버전 | status 상승 | reference_status 상승 |
| --- | --- | --- |
| v1 | **26** | **26** |
| v3 | 0 | 0 |
| **v4** | **0** | **0** |

v1의 26/26은 내 계수기가 상승을 실제로 검출함을 보이는 **양성 대조**이고, v4의 0/0이 티켓 유지다. 추가로 400 장면 × 교란 4종(duplicate·stale_override·suffix_removal·single_outlier) 전수에서 v4 상승 카운터는 **전부 0**.

### 4-b. 수리 가능 class 6종 = 0 · 잔존 수치 유지 (s5·s6)

72,396 전이의 공개 원시 manifest(`transition_manifest`, 행마다 family·upward_fields·digest·classification_id)를 전수 재계수:

- manifest 길이 **72,396** 정확; 가족별 행 수(5,904×6 + 17,712×2 + 1,548) REPORT 표와 9/9 일치.
- upward_fields 재합산: **outlier_clone·handle_collision·display_removal·geometry_ratio_break·exact_duplicate·reference_support_drop 전부 상승 0·이벤트 0**; 잔존 stale_override 36전이/180이벤트·suffix_removal 66/330·type_to_grid 210/1,050 — REPORT 표·family_stats·field_upward_counts 3중 모두 재계수와 일치.
- 증인 연결 완전성: 상승 manifest 행 312개(=36+66+210)의 classification_id 집합 == seat4_small_state_search 증인 레코드 312개의 ID 집합 (**정확 집합 일치, 누락 0**).

### 4-c. 1,767 이벤트 대사 (s5·s6)

- witness_classifications.json: 레코드 **361** = 312(small_state) + 43(property) + 5(third_fleet) + 1(fleet_core); field_events 총합 재계수 **1,767** = 1,560 + 183 + 21 + 3.
- 교차 원천 재계수: third_fleet 11 case의 before/after 스냅샷에서 v4 상승을 내가 재계수 → 21, 저장 카운터와 일치, 상승 case 전건 증인 연결; property는 c1v6 `v4_upward_field_counts` 합 183과 일치; denominator sweep 저장 상승 전부 0(증인 scope 부재와 정합).
- 라벨: information_limit_record **361/361**, violation **0**, unclassified **0**, manual suppression **0**. REPORT 실행 수치 표의 전 행(641/630/11/361/1767/0/0/0/1548/72396/400/101828/38640) 재계수 또는 교차 확인 완료.

**판정: ④ 성립.**

## 5. 특이 관찰 (평결에 영향 없는 공개 사항)

1. **모듈 사슬이 run 영역 사본을 경유** — repo v3가 v1·v2를 `D:\runs\…` 사본에서 로드한다. byte-동일임을 SHA로 확인했으므로 무결하나, 후속 루프에서 사본 drift가 생기면 즉시 위험해지는 지점이다(이전 함대들도 이 구조를 통과시킨 기존 설계).
2. REPORT의 HIGH_relerr_max는 추정기 자체 `relative_error` 필드 기준이다. 내 독립 공식과 ≤5.33e-17 차이 — 수치 주장으로서는 동일하나, 열 정의를 "추정기 필드 최대값"으로 읽어야 정확 재현된다.
3. 증인 중 geometry_ratio_break 1건은 third_fleet의 구성 프로브(CE-C)이지 72,396 탐색이 아니다 — "수리 class 상승 0은 72,396 전수에서"라는 주장 스코프와 정합.
4. replay 재현에서 휘발 필드가 0개였다 — 파이프라인이 완전 결정론적.

## 6. 내 시야가 아닌 것 (경계 명시)

- 봉인 커밋 @3a390e8의 git 이력·시점·추정기 부재 검증 = seat4 §① (나는 git 금지 계약대로 git 명령 0회; 봉인은 내용 SHA 수준까지만 검증).
- 72,396 전이의 추정기 레벨 **전면 재실행**·독립 재구성 = seat4 §② (나는 공개 manifest 전수 재계수 + 400장면 교란 계층 라이브 검증 + 증인 연결 완전성까지).
- 증인 분류기의 적대 검증·정직성 = lens1, 공개 공식의 구조 공격 = lens2.

## 7. 종합

lens3 계약 4항 전부에서, 주장 수치는 재계산·독립 재실행·양성 대조를 통과했고 단 하나의 불일치도 발견되지 않았다. 재계산 전 과정은 `lens3_work\s0~s6` 스크립트와 JSON 결과로 재현 가능하다.

VERDICT: CONFIRM
