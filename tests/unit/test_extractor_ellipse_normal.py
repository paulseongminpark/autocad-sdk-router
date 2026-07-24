from __future__ import annotations

import math
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
NATIVE_SOURCE = ROOT / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"


def _length(vector: tuple[float, float, float]) -> float:
    return math.sqrt(sum(component * component for component in vector))


def _dot(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> float:
    return sum(a * b for a, b in zip(left, right))


def _orthogonalized_ellipse_axes(
    major: tuple[float, float, float],
    normal: tuple[float, float, float],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Python-isomorphic copy of the AcDbEllipse emit math in C++."""
    original_major_length = _length(major)
    normal_length = _length(normal)
    normalized_normal = tuple(component / normal_length for component in normal)
    projection = _dot(major, normalized_normal)
    projected_major = tuple(
        component - projection * normal_component
        for component, normal_component in zip(major, normalized_normal)
    )
    projected_length = _length(projected_major)
    normalized_major = tuple(
        component * original_major_length / projected_length
        for component in projected_major
    )
    return normalized_major, normalized_normal


def test_noisy_ellipse_major_axis_is_orthogonal_and_keeps_radius():
    normal = (-8.99e-10, -6.41e-9, 1.0000000000000002)
    major = (10.0, 0.0, 3.5e-8)  # dot(major, normalized normal) ~= 2.6e-8

    emitted_major, emitted_normal = _orthogonalized_ellipse_axes(major, normal)

    assert abs(_dot(emitted_major, emitted_normal)) < 1e-12
    assert _length(emitted_major) == pytest.approx(_length(major), abs=1e-12)
    assert _length(emitted_normal) == pytest.approx(1.0, abs=1e-15)


def test_mirrored_ellipse_normal_keeps_negative_z_sign():
    emitted_major, emitted_normal = _orthogonalized_ellipse_axes(
        (4.0, 2.0, 5e-8),
        (0.0, 0.0, -1.0000000000000002),
    )

    assert emitted_normal[2] == -1.0
    assert abs(_dot(emitted_major, emitted_normal)) < 1e-12
    assert _length(emitted_major) == pytest.approx(math.sqrt(20.0), abs=1e-12)


def test_already_orthogonal_ellipse_axes_do_not_change():
    major = (3.0, 4.0, 0.0)
    normal = (0.0, 0.0, 1.0)

    emitted_major, emitted_normal = _orthogonalized_ellipse_axes(major, normal)

    assert emitted_major == major
    assert emitted_normal == normal


def test_native_ellipse_branch_implements_the_same_projection_order():
    source = NATIVE_SOURCE.read_text(encoding="utf-8")
    start = source.index("else if (AcDbEllipse* pEl")
    end = source.index("else if (AcDbSpline* pSpl", start)
    branch = source[start:end]

    for statement in (
        "AcGeVector3d major = pEl->majorAxis();",
        "AcGeVector3d nrm = pEl->normal();",
        "nrm.normalize();",
        "const double majorLength = major.length();",
        "major -= nrm * major.dotProduct(nrm);",
        "major.normalize();",
        "major *= majorLength;",
    ):
        assert statement in branch
