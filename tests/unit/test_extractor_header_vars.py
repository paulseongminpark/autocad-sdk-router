from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from ir_builder import build_ir_from_database_graph  # noqa: E402


NATIVE_SOURCE = ROOT / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"
SCHEMA = ROOT / "schemas" / "dwg_graph_ir.v1.schema.json"

HEADER_VARS = {
    "XCLIPFRAME": 2,
    "DGNFRAME": 1,
    "PDFFRAME": 0,
    "LTSCALE": 800.0,
    "PSLTSCALE": True,
    "MSLTSCALE": False,
    "CELTSCALE": 1.5,
    "FILLMODE": True,
    "PLINEGEN": False,
    "INSUNITS": 4,
    "MIRRTEXT": False,
    "ATTMODE": 1,
    "PDMODE": 3,
    "PDSIZE": 2.5,
}

# #48: no AcDbDatabase getter -- read from the NOD "AcDbVariableDictionary",
# emitted only when the dictionary entry is actually readable.
DICTIONARY_VARS = {
    "WIPEOUTFRAME": 1,
    "IMAGEFRAME": 1,
    "FRAME": 3,
}


def test_native_database_emits_supported_header_vars_and_names_omissions():
    source = NATIVE_SOURCE.read_text(encoding="utf-8")
    region = source[source.index("static std::string databaseMetaJson"):
                    source.index("static std::string collectDatabaseGraph")]

    assert '\\"header_vars\\":{' in region
    for name in HEADER_VARS:
        assert f'\\"{name}\\":' in region
    # #48: the trio is emitted through the dictionary-variable reader, never a
    # synthesized default.
    for name in DICTIONARY_VARS:
        assert f'dictionaryVarInt(pDb, ACRX_T("{name}"), dv)' in region
        assert f'\\"{name}\\":' in region
    assert '"AcDbVariableDictionary"' in source


def test_ir_builder_preserves_dictionary_var_trio_and_schema_accepts_them():
    merged = {**HEADER_VARS, **DICTIONARY_VARS}
    graph = {
        "modelspace_entities": 0,
        "entities": [],
        "database": {"header_vars": merged},
    }

    ir = build_ir_from_database_graph(graph, {"dwg_path": "fixture.dwg"})

    assert ir["database"]["header_vars"] == merged
    schema = json.loads(SCHEMA.read_text(encoding="utf-8-sig"))
    jsonschema.Draft7Validator(schema).validate(ir)


def test_ir_builder_preserves_header_var_types_and_schema_accepts_them():
    graph = {
        "modelspace_entities": 0,
        "entities": [],
        "database": {"header_vars": HEADER_VARS},
    }

    ir = build_ir_from_database_graph(graph, {"dwg_path": "fixture.dwg"})

    assert ir["database"]["header_vars"] == HEADER_VARS
    schema = json.loads(SCHEMA.read_text(encoding="utf-8-sig"))
    jsonschema.Draft7Validator(schema).validate(ir)
