"""Build per-segment feature vectors from SEG-IR v1."""

import argparse
import json
import math
import re
import tempfile
from pathlib import Path


# SEG-IR v1 is the only input format this module accepts.  Revise this single
# mapping when a later, explicitly agreed format revision is introduced.
FORMAT_SPEC = {
    "ir": "seg.v1",
    "top_level_keys": (
        "ir",
        "drawing_id",
        "units",
        "scale_mm_per_unit",
        "segments",
    ),
    "units": ("mm", "unknown"),
    "segment_keys": ("sid", "handle", "pts", "layer", "kind", "label", "source"),
    "kinds": ("line", "poly-edge", "arc-chord"),
    "labels": ("wall", "opening", "other", "unknown"),
    "sources": ("native", "synth", "floorplancad", "cubicasa"),
    "parallel_angle_tolerance_degrees": 2.0,
    "junction_snap_bbox_diagonal_fraction": 0.01,
}


def _require_exact_keys(value, expected, where):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f"{where} must have exactly these keys: {', '.join(expected)}")


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _validate_seg_ir(seg_ir):
    """Validate the declared SEG-IR v1 contract without format inference."""
    _require_exact_keys(seg_ir, FORMAT_SPEC["top_level_keys"], "SEG-IR")
    if seg_ir["ir"] != FORMAT_SPEC["ir"]:
        raise ValueError(f"unsupported ir: {seg_ir['ir']!r}")
    if not isinstance(seg_ir["drawing_id"], str):
        raise ValueError("drawing_id must be a string")
    if seg_ir["units"] not in FORMAT_SPEC["units"]:
        raise ValueError("units is not supported by FORMAT_SPEC")
    scale = seg_ir["scale_mm_per_unit"]
    if scale is not None and not _is_number(scale):
        raise ValueError("scale_mm_per_unit must be a finite number or null")
    if not isinstance(seg_ir["segments"], list):
        raise ValueError("segments must be a list")

    for index, segment in enumerate(seg_ir["segments"]):
        where = f"segments[{index}]"
        _require_exact_keys(segment, FORMAT_SPEC["segment_keys"], where)
        if not isinstance(segment["sid"], str):
            raise ValueError(f"{where}.sid must be a string")
        if segment["handle"] is not None and not isinstance(segment["handle"], str):
            raise ValueError(f"{where}.handle must be a string or null")
        if not isinstance(segment["layer"], str):
            raise ValueError(f"{where}.layer must be a string")
        if segment["kind"] not in FORMAT_SPEC["kinds"]:
            raise ValueError(f"{where}.kind is not supported by FORMAT_SPEC")
        if segment["label"] not in FORMAT_SPEC["labels"]:
            raise ValueError(f"{where}.label is not supported by FORMAT_SPEC")
        if segment["source"] not in FORMAT_SPEC["sources"]:
            raise ValueError(f"{where}.source is not supported by FORMAT_SPEC")
        points = segment["pts"]
        if not isinstance(points, list) or len(points) != 2:
            raise ValueError(f"{where}.pts must contain exactly two points")
        for point in points:
            if not isinstance(point, list) or len(point) != 2 or not all(_is_number(n) for n in point):
                raise ValueError(f"{where}.pts entries must be finite [x, y] pairs")


def _point(segment, index):
    x, y = segment["pts"][index]
    return float(x), float(y)


def _vector(segment):
    x1, y1 = _point(segment, 0)
    x2, y2 = _point(segment, 1)
    return x2 - x1, y2 - y1


def _length(segment):
    dx, dy = _vector(segment)
    return math.hypot(dx, dy)


def _orientation(segment):
    dx, dy = _vector(segment)
    return math.atan2(dy, dx) % math.pi


def _angle_mod90(segment):
    return math.degrees(_orientation(segment)) % 90.0


def _parallel(a, b):
    if _length(a) == 0.0 or _length(b) == 0.0:
        return False
    difference = abs(_orientation(a) - _orientation(b))
    difference = min(difference, math.pi - difference)
    return difference <= math.radians(FORMAT_SPEC["parallel_angle_tolerance_degrees"])


def _parallel_offset_and_overlap(base, partner):
    """Return perpendicular offset and projected overlap in base's direction."""
    x1, y1 = _point(base, 0)
    dx, dy = _vector(base)
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    px, py = _point(partner, 0)
    qx, qy = _point(partner, 1)
    offset = abs((px - x1) * uy - (py - y1) * ux)
    partner_projection = ((px - x1) * ux + (py - y1) * uy, (qx - x1) * ux + (qy - y1) * uy)
    overlap = max(0.0, min(length, max(partner_projection)) - max(0.0, min(partner_projection)))
    return offset, overlap


def _bbox_diagonal(segments):
    points = [_point(segment, endpoint) for segment in segments for endpoint in (0, 1)]
    if not points:
        return 0.0
    xs, ys = zip(*points)
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))


def _point_to_segment_distance(point, segment):
    px, py = point
    x1, y1 = _point(segment, 0)
    dx, dy = _vector(segment)
    length_squared = dx * dx + dy * dy
    if length_squared == 0.0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_squared))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _junction_degree(segment, all_segments, snap_tolerance):
    endpoints = (_point(segment, 0), _point(segment, 1))
    return sum(
        any(_point_to_segment_distance(endpoint, other) <= snap_tolerance for endpoint in endpoints)
        or any(_point_to_segment_distance(_point(other, endpoint), segment) <= snap_tolerance for endpoint in (0, 1))
        for other in all_segments
        if other is not segment
    )


def _layer_tokens(layer):
    return re.findall(r"[A-Za-z0-9]+", layer.lower())


def featurize(seg_ir):
    """Return one geometry/name-separated feature record for every SEG-IR segment."""
    _validate_seg_ir(seg_ir)
    segments = seg_ir["segments"]
    snap_tolerance = _bbox_diagonal(segments) * FORMAT_SPEC["junction_snap_bbox_diagonal_fraction"]
    features = []

    for segment in segments:
        partners = []
        for other in segments:
            if other is segment or not _parallel(segment, other):
                continue
            offset, overlap = _parallel_offset_and_overlap(segment, other)
            partners.append((offset, overlap))
        partners.sort(key=lambda pair: (pair[0], -pair[1]))
        min_offset = partners[0][0] if partners else None
        overlap = partners[0][1] if partners else 0.0
        features.append(
            {
                "sid": segment["sid"],
                "geom": {
                    "length": _length(segment),
                    "angle_mod90": _angle_mod90(segment),
                    "par_min_offset": min_offset,
                    "par_overlap": overlap,
                    "junction_deg": _junction_degree(segment, segments, snap_tolerance),
                    "thickness_candidate": min_offset,
                    "n_parallel_partners": len(partners),
                },
                "name": {"layer_tokens": _layer_tokens(segment["layer"])},
                "label": segment["label"],
            }
        )
    return features


def write_jsonl(features, path):
    """Write feature records as UTF-8 JSON Lines."""
    with Path(path).open("w", encoding="utf-8", newline="\n") as output:
        for feature in features:
            output.write(json.dumps(feature, allow_nan=False, separators=(",", ":")))
            output.write("\n")


def _selftest_fixture():
    """Return a hand-built SEG-IR fixture using only FORMAT_SPEC values."""
    return {
        "ir": FORMAT_SPEC["ir"],
        "drawing_id": "selftest",
        "units": FORMAT_SPEC["units"][0],
        "scale_mm_per_unit": None,
        "segments": [
            {"sid": "s0001", "handle": None, "pts": [[0, 0], [10, 0]], "layer": "A-WALL", "kind": "line", "label": "wall", "source": "synth"},
            {"sid": "s0002", "handle": None, "pts": [[0, 4], [10, 4]], "layer": "A-WALL", "kind": "line", "label": "wall", "source": "synth"},
            {"sid": "s0003", "handle": None, "pts": [[5, 0], [5, 4]], "layer": "A-GRID", "kind": "line", "label": "other", "source": "synth"},
            {"sid": "s0004", "handle": None, "pts": [[20, 20], [23, 22]], "layer": "A-ANNO", "kind": "line", "label": "unknown", "source": "synth"},
        ],
    }


def _selftest():
    fixture = _selftest_fixture()
    with tempfile.TemporaryDirectory() as temporary_directory:
        input_path = Path(temporary_directory) / "ir.json"
        output_path = Path(temporary_directory) / "features.jsonl"
        input_path.write_text(json.dumps(fixture), encoding="utf-8")
        features = featurize(json.loads(input_path.read_text(encoding="utf-8")))
        write_jsonl(features, output_path)
        assert len(output_path.read_text(encoding="utf-8").splitlines()) == 4

    observed = {feature["sid"]: feature["geom"] for feature in features}
    assert observed["s0001"]["par_min_offset"] == 4.0
    assert observed["s0002"]["par_min_offset"] == 4.0
    assert observed["s0003"]["par_min_offset"] is None
    assert observed["s0004"]["par_min_offset"] is None
    assert observed["s0001"]["junction_deg"] == 1
    assert observed["s0002"]["junction_deg"] == 1
    assert observed["s0003"]["junction_deg"] == 2
    assert observed["s0004"]["junction_deg"] == 0
    assert observed["s0001"]["n_parallel_partners"] == 1
    assert observed["s0002"]["n_parallel_partners"] == 1
    assert observed["s0003"]["n_parallel_partners"] == 0
    assert observed["s0004"]["n_parallel_partners"] == 0
    print("SELFTEST PASS: 4 segments; parallel, junction, and isolated assertions verified")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="input_path", help="SEG-IR v1 JSON input path")
    parser.add_argument("--out", dest="output_path", help="feature JSONL output path")
    parser.add_argument("--selftest", action="store_true", help="run the built-in SEG-IR fixture test")
    args = parser.parse_args(argv)
    if args.selftest:
        if args.input_path or args.output_path:
            parser.error("--selftest cannot be combined with --in or --out")
        _selftest()
        return
    if not args.input_path or not args.output_path:
        parser.error("--in and --out are required unless --selftest is used")
    with Path(args.input_path).open("r", encoding="utf-8") as input_file:
        write_jsonl(featurize(json.load(input_file)), args.output_path)


if __name__ == "__main__":
    main()
