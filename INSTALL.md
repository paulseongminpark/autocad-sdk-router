# CAD OS — Install & Use (team)

Let an AI agent (Claude / Codex / Pi / Hermes / Gemini) **drive the AutoCAD SDK
directly** — 457 native ObjectARX operations + inspect / patch / diff / validate /
query — through one MCP server (`cadagent`), safely (original DWGs stay read-only).

> **What this is:** a control plane *on top of* AutoCAD. You still run your own
> AutoCAD. This repo ships the router, the operation registry, the agent surface
> (`cadctl` + the `cadagent` MCP server), and the compiled native modules.

---

## 1. Prerequisites

- **AutoCAD** (Windows). The team standard is **AutoCAD 2027** — prebuilt native
  modules ship for it under `prebuilt/2027/`. Other versions: see *Other AutoCAD
  versions* below.
- **Python 3.10+** (3.12 recommended). The AutoCAD/DWG core is **pure stdlib**; the
  only dependency is `jsonschema` (installed by `install.ps1`).
- **git** (with access to this private repo).

Not required for AutoCAD control: Visual Studio, the ObjectARX SDK, the .NET SDK,
or any heavy Python package. (Those are only for building binaries yourself, or for
the optional non-AutoCAD geometry routes.)

## 2. Quickstart

```powershell
git clone https://github.com/paulseongminpark/autocad-sdk-router.git
cd autocad-sdk-router
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

`install.ps1` detects your AutoCAD, verifies the prebuilt modules, installs the core
dep, runs a status smoke, and **prints an MCP registration block**. Paste that block
into your agent (section 3), start a **new** agent session, and you're done.

Smoke it yourself any time:

```powershell
powershell tools\autocad-router.ps1 -Action status
python   tools\cadctl_cli.py run --op inspect.layers --dwg <your.dwg>
```

The original `<your.dwg>` is never modified — the router works on a staged copy.

## 3. Register the MCP server in your agent

Same server (`tools/cadagent_mcp.py --serve`), each agent's own config format. Use
the absolute paths `install.ps1` prints.

**Claude Code** — `.mcp.json` (project) or your user config:
```json
{
  "mcpServers": {
    "cadagent": {
      "command": "C:/path/to/python.exe",
      "args": ["C:/path/to/autocad-sdk-router/tools/cadagent_mcp.py", "--serve"],
      "env": { "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8" }
    }
  }
}
```

**Codex** — `~/.codex/config.toml`:
```toml
[mcp_servers.cadagent]
command = "C:/path/to/python.exe"
args = ["C:/path/to/autocad-sdk-router/tools/cadagent_mcp.py", "--serve"]
[mcp_servers.cadagent.env]
PYTHONUTF8 = "1"
PYTHONIOENCODING = "utf-8"
```

**Pi** — `~/.pi/agent/mcp.json` → `mcpServers.cadagent` (same command/args/env).

**Hermes** — `~/.hermes/config.yaml` → `mcp_servers.cadagent` (command/args/env),
and add `mcp-cadagent` under `platform_toolsets.cli`.

**Gemini (reviewer, READ-ONLY)** — `~/.gemini/settings.json` → `mcpServers.cadagent`
with an `includeTools` whitelist that **excludes the two write-capable tools**
(`cad.run_operation`, `cad.patch_apply_staged`):
```json
"includeTools": [
  "cad.status", "cad.registry_status", "cad.registry_explain",
  "cad.inspect_drawing", "cad.query_entities", "cad.get_entity",
  "cad.patch_dry_run", "cad.diff_before_after",
  "cad.validate_ir", "cad.visual_report", "cad.live_status"
]
```

After registering, start a new session and confirm the tools load (Claude:
`claude mcp list` → `cadagent` connected).

## 4. Use it

**Via the agent (natural language):** "extract this drawing's layers and blocks",
"draw the wall centerlines on a copy". The agent calls:
- read: `cad.inspect_drawing`, `cad.query_entities`, `cad.get_entity`
- execute (457 ops): `cad.run_operation(op_id, args, write_mode)` — `write_mode`
  must be in the op's `allowed_write_modes`; `write_original` is always refused.
- change: `cad.patch_dry_run` → `cad.patch_apply_staged` (staged copy only) →
  `cad.diff_before_after`
- status/verify: `cad.status`, `cad.registry_status`, `cad.validate_ir`,
  `cad.visual_report`, `cad.live_status`

**Via CLI (scripts/batch):**
```powershell
python tools\cadctl_cli.py run --op write.layer.create --dwg in.dwg --write-mode write_copy --args-json '{...}'
powershell tools\autocad-router.ps1 -Action run -Intent ifc -InputPath model.ifc
```

Discover operations: `powershell tools\autocad-router.ps1 -Action explain -Operation <id>`.

## 5. Optional: non-AutoCAD geometry routes

DXF / IFC / STEP / mesh / point-cloud / geo / PDF-SVG / raster routes need heavy
Python packages (not required for AutoCAD control):
```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Full
```

## 6. Other AutoCAD versions / upgrades

The code is **version-agnostic** — the router auto-detects your installed AutoCAD,
and `Resolve-NativeAcadBinDir` auto-loads `prebuilt/<version>/`. Only the **native
binaries** are version-coupled.

- If `prebuilt/<your-version>/` exists → it just works.
- If not, either ask the maintainer to add a build for your version, or build
  locally: `tools\build_native_acad.ps1` (needs Visual Studio + the matching
  ObjectARX SDK + .NET SDK). Then copy the canonical `.crx` + `.arx` + `.dbx` into
  `prebuilt/<version>/` and commit.

An AutoCAD upgrade does **not** require reworking CAD OS — at most a native rebuild
for a new ObjectARX ABI band. The registry, router, MCP surface, and Python layer
are unchanged.

## 7. Troubleshooting

- **`cadagent` not connected** — MCP loads at session start; start a **new**
  session. Check the `command` path points at your Python and `cadagent_mcp.py`.
- **`native_cad_job_failed` / engine not found** — `tools\autocad-router.ps1
  -Action status`; confirm AutoCAD is installed and `prebuilt/<version>/` has all
  three modules.
- **Want a fresh local native build to win over `prebuilt/`** — set
  `$env:ARIADNE_NATIVE_ACAD_BIN_DIR` to your build output dir.
- **Schema-validation warnings** — `pip install jsonschema` (or re-run
  `install.ps1`).
