#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time

import blockdef_diff


def _time_once(fn, *args, repeat: int):
    started = time.perf_counter()
    for _ in range(repeat):
        fn(*args)
    return (time.perf_counter() - started) / float(repeat)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark full vs partial blockdef diff for one def.")
    parser.add_argument("--census", required=True)
    parser.add_argument("--post", required=True)
    parser.add_argument("--def-name", required=True)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args(argv)

    census_ir = blockdef_diff._load_json(args.census)
    post_ir = blockdef_diff._load_json(args.post)
    repeat = max(int(args.repeat), 1)

    full_s = _time_once(blockdef_diff.diff_block_definitions, census_ir, post_ir, repeat=repeat)
    partial_s = _time_once(
        blockdef_diff.diff_block_definitions_partial,
        census_ir,
        post_ir,
        [args.def_name],
        repeat=repeat,
    )
    speedup = (full_s / partial_s) if partial_s else None
    print(json.dumps({
        "full_s": full_s,
        "partial_s": partial_s,
        "speedup": speedup,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
