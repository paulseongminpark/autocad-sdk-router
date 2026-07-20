# W3 프리레그 초안 v3.3 (4차 확인 — sol 잔여: proposer 설정 고정·DAG 게이트 일치 — 봉인 후보)

작성 2026-07-20. v3 개정(sol_confirm_v3 NOT SEAL_OK 8건 + grok_confirm_v3 NOT SEAL_OK 4건 —
중복 제거 후 10개 축 전부 반영). 반영 SoT: `D:\runs\e2_program\w3_plan_review\{grok,sol,fable}_
review.md` + `SYNTHESIS.md` + `sol_confirm.md` + `sol_confirm_v3.md` + staging의 `grok_confirm
{,_v3}.md` + Paul 결정 D1–D6. 봉인 시 본 문서+로스터 JSON을 json.loads 왕복 후 SHA 봉인.

## 제0조 — 효력·parent·exact 해시

wave_id = **`e2.w3`** (확정 — 봉인 시 변경 없음). parent/증인 전체 SHA-256:

| 문서 | SHA-256 |
|---|---|
| prereg_r2_v1.json | `fc93dad9232cfd877802c1d53996357eccc710daff8cfb2cf7c865bf7f78bcd2` |
| prereg_r2_v1_amendment1.json | `30f752db803f7f589d1a8d1f1a2d8557364ae2d624f76a639533161f552b8283` |
| prereg_r2_v1_amendment2.json | `6e29bbd5f8c502a1bc36277a535521c117408b2460e80511907d610321dd442a` |
| W2_CLOSEOUT_LEDGER.md (파일) | `6991cc42d55442e43c241fb660725a1f6187336579869f29ea429417c4341222` |
| W2_CLOSEOUT_LEDGER 내부 self-SHA | `66b1bed11f8d34ddeb04458e924716219e0fec1d0008e5ad6b3990cc754cb922` |
| PAUL_DECISIONS_20260720.md (D1–D6, @59447bd) | `1acf0e262c029a3073a8869041f5aba8ca9190ba4cf726c4896d7122d8906aad` |
| L1_DEMOTION_RECORD.md | `23a0dd1a98231f9aeaec2732341c9a507e838d619b4d5185f2e971ac8dcb3af9` |
| DATASET_INVENTORY.md | `95c7186c0bca94a8565924b5a2fa98dff6f298ff5e012d088f522df106cec5f0` |
| val-B 배치 러너 (수리판) | `e9edba8b20ed772633f1afa5ecbfc811b28167782795a7611398bf85646b12e9` |
| val-B 출력 스키마 | `f7a7395649971ed10b5cf4ea4d2483188d1cde0b305e9623c8b0f2c77ea2a9b0` |
| 봉인 평가기 | `85481aa49f6cf62307588e73ea502160079f1172de8f5f927a1a7c23bb5ef1de` |
| canonical ledger pre-hash (565 bytes) | `955337d9ec48329e4f55a2ef949700fb5b8d868734d48227a368df25a324443a` |
| val-A/val-B 분할 **내용** 해시 | `5e16541d7191ad01c57a9cee72172f63112ed68590dd371aff5bf0aaaab8e07b` |
| val-A/val-B 분할 매니페스트 **파일** | `8aad64eeda77df55296fc711c21d7befdeada7fe379aeafec81fd1691aea044f` |
| 동결 classical 6특징 모델 | `ccc52d2066cc44502b2a8ccb0412b6c77d8caca4c37cfbf919bb95e46f16c754` |
| GNN-A formal 코드 | `0413f1035de76ab8a175c37c291c3fca634a2f1effb8135b5371aa357d5a94c0` |
| 그래프 빌더 | `c95d4a30d30e0db157fe56102053a7884902b7749464f7f4cb8852c0819321f6` |
| 그래프 config | `56911f4633979a3fe00fd56be2d0a39ac06757ed255ed49ed18ca20ba9d4ac49` |
| 동결 w2_02 config | `ae81bf8c5311fc19c8ad38f7feca5d1c15bf39a71d41a1fb925775d6e63aafe6` |

amendment_rule 승계: outcome 후 arm·band·metric·budget·route 추가 금지, amendment는 강화·킬·
BLOCK·미정값 확정만. amendment1의 `cross_device_promotion`은 G5 실측(0.00864 = 한계 86배)으로
실효 — 확장 금지. 캡·게이트의 SoT는 본 문서 — 선행 리뷰 문서의 개산 캡(예: sol_review의
F04G 4h/셀)은 본 캡표가 대체한다.

## 제0.5조 — 도메인 경계 (본문 봉인)

본 문서의 탐지기 사다리·모든 val-A/val-B 수치의 유효 범위는 **CubiCasa SEG-IR 우주 한정**이다.
**E1 실무 도면 전이는 미검증**이며, 어떤 셀 보고서도 이 경계 밖 일반화를 주장할 수 없다.
M-3(E1 예측물)·M-11(청주)·M-12(ArchCAD)·M-14(실물 제약)는 전이 검증을 *향한* 준비물이지
전이 주장이 아니다. 모든 REPORT 서두에 이 경계 문장을 인용한다.

## 제1조 — 로스터 (전건 처분 — umbrella 금지)

### [GOVERNANCE]
- G-1 **v0 은퇴**: deterministic_v0 = RETIRED/BLOCKED_INPUT 터미널. F01–F07 v0 명의 영구
  UNKNOWN·백필 금지. 0.682 스칼라 = "정의 실종" 역사 기록.
- G-2 **D14 = PARKED**: 원 밴드·의존 보존. 재개 게이트 = **G-6=CLOSURE_OK ∧ M-16 완주(F15–F21
  NUMERIC) ∧ M-7 F02′ PASS ∧ F03 재측정 PASS** (원 사슬 완전 보존·완화 금지).
- G-3 **A0 게이트 봉인**: L1 승인 1단계 문서 봉인+git 증인 커밋. A′/6차 함대 = NON_GOALS.
- G-4 **bet_register 처분**: W2 실측 대비 판정·이월 (오케스트레이터 전용).
- G-5 **라이선스 재론 금지**: Paul PR-3+D2 지배. W3 인용만.
- G-6 **F04 폐포 판정** (adjudication ID `e2.w3.adj_f04_closure`) — **상태기계 정의**:
  범위 = F01–F28 (28셀). 셀 상태 어휘 = {NUMERIC(수치 존재) · PERMANENT_UNKNOWN(F01–F07,
  G-1 확정) · READY_FOR_GPU(F15–F21 — 입력·코드·프리레그 준비 실측 확인) · PARKED(F22–F28,
  F04V) · PENDING}. 판정 상태 = **CLOSURE_OK** ⟺ F08–F14 전건 NUMERIC ∧ F01–F07 전건
  PERMANENT_UNKNOWN ∧ F22–F28 전건 PARKED ∧ F15–F21 전건 READY_FOR_GPU; 그 외 =
  **CLOSURE_INCOMPLETE**. M-5 착지 후 판정문 봉인. 게이트 인용은 반드시 상태로: M-16 게이트 =
  `G-6=CLOSURE_OK`, D14 게이트 = G-2 문언. 판정문 존재 자체는 게이트 충족이 아니다.
- G-7 **부검 예비** (cell ID `e2.w3.autopsy_valb` — REPORT_ONLY): val-B ADJ-FAIL·sentinel
  불일치·GOVERNANCE_STOP 발생 시 읽기 전용 부검 1기 — 신규 측정·재개봉·수리 금지, 로그·ledger·
  해시 대조만. 종료 상태 = {AUTOPSY_COMPLETE, AUTOPSY_BLOCKED}. 캡 = CPU 4h (제6조 총계 포함).
  제3.5조 STOP의 유일 허용 예외.
- G-8 **gen3 방향 기록** (Paul D3): 목표 분포=E1 실무 face 통계(M-11 PASS 시 청주 추가) ·
  용도=계측 보정 전용(학습 증강 별도 게이트) · 순서=M-6 어댑터 선행. 실행 프리레그는 M-6 착지
  후 별도 봉인 — 본 문서에서 gen3 실행 없음.

### [MEASUREMENT]
- **M-1 val-B 단발 배치** (Phase 0C, W3 첫 비가역 outcome). amendment3 봉인 계약(전 항목 exact
  포함 의무): {wave_id `e2.w3` · canonical ledger 절대경로
  `D:\runs\e2_program\cells\w2_09_valb\valb_ledger.jsonl` + pre-hash `955337d9…`(제0조 전문) ·
  분할 내용 해시 `5e16541d…` + 매니페스트 파일 `8aad64ee…` · drawing-list SHA · 팔 로스터 =
  clean bundle + 2hop×3 + GNN-A×3 (series_count=9, 명시 제외 목록) · 전 artifact SHA(제0조 표
  인용) · 러너 `e9edba8b…` · 출력 스키마 `f7a73956…` · 평가기 `85481aa4…` · G1(GNN−clean CI
  low>0)∧G2(GNN−2hop CI low>0) → ADJ-PASS 한정·역전 팔별 처분·보고전용 선언 · 회계 산술(정상=
  웨이브 1이벤트·12=예외 백스톱·현재 1행·본 배치=통산 2행) · one-shot nonce SHA · D1 인용 ·
  **런처 검증 조문**: 러너는 amendment3 절대경로·파일 전체 SHA·parent `fc93dad9…`·wave_id 삼중
  대조를 실물로 통과해야 하며 env 형식만으로 승인 불가 · **수리 검증 증거 결박**: REPAIR_REPORT
  의 selftest PASS + val-A rehearsal 8/8 재현(허용오차 1e-6) 기록 인용}. 접촉 후 실패 =
  GOVERNANCE_STOP → G-7 부검. 완주 직후 장부 SHA 재봉인·잔여 동결.
- **M-2 GNN AND-게이트 완결**: S-node F1≥0.92 · S-pair F1≥0.80 · true style-OOD drop≤0.10
  (봉인 밴드 그대로). val-A/DEV면만.
- **M-3 M30→E1 예측물**: 동결 w2_02 config(`ae81bf8c…`) 재적합 0으로 E1 384 정의 예측 생성·SHA
  봉인(비열람 봉인 순서) → **M-4 C71 STK 재측정**: authorized-input에 M-3 SHA 등재 후 STK 축만.
- **M-5 F04 classical 정본 채우기**: 동결 모델 `ccc52d20…` + 6특징 추출기·LID·인증서 파이프라인
  신규 프리레그(cubicasa_ml fixture parity 의무). zero-eligible-stop 승계. F08–F14만. 착지 후 G-6.
- **M-6 검증기 어댑터 확장** (INSERT 전개·HATCH 방출): 착수 = val-B 완주 후(폐포 동결).
- **M-7 F02′ 재측정**: 게이트 = **M-6 PASS ∧ gen3 실행 프리레그의 자체 게이트 PASS**(별도 봉인
  프리레그의 봉인·실행·자격 판정까지 완료 — 봉인 사실만으로 불개방). D3 순서상 W3 말 또는 W4
  이월 가능 — 이월 시 그대로 보고, 완화 금지. 모집단·지표·밴드(0.30/0.20) 불변·구 수치 비소급.
- **M-8 R50 의미축 자격** (Phase 1): FloorPlanCAD 의미 클레임 자격 측정. 후속 사슬은 제2조 —
  **C-1은 M-8 PASS 전 발사 금지**.
- **M-9 R51 측정**: 게이트 = **M-8 PASS ∧ C-1 PASS** (명시 AND — 유일 해석은 제2조 Phase 2
  직렬 사슬). 로컬 RTX 고정.
- **M-10 G5 로컬 재자격**: 자원 실측 전용(밴드 없음). GPU 유휴 시만. 132h 캡 잔여 내.
- **M-11 둘째 프로젝트 자격 조사** (Paul D4): 청주 S1BL 144 DWG — 정의 어휘·핸들 체계·주석
  가능성 (원본 READ-ONLY·스테이징만). XP 축 해제는 차기 프리레그로만.
- **M-12 ArchCAD 트랙 개시 조사** (Paul D4): 스키마/분할/좌표 검증 + 어댑터 타당성 조사까지
  W3 연속 진행(D4 가속). 학습 본실행은 차기 프리레그.
- **M-13 RSI 내부 루프 런 1** (Paul D5 — method ID `rsi_inner_v1`, cell ID `e2.w3.rsi_run1`):
  - 게이트 = **C-3 자가시험 PASS ∧ M-14 규칙 라이브러리 SHA 봉인 완료**(라이브러리 불변성만
    요구 — M-14 측정 수치와 무관) **∧ proposer 프롬프트 템플릿 SHA·설정(모델 ID·디코딩
    파라미터) 고정 봉인 완료**(C-3 착지 산출).
  - **후보 제안 계약**: 제안기 = 봉인 프롬프트 템플릿(SHA는 C-3 착지 시 봉인·본 게이트 결박)을
    쓰는 LLM proposer. 허용 입력 = {public ledger 전문 · 현 최고 후보 코드 · 봉인 탐색 공간
    기술}만 — private·val-B·test 정보는 권한 분리로 차단. 반복 k 프로토콜(순서 고정) =
    ① proposer 1회 호출 → 후보 1기 산출 ② 후보 코드 SHA를 public ledger에 **선기록(commit)**
    ③ 그 후에만 평가 실행 — **commit-then-evaluate**: 평가 결과를 본 뒤 해당 후보를 수정·교체
    하는 자유도를 제거한다. **proposer 설정 고정 봉인**: proposer 모델 ID·디코딩 파라미터
    (temperature 등)는 C-3 착지 시 **단일 고정값으로 봉인**하고 전 30반복 동일 적용 — 반복 간
    변경 = 런 전체 무효. 봉인값은 C-3 착지 문서에 기록·M-13 게이트에 결박. 호출별 실측 모델 ID·
    파라미터를 attempt ledger에 기록해 봉인값과 대조(불일치 = 런 무효). 거부 후보 포함 전 제안
    보존(append-only·소급 편집 금지).
  - **적응성 선언**: 다음 후보가 직전 public 결과에 적응하는 것은 본 방법론(autoresearch, Paul
    D5)의 정의적 속성이다 — 사전 고정 grid 봉인은 RSI가 아니라 스윕이므로 채택하지 않는다.
    사후 재량은 위 commit-then-evaluate + 입력 제한 + append-only ledger로만 제거한다.
  - 시작점 = GNN-A 동결 파이프라인(제0조 계보 해시). 탐색 공간 = {특징 추출 코드 · 그래프 구축
    규칙 · GNN 아키텍처/하이퍼 · 온톨로지 제약 규칙층 = **M-14 봉인 라이브러리의 사본**(원본
    write-back 금지 — 단일 작성자: 라이브러리 원본은 M-14만, RSI 작업장은 C-3 하네스만)}.
  - **탐색 신호 = RSI-public 점수 전용.** 목적함수 = pooled AUPRC(봉인 평가기 `85481aa4…`,
    RSI-public 분할) 단일. 반복 진행 = public keep-if-better · 최소 개선폭 0.002(미만 reject) ·
    동률 = 선행 유지. RSI-private는 반복 중 **완전 비노출**(keep/reject에도 미사용).
  - 반복당 후보 1기 · 총 반복 ≤30. 훈련 시드 = 1000+k(k=반복 번호), 재검증 시드 = 6000+k.
  - **이상 점프 가드**: 직전 최고 대비 public 개선 ≥0.02 → 시드 6000+k 재훈련 재검증 의무,
    재현 허용오차 0.005, 실패 = 후보 폐기.
  - **승자 선정 (런 종료 후 1회)**: public 상위 K=5 → 봉인 평가기가 RSI-private로 평가 → 최고
    private 승자. 승자 private ≤ GNN-A 기준선(동일 private 분할 실측) → 런 상태 =
    **NO_IMPROVEMENT** (정직 종료 — 승자 없음).
  - 예산: 후보당 RTX ≤20min 또는 CPU ≤120min (**고정 환산 1 RTX-min = 6 CPU-min**) — 디바이스는
    후보 단위 선택·attempt ledger 기록·후보 내 혼합 금지. 실패 후보 = 실측 소모 전액 청구.
    종료 후 val-A 전면 재평가 1회 = RTX ≤1h, M-13 캡 내 청구. 총 캡 = RTX 16h + CPU 24h.
  - 승자 처분: val-A 전면 재평가 + AND-게이트 후보까지만. **본 웨이브 val-B 진입 금지**
    (series=9 봉인·arm 추가 금지 승계) — 차기 웨이브 reveal 후보로만. 외부 루프 = W4 결정.
- **M-14 온톨로지 제약 실물 트랙** (Paul D5·D6 — method ID `onto_constraint_real_v1`, cell ID
  `e2.w3.onto_real1`, **REPORT_ONLY** — 밴드·채택 판정 없음, 산출 = 라이브러리 SHA + 수치 기록):
  - 절차(순서 고정) = ① 규칙 스키마+편찬 절차 선봉인 ② 규칙 편찬(도메인 공리: 벽 위상·연결·
    공간 폐포·개구부 관계) ③ **라이브러리 동결·SHA 봉인** ④ 측정. 측정 후 규칙 추가·삭제·수정
    금지 — 개정 = 차기 프리레그.
  - 모집단 = val-A DEV 전체(분할 내용 해시 `5e16541d…` 기준). truth = 봉인 평가기와 동일
    SEG-IR 라벨. 점수화 = 규칙 위반 플래그 가중합(규칙별 가중 1 고정·학습 없음) → 평가기
    `85481aa4…`로 AUPRC.
  - 잔차 기준 = GNN-A 3-시드 풀 예측(러너 `e9edba8b…` 재생산 계보: formal 코드 `0413f103…`·
    그래프 config `56911f46…`·그래프 빌더 `c95d4a30…`), 임계 0.5의 FP∪FN. 포획률 = |규칙 플래그
    ∩ 잔차| / |잔차 전체|.
  - **F02/F03/F04 합성 사슬 비의존 명시** — D14(합성 축) PARKED 판정 불변.
- **M-15 deterministic_v1 재입법** (method ID `deterministic_v1`, cell ID
  `e2.w3.det_v1_relegislate` — v0와 절연):
  - 절차 = ① 규칙 명세 선봉인(명세 SHA) ② 구현 착지 시 code SHA 봉인 ③ 측정.
  - 측정 범위 = **F01–F07 v1 명의 전건** (F08 이후 소관 아님). 지표·밴드 = 원 F01–F07 프리레그
    문언 그대로 승계(v1 명의 신규 측정). 판정 = 셀별 PASS/FAIL/INCONCLUSIVE(원 규칙).
  - 킬 = 명세 봉인 전 산출 수치 = INVALID · v0 수치와의 비교·백필 금지 승계.
- **M-16 F04G** (cell ID `e2.w3.f04g_gpu_judge`): 게이트 = **G-6=CLOSURE_OK ∧ M-1 ADJ 생존**.
  7 transform · **셀별 RTX ≤50min(1차 캡) · 총 RTX 6h(2차 캡) · 셀 간 사후 예산 이동 금지**.
  로컬 GPU 직렬.
- **M-17 이미지 배심** (cell ID `e2.w3.image_jury` — cursor grok 4.5 구독, frontier API 0):
  게이트 = M-1 판정 후 ∧ 노출 화이트리스트 봉인(**val-B 도면 무조건 제외**). 캡 = 이미지
  ≤120장 · 질의 ≤240회 · 금전 0.

### [CODE_LANDING]
- C-1 R51 래스터 트레이너: **게이트 = M-8 PASS** (OPEN≠READY — 구축+자가시험+SHA 봉인 후에만
  M-9).
- C-2 xlsx 런타임 수리 (수리 검증 시 xlsx 복귀, 전까지 CSV 정본).
- C-3 **RSI 하네스 착지** (Paul D5):
  - **분할 계약(exact)**: 단위 = 도면(drawing_id). 함수 = SHA-256(drawing_id +
    `":e2.w3.rsi_split.v1"`)의 첫 8 hex를 정수 해석, mod 10 ∈ {0,1,2} → **RSI-private**(30%),
    그 외 → **RSI-public**(70%). 층화 없음(결정적 단순 분할 — 도면 단위라 도면 내 누수 없음).
    산출 매니페스트 SHA 봉인. private < 40도면 → 자가시험 FAIL.
  - **권한 분리**: RSI-private 라벨 읽기 = 봉인 평가기 프로세스(C-3 하네스)만. optimizer·후보
    프로세스 = 경로 가드 fail-closed 차단(val-B·test·RSI-private 전부).
  - **ledger 이원화**: public ledger(optimizer 열람: 후보 코드 SHA·public 점수·비용·keep/
    reject) + private ledger(하네스 전용: private 점수 — **런 완주 후에만 공개**). 둘 다
    append-only JSONL.
  - 반복당 고정 비용 미터링 + 이상 점프 가드 + 산출 스키마 검증 (M-13 문언 인용).
  - **자가시험** = mock 후보로 가드 3종(경로·이상 점프·스키마) 각각 차단 증명 + 분할 결정성
    재현 + private 최소 규모 확인. PASS 전 M-13 발사 금지.

### 처분 전용 (실행 없음)
- **R52** = CONDITIONAL_FRONTIER: M-9 PASS 시 차기 프리레그 후보로만. W3 실행 금지.
- **F04V** = PARKED (NON_GOALS 성문).
- **C70/C71 XP 축** = PARKED: M-11 PASS만으로 해제 불가, 해제는 차기 프리레그.

## 제2조 — 의존 DAG·페이즈 (exact)

```
0A 로스터 JSON 봉인 → 0B amendment3 이중봉인 → 0C M-1(val-B)
Phase 1 (0C 후 병렬): M-2 · M-3→M-4 · M-5→G-6 · M-8 · M-11 · M-12 · M-14 · M-15 ·
                      C-2 · C-3 · G-3 · G-4
Phase 2 (조건부):     C-1 (게이트: M-8 PASS) → M-9 (게이트: C-1 PASS)     [엄격 직렬 사슬]
                      M-6 → [gen3 실행 프리레그(별도 봉인·실행·자격 PASS)] → M-7
                      M-13 (게이트: C-3 자가시험 PASS ∧ M-14 라이브러리 SHA 봉인
                            ∧ proposer 템플릿 SHA·설정 고정 봉인)
                      M-16 (게이트: G-6=CLOSURE_OK ∧ M-1 ADJ 생존) · M-10(GPU 유휴)
Phase 3: T20/M31/M32 F축 (의존 AND 충족 시)
Phase 4: M-17 이미지 배심 (게이트: M-1 판정 후 + 화이트리스트 봉인)
```
GPU 직렬 큐 (exact 순서): M-1 → M-2 → M-16 → M-9 → M-13(GPU 구간) → M-10(유휴 시).
CPU 병렬 = 쓰기 소유 디스조인트 + RAM 워치독 + 동시성 캡(≤6).

## 제3조 — 킬표
amendment3 왕복 실패/해시 불일치→개봉 0 · sentinel 불일치→중단·G-7 부검 · G1∧G2 미충족→
ADJ-FAIL(DEV 역사 보존·RSI_ADOPT 금지·G-7 부검) · 추출기 프리레그 없는 F08–F14 수치→INVALID ·
M-16의 G-6=CLOSURE_OK 미충족 발사→무효 · M-9의 M-8/C-1 선행 미충족 발사→무효 · DGX GPU 수치
밴드 이동→거버넌스 인터럽트 · 배심의 val-B 도면 노출→위반 · **RSI: private 라벨 접근 흔적→런
전체 무효·중단 · 이상 점프 재검증 실패→후보 폐기 · attempt ledger 불연속→중단 · 반복 중
private 점수 노출→런 전체 무효** · M-15 명세 봉인 전 수치→INVALID · M-14 라이브러리 봉인 후
규칙 변경→측정 무효 · 신규 class 결함→중단·상신.

## 제3.5조 — 이상 정지 조문
신규 결함 클래스·ledger 불일치·해시 드리프트·의존 해석 충돌·val-B 실패 발생 시: 대체 해석·
재시도·무언 수리 전면 금지 — 즉시 STOP, 상태 동결, Paul 상신. 해소 전 후속 셀 발사 금지.
**유일 예외 = G-7 read-only 부검**(`e2.w3.autopsy_valb` — 신규 측정·재개봉·수리 금지) 발사.

## 제4조 — 공통 패킷 조항 (전 셀 전문 삽입)
- W3-TELEM: {wall_seconds, peak_rss_bytes, peak_vram_bytes|N/A(no_GPU), device, budget_charge}
  measurement.json+REPORT 서두 이중 기록, 실패 런 포함, 미기록=`*_RESOURCE_NOT_RECORDED`.
- W3-PATH: 전 IO 절대경로·루트 구속·SHA 병기. 상대경로 1건=precheck FAIL.
- W3-SEAL: PREREG_local.json+PREREG.csv 선봉인·SHA를 REPORT 헤더에(수치 전). evidence 정본=CSV.
- W3-BOUNDARY: 제0.5조 경계 문장을 REPORT 서두 인용.
- UNKNOWN 보존·발명 금지·워커 등급 캘리브레이션(수확·목록=저등급, 측정·구축=고등급) ·
  git 금지·서브에이전트 금지·보고 디스크-first.

## 제5조 — NON_GOALS (전건 성문)
G7 Qwen · G8 SSL(킬) · A64/A65(킬) · A′/6차 함대·C2(A0 뒤) · D10/D13(L1 강등 존속) · F06
frozen-test(무접촉) · val-B 2회차·팔 추가 · **F04V(명시 파킹)** · **C70/C71 XP 축(명시 파킹 —
M-11 PASS만으로 해제 불가)** · **R52(조건부 frontier — W3 실행 없음)** · **RSI 외부 루프(W4
결정)** · **gen3 학습 증강 용도(D3 ②)** · gen3 실행(별도 프리레그 전) · Text2CAD/pseudo-12k/
Zenodo 용도 정의 전 사용 · 라이선스 재론.

## 제6조 — 캡표 (exact — 봉인값)
| 셀 | 캡 |
|---|---|
| M-1 | RTX 0.5h · 질의 1회 |
| M-2 | RTX 8h |
| M-3+M-4 | CPU 4h |
| M-5 | CPU 8h |
| M-6+M-7 | CPU 12h |
| M-8 | CPU 6h |
| C-1+M-9 | RTX 12h |
| M-10 | RTX 2h (132h 잔여 내) |
| M-11 | CPU 6h |
| M-12 | CPU 8h (어댑터 타당성 포함) |
| M-13 | RTX 16h + CPU 24h · 반복 ≤30 · 후보당 RTX ≤20min 또는 CPU ≤120min (1 RTX-min = 6 CPU-min) · 종료 재평가 RTX ≤1h 포함 |
| M-14 | CPU 10h |
| M-15 | CPU 4h |
| M-16 | RTX 6h (셀별 ≤50min · 사후 이동 금지) |
| M-17 | 이미지 ≤120 · 질의 ≤240 · 금전 0 |
| G-7 | CPU 4h (발동 시에만) |
| C-2 | CPU 2h |
| C-3 | CPU 8h |
합계 상한: RTX ≤44.5h · CPU ≤96h · frontier API 0 · test권 접촉 0 · DGX-GPU 판정 수치 0.
