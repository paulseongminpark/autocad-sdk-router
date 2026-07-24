from __future__ import annotations

import base64
import hashlib
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


def test_native_ole2frame_emits_geometry_metadata_and_honest_data_fallback():
    source = NATIVE_SOURCE.read_text(encoding="utf-8")
    assert '#include "dbole.h"' in source
    assert "AcDbOle2Frame* pOle" in source
    for field in (
        "frame_corners",
        "ole_type",
        "ole_version",
        "ole_data_b64",
        "ole_data_sha256",
        "ole_data_bytes",
        "ole_data_unavailable_reason",
    ):
        assert f'\\"{field}\\"' in source
    assert "no public getCompoundDocument accessor" in source


def test_ir_builder_decodes_ole2frame_and_preserves_consistent_payload_metadata():
    payload_b64 = "AE9MRQ=="
    payload_sha256 = "d7b78fc05c4e64cb1c945ee44ebebf467063cd886ac6ab305b0b23af2d6e4fe6"
    graph = {
        "modelspace_entities": 2,
        "entities": [
            {
                "handle": "10",
                "dxf_name": "AcDbOle2Frame",
                "layer": "LOGO",
                "frame_corners": [
                    [0.0, 10.0, 0.0],
                    [20.0, 10.0, 0.0],
                    [0.0, 0.0, 0.0],
                    [20.0, 0.0, 0.0],
                ],
                "ole_type": 2,
                "ole_version": 2,
                "ole_data_b64": payload_b64,
                "ole_data_sha256": payload_sha256,
                "ole_data_bytes": 4,
            },
            {
                "handle": "11",
                "dxf_name": "AcDbOle2Frame",
                "layer": "LOGO",
                "frame_corners": [],
                "ole_type": 2,
                "ole_version": 2,
                "ole_data_b64": None,
                "ole_data_sha256": None,
                "ole_data_bytes": None,
                "ole_data_unavailable_reason": "compound document API unavailable",
            },
        ],
    }

    ir = build_ir_from_database_graph(graph, {"dwg_path": "fixture.dwg"})
    by_handle = {entity["handle"]: entity for entity in ir["entities"]}
    embedded = by_handle["10"]
    unavailable = by_handle["11"]

    assert embedded["dxf_name"] == "OLE2FRAME"
    assert embedded["geometry"]["kind"] == "ole2frame"
    assert embedded["source"]["decoded"] is True
    decoded = base64.b64decode(embedded["geometry"]["ole_data_b64"], validate=True)
    assert len(decoded) == embedded["geometry"]["ole_data_bytes"]
    assert hashlib.sha256(decoded).hexdigest() == embedded["geometry"]["ole_data_sha256"]

    assert unavailable["source"]["decoded"] is True
    assert unavailable["geometry"]["ole_data_b64"] is None
    assert unavailable["geometry"]["ole_data_sha256"] is None
    assert unavailable["geometry"]["ole_data_bytes"] is None
    assert unavailable["geometry"]["ole_data_unavailable_reason"]

    schema = json.loads(SCHEMA.read_text(encoding="utf-8-sig"))
    jsonschema.Draft7Validator(schema).validate(ir)
