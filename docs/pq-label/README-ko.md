# PQ Label 1.9.1 — AutoCAD 2027

DWG 객체에 Rhino Attribute User Text 호환 XData로 `CLASS_ID`를 기록하고, 클래스 기준으로
선택·선택 해제·표시·숨김을 수행하는 플러그인입니다.

## 설치

1. `PqLabel.bundle` 폴더 전체를 아래 위치로 복사합니다.
   `%APPDATA%\Autodesk\ApplicationPlugins\PqLabel.bundle`
2. AutoCAD를 다시 시작합니다.
3. 명령창에 `PQHELP`를 입력합니다.

플러그인은 AutoCAD 시작 중에는 DLL을 로드하지 않습니다. `PQPALETTE`,
`PQHELP` 등 `PQ...` 명령을 처음 실행할 때 지연 로드됩니다.

일반 작업은 `PQPALETTE`를 입력해 도킹 가능한 관리 창을 여는 것이 가장
편합니다.

간단히 시험할 때는 `NETLOAD`를 실행하고
`Contents\Windows\PqLabel.dll`을 직접 선택해도 됩니다. AutoCAD가 DLL을
차단하면 파일 속성의 **차단 해제**를 적용하거나 설치 폴더를
`TRUSTEDPATHS`에 추가해야 할 수 있습니다.

## 명령

| 명령 | 기능 |
| --- | --- |
| `PQPALETTE` | class 관리 창 열기 |
| `PQSETCLASS` | 선택 객체에 class 지정 |
| `PQSETCLASSKIND` | 기존 class 전체에 `THING` 또는 `STUFF` 종류 지정 |
| `PQUNSETCLASS` | 선택 객체의 class 해제 |
| `PQSETINSTANCE` | 입력한 INSTANCE_ID를 선택 객체 전체에 지정 |
| `PQNEWINSTANCE` | UUID 하나를 생성해 선택 객체 전체에 지정 |
| `PQUNSETINSTANCE` | 선택 객체의 INSTANCE_ID 해제 |
| `PQSELECTCLASS` | 입력한 class의 현재 공간 객체만 선택 |
| `PQDESELECTCLASS` | 현재 선택에서 입력한 class만 제외 |
| `PQSHOWCLASS` | nested 경로를 포함해 입력한 class만 표시 |
| `PQHIDECLASS` | nested 경로를 포함해 입력한 class 숨김 |
| `PQSHOWALL` | 객체 격리/숨김 모두 해제 |
| `PQSYNCCLASS` | nested/상위 블록의 계산 class 캐시 재생성 |
| `PQINFO` | 객체의 직접 저장 class와 계산된 유효 class 확인 |
| `PQINFONESTED` | 찍은 nested 엔티티와 상위 컨테이너별 XData 확인 |
| `PQAUDITCLASS` | class의 직접 XData를 엔티티 타입별로 집계 |
| `PQVALIDATE` | raw XData 형식과 class/instance 의미 무결성 검증 |
| `PQMIGRATERHINO` | 기존 `COMPANY_PQ` XData를 Rhino 호환 User Text XData로 변환 |
| `PQHELP` | 명령 목록 표시 |

## PQ Label 창

- 상단에서 `CLASS_ID`, `CLASS_KIND`, `INSTANCE_ID`를 직접 입력할 수 있습니다.
- `CLASS_KIND`는 `THING` 또는 `STUFF`입니다. 기존 도면은 class를 선택하고
  `종류 저장`을 누르면 해당 class의 authored label 전체에 일괄 기록됩니다.
- `ID 지정 시 UUID 자동 생성`은 기본 체크 상태입니다. 체크된 상태에서
  `ID 지정`을 누르면 새 UUID를 만들어 입력란에 표시하고 선택 객체에
  지정합니다. 체크를 해제하면 입력란의 값을 사용하며, 입력란이 비어 있으면
  instance를 생성하지 않고 경고창을 표시합니다.
- `Class 지정(DEF)`, `Class 해제`, `Nested 정보`, `ID 지정`, `ID 해제`,
  `선택`, `선택 해제`, `동기화`, `무결성 검증`, `새로고침`, `표시`, `숨김`, `전체 표시`
  버튼으로 명령을 실행할 수 있습니다.
- 목록은 현재 Model/Layout 공간의 class와 `Objects`, `Instances`, `Blocks`, `Entities`
  개수를 보여줍니다.
- homogeneous BlockReference 하나는 명시적 ID가 없어도 implicit instance 1개로
  계산합니다. 독립 엔티티는 `INSTANCE_ID`가 있을 때만 instance로 계산하며,
  여러 엔티티에 같은 ID를 지정하면 하나의 instance가 됩니다. STUFF에는
  `INSTANCE_ID`를 지정할 수 없으며 Objects에만 포함되고 Instances에는 포함되지 않습니다.
- 팔레트에서 class/instance 지정·해제 또는 동기화 명령이 정상 완료되면
  목록과 개수를 자동으로 새로고침합니다. 수동 `새로고침` 버튼도 유지합니다.
- 팔레트가 열린 상태에서 다른 DWG를 열거나 활성 도면을 전환하면 목록을
  자동으로 다시 계산합니다.
- 목록 집계는 최상위 객체에서 끝나지 않고 실제 BlockReference 배치 경로를
  따라 nested definition을 재귀 순회합니다. mixed/incomplete 외부 블록도
  내부의 class는 목록과 개수에 포함됩니다.
- homogeneous nested 블록은 하나의 semantic instance로 접어서 계산하고,
  공유 definition은 실제로 배치된 BlockReference 경로마다 각각 계산합니다.
- 순환 참조나 로드되지 않은 Xref처럼 순회할 수 없는 항목은 상태 영역의
  `미해결 경로` 개수로 표시합니다.

### 입력 및 버튼 기능

| UI | 실행 명령 | 기능 | 적용 범위 및 주의사항 |
| --- | --- | --- | --- |
| `CLASS_ID` 입력란 | — | 지정·조회할 class 값을 입력하거나 목록에서 선택 | 예: `DOOR.SINGLEHINGED` |
| `CLASS_KIND` 선택 | — | class를 `THING` 또는 `STUFF`로 정의 | thing만 instance 검증 대상 |
| `INSTANCE_ID` 입력란 | — | UUID 자동 생성 체크를 해제했을 때 사용할 instance ID 입력 | 빈 ID로 instance를 만들 수 없음 |
| `ID 지정 시 UUID 자동 생성` | — | 체크 시 `ID 지정`을 누를 때마다 새 UUID 생성 | 기본 체크 상태이며 생성된 UUID를 입력란에도 표시 |
| `Class 지정(DEF)` | `PQSETCLASS` | 선택 객체에 class와 kind 지정 | 기존 class가 있으면 개수와 충돌 수를 경고하고 `Yes` 확인 후 덮어씀. `INSTANCE_ID`는 보존 |
| `종류 저장` | `PQSETCLASSKIND` | 입력 class의 기존 authored 레코드 전체에 선택한 kind 기록 | 기존 1.7 이하 도면의 kind 보완용 |
| `Class 해제` | `PQUNSETCLASS` | 선택 객체의 class 제거 | 블록 선택 시 해당 공유 definition 내부까지 재귀 적용. `INSTANCE_ID`는 보존 |
| `Nested 정보` | `PQINFONESTED` | 정확히 찍은 nested 엔티티와 모든 상위 container의 저장·유효 class 및 instance ID 출력 | 조회 전용이며 DWG를 변경하지 않음 |
| `ID 지정` | `PQSETINSTANCE` | 선택 객체들에 동일한 instance ID 지정 | 선택에 STUFF가 하나라도 포함되면 전체 작업 거부. BlockReference에서는 해당 배치에만 기록 |
| `ID 해제` | `PQUNSETINSTANCE` | 선택 객체의 `INSTANCE_ID` 제거 | `CLASS_ID`는 보존 |
| `선택` | `PQSELECTCLASS` | 현재 공간의 일치 객체로 선택 세트를 교체 | 일반 선택은 최상위 객체 기준. mixed 블록 내부 일부 엔티티는 직접 선택하지 않음 |
| `선택 해제` | `PQDESELECTCLASS` | 현재 선택 세트에서 입력 class와 일치하는 객체만 제외 | 선택되지 않은 객체에는 영향 없음 |
| `동기화` | `PQSYNCCLASS` | 하위 class를 다시 판정하여 homogeneous 상위 BlockReference의 derived class 캐시 갱신 | authored leaf label은 변경하지 않으며 mixed/incomplete 부모의 derived 캐시는 제거 |
| `무결성 검증` | `PQVALIDATE` | raw XData 형식과 instance/class 규칙 검사 | 현재 공간 문제 객체를 자동 선택하고 definition 문제는 BTR 경로로 출력 |
| `새로고침` | — | class 목록과 Objects·Instances·Blocks·Entities 수를 다시 계산 | 조회 전용. class/instance 지정·해제 후에는 자동 새로고침도 수행됨 |
| `표시` | `PQSHOWCLASS` | 입력 class만 보이도록 nested 경로까지 격리 | 비영구 graphics filter이며 XData·레이어·객체 `Visible` 값을 변경하지 않음 |
| `숨김` | `PQHIDECLASS` | 입력 class를 nested 경로까지 숨김 | 비영구 graphics filter. 공유 definition 엔티티의 표시 결과는 모든 배치에 적용될 수 있음 |
| `전체 표시` | `PQSHOWALL` | PQ nested 표시 필터와 AutoCAD 객체 격리 상태 해제 | visibility override 초기화 기능이며 XData label은 삭제하지 않음 |

class 목록의 행을 클릭하면 해당 값이 `CLASS_ID` 입력란으로 복사됩니다. 행을
더블클릭하면 그 class에 대해 `선택`을 실행합니다.

`PQSHOWCLASS`로 격리할 때는 각 nested 블록 하위에 대상 class가 하나라도
있는지 재귀 판정합니다. 대상이 전혀 없는 unlabelled/mixed 하위 블록은
BlockReference 자체를 숨깁니다. 따라서 AutoCAD가 하위 엔티티 overrule을
건너뛰고 캐시된 블록 그래픽을 그리더라도 무관한 블록이 새어 나오지 않습니다.

`PQSETCLASS`와 `PQUNSETCLASS`는 먼저 객체를 선택한 다음 명령을 실행해도
되고, 명령 실행 후 객체를 선택해도 됩니다. class 값은 공백 없는 식별자를
권장합니다. 예: `CHAIR`, `FURNITURE.CHAIR`, `WALL_FINISH`.

## 블록 판정 규칙

- 일반 엔티티는 자기 자신에 `CLASS_ID`를 저장합니다.
- 블록 참조의 class 원본은 여전히 하위 객체로부터 계산합니다. 다만 최상위
  DWG나 외부 도구에서도 바로 읽을 수 있도록 homogeneous BlockReference에는
  계산 결과를 `CLASS_ID`와 `CLASS_SOURCE=DERIVED`로 함께 캐시합니다.
- 블록을 지정하면 공유 Block Definition의 최하위 엔티티에 class를 씁니다.
  따라서 같은 정의를 쓰는 모든 블록 참조에 함께 적용됩니다.
- 즉, 블록 편집기로 들어갈 필요 없이 BlockReference를 선택하고
  `PQSETCLASS` 또는 `Class 지정(DEF)`을 실행하면 모든 nested definition의
  최하위 엔티티가 같은 class로 재귀 변경됩니다.
- 블록의 모든 최하위 엔티티가 라벨되어 있고 class가 하나로 같을 때만 그
  블록을 해당 class의 한 객체로 간주합니다.
- 서로 다른 class가 섞였거나 라벨 없는 하위 객체가 있는 블록은
  `mixed/incomplete`로 보고, 블록 전체를 선택하거나 숨기지 않으며 기존
  derived 캐시도 제거합니다.
- 예전 방식으로 BlockReference 자체에 저장된 class는 읽을 수 있지만,
  새 class를 지정/해제할 때 직접 라벨을 제거하고 하위 엔티티 규칙으로
  정규화합니다.
- `PQSETCLASS`와 `PQUNSETCLASS`는 상위 캐시를 자동 갱신합니다. 이전 버전으로
  라벨링한 DWG는 `PQSYNCCLASS` 또는 창의 `동기화` 버튼을 한 번 실행하십시오.

## XData 형식

Registered Application 이름은 `Rhino`이며, 각 문자열 key/value 쌍을 별도의
`{ ... }` 그룹으로 저장합니다. 이는 Rhino 8이 DWG Attribute User Text를
내보낼 때 사용하는 형식과 같습니다. 기존 `COMPANY_PQ` 레코드도 계속 읽을
수 있고, 수정 시 자동 변환됩니다. 도면 전체를 한 번에 변환하려면
`PQMIGRATERHINO`를 사용합니다. 기존 Rhino User Text의 다른 key는 보존됩니다.

```text
1001  Rhino
1002  {
1000  SCHEMA
1000  1.1
1002  }
1002  {
1000  CLASS_ID
1000  DOOR.SINGLEHINGED
1002  }
1002  {
1000  CLASS_KIND
1000  THING
1002  }
1002  {
1000  INSTANCE_ID
1000  550e8400-e29b-41d4-a716-446655440000
1002  }
```

Rhino에서 같은 엔티티를 선택하면 Attribute User Text에는 다음처럼 표시됩니다.

| Key | Value |
| --- | --- |
| `SCHEMA` | `1.0` |
| `CLASS_ID` | `DOOR.SINGLEHINGED` |
| `CLASS_KIND` | `THING` |
| `INSTANCE_ID` | `550e8400-e29b-41d4-a716-446655440000` |

class를 해제해도 동일 앱 안의 `INSTANCE_ID` 및 알 수 없는 추가 필드는
보존합니다.

## INSTANCE_ID 규칙

- `PQSETINSTANCE`: 직접 입력한 ID 하나를 선택된 객체 모두에 기록합니다.
- `PQNEWINSTANCE`: UUID 하나를 자동 생성해 선택된 객체 모두에 기록합니다.
- BlockReference에 지정한 ID는 그 참조 한 개에만 속하며 Block Definition이나
  동일 정의의 다른 참조로 전파되지 않습니다.
- 여러 primitive를 하나의 thing으로 묶고 싶다면 함께 선택하여 같은 ID를
  지정합니다.
- STUFF에는 `INSTANCE_ID`를 지정하면 안 됩니다. STUFF가 선택에 포함되면
  `PQSETINSTANCE`와 `PQNEWINSTANCE`는 아무 객체도 변경하지 않고 전체 작업을 거부합니다.
- 기존 ID가 있는 객체를 STUFF로 지정하거나 class 종류를 STUFF로 변경하는 작업도
  거부됩니다. 먼저 `PQUNSETINSTANCE`로 ID를 제거해야 합니다.

## 검증 규칙

`PQVALIDATE` 또는 팔레트의 `무결성 검증` 버튼은 다음 두 단계를 독립적으로
검사합니다.

1. 물리 XData 검사: 호스트 DWG의 모든 non-Xref BlockTableRecord 엔티티를 한 번씩 검사
2. 의미 검사: 현재 Model/Layout 공간을 실제 nested 배치 경로대로 검사

물리 검사 항목:

- Rhino XData의 `{ key, value }` 괄호와 문자열 개수
- 동일 객체의 중복 key와 서로 다른 값을 가진 충돌 key
- 동일 객체에 여러 `CLASS_ID`가 저장된 상태
- Rhino와 legacy `COMPANY_PQ` 사이의 값 충돌
- 누락·구버전 `SCHEMA`, 빈 `CLASS_ID` 또는 `INSTANCE_ID`
- `CLASS_KIND`의 누락 및 `THING`/`STUFF` 이외 값
- class 없이 존재하는 kind/source/instance
- 일반 엔티티에 잘못 기록된 `CLASS_SOURCE=DERIVED`
- instance ID를 가진 stuff (`ERROR`)

의미 검사 항목:

- homogeneous BlockReference는 별도 ID가 없어도 implicit thing instance로 인정합니다.
- mixed/incomplete 경로의 standalone `THING` leaf는 `INSTANCE_ID`가 없으면
  `MISSING_INSTANCE`입니다.
- 동일 occurrence scope에서 하나의 `INSTANCE_ID`가 두 개 이상의 class에 사용되면
  `MULTI_CLASS_INSTANCE`입니다.
- `CLASS_KIND`가 없거나 같은 homogeneous class 내부에서 일치하지 않으면
  `UNKNOWN_CLASS_KIND`입니다. 이 경우 thing 여부를 모르므로 instance 누락 판정을
  신뢰할 수 없습니다.
- 문제가 발견되면 해당 경로를 포함한 최상위 객체가 자동 선택됩니다.
- block definition에만 존재해 직접 선택할 수 없는 문제는
  `BTR:<블록 이름>/<엔티티 handle>` 경로로 명령창에 출력됩니다.
- 구조·충돌 문제와 STUFF의 instance ID는 `ERROR`, 구 schema·legacy 잔존 등은
  `WARNING`으로 구분합니다.

## 현재 범위와 주의점

- AutoCAD 2027 64-bit / .NET 10용 빌드입니다.
- Xref 내부 객체는 호스트 DWG에서 읽기 전용이므로 지정/해제에서 건너뜁니다.
  원본 Xref DWG를 열어 라벨링해야 합니다.
- XCLIP은 표시 경계일 뿐 분류 단위를 바꾸지 않습니다. Xref 또는 블록의
  판정 규칙은 그대로 적용됩니다.
- class/instance 목록은 현재 공간에서 시작해 nested 경로까지 조회합니다.
  다만 `PQSELECTCLASS`/`PQDESELECTCLASS`의 일반 선택 세트는 최상위 객체만
  포함하며 mixed 블록 내부의 일부 객체는 선택하지 않습니다.
- `PQSHOWCLASS`/`PQHIDECLASS`는 mixed 블록 내부에도 적용되는 비영구
  graphics filter를 사용합니다. 복구는 `PQSHOWALL`을 사용합니다.
- homogeneous 블록이 대상이면 BlockReference 전체를 표시/숨김 처리합니다.
  mixed/incomplete 블록은 부모를 유지한 채 nested definition으로 내려가
  class가 일치하는 하위 블록·엔티티만 처리합니다.
- graphics filter는 DWG의 `Visible` 속성이나 레이어를 변경하지 않으며 저장
  데이터에도 기록되지 않습니다. 공유 Definition의 하위 객체를 숨기면 그
  Definition이 사용된 모든 BlockReference 배치에 동일하게 보입니다.

## 표시 오류 진단

`PQSHOWALL` 실행 후 `PQINFONESTED`로 의심되는 형상을 정확히 찍습니다.

- picked entity의 `Stored CLASS_ID`가 대상 class이면 실제 라벨 오염입니다.
- picked entity는 비어 있지만 Container에 대상 class가 있으면 상위 블록
  판정 때문에 함께 처리된 것입니다.
- picked entity와 모든 Container가 대상 class가 아니라면 graphics filter의
  표시 문제입니다.

`PQAUDITCLASS`에 class를 입력하면 해당 class가 실제 저장된 LINE, HATCH,
INSERT 등의 개수도 확인할 수 있습니다.

소스는 번들의 `Source` 폴더에 포함되어 있습니다.
