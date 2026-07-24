# w1_eval_driver.py — Wave-1 B2 evaluation driver: run detect+eval over an S2 pack
# (both arms: full / name-blind), aggregate per-drawing P/R/F1 into micro+macro stats.
# Deterministic; subprocess per drawing via the S4 CLI (the same entrypoint a user runs).
import argparse
import json
import os
import subprocess
import sys

PY = sys.executable
HERE = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(HERE, 'detect', 'cli.py')


def run_pack(pack_dir, out_dir, threshold):
    manifest = json.load(open(os.path.join(pack_dir, 'manifest.json', ), encoding='utf-8'))
    os.makedirs(out_dir, exist_ok=True)
    arms = {'full': [], 'name_blind': ['--no-layer-channel']}
    results = {a: [] for a in arms}
    failures = []
    for entry in manifest['files']:
        dxf = os.path.join(pack_dir, entry['dxf'])
        truth = os.path.join(pack_dir, entry['truth'])
        for arm, flags in arms.items():
            pred = os.path.join(out_dir, '{0}.{1}.pred.json'.format(entry['drawing_id'], arm))
            ev = os.path.join(out_dir, '{0}.{1}.eval.json'.format(entry['drawing_id'], arm))
            r1 = subprocess.run([PY, CLI, 'detect', '--dxf', dxf, '--out', pred] + flags,
                                capture_output=True, text=True)
            if r1.returncode:
                failures.append({'drawing': entry['drawing_id'], 'arm': arm, 'stage': 'detect',
                                 'stderr': r1.stderr[-300:]})
                continue
            r2 = subprocess.run([PY, CLI, 'eval', '--pred', pred, '--truth', truth,
                                 '--out', ev, '--threshold', str(threshold)],
                                capture_output=True, text=True)
            if r2.returncode:
                failures.append({'drawing': entry['drawing_id'], 'arm': arm, 'stage': 'eval',
                                 'stderr': r2.stderr[-300:]})
                continue
            results[arm].append({'drawing': entry['drawing_id'],
                                 'eval': json.load(open(ev, encoding='utf-8'))})
    return manifest, results, failures


def _find_counts(ev):
    """Locate tp/fp/fn wherever the eval report put them (schema tolerant)."""
    def rec(d):
        if isinstance(d, dict):
            keys = {k.lower() for k in d}
            if {'tp', 'fp', 'fn'} <= keys:
                return {k.lower(): d[k2] for k2 in d for k in [k2.lower()] if k in ('tp', 'fp', 'fn')}
            for v in d.values():
                got = rec(v)
                if got:
                    return got
        return None
    return rec(ev)


def _find_pr(ev):
    def rec(d):
        if isinstance(d, dict):
            keys = {k.lower() for k in d}
            if {'precision', 'recall'} <= keys:
                lk = {k.lower(): v for k, v in d.items()}
                return lk['precision'], lk['recall']
            for v in d.values():
                got = rec(v)
                if got:
                    return got
        return None
    return rec(ev)


def aggregate(rows):
    tp = fp = fn = 0
    macro_p, macro_r, counted = [], [], 0
    for row in rows:
        ev = row['eval']
        c = _find_counts(ev)
        if c:
            tp += c['tp']; fp += c['fp']; fn += c['fn']
            counted += 1
        pr = _find_pr(ev)
        if pr and pr[0] is not None and pr[1] is not None:
            macro_p.append(float(pr[0])); macro_r.append(float(pr[1]))
    out = {'n_drawings': len(rows), 'n_with_counts': counted}
    if counted:
        p = tp / (tp + fp) if tp + fp else None
        r = tp / (tp + fn) if tp + fn else None
        out['micro'] = {'tp': tp, 'fp': fp, 'fn': fn, 'precision': p, 'recall': r,
                        'f1': (2 * p * r / (p + r)) if p and r else None}
    if macro_p:
        out['macro'] = {'precision': sum(macro_p) / len(macro_p),
                        'recall': sum(macro_r) / len(macro_r)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pack', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--threshold', type=float, default=0.5)
    ap.add_argument('--report', required=True)
    a = ap.parse_args()
    manifest, results, failures = run_pack(a.pack, a.out, a.threshold)
    report = {
        'driver': 'w1_eval.v1', 'pack': os.path.abspath(a.pack), 'tier': manifest.get('tier'),
        'threshold': a.threshold,
        'arms': {arm: aggregate(rows) for arm, rows in results.items()},
        'failures': failures,
    }
    with open(a.report, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps({'tier': report['tier'],
                      'full': report['arms']['full'].get('micro') or report['arms']['full'].get('macro'),
                      'name_blind': report['arms']['name_blind'].get('micro') or report['arms']['name_blind'].get('macro'),
                      'failures': len(failures)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
