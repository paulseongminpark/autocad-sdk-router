"""Narrow public interface for E2 instrument qualification.

Phase-one qualification is part of the lightweight evidence boundary.  The
model-assisted phase is optional and owns its heavier numerical/model runtime,
so importing this package must not import that runtime eagerly.
"""

from pathlib import Path
from typing import Any, Mapping

from .engine import build_first_report, qualify


def build_model_assisted_report(
    spec: Mapping[str, Any], run_dir: Path
) -> dict[str, Any]:
    """Load the optional model-assisted phase only when it is requested."""

    from .phase2 import build_model_assisted_report as implementation

    return implementation(spec, run_dir)


__all__ = ["build_first_report", "build_model_assisted_report", "qualify"]
