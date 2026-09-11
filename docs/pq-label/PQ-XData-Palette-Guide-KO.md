# PQ XData 및 PQPALETTE 기능 가이드

대상 버전: PQ Label 1.9.1 / AutoCAD 2027 / Rhino 8 호환

## 1. XData class label 예시

PQ Label은 Rhino의 DWG Attribute User Text 교환 규칙에 맞춰 Registered
Application 이름을 `Rhino`로 사용합니다. 각 key/value는 독립된 중괄호
그룹으로 저장합니다.

다음은 `CLASS_ID=DOOR.SINGLEHINGED`와 하나의 `INSTANCE_ID`가 지정된 엔티티의
DXF 표현입니다.

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

Rhino Attribute User Text에서는 다음 dictionary로 보입니다.

| Key | Value | 의미 |
| --- | --- | --- |
| `SCHEMA` | `1.0` | PQ label 스키마 버전 |
| `CLASS_ID` | `DOOR.SINGLEHINGED` | 객체의 class label |
| `CLASS_KIND` | `THING` | instance 검증에 사용하는 thing/stuff 구분 |
| `INSTANCE_ID` | `550e8400-e29b-41d4-a716-446655440000` | 여러 primitive를 하나의 instance로 묶는 선택적 ID |

STUFF에는 `INSTANCE_ID`를 기록하면 안 됩니다. BlockReference 자체가 암묵적
THING instance인 경우에는 `INSTANCE_ID` 그룹을 생략할 수 있습니다.

homogeneous 상위 BlockReference에 계산 결과를 캐시할 때는 다음 그룹이
추가됩니다. 이는 사용자가 직접 붙인 원본 label이 아니라 하위 객체에서
계산된 값임을 나타냅니다.

```text
1002  {
1000  CLASS_SOURCE
1000  DERIVED
1002  }
```

## 2. PQPALETTE 입력 및 버튼 기능

AutoCAD 명령창에서 `PQPALETTE`를 실행하면 class·instance 관리 창이 열립니다.

| UI | 대응 명령 | 기능 | 적용 범위 및 주의사항 |
| --- | --- | --- | --- |
| `CLASS_ID` 입력란 | — | 지정·조회할 class 값을 입력하거나 목록에서 선택 | 예: `DOOR.SINGLEHINGED` |
| `INSTANCE_ID` 입력란 | — | UUID 자동 생성을 끈 경우 사용할 instance ID 입력 | 빈 ID는 허용하지 않음 |
| `ID 지정 시 UUID 자동 생성` | — | 체크 시 `ID 지정`을 누를 때마다 새 UUID 생성 | 기본 체크 상태. 생성값은 입력란에도 표시 |
| `Class 지정(DEF)` | `PQSETCLASS` | 선택 객체에 입력 class 지정 | 일반 엔티티에는 직접 기록. 블록 선택 시 공유 Block Definition의 최하위 엔티티까지 재귀 적용 |
| `Class 해제` | `PQUNSETCLASS` | 선택 객체의 class 제거 | 블록 선택 시 공유 definition 내부까지 적용. instance ID는 유지 |
| `Nested 정보` | `PQINFONESTED` | 찍은 nested 엔티티와 상위 container의 저장·유효 label 출력 | 조회 전용 |
| `ID 지정` | `PQSETINSTANCE` | 선택 객체 전체에 동일 instance ID 지정 | 체크 시 UUID 생성, 해제 시 입력값 사용. BlockReference의 해당 배치에만 기록 |
| `ID 해제` | `PQUNSETINSTANCE` | 선택 객체의 instance ID 제거 | class label은 유지 |
| `선택` | `PQSELECTCLASS` | 입력 class와 일치하는 현재 공간 객체로 선택 세트 교체 | 최상위 선택 기준이므로 mixed 블록 내부 일부는 직접 선택하지 않음 |
| `선택 해제` | `PQDESELECTCLASS` | 현재 선택에서 입력 class의 객체만 제외 | 다른 선택 객체는 유지 |
| `동기화` | `PQSYNCCLASS` | 하위 class 판정을 다시 수행해 상위 BlockReference의 derived 캐시 갱신 | leaf 원본 label은 변경하지 않음 |
| `새로고침` | — | class 목록과 Objects·Instances·Blocks·Entities 수 재계산 | 조회 전용. label 변경 뒤에는 자동으로도 실행됨 |
| `표시` | `PQSHOWCLASS` | 입력 class만 nested 경로까지 격리 표시 | 비영구 graphics filter. DWG 속성·레이어를 변경하지 않음 |
| `숨김` | `PQHIDECLASS` | 입력 class를 nested 경로까지 숨김 | 비영구 graphics filter |
| `전체 표시` | `PQSHOWALL` | PQ 표시 필터와 AutoCAD 객체 격리 상태 모두 해제 | visibility override 초기화이며 class·instance label은 유지 |

## 3. 목록 동작

| 항목 | 의미 |
| --- | --- |
| `Objects` | 해당 class로 판정된 semantic object 수 |
| `Instances` | BlockReference 또는 명시적 `INSTANCE_ID`의 고유 instance 수 |
| `Blocks` | 해당 class로 판정된 BlockReference instance 수 |
| `Entities` | 블록으로 접히지 않은 standalone entity 수 |

- class 행을 클릭하면 해당 값이 `CLASS_ID` 입력란에 복사됩니다.
- class 행을 더블클릭하면 해당 class의 `선택` 기능이 실행됩니다.
- homogeneous nested 블록은 semantic instance 하나로 접어서 계산합니다.
- mixed/incomplete 블록은 실제 배치 경로를 따라 내부 class를 재귀 집계합니다.
