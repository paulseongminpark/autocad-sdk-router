from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.e2.corpus_qualification import BLOCKED, PARTIAL, build_qualification  # noqa: E402


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _native(path: Path, source_hash: str, entity_count: int) -> None:
    entities = [
        {
            "handle": str(index + 1),
            "class": "AcDbLine",
            "dxf_name": "LINE",
            "geometry": {"kind": "line"},
            "source": {"decoded": True},
        }
        for index in range(entity_count)
    ]
    _write_json(
        path,
        {
            "schema": "ariadne.dwg_graph_ir.v1",
            "coverage_level": "native_full",
            "source": {"sha256": source_hash},
            "database": {"units": {"insunits": 4}},
            "entities": entities,
            "block_definitions": [],
            "layouts": [{}, {}],
            "xrefs": [],
            "diagnostics": {
                "errors": [],
                "warnings": [],
                "coverage": {
                    "match": True,
                    "sections_present": ["entities", "xrefs"],
                    "sections_skipped": ["groups"],
                    "section_status": {"proxy_objects": "partial"},
                },
            },
        },
    )
    _write_json(
        path.parent / "validation_report.json",
        {
            "schema": "ariadne.validation_report.v1",
            "validation_id": f"fixture-{source_hash[:8]}",
            "status": "pass",
            "summary": {
                "gates_total": 14,
                "gates_passed": 7,
                "gates_failed": 0,
                "gates_skipped": 7,
                "gates_blocked": 0,
            },
            "errors": [],
            "warnings": [],
        },
    )


def test_build_qualification_joins_hash_evidence_and_keeps_pair_as_candidate(tmp_path: Path):
    origin = tmp_path / "origin"
    source = tmp_path / "source"
    approval = Path("01 건축(사업승인)") / "건축" / "A30 test 평면도.dwg"
    implementation = Path("01_건축(실시설계)") / "01.DWG" / "A30 test 평면도.dwg"
    for root in (origin, source):
        (root / approval).parent.mkdir(parents=True, exist_ok=True)
        (root / implementation).parent.mkdir(parents=True, exist_ok=True)
        (root / approval).write_bytes(b"approval")
        (root / implementation).write_bytes(b"implementation")

    prior = tmp_path / "prior"
    prior.mkdir()
    paths = [source / approval, source / implementation]
    manifest = [{"path": str(path), "sha256": _hash(path)} for path in paths]
    _write_json(prior / "manifest.json", manifest)
    ledger_rows = [
        {
            "status": "ok",
            "source_sha256_match": True,
            "entity_count": count,
            "layers": 1,
            "blocks": 1,
            "layouts": 2,
            "insunits": "Millimeters",
            "entities_truncated": False,
            "op_status": {"inspect.database.summary": "ok"},
        }
        for count in (1, 2)
    ]
    (prior / "ledger.jsonl").write_text("\n".join(json.dumps(row) for row in ledger_rows) + "\n", encoding="utf-8")

    native = tmp_path / "native"
    _native(native / "approval" / "dwg_graph_ir.json", _hash(paths[0]), 1)
    _native(native / "implementation" / "dwg_graph_ir.json", _hash(paths[1]), 2)
    run = tmp_path / "run"
    (run / "PREREG.md").parent.mkdir(parents=True, exist_ok=True)
    (run / "PREREG.md").write_text("fixture", encoding="utf-8")

    receipt = build_qualification(
        source,
        origin,
        prior,
        native,
        run,
        [approval.name],
        expected_dwg_count=2,
    )

    assert receipt["status"] == PARTIAL
    assert receipt["headline"]["prior_crosswalk_pass"] == 2
    assert receipt["headline"]["exact_filename_pair_candidates"] == 1
    assert receipt["headline"]["pilot_validation_pass_count"] == 2
    assert any(row["gate"] == "pilot_ir_validation" and row["status"] == "PASS" for row in receipt["gates"])
    pair = json.loads((run / "pair_candidates.json").read_text(encoding="utf-8"))["pairs"][0]
    assert pair["status"] == "EXACT_FILENAME_CANDIDATE_NOT_TRUTH"
    assert pair["same_content"] is False
    assert (run / "qualification_receipt.json").is_file()


def test_origin_copy_mismatch_blocks(tmp_path: Path):
    origin = tmp_path / "origin"
    source = tmp_path / "source"
    relative = Path("01 건축(사업승인)") / "x.dwg"
    (origin / relative).parent.mkdir(parents=True)
    (source / relative).parent.mkdir(parents=True)
    (origin / relative).write_bytes(b"origin")
    (source / relative).write_bytes(b"changed")
    prior = tmp_path / "prior"
    prior.mkdir()
    _write_json(prior / "manifest.json", [{"path": str(source / relative), "sha256": _hash(source / relative)}])
    (prior / "ledger.jsonl").write_text(
        json.dumps({"status": "ok", "source_sha256_match": True, "entity_count": 1}) + "\n",
        encoding="utf-8",
    )
    native = tmp_path / "native"
    _native(native / "one" / "dwg_graph_ir.json", _hash(source / relative), 1)
    run = tmp_path / "run"
    run.mkdir()
    (run / "PREREG.md").write_text("fixture", encoding="utf-8")

    receipt = build_qualification(source, origin, prior, native, run, ["missing.dwg"], 1)

    assert receipt["status"] == BLOCKED
    assert any(row["gate"] == "origin_copy_integrity" and row["status"] == BLOCKED for row in receipt["gates"])
