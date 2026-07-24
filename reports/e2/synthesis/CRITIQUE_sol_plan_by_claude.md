# PLAN_sol.md 적대 검증 — 독립 종합자 B (claude)

대상: `D:\runs\e2_dossier_wave\20260718\synthesis\PLAN_sol.md` (295행, 전량 정독).
검증자 입력: 26부 도시에 §6 전문 + PLAN_claude.md. 목표는 흠집이 아니라 진실 — sol 우세 지점은 그대로 인정하고, 내 계획이 공유하는 결함은 병기했다.

**총평 먼저**: sol의 계획은 고품질이다. K01–K08 관행-킬 목록, Phase 1A/1B 구현·자격 분리, 소비자별 충실도 게이트 보존, DGX/API `BLOCKED_RESOURCE`/`BLOCKED_APPROVAL` 규율, 11건 원장은 내 계획보다 우월한 지점들이다. 결함은 주로 **큐 커버리지 구멍·밴드 의미론·역색인 드리프트·원장 3건 누락**에 있다.

---

## ① A가 빠뜨린, 살릴 가치 있는 셀

| 항목 | 판정 | 근거 (원문 인용) | 심각도 |
|---|---|---|---|
| feyerabend_P6 C4의 **1.dwg 정량 프로브 밴드 소실** | 누락 | sol은 fey_P6 C0–C6 전부를 F03(인프라 셀)에 귀속했으나, F03 합격선은 "split-wall folded recall `≤0.20`, unfolded recall `≥0.90`…no-INSERT byte/decision identity"뿐 — fey_P6 C4의 실도면 판별 밴드(적격 def 중 **≥30%가 신규 cross-scope pair 생성, ≥3/10**)가 매트릭스 어디에도 없다. world-assembly 가설의 유일한 실도면 판별량이 배관으로 강등됨. F03에 밴드 1행 추가 또는 microcell 분리 권고 | MED |
| **doe_P5의 GNN/VLM family 어댑터 슬롯 부재** | 누락 (공동 결함) | F04 행은 "GPU adapter는 artifact 준비 뒤 별도"라 쓰지만, §7 GPU-LOCAL-SERIAL 셀 목록(T21·G41·R51·R52·R54·A62·A64 = 7)과 DGX-QUEUE(G42·A65·R55·P80 = 4) 어디에도 doe_P5의 GNN(RTX 4h cap)·VLM(DGX 4h cap) family 셀이 없다. F06이 방법별 F04 의존을 요구하므로 형식상 걸리긴 하나, 예산·일정에 존재하지 않는 작업은 실행 시 "F04 PASS"가 CPU 가족만으로 선언될 위험. **내 PLAN_claude.md도 동일 갭** — 합의 수리 대상 | HIGH |
| **E1.5 admission 재산출의 독립 조기 셀 부재** | 누락 | admission(B1/B4 재산출, CPU `<2h`)이 PARKED인 R53 내부에 접혀 있다. 그러나 T20("R53 admission for silver")·T21("eligible silver only")·R54·R55가 이 판정에 의존한다. Phase 2 비고("admission CPU 재산출은 가능하지만 API 호출 0")로 운영상 구제되나, PARKED 셀의 하위 단계에 TOP/VIABLE 셀들이 의존하는 구조는 실행자 혼동 유발. 독립 TOP CPU 셀로 승격 권고 (PLAN_claude의 SIL-G) | MED |
| fey_P3 C5 REAL-384의 명시 슬롯 희석 | 이의(경미) | 교차표 "C2–C5→T21/T20"으로 흡수되어 실도면 384-def 확인의 별도 역할이 T21 행 지표에 "real meta"로만 남음. 밴드는 살아있으므로 경미 | LOW |
| platt_P1 E5 재귀속 시 원 BLOCK 사유 미표기 | 이의(경미) | E5→R52로 재귀속 자체는 합리적이나(F 축은 bridge 경유), 원문이 FPC 벡터 truth 부재로 BLOCKED 처리했던 사유가 표기되지 않아 원장 C06과의 연결이 약함 | LOW |

## ② 잘못된 병합 (가설 뭉갬)

| 항목 | 판정 | 근거 | 심각도 |
|---|---|---|---|
| **F04로의 doe_P5 전체 흡수** | 이의 | doe_P5는 발견형 요인설계(28셀 method-family×transform 상호작용 + effects/confirmation)이고 platt_P3는 자격 게이트다. sol은 "각 방법의 gate는 C11처럼 별도 유지"로 부분 방어하나, doe_P5의 transform×family 상호작용 분석·confirmation이 별도 행 없이 사라짐 (교차표: "본실험 F01–F28→F04"). 판정 기능은 보존, 발견 기능은 소실 | MED |
| **매트릭스 출처열 ↔ §3 역색인 드리프트** | 이의 | D10 출처열은 "`calibration_P2` C4/C6"를 포함하나 §3은 "C3–C5→M32; C6→F04/T20"로 D10 미기재. F03 출처열은 "platt_P1 G1/E0/E1/E2/E4"를 포함하나 §3은 "E0/E1→D11; E2/E3→D12; E4→D10". §3 서문이 "복수 통합 셀에 귀속했다"고 선언한 감사 도구 자체가 매트릭스와 불일치 — 소실 감사의 신뢰가 깎임. 기계적 수리 필요 | MED |
| T21로의 fey_P3 프로그램 압축 | 동의(조건부) | 핵심 밴드(meta advantage `≥0.10`, S `≥0.80`/meta `≥0.90`, CubiCasa `≥0.517`, Pearson `≤0.35` 보조 강등)가 행에 보존되어 있어 병합 자체는 수용 가능 | LOW |
| D10·D14·T20 병합 | 동의 | 가설 단위가 유지되고 "real kill은 synthetic 지지와 평균내지 않음" 같은 원문 조문이 살아있음 | – |

## ③ 자원 오류 (16GB/64GB/DGX 불통 전제)

| 항목 | 판정 | 근거 | 심각도 |
|---|---|---|---|
| DGX·API 규율 | **동의 (강함)** | 운영규칙 3·4: "queue item 상태를 `BLOCKED_RESOURCE`로 둔다. local result를 DGX full-study PASS로 대체하지 않는다" / "`BLOCKED_APPROVAL`; 결재 전 paid call 0". 위반 없음 | – |
| GPU 캡 수치 | 동의 | G41 18/12/6 GPU-h, R51 2–3 GPU일, A64 24h cap×3 seed — 원문 캡과 일치 | – |
| doe_P5 GPU/DGX family 셀의 예산 부재 | 이의 | ①의 HIGH 항목과 동일 근원 — GPU 큐 7셀·DGX 큐 4셀 합계에 없는 작업량 | (①에 계상) |
| R54 예산 표기 | 이의(경미) | "R54 cell `0.5–2일`"이 셀당인지 총합인지 애매 — doe_P6 open-finetune 6셀이면 3–12 GPU-일이 "GPU-LOCAL-SERIAL 7"의 한 항목 뒤에 숨음. 전개 표기 권고 | LOW |

## ④ 밴딩 이견

| 항목 | 판정 | 근거 | 심각도 |
|---|---|---|---|
| **TOP 의미론의 내적 모순 (T20·D12)** | 이의 | sol §0 정의: "TOP: **즉시 착수할** 공용 계측기·가장 싼 판별·최종 거버넌스". 그러나 T20 의존성은 "F00; F02; F04; R50; **R53 admission for silver**"(PARKED 셀의 하위 단계 포함), D12는 "D11; F05; **T20-qualified truth**". 즉시 착수 불가능한 셀이 TOP에 있다. 행 단위 의존성을 존중하는 실행자는 안전하나, 밴드만 보는 실행자는 오발사하거나 정지한다. TOP을 "즉시 착수형"(claude식)과 "핵심 경로형" 중 하나로 재정의 필요 | MED |
| C73 VIABLE | 이의 | C73은 로컬 가능한 E2–E4(MI·384 fit/freeze)와 외부 자산 의존 E5(독립 라벨 프로젝트 — 현재 부재가 기지 사실)를 한 셀에 묶고 VIABLE을 부여. 자체 킬 조건에 "metadata+label project 부재면 PARK"라 쓰면서 현재 사실상 PARK인 부분을 VIABLE로 밴딩. **분할 권고**: E2–E4 = VIABLE, E5 = PARKED | MED |
| D13(Taguchi)를 D10 뒤로 게이팅 | **동의 — sol 우세, 내 계획 수정 필요** | sol C04 인용: fey_P2 "이 셀이 끝나기 전 doe P2의 절대 band robust optimization이나 다중 knob Taguchi를 실행하지 않는다." 내 PLAN_claude는 TAG-1을 Phase 1 병렬(TOP)로 두어 이 금지를 위반 — sol의 K04·D13 게이팅이 옳다 | (자기 수정) |
| A63을 M30 checkpoint 뒤로 | 동의 | 현실적 후보 우주·고정 분류기 없이 zero-learning 프로브를 돌리면 보상지형이 비대표적 — sol의 게이팅 근거 있음. 내 RL-0의 TOP 배치보다 정밀 | – |

## ⑤ 원칙 위반 (val/test·사전 봉인·대조군·결재 게이트)

| 항목 | 판정 | 근거 | 심각도 |
|---|---|---|---|
| val/test·봉인·셔플·xlsx | **위반 없음** | F00 계약, F06 단발, K07("test 재실행·test 기반 threshold…선택" 킬), 운영규칙 5("실패도 xlsx row로") — 전 항목 조문화 | – |
| **A61의 이중 합격선 미판결** | 이의 | A61 행: "calibration: saving `≥20%` and AUPRC drop `≤0.01`; feyerabend: saving `≥30%` and F1 drop `≤0.02`". 한 런이 saving 25%/drop 0.015이면 calibration 기준 PASS, feyerabend 기준 FAIL — **어느 판정이 프로그램의 bandit 채택 결정이 되는지 규칙이 없다**. 사후 밴드 선택(=사후 프리레그 변경) 벡터. C01이 소비자별 게이트에 적용한 "각 claim은 자기 게이트로" 원칙을 A61에도 명문화해 사전 봉인해야 함. **내 PLAN_claude의 BAND-1("두 제안 밴드 병기 봉인")도 동일 미판결** — 공동 결함 | HIGH |
| C10 판결(412,775 채택) | 동의 | 패킷 고정 사실과 일치, "412,965는 원문 오기로 보존" — 수치 출처 규율 준수 | – |
| 수치 날조 검사 | 동의 | §0의 기준점·데이터 계약 수치 전수 대조 — 세션 실측치와 일치, 신규 측정 주장 없음 | – |

## ⑥ 모순 원장 갭

sol의 C01–C11은 행 번호 인용 형식까지 내 원장(7건)보다 우월하다 — 특히 C02/C03/C06/C08/C09/C10/C11은 내가 원장으로 승격하지 못한 것들이다. 그럼에도 3건이 빠졌다:

| 누락 항목 | 근거 | 심각도 |
|---|---|---|
| **GNN 존재 자체의 충돌 (Occam)** | platt_P2 C1 "graph-stat classical이 …`+0.10`이면 GNN을 정지"(M30 행에 채택) vs calibration_P3의 SSL GNN full 프로그램(E4–E7). sol은 G41 킬 조건("M30이 Occam gate를 닫으면 불필요")으로 운영 처리했으나 원장 미등재 — 이는 파라미터 차이가 아니라 **한 제안의 존재를 다른 제안이 부정하는 충돌**로, 원장 보존 대상 | MED |
| **test 소비 정책의 분기** | fey_P2는 자기 방법을 위해 CubiCasa test 소비를 명시 거부("DIM-bearing 라벨 test 부재"), 다수 제안은 방법당 단발 계획. F06/K07이 운영을 통일하나 정책 분기 자체는 원장에 없음 | LOW |
| **RL 생존 밴드의 목적함수 분기** | C07은 RL의 *적용 범위*(entity-label vs routing vs assembly)만 판결. calibration_P6 "utility `≥1.05`" vs fey_P4 "saving `≥30%`∧drop `≤0.02`" vs platt_P4 "`≥+0.05` F1"의 *합격선 분기*는 미등재 — ⑤의 A61 HIGH와 동일 근원. 원장 등재 + per-claim 귀속 판결 필요 | MED |

## ⑦ 구조적 차이 목록 (판정 포함)

| # | 차이 | claude | sol | 판정 |
|---|---|---|---|---|
| 1 | 소실 감사 | 없음 | §3 역색인 교차표 | **sol 옳음** (단 ②의 드리프트 2건 수리 조건) |
| 2 | 킬 목록의 단위 | 셀 기각/병합 목록 | K01–K08 관행·경로 킬 | **sol 옳음** — 프로그램 불변식으로 더 강함 |
| 3 | 구현≠자격 분리 | 페이즈 내 암묵 | Phase 1A/1B 명시 ("구현 완료는 PASS가 아님") | **sol 옳음** — FM2/FM8 예방 조문 |
| 4 | 충실도 게이트 | 단일 프로그램 봉인(Paul 결재 상신) | 소비자별 3단(0.10/0.10, 0.20/0.10, 0.30/0.20) 동시 산출 | **sol 옳음** — 각 도시에의 프리레그를 사후 개정하지 않음. 단일 confirmatory pack이 필요해지면 그때 Paul 결재 |
| 5 | Taguchi 순서 | Phase 1 병렬 | D10 뒤 게이팅(K04) | **sol 옳음** (fey_P2 금지 조문 인용) |
| 6 | admission 게이트 배치 | 독립 TOP 셀(SIL-G) | PARKED R53 내부 + Phase 2 비고 | **claude 옳음** — CPU-싼 판정이 다수 셀을 개폐하므로 조기 독립 실행 |
| 7 | fey_P6 C4 정량 밴드 | SCOPE-1에 보존("≥30%…≥3/10") | F03에서 소실 | **claude 옳음** |
| 8 | TOP 밴드 의미론 | 즉시 착수형으로 일관 | 정의는 즉시 착수형, 배정은 핵심 경로형 혼재 | **claude 옳음** (내적 일관성) — 단 어느 의미론을 최종 채택할지는 결정 필요 |
| 9 | doe_P5 GPU/VLM 어댑터 | 미배치 | 미배치 | **공동 결함** — 병합안에서 큐 슬롯 신설 |
| 10 | A61/BAND-1 밴드 귀속 | "병기 봉인"(미판결) | 병기(미판결) | **공동 결함 → 결정 필요** (per-claim 귀속 규칙 프리레그) |
| 11 | RL zero-learning 위치 | VER-1 직후 TOP | M30 checkpoint 뒤 VIABLE | **sol 옳음** |
| 12 | 원장 폭 | 7건 | 11건(행번호 인용) | **sol 옳음** — 단 ⑥의 3건 보충 필요 |

**결정 필요 (판정 불가, Paul/프리레그 몫) 3건**: ① A61/BAND-1의 밴드 귀속 규칙(per-claim 권고안 포함) ② TOP 밴드 의미론(즉시 착수형 vs 핵심 경로형) 단일화 ③ 단일 confirmatory 충실도 팩의 필요 여부(현행은 sol식 3단 유지).

## 판정 집계

- **HIGH 2건**: doe_P5 GNN/VLM 어댑터 큐 부재(공동) · A61 이중 밴드 미판결(공동, 사후 밴드 선택 벡터)
- **MED 8건**: fey_P6 C4 밴드 소실 · admission 독립 셀 부재 · F04의 doe_P5 발견 기능 흡수 · 역색인 드리프트 · TOP 의미론 모순 · C73 혼합 밴딩 · Occam 원장 누락 · RL 밴드 원장 누락
- **LOW 4건**: REAL-384 희석 · platt_P1 E5 사유 미표기 · R54 예산 표기 · test 정책 원장 누락
- **sol 우세로 판정(내 계획 수정 필요) 2건**: Taguchi 게이팅 · RL zero-learning 게이팅 (+구조 4건: 역색인·킬 목록·1A/1B·다단 게이트)
- **원칙 위반(⑤ val/test·봉인·대조군·결재 표기): 0건** — sol의 거버넌스 조문은 견고하다.

CRITIQUE_COMPLETE: claude
