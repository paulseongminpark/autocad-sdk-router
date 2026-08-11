# E2 XCLIP 표시 구성원 관측기·모델 입력 모집단 자격 보고서

작성일: 2026-08-07

> **역사 스냅샷 표지 (2026-08-11 갱신)**
>
> 이 문서는 2026-08-07 기록 시점의 실험 결과를 보존한다. 당시의 수치와
> `PASS`/`PASS_WITH_DEFERRAL`/`RETRACTED` 판정은 역사 기록으로 유지하지만,
> 당시 `target_population_oracle.json`의 `status=PASS` 형식은 현재 v1
> authoritative oracle 계약(`status=OBSERVED`, source/receipt/hash 결속)을
> 만족하지 않는 legacy 형식이다. 따라서 이 문서의 artifact를 현재 권위로
> 자동 승격해서는 안 된다.
>
> 기록 기준 commit: `b4621e60d14f5bdef1859eee9c504a9ef79848a6`.
> 아래의 현재형 표현과 실행 결과는 모두 그 commit 당시의 기록이다.
> 현재 구현·CI·병합 상태의 정본이 아니며, 현행 source·receipt·GitHub
> checks를 다시 검증하지 않고 이 문서를 현재 권위로 사용할 수 없다.

## 결론

이번 단계의 결론은 **관측기와 모델 입력 모집단 자격 `PASS`**다. 독립적인 full AutoCAD/ObjectARX 관측기가 XCLIP으로 잘린 원본 선분을 판정했고, 그 결과가 WorldIR와 모델 입력에 같은 안정 ID로 전달되었다.

다만 이것은 탐지기(detector)나 모델의 성능 실험이 아니다. W1/W2 레이어는 실험 대상을 고정하는 라벨 앵커(label anchor)이며 탐지 성과가 아니다. 따라서 과학적 범위는 **`PASS_WITH_DEFERRAL`**이다. 다음 단계에서 이 모집단을 사용해 탐지기·모델 실행과 성능 측정을 별도로 해야 한다.

여기서 표시 구성원(display membership)은 “원본 선분 인스턴스가 블록 삽입 변환, 레이어·엔티티 표시 상태, XCLIP 경계 적용 뒤 남아 있는가”를 뜻한다. XCLIP은 블록 참조에 붙은 공간 자르기 경계다. WorldIR(World Intermediate Representation)은 이 원본 도면 그래프를 월드 좌표 선분으로 확장한 중간 표현이다.

## 무엇을 반증했나

### DWF/DMM 가설 — `RETRACTED`

DMM(Drawing Model Management) 경로의 콜백 수를 표시 구성원 판정으로 사용할 수 있다는 가설을 통제 fixture로 반증했다.

`D:\runs\e2_program\native_display_oracle\fixture_20260807_123705\02_dmm\job_out.json`에서 다음이 관찰되었다.

| 대상 | DMM entity callback | graphic ID가 있는 callback | 판정 |
|---|---:|---:|---|
| `E2_DMM_VISIBLE` | 1 | 0 | 판정 불가 |
| `E2_DMM_CLIPPED` | 1 | 0 | 판정 불가 |

보이는 선과 XCLIP으로 완전히 제외된 선에 콜백이 모두 왔고, 두 기록 모두 graphic ID가 비어 있었다. 따라서 DMM 콜백 존재 여부는 membership truth(구성원 참)를 구분하지 못한다. 이 경로는 primary truth(주 판정 근거)가 아니다.

### 독립 XCLIP fixture — `PASS`

같은 종류의 통제 fixture를 `AcDbSpatialFilter`와 별도 선분/다각형 교차 판정으로 읽었다. `D:\runs\e2_program\native_display_oracle\fixture_20260807_123705\03_xclip_native\job_out.json`은 다음 결과를 남겼다.

| 대상 | expected | visible | clipped away | 보존식 |
|---|---:|---:|---:|---|
| `E2_DMM_VISIBLE` | 1 | 1 | 0 | `1 = 1 + 0` |
| `E2_DMM_CLIPPED` | 1 | 0 | 1 | `1 = 0 + 1` |

결과의 `host_mode`는 `full_autocad`, `oracle_method`는 `xclip_polygon_segment_intersection`, `native_membership_resolved`는 `true`였다. 이 개입은 DMM이 놓친 구분을 독립 native oracle이 실제로 만드는지 확인한 것이다.

## 구현한 관측 경로

### Native ObjectARX 판정

`src/Ariadne.AcadNative/families/e2_display_oracle.inc`에 experiment-only native oracle을 추가하고, `src/Ariadne.AcadNative/AriadneNativeJob.cpp`에 `e2.inspect.xclip_membership` 작업을 등록·디스패치했다.

- 블록 참조의 `ACAD_FILTER`/`SPATIAL` 사전에서 `AcDbSpatialFilter` 정의를 읽는다.
- 경계점, 반전 여부, 원래 블록 역변환을 읽어 월드 좌표 다각형으로 만든다.
- `LINE`과 직선 구간만 있는 `LWPOLYLINE`을 선분으로 바꾸고, 선분-다각형 교차 구간을 독립 계산한다.
- 블록 참조를 재귀적으로 따라가며 INSERT 변환, 레이어 표시, 엔티티 표시, XCLIP을 적용한다.
- 원본 정의 핸들, 원본 엔티티 핸들, INSERT lineage, XCLIP 핸들, subentity/fragment 순서를 출력해 안정적인 provenance를 보존한다.
- `expected = visible + clipped_away` 보존식이 깨지거나, 곡선 bulge·다중 셀 MINSERT·분할 fragment·순환 블록 등 v1 범위를 벗어나면 성공으로 포장하지 않고 닫힌 실패(`BLOCKED`)를 반환한다.

여기서 Python은 visibility를 결정하지 않는다. Python과 WorldIR 경로가 공유하는 것은 안정 ID 규약뿐이며, membership의 판단은 native ObjectARX 결과에 독립적으로 맡긴다.

### 전용 실행·해시 결속

`tools/cadctl.py`의 `Cad.inspect_display_membership`와 `tools/attended_lane.py`가 다음 경계를 구현했다.

- 원본 DWG를 `staged\input.dwg`로 복사하고 실행 전 원본·staging SHA-256을 비교한다.
- 현재 checkout의 `src\Ariadne.AcadNative\bin\x64\Release` ARX/DBX를 명시한다.
- `tools\attended\run_attended_job.ps1`를 통해 전용 disposable full `acad.exe` 인스턴스 하나만 실행한다.
- `accoreconsole` 또는 다른 headless fallback은 사용하지 않는다.
- 실행 후 원본 SHA-256을 다시 읽고, native outer/inner schema, lineage 연속성, ID 중복, 보존식을 검증한다.
- 검증된 결과만 `display_membership_binding.json`과 `target_population_oracle.json`으로 기록한다.

`tools/cadagent_mcp.py`에는 이 경계를 넘지 않는 `cad.inspect_display_membership` MCP 도구를 추가했다. MCP는 인자를 검증·전달하고, staging·해시·전용 full AutoCAD·no-headless gate는 `cadctl`이 소유한다.

### 모델 입력 모집단

`tools/e2/build_display_model_input.py`는 source-scoped native graph를 WorldIR로 확장하고 XCLIP metadata를 보존한 뒤, 요청한 W1/W2의 보이는 선분만 `display_model_input.json`으로 쓴다. 이 스크립트는 native truth를 새로 결정하지 않는다. `tools/e2/experiment_guard.py`가 독립 native oracle과 WorldIR·모델 입력의 수와 안정 ID를 대조해 불일치가 있으면 `BLOCKED`로 닫는다.

## 개입시험과 코드 검증

통제된 개입은 네 가지였다.

1. XCLIP 경계 안의 선과 경계 밖의 선을 같은 fixture에 넣어 DMM 콜백의 비분별성을 드러냈다.
2. 같은 fixture를 native spatial-filter/선분 교차 경로에 넣어 visible 1, clipped 0의 구분과 보존식을 확인했다.
3. attended runner가 optional PowerShell bookkeeping envelope를 늦게 남기는 `degraded=true` 조건을 주입했다. 경로는 inner payload를 꾸미지 않고 정확한 `attended\job_out.json`을 읽어 결과를 검증했다.
4. headless runner를 호출하면 테스트가 즉시 실패하도록 하고, 잘못된 source identity·비 native host·불완전 lineage도 닫힌 실패로 확인했다.

현재 checkout의 변경된 집중 테스트를 실행한 결과는 **55개 통과, 1개 skip, 0개 실패**다. skip은 `tests/unit/test_attended_lane.py:638`의 실제 CAD live smoke이며 `CADOS_LIVE!=1` 때문에 실행하지 않았다. `git diff --check`도 exit code 0이었다.

저장소 전체 단위 테스트는 Windows 사용자 임시경로의 대소문자 차이를 제거하기 위해 새 `D:\tmp` basetemp를 지정해 재실행했고, **2,099개 통과, 30개 skip, 0개 실패**였다. 첫 전체 실행에서 나온 2개 실패는 `C:\Users\PAUL`과 `C:\Users\paul`을 문자열로 비교한 기존 환경 의존 실패였으며, 같은 코드에 대소문자가 안정적인 basetemp만 지정하자 둘 다 통과했다.

실행한 테스트 묶음은 다음과 같다.

- `tests/unit/test_e2_native_display_oracle_source.py`
- `tests/unit/test_e2_display_membership_route.py`
- `tests/unit/test_build_display_model_input.py`
- `tests/unit/test_attended_lane.py`
- `tests/unit/test_mcp_tool_contract.py`

## 실제 L0 도면 결과

실험의 읽기 전용 입력은 `D:\runs\e2_program\l0_gold_1dwg\l0_gold.dwg`이고, 보존 원본은 `D:\assets\CODEX_E2_WALL_WORLD_MODEL_SOURCE_V1.dwg`다. 두 파일은 현재 같은 SHA-256이며, 실험 입력의 실행 전후 SHA-256도 다음 값으로 같았다.

`14eb65eb292d8a07f38ab5662dcafe9761c6185bc5ff0c8a9a008be15b598961`

native 결과는 `D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\attended\job_out.json`에 있고, 작업은 `e2.inspect.xclip_membership`이었다. `display_membership_receipt.json`과 `target_population_oracle.json`은 모두 `PASS`이며, native 결과의 측정 단위는 `source_segment_instance`다.

| target layer | native source entity templates | expected source segments | native visible | clipped away | 모델 입력 선분 |
|---|---:|---:|---:|---:|---:|
| `X-평면도(기본형)$0$W1` | 1618 | 6094 | 145 | 5949 | 145 |
| `X-평면도(기본형)$0$W2` | 1000 | 3742 | 96 | 3646 | 96 |
| **총계** | **2618** | **9836** | **241** | **9595** | **241** |

각 행과 총계에서 `expected = visible + clipped_away`가 성립한다. native 결과에는 camera extent를 적용하지 않았고, layer/entity visibility는 적용했다. `dwf_dmm_used_for_membership`는 `false`다.

## 세 집합 동일성

세 집합은 다음이다.

1. `target_population_oracle.json`의 native visible stable IDs
2. `model_input\display_worldir_probe.json`의 WorldIR `placed_uid`
3. `model_input\display_model_input.json`의 모델 입력 `placed_uid`

최종 guard `D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\display_population_guard_terminal.json`의 target population 비교는 다음을 기록했다.

| layer | native | WorldIR visible | WorldIR emitted | model input | native→WorldIR 누락 | WorldIR→native 추가 | model 누락 | model 추가 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| W1 | 145 | 145 | 145 | 145 | 0 | 0 | 0 | 0 |
| W2 | 96 | 96 | 96 | 96 | 0 | 0 | 0 | 0 |
| **총계** | **241** | **241** | **241** | **241** | **0** | **0** | **0** | **0** |

별도의 read-only set 비교도 세 집합 각각 241개 고유 ID와 pairwise 차집합 0을 반환했다. 따라서 모델 입력은 native 표시 모집단에서 임의로 추가·삭제된 별도 모집단이 아니다.

## 원본 안전성과 전용 인스턴스 증거

`display_membership_binding.json`은 다음을 결속한다.

- source: `D:\runs\e2_program\l0_gold_1dwg\l0_gold.dwg`
- source SHA-256: 위 64자리 값
- staged copy: `D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\staged\input.dwg`
- staged pre-execution SHA-256: source와 동일
- native job output SHA-256: `60242169837fd4750c6c366eb4ce29dbfab952a28eb521a2fc9e4ffd49d647b4`
- `execution_context`: `dedicated_full_autocad`
- `headless_fallback`: `false`

`attended\stdout.txt`에는 기존 acad PID에 붙지 않고 전용 PID `44716`을 시작했으며, `job_out.json`을 읽은 뒤 `hasExited=True`, `timedOut=False`로 종료했다고 남아 있다. `stderr.txt`는 비어 있다. `security_before.txt`와 `security_after.txt`도 다음 두 줄이 동일하다.

```text
0
D:\dev\99_tools\autocad-sdk-router\prebuilt\2027
```

receipt의 `degraded=true`는 이 native 측정의 실패가 아니다. 실행 후 optional PowerShell bookkeeping envelope가 늦어 exact envelope를 즉시 조립하지 못한 상태를 뜻한다. 경로는 그 때문에 결과를 발명하지 않고 실제 `attended\job_out.json`을 다시 읽었고, 원본 해시 전후, security before/after, 전용 프로세스 종료, source/native artifact hash 증거가 모두 남아 있다. 이 degraded bookkeeping을 숨겨진 성공 실패로 바꾸지 않는다.

## 과학적 의미

이번 결과가 닫은 것은 “실험에 넣을 도면 선분의 모집단이 무엇인가”라는 관측 계약이다. 이제 모든 model arm이 W1 145개와 W2 96개, 총 241개의 동일한 XCLIP-visible 선분 인스턴스를 받아야 한다.

이번 결과가 말하지 않는 것은 다음과 같다.

- detector가 선분을 올바르게 찾았다는 것
- 모델의 precision, recall, AUPRC 또는 다른 성능 수치
- W1/W2라는 레이어 라벨 자체가 탐지 성과라는 것
- DWF/DMM이 native membership truth를 제공한다는 것

즉, 이 결과는 관측기와 입력 모집단의 자격을 증명한 것이며 탐지기·모델 성능은 아직 실행하지 않은 상태다. 성능 실험은 `PASS_WITH_DEFERRAL`로 남긴다.

## 한계와 다음 실험

Native oracle v1은 `LINE`과 직선 구간 `LWPOLYLINE`만 지원한다. 곡선 bulge, 다중 셀 MINSERT 배열, 한 선분을 여러 fragment로 나누는 경우, 순환 block graph는 보수적으로 거부한다. 이번 L0 도면에서는 이 제한에 걸린 evidence가 없었지만, 다른 도면에 자동 일반화할 수 있다는 뜻은 아니다.

재현은 전용 full AutoCAD 인스턴스에서만 해야 한다. 원본 DWG는 계속 read-only로 두고, 매번 새 staging/output 디렉터리를 사용한다. headless fallback을 추가하면 이 qualification의 근거가 바뀌므로 허용하지 않는다.

다음 실험은 먼저 이 보고서의 241개 canonical population을 입력으로 고정한 뒤 detector/model 실행과 성능 측정을 별도 receipt로 남기는 것이다. 그 실행이 실제로 일어나기 전에는 성능 PASS를 주장하지 않는다.

## 재현 명령

아래 명령은 기록 commit 당시의 역사적 실행 절차다. 현재 runbook이 아니며,
legacy oracle 형식과 고정된 로컬 증거 경로를 포함하므로 그대로 실행해서
현행 자격이나 성능을 주장해서는 안 된다.

### 집중 테스트

```powershell
Set-Location -LiteralPath 'D:\runs\wt\autocad-sdk-router__e2-qualification'
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\PAUL\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 -m pytest -q -p no:cacheprovider `
  tests/unit/test_e2_native_display_oracle_source.py `
  tests/unit/test_e2_display_membership_route.py `
  tests/unit/test_build_display_model_input.py `
  tests/unit/test_attended_lane.py `
  tests/unit/test_mcp_tool_contract.py
```

관찰된 결과: `55 passed, 1 skipped`; skip 이유는 `CADOS_LIVE!=1`이다.

### 전용 full AutoCAD native membership

```powershell
Set-Location -LiteralPath 'D:\runs\wt\autocad-sdk-router__e2-qualification'
& .\tools\build_native_acad.ps1 -RouterHome (Get-Location).Path
$script = @'
import json
import sys
sys.path.insert(0, r'D:\runs\wt\autocad-sdk-router__e2-qualification\tools')
import cadagent_mcp

request = {
    'jsonrpc': '2.0',
    'id': 1,
    'method': 'tools/call',
    'params': {
        'name': 'cad.inspect_display_membership',
        'arguments': {
            'dwg': r'D:\runs\e2_program\l0_gold_1dwg\l0_gold.dwg',
            'target_layers': [
                'X-평면도(기본형)$0$W1',
                'X-평면도(기본형)$0$W2',
            ],
            'out': r'D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807_repro',
            'timeout': 300,
        },
    },
}
print(cadagent_mcp.handle_rpc(request))
'@
$script | & 'C:\Users\PAUL\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 -
```

이 명령은 `tools/attended/run_attended_job.ps1`를 통해 전용 `acad.exe`를 띄운다. `D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807_repro`가 이미 있으면 다른 새 디렉터리로 바꾼다.

### WorldIR 모델 입력 모집단

```powershell
Set-Location -LiteralPath 'D:\runs\wt\autocad-sdk-router__e2-qualification'
& 'C:\Users\PAUL\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 tools/e2/build_display_model_input.py `
  --scoped-native-graph 'D:\runs\e2_program\l0_gold_1dwg\terra_fix\scoped_native_graph.json' `
  --source-dwg 'D:\runs\e2_program\l0_gold_1dwg\l0_gold.dwg' `
  --target-layer 'X-평면도(기본형)$0$W1' `
  --target-layer 'X-평면도(기본형)$0$W2' `
  --out-dir 'D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807_repro\model_input'
```

### 최종 guarded qualification

```powershell
Set-Location -LiteralPath 'D:\runs\wt\autocad-sdk-router__e2-qualification'
& 'C:\Users\PAUL\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 tools/e2/run_guarded_experiment.py `
  --candidate auto `
  --require nested_insert_world_segments `
  --require world_lineage `
  --require source_document_identity `
  --require native_display_membership `
  --require model_input_membership `
  --probe-ir 'D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\model_input\display_worldir_probe.json' `
  --source-drawing 'D:\runs\e2_program\l0_gold_1dwg\l0_gold.dwg' `
  --target-population-oracle 'D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\target_population_oracle.json' `
  --model-input-ir 'D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\model_input\display_model_input.json' `
  --receipt-output 'D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807_repro\display_population_guard_terminal.json' `
  -- 'C:\Users\PAUL\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 -c "print('DISPLAY_POPULATION_QUALIFIED')"
```

이 guard 명령은 detector/model을 실행하지 않는다. source/probe identity, native target oracle, WorldIR, model input의 동일성만 검사하고, 위와 같은 실험 qualification 명령을 실행한다.

## 아티팩트

구현·테스트:

- `D:\runs\wt\autocad-sdk-router__e2-qualification\src\Ariadne.AcadNative\AriadneNativeJob.cpp`
- `D:\runs\wt\autocad-sdk-router__e2-qualification\src\Ariadne.AcadNative\families\e2_display_oracle.inc`
- `D:\runs\wt\autocad-sdk-router__e2-qualification\tools\cadctl.py`
- `D:\runs\wt\autocad-sdk-router__e2-qualification\tools\cadagent_mcp.py`
- `D:\runs\wt\autocad-sdk-router__e2-qualification\tools\attended_lane.py`
- `D:\runs\wt\autocad-sdk-router__e2-qualification\tools\e2\build_display_model_input.py`
- `D:\runs\wt\autocad-sdk-router__e2-qualification\tests\unit\test_e2_native_display_oracle_source.py`
- `D:\runs\wt\autocad-sdk-router__e2-qualification\tests\unit\test_e2_display_membership_route.py`
- `D:\runs\wt\autocad-sdk-router__e2-qualification\tests\unit\test_build_display_model_input.py`

통제 fixture:

- `D:\runs\e2_program\native_display_oracle\fixture_20260807_123705\02_dmm\job_out.json`
- `D:\runs\e2_program\native_display_oracle\fixture_20260807_123705\03_xclip_native\job_out.json`

실제 L0 native evidence:

- `D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\display_membership_receipt.json`
- `D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\target_population_oracle.json`
- `D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\display_membership_binding.json`
- `D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\attended\job_out.json`
- `D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\attended\security_before.txt`
- `D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\attended\security_after.txt`
- `D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\attended\stdout.txt`
- `D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\attended\stderr.txt`

모델 입력과 최종 guard:

- `D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\model_input\display_model_input_receipt.json`
- `D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\model_input\display_model_input.json`
- `D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\model_input\display_worldir_probe.json`
- `D:\runs\e2_program\native_display_oracle\l0_native_v3_20260807\display_population_guard_terminal.json`

이 기록이 주장하는 범위는 `PASS`인 native 표시 구성원·모델 입력 결속, `PASS_WITH_DEFERRAL`인 detector/model 성능 측정, `RETRACTED`인 DWF/DMM membership 가설이다. 이 문서 자체를 별도의 `PASS`로 판정하지 않는다.
