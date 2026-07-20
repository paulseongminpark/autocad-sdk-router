# M-8 R50 FloorPlanCAD 의미축 자격 보고서

**PREREG_local.json SHA-256:** `15be9fd05420fa68dc5775c0cbc8f170e7b4cf64122d45ffa15dc778f9fb7e9b`  
**PREREG.csv SHA-256:** `1f707343cf56ce34b144a7b5f5f3c5678fcbe6ae548823de2072ecd3d73b51f5`  
**종합 판정:** `NOT_QUALIFIED`

> 본 보고의 탐지기 사다리·모든 val-A/val-B 수치의 유효 범위는 CubiCasa SEG-IR 우주 한정이다. E1 실무 도면 전이는 미검증이다.

## 판정

| 자격 축 | 판정 | 결정 근거 |
|---|---|---|
| 라벨 스키마 | **INCONCLUSIVE** | 카드가 30개 이름을 열거하지만 저장 annotation에는 35개 label이 있고, `class_31`, `class_32`, `class_34`, `class_35`의 의미를 로컬 근거로 해소할 수 없다. wall과 opening 계열 자체는 표본에서 실측했다. |
| 마스크 정합 | **INCONCLUSIVE** | 6,402 paired object의 crop 차원 정합 99.219%, 좌표 유효 99.922%, centroid-distance p95 0.000816이지만, 봉인된 IoU+centroid 동시 정합률은 91.862%로 PASS 95%와 FAIL 90% 사이 gray band다. 변환계 불일치 도면율 2.5%는 FAIL 기준 10% 미만이다. |
| 분할 격리 | **FAIL** | 로컬 package는 card상 `test` 단일 split이고 5,308 sample에 공식 per-sample split field/tag가 없으며, 문서화된 project/drawing group key도 없다. train 대 held-out의 프로젝트 격리를 검증할 수 없어 봉인 FAIL 조건에 직접 해당한다. |
| 의미 밀도 | **INCONCLUSIVE** | 598 evaluable drawing 중 wall-positive 533건(89.130%); wall pixel fraction median 1.7444%, 범위 0.1%–60% 충족률 87.793%, wall instance median 1. PASS 문턱 두 항목은 미달하지만 FAIL 문턱에는 닿지 않아 gray band다. |
| 종합 | **NOT_QUALIFIED** | 봉인 종합 규칙은 한 축이라도 FAIL이면 `NOT_QUALIFIED`이며 split isolation은 hard blocker다. |

이 셀은 데이터 자격만 측정했다. R51 trainer 착지(C-1)나 R51 측정(M-9)은 실행하지 않았다.

## W3 telemetry

`D:\runs\e2_program\cells\m8_r50\measurement.json`과 본 절에 동일한 주 측정 telemetry를 이중 기록한다.

| 필드 | 값 |
|---|---:|
| wall_seconds | `7.002601199987112` |
| peak_rss_bytes | `237088768` |
| peak_vram_bytes | `N/A(no_GPU)` |
| device | `CPU — AMD64 Family 26 Model 68 Stepping 0, AuthenticAMD; 24 logical cores; CUDA_VISIBLE_DEVICES=-1` |
| budget_charge | `0.00194516699999642 CPU-hours / 6 CPU-hours cap` |

GPU 호출은 없었다. 무효 측정 런도 숨기지 않았다.

| 런 | 상태 | wall_seconds | peak_rss_bytes | 처리 |
|---|---|---:|---:|---|
| `primary_measurement_v1` | `failed_invalid_measurement` | `8.784935399977257` | `236908544` | drawing의 aligned-object rate가 90% 미만이라는 사실만으로 일관된 axis/scale/origin mismatch라고 잘못 승격한 checker 조건을 폐기했다. 봉인 표본과 판정 기준은 바꾸지 않고 transform mismatch를 crop 차원률·centroid shift로 직접 검사하여 재실행했다. |

## 실행 경계와 원본 보존

- packet: `D:\runs\e2_program\build\PACKET_w3_m8_r50.md`.
- inventory: `D:\dev\99_tools\autocad-sdk-router\reports\e2\DATASET_INVENTORY.md`.
- inventory가 지정한 원본: `D:\datasets\FloorPlanCAD`.
- 원본 census는 10,630 files / 454,847,042 bytes로 inventory와 정확히 일치한다.
- 측정 전후 `(relative path, size, mtime_ns)` manifest SHA-256은 모두 `f09991a76849698e1edf1e63a92754580f025cfc0d37c638e7e1ba4d6e820687`이며 원본 tree는 변하지 않았다.
- 모든 명시적 IO 경로는 절대경로다. 상대경로 precheck 위반은 0건이다.
- 원본 write, git 명령, GPU, 서브에이전트 사용은 모두 0건이다. 파생 산출은 `D:\runs\e2_program\cells\m8_r50`에만 썼다.

## 선봉인과 결정적 표본

원본 통계 산출 전에 다음 규칙과 판정 기준을 `PREREG_local.json`과 `PREREG.csv`에 선봉인했다.

1. 후보는 원본 root 아래 대소문자 무관 `.png` 전부이며 key는 root-relative `/` 경로다.
2. ordinal 정렬 첫 300건을 lexical arm으로 고정했다.
3. 나머지 key의 UTF-8 SHA-256 마지막 hex nibble이 짝수인 후보를 `(hash,key)`로 정렬해 첫 300건을 hash-even arm으로 고정했다.
4. 최대 표본은 600건이며 대체 표본은 허용하지 않았다.

실측 후보 5,308건에서 lexical 300 + hash-even 300 = 600건을 얻었고 `samples.json` 누락 key와 중복 sample record는 각각 0건이다. 첫/끝 key는 다음과 같다.

| arm | 첫 key | 끝 key |
|---|---|---|
| lexical | `data/0000-0003.png` | `data/0052-0011.png` |
| hash-even order | `data/0875-0045.png` | `data/0474-0012.png` |

표본 600건의 선택 key와 PNG SHA-256은 evidence 정본에 모두 기록했다.

## 1. 라벨 스키마 — INCONCLUSIVE

로컬 `README.md`는 30개 class name을 열거하고 wall/parking을 stuff, door/window/opening_symbol을 opening semantics로 설명한다. 전량 `samples.json` 실측은 35개 label을 찾았다.

- undeclared observed labels: `class_31`, `class_32`, `class_34`, `class_35`, `railing`.
- unresolved placeholder labels: `class_31`, `class_32`, `class_34`, `class_35`.
- 전량 wall detection: 4,710건.
- 봉인 표본 wall detection: 535건.
- 봉인 표본 door/window/opening detection: 1,750건.

관측 이름 기반으로 `wall -> wall`, 7개 door/window/opening name을 `opening`, 나머지 명시 class를 `other`로 투영할 수 있다. 그러나 네 `class_N`의 실제 의미를 추측해 `other`로 승격하면 UNKNOWN 발명에 해당한다. 선언 30과 저장 35를 화해할 로컬 mapping table이 없으므로 봉인된 conflict 조건에 따라 INCONCLUSIVE다.

## 2. 마스크 정합 — INCONCLUSIVE

로컬 annotation은 별도 full-frame mask 파일이 아니라 각 FiftyOne detection의 zlib-compressed NPY crop이다. 공급된 normalized bbox를 독립 좌표 envelope로 사용해 mask crop의 픽셀 위치를 복원했다.

| 측정 | 실측 | 봉인 기준 |
|---|---:|---|
| sampled drawings with pairs | `600` | 최소 `30` |
| total / decoded masks | `6,407 / 6,407` | decode evidence |
| paired nonempty objects | `6,402` | 최소 `100` |
| bbox coordinate validity | `6,402 / 6,407 = 99.92196%` | PASS `>=99%`, FAIL `<95%` |
| crop dimension agreement | `6,352 / 6,402 = 99.21899%` | PASS `>=99%`, FAIL `<95%` |
| aligned object | `5,881 / 6,402 = 91.86192%` | PASS `>=95%`, FAIL `<90%` |
| bbox-envelope IoU p05 / median / p95 | `0.860349 / 0.971855 / 0.998870` | object aligned if `>=0.90` |
| normalized centroid distance p05 / median / p95 | `0.000153 / 0.000496 / 0.000816` | object aligned if `<=0.02` |
| systematic transform mismatch drawings | `15 / 600 = 2.5%` | FAIL if `>=10%` |

차원과 centroid는 좌표계·origin 정합을 강하게 지지하지만, IoU 동시 기준의 정합률이 PASS와 FAIL 사이에 남는다. 원본 SVG는 로컬 package에 없으므로 그 이상을 vector truth로 보강하지 않았다.

## 3. 분할 격리 — FAIL

- `README.md` 제목은 로컬 export를 `test split`으로 명시한다.
- card는 원 데이터의 6,382 train / 3,712 test를 서술하지만, 로컬 5,308건에는 `split` field가 없고 모든 `tags`가 비어 있다.
- 문서화된 project/drawing group identifier는 없다. 파일명 prefix를 프로젝트 ID로 추정하지 않았다.
- 따라서 cross-split group overlap과 cross-split exact duplicate overlap은 `N/A(single_local_split)`이며 0이라고 발명하지 않았다.
- 봉인 표본 안 exact PNG duplicate group은 17개였지만, 이것만으로 cross-split leak를 주장하지 않는다.

공식 train plus held-out assignment가 없는 경우는 봉인된 직접 FAIL 조건이다. 새 split을 이 셀에서 합성하지 않았으며, 이 축은 track blocker다.

## 4. 의미 밀도 — INCONCLUSIVE

wall detection crop을 normalized bbox 위치에 되붙여 도면별 union wall pixels를 계산했다. wall mask crop 차원 불일치가 있던 2건은 density에서 제외하여 598건만 evaluable로 유지했다.

| 측정 | 실측 | 봉인 PASS | 봉인 FAIL |
|---|---:|---:|---:|
| evaluable drawings | `598` | `>=500` | `<100`이면 evidence 부족 |
| wall-positive rate | `533/598 = 89.13043%` | `>=90%` | `<75%` |
| wall pixel fraction p05 / median / p95 | `0% / 1.7444% / 5.40527%` | median `1%–40%` | median `<0.5%` 또는 `>60%` |
| fraction in `0.1%–60%` band | `87.79264%` | `>=90%` | 별도 hard FAIL 없음 |
| wall instances p05 / median / p95 | `0 / 1 / 1` | median `>=1` | median `0` |

표본 수·median density·median instance는 PASS 측을 충족하지만 wall-positive rate와 in-band rate가 각각 약 0.87%p, 2.21%p 부족하다. 반대로 어느 FAIL 문턱도 넘지 않아 봉인 규칙상 INCONCLUSIVE다.

## 한계와 다음 gate

- 이 판정은 로컬 5,308-image `test` export에 한정하며 원 논문의 15,663 vector drawing 전체를 대표한다고 주장하지 않는다.
- unresolved `class_N`에 대한 원 출처 mapping과 프로젝트 단위 공식 split manifest가 확보되어야 재자격할 수 있다.
- 특히 split FAIL이 해소되기 전에는 이 로컬 package를 R51 학습 input으로 승격하면 안 된다.

## 정본과 SHA-256

`evidence.csv`가 evidence 정본이며 1,828 data row를 가진다. `REPORT.md` 최종 self-hash는 보고서 기록 후 `D:\runs\e2_program\cells\m8_r50\SHA256SUMS.csv`에 기록한다.

| artifact | SHA-256 |
|---|---|
| `D:\runs\e2_program\build\PACKET_w3_m8_r50.md` | `1adff5ad594ad951dbc8c5721d95493306d20a4ccb3bd8d70f6f0dc53a275c56` |
| `D:\dev\99_tools\autocad-sdk-router\reports\e2\DATASET_INVENTORY.md` | `95c7186c0bca94a8565924b5a2fa98dff6f298ff5e012d088f522df106cec5f0` |
| `D:\runs\e2_program\cells\m8_r50\PREREG_local.json` | `15be9fd05420fa68dc5775c0cbc8f170e7b4cf64122d45ffa15dc778f9fb7e9b` |
| `D:\runs\e2_program\cells\m8_r50\PREREG.csv` | `1f707343cf56ce34b144a7b5f5f3c5678fcbe6ae548823de2072ecd3d73b51f5` |
| `D:\runs\e2_program\cells\m8_r50\measurement.json` | `1589bc2c127915768e56eb4a08113fa1cde8bc840f905bc4d4bb0240d3b66d8c` |
| `D:\runs\e2_program\cells\m8_r50\evidence.csv` | `60bb106d84dbc4cbde8a5ed9a6a94f5d085086a5b3c5c8f6c77f3b94f3352fea` |
| `D:\runs\e2_program\cells\m8_r50\measure_floorplancad.py` | `655eedc0b13f744bd40d975cbcf3aa140fa0721225331abcaebbf309f726f5d8` |
