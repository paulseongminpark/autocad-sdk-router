"""LEX-0013: spline edge-loop re-decomposition quotient.

The two residual 1.dwg hatch pairs in def X-FORM_청주$0$dA로고
(reports/interior100/loops_residue_analysis_R4x.json: resistant 2,
pointcloud_max_nn 9.16e-4, spline-control-proxy; fixture
tests/fixtures/lex0013_dA_pairs.json) store the same boundary as a few
multi-span cubic B-spline edges on the census side and as per-knot-span
Bezier edges on the rebuild. Segmentation and knot parameterization of a
spline edge chain are notation; the curve is the geometry. LEX-0013 folds
that notation via Boehm knot insertion to a concatenated Bezier segment
list (plus closed-loop cycle rotation).

Independent oracles (de Boor / de Casteljau) live in this module so the
splitter is never used to check itself.
"""
from __future__ import annotations

import copy
import json
import math
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import blockdef_diff

_FIXTURE = os.path.join(_REPO, "tests", "fixtures", "lex0013_dA_pairs.json")
_SAMPLES = 64
# R4x geometry_eq_tolerance / measured pointcloud_max_nn ceiling.
_R4X_CURVE_TOL = 1e-3


def _load_pairs():
    with open(_FIXTURE, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)["pairs"]


def _dump(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def _canon_loops(entity):
    return blockdef_diff._canonical_entity(copy.deepcopy(entity))["geometry"]["loops"]


# ---- independent oracles ----------------------------------------------------

def _find_span(knots, degree, u):
    n = len(knots) - degree - 2
    if u >= knots[n + 1]:
        return n
    if u <= knots[degree]:
        return degree
    low, high = degree, n + 1
    mid = (low + high) // 2
    while u < knots[mid] or u >= knots[mid + 1]:
        if u < knots[mid]:
            high = mid
        else:
            low = mid
        mid = (low + high) // 2
    return mid


def _de_boor(control, knots, degree, u, weights=None):
    """Plain de Boor evaluator (optionally rational via homogeneous coords)."""
    d = degree
    if weights is None:
        pts = [tuple(c[:2]) for c in control]
    else:
        pts = [(c[0] * w, c[1] * w, w) for c, w in zip(control, weights)]
    k = _find_span(knots, d, u)
    dim = len(pts[0])
    d_pts = [pts[k - d + j] for j in range(d + 1)]
    for r in range(1, d + 1):
        for j in range(d, r - 1, -1):
            i = k - d + j
            denom = knots[i + d + 1 - r] - knots[i]
            a = 0.0 if denom == 0.0 else (u - knots[i]) / denom
            d_pts[j] = tuple(
                (1.0 - a) * d_pts[j - 1][t] + a * d_pts[j][t] for t in range(dim)
            )
    p = d_pts[d]
    if weights is None:
        return (p[0], p[1])
    return (p[0] / p[2], p[1] / p[2])


def _de_casteljau(control, t, weights=None):
    """Plain de Casteljau evaluator (optionally rational)."""
    if weights is None:
        pts = [tuple(c[:2]) for c in control]
    else:
        pts = [(c[0] * w, c[1] * w, w) for c, w in zip(control, weights)]
    dim = len(pts[0])
    work = list(pts)
    n = len(work) - 1
    for r in range(1, n + 1):
        for i in range(n - r + 1):
            work[i] = tuple(
                (1.0 - t) * work[i][j] + t * work[i + 1][j] for j in range(dim)
            )
    p = work[0]
    if weights is None:
        return (p[0], p[1])
    return (p[0] / p[2], p[1] / p[2])


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _raise_to_bezier_form(control, knots, degree, weights):
    """Independent Boehm raise (test oracle -- not the implementation)."""
    d = degree
    if weights is None:
        pts = [tuple(c[:2]) for c in control]
    else:
        pts = [(c[0] * w, c[1] * w, w) for c, w in zip(control, weights)]
    U = list(knots)
    ds, de = U[d], U[len(pts)]
    interiors, seen = [], set()
    for t in U:
        if t not in seen and ds < t < de:
            interiors.append(t)
            seen.add(t)
    for u in interiors:
        while sum(1 for t in U if t == u) < d:
            pts, U = _boehm_once(pts, U, d, u)
    return pts, U


def _boehm_once(controls, knots, degree, u):
    d = degree
    n = len(controls) - 1
    k = None
    for i in range(len(knots) - 1):
        if knots[i] <= u < knots[i + 1]:
            k = i
            break
    if k is None:
        return controls, knots
    dim = len(controls[0])
    new_c = [None] * (n + 2)
    for i in range(0, k - d + 1):
        new_c[i] = controls[i]
    for i in range(k - d + 1, k + 1):
        denom = knots[i + d] - knots[i]
        a = 0.0 if denom == 0.0 else (u - knots[i]) / denom
        new_c[i] = tuple(
            (1.0 - a) * controls[i - 1][j] + a * controls[i][j] for j in range(dim)
        )
    for i in range(k + 1, n + 2):
        new_c[i] = controls[i - 1]
    return list(new_c), knots[: k + 1] + [u] + knots[k + 1 :]


def _sample_edge_vs_canon(edge, canon_segs, start_seg_index):
    """Sample one original spline edge against matching canon Beziers."""
    degree = edge["degree"]
    control = edge["control"]
    knots = edge["knots"]
    weights_raw = edge.get("weights") or []
    rational = bool(edge.get("rational")) or bool(weights_raw)
    weights = list(weights_raw) if rational else None
    pts, U = _raise_to_bezier_form(control, knots, degree, weights)
    n = len(pts) - 1
    d = degree
    spans = []
    for i in range(d, n + 1):
        if U[i] < U[i + 1]:
            raw = pts[i - d: i + 1]
            if weights is None:
                ctrl = [(p[0], p[1]) for p in raw]
                wts = None
            else:
                ctrl, wts = [], []
                for hx, hy, hw in raw:
                    ctrl.append((hx / hw, hy / hw))
                    wts.append(hw)
            q = [[round(p[0], 6), round(p[1], 6)] for p in ctrl]
            if all(pt == q[0] for pt in q):
                continue
            spans.append((ctrl, wts, U[i], U[i + 1]))
    max_err = 0.0
    for ctrl, wts, u0, u1 in spans:
        q = [[round(p[0], 6), round(p[1], 6)] for p in ctrl]
        assert any(seg.get("control") == q for seg in canon_segs), (
            "canon missing span for edge sample")
        for i in range(_SAMPLES + 1):
            t = i / _SAMPLES
            u = u0 + (u1 - u0) * t
            p_orig = _de_boor(control, knots, degree, u, weights)
            p_full = _de_casteljau(ctrl, t, wts)
            max_err = max(max_err, _dist(p_orig, p_full))
    return start_seg_index + len(spans), max_err


def _assert_loop_curve_identity(loop, canon_loop, tol=1e-9):
    edges = loop["edges"]
    canon_segs = canon_loop["edges"]
    assert all(s.get("type") == "spline_bezier" for s in canon_segs)
    max_err = 0.0
    si = 0
    for edge in edges:
        si, err = _sample_edge_vs_canon(edge, canon_segs, si)
        max_err = max(max_err, err)
    assert max_err <= tol, max_err


def _spline_hatch(handle, loops):
    return {
        "handle": handle,
        "dxf_name": "HATCH",
        "layer": "0",
        "space": "block",
        "geometry": {
            "kind": "hatch",
            "pattern_name": "SOLID",
            "is_solid_fill": True,
            "loops": loops,
        },
    }


def _spline_edge(degree, control, knots, *, rational=False, weights=None):
    return {
        "type": "spline",
        "degree": degree,
        "control": control,
        "knots": knots,
        "rational": rational,
        "weights": list(weights) if weights is not None else [],
    }


# ---- A. independent oracle --------------------------------------------------

def test_oracle_hand_cubic_two_span_matches_canon_beziers():
    # Clamped cubic, knots [0,0,0,0,1,2,2,2,2], 5 controls -> 2 spans.
    control = [[0.0, 0.0], [1.0, 2.0], [2.0, 2.0], [3.0, 0.0], [4.0, 1.0]]
    knots = [0.0, 0.0, 0.0, 0.0, 1.0, 2.0, 2.0, 2.0, 2.0]
    loop = {
        "index": 0, "loop_type": 1, "status": 1, "closed": False,
        "edges": [_spline_edge(3, control, knots)],
    }
    entity = _spline_hatch("H1", [loop])
    canon = _canon_loops(entity)[0]
    assert len(canon["edges"]) == 2
    assert all(s["type"] == "spline_bezier" and s["degree"] == 3
               for s in canon["edges"])
    _assert_loop_curve_identity(loop, canon, tol=1e-9)


def test_oracle_resistant_a_side_loops_match_canon_beziers():
    pairs = _load_pairs()
    for pi in (2, 3):
        a_ent = pairs[pi]["a_entity"]
        for loop in a_ent["geometry"]["loops"]:
            # Part-1 canon directly: the entity-level path additionally folds
            # these assoc-sourced loops to the derived marker (part 2), which
            # carries no control points to sample against.
            canon_loop = blockdef_diff._canonical_spline_loop(loop)
            _assert_loop_curve_identity(loop, canon_loop, tol=1e-9)


# ---- B. fold ----------------------------------------------------------------

def test_fold_algebraic_multispan_vs_presplit_beziers():
    """Multi-span edge vs its per-span Bezier edges fold to equal canon loops.

    The Bezier controls are derived here with the test's own Boehm (not the
    implementation), so this is an independent algebraic fold check.
    """
    control = [[0.0, 0.0], [1.0, 2.0], [2.0, 2.0], [3.0, 0.0], [4.0, 1.0]]
    knots = [0.0, 0.0, 0.0, 0.0, 1.0, 2.0, 2.0, 2.0, 2.0]
    pts, U = _raise_to_bezier_form(control, knots, 3, None)
    n = len(pts) - 1
    bez_edges = []
    for i in range(3, n + 1):
        if U[i] < U[i + 1]:
            cps = [[p[0], p[1]] for p in pts[i - 3: i + 1]]
            # Single-span clamped cubic knot vector on [U[i], U[i+1]].
            u0, u1 = U[i], U[i + 1]
            bez_edges.append(_spline_edge(
                3, cps, [u0, u0, u0, u0, u1, u1, u1, u1]))
    assert len(bez_edges) == 2
    a = _spline_hatch("A", [{
        "index": 0, "loop_type": 1, "status": 1, "closed": True,
        "edges": [_spline_edge(3, control, knots)],
    }])
    b = _spline_hatch("B", [{
        "index": 0, "loop_type": 1, "status": 1, "closed": True,
        "edges": bez_edges,
    }])
    assert _dump(_canon_loops(a)) == _dump(_canon_loops(b))


def test_fold_resistant_fixture_pairs_curve_agree_part1():
    """Substitute-verifier evidence behind LEX-0013 part 2: the rebuild
    RE-FITS the derived boundary (10 vs 9 spans on loop0), so part-1
    control-polygon JSON equality is unreachable at the 6dp grid; the
    measured R4x claim is curve identity (pointcloud_max_nn 9.16e-4). Both
    sides' PART-1 canonical Bezier chains agree under the independent
    de Casteljau oracle within that measured tolerance."""
    pairs = _load_pairs()
    for pi in (2, 3):
        la_loops = [blockdef_diff._canonical_spline_loop(lp)
                    for lp in pairs[pi]["a_entity"]["geometry"]["loops"]]
        lb_loops = [blockdef_diff._canonical_spline_loop(lp)
                    for lp in pairs[pi]["b_entity"]["geometry"]["loops"]]
        assert len(la_loops) == len(lb_loops)
        for la, lb in zip(la_loops, lb_loops):
            assert la.get("loop_type") == lb.get("loop_type")
            assert bool(la.get("closed")) == bool(lb.get("closed"))
            # Dense sample both canon Bezier chains; max NN within R4x tol.
            def samples(loop):
                pts = []
                for seg in loop["edges"]:
                    for i in range(_SAMPLES + 1):
                        pts.append(_de_casteljau(
                            seg["control"], i / _SAMPLES, seg.get("weights")))
                return pts

            pa, pb = samples(la), samples(lb)
            max_nn = 0.0
            for p in pa:
                max_nn = max(max_nn, min(_dist(p, q) for q in pb))
            for q in pb:
                max_nn = max(max_nn, min(_dist(q, p) for p in pa))
            assert max_nn <= _R4X_CURVE_TOL, (pi, max_nn)


def test_fold_resistant_fixture_pairs_fingerprint_equal():
    """LEX-0013 acceptance: the two R4x resistant pairs now compare EQUAL at
    the fingerprint level. Both are ASSOCIATIVE hatches (1 source entity per
    loop), so part 2 folds the evaluateHatch-derived, re-fit spline-chain
    cache to the structural marker; the authored geometry rides the source
    entities, which the same def diff compares exactly."""
    pairs = _load_pairs()
    for pi in (2, 3):
        ca = _canon_loops(pairs[pi]["a_entity"])
        cb = _canon_loops(pairs[pi]["b_entity"])
        assert _dump(ca) == _dump(cb), pi
        for lp in ca:
            assert lp["edges"] == [{"type": "spline_chain_derived"}]
            assert "loop_type" in lp and "closed" in lp


def _strip_assoc(entity):
    ent = copy.deepcopy(entity)
    ent["geometry"].pop("assoc_source_handles", None)
    ent["geometry"].pop("is_associative", None)
    return ent


def test_derived_fold_requires_assoc_sources():
    """Part 2 is GATED on a positive per-loop source count: a sourceless
    spline loop keeps its part-1 algebraic chain (folding it would erase the
    only place its geometry lives)."""
    pairs = _load_pairs()
    ca = _canon_loops(_strip_assoc(pairs[2]["a_entity"]))
    for lp in ca:
        assert lp["edges"], "chain must survive without sources"
        assert all(s.get("type") == "spline_bezier" for s in lp["edges"])
    # And without the fold the re-fit sides honestly stay UNEQUAL:
    cb = _canon_loops(_strip_assoc(pairs[2]["b_entity"]))
    assert _dump(ca) != _dump(cb)


# ---- C. no-regression controls ---------------------------------------------

def test_no_regression_control_pairs_still_equal():
    pairs = _load_pairs()
    for pi in (0, 1, 4):
        assert _dump(_canon_loops(pairs[pi]["a_entity"])) == _dump(
            _canon_loops(pairs[pi]["b_entity"]))


# ---- D. no false fold -------------------------------------------------------

def test_no_false_fold_when_b_control_perturbed_sourceless():
    """On a SOURCELESS loop the fingerprint keeps full curve sharpness: a
    1e-3 control perturbation stays a difference. (For assoc-sourced loops
    the same perturbation lands in the derived-cache blind spot documented
    in the LEX-0013 ledger entry -- a real change there moves the SOURCE
    entities, which are compared exactly elsewhere in the def diff.)"""
    pairs = _load_pairs()
    p = copy.deepcopy(pairs[2])
    edge = p["b_entity"]["geometry"]["loops"][0]["edges"][0]
    edge["control"][0][0] += 1e-3
    assert _dump(_canon_loops(_strip_assoc(pairs[2]["a_entity"]))) != _dump(
        _canon_loops(_strip_assoc(p["b_entity"])))


# ---- E. guards --------------------------------------------------------------

def test_guard_mixed_non_spline_edge_unchanged():
    loop = {
        "index": 0, "loop_type": 5, "status": 1, "closed": True,
        "edges": [
            _spline_edge(3,
                         [[0, 0], [1, 1], [2, 1], [3, 0]],
                         [0, 0, 0, 0, 1, 1, 1, 1]),
            {"type": "line", "start": [3, 0], "end": [0, 0]},
        ],
    }
    out = blockdef_diff._canonical_spline_loop(loop)
    assert out is loop


def test_guard_inconsistent_knot_count_unchanged():
    loop = {
        "index": 0, "loop_type": 5, "status": 1, "closed": True,
        "edges": [
            _spline_edge(3,
                         [[0, 0], [1, 1], [2, 1], [3, 0]],
                         [0, 0, 0, 0, 1, 1, 1]),  # len 7, need 8
        ],
    }
    out = blockdef_diff._canonical_spline_loop(loop)
    assert out is loop


# ---- F. rational path -------------------------------------------------------

def test_rational_quadratic_quarter_circle():
    # Unit quarter-circle as rational quadratic Bezier (one span).
    w = 1.0 / math.sqrt(2.0)
    control = [[1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
    knots = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
    weights = [1.0, w, 1.0]
    loop = {
        "index": 0, "loop_type": 1, "status": 1, "closed": False,
        "edges": [_spline_edge(2, control, knots, rational=True, weights=weights)],
    }
    # Algebraic identity on the unquantized rational Bezier (1e-9 to the
    # unit circle). Emission then snaps to the 6dp grid (LEX-0009); sampling
    # the snapped controls inherits that grid, so the circle check below
    # uses the independent full-precision form, and the canon is asserted
    # to be exactly the @6dp image of that same single span.
    for i in range(_SAMPLES + 1):
        t = i / _SAMPLES
        x, y = _de_casteljau(control, t, weights)
        assert abs(math.hypot(x, y) - 1.0) <= 1e-9
    canon = blockdef_diff._canonical_spline_loop(loop)
    assert canon is not loop
    assert len(canon["edges"]) == 1
    seg = canon["edges"][0]
    assert seg["type"] == "spline_bezier" and seg["degree"] == 2
    assert "weights" in seg
    assert seg["control"] == [[round(p[0], 6), round(p[1], 6)] for p in control]
    assert seg["weights"] == [round(v, 6) for v in weights]
