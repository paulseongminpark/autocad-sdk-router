#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
import tempfile

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ir_section_coverage as isc  # noqa: E402


def _entity(handle: str, *, xdata=None):
    entity = {
        "handle": handle,
        "class": "AcDbLine",
        "dxf_name": "LINE",
        "owner_handle": "1F",
        "space": "model",
        "layer": "0",
        "bbox": [],
        "geometry": {"kind": "line"},
        "source": {"extractor": "test"},
    }
    if xdata is not None:
        entity[isc.XDATA_FIELD] = xdata
    return entity


def _block_def(name: str, def_entities):
    return {"name": name, "def_entities": list(def_entities)}


def test_section_coverage_counts_pct_and_missing_lists():
    ir_a = {
        "schema": "ariadne.dwg_graph_ir.v1",
        "entities": [
            _entity("E1", xdata=[{"app": "APP", "items": [{"code": 1000, "value": "v"}]}]),
            _entity("E2"),
            _entity("E3", xdata=[]),
        ],
        "block_definitions": [
            _block_def("DOOR", [_entity("D1"), _entity("D2")]),
            _block_def("*U12", [_entity("U1")]),
            _block_def("WINDOW", []),
        ],
        "symbol_tables": {
            "layers": [{"name": "0"}, {"name": "A-WALL"}],
            "app_ids": [{"name": "ACAD"}],
        },
        "layouts": [{"name": "Model"}, {"name": "Layout1"}],
        "dictionaries": [{}, {}],
        "xrecords": [{}, {}, {}],
        "extension_dictionaries": [{}],
    }
    ir_b = {
        "schema": "ariadne.dwg_graph_ir.v1",
        "entities": [
            _entity("E1", xdata=[{"app": "APP", "items": [{"code": 1000, "value": "v"}]}]),
            _entity("E2"),
        ],
        "block_definitions": [
            _block_def("DOOR", [_entity("D1")]),
        ],
        "symbol_tables": {
            "layers": [{"name": "0"}],
            "app_ids": [{"name": "ACAD"}],
        },
        "layouts": [{"name": "Model"}],
        "dictionaries": [{}],
        "xrecords": [{}],
        "extension_dictionaries": [],
    }

    report = isc.section_coverage(ir_a, ir_b)

    assert report["schema"] == isc.SCHEMA_ID
    assert report["sections"]["entities"] == {"a": 3, "b": 2, "pct": 66.67}

    block_defs = report["sections"]["block_definitions"]
    assert block_defs["a_defs"] == 3
    assert block_defs["b_defs"] == 1
    assert block_defs["a_def_entities"] == 3
    assert block_defs["b_def_entities"] == 1
    assert block_defs["pct_defs"] == 33.33
    assert block_defs["pct_def_entities"] == 33.33
    assert block_defs["missing_def_names_sample"] == ["*U12", "WINDOW"]

    assert report["sections"]["symbol_tables"]["per_table"] == {
        "app_ids": {"a_records": 1, "b_records": 1, "pct": 100.0},
        "layers": {"a_records": 2, "b_records": 1, "pct": 50.0},
    }
    assert report["sections"]["layouts"]["names_missing_in_b"] == ["Layout1"]
    assert report["sections"]["xdata"] == {
        "entities_with_xdata_a": 1,
        "entities_with_xdata_b": 1,
    }
    assert report["headline"]["overall_weighted_pct"] == 47.62
    assert report["headline"]["worst_sections"][0]["section"] == "block_definitions"
    assert report["headline"]["worst_sections"][0]["missing"] == 2


def test_section_coverage_tolerates_absent_sections():
    ir_a = {
        "schema": "ariadne.dwg_graph_ir.v1",
        "entities": [_entity("E1")],
        "block_definitions": None,
        "symbol_tables": None,
        "layouts": [],
        "dictionaries": None,
        "xrecords": [],
        "extension_dictionaries": None,
    }
    ir_b = {"schema": "ariadne.dwg_graph_ir.v1"}

    report = isc.section_coverage(ir_a, ir_b)

    assert sorted(report["sections_absent"]) == [
        "a.block_definitions",
        "a.dictionaries",
        "a.extension_dictionaries",
        "a.layouts",
        "a.symbol_tables",
        "a.xrecords",
        "b.block_definitions",
        "b.dictionaries",
        "b.entities",
        "b.extension_dictionaries",
        "b.layouts",
        "b.symbol_tables",
        "b.xrecords",
    ]
    assert report["sections"]["entities"]["pct"] == 0.0
    assert report["sections"]["block_definitions"]["missing_def_names_sample"] == []
    assert report["sections"]["symbol_tables"]["per_table"] == {}
    assert report["sections"]["xdata"] == {
        "entities_with_xdata_a": 0,
        "entities_with_xdata_b": 0,
    }


def test_missing_def_names_sample_caps_at_20_and_keeps_anonymous_names():
    a_defs = [_block_def("*U%02d" % i, []) for i in range(15)] + [_block_def("N%02d" % i, []) for i in range(15)]
    b_defs = [_block_def("*U00", []), _block_def("N00", [])]

    report = isc.section_coverage(
        {"schema": "ariadne.dwg_graph_ir.v1", "block_definitions": a_defs},
        {"schema": "ariadne.dwg_graph_ir.v1", "block_definitions": b_defs},
    )

    sample = report["sections"]["block_definitions"]["missing_def_names_sample"]
    assert len(sample) == 20
    assert "*U01" in sample
    assert any(name.startswith("*U") for name in sample)


def test_main_writes_json_and_md_and_missing_file_exits_3():
    with tempfile.TemporaryDirectory() as tmp:
        a_path = os.path.join(tmp, "a.json")
        b_path = os.path.join(tmp, "b.json")
        json_out = os.path.join(tmp, "out.json")
        md_out = os.path.join(tmp, "out.md")

        with open(a_path, "w", encoding="utf-8") as fh:
            json.dump({"schema": "ariadne.dwg_graph_ir.v1", "entities": [_entity("E1")]}, fh)
        with open(b_path, "w", encoding="utf-8") as fh:
            json.dump({"schema": "ariadne.dwg_graph_ir.v1", "entities": []}, fh)

        rc = isc.main([a_path, b_path, "--out-json", json_out, "--out-md", md_out])
        assert rc == 0
        with open(json_out, "r", encoding="utf-8-sig") as fh:
            payload = json.load(fh)
        assert payload["sections"]["entities"]["pct"] == 0.0
        with open(md_out, "r", encoding="utf-8-sig") as fh:
            md_text = fh.read()
        assert "IR Section Coverage" in md_text
        assert "| entities | 1 | 0 | 0.00% | |" in md_text

        missing_rc = isc.main([a_path, os.path.join(tmp, "missing.json")])
        assert missing_rc == 3
