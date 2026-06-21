# VISUAL_VERIFICATION_SPEC — `tools/visual_report.py`

Lane E visual verification for the CAD OS Layer.

## Purpose

Produce an **`ariadne.visual_artifact.v1`** envelope
(`schemas/visual_artifact.v1.schema.json`) describing a derived visual/output
artifact (PNG / PDF / SVG / DXF / diff overlay) for a drawing or IR — *or*, when
a render cannot be produced, a truthful envelope that records
`not_implemented` / `blocked` with **no usable refs**.

## Status: implemented (real render ATTEMPTED, honest result)

This module is no longer a pure shell. For a raster/pdf `kind` it **actually
runs a real headless render attempt on a staged copy** and reports the truth:

- If a real artifact file appears → `status: "ok"` with populated `refs`
  (path + `byte_size` + `sha256`).
- If no file appears → `status: "not_implemented"` with the captured evidence
  paths (staged copy, `.scr`, stdout, stderr) and an explicit reason.

A claimed visual PASS (**`ok`**) REQUIRES a real artifact on disk. No fake PASS
is ever returned.

## Safety guarantees

- **Standard library only.** `subprocess`, `shutil`, `hashlib`, `json`,
  `pathlib`/`os` — no third-party imports, no pip.
- **Original DWG is READ-ONLY.** The render attempt operates on a
  `shutil.copy2` **staged copy** under the run dir; the original `source_ref` is
  never written.
- **All external I/O captured.** Every accoreconsole / COM invocation has its
  stdout, stderr, exit code written into the run dir.
- **No-fake-success (governing rule).** `status: "ok"` is returned **only** when
  a real producer wrote a file (verified by `os.path.isfile` + non-zero size).
  The process exit code is **not** trusted as proof of output.

## Public API (signatures preserved)

```python
from visual_report import available_render_routes, build_visual_report
probe  = available_render_routes()                       # read-only probe
report = build_visual_report("…/input.dwg", kind="pdf")  # visual_artifact.v1
```

`build_visual_report(source_ref, kind="png", artifact_id=None, out_dir=None,
route=None, *, attempt_render=True, allow_full_autocad=False, timeout=180) ->
dict`

- `attempt_render` (default **True**) — for png/jpg/pdf kinds, actually run the
  accoreconsole staged-copy plot attempt. Set False to get the truthful decision
  without spending a render.
- `allow_full_autocad` (default **False**) — opt-in to drive the **running** full
  AutoCAD via COM `PlotToFile`. Off by default because it touches the live user
  session.
- `timeout` — seconds for each external render attempt.

The added parameters are keyword-only with safe defaults, so every prior caller
(`build_visual_report(src)`, `build_visual_report(src, kind="png")`, …) keeps
working unchanged.

## Render routes (what `available_render_routes()` probes)

Two **safe vector/compare candidate routes** (read from the router status JSON,
read-only):

| route | competent kinds |
|-------|-----------------|
| `pdf_svg_vector_route` | svg, pdf, diff_overlay |
| `raster_compare_route` | png, jpg, diff_overlay |

…plus `render_layout_status` (the registry status of the DWG layout render op
`render.layout`), and two **genuine DWG render routes**:

| render route | when | how it is treated |
|--------------|------|-------------------|
| `accoreconsole_plot` | accoreconsole engine present | `attemptable: true`, `verified: false`. `build_visual_report` drives it on a **staged copy** with a `-PLOT` → `DWG To PDF.pc3` script, then verifies the output file. |
| `full_autocad_com` | `acad.exe` running | `available: true`, **`gated: true`**, `attemptable: false`. Real COM `Plot.PlotToFile` route, but driven **only** with `allow_full_autocad=True`. Never auto-driven. |

## Render route(s) attempted, and the empirical finding on this box

The accoreconsole headless render was probed three ways against the golden
staged copy (AutoCAD 2027 Core Console, **kor** locale):

| attempt | result | why |
|---------|--------|-----|
| `EXPORTPDF` / `-EXPORTPDF` | FAIL | Unknown command in Core Console. |
| `-PLOT` prompt-chain → `DWG To PDF.pc3` | FAIL | command + device + paper accepted, but the post-paper keyword prompts desync under the kor locale / version-specific prompt order; no PDF emitted. |
| AutoLISP COM `vla-…PlotToFile` | FAIL | `vlax-get-acad-object` returns `nil` — Core Console has no ActiveX automation server, so COM plotting is impossible from accoreconsole. |

**Conclusion:** from **Core Console alone** a reliable read-only DWG→PDF/PNG
render is **not achievable** on this host. `build_visual_report(kind="pdf"|"png")`
therefore **attempts** the staged-copy `-PLOT`, captures evidence, finds no
output file, and returns `status: "not_implemented"` (no fake artifact).

A real artifact is achievable via:
- **`full_autocad_com`** — when `acad.exe` is running, full AutoCAD's COM
  `AcadApplication` *does* expose `Plot.PlotToFile` (unlike Core Console). Pass
  `allow_full_autocad=True` to drive it; it opens the **staged copy** as a side
  document (read-only), plots to PDF, and closes it. Gated by default because it
  uses the live GUI session and may be refused if AutoCAD is mid-command — in
  which case it too reports `not_implemented` truthfully.
- a native **PlotEngine ARX** module (out of this lane's scope).

## Artifact contract (`visual_artifact.v1`)

On success (`ok`):

```jsonc
{
  "schema": "ariadne.visual_artifact.v1",
  "artifact_id": "vis-…",
  "kind": "pdf",
  "status": "ok",
  "source_ref": "…/input.dwg",            // READ-ONLY provenance (a copy was plotted)
  "route": "accoreconsole_plot",          // or full_autocad_com
  "media_type": "application/pdf",
  "refs": [
    { "ref": "…/runs/visual_report_…/out.pdf",
      "media_type": "application/pdf",
      "byte_size": 12345,
      "sha256": "…" }                      // real, hashed file on disk
  ],
  "run_dir": "…/runs/visual_report_…",
  "diagnostics": { "exit_code": 0, "warnings": [] }
}
```

On a failed/unproduced render (`not_implemented`):

```jsonc
{
  "schema": "ariadne.visual_artifact.v1",
  "artifact_id": "vis-…",
  "kind": "pdf",
  "status": "not_implemented",
  "source_ref": "…/input.dwg",
  "route": "accoreconsole_plot",
  "refs": [],                              // empty: no-fake-success
  "run_dir": "…/runs/visual_report_…",
  "diagnostics": {
    "exit_code": 0,
    "warnings": [
      "render attempt ran but produced no artifact: accoreconsole ran (exit=0) but produced no PDF file (headless -PLOT did not emit output on this host)",
      "full AutoCAD (acad.exe) is running: a real COM PlotToFile render is possible but GATED -- pass allow_full_autocad=True to drive the live session."
    ]
  },
  "evidence": {                            // captured proof of the real attempt
    "staged_dwg": "…/input.dwg",
    "scr": "…/plot.scr",
    "stdout": "…/accoreconsole_plot_stdout.txt",
    "stderr": "…/accoreconsole_plot_stderr.txt",
    "timed_out": false
  },
  "probe": { "render_layout_status": "blocked", "render_routes": { … } }
}
```

Note: when a raster `kind` (png/jpg) is requested and a *PDF* is what the plot
device emits, the `ok` envelope is returned with `kind` preserved and a warning
that the file is a PDF (rasterize downstream if a bitmap is required).

## Exact commands

```bash
# Fast, deterministic truth (no render spent): emits a sample pdf envelope.
python tools/visual_report.py
#   SELFTEST_OK | status=not_implemented refs=0 | render_layout=blocked |
#   accoreconsole=True full_autocad_com=True any_render_attemptable=True

# REAL render attempt against the golden staged copy (drives accoreconsole on a
# staged copy, captures evidence, verifies the output file):
python tools/visual_report.py --render
#   -> on this host: status=not_implemented (accoreconsole emits no file),
#      with evidence paths populated; original DWG byte-identical throughout.
```

## Not implemented / out of scope

- **Rasterization** of a produced PDF to PNG (would belong in
  `raster_compare_route` / a downstream step).
- **Diff overlays** (before/after visual compare) — depend on patch execution +
  a working render producer.
- **Native PlotEngine ARX** DWG→image rendering — would make
  `accoreconsole_plot` `verified: true`; not built in this lane.
