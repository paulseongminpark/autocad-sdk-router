import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "tools" / "autocad-router.ps1"
PROJECT = ROOT / "src" / "Ariadne.DwgGeometryExtractor" / "Ariadne.DwgGeometryExtractor.csproj"
SCHEMA = ROOT / "schemas" / "dwg_geometry_extract.schema.json"


def test_router_exposes_geometry_native_extract_mode():
    text = ROUTER.read_text(encoding="utf-8")

    assert "ExtractMode" in text
    assert "geometry_native" in text
    assert "ARIADNE_DWG_GEOM_OUT" in text
    assert "ARIADNE_DWG_GEOM_EXTRACT" in text
    assert "Get-CadProcessSnapshot" in text
    assert "process_hygiene" in text
    assert "new_acad_processes" in text


def test_native_extractor_project_references_autocad_managed_api():
    text = PROJECT.read_text(encoding="utf-8")

    assert "<TargetFramework>net10.0-windows</TargetFramework>" in text
    assert "acmgd.dll" in text.lower()
    assert "acdbmgd.dll" in text.lower()
    assert "accoremgd.dll" in text.lower()
    assert "Newtonsoft.Json.DLL" in text
    assert "<Private>false</Private>" in text


def test_geometry_schema_requires_coordinate_entities():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert schema["title"] == "DWG Native Geometry Extract"
    entity_schema = schema["properties"]["entities"]["items"]
    required = set(entity_schema["required"])
    assert {"handle", "object_id", "type", "layer", "geometry"}.issubset(required)
    geometry_kind = entity_schema["properties"]["geometry"]["properties"]["kind"]
    assert "line" in geometry_kind["enum"]
    assert "polyline" in geometry_kind["enum"]
    assert "arc" in geometry_kind["enum"]
    assert "circle" in geometry_kind["enum"]
    assert "block_reference" in geometry_kind["enum"]


def test_native_geometry_validator_script_exists():
    validator = ROOT / "tools" / "validate_dwg_geometry_extract.py"
    text = validator.read_text(encoding="utf-8")

    assert "entities.length == summary.modelspace_count" in text
    assert "require_coordinate_payloads" in text
