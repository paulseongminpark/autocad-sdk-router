"""Internal wall-hypothesis, jury fusion, and review-surface helpers."""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import math
from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence


ANTI_WALL_TOKENS = ("DOOR", "FUR", "KIT", "ELEV", "DIM", "수전", "가구", "문자")
SILVER_THRESHOLDS = {
    "rules_positive": 0.70,
    "learned_positive": 0.85,
    "learned_agreement_delta": 0.15,
    "max_intervention_delta": 0.10,
    "rules_negative": 0.35,
    "learned_negative": 0.15,
}


def _stable_id(*parts: Any) -> str:
    digest = hashlib.sha256()
    for part in parts:
        raw = json.dumps(part, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest()


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, value: str) -> str:
        self.parent.setdefault(value, value)
        if self.parent[value] != value:
            self.parent[value] = self.find(self.parent[value])
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[b] = a


def _stats(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "mean": None, "max": None}
    return {
        "min": round(float(min(values)), 6),
        "mean": round(float(sum(values) / len(values)), 6),
        "max": round(float(max(values)), 6),
    }


def build_hypotheses(
    seg_ir: Mapping[str, Any], candidates: Mapping[str, Any]
) -> dict[str, Any]:
    """Collapse pair-connected rule candidates to reviewable wall hypotheses."""

    segments = {str(row.get("handle")): row for row in seg_ir.get("segments", []) or []}
    candidate_rows = {
        str(row["placed_uid"]): row for row in candidates.get("candidates", []) or []
    }
    union = _UnionFind()
    pairs = list(candidates.get("wall_pair_records", []) or [])
    for pair in pairs:
        handles = [str(value) for value in pair.get("handles", [])]
        if len(handles) != 2:
            raise ValueError("wall pair record must contain exactly two handles")
        union.union(handles[0], handles[1])
    if set(union.parent) != set(candidate_rows):
        missing = sorted(set(candidate_rows) - set(union.parent))
        extra = sorted(set(union.parent) - set(candidate_rows))
        raise ValueError(f"candidate/pair universe mismatch missing={missing[:5]} extra={extra[:5]}")

    components: dict[str, list[str]] = defaultdict(list)
    for handle in sorted(union.parent):
        components[union.find(handle)].append(handle)
    hypotheses = []
    handle_to_hypothesis: dict[str, str] = {}
    for handles in sorted(components.values(), key=lambda values: tuple(sorted(values))):
        handles = sorted(handles)
        hypothesis_id = f"wh_{_stable_id(handles)[:16]}"
        component_pairs = [pair for pair in pairs if any(str(value) in handles for value in pair["handles"])]
        member_segments = [segments[handle] for handle in handles]
        points = [point for segment in member_segments for point in segment.get("pts", [])]
        lengths = [math.dist(segment["pts"][0], segment["pts"][-1]) for segment in member_segments]
        rule_scores = [float(candidate_rows[handle]["score"]) for handle in handles]
        thicknesses = [float(pair["thickness"]) for pair in component_pairs]
        layers = Counter(str(segment.get("layer") or "<EMPTY>") for segment in member_segments)
        anti_layers = sorted(
            layer
            for layer in layers
            if any(token.upper() in layer.upper() for token in ANTI_WALL_TOKENS)
        )
        bbox = [
            min(float(point[0]) for point in points),
            min(float(point[1]) for point in points),
            max(float(point[0]) for point in points),
            max(float(point[1]) for point in points),
        ]
        hypothesis = {
            "hypothesis_id": hypothesis_id,
            "member_handles": handles,
            "member_count": len(handles),
            "pair_count": len(component_pairs),
            "bbox_world": [round(value, 6) for value in bbox],
            "layers": dict(sorted(layers.items())),
            "anti_wall_layer_cues": anti_layers,
            "rule_score_stats": _stats(rule_scores),
            "member_length_stats": _stats(lengths),
            "pair_thickness_stats": _stats(thicknesses),
            "pair_axes": [pair["axis"] for pair in component_pairs],
        }
        hypotheses.append(hypothesis)
        for handle in handles:
            handle_to_hypothesis[handle] = hypothesis_id
    hypotheses.sort(key=lambda row: row["hypothesis_id"])
    return {
        "schema": "e2.wall_hypotheses.v1",
        "status": "PASS",
        "source_candidate_count": len(candidate_rows),
        "source_pair_count": len(pairs),
        "hypothesis_count": len(hypotheses),
        "accounted_candidate_count": len(handle_to_hypothesis),
        "balance_ok": len(candidate_rows) == len(handle_to_hypothesis),
        "definition": "connected component of the rule wall-pair graph; a hypothesis is reviewable evidence, not wall truth",
        "hypotheses": hypotheses,
        "handle_to_hypothesis": dict(sorted(handle_to_hypothesis.items())),
    }


def _aggregate(score_map: Mapping[str, float], handles: Sequence[str]) -> float | None:
    values = [float(score_map[handle]) for handle in handles if handle in score_map]
    return None if not values else float(sum(values) / len(values))


def fuse_jury(
    hypotheses: Mapping[str, Any], segment_scores: Mapping[str, Any]
) -> dict[str, Any]:
    """Fuse evidence conservatively while preserving dependence information."""

    baseline = segment_scores["baseline"]
    intervention_rows = segment_scores["interventions"]
    results = []
    label_counts: Counter[str] = Counter()
    for hypothesis in hypotheses["hypotheses"]:
        handles = hypothesis["member_handles"]
        scores = {
            juror: _aggregate(baseline[juror], handles)
            for juror in ("rules", "gbdt", "gnn")
        }
        if any(value is None for value in scores.values()):
            missing = [key for key, value in scores.items() if value is None]
            raise ValueError(f"{hypothesis['hypothesis_id']} lacks juror scores: {missing}")
        stability = {}
        for juror in scores:
            arm_scores = {
                arm: _aggregate(payload[juror], handles)
                for arm, payload in intervention_rows.items()
            }
            deltas = {
                arm: abs(float(value) - float(scores[juror]))
                for arm, value in arm_scores.items()
                if value is not None
            }
            stability[juror] = {
                "arm_scores": {key: round(float(value), 6) for key, value in arm_scores.items() if value is not None},
                "max_absolute_delta": round(max(deltas.values(), default=0.0), 6),
                "stable_at_0_10": max(deltas.values(), default=0.0) <= SILVER_THRESHOLDS["max_intervention_delta"],
            }
        anti_wall = bool(hypothesis["anti_wall_layer_cues"])
        learned_agreement = abs(float(scores["gbdt"]) - float(scores["gnn"]))
        all_stable = all(row["stable_at_0_10"] for row in stability.values())
        positive = (
            float(scores["rules"]) >= SILVER_THRESHOLDS["rules_positive"]
            and float(scores["gbdt"]) >= SILVER_THRESHOLDS["learned_positive"]
            and float(scores["gnn"]) >= SILVER_THRESHOLDS["learned_positive"]
            and learned_agreement <= SILVER_THRESHOLDS["learned_agreement_delta"]
            and all_stable
            and not anti_wall
        )
        negative = (
            float(scores["rules"]) <= SILVER_THRESHOLDS["rules_negative"]
            and float(scores["gbdt"]) <= SILVER_THRESHOLDS["learned_negative"]
            and float(scores["gnn"]) <= SILVER_THRESHOLDS["learned_negative"]
            and all_stable
        )
        label = "PROVISIONAL_SILVER_WALL" if positive else "PROVISIONAL_SILVER_NOT_WALL" if negative else "REVIEW"
        ranking_score = 0.40 * float(scores["rules"]) + 0.30 * float(scores["gbdt"]) + 0.30 * float(scores["gnn"])
        spread = max(float(value) for value in scores.values()) - min(float(value) for value in scores.values())
        reasons = []
        if anti_wall:
            reasons.append("ANTI_WALL_LAYER_CUE")
        if learned_agreement > SILVER_THRESHOLDS["learned_agreement_delta"]:
            reasons.append("LEARNED_MODEL_DISAGREEMENT")
        if spread > 0.35:
            reasons.append("CROSS_FAMILY_DISAGREEMENT")
        if not all_stable:
            reasons.append("INTERVENTION_UNSTABLE")
        if 0.35 <= ranking_score <= 0.65:
            reasons.append("FUSED_SCORE_UNCERTAIN")
        if label == "REVIEW" and not reasons:
            reasons.append("STRICT_SILVER_GATE_NOT_MET")
        results.append(
            {
                "hypothesis_id": hypothesis["hypothesis_id"],
                "scores": {key: round(float(value), 6) for key, value in scores.items()},
                "ranking_score_not_probability": round(ranking_score, 6),
                "score_spread": round(spread, 6),
                "learned_agreement_delta": round(learned_agreement, 6),
                "intervention_stability": stability,
                "anti_wall_layer_cues": hypothesis["anti_wall_layer_cues"],
                "automatic_label": label,
                "promotion_status": "NOT_GOLD_NOT_TRAINING_TRUTH",
                "review_reasons": reasons,
            }
        )
        label_counts[label] += 1
    results.sort(key=lambda row: row["hypothesis_id"])
    return {
        "schema": "e2.jury_results.v1",
        "status": "PARTIAL_PASS",
        "thresholds_frozen_before_inference": dict(SILVER_THRESHOLDS),
        "independent_evidence_family_count": 2,
        "dependence_rule": "GBDT and GNN share CubiCasa supervision and jointly count as one learned family; rules are the second family; VLM is absent.",
        "label_counts": dict(sorted(label_counts.items())),
        "calibration_warning": "Scores rank review candidates on this DWG but are not calibrated wall probabilities. Silver labels cannot train or validate a promoted model until human calibration and sealed holdout evaluation exist.",
        "results": results,
    }


def _selection_key(drawing_id: str, hypothesis_id: str, lane: str) -> str:
    return _stable_id(drawing_id, hypothesis_id, lane)


def build_review_queue(
    drawing_id: str,
    hypotheses: Mapping[str, Any],
    jury: Mapping[str, Any],
    *,
    public_limit: int = 24,
    audit_count: int = 6,
    sealed_holdout_count: int = 12,
) -> dict[str, Any]:
    hypothesis_index = {row["hypothesis_id"]: row for row in hypotheses["hypotheses"]}
    jury_rows = {row["hypothesis_id"]: row for row in jury["results"]}
    ids = sorted(hypothesis_index)
    sealed = sorted(ids, key=lambda value: _selection_key(drawing_id, value, "sealed-holdout"))[
        : min(sealed_holdout_count, len(ids))
    ]
    eligible = [value for value in ids if value not in set(sealed)]

    def priority(hypothesis_id: str) -> tuple[Any, ...]:
        row = jury_rows[hypothesis_id]
        reasons = set(row["review_reasons"])
        severity = (
            5 * ("ANTI_WALL_LAYER_CUE" in reasons)
            + 4 * ("CROSS_FAMILY_DISAGREEMENT" in reasons)
            + 3 * ("LEARNED_MODEL_DISAGREEMENT" in reasons)
            + 2 * ("INTERVENTION_UNSTABLE" in reasons)
            + 1 * ("FUSED_SCORE_UNCERTAIN" in reasons)
        )
        uncertainty = 1.0 - min(1.0, abs(float(row["ranking_score_not_probability"]) - 0.5) * 2.0)
        return (-severity, -uncertainty, _selection_key(drawing_id, hypothesis_id, "public-targeted"))

    targeted_pool = [value for value in eligible if jury_rows[value]["automatic_label"] == "REVIEW"]
    targeted = sorted(targeted_pool, key=priority)[:public_limit]
    audit_pool = [
        value
        for value in eligible
        if value not in set(targeted) and jury_rows[value]["automatic_label"].startswith("PROVISIONAL_SILVER")
    ]
    audit_lane = "silver_audit"
    if not audit_pool:
        audit_lane = "consensus_audit"
        audit_pool = [value for value in eligible if value not in set(targeted)]
    audit = sorted(audit_pool, key=lambda value: _selection_key(drawing_id, value, "silver-audit"))[:audit_count]
    public_ids = targeted + audit

    def row(hypothesis_id: str, lane: str) -> dict[str, Any]:
        return {
            "hypothesis_id": hypothesis_id,
            "lane": lane,
            "allowed_labels": ["WALL", "NOT_WALL", "AMBIGUOUS", "UNSURE"],
            "human_label": None,
            "geometry": hypothesis_index[hypothesis_id],
            "jury": jury_rows[hypothesis_id] if lane != "sealed_holdout" else None,
        }

    public_rows = [row(value, "targeted_review" if value in targeted else audit_lane) for value in public_ids]
    sealed_rows = [row(value, "sealed_holdout") for value in sealed]
    deferred = sorted(set(ids) - set(public_ids) - set(sealed))
    return {
        "schema": "e2.review_queue.v1",
        "status": "PASS",
        "selection_frozen_before_human_labels": True,
        "drawing_id": drawing_id,
        "public_targeted_count": len(targeted),
        "public_audit_count": len(audit),
        "public_audit_kind": audit_lane,
        "public_total_count": len(public_rows),
        "sealed_holdout_count": len(sealed_rows),
        "deferred_unqueued_count": len(deferred),
        "deferred_unqueued_ids": deferred,
        "population_balance_ok": len(public_rows) + len(sealed_rows) + len(deferred) == len(ids),
        "public_and_holdout_disjoint": not (set(public_ids) & set(sealed)),
        "sealed_holdout_rule": "hash-only selection independent of model scores; label once; never tune thresholds on it",
        "public_queue": public_rows,
        "sealed_holdout_queue": sealed_rows,
    }


def review_csv(queue: Mapping[str, Any]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        [
            "hypothesis_id",
            "lane",
            "human_label",
            "review_reasons",
            "rules_score",
            "gbdt_score",
            "gnn_score",
            "ranking_score_not_probability",
            "member_count",
            "layers",
        ]
    )
    for item in queue["public_queue"]:
        jury = item["jury"]
        geometry = item["geometry"]
        writer.writerow(
            [
                item["hypothesis_id"],
                item["lane"],
                "",
                "|".join(jury["review_reasons"]),
                jury["scores"]["rules"],
                jury["scores"]["gbdt"],
                jury["scores"]["gnn"],
                jury["ranking_score_not_probability"],
                geometry["member_count"],
                json.dumps(geometry["layers"], ensure_ascii=False, sort_keys=True),
            ]
        )
    return stream.getvalue()


def _svg_for_hypothesis(
    hypothesis: Mapping[str, Any], all_segments: Sequence[Mapping[str, Any]], width: int = 520, height: int = 260
) -> str:
    x0, y0, x1, y1 = [float(value) for value in hypothesis["bbox_world"]]
    span = max(x1 - x0, y1 - y0, 100.0)
    margin = max(400.0, span * 0.35)
    left, right, bottom, top = x0 - margin, x1 + margin, y0 - margin, y1 + margin
    scale = min((width - 20) / max(right - left, 1.0), (height - 20) / max(top - bottom, 1.0))
    dx = (width - (right - left) * scale) / 2.0
    dy = (height - (top - bottom) * scale) / 2.0

    def screen(point: Sequence[float]) -> tuple[float, float]:
        return dx + (float(point[0]) - left) * scale, height - (dy + (float(point[1]) - bottom) * scale)

    members = set(hypothesis["member_handles"])
    lines = []
    for segment in all_segments:
        p0, p1 = segment["pts"][0], segment["pts"][-1]
        if max(float(p0[0]), float(p1[0])) < left or min(float(p0[0]), float(p1[0])) > right:
            continue
        if max(float(p0[1]), float(p1[1])) < bottom or min(float(p0[1]), float(p1[1])) > top:
            continue
        a, b = screen(p0), screen(p1)
        selected = str(segment.get("handle")) in members
        lines.append(
            f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" '
            f'stroke="{"#d62728" if selected else "#a7adb5"}" stroke-width="{3.0 if selected else 0.8}" />'
        )
    return f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="wall hypothesis context">' + "".join(lines) + "</svg>"


def review_html(
    title: str,
    rows: Sequence[Mapping[str, Any]],
    all_segments: Sequence[Mapping[str, Any]],
    *,
    include_jury_after_label: bool,
) -> str:
    instruction = (
        "빨간 선이 판정 대상이다. 먼저 사람 판단을 고른 뒤에만 자동 판정 근거가 열린다."
        if include_jury_after_label
        else "빨간 선이 판정 대상이다. 이 봉인 화면에는 자동 판정 점수가 포함되지 않는다."
    )
    cards = []
    for item in rows:
        hypothesis = item["geometry"]
        jury = item.get("jury")
        evidence = ""
        if include_jury_after_label and jury is not None:
            evidence = (
                '<details class="evidence" hidden><summary>자동 판정 근거</summary>'
                f'<pre>{html.escape(json.dumps(jury, ensure_ascii=False, indent=2))}</pre></details>'
            )
        buttons = "".join(
            f'<label><input type="radio" name="{html.escape(item["hypothesis_id"])}" value="{label}"> {label}</label>'
            for label in item["allowed_labels"]
        )
        cards.append(
            f'<article class="card" data-id="{html.escape(item["hypothesis_id"])}" data-lane="{html.escape(item["lane"])}">'
            f'<h2>{html.escape(item["hypothesis_id"])} <small>{html.escape(item["lane"])}</small></h2>'
            f'{_svg_for_hypothesis(hypothesis, all_segments)}'
            f'<p>구성 선분 {hypothesis["member_count"]}개 · 쌍 증거 {hypothesis["pair_count"]}개 · 층 {html.escape(json.dumps(hypothesis["layers"], ensure_ascii=False))}</p>'
            f'<div class="labels">{buttons}</div>{evidence}</article>'
        )
    script = """
const out = {};
document.querySelectorAll('.card').forEach(card => {
  card.querySelectorAll('input[type=radio]').forEach(input => input.addEventListener('change', () => {
    out[card.dataset.id] = {hypothesis_id: card.dataset.id, lane: card.dataset.lane, human_label: input.value};
    const evidence = card.querySelector('.evidence'); if (evidence) evidence.hidden = false;
  }));
});
document.getElementById('export').addEventListener('click', () => {
  const payload = {schema:'e2.human_labels.v1', exported_at:new Date().toISOString(), labels:Object.values(out)};
  const blob = new Blob([JSON.stringify(payload, null, 2)], {type:'application/json'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'human_labels.json'; a.click();
  URL.revokeObjectURL(a.href);
});
"""
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>
body{{font-family:system-ui,sans-serif;margin:24px;background:#f4f6f8;color:#17202a}} header{{position:sticky;top:0;background:#fff;padding:14px;border:1px solid #ccd2d8;z-index:2}}
.card{{background:#fff;border:1px solid #ccd2d8;border-radius:8px;padding:14px;margin:16px 0}} h2{{margin:0 0 8px}} small{{font-weight:400;color:#607080}} svg{{width:100%;background:#fbfbfb;border:1px solid #e1e4e8}}
.labels{{display:flex;gap:18px;flex-wrap:wrap;margin:12px 0}} pre{{white-space:pre-wrap;max-height:320px;overflow:auto;background:#f7f7f7;padding:10px}}
button{{font-size:1rem;padding:8px 14px}}
</style></head><body><header><h1>{html.escape(title)}</h1><p>{html.escape(instruction)}</p><button id="export">라벨 JSON 내보내기</button></header>{''.join(cards)}<script>{script}</script></body></html>"""
