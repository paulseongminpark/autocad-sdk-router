# ROUNDTRIP 100% — Tree-of-Thoughts 계획 트리 (2026-07-09)

> 방법론: 생각을 단위로 자르고(단계) → 분기 생성(후보 계획) → 자기평가(가치점수) → 트리 탐색(가치順) →
> 막다른 길에서 백트래킹(각 분기에 명시된 트리거). 선형 디코딩이 아니라 전역 선택.
> 모든 수치는 산출 아티팩트 병기 (FM9). 기준 도면: `D:\dev\.build\1.dwg` (원본 READ-ONLY).

## 0. 상태 함수 (무엇을 100%로 세는가)

| 층 | 측정기 | 현재 실측 | 소스 |
|---|---|---|---|
| L1 modelspace 인증 그래프 | verdict (geometry basis 1e-6) | **375/375 = 100%** | runs/e2e_1dwg_R3b_full_20260708/verdict.json |
| L2 블록 내부 (def-entities) | tools/blockdef_diff.py | **66.1%** (13,785/20,851) | reports/interior100/blockdef_diff_R3b.json |
| L3 전 IR 섹션 가중 | tools/ir_section_coverage.py | **67.84%** | reports/interior100/section_coverage_R3b.json |
| L4 고정점 (gen1→gen2) | tools/roundtrip_idempotence.py | modelspace TRUE / interior **18.7%** | runs/e2e_1dwg_GEN2_20260709/idempotence_report.json |
| L5 의미 게이트 (rules) | 미구축 | — | reports/alm_synthesis/04_rulepacks.md |

## 1. 분기(계획) 10개 — 가치 = 예상획득 × 실현성 ÷ 비용

**P1. append 6종 확장** [가치 최상 — 집행됨, 검증 중]
갭 6,867 중 6,563(spline 3,973·lwpoly 1,443·nested ref 943·ellipse 201·point 2·polyline 1)이
이미-인증 종류. native m08e 빌더 확장 컴파일 완료(@4a197dc), R4 라이브 검증 진행 중.
기대: L2 66.1→93%+. 백트래킹 트리거: R4에서 per-op 실패율>1% → B1b(adopt-op 설계)로 전환.

**P2. 익명(*U) 동적블록 캡처+리맵** [집행 절반]
154개 def / 320 refs. 추출은 라이브(@60e502d, anonymous:true), 재건은 리맵 설계 대기
(create_block이 *-이름 거부 → `ARIADNE_ANON__U172` 클론+참조 리맵+diff의 이름-맵 인지).
기대: L2 +~5%p & L4 수렴. 트리거: 리맵 후 blockdef_diff 불일치 → 정적 스냅샷 한계 문서화(동적성은 L5로).

**P3. hatch 재건** — 265건. 전략분기: native create.hatch op(레지스트리 확인) vs 경계 폴리라인
decompose(근사, 명시 플래그). 트리거: native hatch loop API 실패 → decompose 승격.

**P4. xdata 재생성** — 64 entities→0. 신규 op write.entity.set_xdata (regapp 등록 포함).
Ariadne 의미층에 직결. 소스: docs/XDATA_TABLES_COMPLETION_PLAN.md.

**P5. 심볼테이블 완성** — layers 91→66, app_ids 25→7, dim_styles 6→2, blocks 410→251.
기존 records 레인 확장(비참조 레코드 포함 모드). L3 직접 상승.

**P6. 고정점 수렴 랩** — GEN2b(6종 append 후) 재실험 → 잔존 drift만 추적.
발견된 +1-per-def 이상현상(C 3→4 등 4개 def) 원인 확정 필수. 수렴 = 파이프라인 무손실 증명.

**P7. 잔여 종류 소탕** — face3d 34·wipeout 5~7·기타. P1 패턴 재적용(빌더 미러).

**P8. 내부-diff를 기본 게이트로 승격** — blockdef_diff를 capstone verdict에 통합,
interior_diff0_fraction을 PASS 기준에 편입 (지금은 L1만 게이트). "측정되지 않으면 회귀한다."

**P9. 코퍼스 일반화 (R4 rung)** — corpus census 9 dwg 완료. 다음: input.dwg(21,747 entities)
샘플드 라운드트립 + 타 도면 1개 전량 — 발견도면≠검증도면. 트리거: 신규 종류 출현 → P7 큐잉.

**P10. 의미 게이트 v1 (L5)** — rulepack 온톨로지(04_rulepacks.md)에서 치수 앵커링·중심선 위상
게이트 2개 프로토타입. diff0를 넘어 "도면으로서 옳은가"로.

## 2. 탐색 순서 (가치순 + 의존성)

```
P1(라이브 검증) ─┬→ P6(고정점 재측정) ─→ P8(게이트 승격)
                 ├→ P2(익명 리맵) ──────┘
                 ├→ P3(hatch) → P7(소탕)
P4(xdata) ───────┤  (P1과 독립, 병렬 가능)
P5(테이블) ──────┘
P9(코퍼스) ← P1·P2 착륙 후    P10(의미) ← P8 후
```

## 3. 백트래킹 원장

| 분기 | 막다른 길 신호 | 롤백 대상 |
|---|---|---|
| P1 B1a | R4 append 실패율>1% / 기하 drift | B1b adopt-op |
| P2 C1 리맵 | 리맵 diff 불일치 | C3 추출-only + 한계 문서화 |
| P3 native | hatch loop API 불가 | decompose 근사(플래그) |
| P6 | +1 이상현상이 추출기 결함으로 판명 | 추출기 수리 우선, P8 보류 |

## 4. ALM 문서 고고학 반영 (reports/alm_synthesis/01~05)

- 05(단계 노트): rebuild-sufficiency 사다리·naive-foil·VACUOUS≠PASS — 본 트리의 상태함수(L1~L5)가 그 사다리의 구현.
- 04(룰팩): P10의 규칙 스키마·비준 절차 원천 (rules-as-data, evidence 의무).
- 01(퍼플렉시티)·02(GPT-web 0617)·03(카탈로그): 실험설계 사다리·GNN/온톨로지 기법 — P9·P10 정밀화 시 재소환.

## 5. 야간 자동화 상태

- R4 (P1 검증) 라이브: `runs/e2e_1dwg_R4_interior_20260709` — 신형 CRX(6종)+가드.
- 모니터 cron :13/:53 — R4 수확→GEN2b→plan 갱신, 쿼터 리셋 후 자동 재개.
- 함대 실적: 이 트리의 도구 5종+문서 5종+native 2종 = octoloop 14패킷 (codex_54med/spark·sonnet_b/c·composer).
