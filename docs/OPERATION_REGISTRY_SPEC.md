# 연산 레지스트리 계약

연산 레지스트리는 CADAgent가 이름을 붙여 공개하는 CAD 작업의 정본입니다.
현재 개수나 구현 비율은 이 문서에 적지 않습니다. 값은 항상 검증 명령의 영수증에서
읽습니다.

## 정본 파일

- `config/operations.v2.json`: 공개 연산, 상태, 호스트, 쓰기 수준, 스키마 참조
- `schemas/operation_registry.v2.schema.json`: 레지스트리 문서 형식
- `config/policy.v2.json`: 읽기·스테이징 쓰기·원본 쓰기 정책
- `config/autocad_native_arx_operation_catalog.json`: 네이티브 SDK 카탈로그
- `src/Ariadne.AcadNative/AriadneNativeJob.cpp`: 공개·내부 네이티브 연산 표
- `tools/patch_ops/`: 구조화된 쓰기 작업의 Python 어댑터

파생 파일인 `config/op_dag.json`은 위 정본에서 다시 만들 수 있습니다. 정본과 다르면
검증이 실패해야 하며, 파생 파일을 근거로 정본을 고치지 않습니다.

## 공개 연산과 내부 연산

공개 연산은 `operations.v2.json`에 레코드가 있고 정책·호스트·입출력 계약을 가집니다.
`cad.run_operation`은 이 공개 목록에 있는 식별자만 받습니다.

진단이나 실험 전용 네이티브 연산은 별도 내부 표에 둡니다. 내부 연산은 일반 MCP·CLI
경로에서 실행할 수 없습니다. 실행 문맥은 다음처럼 분리합니다.

- 일반 네이티브 작업: 공개 연산만 허용
- 진단 작업: 공개 연산과 명시된 진단용 내부 연산만 허용
- 읽기 전용 E2 작업: 지정된 E2 관측 연산만 허용

요청 인자의 `operation` 필드는 예약 필드입니다. 외부 인자가 이미 허용된 연산 이름을
내부 연산 이름으로 덮어쓸 수 없습니다.

## 상태의 뜻

레지스트리 레코드의 상태는 실행 결과가 아니라 제품 선언입니다.

- `implemented`: 구현 소스와 공개 연결 정보가 등록됨
- `wired`: 호출 경로는 있으나 구현 증거가 더 필요함
- `stub`: 이름과 계약만 있고 구현은 없음
- `catalogued`: SDK 카탈로그에는 있으나 공개 실행 경로는 없음
- `blocked`: 현재 정책이나 호스트 조건에서 실행 금지
- `deprecated`: 더 이상 새 호출에 사용하지 않음
- `not_implemented`: 주소는 있으나 실행 구현이 없음

`implemented`는 이 문서나 정적 검증만으로 “지금 이 머신에서 성공한다”는 뜻이
아닙니다. 실제 성공 주장은 정확한 바이너리와 호스트에서 얻은 별도 런타임 영수증이
필요합니다.

## 검증기가 증명하는 것

`tools/verification/operation_registry.py`는 대상 Python이나 C++를 import·실행하지
않습니다. 한 번 캡처한 입력 바이트로 다음 정적 사실을 비교합니다.

- 레지스트리가 JSON Schema에 맞는지
- 연산 식별자가 중복되지 않는지
- 합계와 상태별 집계가 실제 레코드와 같은지
- v1 고정 표면이 제거되거나 바뀌지 않았는지
- 공개·내부 네이티브 연산 어휘가 겹치지 않는지
- 각 가족 모듈의 네이티브 연산 식별자가 정확히 한 가족에만 속하는지
- 공개 네이티브 연산 표와 가족 모듈이 같은 식별자를 중복 소유하지 않는지
- 가족이 유일하게 소유한 연산의 레지스트리 `dispatcher_symbol`이 그 가족이
  선언한 정적 dispatch 함수 이름과 같은지
- 네이티브 표·가족 게이트·Python patch map에 등장하는 연산 어휘가 레지스트리와
  분류상 모순되지 않는지

파생 DAG와 정책 참조는 이 영수증의 범위가 아닙니다. 각각 전용 생성기·계약
테스트가 현재 레지스트리와의 일치를 별도로 검사합니다.

성공 영수증의 범위는
`static_operation_vocabulary_parity`입니다. 다음은 증명하지 않습니다.

- 실제 디스패치 대상 함수의 신원
- 핸들러가 실행되는지 여부
- 핸들러의 의미적 성공
- C++ 컴파일 또는 AutoCAD 호스트 실행

따라서 이 검증의 `VERIFIED`를 런타임 `PASS`로 승격하면 안 됩니다. 현재 상태 문서는
이 범위와 한계를 능력 항목 바로 옆에 함께 표시합니다.

## 실행 전 게이트

연산을 실행할 때는 레지스트리 선언만 보지 않고 다음을 별도로 확인합니다.

1. 요청한 연산이 공개 목록에 있는가
2. 연산 상태가 실행 가능한가
3. 요청한 호스트가 `host_eligibility`에 있는가
4. 쓰기 수준이 정책에 맞는가
5. 원본 CAD 파일이 아니라 승인된 스테이징 사본인가
6. 요청·결과가 지정된 스키마에 맞는가
7. 사용 중인 네이티브 배포물이 현재 소스와 결속됐는가

하나라도 알 수 없으면 `UNKNOWN`, 계약에 맞지 않으면 `BLOCKED`로 남깁니다.

## 안전 규칙

- 원본 DWG·DXF·3DM·GH·RVT는 읽기 전용입니다.
- 변경 작업은 기본적으로 스테이징 사본에서만 수행합니다.
- `write_original`은 별도 명시 승인 없이는 허용하지 않습니다.
- 임의 명령 문자열 대신 등록된 연산 식별자만 실행합니다.
- 파일명이 `latest`라는 이유로 과거 보고서를 현재 증거로 사용하지 않습니다.
- 정적 선언, 빌드 무결성, 런타임 관측은 서로 대신할 수 없습니다.

## 확인 명령

현재 레지스트리 영수증:

```powershell
python -c "from pathlib import Path; from tools.verification.operation_registry import verify_operation_registry; import json; print(json.dumps(verify_operation_registry(Path('.')).to_dict(), ensure_ascii=False, indent=2))"
```

현재 상태의 분리된 투영:

```powershell
python tools/cadctl_cli.py status --schema-version 2
```

정확한 revision에 결속하려면 독립적으로 정한 전체 커밋 SHA를 함께 전달합니다.

```powershell
python tools/cadctl_cli.py status --schema-version 2 --expected-revision <40자리-커밋-SHA>
```

두 명령 모두 AutoCAD를 시작하거나 라이브 가용성 프로브를 실행하지 않습니다.
