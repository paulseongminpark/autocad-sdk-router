#!/usr/bin/env python3
"""Entity-identity helpers for IR roundtrip drift analysis.

Why this exists
---------------
Round-tripped drawings often churn DWG handles and mutate volatile metadata.
Round-tripping tests therefore need a deterministic, read-only way to reason
about logical entity continuity using extraction-only IR artifacts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


_FLOAT_PRECISION = 6
_NO_HANDLE_GEOM_PLACEHOLDER = "<no-handle>"


def _coerce_handle(value: Any) -> str:
    """Return a compact handle string for identity matching."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _coerce_number(value: Any) -> float | None:
    """Convert a scalar to float when possible, excluding booleans."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def _round_number(value: Any) -> float | None:
    n = _coerce_number(value)
    if n is None:
        return None
    return round(n, _FLOAT_PRECISION)


def _coerce_point(value: Any) -> Tuple[float, float, float] | None:
    """Return ``(x, y, z)`` from dict/list-like geometry payloads."""
    if not isinstance(value, (dict, list, tuple)):
        return None

    if isinstance(value, (list, tuple)):
        if not value:
            return None
        nums = [_coerce_number(v) for v in value]
        nums = [n for n in nums if n is not None]
        if not nums:
            return None
        x, y = nums[0], nums[1] if len(nums) > 1 else 0.0
        z = nums[2] if len(nums) > 2 else 0.0
        return (x, y, z)

    # dict form: accepts {"x","y","z"} or lowercase variations.
    x = _coerce_number(value.get("x", value.get("X")))
    y = _coerce_number(value.get("y", value.get("Y")))
    z = _coerce_number(value.get("z", value.get("Z")))
    if x is None and y is None and z is None:
        return None
    return (x or 0.0, y or 0.0, z or 0.0)


def _coarse_geometry_source(entity: Dict[str, Any]) -> Tuple[float, ...]:
    """Extract a coarse, deterministic geometry signature from bbox/first-point.

    Geometry fidelity is intentionally coarse:
      * prefer bbox (when present);
      * fallback to the first point-like payload from geometry.
    """
    bbox = entity.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 6:
        parts = [_round_number(v) for v in bbox[:6]]
        if all(v is not None for v in parts):
            return tuple(float(v) for v in parts)

    geometry = entity.get("geometry")
    if isinstance(geometry, dict):
        for key in ("start", "end", "center", "position"):
            point = _coerce_point(geometry.get(key))
            if point is not None:
                return tuple(float(_round_number(c) or 0.0) for c in point)

        vertices = geometry.get("vertices")
        if isinstance(vertices, (list, tuple)) and vertices:
            first = vertices[0]
            if isinstance(first, dict):
                if "point" in first:
                    point = _coerce_point(first.get("point"))
                    if point is not None:
                        return tuple(float(_round_number(c) or 0.0) for c in point)
                point = _coerce_point(first)
                if point is not None:
                    return tuple(float(_round_number(c) or 0.0) for c in point)

    return tuple()


def _coarse_geometry_fingerprint(entity: Dict[str, Any]) -> str:
    """Return a deterministic coarse geometry fingerprint string."""
    values = _coarse_geometry_source(entity)
    if not values:
        return "no-geom"
    parts = ["{:.6f}".format(v).rstrip("0").rstrip(".") for v in values]
    return "g:" + ",".join(parts)


def _xdata_anchor(entity: Dict[str, Any]) -> str:
    """Build a stable anchor token from extension-dict handle + xdata blocks."""
    anchors: List[str] = []

    ext_dict = _coerce_handle(entity.get("extension_dictionary_handle"))
    if ext_dict:
        anchors.append("ed:%s" % ext_dict)

    xdata = entity.get("xdata")
    if isinstance(xdata, list):
        for block in xdata:
            if not isinstance(block, dict):
                continue
            app = block.get("app")
            if isinstance(app, str) and app.strip():
                anchors.append("xapp:%s" % app.strip())

            for item in block.get("items", []) or []:
                if not isinstance(item, dict):
                    continue
                value = item.get("value")
                if isinstance(value, (str, int, float)):
                    value_text = str(value).strip()
                    if value_text:
                        anchors.append("xval:%s" % value_text)

    if not anchors:
        return ""
    deduped = sorted(set(anchors))
    return "|".join(deduped)


def entity_identity_key(entity: Dict[str, Any]) -> str:
    """
    Stable, deterministic key for an extracted entity.

    Precedence:
      * handle first (portable DWG join key, when present);
      * xdata/extension-dictionary anchor as secondary signal;
      * coarse geometric fingerprint as tie-break/fallback when handle is absent.
    """
    if not isinstance(entity, dict):
        return _NO_HANDLE_GEOM_PLACEHOLDER

    handle = _coerce_handle(entity.get("handle"))
    anchor = _xdata_anchor(entity)
    geom_fp = _coarse_geometry_fingerprint(entity)

    if handle:
        parts = ["h:%s" % handle]
        if anchor:
            parts.append("a:%s" % anchor)
        return "|".join(parts)

    if anchor:
        return "a:%s|%s" % (anchor, geom_fp)

    return geom_fp


def _extract_entities(ir_or_entities: Any) -> List[Dict[str, Any]]:
    if isinstance(ir_or_entities, list):
        return [e for e in ir_or_entities if isinstance(e, dict)]
    if isinstance(ir_or_entities, dict):
        entities = ir_or_entities.get("entities", [])
        if isinstance(entities, list):
            return [e for e in entities if isinstance(e, dict)]
    return []


def verify_identity_stability(ir_before: Any, ir_after: Any) -> Dict[str, Any]:
    """Compare two extracted entity sequences with identity-key pairing.

    Returns:
        {
          "ok": bool,
          "stable": [keys],
          "drifted": [{"key", "before", "after"}, ...],
          "added": [keys],
          "removed": [keys],
          "summary": {stable_n, drifted_n, added_n, removed_n}
        }
    """
    before = _extract_entities(ir_before)
    after = _extract_entities(ir_after)

    before_by_key: Dict[str, List[Dict[str, Any]]] = {}
    after_by_key: Dict[str, List[Dict[str, Any]]] = {}

    for entity in before:
        key = entity_identity_key(entity)
        before_by_key.setdefault(key, []).append(entity)

    for entity in after:
        key = entity_identity_key(entity)
        after_by_key.setdefault(key, []).append(entity)

    stable: List[str] = []
    drifted: List[Dict[str, Any]] = []
    added: List[str] = []
    removed: List[str] = []

    all_keys = sorted(set(before_by_key) | set(after_by_key))
    for key in all_keys:
        before_bucket = before_by_key.get(key, [])
        after_bucket = after_by_key.get(key, [])
        pair_count = min(len(before_bucket), len(after_bucket))

        for idx in range(pair_count):
            before_entity = before_bucket[idx]
            after_entity = after_bucket[idx]
            if _coarse_geometry_fingerprint(before_entity) == _coarse_geometry_fingerprint(after_entity):
                stable.append(key)
            else:
                drifted.append({
                    "key": key,
                    "before": before_entity,
                    "after": after_entity,
                })

        if len(before_bucket) > pair_count:
            removed.extend([key] * (len(before_bucket) - pair_count))
        if len(after_bucket) > pair_count:
            added.extend([key] * (len(after_bucket) - pair_count))

    return {
        "ok": len(drifted) == 0 and len(added) == 0 and len(removed) == 0,
        "stable": stable,
        "drifted": drifted,
        "added": added,
        "removed": removed,
        "summary": {
            "stable_n": len(stable),
            "drifted_n": len(drifted),
            "added_n": len(added),
            "removed_n": len(removed),
        },
    }
