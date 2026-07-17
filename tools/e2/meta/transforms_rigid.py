# -*- coding: utf-8 -*-
"""S5-A — rigid / scale / unit metamorphic transforms for DXF drawings.

Public API
----------
transform(dxf_in, dxf_out, kind, params, seed) -> meta dict

Kinds
-----
- rotate  : params={"angle": <deg>}  — about drawing centroid
- translate: params={"dx": <f>, "dy": <f>}
- mirror  : params={"axis": "x"|"y"}  — reflect across centroid-parallel axis
- scale   : params={"factor": <f>}    — about drawing centroid
- units   : params optional {"to": "mm"|"m"}; default auto-swaps INSUNITS
            mm <-> m and rescales coordinates so geometry is equivalent

Originals are READ-ONLY: always write to dxf_out (must differ from dxf_in).
Handles are preserved by ezdxf on read/modify/saveas → handle_map="identity".

SEGMENT-IR v1 / TRUTH-LEDGER v1 are shared contracts for sibling cards; this
module does not emit them — it only mutates DXF geometry/headers.
"""

from __future__ import annotations

import argparse
import math
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import ezdxf
from ezdxf import transform as ez_transform
from ezdxf.math import Matrix44

# AutoCAD INSUNITS codes (ezdxf.units)
_INSUNITS_MM = 4
_INSUNITS_M = 6
_TOL = 1e-6

KINDS = ("rotate", "translate", "mirror", "scale", "units")


def _as_path(p: Any) -> Path:
    return Path(p).resolve()


def _refuse_inplace(dxf_in: Path, dxf_out: Path) -> None:
    if dxf_in == dxf_out:
        raise ValueError(
            "in-place transform refused: dxf_out must differ from dxf_in "
            "(write to an explicit staging path)"
        )


def _msp_entities(doc: "ezdxf.document.Drawing") -> List[Any]:
    return list(doc.modelspace())


def _collect_xy(entities: Iterable[Any]) -> List[Tuple[float, float]]:
    """Collect 2D sample points from common entity types for centroid/bbox."""
    pts: List[Tuple[float, float]] = []
    for e in entities:
        try:
            dt = e.dxftype()
        except Exception:
            continue
        try:
            if dt == "LINE":
                s, t = e.dxf.start, e.dxf.end
                pts.append((float(s.x), float(s.y)))
                pts.append((float(t.x), float(t.y)))
            elif dt == "LWPOLYLINE":
                for x, y, *_rest in e.get_points("xy"):
                    pts.append((float(x), float(y)))
            elif dt == "POLYLINE":
                for v in e.vertices:
                    loc = v.dxf.location
                    pts.append((float(loc.x), float(loc.y)))
            elif dt in ("POINT", "TEXT", "MTEXT", "INSERT", "CIRCLE", "ARC"):
                c = e.dxf.insert if dt in ("TEXT", "MTEXT", "INSERT") else (
                    e.dxf.center if dt in ("CIRCLE", "ARC") else e.dxf.location
                )
                pts.append((float(c.x), float(c.y)))
            elif hasattr(e, "vertices"):  # fallback
                for v in e.vertices():  # type: ignore[operator]
                    pts.append((float(v.x), float(v.y)))
        except Exception:
            continue
    return pts


def _drawing_centroid(doc: "ezdxf.document.Drawing") -> Tuple[float, float]:
    pts = _collect_xy(_msp_entities(doc))
    if not pts:
        return (0.0, 0.0)
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    n = float(len(pts))
    return (sx / n, sy / n)


def _apply_matrix(doc: "ezdxf.document.Drawing", m: Matrix44) -> None:
    ents = [e for e in _msp_entities(doc) if hasattr(e, "transform")]
    if ents:
        ez_transform.inplace(ents, m)


def _matrix_for_kind(
    kind: str,
    params: Dict[str, Any],
    centroid: Tuple[float, float],
) -> Optional[Matrix44]:
    """Return a Matrix44 for geometric kinds, or None for 'units' (handled separately)."""
    cx, cy = centroid
    if kind == "rotate":
        if "angle" not in params:
            raise ValueError("rotate requires params['angle'] in degrees")
        angle_deg = float(params["angle"])
        angle_rad = math.radians(angle_deg)
        # translate to origin → rotate Z → translate back
        return (
            Matrix44.translate(-cx, -cy, 0.0)
            @ Matrix44.z_rotate(angle_rad)
            @ Matrix44.translate(cx, cy, 0.0)
        )
    if kind == "translate":
        if "dx" not in params or "dy" not in params:
            raise ValueError("translate requires params['dx'] and params['dy']")
        return Matrix44.translate(float(params["dx"]), float(params["dy"]), 0.0)
    if kind == "mirror":
        axis = str(params.get("axis", "")).lower()
        if axis not in ("x", "y"):
            raise ValueError("mirror requires params['axis'] in {'x','y'}")
        # Reflect across centroid-parallel axis:
        #   axis=x → flip Y about y=cy  (horizontal mirror line through centroid)
        #   axis=y → flip X about x=cx  (vertical mirror line through centroid)
        if axis == "x":
            # (x, y) -> (x, 2*cy - y)  ≡  T(0,cy) · Scale(1,-1) · T(0,-cy)
            return (
                Matrix44.translate(0.0, -cy, 0.0)
                @ Matrix44.scale(1.0, -1.0, 1.0)
                @ Matrix44.translate(0.0, cy, 0.0)
            )
        return (
            Matrix44.translate(-cx, 0.0, 0.0)
            @ Matrix44.scale(-1.0, 1.0, 1.0)
            @ Matrix44.translate(cx, 0.0, 0.0)
        )
    if kind == "scale":
        if "factor" not in params:
            raise ValueError("scale requires params['factor']")
        f = float(params["factor"])
        if f == 0.0:
            raise ValueError("scale factor must be non-zero")
        return (
            Matrix44.translate(-cx, -cy, 0.0)
            @ Matrix44.scale(f, f, f)
            @ Matrix44.translate(cx, cy, 0.0)
        )
    if kind == "units":
        return None
    raise ValueError(f"unknown kind {kind!r}; expected one of {KINDS}")


def _apply_units_swap(doc: "ezdxf.document.Drawing", params: Dict[str, Any]) -> Dict[str, Any]:
    """Swap INSUNITS mm <-> m and rescale coordinates so geometry is equivalent.

    Returns the effective params used (including resolved 'to' and 'factor').
    """
    current = int(doc.header.get("$INSUNITS", 0) or 0)
    target = params.get("to")
    if target is None:
        # auto-swap
        if current == _INSUNITS_M:
            target = "mm"
        else:
            # default / MM / anything else → treat as going to metres
            target = "m"
    target = str(target).lower()
    if target not in ("mm", "m"):
        raise ValueError("units params['to'] must be 'mm' or 'm'")

    if target == "m":
        # drawing units currently interpreted as mm → become metres
        factor = 0.001
        new_ins = _INSUNITS_M
        from_u, to_u = "mm", "m"
    else:
        factor = 1000.0
        new_ins = _INSUNITS_MM
        from_u, to_u = "m", "mm"

    # If already at target INSUNITS, still apply rescale only when caller
    # forces a swap from the opposite unit; auto path already chose opposite.
    m = Matrix44.scale(factor, factor, factor)
    _apply_matrix(doc, m)
    doc.header["$INSUNITS"] = new_ins

    effective = dict(params)
    effective.update({"to": target, "from": from_u, "factor": factor, "insunits": new_ins})
    return effective


def transform(
    dxf_in: Any,
    dxf_out: Any,
    kind: str,
    params: Optional[Dict[str, Any]] = None,
    seed: int = 0,
) -> Dict[str, Any]:
    """Apply a metamorphic transform; write result to dxf_out; return metadata.

    Parameters
    ----------
    dxf_in, dxf_out : path-like
        Source is read-only. Output must be a different path (staging).
    kind : str
        One of rotate|translate|mirror|scale|units.
    params : dict
        Kind-specific parameters (see module docstring).
    seed : int
        Accepted for API uniformity with sibling metamorphic modules;
        unused for deterministic rigid kinds.

    Returns
    -------
    dict with keys: kind, params, handle_map ("identity")
    """
    del seed  # rigid kinds are fully determined by (kind, params)
    params = dict(params or {})
    kind = str(kind).lower().strip()
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; expected one of {KINDS}")

    src = _as_path(dxf_in)
    dst = _as_path(dxf_out)
    _refuse_inplace(src, dst)
    if not src.is_file():
        raise FileNotFoundError(f"dxf_in not found: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.readfile(str(src))
    effective_params = dict(params)

    if kind == "units":
        effective_params = _apply_units_swap(doc, params)
    else:
        centroid = _drawing_centroid(doc)
        m = _matrix_for_kind(kind, params, centroid)
        assert m is not None
        _apply_matrix(doc, m)
        effective_params = dict(params)
        effective_params["_centroid"] = [centroid[0], centroid[1]]

    doc.saveas(str(dst))

    return {
        "kind": kind,
        "params": effective_params,
        "handle_map": "identity",
    }


# ---------------------------------------------------------------------------
# Expected-point helpers (selftest)
# ---------------------------------------------------------------------------

def _xform_point(
    x: float,
    y: float,
    kind: str,
    params: Dict[str, Any],
    centroid: Tuple[float, float],
) -> Tuple[float, float]:
    cx, cy = centroid
    if kind == "rotate":
        a = math.radians(float(params["angle"]))
        dx, dy = x - cx, y - cy
        return (cx + dx * math.cos(a) - dy * math.sin(a),
                cy + dx * math.sin(a) + dy * math.cos(a))
    if kind == "translate":
        return (x + float(params["dx"]), y + float(params["dy"]))
    if kind == "mirror":
        axis = str(params["axis"]).lower()
        if axis == "x":
            return (x, 2.0 * cy - y)
        return (2.0 * cx - x, y)
    if kind == "scale":
        f = float(params["factor"])
        return (cx + (x - cx) * f, cy + (y - cy) * f)
    if kind == "units":
        # factor resolved after transform; use params["factor"]
        f = float(params["factor"])
        return (x * f, y * f)
    raise ValueError(kind)


def _line_endpoints(doc: "ezdxf.document.Drawing") -> List[Tuple[str, Tuple[float, float], Tuple[float, float]]]:
    out = []
    for e in doc.modelspace():
        if e.dxftype() == "LINE":
            s, t = e.dxf.start, e.dxf.end
            out.append(
                (
                    str(e.dxf.handle),
                    (float(s.x), float(s.y)),
                    (float(t.x), float(t.y)),
                )
            )
    out.sort(key=lambda r: r[0])
    return out


def _assert_close(a: float, b: float, tol: float, msg: str) -> None:
    if abs(a - b) > tol:
        raise AssertionError(f"{msg}: {a!r} vs {b!r} (tol={tol})")


def _build_fixture(path: Path) -> List[Tuple[str, Tuple[float, float], Tuple[float, float]]]:
    """Build a temp DXF with 3 LINEs; return (handle, start, end) sorted by handle."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = _INSUNITS_MM
    msp = doc.modelspace()
    segs = [
        ((0.0, 0.0), (1000.0, 0.0)),
        ((0.0, 0.0), (0.0, 500.0)),
        ((1000.0, 0.0), (1000.0, 500.0)),
    ]
    for a, b in segs:
        msp.add_line(a, b, dxfattribs={"layer": "WALL"})
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(path))
    doc2 = ezdxf.readfile(str(path))
    return _line_endpoints(doc2)


def run_selftest() -> int:
    """Self-contained selftest: 3 LINEs × each kind; coord / handle / count checks."""
    print("S5-A transforms_rigid selftest starting")
    cases: Sequence[Tuple[str, Dict[str, Any]]] = (
        ("rotate", {"angle": 90.0}),
        ("translate", {"dx": 100.0, "dy": -50.0}),
        ("mirror", {"axis": "x"}),
        ("mirror", {"axis": "y"}),
        ("scale", {"factor": 2.0}),
        ("units", {"to": "m"}),
        ("units", {"to": "mm"}),
    )

    with tempfile.TemporaryDirectory(prefix="s5a_rigid_") as td:
        td_path = Path(td)
        src = td_path / "fixture.dxf"
        before = _build_fixture(src)
        assert len(before) == 3, f"expected 3 LINEs, got {len(before)}"
        handles_before = [h for h, _, _ in before]
        print(f"fixture: {src} handles={handles_before}")

        # centroid from fixture points
        all_pts = []
        for _, s, e in before:
            all_pts.append(s)
            all_pts.append(e)
        cx = sum(p[0] for p in all_pts) / len(all_pts)
        cy = sum(p[1] for p in all_pts) / len(all_pts)
        centroid = (cx, cy)
        print(f"centroid=({cx:.6f},{cy:.6f})")

        for idx, (kind, params) in enumerate(cases):
            tag = "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
            out = td_path / f"out_{idx:02d}_{kind}_{tag}.dxf"

            src_for = src
            before_pts = before
            expect_params = dict(params)
            local_centroid = centroid

            if kind == "units" and params.get("to") == "mm":
                # fixture is MM; produce an intermediate metres drawing first
                mid = td_path / "mid_metres.dxf"
                meta_mid = transform(src, mid, "units", {"to": "m"}, seed=0)
                assert meta_mid["handle_map"] == "identity"
                src_for = mid
                before_pts = _line_endpoints(ezdxf.readfile(str(mid)))
                expect_params = {"to": "mm", "factor": 1000.0}
                local_centroid = (0.0, 0.0)
            elif kind == "units":
                expect_params = {"to": "m", "factor": 0.001}
                local_centroid = (0.0, 0.0)

            meta = transform(src_for, out, kind, params, seed=42)
            assert meta["kind"] == kind
            assert meta["handle_map"] == "identity"
            assert "params" in meta

            doc_out = ezdxf.readfile(str(out))
            after = _line_endpoints(doc_out)
            assert len(after) == len(before_pts), (
                f"{kind}: entity count {len(after)} != {len(before_pts)}"
            )
            handles_after = [h for h, _, _ in after]
            assert handles_after == [h for h, _, _ in before_pts], (
                f"{kind}: handles changed {handles_before} -> {handles_after}"
            )

            # coordinate check
            for (h0, s0, e0), (h1, s1, e1) in zip(before_pts, after):
                assert h0 == h1
                es = _xform_point(s0[0], s0[1], kind, expect_params, local_centroid)
                ee = _xform_point(e0[0], e0[1], kind, expect_params, local_centroid)
                _assert_close(s1[0], es[0], _TOL, f"{kind} {h0} start.x")
                _assert_close(s1[1], es[1], _TOL, f"{kind} {h0} start.y")
                _assert_close(e1[0], ee[0], _TOL, f"{kind} {h0} end.x")
                _assert_close(e1[1], ee[1], _TOL, f"{kind} {h0} end.y")

            if kind == "units":
                ins = int(doc_out.header.get("$INSUNITS", 0))
                want = _INSUNITS_M if expect_params["to"] == "m" else _INSUNITS_MM
                assert ins == want, f"INSUNITS {ins} != {want}"

            print(f"PASS kind={kind} params={params} out={out.name}")

    print("S5-A transforms_rigid selftest ALL PASS")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="S5-A rigid/scale/unit DXF transforms")
    p.add_argument("--selftest", action="store_true", help="run built-in selftest")
    p.add_argument("--dxf-in", type=str, default=None)
    p.add_argument("--dxf-out", type=str, default=None)
    p.add_argument("--kind", type=str, default=None, choices=list(KINDS))
    p.add_argument("--angle", type=float, default=None, help="rotate angle deg")
    p.add_argument("--dx", type=float, default=None)
    p.add_argument("--dy", type=float, default=None)
    p.add_argument("--axis", type=str, default=None, choices=["x", "y"])
    p.add_argument("--factor", type=float, default=None)
    p.add_argument("--to", type=str, default=None, choices=["mm", "m"])
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(list(argv) if argv is not None else None)

    if args.selftest:
        return run_selftest()

    if not args.dxf_in or not args.dxf_out or not args.kind:
        p.error("--dxf-in, --dxf-out, and --kind are required unless --selftest")

    params: Dict[str, Any] = {}
    if args.kind == "rotate":
        if args.angle is None:
            p.error("rotate needs --angle")
        params["angle"] = args.angle
    elif args.kind == "translate":
        if args.dx is None or args.dy is None:
            p.error("translate needs --dx and --dy")
        params["dx"] = args.dx
        params["dy"] = args.dy
    elif args.kind == "mirror":
        if args.axis is None:
            p.error("mirror needs --axis x|y")
        params["axis"] = args.axis
    elif args.kind == "scale":
        if args.factor is None:
            p.error("scale needs --factor")
        params["factor"] = args.factor
    elif args.kind == "units":
        if args.to is not None:
            params["to"] = args.to

    meta = transform(args.dxf_in, args.dxf_out, args.kind, params, args.seed)
    print(meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
