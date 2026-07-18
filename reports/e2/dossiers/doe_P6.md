# 도시에 — doe_P6 · VLM-MODE × MODALITY-FUSION FACTORIAL

**seat_id**: `doe_P6`  
**제안**: VLM 계열의 프로그램 편입 (제약 5) — `{VLM-모드}×{모달리티}×{감독원}` 12셀 완전요인  
**상태**: Phase A 설계서 (effects / interactions / confirmation 전부 UNRUN)  
**작성일**: 2026-07-18

---

## 0. 한 줄 계약

P6는 VLM을 SoT가 아닌 **배심원(frontier-prompt→silver)** 과 **탐지기 후보(open-finetune)** 로 역할 분리한 뒤, 래스터·벡터·융합 모달리티와 감독원(T-SYN / T-SILVER)을 요인화해 **모드×모달리티 상호작용(A×B)** 을 추정한다. 수치 순위는 미실측이므로 본 문서는 실행 가능한 실험 스펙이며 판정이 아니다.

---

## 1. 이론적 근거·선행연구

### 1.1 프로그램 위치

E2 방법론 사다리(결정론→고전ML→그래프→DL→RL→VLM)에서 P6는 **맨 끝 계단**이다. 패널은 이를 CL-G(래스터/VLM 이중 트랙)로 묶었고, 우선순위 권고는 P5+P2 → P3 → P1 → **P4+P6**(활성 확인 후 DGX 무거운 투자). 즉 P6는 “VLM이 좋은가”를 단독 주장하는 자리가 아니라, **결정론·고전ML이 남긴 잔차(아이콘·긴 평행 구조·축척 무감)를 VLM 표현이 회수하는지**, 그리고 그 회수가 **파인튜닝에서만인지 프롬프팅에서도인지**를 분리 추정하는 자리다.

다이제스트 기준 현재 천장:

| 계열 | 지표 | 수치 (다이제스트만) |
|------|------|---------------------|
| 기하 탐지기 v1 전이 (CubiCasa val) | F1 | 0.2358 (P≈기저율, R≈0.981) |
| HistGradientBoosting 6특징 | val F1 / AUC | 0.517 / 0.9215 |
| E1.5 silver↔탐지기 | Pearson | 0.2911 (name-blind 동일 → 레이어명 신호 0) |

P6가 가져올 수 있는 것은 “F1을 무조건 올린다”가 아니라 **(a)** 벡터 특징이 못 보는 래스터 단서(해치·텍스트·치수 화살표 맥락)의 조건부 이득, **(b)** 그 이득이 open-finetune에만 있는지에 대한 A×B 판정, **(c)** frontier arm의 juror 자격(은 R23·E1.5 B1/B4 게이트)이다.

### 1.2 방법론 계보 (일반 지식; 확신 약한 인용은 ‘요검증’)

1. **Factorial / DOE (Box–Hunter–Hunter, Montgomery)**  
   완전요인 \(A(2)×B(3)×C(2)=12\) 는 main·2FI·3FI를 분리한다. P6의 표적 효과는 **A×B**(vlm_mode × modality). “VLM은 좋다/나쁘다” 주효과만 보면 융합 이득의 조건성이 가려진다.

2. **Vision-Language Models as jurors, not oracles**  
   R23 판례: vision-as-SoT 기각, VLM은 판정자 아닌 배심원. 이는 LLM-as-judge / ensemble jury 문헌(일반 지식: Zheng et al. MT-Bench 계열 — 요검증; LLM-as-jury vs single judge)과 정합하되, **건축 CAD에서는 CRS·픽셀↔핸들 역투영이 kill risk**(패널 T24)라서 “배심원” 역할도 exact 하네스 없이는 오염원이 된다.

3. **Multimodal fusion**  
   early / late / hybrid fusion (일반 지식: Baltrušaitis et al. multimodal ML 서베이 — 요검증). P6의 B 수준은 입력 표현 수준에서 고정:
   - `raster-only`: 렌더 이미지(+선택적 bbox/seg 프롬프트)
   - `vector-only`: SEG-IR / 선분·핸들 직렬화 텍스트(또는 SVG/JSON 토큰)
   - `raster+vector-fused`: 동일 샘플에 두 스트림을 동시 제공(프롬프트면 교차참조 지시; 파인튜닝면 dual-encoder 또는 interleaved token)

4. **Instruction / SFT / preference tuning of open VLMs**  
   자산에 **qwen2.5-VL-3B floorplan SFT/GRPO** 실존. 계보는 LLaVA-style visual instruction tuning → Qwen2-VL / Qwen2.5-VL 계열 SFT → GRPO/RLVR식 선호·보상 정렬(일반 지식; GRPO 원논문 인용은 요검증). P6 open-finetune arm은 이 가중치를 **방법검증 전용 격리**에서 재학습·평가한다(제품 경로 오염 금지 — abstention ②).

5. **Prompted frontier VLMs**  
   few-shot + temperature 0 + 고정 예시 순서. 산출은 **silver만**(SoT 승격 금지). E1.5가 이미 5기 silver가 ~2어휘 가문임을 보였으므로, P6 frontier arm도 “5독립”이 아니라 **가문 내 반복 + 가문 간 합의**로 juror 자격을 본다.

6. **Leakage / firm-block / seed control**  
   L-FIRM·L-SEED, 렌더 DPI freeze, few-shot 순서 고정. VLM 파인튜닝은 순수 결정이 아니므로 **seed 축 반복만** 정당(전면 잡음통계 아님) — 패킷 deterministic_note.

### 1.3 이 제안이 기대는 “반증 가능한 주장”

사전 가설(UNRUN):

- open-finetune: `fused > vector > raster` (융합이 파인튜닝에서 이득)
- frontier-prompt: raster에서만 쓸 만(프런티어가 CAD 벡터 텍스트에 약함)
- **A×B 큼**: 융합 이득이 파인튜닝 전용 조건성이면 “VLM 좋다” 단독 주장 반증

null 보고도 성과: 융합 무이득이면 **vector-only로 충분** → 래스터 파이프라인 투자 kill.

---

## 2. 알고리즘 정확 스펙

### 2.1 기호·역할

| 기호 | 정의 |
|------|------|
| \(h\) | 핸들(평가 단위 = per-handle `wall_member(h)`, CL-C 계약과 정합) |
| \(x^r\) | 래스터: 고정 DPI·축척 규칙으로 렌더한 이미지 |
| \(x^v\) | 벡터: SEG-IR 선분/폴리라인 직렬화(레이어명 mask 옵션) |
| \(y\) | 이진 벽 멤버십 (T-SYN 또는 T-SILVER; CubiCasa는 Wall 모서리 진리) |
| \(A\) | `frontier-prompt` \| `open-finetune` |
| \(B\) | `raster` \| `vector` \| `fused` |
| \(C\) | `T-SYN` \| `T-SILVER` (파인튜닝 감독; 프롬프트 arm에서는 few-shot 예시원) |

**역할 불변식 (R23)**:

- \(A=\texttt{frontier-prompt}\) → 출력 \(s(h)\) 는 **silver only**. SoT·학습 타깃 승격 금지(CL-K와 별도 통제 가능).
- \(A=\texttt{open-finetune}\) → 출력 \(\hat{y}(h)\) 는 **탐지기 후보**. R-META / R-SYN으로 v0·GBDT와 겨룸.

### 2.2 입력 구성 (모달리티 B)

```
function BUILD_INPUT(sample, B, render_cfg_frozen):
  assert render_cfg_frozen.dpi, .scale_policy, .bg fixed  # 변동 금지
  xr = RENDER(sample, render_cfg_frozen) if B in {raster, fused} else None
  xv = SERIALIZE_VECTOR(sample, layer_mask=NAME_BLIND_DEFAULT) if B in {vector, fused} else None
  if B == raster: return {image: xr}
  if B == vector: return {text: xv}
  if B == fused:  return {image: xr, text: xv, align_hint: HANDLE_TO_PIXEL_MAP}  # T24 하네스
```

**픽셀↔핸들 역투영**: fused·raster 채점에서 per-handle로 내려가려면 exact map이 필요(T24). map이 없으면 셀은 **도면 단위 집합 지표만** 보고하고 per-handle F1은 `INADMISSIBLE`로 표기(합격 판정 불가).

### 2.3 Arm A1 — frontier-prompt (juror → silver)

```
function FRONTIER_JUROR(input, fewshot_S_fixed, vocab_family):
  # temperature=0, seed API 고정, few-shot 순서 고정(은닉상태 제거)
  prompt = SYSTEM_JUROR_R23()
        + FEWSHOT(fewshot_S_fixed)   # C가 예시원: T-SYN 또는 T-SILVER 유래, 고정 집합
        + TASK(input)                # "각 핸들 wall_member?" 또는 도면 단위 벽 선분 집합
  raw = VLM_API(prompt, temp=0, family=vocab_family)
  silver = PARSE_TO_HANDLES(raw, schema=STRICT_JSON)  # 파싱 실패 = abstain, 강제 채우기 금지
  return silver  # SoT로 쓰지 말 것
```

**Juror 자격 게이트 (패널·반대의견 원장 #1, calibration 정확 인용)**:  
E1.5 기준으로 silver 활성은 **B1 ≥ 0.70 AND B4 Pearson ≥ 0.70**. 미달이면 frontier 갈래 **조기 종료**(kill_condition 후반).

**가문 취급**: 다이제스트상 E1.5 5기는 ~2가문(fable+sol vs opus+sonnet+grok). P6는 가문당 대표 1 + 필요 시 가문 내 1반복만 예산에 넣는다(5중 독립 가정 금지).

### 2.4 Arm A2 — open-finetune (detector)

**모델**: 로컬 실존 `qwen2.5-VL-3B` floorplan SFT/GRPO 체크포인트를 출발점(또는 동일 아키텍처 base+ SFT). 제품 탑재 경로와 가중치 디렉터리 격리.

**헤드**: per-handle 이진 로짓 \(z_h\), \(\hat{p}_h=\sigma(z_h)\). 도면 단위 집합 손실이 필요하면 보조 헤드를 **별도 산출물**로 격리(공격 E / T6 교훈 — 평가 단위 혼선 금지).

**손실 (감독원 C)**:

\[
\mathcal{L}_{\mathrm{SFT}} = \mathbb{E}_{(x,y)\sim D_C}\Big[\mathrm{BCE}(\hat{p}_h, y_h)\Big]
\]

선택적 GRPO/선호 단계(자산에 GRPO 실존):

\[
\mathcal{L}_{\mathrm{GRPO}} = \mathbb{E}\big[-\log\pi_\theta(a|x)\,A^{\mathrm{rel}}(a)\big]
\quad\text{(보상 } R \text{ 은 R-SYN/R-META verifier; false-accept 상한은 CL-H T26과 공유 검토)}
\]

P6 본선은 **SFT 12셀 1 epoch 패밀리**를 1차 청구서로 두고, GRPO는 최적 셀 확인 런에서만 옵션(청구서 폭증 방지).

**하이퍼파라미터 공간 (사전 봉인, 셀 간 고정)**:

| 항목 | 값 / 범위 | 비고 |
|------|-----------|------|
| LR | \{1e-5, 2e-5\} 중 **1개 사전고정** | 셀마다 튜닝 금지(교락) |
| batch / grad_accum | 16GB VRAM에 맞게 고정 | 5070 Ti 16GB |
| epochs | 1 (본선), 확인 런만 +1 | |
| image size | render freeze와 동일 | B 잡음 아님 |
| seed | \{17, 23\} 본선 1개 + 민감도 시 2 | deterministic_note |
| temp (eval) | 0 | |
| LoRA rank | 사전 1값 (예: 16) — 요검증 기본값 | full FT는 DGX 전제 |

### 2.5 평가·반응 지표

**Primary**

- `R-SYN` F1 (per-handle, 합성 팩; B2 채점우주 음성 0 문제 인지 — 정밀도 공허 셀은 F1 단독 보고 금지, P/R 분리)
- `R-META` 게이트 위반율 ↓ (metamorphic; CL-D 센티널·recall 최저선 탑재 전제 — 미탑재 시 R-META 판정 `DEFER`)
- 교차 `R-SILVER`: 탐지기↔juror 합의/불일치 (Pearson 또는 handle-F1; E1.5 0.2911을 기준선으로만 인용)

**External transfer (조건부)**

- CubiCasa val F1 (개발 허용). **test 무접촉(단발)**.
- 합격선은 **셀 착수 전** prereg 파일에 봉인. 제안 기본안(판정 전 초안, 봉인 시 수정 가능하나 착수 후 수정 금지):
  - open-finetune 최적 셀이 CubiCasa val에서 **GBDT 0.517을 넘지 못하고**, R-SYN/R-META에서도 **v0 결정탐지기(P2 강건설정)를 못 이기면** → 계열 kill.

**Direction**: F1 ↑, R-META 위반율 ↓.

### 2.6 요인 모형 (prereg_model)

\[
Y = \mu + A + B + C + A{\times}B + B{\times}C + \varepsilon
\]

- 표적: \(A{\times}B\)
- 보고: main A·B·C + \(A{\times}B\) + \(B{\times}C\) (3FI는 완전요인으로 추정 가능하나 해석 우선순위 낮음 — 탐색만)
- 밴드: R-SYN과 R-META에 **동일 모형** 적용(한쪽만 유의한 “체리피킹” 금지)

### 2.7 12셀 행렬

| 셀 ID | A | B | C | 산출 역할 |
|-------|---|---|---|-----------|
| F-R-SYN | frontier | raster | T-SYN 예시 | silver |
| F-R-SIL | frontier | raster | T-SILVER 예시 | silver |
| F-V-SYN | frontier | vector | T-SYN | silver |
| F-V-SIL | frontier | vector | T-SILVER | silver |
| F-X-SYN | frontier | fused | T-SYN | silver |
| F-X-SIL | frontier | fused | T-SILVER | silver |
| O-R-SYN | open-ft | raster | T-SYN | detector |
| O-R-SIL | open-ft | raster | T-SILVER | detector |
| O-V-SYN | open-ft | vector | T-SYN | detector |
| O-V-SIL | open-ft | vector | T-SILVER | detector |
| O-X-SYN | open-ft | fused | T-SYN | detector |
| O-X-SIL | open-ft | fused | T-SILVER | detector |

실행 순서(패킷): **cheapest_probe = F-R-*** 5장 → juror 능력 없으면 frontier 6셀 조기 종료 → open 6셀만. 학습 셀 무작위화 + seed 기록. IR/render freeze 캐시.

---

## 3. 벽 과업 적응 설계

### 3.1 세 축 하네스 접속

| 축 | 자산 | P6 접속 |
|----|------|---------|
| 벡터·사람라벨 | CubiCasa5k SEG-IR (train 4,200 / val 400 / test 400; 벽 선분율 ~11.8%) | open-finetune의 주 전이 평가; 레이어 중립 변환 유지; name-blind 기본 |
| 래스터 | FloorPlanCAD 5,308 + 벽 bbox/segmask (벡터 SVG 없음) | raster/fused의 렌더·마스크 감독; **벡터 없음**이므로 fused는 “마스크→의사벡터” 또는 CubiCasa 렌더 쪽과 분리 보고 |
| 실도면 | 1.dwg staged DXF (도면정의 384; max 412) | hold-out firm 확인 런; L-FIRM 블록; B3 벽-제로율 밴드(≤0.40) 감시 |

**중요 분리**: FloorPlanCAD는 벡터 SVG가 없으므로 `vector-only`/`fused`의 정본 벡터는 **CubiCasa SEG-IR + 실도면 DXF** 쪽. FloorPlanCAD raster-only 셀은 **래스터 전용 보조 격자**로 보고하고 12셀 본선과 confounded되지 않게 `aux_floorplancad_raster`로 라벨링.

### 3.2 전이 실패(0.236)와 GBDT(0.517)를 아는 상태에서의 기대 기여

기하 v1은 R≈0.981·P≈기저율 → **거의 전부 양성**. FP 주범: Direction 화살표 / BoundaryPolygon / Door / Window / DimensionMark. 최소길이 필터 천장 F1 0.335 — **긴 평행 구조**가 본질 교란. GBDT는 6특징으로 F1 0.517·AUC 0.9215까지 올림.

VLM이 **추가로** 가져올 수 있는 잔차 가설:

1. **아이콘·화살표·치수 맥락의 시각적 억제** (래스터) — 벡터 특징 `parallel/thickness/...`가 구분 못 하는 FP.
2. **해치·텍스트 주기·방 폴리곤 맥락** (래스터+언어) — 프로그램 한계에 적힌 “이름 없는 신호”의 일부; 단 P6는 신호를 **발명하지 않고** 요인 격자 안에서만 측정(card ABSTAIN).
3. **벡터 직렬화 few-shot** — frontier가 CAD 토큰을 이해하면 vector arm이 산다; 이해 못 하면 A×B가 “frontier는 raster만”으로 기울며 가설과 정합.

가져오지 **못하는** 것:

- 합성팩 B1 충실도 FAIL(KS 0.5792)이 고치면 VLM 없이도 올라가는 부분 → PR-1/CL-C 선결.
- 대리 독립성 붕괴(동일 parallel-double-line prior)면 VLM 융합도 편향 증폭 → PR-2/P3.
- NC 라이선스 미해결 시 외부 라벨 학습 arm 자체가 counsel 블록 → PR-3.

### 3.3 렌더 freeze (B의 설정, 잡음 아님)

고정할 것(예시 스펙 — 착수 전 한 파일로 봉인):

- DPI / 픽셀 장변 / 배경색 / 선 굵기 규칙 / 레이어 가시성 마스크
- 축척: CubiCasa는 px(축척 미상, 벽두께 px p50=22) → **물리 mm prior 재도입 금지**(v1이 축척 2~15mm/px 무감이었음)
- 캐시 키: `(def_id, render_cfg_hash)`

변동 시 modality 주효과가 **가짜**가 된다(expected_failure_mode ②).

### 3.4 Silver·SoT 경계 (적응의 핵심)

- Frontier 출력은 E1.5 silver와 같은 **배심원 채널**.
- Open-finetune이 T-SILVER로 학습할 때: CL-K(anti-silver)와 충돌 가능 → C=`T-SILVER` 셀은 **통제 대비**로 명시하고, 제품 후보 선정은 C=`T-SYN`(또는 CubiCasa 사람라벨) 셀만 1차 허용하는 운영 규칙을 둔다.
- 사람라벨 0이 절대가 아니라 CubiCasa GO된 현 국면: CubiCasa Wall 모서리는 **외부 진리**로 val에 쓸 수 있으나, FloorPlanCAD/NC counsel(PR-3) 전엔 가중치·데이터 경로를 방법검증 샌드박스에만 둔다.

---

## 4. 데이터·컴퓨트 요구

### 4.1 자산·제약 (다이제스트)

| 자원 | 상태 | P6 함의 |
|------|------|---------|
| qwen2.5-VL-3B floorplan SFT/GRPO | 로컬 실존 | open-finetune 출발점 |
| RTX 5070 Ti 16GB / RAM 64GB | 가용 | LoRA SFT·렌더·평가 집계 |
| DGX Spark (Ornith-35B) | unreachable (승인됨) | 12셀 full FT·대배치 보류; 야간 시분할은 **재개 후** |
| 프런티어 VLM API | 유일 결재 게이트 **미승인** | cheapest_probe·frontier 6셀 = **승인 전 차단**; 승인 없으면 frontier 갈래 `BLOCKED`로 기록하고 open만 |
| CubiCasa SEG-IR | 전량 변환 실패 0 | 주 전이 축 |
| FloorPlanCAD raster | 5,308 | aux raster |
| Zenodo10K/Text2CAD/ArchCAD/pseudo-12k | 보유 | P6 본선 비사용(범위 밖·오염 위험) |

### 4.2 로컬 실행 계획 (DGX 불통 전제)

1. **Day 0**: render_cfg 봉인, IR 캐시, HANDLE_TO_PIXEL_MAP 합성 프로브(T24) — API 불필요.
2. **Day 0.5 (API 승인 시)**: cheapest_probe `frontier × raster` 5장 — juror 능력 binary.
3. **Week 1**: open-finetune **축소 격자** — 먼저 `B=raster,vector` × `C=T-SYN` (2셀) LoRA 1 epoch on CubiCasa train 서브샘플(예: 10% stratified) → val F1이 GBDT 0.517에 **접근조차 못하면** fused·T-SILVER 확장 전에 kill 검토.
4. **Week 1–2**: 생존 시 6 open 셀(또는 12셀 중 open 절반) full train split, seed 1.
5. 평가: val만; test 봉인.

VRAM 추정(일반 지식·요검증): Qwen2.5-VL-3B LoRA + 1024–1536px 이미지는 16GB에서 가능 구간; fused(이미지+긴 벡터 텍스트)는 컨텍스트 길이가 병목 → 벡터 토큰 상한·샘플당 핸들 청크 필요.

### 4.3 DGX 계획 (unreachable 해제 후)

- open 12셀 full FT 또는 대형 vision 백본, vLLM 호스트와 야간 시분할.
- Ornith vision 지원 여부 **선확인(T13)** — 미지원이면 DGX는 학습만, 추론은 로컬/API.
- 확인 런(confirmation): 최적 (A,B,C) hold-out firm 재실행.

### 4.4 데이터량·누출

- Train: CubiCasa train 4,200 (선분 386만) — 핸들 단위 다운샘플 가능.
- Val: 400 — 조기 정지·셀 비교만.
- Test: 400 — **방법당 단발**.
- L-FIRM: firm/프로젝트 블록; L-SEED: 합성.
- 셔플 대조군 의무(GBDT AUC 0.375 PASS 전례와 동일 정신): 라벨 셔플 시 open 모델 AUC≈0.5 근처.

---

## 5. 구현 계획

### 5.1 모듈 골격 (신규는 CHANGE 허용 범위 밖 — 설계만)

본 좌석은 코드 작성 금지(패킷 CHANGE_ONLY=도시에는 파일 하나). 아래는 구현자가 따를 **파일 골격 제안**:

```
e2/vlm_p6/
  render_freeze.py      # DPI·캐시 키·해시 봉인
  serialize_vector.py   # SEG-IR → 토큰/JSON; name-blind
  pixel_handle_map.py   # T24 exact 역투영
  juror_prompt.py       # R23 시스템·few-shot 고정·스키마
  juror_parse.py        # STRICT_JSON; abstain
  finetune_qwen.py      # LoRA SFT 루프
  eval_per_handle.py    # R-SYN / CubiCasa F1; fast_score 접속
  doe_matrix.py         # 12셀 스케줄·seed·prereg 로드
  prereg_p6.json        # 합격선·킬·모형 봉인
  effects_table.csv     # UNRUN 슬롯
```

### 5.2 기존 도구 접속점

| 기존 | 접속 |
|------|------|
| `cubicasa_ir` | \(x^v\)·진리 Wall 모서리 |
| `cubicasa_ml` | GBDT 0.517 베이스라인 재현·동일 split |
| `fast_score` / NumPy 채점기 | 결정론 v0·P2 강건설정과 동일 지표로 open 모델 비교 |
| `evidence_grid` | 셀별 xlsx 증거 의무(평가 원칙) |
| E1.5 silver 파이프 | juror 자격 B1/B4·가문 분할 재사용 |

### 5.3 개발 규모 추정

| 작업 | 규모 | 의존 |
|------|------|------|
| render freeze + 캐시 | S (1–2일) | 없음 |
| pixel↔handle 하네스 | M (2–4일) | T24; 실패 시 fused per-handle `INADMISSIBLE` |
| juror 오케스트레이션 | S–M | API 승인 |
| LoRA SFT 루프 | M | 로컬 GPU |
| DOE 스케줄·집계·prereg | S | P5 R-META 게이트 가용 시 |
| 12셀 full | L (DGX 또는 다일 로컬) | PR-1/3, T13 |

### 5.4 구현 순서 (tweak-likelihood)

1. 역할 불변식·prereg 봉인 (판단)  
2. T24 역투영 가능 여부 (판단 — fused 해석 가능성)  
3. cheapest_probe / API 승인 (판단 — frontier 갈래)  
4. 렌더 freeze·캐시 (기계)  
5. open 축소 격자 (기계)  
6. 생존 시 확장·effects_table 기입 (기계)

---

## 6. 실험 셀 정의

공통 규칙: **val=개발·튜닝 허용, test=방법당 단발**, 합격선 평가 전 봉인, 셔플 대조군, 증거 xlsx, 실패도 사유 기록.

### 6.1 Cheapest probe (반나절)

| 항목 | 내용 |
|------|------|
| 셀 | `F-R-SYN` 우선 (예시원 T-SYN); 여유 시 `F-R-SIL` |
| n | 실도면 또는 divergent 후보 **5장** |
| 가설 | 프런티어 VLM이 래스터 평면도에서 벽을 silver로 찍을 **능력 존재** |
| 지표 | 파싱 성공률; handle 또는 선분 단위 합의(가용 진리와); E1.5 B1/B4 예비 |
| 합격선 | “완전 무작위보다 유의하게 벽 구조 언급” — **binary capability**; F1 합격선 아님 |
| 킬 | 능력 0 → frontier 6셀 종료, open만. API 미승인 → `BLOCKED`(킬과 구분) |
| 예산 | API 소액 + 0.5일; GPU 불필요 |
| 시드 | temp=0; few-shot 순서 고정; 프롬프트 해시 기록 |

### 6.2 Frontier 6셀 (juror 자격 실험)

| 항목 | 내용 |
|------|------|
| 가설 | raster ≫ vector; fused는 raster에 근접하거나 혼란; C는 few-shot 품질로만 약효과 |
| 지표 | silver 품질(B1 well-posed, B4 vs 탐지기/외부); R-SILVER 교차; **SoT 승격 지표 사용 금지** |
| 합격선 | B1≥0.70 **AND** B4 Pearson≥0.70 (calibration) → juror 자격 |
| 킬 | 신호 0(E1.5 대비) → juror 자격 미달, silver 학습 타깃 경로 봉쇄 |
| 예산 | API 중심; 가문 2×셀; 도면 샘플 상한 prereg |
| 시드 | few-shot 집합·순서 freeze |

### 6.3 Open-finetune 6셀 (탐지기 후보)

각 셀 공통:

| 항목 | 내용 |
|------|------|
| 가설 | 본문 effects: fused>vector>raster; T-SYN이 T-SILVER보다 전이 안정(또는 그 반대 — 둘 다 허용, 사전 방향은 SYN 선호) |
| 지표 | CubiCasa val F1/P/R/AUC; R-SYN F1; R-META 위반율(게이트 준비 시); 셔플 AUC |
| 제안 합격선 (초안·봉인 대상) | (1) val F1 ≥ GBDT **0.517** 또는 (2) R-SYN/R-META에서 P2 강건 v0를 **동시에** 상회. 둘 다 실패 시 계열 kill |
| 킬 | 최적 open 셀이 위 합격선 실패 → VLM 투자 무이득 하차 |
| 예산 | 셀당 LoRA 1 epoch: 로컬 0.5–2일 규모(서브샘플 먼저); full 12은 DGX |
| 시드 | 본선 seed=17 고정; 최적 셀만 seed=23 민감도 |

**셀별 한 줄 가설**

- `O-R-*`: 래스터가 FP 아이콘 억제에 기여하는지.  
- `O-V-*`: 벡터 직렬화만으로 GBDT 특징을 넘는 표현이 있는지(실패 시 “VLM vector는 중복”).  
- `O-X-*`: 융합 이득(표적). A×B는 frontier 대비로 추정.  
- `*-SIL`: silver 증류 위험 — CL-K와 교차 보고.

### 6.4 Confirmation run

| 항목 | 내용 |
|------|------|
| 대상 | 최적 (mode, modality, supervision) |
| 내용 | hold-out firm 재실행; frontier면 **배심원 자격만** 재확인(SoT 금지) |
| status | 패킷대로 `PASS_WITH_DEFERRAL` 슬롯(UNRUN) |
| 시드 | 본선과 동일 + 1회 반복 |

### 6.5 Effects / interactions 슬롯 (UNRUN)

- effects_table 슬롯: A·B·C main + A×B·B×C  
- interactions_found: 표적 A×B (사전: 큼); B×C (융합의 감독원 민감도)  
- 확정 실험 전 **순위표=판정 아님** (card rule 3)

---

## 7. red team 티켓 응답

P6/CL-G에 직접 걸리는 OPEN 티켓과 입장.

| 티켓 | 요지 | P6 응답 |
|------|------|---------|
| **T5 / PR-3** (sev 0.65) | FloorPlanCAD/CubiCasa NC 라벨·원 도면 권리 미해결 | **수용(하드 게이트)**. 외부셋 학습·aux FloorPlanCAD는 counsel 서면 전 `BLOCKED`. CubiCasa GO 국면이어도 가중치·산출은 방법검증 격리; 제품 탑재 금지(abstention ②). |
| **T13** | DGX Ornith vision 지원 여부 | **선확인 필수**. 미지원·unreachable 지속 시 DGX 계획 전체 defer; 로컬 LoRA만. |
| **T24** (CRS kill risk) | 픽셀→핸들 역투영 exact 하네스 | **fused/raster per-handle의 선결**. 합성 선검증 FAIL이면 fused 셀은 도면급 지표만, A×B per-handle 해석 `INADMISSIBLE`. |
| **T1 / PR-2** (0.75) | 대리 독립성 — 동일 parallel prior 증폭 | VLM fused가 같은 prior를 시각적으로 재학습할 위험 **인정**. P3/CL-E 불일치 구조 없이 P6 “성공”을 프로그램 승리로 승격하지 않음. |
| **T2 / PR-1** (0.70) | 벽 합성 생성기 부재·B1 FAIL | R-SYN 의존 셀은 생성기+fidelity 전 **약신뢰**. P6 1차 신호는 CubiCasa val + cheapest_probe로. |
| **T7 / CL-D** | 0벽 sentinel·recall 최저선 | R-META 판정은 sentinel 탑재 전 `DEFER`. 위반율-only로 VLM 통과 금지. |
| **T10/T23** 등 Graph IR | P6 직접 비의존 | 벡터 직렬화가 IR 완전성에 의존하면 간접 리스크 — serialize는 감사된 IR만. |
| **T26** | verifier false-accept ≤0.01 | GRPO 옵션 단계만 해당; SFT 본선은 우회 가능하나 보상 학습 확장 시 공유 게이트. |
| **T15** | seed-confound (P1 교훈) | P6도 seed 기록+최적 셀 반복; 셀마다 seed 튜닝 금지. |
| **T31 / feyerabend P5** | “래스터 본선” PARK | P6는 래스터를 **요인 수준**으로만 둠. “본선” 주장 비채택(반대의견 #4 보존). |
| **T34** | 인용 R-레인 experiment_executed:false | P6 문서의 문헌 수치 일반 지식은 요검증; **다이제스트 외 새 실측 금지**. |

**반대의견 원장 대응**

1. Silver 게이트 식별자: **B1∧B4** (calibration) 채택 — platt 단독 B1 인용 수정.  
2. Silver 신호 vs 오염: C=`T-SILVER`는 통제; feyerabend 입장은 CL-K와 공동 보존.  
4. VLM 프레임: R23대로 frontier=juror, open=detector; 래스터 본선 프레임 거부.

---

## 8. 인접 제안과의 관계

### 8.1 병합·의존

| 제안/클러스터 | 관계 |
|---------------|------|
| **CL-G** | P6의 패널 흡수형. 실행 시 CL-G 조건(T24·PR-3·E1.5 B1∧B4·T13)이 P6 게이트. |
| **P5 / CL-D** | R-META 반응 생성. P6 합격·킬의 한쪽 축. **먼저**. |
| **P2 / CL-B** | kill 비교 대상 “v0 결정탐지기 강건설정”. P6는 P2를 이기지 못하면 하차. |
| **P3 / CL-E** | 정답원 사슬·대리 독립성. 학습 투자 전 폐합 확인. |
| **P1** | 활성 요인 스크린 후 P6 청구서 축소 가능. |
| **P4 / CL-H** | RLVR과 함께 “무거운 투자” 밴드. 평가 단위·verifier 게이트 공유 이슈. |
| **platt P5 / calibration P4–P5** | 동일 CL-G 계열 — 배심원 게이트·래스터 트랙 정합. |
| **feyerabend P5** | 메커니즘만 CL-G 흡수; “본선”은 PARK — P6와 비병합. |
| **CL-K** | T-SILVER 셀의 철학적 통제. |

### 8.2 차별점

- P5: 라벨 0 불변성 — VLM 없음.  
- P2: 결정론 노브 — 표현 학습 없음.  
- P3: 대리 교차 — 모델 계열 비특정.  
- P4: 집합-조립/라우팅 RL — per-handle SFT와 분리.  
- **P6만** mode×modality×supervision으로 **VLM 역할 분리 + 융합 조건성**을 추정.

### 8.3 이 제안이 죽어야 하는 조건 (정직)

1. **정직한 kill (패킷)**: open 최적 셀이 R-SYN/R-META에서 P2 강건 v0를 못 이김 → VLM 계열 하차.  
2. **전이 kill**: CubiCasa val에서 GBDT 0.517을 넘지 못하고, 아이콘 FP 잔차도 증거 xlsx상 미회수.  
3. **Juror kill**: frontier silver가 E1.5 대비 신호 0 또는 B1∧B4 미달 → 프롬프트 갈래 종료(open은 잔존 가능).  
4. **게이트 kill**: PR-3 counsel 거부; T24 역투영 불능으로 표적 A×B가 해석 불능; PR-1 없이 R-SYN만으로 성공 주장하는 자기기만.  
5. **프로그램 hand-off**: 12셀 plateau(전 격자 무반응) → 요인을 발명하지 말고 **abduction 좌석**으로 이관(해치 poché·텍스트 주기·치수 참조 등).  
6. **우선순위 kill**: P5·P2·P3가 실패·미완인 채 DGX 12셀을 강행하는 것 — 절차적 사망(투자 낭비).

### 8.4 프로그램 정직 한계 (좌석 ABSTAIN)

- 요인 발명 금지.  
- 절대 진리 없음 — 대리 교차만.  
- 모든 효과 표는 UNRUN; 본 도시에는 실행 스펙이지 순위 판정이 아님.

---

## 부록 A — Verification design 5요소 (요약)

| 요소 | 내용 |
|------|------|
| truth | T-SYN / T-SILVER + T-META; CubiCasa Wall 모서리(외부) |
| leakage | L-FIRM + L-SEED; 렌더 해상도 freeze; name-blind |
| prereg | A×B 판정 + R-SYN/R-META 공통 밴드 + 합격선 봉인 |
| kill | §8.3 |
| cheapest_probe | frontier×raster 5장 (§6.1) |

## 부록 B — Compute plan 한 장

```
[API 미승인] → frontier BLOCKED → local open LoRA subset → (생존) full open cells
[API 승인]   → cheapest_probe → (pass) frontier 6 juror cells
                              → (fail) open only
[DGX up]     → open full FT 12 + confirmation on hold-out firm
[T24 fail]   → drop per-handle fused claims
[PR-3 fail]  → no NC train; synthetic/real firm only if licensed
```

---

DOSSIER_COMPLETE: doe_P6
