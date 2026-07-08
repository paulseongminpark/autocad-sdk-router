import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_tool(name):
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_run_dir(tmp_path, *, census_report, verdict, regen_summary=None, deferred=None, summary=None):
    write_json(tmp_path / "census_report.json", census_report)
    write_json(tmp_path / "verdict.json", verdict)
    write_json(
        tmp_path / "regen_summary.json",
        regen_summary
        or {
            "op_count": 14,
            "deferred_count": 0,
            "resolvable_ops": {
                "resolvable_count": 12,
                "unresolvable_count": 2,
                "unresolvable_op_ids": ["insert_block"],
            },
            "elapsed_seconds": 181.0,
            "seconds_per_op": 12.9,
            "apply_status": "ok",
            "apply_reason": None,
        },
    )
    write_json(tmp_path / "deferred.json", deferred if deferred is not None else [])
    write_json(
        tmp_path / "summary.json",
        summary
        or {
            "staged": {
                "original_path": r"D:\fixtures\input.dwg",
                "original_sha256": "orig-sha",
                "staged_sha256": "staged-sha",
            }
        },
    )
    return tmp_path


def test_kind_buckets_cover_pass_fail_and_vacuous(tmp_path):
    tool = load_tool("roundtrip_report")
    census_report = {
        "modelspace_entity_total": 21747,
        "certified_total": 21078,
        "out_of_class_total": 669,
        "by_bucket": [
            {"dxf_name": "ARC", "kind": "arc", "count": 2, "certified": True, "label": "arc"},
            {"dxf_name": "INSERT", "kind": "insert", "count": 2, "certified": True, "label": "insert"},
            {"dxf_name": "CIRCLE", "kind": "circle", "count": 0, "certified": True, "label": "circle"},
            {"dxf_name": "HATCH", "kind": "hatch", "count": 669, "certified": False, "label": "pending"},
        ],
    }
    verdict = {
        "comparison_basis": "geometry",
        "rows": [
            {
                "dxf_name": "ARC",
                "regen_attempted_count": 2,
                "diff0_count": 2,
                "modified_count": 0,
                "removed_count": 0,
                "added_count": 0,
                "examples": {},
            },
            {
                "dxf_name": "INSERT",
                "regen_attempted_count": 2,
                "diff0_count": 0,
                "modified_count": 0,
                "removed_count": 2,
                "added_count": 0,
                "examples": {
                    "removed": [
                        {"handle": "11995", "change": "removed", "dxf_name": "INSERT", "layer": "0"}
                    ]
                },
            },
            {
                "dxf_name": "LWPOLYLINE",
                "regen_attempted_count": 0,
                "diff0_count": 0,
                "modified_count": 0,
                "removed_count": 0,
                "added_count": 2,
                "examples": {
                    "added": [
                        {"handle": "2CD", "change": "added", "dxf_name": "LWPOLYLINE", "layer": "X"}
                    ]
                },
            },
        ],
        "totals": {
            "regen_attempted_count": 4,
            "diff0_count": 2,
            "modified_count": 0,
            "removed_count": 2,
            "added_count": 2,
        },
    }

    buckets = tool.kind_buckets(census_report, verdict)

    assert buckets["ARC"]["status"] == "PASS"
    assert buckets["INSERT"]["status"] == "FAIL"
    assert buckets["LWPOLYLINE"]["status"] != "PASS"
    assert buckets["CIRCLE"]["status"] == "VACUOUS"


def test_classify_patterns_marks_polyline_kind_drift_harmless():
    tool = load_tool("roundtrip_report")
    verdict = {
        "rows": [
            {
                "dxf_name": "POLYLINE",
                "regen_attempted_count": 2,
                "diff0_count": 0,
                "modified_count": 0,
                "removed_count": 2,
                "added_count": 0,
                "examples": {
                    "removed": [
                        {"handle": "10", "change": "removed", "dxf_name": "POLYLINE", "layer": "0"},
                        {"handle": "11", "change": "removed", "dxf_name": "POLYLINE", "layer": "0"},
                    ]
                },
            },
            {
                "dxf_name": "LWPOLYLINE",
                "regen_attempted_count": 0,
                "diff0_count": 0,
                "modified_count": 0,
                "removed_count": 0,
                "added_count": 2,
                "examples": {
                    "added": [
                        {"handle": "20", "change": "added", "dxf_name": "LWPOLYLINE", "layer": "0"},
                        {"handle": "21", "change": "added", "dxf_name": "LWPOLYLINE", "layer": "0"},
                    ]
                },
            },
        ]
    }

    patterns = tool.classify_patterns(verdict, [])
    by_key = {
        (pattern["signature"]["dxf_name"], pattern["signature"]["change"]): pattern for pattern in patterns
    }

    assert by_key[("POLYLINE", "removed")]["judgment"] == "harmless"
    assert by_key[("POLYLINE", "removed")]["rule_id"] == tool.RULE_KIND_DRIFT
    assert by_key[("LWPOLYLINE", "added")]["judgment"] == "harmless"
    assert by_key[("LWPOLYLINE", "added")]["rule_id"] == tool.RULE_KIND_DRIFT


def test_build_report_represents_naive_vs_smart_contrast(tmp_path):
    tool = load_tool("roundtrip_report")
    census_report = {
        "modelspace_entity_total": 1,
        "certified_total": 1,
        "out_of_class_total": 0,
        "by_bucket": [
            {"dxf_name": "LINE", "kind": "line", "count": 1, "certified": True, "label": "line"}
        ],
    }
    verdict = {
        "comparison_basis": "geometry",
        "rows": [
            {
                "dxf_name": "LINE",
                "regen_attempted_count": 1,
                "diff0_count": 0,
                "modified_count": 0,
                "removed_count": 1,
                "added_count": 1,
                "examples": {
                    "removed": [{"handle": "A", "change": "removed", "dxf_name": "LINE", "layer": "0"}],
                    "added": [{"handle": "B", "change": "added", "dxf_name": "LINE", "layer": "0"}],
                },
            }
        ],
        "totals": {
            "regen_attempted_count": 1,
            "diff0_count": 0,
            "modified_count": 0,
            "removed_count": 1,
            "added_count": 1,
        },
    }
    write_run_dir(tmp_path, census_report=census_report, verdict=verdict)

    naive = tool.naive_count_verdict(verdict)
    report = tool.build_report(tmp_path)

    assert naive["naive_pass"] is True
    assert report["naive_vs_smart"]["naive_pass"] is True
    assert report["naive_vs_smart"]["smart_all_diff0"] is False
    assert "blind" in report["naive_vs_smart"]["contrast_note"].lower()


def test_render_markdown_contains_kind_and_pattern_tables(tmp_path):
    tool = load_tool("roundtrip_report")
    census_report = {
        "modelspace_entity_total": 3,
        "certified_total": 2,
        "out_of_class_total": 1,
        "by_bucket": [
            {"dxf_name": "ARC", "kind": "arc", "count": 2, "certified": True, "label": "arc"}
        ],
    }
    verdict = {
        "comparison_basis": "geometry",
        "rows": [
            {
                "dxf_name": "ARC",
                "regen_attempted_count": 2,
                "diff0_count": 2,
                "modified_count": 0,
                "removed_count": 0,
                "added_count": 0,
                "examples": {},
            }
        ],
        "totals": {
            "regen_attempted_count": 2,
            "diff0_count": 2,
            "modified_count": 0,
            "removed_count": 0,
            "added_count": 0,
        },
    }
    deferred = [{"index": 3, "handle": "BEEF", "kind": "INSERT", "reason": "no block_definitions entry: XREF"}]
    write_run_dir(tmp_path, census_report=census_report, verdict=verdict, deferred=deferred)

    md = tool.render_markdown(tool.build_report(tmp_path))

    assert "# Roundtrip Fidelity Report" in md
    assert "## Per-kind verdict table" in md
    assert "| DXF Name | Certified | Census | Attempted | Diff0 | Status |" in md
    assert "## Diff patterns table" in md
    assert "| Signature | Count | Judgment | Note |" in md


def test_main_strict_returns_exit_code_3_for_harmful_pattern(tmp_path):
    tool = load_tool("roundtrip_report")
    census_report = {
        "modelspace_entity_total": 2,
        "certified_total": 2,
        "out_of_class_total": 0,
        "by_bucket": [
            {"dxf_name": "INSERT", "kind": "insert", "count": 2, "certified": True, "label": "insert"}
        ],
    }
    verdict = {
        "comparison_basis": "geometry",
        "rows": [
            {
                "dxf_name": "INSERT",
                "regen_attempted_count": 2,
                "diff0_count": 2,
                "modified_count": 0,
                "removed_count": 0,
                "added_count": 0,
                "examples": {},
            }
        ],
        "totals": {
            "regen_attempted_count": 2,
            "diff0_count": 2,
            "modified_count": 0,
            "removed_count": 0,
            "added_count": 0,
        },
    }
    deferred = [{"index": 1, "handle": "11995", "kind": "INSERT", "reason": "no block_definitions entry for handle 99"}]
    write_run_dir(tmp_path, census_report=census_report, verdict=verdict, deferred=deferred)

    out_json = tmp_path / "out" / "report.json"
    out_md = tmp_path / "out" / "report.md"
    exit_code = tool.main(
        [
            "--run-dir",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--strict",
        ]
    )

    assert exit_code == 3
    assert out_json.is_file()
    assert out_md.is_file()
