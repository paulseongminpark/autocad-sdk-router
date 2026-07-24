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


def test_native_btr_emits_acad_sortents_pairs_without_sorting_them():
    source = NATIVE_SOURCE.read_text(encoding="utf-8")
    region = source[source.index("static std::string blockTableRecordsJson"):
                    source.index("static std::string layoutsRichJson")]

    assert "getSortentsTable" in region
    assert "createIfNecessary=false" in region
    assert "getFullDrawOrder" in region
    assert "sortAs" in region
    assert '\\"sortents\\":' in region
    assert "std::sort" not in region


def test_ir_builder_preserves_sortents_pairs_and_schema_accepts_them():
    sortents = [["10", "A"], ["11", "9"]]
    graph = {
        "modelspace_entities": 0,
        "entities": [],
        "block_table_records": [
            {
                "handle": "1F",
                "name": "*Model_Space",
                "is_layout": True,
                "entity_count": 0,
                "sortents": sortents,
            }
        ],
    }

    ir = build_ir_from_database_graph(graph, {"dwg_path": "fixture.dwg"})

    assert ir["symbol_tables"]["block_table_records"][0]["sortents"] == sortents
    schema = json.loads(SCHEMA.read_text(encoding="utf-8-sig"))
    jsonschema.Draft7Validator(schema).validate(ir)
