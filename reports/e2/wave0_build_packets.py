# wave0_build_packets.py — E2 Wave 0 fleet packet builder (25 packets, 6 lanes).
# Paul order 2026-07-17: octoloop, worktree-parallel; opus on aclaude-b/c(3ea)+d/e(5ea),
# codex 5.6 terra x4, cursor grok x5; main aclaude quota untouched.
# Contracts are inlined LITERALLY into every prompt (delegation contract: no "as discussed").
import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wave0_packets.json')

RULES = """
RULES (mandatory):
- You run inside an isolated git worktree of the autocad-sdk-router repo. Work ONLY inside it.
- Do NOT run any git commands. Do NOT spawn subagents. Do NOT use the network.
- WRITE-FIRST: create your declared output file(s) early, then iterate.
- Touch ONLY your declared files. Any temp/fixture data your selftest needs must go to the OS temp dir, never the repo (except files explicitly declared).
- Module dirs are plain script dirs: do NOT create __init__.py anywhere.
- Python: C:/Users/PAUL/AppData/Local/Programs/Python/Python312/python.exe ; stdlib only unless the card explicitly allows ezdxf/openpyxl.
- Implement a --selftest mode (self-contained; builds its own fixture in code or uses repo files named in this card), RUN it, and paste the real output tail in your final message.
- Final message sections: FILES WRITTEN / SELFTEST OUTPUT (verbatim tail) / LIMITS (what is NOT yet validated) / BLOCKERS.
- Never report success for anything not executed. Deferred validation belongs in LIMITS.
"""

PROJ = """
E1 PROJECTION GRAMMAR (verbatim samples; parse exactly; unknown line shapes -> kind='other', never crash):
- LINE layer=DIM handle=8B52 (44248.83,24580.207)->(44248.83,22920.207)
- INSERT layer=DIM handle=8B55 block=DIMDOT
- MTEXT layer=DIM handle=8B57 '\\A1;3280'
- POINT layer=DEFPOINTS handle=8B58
- LWPOLYLINE layer=X-... handle=4376 vertices=5      (NOTE: projections carry NO polyline coordinates)
- WIPEOUT layer=0 handle=4855
- SPLINE layer=... handle=1BCC
- HATCH layer=... handle=1BCE pattern=SOLID loops=2
- TEXT layer=DEFPOINTS handle=3AE '101 dong'
- ARC layer=... handle=820F                          (no coords)
- CIRCLE layer=... handle=3288 radius=81
- ELLIPSE layer=... handle=6B10
- 3DFACE layer=... handle=1DA2
Def header lines: 'Definition name: <name>' / 'entity_count: N' / 'dxf_name histogram: A=1, B=2' /
'layer histogram: ...' / 'bbox from LINE start/end: [x0, y0, 0, x1, y1, 0]' / 'sampled entities (max 30):'.
INPUT FILES: bench/e1_shards/shard_01..20.jsonl - JSONL lines {"kind","prompt","unit_id"}; projection text is in "prompt".
JUDGE FILES: reports/e1/annot_v1/raw/<judge>/shard_NN.json - JSON list of
{"unit_id","def","role","wall_likelihood","wall_line_handles":[...],"notes","rationale":{...}};
wall_line_handles items are strings OR {"handle","reason"} objects - handle BOTH.
Judges: opus48_max, fable5_high, sol56_xhigh, sonnet5_xhigh, grok45_xhigh.
v0 baseline: reports/e1/ornith_annot_v0.jsonl (jsonl). Divergence lists: reports/e1/annot_v1/cluster_probe_v1.json
(full_split_defs / soft_split_defs) and reports/e1/panel_20260717/evidence/calibration_v0.json.
"""

SEG_IR = """
SEGMENT-IR v1 (shared contract - exact keys, version field required):
{"ir":"seg.v1","drawing_id":"str","units":"mm|unknown","scale_mm_per_unit":null,
 "segments":[{"sid":"s0001","handle":"8B52 or null","pts":[[x1,y1],[x2,y2]],"layer":"str",
              "kind":"line|poly-edge|arc-chord","label":"wall|opening|other|unknown",
              "source":"native|synth|floorplancad|cubicasa"}]}
"""

TRUTH = """
TRUTH-LEDGER v1 (shared contract - exact keys):
{"truth":"wall.v1","drawing_id":"str",
 "walls":[{"id":"w1","axis":[[x,y],[x,y]],"thickness":240.0,"layer":"WALL","handles":["h1","h2"]}],
 "openings":[{"id":"o1","wall_id":"w1","span_along_axis":[t0,t1],"type":"door|window"}],
 "wall_handles_flat":["h1","h2"]}
"""

P = []


def pk(pid, lane, files, prompt):
    # 'type'/'parent' = octoloop provenance envelope (schema.mjs PacketSchema) — file-loaded
    # packets bypass the CLI's mintPacket wrapper, so the envelope must be present here.
    P.append({'id': pid, 'type': 'packet', 'parent': [], 'laneKey': lane, 'files': files,
              'prompt': prompt.strip() + '\n' + RULES})


# ───────────────────────── sonnet_d (opus) x5 — S1 forensic audit ─────────────────────────
pk('w0-s1a-handle-audit', 'sonnet_d',
   ['tools/e2/s1_handle_audit.py', 'reports/e2/s1/handle_audit.json', 'reports/e2/s1/handle_audit.md'],
   """
CARD S1-A - cited-handle reality audit (forensic; deterministic script, then RUN it on full data).
Goal: for EVERY wall_line_handle cited by every judge (5 live + v0 ornith), check the handle actually
exists in that def's projection text, and record the entity kind it points to (LINE/LWPOLYLINE/...).
Write tools/e2/s1_handle_audit.py, run it, produce reports/e2/s1/handle_audit.{json,md}.
Report per judge: n_cited, pct_nonexistent, kind histogram of cited handles, per-def worst offenders.
VERDICT band (apply mechanically, state in md): pct_nonexistent >5%% for any judge -> 'INSTRUMENTATION_BUG',
1-5%% -> 'MINOR_NOISE', <1%% -> 'CLEAN'.
""" + PROJ)

pk('w0-s1b-entity-census', 'sonnet_d',
   ['tools/e2/s1_entity_census.py', 'reports/e2/s1/entity_census.json', 'reports/e2/s1/entity_census.md'],
   """
CARD S1-B - per-def entity census (forensic; deterministic script, then RUN on full data).
Goal: quantify what the v0 detector could NOT see. Per def (384): entity histogram, LINE share,
LWPOLYLINE share, INSERT count, has-coordinates share (only LINE lines carry coords in projections).
Cross with divergence: compare census of defs in cluster_probe_v1.json full_split_defs+soft_split_defs
vs uniform defs; and of the v0 divergent top-20 (from reports/e1/panel_20260717/evidence/calibration_v0.json
if it contains the list; else state LIMITS).
VERDICT band: if divergent defs' median LINE-share < half of uniform defs' median -> 'BLINDNESS_CONFIRMED'
(v0 disagreement concentrated where v0 was blind); if similar (ratio 0.8-1.2) -> 'NOT_BLINDNESS'; else 'MIXED'.
""" + PROJ)

pk('w0-s1c-bbox-units', 'sonnet_d',
   ['tools/e2/s1_bbox_units.py', 'reports/e2/s1/bbox_units.json', 'reports/e2/s1/bbox_units.md'],
   """
CARD S1-C - bbox and unit audit (forensic; deterministic script, then RUN on full data).
Goal: per def, is bbox derivable (needs >=1 LINE)? bbox span magnitude class (<10, 10-1e2, 1e2-1e4, 1e4-1e6, >=1e6);
coordinate magnitude distribution; MTEXT/TEXT numeric tokens (candidate dimension values) vs LINE span ratios
(unit anchoring feasibility: count defs where some numeric text equals a LINE span within 1%%).
Output the unit-hypothesis table (mm-scale? drawing-units ambiguous?) per magnitude class.
No fixed verdict here - this card produces the measurement table S4-C will consume; write it complete.
""" + PROJ)

pk('w0-s1d-sortkey-probe', 'sonnet_d',
   ['tools/e2/s1_sortkey_probe.py', 'reports/e2/s1/sortkey_probe.json', 'reports/e2/s1/sortkey_probe.md'],
   """
CARD S1-D - sort-key artifact probe (forensic; deterministic script, then RUN on full data).
Suspicion: the E1 'divergent top-20' is a product of the specific _score_divergence sort design, not a
stable phenomenon. Read the original scoring in reports/e1/panel_20260717/evidence/e1_crosscheck.py.
Recompute def rankings under: (a) the original key, (b) |LLM wall_likelihood - detector signal| absolute diff,
(c) likelihood-weighted rank difference, (d) per-def bootstrap of judge subsets (5 choose 3, all 10 subsets,
using annot_v1 raw judges as the LLM side). Top-20 overlap matrix (Jaccard) across (a)-(d).
VERDICT band: mean pairwise Jaccard of top-20 across keys <0.4 -> 'SORT_ARTIFACT_CONFIRMED';
>0.7 -> 'STABLE_PHENOMENON'; else 'MIXED'.
""" + PROJ)

pk('w0-s1e-censoring', 'sonnet_d',
   ['tools/e2/s1_censoring.py', 'reports/e2/s1/censoring.json', 'reports/e2/s1/censoring.md'],
   """
CARD S1-E - listing-cap censoring probe (forensic; deterministic script, then RUN on full data).
Suspicion: the E1 prompt says 'List up to 10 entity handles' - so ornith's n_handles==10 rows may be a
cap artifact, not a measurement. For v0 ornith (reports/e1/ornith_annot_v0.jsonl) and each annot_v1 judge:
distribution of len(wall_line_handles); pile-up mass at exactly 10; compare defs where entity_count>30
(projection itself truncates at 30 sampled entities - a second censoring layer, quantify it too).
VERDICT band per judge: among defs with n_handles>0, share pinned at exactly 10 >=0.5 -> 'CAP_CENSORED';
<=0.2 -> 'NOT_CENSORED'; else 'MIXED'.
""" + PROJ)

# ───────────────────────── sonnet_e (opus) x5 — S4 detector v1 modules ─────────────────────────
S4_COMMON = SEG_IR + """
S4 module wiring contract (modules must NOT import each other; cli.py wires them via dependency injection):
- normalize.py exposes: parse_modelspace(dxf_path, expand_inserts=False) -> SEG-IR dict;
  entity_to_segments(entity, transform4x?) -> list[segment-dict]   (transform = ((a,b,tx),(c,d,ty)) affine or None)
- insert_expand.py exposes: expand(dxf_path, entity_to_segments) -> SEG-IR dict  (walks INSERT tree depth-first,
  composes affine transforms incl. rotation/scale/offset, calls the INJECTED entity_to_segments)
- unit_anchor.py exposes: infer_from_dxf(dxf_path) -> {"scale_mm_per_unit":float|null,"confidence":0..1,"evidence":[str]}
- evidence_grid.py exposes: score(seg_ir, params=None) -> {"per_handle":{h:{"score":0..1,
  "evidence":{"parallel":x,"thickness":x,"junction":x,"layer":x}}},"walls":[{"handles":[...],"axis":[[x,y],[x,y]],"thickness":t}]}
ezdxf ALLOWED for this card. Selftest MUST build its own small DXF with ezdxf in the OS temp dir
(LINEs + LWPOLYLINE + ARC + a nested INSERT) and exercise your module against it.
"""

pk('w0-s4a-normalize', 'sonnet_e', ['tools/e2/detect/normalize.py'],
   """
CARD S4-A - geometry normalization module (build + selftest; this is code, evaluation comes later).
Implement tools/e2/detect/normalize.py per the wiring contract below: LINE -> line segment;
LWPOLYLINE/POLYLINE -> consecutive poly-edge segments (closed flag respected); ARC -> arc-chord segment
(chord endpoints; sagitta stored in an extra key "sagitta"); MLINE if present -> component lines;
everything else ignored (no crash). Coordinates in world units of the source doc; handle = entity handle.
expand_inserts=False means INSERT entities are SKIPPED here (S4-B owns recursion).
""" + S4_COMMON)

pk('w0-s4b-insert-expand', 'sonnet_e', ['tools/e2/detect/insert_expand.py'],
   """
CARD S4-B - INSERT world-coordinate expansion module (build + selftest).
Implement tools/e2/detect/insert_expand.py per the wiring contract below: depth-first INSERT tree walk with
composed affine transforms (insert point, rotation, xscale/yscale, block base point); cycle guard (max depth 16,
visited-stack); segments from nested blocks get "handle" of the DEEPEST source entity and an extra key
"insert_path":["parentHandle",...]. The per-entity conversion is the INJECTED entity_to_segments callable -
do not import normalize.py.
""" + S4_COMMON)

pk('w0-s4c-unit-anchor', 'sonnet_e', ['tools/e2/detect/unit_anchor.py'],
   """
CARD S4-C - dimension-anchored unit inference module (build + selftest).
Implement tools/e2/detect/unit_anchor.py per the wiring contract below. Strategy: (1) DIMENSION entities'
measurement vs their text override; (2) numeric MTEXT/TEXT tokens vs distances between nearby LINE endpoints
(within a search radius proportional to text height); (3) INSUNITS header. Combine into scale_mm_per_unit +
confidence + evidence strings. A drawing whose numeric texts match spans at ratio ~1.0 is native-mm.
ezdxf ALLOWED. Selftest: build a temp DXF with a 3280-unit line and MTEXT '3280', expect scale 1.0 high confidence.
""" + S4_COMMON)

pk('w0-s4d-evidence-grid', 'sonnet_e', ['tools/e2/detect/evidence_grid.py'],
   """
CARD S4-D - multi-evidence wall scoring module (build + selftest).
Implement tools/e2/detect/evidence_grid.py per the wiring contract below. Evidence channels, each 0..1,
reported SEPARATELY per handle (never collapse silently):
- parallel: has a near-parallel partner segment (angle tol 2deg) with lateral offset in a thickness band
  and longitudinal overlap ratio >=0.5
- thickness: the offset falls in a plausible wall band (default 50..400 in drawing units when scale unknown;
  scale_mm_per_unit-aware when provided as params={"scale_mm_per_unit":...})
- junction: segment endpoints meet other wall-candidate endpoints at L/T/X within snap tol
- layer: layer name contains wall-ish tokens (WALL, WA, BEARING, 벽) - keep this channel SEPARATE (name-blind
  scoring must remain possible by zeroing this channel via params={"use_layer":false})
Aggregate score = weighted mean (weights in params, defaults documented). Pure stdlib (input is SEG-IR json).
Selftest: hand-built SEG-IR with 2 parallel wall pairs + 1 lone line + 1 door arc-chord; assert ranking.
""" + S4_COMMON)

pk('w0-s4e-cli', 'sonnet_e', ['tools/e2/detect/cli.py', 'reports/e2/s4/selftest_demo.json'],
   """
CARD S4-E - detector CLI + eval harness (build + selftest).
Implement tools/e2/detect/cli.py wiring the sibling modules by file path (importlib.util, sys.path append of
its own dir - remember: no __init__.py). Subcommands:
  detect --dxf P --out O.json [--no-layer-channel]  -> SEG-IR via normalize+insert_expand, scale via unit_anchor,
                                                       scores via evidence_grid; writes {"seg_ir":...,"scores":...}
  eval --pred O.json --truth T.json --out E.json    -> per-handle precision/recall/F1 against TRUTH-LEDGER v1
                                                       wall_handles_flat, plus per-evidence-channel ablation table.
Graceful degradation: if a sibling module is missing at import time, print which one and exit 3 (parallel build).
Selftest: build temp DXF (ezdxf ALLOWED) with 2 walls + 1 door, run detect+eval end-to-end IF siblings exist,
else degrade to wiring check; write reports/e2/s4/selftest_demo.json with whatever ran. State degradation in LIMITS.
""" + S4_COMMON + TRUTH)

# ───────────────────────── sonnet_b (opus) x3 — S2 generator core ─────────────────────────
S2_COMMON = TRUTH + """
S2 shared design (inline contract):
WallPlan dict: {"plan":"wp.v1","seed":int,"units":"mm","walls":[{"id":"w1","axis":[[x,y],[x,y]],
"thickness":240.0,"layer":"WALL"}],"openings":[{"id":"o1","wall_id":"w1","span_along_axis":[t0,t1],
"type":"door|window"}]}   (span t in 0..1 along axis)
ezdxf ALLOWED. Selftest builds to OS temp dir. DXF version R2018 ascii.
"""

pk('w0-s2b-grammar', 'sonnet_b', ['tools/e2/synth/grammar.py'],
   """
CARD S2-B - synthetic wall grammar + DXF emitter core (build + selftest).
Implement tools/e2/synth/grammar.py:
- plan_random(seed, spec) -> WallPlan: rectilinear wall network (outer loop + inner partitions),
  L/T/X junctions, thickness sampled from spec {"thickness_choices":[100,150,200,240,300],"n_rooms":2..6,
  "extent":[w,h]}; deterministic per seed.
- emit(plan, dxf_path, opening_renderer=None) -> TRUTH-LEDGER v1: each wall = two parallel LINEs offset
  +-thickness/2 with mitred junction trimming (simple segment-trim acceptable v1); if opening_renderer is
  given call opening_renderer(wall_dict, add_line_fn) per wall and merge the returned opening-truth entries;
  ledger handles = REAL handles read back from the saved ezdxf doc.
Layer for walls from plan; add a few non-wall clutter LINEs on layer 'MISC' (recorded as non-wall).
Selftest: seed 7, 3 rooms; assert ledger wall handle count == 2*len(walls) minimum and re-open DXF to verify.
""" + S2_COMMON)

pk('w0-s2c-openings', 'sonnet_b', ['tools/e2/synth/openings.py'],
   """
CARD S2-C - openings module (build + selftest).
Implement tools/e2/synth/openings.py:
- assign(plan, seed, spec) -> plan with openings填 populated: doors (0.9m default) and windows on random walls,
  spans clamped away from junction zones; spec {"door_p":0.6,"window_p":0.4}.
- opening_renderer(wall_dict, add_line_fn) -> list of opening-truth entries: renders the opening by SPLITTING
  the wall's two parallel lines at the span (the gap), adding jamb tick lines, and (doors) a quarter-circle
  swing arc on layer 'DOOR' - use add_line_fn(start,end,layer) for lines; arcs may be emitted by returning
  {"arc":{"center":[x,y],"r":r,"start":a0,"end":a1,"layer":"DOOR"}} entries the caller renders.
  (This exact callable is injected into grammar.emit - see signature; build against the contract, do not import grammar.)
Selftest: fabricate a WallPlan literal, run assign + call opening_renderer with a recording stub add_line_fn,
assert gap math (no line crosses the span interval).
""" + S2_COMMON)

pk('w0-s2d-noise', 'sonnet_b', ['tools/e2/synth/noise.py'],
   """
CARD S2-D - messiness module (build + selftest).
Implement tools/e2/synth/noise.py: messify(dxf_in, dxf_out, seed, level, ledger) -> (new_ledger, handle_map)
operating on a SAVED synth DXF via ezdxf:
- level 1: convert a fraction of wall LINEs to LWPOLYLINE (same geometry) - the ledger must FOLLOW
  (handle_map old->new; new_ledger handles updated)
- level 2: + wrap random room clusters into a block definition + INSERT (nested one deep)
- level 3: + jitter non-wall clutter, duplicate short fragments, add a hatch patch on layer 'INSUL'
Never alter wall AXIS geometry (truth invariant); only representation. Selftest: build a minimal DXF with
2 wall lines via ezdxf inline (do not import grammar), messify level 1..3, assert handle_map covers all
converted handles and axes unchanged.
""" + S2_COMMON)

# ───────────────────────── sonnet_c (opus) x3 — S2 support ─────────────────────────
pk('w0-s2a-real-stats', 'sonnet_c',
   ['tools/e2/s2_real_stats.py', 'reports/e2/s2/real_stats.json', 'reports/e2/s2/real_stats.md'],
   """
CARD S2-A - real-corpus wall statistics extractor (deterministic script, then RUN on full data).
Goal: the fidelity yardstick for the synthetic generator. From bench/e1_shards projections (LINE coords only -
acknowledge the polyline blindness in LIMITS):
- parallel LINE pair spacing distribution (same def, angle tol 2deg, overlap>=0.3): histogram of offsets ->
  candidate thickness bands, per layer-token class (WALL-ish / DOOR / DIM / other)
- entity-type mix per def role (join annot_v1 raw roles by def: use opus48_max as reference judge)
- layer token frequency table (split on $ separators and non-alnum)
Write reports/e2/s2/real_stats.{json,md}. The json is the S2-F comparator's input - keys:
{"stats":"rs.v1","thickness_hist":{"bin_edges":[...],"counts":[...]},"entity_mix_by_role":{...},"layer_tokens":{...}}
""" + PROJ)

pk('w0-s2e-pack-cli', 'sonnet_c', ['tools/e2/s2_pack_cli.py'],
   """
CARD S2-E - S/F/M pack builder CLI (build + selftest).
Implement tools/e2/s2_pack_cli.py: build --tier S|F|M --n N --seed K --out DIR
- imports synth modules by PATH (importlib.util from tools/e2/synth/: grammar.py, openings.py, noise.py;
  no __init__.py) with graceful per-module absence handling (exit 3 naming the missing module - parallel build)
- tier S = grammar only; F = + openings; M = + noise level 2-3
- emits per drawing: NNNN.dxf + NNNN.truth.json (TRUTH-LEDGER v1) + a pack manifest.json (tier, seeds, files)
Selftest: with whichever sibling modules exist, build a 2-drawing S pack to OS temp; if grammar.py missing,
degrade to manifest-schema check and say so in LIMITS.
""" + S2_COMMON)

pk('w0-s2f-fidelity', 'sonnet_c', ['tools/e2/s2_fidelity.py', 'reports/e2/s2/fidelity_bands.json'],
   """
CARD S2-F - synthetic-vs-real fidelity comparator (build + selftest).
Implement tools/e2/s2_fidelity.py: compare --pack DIR --real reports/e2/s2/real_stats.json --out R.json
- recompute the SAME statistics as S2-A but from pack DXFs via ezdxf (ezdxf ALLOWED): parallel-pair offset
  histogram, entity mix, layer tokens
- distances: KS statistic (own stdlib implementation) for thickness hist; total-variation for categorical mixes
- verdict per statistic against bands read from reports/e2/s2/fidelity_bands.json which YOU also write now as
  DRAFT (clearly marked "draft_pending_prereg": true): thickness KS <= 0.20 PASS_DRAFT, entity-mix TV <= 0.25
  PASS_DRAFT, else FAIL_DRAFT. Bands get sealed by prereg later - your job is the machinery.
Selftest: synthesize two tiny stat dicts inline and assert distance math; real pack comparison goes to LIMITS.
""" + S2_COMMON)

# ───────────────────────── codex_56terra x4 — S3 external datasets ─────────────────────────
S3_COMMON = SEG_IR + """
DEFERRAL RULE: no network. Build format handling around an explicit FORMAT_SPEC dict at the top of the module
(single revision point), plus a fixture file you author from that spec. Real-data validation is a later step -
say PASS_WITH_DEFERRAL in LIMITS. Do not silently guess beyond your FORMAT_SPEC.
"""

pk('w0-s3b-fpc-parse', 'codex_56terra',
   ['tools/e2/extset/fpc_parse.py', 'tools/e2/extset/fixtures_fpc.svg'],
   """
CARD S3-B - FloorPlanCAD SVG parser -> SEGMENT-IR (build + selftest, fixture-driven).
FloorPlanCAD distributes vector floor plans as SVG whose primitives carry semantic class annotations
(line-level labels incl. wall classes). Implement tools/e2/extset/fpc_parse.py:
- FORMAT_SPEC dict: element types handled (line, polyline, path with M/L only), the attribute(s) read for
  the semantic class, and the class list you assume - all in ONE dict
- parse(svg_path, label_map=None) -> SEG-IR (source='floorplancad'; label via label_map callable if given,
  else 'unknown'; handle=None; sid stable from element order)
- author tools/e2/extset/fixtures_fpc.svg from your FORMAT_SPEC: >=12 primitives, >=3 classes incl. a wall class
Selftest: parse the fixture, assert counts per kind and class passthrough.
""" + S3_COMMON)

pk('w0-s3c-label-map', 'codex_56terra',
   ['tools/e2/extset/label_map.py', 'reports/e2/s3/label_map.json'],
   """
CARD S3-C - external label vocabulary mapping (build + selftest).
Implement tools/e2/extset/label_map.py + write reports/e2/s3/label_map.json:
- the json: {"map":"lm.v1","sets":{"floorplancad":{"<their-class>":"wall|opening|other"},
  "cubicasa":{...}},"unmapped_policy":"other"} - fill with your best-known class lists for both datasets,
  every entry carrying "confidence":"known|assumed" (assumed = revisit after real download; be honest)
- module: load() -> mapping; to_label(set_name, cls) -> wall|opening|other|unknown; validate(mapping) ->
  list of violations (unknown target labels, duplicate keys, empty sets)
Selftest: validate the shipped json (0 violations) + roundtrip a dozen lookups incl. unmapped -> policy.
""" + S3_COMMON)

pk('w0-s3d-cubicasa-parse', 'codex_56terra',
   ['tools/e2/extset/cubicasa_parse.py', 'tools/e2/extset/fixtures_cubicasa.svg'],
   """
CARD S3-D - CubiCasa5K parser -> SEGMENT-IR (build + selftest, fixture-driven).
CubiCasa5K distributes per-floorplan SVG with polygon regions whose classes mark walls/rooms/openings.
Implement tools/e2/extset/cubicasa_parse.py:
- FORMAT_SPEC dict as in the deferral rule (polygon/rect handled; class attribute; assumed class list)
- parse(svg_path, label_map=None) -> SEG-IR where WALL POLYGONS become their boundary edges as segments
  (kind='poly-edge', label='wall'), other classes -> label 'other'/'opening'; document the polygon->edge
  convention in the module docstring (edges deduplicated when two wall polygons share a border - v1: no dedup,
  note it in LIMITS)
- author tools/e2/extset/fixtures_cubicasa.svg: >=2 wall polygons + 1 room + 1 door per your spec
Selftest: parse fixture, assert edge counts and labels.
""" + S3_COMMON)

pk('w0-s3e-features', 'codex_56terra', ['tools/e2/extset/features.py'],
   """
CARD S3-E - SEGMENT-IR -> per-segment feature vectors (build + selftest).
Implement tools/e2/extset/features.py: featurize(seg_ir) -> list of
{"sid","geom":{"length":..,"angle_mod90":..,"par_min_offset":..,"par_overlap":..,"junction_deg":..,
"thickness_candidate":..,"n_parallel_partners":..},"name":{"layer_tokens":[...]},"label":"..."}
- geom features are computed ONLY from coordinates (angle tol 2deg for parallel partner search, endpoint snap
  tol = 1%% of drawing bbox diagonal for junction degree)
- name features kept in a SEPARATE subdict (the S6 name-blind arm drops "name" wholesale - never mix)
- also: write_jsonl(features, path) and a main: featurize --in ir.json --out f.jsonl
Selftest: hand-built SEG-IR (two parallel wall segments + a crossing line + an isolated line), assert
par_min_offset/junction_deg/n_parallel_partners values exactly.
""" + S3_COMMON)

# ───────────────────────── grok x5 — S5 battery + S3-A fetch ─────────────────────────
S5_COMMON = SEG_IR + TRUTH + """
ezdxf ALLOWED. Originals are READ-ONLY: every transform reads dxf_in and writes dxf_out under an explicit
staging dir argument - never in place, never touching source paths.
"""

pk('w0-s5a-transforms-rigid', 'grok', ['tools/e2/meta/transforms_rigid.py'],
   """
CARD S5-A - rigid/scale/unit metamorphic transforms (build + selftest).
Implement tools/e2/meta/transforms_rigid.py with transform(dxf_in, dxf_out, kind, params, seed) for kinds:
rotate (angle deg about drawing centroid), translate (dx,dy), mirror (axis x|y), scale (factor about centroid),
units (INSUNITS header swap mm<->m WITH coordinate rescale so geometry is equivalent).
Handles are preserved by ezdxf on copy - return {"kind","params","handle_map":"identity"} metadata dict.
Selftest: temp DXF with 3 LINEs, apply each kind, re-open and assert coordinates transformed within 1e-6
and entity count/handles unchanged.
""" + S5_COMMON)

pk('w0-s5b-transforms-struct', 'grok', ['tools/e2/meta/transforms_struct.py'],
   """
CARD S5-B - structural metamorphic transforms (build + selftest).
Implement tools/e2/meta/transforms_struct.py:
- explode(dxf_in, dxf_out) -> handle_map: flatten every top-level INSERT into world-space entities
  (one level per call; loop to fixpoint with max 16 iterations); handle_map maps old deepest-entity handle ->
  new exploded entity handle (this is what keeps truth ledgers comparable)
- rename_layers(dxf_in, dxf_out, scheme, seed) -> layer_map: scheme 'shuffle' (permute names) or
  'anonymize' (L001, L002...) - geometry untouched
Selftest: temp DXF with a block INSERT of 2 lines + 1 direct line; explode; assert 3 world entities and a
complete handle_map; rename; assert layer_map bijective.
""" + S5_COMMON)

pk('w0-s5c-invariance', 'grok', ['tools/e2/meta/invariance.py'],
   """
CARD S5-C - invariance metric harness + sentinels (build + selftest).
Implement tools/e2/meta/invariance.py:
- compare(pred_before, pred_after, handle_map) -> {"invariance":0..1,"flips":[handles]} where predictions are
  the detector cli output json ({"scores":{"per_handle":{h:{"score":...}}}}) thresholded at 0.5, after mapping
  handles through handle_map
- sentinel_zero(pred) / sentinel_all(pred, n_handles): a detector that predicts NO walls scores invariance 1.0
  trivially - the battery must therefore FAIL any run where wall-count==0 (sentinel_zero) or wall-share>0.9
  (sentinel_all); implement recall_floor(pred, truth_ledger) -> recall for packs where truth exists
- verdict(inv, zero_flag, all_flag, recall) applying: PASS needs inv>=band AND no sentinel flag AND
  (recall>=floor when truth given) - bands are ARGUMENTS, not constants (prereg seals them later)
Selftest: fabricate before/after prediction dicts incl. a zero-wall case; assert sentinel catches it.
""" + S5_COMMON)

pk('w0-s5d-battery-cli', 'grok', ['tools/e2/meta/battery_cli.py'],
   """
CARD S5-D - metamorphic battery runner CLI (build + selftest).
Implement tools/e2/meta/battery_cli.py: run --drawings DIR --staging DIR --detector-cmd "CMD {dxf} {out}"
--transforms rotate,mirror,scale,units,explode,rename --budget-drawings N --timeout-s T --out-xlsx R.xlsx
- imports sibling modules by path (transforms_rigid.py, transforms_struct.py, invariance.py; no __init__.py;
  graceful exit 3 naming missing siblings)
- per drawing x transform: stage transformed copy, run detector cmd twice (original+transformed) via
  subprocess with timeout, compare via invariance.compare, apply sentinels
- xlsx via openpyxl (ALLOWED): one row per (drawing, transform) with invariance, flips count, sentinel flags,
  wall counts, timing; summary sheet with per-transform means
- budget caps are MANDATORY args (runaway defense)
Selftest: mock detector-cmd = a tiny inline python that echoes a fixed prediction json; 1 temp drawing,
2 transforms; assert xlsx written with expected row count.
""" + S5_COMMON)

pk('w0-s3a-fetch', 'grok', ['tools/e2/extset/fetch.py', 'reports/e2/s3/sources.json'],
   """
CARD S3-A - external dataset fetch tooling (build + selftest; NO network in this card).
Implement tools/e2/extset/fetch.py + write reports/e2/s3/sources.json:
- sources.json: {"sources":"src.v1","sets":{"floorplancad":{"homepage":"<best-known official URL>",
  "artifacts":[{"name":"...","url":"<best-known>","sha256":null,"size_hint":null}],"license_note":"labels NC;
  research use approved by owner 2026-07-17"},"cubicasa":{...}}} - fill best-known official locations,
  every url flagged "verified":false (a later online step flips them)
- fetch.py: download --set NAME --dest D:/mirror/extsets/<set> with resumable HTTP (Range), sha256 verify,
  and inventory --dest DIR -> inventory.json (file count, sizes, extensions histogram)
- selftest (OFFLINE): url format validation for all sources.json entries + resume-logic unit check against
  a local temp file served via file:// read (no sockets) + inventory on a temp dir with 3 fake files.
""" + SEG_IR)

# ── validation: fileset disjointness + counts per lane ──
seen = {}
for p in P:
    for f in p['files']:
        if f in seen:
            raise SystemExit('FILESET OVERLAP: {0} in {1} and {2}'.format(f, seen[f], p['id']))
        seen[f] = p['id']
lanes = {}
for p in P:
    lanes[p['laneKey']] = lanes.get(p['laneKey'], 0) + 1
assert lanes == {'sonnet_d': 5, 'sonnet_e': 5, 'sonnet_b': 3, 'sonnet_c': 3,
                 'codex_56terra': 4, 'grok': 5}, lanes
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(P, f, ensure_ascii=False, indent=1)
print('packets:', len(P), 'lanes:', lanes, '->', OUT)
