# lens2 — C1 coverage 0→1.0 정당성 시야 (3차 함대, L1d)

- 좌석: lens2 (C1 coverage 0→1.0 정당성)
- 판정 대상: L1d 종결 주장 중 ⑤ "C1 원본 코호트의 봉인 밴드(HIGH coverage ≥0.60·정확도 ≥0.95)가
  coverage 1.0/정확도 1.0으로 충족" 및 그 정당성 — (Q1) v3 공식 재설계와 도시에 §2.3 조문의 양립,
  (Q2) 3-anchor coherent 장면 confidence 1.0의 "HIGH 남발" 여부, (Q3) coverage 0→1.0이 게이트
  게이밍인지 원 구조적 불일치(min(1,n/5) 캡)의 원리적 해소인지.
- 방법: 모든 원본 READ-ONLY. 재계산·프로브는 `lens2_work\lens2_probe.py` 하나로 수행, 수치 산출물은
  `lens2_work\lens2_results.json`. 아래 모든 수치는 이 스크립트의 실행 출력 또는 명시된 파일:행에서 나왔다.

## 0. 검증 자산 무결 (전제 확인)

- 검증 대상 코드 동일성: 실행본 `cells\loop_l1d\feyerabend_c1_v3.py` SHA256
  `ba7adddb…ce555e` = repo `tools\e2\cells\feyerabend_c1_v3.py` = REPORT.md 기재 SHA. 일치.
- v1 동일성: 실행본 `cells\feyerabend_c1\feyerabend_c1.py` SHA256 `633c5ee1…c4d51` = repo
  `tools\e2\cells\feyerabend_c1.py`. 일치.
- v3는 v1 모듈을 read-only 임포트해 문턱 상수(`HIGH_CONFIDENCE_THRESHOLD=0.75`,
  `CONSENSUS_THRESHOLD=0.80`, `MIN_INDEPENDENT=3`, `RANSAC_LOG_TOLERANCE=log(1.05)`)와 상태
  게이트 함수 `_status`를 **그대로 재사용**한다 (feyerabend_c1_v3.py:73-117 임포트 목록,
  :120-125 `_status` 위임, :28 원본 경로).

## 1. Q1 — 도시에 §2.2~2.4 조문과 v3 재설계의 양립성 (원문 인용 판정)

질문의 핵심: 도시에가 **공식 자체**를 불변 조문으로 새겼는가, 아니면 **밴드가 수용 기준**이고 공식은
수리 대상인가.

### 1.1 도시에가 "봉인"이라 부르는 것의 목록 (원문)

- §2.3:207 — 공식 도입부: "단위 ratio의 **제안** confidence는 다음과 같다." 공식(C_a =
  c_consensus · exp(−MAD/τ) · **min(1, n_ind/5)** · min(1, n_regions/3), :209-214)은 "제안"으로
  도입된다.
- §2.3:229 — "모든 숫자는 P2용 제안 봉인값이며 문헌 성능 인용이 아니다."
- §2.2.2:184 — base weight에 대해: "이 값은 관측값이 아닌 **구현 제안값**이다."
- §2.8:414-425 — 봉인의 조작적 목록인 "봉인 설정과 비결정 탐색" 표. 여기 오르는 항목은 α_L, α_U,
  angle tolerance, overlap min, RANSAC log tolerance, **HIGH confidence 0.75** ("real 30을 보기
  전에 동결"), local mode posterior, max span modes — **공식의 min(1,n/5)·min(1,n/3) 구조는 이
  표에 없다.**
- §2.9:434 — 불변식 #4: "anchor confidence **threshold**는 실측 pair count나 Pearson을 본 뒤
  바꾸지 않는다." — 불변 명령의 대상은 문턱이지 공식 구조가 아니다.
- §6:740 — "모든 threshold는 실행 전 prereg.json과 evidence.xlsx PREREG sheet에 동시에 봉인한다.
  primary 설정을 본 뒤 sensitivity 설정으로 판정을 교체하지 않는다."
- 셀 C1:785-792 — 합격선: "HIGH subset의 95% 이상이 true scale 대비 상대오차 5% 이하 / 네 scale
  각각 HIGH coverage 0.60 이상 / …" 뒤에 "**모두 제안값이다.**"
- 셀 C1:772 — 가설 자체가 행동 계약이다: "HIGH confidence가 실제 정답 scale과 일치하는 **선택적
  subset**을 만든다." 공식이 아니라 HIGH 부분집합의 행동(선택성·정확성)이 검증 대상으로 새겨져 있다.

### 1.2 판정: 밴드·문턱·불변식이 조문이고, 공식은 수리 대상이다

결정적 근거는 **도시에 자체의 내부 모순**이다. §2.3:220-224의 봉인 상태 규칙은:

> "unit_status=HIGH: 독립 ratio anchor가 **3개 이상**, 합의 가중치 비율이 0.80 이상, log MAD가
> log(1.05) 이하, **C_a≥0.75**." (:222)

그런데 제안 공식의 min(1, n_ind/5) 캡 아래에서 n_ind=3이면 C_a ≤ 1·1·0.6·1 = **0.6 < 0.75**로,
네 번째 조항이 산술적으로 충족 불가능하다. 즉 같은 문장 안의 "3개 이상" 조항이 제안 공식 아래에서는
사문(死文)이다. 공식을 불변 조문으로 읽으면 도시에는 자기모순 문서가 되고, 어떤 추정기도 §2.3:222를
만족할 수 없다. 반면 봉인 위계(§2.8 표 + §6:740의 prereg 봉인 = 강제층, "제안/구현 제안값" = 수리
가능층)로 읽으면 문서 전체가 정합적이다. 조문 충돌의 해소는 후자를 따를 수밖에 없다.

v3가 실제로 지킨 것과 바꾼 것:

| 층 | 항목 | v3에서 |
| --- | --- | --- |
| 봉인(불변) | HIGH 문턱 0.75 · consensus 0.80 · MAD ≤ log(1.05) · n≥3 게이트 | v1 상수·`_status` 함수를 바이트 그대로 재사용 (위 §0) |
| 봉인(불변) | 밴드: 스케일별 coverage ≥0.60 · HIGH 정확도 ≥0.95 | L1d `prereg.json` `sealed_bands`에 동일 수치로 재봉인 (`minimum_fraction: 0.6`, `relative_error_maximum: 0.05`, `minimum_fraction: 0.95`, `status_field: unit_status`) |
| 봉인(불변) | §2.9 누수 불변식 (label-free, permutation 불변) | fit 경로는 `scene["anchors"]`만 소비 (feyerabend_c1_v3.py:424-574, :577-581 정독; truth 접근 없음) |
| 제안(수리) | C_a의 절대 카운트 인자 min(1,n/5)·min(1,n/3) | 순도 비율(지지 고유 handle/전체 후보 handle, 지지 bin/후보 bin) + 전후보 무결 일치 게이트(1_coherent)로 교체 (:299-408) |

부가 정합 확인: v3의 "독립성 = 고유 source handle"은 §2.2.4:192("독립 anchor는 서로 다른 source
handle을 가지고")의 **직접 구현**이다. v1은 오히려 inlier **record 수**를 독립성으로 셌고
(feyerabend_c1.py:318 `n_independent = len(inlier_anchors)`), 이것이 §2.2.4 위반이었다. z^mm 선행
정규화는 §2.3:205("physical unit은 명시 suffix anchor의 z^mm 합의가 있을 때만")의 합의 공간을
구현하며, §2.2.1:173("bare number를 임의로 mm로 바꾸지 않는다")도 지켜진다(아래 §2.3 battery
`bare_numbers_3`: physical_unit=UNKNOWN, mm_per_raw=None 확인).

**Q1 답: 양립한다.** 도시에는 공식을 "제안/구현 제안값"으로, 문턱·밴드·누수 불변식을 봉인으로
새겼고, v3는 봉인층을 1비트도 바꾸지 않고 제안층만 교체했다.

## 2. Q2 — 3-anchor coherent confidence 1.0이 "HIGH를 너무 쉽게" 만드는가

### 2.1 v3 HIGH의 실제 구조 (코드 정독)

v3 confidence (feyerabend_c1_v3.py:385-391):
`score = consensus_fraction × residual_factor × independent_fraction × spatial_fraction × 1_coherent`
여기서 1_coherent(:380-384)는 "전 후보 record가 inlier이고, 고유 handle 집합이 일치하고, 가중치
합이 일치"할 때만 1. 따라서 unit HIGH는 다음을 **모두** 요구한다:

1. DIM/TEXT 후보 record 전체의 무결 일치 (record 하나라도 이탈·결측·충돌이면 score=0),
2. 고유 source handle ≥ 3 (게이트, v1 그대로),
3. 합의 가중치 ≥ 0.80 (게이트; 1_coherent 아래에선 사실상 1.0만 통과),
4. score ≥ 0.75 ⟺ residual_factor = exp(−MAD/τ) ≥ 0.75 ⟺ **MAD ≤ τ·ln(4/3) = log(1.0141)** —
   허용창 log(1.05)보다 3.5배 빡빡한 일치 요구.

즉 confidence 1.0은 "쉬워진 HIGH"가 아니라 "완전 무결 일치 장면에만 주어지는 천장"이고, 오염
방향으로는 v1보다 **엄격**해졌다.

### 2.2 오염·저품질 장면 battery 실측 (lens2_probe.py Part C, 13종)

구성 진리값(truth=2.5)을 알고 만든 장면에 v1·v3를 직접 적합시켰다. "wrong-HIGH" = unit_status
HIGH이면서 추정 상대오차 > 5%.

| probe (구성) | v1 | v3 | v3 wrong-HIGH |
| --- | --- | --- | --- |
| clean3_honest (정직 3-anchor, 코호트 형상) | LOW 0.600 | **HIGH 1.000**, relerr 0 | 아니오 |
| forged3_consistent_wrong (3-handle 완전 정합 위조) | LOW 0.600 | HIGH 1.000, relerr 1.0 | **예 — 정보한계급 (아래 §2.4)** |
| mixed_3v3_modes (3:3 혼합 mode) | LOW 0.300 | LOW **0.000** | 아니오 |
| majority_4v1_outlier (4 정상+1 outlier) | LOW 0.640 | LOW **0.000** | 아니오 |
| dup_handle_spread5 (한 handle을 5 record로 산포) | **HIGH 1.000 (가짜 HIGH!)** | LOW 0.000 (n_ind=1) | 아니오 |
| 2good_1missing (결측 display 1) | LOW 0.267 | LOW 0.000 | 아니오 |
| single_bin_cluster3 (한 구석 밀집 3-anchor, 정직) | LOW 0.600 | HIGH 1.000, relerr 0 | 아니오 (확대면 — §2.5) |
| coherent_dispersed_2pct (일치하나 2% 분산) | LOW 0.402 | LOW 0.670 | 아니오 |
| dispersed_8pct_spread (8% 산포) | LOW 0.274 | LOW 0.457 | 아니오 |
| two_anchors_only (2-anchor, score 1.0) | LOW 0.267 | **LOW** 1.000 | 아니오 (n≥3 게이트가 score와 독립으로 작동) |
| bare_numbers_3 (suffix 없는 맨숫자 3) | LOW 0.600 | HIGH 1.000, unit=UNKNOWN·mm 승격 없음 | 아니오 |
| honest_mixed_units_mm_m (1000MM+5M 정직 혼합) | LOW 0.178 | HIGH 1.000, relerr 0 | 아니오 |
| 3good_2forged_minority (3 정상+2 소수 위조쌍) | LOW 0.360 | LOW 0.000 | 아니오 |

- v3 wrong-HIGH 합계 **1/13 — 유일 건이 정보한계급**(전 증거가 정합하게 거짓말하는 완전 위조).
  탐지 가능한 결함(혼합·outlier·중복·결측·소수 위조)이 있는 장면의 wrong-HIGH는 **0**.
- confidence는 상수 반환이 아니다: battery에서 {0, 0.457, 0.670, 1.0}의 등급 거동 관측.
- 역방향 발견: **v1이야말로 가짜 HIGH 경로를 갖고 있었다** — dup_handle_spread5에서 물리적 근원이
  하나뿐인 장면에 record 수 팽창만으로 HIGH 1.0을 부여(§2.2.4 위반의 직접 결과). v3는 이 경로를
  고유 handle 셈으로 차단한다.

### 2.3 코호트 밖 유지 구조인가

HIGH 부여 조건이 "전 후보 무결 일치 + 고유 handle ≥3 + MAD ≤ 1.41%"라는 **장면 내용 무관의 구조적
술어**이고, 코호트 특이 요소(scene id·seed·경로 분기)가 fit 경로에 없음을 정독으로 확인했다
(feyerabend_c1_v3.py:424-574는 anchors 필드만 소비). 오염이 조금이라도 검출 가능하면 score가 0으로
붕괴하므로, HIGH 부분집합의 정확도는 "정합 위조가 아닌 한" 코호트 밖에서도 같은 메커니즘으로
유지된다. 이는 셀 C1 가설(:772 "선택적 subset")이 요구하는 바로 그 구조다.

### 2.4 유일한 확대 — 완전 정합 위조 (B4)와 그 정직성

v3는 3-handle 완전 정합 위조에 HIGH를 준다(v1은 캡 때문에 0.6 LOW). 그러나:

- 이것은 **정보이론적 한계**다: 진짜 지지와 관측 분포가 동일한 위조는 어떤 label-free 추정기도
  구별할 수 없다. v1의 "보호"는 캡 모순의 부산물일 뿐이며, 같은 위조를 handle 5개로 만들면 v1도
  HIGH 1.0을 준다(v1 공식에 대한 산술; §2.2 battery의 dup/forged 계열과 동일 구조). 버전 간 차이는
  위조 비용(3 vs 5 handle)뿐이다.
- L1d는 이를 숨기지 않았다: `prereg.json`이 **실행 전에** `ratio_consistent_complete_forgery_b4:
  {gate: false, measurement_required: true, reason: information-theoretic limit}`로 봉인했고,
  REPORT §"B4 정보 한계 측정"이 LOW→HIGH 상승(upward 3)을 표로 공개하며, §미해결이 "완전 위조는
  식별할 수 없다"고 명기한다. 판정 밴드에 넣지 않고 측정으로 남긴 처리는 도시에의 킬 조건(:794)이
  코호트 진단(복제·stale·suffix·outlier) 범위를 겨눈 것과 정합한다.

**Q2 답: "너무 쉽게"가 아니다.** 정직 3-anchor 장면의 HIGH는 도시에 §2.3:222가 스스로 그은 자격선
그 자체이고, 오염 방향으로는 v1보다 엄격하며(전 오염 probe score 0), 유일한 확대(완전 위조)는
사전 봉인·수치 공개된 정보 한계다.

### 2.5 확대면 2건 명시 (판정 훼손 아님, 기록 목적)

- **공간 밀집**: single_bin_cluster3이 HIGH — v1 공식의 min(1, bins/3) 절대 요구가 순도 비율로
  바뀌며 공간 다양성 요구가 소멸했다. 단 §2.3:222 게이트 조문에 공간 조항은 원래 없고, 도시에는
  다양성을 "별도 audit field"(:216)로 분류한다. 조문 충돌 없음, 표면 확대만 기록한다.
- **맨숫자 ratio-HIGH**: bare_numbers_3이 unit_status HIGH — 단 physical_unit=UNKNOWN이 유지되고
  mm 승격이 없어(:173 준수) 물리 단위 주장은 발생하지 않는다.

## 3. Q3 — coverage 0→1.0: 게이밍인가, 구조적 불일치의 원리적 해소인가

### 3.1 "0"의 원인은 품질이 아니라 캡이었다 (재계산 실증)

C1 원본 코호트 200장면(`cells\feyerabend_c0\scenes`, loop_l1d.py:56이 지정하는 바로 그 READONLY
디렉토리)을 v1으로 **독립 재적합**한 결과 (lens2_probe.py Part A/B):

- v1 coverage: 네 스케일(κ=0.001/0.01/1/1000) 모두 **0.00** — 원본 셀 REPORT의 기록
  (`cells\feyerabend_c1\REPORT.md:46` "HIGH_coverage | 0")과 일치. 같은 파일들 위에서 원본 결과가
  재현되므로 코호트 바꿔치기도 없다.
- 그런데 v1의 **추정값 자체는 전 장면 정확**했다: 추정 상대오차 > 5%인 장면 0, HIGH 후보군 상대오차
  최대 ~4.4e-16 (기계 오차).
- 차단 요인 분해: **200/200 장면에서 min(1, n/5) 캡이 유일 차단자** — 캡을 제외한 곱(consensus ×
  residual × bin 인자)은 ≥ 0.75이고 나머지 게이트 조항(n≥3, weight≥0.80, MAD≤τ) 전부 통과인데
  캡을 곱하면 < 0.75. 코호트 최대 n_independent = **3**이므로 v1 score 상한 = 0.6 < 0.75: coverage
  0은 **설계 시점에 산술로 확정**되어 있었고 추정 품질과 무관했다. {C0 3-anchor 데이터, /5 캡,
  문턱 0.75, 밴드 ≥0.60}의 연립은 어떤 추정기 품질로도 충족 불가능한 구조적 불일치다.

### 3.2 "1.0"은 관대화가 아니라 의미론 교정의 결과다

- **추정층 무변경**: 두 코호트 400장면 전부에서 v1 추정값 == v3 추정값 (불일치 0). 바뀐 것은
  신뢰도 집계뿐이다.
- **밴드·문턱·지표 필드 불변**: L1d prereg의 sealed_bands = 도시에 원 밴드 수치 그대로 (≥0.60,
  ≤5% 오차 비율 ≥0.95); 문턱 상수는 v1에서 임포트; coverage를 세는 필드도 원본 C1 집계기와 동일한
  `unit_status` (feyerabend_c1.py:999-1001·1026-1028 vs prereg `status_field: "unit_status"`) —
  지표 교체 없음.
- **독립 재계산 결과**: v3 coverage 네 스케일 모두 **1.00** (50/50 각각), HIGH 정확도 **1.000**,
  HIGH 부분집합 상대오차 최대 ~4.4e-16. REPORT의 c1_original 표와 일치. 새로 HIGH가 된 200장면에
  오답 유입 0 — 정확도 밴드(≥0.95)도 여유로 동시 충족.
- **비인플레이션 교차 증거**: L1b 코호트에서 v3 == v1 (coverage 0.80 × 4 스케일, 정확도 1.000,
  독립 재계산). 게이밍성 관대화라면 전 코호트가 오르는 경향을 보였을 것이다. v3는 목표 코호트만
  올린 게 아니라, **의미론이 시키는 곳만** 올렸고(3-anchor 무결 장면), 같은 의미론으로 v1의 가짜
  HIGH(dup_handle_spread5)와 전 오염 계열을 0으로 내렸다.
- **참조층 정합 확인**: v3의 c1 참조 confidence는 {0.0, 1.0} 이봉분포(각 100장면)로
  reference_status {LOW:100, HIGH:100}, status {LOW:100, HIGH:100} — REPORT 수치와 일치하고,
  REPORT의 중앙값 0.5·0.857도 이 이봉분포의 산술적 귀결로 재현된다. 표 전사 오류 없음.

### 3.3 게이밍 가설의 잔여 경로 점검

- 코호트 특이 하드코딩: 없음 (fit 경로 정독, §2.3).
- truth 누수: fit은 anchors만 받는다; truth 접근 가드는 selftest(`truth_key_access observed=1`)와
  코드 정독으로 교차 확인.
- 문턱·밴드 사후 조정: prereg `threshold_substitution_after_observation: false`, 봉인 선행 관측은
  REPORT 봉인 관측 표(12항 전부 1) — 봉인 시각·위조 심층 검증은 seat4 관할이며 나는 내용 동일성
  (밴드 수치 = 도시에 수치)만으로 본 판정에 충분하다.

**Q3 답: 원리적 해소다.** "0"은 도시에 자기 게이트(n≥3)와 자기 공식(/5 캡)의 모순이 3-anchor
코호트 위에서 필연화한 산술적 결과였고, v3는 봉인층(밴드·문턱·게이트·지표 필드)을 고정한 채 모순의
근원인 제안층 공식만 §2.2.4의 독립성 정의에 맞게 교정했으며, 그 결과 정확도 무손실(1.0)로 밴드를
충족했다.

## 4. 내가 검증하지 않은 것 (범위 명시)

- v2 3판 replay 무결·replay_delta.json 전수 대조 — lens3 관할 (내 판정은 v1↔v3 독립 재계산으로 성립).
- 이중 봉인의 실물·시각·위조 심층 검증, 600종 속성 시험 재구성, 54종 스윕 재실행 — seat4 관할.
  내 battery는 이와 독립적으로 구성했고 wrong-HIGH 0(탐지가능급)을 얻었다.
- 1_coherent의 경계 거동(문턱 아래 출발 장면의 포화 문제) — lens1 관할. 단 내 battery의 LOW-출발
  장면들(0.267~0.670)에서 교란이 confidence를 올린 사례는 관측되지 않았다.

## 5. 결론

세 질문 모두에서 주장 ⑤와 그 정당성이 실증된다: (Q1) 도시에는 밴드·문턱·불변식을 봉인으로, 공식을
제안으로 새겼고 v3는 봉인층을 보존했다 — 공식-불변 독해는 도시에를 자기모순으로 만든다. (Q2) 3-anchor
confidence 1.0은 도시에가 스스로 그은 자격선의 복원이며, 오염 방향으로는 v1보다 엄격하다(탐지가능급
wrong-HIGH 0, v1의 가짜 HIGH 경로 차단). (Q3) coverage 0→1.0은 추정층·밴드·문턱·지표 불변 아래
캡 모순(200/200 유일 차단자)의 해소이고, 정확도 1.0·L1b 불변이 비게이밍을 교차 입증한다.

VERDICT: CONFIRM
