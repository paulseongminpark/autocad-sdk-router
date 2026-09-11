# PQ Label MCP 통합

PQ Label의 라벨 규칙을 기존 CAD OS MCP의 `cad.run_operation`에서 실행합니다.
별도 MCP 서버나 레이어 검색기는 추가하지 않습니다. LLM이 기존 조회 도구와 PQ 연산을
조합하며, 연산 코드가 인자·THING/STUFF·덮어쓰기·공유 정의 규칙을 검사합니다.

## 사용 순서

1. `cad.inspect_drawing`으로 입력 도면을 추출합니다.
2. `cad.query_entities`에서 `SELECT handle FROM entities WHERE layer = 'A-WALL'` 등으로 대상을 찾습니다.
3. `cad.registry_explain`으로 PQ 연산의 `args_schema`, 범위, 쓰기 모드를 확인합니다.
4. `cad.run_operation`을 호출합니다. 예시 handle은 실제 조회 결과로 교체합니다.

```json
{
  "op_id": "pq_label.class.set",
  "dwg": "C:/work/input.dwg",
  "out": "C:/work/runs/label-wall",
  "args": {
    "handles": ["27A"],
    "class_id": "WALL",
    "class_kind": "STUFF",
    "overwrite": false,
    "allow_shared_definitions": false
  }
}
```

MCP 외부 envelope의 `ok`만으로 성공을 판단하지 않습니다. 내부 cadctl 결과의 `status`,
`execution_receipt.verification`, PQ 처리 결과를 확인합니다. 다음 변경·검증 요청의 `dwg`는
성공한 직전 작업의 `staged_result`를 사용합니다. 원본을 다시 넘기면 이전 변경이 이어지지 않습니다.
handle은 조회한 도면에 종속됩니다. 다른 도면의 handle이나 오래된 조회 결과를 재사용하지 않습니다.

## 연산

| 이름 | 필수 인자 | 범위 |
|---|---|---|
| `pq_label.inspect` | handles | 저장 라벨 및 유효 class/kind |
| `pq_label.inventory` | 없음 | 현재 공간의 클래스·객체·instance 집계 |
| `pq_label.class.set` | handles, class_id, class_kind | 블록 내부 재귀 적용 및 부모 캐시 동기화 |
| `pq_label.class.clear` | handles | 재귀 class 제거 및 동기화 |
| `pq_label.class.set_kind` | class_id, class_kind | 모든 host 정의에서 해당 class의 authored 기록 변경 |
| `pq_label.instance.set` | handles, instance_id | 전달한 객체/배치에 하나의 ID 적용, 정의 내부 재귀 없음 |
| `pq_label.instance.new` | handles | 하나의 UUID를 생성해 모든 대상에 공유 적용 |
| `pq_label.instance.clear` | handles | 대상의 instance 제거 |
| `pq_label.sync` | 없음 | host 블록 참조의 파생 class 동기화 |
| `pq_label.validate` | 없음 | 전체 host 물리 XData 검사 + 현재 공간의 occurrence 의미 검사 |
| `pq_label.migrate` | 없음 | legacy COMPANY_PQ를 Rhino XData로 변환하고 동기화 |

`class.set`은 기존 라벨이 하나라도 있으면 `overwrite=true` 없이는 거절합니다.
class set/clear가 블록 또는 블록 정의 내부 객체를 대상으로 하면 `allow_shared_definitions=true`가
필요합니다. 공유 정의를 쓰는 다른 배치에도 영향을 줍니다. 특정 배치만 바꾸는 옵션이 아닙니다.
STUFF에 instance 지정, instance가 남아 있는 대상을 STUFF로 변경하는 작업은 거절합니다.
읽기 전용/xref 대상은 거절하거나 기존 PQ 순회 규칙에 따라 건너뛰며 결과의 건너뜀 수를 확인해야 합니다.
instance 결과의 `unchanged_or_skipped`는 미변경과 수정 불가 대상을 함께 셉니다.

## 실행과 소스 구조

`cadagent_mcp.py → cadctl.py → autocad-router.ps1 → PQ_LABEL_JOB → 공통 PQ 처리 로직`

- `src/PqLabel/PqJob.cs`: 프롬프트 없는 구조화된 job 어댑터
- `src/PqLabel/PqOperations.cs`: 대화형 명령과 job이 공유하는 변경·순회 로직
- `PqXData`, `PqClassResolver`, `PqClassSynchronizer`, `PqValidation`: 기존 PQ 규칙 재사용
- `config/operations.v2.json`: 연산·인자·호스트·쓰기 정책
- `schemas/pq_label.*.schema.json`: 요청/결과 계약
- `prebuilt/2027/pq-label/router`: 소스 해시와 결속된 MCP용 DLL

AutoCAD 2027 Core Console에서 실행합니다. 조회는 read-only staging 파일로 열고,
변경은 `write_copy` staging 파일에 저장합니다. 기존 receipt가 원본 불변·실행 연산·저장 결과를 확인합니다.
PQ용 write_copy만 허용하도록 확장했으며 기존 다른 managed 연산의 차단 정책은 유지합니다.

팔레트, 화면 선택·숨김·isolation은 기존 대화형 플러그인에 남아 있습니다. 현재 라우터의
일회성 Core Console 작업은 종료 시 화면 상태를 잃으므로 이를 영속적인 live MCP 기능으로
노출하지 않습니다. 모든 layout의 occurrence를 한 번에 검증한다는 의미도 아닙니다.

## 빌드·설치·검증

MCP용 DLL을 다시 빌드하고 소스 결속 manifest를 갱신합니다.

```powershell
pwsh -NoProfile -File .\tools\build_pq_label.ps1
python -m pytest tests/unit/test_pq_label_contract.py -q
python tests/integration/pq_label_runtime.py
```

빌드는 AutoCAD 2027 managed assemblies와 Roslyn을 포함한 .NET 10 기반 PowerShell 7이 필요합니다.
.NET 10 SDK가 있으면 `dotnet build src/PqLabel/PqLabel.csproj -c Release`도 사용할 수 있지만,
라우터 배포 manifest 갱신은 위 빌드 스크립트로 수행합니다. DLL/source가 다르면 라우터가 거절합니다.
런타임 스크립트는 AutoCAD가 있는 Windows에서만 명시적으로 실행하며 `runs/`에 테스트 결과를 남깁니다.

사람용 기존 1.9.1 배포물은 원본 바이트로 보존합니다. 선택 설치:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -PqLabel
```

AutoCAD를 종료한 뒤 설치하고 staging 도면 사본에서 `PQPALETTE`를 사용합니다.
이 배포물은 새 MCP 어댑터 DLL과 별개이며 MCP는 이 설치에 의존하지 않습니다.
원본 프로젝트는 `labelling/PQ_Label`, import revision은
`e5ef5c5e0f34e64d108bb3d2a058fa4b53453a35`입니다.
사용자 설명은 [README-ko.md](README-ko.md), XData 규칙은
[PQ-XData-Palette-Guide-KO.md](PQ-XData-Palette-Guide-KO.md)를 참고하세요.
