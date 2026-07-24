from __future__ import annotations

import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from ir_builder import build_ir_from_database_graph  # noqa: E402


def test_text_alignment_point_survives_native_graph_to_ir():
    graph = {
        "modelspace_entities": 2,
        "entities": [
            {
                "handle": "10",
                "dxf_name": "AcDbText",
                "layer": "TEXT",
                "position": [1.0, 2.0, 0.0],
                "alignment_point": {"x": 4.0, "y": 5.0, "z": 0.0},
                "horizontal_mode": 1,
                "vertical_mode": 0,
            },
            {
                "handle": "11",
                "dxf_name": "AcDbText",
                "layer": "TEXT",
                "position": [7.0, 8.0, 0.0],
                "horizontal_mode": 0,
                "vertical_mode": 0,
            },
        ],
    }

    ir = build_ir_from_database_graph(graph, {"dwg_path": "fixture.dwg"})
    by_handle = {entity["handle"]: entity for entity in ir["entities"]}

    assert by_handle["10"]["geometry"]["alignment_point"] == [4.0, 5.0, 0.0]
    assert "alignment_point" not in by_handle["11"]["geometry"]
