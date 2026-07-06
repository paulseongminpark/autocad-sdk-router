#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from typing import Any

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows fallback
    winreg = None  # type: ignore[assignment]


SCHEMA = "ariadne.sheetset.read.v1"
DEFAULT_PROGID = "AcSmComponents.AcSmSheetSetMgr"
DEFAULT_VERSIONED_PROGID = "AcSmComponents.AcSmSheetSetMgr.26"
DEFAULT_AUTOCAD_DIR = r"C:\Program Files\Autodesk\AutoCAD 2027"
DEFAULT_SAMPLE_ROOTS = [
    os.path.join(DEFAULT_AUTOCAD_DIR, "Sample", "Sheet Sets"),
    os.path.join(DEFAULT_AUTOCAD_DIR, "UserDataCache", "ko-kr", "Template"),
]


def build_envelope(
    *,
    status: str,
    dst_path: str | None,
    summary: dict[str, Any],
    sheets: list[dict[str, Any]],
    subsets: list[dict[str, Any]],
    custom_properties: dict[str, Any],
    probe: dict[str, Any],
    blockers: list[str],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": status,
        "dst_path": dst_path,
        "summary": summary,
        "sheets": sheets,
        "subsets": subsets,
        "custom_properties": custom_properties,
        "probe": probe,
        "blockers": blockers,
    }


def load_win32com_state() -> dict[str, Any]:
    try:
        import win32com.client  # type: ignore
        import pythoncom  # type: ignore
        return {
            "available": True,
            "detail": "win32com.client + pythoncom importable",
            "win32com": win32com.client,
            "pythoncom": pythoncom,
        }
    except Exception as exc:
        return {
            "available": False,
            "detail": "%s: %s" % (type(exc).__name__, exc),
        }


def scan_registered_sheetset_progids() -> list[str]:
    if winreg is None:
        return []
    hits: list[str] = []
    try:
        index = 0
        while True:
            try:
                name = winreg.EnumKey(winreg.HKEY_CLASSES_ROOT, index)
            except OSError:
                break
            index += 1
            if name.startswith("AcSmComponents.AcSmSheetSetMgr"):
                hits.append(name)
    except Exception:
        return []
    return sorted(set(hits))


def find_autocad_dir() -> str | None:
    dll_path = os.path.join(DEFAULT_AUTOCAD_DIR, "AcSmComponents.dll")
    if os.path.isfile(dll_path):
        return DEFAULT_AUTOCAD_DIR
    return None


def find_sample_dst_files(root: str | None = None) -> list[str]:
    roots = [root] if root else list(DEFAULT_SAMPLE_ROOTS)
    hits: list[str] = []
    for base in roots:
        if not base or not os.path.isdir(base):
            continue
        for dirpath, _dirnames, filenames in os.walk(base):
            for filename in filenames:
                if filename.lower().endswith(".dst"):
                    hits.append(os.path.join(dirpath, filename))
    return sorted(hits)


def _resolve_dst_path(dst_path: str | None) -> str | None:
    if dst_path:
        return os.path.abspath(dst_path)
    samples = find_sample_dst_files()
    return samples[0] if samples else None


def probe_win32com_dispatch(progid: str) -> dict[str, Any]:
    state = load_win32com_state()
    if not state.get("available"):
        return {
            "ok": False,
            "progid": progid,
            "error": state.get("detail"),
        }
    try:
        obj = state["win32com"].Dispatch(progid)
        return {
            "ok": True,
            "progid": progid,
            "type": str(type(obj)),
        }
    except Exception as exc:
        return {
            "ok": False,
            "progid": progid,
            "error": "%s: %s" % (type(exc).__name__, exc),
        }


def _run_powershell(script: str) -> subprocess.CompletedProcess[str]:
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-EncodedCommand", encoded],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def probe_powershell_com_object(autocad_dir: str, progid: str) -> dict[str, Any]:
    script = f"""
$ErrorActionPreference = 'Stop'
$env:PATH = '{autocad_dir};' + $env:PATH
try {{
  $obj = New-Object -ComObject '{progid}'
  [pscustomobject]@{{
    status = 'ok'
    dotnet_type = $obj.GetType().FullName
  }} | ConvertTo-Json -Depth 5 -Compress
}} catch {{
  [pscustomobject]@{{
    status = 'blocked'
    error = $_.Exception.Message
    exception_type = $_.Exception.GetType().FullName
  }} | ConvertTo-Json -Depth 5 -Compress
}}
"""
    completed = _run_powershell(script)
    payload = _load_json_text(completed.stdout)
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "payload": payload,
    }


def attempt_powershell_read(dst_path: str, autocad_dir: str) -> dict[str, Any]:
    interop_path = os.path.join(autocad_dir, "AcSmComponents.Interop.dll")
    script = f"""
$ErrorActionPreference = 'Stop'
$env:PATH = '{autocad_dir};' + $env:PATH

function Get-CustomProperties([object]$bag) {{
  $props = [ordered]@{{}}
  if ($null -eq $bag) {{ return $props }}
  try {{
    $enum = $bag.GetPropertyEnumerator()
  }} catch {{
    return $props
  }}
  while ($true) {{
    $name = $null
    $value = $null
    try {{
      $enum.Next([ref]$name, [ref]$value)
    }} catch {{
      break
    }}
    if ([string]::IsNullOrWhiteSpace($name)) {{
      break
    }}
    try {{
      if ($null -eq $value) {{
        $props[$name] = $null
      }} else {{
        $props[$name] = $value.GetValue()
      }}
    }} catch {{
      $props[$name] = $null
    }}
  }}
  return $props
}}

function Read-Component([object]$component, [string]$parentPath) {{
  $typeName = $component.GetTypeName()
  $name = $null
  $desc = $null
  try {{ $name = $component.GetName() }} catch {{}}
  try {{ $desc = $component.GetDesc() }} catch {{}}
  $path = if ($parentPath -and $name) {{ \"$parentPath/$name\" }} elseif ($name) {{ $name }} else {{ $parentPath }}
  $customProps = $null
  try {{ $customProps = Get-CustomProperties ($component.GetCustomPropertyBag()) }} catch {{ $customProps = [ordered]@{{}} }}
  $entry = [ordered]@{{
    type_name = $typeName
    name = $name
    desc = $desc
    path = $path
    custom_properties = $customProps
    children = @()
  }}
  if ($typeName -eq 'AcSmSheet') {{
    $layout = $null
    try {{ $layout = $component.GetLayout() }} catch {{}}
    $entry.sheet = [ordered]@{{
      number = (try {{ $component.GetNumber() }} catch {{ $null }})
      title = (try {{ $component.GetTitle() }} catch {{ $null }})
      layout_name = (try {{ if ($layout) {{ $layout.GetName() }} }} catch {{ $null }})
      layout_file = (try {{ if ($layout) {{ $layout.GetFileName() }} }} catch {{ $null }})
      layout_resolved_file = (try {{ if ($layout) {{ $layout.ResolveFileName() }} }} catch {{ $null }})
      layout_handle = (try {{ if ($layout) {{ $layout.GetAcDbHandle() }} }} catch {{ $null }})
      owner_handle = (try {{ if ($layout) {{ $layout.GetOwnerAcDbHandle() }} }} catch {{ $null }})
    }}
  }}
  $owned = $null
  try {{ $component.GetDirectlyOwnedObjects([ref]$owned) }} catch {{}}
  if ($owned) {{
    foreach ($child in $owned) {{
      if ($null -ne $child) {{
        $entry.children += Read-Component $child $path
      }}
    }}
  }}
  return [pscustomobject]$entry
}}

try {{
  Add-Type -Path '{interop_path}'
  $mgr = New-Object Autodesk.AutoCAD.Interop.AcSmSheetSetMgrClass
  $db = $mgr.OpenDatabase('{dst_path}', $false)
  try {{
    $ss = $db.GetSheetSet()
    $root = Read-Component $ss ''
    [pscustomobject]@{{
      status = 'ok'
      sheet_set = $root
      db_version = (try {{ $db.GetDbVersion() }} catch {{ $null }})
      db_name = (try {{ $db.GetName() }} catch {{ $null }})
      db_desc = (try {{ $db.GetDesc() }} catch {{ $null }})
    }} | ConvertTo-Json -Depth 20 -Compress
  }} finally {{
    try {{ $mgr.Close($db) }} catch {{}}
    try {{ $mgr.CloseAll() }} catch {{}}
  }}
}} catch {{
  [pscustomobject]@{{
    status = 'blocked'
    error = $_.Exception.Message
    exception_type = $_.Exception.GetType().FullName
  }} | ConvertTo-Json -Depth 10 -Compress
}}
"""
    completed = _run_powershell(script)
    payload = _load_json_text(completed.stdout)
    if payload is None:
        return {
            "status": "blocked",
            "error": "PowerShell reader returned non-JSON output",
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    payload["stdout"] = completed.stdout
    payload["stderr"] = completed.stderr
    payload["returncode"] = completed.returncode
    return payload


def _load_json_text(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _flatten_components(component: dict[str, Any], *, sheets: list[dict[str, Any]], subsets: list[dict[str, Any]]) -> None:
    type_name = component.get("type_name")
    if type_name == "AcSmSheet":
        sheet_payload = dict(component.get("sheet") or {})
        sheet_payload["name"] = component.get("name")
        sheet_payload["desc"] = component.get("desc")
        sheet_payload["path"] = component.get("path")
        sheet_payload["custom_properties"] = component.get("custom_properties") or {}
        sheets.append(sheet_payload)
    elif type_name == "AcSmSubset":
        subsets.append(
            {
                "name": component.get("name"),
                "desc": component.get("desc"),
                "path": component.get("path"),
                "custom_properties": component.get("custom_properties") or {},
            }
        )
    for child in component.get("children") or []:
        _flatten_components(child, sheets=sheets, subsets=subsets)


def _summarize_read_payload(dst_path: str, backend: dict[str, Any], probe: dict[str, Any]) -> dict[str, Any]:
    root = backend.get("sheet_set") or {}
    sheets: list[dict[str, Any]] = []
    subsets: list[dict[str, Any]] = []
    for child in root.get("children") or []:
        _flatten_components(child, sheets=sheets, subsets=subsets)
    summary = {
        "name": root.get("name"),
        "desc": root.get("desc"),
        "db_name": backend.get("db_name"),
        "db_desc": backend.get("db_desc"),
        "db_version": backend.get("db_version"),
        "sheet_count": len(sheets),
        "subset_count": len(subsets),
    }
    return build_envelope(
        status="ok",
        dst_path=dst_path,
        summary=summary,
        sheets=sheets,
        subsets=subsets,
        custom_properties=root.get("custom_properties") or {},
        probe=probe,
        blockers=[],
    )


def read_sheetset(dst_path: str | None = None) -> dict[str, Any]:
    resolved_dst = _resolve_dst_path(dst_path)
    autocad_dir = find_autocad_dir()
    win32_state = load_win32com_state()
    progids = scan_registered_sheetset_progids()
    dispatch_probes = [probe_win32com_dispatch(DEFAULT_PROGID)]
    if DEFAULT_VERSIONED_PROGID not in progids:
        progids = sorted(set(progids + [DEFAULT_VERSIONED_PROGID]))
    dispatch_probes.extend(probe_win32com_dispatch(progid) for progid in progids)

    probe: dict[str, Any] = {
        "imports": {
            "win32com": {
                "available": bool(win32_state.get("available")),
                "detail": win32_state.get("detail"),
            },
            "comtypes": {
                "available": False,
                "detail": "Module not probed here; the local wave measurement found it absent.",
            },
        },
        "registry": {
            "progids": progids,
        },
        "dispatch": dispatch_probes,
        "autocad_dir": autocad_dir,
    }

    blockers: list[str] = []
    if not resolved_dst:
        blockers.append("No .dst path was provided and no sample sheet set was found under the AutoCAD 2027 install.")
        return build_envelope(
            status="unavailable",
            dst_path=None,
            summary={},
            sheets=[],
            subsets=[],
            custom_properties={},
            probe=probe,
            blockers=blockers,
        )
    if not autocad_dir:
        blockers.append("AutoCAD 2027 install directory with AcSmComponents.dll was not found at the expected path.")
        return build_envelope(
            status="unavailable",
            dst_path=resolved_dst,
            summary={},
            sheets=[],
            subsets=[],
            custom_properties={},
            probe=probe,
            blockers=blockers,
        )
    if not progids:
        blockers.append("No AcSmComponents.AcSmSheetSetMgr ProgID was registered in HKCR.")
        return build_envelope(
            status="unavailable",
            dst_path=resolved_dst,
            summary={},
            sheets=[],
            subsets=[],
            custom_properties={},
            probe=probe,
            blockers=blockers,
        )

    com_object_probe = probe_powershell_com_object(autocad_dir, DEFAULT_VERSIONED_PROGID)
    probe["powershell_com_object"] = com_object_probe
    backend = attempt_powershell_read(resolved_dst, autocad_dir)
    probe["powershell_read"] = {
        "status": backend.get("status"),
        "error": backend.get("error"),
        "exception_type": backend.get("exception_type"),
        "returncode": backend.get("returncode"),
    }
    if backend.get("status") == "ok":
        return _summarize_read_payload(resolved_dst, backend, probe)

    backend_error = backend.get("error") or "Unknown PowerShell/interop failure."
    blockers.append(
        "Autodesk sheet-set read backend is blocked on this machine: %s" % backend_error
    )
    if isinstance(com_object_probe.get("payload"), dict):
        payload = com_object_probe["payload"]
        if payload.get("status") == "ok":
            blockers.append(
                "Standalone COM activation succeeded after prepending the AutoCAD 2027 install directory to PATH, but the typed interop read path did not."
            )
    return build_envelope(
        status="blocked",
        dst_path=resolved_dst,
        summary={},
        sheets=[],
        subsets=[],
        custom_properties={},
        probe=probe,
        blockers=blockers,
    )


def live_probe_available() -> bool:
    return bool(find_autocad_dir() and scan_registered_sheetset_progids() and find_sample_dst_files())


def live_probe_skip_reason() -> str:
    if not find_autocad_dir():
        return "AutoCAD 2027 install directory not found"
    if not scan_registered_sheetset_progids():
        return "AcSm sheet set manager ProgID not registered"
    if not find_sample_dst_files():
        return "No sample .dst files found"
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe or read AutoCAD Sheet Set (.dst) data.")
    parser.add_argument("--dst", help="Path to the target .dst file. Defaults to the first installed sample.")
    parser.add_argument("--json-out", help="Optional path to write the JSON envelope.")
    args = parser.parse_args(argv)

    result = read_sheetset(args.dst)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.write("\n")
    sys.stdout.write(text)
    sys.stdout.write("\n")
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
