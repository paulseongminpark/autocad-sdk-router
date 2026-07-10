# ROUNDTRIP 100% — Tree-of-Thoughts 계획 트리 (2026-07-09)

> 방법론: 생각을 단위로 자르고(단계) → 분기 생성(후보 계획) → 자기평가(가치점수) → 트리 탐색(가치順) →
> 막다른 길에서 백트래킹(각 분기에 명시된 트리거). 선형 디코딩이 아니라 전역 선택.
> 모든 수치는 산출 아티팩트 병기 (FM9). 기준 도면: `D:\dev\.build\1.dwg` (원본 READ-ONLY).

## 0. 상태 함수 (무엇을 100%로 세는가)

| 층 | 측정기 | 현재 실측 | 소스 |
|---|---|---|---|
| L1 modelspace 인증 그래프 | verdict (geometry basis 1e-6) | **375/375 = 100%** | runs/e2e_1dwg_R4c_interior_20260709/verdict.json |
| L2 블록 내부 named (def-entities) | tools/blockdef_diff.py 정준 | **95.86%** (19,987/20,851; R3b 66.1→R4b 93.78→정준 95.86) | reports/interior100/blockdef_diff_R4c.json |
| L2' 내부 전체 (익명 포함 분모 28,183) | 〃 | **70.92%** (익명 7,332 = P2 리맵 대기) | 〃 |
| L3 전 IR 섹션 가중 | tools/ir_section_coverage.py | **67.84%** (R3b 기준; R4c 재계산 대기) | reports/interior100/section_coverage_R3b.json |
| L4 고정점 (gen1→gen2) | tools/roundtrip_idempotence.py | 내부 diff0 **100.00%** (21,447/21,447), 잔여 드리프트=seed선 +1×135 → R4c에서 **seed 0 확증**, GEN3 판정 대기 | runs/e2e_1dwg_GEN2b_20260709/idempotence_report.json |
| L5 의미 게이트 (rules) | 미구축 | — | reports/alm_synthesis/04_rulepacks.md |

> P1 완료 (6종 append 라이브, spline knots 픽스 @18cf14a) · P6 완료 (+1 근인=createSimpleBlock seed선
> → seed_line 옵트아웃 @4db619f·배포 @238a8e5; spline 불일치=fit 표현 비대칭 → 정준 diff). 다음 최고가치 = P2 익명 리맵.

## 2026-07-10 arc update (R4o–R4r)

R4o~R4r 아크: hatch phase 잔차 규명 → assoc(re-link) 가설 검증 → 고아(orphan) 판정까지.

- **R4o 무효화** (wrong source): 32,545/32,551=0.9998로 돌파처럼 보였으나 population forensics가
  R4n 대비 def-name 겹침 91/294, census 245-vs-407 불일치를 노출; `identity.json` 확인 결과
  `--dwg` 인자 누락으로 `tests/fixtures/native_sample.dwg`(capstone 기본값)를 돌린 것으로 판명 —
  `1.dwg`가 아님. population-control 선례로 legislated: **LEX-0006**
  (`reports/interior100/population_forensics_R4nR4o.md`,
  `runs/e2e_1dwg_R4o_phase_20260709/identity.json`, commit `8124edd`). 소스 sha256/def-population
  신원 확인 전엔 어떤 cross-run 주장도 인정 불가.
- **R4p 26,831**: two-site phase repair. (D1a) predefined-name 패턴(DASH×66)이 origin fold를
  직렬화 엔티티 행에서 읽어 phase 손실(predefined job은 `pattern_definitions` 미보유) — origin
  carriage를 predefined에도 적용하도록 수정; (D2) canonical divisor가 `pattern_type`을
  신뢰(type-1=>baked 가정)했으나 predefined replay는 type-1 UNIT rows 저장 — divisor
  타입-트러스트 버그 수정. 커밋 `d261e44` (`reports/interior100/residue_tail_R4p.json`).
- **R4q 26,834**: 27,130분의 26,834 = 0.98909, phase arc **물리적으로 CLOSED** — 생존 DASH pair의
  canonical geometry diff가 `is_associative` 필드 하나로만 남음(그 외 전 필드는 diff0). Headline은
  +3만 이동(DASH 66 ∩ assoc 66 겹침 63건 — phase가 고쳐져도 assoc 불일치 쌍은 안 접힘). Legislated
  as **LEX-0007**: 잔여 66은 ASSOC 클래스(59+4+3 필드조합). Next lever = assoc re-link, 예상 +66
  (`reports/interior100/R4q_summary.json`, `docs/ASSOC_RELINK_DESIGN.md`).
- **Orphan-assoc 판정** (3개 독립 프로브, 전부 음성): `AcDbHatch::getAssocObjIds` 0/66 ·
  `getAssocObjIdsAt`(loop-local) 0/66 · LibreDWG DXF 그룹 97 부재(0/330) — 소스 자체에 살아있는
  reactor/boundary 연결이 없다. 즉 R4q가 남긴 66-hatch 잔차는 "재연결하면 접히는 differential"이
  아니라 **소스 DWG 안에서 이미 고아(orphan)인 associativity 플래그**다. flag-replay(플래그만
  참으로 복제하고 실제 reactor는 안 건다)로 커밋 `6d59fd5`
  ("assoc: loop-local extraction contract + faithful associativity replay")에 반영,
  `is_associative` 필드 diff는 여기서 닫힘.
- **R4r in flight** — prereg point **26,900**/27,130, band **[26,890, 26,910]** (26,834 +
  flag-replay 접힘분 예측치). 진행 중, 라이브 검증 대기.

**SUPERSEDED 표시**: 위 orphan 판정으로 "진짜 boundary reactor 재연결(native ObjectARX relink,
`assoc_source_handles` 핸들맵 경유)"을 가정한 분기는 무효화된다 — 해당 hatch에 살아있는 소스
연결 자체가 없으므로 재연결할 대상이 없다. 아래 §1 P3, §3 백트래킹 표의 관련 행을 SUPERSEDED로
표기(텍스트 보존, 삭제 없음).

## 1. 분기(계획) 10개 — 가치 = 예상획득 × 실현성 ÷ 비용

**P1. append 6종 확장** [가치 최상 — 집행됨, 검증 중]
갭 6,867 중 6,563(spline 3,973·lwpoly 1,443·nested ref 943·ellipse 201·point 2·polyline 1)이
이미-인증 종류. native m08e 빌더 확장 컴파일 완료(@4a197dc), R4 라이브 검증 진행 중.
기대: L2 66.1→93%+. 백트래킹 트리거: R4에서 per-op 실패율>1% → B1b(adopt-op 설계)로 전환.

**P2. 익명(*U) 동적블록 캡처+리맵** [집행 절반]
154개 def / 320 refs. 추출은 라이브(@60e502d, anonymous:true), 재건은 리맵 설계 대기
(create_block이 *-이름 거부 → `ARIADNE_ANON__U172` 클론+참조 리맵+diff의 이름-맵 인지).
기대: L2 +~5%p & L4 수렴. 트리거: 리맵 후 blockdef_diff 불일치 → 정적 스냅샷 한계 문서화(동적성은 L5로).

**P3. hatch 재건** — 265건. ~~전략분기: native create.hatch op(레지스트리 확인) vs 경계 폴리라인
decompose(근사, 명시 플래그). 트리거: native hatch loop API 실패 → decompose 승격.~~
**[SUPERSEDED 2026-07-10]** native 재연결(re-link) 분기는 orphan-assoc 판정(3개 독립 프로브
전부 음성 — getAssocObjIds 0/66, getAssocObjIdsAt 0/66, LibreDWG DXF group 97 부재 0/330)으로
무효화: 소스에 살아있는 boundary reactor가 없어 재연결할 대상 자체가 없다. decompose(근사,
명시 플래그)가 유일한 실행경로로 확정.

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
| P3 native | hatch loop API 불가 | decompose 근사(플래그) — **SUPERSEDED 2026-07-10**: orphan-assoc 판정(프로브 3종 전부 음성)으로 트리거가 실측 확정됨, decompose가 유일 경로 |
| P6 | +1 이상현상이 추출기 결함으로 판명 | 추출기 수리 우선, P8 보류 |

## 4. ALM 문서 고고학 반영 (reports/alm_synthesis/01~05)

- 05(단계 노트): rebuild-sufficiency 사다리·naive-foil·VACUOUS≠PASS — 본 트리의 상태함수(L1~L5)가 그 사다리의 구현.
- 04(룰팩): P10의 규칙 스키마·비준 절차 원천 (rules-as-data, evidence 의무).
- 01(퍼플렉시티)·02(GPT-web 0617)·03(카탈로그): 실험설계 사다리·GNN/온톨로지 기법 — P9·P10 정밀화 시 재소환.

## 5. 야간 자동화 상태

- R4 (P1 검증) 라이브: `runs/e2e_1dwg_R4_interior_20260709` — 신형 CRX(6종)+가드.
- 모니터 cron :13/:53 — R4 수확→GEN2b→plan 갱신, 쿼터 리셋 후 자동 재개.
- 함대 실적: 이 트리의 도구 5종+문서 5종+native 2종 = octoloop 14패킷 (codex_54med/spark·sonnet_b/c·composer).
