# 시야2 (통계/방법론) — 사슬 독립검증 보고서: C0→C1→L1→L1b 목표 도달 주장

- 검증관: 독립 검증단 시야2 (STATISTICS/METHODOLOGY)
- 검증 일시: 2026-07-19
- 방법: 도시에 원문 행 단위 대조 + 봉인 코드 정독 + **전량 독립 재실행**(샌드박스 사본, `D:\runs\e2_program\chainverify_L1b\rerun\`) + c1v3_results.json 200 장면 전 행 재계산 + v1 장면에 대한 봉인 추정기 라이브 재현 실험. 원본 산출물 무수정 (쓰기는 본 검증 디렉토리에만).
- 이 보고서의 모든 수치는 본 세션의 재계산/재실행 출력이거나, 경로·행번호를 병기한 산출물 인용이다.

---

## 0. 결론 요약

봉인 게이트 **수치 7종은 전부 독립 재계산으로 재현**되었고, **봉인 밴드의 이동은 어느 반복에서도 발견되지 않았으며**, 루프 경로(v1 실패 정직 보고 → L1 기각 → L1b 수리)의 판정 논리도 건전했다. 그러나 주장 문안 중 두 곳이 실측으로 **반증**된다:

1. **⑥의 "(역방향 전이 티켓 수리 확인)" — 허위.** 결함 기전은 수리되지 않았다. 동일한 봉인 추정기 코드가 v1 장면을 입력받으면 **지금도** single-outlier 교란에서 status LOW→HIGH 역상승을 일으킨다(본 검증에서 라이브 재현). L1b에서 0건이 된 것은 코드 수리가 아니라 **결함을 발현시키지 못하는 모집단으로의 교체** 때문이다.
2. **⑦의 "재실행 바이트 동일" — 문자 그대로는 성립 불가능.** c1v3_results.json은 실행시간 필드(`runtime.loop_wall_seconds` 등)를 내장하므로 어떤 재실행도 이 파일을 바이트 동일하게 만들 수 없다. 도시에가 실제로 봉인한 재현 밴드는 "metrics digest 동일"(731행)이며 **그 밴드는 본 검증 재실행으로 충족 확인**되었다(장면 200/200 바이트 동일, 계량 필드 전부 동일).

게이트 실질은 살아 있으나 주장은 문안 그대로 검증을 통과할 수 없다 → 최종 판정은 문서 말미.

---

## 1. 게이트 수치 × 도시에 봉인 조문 1:1 대조

도시에 = `D:\dev\99_tools\autocad-sdk-router\reports\e2\dossiers\feyerabend_P2.md` (이하 행번호는 이 파일). L1·L1b가 읽은 도시에 sha256은 동일함을 두 manifest에서 확인: `3ae87588d52b227a…` (c1v2_results.json·c1v3_results.json 각 source_readonly_manifest).

| # | 주장 | 도시에 봉인 조문 (원문 인용) | 주장값 | 본 검증 재계산 | 판정 |
|---|---|---|---|---|---|
| ① | HIGH 커버리지 4스케일 각각 0.80 (게이트 ≥0.60) | 788행: "네 scale 각각 HIGH coverage 0.60 이상" | 0.80 ×4 | κ∈{0.001, 0.01, 1, 1000} 각각 HIGH 40/50 = **0.8000** (분모 = 그 스케일 전 장면 50, single-span 10·sentinel 포함) | 수치 일치, §3 증거력 주석 |
| ② | HIGH 정확도 1.0 (게이트 ≥0.95, 상대오차 5%) | 787행: "HIGH subset의 95% 이상이 true scale 대비 상대오차 5% 이하" | 1.0 | HIGH 160/160 전부 \|ŝ/s−1\| ≤ 0.05 (실측 최대 상대오차 3.1e−15) | 일치 |
| ③ | mutation family 11/11 (단일-스팬 10 복원) | 758행: "지정 mutation family가 각각 최소 한 scene에 존재" + 550행: "각 scene은 최소한 다음 mutation family를 manifest에 가진다" + 552~561행 불릿 10개 (561행: "단일·다중 reference span 영역") | 11/11 | 11 가족 전부 ≥1: single_reference_span_region=10, multiple=40, 나머지 9 가족 21/25/50/50/50/50/49/1/1 (재실행 stdout 동일) | 일치, §4.1 분할 정당성 확인 |
| ④ | 충실도 KS 0.0403 / TV 0.000212 (게이트 0.20/0.10) | 759행: "제안 fidelity gate: KS ≤ 0.20, TV ≤ 0.10" (752행: "real-vs-synthetic entity/geometry distribution KS와 TV", 746행: κ=1 장면 대상) | 0.0403 / 0.000212 | 독립 재계산 **KS 0.0402878554 / TV 0.000211914583** — v1 장면과 L1b 장면 양쪽에서 동일 | 일치, §3 증거력 주석 |
| ⑤ | 진리 무접촉 (접근 키 anchors 단독, permutation 전후 digest 동일) | 789행: "pair-label permutation 전후 anchor digest 완전 동일" + 431~432행 불변식: "FIT_ANCHOR_MODEL 호출 그래프에는 truth_pairs …가 없어야 한다 / pair label 파일을 순열화해도 anchor와 prediction bytes가 같아야 한다" | digest 동일 | 코드 확인: 추정기 진입점은 `scene["anchors"]` 단독 (feyerabend_c1.py 497~503행), selftest `truth_key_access_guard: accessed_keys=['anchors']`; permutation 196/200 장면 라벨 변경, digest before==after `357de452…` — 본 재실행에서 동일 재현 | 일치 |
| ⑥ | 교란 4종에서 신뢰도·상태 상승 0건 (+ "역방향 전이 티켓 수리 확인") | 774행: "복제, stale override, suffix 제거, 한 개 outlier를 deterministic mutation으로 추가" + 782행: "corruption 전후 status transition"(지표) + 790행: "단일 강한 outlier가 들어가도 scale mode가 바뀌지 않거나 status가 LOW로 내려감" | 상승 0건, 티켓 수리 | 전 장면(200)×4종 재계산: confidence 증가 0, status/unit_status/reference_status 상승 0 — **측정치는 사실**. 그러나 "티켓 수리"는 **반증** (§2 F1) | 측정 일치 / **문언 반증** |
| ⑦ | 결정적 재현 (재실행 바이트 동일) | 731행: "같은 seed/manifest 재실행 시 metrics digest 동일" | 바이트 동일 | 샌드박스 전량 재실행: 장면 **200/200 바이트 동일**, 계량 필드 전 항목 동일. 파생 4파일은 바이트 상이 — 차이는 임베디드 경로·실행시간·그 해시 연쇄뿐(c1v3 17 leaf, 계량 leaf 0) | 도시에 밴드(metrics digest) 충족 / **문언 반증** (§2 F2) |

봉인 상태 규칙 대조(코드 ↔ 도시에): 222행 "unit_status=HIGH: 독립 ratio anchor가 3개 이상, 합의 가중치 비율이 0.80 이상, log MAD가 log(1.05) 이하, C_a≥0.75" ↔ feyerabend_c1.py 42~47행 `RANSAC_LOG_TOLERANCE=log(1.05)`, `HIGH_CONFIDENCE_THRESHOLD=0.75`, `CONSENSUS_THRESHOLD=0.80`, `MIN_INDEPENDENT=3`, `ACCURACY_RELATIVE_ERROR=0.05` — **완전 일치**. 423행 봉인표 "HIGH confidence 0.75 … real 30을 보기 전에 동결"과도 일치.

---

## 2. 발견 사항 (심각도순)

### F1 · [HIGH — 주장 문언 반증] "역방향 전이 티켓 수리 확인"은 허위 — 결함은 잠복 상태로 살아 있다

**주장 문언**: "⑥ 교란 4종에서 신뢰도·상태 상승 0건(역방향 전이 티켓 수리 확인)". 저널은 더 강하게 단언한다 — PROGRAM_JOURNAL.md 432행: "역방향 전이 26건 — 은 이번에 0건으로 수리된 것이 확인됐다. **오히려 교란은 이제 신뢰도를 내리는 방향으로만 작동한다**".

**사실 관계**:
- 티켓의 원 정의는 추정기 **로직 결함**이었다. 저널 298행: "신뢰도 보정 **로직의 결함**으로 별도 기록"; v1 REPORT(reports\e2\cells\feyerabend_c1\REPORT.md) 140행이 기전까지 정확히 진단했다: "추가 anchor의 geometry span이 reference 독립성 수를 늘려 reference/overall status가 26/200에서 LOW→HIGH로 변했다".
- 세 반복이 실행한 추정기 코드는 **동일 파일·동일 sha**다: feyerabend_c1.py `633c5ee154eb3b86…` (L1·L1b manifest 공히; v1 results.json의 sealed_configuration도 동일 상수·동일 공식 문자열). 즉 **로직은 한 줄도 바뀐 적이 없다**.
- **라이브 재현 (본 검증, 봉인 코드 그대로 import)**: v1 장면 `D:\runs\e2_program\cells\feyerabend_c0\scenes\scene_001_k1000.json`에 `C1.apply_corruption(anchors, "single_outlier", base_id)` 적용 →
  `before: status=LOW ref=LOW ref_n=3 ref_bins=3 ref_conf=0.6000` →
  `after: status=HIGH ref=HIGH ref_n=4 ref_bins=4 ref_conf=0.8000` (unit_status는 LOW 유지, ratio confidence는 0.60→0.45로 하락).
  기전: 주입된 outlier는 ratio 공간에서는 outlier지만 span 공간에서는 inlier여서 reference 합의의 n_independent·spatial bin을 늘리고, 점수 공식 `consensus×exp(−mad/τ)×min(1,n/5)×min(1,bins/3)` (feyerabend_c1.py 320~325행)이 0.60→0.80으로 올라 0.75 문턱을 넘는다. `status = reference_status` (440행)이므로 보조 status가 HIGH로 표시된다.
- L1b에서 0건이 된 이유는 코드가 아니라 모집단이다: anchor-rich 장면은 **서로 다른** span 8개로 설계되어 reference 합의(가중치 ≥0.80)가 애초에 성립하지 않고(전 200 장면 reference_status=LOW — L1b REPORT.md 3950행), single-span 장면은 anchor 2개로 문턱(n≥3) 미달이다. 즉 **결함을 발현시킬 수 있는 입력 형태가 모집단에서 제거**된 것이다.

**판정**: 교란 전이 표가 지지하는 명제는 "L1b 모집단에서 역상승 0건"까지다. "티켓 수리"·"이제 내리는 방향으로만 작동"이라는 무조건 명제는 반증되었다(위 재현이 반례). 참고로 도시에 790행의 봉인 밴드 자체는 OR-절("scale mode가 바뀌지 않거나 status가 LOW로")이어서 v1에서도 mode 불변(200/200)으로 충족되었으므로 **봉인 밴드 위반은 아니다** — 이것은 게이트 결함이 아니라 **판정문(주장)의 무결성 결함**이며, reference_status 경로를 소비하는 다운스트림(도시에 218행: GRID-only reference HIGH 경로)이 생기는 순간 실질 위험이 된다.

### F2 · [MEDIUM-HIGH — 주장 문언 반증] "재실행 바이트 동일"(⑦)은 파생 산출물에서 원리적으로 불가능

- c1v3_results.json은 `runtime.loop_cpu_seconds=2.78125`, `runtime.loop_wall_seconds=2.8723753…` 등 실행시간 필드를 내장한다. wall-clock 마이크로초가 재실행에서 일치할 수 없으므로 이 파일의 바이트 동일 재현은 물리적으로 불가능하고, 이 파일 sha를 인용하는 REPORT.md·연쇄 산출물도 마찬가지다.
- 본 검증의 전량 재실행(사본 디렉토리) 결과: scenes_v3 **200/200 파일 바이트 동일**; c0v3_numbers.json 차이 1 leaf(`contract.write_root` 경로), c1v3_results.json 차이 17 leaf(경로 1·실행시간 4·그로 인한 해시/바이트 연쇄 12) — **계량 필드 차이 0**. REPORT.md 차이 5행(전부 경로/해시 연쇄).
- 도시에가 봉인한 재현 요건은 731행 "같은 seed/manifest 재실행 시 **metrics digest** 동일"이며, 이 밴드는 충족된다. C1 v1 단계의 저널(292행)은 "수치가 전부 동일하게 재현됐다(**파일에 남는 실행시간 기록만 서로 달랐다**)"로 정확히 한정했으나, L1b 단계(433행 "재실행한 결과도 바이트 단위로 동일했다")와 검증 대상 주장 ⑦에서 이 한정이 탈락했다. 주장 문안이 증거보다 강하다.

### F3 · [MEDIUM — 증거력/프레이밍] 커버리지 0.80은 측정 결과가 아니라 설계 상수이며, "4스케일 각각"은 독립 확인 4회가 아니다

- L1b 모집단은 게이트를 보고 설계되었다 — PACKET_loop_L1b_mixed_population.md 12행: "C1의 HIGH 커버리지 게이트는 scale당 0.60이므로 50 base 중 **최대 40%가 비-HIGH여도 게이트와 양립**한다". anchor-rich 40 장면은 봉인 공식상 HIGH가 필연이고(anchor 5~8·독립 span·bins≥3 → 완전 합의에서 score=1.0 ≥ 0.75), single-span 10 장면은 HIGH가 구조적으로 불가능하다(anchor 2 < MIN_INDEPENDENT 3, 도시에 222행·feyerabend_c1.py 339행). 따라서 **도달 가능한 coverage의 상한이 정확히 0.80**이고, 관측값 0.80은 그 상한의 실현이다. 게이트 0.60 대비 "여유"는 측정된 성능 마진이 아니라 40/10이라는 배정 선택이다.
- 4스케일 × 0.80의 상관 구조: HIGH가 된 base 집합이 **네 스케일에서 완전히 동일한 40개**임을 전 행 재계산으로 확인했다. 같은 base의 네 스케일 사본은 seed·topology를 공유하므로(도시에 768행) 이는 예상된 설계다. 통계적으로 "0.80이 네 번 나왔다"는 하나의 사실(스케일 불변성)이지 네 개의 독립 확인이 아니다. 단, 도시에가 이 게이트에 부여한 목적 — 794행 킬 조건 "scale별 confidence coverage가 **한 방향으로 붕괴**하면 kill" — 에 대해서는 유효한 검사다(붕괴 없음: 0.80/0.80/0.80/0.80).
- 같은 맥락에서 ② 정확도 1.0도 무부하 시험이다: 합성 anchor가 정확 합의로 구성되므로 HIGH subset 오차는 부동소수 한계(최대 3.1e−15)이고, 5% 게이트는 10^13 배 여유로 통과한다. 이 수치들은 "계측기가 설계대로 조립되었는가"의 확인이지 성능 증거가 아니다 — 주장이 이를 성능 마진처럼 인용하는 것은 프레이밍 과잉이다.
- 분모 자체는 정당함을 확인: per-scale coverage = HIGH_n / (그 스케일 전 장면 50) — feyerabend_c1.py 1028행 `len(scale_high)/len(scale_rows)`; single-span 10과 sentinel 2가 분모에 정직하게 포함된다(전 행 재계산 일치). HIGH 판정 필드도 v1 sealed_configuration에 `"primary_confidence_bin": "unit_status"`로 사전 봉인되어 있어(26건 역상승이 난 보조 `status` 필드와의 지표 바꿔치기 없음) 지표 쇼핑이 아니다.

### F4 · [MEDIUM-LOW — 증거력] 충실도 게이트 ④는 루프 변경에 대한 신규 증거가 아니며, TV 성분은 구성상 자동 통과다

- 세 반복(v1·L1·L1b)의 KS/TV가 12자리까지 동일한 이유를 구조로 확인했다: anchor는 장면 JSON의 `entities` 밖 별도 배열이고, 루프는 anchor만 바꿨으며 `entities`·`entity_mix`는 v1↔L1b 간 **완전 동일**이다(scene_000_k1 직접 대조). 충실도는 entities/segments만 소비하므로(feyerabend_c0.py 1288~1292행) 루프가 바꾼 것(anchor 구조)을 **볼 수 없는** 지표다. 따라서 ④는 L1b의 신규 통과 증거가 아니라 v1 자격의 상속이다 — 저널 430행이 "충실도는 v1과 완전히 동일했다"로 공개하므로 기만은 아니나, 주장 ④를 루프 검증 증거로 세는 것은 이중 계상이다.
- TV 0.000212의 성격: 합성 entity 비율이 실측 참조 분포(fidelity_M_v1_tv.json `real_mix`, 실측 28,121 entities)와 카테고리별 |Δp| ≤ 0.00008로 일치한다(n=8000). iid 표본이라면 표준편차가 ~0.005 수준이므로 관측 편차는 그 1/60~1/500 — 생성기가 참조 비율을 **쿼터 방식으로 복제**하도록 설계되었다는 뜻이다. 즉 TV 게이트는 "생성기 샘플러가 자기 목표 분포를 재현하는가"의 자기 충족 검사에 가깝다. 실질 정보는 KS 0.0403(평행쌍 offset 히스토그램) 쪽에 있다. 재계산은 양쪽 모두 주장값과 일치(KS 0.0402878554 / TV 0.000211914583). 참조 파일 자체(fidelity_M_v2.json `real_summary`)에 source 메타데이터가 비어 있는 점(source=None)은 참조 추적성의 미세 갭.

### F5 · [LOW — 형식] 도시에 740행의 prereg 이중 봉인 형식 요건 미이행 (실질 봉인은 성립)

- 740행: "모든 threshold는 실행 전 **prereg.json과 evidence.xlsx PREREG sheet에 동시에 봉인**한다" (593행 동지). 실측: v1 C1 evidence.xlsx 시트 = {scale_confidence, score_bins, corruption_transitions, pair_label_digest, README}, L1b evidence.xlsx 15 시트 — **어느 쪽에도 PREREG 시트 없음**, 셀 디렉토리에 prereg.json 없음.
- 다만 실질 봉인은 세 겹으로 성립함을 확인: (i) 도시에 자체가 SoT이고 L1·L1b manifest가 sha로 고정(3ae87588 동일), (ii) 봉인 상수가 코드에 하드코딩(feyerabend_c1.py 42~47행)되고 세 반복 동일 sha, (iii) v1 results.json `sealed_configuration`에 공식 문자열까지 기록. **밴드 값의 이동은 없다**(아래 §5). 따라서 형식 위반이되 실해는 없음 — 후속 셀(C2)에서는 조문대로 PREREG 시트를 만들 것을 권고.
- 부수 갭: v1 산출물의 contract는 도시에를 경로로만 참조하고 sha 고정이 없다(L1부터 고정 시작).

### F6 · [LOW — 표기] L1b REPORT의 corruption 표에서 status/reference 열은 무정보

- "Corruption 4종 전이 수치" 표(REPORT.md 1827~1832행)의 `status_transition`·`reference_transition` 열은 전부 `{"LOW->LOW": 200}` — reference_status가 전 장면 LOW이기 때문(3950행에 공개)이며 유의미한 전이는 `unit_transition` 열에만 있다. 표는 정확하나, 이 두 열이 "전이 검사를 통과했다"는 인상을 주기에는 검사 대상 자체가 발현 불가능한 상태다(F1과 동근원). 검증 노트: stale_override의 `scale_same=200`은 허용오차 비교로 정당함을 확인(내 엄밀 비교로는 23 장면에서 상대 8.9e−16 변화 — 부동소수 노이즈).

---

## 3. 표본 구조·상관 분석 (시야 지정 질문에 대한 답)

- **구조**: 200 IR = base 50 × κ 완전요인 4 (도시에 545~548행 "κ∈{0.001,0.01,1,1000} … 총 200 IR", 830행 "scale은 seed가 아니라 완전요인이다"). L1b 배정: anchor-rich 40 / single-span 10, `sha256(str(seed)+':loop_l1b_population')` rank 결정적(REPORT 35~36행, selftest PASS) — 체리픽 여지 없음, single-span 지정 10개가 HIGH 정확도에 영향을 줄 경로도 없음(구조적 LOW).
- **분모 질문 답**: per-scale coverage 0.80은 **올바른 분모(그 스케일 전 장면 50)** 위에서 계산되었다. 코드(1028행)와 데이터(HIGH 40 + LOW 10 = 50/스케일) 양쪽 확인. single-span·sentinel 제외 같은 분모 조작 없음.
- **상관**: 네 스케일의 HIGH base 집합 완전 동일(재계산) — per-scale 게이트 4회는 사실상 base-수준 1개 사실의 스케일 불변성 검사. 이 목적(794행 킬 조건)에는 적합하나, 표본 크기를 "160 HIGH"로 읽는 해석은 유효 표본 40 base로 읽어야 한다.
- **평가 split 반복 개봉**: 도시에 830행은 200 IR을 "config 봉인 뒤 한 번 여는 평가 split"으로 규정한다. 루프는 이 모집단을 세 번(v1→L1→L1b) 재설계·재개봉했다. 완화 요인: (i) 바뀐 것은 추정기·밴드가 아니라 장면 공장뿐(코드 sha 동일), (ii) 830행의 일회 개봉 규율의 보호 대상인 C2(이론 판별)는 아직 닫혀 있고, (iii) 각 반복이 패킷으로 사전 설계·공개되었다. 잔여 위험: C1 게이트 통과는 "모집단을 게이트가 만족되도록 재설계한 3회차" 결과이므로, C2 개시 시 이 모집단 구성(40/10)을 다시 손대는 것은 금지되어야 한다(아니면 계측기 자격의 근거가 소급 훼손된다).

---

## 4. L1 기각·L1b 수락 판정의 방법론 건전성

### 4.1 L1 기각 — SOUND

- 근거 조문이 사전 봉인이었다: 758행(가족별 ≥1 scene) + 550~561행(가족 목록). 11-가족 분할(불릿 "단일·다중 reference span 영역"의 2분할)은 **v1 시점에 이미 동결** — v1 coverage_numbers.json(sha `f5c17b60…`, L1·L1b manifest 공히 고정)에 single_reference_span_region=25 / multiple=25로 존재. L1b REPORT 13행이 분할을 명시 공개. 분할은 요구를 강화하는 방향(각각 ≥1)이므로 검증에 보수적이다. **사후 가족 재정의 없음**.
- L1은 HIGH 게이트를 채웠으나(coverage 1.0) single_reference_span_region 25→0 — 오케스트레이터가 "한 게이트를 채우려다 다른 봉인 요구를 조용히 희생"(저널 407행)으로 기각. 게이트-충족 반복을 스스로 기각한 것은 사슬-전체 검증 원칙의 올바른 적용이다.

### 4.2 L1b 수락 — 절차적으로 SOUND, 단 F1·F2·F3의 문언·프레이밍 결함

- 수리 방향이 원칙적이다: L1 패킷 5행 "밴드는 봉인이라 못 움직인다 — 입력(장면의 앵커 풍부도)을 수리" — 밴드 불가침을 명시한 채 입력만 수정. 셀에는 판정 출력이 금지되었고(두 패킷 공통: "수치만 — 목표/게이트 판정 출력 금지") 판정은 오케스트레이터가 도시에와 대조 — 역할 분리가 유지되었다.
- v1의 실패 보고는 정직했다: v1 REPORT 46행 `HIGH_coverage | 0`, 106행 LOW→HIGH 26 원수치 보존, 138·140행에 원인 자가진단. 상태 올려 부르기 없음.
- 수락의 결함은 §2와 같다: 커버리지 마진의 성능-증거 프레이밍(F3), "티켓 수리" 단언(F1), "바이트 동일" 단언(F2). 수락 자체를 뒤집을 봉인 밴드 위반은 발견하지 못했다.

---

## 5. 사후 밴드 이동 점검 — 이동 없음

| 밴드 | 도시에 | v1 sealed_configuration | 코드 상수 (세 반복 동일 sha) | 패킷 인용 | 이동 |
|---|---|---|---|---|---|
| HIGH coverage ≥0.60/scale | 788행 | (셀 범위 밖, 판정용) | — | L1 패킷 "60% 이상", L1b 패킷 "0.60" | 없음 |
| HIGH 정확도 ≥0.95 @ 5% | 787행 | accuracy_relative_error 0.05 | ACCURACY_RELATIVE_ERROR=0.05 | L1 패킷 "정확도 게이트(봉인 밴드는 그대로)" | 없음 |
| HIGH 문턱 0.75 / 합의 0.80 / logMAD log(1.05) / n≥3 | 222·422~424행 | 동일 4값 + 공식 문자열 | 42~47행 동일 | — | 없음 |
| KS ≤0.20 / TV ≤0.10 | 759행 | — | — | — | 없음 |
| permutation digest 동일 | 789행 | — | — | — | 없음 |
| 재현: metrics digest 동일 | 731행 | — | — | — | 없음 (⑦ 문언만 과잉) |
| corruption "상승 0건" | **도시에에 없음** — 790행은 OR-절, 782행은 지표 나열 | — | — | L1 패킷 26~27행이 신설(방향성 위반 실측 지시) | 강화 방향 신설 — 완화 아님 |

corruption 무상승 게이트는 도시에 밴드가 아니라 루프에서 **추가된 더 엄격한** 검사임을 명시해 둔다(완화가 아니므로 밴드 이동 아님 — 다만 주장 ⑥이 이를 "봉인 게이트"처럼 병렬 나열하는 것은 출처 구분이 흐리다). 도시에 자체의 sha는 L1·L1b manifest에서 동일 고정 확인. 산출물 사후 편집 부재: L1b REPORT 3940~3944행의 자기 해시 표와 현재 디스크 파일 4종(loop_l1b.py / c0v3_numbers.json / c1v3_results.json / evidence.xlsx) sha256 **전부 일치**를 본 검증에서 확인.

---

## 6. 재실행·재계산 기록 (FM9 방지 — 수치 출처)

- 전량 재실행: `D:\runs\e2_program\chainverify_L1b\rerun\loop_l1b.py` (원본 바이트 동일 사본, CELL_DIR 상대 경로 특성으로 산출물이 rerun\에 격리) → exit 0, selftest 17/17 PASS, 최종 검증 JSON의 게이트 필드가 원본과 동일 (`high_coverage 0.8`, `high_accuracy_within_5pct 1.0`, 상승 0, 가족 11종 카운트 동일).
- 바이트 대조: scenes 200/200 동일; 파생 4파일 diff 전수 분류(§2 F2).
- c1v3_results.json 전 행 재계산: per-scale n/HIGH/정확도(§1 표), 4종 교란 × 200 장면 confidence·status·unit·reference 델타(§2), HIGH base-set 스케일 간 동일성(§3).
- KS/TV 독립 재계산: fidelity_stats.py 함수로 v1·L1b 장면 각각 계산(§1 ④, §2 F4).
- 라이브 결함 재현: §2 F1 (v1 장면 + 봉인 C1 import).
- 원본 무수정: 본 검증의 쓰기는 `chainverify_L1b\` 하위에만 발생.

---

## 7. 판정

주장을 구성 명제별로 나누면: 봉인 게이트 수치 ①~⑤ 및 ⑥의 측정부·⑦의 실질부(도시에 731행 밴드)는 **전부 독립 재현으로 확인**되고, 밴드 이동 없음·루프 경로 정직성도 확인된다. 그러나 ⑥의 "(역방향 전이 티켓 수리 확인)"은 라이브 반례로 반증되었고(결함은 봉인 코드에 잠복 — 모집단이 가린 것), ⑦의 "재실행 바이트 동일"은 산출물 구조상 성립 불가능한 과잉 문언이다. 검증 대상은 문안 그대로의 주장이며, 반증된 구성 명제를 포함한 연언은 통과시킬 수 없다. (수리 경로는 좁다: ⑥을 "L1b 모집단에서 상승 0건, 티켓은 latent — 로직 미수리"로, ⑦을 "장면 바이트 동일 + metrics digest 동일"로 재기술하면 본 시야 기준 잔여 반박 사유는 F3~F6 수준의 주석뿐이다.)

VERDICT: REFUTE — 봉인 밴드 7종의 수치·불이동·루프 정직성은 전부 재현 확인되나, ⑥ "역방향 전이 티켓 수리 확인"은 봉인 추정기에 결함이 잠복함을 라이브 재현으로 반증했고(모집단 교체로 은폐된 것), ⑦ "재실행 바이트 동일"은 runtime 필드 탓에 원리적으로 성립 불가라서, 주장 문안 그대로는 성립하지 않는다.
