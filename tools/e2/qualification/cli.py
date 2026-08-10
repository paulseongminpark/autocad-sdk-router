#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from tools.e2.qualification.engine import (
        build_first_report,
        validate_downstream_qualification_receipt,
    )
else:
    from .engine import build_first_report, validate_downstream_qualification_receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the evidence-bound E2 first report.")
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--native-ir", type=Path, required=True)
    parser.add_argument("--adapter-ir", type=Path, required=True)
    parser.add_argument("--world-ir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    spec = {
        "schema": "e2.experiment_spec.v1",
        "experiment_id": args.experiment_id,
        "created_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "target": "wall detection as a probe of convention-robust drawing semantics",
        "source": {
            "path": str(args.source),
            "sha256": args.source_sha256.lower(),
            "read_only": True,
        },
        "evidence": {
            "native_ir": str(args.native_ir),
            "adapter_ir": str(args.adapter_ir),
            "world_ir": str(args.world_ir),
        },
        "interventions": [
            "xclip_on_vs_raw_expansion",
            "rotate_37_degrees",
            "translate_large_offset",
            "scale_coordinates_x1000_consistent",
            "scale_coordinates_x1000_naive",
            "strip_layer_names",
            "split_every_segment_at_midpoint",
        ],
    }
    result = build_first_report(spec, args.run_dir)
    result["downstream_receipt_validation"] = validate_downstream_qualification_receipt(
        Path(result["receipt"])
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["downstream_receipt_validation"]["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
