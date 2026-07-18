# lens2 (회귀 충실도) — L1c 루프 종결 주장 사슬 검증 보고서

- 검증관: 사슬 검증단 2차 함대 lens2 (REGRESSION FIDELITY)
- 검증 일시: 2026-07-19
- 시야: selftest에 편입된 live counterexample이 1차 함대 `chainverify_L1b\lens2_stats.md` F1의 기전과 충실히 일치하는가(축약·스트로맨화 여부), F1 재현 절차로부터의 독립 재구성이 원본·C1v4 양쪽에서 L1c 회귀 표(before/after 4행)와 수치 일치하는가.
- 방법: F1 원문·원본 추정기·C1v4 코드 행 단위 정독 + **F1 절차로부터 반례 독립 재구성·재실행**(원본은 repo 경로에서 독자 import, selftest 코드 경유 없이) + REPORT 표·selftest 함수 출력·c1v4_results.json 저장 기록 3중 대조 + 사슬 무결성 스팟체크. 모든 기존 산출물 READ-ONLY, 쓰기는 `lens2_work\`에만. 재현: `lens2_work\reconstruct_counterexample.py` → exit 0, **46/46 체크 PASS** (전체 덤프 `lens2_work\reconstruction_full.json`).

---

## 0. 결론 요약

selftest의 live counterexample은 F1의 축약본이 아니라 **F1 재현 절차 그 자체**다 — 동일 장면 파일(바이트 고정 확인), 동일 봉인 교란 생성기(함수 동일성 확인), 동일 결정적 인자. 본 검증이 F1 문서 절차만으로 독립 재구성한 반례를 원본(repo 사본)·C1v4 양쪽에 실행한 결과, **회귀 표 4행의 8필드 전부가 정확히 재현**되었고, 기전(ratio-outlier/span-inlier 잠입 → reference 지지 3→4 부양 → 0.75 문턱 돌파)과 가드의 격리 대상(주입 핸들 정확히 1건)이 provenance 수준에서 일치했다. 스트로맨화의 증거 없음.

---

## 1. F1 기전 ↔ selftest 반례 구성 대조 (충실성)

F1 = `reports\e2\chainverify_L1b\lens2_stats.md` §2 F1 (48~51행). selftest = `feyerabend_c1_v2.py` `counterexample_regression()` (488~539행).

| 구성 요소 | F1 재현 절차 (원문) | selftest 구현 | 일치 |
|---|---|---|---|
| 입력 장면 | "v1 장면 `…\feyerabend_c0\scenes\scene_001_k1000.json`" (48행) | `V1_COUNTEREXAMPLE_SCENE` 동일 절대경로 (v2 28~30행), 저장 기록 `selftest.counterexample.scene`도 동일 | 일치 (B2·E2) |
| 교란 | "`C1.apply_corruption(anchors, "single_outlier", base_id)` 적용" (48행) | `apply_corruption(scene["anchors"], "single_outlier", str(scene["base_scene_id"]))` (v2 490~492행); `v2.apply_corruption is ORIGINAL.apply_corruption` — 봉인 원본의 함수 객체 그대로 재수출(v2 85행), 재구현 아님 | 일치 (B0·B3) |
| 원본 측 추정기 | 봉인 코드 그대로 import (F1: "봉인 코드 그대로 import") | `ORIGINAL.fit_anchor_model` — cells 사본 import (v2 27·50행). cells 사본 sha=`633c5ee154eb3b86…` = repo 원본 = **F1이 기록한 봉인 sha와 동일 프리픽스** | 일치 (A1·A2) |
| 판정 필드 | status·reference_status LOW→HIGH 역상승, unit_status LOW 유지, ratio conf 하락 | passed 조건: 원본 status 상승=1 ∧ 원본 ref LOW→HIGH ∧ v4 상방 4필드 합 0 ∧ v4 ref LOW 유지 ∧ v4 ref_n·ref_bins 불변 (v2 518~528행) | 일치 (§5 주석 1) |

**교란 인스턴스의 실질** (독립 재구성 실측): 장면은 DIM anchor 3개(`F001_ANCHOR_DIM_A_0/1/2`), base_scene_id=`feyerabend_c0_001`, κ=1000. 생성기는 A_1을 복제해 `__OUT_ac85e338` 핸들로 주입 — p0·p1 동시 평행이동이므로 **span 1,000,000.0 → 1,000,000.0 불변**(span-inlier), display_value ×10이므로 **log-ratio 편차 2.302585 ≫ 허용오차 0.048790**(ratio-outlier). 이것이 F1 51행의 기전 서술("ratio 공간에서는 outlier지만 span 공간에서는 inlier") 그대로이며, 합성 캐리커처가 아니라 v1 코호트 26건을 낳은 **생산 교란 생성기의 결정적 출력**이다(원본 feyerabend_c1.py 550~568행: `deterministic_index` + sha 기반 shift).

---

## 2. 독립 재구성 실측 — 회귀 표 4행 수치 대조

본 검증 실행(원본은 **repo 경로** `tools\e2\cells\feyerabend_c1.py`에서 독자 로드 — selftest가 쓰는 cells 사본과 무관한 경로) 대 REPORT.md 34~39행 표:

| 행 | 본 검증 재계산 (conf / status / unit / ref / ref_conf / ref_n / ref_bins / guarded) | REPORT 표 | 판정 |
|---|---|---|---|
| original before | 0.6 / LOW / LOW / LOW / 0.6 / 3 / 3 / 0 | 동일 | 일치 |
| original after | 0.44999999999999996 / HIGH / LOW / HIGH / 0.8 / 4 / 4 / 0 | 0.45 표기(반올림, §5 주석 2) 외 동일 | 일치 |
| C1v4 before | 0.6 / LOW / LOW / LOW / 0.6 / 3 / 3 / 0 | 동일 | 일치 |
| C1v4 after | 0.44999999999999996 / LOW / LOW / LOW / 0.6 / 3 / 3 / 1 | 동일 | 일치 |

- 파생 카운트: 원본 status 상승 1건, C1v4 상방 {confidence_score:0, status:0, unit_status:0, reference_status:0} — REPORT 41~42행과 일치 (체크 D2·D3).
- F1 원문 수치(49~50행: before LOW ref 0.6000/3/3 → after HIGH ref 0.8000/4/4, unit LOW 유지, ratio conf 0.60→0.45)와도 전 필드 일치 — **즉 L1c의 회귀는 F1의 라이브 반례를 수치 손실 없이 승계했다**.
- 3중 대조: 본 재계산 == `counterexample_regression()` 라이브 재호출 출력(E1·E3) == c1v4_results.json 저장 기록 2곳(`selftest.counterexample`·`selftest.tests[17].detail`, 상호 동일 — E4~E7). REPORT 표는 이 기록의 렌더링임을 코드로 확인(loop_l1c.py 667~675행).

---

## 3. 기전 세부 실측 (provenance 수준)

| 검사 | 실측 | 체크 |
|---|---|---|
| 원본이 주입 outlier를 reference inlier로 수용 | orig_after `reference_inlier_handles` = [A_0, A_1, **A_1__OUT_ac85e338**, A_2] | C1 |
| 동일 anchor가 ratio 공간에선 outlier | orig_after `ratio_outlier_handles` = [A_1__OUT_ac85e338] | C2 |
| 지지 부양 | ref_n 3→4, ref_bins 3→4 | C3 |
| 문턱 돌파 | ref_conf 0.6 < 0.75 ≤ 0.8 (HIGH_CONFIDENCE_THRESHOLD=0.75, 원본·v2 상수 동일 — B1) | C4 |
| 가드 격리의 정밀성 | v2_after `reference_rejections` = 정확히 1건, 핸들=주입 핸들, reason=`ratio_space_outlier_guard`, ratio_class=`outlier` | C5 |
| v2 reference 지지 불변 | v2_after ref inliers = v2_before의 [A_0, A_1, A_2] 그대로 | C6 |
| 청정 장면 과차단 없음(이 장면 한정) | v2_before guarded_rejection_count=0, 전 필드 원본 before와 동일 | C7 |

원본 코드에 가드 부재(feyerabend_c1.py 402~412행: annotation_scale 거절만 존재), v2에서 가드 블록 신설(feyerabend_c1_v2.py 164~197행)임을 행 단위로 확인 — 회귀가 겨누는 코드 차이는 정확히 그 가드다.

---

## 4. 사슬 무결성 스팟체크 (본 시야 의존 파일)

| 파일 | 실측 sha256 (프리픽스) | 대조 기준 | 판정 |
|---|---|---|---|
| repo 원본 feyerabend_c1.py | `633c5ee154eb3b86` | F1 47행 기록 봉인 sha와 동일 | 무수정 (A1) |
| cells 사본 feyerabend_c1.py | 동일 | repo와 바이트 동일 | 무수정 (A2) |
| scene_001_k1000.json | `1da8cc877442541e` | v1 results.json 내장 manifest 2곳(before/after files[7]) — **L1c 이전 기록** — 과 일치 | 무수정 (A4) |
| lens2_stats.md (F1 문서) | `6cb7a87434c8752b` | c1v4_results.json `source_readonly_manifest`가 고정한 값과 현재 디스크 일치 — L1c가 실행 중 참조한 F1 문서 = 본 검증이 읽은 문서 | 무수정 |
| L1c 산출 6종 (v2·loop·prereg·evidence·c1v4·replay_delta) | — | REPORT.md 124~129행 자기 해시 표와 전부 일치 | 사후 편집 부재 (A3×6) |

---

## 5. 주석 (판정을 뒤집지 않는 관찰)

1. **passed 술어의 범위**: selftest의 통과 조건은 F1 서명의 핵심부(원본 LOW→HIGH 상승, v4 상방 0, v4 ref 지지 불변)를 assert하나, 원본 측 ref_n 3→4·ref_bins 3→4·ref_conf 0.8의 **구체값**은 assert하지 않고 스냅샷으로 기록·공개만 한다. 그 값들은 본 검증의 독립 재구성으로 전부 확인되었으므로 실해 없음 — 다만 향후 장면 파일이 바뀌면 술어는 더 약한 반례로도 통과할 수 있으니, 장면 sha를 술어에 고정하면 더 단단해진다(권고, 결함 아님).
2. **0.45 표기**: REPORT 표의 0.45·0.6은 저장값 0.44999999999999996 등의 표시 반올림. 기계 기록(c1v4_results.json)은 전체 정밀도로 보존되어 있고 본 재계산과 1e-12 이내 일치(실제로는 동일 부동소수).
3. **범위 한정**: 26→0 코호트 귀속은 lens3, 300종 속성 시험·이중 봉인 실질은 seat4 시야다. 본 보고서는 그에 대한 판정을 포함하지 않는다. C1v4의 청정-장면 무과차단 확인(C7)도 이 장면 1건에 한정된다(일반 과차단 탐색은 lens1).

## 6. 수치 출처 (FM9)

본 보고서의 모든 수치는 `lens2_work\reconstruct_counterexample.py` 실행 출력(exit 0, 46/46 PASS, stdout의 CHECK 라인·스냅샷 라인)이거나 경로·행번호를 병기한 산출물 인용이다. 전체 기계 기록: `lens2_work\reconstruction_full.json`. 원본 산출물·repo 무수정, git 미사용, 서브에이전트 미사용.

---

## 7. 판정

시야 질문 — "live counterexample이 F1 기전과 충실히 일치하는가, 독립 재구성이 회귀 표와 수치 일치하는가" — 에 대해: 반례는 F1 절차의 문자 그대로의 편입이고(동일 장면·동일 봉인 생성기·동일 인자, 전부 해시·함수 동일성으로 확인), 독립 재구성 수치는 회귀 표 4행·selftest 출력·저장 기록과 3중으로 정확히 일치하며, 기전의 인과 사슬(span-inlier 잠입→지지 부양→문턱 돌파→가드 격리)이 provenance 수준에서 재현되었다. 축약·스트로맨화의 증거는 발견되지 않았다.

VERDICT: CONFIRM
