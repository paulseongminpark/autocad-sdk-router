# Seat 4 — FULL INDEPENDENT AUDIT (cross-vendor skeptic)

## 감사 범위와 재실행 방법

- 도시에, C0/C1/L1/L1b 코드와 지정 산출물을 READ-ONLY로 조사했다. Git, 서브에이전트, 원본 CAD, CubiCasa test는 사용하지 않았다.
- 원본 L1b 모듈의 출력 경로만 `D:\runs\e2_program\chainverify_L1b\seat4_work\rerun_same_path\`로 바꿔, 서로 다른 Python 프로세스 두 개가 **같은 소스·같은 입력·같은 출력 경로**를 사용하도록 전량 재실행했다.
- C0/C1 모듈을 import하지 않는 stdlib 재구현으로 raw scene JSON의 앵커 추정, family 구조 witness, KS/TV, truth integrity, 교란 전이를 다시 계산했다. 수치 전문은 `seat4_work\independent_recompute.json`에 있다.

## 발견 사항 (심각도순)

### CRITICAL-1 — “재실행 바이트 동일” 주장은 실제 전량 재실행에서 거짓이다

주장 근거인 프로그램 저널은 L1b 재실행 결과가 바이트 단위로 같았다고 명시한다 (`D:\dev\99_tools\autocad-sdk-router\reports\e2\PROGRAM_JOURNAL.md:420-445`, 특히 433행). 그러나 같은 경로에 두 번 전량 실행한 결과, 생성 파일 204개 중 201개만 같고 다음 3개가 달랐다 (`seat4_work\independent_recompute.json:198-226`).

| 파일 | run 1 SHA-256 | run 2 SHA-256 | 결과 |
| --- | --- | --- | --- |
| `REPORT.md` | `f141ac32bdb65443f377c370f3a28cad0081bf6e9dec05bf55feebe241ffc984` | `7082afd8146535aba7d947b0d26261f92d1ed53dc6fa82eae06dba96ef69bb75` | 불일치 |
| `c1v3_results.json` | `f1b0fe02c4d33ffd6ae79bb74b4a1dbfa492a2acbb77fc997582e59334fdecff` | `b49fc0dddaf8a440e8a42493185a94cbb5edfe1e06d6268f1d5bdf074637df69` | 불일치 |
| `evidence.xlsx` | `76a4fc5e25a76df9ae0aa97ab2f0d3a75dd9975177e7f2c7fbda5cda1d31e665` | `2ebfcec6b0a913bc45c386f14c0fcfb7f1bf412ed3cd31ad25f46b72bee0bf33` | 불일치 |

원인은 코드에서도 직접 확인된다. L1 runner는 실행마다 wall/CPU 시간을 측정 (`D:\dev\99_tools\autocad-sdk-router\tools\e2\cells\loop_l1.py:1249-1250,1309-1310`)하여 `c1v3_results.json`의 `runtime`에 직렬화한다 (`loop_l1.py:1362-1369`). L1b는 이 `L1.execute_full()`을 그대로 호출한다 (`D:\runs\e2_program\cells\loop_l1b\loop_l1b.py:1270-1276`). 실제 JSON leaf 차이는 CPU 0.921875→1.09375초, C1 wall 1.0765233→1.1466458초, loop CPU 2.671875→2.921875초, loop wall 2.8803756→3.0415316초 및 workbook hash/size였다 (`seat4_work\independent_recompute.json:228-268`).

XLSX를 압축 해제한 entry별 비교에서는 셀 데이터가 아니라 `docProps/core.xml` 하나가 달랐고, created/modified 시각이 `17:13:41/42Z`에서 `17:13:58/59Z`로 바뀌었다 (`seat4_work\independent_recompute.json:270-283`). 이 hash가 C1 JSON에 들어가고, C1 JSON/workbook hash가 REPORT의 artifact 표에 들어가므로 REPORT도 달라진다 (`loop_l1.py:1385-1397`).

현재 selftest는 같은 프로세스 안에서 개별 fixture scene SHA만 비교한다 (`loop_l1b.py:567-580`). 마지막 verifier도 파일 존재·개수·family count만 검사하며 이전 실행 바이트와 비교하지 않는다 (`loop_l1b.py:1217-1267`). 따라서 저널의 바이트 동일 주장을 지지하는 verifier가 증거 사슬에 없고, 독립 재실행은 그 주장을 직접 반증한다.

### CRITICAL-2 — SoT가 요구한 이중 사전봉인 산출물이 없어 “봉인 밴드 불변”을 계약대로 입증하지 못한다

도시에의 전역 셀 규칙은 모든 threshold를 실행 전에 `prereg.json`과 `evidence.xlsx`의 `PREREG` sheet에 **동시에** 봉인하도록 요구한다 (`D:\dev\99_tools\autocad-sdk-router\reports\e2\dossiers\feyerabend_P2.md:738-740`).

독립 파일·OOXML 조사 결과는 다음과 같다 (`seat4_work\independent_recompute.json:146-196`).

- `D:\runs\e2_program` 전체에 `prereg.json`이 0개다.
- repo E2 아래 기존 `prereg*.json` 후보 5개 중 Feyerabend C1의 HIGH 0.60/정확도 0.95 봉인을 함께 담은 파일은 0개다.
- L1b `evidence.xlsx`의 15개 sheet 중 `PREREG`는 없다. L1 및 원 C1 workbook에도 없다.
- L1b 코드가 선언한 출력 목록 (`D:\runs\e2_program\cells\loop_l1b\loop_l1b.py:30-37`)과 final required-artifact 검사 (`loop_l1b.py:1217-1223`)에도 prereg 산출물이 없다.

현재 코드 상수와 산출 수치가 서로 일치한다는 것은 확인했지만, 그것은 “실행 전에 이중 봉인했고 이후 움직이지 않았다”는 이력 증거가 아니다. SoT가 정한 봉인 절차 자체가 충족되지 않았으므로, 불확실하면 REFUTE라는 감사 계약에서 “봉인 밴드는 어느 반복에서도 이동하지 않았다”를 확인할 수 없다.

### MEDIUM — 두 대표 성능 수치는 맞지만 독립적인 난이도/일반화 증거는 아니다

이 항목만으로 수치 gate를 FAIL 처리하지는 않지만, 주장 해석 범위를 제한한다.

- clean HIGH 정확도 1.0은 생성 규칙상 사실상 예정돼 있다. L1 rich anchor는 `display_value = span`으로 생성되고 (`D:\dev\99_tools\autocad-sdk-router\tools\e2\cells\loop_l1.py:161-195`), single-span도 `raw_span = display_value = 1000`이다 (`D:\runs\e2_program\cells\loop_l1b\loop_l1b.py:152-172`). scale 복제는 기하/raw span만 κ배하고 display는 유지하면서 truth를 `1/κ`로 둔다 (`D:\dev\99_tools\autocad-sdk-router\tools\e2\cells\feyerabend_c0.py:889-905`). 추정기가 계산하는 `display/geometric_span`은 따라서 clean scene에서 정확히 truth다 (`D:\dev\99_tools\autocad-sdk-router\tools\e2\cells\feyerabend_c1.py:347-383`).
- fidelity corpus도 reference histogram을 읽어 1,200개 gap을 그 분포에 배정하고 (`feyerabend_c0.py:717-747`), reference entity mix에 맞을 때까지 filler를 채운 뒤 (`feyerabend_c0.py:829-847`), 같은 reference와 KS/TV를 계산한다 (`feyerabend_c0.py:1278-1292`). 따라서 KS/TV는 정확히 재현되지만 독립 holdout fidelity 검증은 아니다.

## 독립 재계산으로 확인된 항목

위 두 치명 결함과 별개로, 다음 숫자 주장은 원본 scene에서 재현됐다.

| 항목 | 독립 재계산 | 판정 |
| --- | --- | --- |
| scale별 HIGH coverage | κ=0.001/0.01/1/1000 각각 40/50 = **0.80** | 수치 확인 |
| HIGH 정확도 | 160/160 = **1.0**; scale별 최대 상대오차 `0`~`3.11e-15` | 수치 확인 |
| mutation family | tag뿐 아니라 구조 witness도 **11/11**, single-span 10, multiple-span 40 | 수치 확인 |
| fidelity | KS **0.040287855437306064**, TV **0.00021191458340744963** | 수치 확인 |
| truth integrity | 독립 truth 오류 scene 0, 4-scale handle/truth-pair mismatch base 0 | 수치 확인 |
| label blindness | label 입력 변경 196/200(나머지 4는 zero-wall), anchor artifact 동일 200/200, mismatch 0; 정적 bridge key는 `anchors` 단독 | 수치 확인 |
| 교란 역전이 | duplicate/stale/suffix/outlier 모두 상태·confidence 상승 0; stale confidence 하락 200 및 unit HIGH→LOW 48, outlier confidence 하락 200 | 수치 확인 |

근거 수치: `seat4_work\independent_recompute.json:23-145`. 전체 gate matrix에서 수치·truth·교란 항목은 true지만, dual preregistration과 byte-identical rerun은 false이며 결합 주장은 false다 (`seat4_work\independent_recompute.json:286-297`).

판정 사유: 핵심 C0/C1 숫자는 재현됐으나, 명시적 결합 주장 중 “재실행 바이트 동일”이 직접 반증됐고 SoT의 이중 봉인 절차도 누락됐다.

VERDICT: REFUTE
