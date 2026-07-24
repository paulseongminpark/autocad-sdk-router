"""onto_constraint_real_v1 — FROZEN domain-axiom rule library for wall detection
on real CubiCasa SEG-IR.

Contract
--------
Input  : a graph_builder.build_graph(ir, GraphConfig(), collect_edges=True) result
         dict (17-dim node feature matrix + directed typed edges + prepared records)
         plus the builder's EDGE_TYPES tuple.
Output : per-node integer violation/consistency flag for each axiom (1 = the wall
         axiom's antecedent holds for this handle) and the weighted-sum score
         (every rule weight = 1, fixed, no learning).

The score is NOT calibrated and NOT thresholded here; downstream scoring
(average_precision_score against the sealed SEG-IR wall labels) and residual
capture consume `score` and `flags` directly.

Provenance
----------
Every threshold below was compiled by inspecting the CubiCasa **train** split
(runs/e2_ext_cubicasa/ir/train, 4200 drawings) only — feature distributions of
wall vs non-wall handles and per-axiom precision lift over ~250 train drawings.
The val-A DEV split was never inspected during compilation. See PREREG_local.json
(sealed) for the frozen schema, categories, and stop condition. This file is
frozen: once its SHA-256 is recorded in PREREG_local.json, no rule may be
added / removed / edited (a revision requires a new prereg).

All flags are POSITIVE wall-evidence: a handle satisfying more wall axioms scores
higher, so the weighted sum ranks wall-consistent handles above the rest. The
truth namespace is CubiCasa 'wall_handles_flat' (Wall + Wall External classes).
"""
from __future__ import annotations

from collections import OrderedDict
import numpy as np

LIBRARY_ID = "onto_constraint_real_v1"
FEATURE_NAMES = (
    "log1p_length_norm", "midpoint_x_drawing_norm", "midpoint_y_drawing_norm",
    "bbox_width_norm", "bbox_height_norm", "sin_2theta", "cos_2theta",
    "sagitta_norm", "closed_geometry", "kind_line", "kind_poly_edge",
    "kind_arc_chord", "log1p_endpoint_degree", "log1p_junction_count",
    "log1p_parallel_count", "log1p_collinear_count", "block_depth_norm",
)
FEATURE_INDEX = {name: i for i, name in enumerate(FEATURE_NAMES)}

# Adjacency thresholds (dimensionless length ratios) compiled from train.
SHORTER_COLLINEAR_RATIO = 0.6   # opening insert is <0.6x the hosting wall's length
SIMILAR_PARALLEL_LO = 0.5       # wall face partner within 0.5x .. 2.0x length
SIMILAR_PARALLEL_HI = 2.0

# Rule catalogue. Each entry: (id, category, natural-language axiom, rationale).
# Thresholds live in _flag_table so the code and the metadata stay in one file.
RULES = (
    ("A1_length_tier_1", "wall_topology",
     "A wall element is longer than roughly the drawing's median segment "
     "(log1p_length_norm >= 1.0).",
     "Kills sub-median annotation/fixture strokes (Direction, DimensionMark, "
     "Faucet). Train P(wall|fire)=0.149, lift 1.28."),
    ("A2_length_tier_2", "wall_topology",
     "A wall element is clearly supra-median in length "
     "(log1p_length_norm >= 1.5).",
     "Intermediate length tier; train lift 1.67."),
    ("A3_length_tier_3", "wall_topology",
     "A wall element is a long structural run (log1p_length_norm >= 2.0).",
     "Long segments are dominated by walls/boundaries; train lift 2.45."),
    ("A4_length_tier_4", "wall_topology",
     "A wall element can be a dominant-length spine (log1p_length_norm >= 3.0).",
     "The longest strokes in a plan are predominantly external/party walls; "
     "train lift 4.79."),

    ("B1_junction_hub_1", "connectivity",
     "A wall meets several crossing segments at intersection junctions "
     "(intersection_junction fan-out >= 6).",
     "Walls form the crossing skeleton of the plan; train lift 1.47."),
    ("B2_junction_hub_2", "connectivity",
     "A wall is a heavy junction hub (intersection_junction fan-out >= 14).",
     "Dense crossing count concentrates on walls; train lift 2.87."),
    ("B3_endpoint_degree_1", "connectivity",
     "A wall endpoint is shared with other segments (endpoint_degree >= 3).",
     "Walls terminate into corners/T-junctions rather than free ends; "
     "train lift 1.68."),
    ("B4_endpoint_degree_2", "connectivity",
     "A wall endpoint is a strong hub (endpoint_degree >= 8).",
     "High endpoint sharing marks structural corners; train lift 2.10."),

    ("C1_anchored_both_ends", "spatial_closure",
     "A wall is anchored into the fabric rather than dangling "
     "(endpoint_degree >= 4).",
     "Members of closed room cells are anchored at both ends; train lift 1.70."),
    ("C2_continuous_run", "spatial_closure",
     "A wall axis continues through corners as a collinear run "
     "(collinear fan-out >= 2 and endpoint_degree >= 3).",
     "Closed boundaries are continuous collinear chains; train lift 1.31."),
    ("C3_enclosing_hub", "spatial_closure",
     "A wall encloses multiple cells (intersection_junction fan-out >= 10).",
     "Interior partitions bounding many rooms have high crossing count; "
     "train lift 1.69."),
    ("C4_long_anchored_spine", "spatial_closure",
     "A wall is a long anchored enclosing spine "
     "(log1p_length_norm >= 2.0 and endpoint_degree >= 4).",
     "Conjunction of length and anchoring isolates load-bearing runs; "
     "train lift 2.87."),

    ("D1_opening_host_collinear", "opening_relations",
     "A wall hosts an opening: it has a collinear neighbour markedly shorter "
     "than itself (< 0.6x length), i.e. an opening insert sits in its axis.",
     "Windows/doors/thresholds are short collinear inserts within a wall line; "
     "train lift 1.59."),
    ("D2_long_opening_host", "opening_relations",
     "A long wall hosts an opening (D1 and log1p_length_norm >= 1.5).",
     "Restricting the opening-host axiom to long segments sharpens it onto the "
     "wall side of the opening; train lift 2.14."),
    ("D3_double_line_face", "opening_relations",
     "A wall is drawn as a densely parallel-banded face "
     "(parallel_band fan-out >= 6).",
     "Walls appear as double lines with parallel window/glass fills between the "
     "faces; dense banding marks the wall faces; train lift 1.74."),
    ("D4_long_parallel_face", "opening_relations",
     "A long wall face has a similar-length parallel partner "
     "(parallel neighbour within 0.5x-2.0x length and log1p_length_norm >= 1.5).",
     "The two faces of a wall are long parallel partners of comparable length; "
     "train lift 1.56."),
)

RULE_IDS = tuple(r[0] for r in RULES)
CATEGORIES = ("wall_topology", "connectivity", "spatial_closure", "opening_relations")


def _neighbor_lengths_by_relation(lengths, edge_src, edge_dst, edge_type, etid):
    """For each node, gather neighbour lengths for the collinearity and
    parallel_band relations (directed src->dst edges)."""
    n = len(lengths)
    coll = etid["collinearity"]
    par = etid["parallel_band"]
    nb_coll = [[] for _ in range(n)]
    nb_par = [[] for _ in range(n)]
    es = np.asarray(edge_src, dtype=np.int64)
    ed = np.asarray(edge_dst, dtype=np.int64)
    et = np.asarray(edge_type, dtype=np.int64)
    for s, d, t in zip(es.tolist(), ed.tolist(), et.tolist()):
        if t == coll:
            nb_coll[s].append(lengths[d])
        elif t == par:
            nb_par[s].append(lengths[d])
    short_coll = np.zeros(n, dtype=bool)
    sim_par = np.zeros(n, dtype=bool)
    for i in range(n):
        li = lengths[i]
        if li > 0:
            if any(nl < SHORTER_COLLINEAR_RATIO * li for nl in nb_coll[i]):
                short_coll[i] = True
            if any(SIMILAR_PARALLEL_LO * li <= nl <= SIMILAR_PARALLEL_HI * li
                   for nl in nb_par[i]):
                sim_par[i] = True
    return short_coll, sim_par


def _flag_table(features, lengths, edge_src, edge_dst, edge_type, etid):
    f = np.asarray(features, dtype=np.float64)
    LN = f[:, FEATURE_INDEX["log1p_length_norm"]]
    # log1p features are log1p of non-negative integer counts; recover the count.
    ED = np.rint(np.expm1(f[:, FEATURE_INDEX["log1p_endpoint_degree"]]))
    JC = np.rint(np.expm1(f[:, FEATURE_INDEX["log1p_junction_count"]]))
    PC = np.rint(np.expm1(f[:, FEATURE_INDEX["log1p_parallel_count"]]))
    CC = np.rint(np.expm1(f[:, FEATURE_INDEX["log1p_collinear_count"]]))
    short_coll, sim_par = _neighbor_lengths_by_relation(
        lengths, edge_src, edge_dst, edge_type, etid)
    flags = OrderedDict()
    flags["A1_length_tier_1"] = LN >= 1.0
    flags["A2_length_tier_2"] = LN >= 1.5
    flags["A3_length_tier_3"] = LN >= 2.0
    flags["A4_length_tier_4"] = LN >= 3.0
    flags["B1_junction_hub_1"] = JC >= 6
    flags["B2_junction_hub_2"] = JC >= 14
    flags["B3_endpoint_degree_1"] = ED >= 3
    flags["B4_endpoint_degree_2"] = ED >= 8
    flags["C1_anchored_both_ends"] = ED >= 4
    flags["C2_continuous_run"] = (CC >= 2) & (ED >= 3)
    flags["C3_enclosing_hub"] = JC >= 10
    flags["C4_long_anchored_spine"] = (LN >= 2.0) & (ED >= 4)
    flags["D1_opening_host_collinear"] = short_coll
    flags["D2_long_opening_host"] = short_coll & (LN >= 1.5)
    flags["D3_double_line_face"] = PC >= 6
    flags["D4_long_parallel_face"] = sim_par & (LN >= 1.5)
    assert list(flags.keys()) == list(RULE_IDS), "rule id / flag order drift"
    return flags


def evaluate(build_result, edge_type_names):
    """Return per-node flags and score for one drawing.

    build_result : output of graph_builder.build_graph(ir, cfg, collect_edges=True)
    edge_type_names : builder.EDGE_TYPES

    Returns dict with keys:
      rule_ids : list[str]
      flags    : (n_nodes, n_rules) int8 array (column order == rule_ids)
      score    : (n_nodes,) float64 weighted sum (weight 1 each)
      n_nodes  : int
    """
    records = build_result["prepared"]["records"]
    lengths = np.asarray([float(r["length"]) for r in records], dtype=np.float64)
    features = build_result["features"]
    if features is None:
        raise ValueError("build_result has no features; call build_graph(collect_edges=True)")
    etid = {name: i for i, name in enumerate(edge_type_names)}
    flags = _flag_table(features, lengths,
                         build_result["edge_src"], build_result["edge_dst"],
                         build_result["edge_type"], etid)
    F = np.stack([flags[k].astype(np.int8) for k in RULE_IDS], axis=1)
    score = F.sum(axis=1).astype(np.float64)
    return {"rule_ids": list(RULE_IDS), "flags": F, "score": score, "n_nodes": F.shape[0]}
