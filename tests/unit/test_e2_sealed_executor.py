from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tools.e2 import company_gnn_canonical_frame
from tools.e2 import company_gnn_intervention
from tools.e2 import company_pair_intervention
from tools.e2.qualification.sealed_executor import refusal_receipt


REPO = Path(__file__).resolve().parents[2]


def test_shared_refusal_receipt_has_one_valid_schema() -> None:
    receipt = refusal_receipt(
        requested_receipt_schema="e2.legacy_receipt.v1",
        experiment_id=None,
        entrypoint="tests.legacy.run",
        claim_boundary="sealed execution required",
    )
    schema = json.loads(
        (REPO / "schemas" / "e2_sealed_execution_refusal.v1.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert list(Draft202012Validator(schema).iter_errors(receipt)) == []
    assert receipt["experiment_id"] is None
    assert receipt["input_accessed"] is False
    assert receipt["output_accessed"] is False


@pytest.mark.parametrize(
    ("module", "run_args"),
    [
        (company_pair_intervention, (Path("unused-run"), Path("unused-prereg"))),
        (company_gnn_intervention, (Path("unused-run"), Path("unused-prereg"))),
        (company_gnn_canonical_frame, (Path("unused-run"), Path("unused-prereg"))),
    ],
)
def test_retired_company_runner_refuses_even_without_experiment_id(module, run_args) -> None:
    receipt = module.run({}, *run_args)

    assert receipt["status"] == "BLOCKED"
    assert receipt["reason_code"] == "SEALED_DOWNSTREAM_EXECUTOR_REQUIRED"
    assert receipt["experiment_id"] is None
    assert receipt["input_accessed"] is False


@pytest.mark.parametrize(
    "module",
    [
        company_pair_intervention,
        company_gnn_intervention,
        company_gnn_canonical_frame,
    ],
)
def test_retired_company_cli_does_not_read_missing_spec(
    module,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_dir = tmp_path / "run"
    exit_code = module.main(
        [
            "--spec",
            str(tmp_path / "missing-spec.json"),
            "--run-dir",
            str(run_dir),
            "--prereg",
            str(tmp_path / "missing-prereg.json"),
        ]
    )
    receipt = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert receipt["status"] == "BLOCKED"
    assert receipt["experiment_id"] is None
    assert receipt["input_accessed"] is False
    assert not run_dir.exists()
