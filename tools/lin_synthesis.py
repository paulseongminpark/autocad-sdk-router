from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


def _format_lin_number(value: Any) -> str:
    # Match the .pat synthesis rule: clamp floating-point noise to 0 and never
    # emit scientific notation, which AutoCAD sidecar parsers do not accept.
    v = float(value)
    if abs(v) < 1e-9:
        return "0"
    text = format(v, ".10f").rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def _complex_segment_reason(segment: dict[str, Any]) -> str | None:
    if "text" in segment and segment.get("text") is not None:
        return "text segments are not supported in lin_synthesis v1"
    if "shape" in segment and segment.get("shape") is not None:
        return "shape segments are not supported in lin_synthesis v1"
    return None


def _pattern_items(record: dict[str, Any]) -> tuple[list[str] | None, str | None]:
    items: list[str] = []
    for dash in record.get("dashes") or []:
        reason = _complex_segment_reason(dash)
        if reason is not None:
            return None, reason
        items.append(_format_lin_number(dash.get("length", 0.0)))
    return items, None


def synthesize_lin_file(
    linetype_records: Iterable[dict[str, Any]],
    out_path: str | Path,
) -> dict[str, list[Any]]:
    """Write a batch .lin sidecar from extractor-emitted linetype rows.

    Contract:
    {
      "name": str,
      "description": str,
      "pattern_length": float,
      "is_scaled_to_fit": bool,
      "dashes": [{"length": float, "text"?: Any, "shape"?: Any}],
    }

    V1 writes only simple numeric segments. Any record containing a text or
    shape segment is deferred and reported back to the caller instead of being
    partially emitted.
    """

    written: list[str] = []
    deferred: list[dict[str, str]] = []
    lines: list[str] = []

    for record in linetype_records:
        name = str(record.get("name") or "").strip()
        description = str(record.get("description") or "")
        items, reason = _pattern_items(record)
        if reason is not None:
            deferred.append({"name": name, "reason": reason})
            continue

        lines.append(f"*{name},{description}")
        lines.append(",".join(["A", *(items or [])]))
        written.append(name)

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(lines)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8", newline="\n")
    return {"written": written, "deferred": deferred}
