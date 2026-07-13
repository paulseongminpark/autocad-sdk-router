from __future__ import annotations

"""Pure-geometry point-cloud residual measurement utilities.

This module compares two sampled point clouds using nearest-neighbour Euclidean
distance with a brute-force O(len(A) * len(B)) search per directed pass.

Critical design note:
Point-cloud Hausdorff distance conflates sampling density with geometric drift.
Two sparse clouds on the same locus can show a large Hausdorff distance simply
because their samples fall between each other. A "same curve, different
parameterization" result should only be interpreted as ``curve_equal`` when
both clouds were densely sampled to comparable resolution by the caller.
"""

from math import inf, sqrt


def _point3(point):
    if len(point) >= 3:
        return float(point[0]), float(point[1]), float(point[2])
    return float(point[0]), float(point[1]), 0.0


def _distance(a, b):
    ax, ay, az = _point3(a)
    bx, by, bz = _point3(b)
    dx = ax - bx
    dy = ay - by
    dz = az - bz
    return sqrt(dx * dx + dy * dy + dz * dz)


def _directed_nn_distances(source, target):
    distances = []
    for point in source:
        best = inf
        for candidate in target:
            dist = _distance(point, candidate)
            if dist < best:
                best = dist
        distances.append(best)
    return distances


def point_cloud_residual(cloud_a, cloud_b):
    """Measure directed and symmetric residuals between two point clouds.

    The nearest-neighbour search is intentionally brute-force
    O(len(cloud_a) * len(cloud_b)) and deterministic.

    If either cloud is empty, this returns the normal residual keys with all
    distance values set to ``float("inf")`` plus ``{"degenerate": True}``.
    """

    n_a = len(cloud_a)
    n_b = len(cloud_b)
    if n_a == 0 or n_b == 0:
        return {
            "n_a": n_a,
            "n_b": n_b,
            "mean_a2b": inf,
            "max_a2b": inf,
            "mean_b2a": inf,
            "max_b2a": inf,
            "symmetric_hausdorff": inf,
            "mean_symmetric": inf,
            "degenerate": True,
        }

    distances_a2b = _directed_nn_distances(cloud_a, cloud_b)
    distances_b2a = _directed_nn_distances(cloud_b, cloud_a)
    sum_a2b = sum(distances_a2b)
    sum_b2a = sum(distances_b2a)
    max_a2b = max(distances_a2b)
    max_b2a = max(distances_b2a)

    return {
        "n_a": n_a,
        "n_b": n_b,
        "mean_a2b": sum_a2b / n_a,
        "max_a2b": max_a2b,
        "mean_b2a": sum_b2a / n_b,
        "max_b2a": max_b2a,
        "symmetric_hausdorff": max(max_a2b, max_b2a),
        "mean_symmetric": (sum_a2b + sum_b2a) / (n_a + n_b),
    }


def classify_geometric_residual(cloud_a, cloud_b, *, tol=1e-6):
    residual = point_cloud_residual(cloud_a, cloud_b)
    symmetric_hausdorff = residual["symmetric_hausdorff"]
    return {
        "verdict": "curve_equal" if symmetric_hausdorff <= tol else "drift",
        "symmetric_hausdorff": symmetric_hausdorff,
        "mean_symmetric": residual["mean_symmetric"],
        "tol": tol,
    }


def sample_polyline(vertices, n_per_segment=8):
    if n_per_segment < 1:
        raise ValueError("n_per_segment must be >= 1")
    if not vertices:
        return []

    dims = 3 if any(len(vertex) >= 3 for vertex in vertices) else 2
    if len(vertices) == 1:
        point = _point3(vertices[0])
        return [point if dims == 3 else point[:2]]

    cloud = []
    for seg_index in range(len(vertices) - 1):
        start = _point3(vertices[seg_index])
        end = _point3(vertices[seg_index + 1])
        first_step = 0 if seg_index == 0 else 1
        for step in range(first_step, n_per_segment + 1):
            t = step / n_per_segment
            point = (
                start[0] + (end[0] - start[0]) * t,
                start[1] + (end[1] - start[1]) * t,
                start[2] + (end[2] - start[2]) * t,
            )
            cloud.append(point if dims == 3 else point[:2])
    return cloud
