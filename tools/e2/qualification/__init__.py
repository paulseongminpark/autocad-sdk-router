"""Narrow public interface for E2 instrument qualification.

Phase-one qualification is part of the lightweight evidence boundary.  The
former model-assisted host runner is retired: its public entry point lazily
loads only a fail-closed receipt writer and never imports a model runtime.
"""

from pathlib import Path
from typing import Any, Mapping

from .engine import build_first_report, qualify


def build_model_assisted_report(
    spec: Mapping[str, Any], run_dir: Path
) -> dict[str, Any]:
    """Record that model-assisted execution requires a sealed executor."""

    from .phase2 import build_model_assisted_report as implementation

    return implementation(spec, run_dir)


__all__ = ["build_first_report", "build_model_assisted_report", "qualify"]
