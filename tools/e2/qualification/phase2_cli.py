#!/usr/bin/env python3
"""Emit the fail-closed receipt for the unavailable sealed E2 executor."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.e2.qualification.phase2 import build_model_assisted_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Record that phase-2 model execution is blocked until a sealed executor "
            "is available. This command never loads or runs a model."
        )
    )
    parser.add_argument("--first-run", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--experiment-id", required=True)
    args = parser.parse_args(argv)

    first_spec_path = args.first_run / "experiment_spec.json"
    if not first_spec_path.is_file():
        parser.error(f"phase-1 experiment spec missing: {first_spec_path}")
    first_spec = json.loads(first_spec_path.read_text(encoding="utf-8-sig"))
    spec = {
        "experiment_id": args.experiment_id,
        "source": dict(first_spec["source"]),
        "first_run": str(args.first_run.resolve()),
    }
    result = build_model_assisted_report(spec, args.run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"PASS", "PARTIAL_PASS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
