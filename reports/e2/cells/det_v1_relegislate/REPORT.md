# M-15 — deterministic_v1 재입법 (cell `e2.w3.det_v1_relegislate`) — REPORT

## W3-BOUNDARY (서두 인용, prereg_w3_v1 §0.5)

> 본 보고의 탐지기 사다리·모든 val-A/val-B 수치의 유효 범위는 **CubiCasa SEG-IR 우주 한정**이다.
> **E1 실무 도면 전이는 미검증**이다.

이 경계는 아래 BLOCKED_INPUT 판정의 직접 원인이다 — CubiCasa SEG-IR은 단위 메타데이터·INSERT/블록
구조·의미 있는 레이어가 없는 래스터 유래 벡터라, 7개 metamorphic 관계 중 4개(기하 관계)만 이 우주에서
truth-bearing이다 (doe_P5 §3.2).

## W3-SEAL (수치 전 봉인 — 헤더 SHA)

| 항목 | 값 |
|---|---|
| method_id | `deterministic_v1` (v0와 절연) |
| cell_id | `e2.w3.det_v1_relegislate` |
| **spec_sha256** (명세 선봉인) | `3c0c755fb5fce7ce5fc9389788aa56e16fd0c12f5700099f5affdf410eddab12` |
| **code_sha256** (rules_v1.py) | `3b53479ab448c9c1a4a1d3e690c6baa1588f6dd0c461b3812554b871ae6ce851` |
| 봉인 순서 | ① 명세 봉인(spec_sha256) → ② 구현 착지(code_sha256) → ③ 측정 — 위반 없음 |
| 명세 봉인이 수치보다 선행 | `sealed_before_numeric_computation: true` (PREREG_local.json) |

evidence 정본 = `evidence.csv`. 산출물 SHA는 마지막 절.

## W3-TELEM (measurement.json + 서두 이중 기록)

| 필드 | 값 |
|---|---|
| wall_seconds | 62.081 |
| peak_rss_bytes | 82,845,696 (≈ 79.0 MiB) |
| peak_vram_bytes | N/A(no_GPU) |
| device | CPU AMD64 Family 26 Model 68 Stepping 0, AuthenticAMD |
| budget_charge | 0.01724 CPU-h (캡 4 CPU-h, GPU 금지) |

## v0 절연 (G-1)

deterministic_v0는 RETIRED(정의 실종). 본 셀은 v1 명의의 **독립 신규 측정**이다. v0 매니페스트·수치
(0.682 스칼라 포함)를 입력·비교·백필로 사용하지 않았다. 지표·밴드만 원 F01–F07 프리레그 문언에서 승계했다.

## 승계한 지표·밴드 (출처 인용)

- **지표**: `R-META = drawing-macro violation rate = 1 − invariance`.
  - per (도면 d, 변환 k, 파라미터 p): `v = (1/|L_d|) Σ_{ℓ∈L_d} 1[ ŷ(before,ℓ) ≠ ŷ(after,m(ℓ)) ]`;
    변환 후 사라진 LID는 위반 1. 유효 세그먼트 0인 도면은 vacuous pass가 아니라 invalid로 격리.
  - 셀 집계: `R-META_k = mean_over_drawings( mean_over_params( v_{d,k,p} ) )` (파라미터 동일 가중 먼저, 그다음 도면-macro).
  - 평가 단위 = occurrence-level **LID segment** (CubiCasa에서 LID ≡ (drawing_id, handle); INSERT 없음).
  - **출처**: doe_P5.md §2.3.
- **밴드** (봉인 그대로): `PASS: R-META ≤ 0.02` · `INCONCLUSIVE: 0.02 < R-META ≤ 0.10` · `FAIL: R-META > 0.10`.
  - **출처**: doe_P5.md §2.3 == `reports/e2/cells/f04_completion/PREREG_local.json` `verdict_band`
    (SHA-256 `444fa333d0ba816d723e9fc2b0125714a1ad31940710da7a79932b425d7587c0`).
- **변환 카탈로그 T-META v1** (파라미터 verbatim): doe_P5.md §2.2 + F04 PREREG `relation_registry`.
- **셀 정의**: prereg_w3_v1.md M-15 (149–154행); FINAL_PROGRAM_PLAN.md 156행 (`doe_P5 F01–F14 → F04`,
  결정론 계열 = F01–F07).

## 규칙 탐지기 deterministic_v1 (명세 봉인분)

SEG-IR 선분에 대한 규칙 기반 벽 탐지기. 학습 없음, 임계값은 **도메인 프라이어**로만 고정(데이터 튜닝 아님):

- **R1 평행-밴드 페어링**: 세그먼트 ℓ은, ∃ m≠ℓ 로서 (a) 무방향 각도차 ≤ 12°, (b) 두 무한직선의 수직
  간격 ∈ [3, 55] px (벽 두께 밴드; 12 mm/px × 36–660 mm), (c) ℓ 방향 투영 겹침 ≥ 0.25·min(len ℓ, len m)
  이면 벽 후보. 페어는 ℓ·m 양쪽에 대칭 표기.
- **R2 길이 게이트**: len(ℓ) ≥ 8 px (≈ 96 mm).
- 예측 = R1 ∧ R2.
- **레이어 힌트 규칙 없음**: SEG-IR은 전 세그먼트가 단일 상수 레이어 "0"(distinct=1)이라 레이어 힌트가
  무력 — 그래서 v1 규칙에 포함하지 않았다(관측 확인, 발명 아님).

## 모집단 (val-A DEV — val-B·test 무접촉)

- val-A DEV = split A / state DEV / **198 도면** (전건 유효, invalid 0).
- 분할 내용 해시 `5e16541d7191ad01c57a9cee72172f63112ed68590dd371aff5bf0aaaab8e07b`,
  매니페스트 파일 `8aad64eeda77df55296fc711c21d7befdeada7fe379aeafec81fd1691aea044f`.
- IR 루트 `D:\dev\99_tools\autocad-sdk-router\runs\e2_ext_cubicasa\ir\val` (`.segir.json`+`.truth.json`).
- **val-B (split B / ADJ)·test 접촉 0.**

## 자격(sentinel) 판정 — 측정 전 admissibility

| 게이트 | 값 | 판정 |
|---|---|---|
| positive recall floor (≥ 0.20) | pooled recall **0.7084** (macro 0.7036) | PASS |
| non-zero detector | pred_rate **0.6685** (> 0) | PASS |
| non-all detector | pred_rate 0.6685 (< 0.95) | PASS |
| zero-detector 시연 | recall 0.0 → 랭킹 제외 확인 | 게이트 작동 |
| all-detector 시연 | rate 1.0 ≥ 0.95 → near-all 제외 확인 | 게이트 작동 |
| 결정성(Q2 재현) | 프로세스 2회 재실행 R-META byte-동일 | PASS |

집계: 총 walls 19,584 · TP 13,873 · pred_wall 112,013 · segments 167,556.
탐지기는 자명해가 아니며 recall floor를 초과 → 측정 admissible. (출처: doe_P5 §2.3/§6.1 Q1, floor 0.20.)

## F01–F07 셀별 판정 (v1 명의)

| 셀 | 변환 | measurability | R-META | 판정 | 도면 분포 (min/med/max) |
|---|---|---|---:|---|---|
| **F01** | translate | MEASURABLE | 0.0000257 | **PASS** | 0 / 0 / 0.00257 |
| **F02** | rotate | MEASURABLE | 0.0006793 | **PASS** | 0 / 0 / 0.01767 |
| **F03** | uniform-scale | MEASURABLE | **0.206401** | **FAIL** | 0.16020 / 0.20665 / 0.31367 |
| **F04** | unit-change | **BLOCKED_INPUT** | — | **BLOCKED_INPUT** | — |
| **F05** | block-explode | **BLOCKED_INPUT** | — | **BLOCKED_INPUT** | — |
| **F06** | layer-rename | **BLOCKED_INPUT** | — | **BLOCKED_INPUT** | — |
| **F07** | coord-jitter | MEASURABLE | 0.0014183 | **PASS** | 0 / 0.00068 / 0.02381 |

**가족 판정 = FAIL** (F03가 FAIL; 밴드 규칙: 하나라도 FAIL → FAIL). 단 F04–F06 BLOCKED_INPUT이므로
7관계 완전 가족 판정은 성립하지 않는다 — measurable 4셀 한정 결과다.

### 해석 (수치의 뜻)

- **F01/F02/F07 PASS**: v1은 병진·회전·미세 좌표 지터에 대해 사실상 불변(위반율 ≤ 0.14%). 규칙이 상대
  기하(평행성·간격·겹침·길이)만 쓰고 절대 위치·방위를 쓰지 않기 때문 — rigid 관계에서 기대되는 위생.
- **F03 FAIL (0.2064 > 0.10)**: 균등 축척(0.5·2·10배)에서 벽 라벨의 ~20.6%가 뒤집힌다. 원인은 **절대 px
  두께 밴드 [3,55]** — 축척하면 간격이 밴드 밖으로 밀려 벽이 파트너를 잃는다. 이는 metamorphic 시험이
  잡도록 설계된 바로 그 표현 의존성(doe_P5 §1.2 "고정 mm gap band 과의존")이며, 재탐색 금지 조항에 따라
  임계값을 조정하지 않고 FAIL 그대로 기록한다(밴드 미달도 정직 기록).

### BLOCKED_INPUT 근거 (발명 금지·UNKNOWN 보존)

세 셀은 지표·밴드가 없어서가 아니라(있음), **변환이 요구하는 입력 기질이 CubiCasa SEG-IR 우주에
부재**하기 때문이다. vacuous 측정(no-op 후 R-META=0)은 doe_P5 §2.3이 금지 → BLOCKED_INPUT.

- **F04 unit-change**: SEG-IR `units='px'`, `$INSUNITS`·`scale_mm_per_unit` 없음. 변환 유효성 인증
  ("좌표·$INSUNITS·scale가 같은 물리량 인코딩") 불가. doe_P5 §3.2(단위 변경은 CubiCasa 시험지 아님)·
  §6.2(unit-unknown → BLOCKED_DATA). 임의 단위 부여 = 발명, 금지.
- **F05 block-explode**: 세그먼트 필드 = {handle, layer, pts}뿐, INSERT/블록/occurrence 구조 전무.
  explode는 vacuous no-op. doe_P5 §3.2 "block-explode = NA for CubiCasa".
- **F06 layer-rename**: 전 세그먼트 레이어 "0"(distinct=1). 단일 레이어의 전단사 셔플 = 항등이고 탐지기가
  레이어를 안 쓰므로 truth-bearing 기질 없음. doe_P5 §3.2 "CubiCasa 레이어 중립".

## 한계 (limits)

- 결과 유효 범위 = CubiCasa SEG-IR 우주 한정(W3-BOUNDARY). E1 실무 도면·실제 CAD(단위/블록/레이어 있는)
  전이는 미검증 — 특히 F04–F06는 CubiCasa에서 **측정 불가**일 뿐, 실 CAD에서는 별개 프리레그 소관.
- F03 FAIL은 "탐지기 결함"이 아니라 필요조건 게이트가 표현 의존성을 드러낸 것 — R-META는 정확도 대체물이
  아니다(doe_P5 §8.2 필요조건 오독 방지).
- 페어링 이웃 탐색은 per-segment 반경(len+gap_max)·대칭 표기라 극단 길이차 파트너를 이론상 놓칠 수 있으나
  대칭 표기로 상호 커버; recall 0.71로 자명해 아님 확인.
- v0 수치와의 어떤 비교도 하지 않았다(절연). 본 수치는 v0를 대체·백필하지 않는다.

## 산출물 SHA-256 (W3-PATH — 전 IO 절대경로)

| 파일 (D:\runs\e2_program\cells\det_v1_relegislate\) | bytes | SHA-256 |
|---|---:|---|
| PREREG_local.json | 10377 | `541f559f952c322e7ae78962f4bfa87982004da97f6a307b5df78159e532791a` |
| PREREG.csv | 1696 | `d2a4d6b57b4b43fc3720137dc0698e96ac260d13cdc696f1a3180099f05ae042` |
| rules_v1.py | 15308 | `3b53479ab448c9c1a4a1d3e690c6baa1588f6dd0c461b3812554b871ae6ce851` |
| seal_prereg.py | 12529 | `34d778170001434873dbb82ab059855d90b314bb459ef17b45329d531bee2b56` |
| measurement.json | 4107 | `16d0ec2ca21f9ef50f92f2312883c70f017ffebf9627896b24005ad77a8c0d09` |
| evidence.csv | 255305 | `da5fe190b617a39c6c3c6932070ddec5ce7d97b66e7db9d1f30f799d51b06fde` |

spec_sha256 `3c0c755f…` · code_sha256 `3b53479a…`. evidence.csv = 1 header + 2376 obs(12 param-instance ×
198 도면) + 7 cell_summary = 2384행.

AXIS_MEASUREMENT_COMPLETE_V1
