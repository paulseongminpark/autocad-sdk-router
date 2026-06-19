# TRINITY DRAFT — "AutoCAD SDK Router" section

> Drop-in replacement section for the **AutoCAD SDK Router** entry in all three trinity files:
> `D:\dev\CLAUDE.md` (Claude) · `D:\dev\AGENTS.md` (Codex) · `D:\dev\GEMINI.md` (Gemini CLI).
> These three are PROTECTED — do NOT edit them directly. Lead applies this **identical** block to all
> three after `approve P-NN`. The block below is the verbatim text to paste (between the `<<<BEGIN` /
> `END>>>` fences; the fences themselves are not part of the section).
>
> Rebuild date: 2026-06-16. Router home moved Drive-mirror → local `D:\dev\99_tools\autocad-sdk-router`.
> 11 distinct routes implemented (frozen spec header says "12"; see the spec-count note in the block).

---

<<<BEGIN COMMON SECTION (paste identically into CLAUDE.md / AGENTS.md / GEMINI.md)

## AutoCAD SDK Router

DWG·DXF·IFC·BREP·mesh·point-cloud·geo-vector·PDF/SVG·raster 작업의 **단일 진입점**. 의도(intent)만 말하면
라우터가 *현재 사용 가능한* 가장 강한 route를 고르고 capability 로 fallback 한다. 엔진을 직접 손으로 고르지 말 것
(명시 override 는 `-Route`).

**모든 에이전트 必 사용 — 우회 금지.** CAD 계열 파일(아래 11 route 의 입력 타입)을 읽거나 추출·비교·생성할 때는
native 도구나 ad-hoc 스크립트로 직행하지 말고 *반드시* 이 라우터를 먼저 호출한다. 우회는 origin 파일 손상·fake
extraction·route drift 의 원인.

### 위치 (로컬 재구축 — Drive 미러 폐기)

| 항목 | 경로 |
|------|------|
| Router home | `D:\dev\99_tools\autocad-sdk-router` |
| 단일 entrypoint | `D:\dev\99_tools\autocad-sdk-router\tools\autocad-router.ps1` |
| Capabilities (route metadata) | `D:\dev\99_tools\autocad-sdk-router\config\autocad_router_capabilities.json` |
| Live status (probe 결과) | `D:\dev\99_tools\autocad-sdk-router\reports\autocad_router_status_latest.json` |
| Agent contract (필독) | `D:\dev\99_tools\autocad-sdk-router\reports\AUTO_CAD_ROUTER_AGENT_CONTRACT.md` |
| 구 원본 (참고 only) | `C:\Users\PAUL\내 드라이브\Ariadne Atlas\01_RUNS\workitem_by_sjh_ongoing\chatgpt_codex2\workspace\sdk_route_reconstruction_20260605` |

### 규율 (non-negotiable)

- **원본 CAD 소스는 READ-ONLY.** `.dwg/.dxf/.ifc/.step/.3dm` 원본을 절대 수정하지 않는다.
- **ASCII staging.** `dwg_truth_autocad` 는 입력 DWG 를 `staging\dwg_<stamp>\` 로 복사 후 그 사본에서
  accoreconsole 를 forward-slash·ASCII-safe 스크립트로 실행 (비-ASCII·Drive 경로 회피).
- **Export/derive only.** AutoCAD route 의 기본 job 은 AutoLISP entity → JSON 추출. `QUIT` 만 하고 절대
  SAVE 안 함. 파생물은 `runs\dwg_truth_autocad_<stamp>\` 아래.
- **No fake success.** REQUIRED 도구가 실제로 import/resolve 될 때만 `available:true` (live probe). 불가용
  route 를 강제하면 `status:UNAVAILABLE` 반환 후 실행 거부 — 가짜 pass 없음.
- **LibreDWG = GPL → sidecar only.** `dwg_libredwg_sidecar` 는 별도 프로세스로만. production 라우터에
  link/import 금지.

### 11 route 요약

> 동결 스펙 헤더는 "12-ROUTE" 라 표기하나 실제 distinct route ID 는 **11개** (스펙 자신의 dispatch 목록도 엔진
> 11개). 라우터는 정확히 이 11개를 구현. "12번째"는 구 Drive 라우터가 AutoCAD 를 6개 내부 sub-route
> (CoreConsole/AutoLISP/ObjectDBX/ObjectARX/COM/full-AutoCAD)로 쪼갠 것을 여기서 단일 `dwg_truth_autocad`
> 엔진으로 folding 한 결과. 진짜 12번째 top-level route 가 의도된 것이면 Paul 확인 사항 — 임의 발명 안 함.

| # | route | 엔진 | available | 의도 키워드 | 대표 입력 |
|---|-------|------|-----------|-------------|-----------|
| 1 | `dwg_truth_autocad` | accoreconsole (AutoCAD 2027) | yes | dwg, autocad, dynamic_block, xdata, layout, objectdbx | .dwg |
| 2 | `dxf_fast_secondary` | ezdxf + shapely | yes | dxf, polyline, 2d_geometry | .dxf |
| 3 | `ifc_bim_semantic` | ifcopenshell | yes | ifc, bim, wall, storey, property_set | .ifc |
| 4 | `solid_brep_occ` | cadquery + OCP (OCCT 7.8) | yes | step, brep, solid, iges, topology, boolean | .step/.brep/.iges |
| 5 | `parametric_rebuild` | cadquery (생성 전용) | yes | rebuild, generate, parametric, export_step | (출력 .step/.stl/.svg) |
| 6 | `dwg_libredwg_sidecar` | LibreDWG CLI | yes | libredwg, dwg_no_autocad, dwg_crosscheck | .dwg |
| 7 | `mesh_analysis` | trimesh + meshio + open3d | yes | mesh, stl, watertight, obj, ply | .stl/.obj/.ply |
| 8 | `pointcloud_route` | open3d + laspy | yes | pointcloud, las, laz, rcs, icp | .las/.laz/.pcd/.ply |
| 9 | `geo_vector_route` | pyogrio (bundled GDAL 3.11.4) + pyproj | yes | geo, shp, geojson, crs, dgn | .shp/.geojson/.dxf/.dgn/.gpkg |
| 10 | `pdf_svg_vector_route` | svgpathtools + svgelements (PyMuPDF optional) | yes | pdf, svg, vector_path, overlay | .svg/.pdf |
| 11 | `raster_compare_route` | opencv-headless + scikit-image | yes | raster, image_compare, ssim, visual_qa | .png/.jpg render |

### 엔진 — accoreconsole (route 1, ground-truth)

- 실행파일: `C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe` (로컬 설치 확인됨).
- DWG 원본 truth (dynamic block, xdata, layout, named objects, ObjectDBX read, CoreConsole batch extraction).
- 스모크 확인 (input.dwg): modelspace 375 entities — INSERT 50 / LWPOLYLINE 73 / TEXT 117 / DIMENSION 113 /
  LINE 21 / CIRCLE 1. 원본 byte/mtime 불변. (DXF route 와 375=375 cross-engine 일치.)

### Actions / 사용

```powershell
$R = 'D:\dev\99_tools\autocad-sdk-router\tools\autocad-router.ps1'
& $R -Action status                                  # 전 route 가용성 live probe
& $R -Action select  -Intent ifc                     # intent→route 선택 (fallback 포함, 미실행)
& $R -Action run     -Intent dwg  -InputPath '<...\drawing.dwg>'   # DWG ground-truth 추출 (원본 불변)
& $R -Action run     -Intent dxf  -InputPath '<...\model.dxf>'     # AutoCAD 없이 DXF 빠른 read
& $R -Action run     -Intent step -InputPath '<...\part.step>'     # STEP/BREP topology
& $R -Action run     -Intent parametric -Out '<...\out.step>'      # 새 파라메트릭 솔리드 생성
& $R -Action run     -Intent raster -InputPath 'a.png' -InputPath2 'b.png'  # 두 render SSIM 비교
```

### Env-var 바인딩 (ARIADNE_AUTOCAD_ROUTER_*)

tracked 엔트리포인트(`aclaude`/`acodex`/`ahermes`)가 `ARIADNE_AUTOCAD_ROUTER_*` 를 export 한다. 그 값은
`D:\dev\_ariadne\bin\ariadne_entrypoint_common.ps1` (lines 21-25, export 130-135)에 하드코딩되어 있고 **현재 구
로컬 router** 를 가리킨다. `ARIADNE_LIBREDWG_BIN_DIR=D:\dev\99_tools\libredwg\bin` 과
`ARIADNE_CAD_ROUTER_ENFORCEMENT=required` 도 함께 export 한다.

- 승인 대기 (영구 repoint): `D:\dev\99_tools\autocad-sdk-router\ENVVAR_REPOINT.md` 의 정확한 diff 를 `approve
  P-NN` 후 적용. (line 21 `$Script:AutoCadRouterRoot` 만 로컬 루트로 교체; 22-25·130-135 은 Join-Path 파생이라
  무변경.)
- 승인 전 임시 (세션 한정, protected 미수정): `. D:\dev\99_tools\autocad-sdk-router\set-router-env.ps1` 를
  dot-source → 현재 셸의 Process-scope env 만 로컬 router 로 override.
- tracked wrapper 는 boot context 와 CLI별 prompt/context injection 으로 이 규칙을 주입하고,
  CAD router 우회 flag 를 차단한다.

### 입력 경로 A·B (워크아이템 실데이터)

| 레인 | 경로 | 내용 |
|------|------|------|
| **A (truth DWG)** | `D:\dev\_ariadne\alm\build\input.dwg` | accoreconsole ground-truth 추출 대상. modelspace 375 entities. 원본 READ-ONLY (staging 사본에서만 작업). |
| **B (export DXF)** | `D:\dev\_ariadne\alm\build\input_84A.dxf` | 같은 도면의 DXF export (15.7MB, AC1032). ezdxf route 로 375 entities — A 와 동일 프로파일이라 **B 는 A 의 DXF export** (375=375 검증). line_total_length 83738.70, 14 layers (한국어 '설비OPEN' 포함). |

> 보조 reference 실데이터(같은 build 폴더): `84A_hq.pdf` (PyMuPDF 1 page / 54882 vector drawings,
> `pdf_svg_vector_route`) · `84A_walls.png` (`raster_compare_route` self-SSIM=1.0). IFC/SVG 는 build 에 실샘플
> 없어 스모크는 생성본/ import-verify 로 확인.

### 설치 / 알려진 gap (정직)

- 이미 설치: ifcopenshell 0.8.5 · ezdxf 1.4.3 · shapely 2.1.2 · cadquery + cadquery-ocp 7.8.1.1 · trimesh +
  meshio + open3d · open3d + laspy · pyogrio 0.12.1 (GDAL 3.11.4 bundle) + pyproj · svgpathtools + svgelements ·
  PyMuPDF(fitz) 1.27.2.3 · opencv-python-headless + scikit-image · freecadcmd 1.1.1 (optional alt kernel).
- **`dwg_libredwg_sidecar` 가용.** LibreDWG 0.13.4 sidecar CLI 는 `D:\dev\99_tools\libredwg\bin` 아래.
  전역 PATH 추가 없음. GPL — 절대 production 에 import/link/bundle 금지.
- `geo_vector_route`: native `osgeo.gdal` 바인딩 없음 (Windows wheel 부재). pyogrio(GDAL 3.11.4 bundle) + pyproj
  로 vector IO·CRS 충족. native GDAL 은 raster 연산·`ogr2ogr`/`gdal_translate` CLI 에만 필요 (수동: OSGeo4W /
  conda-forge).
- `pdf_svg_vector_route`: PyMuPDF 가 main Python312 env 에 **shared** 설치 (스펙은 "isolated" 명시). 작동에는
  무관 — isolation 은 Paul 결정 대기.
- Native-extension shutdown segfault (0xC0000005): 모든 heavy CAD/geometry C-extension 을 한 프로세스에서 import
  하면 작업 완료 *후* interpreter shutdown 에서 발생 가능. probe 는 각 모듈을 isolated subprocess + flush/fsync
  파일로 우회; per-route run 은 해당 route lib 만 load 해 clean exit. 모든 route exit 0 + valid JSON 확인됨.
- Status JSON 은 PowerShell `-Encoding UTF8` (BOM). 라우터의 PowerShell read 는 정상; Python `json.load` 는 이
  머신 cp949 로케일에서 `encoding='utf-8-sig'` 필요 (cosmetic).

### 진단 / 단일 진실 소스

```powershell
& 'D:\dev\99_tools\autocad-sdk-router\tools\autocad-router.ps1' -Action status
# → ALL_AVAILABLE, route_count=11, available_count=11
```

라우팅 단일 진실 소스: `D:\dev\99_tools\autocad-sdk-router\reports\AUTO_CAD_ROUTER_AGENT_CONTRACT.md`.

> **공유**: 이 AutoCAD SDK Router 섹션은 `D:\dev\CLAUDE.md`·`D:\dev\AGENTS.md`·`D:\dev\GEMINI.md` 셋 다 동일.
> 한 파일 수정 시 셋 다 갱신 (셋 다 PROTECTED — `approve P-NN` 필요).

END>>>
