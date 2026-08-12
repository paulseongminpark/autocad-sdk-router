from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import corpus_batch  # noqa: E402
import cadctl  # noqa: E402
from operation_provenance import build_execution_receipt  # noqa: E402


def _canonical_read_envelope(operation: str, path: Path) -> dict:
    resolved = path.resolve()
    result_path = resolved.with_name("router_read_result.dwg")
    result_path.write_bytes(resolved.read_bytes())
    return {
        "schema": "ariadne.cadctl.run_operation.v1",
        "status": "ok",
        "executed": True,
        "result": {},
        "execution_receipt": build_execution_receipt(
            authorized_operation=operation,
            authorized_write_mode="read",
            executed=True,
            reported_status="ok",
            executed_operation=operation,
            executed_write_mode="read",
            router_input_path=str(resolved),
            original_path=str(resolved),
            original_sha256_before="a" * 64,
            original_sha256_after="a" * 64,
            baseline_path=str(resolved),
            baseline_sha256="a" * 64,
            baseline_sha256_after="a" * 64,
            result_path=str(result_path),
            result_sha256="a" * 64,
            result_kind="router_working_copy",
            process_exit_code=0,
            engine_exit_code=0,
            engine_output_exit_code=0,
            native_status="ok",
            native_schema="ariadne.autocad_native_job_result.v1",
            native_engine="native_objectarx",
            native_operation=operation,
            native_result_source="file",
            native_result_is_object=True,
            native_error_code=None,
            native_result_path=str(result_path) + ".native-result.json",
            native_result_sha256="c" * 64,
            router_status="PASS",
            router_schema="ariadne.autocad_router_run.v2",
            executed_route="dwg_truth_autocad",
            timed_out=False,
            input_kind="staged_copy",
            save_command_issued=False,
            router_working_sha256_before="a" * 64,
            router_working_sha256_after="a" * 64,
        ),
    }


def test_parse_ops_default_when_no_args():
    ops = corpus_batch.parse_ops()
    assert ops == corpus_batch.DEFAULT_OPS
    assert corpus_batch.op_ids(ops) == corpus_batch.DEFAULT_OP_IDS


def test_parse_ops_comma_separated_ids():
    ops = corpus_batch.parse_ops(ops_text="inspect.layers,inspect.blocks")
    assert corpus_batch.op_ids(ops) == ["inspect.layers", "inspect.blocks"]
    assert all(op["args"] == {} for op in ops)


def test_parse_ops_rejects_empty_comma_list():
    with pytest.raises(ValueError, match="no operation ids"):
        corpus_batch.parse_ops(ops_text=" , ")


def test_parse_ops_rejects_both_text_and_file(tmp_path):
    ops_file = tmp_path / "ops.json"
    ops_file.write_text(json.dumps(["inspect.layers"]), encoding="utf-8")
    with pytest.raises(ValueError, match="not both"):
        corpus_batch.parse_ops(ops_text="inspect.layers", ops_file=str(ops_file))


def test_parse_ops_file_accepts_strings_and_objects(tmp_path):
    ops_file = tmp_path / "ops.json"
    ops_file.write_text(
        json.dumps(
            [
                "inspect.layers",
                {"id": "inspect.blocks", "args": {"limit": 10}},
            ]
        ),
        encoding="utf-8",
    )
    ops = corpus_batch.parse_ops(ops_file=str(ops_file))
    assert corpus_batch.op_ids(ops) == ["inspect.layers", "inspect.blocks"]
    assert ops[1]["args"] == {"limit": 10}


def test_arg_parser_ops_default_preservation():
    parser = corpus_batch._build_arg_parser()
    args = parser.parse_args(["--manifest", "m.json"])
    ops = corpus_batch.parse_ops(args.ops, args.ops_file)
    assert ops == corpus_batch.DEFAULT_OPS


def test_arg_parser_ops_override():
    parser = corpus_batch._build_arg_parser()
    args = parser.parse_args(
        ["--manifest", "m.json", "--ops", "inspect.layers,inspect.blocks"]
    )
    ops = corpus_batch.parse_ops(args.ops, args.ops_file)
    assert corpus_batch.op_ids(ops) == ["inspect.layers", "inspect.blocks"]


def test_result_envelope_records_ops_requested():
    entry = corpus_batch.CorpusEntry(
        ordinal=0,
        source_path="C:/x/a.dwg",
        expected_sha256=None,
        input_kind="manifest",
    )
    requested = ["inspect.layers", "inspect.blocks"]
    payload = corpus_batch._result_envelope(
        entry=entry,
        run_dir=Path("/tmp/run"),
        status="ok",
        error_class=None,
        source_sha256="abc",
        staged_path="/tmp/run/source_staged.dwg",
        ops_requested=requested,
        ops_run=[],
        started_at="2026-07-07T00:00:00Z",
        finished_at="2026-07-07T00:00:01Z",
        elapsed_sec=1.0,
    )
    assert payload["ops_requested"] == requested


def test_worker_forces_read_mode_and_records_canonical_result(tmp_path):
    source = tmp_path / "sample.dwg"
    source.write_bytes(b"DWG")
    run_dir = tmp_path / "case"
    run_dir.mkdir()
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "entry": corpus_batch.CorpusEntry(
                    ordinal=0,
                    source_path=str(source),
                    expected_sha256=None,
                    input_kind="manifest",
                ).to_json(),
                "run_dir": str(run_dir),
                "ops": [{"id": "inspect.layers", "args": {}}],
                "resume_rerun_reason": None,
            }
        ),
        encoding="utf-8",
    )
    calls = []

    class FakeCad:
        def __init__(self, router_home=None):
            pass

        def run_operation(self, operation, **kwargs):
            calls.append({"operation": operation, **kwargs})
            return _canonical_read_envelope(operation, Path(kwargs["dwg_path"]))

    with patch.object(cadctl, "Cad", FakeCad):
        assert corpus_batch._worker_impl(request_path) == 0

    assert calls[0]["write_mode"] == "read"
    payload = json.loads((run_dir / corpus_batch.RESULT_FILE).read_text(encoding="utf-8"))
    op_record = payload["ops_run"][0]
    assert op_record["status"] == "ok"
    assert op_record["result_path"] == str(
        (run_dir / "router_read_result.dwg").resolve()
    )
    assert op_record["result_sha256"] == "a" * 64


def test_operation_record_fails_closed_when_executed_receipt_is_missing():
    record = corpus_batch._operation_record(
        {"id": "inspect.layers", "args": {}},
        {"status": "ok", "executed": True, "result": {}},
        0.1,
    )

    assert record["status"] != "ok"
    assert "receipt" in (record.get("reason") or "").lower()


def test_recorded_op_ids_backward_compat_without_ops_requested():
    envelope = {"status": "ok", "ops_run": [{"operation": "inspect.layers"}]}
    assert corpus_batch.recorded_op_ids_from_envelope(envelope) == corpus_batch.DEFAULT_OP_IDS


def test_recorded_op_ids_uses_ops_requested_when_present():
    envelope = {
        "status": "ok",
        "ops_requested": ["inspect.layers", "inspect.blocks"],
    }
    assert corpus_batch.recorded_op_ids_from_envelope(envelope) == [
        "inspect.layers",
        "inspect.blocks",
    ]


def test_ops_set_covers_superset_allows_skip():
    recorded = corpus_batch.DEFAULT_OP_IDS
    requested = ["inspect.layers"]
    assert corpus_batch.ops_set_covers(recorded, requested) is True


def test_ops_set_covers_missing_op_requires_rerun():
    recorded = ["inspect.layers"]
    requested = ["inspect.layers", "inspect.blocks"]
    assert corpus_batch.ops_set_covers(recorded, requested) is False


@pytest.mark.parametrize(
    ("envelope", "requested_ops", "expected_skip"),
    [
        (
            {"status": "ok"},
            corpus_batch.DEFAULT_OPS,
            True,
        ),
        (
            {"status": "ok", "ops_requested": corpus_batch.DEFAULT_OP_IDS},
            corpus_batch.DEFAULT_OPS,
            True,
        ),
        (
            {"status": "ok", "ops_requested": ["inspect.layers"]},
            [{"id": "inspect.layers", "args": {}}],
            True,
        ),
        (
            {"status": "ok", "ops_requested": ["inspect.layers"]},
            corpus_batch.DEFAULT_OPS,
            False,
        ),
        (
            {"status": "ok"},
            [{"id": "inspect.blocks", "args": {}}],
            False,
        ),
        (
            {"status": "running"},
            corpus_batch.DEFAULT_OPS,
            False,
        ),
    ],
)
def test_should_resume_skip_ops_aware(
    tmp_path, envelope, requested_ops, expected_skip
):
    result_path = tmp_path / "result_envelope.json"
    result_path.write_text(json.dumps(envelope), encoding="utf-8")
    assert (
        corpus_batch.should_resume_skip(
            result_path, force=False, requested_ops=requested_ops
        )
        is expected_skip
    )


def test_resume_rerun_reason_when_ops_changed(tmp_path):
    envelope = {
        "status": "ok",
        "ops_requested": ["inspect.layers"],
    }
    requested = corpus_batch.DEFAULT_OPS
    reason = corpus_batch.resume_rerun_reason(envelope, requested)
    assert reason is not None
    assert "ops_requested changed" in reason
    assert "inspect.layers" in reason


def test_resume_rerun_reason_none_when_ops_match():
    envelope = {
        "status": "ok",
        "ops_requested": corpus_batch.DEFAULT_OP_IDS,
    }
    assert corpus_batch.resume_rerun_reason(envelope, corpus_batch.DEFAULT_OPS) is None


def test_run_batch_reruns_when_ops_changed(tmp_path):
    dwg = tmp_path / "sample.dwg"
    dwg.write_bytes(b"DWG")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([{"path": str(dwg)}]), encoding="utf-8")
    out_dir = tmp_path / "run"
    out_dir.mkdir()
    case_dir = out_dir / "0000_sample"
    case_dir.mkdir()
    old_envelope = {
        "schema": corpus_batch.RESULT_SCHEMA,
        "status": "ok",
        "ops_run": [{"operation": "inspect.layers", "status": "ok"}],
    }
    (case_dir / corpus_batch.RESULT_FILE).write_text(
        json.dumps(old_envelope), encoding="utf-8"
    )

    new_ops = [{"id": "inspect.blocks", "args": {}}]
    fake_result = {
        "status": "ok",
        "ops_requested": ["inspect.blocks"],
        "ops_run": [{"operation": "inspect.blocks", "status": "ok"}],
        "timings": {"elapsed_sec": 0.1},
    }

    with patch.object(corpus_batch, "_run_entry_parent", return_value=fake_result) as run_parent:
        summary = corpus_batch.run_batch(
            manifest_path=str(manifest),
            glob_pattern=None,
            out_dir=str(out_dir),
            force=False,
            timeout_sec=30,
            ops=new_ops,
        )

    run_parent.assert_called_once()
    call_kwargs = run_parent.call_args.kwargs
    assert call_kwargs["ops"] == new_ops
    assert call_kwargs["resume_rerun_reason"] is not None
    assert "ops_requested changed" in call_kwargs["resume_rerun_reason"]
    assert summary["total_inputs"] == 1


def test_run_batch_skips_when_ops_cover_requested(tmp_path):
    dwg = tmp_path / "sample.dwg"
    dwg.write_bytes(b"DWG")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([{"path": str(dwg)}]), encoding="utf-8")
    out_dir = tmp_path / "run"
    out_dir.mkdir()
    case_dir = out_dir / "0000_sample"
    case_dir.mkdir()
    old_envelope = {
        "schema": corpus_batch.RESULT_SCHEMA,
        "status": "ok",
        "ops_requested": corpus_batch.DEFAULT_OP_IDS,
        "ops_run": [],
        "timings": {"elapsed_sec": 1.0},
    }
    (case_dir / corpus_batch.RESULT_FILE).write_text(
        json.dumps(old_envelope), encoding="utf-8"
    )

    with patch.object(corpus_batch, "_run_entry_parent") as run_parent:
        summary = corpus_batch.run_batch(
            manifest_path=str(manifest),
            glob_pattern=None,
            out_dir=str(out_dir),
            force=False,
            timeout_sec=30,
            ops=[{"id": "inspect.layers", "args": {}}],
        )

    run_parent.assert_not_called()
    assert summary["total_inputs"] == 1
    result = json.loads(
        (case_dir / corpus_batch.RESULT_FILE).read_text(encoding="utf-8")
    )
    assert result.get("resumed") is True
