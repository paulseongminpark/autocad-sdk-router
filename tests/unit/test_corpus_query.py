from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import corpus_query  # noqa: E402


def _write_ledger(tmp_path: Path, lines: list[str]) -> Path:
    path = tmp_path / "ledger.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _ok_row(name: str, entity_count: int, by_layer: dict, by_entity_type: dict) -> dict:
    return {
        "source_path": name,
        "status": "ok",
        "error_class": None,
        "reason": None,
        "entity_count": entity_count,
        "by_layer": by_layer,
        "by_entity_type": by_entity_type,
    }


def _failed_row(name: str, reason: str) -> dict:
    return {
        "source_path": name,
        "status": "failed",
        "error_class": "extraction-crash",
        "reason": reason,
        "entity_count": 0,
        "by_layer": {},
        "by_entity_type": {},
    }


NORMAL_COUNTS = [100, 101, 99, 102, 98, 100, 101, 99, 100, 102, 98, 100]
NORMAL_ROWS = [
    _ok_row(f"normal_{i}.dwg", count, {"0": count - 40, "WALL": 40}, {"LINE": count - 30, "CIRCLE": 30})
    for i, count in enumerate(NORMAL_COUNTS)
]
FAILURE_ROW = _failed_row("e.dwg", "sha256 mismatch for source drawing")
OUTLIER_ROW = _ok_row("f.dwg", 2000, {"0": 1960, "WALL": 40}, {"LINE": 1970, "CIRCLE": 30})


def _all_rows() -> list[dict]:
    return [*NORMAL_ROWS, FAILURE_ROW, OUTLIER_ROW]


def test_load_ledger_skips_malformed_lines(tmp_path, caplog):
    lines = [json.dumps(row) for row in NORMAL_ROWS]
    lines.insert(1, "{not valid json")
    lines.append("[1, 2, 3]")  # valid JSON, not an object -> also malformed
    lines.append("")  # blank line is silently ignored, not malformed
    path = _write_ledger(tmp_path, lines)

    with caplog.at_level("WARNING"):
        rows = corpus_query.load_ledger(path)

    assert len(rows) == len(NORMAL_ROWS)
    assert [row["source_path"] for row in rows] == [row["source_path"] for row in NORMAL_ROWS]
    assert any("2" in message and "malformed" in message for message in caplog.messages)


def test_summarize_counts_files_status_and_entities(tmp_path):
    rows = _all_rows()

    summary = corpus_query.summarize(rows)

    assert summary["files"] == len(NORMAL_ROWS) + 2
    assert summary["ok"] == len(NORMAL_ROWS) + 1
    assert summary["failed"] == 1
    expected_total = sum(row["entity_count"] for row in rows)
    assert summary["total_entities"] == expected_total
    assert summary["by_layer"]["WALL"] == sum(40 for _ in NORMAL_ROWS) + 40
    assert summary["by_layer"]["0"] == sum(count - 40 for count in NORMAL_COUNTS) + 1960
    assert summary["by_entity_type"]["LINE"] == sum(count - 30 for count in NORMAL_COUNTS) + 1970
    assert summary["by_entity_type"]["CIRCLE"] == sum(30 for _ in NORMAL_ROWS) + 30


def test_summarize_handles_empty_ledger():
    summary = corpus_query.summarize([])

    assert summary == {
        "files": 0,
        "ok": 0,
        "failed": 0,
        "total_entities": 0,
        "by_layer": {},
        "by_entity_type": {},
    }


def test_anomalies_flags_failures_and_entity_outliers():
    rows = _all_rows()

    findings = corpus_query.anomalies(rows, entity_z=3.0)

    files_flagged = {finding["file"] for finding in findings}
    assert "e.dwg" in files_flagged
    assert "f.dwg" in files_flagged
    for finding in findings:
        if finding["file"] == "e.dwg":
            assert "sha256 mismatch" in finding["reason"]
        if finding["file"] == "f.dwg":
            assert "outlier" in finding["reason"]
    normal_files = {row["source_path"] for row in NORMAL_ROWS}
    assert not (normal_files & files_flagged)


def test_anomalies_guards_small_sample_size():
    rows = [
        _ok_row("a.dwg", 10, {}, {}),
        _ok_row("b.dwg", 10000, {}, {}),
    ]

    findings = corpus_query.anomalies(rows, entity_z=3.0)

    assert findings == []


def test_anomalies_only_failures_when_no_ok_rows():
    findings = corpus_query.anomalies([FAILURE_ROW], entity_z=3.0)

    assert findings == [{"file": "e.dwg", "reason": "sha256 mismatch for source drawing"}]


def test_cli_summarize_prints_json(tmp_path, capsys):
    lines = [json.dumps(row) for row in _all_rows()]
    path = _write_ledger(tmp_path, lines)

    exit_code = corpus_query.main(["summarize", str(path)])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["files"] == len(NORMAL_ROWS) + 2
    assert payload["ok"] == len(NORMAL_ROWS) + 1
    assert payload["failed"] == 1


def test_cli_anomalies_prints_json(tmp_path, capsys):
    lines = [json.dumps(row) for row in _all_rows()]
    path = _write_ledger(tmp_path, lines)

    exit_code = corpus_query.main(["anomalies", str(path), "--entity-z", "3.0"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    files_flagged = {finding["file"] for finding in payload}
    assert {"e.dwg", "f.dwg"} <= files_flagged
