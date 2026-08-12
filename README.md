# CAD OS

CAD OS는 AI 에이전트와 스크립트가 AutoCAD 작업을 하나의 통제된 경로로
실행하도록 연결하는 Windows용 제어 계층입니다. 원본 CAD 파일은 읽기 전용이며,
변경은 staging 사본이나 새 출력에만 적용합니다.

## 안전 계약

- 원본 DWG, DXF, 3DM, GH, RVT 파일은 수정하지 않습니다.
- 실행은 MCP, `cadctl` 또는 라우터의 검증된 진입점을 거칩니다.
- 구현되지 않았거나 증명되지 않은 상태는 `BLOCKED` 또는 `UNKNOWN` 그대로 반환합니다.
- 과거 보고서의 파일명, 날짜 또는 `PASS` 판정만으로 현재 상태를 주장하지 않습니다.

## 설치

필수 조건은 Windows, AutoCAD, Python, Git입니다. 현재 저장소가 함께 제공하고
증명하는 native bundle은 AutoCAD 2027용입니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

설치기는 선택한 Python 환경에 의존성을 설치하고 MCP 등록용 JSON을 출력합니다.
prebuilt 파일이 존재하거나 라우트 탐지가 성공했다는 사실만으로 설치 전체가 검증된
것은 아닙니다.

## 사용 인터페이스

| 목적 | 진입점 |
|---|---|
| AI 에이전트 | `python tools\cadagent_mcp.py --serve` |
| 셸과 자동화 | `python tools\cadctl_cli.py ...` |
| CAD·파일 형식 라우팅 | `powershell tools\autocad-router.ps1 ...` |

도구와 연산의 실제 목록은 MCP `tools/list`와 operation-registry 검증 영수증에서
조회합니다. README에는 쉽게 바뀌는 개수를 고정해 적지 않습니다.

## 현재 상태 확인

```powershell
python -B .\tools\cadctl_cli.py status --schema-version 2
python -B .\tools\cadctl_cli.py status --schema-version 2 `
  --expected-revision <외부에서 받은 40자 커밋 SHA>
```

`expected-revision`은 CI, 릴리스 또는 검토자가 제공해야 합니다. 현재 checkout에서
읽은 HEAD를 그 checkout 자체의 증명으로 사용하지 않습니다. 최상위 `PASS`는 상태
문서를 정상적으로 조립했다는 뜻일 뿐입니다. 실제 판단은 다음 항목을 따로 봅니다.

- `anchor`: 어떤 Git revision과 checkout 상태에 결박됐는가
- `capability`: 어떤 MCP 도구와 CAD 연산을 선언·구현하는가
- `proof`: 그 선언을 어떤 소스·배포 바이트로 증명했는가
- `runtime_observation`: 특정 머신과 시점에서 무엇을 실제로 관측했는가
- `historical_snapshot`: 과거 기록이며 현재 상태로 승격되지 않는 증거

등록된 MCP에서는 같은 인자로 `cad.status`를 호출합니다. CLI만 실행하면 MCP
프로세스가 실제로 선언한 도구와 dispatch 함수를 볼 수 없으므로, MCP surface가
`UNKNOWN` 또는 `BLOCKED`인 것이 정상입니다.

실시간 라우트 탐지는 별도 명령으로 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\autocad-router.ps1 -Action status
```

이 결과는 해당 머신과 시점의 관측입니다. 전체 준비 상태나 특정 revision에 결박된
증명은 아닙니다.

기존 사용자는 인자 없이 `cad.status` 또는 `cadctl status`를 호출하면 호환용 v1
형식을 받습니다. 이 형식의 라우트 정보는 `historical_unbound`로 표시되며 현재
revision의 증명으로 사용할 수 없습니다. 새 자동화는 schema version 2를 사용합니다.

## 저장소 지도

- `config/`: operation registry와 정책의 정본
- `tools/`: MCP, CLI, 라우터, 검증기
- `src/`: native·managed 구현
- `prebuilt/2027/`: 배포 binary와 무결성 manifest
- `schemas/`: 교환 형식
- `tests/`: 자동 검증
- `docs/`: 설계와 상세 계약
- `reports/`: 과거 증거와 호환성 출력. 파일명의 `latest`를 현재 사실로 해석하지 않습니다.

## 상세 문서

- [현재 상태 용어와 경계](docs/CURRENT_STATUS_MODEL.md)
- [MCP 계약](docs/MCP_TOOL_CONTRACT.md)
- [operation registry 명세](docs/OPERATION_REGISTRY_SPEC.md)
- [native ObjectARX·ObjectDBX 설계](docs/NATIVE_ARX_DBX_DESIGN.md)
- [라우터 안전 계약](reports/AUTO_CAD_ROUTER_AGENT_CONTRACT.md)
- [라이선스](LICENSE)
