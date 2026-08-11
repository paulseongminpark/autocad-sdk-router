# AutoCAD ObjectARX DMM `getGraphicIDs`의 2D DWF XCLIP 가시성 판정 적합성 연구

- 작성일: 2026-08-05
- 대상: AutoCAD ObjectARX 2027, DMM(Design Web Format Metadata) reactor, 2D DWF
- 목적: `AcDMMEntityReactorInfo::getGraphicIDs`를 XCLIP 이후 실제 출력 가시성 판정에 쓸 수 있는지 검증하고, 호출 측 API 오용과 SDK 계약의 한계 또는 결함 가능성을 분리한다.
- 상태: `PARTIAL_PASS` — 최소 재현 실험과 인과 개입으로 우리 측 오용 두 건은 교정했지만, `getGraphicIDs`의 2D 계약은 공개 근거만으로 확정할 수 없다.

## 1. 결론

현재 증거로는 `getGraphicIDs`를 **2D DWF에서 XCLIP 후 실제로 그려진 개체를 판별하는 공식 오라클로 사용할 수 없다.** 최소 fixture에서 보이는 선과 잘린 선 모두 DMM entity callback과 ObjectDefinition 메타데이터 노드를 만들었지만, 두 선 모두 `getGraphicIDs`는 비어 있었다. 반면 실제 W2D 그래픽에는 보이는 선만 존재했다.

우리 구현에는 두 가지 오용이 있었다. 원본 개체의 source layer 대신 `effectiveBlockLayerId`만 비교했고, Autodesk 공식 예제의 메타데이터 연결 순서인 `AddProperties → AddNodeToMap → AddPropertiesIds`를 빠뜨렸다. 두 문제를 각각 교정한 뒤에도 `getGraphicIDs` 결과는 바뀌지 않았다. 따라서 이번 빈 결과를 그 두 오용의 결과로 설명할 수는 없다.

그러나 이 결과만으로 Autodesk SDK 결함을 입증한 것도 아니다. 로컬 헤더에서 `getGraphicIDs`를 직접 설명하는 인접 문맥은 3D DWF publisher의 graphics key이며, Autodesk 공식 문서는 3D DWF에서 section clipping과 XClipping을 지원하지 않는다고 밝힌다. 가장 강한 현재 설명은 **2D plot pipeline에서 `getGraphicIDs`의 계약이 제한적이거나 불명확하며, 적어도 문서화된 XCLIP 후 가시성 API는 아니라는 것**이다.

### 결론 표

| 질문 | 판정 | 근거 | 실무 의미 |
|---|---|---|---|
| 우리 측 layer 판정이 잘못되었는가? | `CONFIRMED_AND_CORRECTED` | `effectiveBlockLayerId`만 비교하던 코드를 source layer까지 보도록 교정했다. | 기존 구현에는 실제 오용이 있었으나, 빈 `getGraphicIDs`의 원인은 아니었다. |
| Autodesk 공식 metadata recipe를 누락했는가? | `CONFIRMED_AND_CORRECTED` | `AddProperties → AddNodeToMap → AddPropertiesIds` 순서를 적용했고 property association failure는 0건이었다. | metadata 연결은 공식 예제와 맞췄지만 결과는 불변이었다. |
| `getGraphicIDs`가 2D XCLIP 후 가시성 오라클인가? | `NOT_SUPPORTED_BY_EVIDENCE` | 보이는 선과 잘린 선 모두 target callback은 있었으나 graphic ID는 0건이었다. 실제 W2D에는 보이는 선만 있었다. | 현재 구현의 visibility gate로 채택하면 안 된다. |
| ObjectARX SDK defect가 입증되었는가? | `NOT_PROVEN` | 세 arm의 결과가 같다는 사실은 재현성을 높이지만, 공개된 2D 계약과 기준 구현이 없다. | ADN에 계약과 기대 동작을 먼저 확인해야 한다. |
| 3D DWF로 우회할 수 있는가? | `INVALID_FALLBACK` | Autodesk 공식 제한 문서가 3D DWF의 section clipping 및 XClipping 미지원을 명시한다. | 같은 XCLIP 판정을 3D 경로로 검증하거나 대체할 수 없다. |
| 현재 가장 강한 설명은 무엇인가? | `CONTRACT_LIMITATION_OR_AMBIGUITY` | 관련 헤더의 graphics key 설명은 3D 문맥이고, 2D W2D 실측과 `getGraphicIDs`가 대응하지 않았다. | 문서화된 2D post-XCLIP 계약이 확인될 때까지 별도 가시성 오라클이 필요하다. |

## 2. 검증 질문과 판정 기준

핵심 질문은 다음과 같다.

> 2D DWF를 생성할 때 `getGraphicIDs`가 XCLIP 이후 실제 W2D 그래픽에 남은 drawables만 식별하는가?

이를 판정하려면 세 층이 서로 일치해야 한다.

1. DMM entity callback에서 대상 원본 개체를 정확히 식별해야 한다.
2. `getGraphicIDs`의 결과가 보이는 개체와 잘린 개체를 구분해야 한다.
3. 그 구분이 최종 W2D graphics의 실제 포함 여부와 일치해야 한다.

이번 실험은 1번과 최종 그래픽의 차이를 확인했지만, 2번 결과가 두 대상 모두 비어 있어 세 층을 잇지 못했다.

## 3. 최소 fixture

블록 내부에 서로 분리된 두 선을 두고, XCLIP 경계가 한 선만 포함하도록 구성했다.

| 역할 | handle | layer | 블록 좌표 | XCLIP 기대 |
|---|---:|---|---|---|
| visible line | `19194` | `E2_DMM_VISIBLE` | `(0,0)–(10,0)` | 포함, 출력되어야 함 |
| clipped line | `19195` | `E2_DMM_CLIPPED` | `(20,0)–(30,0)` | 제외, 출력되면 안 됨 |
| XCLIP | — | — | `[-1,-2]–[11,2]` | visible line만 포함 |

기하·수량 보존을 독립적으로 확인하는 WorldIR 검증은 `PASS`였다.

| 지표 | 값 |
|---|---:|
| expected | 3개 — frame 포함 |
| visible | 2개 |
| clipped | 1개 |
| emitted | 2개 |
| conservation delta | 0개 |

따라서 fixture 자체는 “보여야 하는 것 2개, 잘려야 하는 것 1개”를 손실 없이 구분했다. DMM 관찰 결과가 모호한 이유를 입력 기하의 불확실성이나 수량 유실로 돌릴 근거는 없다.

## 4. 세 실험 arm

같은 fixture와 출력 조건을 유지하고 DMM node 및 property 연결 방식만 바꿨다.

| arm | 개입 | 목적 |
|---|---|---|
| `set_current_node_only` | current node만 설정 | 최소 node 설정에서의 기준 결과 측정 |
| `set_current_node_with_properties` | current node와 properties 설정 | property 부여 자체가 graphic ID 제공에 영향을 주는지 측정 |
| `official_metadata` | `AddProperties → AddNodeToMap → AddPropertiesIds` | Autodesk 공식 예제와 같은 metadata association을 구성한 뒤 결과 측정 |

### 실측 결과

| arm | begin entity | 대상 callback | `getGraphicIDs`가 있는 대상 | 생성 node | properties | property association failure |
|---|---:|---:|---:|---:|---:|---:|
| `set_current_node_only` | 5 | 2 | 0 | 2 | 0 | 해당 없음 |
| `set_current_node_with_properties` | 5 | 2 | 0 | 2 | 2 | 해당 없음 |
| `official_metadata` | 5 | 2 | 0 | 2 | 2 | 0 |

두 target callback은 visible handle `19194`와 clipped handle `19195`에 각각 대응한다. 즉, DMM이 대상 개체를 보지 못한 것이 아니다. 세 arm 모두 두 개체의 callback과 node를 만들었지만 두 개체 모두 graphic ID를 받지 못했다.

## 5. 인과 개입: 오용을 고친 뒤 무엇이 변했는가

단순 상관이 아니라 원인 후보를 실제로 제거하는 방식으로 두 번 개입했다.

### 개입 A — source layer 식별 복구

기존 구현은 block 내부 source entity의 layer를 놓치고 `effectiveBlockLayerId`만 비교했다. 이 조건은 block reference의 유효 layer와 원본 선의 layer가 다를 때 대상 선을 잘못 분류할 수 있다. source layer를 함께 매칭하도록 교정해 두 target callback을 명시적으로 식별했다.

교정 뒤에도 visible과 clipped 대상 모두 `getGraphicIDs`가 0개였다. 따라서 layer 식별 오용은 **실재했고 교정되었지만**, 이번 빈 graphic ID 결과의 충분한 원인은 아니다.

### 개입 B — 공식 metadata recipe 복구

기존 구현은 Autodesk 공식 예제의 `AddProperties → AddNodeToMap → AddPropertiesIds` 연결 순서를 완성하지 않았다. `official_metadata` arm에서 이 순서를 그대로 적용했다. 그 결과 두 대상 모두 property가 생겼고, property association failure는 0건이었다.

그럼에도 `getGraphicIDs`가 있는 대상은 2개 중 0개로 유지됐다. 따라서 공식 metadata 연결 누락도 **실재했고 교정되었지만**, 빈 graphic ID 결과를 설명하지 못한다.

### 개입의 해석 경계

두 개입 후 관측값이 불변이라는 사실은 “이 두 오용 때문에 graphic ID가 비었다”는 가설을 반박한다. 반대로 “SDK에 결함이 있다”를 바로 증명하지는 않는다. 그 결론에는 2D DWF에서의 명시적 API 계약, Autodesk 기준 샘플의 기대 출력, 또는 Autodesk의 확인이 추가로 필요하다.

## 6. 최종 DWF 내부의 교차 증거

### ObjectDefinition 메타데이터

공식 arm의 DWF ObjectDefinition에는 두 대상이 모두 존재했다.

- node 1, visible: `Object`, `Instance`, `Properties` 생성
- node 2, clipped: `Object`, `Instance`, `Properties` 생성

이는 metadata 존재 여부만으로 실제 그려진 개체와 잘린 개체를 구분할 수 없음을 보여준다. DMM의 object graph는 두 source entity를 모두 표현했다.

### 썸네일과 실제 W2D graphics

렌더 결과에는 다음만 있었다.

- visible line: red
- frame: gray
- clipped line: green, 없음

즉 최종 그림은 XCLIP 기대와 일치했다. 최소 W2D graphics payload는 1,396 bytes였고, 현재의 제한된 관찰에서는 실제 graphics 쪽 `object-node 1` 연결만 확인됐다. 이는 visible node와 실제 drawable 사이의 연결 가능성을 지지하지만, 아직 일반 W2D parser로 검증한 결과는 아니다.

가장 중요한 불일치는 다음과 같다.

| 증거 층 | visible | clipped | 구분 가능 여부 |
|---|---|---|---|
| entity callback | 있음 | 있음 | 불가 |
| ObjectDefinition node/property | 있음 | 있음 | 불가 |
| `getGraphicIDs` | 없음 | 없음 | 불가 |
| 최종 W2D graphics | 있음 | 없음 | 가능 |

현재 데이터에서 post-XCLIP visibility의 truth는 `getGraphicIDs`가 아니라 최종 W2D graphics에 있다.

## 7. SDK 헤더 및 공식 자료와의 정합성

### ObjectARX 2027 로컬 헤더

`C:\ObjectARX 2027\inc\acdmmapi.h`에서 확인한 관련 구간은 다음과 같다.

| 줄 | 내용 |
|---:|---|
| 1106–1113 | node 사용에 관한 guidance |
| 1149–1163 | properties를 `EPlotObject`/`Instance`에 연결하는 설명 |
| 1185–1193 | `AddPropertiesIds` |
| 1246 | `AddNodeToMap` |
| 1248–1318 | 3D property/attribute 설명 직후 `getGraphicIDs` 선언 |

`C:\ObjectARX 2027\inc\Ac3dDwfNavTree.h`의 10–25행은 3D publisher의 graphics keys를 설명하고, 45–53행은 같은 형태인 `AcArray<long>` keys를 사용한다.

이 배치는 `getGraphicIDs`가 3D publisher의 graphics key 문맥과 관련될 가능성을 높인다. 다만 헤더의 인접 배치만으로 2D에서 지원하지 않는다고 단정할 수는 없다. 확정에 필요한 것은 Autodesk가 정의한 2D 계약이다.

### Autodesk 공식 metadata 예제

Autodesk 공식 게시물과 연결된 샘플은 다음 순서를 사용한다.

1. `AddProperties`
2. `AddNodeToMap`
3. `AddPropertiesIds`

- 게시물: <https://blog.autodesk.io/adding-metadata-to-dwf-sheets-with-acdmmreactor-in-autocad/>
- 샘플 코드: <https://github.com/MadhukarMoogala/inject-dwf-metadata/blob/main/main.cpp>

이번 `official_metadata` arm은 이 순서를 적용했고 association failure 0건을 기록했다. 따라서 공식 recipe를 지키지 않았다는 반론은 현재 재현 결과를 설명하지 못한다.

### 3D DWF 제한

Autodesk의 AutoCAD 2027 공식 문서는 3D DWF에서 section clipping과 XClipping이 지원되지 않는다고 명시한다.

- 문서: <https://help.autodesk.com/cloudhelp/2027/KOR/AutoCAD-Core/files/GUID-792617AA-2DB3-4870-A739-C9225A5889DD.htm>

따라서 3D graphics key 경로가 더 잘 문서화되어 있더라도, 이번 질문인 XCLIP 후 가시성을 3D DWF로 우회 검증하는 것은 유효한 대안이 아니다.

## 8. 가설별 판정

| 가설 | 판정 | 반증 또는 지지 증거 | 남은 조건 |
|---|---|---|---|
| H1. 대상 entity를 잘못 찾았기 때문에 ID가 비었다. | `REJECTED_FOR_THIS_REPRO` | source layer 교정 뒤 visible/clipped target callback 2개를 확인했으나 ID는 계속 0개였다. | 다른 fixture의 식별 정확성은 별도 문제다. |
| H2. 공식 metadata association을 누락했기 때문에 ID가 비었다. | `REJECTED_FOR_THIS_REPRO` | 공식 순서를 적용해 properties 2개, association failure 0건을 얻었으나 ID는 0개였다. | Autodesk가 추가적인 미문서 호출 순서를 요구하는지는 확인 필요다. |
| H3. `getGraphicIDs`가 2D XCLIP 후 살아남은 drawable만 돌려준다. | `NOT_SUPPORTED` | 최종 W2D는 visible만 포함했으나 visible과 clipped 모두 ID가 없었다. | Autodesk의 2D 기준 샘플 또는 명시적 계약이 필요하다. |
| H4. `getGraphicIDs`는 사실상 3D graphics key 중심 계약이다. | `PLAUSIBLE_NOT_PROVEN` | `acdmmapi.h` 인접 문맥과 `Ac3dDwfNavTree.h`가 3D graphics keys를 설명한다. | Autodesk의 API 소유 범위와 2D 동작 확인이 필요하다. |
| H5. ObjectARX SDK defect다. | `NOT_PROVEN` | 세 arm에서 재현되지만, 기대되는 2D 동작 자체가 공개 근거로 확정되지 않았다. | 지원 계약이 “2D에서 non-empty여야 한다”로 확인된 뒤에만 defect 여부를 판정할 수 있다. |
| H6. 최종 W2D object-node 연결로 가시성을 판정할 수 있다. | `PROMISING_PARTIAL_EVIDENCE` | 1,396-byte 최소 W2D에서 graphics 쪽 node 1 연결만 관찰됐고 화면 결과도 visible만 포함했다. | 일반 DWF Toolkit/WHIP parser로 다양한 opcode와 fixture를 검증해야 한다. |

## 9. 별도 SDK packaging/ABI 확인 사항

`AcDbSpatialFilter` convenience constructor는 헤더에 선언되어 있지만 `acdb26.lib`에서 대응 link symbol을 찾지 못했다. 재현 빌드는 default constructor를 사용한 뒤 `setDefinition`을 호출하는 방식으로 우회했다.

이 현상은 DMM `getGraphicIDs` 결과와 인과적으로 연결되지 않았다. 따라서 본문의 DMM 판정과 섞지 않고 **별도의 SDK packaging 또는 ABI clarification 후보**로 분류한다. 헤더 선언에 대응하는 import library 또는 올바른 link target이 따로 있는지 ADN에 확인한다.

## 10. 한계

1. 현재 W2D 해석은 1,396-byte 최소 payload에서의 제한된 관찰이다. DWF Toolkit 또는 WHIP 기반의 일반 parser가 아니므로 모든 W2D opcode, object-node scope, 중첩 상태를 처리한다고 주장할 수 없다.
2. fixture는 의도적으로 최소화한 단일 block/XCLIP 사례다. 여러 block reference, nested block, inverted clip, polygonal clip, viewport clip, plot style 차이는 아직 포함하지 않았다.
3. 실험은 `getGraphicIDs`의 반환 유무를 관찰했지만 Autodesk 내부 publisher state나 호출 시점별 population 규칙은 볼 수 없다.
4. 헤더의 인접 문맥은 계약 해석의 단서이지 공식적인 2D 비지원 선언이 아니다.
5. 3D DWF는 공식적으로 XClipping을 지원하지 않으므로 이번 2D 질문의 대조군이나 fallback으로 쓸 수 없다.
6. `AcDbSpatialFilter` link symbol 문제는 재현 빌드 중 발견한 별도 현상이며, DMM 결과의 원인이라고 볼 증거가 없다.

## 11. 다음 검증

### 우선 경로 — W2D graphics의 정식 해석

DWF Toolkit/WHIP 기반 parser로 `WT_Object_Node` ID와 실제 drawable opcode의 포함 관계를 추출한다. 목표는 다음 mapping을 일반적으로 생성하는 것이다.

```text
source entity / DMM node
        ↓
WT_Object_Node scope
        ↓
actual W2D drawables emitted inside that scope
```

이 mapping이 다양한 XCLIP fixture에서 안정적으로 성립하면 `getGraphicIDs` 대신 최종 산출물 기반의 2D visibility oracle로 사용할 수 있다.

### 백업 경로 — native offscreen GS differential

W2D parser의 적용 범위가 불충분하면 AutoCAD native offscreen Graphics System(GS) 렌더링을 사용해 “대상 entity 포함/제외” 영상 또는 픽셀 차이를 측정한다. 이는 DWF metadata 계약에 의존하지 않는 대신, 렌더 상태 통제와 허용 오차 정의가 추가로 필요하다.

## 12. Autodesk ADN에 보낼 정확한 질문

1. **AutoCAD 2027의 2D DWF plot pipeline에서 `AcDMMEntityReactorInfo::getGraphicIDs`가 지원되는 API입니까?** 지원된다면 반환되는 `AcArray<long>` 값의 정확한 의미와 값이 population되는 callback 시점 또는 선행 호출 조건을 알려 주십시오.
2. **2D DWF에서 XCLIP으로 완전히 제거된 source entity와 최종 W2D에 남은 source entity를 `getGraphicIDs`가 구분하도록 설계되어 있습니까?** 그렇다면 첨부한 최소 재현에서 두 entity 모두 빈 배열을 받는 것이 기대 동작인지 확인해 주십시오.
3. **`AddProperties → AddNodeToMap → AddPropertiesIds`를 성공적으로 수행하고 ObjectDefinition에 Object/Instance/Properties가 생성된 뒤에도, 최종 W2D에 존재하는 visible entity의 `getGraphicIDs`가 비어 있을 수 있습니까?** 가능하다면 metadata node와 실제 W2D drawable의 공식 매핑 API 또는 권장 판별법은 무엇입니까?
4. **`getGraphicIDs`가 3D DWF publisher의 graphics key에만 유효하거나 주로 그 경로를 위한 API입니까?** 그렇다면 `acdmmapi.h`에서 2D/3D 지원 범위를 명확히 구분한 문서나 2D 기준 샘플을 제공해 주십시오.
5. **ObjectARX 2027 헤더에 선언된 `AcDbSpatialFilter` convenience constructor의 symbol이 `acdb26.lib`에 없는 것이 의도된 packaging/ABI입니까?** default constructor와 `setDefinition` 조합이 권장 사용법인지, 아니면 추가로 link해야 할 공식 library가 있는지 알려 주십시오. 이 질문은 DMM 결과와 분리된 빌드 호환성 문의입니다.

## 13. ADN 첨부물 목록

### 최소 재현 및 계측 결과

- `D:\runs\e2_instrument_guard\20260805_dmm_api_repro_v1\diagnosis_summary.json`
- 위 디렉터리 아래 세 arm의 child run JSONs
  - `set_current_node_only`
  - `set_current_node_with_properties`
  - `official_metadata`
- native build 및 재현 산출물: `D:\runs\e2_instrument_guard\20260805_native_display_oracle_build_v11`

### SDK 계약 근거

- `C:\ObjectARX 2027\inc\acdmmapi.h` — 특히 1106–1113, 1149–1163, 1185–1193, 1246, 1248–1318행
- `C:\ObjectARX 2027\inc\Ac3dDwfNavTree.h` — 특히 10–25, 45–53행
- Autodesk 공식 metadata 게시물: <https://blog.autodesk.io/adding-metadata-to-dwf-sheets-with-acdmmreactor-in-autocad/>
- 공식 게시물의 연결 샘플: <https://github.com/MadhukarMoogala/inject-dwf-metadata/blob/main/main.cpp>
- Autodesk 3D DWF 제한 문서: <https://help.autodesk.com/cloudhelp/2027/KOR/AutoCAD-Core/files/GUID-792617AA-2DB3-4870-A739-C9225A5889DD.htm>

### ADN이 재현할 때 확인할 핵심 기대값

- callback: visible과 clipped 대상 모두 관찰됨
- ObjectDefinition: node 1 visible과 node 2 clipped 모두 Object/Instance/Properties 존재
- rendered/W2D result: visible red line과 gray frame만 존재, clipped green line은 없음
- observed `getGraphicIDs`: visible 0개, clipped 0개
- 확인을 요청하는 계약: 위 관찰이 2D DWF에서 정상인지, 아니면 visible entity에 non-empty graphics key가 있어야 하는지

## 14. 최종 분류

- `API_MISUSE`: **CONFIRMED_AND_CORRECTED**
- `SDK_DEFECT`: **NOT_PROVEN**
- 가장 강한 현재 설명: **2D DWF에서 `getGraphicIDs` 계약의 제한 또는 불명확성**
- 금지할 결론: “빈 `getGraphicIDs`가 곧 Autodesk SDK bug다.”
- 현재 권장: ADN으로 2D 계약을 확인하는 동안 DWF Toolkit/WHIP W2D parser를 우선 검증하고, 필요하면 native offscreen GS differential을 백업 오라클로 사용한다.
