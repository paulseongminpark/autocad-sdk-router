# SEAT — platt_strong_inferencer · 벽 의미 탐지기 방법론 (Phase A, BLIND)

생성 규율: 이 좌석은 Platt 강한 추론(strong inference) / Chamberlin 다중 작업가설 카드로 사고한다. 방법론 후보를 "취향으로 추천"하지 않는다 — 후보들을 **상호배타 가설의 장(field)에 대한 판별 실험 큐**로 재정식화하고, 실행 전에 outcome→kill 판별표를 동결하며, kill 권한은 외부 게이트에만 둔다. **이 문서는 어떤 가설도 죽이지 않는다** (0라운드, 실험 미실행 — 좌석은 kill 권한이 없다).

## 0. 재정식화 — "어떤 방법이 좋은가?"가 아니라 "벽 신호는 어느 메커니즘 계열에 사는가?"

판별 질문 두 개:
- **Field-1 (메커니즘 지배)**: 사람 라벨 없이 실무 DWG에서 벽 정체성을 회수할 때, 어느 메커니즘 계열이 지배 신호를 담는가 — 그리고 E1이 보고한 "LLM 고확신 vs 탐지기 0쌍" 불일치는 애초에 실재하는가?
- **Field-2 (RL 적용성)**: R26 C07("고정 라벨 분류에 RL 오용")은 이 과업의 어느 부분과업에서 성립하고 어디서 무너지는가? (제약 4: 교리 아닌 증거로)

### E1 증거 재독해 (수치는 산출 아티팩트 병기)

- 역할 일치 0.5491 (n=377), 핸들 Jaccard 평균 0.1319 / zero_frac 0.682 — `reports/e1/calibration_v0.json`
- ornith likelihood vs 탐지기 쌍수 Pearson 0.2842, top-20 divergent 전건 "고확신+0쌍" — `reports/e1/wall_crosscheck_v0.md`
- **코드 확인 사실 1**: 현행 v0는 def_entities 중 `dxf_name=="LINE"`만 읽고(`tools/semantic/wall_pairs.py:46`), 중첩 INSERT를 전개하지 않는다(`:218-239` — block_definitions의 def_entities만 순회). LWPOLYLINE/MLINE/ARC 벽과 중첩 블록 내부 기하는 **원리적으로 입력에서 배제**된다. top-20의 n_h_det=0은 "탐지 실패"가 아니라 "입력 배제"였을 수 있다.
- **코드 확인 사실 2**: `gap_range=(30.0, 500.0)`은 mm 스케일 가정(`wall_pairs.py:144`). 도면/블록이 m 단위·이형 스케일이면 gap이 하한 30 미만으로 전멸 → 0쌍. 단위 불일치는 별도의 계측 아티팩트 후보다.
- **코드 확인 사실 3**: top-20 정렬은 high_likelihood_zero_pairs 종을 구조적으로 우선한다(`tools/e1_crosscheck.py:113-117`, kind 0 우선). "top-20 전건 단일종"은 부분적으로 정렬 설계의 산물 — many_pairs_low_likelihood 종의 규모는 미보고 상태다.
- **의심 패턴**: top-20의 n_h_ornith가 17/20에서 정확히 10 (나머지 8,8,5 — `wall_crosscheck_v0.md` 표) — "최대 10개 나열" 지시의 서명일 개연성. 판정자 출력이 증거 접지가 아니라 나열 지시를 따른 아티팩트인지 P0가 원시 출력에서 판정한다.
- 판정자 간 likelihood Pearson은 0.4866(중간)인데 핸들 집합 zero_frac은 0.682 — "게슈탈트/prior에는 동의하나 접지(grounding)에는 불일치"라는 서명. 이름-prior(H3) 또는 접지 아티팩트(H0)와 정합.

### 가설의 장 (요약 — 정식 정의는 §hypothesis_set)

- **H0** 계측 아티팩트 널: E1 불일치는 도구(핸들 공간 불일치·조인·입력 배제·단위·나열 지시)가 제조했다.
- **H1** 기하 충분: 커버리지 완성된 국소 기하 규칙(평행쌍+두께 밴드)이면 지배 신호로 충분.
- **H2** 위상/문맥 필요: 국소 쌍 기하는 과소결정 — 네트워크 문맥(정션·폐합·개구부 인접)이 결정적.
- **H3** 관례 지배: 레이어명/블록명/해치 관례가 실무 DWG의 지배 신호.
- **H4** 시각 게슈탈트: 래스터 공간(poché·이중선 게슈탈트)이 판독에 가장 유리.
- **HR1/HR2** (Field-2): 집합-조립 부과업에서 RLVR이 동률 컴퓨트의 탐색(beam/ILP)·supervised를 이긴다 / 이기지 못한다(C07 성립).

배타성 독법: H1–H4는 "지배 신호" 주장으로서 상호배타 — 그 계열을 제거하면 성능이 prereg 밴드 아래로 붕괴하는 단일 계열이 무엇인가를 다툰다. 혼합 결과는 배합으로 뭉개지 않고 Δ-게이트로 판별하며, 판별 불가면 abstain한다 (카드 금지: averaging).

자기기각 패스 (strawman 방지):
- "H5: 판정자 silver만으로 충분(탐지기 불요)" — 기각: 그 판별은 E1.5가 이미 소유한다(`prereg_e15.json` B1/B4 밴드, 동결됨). 중복 kill-signature — 장에 넣지 않고 그 게이트 산출을 소비한다.
- "H6: 사람 라벨 없이는 원리적 불가" — 기각: 메커니즘 가설이 아니라 프로그램 전체의 여집합. budget-exhausted 종결 상태(§abstain_condition A4)가 담당한다.

라우팅 (카드 규칙 6 — 가설-선택이 아닌 문제의 거절): gap 밴드·각도 허용치 등 연속 파라미터 튜닝 = 추정 문제 → 판별 경주 밖(각 제안 내부의 estimation 절차로 격리, 가설 지위 부여 금지). "벽이란 무엇인가" 어휘 제정 = legislation → E1.5 B1<0.60 시 projection 재설계로 회귀(동결 라우팅 준수). 단, 라이벌 정의가 구체 케이스-쌍을 다르게 분류하면 그 쌍으로 게이트 판별 가능(카드 예외 조항) — 그 경우만 판별 대상으로 승격.

---

## PROPOSALS

7건. 각 건은 판별표의 실험이다. 공통 규율: 모든 밴드는 실행 전 `reports/e2/prereg_*.json`으로 동결(커밋 sha 핀 — E1.5 prereg 패턴 그대로), 모든 수치 주장은 산출 아티팩트 경로 병기, 원본 DWG READ-ONLY·ASCII staging 사본, 로컬 RAM은 상시 계측 후 사용.

### P0 — E1 불일치 법의학 감사 + 핸들-공간 계약 (dissolver · 결정론)

**mechanism**: top-20 divergent def(+무작위 대조 20 def)에 대해 결정론 감사 스크립트 1개를 돌린다: (i) def별 엔티티 타입 히스토그램(LINE/LWPOLYLINE/MLINE/ARC/INSERT/HATCH), (ii) LLM 인용 핸들의 실재성·타입·소속(해당 def 내인가, 중첩 def 내인가, 아예 부재인가), (iii) 중첩 INSERT 깊이와 내부 기하량, (iv) def 좌표 bbox 스케일 분포(단위 불일치 검출 — gap_range mm 가정 대비), (v) 블록명 토큰('평면도' 등)과 wall_likelihood의 상관, (vi) n_h_ornith=10 클러스터의 원시 출력 대조(나열 지시 아티팩트 여부). 학습도 판정자도 없다 — IR에 어떤 엔티티가 실재하는가는 결정론적 사실이므로 이 실험은 진리원 논쟁 자체가 없다. 강한 추론의 규칙 3(dissolver 먼저): E1 불일치가 계측기 제조물이면 "탐지기가 약하다"는 전제 위에 세운 모든 고가 실험이 불필요해진다.

- **truth source**: DWG Graph IR 자체(엔티티 실재는 결정론 사실) + E1 원시 JSONL(`reports/e1/` 내 ornith 산출).
- **leakage 방지**: 학습 없음. 분류 규칙(부재/비-LINE/중첩/단위의심 판정 기준)을 결과 보기 전 prereg로 동결. 대조군 20 def 무작위 시드 고정.
- **prereg band 초안**: top-20에서 LLM 인용 핸들의 ≥50%가 def 내 부재 또는 비-LINE → H0 생존 강화 + crosscheck v0 해석 RETRACT 후보; ≤10% 부재이고 대다수가 쌍가능 LINE → H0 kill. bbox 스케일이 mm 가정과 ≥10× 이탈하는 def 비율 ≥30% → 단위-보조가정 위반 플래그(P1에 주입).
- **kill condition**: O-B(핸들 실재·쌍가능 다수)면 **H0 kill**. O-A(다수 부재/비-LINE)면 "불일치는 실재하며 탐지기 개념 결함" 전제가 죽고, E1 기반 서사 전체가 재계측 대상이 된다.
- **cheapest probe**: 이 실험 자체가 프로그램 전체의 최저가 프로브다 — 기존 IR JSON + JSONL 위 파이썬 스크립트 1개.
- **compute plan**: 로컬 CPU <1h (스크립트 작성 반나절). GPU 0, LLM 0, DGX 불사용.
- **expected failure modes**: top-20 선택 편향(전건 익명 `*U###`/xref-바운드 블록 — 정렬 설계가 만든 편중임을 보고서에 명시하고 대조군으로 상쇄); def-이름 정규화 버그가 아티팩트를 재제조(공백 변형 케이스 결정론 테스트); cp949 콘솔 깨짐을 데이터 손상으로 오진(코드포인트로 판정).
- **판별 기여**: H0 생사 + H1(커버리지 갭 실증 여부)·H3(이름토큰↔likelihood 상관) 방향 증거 + P1의 단위-보조가정 입력. 뒤 실험들을 불필요하게 만들 수 있는 유일한 dissolver.

### P1 — 커버리지-완전 결정론 탐지기 v1 (엔티티 정규화 + 정션 후필터 · 결정론)

**mechanism**: v0 앞에 정규화 프런트엔드를 붙인다 — LWPOLYLINE→세그먼트 분해, MLINE 전개, 중첩 INSERT의 transform(이동·회전·스케일·미러) 적용 전개(flatten), ARC의 동심 오프셋쌍 처리, INSUNITS/bbox 기반 단위 정규화(P0 산출 소비) — 그 위에 기존 평행쌍 휴리스틱을 돌리고, 고립쌍 vs 벽 네트워크를 가르는 정션-그래프 후필터(쌍들이 체인·교차로 연결되는가)를 더한다. H1(기하 충분)의 최강 형태를 만들어 시험한다: 이 가설은 "v0의 실패는 개념이 아니라 커버리지"라고 주장한다.

- **truth source**: (a) 합성 벽 truth 생성기 — 기존 `tools/semantic_gates/synthetic_truth.py`의 correct-by-construction + mutate 패턴을 벽으로 확장(벽 쌍/체인/교차 + distractor 계열: 치수선·그리드선·가구 블록; 뮤테이션: 한쪽 선 삭제·gap 이탈·회전 어긋남), (b) FloorPlanCAD 선-단위 의미 라벨(CC BY-NC — **방법 개발 전용, 가중치·파생물 제품 반입 금지 방화벽 문서화**, R23 판례 준수) 외부 교차.
- **leakage 방지**: 생성기 파라미터(두께 분포·distractor 밀도) 동결 후 평가; FloorPlanCAD 도면 단위 스플릿; **145 아카이브는 파라미터 튜닝 금지**(순수 추론 대상 — 튜닝은 synthetic train split에서만).
- **prereg band 초안**: synthetic held-out에서 쌍 recall ≥0.9 · precision ≥0.8; FloorPlanCAD 벽-선 F1에서 v1−v0 ≥ +0.2 절대(v0의 FPC 값 자체를 먼저 계측·동결 — 현재 미계측).
- **kill condition**: 완전 정규화 후에도 synthetic recall <0.7 또는 FPC F1 <0.4 → **H1 kill**(국소 기하 불충분) → H2 승계. 역방향: 밴드 통과면 H2·H3·H4는 "지배" 주장에서 demote.
- **cheapest probe**: divergent-20 def만 정규화 후 재실행 — n_pairs 0→>0 전환 계수. 1일, 로컬.
- **compute plan**: 로컬 CPU only(기하 연산·그래프 후필터). 145장 배치 시 IR 스트리밍 파싱으로 RAM 계측 하 운용. DGX 불사용.
- **expected failure modes**: INSERT transform 전개 버그(미러·비등방 스케일) — synthetic에 중첩 케이스를 넣어 왕복 검증; synthetic 분포가 휴리스틱 가정과 동형이 되는 Goodhart(FPC 외부 교차가 방어); FPC의 "벽 선" 정의와 우리 5-클래스 어휘의 불일치(라벨 스키마 이중 파서 합치 검사); 단위 정규화 오판(bbox 휴리스틱의 한계 — 판정 근거를 per-def 기록).
- **판별 기여**: H1의 생사를 직접 판정. E-P2의 Δ-베이스라인 제공.

### P2 — Graph IR + GNN 벽-멤버 분류기 (그래프·DL — 문맥 Δ-판별)

**mechanism**: 결정적 DWG Graph IR 위에 노드 피처(엔티티 타입·길이·각도·레이어 임베딩은 mask-ablation 축), 엣지 피처(평행성·gap·overlap·끝점 접속 — 사실상 wall_pairs 후보 그래프의 학습판)를 얹고 GraphSAGE/GAT급 소형 GNN으로 엔티티의 벽-멤버 여부를 분류한다. 훈련 truth는 3원: synthetic / FloorPlanCAD(transfer) / E1.5 상위합의 silver(**B1 밴드 통과 시에만 활성화**). 본질은 H2의 Δ-실험이다: 동일 truth·동일 스플릿에서 P1(문맥 없는 최강 기하) 대비 문맥 피처의 기여를 잰다 — "GNN이 좋더라"가 아니라 "문맥이 없으면 얼마가 무너지는가"를 계측한다.

- **truth source**: 3원 삼각측량(synthetic / FPC / E1.5 silver) — 어느 단일원도 신뢰하지 않으며, 승격 주장은 ≥2원 concordance를 요구.
- **leakage 방지**: 도면·def 단위 스플릿; silver 훈련 def와 평가 def 분리(384-def 벤치의 def-단위 분할); **이름/레이어 피처 mask-ablation 암 필수** — 마스크 시 성능이 붕괴하면 그것은 H3 증거인 동시에 "silver를 이름으로 맞추는 누수" 경보(E1 판정자가 이름을 탔다면 silver 자체가 이름과 상관).
- **prereg band 초안**: 동일 held-out에서 GNN vs P1: ΔF1 ≥ +0.1 → H2 지지; [0, +0.1) → H2 demote(문맥 한계 기여); < 0 → H2 kill(현 계측기 하). silver 암 활성 조건 = E1.5 B1 ≥ 0.70 (`prereg_e15.json` 동결 밴드 소비).
- **kill condition**: 위 밴드. 부수: synthetic-훈련 GNN이 FPC에서 결정론 베이스라인 미달 → "synthetic 분포 충분" **보조가정 kill**(H2 본체가 아님 — 보조와 본체를 분리 기재).
- **cheapest probe**: 동일 피처로 로지스틱 회귀/GBDT 1일(고전 ML 사다리 하단) — 선형·트리가 이미 점프하면 GNN은 불요(Occam 사다리를 카드 규칙 3의 비용 순서로 강제).
- **compute plan**: 피처 빌드 로컬 CPU; 훈련은 RTX 5070 Ti 16GB로 충분(384 def 규모, 미니배치 이웃 샘플링); 145장 modelspace 전체 그래프로 확장 시에만 DGX 야간 슬롯(vLLM 서빙과 시간분할 합의, 체크포인트 재개 전제 — DGX는 현재 Ornith 서빙 겸용).
- **expected failure modes**: silver 노이즈(역할 일치 0.5491의 세계 — 상위 판정자 만장일치 def만 사용); 판정자-버릇 Goodhart(rationale 필드로 증거 클래스 분포 감사); 레이어명 피처의 자명 누수(mask 암이 폭로); IR 인접성 완전성 미증명(R23 지적 — 인접성 통계를 P1 정규화 산출로 먼저 계측하고 훈련).
- **판별 기여**: H2 생사(Δ-게이트) + H3 방향 증거(mask 암) + 고전ML/DL 사다리 커버.

### P3 — Metamorphic/불변식 게이트 배터리 (라벨-프리 심판기 제작 · 평가 방법론)

**mechanism**: 벽 탐지기용 metamorphic 관계 배터리를 만든다 — (불변) 강체변환·미러·단위 재스케일에 예측 불변, (equivariance) 두께 밴드 내 섭동에 멤버십 유지, (일관성) 검출 쌍이 체인·정션으로 연결되어 공간 분할에 참여(R16 arrangement 계열), (anti-관계) 벽-유사 오프셋의 치수선/그리드 주입이 벽 수를 늘리면 위반. 이 배터리는 **모든 후보(P1/P2/P4/P5)의 공통 심판기**다: 145 실코퍼스에서 라벨 없이 채점한다. 관계 자체의 자격을 synthetic 뮤턴트 conviction으로 심사한다(게이트의 게이트 — 기존 L5 `mutate()` 패턴 그대로). R28의 metamorphic 라인을 벽 도메인에 실체화한 것.

- **truth source**: 관계 자체(선험 논증) + synthetic admission 게이트: correct-by-construction IR에서 위반 0% AND 시딩 뮤턴트 ≥95% 적발인 관계만 배터리 편입.
- **leakage 방지**: 관계 목록·역치를 어떤 후보 채점 전에 동결; admission은 synthetic만 사용(실코퍼스로 관계를 튜닝하면 심판기가 후보에 오염).
- **prereg band 초안**: 후보 승격 요건 = 불변 관계 위반율 ≤1%(145 표본); 배터리 자체의 뮤턴트 conviction ≥95%(기존 L5 기준선 준용).
- **kill condition**: 회전-불변 위반 후보는 silver 점수 불문 즉사(하드 게이트). 전 후보 대량 위반 & synthetic 통과 → 해당 관계 무효 또는 synthetic-실코퍼스 도메인 갭(**보조가정 kill**로 귀속, 후보 kill 아님).
- **cheapest probe**: 관계 2개(회전 불변 + distractor 주입)만 구현해 현행 v0·20 def에 적용. 1일, 로컬.
- **compute plan**: 로컬 CPU, embarrassingly parallel(def 단위). GPU 0. DGX 불사용.
- **expected failure modes**: 관계가 약해 전부 통과 — **판별력 0인 실험은 카드 규칙 2에 따라 큐에서 제거**(아무것도 못 죽이는 행은 페기); 폐합 관계가 오픈플랜에서 과강(R16 KR2 — 스코프 태그로 완화); "0벽 예측이 무위반" 퇴행(재현율 강제항을 synthetic으로 검증해 배터리에 추가); 관계 간 상관(독립성 착시 — 위반 패턴 상관 행렬 보고).
- **판별 기여**: 실코퍼스에서 H1/H2/H4 후보를 라벨 없이 비교하는 유일한 계기. 전 계열 동률이면 §abstain_condition A1의 트리거 입력.

### P4 — RLVR 벽-집합 조립 정책 (RL 레인의 정직한 자리 — C07을 증거로 판별)

**mechanism**: R26 C07을 교리가 아닌 판별 대상으로 취급한다 — C07 자체가 draft 레인의 NEEDS_WEB_VERIFY 주장임을 기록해 둔다(이중으로 교리 자격 없음). 독립 논증(제약 4 요구): (i) **엔티티 단위 고정-라벨 분류** — 같은 신호로 supervised 베이스라인이 항상 구성 가능 → RL 열위 예상, C07 잠정 유지(단 실측 게이트로 종결); (ii) **집합-구조 조립**(쌍→체인→네트워크의 부분집합 선택 — 조합적 구조, 보상은 검증가능·비미분: 합성 정답 일치 + metamorphic 점수) — RLVR의 정당 후보지. 단 생존 조건은 "동률 컴퓨트의 beam/ILP 탐색과 supervised+greedy를 이긴다"이다 — 실무에서 탐색이 이기는 경우가 많다는 것이 정확히 kill 후보; (iii) **획득 순서 결정**(어느 def에 비싼 판정자/렌더를 지출하나) — horizon≈1 contextual bandit(R26 C10과 정합), full RL 아님 — P7로 분리하지 않고 이 레인의 부속 절차로 격리; (iv) **self-training 루프** — RL이 아니라 EM/자기증류, 명명 교정만 하고 P2의 훈련 옵션으로 귀속. 실험: 동결 보상 위에서 policy-gradient vs beam vs supervised+greedy, 인코더 공유(P2와 동일 가중치)·동일 월클록.

- **truth source**: synthetic 벽 truth(보상 오라클 — RLVR의 "verifiable" 자격) + metamorphic 배터리(실코퍼스 보상). **E1.5 silver는 보상에 절대 불사용**(판정자-보상 해킹 차단, R26 C08) — 최종 held-out 일치 보고에만.
- **leakage 방지**: 보상 함수 sha 동결 후 훈련; synthetic 생성기 train/eval 스플릿 분리; silver는 훈련 루프 밖.
- **prereg band 초안**: RL vs beam(동일 보상·인코더·월클록): synthetic held-out ΔF1 ≥ +0.05 AND metamorphic 위반 Δ ≤ 0 → **HR1 생존 + "C07의 이 과업 적용" kill**; 미달 → **HR1(RL 레인) kill** — 어느 쪽이든 Paul의 이의가 요구한 판별이 증거로 종결된다.
- **kill condition**: 위 밴드 + 보상해킹 시그니처(정책 보상↑ & synthetic F1↓ 괴리) 검출 시 즉시 kill + 사건 기록.
- **cheapest probe**: **학습 0의 보상 지형 측정** — greedy vs beam vs random을 동결 보상에서 1일. greedy≈beam≈상한이면 순차-선택 구조가 자명 → **훈련 전에 RL kill**(최저가 RL 판결 — 카드 규칙 3).
- **compute plan**: 롤아웃 CPU 병렬(로컬 64GB, 계측 하); 정책/인코더는 5070 Ti(소형 — P2 인코더 공유); 시드 3 ablation만 DGX 야간 슬롯. Ornith 서빙과의 GPU 경합 없음(로컬 우선 설계).
- **expected failure modes**: 퇴행 정책("0벽"이 무위반) → 재현율 강제항(P3에서 검증된 것만); 약한 베이스라인이 만든 가짜 RL 승리 → beam/ILP 예산 스윕 로그 의무(보조 통제); RL 분산 폭주 → 스텝 캡·시드 3 고정, 캡 도달 시 밴드로 판정(연장 금지); 보상-과최적화가 metamorphic의 빈틈으로 이주(이중 지표 모니터).
- **판별 기여**: Field-2 {HR1, HR2}의 crucial experiment. 부산물로 집합-조립이라는 부과업 정식화가 H1/H2 판별에도 피처를 공급.

### P5 — VLM 이중 트랙: 프런티어 배심원 vs 로컬 래스터 분할 (vision 레인 · H4)

**mechanism**: 제약 5의 두 갈래를 분리해 다룬다. **(5a) 프롬프팅**: def 크롭을 렌더(라우터 visual_report/render 경로 재사용) → 프런티어 VLM이 벽 영역 polygon+판정 반환 → 벡터 기하로 역투영(back-projection)해 핸들 집합화 → E1.5식 앙상블의 **배심원 1석으로만** 편입(R23 판례 "vision-as-SoT 기각, VLM은 배심원" 정합 — 진리원 아님). **(5b) 학습**: FloorPlanCAD 래스터로 소형 분할 모델(SegFormer-B0/U-Net급) 파인튜닝 → 역투영 배심원. NC 방화벽: 5b 가중치는 연구 계측기 전용·제품 반입 금지, 레인 승리 시 클린 데이터 재훈련을 별도 결재로 계획. H4 시험의 핵심: 벡터 측이 못 푸는 divergent를 래스터가 metamorphic-정합으로 푸는가. 부수 효과 하나가 판별상 귀중하다 — **래스터 배심원은 레이어명·블록명을 물리적으로 못 본다** → H3(관례 지배)의 교차검증기가 공짜로 생긴다.

- **truth source**: synthetic 렌더(합성 벽 IR → 래스터, 픽셀↔핸들 맵 보유 — 사람 라벨 0으로 truth 사슬이 닫힌다) + FPC(5b 훈련) + 배심 기여도(앙상블 κ 변화·divergent 해소율).
- **leakage 방지**: 렌더 스타일 파라미터(선폭·poché 유무·노이즈)를 다양화 후 동결; FPC 도면 단위 스플릿; 역투영 코드는 synthetic에서 선검증 통과 후에만 실코퍼스 발언권.
- **prereg band 초안**: synthetic 렌더에서 5b 벽-픽셀 IoU ≥0.7 & 역투영 핸들 F1 ≥0.6; 배심 가치 밴드 = divergent-20의 ≥30%를 metamorphic-정합 출력으로 해소 또는 앙상블 Fleiss κ 상승 → 배심원 생존; 미달 → 타이브레이커로 demote.
- **kill condition**: synthetic 역투영 핸들 F1 <0.4 → **브리지 병목으로 양 트랙 동시 kill**(vision 품질과 무관하게 레인의 사활은 래스터→벡터 브리지에 있다); 5a의 def당 API 비용이 봉투 초과 → 5a 비용 kill.
- **cheapest probe**: 5a를 divergent-20에만(렌더 20장 + 프런티어 VLM 1패스) — P0 법의학 결과와 교차 대조: "이름 없이 순수 시각으로도 벽이 보이는가". 1일, 소액 API.
- **compute plan**: 렌더 로컬 CPU; 5b 파인튜닝 5070 Ti 16GB 충분(소형 백본); 대형 백본은 5b 생존 시에만 DGX 야간. 5a는 프런티어 API 과금(페이싱 관리) — DGX의 Ornith-35B는 텍스트 판정자로 이미 점유 중이며 vision 지원 여부 미확인(**가정 플래그**: P5 착수 전 확인, 미지원이면 5a는 외부 API 전용).
- **expected failure modes**: NC 오염 경로(방화벽 문서로 차단·산출물 계보 기록); 렌더-도메인 갭(synthetic 렌더 과청결 — 스타일 노이즈 주입으로 완화); 두꺼운 poché의 역투영 다의성(후보 다중화+신뢰도 하향); κ 상승의 우연(순열 검정); 크롭 경계에서 벽 절단(오버랩 타일링).
- **판별 기여**: H4 생사(브리지 게이트 + 배심 가치) + H3 교차검증(이름-맹 배심원) + vision 계열 커버.

### P6 — 관례-prior 명시 모델 (고전 ML · H3의 계측화 + E1 재해석)

**mechanism**: 145 아카이브에서 관례 신호만으로 — 레이어명/블록명 토큰, 해치 패턴, 선폭·색 통계, **기하 피처는 의도적으로 배제** — 투명한 고전 모델(로지스틱/GBDT)을 훈련해 벽-멤버를 예측한다. 목적은 이기는 것이 아니라 H3를 일화에서 측정치로 바꾸는 것: (i) cross-project 일반화 곡선(관례는 프로젝트-국소인가 재사용 가능한가)이 그 자체로 발견이고, (ii) LLM wall_likelihood와 관례 점수의 상관은 "E1 판정자가 이름-prior를 탔는가"를 정량화한다(top-20 블록명에 '평면도' 포함 — P0의 토큰 분석과 연동). H3가 지배 신호라면 이 빈약한 모델이 이상하게 강할 것이고, 아니라면 chance 근처로 떨어진다.

- **truth source**: synthetic은 불가(합성물엔 관례가 없다) — (a) FPC 레이어 메타(가용 시), (b) concordance truth: P1/P3 기하-검증 벽과의 일치(검증셋과 스태킹 훈련셋을 분리해 순환 차단), (c) cross-project held-out 곡선 자체.
- **leakage 방지**: **프로젝트 단위 스플릿**(도면 단위로는 같은 프로젝트의 관례가 구조적으로 누수); 라벨어 동어반복 토큰("WALL"·"벽" 레이어명)은 별도 분리 보고 — 누수를 학습 성과로 위장하는 것을 금지.
- **prereg band 초안**: cross-project AUC ≥0.75 → 재사용 가능 prior로 H3 지지; within ≥0.9 & cross ≤0.6 → H3 demote(프로젝트-국소 — 적응 캘리브레이션 역할로 강등); corr(LLM likelihood, 관례점수) ≥0.7 → E1 silver의 독립성 demote(E1.5 해석 테이블에 주입).
- **kill condition**: cross-project AUC ≤0.55(chance 근방) → **H3 kill**(지배 메커니즘으로서); 스태킹에서 기하 피처 대비 한계 기여 ≈0 → 타이브레이커로 demote.
- **cheapest probe**: 토큰 빈도표 + 현행 v0 쌍-밀도와의 point-biserial 상관, 384-def 벤치에서. 수 시간, 로컬.
- **compute plan**: 로컬 CPU only(GBDT). GPU/DGX 불사용.
- **expected failure modes**: 동어반복 토큰 누수(분리 보고로); concordance 순환(P1로 검증하고 P1과 스태킹 — 셋 분리로 차단); 한/영 토큰 정규화·cp949 함정(코드포인트 검증, PYTHONUTF8); 프로젝트-ID 유도 오류(파일명/xref 구조에서 유도 — 유도 규칙 자체를 감사 대상 보조가정으로 명시).
- **판별 기여**: H3 생사 + E1/E1.5 silver의 독립성 감사(모든 silver 소비 실험의 보조가정 통제) + 고전 ML 커버.

### 제안 간 커버리지 (평가 기준 5 대응)

결정론 P0·P1 / 그래프+DL P2 / 평가·게이트 방법론 P3 / RL(RLVR·bandit 격리 포함) P4 / VLM(프롬프팅·학습 이원) P5 / 고전 ML P6 + P2 프로브(로지스틱/GBDT 사다리). 전 계열 커버.

---

## REQUIRED OUTPUT FIELDS

### hypothesis_set

배타 독법: Field-1은 "지배 신호"(제거 시 밴드 아래 붕괴) 주장 간 경쟁. prior는 큐 정렬용 작업치일 뿐 kill 권한과 무관.

| id | statement | prior | mechanism class | kill-signature (구별됨) |
|----|-----------|-------|-----------------|------------------------|
| H0 | E1 "LLM 고확신 vs 탐지기 0쌍" 불일치는 계측기(핸들 공간·조인·LINE-only 입력 배제·단위 가정·나열 지시)가 제조한 아티팩트다 | 0.25 | instrument-artifact (측정 널) | P0에서 인용 핸들 다수가 실재·쌍가능 LINE으로 판명 → kill |
| H1 | 커버리지-완전한 국소 기하 규칙(평행쌍+두께 밴드+정션)만으로 지배 신호 충분 | 0.30 | deterministic-geometric | P1 완전 정규화 후에도 synthetic recall<0.7 또는 FPC F1<0.4 → kill |
| H2 | 국소 쌍 기하는 과소결정 — 네트워크 위상/문맥이 결정적 기여 | 0.20 | relational-graph | P2 Δ-게이트: 문맥 피처 기여 ΔF1<+0.1 (동일 truth·스플릿) → demote, <0 → kill |
| H3 | 레이어/이름/해치 관례가 실무 코퍼스의 지배 신호 | 0.15 | symbolic-convention | P6 cross-project AUC ≤0.55 → kill |
| H4 | 래스터 게슈탈트(poché·이중선)가 가장 판독 유리한 신호 공간 | 0.10 | visual-raster | P5 synthetic 역투영 F1<0.4(브리지) 또는 배심 가치 밴드 미달 → kill/demote |
| HR1 | (Field-2) 집합-조립 부과업에서 RLVR이 동률 컴퓨트의 beam/ILP·supervised를 이긴다 | 0.3 | policy-optimization | P4 밴드 미달 또는 greedy≈optimal 프로브 → kill |
| HR2 | (Field-2) 탐색/supervised로 충분 — C07이 이 과업에도 성립 | 0.7 | search/supervised | P4에서 RL이 밴드 이상으로 승리 → kill |

측정-아티팩트 널(H0)은 카드 요구대로 라이브 언더독으로 포함 — 그리고 이 도메인에서는 언더독이 아니라 유력 후보다(n_h_ornith 17/20=10, zero_frac 0.682, LINE-only 코드 확인).

### discrimination_table

실험 × 사전약정 outcome → {kill | demote | survive}. 모든 실험은 최소 1개 outcome에서 무언가를 죽인다 (카드 규칙 2 — 죽이지 못하는 행은 편입 금지).

| 실험 | outcome (사전약정) | H0 | H1 | H2 | H3 | H4 | HR1/HR2 |
|------|--------------------|----|----|----|----|----|---------|
| E-P0 법의학 | O-A: 인용 핸들 ≥50% 부재/비-LINE | survive↑ | survive(히스토그램 서브판정) | survive | survive↑(이름토큰 상관 시) | survive | — |
| | O-B: 핸들 실재·쌍가능 LINE 다수 | **kill** | survive↑(단, 단위/파라미터 진단 발동) | survive | demote | survive | — |
| | O-C: 중간(10–50% 부재) | demote | survive | survive | survive | survive | — |
| E-P1 정규화 v1 | O-A: 밴드 통과 | — | survive↑ | demote | demote | demote | — |
| | O-B: 밴드 미달 | — | **kill** | survive↑ | survive↑ | survive↑ | — |
| E-P2 Δ문맥 | O-A: ΔF1≥+0.1 | — | demote | survive↑ | — | — | — |
| | O-B: ΔF1<+0.1 (특히 <0) | — | survive↑ | demote/**kill** | — | — | — |
| | O-mask: 이름 마스크 시 붕괴 | — | — | — | survive↑ | — | — |
| E-P3 배터리 | O-A: 특정 계열 후보만 불변식 통과 | — | 해당 계열 survive↑ / 타계열 demote | ← | ← | ← | — |
| | O-B: 전 계열 통과·동률 | — | 비판별 → §abstain A1 트리거 | ← | ← | ← | — |
| | O-C: 전 계열 대량 위반 & synthetic 통과 | — | (synthetic-충실 **보조가정 kill** — 본체 아님) | ← | ← | ← | — |
| E-P4 RL 판별 | O-A: greedy≈optimal (프로브) | — | — | — | — | — | **HR1 kill** (사전) |
| | O-B: RL>beam 밴드 이상 | — | — | — | — | — | **HR2 kill** |
| | O-C: RL≤beam | — | — | — | — | — | **HR1 kill** |
| E-P5 VLM | O-A: 브리지 F1<0.4 | — | — | — | — | **kill** | — |
| | O-B: 배심 가치 밴드 통과 | — | — | — | demote(이름-맹 확인) | survive↑ | — |
| | O-C: 브리지 OK·배심 가치 미달 | — | — | — | — | demote | — |
| E-P6 관례 곡선 | O-A: cross AUC≥0.75 | — | — | — | survive↑ | — | — |
| | O-B: within-高/cross-低 | — | — | — | demote(국소 prior) | — | — |
| | O-C: AUC≤0.55 | — | — | — | **kill** | — | — |
| | O-corr: corr(LLM,관례)≥0.7 | (E1 silver 독립성 demote — 보조 판정, E1.5 해석 주입) | — | — | survive↑ | — | — |

### auxiliary_assumptions

주요 kill 셀별 — kill이 올라타는 보조가정 묶음과, 그 보조가정이 실제로 성립했는지 확인하는 통제:

| kill 셀 | 보조가정 묶음 | 통제 (auxiliary control) |
|---------|---------------|--------------------------|
| E-P0/O-B → H0 kill | IR 추출이 완전하다; def-이름 조인 정규화가 건전하다; E1 원시 인용 파싱이 정확하다 | 이중 엔진 엔티티 카운트 대조(accoreconsole census vs ezdxf, 3 def); 공백/변형 이름 결정론 테스트 케이스; 인용 파서 왕복(round-trip) 검사 |
| E-P1/O-B → H1 kill | synthetic 생성기가 벽 현상을 충실 재현; FPC 라벨 의미가 우리 정의와 정합; transform 전개가 정확; 단위 정규화가 옳다 | 뮤턴트 conviction ≥95% (게이트의 게이트); FPC 스키마 이중 파서 합치; 중첩-synthetic 왕복 검증; P0의 bbox 스케일 감사 소비 |
| E-P2/O-B → H2 kill | 피처에 이름 누수 없음; 훈련이 수렴했다; 모델 용량이 병목 아님; (silver 암) E1.5 B1≥0.70 | mask-ablation 암; 러닝커브 로그 첨부; 용량 1축 스윕; B1 밴드 게이트(동결된 prereg_e15.json) |
| E-P4/O-C → HR1 kill | 베이스라인(beam/ILP)이 충분히 강함; 인코더 동일; 보상 동결 | beam 폭/ILP 시간예산 스윕 기록(약한 베이스라인이면 kill 무효); 인코더 가중치 sha 일치; 보상 함수 sha 핀 |
| E-P4/O-B → HR2 kill | 보상이 해킹되지 않음; 컴퓨트 동률 | 이중 지표 모니터(보상↑ & synthetic F1↑ 동반 확인 — 괴리 시 kill 무효+사건 기록); 월클록 로그·시드 3 재현 |
| E-P5/O-A → H4 kill | 렌더가 기하를 충실 반영; 크롭이 def를 커버; 렌더 스타일이 과소 다양하지 않음 | synthetic 픽셀↔핸들 왕복 exact 검사; bbox 커버리지 assert; 스타일 파라미터 스펙트럼 보고 |
| E-P6/O-C → H3 kill | 토큰 정규화 무결(한/영·인코딩); 프로젝트-ID 유도 정확; 동어반복 토큰 분리됨 | 코드포인트 레벨 검증(cp949 함정 회피); 유도 규칙 감사 표본; with/without 라벨어 이중 보고 |

### preferred_experiment

**E-P0 (E1 불일치 법의학 감사)** = argmax(배제 가능 가설 수 / cost_to_test).

- cost_to_test: 스크립트 반나절 + 실행 <1h, 로컬 CPU only, GPU 0·LLM 0·API 0.
- 배제력: H0 생사 직접 판정(전제 용해 가능) + H1·H3 방향 증거 + P1의 단위-보조가정 입력. E1 불일치가 아티팩트로 판명되면 "탐지기 개념 결함" 위에 세운 고가 실험들이 통째로 불필요해진다 — 카드 규칙 3의 dissolver-before-probes 그 자체.
- 큐 (배제력/비용 내림차순, 프로브 우선): E-P0 → E-P3 프로브(2관계, 1일) → E-P1 프로브(divergent-20 재실행, 1일) → E-P6 프로브(토큰 상관, 수 시간) → E-P4 greedy 프로브(1일) → E-P5a(divergent-20 렌더+VLM 1패스, 1일) → [게이트 결과 조건부] P1 full → P2(고전ML 사다리 → GNN) → P4 full → P5b full. 첫 판별 신호까지 ~1일, 프로브 큐 전체 ~1주 (평가 기준 3 충족).

### gate_binding

kill을 렌더하는 것은 외부 게이트다 — 좌석·모델·서사가 아니다:

- **prereg 게이트**: 각 실험의 밴드를 `reports/e2/prereg_p*.json`으로 실행 전 커밋(sha 핀) — E1.5의 `prereg_e15.json` 패턴 준용. 판정은 수집 스크립트(`tools/e2_collect_*.py`류)의 산출 JSON이 동결 밴드와 기계 대조되어 렌더된다.
- **synthetic 게이트**: correct-by-construction + `mutate()` conviction 프로토콜(기존 L5 semantic-gate 패턴) — 게이트 자격 자체가 뮤턴트 적발률로 심사된다.
- **E1.5 밴드 (이미 동결)**: B1(과업 well-posed)·B4(likelihood silver 자격) — silver를 소비하는 모든 암(P2/P4 보고/P5 배심 합류)의 활성화 게이트.
- **라이선스 게이트 (인간)**: FloorPlanCAD/CubiCasa NC — 방법 개발 사용은 과업이 허용, 가중치·파생물의 제품 반입은 Paul+counsel 결재 (연구/제품 방화벽 문서 필수).
- **프로그램 승격 게이트 (인간)**: 탐지기 v1 채택·145 아카이브 대량 적용·차기 컴퓨트 증액은 Paul ballot — 좌석은 제안하고 게이트가 처분한다.

### abstain_condition

사전약정 관측-동등 트리거:

- **A1**: H1·H2 후보가 synthetic/FPC/metamorphic **전** 게이트에서 CI 중첩 → 비판별 선언. 요구 신계측기 = (a) 프로젝트-held-out 네이티브 라벨 코퍼스 조달(R12 최상위 unknown과 동일 — 조달 ballot로 라우팅; 구조도 조달 판례 준용) 또는 (b) B1≥0.70 품질의 E1.5 silver 대량화. 동일 게이트 위 추가 실험 금지(분리 불능이 증명된 실험의 반복은 카드 위반).
- **A2**: E1.5 B1 < 0.60 → 과업 자체가 ill-posed(정의/projection 모호가 지배) — 탐지기 방법 경주를 중단하고 projection 재설계 선행 (prereg_e15.json의 동결 라우팅 준수).
- **A3**: E-P4가 시드 간 노이즈 안에서 비분리 → RL 적용성 비판별을 **deferral로 기록** (verdict로 반올림 금지).
- **A4**: 컴퓨트/기간 봉투 소진 → 생존자 목록 + 최고 판별/비용 차기 실험 1건을 명시적 deferral로 보고.

### recursion_state

- **round**: 0 (Phase A BLIND — 설계만, 게이트 실행 0건).
- **survivors**: Field-1 {H0, H1, H2, H3, H4} 전원 생존; Field-2 {HR1, HR2} 전원 생존. 어떤 kill도 기록되지 않음 — 이 문서의 어떤 문장도 kill이 아니다.
- **termination state**: **deferred** (예산 미투입 상태의 명시적 이연 — converged 아님, non_discriminable 아님).
- **next action**: E-P0 실행 → 판별표 O-A/O-B/O-C 매칭 → 생존자 재계산 → 프로브 큐 순회.
