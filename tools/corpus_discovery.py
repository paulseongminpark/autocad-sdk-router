"""Read-only corpus discovery: filesystem metadata + filename heuristics only.

Never opens, reads, or parses drawing bytes. No CAD engine, router, or census.
"""

import argparse
import datetime
import json
import os
import re

_DELIM_RE = re.compile(r"[ ~(_]")
_LEADING_LETTERS_RE = re.compile(r"^[A-Za-z]+")


def infer_family(name):
    delim = _DELIM_RE.search(name)
    token = name[: delim.start()] if delim else os.path.splitext(name)[0]

    letters = _LEADING_LETTERS_RE.match(name)
    stem = letters.group(0).lower() if letters else "misc"

    return {"token": token, "stem": stem}


def size_bucket(byte_size):
    if byte_size < 1_000_000:
        return "small"
    if byte_size < 5_000_000:
        return "medium"
    return "large"


def discover(roots, exts=(".dwg",)):
    exts = tuple(e.lower() for e in exts)
    results = []
    for root in roots:
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                if os.path.splitext(filename)[1].lower() not in exts:
                    continue
                path = os.path.join(dirpath, filename)
                st = os.stat(path)
                family = infer_family(filename)
                results.append(
                    {
                        "path": os.path.abspath(path),
                        "name": filename,
                        "byte_size": st.st_size,
                        "mtime_iso": datetime.datetime.fromtimestamp(
                            st.st_mtime
                        ).isoformat(),
                        "family_token": family["token"],
                        "family_stem": family["stem"],
                        "size_bucket": size_bucket(st.st_size),
                    }
                )
    return results


def rank_diverse(candidates, k):
    groups = {}
    for c in candidates:
        groups.setdefault(c["family_stem"], []).append(c)

    group_order = list(groups.keys())
    seen_buckets = {stem: set() for stem in group_order}
    remaining = {stem: list(items) for stem, items in groups.items()}

    chosen = []
    while len(chosen) < k and any(remaining.values()):
        for stem in group_order:
            if len(chosen) >= k:
                break
            items = remaining.get(stem)
            if not items:
                continue

            unseen = [c for c in items if c["size_bucket"] not in seen_buckets[stem]]
            pick = unseen[0] if unseen else items[0]

            items.remove(pick)
            seen_buckets[stem].add(pick["size_bucket"])
            chosen.append(pick)

    return chosen


def _summarize(candidates):
    families = {}
    size_buckets = {}
    for c in candidates:
        families[c["family_stem"]] = families.get(c["family_stem"], 0) + 1
        size_buckets[c["size_bucket"]] = size_buckets.get(c["size_bucket"], 0) + 1
    return families, size_buckets


def main():
    parser = argparse.ArgumentParser(description="Read-only DWG corpus discovery")
    parser.add_argument("--root", action="append", required=True, dest="roots")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--out", default="candidate_corpus.json")
    args = parser.parse_args()

    candidates = discover(args.roots)
    candidates.sort(key=lambda c: (c["family_stem"], c["name"]))
    families, size_buckets = _summarize(candidates)
    diverse = rank_diverse(candidates, args.k)

    payload = {
        "schema": "ariadne.corpus_discovery.v1",
        "roots": args.roots,
        "discovered_count": len(candidates),
        "families": families,
        "size_buckets": size_buckets,
        "candidates": candidates,
        "recommended_diverse_subset": [c["path"] for c in diverse],
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(
        f"discovered {len(candidates)} candidate(s) across {len(families)} "
        f"family/families -> {args.out}"
    )


if __name__ == "__main__":
    main()
