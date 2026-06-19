#!/usr/bin/env python
"""
probe_routes.py -- Live availability probe for the AutoCAD SDK router (12-route spec).

Ground truth, not a guess. For each route it checks whether the REQUIRED tools
really resolve, then emits per-route availability.

IMPORTANT (robustness): the heavy native CAD/geometry extensions on this machine
(OCCT/OCP, open3d, GDAL, PyMuPDF, opencv) can race during *interpreter shutdown*
when many are loaded in ONE process, producing a 0xC0000005 access violation at
exit -- AFTER all real work is done. To make the probe deterministic and immune
to that teardown race, each module import is checked in an ISOLATED short-lived
subprocess. A crash/segfault in one module's subprocess is reported as that
module being unavailable; it cannot poison the others or the overall exit code.

Output is written to a file (with flush + fsync) AND printed to stdout, so the
result survives even if some child crashes.

Usage:
    python probe_routes.py [--out <path>] [--route <id>]

No side effects on CAD files. Read-only.
"""
import argparse
import importlib.metadata as M
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

PYEXE = sys.executable

# One-liner that tries to import a module in a clean child and exits 0/1.
_IMPORT_PROBE = (
    "import importlib,sys\n"
    "try:\n"
    "    importlib.import_module(sys.argv[1])\n"
    "    sys.exit(0)\n"
    "except Exception:\n"
    "    sys.exit(1)\n"
)


def _dist_version(dist_name):
    try:
        return M.version(dist_name)
    except Exception:
        return None


def _import_ok_isolated(import_name):
    """Import the module in a fresh subprocess. Returns (ok, signal_note)."""
    try:
        p = subprocess.run(
            [PYEXE, "-c", _IMPORT_PROBE, import_name],
            capture_output=True, timeout=90,
        )
    except subprocess.TimeoutExpired:
        return False, "timeout"
    if p.returncode == 0:
        return True, None
    # Negative / large return codes on Windows == crashed child (e.g. segfault).
    if p.returncode not in (0, 1):
        return False, f"child_exit_{p.returncode}"
    return False, "import_error"


def _mod_record(import_name, dist_name):
    ok, note = _import_ok_isolated(import_name)
    return {
        "import": import_name,
        "dist": dist_name,
        "importable": ok,
        "version": _dist_version(dist_name),
        "note": note,
        "kind": "module",
    }


def _extra_cli_dirs(candidates):
    names = {os.path.basename(c).lower() for c in candidates}
    dirs = []
    if names.intersection({"dwgread.exe", "dwgread", "dwg2dxf.exe", "dwg2dxf"}):
        dirs.extend([
            os.environ.get("ARIADNE_LIBREDWG_BIN_DIR"),
            r"D:\dev\99_tools\libredwg\bin",
            r"C:\msys64\mingw64\bin",
            r"C:\msys64\ucrt64\bin",
        ])
    return [d for d in dirs if d]


def _iter_cli_candidates(candidates):
    for d in _extra_cli_dirs(candidates):
        for c in candidates:
            if not os.path.isabs(c):
                yield os.path.join(d, c)
    yield from candidates


def _cli(candidates):
    for c in _iter_cli_candidates(candidates):
        if os.path.isabs(c):
            if os.path.exists(c):
                return c
        else:
            found = shutil.which(c)
            if found:
                return found
    return None


ACCORECONSOLE_CANDIDATES = [
    r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe",
    "accoreconsole.exe", "accoreconsole",
]
FREECAD_CANDIDATES = [
    r"C:\Users\PAUL\AppData\Local\Programs\FreeCAD 1.1\bin\freecadcmd.exe",
    "freecadcmd.exe", "freecadcmd",
]
LIBREDWG_CANDIDATES = ["dwgread.exe", "dwgread", "dwg2dxf.exe", "dwg2dxf"]


def probe():
    routes = {}
    # Cache module records so we don't spawn the same import twice.
    cache = {}

    def mod(import_name, dist_name):
        key = (import_name, dist_name)
        if key not in cache:
            cache[key] = _mod_record(import_name, dist_name)
        return cache[key]

    def add(rid, required_mods=(), required_cli=None, optional_mods=(),
            optional_cli=None):
        req = []
        ok_all = True
        for imp, dist in required_mods:
            r = mod(imp, dist)
            req.append(r)
            if not r["importable"]:
                ok_all = False
        if required_cli is not None:
            label, cands = required_cli
            path = _cli(cands)
            req.append({"name": label, "path": path, "present": bool(path),
                        "kind": "cli"})
            if not path:
                ok_all = False
        opt = []
        for imp, dist in optional_mods:
            opt.append(mod(imp, dist))
        if optional_cli is not None:
            label, cands = optional_cli
            path = _cli(cands)
            opt.append({"name": label, "path": path, "present": bool(path),
                        "kind": "cli"})
        routes[rid] = {"route": rid, "available": ok_all,
                       "required": req, "optional": opt}

    # 1. dwg_truth_autocad
    add("dwg_truth_autocad",
        required_cli=("accoreconsole", ACCORECONSOLE_CANDIDATES))
    # 2. dxf_fast_secondary
    add("dxf_fast_secondary",
        required_mods=[("ezdxf", "ezdxf"), ("shapely", "shapely")])
    # 3. ifc_bim_semantic
    add("ifc_bim_semantic", required_mods=[("ifcopenshell", "ifcopenshell")])
    # 4. solid_brep_occ
    add("solid_brep_occ",
        required_mods=[("OCP", "cadquery-ocp"), ("cadquery", "cadquery")],
        optional_mods=[("OCC", "pythonocc-core")],
        optional_cli=("freecadcmd", FREECAD_CANDIDATES))
    # 5. parametric_rebuild
    add("parametric_rebuild",
        required_mods=[("cadquery", "cadquery"), ("OCP", "cadquery-ocp")],
        optional_cli=("freecadcmd", FREECAD_CANDIDATES))
    # 6. dwg_libredwg_sidecar
    add("dwg_libredwg_sidecar",
        required_cli=("libredwg(dwgread/dwg2dxf)", LIBREDWG_CANDIDATES))
    # 7. mesh_analysis
    add("mesh_analysis",
        required_mods=[("trimesh", "trimesh"), ("meshio", "meshio")],
        optional_mods=[("open3d", "open3d")])
    # 8. pointcloud_route
    add("pointcloud_route",
        required_mods=[("open3d", "open3d"), ("laspy", "laspy")],
        optional_mods=[("pdal", "pdal")])
    # 9. geo_vector_route (native osgeo OR pyogrio gates availability)
    osgeo = mod("osgeo", "gdal")
    if osgeo["importable"]:
        add("geo_vector_route",
            required_mods=[("osgeo", "gdal"), ("pyproj", "pyproj")],
            optional_mods=[("pyogrio", "pyogrio")])
    else:
        add("geo_vector_route",
            required_mods=[("pyogrio", "pyogrio"), ("pyproj", "pyproj")],
            optional_mods=[("osgeo", "gdal")])
    # 10. pdf_svg_vector_route
    add("pdf_svg_vector_route",
        required_mods=[("svgpathtools", "svgpathtools"),
                       ("svgelements", "svgelements")],
        optional_mods=[("fitz", "pymupdf")])
    # 11. raster_compare_route
    add("raster_compare_route",
        required_mods=[("cv2", "opencv-python-headless"),
                       ("skimage", "scikit-image")])
    return routes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", default=None)
    ap.add_argument("--out", default=None, help="write probe JSON to this path")
    args = ap.parse_args()

    routes = probe()
    if args.route:
        rec = routes.get(args.route)
        if rec is None:
            print(json.dumps({"error": "unknown_route", "route": args.route}))
            sys.exit(2)
        payload = rec
    else:
        payload = {
            "schema": "ariadne.autocad_router_route_probe.v1",
            "probed_at": datetime.now(timezone.utc).isoformat(),
            "python_exe": PYEXE,
            "route_count": len(routes),
            "available_count": sum(1 for r in routes.values() if r["available"]),
            "routes": routes,
        }

    text = json.dumps(payload, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
    sys.stdout.write(text)
    sys.stdout.flush()


if __name__ == "__main__":
    main()
