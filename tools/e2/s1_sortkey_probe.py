#!/usr/bin/env python3
"""S1-D: sort-key artifact probe for the E1 'divergent top-20'.

Question: is the E1 divergent top-20 a product of the specific ``_score_divergence``
sort design in ``reports/e1/panel_20260717/evidence/e1_crosscheck.py``, or a stable
phenomenon that survives a change of ranking key?

Four rankings are recomputed over one controlled def universe:

  (a) original  - mirrored ``_score_divergence``: hard gate (candidate kinds) plus a
                  lexicographic tier key over (kind, wall_likelihood, n_pairs).
  (b) absdiff   - |LLM wall_likelihood - detector_signal|, continuous, ungated.
  (c) wrankdiff - wall_likelihood-weighted |rank_llm - rank_detector| / N.
  (d) bootstrap - per-def bootstrap over judge subsets (5 choose 3 = 10 subsets) of the
                  annot_v1 raw judges; defs ranked by how often they enter the top-20.

Verdict band on the mean pairwise Jaccard of the four top-20 sets:
  < 0.4 -> SORT_ARTIFACT_CONFIRMED ; > 0.7 -> STABLE_PHENOMENON ; else MIXED.

stdlib only.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import tempfile
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Sequence

_JSON_ENCODING = "utf-8-sig"
SCHEMA = "ariadne.e2_s1_sortkey_probe.v1"

JUDGES: tuple[str, ...] = (
    "opus48_max",
    "fable5_high",
    "sol56_xhigh",
    "sonnet5_xhigh",
    "grok45_xhigh",
)
TOP_N = 20
SUBSET_K = 3

# Mirrored verbatim from e1_crosscheck.py -- the gate is part of the sort design under test.
HIGH_LIKELIHOOD_CUTOFF = 0.7
LOW_LIKELIHOOD_CUTOFF = 0.3
MANY_PAIRS_CUTOFF = 5

# Verdict bands (pre-registered by the card; boundaries inclusive of MIXED).
ARTIFACT_BAND = 0.4
STABLE_BAND = 0.7

KEYS: tuple[str, ...] = ("a_original", "b_absdiff", "c_wrankdiff", "d_bootstrap")


# --------------------------------------------------------------------------- io


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding=_JSON_ENCODING) as handle:
        return json.load(handle)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding=_JSON_ENCODING) as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


# ------------------------------------------------------- shared helpers (mirrored)


def _normalize_def_name(def_name: str | None) -> str:
    return "".join((def_name or "").split())


def _handle_value(handle: Any) -> str | None:
    """wall_line_handles items are strings OR {"handle","reason"} objects."""
    if isinstance(handle, dict):
        value = handle.get("handle")
    else:
        value = handle
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _handle_set(items: Any) -> set[str]:
    handles: set[str] = set()
    if not isinstance(items, list):
        return handles
    for item in items:
        value = _handle_value(item)
        if value is not None:
            handles.add(value)
    return handles


def _pair_handle_set(pair_rows: Iterable[dict[str, Any]]) -> set[str]:
    handles: set[str] = set()
    for pair_row in pair_rows:
        for value in (pair_row.get("pair") or []):
            handle = _handle_value(value)
            if handle is not None:
                handles.add(handle)
    return handles


def _jaccard(lhs: set[str], rhs: set[str]) -> float:
    union = lhs | rhs
    if not union:
        return 1.0
    return len(lhs & rhs) / len(union)


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


# --------------------------------------------------- E1 projection grammar parser

KNOWN_DXF_KINDS = frozenset(
    {
        "LINE",
        "INSERT",
        "MTEXT",
        "POINT",
        "LWPOLYLINE",
        "WIPEOUT",
        "SPLINE",
        "HATCH",
        "TEXT",
        "ARC",
        "CIRCLE",
        "ELLIPSE",
        "3DFACE",
    }
)

_RE_LAYER = re.compile(r"\blayer=(\S+)")
_RE_HANDLE = re.compile(r"\bhandle=(\S+)")
_RE_BLOCK = re.compile(r"\bblock=(\S+)")
_RE_VERTICES = re.compile(r"\bvertices=(\d+)")
_RE_RADIUS = re.compile(r"\bradius=(-?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)")
_RE_PATTERN = re.compile(r"\bpattern=(\S+)")
_RE_LOOPS = re.compile(r"\bloops=(\d+)")
_NUM = r"(-?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)"
_RE_SEGMENT = re.compile(
    r"\(\s*" + _NUM + r"\s*,\s*" + _NUM + r"\s*\)\s*->\s*\(\s*" + _NUM + r"\s*,\s*" + _NUM + r"\s*\)"
)
_RE_QUOTED = re.compile(r"'([^']*)'")

_RE_DEF_NAME = re.compile(r"^Definition name:\s*(.+?)\s*$")
_RE_ENTITY_COUNT = re.compile(r"^entity_count:\s*(\d+)\s*$")
_RE_DXF_HIST = re.compile(r"^dxf_name histogram:\s*(.*)$")
_RE_LAYER_HIST = re.compile(r"^layer histogram:\s*(.*)$")
_RE_BBOX = re.compile(r"^bbox from LINE start/end:\s*\[(.*)\]\s*$")
_RE_SAMPLED = re.compile(r"^sampled entities \(max \d+\):\s*$")
_RE_HIST_ITEM = re.compile(r"^\s*(\S+)\s*=\s*(\d+)\s*$")


def parse_entity_line(raw: str) -> dict[str, Any]:
    """Parse one 'sampled entities' line. Unknown shapes -> kind='other'. Never raises."""
    entity: dict[str, Any] = {"kind": "other", "layer": None, "handle": None}
    try:
        text = raw.strip()
        if text.startswith("-"):
            text = text[1:].strip()
        if not text:
            return entity
        token = text.split(None, 1)[0]
        entity["kind"] = token if token in KNOWN_DXF_KINDS else "other"

        match = _RE_LAYER.search(text)
        if match:
            entity["layer"] = match.group(1)
        match = _RE_HANDLE.search(text)
        if match:
            entity["handle"] = match.group(1)
        match = _RE_BLOCK.search(text)
        if match:
            entity["block"] = match.group(1)
        match = _RE_VERTICES.search(text)
        if match:
            entity["vertices"] = int(match.group(1))
        match = _RE_RADIUS.search(text)
        if match:
            entity["radius"] = float(match.group(1))
        match = _RE_PATTERN.search(text)
        if match:
            entity["pattern"] = match.group(1)
        match = _RE_LOOPS.search(text)
        if match:
            entity["loops"] = int(match.group(1))

        match = _RE_SEGMENT.search(text)
        if match:
            entity["start"] = (float(match.group(1)), float(match.group(2)))
            entity["end"] = (float(match.group(3)), float(match.group(4)))
        else:
            quoted = _RE_QUOTED.search(text)
            if quoted:
                entity["text"] = quoted.group(1)
    except Exception:  # grammar is advisory; never crash a 400-unit sweep on one odd line
        return {"kind": "other", "layer": None, "handle": None}
    return entity


def _parse_histogram(text: str) -> dict[str, int]:
    hist: dict[str, int] = {}
    for chunk in (text or "").split(","):
        match = _RE_HIST_ITEM.match(chunk)
        if match:
            try:
                hist[match.group(1)] = int(match.group(2))
            except ValueError:
                continue
    return hist


def _parse_bbox(text: str) -> list[float] | None:
    values: list[float] = []
    for chunk in (text or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            values.append(float(chunk))
        except ValueError:
            return None
    return values or None


def parse_projection(prompt: str) -> dict[str, Any]:
    """Parse a def projection block. Unknown line shapes are tolerated."""
    doc: dict[str, Any] = {
        "def": None,
        "entity_count": None,
        "dxf_histogram": {},
        "layer_histogram": {},
        "bbox": None,
        "entities": [],
        "kind_counts": {},
        "other_lines": 0,
    }
    in_entities = False
    for raw in (prompt or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if _RE_SAMPLED.match(line.strip()):
            in_entities = True
            continue
        if line.lstrip().startswith("-") and in_entities:
            entity = parse_entity_line(line)
            doc["entities"].append(entity)
            kind = entity["kind"]
            doc["kind_counts"][kind] = doc["kind_counts"].get(kind, 0) + 1
            if kind == "other":
                doc["other_lines"] += 1
            continue
        stripped = line.strip()
        match = _RE_DEF_NAME.match(stripped)
        if match:
            doc["def"] = match.group(1)
            continue
        match = _RE_ENTITY_COUNT.match(stripped)
        if match:
            doc["entity_count"] = int(match.group(1))
            continue
        match = _RE_DXF_HIST.match(stripped)
        if match:
            doc["dxf_histogram"] = _parse_histogram(match.group(1))
            continue
        match = _RE_LAYER_HIST.match(stripped)
        if match:
            doc["layer_histogram"] = _parse_histogram(match.group(1))
            continue
        match = _RE_BBOX.match(stripped)
        if match:
            doc["bbox"] = _parse_bbox(match.group(1))
            continue
    return doc


def load_projections(shard_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """def -> parsed projection, plus a parse-coverage summary."""
    by_def: dict[str, dict[str, Any]] = {}
    stats = {"lines": 0, "parsed": 0, "no_def": 0, "collisions": 0, "other_entity_lines": 0}
    for shard in sorted(shard_dir.glob("shard_*.jsonl")):
        for row in _load_jsonl(shard):
            stats["lines"] += 1
            doc = parse_projection(row.get("prompt") or "")
            doc["unit_id"] = row.get("unit_id")
            stats["other_entity_lines"] += doc["other_lines"]
            def_name = doc.get("def")
            if not def_name:
                stats["no_def"] += 1
                continue
            stats["parsed"] += 1
            if def_name in by_def:
                stats["collisions"] += 1
                continue
            by_def[def_name] = doc
    return by_def, stats


# ------------------------------------------------------------------ detector side


def detector_signal(pair_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Continuous [0,1] detector signals for one def.

    max_conf is the primary signal: the detector's strongest evidence that this def
    contains a wall. Zero pairs -> 0.0. mean_conf is kept for a sensitivity check.
    """
    confs = [r.get("conf") for r in pair_rows]
    confs = [float(c) for c in confs if isinstance(c, (int, float))]
    return {
        "n_pairs": len(pair_rows),
        "max_conf": max(confs) if confs else 0.0,
        "mean_conf": (sum(confs) / len(confs)) if confs else 0.0,
    }


def _resolve_pair_keys(per_def: dict[str, Any]) -> dict[str, str | None]:
    """Mirror of e1_crosscheck's normalized-name resolution (ambiguous -> None)."""
    normalized: dict[str, str | None] = {}
    for def_name in per_def:
        if not isinstance(def_name, str) or not def_name:
            continue
        norm = _normalize_def_name(def_name)
        if norm not in normalized:
            normalized[norm] = def_name
        else:
            normalized[norm] = None
    return normalized


# ---------------------------------------------------------------- ranking helpers


def average_ranks(items: Sequence[tuple[str, float]]) -> dict[str, float]:
    """Average (tie-corrected) 1-based ranks, descending by value."""
    order = sorted(items, key=lambda kv: -kv[1])
    ranks: dict[str, float] = {}
    index = 0
    while index < len(order):
        end = index
        while end + 1 < len(order) and order[end + 1][1] == order[index][1]:
            end += 1
        avg = (index + end) / 2.0 + 1.0
        for pos in range(index, end + 1):
            ranks[order[pos][0]] = avg
        index = end + 1
    return ranks


def candidate_divergence(row: dict[str, Any]) -> str | None:
    """Mirrored from e1_crosscheck._candidate_divergence."""
    likelihood = row.get("wall_likelihood")
    if not isinstance(likelihood, (int, float)):
        return None
    if row.get("n_pairs", 0) == 0 and likelihood >= HIGH_LIKELIHOOD_CUTOFF:
        return "high_likelihood_zero_pairs"
    if row.get("n_pairs", 0) >= MANY_PAIRS_CUTOFF and likelihood <= LOW_LIKELIHOOD_CUTOFF:
        return "many_pairs_low_likelihood"
    return None


def score_divergence_original(row: dict[str, Any]) -> tuple[int, float, float, str]:
    """Mirrored from e1_crosscheck._score_divergence."""
    kind = row["divergence_kind"]
    if kind == "high_likelihood_zero_pairs":
        return (0, -float(row["wall_likelihood"]), 0.0, row["def"])
    return (1, -float(row["n_pairs"]), float(row["wall_likelihood"]), row["def"])


def rank_a_original(rows: Sequence[dict[str, Any]]) -> list[str]:
    """(a) The original gated lexicographic key."""
    candidates = [dict(r, divergence_kind=candidate_divergence(r)) for r in rows]
    candidates = [r for r in candidates if r["divergence_kind"]]
    candidates.sort(key=score_divergence_original)
    return [r["def"] for r in candidates]


def rank_b_absdiff(rows: Sequence[dict[str, Any]], signal_field: str = "max_conf") -> list[str]:
    """(b) |LLM wall_likelihood - detector signal|, ungated."""
    scored: list[tuple[float, str]] = []
    for row in rows:
        likelihood = row.get("wall_likelihood")
        if not isinstance(likelihood, (int, float)):
            continue
        scored.append((abs(float(likelihood) - float(row[signal_field])), row["def"]))
    scored.sort(key=lambda sv: (-sv[0], sv[1]))
    return [name for _, name in scored]


def rank_c_weighted_rankdiff(rows: Sequence[dict[str, Any]], signal_field: str = "max_conf") -> list[str]:
    """(c) wall_likelihood-weighted |rank_llm - rank_detector| / N."""
    usable = [r for r in rows if isinstance(r.get("wall_likelihood"), (int, float))]
    if not usable:
        return []
    rank_llm = average_ranks([(r["def"], float(r["wall_likelihood"])) for r in usable])
    rank_det = average_ranks([(r["def"], float(r[signal_field])) for r in usable])
    total = len(usable)
    scored: list[tuple[float, str]] = []
    for row in usable:
        name = row["def"]
        weighted = float(row["wall_likelihood"]) * abs(rank_llm[name] - rank_det[name]) / total
        scored.append((weighted, name))
    scored.sort(key=lambda sv: (-sv[0], sv[1]))
    return [name for _, name in scored]


def judge_subsets(judges: Sequence[str] = JUDGES, k: int = SUBSET_K) -> list[tuple[str, ...]]:
    return [tuple(c) for c in combinations(judges, k)]


def rank_d_bootstrap(
    rows: Sequence[dict[str, Any]],
    signal_field: str = "max_conf",
    top_n: int = TOP_N,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """(d) Bootstrap over judge subsets (5 choose 3).

    Each 3-judge subset yields a mean wall_likelihood per def, an absdiff ranking, and a
    top-N set. Defs are ranked by selection frequency across the 10 subsets. Averaging the
    divergence across subsets would collapse to the full-panel mean (each judge appears in
    the same number of subsets), so the bootstrap is consumed as *stability*, not location.
    """
    subsets = judge_subsets()
    per_def: dict[str, dict[str, Any]] = {
        r["def"]: {"selection_count": 0, "subset_divergences": [], "subset_likelihoods": []}
        for r in rows
    }
    for subset in subsets:
        scored: list[tuple[float, str]] = []
        for row in rows:
            values = [
                float(row["judges"][j])
                for j in subset
                if isinstance(row.get("judges", {}).get(j), (int, float))
            ]
            if not values:
                continue
            likelihood = sum(values) / len(values)
            divergence = abs(likelihood - float(row[signal_field]))
            per_def[row["def"]]["subset_divergences"].append(divergence)
            per_def[row["def"]]["subset_likelihoods"].append(likelihood)
            scored.append((divergence, row["def"]))
        scored.sort(key=lambda sv: (-sv[0], sv[1]))
        for _, name in scored[:top_n]:
            per_def[name]["selection_count"] += 1

    for stats in per_def.values():
        stats["mean_divergence"] = _mean(stats["subset_divergences"])
        stats["mean_likelihood"] = _mean(stats["subset_likelihoods"])
        divs = stats["subset_divergences"]
        stats["divergence_spread"] = (max(divs) - min(divs)) if divs else None
        stats.pop("subset_divergences", None)
        stats.pop("subset_likelihoods", None)

    ranked = sorted(
        per_def.items(),
        key=lambda kv: (
            -kv[1]["selection_count"],
            -(kv[1]["mean_divergence"] if kv[1]["mean_divergence"] is not None else -1.0),
            kv[0],
        ),
    )
    return [name for name, _ in ranked], per_def


# ------------------------------------------------------------------- verdict math


def jaccard_matrix(top_sets: dict[str, set[str]]) -> tuple[dict[str, dict[str, float]], list[dict[str, Any]], float]:
    names = list(top_sets)
    matrix = {a: {b: _jaccard(top_sets[a], top_sets[b]) for b in names} for a in names}
    pairs: list[dict[str, Any]] = []
    for lhs, rhs in combinations(names, 2):
        pairs.append(
            {
                "pair": [lhs, rhs],
                "jaccard": matrix[lhs][rhs],
                "intersection": len(top_sets[lhs] & top_sets[rhs]),
                "union": len(top_sets[lhs] | top_sets[rhs]),
            }
        )
    mean_pairwise = _mean([p["jaccard"] for p in pairs]) or 0.0
    return matrix, pairs, mean_pairwise


def verdict_for(mean_pairwise: float) -> str:
    if mean_pairwise < ARTIFACT_BAND:
        return "SORT_ARTIFACT_CONFIRMED"
    if mean_pairwise > STABLE_BAND:
        return "STABLE_PHENOMENON"
    return "MIXED"


# ------------------------------------------------------------------- build & run


def build_universe(
    v0_rows: Sequence[dict[str, Any]],
    judge_data: dict[str, dict[str, dict[str, Any]]],
    pair_doc: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Join v0 baseline + annot_v1 judges + detector pairs on def name."""
    per_def = pair_doc.get("per_def") if isinstance(pair_doc.get("per_def"), dict) else {}
    normalized = _resolve_pair_keys(per_def)

    rows: list[dict[str, Any]] = []
    used_pair_keys: set[str] = set()
    coverage = {
        "v0_rows": len(v0_rows),
        "pairs_defs": len(per_def),
        "judges": {j: len(d) for j, d in judge_data.items()},
        "dropped_no_def": 0,
        "dropped_no_pairs": 0,
        "dropped_dup_pair_key": 0,
        "dropped_no_judges": 0,
    }

    for orn_row in v0_rows:
        parsed = orn_row.get("parsed") if isinstance(orn_row.get("parsed"), dict) else {}
        def_name = parsed.get("def")
        if not isinstance(def_name, str) or not def_name.strip():
            coverage["dropped_no_def"] += 1
            continue
        pair_key = def_name if def_name in per_def else normalized.get(_normalize_def_name(def_name))
        if pair_key is None:
            coverage["dropped_no_pairs"] += 1
            continue
        if pair_key in used_pair_keys:
            coverage["dropped_dup_pair_key"] += 1
            continue

        judges = {}
        for judge, by_def in judge_data.items():
            item = by_def.get(def_name)
            if item is None:
                continue
            value = item.get("wall_likelihood")
            if isinstance(value, (int, float)):
                judges[judge] = float(value)
        if len(judges) != len(judge_data):
            coverage["dropped_no_judges"] += 1
            continue

        used_pair_keys.add(pair_key)
        pair_rows = per_def.get(pair_key) or []
        signals = detector_signal(pair_rows)
        h_llm = _handle_set(parsed.get("wall_line_handles"))
        h_det = _pair_handle_set(pair_rows)
        row = {
            "def": def_name,
            "wall_likelihood": parsed.get("wall_likelihood"),
            "role": parsed.get("role"),
            "judges": judges,
            "judge_mean": _mean(sorted(judges.values())),
            "handle_jaccard": _jaccard(h_llm, h_det),
        }
        row.update(signals)
        row["divergence_kind"] = candidate_divergence(row)
        rows.append(row)

    coverage["universe"] = len(rows)
    return rows, coverage


def _load_judges(judge_root: Path, judges: Sequence[str]) -> dict[str, dict[str, dict[str, Any]]]:
    data: dict[str, dict[str, dict[str, Any]]] = {}
    for judge in judges:
        by_def: dict[str, dict[str, Any]] = {}
        for shard in sorted((judge_root / judge).glob("shard_*.json")):
            items = _load_json(shard)
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and isinstance(item.get("def"), str):
                    by_def.setdefault(item["def"], item)
        data[judge] = by_def
    return data


def _original_parity(crosscheck_path: Path, v0_path: Path, pairs_path: Path, mine: list[str]) -> dict[str, Any]:
    """Run the untouched original module and compare its top-20 against key (a)."""
    try:
        spec = importlib.util.spec_from_file_location("e1_crosscheck_ref", crosscheck_path)
        if spec is None or spec.loader is None:
            return {"status": "unavailable", "reason": "spec_failed"}
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report = module.run(v0_path, pairs_path)
        original = list(report["summary"]["top20_divergent"])
    except Exception as exc:  # parity is diagnostic; never fail the probe on it
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}"}
    return {
        "status": "ok",
        "original_top20": original,
        "identical_order": original == mine,
        "set_jaccard": _jaccard(set(original), set(mine)),
        "note": (
            "key (a) is restricted to the 3-way common universe; the original ranks its own "
            "v0-join universe. Set jaccard < 1.0 means the universe restriction moved members."
        ),
    }


def _factorial_control(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Decisive control: key (d) differs from (a)-(c) on TWO factors at once.

    (d) changes both the ranking key AND the LLM side (v0 ornith -> annot_v1 panel), so a
    low a-vs-d Jaccard cannot by itself attribute the instability to the sort key. This
    crosses {key form} x {LLM side} so each factor is isolated:

      * key-form effect  = mean Jaccard across keys with the LLM side held fixed
      * llm-side effect  = mean Jaccard across LLM sides with the key form held fixed
    """
    rows_panel = [dict(r, wall_likelihood=r["judge_mean"]) for r in rows]
    sides: dict[str, Sequence[dict[str, Any]]] = {"v0": rows, "panel": rows_panel}
    forms = {
        "a_original": rank_a_original,
        "b_absdiff": rank_b_absdiff,
        "c_wrankdiff": rank_c_weighted_rankdiff,
    }
    tops: dict[str, set[str]] = {}
    for side, side_rows in sides.items():
        for form, fn in forms.items():
            tops[f"{form}@{side}"] = set(fn(side_rows)[:TOP_N])

    key_form_pairs: list[dict[str, Any]] = []
    for side in sides:
        for lhs, rhs in combinations(forms, 2):
            key_form_pairs.append(
                {
                    "held_fixed": f"llm_side={side}",
                    "pair": [lhs, rhs],
                    "jaccard": _jaccard(tops[f"{lhs}@{side}"], tops[f"{rhs}@{side}"]),
                }
            )
    llm_side_pairs: list[dict[str, Any]] = []
    for form in forms:
        llm_side_pairs.append(
            {
                "held_fixed": f"key={form}",
                "pair": ["v0", "panel"],
                "jaccard": _jaccard(tops[f"{form}@v0"], tops[f"{form}@panel"]),
            }
        )

    gate_population = {}
    for side, side_rows in sides.items():
        kinds = [candidate_divergence(r) for r in side_rows]
        gate_population[side] = {
            "gated": sum(1 for k in kinds if k),
            "tier0_high_likelihood_zero_pairs": sum(1 for k in kinds if k == "high_likelihood_zero_pairs"),
            "tier1_many_pairs_low_likelihood": sum(1 for k in kinds if k == "many_pairs_low_likelihood"),
        }

    signed = {}
    for side, side_rows in sides.items():
        signed[side] = {
            "llm_over_calls": sum(1 for r in side_rows if float(r["wall_likelihood"]) - float(r["max_conf"]) > 0.5),
            "detector_over_calls": sum(1 for r in side_rows if float(r["max_conf"]) - float(r["wall_likelihood"]) > 0.5),
            "mean_likelihood": _mean([float(r["wall_likelihood"]) for r in side_rows]),
        }

    key_form_effect = _mean([p["jaccard"] for p in key_form_pairs]) or 0.0
    llm_side_effect = _mean([p["jaccard"] for p in llm_side_pairs]) or 0.0
    by_side = {
        side: _mean([p["jaccard"] for p in key_form_pairs if p["held_fixed"] == f"llm_side={side}"]) or 0.0
        for side in sides
    }
    return {
        "key_form_pairs": key_form_pairs,
        "llm_side_pairs": llm_side_pairs,
        "key_form_effect_mean_jaccard": key_form_effect,
        "key_form_effect_by_side": by_side,
        "llm_side_effect_mean_jaccard": llm_side_effect,
        "interaction_spread": abs(by_side.get("v0", 0.0) - by_side.get("panel", 0.0)),
        "gate_population": gate_population,
        "signed_divergence": signed,
        "interpretation": (
            "The two factors interact, so neither marginal mean stands alone. Read "
            "key_form_effect_by_side first: if the top-20 is sort-key-robust under one annotator "
            "and sort-key-fragile under another, the pooled key_form_effect is an average across "
            "regimes that describes neither. A large interaction_spread means the sort key's "
            "apparent robustness is contingent on the annotator, not a property of the data."
        ),
    }


def _tier_diagnostics(rows: Sequence[dict[str, Any]], projections: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Is 'high_likelihood_zero_pairs' a representation artifact rather than disagreement?

    The projection's bbox is derived 'from LINE start/end', and the detector pairs LINE
    segments. A def whose geometry is LWPOLYLINE/ARC/SPLINE-based exposes no LINE
    coordinates, so the detector can find zero pairs regardless of whether a wall exists.
    """

    def profile(subset: Sequence[dict[str, Any]]) -> dict[str, Any]:
        if not subset:
            return {"n": 0}
        line_counts: list[float] = []
        zero_line = 0
        has_poly = 0
        no_proj = 0
        for row in subset:
            doc = projections.get(row["def"])
            if doc is None:
                no_proj += 1
                continue
            hist = doc.get("dxf_histogram") or {}
            lines = float(hist.get("LINE", 0))
            line_counts.append(lines)
            if lines == 0:
                zero_line += 1
            if any(hist.get(k) for k in ("LWPOLYLINE", "ARC", "SPLINE", "ELLIPSE")):
                has_poly += 1
        seen = len(subset) - no_proj
        return {
            "n": len(subset),
            "projection_missing": no_proj,
            "mean_LINE_count": _mean(line_counts),
            "zero_LINE_frac": (zero_line / seen) if seen else None,
            "curve_or_polyline_frac": (has_poly / seen) if seen else None,
        }

    tier0 = [r for r in rows if r["divergence_kind"] == "high_likelihood_zero_pairs"]
    tier1 = [r for r in rows if r["divergence_kind"] == "many_pairs_low_likelihood"]
    rest = [r for r in rows if not r["divergence_kind"]]
    return {
        "high_likelihood_zero_pairs": profile(tier0),
        "many_pairs_low_likelihood": profile(tier1),
        "non_candidate": profile(rest),
        "interpretation_hint": (
            "If zero_LINE_frac / curve_or_polyline_frac is much higher for "
            "high_likelihood_zero_pairs than for non_candidate defs, the tier is at least "
            "partly a projection-representation artifact, not an LLM-vs-detector conflict."
        ),
    }


def run(
    v0_path: Path,
    pairs_path: Path,
    judge_root: Path,
    shard_dir: Path,
    cluster_path: Path | None = None,
    crosscheck_path: Path | None = None,
    judges: Sequence[str] = JUDGES,
) -> dict[str, Any]:
    v0_rows = _load_jsonl(v0_path)
    pair_doc = _load_json(pairs_path)
    judge_data = _load_judges(judge_root, judges)
    rows, coverage = build_universe(v0_rows, judge_data, pair_doc)

    projections, proj_stats = ({}, {})
    if shard_dir.exists():
        projections, proj_stats = load_projections(shard_dir)

    rankings: dict[str, list[str]] = {
        "a_original": rank_a_original(rows),
        "b_absdiff": rank_b_absdiff(rows),
        "c_wrankdiff": rank_c_weighted_rankdiff(rows),
    }
    rankings["d_bootstrap"], bootstrap_stats = rank_d_bootstrap(rows)

    top_sets = {key: set(ranked[:TOP_N]) for key, ranked in rankings.items()}
    matrix, pairs, mean_pairwise = jaccard_matrix(top_sets)
    verdict = verdict_for(mean_pairwise)

    # -- decomposition: gate vs ordering --------------------------------------
    gated = {r["def"] for r in rows if r["divergence_kind"]}
    tier0 = {r["def"] for r in rows if r["divergence_kind"] == "high_likelihood_zero_pairs"}
    decomposition = {
        "n_candidates_gated": len(gated),
        "n_tier0_high_likelihood_zero_pairs": len(tier0),
        "n_tier1_many_pairs_low_likelihood": len(gated) - len(tier0),
        "key_a_top20_all_tier0": bool(top_sets["a_original"] <= tier0),
        "gate_passing_frac": {
            key: (len(top_sets[key] & gated) / len(top_sets[key])) if top_sets[key] else None
            for key in rankings
        },
        "note": (
            "gate_passing_frac is how much of each key's top-20 the original gate would have "
            "even admitted. A low value for (b)/(c)/(d) means the hard gate -- not the tie "
            "ordering -- is what selects the original top-20."
        ),
    }

    # -- sensitivity: does (b) depend on the detector-signal definition? -------
    b_meanconf = rank_b_absdiff(rows, signal_field="mean_conf")
    sensitivity = {
        "b_absdiff_maxconf_vs_meanconf_jaccard": _jaccard(top_sets["b_absdiff"], set(b_meanconf[:TOP_N])),
        "note": "detector_signal primary = max conf over pair rows; secondary = mean conf.",
    }

    # -- bootstrap stability ---------------------------------------------------
    freq_hist: dict[str, int] = {}
    for stats in bootstrap_stats.values():
        bucket = str(stats["selection_count"])
        freq_hist[bucket] = freq_hist.get(bucket, 0) + 1
    selected_any = [name for name, s in bootstrap_stats.items() if s["selection_count"] > 0]
    unanimous = [name for name, s in bootstrap_stats.items() if s["selection_count"] == len(judge_subsets())]
    bootstrap_summary = {
        "n_subsets": len(judge_subsets()),
        "subsets": ["+".join(s) for s in judge_subsets()],
        "selection_count_histogram": dict(sorted(freq_hist.items(), key=lambda kv: -int(kv[0]))),
        "n_defs_selected_in_any_subset": len(selected_any),
        "n_defs_selected_in_all_subsets": len(unanimous),
        "churn_ratio": (len(selected_any) / TOP_N) if TOP_N else None,
        "note": (
            "churn_ratio = distinct defs that entered any subset's top-20, divided by 20. "
            "1.0 means the panel choice never changes the top-20; higher means it does."
        ),
    }

    # -- cross-reference the E1 cluster probe ---------------------------------
    cluster_xref: dict[str, Any] = {"status": "skipped"}
    if cluster_path is not None and cluster_path.exists():
        try:
            cluster = _load_json(cluster_path)
            full_split = set(cluster.get("full_split_defs") or [])
            soft_split = set(cluster.get("soft_split_defs") or [])
            cluster_xref = {
                "status": "ok",
                "n_full_split": len(full_split),
                "n_soft_split": len(soft_split),
                "overlap": {
                    key: {
                        "full_split": len(top_sets[key] & full_split),
                        "soft_split": len(top_sets[key] & soft_split),
                    }
                    for key in rankings
                },
            }
        except Exception as exc:
            cluster_xref = {"status": "error", "reason": f"{type(exc).__name__}: {exc}"}

    parity: dict[str, Any] = {"status": "skipped"}
    if crosscheck_path is not None and crosscheck_path.exists():
        parity = _original_parity(crosscheck_path, v0_path, pairs_path, rankings["a_original"][:TOP_N])

    per_def_out = []
    for row in sorted(rows, key=lambda r: r["def"]):
        stats = bootstrap_stats.get(row["def"], {})
        per_def_out.append(
            {
                "def": row["def"],
                "wall_likelihood_v0": row["wall_likelihood"],
                "judge_mean_v1": row["judge_mean"],
                "n_pairs": row["n_pairs"],
                "detector_max_conf": row["max_conf"],
                "detector_mean_conf": row["mean_conf"],
                "handle_jaccard": row["handle_jaccard"],
                "divergence_kind": row["divergence_kind"],
                "bootstrap_selection_count": stats.get("selection_count"),
                "bootstrap_mean_divergence": stats.get("mean_divergence"),
                "ranks": {key: (rankings[key].index(row["def"]) + 1 if row["def"] in rankings[key] else None) for key in rankings},
            }
        )

    return {
        "schema": SCHEMA,
        "verdict": verdict,
        "mean_pairwise_jaccard_top20": mean_pairwise,
        "bands": {"artifact_below": ARTIFACT_BAND, "stable_above": STABLE_BAND},
        "keys": {
            "a_original": "mirrored _score_divergence: gate + lexicographic tiers (kind, likelihood, n_pairs)",
            "b_absdiff": "|v0 wall_likelihood - detector max_conf|, ungated",
            "c_wrankdiff": "v0 wall_likelihood * |rank_llm - rank_detector| / N",
            "d_bootstrap": "annot_v1 judges, 5C3=10 subsets, ranked by top-20 selection frequency",
        },
        "coverage": coverage,
        "projection_parse": proj_stats,
        "top20": {key: rankings[key][:TOP_N] for key in rankings},
        "jaccard_matrix": matrix,
        "pairwise": pairs,
        "decomposition": decomposition,
        "factorial_control": _factorial_control(rows),
        "sensitivity": sensitivity,
        "bootstrap": bootstrap_summary,
        "tier_diagnostics": _tier_diagnostics(rows, projections),
        "cluster_xref": cluster_xref,
        "original_parity": parity,
        "per_def": per_def_out,
    }


# ---------------------------------------------------------------------- markdown


def _fmt(value: Any, spec: str = ".3f") -> str:
    """Format a number, tolerating None (degenerate/empty universes)."""
    return format(value, spec) if isinstance(value, (int, float)) else "—"


def render_markdown(report: dict[str, Any]) -> str:
    keys = list(report["top20"])
    lines = [
        "# E2 S1-D — Sort-key artifact probe",
        "",
        f"**VERDICT: {report['verdict']}** "
        f"(mean pairwise Jaccard of top-20 = {report['mean_pairwise_jaccard_top20']:.4f}; "
        f"<{report['bands']['artifact_below']} artifact, >{report['bands']['stable_above']} stable)",
        "",
        "## Question",
        "",
        "Is the E1 'divergent top-20' a property of the drawings, or of the `_score_divergence`",
        "sort design in `reports/e1/panel_20260717/evidence/e1_crosscheck.py`?",
        "",
        "## Ranking keys",
        "",
        "| key | definition |",
        "| --- | --- |",
    ]
    for key, desc in report["keys"].items():
        lines.append(f"| `{key}` | {desc} |")

    cov = report["coverage"]
    lines += [
        "",
        "## Universe",
        "",
        f"- Controlled universe (v0 ∩ 5 judges ∩ detector pairs): **{cov['universe']}** defs",
        f"- v0 rows: {cov['v0_rows']} · detector defs: {cov['pairs_defs']}",
        f"- dropped: no_def={cov['dropped_no_def']} · no_pairs={cov['dropped_no_pairs']} · "
        f"dup_pair_key={cov['dropped_dup_pair_key']} · missing_judge={cov['dropped_no_judges']}",
        "",
        "## Top-20 Jaccard matrix",
        "",
        "| | " + " | ".join(f"`{k}`" for k in keys) + " |",
        "| --- | " + " | ".join("---:" for _ in keys) + " |",
    ]
    for lhs in keys:
        cells = " | ".join(f"{report['jaccard_matrix'][lhs][rhs]:.3f}" for rhs in keys)
        lines.append(f"| `{lhs}` | {cells} |")

    lines += ["", "### Pairwise detail", "", "| pair | Jaccard | ∩ | ∪ |", "| --- | ---: | ---: | ---: |"]
    for pair in report["pairwise"]:
        lines.append(
            f"| `{pair['pair'][0]}` vs `{pair['pair'][1]}` | {pair['jaccard']:.3f} | "
            f"{pair['intersection']} | {pair['union']} |"
        )

    dec = report["decomposition"]
    lines += [
        "",
        "## Decomposition — gate vs ordering",
        "",
        f"- Gated candidates: **{dec['n_candidates_gated']}** of {cov['universe']} defs "
        f"(tier0 high_likelihood_zero_pairs = {dec['n_tier0_high_likelihood_zero_pairs']}, "
        f"tier1 many_pairs_low_likelihood = {dec['n_tier1_many_pairs_low_likelihood']})",
        f"- Original top-20 lies entirely inside tier0: **{dec['key_a_top20_all_tier0']}**",
        "",
        "| key | fraction of its top-20 the original gate would admit |",
        "| --- | ---: |",
    ]
    for key, frac in dec["gate_passing_frac"].items():
        lines.append(f"| `{key}` | {frac:.3f} |" if frac is not None else f"| `{key}` | n/a |")
    lines += ["", f"> {dec['note']}"]

    ctl = report["factorial_control"]
    lines += [
        "",
        "## Factorial control — sort key vs annotator",
        "",
        "Key (d) changes two things at once (the ranking key *and* the LLM side), so the low",
        "a-vs-d Jaccard above cannot on its own blame the sort key. Crossing {key form} x",
        "{LLM side} separates them:",
        "",
        f"- **Key-form effect** (swap the key, hold the annotator): pooled mean Jaccard = "
        f"**{ctl['key_form_effect_mean_jaccard']:.3f}** — but this pools two regimes, see below",
        "    - under annotator `v0`: **"
        + _fmt(ctl["key_form_effect_by_side"].get("v0"))
        + "** (sort key barely moves the top-20)",
        "    - under annotator `panel`: **"
        + _fmt(ctl["key_form_effect_by_side"].get("panel"))
        + "** (sort key almost entirely determines the top-20)",
        f"    - interaction spread = **{ctl['interaction_spread']:.3f}**",
        f"- **Annotator effect** (swap the annotator, hold the key): mean Jaccard = "
        f"**{ctl['llm_side_effect_mean_jaccard']:.3f}**",
        "",
        "| held fixed | compared | Jaccard |",
        "| --- | --- | ---: |",
    ]
    for pair in ctl["key_form_pairs"] + ctl["llm_side_pairs"]:
        lines.append(f"| {pair['held_fixed']} | `{pair['pair'][0]}` vs `{pair['pair'][1]}` | {pair['jaccard']:.3f} |")

    lines += [
        "",
        "### Gate population under each annotator",
        "",
        "| annotator | gated candidates | tier0 (high_likelihood_zero_pairs) | tier1 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for side, pop in ctl["gate_population"].items():
        lines.append(
            f"| {side} | {pop['gated']} | {pop['tier0_high_likelihood_zero_pairs']} | "
            f"{pop['tier1_many_pairs_low_likelihood']} |"
        )
    lines += [
        "",
        "### Signed divergence — which side over-calls walls?",
        "",
        "| annotator | LLM says wall, detector silent | detector says wall, LLM silent | mean likelihood |",
        "| --- | ---: | ---: | ---: |",
    ]
    for side, sig in ctl["signed_divergence"].items():
        lines.append(
            f"| {side} | {sig['llm_over_calls']} | {sig['detector_over_calls']} | "
            f"{_fmt(sig['mean_likelihood'])} |"
        )
    lines += ["", f"> {ctl['interpretation']}"]

    boot = report["bootstrap"]
    lines += [
        "",
        "## Judge-subset bootstrap (5 choose 3)",
        "",
        f"- Subsets: {boot['n_subsets']}",
        f"- Distinct defs entering any subset's top-20: **{boot['n_defs_selected_in_any_subset']}** "
        f"(churn ratio {boot['churn_ratio']:.2f}× vs a stable 20)",
        f"- Defs present in all {boot['n_subsets']} subsets' top-20: **{boot['n_defs_selected_in_all_subsets']}**",
        f"- Selection-count histogram (count → #defs): `{json.dumps(boot['selection_count_histogram'])}`",
        "",
        f"> {boot['note']}",
    ]

    tier = report["tier_diagnostics"]
    lines += [
        "",
        "## Tier diagnostic — is `high_likelihood_zero_pairs` a representation artifact?",
        "",
        "The projection's bbox is derived *from LINE start/end* and the detector pairs LINE",
        "segments, so a def drawn with LWPOLYLINE/ARC/SPLINE exposes no pairable coordinates.",
        "",
        "| def group | n | mean LINE count | zero-LINE frac | curve/polyline frac |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for group in ("high_likelihood_zero_pairs", "many_pairs_low_likelihood", "non_candidate"):
        prof = tier[group]
        if not prof.get("n"):
            lines.append(f"| {group} | 0 | — | — | — |")
            continue
        lines.append(
            f"| {group} | {prof['n']} | {_fmt(prof['mean_LINE_count'], '.2f')} | "
            f"{_fmt(prof['zero_LINE_frac'])} | {_fmt(prof['curve_or_polyline_frac'])} |"
        )
    lines += ["", f"> {tier['interpretation_hint']}"]

    sens = report["sensitivity"]
    lines += [
        "",
        "## Sensitivity & parity",
        "",
        f"- Key (b) under max-conf vs mean-conf detector signal: Jaccard = "
        f"{sens['b_absdiff_maxconf_vs_meanconf_jaccard']:.3f}",
    ]
    parity = report["original_parity"]
    if parity.get("status") == "ok":
        lines.append(
            f"- Parity vs untouched `e1_crosscheck.run()`: identical_order="
            f"**{parity['identical_order']}**, set Jaccard={parity['set_jaccard']:.3f}"
        )
    else:
        lines.append(f"- Parity vs original: {parity.get('status')} ({parity.get('reason', '')})")

    xref = report["cluster_xref"]
    if xref.get("status") == "ok":
        lines += [
            "",
            "## Cross-reference — E1 cluster probe",
            "",
            f"- full_split_defs: {xref['n_full_split']} · soft_split_defs: {xref['n_soft_split']}",
            "",
            "| key | ∩ full_split | ∩ soft_split |",
            "| --- | ---: | ---: |",
        ]
        for key, counts in xref["overlap"].items():
            lines.append(f"| `{key}` | {counts['full_split']} | {counts['soft_split']} |")

    lines += ["", "## Top-20 per key", ""]
    for key in keys:
        lines.append(f"- **`{key}`**: {', '.join(report['top20'][key]) or '(none)'}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------- selftest


def _selftest() -> int:
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        status = "PASS" if condition else "FAIL"
        print(f"  [{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
        if not condition:
            failures.append(name)

    print("== 1. projection grammar (verbatim card samples) ==")
    samples = [
        ("- LINE layer=DIM handle=8B52 (44248.83,24580.207)->(44248.83,22920.207)", "LINE", "DIM", "8B52"),
        ("- INSERT layer=DIM handle=8B55 block=DIMDOT", "INSERT", "DIM", "8B55"),
        ("- MTEXT layer=DIM handle=8B57 '\\A1;3280'", "MTEXT", "DIM", "8B57"),
        ("- POINT layer=DEFPOINTS handle=8B58", "POINT", "DEFPOINTS", "8B58"),
        ("- LWPOLYLINE layer=X-... handle=4376 vertices=5", "LWPOLYLINE", "X-...", "4376"),
        ("- WIPEOUT layer=0 handle=4855", "WIPEOUT", "0", "4855"),
        ("- SPLINE layer=... handle=1BCC", "SPLINE", "...", "1BCC"),
        ("- HATCH layer=... handle=1BCE pattern=SOLID loops=2", "HATCH", "...", "1BCE"),
        ("- TEXT layer=DEFPOINTS handle=3AE '101 dong'", "TEXT", "DEFPOINTS", "3AE"),
        ("- ARC layer=... handle=820F", "ARC", "...", "820F"),
        ("- CIRCLE layer=... handle=3288 radius=81", "CIRCLE", "...", "3288"),
        ("- ELLIPSE layer=... handle=6B10", "ELLIPSE", "...", "6B10"),
        ("- 3DFACE layer=... handle=1DA2", "3DFACE", "...", "1DA2"),
    ]
    for raw, kind, layer, handle in samples:
        got = parse_entity_line(raw)
        check(
            f"grammar {kind}",
            got["kind"] == kind and got["layer"] == layer and got["handle"] == handle,
            f"got {got}",
        )
    line = parse_entity_line(samples[0][0])
    check("LINE coords", line.get("start") == (44248.83, 24580.207) and line.get("end") == (44248.83, 22920.207), str(line))
    check("INSERT block", parse_entity_line(samples[1][0]).get("block") == "DIMDOT")
    check("MTEXT text", parse_entity_line(samples[2][0]).get("text") == "\\A1;3280")
    check("LWPOLYLINE vertices", parse_entity_line(samples[4][0]).get("vertices") == 5)
    check("HATCH pattern/loops", parse_entity_line(samples[7][0]).get("pattern") == "SOLID" and parse_entity_line(samples[7][0]).get("loops") == 2)
    check("TEXT with space", parse_entity_line(samples[8][0]).get("text") == "101 dong")
    check("CIRCLE radius", parse_entity_line(samples[10][0]).get("radius") == 81.0)

    print("== 2. unknown / hostile line shapes -> kind='other', never crash ==")
    for raw in [
        "- BLARGH layer=Z handle=DEAD extra=1",
        "- ",
        "",
        "-",
        "garbage with no dashes at all",
        "- LINE layer=DIM handle=8B52 (nan,nan)->(",
        "- HATCH layer=A handle=B pattern=SOLID loops=notanumber",
        "- LWPOLYLINE layer=A handle=B vertices=",
        "- \x00\x01 binary junk",
    ]:
        try:
            got = parse_entity_line(raw)
            ok = isinstance(got, dict) and "kind" in got
        except Exception as exc:
            ok = False
            got = f"raised {exc}"
        check(f"tolerates {raw[:28]!r}", ok, str(got))
    check("unknown kind is other", parse_entity_line("- BLARGH layer=Z handle=DEAD")["kind"] == "other")
    check("unknown still yields handle", parse_entity_line("- BLARGH layer=Z handle=DEAD")["handle"] == "DEAD")

    print("== 3. handle polymorphism (str | {handle,reason}) ==")
    mixed = ["8B52", {"handle": "8B53", "reason": "parallel"}, {"reason": "no handle"}, None, "", "  8B54  "]
    check("handle set", _handle_set(mixed) == {"8B52", "8B53", "8B54"}, str(_handle_set(mixed)))
    check("handle non-list", _handle_set(None) == set())

    print("== 4. rank / jaccard math ==")
    ranks = average_ranks([("a", 1.0), ("b", 1.0), ("c", 0.5)])
    check("tie -> average rank", ranks == {"a": 1.5, "b": 1.5, "c": 3.0}, str(ranks))
    check("jaccard disjoint", _jaccard({"a"}, {"b"}) == 0.0)
    check("jaccard identical", _jaccard({"a"}, {"a"}) == 1.0)
    check("jaccard empty-empty", _jaccard(set(), set()) == 1.0)
    check("jaccard half", abs(_jaccard({"a", "b"}, {"b", "c"}) - 1 / 3) < 1e-12)

    print("== 5. verdict banding (incl. boundaries) ==")
    check("0.39 -> artifact", verdict_for(0.39) == "SORT_ARTIFACT_CONFIRMED")
    check("0.40 boundary -> MIXED", verdict_for(0.40) == "MIXED")
    check("0.70 boundary -> MIXED", verdict_for(0.70) == "MIXED")
    check("0.71 -> stable", verdict_for(0.71) == "STABLE_PHENOMENON")
    check("0.0 -> artifact", verdict_for(0.0) == "SORT_ARTIFACT_CONFIRMED")
    check("1.0 -> stable", verdict_for(1.0) == "STABLE_PHENOMENON")

    print("== 6. subsets ==")
    subs = judge_subsets()
    check("5C3 == 10 subsets", len(subs) == 10, str(len(subs)))
    check("all subsets size 3", all(len(s) == 3 for s in subs))
    check("subsets distinct", len({frozenset(s) for s in subs}) == 10)

    print("== 7. original key (a) semantics on a controlled fixture ==")
    fixture_rows = [
        {"def": "*T0_HI", "wall_likelihood": 0.95, "n_pairs": 0, "max_conf": 0.0, "mean_conf": 0.0},
        {"def": "*T0_LO", "wall_likelihood": 0.70, "n_pairs": 0, "max_conf": 0.0, "mean_conf": 0.0},
        {"def": "*T1_MANY", "wall_likelihood": 0.10, "n_pairs": 30, "max_conf": 0.9, "mean_conf": 0.8},
        {"def": "*T1_FEW", "wall_likelihood": 0.10, "n_pairs": 5, "max_conf": 0.9, "mean_conf": 0.8},
        {"def": "*NEUTRAL", "wall_likelihood": 0.50, "n_pairs": 2, "max_conf": 0.6, "mean_conf": 0.6},
        {"def": "*NEAR_MISS", "wall_likelihood": 0.69, "n_pairs": 0, "max_conf": 0.0, "mean_conf": 0.0},
    ]
    ranked_a = rank_a_original(fixture_rows)
    check(
        "tier0 precedes tier1, likelihood desc",
        ranked_a == ["*T0_HI", "*T0_LO", "*T1_MANY", "*T1_FEW"],
        str(ranked_a),
    )
    check("ungated defs excluded entirely", "*NEUTRAL" not in ranked_a and "*NEAR_MISS" not in ranked_a)
    check("gate is a hard cliff at 0.7", candidate_divergence(fixture_rows[5]) is None)
    check("0.70 exactly is admitted", candidate_divergence(fixture_rows[1]) == "high_likelihood_zero_pairs")

    print("== 8. key (b)/(c) semantics ==")
    ranked_b = rank_b_absdiff(fixture_rows)
    check("b ranks max |likelihood-signal| first", ranked_b[0] == "*T0_HI", str(ranked_b))
    check("b ranks all defs (ungated)", len(ranked_b) == len(fixture_rows), str(len(ranked_b)))
    check("b is deterministic under ties", rank_b_absdiff(fixture_rows) == ranked_b)
    ranked_c = rank_c_weighted_rankdiff(fixture_rows)
    check("c ranks all defs", len(ranked_c) == len(fixture_rows), str(len(ranked_c)))
    check("c suppresses zero-likelihood defs", ranked_c[0] in {"*T0_HI", "*T0_LO", "*NEAR_MISS"}, str(ranked_c))
    nonnum = rank_b_absdiff([{"def": "*X", "wall_likelihood": None, "max_conf": 0.0, "n_pairs": 0}])
    check("b skips non-numeric likelihood", nonnum == [], str(nonnum))
    check("c on empty input", rank_c_weighted_rankdiff([]) == [])

    print("== 9. key (d) bootstrap ==")
    boot_rows = [
        {"def": f"*B{i:02d}", "judges": {j: (0.9 if i < 25 else 0.05) for j in JUDGES}, "max_conf": 0.0, "n_pairs": 0}
        for i in range(30)
    ]
    ranked_d, stats_d = rank_d_bootstrap(boot_rows, top_n=5)
    check("d ranks all defs", len(ranked_d) == 30, str(len(ranked_d)))
    check("d picks high-divergence defs", all(n.startswith("*B0") for n in ranked_d[:5]), str(ranked_d[:5]))
    check("unanimous judges -> selection_count 10", stats_d[ranked_d[0]]["selection_count"] == 10, str(stats_d[ranked_d[0]]))
    check("d spread is 0 when judges agree", stats_d[ranked_d[0]]["divergence_spread"] == 0.0)
    # a def the panel is split on should churn across subsets
    split_rows = [
        {"def": "*SPLIT", "judges": {"opus48_max": 1.0, "fable5_high": 1.0, "sol56_xhigh": 0.0, "sonnet5_xhigh": 0.0, "grok45_xhigh": 0.0}, "max_conf": 0.0, "n_pairs": 0},
        {"def": "*STEADY", "judges": {j: 0.5 for j in JUDGES}, "max_conf": 0.0, "n_pairs": 0},
    ]
    _, split_stats = rank_d_bootstrap(split_rows, top_n=1)
    check("split panel -> nonzero spread", split_stats["*SPLIT"]["divergence_spread"] > 0.0, str(split_stats["*SPLIT"]))
    check("split panel churns in/out of top-1", 0 < split_stats["*SPLIT"]["selection_count"] < 10, str(split_stats["*SPLIT"]["selection_count"]))

    print("== 10. end-to-end on a synthetic fixture (temp dir, never the repo) ==")
    with tempfile.TemporaryDirectory(prefix="s1d_selftest_") as tmp:
        root = Path(tmp)
        shard_dir = root / "shards"
        shard_dir.mkdir()
        judge_root = root / "judges"
        n_defs = 40
        v0_lines = []
        pairs: dict[str, list[dict[str, Any]]] = {}
        shard_rows = []
        judge_items: dict[str, list[dict[str, Any]]] = {j: [] for j in JUDGES}
        for i in range(n_defs):
            name = f"*S{i:03d}"
            # first 12 defs: high likelihood, zero pairs, polyline-only geometry
            hi = i < 12
            likelihood = 0.9 - i * 0.01 if hi else 0.05 + (i % 5) * 0.01
            n_pairs = 0 if hi else (i % 9)
            pairs[name] = [
                {"pair": [f"{i:04X}", f"{i + 1:04X}"], "conf": 0.5 + 0.01 * k, "kind": "wall_pair_candidate"}
                for k in range(n_pairs)
            ]
            v0_lines.append(
                json.dumps(
                    {
                        "unit_id": f"defannot-s{i:03d}-1",
                        "parsed": {
                            "def": name,
                            "role": "wall" if hi else "dim",
                            "wall_likelihood": likelihood,
                            "wall_line_handles": [f"{i:04X}"] if hi else [{"handle": f"{i:04X}", "reason": "x"}],
                        },
                    },
                    ensure_ascii=False,
                )
            )
            body = "LWPOLYLINE" if hi else "LINE"
            ent_lines = "\n".join(
                f"- {body} layer=X handle={i * 10 + k:04X}" + (" vertices=4" if hi else " (0,0)->(1,1)")
                for k in range(3)
            )
            prompt = (
                f"Definition name: {name}\n"
                f"entity_count: 3\n"
                f"dxf_name histogram: {body}=3\n"
                f"layer histogram: X=3\n"
                + ("" if hi else "bbox from LINE start/end: [0, 0, 0, 1, 1, 0]\n")
                + "sampled entities (max 30):\n"
                + ent_lines
                + "\n- QUUX unparseable line\n"
            )
            shard_rows.append(json.dumps({"kind": "def_annotation", "prompt": prompt, "unit_id": f"defannot-s{i:03d}-1"}))
            for jdx, judge in enumerate(JUDGES):
                jitter = 0.10 * ((i + jdx) % 3 - 1)
                judge_items[judge].append(
                    {
                        "unit_id": f"defannot-s{i:03d}-1",
                        "def": name,
                        "role": "wall" if hi else "dim",
                        "wall_likelihood": max(0.0, min(1.0, likelihood + jitter)),
                        "wall_line_handles": [{"handle": f"{i:04X}", "reason": "r"}] if hi else [],
                        "notes": "fixture",
                        "rationale": {"evidence": "fixture"},
                    }
                )
        (root / "v0.jsonl").write_text("\n".join(v0_lines) + "\n", encoding="utf-8")
        (shard_dir / "shard_01.jsonl").write_text("\n".join(shard_rows) + "\n", encoding="utf-8")
        _write_json(root / "pairs.json", {"schema": "fixture", "per_def": pairs, "totals": {}})
        for judge, items in judge_items.items():
            _write_json(judge_root / judge / "shard_01.json", items)  # type: ignore[arg-type]

        report = run(
            v0_path=root / "v0.jsonl",
            pairs_path=root / "pairs.json",
            judge_root=judge_root,
            shard_dir=shard_dir,
            cluster_path=None,
            crosscheck_path=None,
        )
        check("universe joined", report["coverage"]["universe"] == n_defs, str(report["coverage"]))
        check("projections parsed", report["projection_parse"]["parsed"] == n_defs, str(report["projection_parse"]))
        check("unparseable line counted as other", report["projection_parse"]["other_entity_lines"] == n_defs)
        check("verdict is a known band", report["verdict"] in {"SORT_ARTIFACT_CONFIRMED", "STABLE_PHENOMENON", "MIXED"}, report["verdict"])
        check("4 keys ranked", set(report["top20"]) == set(KEYS), str(sorted(report["top20"])))
        check("matrix diagonal is 1.0", all(report["jaccard_matrix"][k][k] == 1.0 for k in KEYS))
        check(
            "matrix symmetric",
            all(
                abs(report["jaccard_matrix"][a][b] - report["jaccard_matrix"][b][a]) < 1e-12
                for a in KEYS
                for b in KEYS
            ),
        )
        check("mean jaccard in [0,1]", 0.0 <= report["mean_pairwise_jaccard_top20"] <= 1.0)
        check("tier diagnostic sees polyline skew", report["tier_diagnostics"]["high_likelihood_zero_pairs"]["curve_or_polyline_frac"] == 1.0, str(report["tier_diagnostics"]["high_likelihood_zero_pairs"]))
        check("per_def complete", len(report["per_def"]) == n_defs)
        ctl = report["factorial_control"]
        check("factorial has both effects", 0.0 <= ctl["key_form_effect_mean_jaccard"] <= 1.0 and 0.0 <= ctl["llm_side_effect_mean_jaccard"] <= 1.0, str(ctl)[:200])
        check("factorial pair counts (2 sides x 3C2) + 3", len(ctl["key_form_pairs"]) == 6 and len(ctl["llm_side_pairs"]) == 3)
        check("gate population covers both sides", set(ctl["gate_population"]) == {"v0", "panel"})
        check("key-form effect reported per side", set(ctl["key_form_effect_by_side"]) == {"v0", "panel"})
        check("interaction spread is a magnitude", ctl["interaction_spread"] >= 0.0)
        # fixture judges jitter around the v0 value, so swapping the annotator must NOT wipe the top-20
        check("fixture: annotator swap is benign when judges track v0", ctl["llm_side_effect_mean_jaccard"] > 0.3, str(ctl["llm_side_effect_mean_jaccard"]))
        check("markdown renders", len(render_markdown(report)) > 800)
        check("report is json-serializable", isinstance(json.dumps(report, ensure_ascii=False), str))

        print("== 11. degenerate inputs ==")
        (root / "empty.jsonl").write_text("", encoding="utf-8")
        _write_json(root / "empty_pairs.json", {"per_def": {}})
        empty = run(
            v0_path=root / "empty.jsonl",
            pairs_path=root / "empty_pairs.json",
            judge_root=judge_root,
            shard_dir=root / "nonexistent_shards",
            cluster_path=None,
            crosscheck_path=None,
        )
        check("empty universe does not crash", empty["coverage"]["universe"] == 0)
        check("empty universe -> all top20 empty", all(v == [] for v in empty["top20"].values()))
        check("empty universe -> jaccard 1.0 (all sets empty)", empty["mean_pairwise_jaccard_top20"] == 1.0)
        check("empty markdown renders", len(render_markdown(empty)) > 200)

    print()
    if failures:
        print(f"SELFTEST FAIL -- {len(failures)} check(s) failed: {failures}")
        return 1
    print("SELFTEST PASS -- all checks green")
    return 0


# -------------------------------------------------------------------------- cli


def build_arg_parser() -> argparse.ArgumentParser:
    here = Path(__file__).resolve()
    repo = here.parents[2]
    parser = argparse.ArgumentParser(description="S1-D sort-key artifact probe.")
    parser.add_argument("--selftest", action="store_true", help="run self-contained checks and exit")
    parser.add_argument("--v0", default=str(repo / "reports/e1/ornith_annot_v0.jsonl"))
    parser.add_argument("--pairs", default=str(repo / "reports/e1/wall_pairs_v0.json"))
    parser.add_argument("--judge-root", default=str(repo / "reports/e1/annot_v1/raw"))
    parser.add_argument("--shards", default=str(repo / "bench/e1_shards"))
    parser.add_argument("--cluster", default=str(repo / "reports/e1/annot_v1/cluster_probe_v1.json"))
    parser.add_argument("--crosscheck", default=str(repo / "reports/e1/panel_20260717/evidence/e1_crosscheck.py"))
    parser.add_argument("--out", default=str(repo / "reports/e2/s1/sortkey_probe.json"))
    parser.add_argument("--md", default=str(repo / "reports/e2/s1/sortkey_probe.md"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.selftest:
        return _selftest()

    report = run(
        v0_path=Path(args.v0),
        pairs_path=Path(args.pairs),
        judge_root=Path(args.judge_root),
        shard_dir=Path(args.shards),
        cluster_path=Path(args.cluster) if args.cluster else None,
        crosscheck_path=Path(args.crosscheck) if args.crosscheck else None,
    )
    _write_json(Path(args.out), report)
    _write_text(Path(args.md), render_markdown(report))
    print(f"universe={report['coverage']['universe']} defs")
    print(f"mean_pairwise_jaccard_top20={report['mean_pairwise_jaccard_top20']:.4f}")
    print(f"VERDICT={report['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
