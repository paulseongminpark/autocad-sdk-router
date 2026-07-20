# M-12 ArchCAD 데이터셋 자격 검증 보고서

**PREREG_local.json SHA-256:** `46facdbd18d1dfdcd26b3a630cb1b4cbb114b6471104af39ba320a40552ca721`  
**PREREG.csv SHA-256:** `aa0526e21535379a5e0303af3753ce8088312bf3f2b315ab19bd58831134789e`  
**최종 판정:** `TRACK_BLOCKED`

> 본 보고의 탐지기 사다리·모든 val-A/val-B 수치의 유효 범위는 CubiCasa SEG-IR 우주 한정이다. E1 실무 도면 전이는 미검증이다.

## 판정

| 축 | 판정 | 결정 근거 |
|---|---|---|
| 스키마 | **PASS** | 봉인 표본 500/500에서 5모달 파싱·파일키/JSON↔SVG 의미·인스턴스 정렬 100%; 선언된 31개 의미 ID 전부 실측; 미해석 ID 0%; wall=`semantic:20` 실측 |
| 분할 격리 | **FAIL** | 전량 경로 census에서 공식 train/val/test 디렉터리·manifest 0건; 표본 JSON의 project/drawing grouping key 0건; 누수 검증 자체 불가 |
| 좌표 규약 | **INCONCLUSIVE** | 980×980, 좌상단 원점, `+x` 우향/`+y` 하향, NPY `[code,y,x]`는 실측했으나 물리 단위·world origin은 machine-readable 근거가 없음 |
| 어댑터 타당성 | **PASS** | 실측된 `LINE/ARC/CIRCLE/ELLIPSE` 전부를 현재 `seg.v1`로 결정적으로 변환 가능; 손실·UNKNOWN·격리 규칙을 설계 문서에 명시 |
| 종합 | **TRACK_BLOCKED** | 봉인 종합 규칙상 한 축이라도 FAIL이면 TRACK_BLOCKED; 공식·프로젝트 격리 split 부재가 학습 투입 blocker |

어댑터 기술 타당성 PASS는 학습 자격 PASS가 아니다. 이 셀은 학습을 실행하지 않았으며, `D:\runs\e2_program\cells\m12_archcad\ADAPTER_FEASIBILITY.md`의 설계만 작성했다.

## 실행 경계와 데이터 고정

- 패킷: `D:\runs\e2_program\build\PACKET_w3_m12_archcad.md` (`8f24733aef56a3eced73f278b6acf004c5305e652d7f8dc057e3346a116dcbbf`).
- inventory: `D:\dev\99_tools\autocad-sdk-router\reports\e2\DATASET_INVENTORY.md` (`95c7186c0bca94a8565924b5a2fa98dff6f298ff5e012d088f522df106cec5f0`).
- inventory가 지정한 원본: `D:\datasets\ArchCAD`.
- 원본 census: `205,504` files, `9,874,167,331` bytes. inventory 수치와 일치한다.
- 실행 장치: CPU only. `CUDA_VISIBLE_DEVICES=-1`; GPU 호출·VRAM 사용 없음.
- 모든 선언·실행 IO 경로는 절대경로다. 상대경로 precheck 위반은 0건이다.
- git 명령과 서브에이전트는 사용하지 않았다. 원본 데이터에 대한 write API는 실행하지 않았고 파생 산출은 `D:\runs\e2_program\cells\m12_archcad`에만 기록했다.

## W3 telemetry

`D:\runs\e2_program\cells\m12_archcad\measurement.json`과 본 절에 동일한 주 측정 telemetry를 기록한다.

| 필드 | 값 |
|---|---:|
| wall_seconds | `55.94478320001508` |
| peak_rss_bytes | `312315904` |
| peak_vram_bytes | `N/A(no_GPU)` |
| device | `CPU — AMD64 Family 26 Model 68 Stepping 0, AuthenticAMD; 24 logical cores; CUDA_VISIBLE_DEVICES=-1` |
| budget_charge | `0.015540217555559744 CPU-hours / 8 CPU-hours cap` |

실패/무효 측정 런도 숨기지 않았다.

| 런 | 상태 | wall_seconds | peak_rss_bytes | 처리 |
|---|---|---:|---:|---|
| `candidate_intersection_v1` | failed | `71.287986` | `208822272` | PowerShell HashSet overload 오류; usable sample 0, 봉인 규칙 그대로 재실행 |
| `single_sample_probe_v1` | failed | `WALL_SECONDS_RESOURCE_NOT_RECORDED` | `PEAK_RSS_BYTES_RESOURCE_NOT_RECORDED` | Windows에 `resource` 모듈 없음; dataset file open 전에 실패; budget=`BUDGET_CHARGE_RESOURCE_NOT_RECORDED` |
| `primary_measurement_v1` | failed_invalid_measurement | `64.03682010000921` | `311070720` | ARC를 full-circle bbox로 잘못 확장한 checker bug; 표본·기준 변경 없이 수정 후 재측정 |

## 선봉인과 표본

데이터 파일을 열기 전에 `D:\runs\e2_program\cells\m12_archcad\PREREG_local.json`과 `D:\runs\e2_program\cells\m12_archcad\PREREG.csv`를 생성하고 read-only로 봉인했다. 그 뒤에만 측정했다.

봉인 규칙은 확장자별 최대 family 1개(`.png`, `.svg`, `.npy`)와 `.json` 최대 family 2개를 file count 내림차순·절대경로 lexical tie-break로 선택하고, 다섯 family basename 교집합을 `SHA256("M12_ARCHCAD_W3|" + sample_key)` 오름차순으로 정렬해 앞의 `min(500,N)`을 취한다. 실측 family는 다음과 같다.

| 모달 | 절대 디렉터리 | 파일/고유 stem |
|---|---|---:|
| PNG raster | `D:\datasets\ArchCAD\data\png` | 41,097 |
| SVG vector | `D:\datasets\ArchCAD\data\svg` | 41,097 |
| NPY point | `D:\datasets\ArchCAD\data\point` | 41,097 |
| caption Q&A JSON | `D:\datasets\ArchCAD\data\caption` | 41,097 |
| entity JSON | `D:\datasets\ArchCAD\data\json` | 41,097 |

교집합 후보는 `41,097`, 봉인 표본은 `500`, 대체 표본은 `0`이다. 첫 키는 `12ff0471-4cec-4543-a6e9-f02f5fcc28b6`, 500번째 키는 `7d88181f-65dd-48d0-8fe7-10ea910211da`다. 표본 전체와 per-sample 상태는 `D:\runs\e2_program\cells\m12_archcad\measurement.json`과 evidence 정본 `D:\runs\e2_program\cells\m12_archcad\evidence.csv`에 있다.

## 1. 스키마 — PASS

### 5모달의 실제 구성과 정렬

- PNG: 500/500 header parse, 모두 `980×980`.
- SVG: 500/500 XML parse, 모두 `viewBox="0 0 980 980"`; 표본 합계 `path=204,770`, `circle=3,317`, `ellipse=104` semantic-bearing element.
- entity JSON: 500/500 parse, top-level은 500건 모두 `{"entities": [...]}`. 실측 entity 합계 `208,191`.
- caption JSON: 500/500 parse, 모두 Q&A object list.
- NPY: 500/500 `allow_pickle=false` parse, 전부 `N×3`, finite. 첫 열의 실측 code는 `{1,2,3,4}`이며 좌표열은 `[code,y,x]`로 500/500 일관했다.
- 동일 UUID stem, PNG/SVG canvas, JSON↔SVG entity 수·semantic 순서·instance 순서가 500/500 일치했다. 따라서 봉인 PASS 기준의 five-family full parse와 alignment는 모두 `1.0`이다.

NPY는 vector JSON의 완전한 복사본이 아니다. LINE endpoint multiset match의 p05/median/p95는 `0.2905288889 / 0.5528777907 / 0.7407503358`로, dedup/downsampling/quantization을 포함한 control-point 표면이다. 의미·기하 정본은 entity JSON이고 NPY는 audit-only여야 한다.

### 라벨·wall·primitive

`D:\datasets\ArchCAD\README.md` (`d6e741d6924aa51994a83dd1163e8fedbce1024376740e645eca36aaf4126af8`)의 ID/name 표를 문서 근거로 고정하고, 실제 entity JSON에서 ID 존재와 값 범위를 측정했다.

- 실측 semantic ID: `0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,100` — 선언 31개 전부 관측.
- unexplained semantic: `0 / 208,191 = 0.0`.
- wall은 ID `20`, 문서상 non-countable이고 실제 표본에서 `19,265` primitive가 `semantic:20`; instance presence는 `0.0`이다. 즉 wall primitive class는 있으나 wall-object instance grouping은 없다.
- primitive: `LINE=185,712`, `ARC=18,278`, `CIRCLE=3,317`, `ELLIPSE=884`.
- `LINE`은 start/end, `ARC`는 center/radius/start/end/angles/direction, `CIRCLE`은 center/radius, `ELLIPSE`는 center/major-axis/ratio/params/endpoints를 machine-readable field로 제공한다. 네 타입 모두 semantic, style fields를 제공하며 countable class는 대체로 instance도 제공한다. 다만 일부 countable class의 instance 누락은 0이 아니므로 adapter가 합성하면 안 된다.

## 2. 분할 격리 — FAIL

`D:\datasets\ArchCAD`의 205,504개 절대경로를 전량 census했지만 train/training/val/validation/test/split/manifest 이름의 파일 또는 디렉터리는 `0`건이다. 표본 entity JSON top-level도 `entities`뿐이고 project, drawing, source, family 계열 grouping key는 `0`건이다. 파일명은 독립 UUID이며 UUID에서 parent drawing/project를 복원할 근거가 없다.

따라서 공식 train/val/test 분할은 존재하지 않는 것으로 판정한다. 동일 도면에서 만들어진 여러 14 m slice가 무작위 sample split을 가로지를 수 있는지 측정할 project key 자체가 없어 누수는 `UNKNOWN`이 아니라 **검증 불가능한 고위험 상태**다. 선봉인 FAIL 기준인 “공식 분할 없음”에 직접 해당한다. 이후 split을 임의 생성해 이 셀을 PASS로 소급 변경할 수 없다.

## 3. 좌표 규약 — INCONCLUSIVE

확정 가능한 machine-readable 좌표 규약은 다음과 같다.

- JSON/SVG/PNG plane: `980×980`, origin `(0,0)` top-left, `+x` right, `+y` down.
- NPY: `[primitive_code,y,x]`; SEG-IR audit 좌표로 읽을 때 `[x,y]=[column2,column1]`.
- coordinate-bearing sample: `500/500`; non-finite `0`; degenerate occupied extent `0`.
- JSON LINE bbox와 NPY code-1 bbox의 extent residual `<=5%`: `497/500 = 0.994`; median=`0`, p95=`0`, max=`0.1103166496`.
- JSON occupied span p05/median/p95: x=`866.2669318796 / 980.0000000000 / 1639.2794247623`, y=`758.6236567537 / 980.0000000000 / 1972.3116783704` coordinate units. 980보다 큰 값은 slice canvas 밖 curve/control geometry가 SVG/PNG에서 clip되는 경우를 포함한다.

machine-readable physical unit, CAD world origin, source drawing transform은 모두 `UNKNOWN`이다. README의 “14 m × 14 m slice”를 믿으면 후보 scale은 `14000/980 = 14.2857142857 mm/coordinate-unit`이지만 문서 단독 주장이므로 `scale_mm_per_unit`에 넣지 않는다. 안전한 SEG-IR 변환은 좌표 identity, `units="px"`, `scale_mm_per_unit=null`, `axis_convention="x_right_y_down_origin_top_left"`다. 물리 단위가 미확정이므로 선봉인 PASS의 모든 요건을 충족하지 못해 `INCONCLUSIVE`다; 충돌을 실측한 것은 아니므로 FAIL도 아니다.

## 4. 어댑터 타당성 — PASS (설계만)

`D:\runs\e2_program\cells\m12_archcad\ADAPTER_FEASIBILITY.md`는 entity JSON을 authority로 선택하고, 네 geometry type의 chord/segment 규칙, deterministic unique handle, 31-class preservation과 E2 `wall/opening/other` projection, instance null 보존, 좌표 identity, curve sidecar/loss ledger, split quarantine를 정의한다.

현재 E2 core contract의 필수 top-level `ir/drawing_id/units/scale_mm_per_unit/segments`와 per-segment `sid/handle/pts/layer/kind/label/source`를 모두 채울 수 있다. source에 없는 layer/physical scale/project/split/wall-instance는 `UNKNOWN`/null로 명시하고, analytic curve는 최대 7.5° chord와 exact-parameter sidecar로 보존한다. 따라서 silent corruption 없이 설계 가능한 기술 축은 PASS다. 단, `eligible_for_training=false`는 공식 project-isolated split이 생길 때까지 고정한다.

## 결론과 다음 gate

ArchCAD는 machine-readable 31-class primitive semantics와 일관된 5모달 구조를 갖고 있어 adapter/pretraining 후보로서 기술적 가치는 확인됐다. 그러나 현재 로컬 복제본에는 공식 split과 parent-project provenance가 모두 없다. 무작위 UUID split은 drawing leakage를 만들 수 있으므로 이 상태의 학습 투입은 금지한다.

다음 프리레그는 코드 작성이나 학습보다 먼저 원 배포자 제공 project/drawing grouping 및 official split manifest를 확보·해시 봉인해야 한다. 그것이 없으면 M-12는 계속 `TRACK_BLOCKED`다.

## 산출물과 SHA-256

| 절대경로 | SHA-256 |
|---|---|
| `D:\runs\e2_program\cells\m12_archcad\PREREG_local.json` | `46facdbd18d1dfdcd26b3a630cb1b4cbb114b6471104af39ba320a40552ca721` |
| `D:\runs\e2_program\cells\m12_archcad\PREREG.csv` | `aa0526e21535379a5e0303af3753ce8088312bf3f2b315ab19bd58831134789e` |
| `D:\runs\e2_program\cells\m12_archcad\measurement.json` | `2132e962b458fe0a51b2fba52ffa189880b0c90cfb6840775e00a00976989d6e` |
| `D:\runs\e2_program\cells\m12_archcad\evidence.csv` | `27bf3046b2a2943636c90d7852d93467ca6e21139433f23fd12576d5b53a6297` |
| `D:\runs\e2_program\cells\m12_archcad\ADAPTER_FEASIBILITY.md` | `fdbe455dc382dcd1f82d5f5adbed764cc1f2a285ef2039395423cf9796e7c4d3` |
| `D:\runs\e2_program\cells\m12_archcad\measure_archcad.py` | `57f19c7c32262567c25edad5b8c959fe36f4f11af6ed4a4887964e6cf573a509` |

`D:\runs\e2_program\cells\m12_archcad\REPORT.md`의 final hash는 보고서 작성 후 생성되는 `D:\runs\e2_program\cells\m12_archcad\SHA256SUMS.csv`에 기록한다.
