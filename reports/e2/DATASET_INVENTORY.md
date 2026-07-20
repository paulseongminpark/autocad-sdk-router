# E2 로컬 CAD·평면도 데이터셋 인벤토리

- 생성 시각: 2026-07-20 (Asia/Seoul)
- 실행 계약: 읽기 전용 harvest. 원본 파일의 이동·수정·삭제 없음.
- 측정 원칙: 파일 본문 대신 디렉터리 엔트리의 크기·확장자·수정시각을 집계했다. README, 로컬 manifest, 기존 결과 보고서는 provenance와 schema를 확인하는 범위에서 읽었다. 대형 컨테이너 해시는 생략했다.
- 보호 경계: test/val-B 계열은 존재와 split 표면만 기록하고 샘플 본문은 열지 않았다.
- 크기 표기: 정확한 byte가 기준이며, 괄호 안 IEC 크기는 읽기 편의를 위한 근삿값이다.

## 요약

| 항목 | 절대 경로 | 측정 규모 | E2 사용 상태 | W3 실물 트랙 후보 적합성 |
|---|---|---:|---|---|
| FloorPlanCAD | `D:\datasets\FloorPlanCAD` | 10,630 files / 454,847,042 bytes | 메타데이터만; 해당 cell은 무효 | 벽·개구부·기호 지도학습 후보, 라이선스 충돌 해소 필요 |
| ArchCAD | `D:\datasets\ArchCAD` | 205,504 files / 9,874,167,331 bytes | 메타데이터만; 해당 cell은 무효 | 다중 모달 primitive/instance 사전학습 후보 |
| pseudo-floor-plan-12k | `D:\datasets\pseudo-floor-plan-12k` | 22 files / 3,922,945,924 bytes | 메타데이터만; 해당 cell은 무효 | synthetic 사전학습·변형 테스트 후보 |
| Zenodo10K partial | `D:\datasets\Zenodo10K` | 1,654 files / 14,260,986,093 bytes | 메타데이터만; 해당 cell은 무효 | CAD GT가 아닌 문서-layout 대조군 후보 |
| Text2CAD | `C:\datasets\Text2CAD` | 113 files / 604,874,254,779 bytes | 사용 증거 없음 | 언어-CAD 의미 전이 후보; floor-plan GT 아님 |
| CubiCasa5K | `D:\datasets\cubicasa5k.zip`; `D:\dev\_ariadne\huggingface\datasets\cubicasa5k\zenodo\cubicasa5k.zip`; `D:\dev\_ariadne\huggingface\datasets\cubicasa5k\cubicasa5k` | 2 ZIP / 10,938,991,412 bytes; extracted footprint UNKNOWN | CRS·graph 계열 cell에서 사용 | segmentation/graph/judge 검증 후보; test 격리 |
| E1 annotation corpus | `D:\dev\99_tools\autocad-sdk-router\reports\e1` | 178 files / 10,780,453 bytes | F01/F02/F03/C70/C71 및 graph 계열 | silver/weak label 후보; human GT로 취급 금지 |
| interior-100 real axis | `D:\dev\.build\1.dwg`; `D:\dev\99_tools\autocad-sdk-router\runs\e2_b3_dxfout_20260717\1_export.dxf` | 2 files / 17,674,100 bytes | E2 실측의 주 real axis | handle·geometry anchor; 단일 프로젝트 한계 |
| Hyundai304 | `D:\dev\01_projects\02_dashboard\00_given\현대304동.3dm` | 1 file / 5,848,510 bytes | 사용 증거 없음 | 추가 real-project 후보; 파생 semantics는 candidate-only |
| 청주 S1BL 실시도면 archive | `D:\dev\_ariadne\alm\build\실시도면 자료` | 163 files / 1,136,308,960 bytes; DWG 144 | E2 사용 증거 없음 | archive-scale 및 THK text 추출 후보 |
| 격리 ZIP 후보 | `C:\Users\PAUL\Desktop\실시도면 자료.zip` | 1 ZIP / 1,136,566,464 bytes | 사용 증거 없음 | provenance·split·license 해소 전 격리 유지 |

## 데이터셋별 상세

### 1. FloorPlanCAD

- 이름: FloorPlanCAD.
- 절대 경로: `D:\datasets\FloorPlanCAD`.
- 크기·개수·형식: 454,847,042 bytes (433.78 MiB), 10,630 files. `.metadata` 5,314, `.png` 5,308, `.json` 2, `.yml` 1, `.md` 1, `.gif` 1, `.gitattributes` 1, `.gitignore` 1, `.tag` 1.
- label/annotation: 로컬 dataset card는 5,308개 로컬 sample과 object-detection 표현을 설명한다. 원 출처 설명은 15,663 annotated floor plans, 30 categories, 28 thing classes와 wall/parking stuff classes를 기재한다. 로컬 표현은 PNG, bounding box, mask이며 원 데이터는 line-grained vector annotation으로 설명된다.
- 좌표·단위 단서: bounding box는 `[0,1]` 정규화. dataset card는 SVG 좌표에 10을 곱해 PNG에 대응한다고 설명한다. 원 설명에는 meter 기반이라는 문구가 있으나 로컬 raster만으로 실제 물리 단위를 재검증하지 않았다.
- 라이선스·출처: `D:\datasets\FloorPlanCAD\README.md` 내부에서 YAML frontmatter의 `cc-by-sa-4.0`과 본문의 `CC BY-NC 4.0`이 충돌한다. 따라서 정확한 사용 조건은 **UNKNOWN / 해결 필요**다. 출처 표기는 FloorPlanCAD dataset card다.
- E2 사용/cell: `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\g0a_inventory\REPORT.md`에서 메타데이터 census만 수행되었고 그 cell의 최종 상태는 `INVALID_PROTOCOL_BREACH`다. 유효한 E2 학습·평가 사용은 입증되지 않았다.
- W3 fit: wall/opening/symbol category 지도학습 또는 judge prior 후보. 다만 license 충돌 해결과 split 재확인 전에는 학습 입력으로 승격하면 안 된다. 로컬 card가 test split이라고 표기하므로 이번 harvest는 샘플 본문을 열지 않았다.

### 2. ArchCAD

- 이름: ArchCAD.
- 절대 경로: `D:\datasets\ArchCAD`.
- 크기·개수·형식: 9,874,167,331 bytes (9.20 GiB), 205,504 files. `.json` 82,194, `.png` 41,098, `.svg` 41,097, `.npy` 41,097, `.metadata` 11, `.md` 4 및 소수의 repository metadata 파일.
- label/annotation: 로컬 card는 약 40k sample, raster PNG·SVG·JSON·Q&A caption·NPY point cloud의 5개 정렬 modality, primitive semantic 및 instance labels, wall을 포함한 약 30 classes를 설명한다.
- 좌표·단위 단서: sample당 14 m × 14 m slice라는 설명은 있으나 각 로컬 numeric field의 단위·원점·축 convention은 명시적으로 검증되지 않아 **UNKNOWN**이다.
- 라이선스·출처: `D:\datasets\ArchCAD\README.md`에 `cc-by-nc-4.0`; 출처는 `jackluoluo/ArchCAD`와 ArchCAD-400K paper로 표기된다.
- E2 사용/cell: `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\g0a_inventory\REPORT.md`의 메타데이터 census만 확인되며 cell은 `INVALID_PROTOCOL_BREACH`다.
- W3 fit: vector/raster/point/QA를 함께 쓰는 primitive·instance pretraining 후보. 실제 W3 채택 전 좌표 convention과 split isolation을 별도 검증해야 한다.

### 3. pseudo-floor-plan-12k

- 이름: pseudo-floor-plan-12k.
- 절대 경로: `D:\datasets\pseudo-floor-plan-12k`.
- 크기·개수·형식: 3,922,945,924 bytes (3.65 GiB), 22 files. `.parquet` 8, `.metadata` 10, `.md` 1 및 repository metadata 파일. Card상 논리 sample 수는 train 12,000이다.
- label/annotation: `plans`, `walls`, `colors`, `footprints`, `captions`; Grasshopper PlanFinder 기반 synthetic 생성물로 설명된다.
- 좌표·단위 단서: 물리 단위·CRS는 card에서 확인되지 않아 **UNKNOWN**이다.
- 라이선스·출처: `D:\datasets\pseudo-floor-plan-12k\README.md`에 명시적 license를 확인하지 못했다. 출처는 로컬 card의 synthetic/Grasshopper 설명이며 사용 조건은 **UNKNOWN**이다.
- E2 사용/cell: `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\g0a_inventory\REPORT.md`의 메타데이터 census만 확인되며 cell은 `INVALID_PROTOCOL_BREACH`다.
- W3 fit: synthetic pretraining, augmentation, metamorphic test 후보. real-world 성능의 독립 근거 또는 ground truth로 취급하면 안 된다.

### 4. Zenodo10K partial

- 이름: Zenodo10K partial / PPTAgent presentation corpus.
- 절대 경로: `D:\datasets\Zenodo10K`.
- 크기·개수·형식: 14,260,986,093 bytes (13.28 GiB), 1,654 files. `.pptx` 823, `.metadata` 826, `.parquet` 1 및 repository metadata 파일. 로컬 mirror는 partial이다.
- label/annotation: presentation 파일과 per-item metadata/license field를 갖는 문서 corpus로 설명된다. CAD 또는 floor-plan geometry label은 확인되지 않았다.
- 좌표·단위 단서: slide/document 좌표 외 CAD 물리 단위는 해당 없음.
- 라이선스·출처: `D:\datasets\Zenodo10K\README.md`는 PPTAgent/Zenodo10K 및 Zenodo 출처를 설명한다. license는 item별로 달라 aggregate license는 **UNKNOWN**이다.
- E2 사용/cell: `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\g0a_inventory\REPORT.md`의 메타데이터 census만 확인되며 cell은 `INVALID_PROTOCOL_BREACH`다.
- W3 fit: CAD GT로는 부적합. 문서-layout/negative control 연구가 명시될 때만 별도 후보가 된다.

### 5. Text2CAD

- 이름: Text2CAD v1.
- 절대 경로: `C:\datasets\Text2CAD`.
- 크기·개수·형식: 604,874,254,779 bytes (563.33 GiB), 113 files. `.metadata` 55, `.zip` 43, `.json` 3, `.gitattributes` 3, `.pkl` 2, `.csv` 2, `.md` 1, `.pth` 1, `.txt` 1, `.gitignore` 1, `.tag` 1.
- label/annotation: abstract/beginner/intermediate/expert 수준의 language descriptions, description 및 keywords. README는 archive 내부 CAD sequence, minimal JSON, RGB/depth image 등을 설명한다.
- 좌표·단위 단서: CAD sequence와 camera 정보가 있으며 camera matrix는 Blender coordinate system을 언급한다. model geometry의 물리 단위는 **UNKNOWN**이다.
- 라이선스·출처: `C:\datasets\Text2CAD\README.md`에 `cc-by-nc-sa-4.0`; 출처는 DFKI/Text2CAD v1.
- E2 사용/cell: 확인된 E2 사용 없음.
- W3 fit: text-to-CAD semantic transfer 또는 language supervision 후보이며 floor-plan wall GT는 아니다. `C:\datasets\Text2CAD\train_test_val.json`은 존재만 확인하고 내용을 열지 않았다.

### 6. CubiCasa5K

- 이름: CubiCasa5K.
- 절대 경로: `D:\datasets\cubicasa5k.zip`; `D:\dev\_ariadne\huggingface\datasets\cubicasa5k\zenodo\cubicasa5k.zip`; 추출 split 표면 `D:\dev\_ariadne\huggingface\datasets\cubicasa5k\cubicasa5k`.
- 크기·개수·형식: ZIP 2개, 각각 5,469,495,706 bytes (5.09 GiB), 합계 10,938,991,412 bytes (10.19 GiB). 두 ZIP은 byte size가 같지만 대형 hash를 생략했으므로 duplicate라고 단정하지 않는다. 추출 tree는 test isolation 때문에 재귀 집계하지 않아 전체 물리 footprint는 **UNKNOWN**이다.
- label/annotation: `D:\datasets\MANIFEST.md`는 약 5,000 floor plans와 80+ class SVG ground truth를 설명한다.
- 좌표·단위 단서: `D:\dev\99_tools\autocad-sdk-router\reports\e2\instruments\crs_REPORT.md`의 근거는 SVG coordinate에서 pixel-edge로의 transform을 사용한다. 물리 단위는 **UNKNOWN**이다.
- 라이선스·출처: 로컬 E1/W3 note는 non-commercial 조건을 언급하지만 보호된 archive 내부의 정확한 license 파일은 이번 harvest에서 열지 않았다. 정확한 on-disk license는 **UNKNOWN**이며 출처는 CubiCasa/cubicasa5k GitHub·Zenodo로 기록돼 있다.
- E2 사용/cell: CRS bridge의 label-free 3 samples, `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\graph_builder\REPORT.md`의 val 400, `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\g5_full_graph\REPORT.md`의 한 high_quality_architectural reference 사용을 확인했다. graph_builder 보고서는 test 미사용을 명시한다.
- W3 fit: segmentation, graph construction, judge validation 후보. 추출 root에서 `D:\dev\_ariadne\huggingface\datasets\cubicasa5k\cubicasa5k\train.txt`, `D:\dev\_ariadne\huggingface\datasets\cubicasa5k\cubicasa5k\val.txt`, `D:\dev\_ariadne\huggingface\datasets\cubicasa5k\cubicasa5k\test.txt`와 quality directories의 존재만 확인했으며 test 파일 내용과 test sample payload는 열지 않았다.

### 7. E1 annotation corpus

- 이름: E1 local annotation/silver corpus.
- 절대 경로: `D:\dev\99_tools\autocad-sdk-router\reports\e1`.
- 크기·개수·형식: 10,780,453 bytes (10.28 MiB), 178 files. `.json` 132, `.md` 21, `.txt` 20, `.py` 3, `.xlsx` 1, `.jsonl` 1.
- 내부 구성: `D:\dev\99_tools\autocad-sdk-router\reports\e1\annot_v1\raw`은 JSON 100개 / 2,555,078 bytes; `D:\dev\99_tools\autocad-sdk-router\reports\e1\sonnet_annot`은 JSON 20개 / 239,536 bytes; `D:\dev\99_tools\autocad-sdk-router\reports\e1\annot_v1\prompts`는 21 files / 699,133 bytes. v0 명시 파일 `D:\dev\99_tools\autocad-sdk-router\reports\e1\ornith_annot_v0.jsonl`, `D:\dev\99_tools\autocad-sdk-router\reports\e1\wall_pairs_v0.json`, `D:\dev\99_tools\autocad-sdk-router\reports\e1\wall_crosscheck_v0.json`, `D:\dev\99_tools\autocad-sdk-router\reports\e1\calibration_v0.json`은 합계 6,859,782 bytes.
- label/annotation: `unit_id`, `def`, `role`, `wall_likelihood`, `wall_line_handles`, `notes`, 일부 schema의 `rationale`. multi-judge에서 생성된 weak/silver annotation이며 human-authored GT로 입증되지 않았다.
- 좌표·단위 단서: staged DXF entity handles와 연결된다. `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\f01_handle_forensics\REPORT.md`는 unit name을 **UNKNOWN**으로 남긴다. 표시 치수의 1:1 관계는 mm 또는 m를 증명하지 않는다.
- 라이선스·출처: 로컬 E1 작업 산출물. 원 CAD의 재배포·학습 license는 on disk에서 확인되지 않아 **UNKNOWN**이다.
- E2 사용/cell: F01/F02/F03/C70/C71, graph_builder, g5 계열의 annotation/real-axis 근거. `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\f03_real_probe\REPORT.md`는 0 cross-scope pair로 `BLOCKED_INPUT`; C71의 cross-project AUC도 프로젝트 수 부족으로 `BLOCKED_INPUT`이다.
- W3 fit: silver supervision 및 review queue seed 후보. human GT와 분리하고 blocked cross-project gate를 유지해야 한다.

### 8. interior-100 / E1 real source axis

- 이름: interior-100 real source and staged DXF.
- 절대 경로: canonical `D:\dev\.build\1.dwg`; derived staging `D:\dev\99_tools\autocad-sdk-router\runs\e2_b3_dxfout_20260717\1_export.dxf`.
- 크기·개수·형식: 2 files, 합계 17,674,100 bytes (16.86 MiB). `.dwg` 1 = 2,368,524 bytes; `.dxf` 1 = 15,305,576 bytes.
- label/annotation: raw files 자체에는 검증된 semantic GT가 없다. 대응 silver labels는 위 E1 corpus에 별도로 존재한다.
- 좌표·단위 단서: DXF/CAD model coordinates와 entity handles. F01 결과의 unit name은 **UNKNOWN**이다.
- 라이선스·출처: local source; 소유권·재배포·학습 조건은 **UNKNOWN**이다.
- E2 사용/cell: F01 handle forensics, F02 wall-pair measurements, F03 cross-scope attempt, C70/C71, graph_builder, g5의 주 real axis.
- W3 fit: handle continuity, geometry extraction, wall-pair scoring의 anchor 후보. 기존 실측은 한 independent project만 확보해 cross-project 일반화 주장을 지원하지 않는다.

### 9. Hyundai304

- 이름: Hyundai304 Rhino model.
- 절대 경로: `D:\dev\01_projects\02_dashboard\00_given\현대304동.3dm`.
- 크기·개수·형식: 1 `.3dm`, 5,848,510 bytes (5.58 MiB).
- label/annotation: source에 검증된 GT label은 없다. `D:\dev\01_projects\02_dashboard\runs\hyundai304_ir_ingest\02_ingest_hyundai304_ir.py`는 candidate-only derived semantics를 생성하며 ontology는 discovered가 아니라 legislated라고 명시한다.
- 좌표·단위 단서: read-only rhino3dm metadata에서 `UnitSystem.Meters`, absolute tolerance `0.001`, angle tolerance `0.017453292519943295` radians, 4,743 objects, 38 layers를 확인했다. 파생 ingest coordinate 표기는 `model_world`다.
- 라이선스·출처: source·license 표기가 없어 **UNKNOWN**이다.
- E2 사용/cell: 확인된 E2 사용 없음. 기존 파생 출력은 `D:\dev\_ariadne\harness\runs\CAD_IR_HYUNDAI304_INGEST_20260619_CLAUDE\outputs`에 있으며 원본과 분리되어 있다.
- W3 fit: meter 단위의 추가 real-project 후보. 파생 semantics는 candidate로만 사용하고 검토 전 GT로 승격하지 않는다.

### 10. 청주 테크노폴리스 S1BL 실시도면 archive

- 이름: Cheongju Technopolis S1BL implementation-drawing archive.
- 절대 경로: `D:\dev\_ariadne\alm\build\실시도면 자료`.
- 크기·개수·형식: fresh metadata census 기준 1,136,308,960 bytes (1.06 GiB), 163 files. `.dwg` 144 / 670,677,262 bytes, `.pdf` 2 / 405,154,722 bytes, `.jpg` 2 / 40,985,494 bytes, `.png` 10 / 19,417,877 bytes, `.log` 2 / 13,349 bytes, `.xlsx` 1 / 59,982 bytes, `.dwl` 1 / 58 bytes, `.dwl2` 1 / 216 bytes.
- label/annotation: human semantic GT는 확인되지 않았다. 기존 item census와 파일명/sheet metadata가 있다. `C:\Users\PAUL\Desktop\0713_research\experiments\PROGRAM_20260717\E-D2_archive_inventory\RESULT.md`는 `A20-011~015 형별성능관계내역(아파트).dwg` 이름의 native ARX extract에서 7,558 entities, 823 texts, `THK·mm` pattern 71 hits를 보고하며 `THK250 콘크리트`, `THK40 시멘트몰탈`, `THK115 PF보드`를 예로 든다. 현재 source에는 그 이름이 `D:\dev\_ariadne\alm\build\실시도면 자료\01 건축(사업승인)\건축\A20-011~015 형별성능관계내역(아파트).dwg`, `D:\dev\_ariadne\alm\build\실시도면 자료\01_건축(실시설계)\01.DWG\00.표제부\A20-011~015 형별성능관계내역(아파트).dwg`, `D:\dev\_ariadne\alm\build\실시도면 자료\01_건축(실시설계)\01.DWG\01.건축\A20-011~015 형별성능관계내역(아파트).dwg`의 세 곳에 있고 기존 evidence가 exact original을 구분하지 않으므로 어느 copy였는지는 **UNKNOWN**이다. 71은 파생 text evidence이지 dataset-wide label 수가 아니다.
- 좌표·단위 단서: native DWG coordinates. `D:\dev\99_tools\autocad-sdk-router\runs\dwg_truth_autocad_20260717_090437607_p38868_3034\extract_arx.json`의 staged selected drawing은 `source.units = Millimeters`를 기록한다. 이는 선택된 drawing의 단서이며 144개 archive 전체의 단위 일관성은 검증하지 않아 **UNKNOWN**이다.
- 라이선스·출처: 기존 census는 청주 테크노폴리스 S1BL 단일 프로젝트의 승인+실시설계 자료라고 기록한다. on-disk 재배포·학습 license는 확인되지 않아 **UNKNOWN**이다.
- E2 사용/cell: 확인된 E2 사용 없음. 기존 분석은 `C:\Users\PAUL\Desktop\0713_research\experiments\PROGRAM_20260717\E-D2_archive_inventory` 및 `C:\Users\PAUL\Desktop\0713_research\experiments\PROGRAM_20260717\E-E_census`의 별도 PROGRAM 실험이다.
- W3 fit: archive-scale parsing, text/thickness extraction, discipline classification 후보. 먼저 project independence, license, split을 확인해야 한다.
- count 정합성: 기존 E-D2 prereg의 예상치는 DWG 145였으나 fresh filesystem census와 E-E full sweep은 모두 DWG 144를 가리킨다. 현재 authoritative count는 144이며 오래된 145 예상치의 원인은 **UNKNOWN**이다. E-D2 RESULT의 문서 상단 status는 여전히 `DRAFT`이고 본문 headline은 inline confirmation을 기록하므로 최종 승인 상태도 별도 확인이 필요하다.

### 11. 격리된 실시도면 ZIP 후보

- 이름: isolated implementation-drawing ZIP / holdout candidate.
- 절대 경로: `C:\Users\PAUL\Desktop\실시도면 자료.zip`.
- 크기·개수·형식: 1 `.zip`, 1,136,566,464 bytes (1.06 GiB), mtime `2026-06-05T20:25:30.7308452+09:00`.
- label/annotation: archive payload를 열지 않았으므로 **UNKNOWN**이다.
- 좌표·단위 단서: **UNKNOWN**.
- 라이선스·출처: `D:\datasets\MANIFEST.md`가 unopened holdout candidate로 기록한다. 정확한 provenance와 license는 **UNKNOWN**이다.
- E2 사용/cell: 확인된 E2 사용 없음.
- W3 fit: provenance·license·split이 해소될 때까지 격리 유지. `D:\dev\_ariadne\alm\build\실시도면 자료`의 container인지도 hash 또는 manifest로 입증하지 않았으므로 관계는 **UNKNOWN**이다.

## Zone 조사 결과

- `D:\assets`: `D:\assets\index.yaml` 및 `D:\assets\index.md`를 먼저 읽었다. index는 policy-only였고 root에 dataset item은 없었다.
- `D:\mirror`: `D:\mirror\index.yaml` 및 `D:\mirror\index.md`를 먼저 읽었다. root의 `D:\mirror\chrome-profile_20260707`은 CAD dataset으로 분류하지 않았다.
- `D:\dev\reference`: `D:\dev\reference\index.yaml` 및 `D:\dev\reference\index.md`를 먼저 읽었다. architecture/code/reference 항목만 확인됐고 dataset item은 없었다.
- `D:\dev\research`: `D:\dev\research\index.yaml` 및 `D:\dev\research\index.md`를 먼저 읽었다. root에 CAD dataset item은 없었다.
- `D:\datasets`: index는 없었으나 `D:\datasets\MANIFEST.md`를 읽고 명시된 raw dataset roots만 집계했다. `D:\datasets\_models`는 model이라 제외했다.
- `D:\archive`: `D:\archive\index.yaml` 및 `D:\archive\index.md`를 먼저 읽었다. indexed CAD dataset item은 없었다.
- `D:\Ndrive`: `D:\Ndrive\index.yaml` 및 `D:\Ndrive\index.md`를 먼저 읽고 named Hyundai 후보만 제한적으로 확인했으나 일치 항목은 없었다.

## 보호 split 및 읽기 경계

- `D:\dev\_ariadne\huggingface\datasets\cubicasa5k\cubicasa5k\test.txt`: 존재만 확인; 내용 미열람.
- `D:\dev\_ariadne\huggingface\datasets\cubicasa5k\cubicasa5k\val.txt`: split 표면 존재만 확인; 이번 harvest에서 sample payload 미열람.
- `C:\datasets\Text2CAD\train_test_val.json`: 존재만 확인; 내용 미열람.
- `C:\Users\PAUL\Desktop\실시도면 자료.zip`: container metadata만 확인; archive payload 미열람.
- E2의 val-B/test 보호 영역은 재귀 탐색하거나 내용을 열지 않았다.

## 불확실성 및 차단 항목

- FloorPlanCAD license conflict: `cc-by-sa-4.0` 대 `CC BY-NC 4.0`; 해결 전 사용 조건 **UNKNOWN**.
- CubiCasa5K exact on-disk license와 extracted footprint: 보호 경계 때문에 **UNKNOWN**.
- interior-100, E1 source, Hyundai304, 청주 S1BL archive의 재배포·학습 조건: **UNKNOWN**.
- E1 F03 cross-scope pair와 C71 cross-project AUC: `BLOCKED_INPUT`; 이를 PASS로 재해석하지 않는다.
- 두 CubiCasa ZIP의 동일성 및 Desktop ZIP과 추출 archive의 관계: size만으로 입증되지 않아 **UNKNOWN**.
- `g0a_inventory` metadata 결과는 존재하지만 protocol status가 `INVALID_PROTOCOL_BREACH`이므로 유효 cell 완료로 세지 않는다.

## Telemetry

- `wall_seconds`: `15.832424` — 두 metadata census process의 wall time 합계(주요 roots 15.358977초 + archive addendum 0.473447초). 조사·보고서 작성 orchestration 시간은 포함하지 않는다.
- `peak_rss_bytes`: `108945408` — 두 census process에서 관측한 최대 PeakWorkingSet64.
- hash policy: 대형 dataset/ZIP hash는 생략; size와 mtime을 evidence로 사용했다.
- write scope: `D:\runs\e2_program\dataset_inventory\INVENTORY.md` 및 `D:\dev\99_tools\autocad-sdk-router\reports\e2\DATASET_INVENTORY.md`만 생성한다. 원본 dataset은 변경하지 않았다.

INVENTORY_COMPLETE
