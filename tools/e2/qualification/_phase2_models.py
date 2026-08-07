"""Internal frozen-model adapters for the E2 model-assisted jury.

The adapters do not retrain, recalibrate, or select a checkpoint.  They reuse
the exact W4 transfer artifacts and report scores as uncalibrated transfer
evidence on this new DWG.  GBDT and GNN share the CubiCasa supervision family;
the caller must not count them as statistically independent truth sources.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import joblib
import numpy as np
import torch


MODEL_SEEDS = (17, 29, 43)
PHYSICAL_MM_PER_FROZEN_PIXEL = 12.0
INTERVENTIONS = (
    "rotate_37_degrees",
    "translate_large_offset",
    "scale_units_x1000_consistent",
    "strip_layer_names",
    "split_every_segment_at_midpoint",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import frozen jury module {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mean_by_parent(values: Mapping[str, float], parent_map: Mapping[str, str]) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for handle, value in values.items():
        grouped[str(parent_map.get(str(handle), str(handle)))].append(float(value))
    return {key: float(sum(group) / len(group)) for key, group in sorted(grouped.items())}


def _scale_mm_per_unit(ir: Mapping[str, Any]) -> float:
    try:
        value = float(ir.get("scale_mm_per_unit", 1.0))
    except (TypeError, ValueError) as exc:
        raise ValueError("seg IR scale_mm_per_unit must be numeric") from exc
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError("seg IR scale_mm_per_unit must be finite and positive")
    return value


def _frozen_pixel_space(ir: Mapping[str, Any]) -> dict[str, Any]:
    """Map physical coordinates to the frozen CubiCasa 12 mm/pixel contract."""

    output = copy.deepcopy(ir)
    factor = _scale_mm_per_unit(ir) / PHYSICAL_MM_PER_FROZEN_PIXEL
    for segment in output.get("segments", []) or []:
        segment["pts"] = [
            [float(point[0]) * factor, float(point[1]) * factor]
            for point in segment.get("pts", [])
        ]
    output["units"] = "frozen_cubicasa_pixel"
    output["scale_mm_per_unit"] = PHYSICAL_MM_PER_FROZEN_PIXEL
    return output


def transform_seg_ir(ir: Mapping[str, Any], intervention: str) -> tuple[dict[str, Any], dict[str, str]]:
    output = copy.deepcopy(ir)
    parent_map: dict[str, str] = {}
    if intervention == "split_every_segment_at_midpoint":
        children = []
        for segment in output.get("segments", []) or []:
            parent = str(segment.get("handle") or segment.get("sid"))
            p0, p1 = segment["pts"][0], segment["pts"][-1]
            midpoint = [(float(p0[0]) + float(p1[0])) / 2.0, (float(p0[1]) + float(p1[1])) / 2.0]
            for ordinal, points in enumerate(((p0, midpoint), (midpoint, p1))):
                child = dict(segment)
                child_handle = f"{parent}:split{ordinal}"
                child["handle"] = child_handle
                child["sid"] = child_handle
                child["pts"] = [list(points[0]), list(points[1])]
                children.append(child)
                parent_map[child_handle] = parent
        output["segments"] = children
        return output, parent_map

    if intervention == "strip_layer_names":
        for segment in output.get("segments", []) or []:
            handle = str(segment.get("handle") or segment.get("sid"))
            parent_map[handle] = handle
            segment["layer"] = ""
        return output, parent_map

    radians = math.radians(37.0)
    cosine, sine = math.cos(radians), math.sin(radians)
    for segment in output.get("segments", []) or []:
        handle = str(segment.get("handle") or segment.get("sid"))
        parent_map[handle] = handle
        transformed = []
        for x_raw, y_raw in segment.get("pts", []):
            x, y = float(x_raw), float(y_raw)
            if intervention == "rotate_37_degrees":
                transformed.append([cosine * x - sine * y, sine * x + cosine * y])
            elif intervention == "translate_large_offset":
                transformed.append([x + 1_000_000.0, y - 2_000_000.0])
            elif intervention == "scale_units_x1000_consistent":
                transformed.append([x * 1000.0, y * 1000.0])
            else:
                raise ValueError(f"unknown model-jury intervention {intervention}")
        segment["pts"] = transformed
    if intervention == "scale_units_x1000_consistent":
        output["scale_mm_per_unit"] = _scale_mm_per_unit(ir) / 1000.0
        output["units"] = "micrometre_coordinate_unit"
    return output, parent_map


class FrozenJury:
    """Load the sealed W4 model stack once and score arbitrary SEG-IR variants."""

    def __init__(self, transfer_harness: Path) -> None:
        self.transfer_harness_path = Path(transfer_harness)
        self.a4 = _load_module(self.transfer_harness_path, "e2_phase2_frozen_a4")
        self.integrity = self.a4.verify_integrity()
        self.components = self.a4.load_components()
        self.gbdt_bundle = joblib.load(self.a4.CLEAN_INCUMBENT_PATH)
        if "models_by_seed" not in self.gbdt_bundle:
            raise RuntimeError("frozen GBDT bundle has no models_by_seed")

    def artifact_receipt(self) -> dict[str, Any]:
        checks = {
            key: {
                **value,
                "role": (
                    "deterministic_geometry"
                    if key == "rules_library_py"
                    else "cubicasa_supervised"
                ),
            }
            for key, value in sorted(self.integrity.items())
        }
        return {
            "schema": "e2.frozen_jury_artifacts.v1",
            "status": "PASS" if all(row.get("match") for row in checks.values()) else "BLOCKED",
            "transfer_harness": {
                "path": str(self.transfer_harness_path),
                "sha256": _sha256(self.transfer_harness_path),
            },
            "checks": checks,
            "dependence_groups": {
                "rules": "deterministic_geometry",
                "gbdt": "cubicasa_supervised",
                "gnn": "cubicasa_supervised",
            },
            "warning": "GBDT and GNN differ architecturally but share CubiCasa supervision, so they count as one independent evidence family for silver promotion.",
        }
    def _score_one(self, ir: Mapping[str, Any], parent_map: Mapping[str, str]) -> dict[str, Any]:
        builder = self.components["builder"]
        graph_result = builder.build_graph(
            dict(ir), self.components["graph_config"], collect_edges=True
        )
        handles_gnn = [
            str(record["handle"])
            for record in graph_result["prepared"]["records"]
        ]
        rules_result = self.components["rules_lib"].evaluate(
            graph_result, builder.EDGE_TYPES
        )
        rules_scores = np.asarray(rules_result["score"], dtype=np.float64) / 16.0
        if rules_scores.shape != (len(handles_gnn),):
            raise RuntimeError("frozen A4 rules returned a non-node-aligned score vector")
        rules_raw = {
            handle: float(value) for handle, value in zip(handles_gnn, rules_scores)
        }

        pixel_ir = _frozen_pixel_space(ir)
        handles_gbdt, design = self.a4.build_gbdt_design(
            pixel_ir,
            self.components["w1_real_defs"],
            self.components["ce"],
            self.components["cml_ctx"],
        )
        seed_gbdt = [
            self.gbdt_bundle["models_by_seed"][seed].predict_proba(design)[:, 1].astype(np.float64)
            for seed in MODEL_SEEDS
        ]
        gbdt_raw = {
            handle: float(value)
            for handle, value in zip(handles_gbdt, np.mean(np.vstack(seed_gbdt), axis=0))
        }

        gf = self.components["gf"]
        sample = gf.graph_sample_from_result(
            graph_id="e2-phase2/new-dwg",
            drawing_id=str(ir.get("drawing_id") or "unknown"),
            family_id="new-dwg",
            split="unlabeled-transfer",
            result=graph_result,
            labels=np.zeros(len(handles_gnn), dtype=np.int8),
            eval_index=None,
        )
        seed_gnn = []
        with torch.no_grad():
            batch = gf.collate_graphs([sample], torch.device("cpu"))
            for seed in MODEL_SEEDS:
                model = self.components["gnn_models"][seed]
                model.eval()
                seed_gnn.append(torch.sigmoid(model(batch, "full")).cpu().numpy().astype(np.float64))
        gnn_raw = {
            handle: float(value)
            for handle, value in zip(handles_gnn, np.mean(np.vstack(seed_gnn), axis=0))
        }

        return {
            "rules": _mean_by_parent(rules_raw, parent_map),
            "gbdt": _mean_by_parent(gbdt_raw, parent_map),
            "gnn": _mean_by_parent(gnn_raw, parent_map),
            "diagnostics": {
                "input_segments": len(ir.get("segments", []) or []),
                "rule_scored_handles": len(rules_raw),
                "gbdt_scored_handles": len(gbdt_raw),
                "gnn_scored_handles": len(gnn_raw),
                "graph_edge_count": int(len(graph_result.get("edge_src", []))),
                "graph_feature_count": int(graph_result["features"].shape[1]),
                "gbdt_feature_count": int(design.shape[1]),
            },
        }

    def score_baseline(self, baseline_ir: Mapping[str, Any]) -> dict[str, Any]:
        """Score one unchanged SEG-IR population with every sealed baseline arm.

        This is the public, no-intervention entry point used by the L0 gold
        drawing.  It preserves the caller's stable handles and performs no
        training, threshold selection, or calibration.
        """

        identity = {
            str(segment.get("handle") or segment.get("sid")): str(
                segment.get("handle") or segment.get("sid")
            )
            for segment in baseline_ir.get("segments", []) or []
        }
        result = self._score_one(baseline_ir, identity)
        return {
            "schema": "e2.segment_juror_baseline.v1",
            "status": "FROZEN_TRANSFER_SCORES",
            **result,
        }

    def score_with_interventions(self, baseline_ir: Mapping[str, Any]) -> dict[str, Any]:
        identity = {
            str(segment.get("handle") or segment.get("sid")): str(segment.get("handle") or segment.get("sid"))
            for segment in baseline_ir.get("segments", []) or []
        }
        baseline = self._score_one(baseline_ir, identity)
        arms = {}
        for name in INTERVENTIONS:
            transformed, parent_map = transform_seg_ir(baseline_ir, name)
            arms[name] = self._score_one(transformed, parent_map)
        return {
            "schema": "e2.segment_juror_scores.v1",
            "status": "UNLABELED_TRANSFER_SCORES",
            "juror_contracts": {
                "rules": {
                    "dependence_group": "deterministic_geometry",
                    "interpretation": "hand-coded geometric evidence score, not probability",
                },
                "gbdt": {
                    "dependence_group": "cubicasa_supervised",
                    "interpretation": "frozen 3-seed ensemble score after explicit 12 mm/pixel unit normalization",
                },
                "gnn": {
                    "dependence_group": "cubicasa_supervised",
                    "interpretation": "frozen 3-seed graph score; known corpus-shortcut risk remains",
                },
            },
            "baseline": baseline,
            "interventions": arms,
        }
