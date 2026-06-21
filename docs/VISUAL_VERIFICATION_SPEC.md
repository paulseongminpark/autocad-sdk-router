# VISUAL_VERIFICATION_SPEC — `tools/visual_report.py`

Lane E visual verification for the CAD OS Layer.

## Purpose

Produce an **`ariadne.visual_artifact.v1`** envelope
(`schemas/visual_artifact.v1.schema.json`) describing a derived visual/output
artifact for a drawing or its extracted IR — and, for the default route, produce
**real artifact files on disk** (`before.svg` / `after.svg` / `overlay.svg` +
`visual_diff.json`).

The verification idea: the strongest *host-independent* visual answer to "did the
extraction/patch produce what we think?" is to **render the EXTRACTED IR geometry
itself** — a real SVG drawn directly from the `dwg_graph_ir.v1` entities. No
AutoCAD, no plotter, no host quirks. The SVG is a picture of *exactly* the
geometry that landed in the IR, so a correct render is evidence the extraction is
sound, and the overlay shows *exactly* the handles the diff says changed.

## Status: IMPLEMENTED (real artifacts via the `ir_svg` route)

`build_visual_report` defaults to the **`ir_svg`** route, a pure-standard-library
IR→SVG renderer. It **always** writes real artifacts and returns
`status: "ok"` with populated `refs` (path + `byte_size` + `sha256`). The visual
lane is therefore a **genuine PASS** — the artifacts really exist on disk; nothing
is faked.

`accoreconsole_plot` (headless DWG→PDF) remains **`not_implemented` on this host**
(honest): from Core Console alone a reliable read-only DWG→PDF/PNG render is not
achievable here — see the empirical finding below. It is never claimed to emit a
file.

## Safety guarantees

- **Standard library only.** `hashlib`, `json`, `math`, `os`, `time`, `uuid`,
  `xml.etree` (in tests) — no third-party imports, no pip, no AutoCAD.
- **Original DWG/IR is READ-ONLY.** The renderer only ever *reads* `source_ref`
  and `post_ir_path`; it writes solely into `out_dir`.
- **No-fake-success (governing rule).** `status: "ok"` is returned only after the
  files were written (verified by the caller via `os.path.isfile` + non-zero
  size). If the source IR cannot be loaded → `status: "error"` with empty `refs`.
- **Deterministic artifact bodies.** Entities are emitted in input order; all
  numbers use a fixed 4-dp format (`-0` collapsed, no exponents); no timestamps
  appear inside any artifact body. Re-rendering the same IR to the same path is
  byte-identical. (`visual_diff.json` records absolute artifact paths, so its
  bytes are stable for a fixed `out_dir`; only the run-dir prefix varies between
  different output directories — by design, since it points at where the files
  are.)

## Public API

```python
from visual_report import (available_render_routes, render_ir_to_svg,
                           build_visual_report)
```

### `render_ir_to_svg(ir, out_svg_path, highlight_handles=None) -> dict`

Renders a `dwg_graph_ir.v1` IR to a real SVG file. Returns
`{"path", "element_count", "viewbox": [x, y, w, h]}`.

Per-kind rendering (`geometry.kind`):

| kind | SVG |
|------|-----|
| `line` | `<line>` start→end |
| `arc` | `<path>` elliptical arc. **IR stores angles in RADIANS** (verified: 0..2π on the golden drawing); converted to an SVG arc. A full-circle (start==end) degenerates to a `<circle>`. |
| `circle` | `<circle>` center + radius |
| `lwpolyline` / `polyline` | `<polyline>`/`<polygon>` from `vertices`; **when the native IR carries no vertices**, the entity **bbox rectangle** is drawn instead (renders the extracted footprint — never invents geometry). |
| `block_reference` (INSERT) | crosshair marker + block-name label at the insertion point |
| `text` / `mtext` | the string at its position, drawn with a local Y-flip so glyphs are upright |
| *anything else with a bbox* | bbox rectangle (the extracted footprint) |

- **Y-flip.** DWG is Y-up, SVG is Y-down. The whole drawing is wrapped in one
  `transform="translate(…) scale(1,-1)"` group, so coordinates stay in world
  units and the picture is right-side-up. Text/marker labels carry a *local*
  counter-flip so they read upright.
- **viewBox.** The union of entity bboxes (entities with an empty `bbox` are
  skipped for the extent), padded by a 2% margin. Stroke width / marker / text
  sizes scale to the drawing span so they render at a consistent on-screen weight
  regardless of model units.
- **`highlight_handles`.** Those entities are stroked **red** (`#e00000`, 3× the
  base stroke) and their `<g>` carries `class="hl"`; everything else is
  `class="ent"`. Each group also carries `data-handle` / `data-kind` so the DOM
  is inspectable.

### `build_visual_report(source_ref, kind="svg", post_ir_path=None, diff_path=None, artifact_id=None, out_dir=None, route="ir_svg", *, highlight_handles=None, timeout=180) -> dict`

Builds a `visual_artifact.v1` envelope of REAL rendered artifacts.

- Always renders **`before.svg`** from the `source_ref` IR.
- When **both** `post_ir_path` and `diff_path` are supplied, also renders
  **`after.svg`**, **`overlay.svg`** (the after drawing with the diff's
  created+modified handles in red), and writes **`visual_diff.json`**
  (created/modified/deleted counts + the artifact paths + per-artifact element
  counts and viewboxes).
- `highlight_handles` overrides the diff-derived highlight set when given;
  otherwise the diff's created+modified handles are used. Diff vocabularies are
  handled robustly: both the frozen `added`/`modified` and the M02 alias
  `created`/`modified` count as "highlight"; `removed`/`deleted` count as
  deletions.

`refs` carries one entry per artifact with `role` ∈ {before, after, overlay,
visual_diff}, plus real `byte_size` + `sha256`.

### `available_render_routes() -> dict`

Read-only probe.

| route | available | implemented | meaning |
|-------|-----------|-------------|---------|
| **`ir_svg`** | **true** (always) | **true** | pure-stdlib IR→SVG of the extracted geometry; the default route; needs no AutoCAD; verifies the extraction directly. |
| `pdf_svg_vector_route` | from live router status | false | router vector route; no producer wired in this lane. |
| `raster_compare_route` | from live router status | false | router compare route; no producer wired in this lane. |
| `accoreconsole_plot` | engine present | **false** (`status: not_implemented`) | headless DWG→PDF — NOT achievable on this Core Console host (see below). Never claimed to emit a file. |

`default_route` is `ir_svg`; `any_available` is always `true`.

## Empirical finding on this box (accoreconsole 2027, kor locale)

The accoreconsole headless render was probed three ways against the golden staged
copy:

| attempt | result | why |
|---------|--------|-----|
| `EXPORTPDF` / `-EXPORTPDF` | FAIL | Unknown command in Core Console. |
| `-PLOT` prompt-chain → `DWG To PDF.pc3` | FAIL | command + device + paper accepted, but the post-paper keyword prompts desync under the kor locale / version-specific prompt order; no PDF emitted. |
| AutoLISP COM `vla-…PlotToFile` | FAIL | `vlax-get-acad-object` returns `nil` — Core Console has no ActiveX automation server, so COM plotting is impossible from accoreconsole. |

**Conclusion:** from Core Console alone a reliable read-only DWG→PDF/PNG render is
not achievable here, so `accoreconsole_plot` is reported `not_implemented`. The
real visual artifact on this host is the **`ir_svg`** render, which needs no
AutoCAD at all. (A native PlotEngine ARX module, or full-AutoCAD COM
`Plot.PlotToFile` while `acad.exe` runs, could make a DWG→PDF route real later;
both are out of this lane's scope.)

## Artifact contract (`visual_artifact.v1`)

On success (`ok`), an overlay run:

```jsonc
{
  "schema": "ariadne.visual_artifact.v1",
  "artifact_id": "vis-…",
  "kind": "diff_overlay",                  // "svg" when before-only
  "status": "ok",
  "source_ref": "…/pre/dwg_graph_ir.json", // READ-ONLY provenance (before IR)
  "route": "ir_svg",
  "media_type": "image/svg+xml",
  "refs": [
    { "ref": "…/runs/m02_visual/before.svg",  "role": "before",
      "media_type": "image/svg+xml", "byte_size": 3604390, "sha256": "…" },
    { "ref": "…/runs/m02_visual/after.svg",   "role": "after",   … },
    { "ref": "…/runs/m02_visual/overlay.svg", "role": "overlay", … },
    { "ref": "…/runs/m02_visual/visual_diff.json", "role": "visual_diff",
      "media_type": "application/json", … }
  ],
  "run_dir": "…/runs/m02_visual",
  "visual_diff": "…/runs/m02_visual/visual_diff.json",
  "diagnostics": {
    "before":  { "element_count": 23258, "viewbox": […], "entity_count": 21747 },
    "after":   { "element_count": 23259, "viewbox": […], "entity_count": 21748 },
    "overlay": { "element_count": 23259, "highlighted_handles": ["1919D"],
                 "highlighted_present_in_after": ["1919D"] },
    "diff_counts": { "created": 1, "modified": 0, "deleted": 0 },
    "warnings": []
  }
}
```

`visual_diff.json` (`ariadne.visual_diff.v1`):

```jsonc
{
  "schema": "ariadne.visual_diff.v1",
  "diff_id": "diff-3a4e8e6015e1444f",
  "counts": { "created": 1, "modified": 0, "deleted": 0 },
  "highlighted_handles": ["1919D"],
  "highlighted_handles_present_in_after": ["1919D"],
  "artifacts": { "before": "…/before.svg", "after": "…/after.svg",
                 "overlay": "…/overlay.svg" },
  "element_counts": { "before": 23258, "after": 23259, "overlay": 23259 },
  "viewbox": { "before": […], "after": […], "overlay": […] }
}
```

On a bad source (`error`, no-fake-success): `status: "error"`, `refs: []`, with a
warning naming the unreadable `source_ref`.

## Verified live run (the M02 patch)

Rendered the real patch run (pre 21747 → post 21748, **+1 LINE** at handle
`1919D`, layer `ARIADNE_M02_PROBE`):

```bash
python tools/visual_report.py --render
#   build_visual_report(
#     source_ref ="runs/m02_patch_live2/pre/dwg_graph_ir.json",
#     post_ir_path="runs/m02_patch_live2/post/dwg_graph_ir.json",
#     diff_path  ="runs/m02_patch_live2/cad_diff.json",
#     out_dir    ="runs/m02_visual")
```

Produced under `runs/m02_visual/` (all real, on disk):

| artifact | size | element_count |
|----------|------|---------------|
| `before.svg`  | ~3.60 MB | 23258 (19204 entity groups) |
| `after.svg`   | ~3.60 MB | 23259 (19205 entity groups) |
| `overlay.svg` | ~3.60 MB | 23259 — **1 group highlighted red** (handle `1919D`) |
| `visual_diff.json` | ~1.2 KB | counts created=1 / modified=0 / deleted=0 |

The overlay highlights exactly the **+1 created LINE** (`1919D`) in red; it is
present in `after`/`overlay` and (correctly) absent from `before` (the pre-patch
state). `after − before` drawable-group delta = **1**, matching the diff.

## Exact commands

```bash
# Fast, deterministic self-test (renders a fixture + a tiny overlay in a temp
# dir, parses the SVG as XML, asserts the created handle is highlighted red):
python tools/visual_report.py
#   selftest: OK | default_route: ir_svg | ir_svg implemented: true |
#   accoreconsole_plot implemented: false

# REAL render of the live patch run into runs/m02_visual:
python tools/visual_report.py --render

# Unit tests (pytest-discoverable, dual-runnable, stdlib only):
python -m unittest tests.unit.test_visual_report -v
python tests/unit/test_visual_report.py
```

## Out of scope (this lane)

- **Rasterizing** an SVG/PDF to PNG (downstream / `raster_compare_route`).
- **Headless DWG→PDF** rendering (`accoreconsole_plot` stays `not_implemented`
  on this host; full-AutoCAD COM `Plot.PlotToFile` and a native PlotEngine ARX
  module are possible future routes).
- **Hatch fill / spline curve** rendering — the native IR carries no coordinate
  geometry for those here, so they render as their bbox footprint.
