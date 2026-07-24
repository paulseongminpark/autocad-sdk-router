# lens1_verdict.md — 정직 봉투 타당성 · Tier 경계 · 증인 실질 (5차 함대, fable 좌석 1)

## VERDICT: REFUTE

봉인 조문 위반이 실증됐다. v5(c1v7)는 **비독립 증거(동일 위치 중복·동일 source_span_id 공유
핸들)를 독립 지지로 이중계수**하여 위조 장면을 `unit_status` LOW→HIGH로 상승시키고 `information_
limit_record`(정직)로 인증한다. 4차의 raw_span↔기하 수리(W000002/B5)는 **실제로 동작**하지만, 그
수리는 `raw_span` 한 필드에 국한된 점(点)수리였고, 봉인 조문이 요구한 "모든 선언 필드의 값·다중도·
순서 심판"을 일반 구현하지 못했다. 그 결과 4차 (b)-class 구멍(탐지기가 정직 생성계보다 좁음)이
`source_span_id`와 교차-핸들 기하 다중도에서 재발한다.

- 봉인 조문 위반 3건 실증(아래 §2). 봉인 게이트 `violation allowed_count: 0`이 **거짓 음성**으로
  깨진다 — 위반이어야 할 상승 20종이 전부 정직으로 분류됐다.
- 부분 확인은 CONFIRM이 아니다(task.md L43). 봉투 실측성·W000002 수리 등 **살아남은 것은 §1에
  정직하게 기록**하되, 조문 위반이 하나라도 실증되면 판정은 REFUTE다.

---

## §1. 살아남은 것 (정직 보고 — 확인된 견고한 부분)

이 좌석은 파괴자가 아니라 정직한 판정자다. 다음은 재현으로 **확인된** 참이다.

1. **정직 봉투는 실측이다 (선험 아님).** 추정기 코드를 신뢰하지 않고 *독립* 측정계(내 2D 기하·내
   단위정규화·중앙값 기반 장면내 합의)로 400장면/2008앵커를 재측정한 결과, 봉인 수치를 **비트
   단위로 재현**: 최대 장면내 비율 편차 `1.4563237239633405e-13τ`(봉인값과 정확 일치),
   raw_span↔기하 불일치 `0`. 봉인 상한은 실제로 **달성**된다(scene_004_k0p001이 정확히 1.456e-13
   착지) — 아무도 안 닿는 느슨한 상한이 아니다. 봉투 구축이 측정 대상을 좁히는 self-narrowing
   흔적 없음(다중 비율공간 장면 0, 침묵 드롭된 비율 핸들 0).
   · 근거: `python probe_a_envelope.py` → probe_a_envelope.json / `probe_a2_artifact.py` →
   probe_a2_artifact.json (artifact `measured == sealed == 독립측정`).

2. **W000002/B5 (4차 lens1 결정타) 수리는 동작한다.** v5에 재실행 시 전건 경성 차단:
   W000002(CE-C geometry_ratio_break seed9), B5(raw_span 100 vs 기하 300), B5-general 모두
   `declared_field_geometry_contradiction` Tier-B, 상승 0, 정직 인증 0. 부수 canonical 의심
   B1(severe)/B2(handle collision)/B4(missing display)도 전부 Tier-B 차단.
   · 근거: `python probe_e_regressions.py` → probe_e_regressions.json.

3. **봉인·무결성.** prereg.json SHA-256 = `76AC2A58…207861`(task 계약과 일치), 7개 아티팩트
   해시 전부 REPORT.md 주장과 일치. O1/O2 무손실(강등 0·커버리지 손실 0). 증인 90건 수치
   충실도 전건 성립(15 교차검사에서 record_count·surface digest·rule_counts·inventory 전부
   재계산과 일치).
   · 근거: `Get-FileHash`(대화 로그) / probe_a2_artifact.json / probe_d_witness.json.

4. **O2 창(窓) 상승은 위반 아님.** 봉투 안 O2 display-stale(≤2.1594622082423τ) 잔차를 상승
   허용하는 것은 봉인 조문대로다. 심각 이상치를 O2 창(2.0τ·2.159τ)으로 부분교정한 장면(O01/O02)이
   정직 인증되지만, 그 잔차는 봉인 O2 봉투 *안*이고 이력-독립 원칙상 장면 자체로 판정되므로
   방어가능 — **위반으로 계수하지 않는다.** (seat4 회귀는 2.4τ를 쓰는데 이는 O2 최대(2.159)를
   넘어 Tier-B로 정확히 차단됨을 확인.)
   · 근거: probe_b_battery.json(O01/O02/O03) + loop_l1f.py:743 seat4 stale 케이스 정독.

---

## §2. 반증 — 봉인 조문 위반 (수용)

### 결함 F1 (PRIMARY): 비독립 증거 이중계수 → 위조 독립지지 제조 (manufactured independent support)

**한 줄 정의**: v5는 비율/스팬 독립지지를 *핸들 문자열*로 센다. 동일 위치(same p0/p1) 중복 앵커나
동일 `source_span_id`를 선언한 다른-핸들 앵커는, 물리적으로 하나의 측정인데도 **두 개의 독립
지지로 계수**되어 `n_independent` 2→3을 만들고 `unit_status` LOW→HIGH를 상승시킨다. 이 상승은
Tier-B 신호가 없어 `build_honest_witness`가 성공하고 `classify_upward`가 `information_limit_
record`(정직)로 인증한다.

**핵심 기전 (코드 라인)**:
- `analyze_frozen_surface`는 앵커를 `by_handle`(핸들 문자열)로 그룹핑한다(feyerabend_c1_v5.py:406,
  427). 서로 다른 핸들 = 서로 다른 그룹 = 별개 ratio_rep. 동일 기하/표시라도 dedup하지 않는다.
- `_support_policy`의 `n_independent = len(support_handles)` = 서로 다른 청정 핸들 수(v5:756,761).
- `_status`의 HIGH 게이트는 `n_independent >= MIN_HANDLES_HIGH(3)`만 볼 뿐, 공간 bin·기하
  중복·source 동일성을 보지 않는다(v5:786-791).
- 위조 중복은 raw_span==기하(정합), 동일-핸들 충돌 없음(핸들이 다름), 비율 잔차 0 → **Tier-B
  신호 0** → `classify_upward`의 `legitimate = exact and tier_B==0`이 참(loop_l1f.py:311).

**실증 (전건 착지)**:
- 배터리 20종 변주 전부 착지(rose=1, label=information_limit_record, tierB=0): 비율경로 7단위/
  4비율 + TEXT + source_span_id 공유(동일위치·상이기하) + B중복 + 2중복 + 실제
  `randomized_corruption('exact_duplicate')` + 4개 실제 코퍼스 2핸들 장면; 스팬경로 GRID 중복
  3종. → `python probe_b_battery.py` → probe_b_battery.json (`defects_landed: 20/20` 중
  O2계열 3종 제외한 manufactured-support 20종).
- 실제 봉인 코퍼스 정직 장면 scene_000(정직 2핸들)에 **실제 부패함수**
  `V4.randomized_corruption(...,'exact_duplicate',...)` 적용 → LOW→HIGH, information_limit_record.
  → probe_b3_masking.json `real_exact_duplicate_on_honest_2handle_scene_000`.
- **BRIDGE**: raw_span을 기하에 맞춰 정합 유지한 채(기하 불일치 0) 동일위치 twin만 추가 →
  HIGH·정직. W000002 수리(raw_span)가 닫은 문 옆의 열린 문임을 실증. → probe_e_regressions.json
  `BRIDGE_independence_forgery_no_rawspan_mismatch`.

**정직 생산 불가능성 (실측)**:
- 정직 코퍼스에서 서로 다른 핸들이 동일 2D 기하를 공유하는 장면 = **0/400**.
- `source_span_id`를 다른 핸들이 공유하는 경우 = **0/1028** (source_span_id는 핸들과 전단사:
  257 id ↔ 257 handle). → probe_c_fields.json / probe_c2_ssid_semantics.json.
- 즉 위조 표면(동일위치 중복·공유 source_span_id)은 봉인 정직 생성계가 **결코 만들지 않는다**.
  A3(공유 source_span_id + 상이 기하)는 아예 자기모순(하나의 source span이 두 위치)인데도 정직
  인증된다. `build_honest_witness`는 그 표면을 그대로 복사해 증인을 만들며 공유 id를 재현한다
  (probe_b_core.json: witness가 `["S1","S2","S1"]` 재현).

**위반한 봉인 조문 (prereg.json)**:
1. `sealed_bands.frozen_serialization_detection_surface.adjudication_surface.completeness_rule`:
   "Every declared field present … is inspected with its original presence/absence, type,
   **value, multiplicity, and order**." + `omitted_or_normalized_away_declared_field_result:
   violation`. → v5는 `source_span_id`의 값·다중도(핸들 간 반복)를 어떤 규칙으로도 검사하지
   않으며, 교차-핸들 기하 다중도(동일 기하 2회)도 보지 않는다. `analyze_frozen_surface`가 반환하는
   `uncovered_declared_field_count: 0`(v5:687 하드코딩)은 **거짓**: 정직 코퍼스에 실재하는 선언
   필드 `source_span_id`(1028앵커)·`anchor_factory_revision`(1108앵커)를 심판하는 규칙이 없다.
   → probe_c_fields.json `fields_never_adjudicated_by_any_rule: ["anchor_factory_revision",
   "source_span_id"]`.
2. `sealed_bands.suspicion_two_tier_classification.honest_envelope_measurement.closed_world_rule`:
   "Any unlisted kind, missing measurement, ambiguous provenance, or **envelope exceedance is
   Tier B**." → 동일위치·공유-source 구성은 실측 봉투(0/400, 0/1028) 밖이지만 Tier-B로 경성
   차단되지 않는다.
3. `semantic_repairs.CE-D`(minimum_distinct_source_handles_for_high: 3) + `D1`("repeated honest
   labels … cannot manufacture … independent support"). CE-D의 독립 단위는 "distinct **source**
   handle"이다. 동일위치 복사·공유 source_span_id는 물리적으로 하나의 source이므로 3-독립-source
   요건을 만족하지 못한 채 HIGH를 받는다. D1은 *동일 핸들* 반복만 막았고 *다른 핸들/같은 source*
   중복은 커버하지 않는다.
4. `sealed_bands.perturbation_monotonicity.witness_adjudication_procedure` item6 + `classification.
   violation.allowed_count: 0`: 관측-동치 정직 증인이 없는 상승은 violation이다. 정직 생성계가
   그 표면을 못 만드므로(0/400·0/1028) 정직 증인은 존재하지 않는다 — 그럼에도 v5는
   `information_limit_record`로 분류. 게이트가 거짓 음성으로 깨진다.

### 결함 F2 (SECONDARY): 증인 = post 표면 왕복복사 항진 — 4차 §3 미수리

- 90건 증인 표면 **전건**이 post-perturbation 표면과 **바이트 동일**(`witness_serialization ==
  post_serialization`: 90/90). `build_honest_witness`는 raw_span만 기하에서 재생성(정합이면
  무연산)하고 나머지 모든 필드(handle·source_span_id·display·p0·p1)를 그대로 복사한다
  (v5:968-983). 즉 증인은 위조 표면 자신을 파라미터로 먹인 왕복복사다.
- 90건 "scene-specific narrative"는 scene-값만 슬롯 채운 **2개 템플릿**으로 붕괴(값 제거 후
  distinct skeleton = 2). 전건이 동일 generic 문구 "rebuilds raw_span from each p0/p1 relation
  and reproduces all N declared field names exactly" 사용(90/90). → 이 장면이 *왜* 정직 생성
  가능한지 설명하지 않고, 필드를 재현했다는 동어반복만 한다.
- **위반 조문**: `sealed_bands.scene_specific_witness_substantiation.post_surface_round_trip_
  copy_is_not_independent_witness: true` + `boilerplate_rationale_forbidden: true`. F1이 정직으로
  인증되는 *이유*가 바로 이 미수리된 순환성이다 — 증인의 정직성이 독립 정당성이 아니라 분류기
  맹점의 재서술(4차 lens1 §3 그대로).
  · 근거: `python probe_d_witness.py` → probe_d_witness.json.

### 결함 F3 (TERTIARY, 테스트-레이어): 모집단 마스킹 — 1차 class 재발

- `run_property`는 400장면 코퍼스를 **표집하지 않는다**. 6개 고정 픽스처(CE-A, CE-B2, D2, CE-D,
  D3-below, D3-above)를 `strata[index % 6]`로 순환할 뿐이다(loop_l1f.py:565-582). "630 무작위
  케이스"는 6장면의 부패 630회다.
- `exact_duplicate`(family 9종 중 하나, 70케이스)는 오직 CE-A(35회)·CE-D(35회)에만 착지하는데
  둘 다 before가 이미 `NONE`(CE-A는 Tier-B 1, CE-D는 청정 비율핸들 0). 유일한 LOW·2핸들 픽스처
  (D3-below/above)에는 exact_duplicate가 **한 번도** 안 간다. → 70케이스 전건 `rose: false`.
  → probe_b3_masking.json `exact_duplicate_property_cases.any_rose: false`, `fixtures_used:
  CE-A 35 / CE-D 35`.
- 마스크된 모집단: 정직 코퍼스 400장면 중 **40장면**이 정확히 2 청정 비율핸들(before=LOW)이며,
  그 **40장면 전부** exact_duplicate에서 HIGH로 상승한다(probe_b3_masking.json
  `maskable_population: 40 / 40`). 즉 코퍼스의 10%가 유효 LOW 기저인데 속성시험이 결코 안 쓴다.
- 봉인 게이트 결과가 "exact_duplicate 70케이스, violation 0"인 것은 성과가 아니라 **도달
  불가능성의 산물**(4차 lens1 B1의 논리와 동형).

---

## §3. class 구분 (엄수 — 에스컬레이션 판단 재료, 과장 금지)

**판정: 주로 (a) 기존 class의 회귀/변주** — 단, 결함의 *결과*(독립지지 위조)는 새로운 영향이다.
경계가 불확실한 지점은 아래에 명시한다.

- **(a) 근거**: 뿌리원인은 4차 (b)-class "탐지기가 정직 생성계보다 좁음 / 미심판 선언 필드"의
  재발이다. 본 좌석 패킷 target 3의 정의적 기준 — *"v5가 심판하지 않는 선언 필드가 하나라도
  있으면 4차 (b)-class 회귀"* — 에 `source_span_id`(미심판, 1028앵커)가 정확히 해당한다.
  W000002 수리가 `raw_span` 한 필드 점수리였을 뿐 봉인 completeness_rule("모든 선언 필드의
  값·다중도·순서")을 일반 구현하지 않아 같은 메타패턴이 재발했다. 여기에 1차 모집단 마스킹(F3)과
  4차 §3 증인 항진(F2)이 겹친 **회귀 클러스터**다.
- **신규 영향(불확실성 명시)**: 동일위치 중복이 *독립지지를 제조*해 HIGH를 위조하는 소비 경로는
  선행 수리(D1 동일핸들·CE-D 공집합·W000002 raw_span) 어디에도 커버되지 않는 새 소비다. 특히
  A1(source_span_id 無, 순수 동일위치)은 "미심판 필드" 프레임에 안 맞고 "독립 지표(handle)가 물리
  독립보다 거침" 프레임에 맞아 — 이 축은 새롭다. **다만** A1의 "동일위치 중복이 정직 생산가능한가"는
  CAD 도메인 의미 판단이라 아티팩트만으론 완결 못 한다. 이 불확실성 때문에 판정을 A1에 걸지 않고,
  **의심 여지 없는 A2/A3(공유 source_span_id: 0/1028, 자기모순)와 completeness_rule/closed_world
  조문 위반**에 건다.
- **에스컬레이션 함의**: SYNTHESIS(4차)는 L1f를 "구현-레이어 반복의 **마지막**"으로 성문화했다.
  본 REFUTE는 L1f 수리들이 *일반 구현이 아니라 점수리*였고 동일 메타패턴(round 4b)이 재발했음을
  보인다 — 이는 봉인 closure_rule이 경계한 "무한 두더지잡기"의 실증이다. (a)/(b) 어느 쪽으로
  읽든, 마지막 구현 반복이 기각됐으므로 **구현 반복 중단 → "0-violation 밴드의 원리적 달성
  가능성 vs 도시에-레벨 재설계" Paul 결재**로 올릴 것을 권고한다. 오케스트레이터가 이 (a)/(b)
  경계를 재판정할 수 있도록 양쪽 근거를 다 남긴다.

---

## §4. 재현 절차 (git 없음·서브에이전트 없음·Python 3.12 stdlib+numpy+openpyxl)

모든 프로브는 `D:\runs\e2_program\chainverify_L1f\lens1_work\`에 있고 봉인 파일을 READ-ONLY로
임포트한다(loop_l1f.py를 모듈로 로드 → V5/V4/L1E 노출). 실행:

```
cd D:\runs\e2_program\chainverify_L1f\lens1_work
$py = "C:\Users\PAUL\AppData\Local\Programs\Python\Python312\python.exe"
& $py probe_00_smoke.py            # 상수·임포트 확인 (τ, HIGH=0.75, O2 max=2.159, 6:200/200)
& $py probe_a_envelope.py          # §1.1 독립 봉투 재측정 (1.456e-13τ, mismatch 0)
& $py probe_a2_artifact.py         # §1.1 artifact 내부정합 (measured==sealed==독립)
& $py probe_c_fields.py            # §2.F1 미심판 선언필드 (source_span_id/anchor_factory_revision)
& $py probe_c2_ssid_semantics.py   # §2.F1 source_span_id 전단사·0 공유·0 동일기하
& $py probe_b_core.py              # §2.F1 A1/A2/A3 핵심 + witness 공유 id 재현
& $py probe_b_battery.py           # §2.F1 20종 변주 전건 착지
& $py probe_b2_fleetdata.py        # §2.F3 90 witness 라벨/family + exact_duplicate 부재
& $py probe_b3_masking.py          # §2.F3 6픽스처 마스킹 + 40/400 마스크 모집단
& $py probe_d_witness.py           # §2.F2 90 witness 왕복복사·2템플릿·15 교차검사
& $py probe_e_regressions.py       # §1.2 W000002/B5 차단 + BRIDGE 상승 + fleet 회귀요약
```

**최소 재현 (F1 한 줄 증명)** — 정직 2핸들에 실제 부패함수 적용:
```python
import loop_l1f as H  # (모듈 로드; probe_b3_masking.py 참조)
sc = json.load(open(r"D:\runs\e2_program\cells\loop_l1b\scenes_v3\scene_000_k0p001.json"))
corr = H.V4.randomized_corruption(sc["anchors"], "exact_duplicate", random.Random(1), 0)
b, a = H.snapshot(H.V5, sc["anchors"]), H.snapshot(H.V5, corr)
# b.unit_status == "LOW", a.unit_status == "HIGH";
# classify_upward(...) → "information_limit_record"; suspicion_analysis(corr).tier_B_signal_count == 0
```

---

## §5. 수치 부록 (모든 주장 → 산출 명령·아티팩트)

| 주장 | 값 | 산출 |
|---|---|---|
| 독립 최대 장면내 비율편차 | 1.4563237239633405e-13τ (봉인과 정확 일치) | probe_a_envelope.py → probe_a_envelope.json |
| 독립 raw_span↔기하 불일치 | 0 / 2008 | probe_a_envelope.json |
| self-narrowing (다중공간·드롭) | 0 / 0 | probe_a_envelope.json |
| artifact measured==sealed==독립 | true | probe_a2_artifact.json |
| 미심판 선언필드 | source_span_id, anchor_factory_revision | probe_c_fields.json |
| source_span_id 전단사 | 257 id ↔ 257 handle, 공유 0 | probe_c_fields.json / probe_c2_ssid_semantics.json |
| 동일 2D기하 공유 핸들(정직) | 0 / 400 | probe_c2_ssid_semantics.json |
| 배터리 manufactured-support 착지 | 20 / 20 | probe_b_battery.json |
| 실제 exact_duplicate on scene_000 | LOW→HIGH, information_limit_record | probe_b3_masking.json |
| property 6픽스처 (코퍼스 미표집) | strata%6, exact_dup→CE-A/CE-D만 | probe_b3_masking.json |
| exact_duplicate 70케이스 상승 | 0 (any_rose false) | probe_b3_masking.json |
| 마스크 모집단 (2핸들 LOW) | 40 / 400, 전건 HIGH 상승 | probe_b3_masking.json |
| 90 witness 라벨 | information_limit_record 90 / violation 0 | probe_b2_fleetdata.json |
| witness family (exact_duplicate 부재) | suffix_removal36·remove_one25·… | probe_b2_fleetdata.json |
| witness 왕복복사 | 90 / 90 (witness_ser==post_ser) | probe_d_witness.json |
| witness 템플릿 골격 | 2 (90건 붕괴) | probe_d_witness.json |
| witness 15 교차검사 충실도 | 전건 true | probe_d_witness.json |
| W000002/B5/B5g v5 차단 | Tier-B, 상승 0, 인증 0 | probe_e_regressions.json |
| BRIDGE (raw_span 정합 + 독립위조) | HIGH, information_limit_record | probe_e_regressions.json |
| fleet known-adverse info-limit | 0 (내 벡터는 회귀셋에 부재) | probe_e_regressions.json |
| 봉인 SHA-256 | prereg 76AC2A58…207861 외 6건 일치 | Get-FileHash |

*(핵심 상수: τ=RANSAC_LOG_TOLERANCE=0.04879016416943204, HIGH_CONFIDENCE_THRESHOLD=0.75,
O2_STALE_MAX_TAU=2.1594622082423 → floor 0.25 → 감쇠계수 0.75 = HIGH 경계 정확 착지;
MIN_HANDLES_NON_NONE=2, MIN_HANDLES_HIGH=3 — probe_00_smoke.json.)*
