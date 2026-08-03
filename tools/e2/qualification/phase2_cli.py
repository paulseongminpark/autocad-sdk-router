#!/usr/bin/env python3
"""CLI for the guarded E2 model-assisted jury run."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.e2.qualification.phase2 import build_model_assisted_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the E2 model-assisted wall-hypothesis jury report.")
    parser.add_argument("--first-run", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument(
        "--frozen-transfer-harness",
        type=Path,
        default=Path(r"D:\runs\e2_program\w4\cells\a4_transfer\a4_transfer.py"),
    )
    parser.add_argument("--public-limit", type=int, default=24)
    parser.add_argument("--audit-count", type=int, default=6)
    parser.add_argument("--sealed-holdout-count", type=int, default=12)
    args = parser.parse_args(argv)

    first_spec_path = args.first_run / "experiment_spec.json"
    if not first_spec_path.is_file():
        parser.error(f"phase-1 experiment spec missing: {first_spec_path}")
    first_spec = json.loads(first_spec_path.read_text(encoding="utf-8-sig"))
    spec = {
        "schema": "e2.model_assisted_spec.v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "experiment_id": args.experiment_id,
        "target": "model-assisted adjudication of wall hypotheses without treating model agreement as truth",
        "source": dict(first_spec["source"]),
        "first_run": str(args.first_run.resolve()),
        "frozen_transfer_harness": str(args.frozen_transfer_harness.resolve()),
        "required_interventions": [
            "rotate_37_degrees",
            "translate_large_offset",
            "scale_units_x1000_consistent",
            "strip_layer_names",
            "split_every_segment_at_midpoint",
        ],
        "review_policy": {
            "public_limit": args.public_limit,
            "audit_count": args.audit_count,
            "sealed_holdout_count": args.sealed_holdout_count,
            "holdout_selection": "SHA-256 of drawing_id, hypothesis_id, and lane only",
        },
        "vlm_adapter_paths": [
            r"D:\dev\_ariadne\huggingface\models\qwen25_vl_3b_floorplan_sft\full",
            r"D:\dev\_ariadne\huggingface\models\qwen25_vl_3b_floorplan_grpo\full",
        ],
        "vlm_base_search_roots": [
            r"D:\dev\_ariadne\huggingface\models",
            r"C:\Users\PAUL\.cache\huggingface\hub",
        ],
    }
    result = build_model_assisted_report(spec, args.run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"PASS", "PARTIAL_PASS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
