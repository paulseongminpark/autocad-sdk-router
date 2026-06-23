# AutoCAD Fallback Policy (M08O / Wave4X)

Status: enforced for fallback work in
`D:/dev/99_tools/autocad-sdk-router`.

## 1) Hard rule: no raw AutoCAD command surface

These operations remain **hard-blocked** and are never agent-exposed:

- `automate.com.send_command`
- `command.invoke.coroutine`
- `command.invoke.sync`
- `command.invoke.sync.resbuf`
- `command.menu.invoke`
- `command.queue.post`
- `module.command.lookup`

Rationale:

- they are raw command-string or command-macro dispatch (`SendCommand`,
  `acedCommand*`, `acedPostCommand*`, `acedMenuCmd`),
- they bypass the router operation allow-list,
- they create unbounded editor side effects.

Internal note:

- the router may still use a **router-authored fixed script** as a transport for an
  attended/full-AutoCAD workflow,
- but no API accepts arbitrary operator command text and no result ever exposes a
  reusable command surface.

## 2) Implemented safe COM metadata surface

The following operations are implemented as **bounded metadata** only:

- `automate.com.get_app`
- `automate.com.get_document`
- `automate.com.get_for_command`
- `automate.com.get_winapp`
- `automate.com.wrapper_for_object`

Rules:

- return structured metadata only,
- never return `IDispatch`, `IUnknown`, `AcadDocument`, or raw COM object handles,
- `automate.com.wrapper_for_object` requires `args.handle` and returns object
  metadata only,
- `automate.com.get_for_command` reports command-state variables (`CMDNAMES`,
  `CMDACTIVE`, etc.), not a command-context COM pointer.

Implementation lane:

- router lane: `fallback_safe_surface`
- dispatcher: `Invoke-SafeFallbackOperation`
- host: running full AutoCAD COM session (`GetActiveObject`) only

## 3) Implemented AutoLISP safe-script fallback

`module.load.lisp` is implemented as a **router-authored AutoLISP adapter load**.
It does **not** accept arbitrary script paths or arbitrary LISP text.

Current allow-listed adapter names:

- `safe_status`

Behavior:

- stages a DWG copy (or uses `test_native/blank.dwg` when no input was supplied),
- writes a fixed `.lsp` status adapter and a fixed `.scr` launcher,
- runs the launcher through `accoreconsole`,
- reads back a status file,
- returns the managed adapter map below.

This is the only accepted LISP fallback surface here.

## 4) Managed .NET adapter map

Allow-listed managed adapters are documented and surfaced by the safe fallback:

- `NETLOAD` → `Ariadne.DwgGeometryExtractor.dll` → `ARIADNE_CAD_JOB`
- `NETLOAD` → `Ariadne.DwgGeometryExtractor.dll` → `ARIADNE_DWG_GEOM_EXTRACT`
- `NETLOAD` → `Ariadne.DwgGeometryExtractor.dll` → `ARIADNE_DWG_DBX_EXTRACT`

The mapping is returned as metadata; no arbitrary managed command name is accepted.

## 5) OLE remains bounded / honest

Still blocked:

- `embed.ole.frame` → `HOST_UNAVAILABLE`
- `module.lifecycle.on_ole_unload` → `HOST_UNAVAILABLE`

Rationale:

- `embed.ole.frame` would require a live OLE client item + controlled attended OLE
  payload contract, which is not available here,
- `module.lifecycle.on_ole_unload` is a host lifecycle callback, not a safe routed
  operation.

## 6) Test hooks

Validated by:

- `tests/unit/test_m08o_fallback.py`
- `tests/unit/test_wave3_remaining_registry_closure.py`
- `tests/unit/test_wave4x_fallback_surface.py`
- `tools/operation_coverage_matrix.py`

## 7) References

- `tools/fallback_safe_surface.ps1`
- `tools/autocad-router.ps1`
- `docs/M08_REMAINING_BATCH_PLAN.md`
- `config/policy.v2.json`
- `config/operations.v2.json`
