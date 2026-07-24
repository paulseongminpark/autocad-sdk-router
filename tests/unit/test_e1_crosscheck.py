#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
TOOLS_DIR = os.path.join(_REPO, "tools")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import e1_crosscheck as ec  # noqa: E402


def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _write_json(path, payload):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _orn_row(def_name=None, likelihood=0.0, handles=None):
    parsed = {"wall_likelihood": likelihood, "wall_line_handles": handles or []}
    if def_name is not None:
        parsed["def"] = def_name
    return {"unit_id": f"u-{def_name or 'missing'}", "parsed": parsed}


def test_run_joins_exact_and_whitespace_normalized_defs(tmp_path):
    ornith_path = tmp_path / "ornith.jsonl"
    pairs_path = tmp_path / "pairs.json"
    _write_jsonl(
        ornith_path,
        [
            _orn_row("A", 0.9, [{"handle": "h1"}, {"handle": "h2"}]),
            _orn_row("B name", 0.1, [{"handle": "h3"}]),
            _orn_row(None, 0.4, [{"handle": "hx"}]),
        ],
    )
    _write_json(
        pairs_path,
        {
            "schema": "ariadne.semantic.wall_pairs.v0",
            "per_def": {
                "A": [],
                "Bname": [
                    {"kind": "wall_pair_candidate", "pair": ["h3", "h4"]},
                    {"kind": "wall_pair_candidate", "pair": ["h4", "h5"]},
                    {"kind": "wall_pair_candidate", "pair": ["h6", "h7"]},
                    {"kind": "wall_pair_candidate", "pair": ["h8", "h9"]},
                    {"kind": "wall_pair_candidate", "pair": ["h10", "h11"]},
                ],
                "C": [{"kind": "wall_pair_candidate", "pair": ["c1", "c2"]}],
            },
            "totals": {"defs": 3, "claims": 6},
        },
    )

    report = ec.run(ornith_path, pairs_path)

    assert report["schema"] == "ariadne.e1_crosscheck.v0"
    assert [row["def"] for row in report["per_def"]] == ["A", "B name"]
    assert report["per_def"][0]["n_pairs"] == 0
    assert report["per_def"][0]["n_h_ornith"] == 2
    assert report["per_def"][0]["n_h_det"] == 0
    assert report["per_def"][0]["jaccard"] == 0.0
    assert report["per_def"][0]["containment"] == 0.0
    assert report["per_def"][1]["n_pairs"] == 5
    assert report["per_def"][1]["n_h_ornith"] == 1
    assert report["per_def"][1]["n_h_det"] == 9
    assert report["per_def"][1]["jaccard"] == 1 / 9
    assert report["per_def"][1]["containment"] == 1.0
    assert report["summary"]["joined"] == 2
    assert report["summary"]["unjoined_ornith"] == 1
    assert report["summary"]["unjoined_pairs"] == 1
    assert report["summary"]["top20_divergent"] == ["A", "B name"]


def test_pearson_and_divergent_detection_use_joined_rows_only(tmp_path):
    ornith_path = tmp_path / "ornith.jsonl"
    pairs_path = tmp_path / "pairs.json"
    _write_jsonl(
        ornith_path,
        [
            _orn_row("High", 0.95, [{"handle": "h1"}]),
            _orn_row("Low", 0.05, [{"handle": "h2"}]),
            _orn_row("Ignored", 0.8, [{"handle": "h3"}]),
        ],
    )
    _write_json(
        pairs_path,
        {
            "schema": "ariadne.semantic.wall_pairs.v0",
            "per_def": {
                "High": [],
                "Low": [{"kind": "wall_pair_candidate", "pair": ["h2", "h4"]} for _ in range(5)],
            },
            "totals": {"defs": 2, "claims": 5},
        },
    )

    report = ec.run(ornith_path, pairs_path)

    assert report["summary"]["joined"] == 2
    assert report["summary"]["unjoined_ornith"] == 1
    assert report["summary"]["unjoined_pairs"] == 0
    assert report["summary"]["likelihood_vs_pairs_pearson"] == -1.0
    assert report["summary"]["top20_divergent"] == ["High", "Low"]


def test_write_reports_writes_json_and_markdown(tmp_path):
    report = {
        "schema": "ariadne.e1_crosscheck.v0",
        "per_def": [
            {
                "def": "A",
                "wall_likelihood": 0.9,
                "n_pairs": 0,
                "n_h_ornith": 1,
                "n_h_det": 0,
                "jaccard": 0.0,
                "containment": 0.0,
            }
        ],
        "summary": {
            "joined": 1,
            "unjoined_ornith": 0,
            "unjoined_pairs": 0,
            "likelihood_vs_pairs_pearson": None,
            "top20_divergent": ["A"],
        },
    }
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"

    ec.write_reports(report, out_json, out_md)

    assert json.loads(out_json.read_text(encoding="utf-8")) == report
    assert "Top-20 Divergent" in out_md.read_text(encoding="utf-8")
