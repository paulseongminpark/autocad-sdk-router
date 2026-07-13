from __future__ import annotations

import pytest

from tools.geometry_residue_measure import (
    classify_geometric_residual,
    point_cloud_residual,
    sample_polyline,
)


def _segment_points(count, transform=None):
    points = []
    for i in range(count):
        t = i / (count - 1)
        if transform is not None:
            t = transform(t)
        points.append((10.0 * t, 0.0))
    return points


def test_identical_clouds_have_zero_residual():
    cloud = [[0, 0], [1, 1], [2, 2]]

    residual = point_cloud_residual(cloud, cloud)
    verdict = classify_geometric_residual(cloud, cloud)

    assert residual["symmetric_hausdorff"] == 0.0
    assert verdict["verdict"] == "curve_equal"


def test_dense_same_locus_different_parameterization_reads_equal_at_loose_tol():
    cloud_a = _segment_points(100)
    cloud_b = _segment_points(100, transform=lambda t: t * t)

    residual = point_cloud_residual(cloud_a, cloud_b)
    verdict = classify_geometric_residual(cloud_a, cloud_b, tol=0.2)

    assert residual["symmetric_hausdorff"] < 0.2
    assert verdict["verdict"] == "curve_equal"


def test_shifted_clouds_report_drift():
    cloud_a = _segment_points(100)
    cloud_b = [(x + 5.0, y) for x, y in cloud_a]

    residual = point_cloud_residual(cloud_a, cloud_b)
    verdict = classify_geometric_residual(cloud_a, cloud_b)

    assert residual["symmetric_hausdorff"] == pytest.approx(5.0, abs=1e-6)
    assert verdict["verdict"] == "drift"


def test_empty_cloud_is_degenerate():
    residual = point_cloud_residual([], [[0, 0]])

    assert residual["degenerate"] is True
    assert residual["symmetric_hausdorff"] == float("inf")


def test_sample_polyline_spans_segment_and_keeps_endpoints():
    cloud = sample_polyline([[0, 0], [10, 0]], n_per_segment=10)
    xs = [point[0] for point in cloud]

    assert cloud[0] == (0.0, 0.0)
    assert cloud[-1] == (10.0, 0.0)
    assert min(xs) == 0.0
    assert max(xs) == 10.0
