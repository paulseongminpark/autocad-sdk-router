import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from corpus_discovery import discover, infer_family, rank_diverse, size_bucket


def test_infer_family_dash_token():
    fam = infer_family("A30-001~013 x.dwg")
    assert fam["stem"] == "a"
    assert fam["token"] == "A30-001"


def test_infer_family_no_delimiter_letters():
    fam = infer_family("input0616 z.dwg")
    assert fam["stem"] == "input"


def test_size_bucket():
    assert size_bucket(500_000) == "small"
    assert size_bucket(2_000_000) == "medium"
    assert size_bucket(9_000_000) == "large"


def test_discover_ignores_non_matching_ext(tmp_path):
    (tmp_path / "A30-001~013 x.dwg").write_bytes(b"abc")
    (tmp_path / "A30-021 y.dwg").write_bytes(b"abc")
    (tmp_path / "input0616 z.dwg").write_bytes(b"abc")
    (tmp_path / "note.txt").write_bytes(b"abc")

    results = discover([str(tmp_path)])

    assert len(results) == 3
    names = {r["name"] for r in results}
    assert names == {"A30-001~013 x.dwg", "A30-021 y.dwg", "input0616 z.dwg"}


def test_rank_diverse_spans_multiple_families(tmp_path):
    (tmp_path / "A30-001~013 x.dwg").write_bytes(b"abc")
    (tmp_path / "A30-021 y.dwg").write_bytes(b"abc")
    (tmp_path / "input0616 z.dwg").write_bytes(b"abc")

    results = discover([str(tmp_path)])
    chosen = rank_diverse(results, 2)

    assert len(chosen) == 2
    assert len({c["family_stem"] for c in chosen}) >= 2
