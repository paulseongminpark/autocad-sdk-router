#!/usr/bin/env python3
"""E2 synthetic wall-pack generator v2.

This is an isolated, correct-by-construction generator.  It never reads CAD
source files.  It writes S2-compatible ``s2pack.v1`` manifests and ``wall.v1``
truth ledgers, while extending the ledger with an explicit ``class_of_handle``
scoring universe for hard negatives.

Usage:
  python gen2.py --selftest
  python gen2.py build --out packs_sample --seed 20260718 --n-per-tier 1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

import ezdxf


GENERATOR_SCHEMA = "ariadne.e2.gen2.v2"
MANIFEST_SCHEMA = "s2pack.v1"
TRUTH_SCHEMA = "wall.v1"
DXF_VERSION = "R2018"
TIERS = ("S", "F", "M")
TIER_SEED_OFFSETS = {"S": 0, "F": 100_000, "M": 200_000}

# Aggregate entity counts copied from the existing fidelity JSON statistics,
# not from a CAD file.  Ratios are exposed through --entity-ratios.
REAL_ENTITY_COUNTS = {
    "3DFACE": 34,
    "ARC": 2198,
    "CIRCLE": 141,
    "ELLIPSE": 201,
    "HATCH": 264,
    "INSERT": 1158,
    "LINE": 12110,
    "LWPOLYLINE": 7400,
    "MTEXT": 113,
    "POINT": 341,
    "POLYLINE": 1,
    "SPLINE": 3973,
    "TEXT": 154,
    "WIPEOUT": 33,
}
_REAL_ENTITY_TOTAL = sum(REAL_ENTITY_COUNTS.values())
DEFAULT_ENTITY_RATIOS = {
    key: value / _REAL_ENTITY_TOTAL for key, value in REAL_ENTITY_COUNTS.items()
}

# Existing fidelity_M_v2.json real thickness histogram.  The generator uses a
# downsampled, deterministic drafting-clutter population with this distribution.
REAL_THICKNESS_EDGES = [
    0, 1, 2, 5, 10, 25, 50, 75, 100, 125, 150, 175, 200, 250, 300,
    400, 500, 750, 1000, 1500, 2500, 5000, 10000, 20000, 50000, 300000,
]
REAL_THICKNESS_COUNTS = [
    39, 75, 144, 140, 535, 226, 318, 193, 155, 208, 97, 77, 88,
    183, 233, 146, 298, 347, 316, 264, 289, 298, 178, 9, 21,
]

REQUIRED_HARD_NEGATIVE_CLASSES = {
    "dimension_helper",
    "door_frame",
    "furniture_bed",
    "furniture_desk",
    "furniture_storage",
    "stair_tread",
    "direction_arrow",
    "room_boundary",
}
REQUIRED_DIVERSE_TYPES = {
    "SPLINE", "ARC", "HATCH", "TEXT", "MTEXT", "CIRCLE"
}

LAYER_COLORS = {
    "WALL": 7,
    "WALL-FILL": 8,
    "DOOR": 3,
    "DIM": 2,
    "FURN": 4,
    "STAIR": 5,
    "ANNO": 6,
    "ROOM": 1,
    "FLOOR": 9,
    "MESSY": 30,
    "CALIBRATION-CONTEXT": 250,
    "PROFILE-FILL": 251,
}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_doc() -> ezdxf.document.Drawing:
    """Create a DXF whose volatile header fields are deterministic."""
    previous_fixed_metadata = ezdxf.options.write_fixed_meta_data_for_testing
    ezdxf.options.write_fixed_meta_data_for_testing = True
    try:
        doc = ezdxf.new(DXF_VERSION)
    finally:
        ezdxf.options.write_fixed_meta_data_for_testing = previous_fixed_metadata
    fixed_julian = 2451544.5  # 2000-01-01T00:00:00Z
    for key in ("$TDCREATE", "$TDUCREATE", "$TDUPDATE", "$TDUUPDATE"):
        doc.header[key] = fixed_julian
    doc.header["$TDINDWG"] = 0.0
    doc.header["$TDUSRTIMER"] = 0.0
    doc.header["$USRTIMER"] = 0
    doc.header["$FINGERPRINTGUID"] = "{00000000-0000-0000-0000-000000000002}"
    doc.header["$VERSIONGUID"] = "{00000000-0000-0000-0000-000000000002}"
    doc.header["$INSUNITS"] = 4  # millimetres
    for name, color in LAYER_COLORS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)
    return doc


def _normal(p0, p1):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy)
    if length <= 0:
        raise ValueError("zero-length axis")
    return -dy / length, dx / length


def _offset_segment(p0, p1, offset):
    nx, ny = _normal(p0, p1)
    return (
        (p0[0] + nx * offset, p0[1] + ny * offset),
        (p1[0] + nx * offset, p1[1] + ny * offset),
    )


def _allocate_hist_samples(counts, n):
    """Largest-remainder allocation that sums exactly to n."""
    total = sum(counts)
    raw = [n * count / total for count in counts]
    allocated = [int(math.floor(value)) for value in raw]
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - allocated[i]), i))
    for i in order[: n - sum(allocated)]:
        allocated[i] += 1
    return allocated


def _load_ratios(value: str | None):
    if not value:
        return dict(DEFAULT_ENTITY_RATIOS)
    candidate = Path(value)
    if candidate.is_file():
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    else:
        payload = json.loads(value)
    ratios = {str(k).upper(): float(v) for k, v in payload.items() if float(v) >= 0}
    mass = sum(ratios.values())
    if mass <= 0:
        raise ValueError("entity ratios must have positive total mass")
    return {key: value / mass for key, value in ratios.items()}


class DrawingBuilder:
    def __init__(self, tier: str, seed: int, entity_ratios, entity_count: int,
                 calibration_pairs: int):
        self.tier = tier
        self.seed = int(seed)
        self.rng = random.Random(self.seed)
        self.entity_ratios = dict(entity_ratios)
        self.entity_count = int(entity_count)
        self.calibration_pairs = int(calibration_pairs)
        self.doc = _stable_doc()
        self.msp = self.doc.modelspace()
        self.walls = []
        self.openings = []
        self.class_of_handle = {}
        self.variants = set()

    def label(self, entity, class_name: str):
        handle = str(entity.dxf.handle)
        if handle in self.class_of_handle:
            raise AssertionError(f"handle {handle} labeled twice")
        self.class_of_handle[handle] = class_name
        return handle

    def add_wall_segment(self, wall_id, p0, p1, thickness, *, polyline=False,
                         variant="straight", thickness_end=None):
        thickness_end = float(thickness if thickness_end is None else thickness_end)
        p0 = tuple(map(float, p0))
        p1 = tuple(map(float, p1))
        nx, ny = _normal(p0, p1)
        handles = []
        for side in (1.0, -1.0):
            q0 = (p0[0] + nx * float(thickness) * 0.5 * side,
                  p0[1] + ny * float(thickness) * 0.5 * side)
            q1 = (p1[0] + nx * thickness_end * 0.5 * side,
                  p1[1] + ny * thickness_end * 0.5 * side)
            if polyline or thickness_end != float(thickness):
                entity = self.msp.add_lwpolyline(
                    [q0, q1], format="xy", dxfattribs={"layer": "WALL"}
                )
            else:
                entity = self.msp.add_line(q0, q1, dxfattribs={"layer": "WALL"})
            handles.append(self.label(entity, "wall"))
        self.walls.append({
            "id": wall_id,
            "axis": [list(p0), list(p1)],
            "thickness": (float(thickness) + thickness_end) / 2.0,
            "thickness_range": [float(thickness), thickness_end],
            "layer": "WALL",
            "handles": handles,
            "geometry_kind": "line",
            "variant": variant,
        })
        self.variants.add(variant)

    def add_curved_wall(self, wall_id, center, radius, start_angle, end_angle, thickness):
        handles = []
        for radial in (-0.5, 0.5):
            entity = self.msp.add_arc(
                center, radius + radial * thickness, start_angle, end_angle,
                dxfattribs={"layer": "WALL"},
            )
            handles.append(self.label(entity, "wall"))
        a0 = math.radians(start_angle)
        a1 = math.radians(end_angle)
        self.walls.append({
            "id": wall_id,
            "axis": [
                [center[0] + radius * math.cos(a0), center[1] + radius * math.sin(a0)],
                [center[0] + radius * math.cos(a1), center[1] + radius * math.sin(a1)],
            ],
            "arc": {"center": list(center), "radius": radius,
                    "start_angle": start_angle, "end_angle": end_angle},
            "thickness": float(thickness),
            "thickness_range": [float(thickness), float(thickness)],
            "layer": "WALL",
            "handles": handles,
            "geometry_kind": "arc",
            "variant": "curved",
        })
        self.variants.add("curved")

    def add_wall_hatch(self, x0, y0, x1, y1):
        hatch = self.msp.add_hatch(dxfattribs={"layer": "WALL-FILL"})
        hatch.set_solid_fill(color=8)
        hatch.paths.add_polyline_path(
            [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], is_closed=True
        )

    def add_floor_hatch(self, x0, y0, x1, y1):
        hatch = self.msp.add_hatch(dxfattribs={"layer": "FLOOR"})
        hatch.set_pattern_fill("ANSI31", scale=120.0)
        hatch.paths.add_polyline_path(
            [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], is_closed=True
        )

    def build_walls(self):
        # Open-plan boundary: deliberate gaps in the upper and right sides.
        self.add_wall_segment("w01", (0, 0), (9000, 0), 240, variant="open_plan")
        self.add_wall_segment("w02", (0, 0), (0, 6500), 180, polyline=True,
                              variant="thickness_change", thickness_end=300)
        self.add_wall_segment("w03", (0, 6500), (3600, 6500), 220,
                              variant="open_plan")
        self.add_wall_segment("w04", (5100, 6500), (9000, 6500), 260,
                              variant="open_plan")
        self.add_wall_segment("w05", (9000, 0), (9000, 2500), 150,
                              variant="partial")
        self.add_wall_segment("w06", (9000, 3900), (9000, 6500), 320,
                              variant="partial")
        self.add_wall_segment("w07", (3200, 0), (3200, 4100), 120,
                              variant="partial")
        self.add_wall_segment("w08", (3200, 4850), (3200, 6500), 210,
                              variant="partial")
        if self.tier in ("F", "M"):
            self.add_curved_wall("w09", (6500, 3100), 1350, 195, 345, 200)
        if self.tier == "M":
            self.add_wall_segment("w10", (1100, 1800), (5100, 2020), 90,
                                  polyline=True, variant="messy_nonparallel",
                                  thickness_end=360)
            # Visually nearby fragment with a slightly different angle.
            fragment = self.msp.add_line(
                (1200, 2310), (3400, 2480), dxfattribs={"layer": "MESSY"}
            )
            self.label(fragment, "messy_fragment")
            self.variants.add("messy_nonparallel")
        self.add_wall_hatch(100, -120, 2800, 120)
        self.add_floor_hatch(350, 350, 2750, 1550)

    def add_opening_entities(self):
        if self.tier == "S":
            return
        # Door swing ARC and jamb CIRCLE supply explicit opening geometry.
        arc = self.msp.add_arc(
            (3200, 4100), 750, 0, 90, dxfattribs={"layer": "DOOR"}
        )
        self.label(arc, "door_swing")
        circle = self.msp.add_circle(
            (3200, 4100), 35, dxfattribs={"layer": "DOOR"}
        )
        self.label(circle, "door_hardware")
        self.openings.append({
            "id": "o01", "wall_id": "w08", "span_along_axis": [0.0, 0.45],
            "type": "door",
        })
        if self.tier == "M":
            arc2 = self.msp.add_arc(
                (9000, 2500), 1050, 90, 180, dxfattribs={"layer": "DOOR"}
            )
            self.label(arc2, "door_swing")
            self.openings.append({
                "id": "o02", "wall_id": "w06", "span_along_axis": [0.0, 0.4],
                "type": "door",
            })

    def add_hard_negatives(self):
        # 1) Dimension helper pair at a wall-like gap, plus dimension text.
        for y in (20_000, 20_180):
            entity = self.msp.add_line((20_000, y), (24_700, y), dxfattribs={"layer": "DIM"})
            self.label(entity, "dimension_helper")
        dim_tick = self.msp.add_line((20_000, 19_900), (20_000, 20_280), dxfattribs={"layer": "DIM"})
        self.label(dim_tick, "dimension_helper")
        text = self.msp.add_text("4700", height=180, dxfattribs={"layer": "DIM"})
        text.set_placement((22_100, 20_320))
        self.label(text, "dimension_text")
        mtext = self.msp.add_mtext("CLEAR DIMENSION", dxfattribs={"layer": "DIM", "char_height": 150})
        mtext.set_location((20_200, 20_550))
        self.label(mtext, "dimension_text")

        # 2) Door-frame double jambs: each jamb is a wall-band parallel pair.
        for x0 in (30_000, 31_200):
            for x in (x0, x0 + 120):
                entity = self.msp.add_line((x, 30_000), (x, 30_900), dxfattribs={"layer": "DOOR"})
                self.label(entity, "door_frame")

        # 3) Furniture double outlines (bed, desk, storage) with 100-140 mm gap.
        furniture = [
            ("furniture_bed", 40_000, 40_000, 2100, 1100, 120),
            ("furniture_desk", 50_000, 50_000, 1600, 750, 100),
            ("furniture_storage", 60_000, 60_000, 1800, 600, 140),
        ]
        for class_name, x, y, w, h, gap in furniture:
            outer = self.msp.add_lwpolyline(
                [(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
                format="xy", close=True, dxfattribs={"layer": "FURN"},
            )
            inner = self.msp.add_lwpolyline(
                [(x + gap, y + gap), (x + w - gap, y + gap),
                 (x + w - gap, y + h - gap), (x + gap, y + h - gap)],
                format="xy", close=True, dxfattribs={"layer": "FURN"},
            )
            self.label(outer, class_name)
            self.label(inner, class_name)
            # Furniture/free-curve SPLINE is a separate visible feature.
            spline = self.msp.add_spline(
                [(x + 100, y + h * 0.5), (x + w * 0.35, y + h * 0.8),
                 (x + w * 0.65, y + h * 0.2), (x + w - 100, y + h * 0.5)],
                degree=3, dxfattribs={"layer": "FURN"},
            )
            self.label(spline, class_name)

        # 4) Stair treads: repeated parallel lines at wall-like spacing.
        for i in range(9):
            y = 70_000 + i * 250
            tread = self.msp.add_line((70_000, y), (71_900, y), dxfattribs={"layer": "STAIR"})
            self.label(tread, "stair_tread")

        # 5) Direction-arrow shaft has 100 mm parallel sides.
        arrow = self.msp.add_lwpolyline(
            [(80_000, 80_200), (81_200, 80_200), (81_200, 80_000), (81_900, 80_400),
             (81_200, 80_800), (81_200, 80_600), (80_000, 80_600),
             (80_000, 80_500), (81_050, 80_500), (81_050, 80_300), (80_000, 80_300)],
            format="xy", close=True, dxfattribs={"layer": "ANNO"},
        )
        self.label(arrow, "direction_arrow")

        # 6) Room-boundary double polylines, offset 160 mm.
        for inset in (0, 160):
            room = self.msp.add_lwpolyline(
                [(90_000 + inset, 90_000 + inset), (93_900 - inset, 90_000 + inset),
                 (93_900 - inset, 93_200 - inset), (90_000 + inset, 93_200 - inset)],
                format="xy", close=True, dxfattribs={"layer": "ROOM"},
            )
            self.label(room, "room_boundary")

        # Circle marker and curved furniture arc ensure diversity independent of tiers.
        marker = self.msp.add_circle((95_000, 95_000), 300, dxfattribs={"layer": "ANNO"})
        self.label(marker, "direction_symbol")
        curve = self.msp.add_arc((95_000, 95_000), 700, 15, 160, dxfattribs={"layer": "FURN"})
        self.label(curve, "furniture_curve")

    def add_reference_parallel_context(self):
        allocations = _allocate_hist_samples(REAL_THICKNESS_COUNTS, self.calibration_pairs)
        sample_index = 0
        for bin_index, amount in enumerate(allocations):
            lo, hi = REAL_THICKNESS_EDGES[bin_index], REAL_THICKNESS_EDGES[bin_index + 1]
            for _ in range(amount):
                # Keep each pair's x projection disjoint so it contributes exactly one
                # intended offset and does not cross-pair with its neighbours.
                x0 = 100_000 + sample_index * 2200
                length = 1200.0
                gap = lo + (hi - lo) * (0.2 + 0.6 * self.rng.random())
                if gap <= 1e-6:
                    gap = 0.5
                y0 = 20_000 + (sample_index % 7) * 17
                self.msp.add_line(
                    (x0, y0), (x0 + length, y0),
                    dxfattribs={"layer": "CALIBRATION-CONTEXT"},
                )
                self.msp.add_line(
                    (x0, y0 + gap), (x0 + length, y0 + gap),
                    dxfattribs={"layer": "CALIBRATION-CONTEXT"},
                )
                sample_index += 1

    def entity_counts(self):
        return Counter(entity.dxftype() for entity in self.msp)

    def _profile_target_total(self, existing):
        total = max(self.entity_count, sum(existing.values()))
        for entity_type, count in existing.items():
            ratio = self.entity_ratios.get(entity_type, 0.0)
            if ratio > 0:
                total = max(total, int(math.ceil(count / ratio)))
        return total

    def _add_profile_entity(self, entity_type, i):
        # Every filler occupies a distinct local interval.  LINE/LWPOLYLINE fillers
        # are vertical and y-disjoint, avoiding artificial parallel-pair samples.
        x = 1_000_000 + (i % 200) * 40
        y = 1_000_000 + i * 30
        layer = "PROFILE-FILL"
        if entity_type == "LINE":
            self.msp.add_line((x, y), (x, y + 10), dxfattribs={"layer": layer})
        elif entity_type == "LWPOLYLINE":
            self.msp.add_lwpolyline([(x, y), (x, y + 10)], format="xy",
                                    dxfattribs={"layer": layer})
        elif entity_type == "SPLINE":
            self.msp.add_spline(
                [(x, y), (x + 8, y + 15), (x + 16, y - 5), (x + 24, y + 10)],
                degree=3, dxfattribs={"layer": layer},
            )
        elif entity_type == "ARC":
            self.msp.add_arc((x, y), 12, 15, 145, dxfattribs={"layer": layer})
        elif entity_type == "CIRCLE":
            self.msp.add_circle((x, y), 8, dxfattribs={"layer": layer})
        elif entity_type == "ELLIPSE":
            self.msp.add_ellipse((x, y), (12, 0), ratio=0.45,
                                 dxfattribs={"layer": layer})
        elif entity_type == "HATCH":
            hatch = self.msp.add_hatch(dxfattribs={"layer": layer})
            hatch.set_pattern_fill("ANSI31", scale=5.0)
            hatch.paths.add_polyline_path(
                [(x, y), (x + 20, y), (x + 20, y + 20), (x, y + 20)],
                is_closed=True,
            )
        elif entity_type == "TEXT":
            text = self.msp.add_text("D", height=8, dxfattribs={"layer": layer})
            text.set_placement((x, y))
        elif entity_type == "MTEXT":
            text = self.msp.add_mtext("NOTE", dxfattribs={"layer": layer, "char_height": 8})
            text.set_location((x, y))
        elif entity_type == "POINT":
            self.msp.add_point((x, y), dxfattribs={"layer": layer})
        elif entity_type == "3DFACE":
            self.msp.add_3dface(
                [(x, y, 0), (x + 20, y, 0), (x + 20, y + 20, 0), (x, y + 20, 0)],
                dxfattribs={"layer": layer},
            )
        elif entity_type == "POLYLINE":
            self.msp.add_polyline2d([(x, y), (x, y + 10)], dxfattribs={"layer": layer})
        elif entity_type == "WIPEOUT":
            self.msp.add_wipeout(
                [(x, y), (x + 20, y), (x + 20, y + 20), (x, y + 20)],
                dxfattribs={"layer": layer},
            )
        elif entity_type == "INSERT":
            block_name = "PROFILE-SYMBOL"
            if block_name not in self.doc.blocks:
                block = self.doc.blocks.new(block_name)
                block.add_circle((0, 0), 4, dxfattribs={"layer": layer})
                block.add_line((-4, 0), (4, 0), dxfattribs={"layer": layer})
            self.msp.add_blockref(block_name, (x, y), dxfattribs={"layer": layer})

    def fill_entity_profile(self):
        existing = self.entity_counts()
        total = self._profile_target_total(existing)
        desired = {
            entity_type: int(round(total * ratio))
            for entity_type, ratio in self.entity_ratios.items()
        }
        # Required diverse types are never allowed to round to zero.
        for entity_type in REQUIRED_DIVERSE_TYPES:
            desired[entity_type] = max(1, desired.get(entity_type, 0))
        fill_index = 0
        for entity_type in sorted(desired):
            need = max(0, desired[entity_type] - existing.get(entity_type, 0))
            for _ in range(need):
                self._add_profile_entity(entity_type, fill_index)
                fill_index += 1

    def render(self, path: Path, drawing_id: str):
        self.build_walls()
        self.add_opening_entities()
        self.add_hard_negatives()
        self.add_reference_parallel_context()
        self.fill_entity_profile()
        path.parent.mkdir(parents=True, exist_ok=True)
        # ClassesSection otherwise registers types from a set and can serialize
        # LAYOUT/ACDBPLACEHOLDER in hash-order.  Pre-registering the sorted types
        # makes the CLASSES section stable without changing drawing semantics.
        for entity_type in sorted(self.doc.entitydb.dxf_types_in_use()):
            self.doc.classes.add_class(entity_type)
        # ezdxf normally renews $VERSIONGUID/$TDUPDATE on every write.  Its
        # fixed-metadata mode preserves a byte-identical artifact for a seed.
        previous_fixed_metadata = ezdxf.options.write_fixed_meta_data_for_testing
        ezdxf.options.write_fixed_meta_data_for_testing = True
        try:
            self.doc.saveas(path)
        finally:
            ezdxf.options.write_fixed_meta_data_for_testing = previous_fixed_metadata

        wall_handles = [handle for wall in self.walls for handle in wall["handles"]]
        negative_classes = Counter(
            class_name for handle, class_name in self.class_of_handle.items()
            if handle not in set(wall_handles)
        )
        truth = {
            "truth": TRUTH_SCHEMA,
            "truth_extension": "wall.v2.classes",
            "drawing_id": drawing_id,
            "tier": self.tier,
            "seed": self.seed,
            "walls": self.walls,
            "openings": self.openings,
            "wall_handles_flat": wall_handles,
            "class_of_handle": dict(sorted(self.class_of_handle.items())),
            "class_counts": dict(sorted(Counter(self.class_of_handle.values()).items())),
            "negative_class_counts": dict(sorted(negative_classes.items())),
            "wall_variants": sorted(self.variants),
            "entity_mix": dict(sorted(self.entity_counts().items())),
            "generator": GENERATOR_SCHEMA,
        }
        return truth


def build_tier_pack(outdir: Path, tier: str, seeds, *, entity_ratios,
                    entity_count: int, calibration_pairs: int):
    outdir.mkdir(parents=True, exist_ok=True)
    files = []
    for index, seed in enumerate(seeds):
        drawing_id = f"{index:04d}"
        dxf_path = outdir / f"{drawing_id}.dxf"
        truth_path = outdir / f"{drawing_id}.truth.json"
        builder = DrawingBuilder(
            tier, seed, entity_ratios, entity_count, calibration_pairs
        )
        truth = builder.render(dxf_path, drawing_id)
        _write_json(truth_path, truth)
        files.append({
            "drawing_id": drawing_id,
            "dxf": dxf_path.name,
            "truth": truth_path.name,
            "seed": seed,
            "dxf_sha256": _sha256(dxf_path),
            "truth_sha256": _sha256(truth_path),
        })
    manifest = {
        "manifest": MANIFEST_SCHEMA,
        "generator": GENERATOR_SCHEMA,
        "tier": tier,
        "n": len(seeds),
        "seed": seeds[0] if seeds else None,
        "seeds": list(seeds),
        "noise_level": 3 if tier == "M" else None,
        "dxf_version": DXF_VERSION,
        "truth_schema": TRUTH_SCHEMA,
        "truth_extension": "wall.v2.classes",
        "created_utc": "deterministic-from-seed",
        "entity_ratios": dict(sorted(entity_ratios.items())),
        "entity_target_count": entity_count,
        "reference_parallel_pairs": calibration_pairs,
        "files": files,
    }
    _write_json(outdir / "manifest.json", manifest)
    return manifest


def build_pack_root(outdir: Path, base_seed: int, n_per_tier: int, *,
                    entity_ratios, entity_count: int, calibration_pairs: int):
    tier_records = {}
    for tier in TIERS:
        seeds = [base_seed + TIER_SEED_OFFSETS[tier] + i for i in range(n_per_tier)]
        manifest = build_tier_pack(
            outdir / tier,
            tier,
            seeds,
            entity_ratios=entity_ratios,
            entity_count=entity_count,
            calibration_pairs=calibration_pairs,
        )
        tier_records[tier] = {
            "manifest": f"{tier}/manifest.json",
            "n": manifest["n"],
            "seeds": manifest["seeds"],
        }
    root = {
        "manifest": "s2pack-set.v2",
        "generator": GENERATOR_SCHEMA,
        "base_seed": base_seed,
        "tiers": tier_records,
    }
    _write_json(outdir / "manifest.json", root)
    return root


def _tree_hashes(root: Path):
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def selftest() -> int:
    print("=== gen2 selftest ===")
    print(f"python={sys.version.split()[0]} ezdxf={ezdxf.__version__}")
    temp = Path(tempfile.mkdtemp(prefix="e2_gen2_selftest_"))
    first = temp / "first"
    second = temp / "second"
    failures = []

    def check(name, condition, detail):
        status = "OK" if condition else "FAIL"
        print(f"[{status}] {name}: {detail}")
        if not condition:
            failures.append(name)

    try:
        kwargs = {
            "base_seed": 424242,
            "n_per_tier": 1,
            "entity_ratios": DEFAULT_ENTITY_RATIOS,
            "entity_count": 700,
            "calibration_pairs": 72,
        }
        build_pack_root(first, **kwargs)
        check("pack_created", (first / "manifest.json").is_file(), str(first))

        union_negative_classes = set()
        union_entity_types = set()
        for tier in TIERS:
            manifest = json.loads((first / tier / "manifest.json").read_text(encoding="utf-8"))
            check(f"{tier}_manifest", manifest.get("manifest") == MANIFEST_SCHEMA,
                  f"schema={manifest.get('manifest')} n={manifest.get('n')}")
            entry = manifest["files"][0]
            dxf_path = first / tier / entry["dxf"]
            truth_path = first / tier / entry["truth"]
            try:
                doc = ezdxf.readfile(dxf_path)
                parsed = True
            except Exception as exc:  # pragma: no cover - evidence path
                doc = None
                parsed = False
                failures.append(f"{tier}_ezdxf_parse")
                print(f"[FAIL] {tier}_ezdxf_parse: {exc}")
            if not parsed:
                continue
            check(f"{tier}_ezdxf_parse", True,
                  f"version={doc.dxfversion} entities={len(doc.modelspace())}")
            truth = json.loads(truth_path.read_text(encoding="utf-8"))
            handles = {str(entity.dxf.handle) for entity in doc.modelspace()}
            classes = truth.get("class_of_handle", {})
            walls = set(truth.get("wall_handles_flat", []))
            class_handles = set(classes)
            missing = sorted(class_handles - handles)
            check(f"{tier}_ledger_handles", not missing,
                  f"labeled={len(class_handles)} missing={len(missing)}")
            check(f"{tier}_wall_class", all(classes.get(h) == "wall" for h in walls),
                  f"walls={len(walls)}")
            negative_handles = class_handles - walls
            wall_frac = len(walls) / len(class_handles) if class_handles else 0.0
            check(f"{tier}_negative_present", bool(negative_handles),
                  f"wall={len(walls)} negative={len(negative_handles)}")
            check(f"{tier}_wall_frac", 0.15 <= wall_frac <= 0.60,
                  f"wall_frac={wall_frac:.6f}")
            union_negative_classes.update(classes[h] for h in negative_handles)
            union_entity_types.update(entity.dxftype() for entity in doc.modelspace())

        missing_classes = sorted(REQUIRED_HARD_NEGATIVE_CLASSES - union_negative_classes)
        check("hard_negative_classes", not missing_classes,
              f"required={len(REQUIRED_HARD_NEGATIVE_CLASSES)} missing={missing_classes}")
        missing_types = sorted(REQUIRED_DIVERSE_TYPES - union_entity_types)
        check("entity_diversity", not missing_types,
              f"observed={sorted(union_entity_types)} missing={missing_types}")

        build_pack_root(second, **kwargs)
        hashes_first = _tree_hashes(first)
        hashes_second = _tree_hashes(second)
        differing = sorted(
            key for key in set(hashes_first) | set(hashes_second)
            if hashes_first.get(key) != hashes_second.get(key)
        )
        check("seed_reproducibility", not differing,
              f"files={len(hashes_first)} differing={differing}")
    except Exception as exc:  # noqa: BLE001
        failures.append("unexpected_exception")
        print(f"[FAIL] unexpected_exception: {type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(temp, ignore_errors=True)
        print(f"temp_cleaned={temp}")

    if failures:
        print(f"SELFTEST_RESULT: FAIL ({len(failures)}): {', '.join(failures)}")
        return 1
    print("SELFTEST_RESULT: PASS")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="E2 synthetic wall-pack generator v2")
    parser.add_argument("--selftest", action="store_true")
    sub = parser.add_subparsers(dest="command")
    build = sub.add_parser("build", help="build one S/F/M pack set")
    build.add_argument("--out", required=True)
    build.add_argument("--seed", type=int, default=20260718)
    build.add_argument("--n-per-tier", type=int, default=1)
    build.add_argument("--entity-count", type=int, default=1400)
    build.add_argument("--calibration-pairs", type=int, default=600)
    build.add_argument(
        "--entity-ratios",
        help="JSON object or path mapping DXF entity type to desired ratio",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.selftest:
        return selftest()
    if args.command == "build":
        if args.n_per_tier < 1 or args.entity_count < 1 or args.calibration_pairs < 1:
            print("ERROR: n-per-tier, entity-count, and calibration-pairs must be positive",
                  file=sys.stderr)
            return 2
        ratios = _load_ratios(args.entity_ratios)
        out = Path(args.out).resolve()
        build_pack_root(
            out,
            args.seed,
            args.n_per_tier,
            entity_ratios=ratios,
            entity_count=args.entity_count,
            calibration_pairs=args.calibration_pairs,
        )
        print(f"built S/F/M pack set: {out}")
        return 0
    build_parser().print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
