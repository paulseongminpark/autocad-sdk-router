#!/usr/bin/env python
"""
run_route.py -- Execute a single non-AutoCAD route against an input file.

This is the real per-route work engine. Each route does a genuine read/analyze
operation with its mandated library and emits a structured JSON result.

The AutoCAD-native route (`dwg_truth_autocad`) is NOT handled here -- it is
dispatched by the PowerShell router directly to accoreconsole with ASCII
staging, because it needs a script (.scr) and a host process, not a Python lib.

Contract:
  - Input files are treated READ-ONLY. Nothing here writes back to the input.
  - `parametric_rebuild` is the only generative route; it writes a NEW artifact
    under an explicit --out path (never near the input).
  - On a missing required tool, exits 3 with status=unavailable (no fake pass).
  - On a route that needs an input but none given, exits 4.

Usage:
  python run_route.py --route dxf_fast_secondary --input model.dxf
  python run_route.py --route parametric_rebuild --out box.step
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone


def emit(payload, code=0):
    print(json.dumps(payload, indent=1, default=str))
    sys.exit(code)


def need_input(path, route):
    if not path:
        emit({"route": route, "status": "error",
              "error": "input_required",
              "detail": f"{route} requires --input <file>"}, 4)
    if not os.path.exists(path):
        emit({"route": route, "status": "error",
              "error": "input_not_found", "detail": path}, 4)


def unavailable(route, tool, err):
    emit({"route": route, "status": "unavailable",
          "missing_tool": tool, "import_error": err}, 3)


def _router_runs_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "runs"))


def _libredwg_search_dirs(libredwg_bin=None):
    dirs = []
    if libredwg_bin:
        dirs.append(libredwg_bin)
    dirs.extend([
        os.environ.get("ARIADNE_LIBREDWG_BIN_DIR"),
        r"D:\dev\99_tools\libredwg\bin",
        r"C:\msys64\mingw64\bin",
        r"C:\msys64\ucrt64\bin",
    ])
    return [d for d in dirs if d]


def _find_cli(names, search_dirs):
    for d in search_dirs:
        for name in names:
            candidate = os.path.join(d, name)
            if os.path.exists(candidate):
                return candidate
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def resolve_libredwg_tools(libredwg_bin=None):
    search_dirs = _libredwg_search_dirs(libredwg_bin)
    return {
        "dwgread": _find_cli(["dwgread.exe", "dwgread"], search_dirs),
        "dwg2dxf": _find_cli(["dwg2dxf.exe", "dwg2dxf"], search_dirs),
        "search_dirs": search_dirs,
    }


def _summarize_process(name, cmd, proc):
    return {
        "name": name,
        "command": cmd,
        "exit_code": proc.returncode,
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-20:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-20:]),
    }


def _run_libredwg_command(name, cmd, runner):
    proc = runner(cmd, capture_output=True, text=True, timeout=120,
                  check=False)
    return _summarize_process(name, cmd, proc)


def run_libredwg_sidecar(input_path, run_root=None, libredwg_bin=None,
                         runner=subprocess.run, stamp=None):
    route = "dwg_libredwg_sidecar"
    if not input_path:
        return {"route": route, "status": "error",
                "error": "input_required",
                "detail": f"{route} requires --input <file>"}
    if not os.path.exists(input_path):
        return {"route": route, "status": "error",
                "error": "input_not_found", "detail": input_path}

    tools = resolve_libredwg_tools(libredwg_bin)
    if not tools["dwgread"]:
        return {"route": route, "status": "unavailable",
                "missing_tool": "dwgread",
                "detail": "LibreDWG dwgread CLI not found in sidecar bin, "
                          "ARIADNE_LIBREDWG_BIN_DIR, known MSYS2 paths, or PATH.",
                "searched": tools["search_dirs"]}

    if stamp is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_root = run_root or _router_runs_dir()
    run_dir = os.path.join(run_root, f"{route}_{stamp}")
    os.makedirs(run_dir, exist_ok=True)

    json_out = os.path.join(run_dir, "libredwg_extract.json")
    dxf_out = os.path.join(run_dir, "libredwg_export.dxf")
    commands = []
    commands.append(_run_libredwg_command(
        "dwgread_json",
        [tools["dwgread"], "-O", "JSON", "-o", json_out, input_path],
        runner))
    if commands[-1]["exit_code"] != 0:
        return {"route": route, "status": "error",
                "error": "libredwg_json_failed",
                "input": input_path, "run_dir": run_dir,
                "sidecar_process": True,
                "tool_paths": {k: v for k, v in tools.items() if k != "search_dirs"},
                "commands": commands}

    commands.append(_run_libredwg_command(
        "dwgread_dxf",
        [tools["dwgread"], "-O", "DXF", "-o", dxf_out, input_path],
        runner))
    if commands[-1]["exit_code"] != 0:
        return {"route": route, "status": "error",
                "error": "libredwg_dxf_failed",
                "input": input_path, "run_dir": run_dir,
                "sidecar_process": True,
                "tool_paths": {k: v for k, v in tools.items() if k != "search_dirs"},
                "commands": commands,
                "json_output": json_out,
                "json_exists": os.path.exists(json_out)}

    return {"route": route, "status": "ok",
            "input": input_path,
            "run_dir": run_dir,
            "sidecar_process": True,
            "license_boundary": "GPL LibreDWG invoked as a separate CLI process; no import/link.",
            "tool_paths": {k: v for k, v in tools.items() if k != "search_dirs"},
            "commands": commands,
            "json_output": json_out,
            "json_exists": os.path.exists(json_out),
            "dxf_output": dxf_out,
            "dxf_exists": os.path.exists(dxf_out)}


# --- per-route implementations -------------------------------------------------

def r_dxf_fast_secondary(args):
    route = "dxf_fast_secondary"
    need_input(args.input, route)
    try:
        import ezdxf
        import logging
        from shapely.geometry import LineString, Point  # noqa: F401
    except Exception as e:
        unavailable(route, "ezdxf/shapely", type(e).__name__)
    logging.getLogger("ezdxf").setLevel(logging.ERROR)
    doc = ezdxf.readfile(args.input)
    msp = doc.modelspace()
    by_type = {}
    total_len = 0.0
    for e in msp:
        t = e.dxftype()
        by_type[t] = by_type.get(t, 0) + 1
        if t == "LINE":
            s, en = e.dxf.start, e.dxf.end
            total_len += LineString([(s.x, s.y), (en.x, en.y)]).length
    layers = sorted({e.dxf.layer for e in msp if e.dxf.hasattr("layer")})
    virtual_by_type = {}
    virtual_layers = {}
    virtual_errors = 0

    def virtual_leaf_entities(entity, depth=0):
        nonlocal virtual_errors
        if depth > 24:
            virtual_errors += 1
            return
        if entity.dxftype() == "INSERT":
            try:
                for child in entity.virtual_entities():
                    yield from virtual_leaf_entities(child, depth + 1)
            except Exception:
                virtual_errors += 1
        else:
            yield entity

    for entity in msp:
        for leaf in virtual_leaf_entities(entity):
            t = leaf.dxftype()
            virtual_by_type[t] = virtual_by_type.get(t, 0) + 1
            layer = leaf.dxf.layer if leaf.dxf.hasattr("layer") else ""
            virtual_layers[layer] = virtual_layers.get(layer, 0) + 1
    emit({"route": route, "status": "ok", "input": args.input,
          "dxf_version": doc.dxfversion,
          "entity_count": sum(by_type.values()),
          "entities_by_type": by_type,
          "line_total_length": round(total_len, 6),
          "layer_count": len(layers), "layers": layers[:50],
          "virtual_entity_count": sum(virtual_by_type.values()),
          "virtual_entities_by_type": virtual_by_type,
          "virtual_layer_count": len(virtual_layers),
          "virtual_layers": dict(sorted(virtual_layers.items())[:100]),
          "virtual_errors": virtual_errors})


def r_ifc_bim_semantic(args):
    route = "ifc_bim_semantic"
    need_input(args.input, route)
    try:
        import ifcopenshell
    except Exception as e:
        unavailable(route, "ifcopenshell", type(e).__name__)
    f = ifcopenshell.open(args.input)
    counts = {}
    for cls in ("IfcWall", "IfcSlab", "IfcSpace", "IfcBuildingStorey",
                "IfcDoor", "IfcWindow", "IfcColumn", "IfcBeam"):
        try:
            counts[cls] = len(f.by_type(cls))
        except Exception:
            counts[cls] = 0
    emit({"route": route, "status": "ok", "input": args.input,
          "schema": f.schema, "total_entities": len(f.by_type("IfcRoot")),
          "element_counts": counts})


def r_solid_brep_occ(args):
    route = "solid_brep_occ"
    need_input(args.input, route)
    try:
        import cadquery as cq
    except Exception as e:
        unavailable(route, "cadquery/OCP", type(e).__name__)
    ext = os.path.splitext(args.input)[1].lower()
    if ext in (".step", ".stp"):
        shp = cq.importers.importStep(args.input)
    elif ext in (".brep",):
        from OCP.BRepTools import BRepTools
        from OCP.BRep import BRep_Builder
        from OCP.TopoDS import TopoDS_Shape
        s = TopoDS_Shape()
        BRepTools.Read_s(s, args.input, BRep_Builder())
        shp = cq.Workplane().add(cq.Shape(s))
    else:
        emit({"route": route, "status": "error", "error": "unsupported_ext",
              "detail": f"{ext}; supported: .step/.stp/.brep"}, 5)
    solids = shp.solids().vals()
    faces = shp.faces().vals()
    edges = shp.edges().vals()
    vol = sum(s.Volume() for s in solids) if solids else 0.0
    bb = shp.val().BoundingBox()
    emit({"route": route, "status": "ok", "input": args.input,
          "solid_count": len(solids), "face_count": len(faces),
          "edge_count": len(edges), "total_volume": round(vol, 6),
          "bbox": {"xlen": round(bb.xlen, 4), "ylen": round(bb.ylen, 4),
                   "zlen": round(bb.zlen, 4)}})


def r_parametric_rebuild(args):
    route = "parametric_rebuild"
    if not args.out:
        emit({"route": route, "status": "error", "error": "out_required",
              "detail": "parametric_rebuild needs --out <file.step|.stl|.svg>"}, 4)
    try:
        import cadquery as cq
    except Exception as e:
        unavailable(route, "cadquery/OCP", type(e).__name__)
    # Demonstrator parametric solid (real geometry generation, not a stub).
    L = args.p_len if args.p_len else 20.0
    W = args.p_wid if args.p_wid else 10.0
    H = args.p_hgt if args.p_hgt else 5.0
    model = cq.Workplane("XY").box(L, W, H).edges("|Z").fillet(1.0)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    ext = os.path.splitext(args.out)[1].lower()
    if ext in (".step", ".stp"):
        cq.exporters.export(model, args.out)
        fmt = "STEP"
    elif ext == ".stl":
        cq.exporters.export(model, args.out)
        fmt = "STL"
    elif ext == ".svg":
        cq.exporters.export(model, args.out)
        fmt = "SVG"
    else:
        emit({"route": route, "status": "error", "error": "unsupported_out_ext",
              "detail": f"{ext}; supported: .step/.stp/.stl/.svg"}, 5)
    vol = model.val().Volume()
    emit({"route": route, "status": "ok", "out": args.out, "format": fmt,
          "params": {"len": L, "wid": W, "hgt": H, "fillet": 1.0},
          "generated_volume": round(vol, 6),
          "out_bytes": os.path.getsize(args.out)})


def r_mesh_analysis(args):
    route = "mesh_analysis"
    need_input(args.input, route)
    try:
        import trimesh
    except Exception as e:
        unavailable(route, "trimesh", type(e).__name__)
    m = trimesh.load(args.input, force="mesh")
    emit({"route": route, "status": "ok", "input": args.input,
          "vertices": int(len(m.vertices)), "faces": int(len(m.faces)),
          "is_watertight": bool(m.is_watertight),
          "volume": round(float(m.volume), 6) if m.is_watertight else None,
          "area": round(float(m.area), 6),
          "bounds": m.bounds.tolist(), "euler_number": int(m.euler_number)})


def r_pointcloud_route(args):
    route = "pointcloud_route"
    need_input(args.input, route)
    ext = os.path.splitext(args.input)[1].lower()
    if ext in (".las", ".laz"):
        try:
            import laspy
        except Exception as e:
            unavailable(route, "laspy", type(e).__name__)
        las = laspy.read(args.input)
        emit({"route": route, "status": "ok", "input": args.input,
              "reader": "laspy", "point_count": int(las.header.point_count),
              "point_format": int(las.header.point_format.id),
              "scales": list(las.header.scales),
              "mins": list(las.header.mins), "maxs": list(las.header.maxs)})
    else:
        try:
            import open3d as o3d
        except Exception as e:
            unavailable(route, "open3d", type(e).__name__)
        pcd = o3d.io.read_point_cloud(args.input)
        n = len(pcd.points)
        bb = pcd.get_axis_aligned_bounding_box()
        emit({"route": route, "status": "ok", "input": args.input,
              "reader": "open3d", "point_count": int(n),
              "bbox_min": list(bb.min_bound), "bbox_max": list(bb.max_bound)})


def r_geo_vector_route(args):
    route = "geo_vector_route"
    need_input(args.input, route)
    try:
        import pyproj  # noqa: F401
    except Exception as e:
        unavailable(route, "pyproj", type(e).__name__)
    info = {}
    try:
        from osgeo import ogr
        ds = ogr.Open(args.input)
        lyr = ds.GetLayer(0)
        info["reader"] = "osgeo.ogr"
        info["feature_count"] = lyr.GetFeatureCount()
        srs = lyr.GetSpatialRef()
        info["crs"] = srs.ExportToWkt()[:120] if srs else None
    except Exception:
        try:
            import pyogrio
        except Exception as e:
            unavailable(route, "gdal/pyogrio", type(e).__name__)
        meta = pyogrio.read_info(args.input)
        info["reader"] = "pyogrio"
        info["feature_count"] = int(meta.get("features", -1))
        info["fields"] = list(meta.get("fields", []))[:30]
        info["crs"] = str(meta.get("crs"))
        info["geometry_type"] = str(meta.get("geometry_type"))
    emit({"route": route, "status": "ok", "input": args.input, **info})


def r_pdf_svg_vector_route(args):
    route = "pdf_svg_vector_route"
    need_input(args.input, route)
    ext = os.path.splitext(args.input)[1].lower()
    if ext == ".svg":
        try:
            from svgpathtools import svg2paths2
        except Exception as e:
            unavailable(route, "svgpathtools", type(e).__name__)
        paths, attrs, svg_attr = svg2paths2(args.input)
        total = sum(p.length() for p in paths)
        seg = sum(len(p) for p in paths)
        emit({"route": route, "status": "ok", "input": args.input,
              "reader": "svgpathtools", "path_count": len(paths),
              "segment_count": seg, "total_path_length": round(total, 4)})
    elif ext == ".pdf":
        try:
            import fitz
        except Exception as e:
            unavailable(route, "pymupdf(fitz)", type(e).__name__)
        doc = fitz.open(args.input)
        page = doc[0]
        draws = page.get_drawings()
        emit({"route": route, "status": "ok", "input": args.input,
              "reader": "pymupdf", "page_count": doc.page_count,
              "page0_vector_drawings": len(draws),
              "page0_size": [round(page.rect.width, 2),
                             round(page.rect.height, 2)]})
    else:
        emit({"route": route, "status": "error", "error": "unsupported_ext",
              "detail": f"{ext}; supported: .svg/.pdf"}, 5)


def r_raster_compare_route(args):
    route = "raster_compare_route"
    need_input(args.input, route)
    try:
        import cv2
        import numpy as np  # noqa: F401
    except Exception as e:
        unavailable(route, "opencv-headless", type(e).__name__)
    img = cv2.imread(args.input, cv2.IMREAD_GRAYSCALE)
    if img is None:
        emit({"route": route, "status": "error", "error": "image_unreadable",
              "detail": args.input}, 5)
    out = {"route": route, "status": "ok", "input": args.input,
           "reader": "opencv", "shape": list(img.shape),
           "mean_intensity": round(float(img.mean()), 4)}
    if args.input2 and os.path.exists(args.input2):
        img2 = cv2.imread(args.input2, cv2.IMREAD_GRAYSCALE)
        if img2 is not None and img2.shape == img.shape:
            try:
                from skimage.metrics import structural_similarity as ssim
                score = ssim(img, img2)
                out["compare_to"] = args.input2
                out["ssim"] = round(float(score), 6)
            except Exception:
                out["compare_note"] = "skimage ssim unavailable"
    emit(out)


def r_dwg_libredwg_sidecar(args):
    result = run_libredwg_sidecar(
        input_path=args.input,
        run_root=args.run_dir,
        libredwg_bin=args.libredwg_bin,
    )
    if result["status"] == "ok":
        emit(result)
    if result["status"] == "unavailable":
        emit(result, 3)
    emit(result, 5)


DISPATCH = {
    "dxf_fast_secondary": r_dxf_fast_secondary,
    "ifc_bim_semantic": r_ifc_bim_semantic,
    "solid_brep_occ": r_solid_brep_occ,
    "parametric_rebuild": r_parametric_rebuild,
    "mesh_analysis": r_mesh_analysis,
    "pointcloud_route": r_pointcloud_route,
    "geo_vector_route": r_geo_vector_route,
    "pdf_svg_vector_route": r_pdf_svg_vector_route,
    "raster_compare_route": r_raster_compare_route,
    "dwg_libredwg_sidecar": r_dwg_libredwg_sidecar,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", required=True)
    ap.add_argument("--input", default=None)
    ap.add_argument("--input2", default=None, help="second image for compare")
    ap.add_argument("--out", default=None, help="output path (parametric_rebuild)")
    ap.add_argument("--run-dir", default=None, help="router run output root")
    ap.add_argument("--libredwg-bin", default=None, help="sidecar-only LibreDWG bin dir")
    ap.add_argument("--p-len", dest="p_len", type=float, default=None)
    ap.add_argument("--p-wid", dest="p_wid", type=float, default=None)
    ap.add_argument("--p-hgt", dest="p_hgt", type=float, default=None)
    args = ap.parse_args()
    fn = DISPATCH.get(args.route)
    if fn is None:
        emit({"route": args.route, "status": "error",
              "error": "route_not_python_runnable",
              "detail": "dwg_truth_autocad is dispatched by the PowerShell "
                        "router to accoreconsole, not run_route.py"}, 2)
    fn(args)


if __name__ == "__main__":
    main()
