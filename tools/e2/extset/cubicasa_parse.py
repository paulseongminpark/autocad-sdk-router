"""Parse the declared CubiCasa SVG subset into SEGMENT-IR v1.

Each supported polygon or rectangle is represented by its boundary edges.  In
particular, a wall polygon produces one ``poly-edge`` segment per boundary
edge; the filled polygon itself is not emitted as a separate IR object.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


FORMAT_SPEC = {
    "revision": "cubicasa-svg-v1-fixture",
    "elements": ("polygon", "rect"),
    "class_attribute": "class",
    "assumed_classes": {
        "wall": "wall",
        "room": "other",
        "door": "opening",
        "window": "opening",
    },
}

LIMITS = (
    "PASS_WITH_DEFERRAL: only the explicit FORMAT_SPEC subset and authored "
    "fixture are validated; real CubiCasa5K SVG data is not yet validated. "
    "Wall edges are not deduplicated when wall polygons share a border."
)

_NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def _number(value: str) -> float:
    return float(value)


def _polygon_points(value: str) -> list[list[float]]:
    values = [_number(item) for item in _NUMBER.findall(value)]
    if len(values) < 6 or len(values) % 2:
        return []
    return [[values[index], values[index + 1]] for index in range(0, len(values), 2)]


def _rect_points(element: ET.Element) -> list[list[float]]:
    try:
        x = _number(element.attrib.get("x", "0"))
        y = _number(element.attrib.get("y", "0"))
        width = _number(element.attrib["width"])
        height = _number(element.attrib["height"])
    except (KeyError, ValueError):
        return []
    return [[x, y], [x + width, y], [x + width, y + height], [x, y + height]]


def _label_for(element: ET.Element, label_map: dict[str, str]) -> tuple[str, str]:
    classes = element.attrib.get(FORMAT_SPEC["class_attribute"], "").split()
    for class_name in classes:
        if class_name in label_map:
            return class_name, label_map[class_name]
    return (classes[0] if classes else "unclassified"), "unknown"


def parse(svg_path: str | Path, label_map: dict[str, str] | None = None) -> dict:
    """Return SEGMENT-IR v1 for the explicit SVG subset in FORMAT_SPEC."""
    path = Path(svg_path)
    labels = dict(FORMAT_SPEC["assumed_classes"])
    if label_map:
        labels.update(label_map)

    root = ET.parse(path).getroot()
    segments = []
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag not in FORMAT_SPEC["elements"]:
            continue
        if tag == "polygon":
            points = _polygon_points(element.attrib.get("points", ""))
        else:
            points = _rect_points(element)
        if not points:
            continue

        layer, label = _label_for(element, labels)
        for start, end in zip(points, points[1:] + points[:1]):
            segments.append(
                {
                    "sid": f"s{len(segments) + 1:04d}",
                    "handle": None,
                    "pts": [start, end],
                    "layer": layer,
                    "kind": "poly-edge",
                    "label": label,
                    "source": "cubicasa",
                }
            )

    return {
        "ir": "seg.v1",
        "drawing_id": path.stem,
        "units": "unknown",
        "scale_mm_per_unit": None,
        "segments": segments,
    }


def _selftest() -> None:
    fixture = Path(__file__).with_name("fixtures_cubicasa.svg")
    result = parse(fixture)
    labels = [segment["label"] for segment in result["segments"]]
    assert result["ir"] == "seg.v1"
    assert len(result["segments"]) == 16
    assert labels.count("wall") == 8
    assert labels.count("other") == 4
    assert labels.count("opening") == 4
    assert all(segment["kind"] == "poly-edge" for segment in result["segments"])
    print("selftest PASS: 16 polygon boundary edges (8 wall, 4 other, 4 opening)")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        _selftest()
    else:
        raise SystemExit("usage: cubicasa_parse.py --selftest")
