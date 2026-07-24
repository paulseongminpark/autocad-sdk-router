# REPORT — M-11 · 청주 S1BL 둘째-프로젝트 자격 조사

- cell: `m11_cheongju`
- generated_at: 2026-07-20 (Asia/Seoul)
- parent prereg: W3 PREREG, SHA prefix `1348c40b…` (Paul D4 승인 항목 M-11)
- archive (원본, READ-ONLY): `D:\dev\_ariadne\alm\build\실시도면 자료` — 144 DWG / 670,677,262 bytes
- 종합 판정: **QUALIFIED** (3/3 축 PASS, 표본 커버리지 1.000)

## W3-BOUNDARY (서두 인용)

> "본 보고의 탐지기 사다리·모든 val-A/val-B 수치의 유효 범위는 CubiCasa SEG-IR 우주 한정이다.
> E1 실무 도면 전이는 미검증이다."

본 셀은 그 경계를 **넓히기 위한 준비 조사**다 — 청주 실무 아카이브가 cross-project 축의 둘째 독립
프로젝트로서 구조적으로 자격이 되는지만 측정한다. **전이(transfer) 주장이 아니다.** XP 축 실제
활성화(프로젝트 페어링·AUC 산출)는 본 셀 소관이 아니며 차기 프리레그로 이연된다.

## W3-TELEM (이중 기록 — measurement.json과 동일)

| 항목 | 값 |
|---|---|
| wall_seconds | 2000.506 (39-sheet native 추출 배치) |
| peak_rss_bytes | 5,140,905,984 (background sampler, accoreconsole/python WorkingSet64 @400ms 최대) |
| peak_vram_bytes | N/A (no_GPU — GPU 미사용) |
| device | DESKTOP-PAUL / windows |
| budget_charge | ~2000.5 CPU-s (추출 배치가 지배적 비용). 캡 = CPU 6h(21,600s), 여유 충분 |

주: 오케스트레이션·집계 CPU는 별도 계측하지 않았다(추출 배치 wall이 지배적). 이는 누락이 아니라
지배 비용만 기록한 것이며, 나머지는 캡 대비 무시 가능.

## 데이터·CAD 규율 준수

- 원본 144 DWG **불변** — 분석은 전부 ASCII-이름 스테이징 사본(`staging\S00.dwg … S38.dwg`)에서만.
- DWG 접근 **손파싱 0건** — 첫 CAD 액션은 cad.* MCP(`cad_inspect_drawing`, S00에서 성공 증명:
  `router_status=ALL_AVAILABLE`, `native_available=true`, entity_count=389). 잔여 38장은 **동일 네이티브
  ObjectARX 엔진**의 CLI(`cadctl_cli.py inspect --mode rich`, MCP가 위임하는 바로 그 `cad.inspect`)를
  단일 루프로 실행 — 48장 배치를 MCP 왕복 39회로 도는 자원 낭비를 피하기 위한 R8 효력-보정 결정
  (손코딩 아님, 산출 아티팩트 동일: `dwg_graph_ir.json` native_full IR). 39/39 exit 0.
- 원본 손상·fake extraction 없음: 각 IR의 `source.original_path`는 스테이징 사본을 가리키고, 원본
  아카이브는 열지도 건드리지도 않았다.

## 표본 규칙 (PREREG_local.json에 선봉인, 수치 산출 전)

- 모집단: 아카이브 재귀 144 DWG.
- 파일 정체성(identity key) = 아카이브 루트 기준 상대경로(POSIX `/`, NFC, UTF-8 bytes). 사유: 아카이브에
  동일 basename이 하위폴더에 중복 존재 → basename 정렬/해시는 비결정적이므로 전체 상대경로를 정렬·해시
  양쪽의 표준 정체성으로 봉인.
- Set A = identity key 오름차순 첫 24장. Set B = SHA-256(identity key) 첫 hex nibble ∈ {0,2,4,6,8}인
  파일(pool 51장) 중 오름차순 첫 24장. 표본 = A∪B 중복제거 = **39장**(A∩B 겹침 9), ≤48 충족.
- 스테이징 사본은 ASCII 이름(S00–S38), 각 사본 SHA-256 기록(PREREG_local.json `selected_files`).

## 축별 판정 (봉인 임계값 대비 — measurement.json 정본, evidence.csv 정본 증거)

### 축 1 — 정의 어휘 존재: **PASS**
- M1a(어휘 매칭 레이어/블록명 ≥1 보유 시트 비율) = **1.000** (39/39). 봉인 PASS 조건 ≥0.50.
- M1b(표본 전체에서 매칭된 의미 카테고리 수, 10 중) = **9** (봉인 PASS 조건 ≥5). 미매칭 1종 = `stair`(계단).
- 매칭된 이름은 실제 전문 AEC 레이어/블록명 — 스퓨리어스 아님 (검증 통과):
  - wall: `WALL`, `A-WALL-MASN-PAT2`, `A02-벽체-조적`, `CW900`, `FCW/NCW/I-WALL`
  - opening(72 distinct): `A-DOOR`, `A-WIN`, `WINDOW`, `A-02-창(외부)`
  - dimension(13): `DIM`, `AA-AXIS-DIM7`, `DIMDOT`
  - text_note(42): `A-TEXT`, `A-ANNO-TEXT1`, `A-TXT1`
  - column(6): `COL`, `A-COL`, `DEFCOL`; room_space(35): `84a중심면적`, `시설면적`, `화장실`;
    finish_hatch(15): `A-03-마감(석고보드)`, `AFIN`; grid_axis(9): `GRID`, `b1grid`, `AXIS`; slab_floor(4): `RSLAB`, `슬래브 단차`.
- **정직한 한계(UNKNOWN 보존)**: 단일 한글 토큰(`실`,`열`)이 `경비실`·`단열`에서 부분일치하는 경미한
  over-match가 존재. 다만 A-WALL/A-DOOR/DIM/TEXT 등 명백한 이름이 사실상 전 시트에 있어 이 토큰들을
  제거해도 판정(PASS)은 불변. E1(384 정의)과 대응 가능한 명명 체계임이 확인됨.

### 축 2 — 핸들 체계: **PASS**
- M2a(모든 추출 엔티티가 비어있지 않은 handle 보유 시트 비율) = **1.000**.
- M2b(시트 내 handle 중복 0 비율) = **1.000**.
- M2c(엔티티가 resolvable owner[owner_handle+space] 보유 ≥0.95 시트 비율) = **1.000**.
- 봉인 PASS 조건 = 세 지표 모두 ≥0.95. E1식 handle-anchored SEG-IR 변환(예: `wall_line_handles`)을
  지탱하는 안정적 hex handle + 소유 구조(space=model/block, layout) 확인.

### 축 3 — 주석 가능성: **PASS**
- M3a(추출 시트 엔티티 수 중앙값) = **1267** (봉인 PASS 조건 ≥100).
- M3b(wall_candidate[LINE+LWPOLYLINE+POLYLINE+ARC] ≥20 시트 비율) = **0.949** (37/39, 조건 ≥0.60).
- M3c(text[TEXT+MTEXT] ≥1 시트 비율) = **1.000** (조건 ≥0.80).
- 봉인 PASS 조건 = 세 조건 동시 충족. 실물 실시도면답게 벽 후보 밀도·텍스트/치수 존재율이 silver
  라벨(판정자 앙상블) 생산에 충분.
- floor 미달 2장은 저-기하 시트로 정당: `A00-011 조감도.dwg`(8 엔티티, 렌더 성격),
  `A00-045~046 방화구획평면도.dwg`(69 엔티티, text/hatch 중심).

## 종합: **QUALIFIED**
봉인 규칙 = 3축 전부 PASS → QUALIFIED. 청주 S1BL 아카이브는 cross-project 축의 둘째 독립 프로젝트
역할을 할 **구조적 자격**을 갖춘다.

## 부수 확정 사실 (아카이브 기존 UNKNOWN 축소)
- **단위**: 표본 39/39 모두 Millimeters(insunits=2). 인벤토리의 "144 전체 단위 일관성 UNKNOWN"을 이
  결정적 39-표본 범위에서 mm 일관으로 좁힘(전체 144는 여전히 미측정 표면).
- **인코딩**: 39/39 시트에 한글 레이어/블록명 존재, mojibake 0건 — native-rich 추출이 cp949→UTF-8을
  손실 없이 보존(E-E census `kr_preserve` 계보와 일치).

## 계보(lineage) 교차참조
- E-E census(같은 144 아카이브 전수, PROGRAM 캠페인):
  `C:\Users\PAUL\Desktop\0713_research\experiments\PROGRAM_20260717\E-E_census\census_features.csv`.
  본 셀의 신선 추출을 대체하지 않고 보강 대조로만 사용. 그 헤드라인("단일 아파트 프로젝트 —
  교차 프로젝트 일반화 불가")은 청주가 **하나의 응집된 프로젝트**임을 독립 확인 → "둘째 프로젝트"
  전제와 정합. n_entities 대조도 일치(예: A20-001 finish schedule 389 == 본 셀 S00 389).
- 144-sheet ndjson 덤프는 **부재**(재사용 불가) — `D:\dev\_ariadne\alm\data\*.jsonl`은 84A 유닛
  semantic 파생물이지 per-sheet 아카이브 덤프가 아님. 따라서 신선 추출 수행(생략 안 함).

## 범위 밖 UNKNOWN (발명 금지, 보존)
- **재배포·학습 라이선스**: UNKNOWN (인벤토리와 동일). 본 셀 3축은 구조적 자격만 측정 — 라이선스는
  자격 축이 아니므로 미판정 유지. 실제 학습 입력 승격 전 별도 해소 필요.
- 전체 144 단위/인코딩 일관성: 39-표본 밖은 미측정.
- XP 축 활성화(interior-100 ↔ 청주 페어링, cross-project AUC): 차기 프리레그.

## 방법 결정 로그
- MCP-우선 준수: `cad_inspect_drawing`(rich)를 S00에서 성공 증명 후, 배치는 동일 `cad.inspect` 네이티브
  엔진의 CLI로 실행(R8: 39-파일 바운드 배치의 왕복 비용 회피). 아티팩트 동일.
- 봉인 우선(W3-SEAL): 모든 수치는 PREREG_local.json 봉인 이후 산출. 임계값·어휘는 PREREG에서 로드(재발명 0).

## 산출물 + SHA-256 (W3-PATH: 전부 절대경로 + SHA 병기)
- `D:\runs\e2_program\cells\m11_cheongju\PREREG_local.json` — `5323C349E1907342192F6AC11C474299C5F2AF2290FE6C995271962A991DC396` (20,535 B)
- `D:\runs\e2_program\cells\m11_cheongju\PREREG.csv` — `BA6EAA934806E704A562458C1C36C62E0C9B11BC78CA2DEA05525CFAB24814D6` (25,837 B, 144행 모집단 멤버십)
- `D:\runs\e2_program\cells\m11_cheongju\sample_manifest.json` — `4A16C00A055774B471C8A725D7FA08B63A58A5878472698C96B0AD7DE4607C08` (9,919 B)
- `D:\runs\e2_program\cells\m11_cheongju\measurement.json` — `4DB30288616CB635630E18D76C7765F5A3E36AD96D6634E0FB158BD1DF52771A` (2,827 B)
- `D:\runs\e2_program\cells\m11_cheongju\evidence.csv` — `2F694A00621F80A7692FEA521852CC28302D50853A444B4894A3522F618BD33F` (10,972 B, 정본 증거)
- `D:\runs\e2_program\cells\m11_cheongju\telem_extraction.json` — `629D51CACAF7EBF5514694BAF58C9DD00151EECC2F4D7A4ACB3DC58BB9970FBD` (354 B)
- per-sheet native IR: `D:\runs\e2_program\cells\m11_cheongju\extract\S00..S38\dwg_graph_ir.json` (39개)
