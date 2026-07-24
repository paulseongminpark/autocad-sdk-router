# Task: 벽 의미 탐지기 방법론 발굴 (E2 detector program seed)

## 과업 진술 (한 문장)

실무 CAD 평면도(1.dwg류 DWG)의 블록 정의/엔티티에서 벽 등 구조적 의미를 **사람 라벨 없이** 탐지·학습하는 알고리즘 방법론 후보를 결정론·그래프·ML·DL·RL 전 계열에 걸쳐 발굴하고, 각 후보에 대해 **검증 설계**와 로컬/DGX 실행 계획을 제안하라.

## 배경 (읽고 시작)

- E1 실측: LLM 판정자 2종(ornith 35B, sonnet)의 역할 일치 54.9%, 벽 핸들 Jaccard 평균 0.13 (`reports/e1/calibration_v0.json`). LLM(ornith) vs 결정적 탐지기 상관 0.28 (`reports/e1/wall_crosscheck_v0.md` — top-20 전건 "LLM 고확신 + 탐지기 0쌍").
- 현행 탐지기 `tools/semantic/wall_pairs.py`는 "평행+근접 LINE 쌍" 단일 휴리스틱(v0)이다. R12 레인 스스로 "local wall-pair code implements only deterministic candidate generation"이라 진단했다.
- E1.5(모델×effort 사다리 재판정, 6판정자)가 병행 중 — 그 산출(rationale 포함 silver 후보)은 이 패널 제안의 입력 자원으로 가정해도 된다 (`reports/e1/annot_v1/prereg_e15.json`).
- 기질(substrate) 보유: 결정적 DWG Graph IR(핸들 그래프 — GNN/networkx를 얹을 기반), 합성 정답 생성기(`tools/semantic_gates/synthetic_truth.py`), 실무 DWG 아카이브 145장, 외부 라벨 데이터셋 조사분(R23: FloorPlanCAD=선 단위 의미 라벨, CubiCasa5K — 둘 다 NC 라이선스: 방법 개발 가능·가중치 제품 탑재 불가).

## 제약 (불변)

1. **사람 라벨은 현재 불가** — 정답원은 합성 정답, 외부 라벨 데이터셋(라이선스 준수), 검증 가능한 게이트(metamorphic 등), 판정자 앙상블 silver만.
2. **컴퓨트 봉투**: 로컬(Windows, RAM 64GB, RTX 5070 Ti — RAM 여유는 상시 계측 후 사용) + DGX Spark(Tailscale 접근, 현재 vLLM 서빙 호스트 겸용). 제안마다 로컬/DGX 배치 계획 명시.
3. **검증 설계 없는 제안은 무효** — 각 제안은 (a) 정답원(무엇을 truth로 삼나) (b) 누수 방지(도면 단위 분리 등) (c) prereg 밴드 초안 (d) kill condition (e) 최저비용 프로브를 반드시 포함한다.
4. R26 C07("고정 라벨 분류에 RL은 오용, supervised 우위")은 **교리로 취급하지 말고 증거로 다뤄라** — 발주자(Paul)가 이 결론에 이의를 제기했다. RL 계열이 정당하게 서는 자리(RLVR: 검증 가능한 보상 = 합성 정답/metamorphic 게이트, active acquisition 정책, self-training 루프, 도구 라우팅 bandit)와 서지 못하는 자리를 좌석 각자가 독립적으로 논증하라.
5. VLM(도면 래스터 이미지 이해) 후보를 배제하지 마라 — 단 R23의 "vision-as-SoT 기각, VLM은 판정자 아닌 배심원" 판례와 정합하게: 학습(로컬 오픈 VLM 파인튜닝) vs 프롬프팅(프런티어 VLM silver 생성)의 두 갈래를 구분해 다뤄라.
6. 원본 CAD 파일 READ-ONLY. 이 패널은 조사·설계만 한다 — 코드 실행·파일 수정 없음.

## 읽기 허용 증거 경로

- `C:\Users\PAUL\Desktop\0713_research\lanes\R12_primitive_role_grouping\FINAL_REPORT.md`
- `C:\Users\PAUL\Desktop\0713_research\lanes\R14_arch_object_classification\FINAL_REPORT.md`
- `C:\Users\PAUL\Desktop\0713_research\lanes\R16_space_boundary_opening\FINAL_REPORT.md`
- `C:\Users\PAUL\Desktop\0713_research\lanes\R23_vector_raster_text_graph_models\FINAL_REPORT.md`
- `C:\Users\PAUL\Desktop\0713_research\lanes\R26_rl_preference_active_learning\FINAL_REPORT.md`
- `C:\Users\PAUL\Desktop\0713_research\lanes\R28_evaluation_calibration\FINAL_REPORT.md`
- `D:\dev\99_tools\autocad-sdk-router\tools\semantic\wall_pairs.py`
- `D:\dev\99_tools\autocad-sdk-router\tools\e1_crosscheck.py`
- `D:\dev\99_tools\autocad-sdk-router\tools\semantic_gates\synthetic_truth.py`
- `D:\dev\99_tools\autocad-sdk-router\reports\e1\` (calibration_v0.json, wall_crosscheck_v0.md, annot_v1\prereg_e15.json)

## 평가 기준 (SYNTHESIZE에서 이 순서로 본다)

1. 검증 설계의 강도 (제약 3의 5요소 완비 + 누수·Goodhart 방어)
2. 사람-라벨-제로 제약 하의 실행 가능성 (부트스트랩 사슬이 실제로 닫히는가)
3. 컴퓨트 봉투 적합 (로컬/DGX로 감당되는가, 며칠 안에 첫 신호가 나오는가)
4. 기존 기질 재사용 (Graph IR·synthetic_truth·145 아카이브·E1.5 산출)
5. 방법 다양성 — 프로그램 전체가 결정론/그래프/고전ML/DL/RL/VLM을 고루 커버하도록

## 산출 계약

각 좌석: `seats\<framework>.md` — `## PROPOSALS` 3–7개, 제안마다 {mechanism 1문단, truth source, verification design(5요소), compute plan(local/DGX), kill condition, cheapest probe, expected failure modes} + 카드의 REQUIRED OUTPUT FIELDS.
