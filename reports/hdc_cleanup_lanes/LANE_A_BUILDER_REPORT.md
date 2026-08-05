# HDC builder lane — IR→DXF 재생성기 이식 보고

**STATUS: PASS_WITH_DEFERRAL** — 이슈 9건(#49 #51 #53 #54 #55 #56 #58 #59 #60)의 결함 행동을 막는 회귀 테스트 32개 전부 GREEN, 기존 베이스라인 대비 신규 실패 0. 실도면(HDC 267장) 재검증은 도면이 이 머신에 없어 이연.

- 워크트리: `D:/runs/wt/autocad-sdk-router__hdc-builder` (브랜치 `fix/hdc-builder-port`)
- 만든 것: `tools/build_from_ir.py`(신규 1,078행) · `tests/unit/test_build_from_ir.py`(신규 554행, 테스트 32개)
- ezdxf 1.4.3 / Python 3.12 / Windows

---

## 1. 확정한 공개 API와 지원 kind

```python
build_dxf_from_ir(ir: dict, out_path=None, *,
                  inline_block_dims: bool = False,
                  dxfversion: str = DEFAULT_DXFVERSION) -> (ezdxf.document.Drawing, BuildReport)
```

- `out_path`가 없으면 파일을 쓰지 않고 `Drawing`만 돌려준다(인메모리 소비자용).
- `BuildReport`는 카운터 3개다. `added`(생성한 kind + `table:*` 같은 빌드 이벤트), `skipped`(재현하지 못한 것, 키가 `"<대상>:<사유>"`), `errors`(삼킨 예외, 키가 `"<대상>:<예외형>:<메시지>"`). `total_added`는 `SUPPORTED_KINDS`에 든 키만 합산해 이벤트 이중계산을 막는다.
- **침묵 금지**: 미인식 kind는 `skipped["<kind>:unrecognized_kind"]`, 구조적 불가는 사유별 키(`region:acis_binary_not_in_ir` 등), 해치 경계의 미인식 edge type은 `skipped["hatch_edge:<type>"]`로 반드시 계수된다(#55 TODO 요구).
- 지원 kind 22종(`SUPPORTED_KINDS`, `_HANDLERS`에서 파생해 표류 불가): line, arc, circle, ellipse, lwpolyline, polyline, point, text, mtext, attribute, block_reference, spline, hatch, mpolygon, solid, trace, face3d, wipeout, leader, ray, xline, dimension.
- 재현 불가로 계수만 하는 kind: ACIS 계열(solid3d/region/surface/nurbsurface/body), ole2frame, rasterimage/image, viewport, mline, polygon_mesh, poly_face_mesh, proxy, unsupported.
- CLI: `python tools/build_from_ir.py <ir.json> <out.dxf> [--inline-block-dims]` → 리포트를 JSON으로 출력.

### #51 반영 (기본값 설계)

블록 내부 치수 인라인은 **기본 OFF**다. 기본 경로는 `*D` 익명 블록 정의를 그대로 만들고, DIMENSION 엔티티를 생성해 `dxf.geometry`가 그 `*D`를 가리키게 한다(고아화·purge 연쇄 차단). `inline_block_dims=True`는 반대 트레이드를 선택해 `*D`의 def_entities를 제자리에 전개한다. rc53 자동 재빌드 루프(빌드→변환→실패 시 인라인 재빌드)는 드라이버 층 몫이며 모듈 docstring에 규약으로만 명시했다 — 이 함수는 순수 빌더로 외부 프로세스를 부르지 않는다.

---

## 2. 베이스라인

착수 직후(`python -m pytest tests/unit -q`):

```
1989 passed, 30 skipped in 48.27s
```

종료 시점(같은 명령):

```
2021 passed, 30 skipped in 43.47s
```

신규 테스트 32개(2021−1989) 전부 통과, **신규 실패 0**, skip 증가 0. (두 실행 모두 끝에 pytest의 Windows 임시폴더 정리 `PermissionError`가 찍히지만 테스트 실패가 아니라 atexit 훅 잡음이며 베이스라인에도 동일하게 있다.)

---

## 3. 이슈별 구현 위치 · RED 증거 · GREEN 증거

RED는 "수리 전(순진한) 구현"에 회귀 테스트를 먼저 걸어 얻은 실제 실패 출력이다. 세 파동으로 나눠 각 파동마다 RED → 수리 → GREEN → 커밋했다.

| 이슈 | 구현 위치 | RED 증거 (수리 전 실제 출력) | GREEN 증거 |
|---|---|---|---|
| **#49** WIPEOUT layer | `tools/build_from_ir.py:650` `_h_wipeout` / 사후설정 `:662` | `test_wipeout_keeps_its_original_layer`: `AssertionError: '0' != 'PV-MASK'` | 2/2 통과. 재로드 후 layer=`PV-MASK`, 마스킹 사각형 WCS 4점이 원본과 일치 |
| **#51** 블록내부 치수 인라인 | `:737` `_h_dimension` (인라인 분기 `:744`, `*D` 링크 `:767`) | 해당 없음(신규 설계 — 결함 재현 대상이 아니라 기본값 결정) | 2/2 통과. 기본 OFF에서 `*D1` 정의 보존 + FRAME 블록 내용이 `['DIMENSION']` + `dxf.geometry=='*D1'`, ON에서 `['LINE','LINE']` + `added['dim_inlined']==1` |
| **#53** 주기 스플라인 knot | `:603` `_h_spline` (3단 분기 `:609`–`:637`) | `test_periodic_spline_gets_a_valid_dxf_knot_vector`: `AssertionError: 0 not greater than 0` / `0 != 8` (재로드 스플라인의 knot 0개 = rc53 유발 상태) | 3/3 통과. periodic은 `set_closed`로 knots 15 = ncp 11 + degree 3 + 1, 표준 knot은 무변형 통과, 불일치는 open-uniform 합성(`spline_knots_synthesized`) |
| **#54** dimstyle prune 대소문자 | `:352` `_build_dim_styles` (casefold 가드 `:383`) | `test_referenced_uppercase_standard_survives`: `AssertionError: 2.5 != 3.75` (설정한 STANDARD 레코드가 삭제되고 ezdxf가 기본값으로 재생성) | 2/2 통과. `STANDARD`의 DIMTXT 3.75 보존, `table:prune_dimstyle_std` 미발동 |
| **#55** hatch ellipse_arc | `:783` `_edge_ellipse` · dispatch `:841` · 미인식 카운터 `:862` | `test_ellipse_arc_loop_is_not_dropped`: `AssertionError: 0 != 1` (해치 전량 폐기) / `test_unrecognized_edge_type_is_counted`: `AssertionError: 0 != 1` | 6/6 통과. major 벡터 길이 5000.0 = major_radius, ratio 0.4 = minor/major, 두 dialect 동일 결과, 미인식 edge는 `hatch_edge:helix_edge_from_the_future`로 계수 |
| **#56** 3DFACE | `:689` `_h_face3d` | `test_face3d_is_created_with_z_preserved`: `AssertionError: 0 != 1` / `IndexError: list index out of range` (분기 없음 → 전량 손실) | 2/2 통과. `invisible_edges == 2\|8 == 10`, Z 30.0/−0.0002 보존, 함정 확인용 `dxf.invisible == 0` 동시 단정 |
| **#58** shape 파일 STYLE 레코드 | `:307` `_build_text_styles` (`is_shape_file` 분기 `:324`) | `test_text_style_font_is_not_corrupted_by_a_shape_record`: `AssertionError: 'SYMBOL' != 'arial.ttf'` / `find_shx("SYMBOL")` → `unexpectedly None` | 2/2 통과. `Standard` 폰트 arial.ttf 유지, SYMBOL·ltypeshp.shx 두 shape 레코드 복원(`table:shape_file==2`) |
| **#59** LEADER + LWPOLYLINE elevation | `:702` `_h_leader` · `:467` `_h_lwpolyline`(elevation `:481`–`:489`) | `test_leader_stays_a_leader`: `AssertionError: 0 != 1` (LEADER 0개, POLYLINE으로 강등) / `test_lwpolyline_elevation_...`: `AssertionError: 0 != 2000000.020962` | 4/4 통과. LEADER 1개·POLYLINE 0개, `has_arrowhead`/`path_type`(0·1) 보존, elevation 2000000.020962와 −0.023448 복원 |
| **#60** DEFPOINTS 케이싱 | `:198` `_build_layers` (recase `:225`–`:235`, casefold prune `:258`) | `test_layer_table_keeps_the_original_casing`: `AssertionError: 7 != 3` (레코드가 파괴되고 속성 없이 재생성) + `errors == {"layer:DXFTableEntryError:LAYER '0' already exists!": 1}` | 2/2 통과. 레이어 테이블에 `DEFPOINTS`(대문자)만, color 3 보존, `table:layer_recased==1`, POINT가 `DEFPOINTS`에 배치 |

추가로 왕복 셀프테스트(BUNDLE 5)와 API 계약 테스트 7개: `test_roundtrip_kind_counts_match_the_ir`(make_fixture_ir → 빌드 → DXF 재로드 → DXF 타입별 개수가 IR과 정확히 일치, skipped 0), `test_out_path_writes_a_readable_dxf`, `test_unrebuildable_kind_is_counted_with_a_reason`, `test_unknown_kind_is_counted_not_dropped`, `test_symbol_tables_are_rebuilt`, `test_supported_kinds_cover_the_defect_issues`, `test_returns_drawing_and_report`.

---

## 4. 커밋

| 해시 | 내용 |
|---|---|
| `34f1593` | builder: IR->DXF regenerator core + symbol-table casing fixes (#51 #54 #58 #60) |
| `f234356` | builder: WIPEOUT layer, periodic spline knots, 3DFACE, LEADER identity (#49 #53 #56 #59) |
| `c70a183` | builder: hatch ellipse_arc edges + unrecognized-edge counter (#55) |
| `f7f089a` | builder: BuildReport.total_added counts entities, not build events |

세 파동 커밋은 각각 커밋 시점에 전체 신규 테스트가 GREEN인 상태다(RED 상태는 커밋하지 않았다). 커밋 메시지의 `Co-Authored-By`는 패킷이 지정한 문구를 그대로 썼다.

`REPORT.md`(이 파일)는 CHANGE_ONLY 목록에 없어 커밋하지 않았다. 작업트리에는 `reports/autocad_router_status_latest.json`의 수정이 하나 남아 있는데 내가 만든 것이 아니라 세션 훅/MCP 상태 기록이며 PROTECTED_PATHS라 손대지 않았다.

---

## 5. 이슈 스니펫과 IR 스키마의 불일치 — 해소 방식 (BLOCKED 0건)

구현 불가로 막힌 항목은 없다. 다만 이슈 스니펫의 필드명이 IR 스키마(`tools/ir_builder.py`)와 다른 지점이 다섯 있어, 전부 **스키마 쪽 이름을 정본으로** 삼아 해소했다. 기록해 둔다.

1. **#58의 `font`** → IR 텍스트 스타일 레코드의 실제 필드는 `font_file`(`schemas/dwg_graph_ir.v1.schema.json` `$defs/text_style_record`). `font_file`로 구현.
2. **#55의 `radius_ratio`** → 해치 edge IR에 그 키는 없다(이슈 본문도 같은 지적). `minor_radius/major_radius`로 유도하고, `ratio`(다른 dialect)가 오면 그것을 우선한다.
3. **해치 edge type 문자열이 이 repo에 두 dialect로 존재**한다 — `ellipse_arc` + 단위 `major_axis` + `major_radius`/`minor_radius` + `counterclockwise` (SoT 테스트 `tests/unit/test_ir_builder.py:706`)와, `ellipse` + 전길이 `major` + `ratio` + `ccw` (`src/Ariadne.AcadNative/AriadneNativeJob.cpp:1260`, #46/#41 WCS-degree emit). 빌더는 둘 다 받아 한 곳에서 정규화한다(`_edge_ellipse`). #55 TODO "edge type 규약 고정"에 대한 실측 근거다.
4. **#54의 가드 `DIM_STYLE_REF != "Standard"`** → `DIM_STYLE_REF`가 상수 `"Standard"`이면 이 절이 항상 False가 되어 prune이 죽은 코드가 된다. 빌더는 참조 dimstyle을 IR의 첫 dim_styles 이름에서 유도해(`_build_dim_styles` 말미) 가드가 실제로 동작하게 했고, casefold 비교는 이슈대로 적용했다.
5. **WIPEOUT 경계의 좌표계** → IR은 ObjectARX `clipBoundary()`를 그대로 실어 이미지 평면 2D(y 반전, 좌상단 원점)로 온다. WCS 복원식은 ezdxf `ImageBase.boundary_path_wcs`를 실측해 그대로 따랐다: `insert + u*0.5 − v*0.5 + u*x + v*(height − y)`. 실측 확인: 원본 사각형 (10,20)-(40,35)이 왕복 후 동일 4점으로 복귀(`test_masking_area_returns_to_the_original_wcs_rectangle`).

---

## 6. 검증하지 않은 것 (이연·범위 밖)

- **HDC 267장·옥포 16장 실도면 재검증**: 도면이 이 머신에 없어 불가. 이슈 본문의 실측 수치(PASS 36→182, `hatch_no_boundary` 20→0, 보존율 99.9893% 등)는 협업자 머신의 캠페인 결과를 인용한 것이고, 이 레인이 재현한 것은 **메커니즘과 그 방지**뿐이다. 실도면 판정은 이연.
- **DXF→DWG 변환(accoreconsole)·rc53 재현**: 실행하지 않았다. #53/#54의 rc53은 "knot 0개 스플라인이 만들어지는가", "참조되는 dimstyle이 삭제되는가"라는 **원인 조건**으로만 검증했다.
- 범위 제외 이슈: #43(Paul 지시) · #50(C++) · #52(문서) · #57(검증기).
- 빌더의 알려진 공백(모두 `skipped`에 계수, docstring에 명시): MULTILEADER는 IR이 `kind="leader"`로 주므로 LEADER로 강등된다 · polygon_mesh/poly_face_mesh/mline/viewport 미구현 · 해치 gradient 미구현 · ACIS/OLE/래스터는 구조적 불가.
- 심볼테이블 케이싱 복구는 레이어에만 적용했다(#60 TODO의 선종류·텍스트/치수 스타일 확장은 미구현 — dimstyle/textstyle은 ezdxf의 무구분 조회로 참조가 해소되므로 rc53 위험은 없지만 L2 테이블 이름 비교에서는 남는다).
