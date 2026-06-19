# DWG Native Geometry Extractor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a production-grade DWG coordinate extraction mode to `dwg_truth_autocad` using `accoreconsole` + `NETLOAD` of an AutoCAD .NET plugin, then restart the centerline experiment from router evidence as R2.

**Architecture:** Keep the existing AutoLISP count extractor as the default compatibility path. Add a managed ObjectARX/.NET DLL that runs inside AutoCAD Core Console, opens the active staged DWG database through the AutoCAD managed API, extracts coordinate-level entity geometry into a schema-versioned JSON file, and returns through the existing router staging/run policy. The R2 centerline experiment consumes the new JSON instead of the count-only summary.

**Tech Stack:** PowerShell router, AutoCAD 2027 `accoreconsole.exe`, AutoCAD managed assemblies (`acmgd.dll`, `acdbmgd.dll`, `accoremgd.dll`), C#/.NET 10, `Newtonsoft.Json`, pytest, Python JSON/schema checks.

---

## File Structure

- Create: `src/Ariadne.DwgGeometryExtractor/Ariadne.DwgGeometryExtractor.csproj`
  Builds the NETLOAD plugin against AutoCAD 2027 managed assemblies.
- Create: `src/Ariadne.DwgGeometryExtractor/Commands.cs`
  Exposes `ARIADNE_DWG_GEOM_EXTRACT` command and reads the output path from `ARIADNE_DWG_GEOM_OUT`.
- Create: `src/Ariadne.DwgGeometryExtractor/GeometryExtractor.cs`
  Iterates modelspace entities and converts supported geometry to JSON-safe DTOs.
- Create: `src/Ariadne.DwgGeometryExtractor/GeometryDtos.cs`
  DTO contracts for document metadata, summary, entity records, points, bounding boxes, xdata, block references, and geometry payloads.
- Create: `src/Ariadne.DwgGeometryExtractor/JsonWriter.cs`
  Writes deterministic UTF-8 JSON using AutoCAD-bundled `Newtonsoft.Json`.
- Modify: `tools/autocad-router.ps1`
  Adds `-ExtractMode summary|geometry_native`, builds/locates the DLL, writes a NETLOAD script for geometry mode, sets `ARIADNE_DWG_GEOM_OUT`, and returns the same router envelope.
- Create: `schemas/dwg_geometry_extract.schema.json`
  Defines the coordinate-level extraction contract.
- Create: `tests/test_dwg_geometry_native_contract.py`
  Locks route parameters, script generation semantics, project file references, and output schema.
- Create: `tools/validate_dwg_geometry_extract.py`
  Validates extractor JSON against count parity and required coordinate payloads.
- Create: `D:\dev\_ariadne\alm\runs\CODEX_CENTERLINE_RULEPACK_0616_R2_ARX_GEOM\...`
  New isolated R2 run folder after the router mode is proven.

## Task 1: Contract Tests

- [ ] Write failing pytest checks in `tests/test_dwg_geometry_native_contract.py`.
- [ ] Verify they fail because `-ExtractMode`, `schemas/dwg_geometry_extract.schema.json`, and the C# project do not exist.
- [ ] Add only the minimum files/parameters required for those tests to pass.
- [ ] Run `python -m pytest tests -q`.

## Task 2: C# Plugin Build

- [ ] Create the C# project targeting `net10.0-windows`.
- [ ] Reference `C:\Program Files\Autodesk\AutoCAD 2027\acmgd.dll`, `acdbmgd.dll`, `accoremgd.dll`, and `Newtonsoft.Json.DLL` with `Private=false`.
- [ ] Implement `ARIADNE_DWG_GEOM_EXTRACT` to write an explicit error JSON if extraction fails.
- [ ] Run `dotnet build src/Ariadne.DwgGeometryExtractor/Ariadne.DwgGeometryExtractor.csproj -c Release`.

## Task 3: Geometry Coverage

- [ ] Extract `LINE` as start/end points.
- [ ] Extract `LWPOLYLINE` and `POLYLINE` as ordered vertices with closed/bulge flags where exposed by the managed API.
- [ ] Extract `ARC` and `CIRCLE` as center/radius/angle payloads.
- [ ] Extract `INSERT`/`BlockReference` with block name, effective name where available, transform matrix, position, scale, rotation, and attributes.
- [ ] Extract `DBText`, `MText`, and `Dimension` placement/value metadata.
- [ ] Include layer, handle, object id, layout, color, linetype, visibility, bbox, and xdata for every entity.

## Task 4: Router Integration

- [ ] Keep default `-Action run -Intent dwg` behavior unchanged as summary mode.
- [ ] Add `-ExtractMode geometry_native`.
- [ ] In geometry mode, stage the DWG exactly like summary mode, run `NETLOAD` on the built DLL, execute `ARIADNE_DWG_GEOM_EXTRACT`, then `QUIT` without save.
- [ ] Return `mode=geometry_native`, `extract_json=<...geometry.json>`, `extract_exists=true`, and parsed `extract`.
- [ ] Preserve original DWG bytes and mtimes.

## Task 5: Real DWG Verification

- [ ] Run router status first.
- [ ] Run geometry extraction on `D:\dev\_ariadne\alm\build\input0616.dwg`.
- [ ] Run geometry extraction on `D:\dev\_ariadne\alm\build\output0616.dwg`.
- [ ] Validate that `entities.length == summary.modelspace_count`.
- [ ] Validate that supported entity coordinate payloads exist for `LINE`, `LWPOLYLINE`/`POLYLINE`, `ARC`, `CIRCLE`, and `INSERT`.
- [ ] Re-hash original DWGs and confirm they match the known R1 hashes.

## Task 6: R2 Experiment Restart

- [ ] Create `D:\dev\_ariadne\alm\runs\CODEX_CENTERLINE_RULEPACK_0616_R2_ARX_GEOM`.
- [ ] Copy source manifest and rulepack snapshot shape from R1, but regenerate all router evidence from geometry mode.
- [ ] Convert geometry JSON into `04_intermediate/cad_geometry_summary.json`.
- [ ] Produce `05_generated/centerline_candidates.json` only from real entity handles and coordinates.
- [ ] Produce `06_validation/geometry_gate_summary.json`.
- [ ] Report R1 vs R2 differences and explicitly state which gates remain blocked.
