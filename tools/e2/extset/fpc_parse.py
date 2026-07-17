"""Parse the explicitly supported FloorPlanCAD SVG subset into SEG-IR v1."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree


FORMAT_SPEC = {
    "elements": {
        "line": {"kind": "line", "coordinates": ("x1", "y1", "x2", "y2")},
        "polyline": {"kind": "poly-edge", "coordinates": "points"},
        "path": {"kind": "line", "commands": ("M", "L")},
    },
    "semantic_class_attributes": ("class", "data-class"),
    "semantic_classes": ("wall", "opening", "other"),
}

_NUMBER_RE = re.compile(r"[-+]?(?:\d+\.?(?:\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
_PATH_TOKEN_RE = re.compile(r"[ML]|[-+]?(?:\d+\.?(?:\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def _number(value: str) -> float:
    return float(value)


def _class_name(element: ElementTree.Element) -> str:
    for attribute in FORMAT_SPEC["semantic_class_attributes"]:
        value = element.get(attribute)
        if value:
            return value
    return ""


def _polyline_points(value: str) -> list[list[float]]:
    numbers = [_number(token) for token in _NUMBER_RE.findall(value)]
    if len(numbers) < 4 or len(numbers) % 2:
        raise ValueError("polyline points must contain at least two coordinate pairs")
    return [[numbers[index], numbers[index + 1]] for index in range(0, len(numbers), 2)]


def _path_points(value: str) -> list[list[float]]:
    tokens = _PATH_TOKEN_RE.findall(value)
    if "".join(tokens) != re.sub(r"[\s,]+", "", value):
        raise ValueError("path contains unsupported syntax; only M/L commands are supported")

    points: list[list[float]] = []
    command = None
    index = 0
    while index < len(tokens):
        if tokens[index] in FORMAT_SPEC["elements"]["path"]["commands"]:
            command = tokens[index]
            index += 1
        if command is None or index + 1 >= len(tokens):
            raise ValueError("path must contain coordinate pairs after M/L commands")
        if tokens[index] in ("M", "L") or tokens[index + 1] in ("M", "L"):
            raise ValueError("path must contain complete coordinate pairs")
        points.append([_number(tokens[index]), _number(tokens[index + 1])])
        index += 2
    if len(points) < 2:
        raise ValueError("path must contain at least two points")
    return points


def parse(svg_path: str | Path, label_map=None) -> dict:
    """Return SEG-IR v1 for the subset declared by ``FORMAT_SPEC``."""
    path = Path(svg_path)
    root = ElementTree.parse(path).getroot()
    segments = []

    for element in root.iter():
        name = element.tag.rsplit("}", 1)[-1]
        if name not in FORMAT_SPEC["elements"]:
            continue
        semantic_class = _class_name(element)
        label = label_map(semantic_class) if label_map else "unknown"

        if name == "line":
            values = [_number(element.attrib[attribute])
                      for attribute in FORMAT_SPEC["elements"]["line"]["coordinates"]]
            edges = [[[values[0], values[1]], [values[2], values[3]]]]
        elif name == "polyline":
            points = _polyline_points(element.attrib["points"])
            edges = [[start, end] for start, end in zip(points, points[1:])]
        else:
            points = _path_points(element.attrib["d"])
            edges = [[start, end] for start, end in zip(points, points[1:])]

        for start, end in edges:
            segments.append({
                "sid": f"s{len(segments) + 1:04d}",
                "handle": None,
                "pts": [start, end],
                "layer": semantic_class,
                "kind": FORMAT_SPEC["elements"][name]["kind"],
                "label": label,
                "source": "floorplancad",
            })

    return {
        "ir": "seg.v1",
        "drawing_id": path.stem,
        "units": "unknown",
        "scale_mm_per_unit": None,
        "segments": segments,
    }


def _selftest() -> None:
    fixture = Path(__file__).with_name("fixtures_fpc.svg")
    ir = parse(fixture, label_map=lambda class_name: class_name)
    kind_counts = Counter(segment["kind"] for segment in ir["segments"])
    class_counts = Counter(segment["layer"] for segment in ir["segments"])
    label_counts = Counter(segment["label"] for segment in ir["segments"])
    assert kind_counts == Counter({"line": 8, "poly-edge": 6}), kind_counts
    assert class_counts == Counter({"wall": 6, "opening": 4, "other": 4}), class_counts
    assert label_counts == class_counts, (label_counts, class_counts)
    assert [segment["sid"] for segment in ir["segments"]] == [
        f"s{index:04d}" for index in range(1, 15)
    ]
    print("PASS: 14 segments; kinds=line:8, poly-edge:6; classes=wall:6, opening:4, other:4")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        _selftest()
    else:
        raise SystemExit("usage: fpc_parse.py --selftest")
