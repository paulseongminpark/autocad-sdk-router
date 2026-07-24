# HARVEST_REPORT — P1 Failure Ledger v1 적재

## W3-TELEM (자원 텔레메트리)

- wall_seconds: `1426` (실측, START_TS=1784531152 -> END_TS=1784532578, date+%s)
- peak_rss_bytes: `*_RESOURCE_NOT_RECORDED` (프로세스 RSS 모니터 미가동 — 미계측)
- device: 로컬 CPU (GPU/DGX 미사용)
- budget_charge: CPU, 실측 wall ~23.8분 / 캡 4h — 여유 대폭 (저비용 수확 목적 부합)

## 수확 결과

- **LEDGER.jsonl**: 55행, 전건 JSON 유효성 검증 통과(`json.loads` 왕복 55/55).
  - SHA-256: `7163e3045762b5f71119b30a7623ed1785eac875c4b13934487ef256d7728804`
- **TAXONOMY.md**: root_class 자유 태그 49종.
  - SHA-256: `e02067e9cf0a63dd401c4f3f555d410aa00fbd43ff50708cc06620b45c84b256`
- status 분포: `closed` 37 / `open` 12 / `escalated` 6
- layer 분포: `target_code` 35 / `packet` 15 / `orchestrator` 3 / `review` 1 / `worker` 1
- 모든 행의 `lesson` 필드는 오케스트레이터 소관으로 빈 문자열 유지 (증류 없음).

## 소스별 분해 (id 범위 = LEDGER.jsonl 순서)

| # | 소스 | id 범위 | 행수 | 비고 |
|---|---|---|---:|---|
| 1 | `w3_plan_review_staging\*.md` (grok 4라운드: review/confirm/confirm_v3/confirm_v31) | L001–L015 | 15 | v1 DO_NOT_SEAL 8건 + v2잔여 3건 + v3잔여 4건. 전건 v3.1 SEAL_OK로 해소(closed) |
| 1b | 동 소스 — sol 좌석 집계 (개별 원문 out-of-scope) | L016 | 1 | sol이 v2 7건·v3 8건(계 15건) 봉인차단 — 원본 텍스트가 `D:\runs\e2_program\w3_plan_review\`에 있어 패킷의 read 범위(`reports\e2\` 하위)를 벗어남. 건수만 PROGRAM_JOURNAL.md 교차확인, 개별 항목은 미수확(발명 금지 원칙에 따라 합성하지 않음) |
| 2 | `chainverify_L1b`~`chainverify_L1f`/SYNTHESIS.md (5라운드 함대: 1차~5차) | L017–L036 | 20 | L1(seed 반려) 1 + L1b REFUTE 3 + L1c REFUTE 4 + L1d REFUTE 3 + L1e REFUTE 3 + L1f(4차) REFUTE 5 + L1f(5차, 최종) REFUTE 1(신규class)+에스컬레이션 1. `chainverify_L1a` 디렉토리는 존재하지 않음 — `cells\loop_l1\REPORT.md`가 사실상의 L1(seed) 라운드로 확인 |
| 3 | `cells\*\REPORT.md` 판정 FAIL/KILL/BLOCKED_INPUT + 반복인용 W1 근본결함(B1/B4) | L037–L046 | 10 | f02(FAIL) · f03(BLOCKED_INPUT) · f04_canonical_fill(BLOCKED_INPUT) · f04_artifact_freeze(BLOCKED_INPUT) · c71_stk_hybrid(BLOCKED_INPUT) · w3_m2_gnn_andgate(FAIL) · g5_full_graph(교차기기 FAIL) · B1 fidelity FAIL · B4 scale FAIL · GNN E2 screen v1(BLOCKED, 이후 해소) |
| 4 | `PROGRAM_JOURNAL.md` erratum/repair 챕터 + 요약인용 2건 | L047–L053 | 7 | val-B 러너 회계결함 · W2-02 데이터누출 자체발견 · 자원등급 오배정 · B* family collision · "합성 한정" 오기 · Wave-1 이중검증결함(요약수준) · 해시전사오류 2건(요약수준) |
| 5 | `git log --oneline -n 400` (읽기전용) 상호참조 | L054–L055 | 2 | G9/A63 RL kill(이중독립검증) · GNN SSL arm FAILED |

**미상(UNKNOWN) 건수**: root_class UNKNOWN 2행(L052, L053 — RSI_SYSTEM_DESIGN.md/RSI_METHODOLOGY_MAP.md의 요약 인용만 확보, harvest 범위 내 원본 상세 리포트 미발견), date UNKNOWN 28행(커밋일 특정 불가 — 대부분 `chainverify_L1*` 라운드로 커밋 SHA는 있으나 저널의 정확 타임스탬프 문장을 개별 대조하지 않음).

## 규율 준수 확인

- 읽기 전용 수확: `git log --oneline -n 400` 1회만 실행, `git show`/커밋/브랜치 변경 0건.
- 서브에이전트 사용 0건 (전 작업 본 세션에서 직접 수행).
- 발명 금지: source 4의 2행(L052/L053)과 source 1의 1행(L016)은 원본 상세를 확보하지 못해 root_class=UNKNOWN 또는 개별 항목 미생성으로 정직하게 보존 — 패킷의 "22건 이상" 예시 수치를 채우기 위해 사실을 지어내지 않았다.
- 패킷 예시로 언급된 "g9_a63 RL kill"·"ssl kill"·"B1 fidelity fail"·"B4 scale fail"은 문자열 그대로는 어느 파일에도 존재하지 않았으나(패킷 저자의 요약 표현으로 판단), 대응하는 실측 근거(G9/A63 RL kill 밴드 발화, GNN-B SSL arm FAILED, B1 KS 0.5792/TV 0.265, B4 scale 0.7624)를 각각 확인해 L044/L045/L054/L055로 수확했다.

## 산출물

- `D:\dev\99_tools\autocad-sdk-router\reports\e2\failure_ledger\LEDGER.jsonl`
- `D:\dev\99_tools\autocad-sdk-router\reports\e2\failure_ledger\TAXONOMY.md`
- `D:\dev\99_tools\autocad-sdk-router\reports\e2\failure_ledger\HARVEST_REPORT.md` (본 파일)
