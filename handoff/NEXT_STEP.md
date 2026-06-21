# NEXT_STEP — after CADOS_M02 (PARTIAL_PASS)

CADOS_M02 closed **PARTIAL_PASS** (12/15 full PASS). The CAD OS Layer now has a
**live, validated read + write stack**: native rich `inspect.database.graph` →
`native_full` IR (21747 truth) routable via `cadctl inspect --include-rich`; a
real staged-copy patch lifecycle (create_line → +1 LINE → cad_diff → 14/14
validator gates → journal, original byte-unchanged); Operation Registry v2 (43
ops, 34 implemented, consistent); 215 tests green. Honest partials: non-ASCII
(upstream accoreconsole), visual render (NOT_IMPLEMENTED on this host), live ARX
pump runtime (attended-injection blocked).

## Decision

**Recommended: `D04_IMPORT_CAD_OS_CAPABILITIES`** — return to Daedalus and consume
the CAD OS v1 read+patch+registry surface via `cadctl`. The read/write stack is
ready; visual + live-pump are non-critical for D04 (read + staged-patch + validate
is the capability Daedalus needs). Handoff for D04 is in
`D:\dev\_ariadne\_daedalus\external\cad_os\` (CADOS_M02_SUMMARY.md,
cad_os_latest_status.json, CAD_OS_V1_CAPABILITIES.json, CAD_OS_ADAPTER_IMPORT_NOTES.md,
CADOS_NEXT_RECOMMENDATION.md).

**Alternative: `CADOS_M03_NATIVE_IR_COMPLETION`** — stay in CAD OS and close the
3 partials + deepen rich IR:
- non-ASCII symbol-table names: cross-source from the DXF/ezdxf route (which
  preserves cp949) or configure the accoreconsole code page at DWG load.
- rich-IR depth: native per-entity xdata, extension dictionaries, 2D/3D-polyline
  + hatch vertex geometry.
- visual: full_autocad COM plot (acad.exe running, allow_full_autocad) OR a native
  PlotEngine ARX export module → real before/after/overlay artifacts.
- live ARX pump: build canonical `.arx` lock-free, implement CADAGENT_START/STOP/
  STATUS/PUMP named-pipe server (length-prefixed JSON, AcDb on document context),
  verify live.status/echo/list_documents in an attended session.

## First commands for either

```
python -m pytest tests -q                              # 215 pass / 2 skip
python tools/cadctl_cli.py inspect --dwg staging/dwg_20260617_191504/input.dwg --out runs/check --include-rich
python tools/cadctl_cli.py registry coverage           # 34 implemented, consistent
```
