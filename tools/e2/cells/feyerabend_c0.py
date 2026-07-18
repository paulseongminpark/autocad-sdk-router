#!/usr/bin/env python3
"""Feyerabend P2 cell C0: deterministic canonical wall-scene factory.

This program writes only the artifacts declared by PACKET_feyerabend_c0.md:
200 JSON IR scenes, coverage_numbers.json, and REPORT.md below this file's
directory.  Repository inputs are imported/read without modification.  No CAD
source drawing or held-out/test split is accessed.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import ezdxf
import numpy as np


CELL_DIR = Path(__file__).resolve().parent
SCENES_DIR = CELL_DIR / "scenes"
GEN2_PATH = Path(r"D:\dev\99_tools\autocad-sdk-router\tools\e2\gen2\gen2.py")
FIDELITY_STATS_PATH = Path(
    r"D:\dev\99_tools\autocad-sdk-router\tools\e2\gen2\fidelity_stats.py"
)

SCENE_SCHEMA = "ariadne.e2.feyerabend_c0.scene.v1"
NUMBERS_SCHEMA = "ariadne.e2.feyerabend_c0.coverage_numbers.v1"
SEED_PREFIX = "feyerabend_P2:"
BASE_SCENE_COUNT = 50
SCALES = (
    (0.001, "0p001"),
    (0.01, "0p01"),
    (1.0, "1"),
    (1000.0, "1000"),
)
ENTITY_PROFILE_TARGET = 8_000
FIDELITY_GAP_SAMPLE_TARGET = 1_200

MUTATION_FAMILIES = (
    "pure_line_parallel_pair",
    "lwpolyline_segmentation",
    "arc_spline_adjacent_or_distractor",
    "hatch_boundary_distractor",
    "nested_insert_nonuniform_accumulated_transform",
    "partial_overlap_near_parallel_fragment",
    "door_window_dimension_long_parallel_distractor",
    "zero_wall_sentinel",
    "all_wall_sentinel",
    "single_reference_span_region",
    "multiple_reference_span_regions",
)

_REFERENCE_CACHE: tuple[Any, Any] | None = None


def _load_module(name: str, path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reference_modules() -> tuple[Any, Any]:
    global _REFERENCE_CACHE
    if _REFERENCE_CACHE is None:
        _REFERENCE_CACHE = (
            _load_module("feyerabend_c0_gen2_reference", GEN2_PATH),
            _load_module("feyerabend_c0_fidelity_reference", FIDELITY_STATS_PATH),
        )
    return _REFERENCE_CACHE


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def seed_for_index(index: int) -> int:
    if not 0 <= index < BASE_SCENE_COUNT:
        raise ValueError(f"base scene index out of range: {index}")
    digest = hashlib.sha256(f"{SEED_PREFIX}{index}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], byteorder="big", signed=False)


def seed_fraction(seed: int, label: str) -> float:
    """A direct deterministic function of the prescribed seed; no RNG state."""
    digest = hashlib.sha256(f"{seed}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def pair_id(handles: Iterable[str]) -> str:
    ordered = sorted(str(handle) for handle in handles)
    if len(ordered) != 2 or ordered[0] == ordered[1]:
        raise ValueError(f"invalid unordered pair: {ordered}")
    return "|".join(ordered)


def _point(value: Iterable[float]) -> list[float]:
    return [float(component) for component in value]


def _finite_numbers(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(_finite_numbers(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite_numbers(item) for item in value)
    return True


class SceneBuilder:
    """Build one unscaled canonical scene with stable, descriptive handles."""

    def __init__(self, index: int):
        self.index = int(index)
        self.seed = seed_for_index(index)
        self.base_scene_id = f"feyerabend_c0_{index:03d}"
        self.entities: list[dict[str, Any]] = []
        self.block_definitions: list[dict[str, Any]] = []
        self.anchors: list[dict[str, Any]] = []
        self.truth_pairs: list[dict[str, Any]] = []
        self.candidate_pairs: list[dict[str, Any]] = []
        self.mutations: set[str] = set()
        self.sentinel = "zero_wall" if index == 0 else (
            "all_wall" if index == 1 else "none"
        )
        self._handles: set[str] = set()
        self._profile_block_added = False

    def handle(self, token: str) -> str:
        cleaned = "".join(ch if ch.isalnum() else "_" for ch in token.upper())
        handle = f"F{self.index:03d}_{cleaned}"
        if handle in self._handles:
            raise AssertionError(f"duplicate handle request: {handle}")
        self._handles.add(handle)
        return handle

    def add_entity(
        self,
        entity_type: str,
        token: str,
        geometry: dict[str, Any],
        *,
        role: str,
        layer: str,
        score_candidate: bool = False,
    ) -> str:
        handle = self.handle(token)
        self.entities.append(
            {
                "handle": handle,
                "entity_type": entity_type,
                "layer": layer,
                "role": role,
                "score_candidate": bool(score_candidate),
                "geometry": geometry,
            }
        )
        return handle

    def add_block_entity(
        self,
        block: dict[str, Any],
        entity_type: str,
        token: str,
        geometry: dict[str, Any],
        *,
        role: str,
        layer: str,
    ) -> str:
        handle = self.handle(token)
        block["entities"].append(
            {
                "handle": handle,
                "entity_type": entity_type,
                "layer": layer,
                "role": role,
                "score_candidate": False,
                "geometry": geometry,
            }
        )
        return handle

    def add_candidate_pair(
        self,
        handles: Iterable[str],
        pair_class: str,
        family: str,
        canonical_gap: float,
    ) -> None:
        ordered = sorted(handles)
        self.candidate_pairs.append(
            {
                "pair_id": pair_id(ordered),
                "handles": ordered,
                "pair_class": pair_class,
                "family": family,
                "canonical_gap": float(canonical_gap),
                "raw_gap": float(canonical_gap),
            }
        )

    def add_wall_pair(
        self,
        token: str,
        entity_type: str,
        p0: tuple[float, float],
        p1: tuple[float, float],
        gap: float,
        *,
        partial_overlap: bool = False,
    ) -> None:
        gen2, _ = reference_modules()
        first = gen2._offset_segment(p0, p1, -0.5 * gap)
        second = gen2._offset_segment(p0, p1, 0.5 * gap)
        if partial_overlap:
            dx = p1[0] - p0[0]
            dy = p1[1] - p0[1]
            second = (
                (second[0][0] + 0.18 * dx, second[0][1] + 0.18 * dy),
                second[1],
            )
        geometry_a: dict[str, Any]
        geometry_b: dict[str, Any]
        if entity_type == "LINE":
            geometry_a = {"p0": _point(first[0]), "p1": _point(first[1])}
            geometry_b = {"p0": _point(second[0]), "p1": _point(second[1])}
            mutation = "pure_line_parallel_pair"
        elif entity_type == "LWPOLYLINE":
            midpoint = (
                0.5 * (first[0][0] + first[1][0]),
                0.5 * (first[0][1] + first[1][1]),
            )
            midpoint_b = (
                0.5 * (second[0][0] + second[1][0]),
                0.5 * (second[0][1] + second[1][1]),
            )
            geometry_a = {
                "points": [_point(first[0]), _point(midpoint), _point(first[1])],
                "closed": False,
            }
            geometry_b = {
                "points": [_point(second[0]), _point(midpoint_b), _point(second[1])],
                "closed": False,
            }
            mutation = "lwpolyline_segmentation"
        else:
            raise ValueError(f"unsupported straight wall entity type: {entity_type}")
        handle_a = self.add_entity(
            entity_type,
            f"{token}_wall_face_a",
            geometry_a,
            role="wall_face",
            layer="WALL",
            score_candidate=True,
        )
        handle_b = self.add_entity(
            entity_type,
            f"{token}_wall_face_b",
            geometry_b,
            role="wall_face",
            layer="WALL",
            score_candidate=True,
        )
        handles = sorted((handle_a, handle_b))
        self.truth_pairs.append(
            {
                "pair_id": pair_id(handles),
                "handles": handles,
                "wall_id": f"{self.base_scene_id}:{token}",
                "source_geometry_type": entity_type,
                "canonical_gap": float(gap),
                "raw_gap": float(gap),
            }
        )
        self.add_candidate_pair(handles, "wall", mutation, gap)
        self.mutations.add(mutation)

    def add_arc_wall_pair(self, token: str, gap: float) -> None:
        center = (6_500.0, 3_100.0)
        radius = 1_350.0 + float(self.index % 5) * 25.0
        handles = []
        for side, suffix in ((-0.5, "a"), (0.5, "b")):
            handles.append(
                self.add_entity(
                    "ARC",
                    f"{token}_arc_wall_{suffix}",
                    {
                        "center": _point(center),
                        "radius": radius + side * gap,
                        "start_angle_deg": 195.0,
                        "end_angle_deg": 345.0,
                    },
                    role="wall_face",
                    layer="WALL",
                    score_candidate=True,
                )
            )
        handles.sort()
        self.truth_pairs.append(
            {
                "pair_id": pair_id(handles),
                "handles": handles,
                "wall_id": f"{self.base_scene_id}:{token}",
                "source_geometry_type": "ARC",
                "canonical_gap": float(gap),
                "raw_gap": float(gap),
            }
        )
        self.add_candidate_pair(handles, "wall", "arc_wall_pair", gap)
        self.mutations.add("arc_spline_adjacent_or_distractor")

    def add_parallel_distractor(
        self,
        token: str,
        family: str,
        origin: tuple[float, float],
        gap: float,
        *,
        include_candidate: bool = True,
    ) -> None:
        x, y = origin
        handles = []
        for offset, suffix in ((0.0, "a"), (gap, "b")):
            handles.append(
                self.add_entity(
                    "LINE",
                    f"{token}_{suffix}",
                    {"p0": [x, y + offset], "p1": [x + 4_700.0, y + offset]},
                    role="hard_negative",
                    layer=family.upper(),
                    score_candidate=include_candidate,
                )
            )
        if include_candidate:
            self.add_candidate_pair(handles, "distractor", family, gap)

    def add_arc_spline_hatch_context(self) -> None:
        base_x = 30_000.0 + self.index * 19.0
        self.add_entity(
            "ARC",
            "context_arc",
            {
                "center": [base_x, 8_000.0],
                "radius": 700.0 + self.index,
                "start_angle_deg": 15.0,
                "end_angle_deg": 160.0,
            },
            role="curved_distractor",
            layer="FURN",
        )
        self.add_entity(
            "SPLINE",
            "context_spline",
            {
                "degree": 3,
                "control_points": [
                    [base_x, 10_000.0],
                    [base_x + 600.0, 10_400.0],
                    [base_x + 1_200.0, 9_700.0],
                    [base_x + 1_900.0, 10_100.0],
                ],
            },
            role="curved_distractor",
            layer="FURN",
        )
        self.add_entity(
            "HATCH",
            "context_hatch",
            {
                "pattern": "ANSI31",
                "boundary": [
                    [base_x, 12_000.0],
                    [base_x + 1_800.0, 12_000.0],
                    [base_x + 1_800.0, 12_900.0],
                    [base_x, 12_900.0],
                ],
                "closed": True,
            },
            role="hatch_boundary_distractor",
            layer="FLOOR",
        )
        self.mutations.add("arc_spline_adjacent_or_distractor")
        self.mutations.add("hatch_boundary_distractor")

    def add_nested_insert_context(self) -> None:
        inner_id = f"{self.base_scene_id}:INNER"
        outer_id = f"{self.base_scene_id}:OUTER"
        inner = {"block_id": inner_id, "base_point": [0.0, 0.0], "entities": []}
        outer = {"block_id": outer_id, "base_point": [0.0, 0.0], "entities": []}
        self.add_block_entity(
            inner,
            "LINE",
            "nested_inner_line",
            {"p0": [0.0, 0.0], "p1": [1_400.0, 0.0]},
            role="nested_block_fragment",
            layer="NESTED",
        )
        self.add_block_entity(
            inner,
            "SPLINE",
            "nested_inner_spline",
            {
                "degree": 3,
                "control_points": [
                    [0.0, 100.0], [350.0, 250.0], [900.0, -50.0], [1_400.0, 100.0]
                ],
            },
            role="nested_block_fragment",
            layer="NESTED",
        )
        inner_insert = self.add_block_entity(
            outer,
            "INSERT",
            "nested_inner_insert",
            {
                "block_ref": inner_id,
                "insertion": [250.0, 175.0],
                "xscale": 1.25,
                "yscale": 0.75,
                "rotation_deg": 7.0,
            },
            role="nested_insert",
            layer="NESTED",
        )
        outer["nested_insert_handles"] = [inner_insert]
        self.block_definitions.extend((inner, outer))
        self.add_entity(
            "INSERT",
            "nested_outer_insert",
            {
                "block_ref": outer_id,
                "insertion": [42_000.0 + self.index * 11.0, 18_000.0],
                "xscale": 0.90,
                "yscale": 1.10,
                "rotation_deg": -12.0,
            },
            role="nested_insert",
            layer="NESTED",
        )
        self.mutations.add("nested_insert_nonuniform_accumulated_transform")

    def add_near_parallel_fragments(self, include_candidate: bool) -> None:
        x = 52_000.0 + self.index * 13.0
        y = 25_000.0
        length = 2_500.0
        angle = math.radians(1.5)
        first = self.add_entity(
            "LINE",
            "near_parallel_fragment_a",
            {"p0": [x, y], "p1": [x + length, y]},
            role="nonparallel_fragment",
            layer="MESSY",
            score_candidate=include_candidate,
        )
        second = self.add_entity(
            "LINE",
            "near_parallel_fragment_b",
            {
                "p0": [x + 350.0, y + 210.0],
                "p1": [
                    x + 350.0 + length * math.cos(angle),
                    y + 210.0 + length * math.sin(angle),
                ],
            },
            role="nonparallel_fragment",
            layer="MESSY",
            score_candidate=include_candidate,
        )
        if include_candidate:
            self.add_candidate_pair(
                (first, second), "distractor", "near_parallel_fragment", 210.0
            )
        self.mutations.add("partial_overlap_near_parallel_fragment")

    def add_reference_anchors(self) -> None:
        multi_region = self.index % 2 == 0
        for anchor_index in range(3):
            y = 35_000.0 + anchor_index * 1_200.0
            p0 = [5_000.0, y]
            p1 = [6_000.0, y]
            self.anchors.append(
                {
                    "handle": self.handle(f"anchor_dim_a_{anchor_index}"),
                    "anchor_type": "DIM",
                    "region": "A",
                    "p0": p0,
                    "p1": p1,
                    "raw_span": 1_000.0,
                    "display_value": 1_000.0,
                    "display_unit": "MM",
                    "text_height": 100.0,
                    "weight": 1.0,
                }
            )
        if multi_region:
            for anchor_index in range(3):
                y = 35_000.0 + anchor_index * 1_300.0
                self.anchors.append(
                    {
                        "handle": self.handle(f"anchor_grid_b_{anchor_index}"),
                        "anchor_type": "GRID",
                        "region": "B",
                        "p0": [15_000.0, y],
                        "p1": [17_000.0, y],
                        "raw_span": 2_000.0,
                        "display_value": None,
                        "display_unit": "UNKNOWN",
                        "text_height": None,
                        "weight": 0.4,
                    }
                )
            self.mutations.add("multiple_reference_span_regions")
        else:
            self.mutations.add("single_reference_span_region")

    def add_calibration_pair(
        self,
        local_index: int,
        global_index: int,
        gap: float,
        entity_type: str,
    ) -> None:
        x = 100_000.0 + local_index * 2_200.0
        y = 20_000.0 + (local_index % 7) * 17.0
        handles = []
        for offset, suffix in ((0.0, "a"), (gap, "b")):
            if entity_type == "LINE":
                geometry = {
                    "p0": [x, y + offset],
                    "p1": [x + 1_200.0, y + offset],
                }
            elif entity_type == "LWPOLYLINE":
                geometry = {
                    "points": [[x, y + offset], [x + 1_200.0, y + offset]],
                    "closed": False,
                }
            else:
                raise ValueError(entity_type)
            handles.append(
                self.add_entity(
                    entity_type,
                    f"cal_{global_index:04d}_{suffix}",
                    geometry,
                    role="fidelity_calibration",
                    layer="CALIBRATION_CONTEXT",
                )
            )
        # This pair is fidelity context, never wall truth or detector score truth.
        _ = handles

    def ensure_profile_symbol(self) -> str:
        block_id = f"{self.base_scene_id}:PROFILE_SYMBOL"
        if self._profile_block_added:
            return block_id
        block = {"block_id": block_id, "base_point": [0.0, 0.0], "entities": []}
        self.add_block_entity(
            block,
            "CIRCLE",
            "profile_symbol_circle",
            {"center": [0.0, 0.0], "radius": 4.0},
            role="profile_symbol_geometry",
            layer="PROFILE_FILL",
        )
        self.block_definitions.append(block)
        self._profile_block_added = True
        return block_id

    def add_profile_entity(self, entity_type: str, global_index: int) -> None:
        x = 1_000_000.0 + (global_index % 200) * 40.0
        y = 1_000_000.0 + global_index * 30.0
        layer = "PROFILE_FILL"
        token = f"profile_{entity_type}_{global_index:05d}"
        if entity_type == "LINE":
            geometry = {"p0": [x, y], "p1": [x, y + 10.0]}
        elif entity_type == "LWPOLYLINE":
            geometry = {"points": [[x, y], [x, y + 10.0]], "closed": False}
        elif entity_type == "POLYLINE":
            geometry = {"points": [[x, y], [x, y + 10.0]], "closed": False}
        elif entity_type == "SPLINE":
            geometry = {
                "degree": 3,
                "control_points": [
                    [x, y], [x + 8.0, y + 15.0], [x + 16.0, y - 5.0], [x + 24.0, y + 10.0]
                ],
            }
        elif entity_type == "ARC":
            geometry = {
                "center": [x, y], "radius": 12.0,
                "start_angle_deg": 15.0, "end_angle_deg": 145.0,
            }
        elif entity_type == "CIRCLE":
            geometry = {"center": [x, y], "radius": 8.0}
        elif entity_type == "ELLIPSE":
            geometry = {"center": [x, y], "major_axis": [12.0, 0.0], "ratio": 0.45}
        elif entity_type == "HATCH":
            geometry = {
                "pattern": "ANSI31",
                "boundary": [[x, y], [x + 20.0, y], [x + 20.0, y + 20.0], [x, y + 20.0]],
                "closed": True,
            }
        elif entity_type == "TEXT":
            geometry = {"insertion": [x, y], "height": 8.0, "text": "D"}
        elif entity_type == "MTEXT":
            geometry = {"insertion": [x, y], "height": 8.0, "text": "NOTE"}
        elif entity_type == "POINT":
            geometry = {"point": [x, y]}
        elif entity_type == "3DFACE":
            geometry = {
                "points": [[x, y, 0.0], [x + 20.0, y, 0.0], [x + 20.0, y + 20.0, 0.0], [x, y + 20.0, 0.0]]
            }
        elif entity_type == "WIPEOUT":
            geometry = {
                "boundary": [[x, y], [x + 20.0, y], [x + 20.0, y + 20.0], [x, y + 20.0]],
                "closed": True,
            }
        elif entity_type == "INSERT":
            geometry = {
                "block_ref": self.ensure_profile_symbol(),
                "insertion": [x, y],
                "xscale": 1.0,
                "yscale": 1.0,
                "rotation_deg": 0.0,
            }
        else:
            raise ValueError(f"unsupported profile entity type: {entity_type}")
        self.add_entity(
            entity_type,
            token,
            geometry,
            role="fidelity_profile",
            layer=layer,
        )

    def entity_mix(self) -> Counter[str]:
        return Counter(entity["entity_type"] for entity in self.entities)

    def finalize(self) -> dict[str, Any]:
        scene: dict[str, Any] = {
            "schema": SCENE_SCHEMA,
            "scene_id": f"{self.base_scene_id}:k1",
            "base_scene_id": self.base_scene_id,
            "base_scene_index": self.index,
            "seed": self.seed,
            "seed_rule": "uint32_be(sha256('feyerabend_P2:'+j)[0:4])",
            "scale_kappa": 1.0,
            "truth_unit_scale": 1.0,
            "sentinel": self.sentinel,
            "mutation_families": sorted(self.mutations),
            "entities": self.entities,
            "block_definitions": self.block_definitions,
            "anchors": self.anchors,
            "truth_pairs": sorted(self.truth_pairs, key=lambda row: row["pair_id"]),
            "candidate_pairs": sorted(self.candidate_pairs, key=lambda row: row["pair_id"]),
            "entity_mix": dict(sorted(self.entity_mix().items())),
            "provenance": {
                "generator_reference": str(GEN2_PATH),
                "generator_reference_calls": ["_allocate_hist_samples", "_offset_segment"],
                "fidelity_reference": str(FIDELITY_STATS_PATH),
                "randomness": "none beyond direct deterministic functions of prescribed seed",
                "source_cad_accessed": False,
                "test_split_accessed": False,
            },
        }
        refresh_scene_digests(scene)
        return scene


def reference_payloads() -> tuple[dict[str, Any], dict[str, Any]]:
    _, fidelity = reference_modules()
    histogram_payload = json.loads(
        fidelity.DEFAULT_REFERENCE_FIDELITY.read_text(encoding="utf-8")
    )
    entity_payload = json.loads(
        fidelity.DEFAULT_REFERENCE_ENTITY.read_text(encoding="utf-8")
    )
    return histogram_payload, entity_payload


def fidelity_schedule() -> list[list[tuple[int, int, float, str]]]:
    gen2, _ = reference_modules()
    histogram_payload, _ = reference_payloads()
    real_hist = histogram_payload["real_summary"]["thickness_hist"]
    edges = real_hist.get("edges") or real_hist["bin_edges"]
    counts = real_hist["counts"]
    allocation = gen2._allocate_hist_samples(counts, FIDELITY_GAP_SAMPLE_TARGET)
    schedule: list[list[tuple[int, int, float, str]]] = [
        [] for _ in range(BASE_SCENE_COUNT)
    ]
    global_index = 0
    for bin_index, amount in enumerate(allocation):
        lo = float(edges[bin_index])
        hi = float(edges[bin_index + 1])
        for _ in range(amount):
            scene_index = global_index % BASE_SCENE_COUNT
            seed = seed_for_index(scene_index)
            unit = 0.2 + 0.6 * seed_fraction(seed, f"fidelity_gap:{global_index}")
            gap = lo + (hi - lo) * unit
            if gap <= 1e-6:
                gap = 0.5
            entity_type = (
                "LINE"
                if seed_fraction(seed, f"fidelity_type:{global_index}") < 0.62
                else "LWPOLYLINE"
            )
            schedule[scene_index].append((global_index, bin_index, gap, entity_type))
            global_index += 1
    if global_index != FIDELITY_GAP_SAMPLE_TARGET:
        raise AssertionError(global_index)
    return schedule


def build_structural_scene(
    index: int, calibration_rows: list[tuple[int, int, float, str]]
) -> SceneBuilder:
    builder = SceneBuilder(index)
    if index == 0:
        # The zero-wall sentinel deliberately contains hard candidate distractors
        # and no wall truth.  This is the sole exception to positive-scene truth.
        pass
    elif index == 1:
        builder.add_wall_pair("all_line", "LINE", (0.0, 0.0), (8_000.0, 0.0), 180.0)
        builder.add_wall_pair("all_lw", "LWPOLYLINE", (0.0, 2_000.0), (7_500.0, 2_000.0), 240.0)
        builder.add_arc_wall_pair("all_arc", 200.0)
        builder.mutations.add("all_wall_sentinel")
    else:
        gap = 90.0 + float((builder.seed >> 8) % 231)
        if index % 10 == 0:
            builder.add_arc_wall_pair("primary", gap)
        else:
            wall_type = "LINE" if index % 2 == 0 else "LWPOLYLINE"
            builder.add_wall_pair(
                "primary",
                wall_type,
                (0.0, 0.0),
                (7_000.0 + float(index % 7) * 170.0, 0.0),
                gap,
                partial_overlap=(index % 5 == 0),
            )

    builder.add_arc_spline_hatch_context()
    builder.add_nested_insert_context()
    builder.add_near_parallel_fragments(include_candidate=index != 1)

    if index != 1:
        family = ("door", "window", "dimension")[index % 3]
        builder.add_parallel_distractor(
            f"{family}_long_parallel",
            family,
            (62_000.0, 30_000.0 + float(index % 4) * 1_000.0),
            100.0 + float(index % 5) * 20.0,
        )
        builder.mutations.add("door_window_dimension_long_parallel_distractor")
    if index == 0:
        builder.mutations.add("zero_wall_sentinel")

    builder.add_reference_anchors()
    for local_index, (global_index, _bin_index, gap, entity_type) in enumerate(
        calibration_rows
    ):
        builder.add_calibration_pair(local_index, global_index, gap, entity_type)
    return builder


def allocate_profile_targets(
    current: Counter[str], reference_mix: dict[str, int]
) -> tuple[int, dict[str, int]]:
    gen2, _ = reference_modules()
    keys = sorted(reference_mix)
    target_total = ENTITY_PROFILE_TARGET
    while True:
        allocation = gen2._allocate_hist_samples(
            [int(reference_mix[key]) for key in keys], target_total
        )
        targets = dict(zip(keys, allocation))
        if all(current.get(key, 0) <= targets[key] for key in keys):
            return target_total, targets
        target_total += 500
        if target_total > 100_000:
            raise RuntimeError("unable to allocate an entity profile above mandatory geometry")


def build_base_corpus() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    schedule = fidelity_schedule()
    builders = [
        build_structural_scene(index, schedule[index])
        for index in range(BASE_SCENE_COUNT)
    ]
    current: Counter[str] = Counter()
    for builder in builders:
        current.update(builder.entity_mix())
    _, entity_payload = reference_payloads()
    real_mix = {key: int(value) for key, value in entity_payload["real_mix"].items()}
    target_total, targets = allocate_profile_targets(current, real_mix)

    global_profile_index = 0
    for type_index, entity_type in enumerate(sorted(targets)):
        need = targets[entity_type] - current.get(entity_type, 0)
        for local_index in range(need):
            scene_index = (local_index * 17 + type_index * 11) % BASE_SCENE_COUNT
            builders[scene_index].add_profile_entity(entity_type, global_profile_index)
            global_profile_index += 1

    scenes = [builder.finalize() for builder in builders]
    final_mix: Counter[str] = Counter()
    for scene in scenes:
        final_mix.update(scene["entity_mix"])
    positive_targets = {key: value for key, value in targets.items() if value > 0}
    if dict(sorted(final_mix.items())) != dict(sorted(positive_targets.items())):
        raise AssertionError("final entity mix does not match allocated target")
    build_numbers = {
        "entity_profile_target_total": target_total,
        "entity_profile_filler_count": global_profile_index,
        "fidelity_gap_sample_target": FIDELITY_GAP_SAMPLE_TARGET,
    }
    return scenes, build_numbers


def scale_point(point: list[float], kappa: float) -> list[float]:
    return [float(component) * kappa for component in point]


def scale_geometry(entity_type: str, geometry: dict[str, Any], kappa: float) -> None:
    if entity_type == "LINE":
        geometry["p0"] = scale_point(geometry["p0"], kappa)
        geometry["p1"] = scale_point(geometry["p1"], kappa)
    elif entity_type in ("LWPOLYLINE", "POLYLINE", "3DFACE"):
        geometry["points"] = [scale_point(point, kappa) for point in geometry["points"]]
    elif entity_type == "SPLINE":
        geometry["control_points"] = [
            scale_point(point, kappa) for point in geometry["control_points"]
        ]
    elif entity_type in ("ARC", "CIRCLE"):
        geometry["center"] = scale_point(geometry["center"], kappa)
        geometry["radius"] = float(geometry["radius"]) * kappa
    elif entity_type == "ELLIPSE":
        geometry["center"] = scale_point(geometry["center"], kappa)
        geometry["major_axis"] = scale_point(geometry["major_axis"], kappa)
    elif entity_type in ("HATCH", "WIPEOUT"):
        geometry["boundary"] = [scale_point(point, kappa) for point in geometry["boundary"]]
    elif entity_type in ("TEXT", "MTEXT"):
        geometry["insertion"] = scale_point(geometry["insertion"], kappa)
        geometry["height"] = float(geometry["height"]) * kappa
    elif entity_type == "POINT":
        geometry["point"] = scale_point(geometry["point"], kappa)
    elif entity_type == "INSERT":
        geometry["insertion"] = scale_point(geometry["insertion"], kappa)
    else:
        raise ValueError(f"unsupported entity geometry: {entity_type}")


def scale_scene(base_scene: dict[str, Any], kappa: float, scale_token: str) -> dict[str, Any]:
    scene = copy.deepcopy(base_scene)
    scene["scene_id"] = f"{scene['base_scene_id']}:k{scale_token}"
    scene["scale_kappa"] = float(kappa)
    scene["truth_unit_scale"] = 1.0 / float(kappa)
    for entity in scene["entities"]:
        scale_geometry(entity["entity_type"], entity["geometry"], kappa)
    for block in scene["block_definitions"]:
        block["base_point"] = scale_point(block["base_point"], kappa)
        for entity in block["entities"]:
            scale_geometry(entity["entity_type"], entity["geometry"], kappa)
    for anchor in scene["anchors"]:
        anchor["p0"] = scale_point(anchor["p0"], kappa)
        anchor["p1"] = scale_point(anchor["p1"], kappa)
        anchor["raw_span"] = float(anchor["raw_span"]) * kappa
        if anchor["text_height"] is not None:
            anchor["text_height"] = float(anchor["text_height"]) * kappa
    for row in scene["truth_pairs"]:
        row["raw_gap"] = float(row["canonical_gap"]) * kappa
    for row in scene["candidate_pairs"]:
        row["raw_gap"] = float(row["canonical_gap"]) * kappa
    refresh_scene_digests(scene)
    return scene


def geometry_topology(entity: dict[str, Any]) -> dict[str, Any]:
    entity_type = entity["entity_type"]
    geometry = entity["geometry"]
    signature: dict[str, Any] = {}
    if entity_type in ("LWPOLYLINE", "POLYLINE", "3DFACE"):
        signature = {
            "point_count": len(geometry["points"]),
            "closed": bool(geometry.get("closed", False)),
        }
    elif entity_type == "SPLINE":
        signature = {
            "degree": int(geometry["degree"]),
            "control_point_count": len(geometry["control_points"]),
        }
    elif entity_type in ("HATCH", "WIPEOUT"):
        signature = {
            "boundary_point_count": len(geometry["boundary"]),
            "closed": bool(geometry.get("closed", False)),
            "pattern": geometry.get("pattern"),
        }
    elif entity_type == "INSERT":
        signature = {
            "block_ref": geometry["block_ref"],
            "xscale": geometry["xscale"],
            "yscale": geometry["yscale"],
            "rotation_deg": geometry["rotation_deg"],
        }
    elif entity_type in ("ARC",):
        signature = {
            "start_angle_deg": geometry["start_angle_deg"],
            "end_angle_deg": geometry["end_angle_deg"],
        }
    return {
        "handle": entity["handle"],
        "entity_type": entity_type,
        "layer": entity["layer"],
        "role": entity["role"],
        "score_candidate": entity["score_candidate"],
        "signature": signature,
    }


def topology_projection(scene: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": scene["schema"],
        "base_scene_id": scene["base_scene_id"],
        "base_scene_index": scene["base_scene_index"],
        "seed": scene["seed"],
        "sentinel": scene["sentinel"],
        "mutation_families": scene["mutation_families"],
        "entities": [geometry_topology(entity) for entity in scene["entities"]],
        "block_definitions": [
            {
                "block_id": block["block_id"],
                "entities": [geometry_topology(entity) for entity in block["entities"]],
            }
            for block in scene["block_definitions"]
        ],
        "anchors": [
            {
                "handle": anchor["handle"],
                "anchor_type": anchor["anchor_type"],
                "region": anchor["region"],
                "display_value": anchor["display_value"],
                "display_unit": anchor["display_unit"],
                "weight": anchor["weight"],
            }
            for anchor in scene["anchors"]
        ],
        "truth_pairs": [
            {
                "pair_id": row["pair_id"],
                "handles": row["handles"],
                "wall_id": row["wall_id"],
                "source_geometry_type": row["source_geometry_type"],
            }
            for row in scene["truth_pairs"]
        ],
        "candidate_pairs": [
            {
                "pair_id": row["pair_id"],
                "handles": row["handles"],
                "pair_class": row["pair_class"],
                "family": row["family"],
            }
            for row in scene["candidate_pairs"]
        ],
    }


def normalized_geometry_projection(scene: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(scene)
    inverse = 1.0 / float(scene["scale_kappa"])
    for entity in normalized["entities"]:
        scale_geometry(entity["entity_type"], entity["geometry"], inverse)
    for block in normalized["block_definitions"]:
        block["base_point"] = scale_point(block["base_point"], inverse)
        for entity in block["entities"]:
            scale_geometry(entity["entity_type"], entity["geometry"], inverse)
    for anchor in normalized["anchors"]:
        anchor["p0"] = scale_point(anchor["p0"], inverse)
        anchor["p1"] = scale_point(anchor["p1"], inverse)
        anchor["raw_span"] = float(anchor["raw_span"]) * inverse
        if anchor["text_height"] is not None:
            anchor["text_height"] = float(anchor["text_height"]) * inverse
    for row in normalized["truth_pairs"]:
        row["raw_gap"] = float(row["raw_gap"]) * inverse
    for row in normalized["candidate_pairs"]:
        row["raw_gap"] = float(row["raw_gap"]) * inverse
    return {
        "entities": [
            {"handle": entity["handle"], "geometry": _round_floats(entity["geometry"])}
            for entity in normalized["entities"]
        ],
        "block_definitions": [
            {
                "block_id": block["block_id"],
                "base_point": _round_floats(block["base_point"]),
                "entities": [
                    {"handle": entity["handle"], "geometry": _round_floats(entity["geometry"])}
                    for entity in block["entities"]
                ],
            }
            for block in normalized["block_definitions"]
        ],
        "anchors": [
            {
                "handle": anchor["handle"],
                "p0": _round_floats(anchor["p0"]),
                "p1": _round_floats(anchor["p1"]),
                "raw_span": _round_floats(anchor["raw_span"]),
                "display_value": anchor["display_value"],
            }
            for anchor in normalized["anchors"]
        ],
        "truth_pairs": [
            {"pair_id": row["pair_id"], "raw_gap": _round_floats(row["raw_gap"])}
            for row in normalized["truth_pairs"]
        ],
        "candidate_pairs": [
            {"pair_id": row["pair_id"], "raw_gap": _round_floats(row["raw_gap"])}
            for row in normalized["candidate_pairs"]
        ],
    }


def _round_floats(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, float):
        rounded = round(value, 8)
        return 0.0 if rounded == -0.0 else rounded
    if isinstance(value, int):
        return value
    if isinstance(value, list):
        return [_round_floats(item) for item in value]
    if isinstance(value, dict):
        return {key: _round_floats(item) for key, item in value.items()}
    return value


def refresh_scene_digests(scene: dict[str, Any]) -> None:
    scene["topology_sha256"] = canonical_sha256(topology_projection(scene))
    scene["normalized_geometry_sha256"] = canonical_sha256(
        normalized_geometry_projection(scene)
    )


def all_handles(scene: dict[str, Any]) -> list[str]:
    handles = [entity["handle"] for entity in scene["entities"]]
    handles.extend(anchor["handle"] for anchor in scene["anchors"])
    for block in scene["block_definitions"]:
        handles.extend(entity["handle"] for entity in block["entities"])
    return handles


def block_depth_and_nonuniform(scene: dict[str, Any]) -> tuple[int, int]:
    definitions = {block["block_id"]: block for block in scene["block_definitions"]}

    def depth_for_ref(block_ref: str, stack: tuple[str, ...]) -> int:
        if block_ref in stack:
            return 10_000
        block = definitions.get(block_ref)
        if block is None:
            return 0
        children = [
            entity["geometry"]["block_ref"]
            for entity in block["entities"]
            if entity["entity_type"] == "INSERT"
        ]
        if not children:
            return 1
        return 1 + max(depth_for_ref(child, stack + (block_ref,)) for child in children)

    depths = []
    nonuniform = 0
    for entity in scene["entities"]:
        if entity["entity_type"] == "INSERT":
            geometry = entity["geometry"]
            depths.append(depth_for_ref(geometry["block_ref"], ()))
            if not math.isclose(geometry["xscale"], geometry["yscale"]):
                nonuniform += 1
    for block in scene["block_definitions"]:
        for entity in block["entities"]:
            if entity["entity_type"] == "INSERT":
                geometry = entity["geometry"]
                if not math.isclose(geometry["xscale"], geometry["yscale"]):
                    nonuniform += 1
    return max(depths, default=0), nonuniform


def validate_scene(scene: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    prefix = scene.get("scene_id", "<unknown>")

    def error(message: str) -> None:
        errors.append(f"{prefix}: {message}")

    if scene.get("schema") != SCENE_SCHEMA:
        error(f"schema={scene.get('schema')!r}")
    index = scene.get("base_scene_index")
    if not isinstance(index, int) or not 0 <= index < BASE_SCENE_COUNT:
        error(f"invalid base_scene_index={index!r}")
    elif scene.get("seed") != seed_for_index(index):
        error("seed does not match SHA-256 rule")
    kappa = scene.get("scale_kappa")
    if not isinstance(kappa, (int, float)) or not math.isfinite(float(kappa)) or kappa <= 0:
        error(f"invalid scale_kappa={kappa!r}")
        kappa = 1.0
    if not math.isclose(float(scene.get("truth_unit_scale", math.nan)), 1.0 / float(kappa), rel_tol=1e-12):
        error("truth_unit_scale is not 1/kappa")
    if scene.get("topology_sha256") != canonical_sha256(topology_projection(scene)):
        error("topology_sha256 mismatch")
    if scene.get("normalized_geometry_sha256") != canonical_sha256(normalized_geometry_projection(scene)):
        error("normalized_geometry_sha256 mismatch")
    if not _finite_numbers(scene):
        error("non-finite numeric value")

    handles = all_handles(scene)
    if len(handles) != len(set(handles)):
        error("duplicate source handles")
    top_entities = {entity["handle"]: entity for entity in scene["entities"]}
    block_ids = {block["block_id"] for block in scene["block_definitions"]}
    for entity in scene["entities"]:
        if entity["entity_type"] == "INSERT" and entity["geometry"]["block_ref"] not in block_ids:
            error(f"missing block_ref for {entity['handle']}")
    for block in scene["block_definitions"]:
        for entity in block["entities"]:
            if entity["entity_type"] == "INSERT" and entity["geometry"]["block_ref"] not in block_ids:
                error(f"missing nested block_ref for {entity['handle']}")

    truth_ids: set[str] = set()
    for row in scene.get("truth_pairs", []):
        handles_pair = row.get("handles", [])
        try:
            expected_id = pair_id(handles_pair)
        except ValueError as exc:
            error(str(exc))
            continue
        if row.get("pair_id") != expected_id:
            error(f"noncanonical truth pair id {row.get('pair_id')}")
        if expected_id in truth_ids:
            error(f"duplicate truth pair {expected_id}")
        truth_ids.add(expected_id)
        for handle in handles_pair:
            entity = top_entities.get(handle)
            if entity is None:
                error(f"truth handle missing from scene entities: {handle}")
            elif entity.get("role") != "wall_face":
                error(f"truth handle is not a wall_face: {handle}")
        if not math.isclose(float(row["raw_gap"]), float(row["canonical_gap"]) * float(kappa), rel_tol=1e-12, abs_tol=1e-10):
            error(f"truth raw_gap scale mismatch: {expected_id}")

    candidate_ids: set[str] = set()
    for row in scene.get("candidate_pairs", []):
        try:
            expected_id = pair_id(row.get("handles", []))
        except ValueError as exc:
            error(str(exc))
            continue
        if row.get("pair_id") != expected_id:
            error(f"noncanonical candidate pair id {row.get('pair_id')}")
        if expected_id in candidate_ids:
            error(f"duplicate candidate pair {expected_id}")
        candidate_ids.add(expected_id)
        if any(handle not in top_entities for handle in row["handles"]):
            error(f"candidate pair contains missing handle: {expected_id}")
        if not math.isclose(float(row["raw_gap"]), float(row["canonical_gap"]) * float(kappa), rel_tol=1e-12, abs_tol=1e-10):
            error(f"candidate raw_gap scale mismatch: {expected_id}")
    if not truth_ids.issubset(candidate_ids):
        error("truth pair is absent from candidate universe")

    sentinel = scene.get("sentinel")
    wall_face_count = sum(entity["role"] == "wall_face" for entity in scene["entities"])
    if sentinel == "zero_wall":
        if truth_ids:
            error("zero-wall sentinel contains truth pairs")
        if wall_face_count:
            error("zero-wall sentinel contains wall-face handles")
        if not candidate_ids:
            error("zero-wall sentinel lacks hard-negative candidates")
    else:
        if not truth_ids:
            error("positive scene has no source-handle truth pair")
    if sentinel == "all_wall":
        if not candidate_ids or candidate_ids != truth_ids:
            error("all-wall candidate universe is not exactly truth")

    for anchor in scene.get("anchors", []):
        p0 = np.asarray(anchor["p0"], dtype=float)
        p1 = np.asarray(anchor["p1"], dtype=float)
        raw_span = float(np.linalg.norm(p1 - p0))
        if not math.isclose(raw_span, float(anchor["raw_span"]), rel_tol=1e-12, abs_tol=1e-8):
            error(f"anchor raw span mismatch: {anchor['handle']}")
        if anchor["display_value"] is not None:
            observed = float(anchor["display_value"]) / raw_span
            if not math.isclose(observed, 1.0 / float(kappa), rel_tol=1e-12, abs_tol=1e-12):
                error(f"anchor display/raw mismatch: {anchor['handle']}")

    depth, nonuniform = block_depth_and_nonuniform(scene)
    if "nested_insert_nonuniform_accumulated_transform" in scene.get("mutation_families", []):
        if depth < 2:
            error(f"nested INSERT depth={depth}")
        if nonuniform < 2:
            error(f"non-uniform transform count={nonuniform}")

    actual_mix = Counter(entity["entity_type"] for entity in scene["entities"])
    if dict(sorted(actual_mix.items())) != scene.get("entity_mix"):
        error("entity_mix does not match entities")
    return errors


def segments_from_scene(scene: dict[str, Any]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for entity in scene["entities"]:
        entity_type = entity["entity_type"]
        geometry = entity["geometry"]
        if entity_type == "LINE":
            segments.append((tuple(geometry["p0"][:2]), tuple(geometry["p1"][:2])))
        elif entity_type in ("LWPOLYLINE", "POLYLINE"):
            points = [tuple(point[:2]) for point in geometry["points"]]
            segments.extend(zip(points[:-1], points[1:]))
            if geometry.get("closed") and len(points) >= 2:
                segments.append((points[-1], points[0]))
    return list(segments)


def phenomenon_present(scene: dict[str, Any], phenomenon: str) -> bool:
    types = {entity["entity_type"] for entity in scene["entities"]}
    if phenomenon in ("ARC", "SPLINE", "HATCH"):
        return phenomenon in types
    if phenomenon == "nested_block":
        depth, _ = block_depth_and_nonuniform(scene)
        return depth >= 2
    if phenomenon == "nonparallel_fragment":
        return any(entity["role"] == "nonparallel_fragment" for entity in scene["entities"])
    raise ValueError(phenomenon)


def aggregate_numbers(
    base_scenes: list[dict[str, Any]],
    all_scenes: list[dict[str, Any]],
    build_numbers: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    _, fidelity = reference_modules()
    histogram_payload, entity_payload = reference_payloads()
    real_hist = histogram_payload["real_summary"]["thickness_hist"]
    edges = real_hist.get("edges") or real_hist["bin_edges"]
    real_hist_counts = [int(value) for value in real_hist["counts"]]
    real_mix = {key: int(value) for key, value in entity_payload["real_mix"].items()}

    synthetic_mix: Counter[str] = Counter()
    offsets: list[float] = []
    for scene in base_scenes:
        synthetic_mix.update(scene["entity_mix"])
        offsets.extend(fidelity.parallel_pair_offsets(segments_from_scene(scene)))
    synthetic_hist = fidelity.histogram(offsets, edges)
    entity_tv = fidelity.total_variation(synthetic_mix, real_mix)
    thickness_ks = fidelity.ks_from_hist(synthetic_hist, real_hist_counts)

    validation_errors: list[str] = []
    for scene in all_scenes:
        validation_errors.extend(validate_scene(scene))

    group_topology_mismatch_count = 0
    group_geometry_mismatch_count = 0
    group_handle_mismatch_count = 0
    for index in range(BASE_SCENE_COUNT):
        group = [scene for scene in all_scenes if scene["base_scene_index"] == index]
        if len({scene["topology_sha256"] for scene in group}) != 1:
            group_topology_mismatch_count += 1
        if len({scene["normalized_geometry_sha256"] for scene in group}) != 1:
            group_geometry_mismatch_count += 1
        handle_sets = {tuple(sorted(all_handles(scene))) for scene in group}
        if len(handle_sets) != 1:
            group_handle_mismatch_count += 1

    mutation_counts = {
        family: sum(family in scene["mutation_families"] for scene in base_scenes)
        for family in MUTATION_FAMILIES
    }
    phenomenon_counts = {
        phenomenon: sum(phenomenon_present(scene, phenomenon) for scene in base_scenes)
        for phenomenon in ("ARC", "SPLINE", "HATCH", "nested_block", "nonparallel_fragment")
    }
    positive_base = [scene for scene in base_scenes if scene["sentinel"] != "zero_wall"]
    positive_all = [scene for scene in all_scenes if scene["sentinel"] != "zero_wall"]
    base_with_truth = sum(bool(scene["truth_pairs"]) for scene in base_scenes)
    all_with_truth = sum(bool(scene["truth_pairs"]) for scene in all_scenes)

    zero_scene = next(scene for scene in base_scenes if scene["sentinel"] == "zero_wall")
    all_wall_scene = next(scene for scene in base_scenes if scene["sentinel"] == "all_wall")
    zero_errors = validate_scene(zero_scene)
    all_wall_errors = validate_scene(all_wall_scene)
    all_truth_ids = {row["pair_id"] for row in all_wall_scene["truth_pairs"]}
    all_candidate_ids = {row["pair_id"] for row in all_wall_scene["candidate_pairs"]}

    numbers: dict[str, Any] = {
        "schema": NUMBERS_SCHEMA,
        "scene_counts": {
            "base_scene_count": len(base_scenes),
            "scale_count": len(SCALES),
            "ir_scene_count": len(all_scenes),
            "kappa_1_scene_count": len(base_scenes),
            "positive_base_scene_count": len(positive_base),
            "positive_ir_scene_count": len(positive_all),
        },
        "truth_pair_numbers": {
            "base_scenes_with_truth_pair_count": base_with_truth,
            "base_scene_truth_pair_ratio": base_with_truth / len(base_scenes),
            "positive_base_scenes_with_truth_pair_count": sum(bool(scene["truth_pairs"]) for scene in positive_base),
            "positive_base_scene_truth_pair_ratio": sum(bool(scene["truth_pairs"]) for scene in positive_base) / len(positive_base),
            "ir_scenes_with_truth_pair_count": all_with_truth,
            "ir_scene_truth_pair_ratio": all_with_truth / len(all_scenes),
            "positive_ir_scenes_with_truth_pair_count": sum(bool(scene["truth_pairs"]) for scene in positive_all),
            "positive_ir_scene_truth_pair_ratio": sum(bool(scene["truth_pairs"]) for scene in positive_all) / len(positive_all),
            "base_truth_pair_count": sum(len(scene["truth_pairs"]) for scene in base_scenes),
            "ir_truth_pair_count": sum(len(scene["truth_pairs"]) for scene in all_scenes),
        },
        "phenomenon_coverage": {
            name: {
                "scene_count": count,
                "scene_ratio": count / len(base_scenes),
            }
            for name, count in phenomenon_counts.items()
        },
        "mutation_family_coverage": {
            name: {
                "scene_count": count,
                "scene_ratio": count / len(base_scenes),
            }
            for name, count in mutation_counts.items()
        },
        "fidelity_numbers_kappa_1": {
            "entity_mix_tv": entity_tv,
            "thickness_histogram_ks": thickness_ks,
            "synthetic_entity_total": sum(synthetic_mix.values()),
            "reference_entity_total": sum(real_mix.values()),
            "synthetic_parallel_pair_offset_count": len(offsets),
            "synthetic_parallel_pair_offsets_in_histogram_count": sum(synthetic_hist),
            "reference_parallel_pair_offset_count": sum(real_hist_counts),
            "histogram_bin_count": len(real_hist_counts),
            "synthetic_entity_mix": dict(sorted(synthetic_mix.items())),
            "reference_entity_mix": dict(sorted(real_mix.items())),
            "histogram_edges": edges,
            "synthetic_thickness_histogram_counts": synthetic_hist,
            "reference_thickness_histogram_counts": real_hist_counts,
        },
        "sentinel_truth_integrity": {
            "zero_wall_scene_count": 1,
            "zero_wall_truth_pair_count": len(zero_scene["truth_pairs"]),
            "zero_wall_candidate_pair_count": len(zero_scene["candidate_pairs"]),
            "zero_wall_wall_face_handle_count": sum(entity["role"] == "wall_face" for entity in zero_scene["entities"]),
            "zero_wall_validation_error_count": len(zero_errors),
            "all_wall_scene_count": 1,
            "all_wall_truth_pair_count": len(all_wall_scene["truth_pairs"]),
            "all_wall_candidate_pair_count": len(all_wall_scene["candidate_pairs"]),
            "all_wall_candidate_truth_intersection_count": len(all_truth_ids & all_candidate_ids),
            "all_wall_candidate_truth_coverage_ratio": len(all_truth_ids & all_candidate_ids) / len(all_candidate_ids),
            "all_wall_validation_error_count": len(all_wall_errors),
        },
        "truth_validator": {
            "validated_ir_scene_count": len(all_scenes),
            "error_count": len(validation_errors),
        },
        "determinism_and_scale_numbers": {
            "unique_seed_count": len({scene["seed"] for scene in base_scenes}),
            "seed_collision_count": len(base_scenes) - len({scene["seed"] for scene in base_scenes}),
            "four_scale_topology_mismatch_base_scene_count": group_topology_mismatch_count,
            "four_scale_normalized_geometry_mismatch_base_scene_count": group_geometry_mismatch_count,
            "four_scale_source_handle_mismatch_base_scene_count": group_handle_mismatch_count,
        },
        "build_numbers": build_numbers,
        "reference_sha256": {
            "gen2_py": sha256_file(GEN2_PATH),
            "fidelity_stats_py": sha256_file(FIDELITY_STATS_PATH),
            "fidelity_histogram_json": sha256_file(fidelity.DEFAULT_REFERENCE_FIDELITY),
            "entity_mix_json": sha256_file(fidelity.DEFAULT_REFERENCE_ENTITY),
        },
    }
    return numbers, validation_errors


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def scene_filename(scene: dict[str, Any]) -> str:
    token = next(token for kappa, token in SCALES if math.isclose(kappa, scene["scale_kappa"]))
    return f"scene_{scene['base_scene_index']:03d}_k{token}.json"


def gen2_library_probe() -> tuple[set[str], int]:
    """Exercise the permitted generator in memory as a synthetic-only fixture."""
    gen2, _ = reference_modules()
    builder = gen2.DrawingBuilder(
        "M",
        seed_for_index(7),
        gen2.DEFAULT_ENTITY_RATIOS,
        entity_count=1,
        calibration_pairs=1,
    )
    builder.add_wall_segment("probe-line", (0, 0), (1000, 0), 180)
    builder.add_curved_wall("probe-arc", (2000, 2000), 700, 10, 120, 160)
    builder.add_wall_hatch(0, 0, 1000, 180)
    builder.add_hard_negatives()
    entity_types = {entity.dxftype() for entity in builder.msp}
    return entity_types, len(builder.walls)


def run_selftest(stream: io.TextIOBase) -> int:
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str) -> None:
        status = "PASS" if condition else "FAIL"
        print(f"[{status}] {name}: {detail}", file=stream)
        if not condition:
            failures.append(name)

    print("=== feyerabend_c0 selftest ===", file=stream)
    print(
        f"python={sys.version.split()[0]} numpy={np.__version__} ezdxf={ezdxf.__version__}",
        file=stream,
    )
    try:
        j = 7
        expected_seed = int.from_bytes(
            hashlib.sha256(f"{SEED_PREFIX}{j}".encode("utf-8")).digest()[:4],
            "big",
        )
        check(
            "seed_rule",
            seed_for_index(j) == expected_seed,
            f"j={j} seed={seed_for_index(j)} sha256_prefix={expected_seed}",
        )
        fixture_rows = fidelity_schedule()[j][:3]
        first = build_structural_scene(j, fixture_rows).finalize()
        second = build_structural_scene(j, fixture_rows).finalize()
        check(
            "same_j_same_sha",
            canonical_sha256(first) == canonical_sha256(second),
            f"j={j} sha256={canonical_sha256(first)}",
        )
        scaled = [scale_scene(first, kappa, token) for kappa, token in SCALES]
        topology_hashes = {scene["topology_sha256"] for scene in scaled}
        geometry_hashes = {scene["normalized_geometry_sha256"] for scene in scaled}
        check(
            "same_j_four_scale_topology",
            len(topology_hashes) == 1,
            f"kappas={[kappa for kappa, _ in SCALES]} unique_topology_sha={len(topology_hashes)}",
        )
        check(
            "same_j_four_scale_normalized_geometry",
            len(geometry_hashes) == 1,
            f"unique_normalized_geometry_sha={len(geometry_hashes)}",
        )
        positive_errors = [error for scene in scaled for error in validate_scene(scene)]
        check(
            "truth_validator_positive_cases",
            not positive_errors,
            f"scene_count={len(scaled)} error_count={len(positive_errors)}",
        )

        corrupted = copy.deepcopy(scaled[0])
        corrupted["truth_pairs"][0]["handles"][1] = "MISSING_SOURCE_HANDLE"
        corrupted["truth_pairs"][0]["pair_id"] = pair_id(
            corrupted["truth_pairs"][0]["handles"]
        )
        negative_errors = validate_scene(corrupted)
        check(
            "truth_validator_negative_case_honest_fail",
            bool(negative_errors),
            f"validator_status={'FAIL' if negative_errors else 'PASS'} error_count={len(negative_errors)}",
        )

        entity_types, wall_count = gen2_library_probe()
        required = {"LINE", "ARC", "SPLINE", "HATCH", "LWPOLYLINE"}
        check(
            "permitted_gen2_synthetic_fixture",
            wall_count >= 2 and required.issubset(entity_types),
            f"wall_records={wall_count} entity_types={sorted(entity_types)}",
        )
    except Exception as exc:  # evidence path
        failures.append("unexpected_exception")
        print(f"[FAIL] unexpected_exception: {type(exc).__name__}: {exc}", file=stream)
    if failures:
        print(f"SELFTEST_RESULT: FAIL ({len(failures)}): {', '.join(failures)}", file=stream)
        return 1
    print("SELFTEST_RESULT: PASS", file=stream)
    return 0


def render_report(numbers: dict[str, Any], selftest_transcript: str) -> str:
    numeric_text = json.dumps(
        numbers, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
    )
    lines = [
        "# Feyerabend C0 실행 보고서",
        "",
        "## 설계",
        "",
        f"- canonical base scene {BASE_SCENE_COUNT}개를 만들고 κ={{{', '.join(str(k) for k, _ in SCALES)}}}로 복제해 JSON IR {BASE_SCENE_COUNT * len(SCALES)}개를 생성했다.",
        "- seed는 각 j에 대해 SHA-256(`feyerabend_P2:`+j)의 첫 32 bit를 big-endian uint32로 해석했다. 별도 RNG나 random search는 사용하지 않았다.",
        "- 모든 scale copy는 같은 source handle, unordered truth pair, block/anchor topology를 보존한다. 좌표와 annotation geometry는 κ배이고 표시 치수는 canonical physical 값으로 유지되어 truth unit scale은 1/κ다.",
        "- truth는 실제 scene entity의 두 source handle을 가리킨다. zero-wall sentinel만 정의상 truth pair가 0개이며, 그 외 positive scene은 모두 1개 이상이다.",
        "- ARC/SPLINE/HATCH, LWPOLYLINE 분절, nested INSERT의 누적 비균일 transform, 비평행 조각, door/window/dimension형 hard negative를 IR에 명시했다.",
        "- gen2.py는 read-only import/call로 사용했고, fidelity_stats.py의 TV·histogram KS 정의를 κ=1 scene에 그대로 적용했다. 원본 CAD와 test split은 열지 않았다.",
        "- coverage_numbers.json과 아래 수치에는 KS/TV threshold 또는 C0 gate 판정을 넣지 않았다.",
        "",
        "## Selftest 전문",
        "",
        "```text",
        selftest_transcript.rstrip("\n"),
        "```",
        "",
        "## 커버리지·정합 수치 전문",
        "",
        "```json",
        numeric_text,
        "```",
        "",
        "## 미해결",
        "",
        "- zero-wall sentinel과 ‘각 scene truth pair ≥1’ 문구는 동시에 문자 그대로 만족할 수 없다. dossier의 ‘positive scene’ 조건을 따라 zero-wall 한 scene만 명시적 예외로 두었다.",
        "- entity TV와 thickness-histogram KS는 허용된 aggregate reference 통계를 직접 profile한 수치다. 낮은 거리는 분포 정합을 뜻하지만 CAD 의미 현실성이나 후속 C1/C2 판정을 대신하지 않는다.",
        "- nested transform과 nonparallel fragment는 synthetic IR 계약에서 검증했다. 원본 CAD에 대한 외적 검증은 packet의 접근 금지 범위 때문에 수행하지 않았다.",
        "- 실행 경계 메모: packet을 처음 읽은 진단 명령에 read-only `git rev-parse` 점검이 함께 들어갔고 `not a git repository`로 종료했다. Git 상태나 파일은 바뀌지 않았으며 이후 git 명령은 실행하지 않았다.",
        "- 이 셀은 C0 factory와 numeric qualification evidence만 산출한다. 봉인된 prereg threshold의 판정과 P2 이론 판별은 출력하지 않았다.",
        "",
        "CELL_COMPLETE: feyerabend_c0",
    ]
    return "\n".join(lines) + "\n"


def execute_full() -> int:
    selftest_buffer = io.StringIO()
    if run_selftest(selftest_buffer) != 0:
        print(selftest_buffer.getvalue(), end="")
        return 1

    base_scenes, build_numbers = build_base_corpus()
    all_scenes = [
        scale_scene(base_scene, kappa, token)
        for base_scene in base_scenes
        for kappa, token in SCALES
    ]
    numbers, validation_errors = aggregate_numbers(base_scenes, all_scenes, build_numbers)
    if validation_errors:
        print(f"truth validator found {len(validation_errors)} error(s)", file=sys.stderr)
        for error in validation_errors[:20]:
            print(error, file=sys.stderr)
        return 1

    SCENES_DIR.mkdir(parents=True, exist_ok=True)
    expected_paths: set[Path] = set()
    for scene in all_scenes:
        path = SCENES_DIR / scene_filename(scene)
        expected_paths.add(path.resolve())
        write_json(path, scene)
    for stale in SCENES_DIR.glob("scene_*.json"):
        if stale.resolve() not in expected_paths:
            stale.unlink()

    write_json(CELL_DIR / "coverage_numbers.json", numbers)
    (CELL_DIR / "REPORT.md").write_text(
        render_report(numbers, selftest_buffer.getvalue()), encoding="utf-8"
    )
    print(f"wrote {len(all_scenes)} IR scenes to {SCENES_DIR}")
    print(f"coverage_numbers={CELL_DIR / 'coverage_numbers.json'}")
    print(f"report={CELL_DIR / 'REPORT.md'}")
    print("CELL_COMPLETE: feyerabend_c0")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return run_selftest(sys.stdout)
    return execute_full()


if __name__ == "__main__":
    raise SystemExit(main())
