from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import corpus_batch  # noqa: E402


def test_load_manifest_entries_accepts_list_of_path_records(tmp_path):
    manifest = tmp_path / "manifest.json"
    fixture = tmp_path / "a.dwg"
    fixture.write_bytes(b"DWG")
    manifest.write_text(
        json.dumps(
            [
                {"path": str(fixture), "sha256": "abc123"},
                {"path": str(tmp_path / "b.dwg")},
            ]
        ),
        encoding="utf-8",
    )

    entries = corpus_batch.load_manifest_entries(manifest)

    assert [entry.source_path for entry in entries] == [str(fixture), str(tmp_path / "b.dwg")]
    assert entries[0].expected_sha256 == "abc123"
    assert entries[0].ordinal == 0
    assert entries[1].ordinal == 1
    assert entries[0].input_kind == "manifest"


def test_load_manifest_entries_rejects_non_list_payload(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"files": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="must be a JSON list"):
        corpus_batch.load_manifest_entries(manifest)


def test_expand_glob_entries_sorts_deterministically(tmp_path):
    (tmp_path / "zeta.dwg").write_bytes(b"z")
    (tmp_path / "alpha.dwg").write_bytes(b"a")
    (tmp_path / "skip.txt").write_text("x", encoding="utf-8")

    entries = corpus_batch.expand_glob_entries(str(tmp_path / "*.dwg"))

    assert [Path(entry.source_path).name for entry in entries] == ["alpha.dwg", "zeta.dwg"]
    assert all(entry.input_kind == "glob" for entry in entries)


def test_should_resume_skips_terminal_result_when_not_forced(tmp_path):
    result_path = tmp_path / "result_envelope.json"
    result_path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")

    assert corpus_batch.should_resume_skip(result_path, force=False) is True
    assert corpus_batch.should_resume_skip(result_path, force=True) is False


@pytest.mark.parametrize(
    ("source_path", "status", "reason", "expected"),
    [
        ("C:/x/nope.txt", "failed", "not a dwg", "non-dwg"),
        ("C:/x/a.dwg", "timeout", "worker timed out after 10s", "timeout"),
        ("C:/x/a.dwg", "failed", "password protected drawing", "password_or_proxy"),
        ("C:/x/a.dwg", "failed", "proxy object prevented read", "password_or_proxy"),
        ("C:/x/a.dwg", "failed", "input DWG not found", "unreadable"),
        ("C:/x/a.dwg", "failed", "Unhandled Access Violation", "extraction-crash"),
    ],
)
def test_classify_error_taxonomy(source_path, status, reason, expected):
    assert corpus_batch.classify_error(source_path=source_path, status=status, reason=reason) == expected


def test_build_summary_counts_statuses_and_error_classes():
    results = [
        {"status": "ok", "error_class": None, "timings": {"elapsed_sec": 1.5}},
        {"status": "failed", "error_class": "unreadable", "timings": {"elapsed_sec": 2.0}},
        {"status": "timeout", "error_class": "timeout", "timings": {"elapsed_sec": 5.0}},
    ]

    summary = corpus_batch.build_summary(results, started_at="2026-07-06T00:00:00Z", finished_at="2026-07-06T00:00:10Z")

    assert summary["total_inputs"] == 3
    assert summary["counts_by_status"] == {"ok": 1, "failed": 1, "timeout": 1}
    assert summary["counts_by_error_class"] == {"unreadable": 1, "timeout": 1}
    assert summary["total_elapsed_sec"] == 8.5


def _live_smoke_dwg() -> str | None:
    configured = os.environ.get("CADOS_CORPUS_BATCH_SMOKE_DWG")
    if configured and os.path.isfile(configured):
        return configured
    fixture = _ROOT / "tests" / "fixtures" / "native_sample.dwg"
    if fixture.is_file():
        return str(fixture)
    return None


def _live_smoke_available() -> bool:
    return os.environ.get("CADOS_LIVE") == "1" and _live_smoke_dwg() is not None


def _live_smoke_skip_reason() -> str:
    reasons = []
    if os.environ.get("CADOS_LIVE") != "1":
        reasons.append("CADOS_LIVE!=1")
    if _live_smoke_dwg() is None:
        reasons.append("no smoke dwg available")
    return "corpus batch live smoke skipped: " + ", ".join(reasons)


@pytest.mark.skipif(not _live_smoke_available(), reason=_live_smoke_skip_reason())
def test_corpus_batch_live_smoke(tmp_path):
    dwg_path = _live_smoke_dwg()
    assert dwg_path is not None
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps([{"path": dwg_path}]), encoding="utf-8")
    out_dir = tmp_path / "run"

    cmd = (
        f'set PYTHONUTF8=1 && "{sys.executable}" -X utf8 "{_TOOLS / "corpus_batch.py"}" '
        f'--manifest "{manifest_path}" --out-dir "{out_dir}" --timeout-sec 180'
    )
    proc = subprocess.run(
        ["cmd.exe", "/d", "/s", "/c", cmd],
        cwd=_ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["total_inputs"] == 1
    assert summary["counts_by_status"]["ok"] == 1
