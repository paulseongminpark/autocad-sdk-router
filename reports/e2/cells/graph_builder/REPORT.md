# Graph Builder Cell E1 Report

## Scope and data boundary

This run built a segment-node typed Graph IR, audited fixed-seed gen2 relation recovery, processed the complete CubiCasa validation SEG-IR set after a 10-drawing throughput pilot, and stress-built the largest staged real definitions selected from the read-only 384-definition census. No CubiCasa test file, original CAD file, Git surface, or repository file was read for output mutation.

## Design

- Nodes are non-degenerate SEG-IR segments. Source handles are preserved only in the `node_handle` NPZ sidecar.
- Numeric features contain geometry type, normalized length/bbox/midpoint/orientation, curvature/closed state, topology counts, and block depth. Identifier and name fields are absent.
- Directed edge types are `parallel_band`, `intersection_junction`, `proximity`, `collinearity`, `containment`, and `instancing`. Multiple types may coexist per pair.
- Spatial lookup uses a segment-cell index. Capped relation neighbors are ranked by geometry metrics and geometry SHA-256; exact geometry ties are retained and counted.
- Large graphs stream source-owned edge rows in canonical geometry order. Each shard records core nodes, halo targets, and directed edges without materializing an unbounded whole-graph edge table.
- NPZ serialization uses only numeric and Unicode arrays (no pickle). JSON sidecars carry schema, config, graph hash, feature names, edge mappings, and audit statistics.

### Frozen graph config

```json
{
  "angle_collinear_deg": 2.0,
  "angle_parallel_deg": 6.0,
  "collinear_gap_norm": 2.0,
  "collinear_offset_norm": 0.3,
  "containment_entity_cap": 16,
  "geometry_round_digits": 9,
  "junction_snap_norm": 0.01,
  "max_candidate_collect": 256,
  "max_candidate_scan": 96,
  "max_core_nodes_per_shard": 16384,
  "max_index_cells_per_segment": 512,
  "parallel_min_overlap": 0.2,
  "parallel_offset_norm": 0.5,
  "proximity_radius_norm": 0.5,
  "topk_collinear": 8,
  "topk_parallel": 12,
  "topk_proximity": 12
}
```

### Feature allowlist

```json
[
  "log1p_length_norm",
  "midpoint_x_drawing_norm",
  "midpoint_y_drawing_norm",
  "bbox_width_norm",
  "bbox_height_norm",
  "sin_2theta",
  "cos_2theta",
  "sagitta_norm",
  "closed_geometry",
  "kind_line",
  "kind_poly_edge",
  "kind_arc_chord",
  "log1p_endpoint_degree",
  "log1p_junction_count",
  "log1p_parallel_count",
  "log1p_collinear_count",
  "block_depth_norm"
]
```

## Selftest transcript

```text
=== graph_builder --selftest ===
python=3.12.10 numpy=1.26.4 ezdxf=1.4.3
[OK] same_input_graph_hash: f925bd96cf731af652779b54c489f84509a864da2064e66a6f5a9fca52d9fc57
[OK] node_permutation_graph_hash: f925bd96cf731af652779b54c489f84509a864da2064e66a6f5a9fca52d9fc57
[OK] mini_relation_parallel_band: support_pair_nodes=1x1 directed_edges=6
[OK] mini_relation_intersection_junction: support_pair_nodes=1x1 directed_edges=8
[OK] mini_relation_proximity: support_pair_nodes=1x1 directed_edges=18
[OK] mini_relation_collinearity: support_pair_nodes=1x1 directed_edges=14
[OK] mini_relation_containment: support_pair_nodes=2x2 directed_edges=2
[OK] mini_relation_instancing: support_pair_nodes=2x2 directed_edges=2
[OK] empty_honest_status: status=degenerate_empty nodes=0 edges=0
[OK] singleton_honest_status: status=degenerate_singleton nodes=1 edges=0
[OK] zero_length_not_recast: {"zero_length": 1}
[OK] identifier_name_feature_exclusion: feature_count=17 forbidden_hits=[]
[OK] numeric_feature_matrix: shape=(9, 17)
SELFTEST_RESULT: OK (13/13)
```

Selftest counters:

```json
{
  "checks_error": 0,
  "checks_ok": 13,
  "checks_total": 13,
  "graph_hash": "f925bd96cf731af652779b54c489f84509a864da2064e66a6f5a9fca52d9fc57",
  "mini_directed_edges": 50,
  "mini_nodes": 9
}
```

## Relation recall numbers

```json
{
  "config_hash": "56911f4633979a3fe00fd56be2d0a39ac06757ed255ed49ed18ca20ba9d4ac49",
  "drawing_count": 9,
  "elapsed_seconds": 20.780457499990007,
  "graphs": [
    {
      "directed_edges": 28222,
      "graph_hash": "7a81f6867b39ce810aceb02cdb6d4dd2a835a21266f264b65da317da43e43102",
      "nodes": 2357,
      "relation_recall": {
        "collinearity": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 3,
          "support": 3,
          "uncapped_recovered": 3
        },
        "containment": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 9,
          "support": 9,
          "uncapped_recovered": 9
        },
        "instancing": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 118,
          "support": 118,
          "uncapped_recovered": 118
        },
        "intersection_junction": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 6,
          "support": 6,
          "uncapped_recovered": 6
        },
        "parallel_band": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 8,
          "support": 8,
          "uncapped_recovered": 8
        },
        "proximity": {
          "cap_attributable_false_negatives": 0,
          "recall": null,
          "recovered": 0,
          "support": 0,
          "uncapped_recovered": 0
        }
      },
      "seed": 20260718,
      "tier": "S",
      "unresolved_references": 0
    },
    {
      "directed_edges": 28208,
      "graph_hash": "4faed218ea567295cc9c29e19ee85bf58625c250e971b57b52e9f2f883bc3b49",
      "nodes": 2357,
      "relation_recall": {
        "collinearity": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 3,
          "support": 3,
          "uncapped_recovered": 3
        },
        "containment": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 9,
          "support": 9,
          "uncapped_recovered": 9
        },
        "instancing": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 118,
          "support": 118,
          "uncapped_recovered": 118
        },
        "intersection_junction": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 6,
          "support": 6,
          "uncapped_recovered": 6
        },
        "parallel_band": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 8,
          "support": 8,
          "uncapped_recovered": 8
        },
        "proximity": {
          "cap_attributable_false_negatives": 0,
          "recall": null,
          "recovered": 0,
          "support": 0,
          "uncapped_recovered": 0
        }
      },
      "seed": 20260719,
      "tier": "S",
      "unresolved_references": 0
    },
    {
      "directed_edges": 28210,
      "graph_hash": "04269d83b2b5bd86dab8c9f559d5b56e84dc284721d781d6d4b63750dace0660",
      "nodes": 2357,
      "relation_recall": {
        "collinearity": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 3,
          "support": 3,
          "uncapped_recovered": 3
        },
        "containment": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 9,
          "support": 9,
          "uncapped_recovered": 9
        },
        "instancing": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 118,
          "support": 118,
          "uncapped_recovered": 118
        },
        "intersection_junction": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 6,
          "support": 6,
          "uncapped_recovered": 6
        },
        "parallel_band": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 8,
          "support": 8,
          "uncapped_recovered": 8
        },
        "proximity": {
          "cap_attributable_false_negatives": 0,
          "recall": null,
          "recovered": 0,
          "support": 0,
          "uncapped_recovered": 0
        }
      },
      "seed": 20260720,
      "tier": "S",
      "unresolved_references": 0
    },
    {
      "directed_edges": 28136,
      "graph_hash": "784eb2ccc45ea71b0ba6ea2b2a4c0dbbd7ce3574d7f4fec976c48a64f4d690ae",
      "nodes": 2357,
      "relation_recall": {
        "collinearity": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 3,
          "support": 3,
          "uncapped_recovered": 3
        },
        "containment": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 9,
          "support": 9,
          "uncapped_recovered": 9
        },
        "instancing": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 118,
          "support": 118,
          "uncapped_recovered": 118
        },
        "intersection_junction": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 6,
          "support": 6,
          "uncapped_recovered": 6
        },
        "parallel_band": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 9,
          "support": 9,
          "uncapped_recovered": 9
        },
        "proximity": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 1,
          "support": 1,
          "uncapped_recovered": 1
        }
      },
      "seed": 20360718,
      "tier": "F",
      "unresolved_references": 0
    },
    {
      "directed_edges": 28144,
      "graph_hash": "b346024a8de53225843fcb3c37558403c754c9d1b59a415a73466faae236d6ab",
      "nodes": 2357,
      "relation_recall": {
        "collinearity": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 3,
          "support": 3,
          "uncapped_recovered": 3
        },
        "containment": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 9,
          "support": 9,
          "uncapped_recovered": 9
        },
        "instancing": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 118,
          "support": 118,
          "uncapped_recovered": 118
        },
        "intersection_junction": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 6,
          "support": 6,
          "uncapped_recovered": 6
        },
        "parallel_band": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 9,
          "support": 9,
          "uncapped_recovered": 9
        },
        "proximity": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 1,
          "support": 1,
          "uncapped_recovered": 1
        }
      },
      "seed": 20360719,
      "tier": "F",
      "unresolved_references": 0
    },
    {
      "directed_edges": 28156,
      "graph_hash": "88ba73716132b001343bb0450bc5c8fd2915799e325eb24efcbe04e7647d73c7",
      "nodes": 2357,
      "relation_recall": {
        "collinearity": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 3,
          "support": 3,
          "uncapped_recovered": 3
        },
        "containment": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 9,
          "support": 9,
          "uncapped_recovered": 9
        },
        "instancing": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 118,
          "support": 118,
          "uncapped_recovered": 118
        },
        "intersection_junction": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 6,
          "support": 6,
          "uncapped_recovered": 6
        },
        "parallel_band": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 9,
          "support": 9,
          "uncapped_recovered": 9
        },
        "proximity": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 1,
          "support": 1,
          "uncapped_recovered": 1
        }
      },
      "seed": 20360720,
      "tier": "F",
      "unresolved_references": 0
    },
    {
      "directed_edges": 28130,
      "graph_hash": "e23686a40a18c95b953051116729c20a4887f437936ab8e6876faa03a2e361ac",
      "nodes": 2358,
      "relation_recall": {
        "collinearity": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 3,
          "support": 3,
          "uncapped_recovered": 3
        },
        "containment": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 9,
          "support": 9,
          "uncapped_recovered": 9
        },
        "instancing": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 118,
          "support": 118,
          "uncapped_recovered": 118
        },
        "intersection_junction": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 7,
          "support": 7,
          "uncapped_recovered": 7
        },
        "parallel_band": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 10,
          "support": 10,
          "uncapped_recovered": 10
        },
        "proximity": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 2,
          "support": 2,
          "uncapped_recovered": 2
        }
      },
      "seed": 20460718,
      "tier": "M",
      "unresolved_references": 0
    },
    {
      "directed_edges": 28140,
      "graph_hash": "144968e8550465a6499d49683b9356d98088fa548b4e43711e3245f7381804f7",
      "nodes": 2358,
      "relation_recall": {
        "collinearity": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 3,
          "support": 3,
          "uncapped_recovered": 3
        },
        "containment": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 9,
          "support": 9,
          "uncapped_recovered": 9
        },
        "instancing": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 118,
          "support": 118,
          "uncapped_recovered": 118
        },
        "intersection_junction": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 7,
          "support": 7,
          "uncapped_recovered": 7
        },
        "parallel_band": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 10,
          "support": 10,
          "uncapped_recovered": 10
        },
        "proximity": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 2,
          "support": 2,
          "uncapped_recovered": 2
        }
      },
      "seed": 20460719,
      "tier": "M",
      "unresolved_references": 0
    },
    {
      "directed_edges": 28146,
      "graph_hash": "27ca914fe0637d8a05e601df0685e7fbd6b336f30f9b50c1014ae6922da7f7dd",
      "nodes": 2358,
      "relation_recall": {
        "collinearity": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 3,
          "support": 3,
          "uncapped_recovered": 3
        },
        "containment": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 9,
          "support": 9,
          "uncapped_recovered": 9
        },
        "instancing": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 118,
          "support": 118,
          "uncapped_recovered": 118
        },
        "intersection_junction": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 7,
          "support": 7,
          "uncapped_recovered": 7
        },
        "parallel_band": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 10,
          "support": 10,
          "uncapped_recovered": 10
        },
        "proximity": {
          "cap_attributable_false_negatives": 0,
          "recall": 1.0,
          "recovered": 2,
          "support": 2,
          "uncapped_recovered": 2
        }
      },
      "seed": 20460720,
      "tier": "M",
      "unresolved_references": 0
    }
  ],
  "micro": {
    "cap_attributable_false_negatives": 0,
    "recall": 1.0,
    "recovered": 1317,
    "support": 1317,
    "uncapped_recovered": 1317
  },
  "n_per_tier": 3,
  "relation_types": {
    "collinearity": {
      "cap_attributable_false_negatives": 0,
      "oracle_sources": {
        "gen2.wall.axis_collinear_fragment": 27
      },
      "recall": 1.0,
      "recovered": 27,
      "support": 27,
      "uncapped_recovered": 27
    },
    "containment": {
      "cap_attributable_false_negatives": 0,
      "oracle_sources": {
        "dxf.entity_component_structure_with_truth_handle": 81
      },
      "recall": 1.0,
      "recovered": 81,
      "support": 81,
      "uncapped_recovered": 81
    },
    "instancing": {
      "cap_attributable_false_negatives": 0,
      "oracle_sources": {
        "dxf.insert_occurrence_structure": 1062
      },
      "recall": 1.0,
      "recovered": 1062,
      "support": 1062,
      "uncapped_recovered": 1062
    },
    "intersection_junction": {
      "cap_attributable_false_negatives": 0,
      "oracle_sources": {
        "gen2.wall.axis_intersection": 57
      },
      "recall": 1.0,
      "recovered": 57,
      "support": 57,
      "uncapped_recovered": 57
    },
    "parallel_band": {
      "cap_attributable_false_negatives": 0,
      "oracle_sources": {
        "gen2.wall.handles": 81
      },
      "recall": 1.0,
      "recovered": 81,
      "support": 81,
      "uncapped_recovered": 81
    },
    "proximity": {
      "cap_attributable_false_negatives": 0,
      "oracle_sources": {
        "gen2.opening.wall_id_plus_nearest_door_geometry": 9
      },
      "recall": 1.0,
      "recovered": 9,
      "support": 9,
      "uncapped_recovered": 9
    }
  },
  "schema": "ariadne.e2.graph_recall_audit.v1",
  "seed": 20260718,
  "truth_boundary_note": "wall parallel/intersection/collinearity/opening proximity units derive from gen2 wall/opening ledger; containment and instancing units derive from the read-only DXF entity/INSERT structure because wall.v1 has no explicit relation table",
  "unresolved_required_reference_count": 0
}
```

## Edge/RAM envelope numbers

```json
{
  "aggregates": {
    "combined": {
      "build_seconds_quantiles": {
        "max": 443.960856900012,
        "min": 0.045344400001340546,
        "p50": 0.26096999998844694,
        "p90": 0.6362974599935117,
        "p95": 0.7887825800004065,
        "p99": 1.0879509940027494
      },
      "build_seconds_total": 593.0975389001251,
      "directed_edge_count_quantiles": {
        "max": 6047119.0,
        "min": 4456.0,
        "p50": 17912.0,
        "p90": 40378.0,
        "p95": 48344.1,
        "p99": 68723.46000000005
      },
      "directed_edge_count_total": 15074665,
      "drawing_count": 403,
      "edge_node_ratio_quantiles": {
        "max": 29.519795657726693,
        "min": 14.662277202995924,
        "p50": 24.28002894356006,
        "p90": 26.61210874789254,
        "p95": 26.995191158072373,
        "p99": 28.194414232207652
      },
      "maximum_shard_nodes_with_halo": {
        "core_nodes": 16384,
        "directed_edges": 251185,
        "source_ref": "staged_real_rank_001",
        "value": 94432
      },
      "maximum_source_directed_edges": {
        "source_ref": "staged_real_rank_001",
        "value": 6047119
      },
      "maximum_source_nodes": {
        "source_ref": "staged_real_rank_001",
        "value": 412427
      },
      "node_count_quantiles": {
        "max": 412427.0,
        "min": 210.0,
        "p50": 748.0,
        "p90": 1587.6000000000001,
        "p95": 1873.4999999999995,
        "p99": 2736.720000000005
      },
      "node_count_total": 787370,
      "pooled_fanout_quantiles": {
        "max": 140.0,
        "min": 0.0,
        "p50": 17.0,
        "p90": 36.0,
        "p95": 41.0,
        "p99": 61.0
      },
      "relation_directed_edge_count_totals": {
        "collinearity": 2200773,
        "containment": 1806548,
        "instancing": 395946,
        "intersection_junction": 3404499,
        "parallel_band": 1653707,
        "proximity": 5613192
      },
      "status_counts": {
        "ok": 403
      },
      "unresolved_reference_count_total": 0,
      "working_set_peak_bytes_quantiles": {
        "max": 1393426432.0,
        "min": 91222016.0,
        "p50": 96292864.0,
        "p90": 101498880.0,
        "p95": 101675008.0,
        "p99": 102784614.4
      },
      "working_set_peak_delta_bytes_quantiles": {
        "max": 1212542976.0,
        "min": 0.0,
        "p50": 24576.0,
        "p90": 149094.40000000014,
        "p95": 265420.7999999998,
        "p99": 632340.4800000023
      }
    },
    "cubicasa_val": {
      "build_seconds_quantiles": {
        "max": 1.115306799998507,
        "min": 0.045344400001340546,
        "p50": 0.26016399999934947,
        "p90": 0.6096487699993304,
        "p95": 0.7786050600007001,
        "p99": 0.9935822769944199
      },
      "build_seconds_total": 130.13303580011416,
      "directed_edge_count_quantiles": {
        "max": 73200.0,
        "min": 4456.0,
        "p50": 17903.0,
        "p90": 38831.4,
        "p95": 47721.649999999994,
        "p99": 58209.72
      },
      "directed_edge_count_total": 8683244,
      "drawing_count": 400,
      "edge_node_ratio_quantiles": {
        "max": 29.519795657726693,
        "min": 17.474509803921567,
        "p50": 24.311850519584333,
        "p90": 26.61951513184584,
        "p95": 27.000471559092244,
        "p99": 28.198276276276275
      },
      "maximum_shard_nodes_with_halo": {
        "core_nodes": 2861,
        "directed_edges": 73200,
        "source_ref": "val/high_quality_14094.segir.json",
        "value": 2861
      },
      "maximum_source_directed_edges": {
        "source_ref": "val/high_quality_14094.segir.json",
        "value": 73200
      },
      "maximum_source_nodes": {
        "source_ref": "val/high_quality_14094.segir.json",
        "value": 2861
      },
      "node_count_quantiles": {
        "max": 2861.0,
        "min": 210.0,
        "p50": 748.0,
        "p90": 1537.1000000000008,
        "p95": 1849.5499999999995,
        "p99": 2254.5399999999995
      },
      "node_count_total": 353953,
      "pooled_fanout_quantiles": {
        "max": 135.0,
        "min": 2.0,
        "p50": 23.0,
        "p90": 40.0,
        "p95": 48.0,
        "p99": 70.0
      },
      "relation_directed_edge_count_totals": {
        "collinearity": 1179306,
        "containment": 0,
        "instancing": 0,
        "intersection_junction": 2933745,
        "parallel_band": 1063117,
        "proximity": 3507076
      },
      "status_counts": {
        "ok": 400
      },
      "unresolved_reference_count_total": 0,
      "working_set_peak_bytes_quantiles": {
        "max": 102785024.0,
        "min": 91222016.0,
        "p50": 96292864.0,
        "p90": 101498880.0,
        "p95": 101675008.0,
        "p99": 102732103.68
      },
      "working_set_peak_delta_bytes_quantiles": {
        "max": 3063808.0,
        "min": 0.0,
        "p50": 24576.0,
        "p90": 119603.20000000019,
        "p95": 254156.7999999998,
        "p99": 438968.31999999937
      }
    },
    "staged_real_definitions": {
      "build_seconds_quantiles": {
        "max": 443.960856900012,
        "min": 9.23678980000841,
        "p50": 9.766856399990502,
        "p90": 357.1220568000077,
        "p95": 400.5414568500098,
        "p99": 435.27697689001155
      },
      "build_seconds_total": 462.9645031000109,
      "directed_edge_count_quantiles": {
        "max": 6047119.0,
        "min": 159908.0,
        "p50": 184394.0,
        "p90": 4874574.0,
        "p95": 5460846.5,
        "p99": 5929864.5
      },
      "directed_edge_count_total": 6391421,
      "drawing_count": 3,
      "edge_node_ratio_quantiles": {
        "max": 17.83135093317861,
        "min": 14.662277202995924,
        "p50": 15.01624565686919,
        "p90": 17.268329877916724,
        "p95": 17.549840405547666,
        "p99": 17.77504882765242
      },
      "maximum_shard_nodes_with_halo": {
        "core_nodes": 16384,
        "directed_edges": 251185,
        "source_ref": "staged_real_rank_001",
        "value": 94432
      },
      "maximum_source_directed_edges": {
        "source_ref": "staged_real_rank_001",
        "value": 6047119
      },
      "maximum_source_nodes": {
        "source_ref": "staged_real_rank_001",
        "value": 412427
      },
      "node_count_quantiles": {
        "max": 412427.0,
        "min": 10341.0,
        "p50": 10649.0,
        "p90": 332071.4,
        "p95": 372249.19999999995,
        "p99": 404391.44
      },
      "node_count_total": 433417,
      "pooled_fanout_quantiles": {
        "max": 140.0,
        "min": 0.0,
        "p50": 10.0,
        "p90": 33.0,
        "p95": 37.0,
        "p99": 47.0
      },
      "relation_directed_edge_count_totals": {
        "collinearity": 1021467,
        "containment": 1806548,
        "instancing": 395946,
        "intersection_junction": 470754,
        "parallel_band": 590590,
        "proximity": 2106116
      },
      "status_counts": {
        "ok": 3
      },
      "unresolved_reference_count_total": 0,
      "working_set_peak_bytes_quantiles": {
        "max": 1393426432.0,
        "min": 626675712.0,
        "p50": 627032064.0,
        "p90": 1240147558.4,
        "p95": 1316786995.1999998,
        "p99": 1378098544.6399999
      },
      "working_set_peak_delta_bytes_quantiles": {
        "max": 1212542976.0,
        "min": 380928.0,
        "p50": 733184.0,
        "p90": 970181017.6,
        "p95": 1091361996.8,
        "p99": 1188306780.16
      }
    }
  },
  "config_hash": "56911f4633979a3fe00fd56be2d0a39ac06757ed255ed49ed18ca20ba9d4ac49",
  "data_boundary": {
    "cubicasa_partition_accessed": "val",
    "cubicasa_test_files_accessed": 0,
    "cubicasa_val_discovered": 400,
    "cubicasa_val_processed": 400,
    "original_cad_files_accessed": 0,
    "staged_real": {
      "definition_universe_in_readonly_census": 384,
      "definitions_processed": 3,
      "selection": "largest n_segments from complete readonly 384-definition census",
      "source_kind": "staged_dxf_only",
      "staged_path": "D:\\dev\\99_tools\\autocad-sdk-router\\runs\\e2_b3_dxfout_20260717\\1_export.dxf",
      "staged_sha256": "5a6035721630cddc6d753b1b97b898e7a4ce4d5988342ce85e2c465cdb81deff",
      "status": "MEASURED",
      "whole_staged_phase_memory": {
        "working_set_end_bytes": 626995200,
        "working_set_peak_bytes": 1387999232,
        "working_set_peak_delta_bytes": 1285238784,
        "working_set_start_bytes": 102760448
      }
    }
  },
  "elapsed_seconds": 600.0538349999988,
  "production_p95_measurement_basis": {
    "cubicasa_edge_exceedance_count": 20,
    "cubicasa_edge_exceedance_rate": 0.05,
    "cubicasa_memory_exceedance_count": 17,
    "cubicasa_memory_exceedance_rate": 0.0425,
    "directed_edge_count_p95": 47721.649999999994,
    "preexisting_frozen_p95_reference_available": false,
    "reference_source": "current full CubiCasa val empirical p95",
    "staged_real_edge_exceedance_count": 3,
    "staged_real_edge_exceedance_rate": 1.0,
    "staged_real_memory_exceedance_count": 3,
    "staged_real_memory_exceedance_rate": 1.0,
    "working_set_peak_bytes_p95": 101675008.0
  },
  "ram_numbers": {
    "hard_band_bytes": 51539607552,
    "observed_process_working_set_peak_bytes": 1393426432,
    "observed_to_band_fraction": 0.027036031087239582
  },
  "schema": "ariadne.e2.graph_envelope_audit.v1",
  "throughput_pilot": {
    "full_val_started_after_pilot_drawings": 10,
    "pilot_build_seconds": 3.3588421000167727,
    "pilot_directed_edges": 246580,
    "pilot_drawings": 10,
    "pilot_edges_per_build_second": 73412.2035682382,
    "pilot_nodes": 10717,
    "pilot_nodes_per_build_second": 3190.6828844221295
  }
}
```

Per-drawing numeric records are preserved without hand-copying in `envelope_numbers.json`; per-synthetic-drawing recall rows are in `recall_numbers.json`.

## Unresolved and interpretation boundaries

- Synthetic unresolved-reference count measured as 0.
- Staged-real census/extraction count deltas: [0, 0, 0].
- The source dossier supplies no previously frozen numeric production p95 edge/memory reference. This cell records the full CubiCasa-val empirical p95 and exceedance rates as a freeze basis; it emits no compliance verdict.
- gen2 wall.v1 has no explicit relation-pair table. Wall/opening relation units are derived from its wall axes, wall handles, and opening wall_id; containment/instancing units are independently read from DXF entity/INSERT structure and are labeled as such.

No preregistration threshold judgment is emitted by this cell.

CELL_COMPLETE: graph_builder
