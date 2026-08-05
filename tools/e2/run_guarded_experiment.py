#!/usr/bin/env python3
"""Official fail-closed launcher for new E2 experiment commands."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import experiment_guard


def _load_probe(path: Path | None) -> Mapping[str, Any] | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_guarded(
    *,
    required_observables: Iterable[str],
    command: Sequence[str],
    candidate: str = "auto",
    conclusion: str = "exploratory",
    probe_output: Mapping[str, Any] | None = None,
    allow_empty: bool = False,
    independent_oracle_receipt: Mapping[str, Any] | None = None,
    target_population_oracle: Mapping[str, Any] | None = None,
    model_input_output: Mapping[str, Any] | None = None,
    receipt_path: Path | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    decision = experiment_guard.qualify(
        required_observables=required_observables,
        candidate=candidate,
        conclusion=conclusion,
    )
    if probe_output is not None and decision["status"] == experiment_guard.NEEDS_PROBE:
        decision = experiment_guard.verify_probe(
            decision,
            probe_output,
            allow_empty=allow_empty,
            independent_oracle_receipt=independent_oracle_receipt,
            target_population_oracle=target_population_oracle,
            model_input_output=model_input_output,
        )

    result = {
        "schema": "ariadne.e2.guarded_experiment_run.v1",
        "guard": decision,
        "executed": False,
        "command": list(command),
        "command_exit_code": None,
    }
    if receipt_path is not None:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    if decision["status"] != experiment_guard.READY:
        return result
    if not command:
        result["guard"] = {
            **decision,
            "status": experiment_guard.REDESIGN,
            "exit_code": experiment_guard.EXIT_CODES[experiment_guard.REDESIGN],
            "reason_code": "NO_EXPERIMENT_COMMAND",
            "reason": "The instrument is qualified, but no experiment command was supplied.",
        }
        return result

    completed = runner(list(command), check=False)
    result["executed"] = True
    result["command_exit_code"] = int(completed.returncode)
    if receipt_path is not None:
        receipt_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return result


def _requirements(values: Iterable[str]) -> list[str]:
    flattened: list[str] = []
    for value in values:
        flattened.extend(piece.strip() for piece in value.split(",") if piece.strip())
    return flattened


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an E2 experiment command only after instrument qualification."
    )
    parser.add_argument("--require", action="append", default=[], help="Observable token; repeat or comma-separate.")
    parser.add_argument(
        "--candidate",
        default="auto",
        choices=["auto", "database_summary", "native_graph", "native_graph_worldir_segments"],
    )
    parser.add_argument(
        "--conclusion",
        default="exploratory",
        choices=["exploratory", "direction_changing", "absence", "impossibility"],
    )
    parser.add_argument("--probe-ir", type=Path)
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--independent-oracle-receipt", type=Path)
    parser.add_argument("--target-population-oracle", type=Path)
    parser.add_argument("--model-input-ir", type=Path)
    parser.add_argument(
        "--receipt-output",
        type=Path,
        help="Write the guard decision before execution and the final run receipt after execution.",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    result = run_guarded(
        required_observables=_requirements(args.require),
        command=command,
        candidate=args.candidate,
        conclusion=args.conclusion,
        probe_output=_load_probe(args.probe_ir),
        allow_empty=args.allow_empty,
        independent_oracle_receipt=_load_probe(args.independent_oracle_receipt),
        target_population_oracle=_load_probe(args.target_population_oracle),
        model_input_output=_load_probe(args.model_input_ir),
        receipt_path=args.receipt_output,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["executed"]:
        return int(result["command_exit_code"])
    return int(result["guard"]["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
