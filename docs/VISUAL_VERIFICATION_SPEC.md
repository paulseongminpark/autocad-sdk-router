# VISUAL_VERIFICATION_SPEC — `tools/visual_report.py`

Lane E visual verification shell for the CAD OS Layer.

## Purpose

Produce an **`ariadne.visual_artifact.v1`** envelope
(`schemas/visual_artifact.v1.schema.json`) describing a derived visual/output
artifact (PNG / PDF / SVG / DXF / diff overlay) for a drawing or IR — *or*,
when no producer is wired, a truthful placeholder that records
`not_implemented`/`blocked` with **no usable refs**.

## Safety guarantees

- **Standard library only.** No third-party imports, no pip.
- **No rendering, no file writes** in this packet. The shell decides *whether* a
  safe producer exists by reading the router-published status JSON (read-only);
  it does not render.
- **Original DWG is a READ-ONLY `source_ref`.** The source path is recorded for
  provenance only and is never written.
- **No-fake-success (governing rule).** The shell NEVER returns `status: "ok"`
  unless a real producer actually wrote files. Today no DWG→raster producer is
  wired, so the shell returns:
  - `not_implemented` — no wired route can produce the requested kind, **or** a
    route is available+competent but the producer is not implemented; or
  - `blocked` — a competent route exists but is currently unavailable.
  In every non-`ok` case `refs == []`.

## Public API

```python
from visual_report import available_render_routes, build_visual_report
probe  = available_render_routes()                 # read-only status probe
report = build_visual_report("…/input.dwg", kind="png")   # visual_artifact.v1
```

`build_visual_report(source_ref, kind="png", artifact_id=None, out_dir=None,
route=None) -> dict`.

## Route probe

`available_render_routes()` reads `reports/autocad_router_status_latest.json`
(read-only) and reports availability of the **safe visual candidate routes**:

| route | competent kinds |
|-------|-----------------|
| `pdf_svg_vector_route` | svg, pdf, diff_overlay |
| `raster_compare_route` | png, jpg, diff_overlay |

It also reports `render_layout_status` — the registry status of the DWG layout
render op `render.layout` (which gates native DWG-to-image rendering).

## Why visual PASS is currently `not_implemented`

- The operation-registry op `render.layout` is **`blocked`** in
  `operations.v2.json` — there is no wired, host-available DWG→image renderer.
- The two candidate routes are *available* but are **vector/compare** tools:
  `pdf_svg_vector_route` consumes existing PDFs/SVGs; `raster_compare_route`
  compares existing PNG renders (SSIM). Neither *renders a DWG* to a new image.
- Therefore, for a DWG/IR source the shell truthfully returns
  `status: "not_implemented"` (recording the route that *would* have been used
  if a producer existed) rather than fabricating a visual PASS.

When a real read-only render/export producer is wired (e.g. `render.layout`
moves to `implemented`, or a router export route emits an SVG/PDF from the DWG),
`build_visual_report` will route through it and return `status: "ok"` with
populated `refs`. That code path exists; it is simply not exercised today.

## visual_artifact envelope (placeholder example)

```jsonc
{
  "schema": "ariadne.visual_artifact.v1",
  "artifact_id": "vis-…",
  "kind": "png",
  "status": "not_implemented",
  "source_ref": "…/input.dwg",          // READ-ONLY provenance
  "refs": [],                            // empty: no-fake-success
  "diagnostics": { "warnings": ["no wired route can produce kind 'png' for a DWG/IR source"] },
  "probe": { "render_layout_status": "blocked", "any_route_available": true, "routes": {...} }
}
```

## Exact commands

```bash
# Self-test: emit a sample envelope for a DWG source, verdict on last line.
python tools/visual_report.py       # exit 0 = SELFTEST_OK

# Verdict line example:
#   SELFTEST_OK | status=not_implemented refs=0 | render_layout=blocked any_route=True
```

## Not implemented yet

- **Any rendering/export producer.** No PNG/PDF/SVG/diff-overlay is produced for
  a DWG/IR. Wiring requires either `render.layout` becoming host-available, or a
  router route that exports a vector/raster from the staged DWG.
- **Diff overlays** (before/after visual compare) — depends on the patch
  execution + render producers, both out of scope here.
