# M-12 ArchCAD → E2 SEG-IR adapter feasibility

**Axis verdict: PASS (design-only; no adapter code or training run was authorized).** The four measured source geometry types can be converted deterministically to the current `seg.v1` segment contract. Missing physical scale, parent-project identity, and official split provenance remain explicit `UNKNOWN`/quarantine fields; they must never be silently inferred.

## Grounded contracts

| Surface | Absolute path | SHA-256 | What it fixes |
|---|---|---|---|
| ArchCAD measurement | `D:\runs\e2_program\cells\m12_archcad\measurement.json` | `2132e962b458fe0a51b2fba52ffa189880b0c90cfb6840775e00a00976989d6e` | Observed source fields, classes, types, coordinates, and losses |
| E2 SEG-IR writer | `D:\dev\99_tools\autocad-sdk-router\tools\e2\cells\graph_builder.py` | `c95d4a30d30e0db157fe56102053a7884902b7749464f7f4cb8852c0819321f6` | Top-level `seg.v1` and per-segment fields |
| Existing CubiCasa subset adapter | `D:\dev\99_tools\autocad-sdk-router\tools\e2\extset\cubicasa_parse.py` | `b72e6b20204f10a2a68db30a8270cdca0cb38a6f2b24a2feff589e60186c3a50` | Current SVG-to-SEG-IR compatibility pattern; its own source says real CubiCasa is deferred |
| CRS consumer | `D:\dev\99_tools\autocad-sdk-router\tools\e2\instruments\crs_bridge.py` | `b7c0ac84e501c5895949f1db23f9ead0d6e70691271a0a1d176d9378cd8fdd5b` | Requires finite non-degenerate endpoints and unique non-empty handles |
| Verifier consumer | `D:\dev\99_tools\autocad-sdk-router\tools\e2\instruments\verifier.py` | `72e33ab0e87e96defd00f74c5a22ae6c5cb001c69b740e627edeedaf2a80b690` | Reads `sid`, `handle`, `pts`, `layer`, and `kind`; does not trust `label` |

The current core record is:

```json
{
  "ir": "seg.v1",
  "drawing_id": "<ArchCAD sample UUID>",
  "units": "px",
  "scale_mm_per_unit": null,
  "segments": [
    {
      "sid": "s0000001",
      "handle": "archcad:<sample_uuid>:e000001:p0000",
      "pts": [[0.0, 0.0], [1.0, 1.0]],
      "layer": "UNKNOWN",
      "kind": "line",
      "label": "other",
      "source": "archcad-json"
    }
  ]
}
```

The adapter adds non-breaking provenance extensions at the top level (`axis_convention`, `canvas`, `project_id`, `official_split`, `eligible_for_training`, `source_modalities`) and per segment (`semantic_id`, `semantic_name`, `source_entity_index`, `source_piece_index`, `instance`, `source_curve_type`). Core consumers may ignore these extensions.

## Authority order and admission gate

1. Use `D:\datasets\ArchCAD\data\json\<sample_uuid>.json` as the geometry/semantic authority. The sealed sample observed only the top-level `entities` key and the entity types `LINE`, `ARC`, `CIRCLE`, and `ELLIPSE`.
2. Require the sibling paths under `D:\datasets\ArchCAD\data\svg`, `D:\datasets\ArchCAD\data\png`, `D:\datasets\ArchCAD\data\caption`, and `D:\datasets\ArchCAD\data\point` to have the identical UUID stem. Validate JSON/SVG entity count, semantic sequence, and instance sequence before conversion.
3. Use SVG as a curve-direction and render-plane cross-check, not as a second geometry source. Use PNG only for canvas/raster checks. Use caption JSON only as language metadata.
4. Treat NPY as a quantized/reduced control-point audit surface. The measured form is `N×3`, finite, with primitive-code values `{1,2,3,4}` and coordinates ordered `[primitive_code,y,x]`; its median LINE endpoint multiset match was only `0.5528777907`, so it must not replace the vector JSON.
5. If any required sibling, semantic ID, finite geometry field, or JSON/SVG cross-check fails, emit no SEG-IR record. Record a hard adapter error; do not substitute another sample.

## Geometry and handle rules

All calculations use float64. Input JSON/SVG coordinates are kept in the measured 980×980 raster plane: origin top-left, `+x` right, `+y` down. No y flip and no physical-scale multiplication are applied.

| ArchCAD entity | SEG-IR emission rule | Preserved auxiliary fields | Information loss in core `seg.v1` |
|---|---|---|---|
| `LINE` | One `kind="line"` segment from `start` to `end` | `linetype`, `rgb`, `line_width`, source entity index | CAD layer, native handle, owner/block lineage absent at source |
| `ARC` | Deterministic chord tessellation with maximum angular step `7.5°`; each piece is `kind="arc-chord"` | `center`, `radius`, `start_angle`, `end_angle`, `direction`, source entity index | Exact analytic arc is not a core segment; preserve exact parameters in provenance |
| `CIRCLE` | 48 closed `kind="arc-chord"` pieces (`360° / 7.5°`) | `center`, `radius`, source entity index | Exact circle identity/curvature is auxiliary only |
| `ELLIPSE` | `ceil(abs(end_param-start_param)/(π/24))` chord pieces, with direction from `is_ccw`; minimum one non-degenerate piece | `center`, `major_axis`, `ratio`, `radius_a`, `radius_b`, params, `theta`, source entity index | Exact ellipse identity/curvature is auxiliary only |

For ARC/ELLIPSE, JSON direction and the same-index SVG path flags must agree. A disagreement is a hard error. Zero-length pieces are omitted only after their source entity is recorded in the loss ledger; if every piece is degenerate, the sample fails conversion.

Every emitted segment gets a unique deterministic handle `archcad:<sample_uuid>:e<entity_index_6d>:p<piece_index_4d>` and a sequential `sid`. The source instance string is copied exactly when present. It remains `null` with `instance_missing=true` when absent; no instance is synthesized. This matters because measured instance presence was below 100% for some documented-countable classes and was 0% for wall ID 20.

## Semantic projection

The README-declared table was corroborated by observing every listed ID in the sealed vector files: `0..29` plus `100`, with no unexplained value among 208,191 measured entities. Freeze the following source map in the future adapter rather than reparsing prose at runtime:

| ID | Source class | `seg.v1.label` compatibility projection |
|---:|---|---|
| 0 | Axis & Grid | other |
| 1 | Single Door | opening |
| 2 | Double Door | opening |
| 3 | Parent-Child Door | opening |
| 4 | Other Door | opening |
| 5 | Elevator | other |
| 6 | Staircase | other |
| 7 | Sink | other |
| 8 | Urinal | other |
| 9 | Toilet | other |
| 10 | Bathtub | other |
| 11 | Squat Toilet | other |
| 12 | Other Fixtures | other |
| 13 | Drain | other |
| 14 | Table | other |
| 15 | Chair | other |
| 16 | Bed | other |
| 17 | Sofa | other |
| 18 | Hole | other |
| 19 | Glass | other |
| 20 | Wall | wall |
| 21 | Concrete Column | other |
| 22 | Steel Column | other |
| 23 | Concrete Beam | other |
| 24 | Steel Beam | other |
| 25 | Parking Space | other |
| 26 | Foundation | other |
| 27 | Pile | other |
| 28 | Rebar | other |
| 29 | Fire Hydrant | other |
| 100 | Others | other |

Always preserve `semantic_id` and `semantic_name` beside this compatibility projection. Set `layer="UNKNOWN"`; encoding the class in `layer` would leak ground truth into layer-aware verifiers.

## Coordinate rule

```text
ArchCAD JSON/SVG [x,y] -> SEG-IR pts [x,y]       (identity)
ArchCAD NPY [primitive_code,y,x] -> audit [x,y]  (columns [2,1], quantized)
units = "px"
scale_mm_per_unit = null
axis_convention = "x_right_y_down_origin_top_left"
canvas = [0,0,980,980]
```

The README says each slice covers 14 m × 14 m, which would imply `14.2857142857 mm/coordinate-unit`, but no sampled machine-readable field encodes that scale or a world transform. Store it only as `documented_candidate_scale_mm_per_unit`; do not populate `scale_mm_per_unit` until an independent machine-readable anchor validates it.

## Loss and quarantine ledger

| Loss/unknown | Severity | Required handling |
|---|---|---|
| No official train/val/test assignment | Qualification blocker | `official_split=null`, `eligible_for_training=false`; TRACK remains blocked |
| No project/drawing parent key for UUID slices | Leakage blocker | `project_id=null`; do not create random sample splits |
| Physical unit and world origin absent | Metric-transfer blocker | `units="px"`, `scale_mm_per_unit=null`; retain documented candidate separately |
| No CAD handle/layer/owner/block lineage | Fidelity loss | Deterministic synthetic handles; `layer="UNKNOWN"`; never imply source provenance |
| Curves flattened to chords | Geometric approximation | Preserve analytic parameters and source-index mapping; report chord tolerance/count |
| Wall ID 20 has no instance grouping | Topology/instance loss | Preserve wall segment labels but set wall-instance grouping `UNKNOWN`; derive topology only in a later explicit stage |
| Some countable entities lack instance values | Instance loss | Preserve null and missing flag; no synthesis |
| NPY is quantized/reduced and not semantic-complete | Modality loss | Audit-only; JSON remains authoritative |
| Caption Q&A is generated prose | Semantic-noise risk | Keep out of geometry/label authority path |

## Future implementation acceptance gates

The next preregistration must freeze the implementation and then require all of the following before any training input is emitted:

1. Reproduce the sealed 500 UUIDs and the 500/500 five-modality parse/alignment result from `D:\runs\e2_program\cells\m12_archcad\evidence.csv`.
2. Reject unknown semantic IDs and JSON/SVG mismatches; prove class and instance conservation per source entity.
3. Prove every emitted `pts` value is finite, every segment is non-degenerate, and every handle is unique/non-empty under `D:\dev\99_tools\autocad-sdk-router\tools\e2\instruments\crs_bridge.py`.
4. Rasterize emitted chords into the 980×980 plane and freeze an explicit residual threshold before testing; report per-type ARC/CIRCLE/ELLIPSE error separately.
5. Emit a per-sample loss ledger with source entity count, emitted segment count, omitted/degenerate count, and exact-curve sidecar hash.
6. Keep `eligible_for_training=false` until an official project-isolated split or equivalent source grouping evidence exists.

## Feasibility decision

`PASS` means the representation conversion is implementable without silent corruption: all observed source types have deterministic rules; the target core fields are populated; absent layer, physical scale, wall instances, project identity, and split are explicit; and every approximation is ledgered. It does **not** make this dataset training-eligible. The split-isolation FAIL independently keeps the overall M-12 result `TRACK_BLOCKED`.
