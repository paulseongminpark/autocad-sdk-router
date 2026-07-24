#!/usr/bin/env python3
"""Numeric-only fidelity statistics for E2 gen2 packs.

The implementation mirrors tools/e2/s2_fidelity.py: all modelspace entity
types are counted for categorical TV, and LINE/LWPOLYLINE/POLYLINE segments are
used to enumerate overlapping parallel-pair offsets for histogram KS.

No PASS/FAIL/band verdict is computed or emitted.
"""
from __future__ import annotations

import argparse
import bisect
import glob
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import ezdxf


DEFAULT_REFERENCE_FIDELITY = Path(
    r"D:\dev\99_tools\autocad-sdk-router\reports\e2\s2\fidelity_M_v2.json"
)
DEFAULT_REFERENCE_ENTITY = Path(
    r"D:\dev\99_tools\autocad-sdk-router\reports\e2\s2\fidelity_M_v1_tv.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def total_variation(a, b):
    total_a = sum(a.values())
    total_b = sum(b.values())
    if total_a <= 0 or total_b <= 0:
        raise ValueError("categorical distributions require positive mass")
    return 0.5 * sum(
        abs(a.get(key, 0) / total_a - b.get(key, 0) / total_b)
        for key in set(a) | set(b)
    )


def ks_from_hist(counts_a, counts_b):
    total_a = sum(counts_a)
    total_b = sum(counts_b)
    if total_a <= 0 or total_b <= 0:
        raise ValueError("histograms require positive mass")
    cumulative_a = 0.0
    cumulative_b = 0.0
    distance = 0.0
    for a, b in zip(counts_a, counts_b):
        cumulative_a += a / total_a
        cumulative_b += b / total_b
        distance = max(distance, abs(cumulative_a - cumulative_b))
    return distance


def histogram(samples, edges):
    counts = [0] * (len(edges) - 1)
    for sample in samples:
        index = bisect.bisect_right(edges, float(sample)) - 1
        if 0 <= index < len(counts):
            counts[index] += 1
    return counts


def segments_from_modelspace(modelspace):
    segments = []
    for entity in modelspace:
        entity_type = entity.dxftype()
        try:
            if entity_type == "LINE":
                start = entity.dxf.start
                end = entity.dxf.end
                segments.append(((start.x, start.y), (end.x, end.y)))
            elif entity_type == "LWPOLYLINE":
                points = [(point[0], point[1]) for point in entity.get_points("xy")]
                segments.extend(zip(points[:-1], points[1:]))
                if entity.closed and len(points) >= 2:
                    segments.append((points[-1], points[0]))
            elif entity_type == "POLYLINE":
                points = [
                    (vertex.dxf.location.x, vertex.dxf.location.y)
                    for vertex in entity.vertices
                ]
                segments.extend(zip(points[:-1], points[1:]))
                if entity.is_closed and len(points) >= 2:
                    segments.append((points[-1], points[0]))
        except Exception:
            # Matches the reference calculator's per-entity malformed-data policy.
            continue
    return list(segments)


def parallel_pair_offsets(segments, angle_tol_deg=1.0, min_overlap_frac=0.10):
    sin_tolerance = math.sin(math.radians(angle_tol_deg))
    prepared = []
    for (x1, y1), (x2, y2) in segments:
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length <= 0:
            continue
        prepared.append(((x1, y1), (x2, y2), dx / length, dy / length, length))

    offsets = []
    for i in range(len(prepared)):
        (p0x, p0y), (p1x, p1y), ux, uy, length_i = prepared[i]
        nx, ny = -uy, ux
        ai0 = p0x * ux + p0y * uy
        ai1 = p1x * ux + p1y * uy
        i_lo, i_hi = sorted((ai0, ai1))
        for j in range(i + 1, len(prepared)):
            (q0x, q0y), (q1x, q1y), vx, vy, length_j = prepared[j]
            if abs(ux * vy - uy * vx) > sin_tolerance:
                continue
            offset = abs((q0x - p0x) * nx + (q0y - p0y) * ny)
            if offset <= 1e-6:
                continue
            aj0 = q0x * ux + q0y * uy
            aj1 = q1x * ux + q1y * uy
            j_lo, j_hi = sorted((aj0, aj1))
            overlap = min(i_hi, j_hi) - max(i_lo, j_lo)
            if overlap <= min_overlap_frac * min(length_i, length_j):
                continue
            offsets.append(offset)
    return offsets


def compute_stats(pack_dir: Path):
    entity_mix = Counter()
    layer_tokens = Counter()
    offsets = []
    read_errors = 0
    dxf_files = sorted(Path(path) for path in glob.glob(
        str(pack_dir / "**" / "*.dxf"), recursive=True
    ))
    for path in dxf_files:
        try:
            document = ezdxf.readfile(path)
        except Exception:
            read_errors += 1
            continue
        modelspace = document.modelspace()
        for entity in modelspace:
            entity_mix[entity.dxftype()] += 1
            layer_tokens[getattr(entity.dxf, "layer", "0")] += 1
        offsets.extend(parallel_pair_offsets(segments_from_modelspace(modelspace)))
    return {
        "n_drawings": len(dxf_files) - read_errors,
        "n_files_seen": len(dxf_files),
        "read_errors": read_errors,
        "entity_mix": dict(sorted(entity_mix.items())),
        "layer_tokens": dict(sorted(layer_tokens.items())),
        "thickness_samples": offsets,
    }


def numeric_report(pack_dir: Path, reference_fidelity: Path, reference_entity: Path):
    fidelity = json.loads(reference_fidelity.read_text(encoding="utf-8"))
    entity_reference = json.loads(reference_entity.read_text(encoding="utf-8"))
    real_hist = fidelity["real_summary"]["thickness_hist"]
    edges = real_hist.get("edges") or real_hist["bin_edges"]
    real_counts = real_hist["counts"]
    real_mix = entity_reference["real_mix"]

    aggregate = compute_stats(pack_dir)
    pack_hist = histogram(aggregate["thickness_samples"], edges)
    tiers = {}
    for tier in ("S", "F", "M"):
        tier_dir = pack_dir / tier
        if not tier_dir.is_dir():
            continue
        stats = compute_stats(tier_dir)
        tier_hist = histogram(stats["thickness_samples"], edges)
        tiers[tier] = {
            "entity_mix_tv": total_variation(stats["entity_mix"], real_mix),
            "thickness_ks": ks_from_hist(tier_hist, real_counts),
            "n_drawings": stats["n_drawings"],
            "n_entities": sum(stats["entity_mix"].values()),
            "n_parallel_pair_offsets": len(stats["thickness_samples"]),
            "read_errors": stats["read_errors"],
        }

    return {
        "schema": "ariadne.e2.gen2.fidelity_numbers.v1",
        "metrics": {
            "entity_mix_tv": total_variation(aggregate["entity_mix"], real_mix),
            "thickness_ks": ks_from_hist(pack_hist, real_counts),
        },
        "sample_counts": {
            "n_drawings": aggregate["n_drawings"],
            "n_entities": sum(aggregate["entity_mix"].values()),
            "n_parallel_pair_offsets": len(aggregate["thickness_samples"]),
            "read_errors": aggregate["read_errors"],
        },
        "per_tier": tiers,
        "reference_counts": {
            "entity_total": sum(real_mix.values()),
            "parallel_pair_offsets": sum(real_counts),
        },
        "reference_sha256": {
            "fidelity_histogram_json": sha256(reference_fidelity),
            "entity_mix_json": sha256(reference_entity),
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compute numeric KS/TV statistics for a gen2 pack (no verdicts)."
    )
    parser.add_argument("--pack", required=True)
    parser.add_argument("--reference-fidelity", default=str(DEFAULT_REFERENCE_FIDELITY))
    parser.add_argument("--reference-entity", default=str(DEFAULT_REFERENCE_ENTITY))
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    pack = Path(args.pack).resolve()
    reference_fidelity = Path(args.reference_fidelity).resolve()
    reference_entity = Path(args.reference_entity).resolve()
    if not pack.is_dir():
        parser.error(f"pack directory not found: {pack}")
    for reference in (reference_fidelity, reference_entity):
        if not reference.is_file():
            parser.error(f"reference JSON not found: {reference}")

    report = numeric_report(pack, reference_fidelity, reference_entity)
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Deliberately numeric and verdict-free.
    print(f"thickness_ks={report['metrics']['thickness_ks']:.12f}")
    print(f"entity_mix_tv={report['metrics']['entity_mix_tv']:.12f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
