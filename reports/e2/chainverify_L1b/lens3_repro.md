# Lens3 — CODE/REPRODUCTION 검증 보고 (L1b 사슬 독립검증)

- 검증관 시야: 코드/재현 — selftest 재실행, 전량 재생성+재평가, 코드의 숨은 진리 접근·하드코딩 감사, 결정성 실측, c1v3 내부 정합 재계산.
- 검증 대상: `D:\runs\e2_program\cells\loop_l1b\` (loop_l1b.py · scenes_v3 200개 · c0v3_numbers.json · c1v3_results.json · evidence.xlsx · REPORT.md) 및 상류 사슬(feyerabend_c0.py · feyerabend_c1.py · loop_l1.py).
- 재실행 환경: Python 3.12.10 / numpy 1.26.4 / ezdxf 1.4.3 / openpyxl 3.1.5 / Windows-11-10.0.26200. 원본 c1v3의 environment 블록과 완전 일치(byte-diff에서 environment 리프 차이 0) — 부동소수 비트 단위 재현의 전제가 성립하는 환경.
- 실행 방식: loop_l1b.py를 `lens3_work\rerun1\`로 복사(사본 sha256 = 원본과 동일 `ac8a9c0a…`)해 그 디렉토리에서 2회 전량 실행. 원본 디렉토리에는 쓰기 0회 — 원본 5개 산출물의 현재 디스크 해시가 원본 REPORT.md 산출물 표(생성 시점 02:05 기록)의 해시와 전부 일치함으로 입증.
- 모든 재실행 출력: `D:\runs\e2_program\chainverify_L1b\lens3_work\` 하위에만 기록.

---

## 발견 사항 (심각도순)

### F1 [LOW] 주장 ⑦ "재실행 바이트 동일"은 문구 그대로는 과대 — 수치 결정성은 100%이나, 산출물 3종은 구조적으로 바이트 동일이 불가능

- 실측(동일 디렉토리 2회 연속 전량 실행, run1 vs run2): **205개 파일 중 202개 바이트 동일** — scene 200개 전부 + `c0v3_numbers.json` + 스크립트. 차이 3개:
  - `c1v3_results.json`: 차이 리프 6개 전부가 `runtime.cpu_seconds`/`wall_seconds`/`loop_cpu_seconds`/`loop_wall_seconds`(실행시간 4개) + `evidence.sha256`·`artifacts[2].sha256_or_digest`(아래 xlsx 파생 2개). 수치 페이로드(aggregates·scenes 200행·ticket·manifest) 차이 0. 근거: `lens3_work\json_diffs.txt` 58-76행.
  - `evidence.xlsx`: 바이트는 다르나 **15개 시트 전 셀 값 차이 0** — openpyxl이 저장 시각을 파일 내부(docProps)에 기록하기 때문. 근거: `lens3_work\xlsx_diff.txt` (run1_vs_run2 cell_diff_count=0).
  - `REPORT.md`: 3953행 중 2행 차이 — 위 두 파일의 해시를 인용하는 산출물 표 행. 근거: `lens3_work\report_diff.txt`.
- 즉 실행시간 기록을 담는 c1v3와, 저장 타임스탬프를 담는 xlsx, 그 둘의 해시를 인용하는 REPORT 3종은 **어떤 재실행으로도 바이트 동일이 될 수 없는 구조**다(loop_l1.py:1362-1369가 runtime을 결과 JSON에 기록). 프로그램 저널의 C1 항목(292행)은 "실행시간 기록만 서로 달랐다"는 단서를 정확히 달았으나, L1b 항목(433행 "재실행한 결과도 바이트 단위로 동일")은 이 단서를 생략했다.
- 판정 영향: 없음(수치 왜곡 0 — 주장 ⑦의 실질인 "결정적 재현"은 아래 검증 결과 V7에서 성립). 문구 정밀도 문제로만 기록.

### F2 [참고] HIGH 정확도 1.0은 구조적으로 보장된 설계 — 추정 난이도의 증거로 읽으면 안 됨

- C0 생성기는 모든 ratio 앵커의 표시값(display_value)을 진리와 정확히 일관되게 심는다: 기본 장면에서 display=raw(feyerabend_c0.py:526-527), 스케일 복제는 좌표·raw_span만 κ배 하고 display는 고정(feyerabend_c0.py:900-909), 검증기가 display/raw = 1/κ를 1e-12 오차로 강제(feyerabend_c0.py:1228-1231). 실측: c0v3 `ir_display_raw_truth_ratio_mismatch_count = 0`.
- 따라서 추정기가 합의에 도달하기만 하면 그 값은 정확히 진리이며, HIGH 정확도 1.0(상대오차 최대 3.1e-15 = 부동소수 한계)은 **봉인 신뢰도 공식의 선택성**을 재는 것이지 추정 난이도를 재는 것이 아니다. 단, 이는 도시에 자체가 봉인한 설계다(feyerabend_P2.md:563 "표시 치수값은 canonical physical geometry와 일관되게 유지") — 결함이 아니라 판독 맥락으로 기록.

### F3 [참고] 저널 인용 커밋(8bc4ce7 등)은 본 시야에서 검증 불가

- 발사 프롬프트가 git 명령을 금지하므로 커밋 존재·내용은 확인하지 않았다. 산출물 자체의 재현으로 대체 검증했다(아래 V1-V7).

### F4 [참고] REPORT 임시 마커 치환은 무해 기믹

- render_report가 임시로 `LOOP_COMPLETE: L1`을 쓰고(loop_l1b.py:1147-1153) L1.execute_full의 마지막 줄 검증(loop_l1.py:1407)을 통과시킨 뒤 `finalize_report_marker`(loop_l1b.py:1208-1214)가 원자적으로 `LOOP_COMPLETE: L1b`로 바꾼다. 재실행에서 최종 줄 = `LOOP_COMPLETE: L1b` 확인. 속임수 아님 — 기록만.

**치명·중대 결함: 발견 0건.** 숨은 진리 접근, 하드코딩된 결과, 재현 불가, 집계 조작 — 모두 부재를 실측으로 확인(아래).

---

## 검증 결과 — 주장 ①~⑦ 전 항목 재계산

재계산 스크립트: `lens3_work\consistency_check.py` (23/23 OK, 상세 `consistency_detail.json`), `lens3_work\compare_artifacts.py`.

### V0. 재현의 핵심 사슬 (3중 재현)

1. **장면 재생성 = 원본과 바이트 동일**: 내 재실행이 만든 scene 200개 전부가 커밋된 `scenes_v3\`의 200개와 sha256 일치 (`hash_compare.json`: run1_vs_orig scene_diffs=0). → 커밋된 시험지는 코드+시드가 만드는 그것 그대로다.
2. **평가 재도출 = 원본과 정확 일치**: L1b 코드를 거치지 않고, 커밋된 scene 200개를 봉인 C1 모듈(`feyerabend_c1.py`)에 직접 넣어 `evaluate_scene`×200 + `aggregate_results`를 재계산 → **200행 전부와 aggregates 전체가 커밋된 c1v3_results.json과 canonical-JSON 기준 정확 일치**(양쪽 digest `09d7cf9e…`). → c1v3의 수치 본문은 장면+봉인 추정기에서 완전 유도 가능 — 손대거나 하드코딩할 자리가 없다.
3. **전량 재실행 대조**: 원본 디렉토리 산출물과 내 재실행 산출물의 차이는 전부 경로 반향·실행시간·xlsx 타임스탬프 파생뿐:
   - c0v3_numbers.json: 차이 리프 **1개** = `contract.write_root`(내 재실행 디렉토리 경로 반향).
   - c1v3_results.json: 차이 리프 17개 = 경로 7 + 실행시간 4 + evidence 바이트/해시 4 + 스크립트 경로 행 2. 수치 리프 차이 **0**.
   - evidence.xlsx: 전 시트 셀 값 차이 **1개** = source_manifest 시트의 스크립트 경로 문자열(해시·크기는 동일).
   - REPORT.md: 3953행 중 5행 = 경로 반향 2 + 산출물 해시 표 3.

### V1. 주장 ① — HIGH 커버리지 4스케일 각각 0.80 (게이트 ≥0.60, 도시에 788행)

원시 scene 행에서 재계산: κ=0.001 → 40/50=0.80, κ=0.01 → 40/50=0.80, κ=1 → 40/50=0.80, κ=1000 → 40/50=0.80. aggregates의 `scale_confidence_rows`(HIGH 행)와 교차 일치. **성립.**

### V2. 주장 ② — HIGH 정확도 1.0 (게이트 ≥0.95 상대오차 5%, 도시에 787행)

HIGH 160행 전부 추정 존재, 상대오차 ≤0.05인 것 160/160 = **1.0**. 스케일별 HIGH 최대 상대오차: 2.0e-15 / 3.1e-15 / 0.0 / 2.2e-16. 행 단위 `relative_error`·`e_s`를 `scale_estimate`와 `truth_unit_scale`(=1/κ 재확인)로부터 전수 재계산 — 불일치 0. **성립** (구조적 맥락은 F2).

### V3. 주장 ③ — mutation family 11/11, 단일-스팬 10 장면 복원 (도시에 758행)

c0v3 재계산: 11개 가족 전부 ≥1 — `single_reference_span_region=10`, `multiple_reference_span_regions=40`, 나머지 {pure_line 21, lwpoly 25, arc_spline 50, hatch 50, nested 50, partial 50, door_window 49, zero 1, all 1}. 모집단 base {anchor_rich 40, single_span 10}, IR {160, 40}. 도시에 550-561행의 10개 불릿(마지막 "단일·다중" 결합 불릿을 2개 manifest 가족으로 분리)과 1:1 대응 — loop_l1b.py:78-99가 대응을 강제 검증. **성립.** 루프 경로 정직성도 수치로 확인: single_ref 장면 수 v1=25 → L1=**0**(가족 소멸, 기각 사유) → L1b=**10**(복원).

### V4. 주장 ④ — 충실도 KS 0.0403 / TV 0.000212 (게이트 0.20/0.10, 도시에 759행)

재실행 재계산값 KS = 0.040287855437306064, TV = 0.00021191458340744963. v1(coverage_numbers.json)·L1(c0v2_numbers.json)·L1b(c0v3_numbers.json) 세 값이 **비트 단위 동일**(부동소수 전 자리 일치). 참조 통계는 aggregate 리포트 파일(fidelity_stats.py:24-29 → `reports\e2\s2\fidelity_M_v2.json`·`fidelity_M_v1_tv.json`)이지 원본 CAD/test 데이터가 아님. **성립.**

### V5. 주장 ⑤ — 진리 무접촉 (도시에 789행)

- **코드 경계(전문 정독)**: `fit_anchor_model`(feyerabend_c1.py:347-494)은 anchor 시퀀스만 인자로 받고 기하 스팬을 p0/p1에서 직접 계산(154-160). `anchor_artifact_from_scene`(497-503)은 scene에서 `anchors` 키 하나만 읽음. `truth` 문자열의 등장 위치를 전수 나열 — 전부 평가층(입력 검증 732-736, 오차 계산 845·883-884·909-910, permutation 572-593, 계약 선언 1578-1580)이며 추정기 내부 등장 0회.
- **가드 실증**: `GuardedScene`(596-611)은 `anchors` 외 키 접근 시 예외 — 내 selftest 재실행에서 `accessed_keys=['anchors']`로 통과.
- **permutation 실증**: 재계산 — anchor artifact digest 불일치 0/200, 전역 digest before==after, 전역 digest를 행 목록에서 독립 재계산해 일치 확인. permutation이 공시험이 아님도 확인: truth_pairs 라벨이 실제로 바뀐 장면 196/200 (나머지 4 = zero-wall 장면의 κ-복제 4개, truth pair 0개라 회전이 항등).
- **소스 봉인 실증**: 실행 전후 source manifest(도시에·C0·C1·L1·v1 산출물) mismatch 0. 봉인 추정기 파일 sha256 `633c5ee1…`이 L1 manifest·L1b manifest·현재 디스크 3곳 동일 — **두 루프 반복이 같은 비트의 추정기를 썼다**. sealed_configuration(τ=log1.05, HIGH 0.75, consensus 0.80, min_independent 3, 5% 정확도 기준)도 v1/L1/L1b 결과 JSON 3곳 동일 — "봉인 밴드 불이동"의 코드 측 방증. **성립.**

### V6. 주장 ⑥ — 교란 4종 상승 0건 + 역방향 전이 티켓 수리

800개 교란 진단(200장면×4종) 전수 재계산: unit/overall/reference 상태 상승 + confidence 상승 = **전 조합 0건**. ticket 재계산 `v2_confidence_or_status_increased_count=0`(v1 기준선 26 대비), scale_estimate_unchanged 4종 모두 200/200. 저널 세부 주장 "stale_override HIGH→LOW 48건, 역방향 0건"도 재계산 일치: {HIGH→HIGH 112, HIGH→LOW 48, LOW→LOW 40} — 48 = 앵커 5개 장면 12개×4스케일(5개 중 1개가 오염되면 합의 가중 4/5×min(1,4/5)=0.64<0.75로 강등되는 봉인 공식의 예측과 정확히 부합; 앵커 분포 {2:10, 5:12, 6:11, 7:5, 8:12} 재확인). **성립.**

### V7. 주장 ⑦ — 결정적 재현

- selftest 재실행: L1b **17/17 PASS**(내장 봉인 C1 6/6 포함), 독립 실행 C1 6/6, C0 PASS, L1 17/17 (`lens3_work\selftest_*.txt`). 커밋된 c1v3의 selftest 블록(17/17)과 transcript까지 일치(byte-diff에서 selftest 리프 차이 0).
- 결정성 실측: 위 V0 — 장면 200개·c0v3는 재실행 간 바이트 동일, 수치 페이로드 전체 동일, 차이는 실행시간·타임스탬프·경로 반향뿐. 난수원 부재를 코드로 확인 — 4개 스크립트 전부에서 `random` 모듈·시계 기반 난수 0회, 모든 변동은 선언된 시드의 sha256 파생(C0.seed_for_index/seed_fraction, 교란 배정 506-516, L1b 모집단 분할 116-133 — 분할 규칙을 독립 재계산해 single_span_indices 일치 확인). **실질 성립** (문구 단서는 F1).

### 부가 — 하드코딩 부재

결과 수치(0.80·1.0·0.0403·0.000212 등)의 리터럴이 4개 스크립트 어디에도 없음(전문 정독). 존재하는 상수는 봉인 설정(0.75/0.80/log1.05/3/0.05)과 기하 좌표뿐. V0-2(커밋 장면→봉인 추정기→커밋 수치의 완전 재유도)가 하드코딩 가능성을 원천 배제.

---

## 검증하지 못한 것 (정밀 표기)

- 저널 인용 커밋 해시들(git 금지 — F3).
- 오케스트레이터 자신의 재실행이 어느 디렉토리·어느 파일 집합 대상이었는지(F1의 문구 판정은 내 실측 기준).
- 도시에 조문 해석의 전면 대조(SEALS 시야 소관) — 본 보고는 주장에 인용된 게이트 조문(758·759·787-790행)의 존재와 수치 대응만 확인.
- evidence.xlsx의 시각적 렌더 품질(구조·셀 값만 검증).

## 재실행 산출물 목록 (`lens3_work\`)

selftest_l1b/c1/c0/l1.txt · run1/run2_stdout.txt · rerun1\(2차 실행 산출물) · run1_snapshot\(1차 스냅샷) · compare_artifacts.py · consistency_check.py · hash_compare.json · json_diffs.txt · report_diff.txt · xlsx_diff.txt · consistency_detail.json

---

VERDICT: CONFIRM — 전량 재실행·독립 재유도·전수 재계산에서 주장 ①~⑥이 정확히 재현되고 숨은 진리 접근·하드코딩·수치 드리프트가 0건이며, 유일한 흠은 ⑦의 "바이트 동일" 문구가 실행시간·타임스탬프 필드(수치 무관)를 단서 없이 포괄한 낮은 심각도의 표현 과대뿐이다.
