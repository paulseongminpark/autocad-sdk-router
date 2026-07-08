import json
import subprocess
import sys
import tempfile
from pathlib import Path

from tools.deferred_kind_analysis import analyze, _render_markdown, run_analysis


def _fixture_census() -> dict:
    return {
        "block_definitions": [
            {
                "name": "BLOCK_A",
                "def_entities": [
                    {"dxf_name": "POLYLINE", "geometry": {"kind": "POLY", "vertices": [1, 2], "bbox": [0, 0, 1, 1]}},
                    {"dxf_name": "POLYLINE", "geometry": {"kind": "POLY", "vertices": [3, 4]}},
                    {"dxf_name": "HATCH", "geometry": {"kind": "HATCH", "boundary": [1, 2, 3], "bbox": [0, 0, 1, 1]}},
                ],
            },
            {
                "name": "BLOCK_B",
                "def_entities": [
                    {"dxf_name": "LINE", "geometry": {"kind": "BOX", "bbox_min": [0, 0], "bbox_max": [1, 1]}},
                ],
            },
            {
                "name": "*U1",
                "def_entities": [
                    {"dxf_name": "CIRCLE", "geometry": {"kind": "CIRC", "center": [0, 0], "radius": 1}},
                ],
            },
        ]
    }


def test_reason_classing():
    deferred = [
        {"reason": "def_entity kind unsupported by write.block.append_entity", "block_name": "BLOCK_A", "def_entity_index": 0},
        {"reason": "no block_definitions entry for nested block_name *U12", "block_name": "*U12"},
        {"reason": "some other reason", "block_name": "BLOCK_A", "def_entity_index": 1},
    ]
    report = analyze(deferred, _fixture_census())
    assert report["reasons"]["unsupported_kind"] == 1
    assert report["reasons"]["missing_nested_def"] == 1
    assert report["reasons"]["other"] == 1


def test_kind_aggregation_and_geometry_key_fractions():
    deferred = [
        {"reason": "def_entity kind unsupported by write.block.append_entity", "block_name": "BLOCK_A", "def_entity_index": 0},
        {"reason": "def_entity kind unsupported by write.block.append_entity", "block_name": "BLOCK_A", "def_entity_index": 1},
    ]
    report = analyze(deferred, _fixture_census())
    poly = report["unsupported_kinds"][0]
    assert poly["kind"] == "POLY"
    assert poly["count"] == 2
    assert poly["geometry_keys_present"]["vertices"] == 1.0
    assert poly["geometry_keys_present"]["bbox"] == 0.5


def test_strategy_rule_full_geometry_and_bbox_only():
    deferred = [
        {"reason": "def_entity kind unsupported by write.block.append_entity", "block_name": "BLOCK_A", "def_entity_index": 1},
        {"reason": "def_entity kind unsupported by write.block.append_entity", "block_name": "BLOCK_B", "def_entity_index": 0},
    ]
    report = analyze(deferred, _fixture_census())

    full = next(item for item in report["unsupported_kinds"] if item["kind"] == "POLY")
    bbox = next(item for item in report["unsupported_kinds"] if item["kind"] == "BOX")
    assert full["strategy"] == "native_append_extension"
    assert bbox["strategy"] == "defer_documented"


def test_decompose_candidate_for_hatch_boundary():
    deferred = [
        {"reason": "def_entity kind unsupported by write.block.append_entity", "block_name": "BLOCK_A", "def_entity_index": 2},
    ]
    report = analyze(deferred, _fixture_census())
    hatch = report["unsupported_kinds"][0]
    assert hatch["kind"] == "HATCH"
    assert hatch["strategy"] == "decompose_to_certified"


def test_anonymous_nested_def_detection():
    deferred = [
        {"reason": "no block_definitions entry for nested block_name *U1", "block_name": "*U1"},
        {"reason": "no block_definitions entry for nested block_name *U2", "block_name": "*U2"},
    ]
    report = analyze(deferred, _fixture_census())
    assert report["missing_nested_defs"]["all_anonymous"] is True
    assert report["missing_nested_defs"]["count"] == 2
    assert report["missing_nested_defs"]["names"] == ["*U1", "*U2"]


def test_missing_files_exit_code_is_3():
    with tempfile.TemporaryDirectory() as tmp:
        assert run_analysis(Path(tmp), None, None) == 3


def test_markdown_contains_top_kind_row():
    deferred = [
        {"reason": "def_entity kind unsupported by write.block.append_entity", "block_name": "BLOCK_A", "def_entity_index": 0},
        {"reason": "def_entity kind unsupported by write.block.append_entity", "block_name": "BLOCK_A", "def_entity_index": 1},
        {"reason": "def_entity kind unsupported by write.block.append_entity", "block_name": "BLOCK_B", "def_entity_index": 0},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "run"
        run_dir.mkdir()
        (run_dir / "deferred.json").write_text(
            json.dumps(deferred, ensure_ascii=True),
            encoding="utf-8",
        )
        census_path = run_dir / "census"
        census_path.mkdir()
        (census_path / "dwg_graph_ir.json").write_text(
            json.dumps(_fixture_census(), ensure_ascii=True),
            encoding="utf-8",
        )
        md_file = run_dir / "matrix.md"
        proc = subprocess.run(
            [sys.executable, "tools/deferred_kind_analysis.py", "--run-dir", str(run_dir), "--out-md", str(md_file)],
            cwd=Path(__file__).resolve().parents[1].parent,
            check=False,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        text = md_file.read_text(encoding="utf-8-sig")
        table = _render_markdown(analyze(deferred, _fixture_census()))
        assert "| POLY | 2 | native_append_extension" in text
        assert table.startswith("# Deferred kind analysis")
        assert "POLY" in table
        assert proc.stdout == ""
        assert proc.stderr == ""
