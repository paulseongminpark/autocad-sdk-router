# 독립 재검증 평결 — GNN 채택 아크 (검증 좌석: Fable)

- 실행: 2026-07-19 (KST) · 패킷: `D:\runs\e2_program\build\PACKET_verify_adoption_arc.md` · 기본 자세 = 반박 시도
- 제약: **git 명령 전면 미사용** (사용자 지시가 패킷의 "읽기 git 허용"보다 우선) · 서브에이전트 0
- 방법: SHA-256 해시사슬 전량 재계산 · results.json 원자료로부터 수치 독립 재계산(Python 3.12 + numpy 1.26.4) · G9 부트스트랩 10,000회 완전 재실행 · E6 분할 규칙 제로베이스 재유도 · 파일 mtime 시계열 · 봉인 조문 원문 대조

## 종합 평결

| # | 판정 (오케스트레이터, PROGRAM_JOURNAL.md) | 평결 |
|---|---|---|
| V1 | GNN-A 채택 — E6/E7 lift 게이트 통과 (저널 :860) | **CONFIRM** (범위 주석 1건) |
| V2 | SSL 킬 발화 — 도시에 E4:656 문언 (저널 :861) | **CONFIRM** |
| V3 | G9 RL 킬 발화 — A63 밴드 (저널 :958) | **CONFIRM** |
| V4 | E6 캘리브레이션 밴드 통과·:676 킬 미발화 (저널 :1017) | **CONFIRM** |
| ① | 봉인 선행성 (3셀 전부) | **CONFIRM** (해시·구조·mtime 한도 내 — §깊이 참조) |
| ④ | 누출 가드 (val-B/test 접촉 0 · family 교차 0) | **CONFIRM** |

반박 시도는 아래 §반례 장부에 전건 기록했고, 판정을 뒤집는 데 성공한 것은 0건이다.
판정 비영향의 경미 결함 4건을 별도 §에 적었다.

---

## ① 봉인 선행성 — 해시 사슬 + 시계열

**구조 증명(해시 사슬)**: 결과물이 prereg 지문을 물고, prereg가 조문·패킷 지문을 물고 있다.
아래 전 항목을 디스크 파일에서 SHA-256 재계산으로 확인했다 (전부 일치):

| 링크 | 실측 |
|---|---|
| 도시에 `reports/e2/dossiers/calibration_P3.md` = `6641dd63…` | gnn prereg `input_hashes.dossier` == e6 prereg `inputs.calibration_dossier` == 실측 ✓ → **내가 읽은 E4/E6/E7 조문 원문이 봉인판** |
| 프로그램 prereg `reports/e2/prereg_r2_v1.json` = `fc93dad9…` | gnn·g9 prereg의 `prereg_base`/`prereg_r2_v1` 핀과 일치 ✓ |
| `FINAL_PROGRAM_PLAN.md` = `53efc08a…` | g9 prereg `final_program_plan` 핀과 일치 ✓ → **A63 킬 밴드 원문이 봉인판** |
| 패킷 3건 (`PACKET_gnn_formal/g9_rl_diag/e6_calibration_ood.md`) | 각 셀 prereg의 `packet` 핀과 일치 ✓ |
| gnn `prereg.json`=`53d10948…`·`PREREG.csv`=`34dfdd6e…`·`gnn_formal.py`=`0413f103…` | REPORT.md 서두 주장·selftest dual_seal·results.json `artifacts` 블록·e6 prereg `formal_runner` 핀과 전부 일치 ✓ |
| g9 `prereg.json`=`c85c2a13…`·`PREREG.csv`=`c1a94401…`·`content_hash`=`2f3fd80f…`·`g9_rl_diag.py`=`d4537fbd…`·`verifier.py`=`72e33ab0…` | REPORT 서두 3종 주장·results.json 내 임베드·prereg 핀과 전부 일치 ✓ |
| e6 `prereg.json`=`7cc94925…`·`PREREG.csv`=`191fb4ad…`·`e6_calibration_ood.py`=`06fcbb8f…`·`evidence.csv`=`4745e84a…` | REPORT 승계봉인 서두·results.json `artifacts`/`post_execution_immutability` 블록과 전부 일치 ✓ |
| GNN-A·control 체크포인트 6종 (`ckpt/`) | e6 prereg 핀 6/6 일치 ✓ (동결 모델 불변 증명) |
| W2-09 `split_manifest.json`=`8aad64ee…` (content `5e16541d…`) | gnn·e6 prereg 핀 + gnn selftest `manifest_content_hash` 일치 ✓ |
| gnn `results.json` 현재 파일 | e6 results의 `full_val_A_formal_results_sha256_observed`=`fe4a52c4…`와 일치 ✓ → **채택 근거 수치가 E6 시점 이후에도 무변조** |
| 레포 `reports/e2/cells/*` ↔ 원본 `D:\runs\e2_program\cells\*` | 3셀 전 파일 바이트 동일(해시) ✓ |

**시계열(mtime, KST=UTC+9)**: 세 셀 모두 prereg가 결과보다 앞선다.
- gnn_formal: 패킷 19:57Z → prereg 봉인 20:05:14Z(=mtime 20:08Z) → 스크립트 최종 21:03Z → results/REPORT 22:36:14Z (`completed_at` 필드와 mtime 일치)
- g9_rl_diag: 패킷 23:36Z → 구봉인 00:00:57Z → 스크립트 수정 00:02:37Z → **현행 봉인 00:03:11Z** → scorer 동결 00:04:17Z → results 00:04:25Z
- e6_calibration_ood: 패킷 00:14Z → prereg 봉인 00:21:18Z(=mtime 00:22Z) → 재개 노트 00:27Z → 스크립트 최종 00:56Z → results 01:04:28Z

**G9 봉인 교체(superseded) 정밀 분석** — 저널(:960)의 "outcome을 본 뒤 바꾼 것이 아니다" 주장 검증:
- 구·신 prereg의 `frozen` 전체를 JSON 파싱 비교 → 차이는 **`input_hashes.files.g9_script` 한 필드뿐** (`254840b1…`→`d4537fbd…`). PREREG.csv 쌍도 정확히 같은 2줄(content_hash 행 + g9_script 행)만 다름.
- 즉 **밴드·지표·분할·정책·시드·캡은 바이트 동일** — 교체로 이동한 판정 조문이 0개다. 어떤 경우에도 이 교체는 판정을 바꿀 수 없었다.
- 신봉인(00:03:11Z)이 scorer 동결(00:04:17Z)·hidden 내용 개봉(동결 후 150건)·results(00:04:25Z)보다 앞선다.
- 한계: 구판 스크립트(`254840b1…`)의 실물은 디스크에 없어 "JSON 키 순서 수정"이라는 변경 사유 자체는 내용 검증 불가(해시만 봉인에 남음). git 미사용 제약으로 이연. 단 위 문단대로 판정 무영향.

**E6 봉인 승계** — REPORT가 "adopted unchanged; no re-sealing" 명기, `RESUME_NOTE_g5_e6.md`(00:27Z)가 "이전 워커가 팩/데이터 내용을 읽기 전에 봉인(봉인 쓰기 09:21~09:23 KST, 이후 산출 0)·재봉인 금지"를 규정 — prereg mtime 09:22:57 KST가 그 창 안. superseded 파일 없음.

**선행성 총평: CONFIRM.** 단서: git 봉인-증인(커밋 선행 증명)을 쓰지 않았으므로 "절대 시계" 수준의 선행 증명은 아니다 — mtime·내부 타임스탬프는 원리적으로 위조 가능하다. 이 한계 안에서, 해시 상호참조의 정합(특히 e6→gnn 교차 관측 `fe4a52c4…`)과 교체분의 판정-무영향성은 전부 실측으로 성립.

---

## ② 판정 축조 대조 + ③ 독립 재계산

### V1 — GNN-A 채택 게이트: **CONFIRM**

**봉인 조문 원문** (`calibration_P3.md`, 해시 `6641dd63…` 확인):
- E6:675 "development rehearsal에서 formal band 전부 충족: lift `>=0.05`, lift CI low `>0`, …"
- E7:685 "`AUPRC_F>=B*+0.05`; … `P3_lift_CI_low>0`. 모두 AND다."
- §6.1:604 CI = paired family-cluster stratified bootstrap 10,000 (gnn prereg bootstrap 블록과 일치)
- R2 `adoption_gates.cell_pass` "ΔAUPRC(DEV) ≥ +0.01 ∧ family-paired CI 하한 > 0 ∧ 전 가드 PASS"

**독립 재계산** (`gnn_formal/results.json`):
- 9개 시드행 전부 F1·정밀도·재현율을 TP/FP/FN/TN에서 재계산 → REPORT 표와 전건 일치. ECE 6팔값 전부를 저장된 10-bin 표에서 재계산 → 전건 일치.
- 팔 평균 재계산: GNN-A AUPRC **0.97475955**, control **0.87408233** → Δ = **+0.10067721** (저널 +0.1007 ✓)
- 부트스트랩 CI(보고값): ΔAUPRC **[0.09539842, 0.10600993]** — 10k 복제 원본이 results에 없어 재실행은 불가하나, 보고 SE 0.0027069와 정규근사 교차검증 시 [0.09537, 0.10598]로 백분위 CI와 1e-4 이내 정합. (G9에서 동일 계보의 부트스트랩을 완전 재현했음 → V3)
- **대조군 공정성**: 신선 재적합 control 평균 0.8740823342431076 == prereg에 봉인된 W2-02 참조 0.8740823342431078 (float 표기 오차 <1e-12) — 비교 상대를 약화시키지 않음.

**축조 대조**: 게이트 적용이 조문 문언대로인가 —
- lift ≥ 0.05: +0.1007 ✓ (CI 하한 0.0954로 봐도 ✓ — 조문보다 보수적인 적용)
- lift CI low > 0: 0.0954 > 0 ✓ · cell_pass ≥+0.01: ✓ · 전 가드 PASS: ✓(§④)
- B* 해석 양쪽 모두 통과: B*=0.8741(2-hop 포함 최강 고전, 도시에 :602의 max 정의) → +0.1007 ≥0.05 ✓ / B*=0.8315(R2 봉인 동결값) → +0.1433 ✓. **유리한 쪽 선택이 판정을 만든 구조가 아님.**
- Occam-KILL(:862): 조문 "2-hop이 B*+0.10 달성 시" — 0.8315+0.10=0.9315, control 0.8741 < 0.9315 → 미발화 ✓ 산술 정확.
- **범위 주석(판정 유지)**: "ADOPTED"는 웨이브 수준 현직자 교체(W2-02 폐위)다. 도시에 E7 최종 AND의 나머지 다리 — S-node F1≥0.92·S-pair≥0.80(합성 우주 기준)·참 style-OOD·val-B 단발 — 는 **판정문 자체가 :863-864에서 미결로 공개**했고(node F1 0.870<0.92 명시), REL≤0.03∧RES≥0.03 다리는 직후 E6 셀이 실측 통과(V4). 프로덕션 채택이 아니라는 한정이 판정문·:870(오컴 가드 유지)·:1042(val-B 유보)에 반복 명시돼 있으므로 과대 주장 아님. 밴드 이동·유리한 해석 **불검출**.

### V2 — SSL 킬 (E4:656): **CONFIRM**

- **조문 원문** E4:656 — "킬 조건: family dedupe 후 SSL lift CI 하한 `<=0` … supervised HGT만 이기고 SSL이 기여하지 않으면 **self-supervised P3라는 제안은 실패**로 기록하고 별도 제안으로 재프리레그한다." (E4:655 합격선도 "CI 하한이 양수"를 요구)
- **재계산**: SSL lift(GNN-B−GNN-A) ΔAUPRC = 0.97463287−0.97475955 = **−0.00012668**, CI **[−0.00058097, +0.00034416]** → **CI 하한 −0.00058 ≤ 0, 문언 그대로 발화** ✓. ΔF1 CI [−0.00531185, −0.00235348]는 전 구간 음수(악화 방향 보강 증거).
- family dedupe 전제: family-paired 부트스트랩(198가족)·train-valA family 충돌 0으로 충족.
- 판정문이 요구한 후속 행위("조용한 재프리레그 금지·실패 장부 기록")도 저널 :861에 그대로 이행 기록.

### V3 — G9 RL 킬 (A63): **CONFIRM**

- **봉인 밴드 사슬**: `FINAL_PROGRAM_PLAN.md`:69 (A63) "beam−greedy `<0.01` ∧ upper gap `≤0.01`이면 RL kill (훈련 전)" — 파일 해시 `53efc08a…`가 g9 prereg에 핀 → 봉인판 확정. 패킷(:11-12)이 동일 문언 재봉인, prereg `metrics`가 지표를 **도면단위 set-F1 평균 Δ**로 고정(`beam_minus_greedy`="beam64 drawing F1 minus greedy drawing F1", `primary_delta_estimand`="hidden 75도면 도면단위 set-F1 차이의 산술평균"). 전부 측정 전 봉인.
- **재계산** (`g9_rl_diag/results.json` drawings[75]):
  - beam64−greedy 도면평균 = **+0.0027938** (보고 0.002793806… ✓, 저널 +0.00279 ✓) → **< 0.01** ✓
  - 인증최적−beam64 = **+0.0015504** (보고 ✓, 저널 +0.00155 ✓) → **≤ 0.01** ✓
  - **부트스트랩 완전 재현**: numpy `default_rng(20260719)`·가족 3개 복원추출·25도면 유지·10,000회 → bg mean 0.002782716, CI [0.000000000, 0.004872647] / eb mean 0.001536899, CI [0.000000000, 0.004651163] — **보고값과 소수 9자리 일치**. CI 상한(0.00487)조차 밴드 0.01의 절반 이하 → CI 수준에서도 킬 강건.
  - 보조 수치 재검: greedy pooled F1 0.9952993(보고 0.995299 ✓)·수락 65/75, beam64 0.998433·70/75, 인증최적 1.0·75/75, beam 폭 4/16/64 도면별 결과 동일 ✓, greedy==인증최적 65/75 재계수 ✓, 인증 75/75, CPU 0.00927h/72h ✓. 저널 여유 주장 "3배·6배": 0.01/0.0027938=3.58, 0.01/0.0015504=6.45 ✓.
- **축조 대조**: 두 조건이 봉인 지표(도면평균 set-F1)로 동시 성립 — 문언 그대로. R2 사다리("갭≥0.01 시에만 bandit")의 단일-갭 독법으로 봐도 최대 갭(인증최적−greedy=+0.0043)<0.01 → 동일 결론. **어느 봉인 독법에서도 킬.**

### V4 — E6 캘리브레이션 무해 (REL/RES 밴드): **CONFIRM**

- **봉인 밴드**: e6 prereg `sealed_band_text` = "temperature 전후 REL≤0.03 ∧ RES≥0.03"·"style drop≤0.10"·":676 calibration 실패를 threshold 재탐색으로 덮지 않는다" — 도시에 E6:674-676 문언과 일치, REPORT에도 무판정 인용.
- **재계산** (`e6_calibration_ood/results.json`, GNN-A, cal-eval만):
  - 6개 상태(3시드×전/후) 전부의 REL·RES·ECE를 저장된 10-bin reliability 표에서 재계산 → **전건 1e-12 이내 일치**.
  - 시드 평균: REL **0.008190 → 0.007360** (저널 0.0082→0.0074 ✓; 밴드 ≤0.03의 ~1/4) · RES **0.084217 → 0.085875** (저널 0.0842→0.0859 ✓; ≥0.03의 2.86배) · NLL 0.074094→0.067559 ✓ · T = [1.4221, 1.7239, 1.4680], 평균 1.538(저널 ≈1.54 ✓) · ECE 0.02783→0.02788(저널 "≈0.028 그대로" ✓ — 봉인 지표 아님 명기 정확).
  - **"전후" 전건**: 시드별 최악값 REL 0.009201(before,17) ≤0.03 ✓ · RES 최소 0.083586(before,29) ≥0.03 ✓ — **전/후·전 시드에서 밴드 성립**. 유리한 상태 선택 여지 자체가 없음.
  - threshold 0.5 판정 플립 = [0,0,0] ✓ (재탐색 금지 조문과 정합, `threshold_search_count`=0)
  - style 슬라이스: pooled−category AUPRC 최악 격차 **+0.001947**(high_quality_architectural; 저널 +0.0019 ✓) ≤0.10 — 단 판정문이 이를 **IID 슬라이스로 한정**하고 참 style-OOD를 미판정 유보(:1017) — prereg `style_limit` 문언과 정확히 일치, 승격 없음 ✓.
  - **분할 제로베이스 재유도**: SHA-256("e6.calibration.ood.v1|43|{family_id}") 정렬 → 선두 99=cal-fit 규칙을 그대로 재구현 → 기록된 198건 배정과 **불일치 0**, `assignment_sha256`·cal-fit/cal-eval drawing-ids SHA 3종 전부 재계산 일치, 가족 교차 0.
  - **교차 재현**: e6가 GNN-A를 val-A 전량 재추론해 gnn_formal 보고치와 대조한 `full_val_A_reference_numeric_check` — 3시드 전부 카운트 델타(tp/fp/fn/tn/n) 0, AUPRC 델타 ~1e-6 이내.

---

## ④ 누출 가드 재확인 — 전건 0

| 가드 | gnn_formal | g9_rl_diag | e6_calibration_ood |
|---|---|---|---|
| val-B 도면 읽기 | 0 (`execution_scope`+`read_counters`; selftest는 metadata-only 대조로 한정 명기) | 0 (`scope.val_b_reads`) | 0 (`execution_scope`+`data_audit`) |
| test 읽기 | 0 | 0 (`repository_test_reads`) | 0 |
| 원본 CAD | 0 | 0 | 0 |
| family 교차 | train↔val-A 충돌 **0** (+selftest `family_overlap_count` 0) | reward↔hidden 가족 서로소·scorer 동결(00:04:17Z) 후에만 hidden 내용 개봉 150건·동결 후 학습 갱신 **0** | cal-fit↔cal-eval 가족 교차 **0** (재유도로 독립 확인) |
| 기타 | 서브에이전트 0·repo 수정 0·git(패킷 후) 0·OOM 강하 미발동 | GNN 사용 0·CubiCasa 0·hidden은 동결 전 hash-only 1,612건 | 학습/재적합 0·threshold 탐색 0·밴드 판정 출력 0·체크포인트 불변 |

세 셀 모두 `judgment_emitted=False`/`judgment=None` — "셀은 수치만, 판정은 오케스트레이터" 계약 준수.

---

## ⑤ 반례 시도 장부 (전부 기각)

1. **G9 지표 바꿔치기 시도** — terminal objective(0.5·F1+0.5·수락) 기준 최적−greedy 갭은 1.0−0.9312=**+0.0688 ≥ 0.01**, 수락률 갭도 10/75=+0.133. 이 독법이면 킬은 미발화다. **기각 사유**: 킬 지표는 측정 전 3중 봉인(A63→패킷 Δ정의→prereg `metrics`)이 도면평균 set-F1로 고정했고, terminal objective는 prereg가 "completed-state 비교 전용"으로 별도 봉인. 사후에 이 지표로 갈아타는 쪽이 오히려 밴드 이동(K07급)이다. 해당 수치는 results에 전량 공개돼 있어 은폐도 아님. 차기 프리레그 설계 입력으로만 유효.
2. **G9 CI 하한 0 공격** — 두 Δ의 CI가 [0.000, …]로 0에 닿음 → "beam 우위 자체가 유의하지 않다"는 방향의 반례인데, 이는 킬을 **강화**하는 방향이다(여지가 더욱 없음). 기각.
3. **G9 봉인 교체 = 사후 조작 가설** — §① 정밀 분석: 변경이 스크립트 해시 재핀 1필드뿐, 판정 조문 이동 0. 신봉인이 scorer 동결·hidden 개봉·결과보다 선행. 기각(잔여 한계: 구판 스크립트 실물 부재 — 판정 무영향).
4. **채택 게이트 과대 주장 가설** — E7 전체 AND 미충족 상태의 "ADOPTED"가 유리한 해석인가: 판정문 자체가 미충족 다리를 열거·공개(:863-864)하고 프로덕션 채택을 별도 게이트로 유보(:870, :1042). W2-02 채택과 동일한 웨이브-수준 용법(선례 일관). R2 `rsi_status_layers` 3층 분리 조문과 정합. 기각.
5. **E6 유리한 상태 선택 가설** — "전후" 중 좋은 쪽만 인용했는가: 전/후·전 시드 12개 값 전부 밴드 내(§V4). 최악 시드값 기준으로도 3.3배 여유. 기각.
6. **E6 대조군 유기 가설** — control(REL≈0.0001)이 GNN보다 훨씬 좋음을 숨겼는가: 저널 자체가 "ECE 4배 나쁨"을 채택 시점에 공개했고, E6 밴드의 주어는 P3(GNN)다. 기각.
7. **B* 선택 조작 가설** — §V1: 어느 B* 독법에서도 통과. 기각.
8. **수치 전사 오류 사냥** — 저널·REPORT·results 3층에서 패킷 인용 수치(Δ+0.1007, CI[0.0954,0.1060], +0.0028, +0.0016, REL 0.0074, RES 0.0859) 전부 원자료 재계산과 일치(반올림 표기만 상이). 기각.

## 경미 결함 (판정 비영향, 기록용)

1. **PACKET_gnn_formal.md:10-12 조문 라벨 한 칸 밀림** — "E4(646행)·E5(656행)·E6(666행)·E7(676행)"로 표기했으나 도시에 실제 번호는 646=E3킬·656=E4킬·666=E5킬·676=E6킬. 행번호·내용 서술은 정확하고, **저널 판정문(:861 "E4", :863 ":676")은 도시에 자체 번호를 올바르게 사용** — 오라벨이 판정에 전파되지 않았다.
2. **저널 :860 "각각 10배·2배 여유"** — CI 하한 0.0954는 R2 cell_pass 문턱 +0.01의 9.5배, E6/E7 lift 밴드 0.05의 1.9배다. 산술은 성립하나 "10배"의 귀속 문턱(+0.01)이 문장에 인용된 두 조문("CI>0"·"≥0.05")과 어긋나게 읽힐 수 있는 축약.
3. **저널 :946·:963 "완전 탐색"** — 실제로는 hidden 75도면 전부 후보 수>18이라 exhaustive 열거가 아닌 결정적 branch-and-bound 경로(`upper_bound_replacement_count`=75)로 **전 도면 최적성 인증**(incumbent==bound). "인증된 최적해" 주장 자체는 정확.
4. **저널 :1005 E6 "7시간 행"** — E6 파일 시계열(봉인 00:21Z→완료 01:04Z, 중단 창 ~5분)과 부정합(G5의 행 서사가 E6에 전이된 것으로 보임). 봉인 수치·판정 무관 서사 결함.

## 검증 한계 (이연 항목, 정직 기록)

- **절대 시계 선행성**: git 미사용(사용자 지시)으로 커밋-증인 대조를 하지 않았다. mtime·내부 타임스탬프·해시 상호참조 수준에서의 선행성만 성립 (이 세션의 환경 스냅샷에 보인 커밋 로그 문구들은 저널 근거 라인과 정합했으나, 독립 검증 수단으로 사용하지 않음).
- gnn_formal 부트스트랩 CI는 복제 원본 미보존으로 재실행 불가 — SE 정규근사 교차검증 + G9 동계보 완전 재현으로 대체.
- G9 구판 스크립트(`254840b1…`) 실물 부재 — 변경 사유("JSON 키 순서")의 내용 검증 불가, 판정 무영향은 §①에서 증명.
- 검증기(verifier.py) 내부 로직·gen2 팩 truth의 재감사는 본 패킷 범위 밖(G1 셀 소관) — 해시 불변만 확인.

## 결론

오케스트레이터의 판정 3건(채택·SSL 킬·RL 킬)과 E6 무해 판정은 **전부 봉인 조문 문언대로 축조되었고, 근거 수치는 원자료에서 독립 재계산으로 전건 재현되며, 봉인 선행성·누출 가드는 실측 가능한 전 수단에서 성립한다.** 반박 자세로 시도한 8개 공격 벡터는 모두 기각됐다. — 4/4 **CONFIRM**.

VERDICT_COMPLETE: verify_adoption_arc (seat=fable)
