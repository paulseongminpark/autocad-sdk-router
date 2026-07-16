#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dbx_import_audit.py -- P2c: PE import-table audit of the ObjectDBX module.

WHY: a .dbx module must stay loadable in a pure ObjectDBX host (RealDWG /
coreconsole db layer) -- which means its PE import table must not bind to the
AutoCAD editor/application host. This audit parses the import table (stdlib
only, no dumpbin dependency) and classifies every imported DLL:

  DB-LAYER (allowed): acdb*.dll, acge*.dll, ac1st*.dll, acutil*.dll,
      accore.dll (db+utility exports; the coreconsole host layer),
      axdb*.dll, acdbmgd-native deps, MSVC/UCRT/Windows system DLLs.
  HOST-BOUND (flagged): acad.exe, aced*.dll, acui*/adui* (UI), acapp*.dll,
      acgs*.dll (graphics system), acpl* (plot), actc* (tool palettes).

Exit 0 = no host-bound import; exit 1 = host-bound import found (listed).

Usage:
    python tools/dbx_import_audit.py [path\\to\\module.dbx]
"""
from __future__ import annotations

import os
import struct
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT = os.path.join(_REPO, "prebuilt", "2027", "Ariadne.AcadNativeDbx.dbx")

_HOST_BOUND_PREFIXES = ("acad", "aced", "acui", "adui", "acapp", "acgs", "acpl", "actc")
_DB_LAYER_PREFIXES = ("acdb", "acge", "ac1st", "acutil", "accore", "axdb",
                      "vcruntime", "msvcp", "api-ms-", "kernel32", "user32",
                      "advapi32", "ucrtbase", "ntdll", "shell32", "ole32",
                      "oleaut32", "rpcrt4", "ws2_32", "dbghelp", "bcrypt")


def _rva_to_off(rva: int, sections):
    for va, vsz, ptr, rsz in sections:
        if va <= rva < va + max(vsz, rsz):
            return rva - va + ptr
    return None


def imported_dlls(path: str):
    data = open(path, "rb").read()
    if data[:2] != b"MZ":
        raise ValueError("not a PE file")
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_off:pe_off + 4] != b"PE\0\0":
        raise ValueError("PE signature missing")
    nsec, = struct.unpack_from("<H", data, pe_off + 6)
    opt_size, = struct.unpack_from("<H", data, pe_off + 20)
    opt_off = pe_off + 24
    magic, = struct.unpack_from("<H", data, opt_off)
    if magic != 0x20B:
        raise ValueError("expected PE32+ (x64)")
    # data directory: PE32+ optional header -> directories start at +112
    imp_rva, imp_sz = struct.unpack_from("<II", data, opt_off + 112 + 8 * 1)
    sec_off = opt_off + opt_size
    sections = []
    for i in range(nsec):
        s = sec_off + 40 * i
        vsz, va, rsz, ptr = struct.unpack_from("<IIII", data, s + 8)
        sections.append((va, vsz, ptr, rsz))
    if not imp_rva:
        return []
    off = _rva_to_off(imp_rva, sections)
    dlls = []
    while off is not None:
        desc = data[off: off + 20]
        if len(desc) < 20 or desc == b"\0" * 20:
            break
        name_rva = struct.unpack_from("<I", desc, 12)[0]
        if not name_rva:
            break
        noff = _rva_to_off(name_rva, sections)
        if noff is None:
            break
        end = data.index(b"\0", noff)
        dlls.append(data[noff:end].decode("ascii", "replace"))
        off += 20
    return dlls


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else _DEFAULT
    print(f"[p2c] module: {path} ({os.path.getsize(path)} bytes)")
    dlls = imported_dlls(path)
    host_bound, db_layer, other = [], [], []
    for d in sorted(set(dlls), key=str.lower):
        dl = d.lower()
        if any(dl.startswith(p) for p in _HOST_BOUND_PREFIXES):
            host_bound.append(d)
        elif any(dl.startswith(p) for p in _DB_LAYER_PREFIXES):
            db_layer.append(d)
        else:
            other.append(d)
    print(f"[p2c] imports: {len(set(dlls))} distinct DLLs")
    print("  db-layer/system:", ", ".join(db_layer) or "(none)")
    if other:
        print("  UNCLASSIFIED (review):", ", ".join(other))
    if host_bound:
        print("  HOST-BOUND (VIOLATION):", ", ".join(host_bound))
        print("[p2c] FAIL: dbx module binds the AutoCAD host")
        return 1
    print("[p2c] PASS: no host-bound import -- module loadable by a pure DBX host"
          + ("" if not other else " (unclassified imports listed above for review)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
