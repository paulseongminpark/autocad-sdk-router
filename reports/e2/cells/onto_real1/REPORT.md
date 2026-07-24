# M-14 온톨로지 제약 실물 트랙 (cell e2.w3.onto_real1, REPORT_ONLY)

> 산문 복원 주: 하네스의 서브에이전트 정책 훅이 워커의 `REPORT.md` 파일 쓰기를 차단해, 워커가
> 산문을 메시지로 전달하고 기계 판독 증거(measurement.json + evidence.csv)만 디스크에 남겼다.
> 본 REPORT.md는 오케스트레이터가 그 인라인 산문에서 복원한 것이며, 수치는 전부 디스크 정본
> 인용이다. (R9 표면화: packet↔harness 충돌 — 증거 디스크-first, 산문 복원.)

> **W3-BOUNDARY**: 본 보고의 모든 수치는 **CubiCasa SEG-IR 우주 한정**. E1 실무 도면 전이 미검증.

## 결과 (val-A DEV)
- **단독 규칙 라이브러리 AUPRC = 0.2798** (기저율 0.1169, 약 2.4배 lift). 16공리·가중 1·학습 없음.
- **GNN-A 3시드 풀 AUPRC = 0.9785** (시드별 0.975671/0.973858/0.974749) — 원 GPU 런
  gnn_formal/results.json과 exact 일치 → 잔차는 진짜 봉인 모델에서 나온 것.
- **잔차(FP∪FN @0.5) = 5341** (FP 5131, FN 210; GNN이 0.5에서 과잉 예측 → FP 편중).
- **잔차 포획률** (score≥8) = **0.580**. 곡선: ≥1→0.961, ≥4→0.870, ≥8→0.580, ≥12→0.384.
  FP 포획 ≫ FN 포획 (0.594 vs 0.238 @K=8) → **규칙과 GNN이 같은 "벽처럼 생긴" 기하 혼동을 공유**.

## 규칙 라이브러리 (16공리, 카테고리당 4, DEV lift)
- A 벽 위상: A1 len_norm≥1.0(1.28)·A2 ≥1.5(1.83)·A3 ≥2.0(2.62)·A4 ≥3.0(5.42)
- B 연결성: B1 junction≥6(1.48)·B2 ≥14(2.92)·B3 endpt_deg≥3(1.71)·B4 ≥8(2.14)
- C 공간 폐포: C1 endpt_deg≥4(1.72)·C2 collinear≥2&endpt≥3(1.31)·C3 junction≥10(1.69)·C4 len≥2.0&endpt≥4(3.08)
- D 개구부 관계: D1 shorter-collinear-neighbor(1.50)·D2 D1&len≥1.5(2.18)·D3 parallel≥6(1.65)·D4 similar-parallel-neighbor&len≥1.5(1.67)
- 전 공리 DEV 양의 상관. 규칙별 발화율/정밀도/포획은 evidence.csv per_rule 행.

## 봉인 (전부 ir/train만으로 편찬, DEV 읽기 전 봉인; measure.py가 rules_library 재해시·불일치 시 거부)
- rules_library.py `0b51586b69a7b677f5c1476b48acef07dc52fefbe60350c6e800cd0c81a22f5d` (M-13 RSI 탐색공간 동결 입력)
- PREREG_local.json `97929c61a895f2902ff4aa8eb2ece7f5f60c0b0d9547088dfb3de6515cda81ba`
- measurement.json `4503806c814465ac79eaea4704c4a1c46e51b574bc0fa153c084776da4c4c6e3`
- evidence.csv `395e11aaa613381fa483097cd2f9f873c699401a79640a1c78d9ee74a46d695c`
- split content_hash 5e16541d…(검증) · graph_config 56911f46… · val-B/test/합성 읽기 = 0

## W3-TELEM
wall_seconds 92.25 · peak_rss 939,696,128 B (0.875 GiB) · peak_vram N/A(no_GPU) · device cpu
(CUDA_VISIBLE_DEVICES=-1, torch.cuda.is_available=False → GPU 무접촉) · budget_charge 0.0319 CPU-h / 10h 캡.

## 정직한 한계
- 절대 AUPRC 0.28은 낮다: 기하 전용 손공리 — 벽은 방 경계·창·패널·공간과 기하적으로 혼동됨.
  참조 천장(train-only, 미동결): 같은 17 노드특징 HistGBDT ~0.75 in-sample; GNN 0.98.
- "위반 플래그"는 truth가 is-wall이므로 벽-소속 공리 만족(양성 증거)으로 실현 — 기전 명시.
- 잔차 포획은 FP 지배(|FN|=210뿐); GNN 임계 변경 시 잔차·포획 변함. "flag" K는 보고 선택,
  {1,4,8,12} 전부 보고.
- 이 라이브러리 SHA(0b51586b…)가 M-13 RSI 루프의 동결 탐색공간 입력.

CELL_COMPLETE: e2.w3.onto_real1
