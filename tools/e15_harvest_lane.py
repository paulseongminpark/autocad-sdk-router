#!/usr/bin/env python3
"""Harvest E1.5 lane receipts (octoloop runDir) into raw/<judge>/shard_NN.json.

Oneshot receipts carry the judge's answer in receipt.result_text. Models
occasionally wrap the array in prose/fences or drop a closing brace, so the
parser is deliberately tolerant: direct parse -> bracket extraction -> targeted
missing-'}' repair (insert before a `,{` object boundary and retry). Every
repair is logged; anything still unparseable is reported for a shard re-run
(prereg B3 allows exactly one).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_BASE = ROOT / "reports" / "e1" / "annot_v1"
ROLES = {"평면 부분도", "심볼", "치수캐시", "가구", "기타"}
PACKET_RE = re.compile(r"e15-(?P<judge>[a-z0-9]+)-s(?P<shard>\d{2})")
JUDGE_MAP = {"sol56": "sol56_xhigh", "grok45": "grok45_xhigh", "sonnet5": "sonnet5_xhigh"}
RATIONALE_FIELDS = ("evidence", "rule", "counterfactual", "uncertainty")


def tolerant_parse(text: str) -> tuple[list | None, str]:
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(s), "direct"
    except Exception:
        pass
    i, j = s.find("["), s.rfind("]")
    if i < 0 or j <= i:
        return None, "no array brackets"
    s = s[i : j + 1]
    try:
        return json.loads(s), "bracket"
    except Exception:
        pass
    repairs = 0
    while repairs < 30:
        try:
            return json.loads(s), f"brace_repair_x{repairs}"
        except json.JSONDecodeError as exc:
            pos = exc.pos
            if "property name" in exc.msg and 0 < pos < len(s) and s[pos] == "{":
                k = pos - 1
                while k > 0 and s[k] in " \r\n\t":
                    k -= 1
                if s[k] == ",":
                    s = s[:k] + "}" + s[k:]
                    repairs += 1
                    continue
            return None, f"unrepairable: {exc.msg} @ {pos}"
    return None, "repair budget exhausted"


def validate(arr: list, expect_n: int | None) -> tuple[bool, str]:
    if not isinstance(arr, list) or not arr:
        return False, "not a non-empty list"
    if expect_n is not None and len(arr) != expect_n:
        return False, f"expected {expect_n} items, got {len(arr)}"
    for a in arr:
        if not isinstance(a, dict) or not a.get("unit_id"):
            return False, "item missing unit_id"
        if a.get("role") not in ROLES:
            return False, f"bad role {a.get('role')!r} @ {a.get('unit_id')}"
        r = a.get("rationale")
        if not isinstance(r, dict) or not all((r.get(f) or "").strip() for f in RATIONALE_FIELDS):
            return False, f"rationale incomplete @ {a.get('unit_id')}"
    return True, ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", default="raw", choices=["raw", "raw_canary"])
    ap.add_argument("--units-manifest", default=str(RAW_BASE / "prompts" / "prompts_manifest.json"))
    args = ap.parse_args()

    manifest = json.loads(Path(args.units_manifest).read_text(encoding="utf-8"))["shards"]
    ok, failed = [], []
    for rp in sorted(Path(args.run_dir).glob("receipts/*.receipt.json")):
        receipt = json.loads(rp.read_text(encoding="utf-8-sig"))
        m = PACKET_RE.search(receipt.get("packet") or "")
        if not m:
            continue
        judge = JUDGE_MAP.get(m.group("judge"), m.group("judge"))
        shard = f"shard_{m.group('shard')}"
        expect_n = manifest.get(shard, {}).get("units")
        text = receipt.get("result_text") or ""
        arr, how = tolerant_parse(text)
        status = receipt.get("swarm_status")
        if arr is None:
            failed.append({"judge": judge, "shard": shard, "swarm": status, "why": how})
            continue
        good, why = validate(arr, expect_n)
        if not good:
            failed.append({"judge": judge, "shard": shard, "swarm": status, "why": why, "parse": how})
            continue
        out = RAW_BASE / args.out / judge
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{shard}.json").write_text(
            json.dumps(arr, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
        )
        ok.append({"judge": judge, "shard": shard, "parse": how,
                   "usage": (receipt.get("usage") or {}).get("output")})
    print(json.dumps({"harvested": len(ok), "failed": failed,
                      "repaired": [o for o in ok if o["parse"] != "direct"]},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
