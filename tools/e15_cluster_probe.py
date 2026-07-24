# e15_cluster_probe.py — E1.5 judge-agreement cluster ("이상한 무늬") forensic probe.
# Question: pairwise role agreement splits into two blocs (fable+sol vs opus+sonnet+grok).
# Is this a vocabulary-interpretation split (same block, different label convention)
# or genuine capability disagreement? Deterministic, stdlib-only, local CPU.
#
# Inputs : reports/e1/annot_v1/raw/<judge>/shard_NN.json  (list of {def, role, wall_likelihood, rationale...})
# Outputs: reports/e1/annot_v1/cluster_probe_v1.json / .md
import json
import os
from collections import Counter, defaultdict

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'reports', 'e1', 'annot_v1')
RAW = os.path.join(BASE, 'raw')

JUDGES = ['opus48_max', 'fable5_high', 'sol56_xhigh', 'sonnet5_xhigh', 'grok45_xhigh']
BLOC_A = ['fable5_high', 'sol56_xhigh']            # the 0.94-agreement pair
BLOC_B = ['opus48_max', 'sonnet5_xhigh', 'grok45_xhigh']


def load_judge(judge):
    recs = {}
    jdir = os.path.join(RAW, judge)
    for name in sorted(os.listdir(jdir)):
        if not name.endswith('.json'):
            continue
        with open(os.path.join(jdir, name), encoding='utf-8') as f:
            for r in json.load(f):
                recs[r['def']] = r
    return recs


def main():
    data = {j: load_judge(j) for j in JUDGES}
    defs = sorted(set.intersection(*(set(d) for d in data.values())))
    n = len(defs)

    # 1) pairwise role agreement (recompute; cross-check against calibration_v1.json)
    pair_agree = {}
    for i, j1 in enumerate(JUDGES):
        for j2 in JUDGES[i + 1:]:
            eq = sum(1 for d in defs if data[j1][d]['role'] == data[j2][d]['role'])
            pair_agree['{0} x {1}'.format(j1, j2)] = round(eq / n, 4)

    # 1b) label-merge invariance test: if the whole pattern is the single
    # '평면 부분도' vs '기타' boundary, merging those two labels must lift
    # every pair to near-uniform agreement.
    MERGE = {'평면 부분도': 'PF|기타', '기타': 'PF|기타'}
    pair_agree_merged = {}
    for i, j1 in enumerate(JUDGES):
        for j2 in JUDGES[i + 1:]:
            eq = sum(1 for d in defs
                     if MERGE.get(data[j1][d]['role'], data[j1][d]['role'])
                     == MERGE.get(data[j2][d]['role'], data[j2][d]['role']))
            pair_agree_merged['{0} x {1}'.format(j1, j2)] = round(eq / n, 4)

    # 2) bloc-split classification per def
    full_split, soft_split, uniform, other = [], [], [], []
    for d in defs:
        a = [data[j][d]['role'] for j in BLOC_A]
        b = [data[j][d]['role'] for j in BLOC_B]
        roles = set(a) | set(b)
        if len(roles) == 1:
            uniform.append(d)
            continue
        a_coherent = len(set(a)) == 1
        b_major, b_cnt = Counter(b).most_common(1)[0]
        if a_coherent and b_cnt == 3 and a[0] != b_major:
            full_split.append(d)
        elif a_coherent and b_cnt >= 2 and a[0] != b_major:
            soft_split.append(d)
        else:
            other.append(d)

    # 3) confusion matrix A-bloc role -> B-bloc majority role (full + soft splits)
    conf = defaultdict(list)
    for d in full_split + soft_split:
        a_role = data[BLOC_A[0]][d]['role']
        b_major = Counter(data[j][d]['role'] for j in BLOC_B).most_common(1)[0][0]
        conf[(a_role, b_major)].append(d)
    conf_rows = sorted(((a, b, len(ds), ds[:8]) for (a, b), ds in conf.items()),
                       key=lambda x: -x[2])

    # 4) wall_likelihood alignment on split defs (is the split label-only?)
    def bloc_wl(d, judges):
        return sum(float(data[j][d]['wall_likelihood']) for j in judges) / len(judges)

    def mean_abs_dwl(dd):
        if not dd:
            return None
        return round(sum(abs(bloc_wl(d, BLOC_A) - bloc_wl(d, BLOC_B)) for d in dd) / len(dd), 4)

    wl_split = mean_abs_dwl(full_split + soft_split)
    wl_uniform = mean_abs_dwl(uniform)

    # 5) rationale excerpts for the top confusion cells (1 def each, A vs B judge)
    samples = []
    for a_role, b_role, cnt, ds in conf_rows[:3]:
        d = ds[0]
        rec_a = data['fable5_high'][d]
        rec_b = data['opus48_max'][d]

        def ex(rec):
            r = rec.get('rationale') or {}
            return {
                'role': rec['role'], 'wl': rec['wall_likelihood'],
                'rule': str(r.get('rule', ''))[:300],
                'evidence': str(r.get('evidence', ''))[:300],
            }
        samples.append({'def': d, 'cell': '{0} -> {1} (n={2})'.format(a_role, b_role, cnt),
                        'fable5_high': ex(rec_a), 'opus48_max': ex(rec_b)})

    out = {
        'n_defs': n,
        'pairwise_role_agreement': pair_agree,
        'pairwise_role_agreement_merged_PF_ETC': pair_agree_merged,
        'counts': {
            'uniform_all5': len(uniform),
            'full_split_A_vs_B': len(full_split),
            'soft_split_A_vs_Bmajority': len(soft_split),
            'other_mixed': len(other),
        },
        'confusion_A_to_Bmajority': [
            {'A_role': a, 'B_majority_role': b, 'n': c, 'sample_defs': ds}
            for a, b, c, ds in conf_rows
        ],
        'wall_likelihood_mean_abs_bloc_diff': {
            'on_split_defs': wl_split, 'on_uniform_defs': wl_uniform,
        },
        'rationale_samples': samples,
        'full_split_defs': full_split,
        'soft_split_defs': soft_split,
    }
    jp = os.path.join(BASE, 'cluster_probe_v1.json')
    with open(jp, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    md = ['# cluster_probe_v1 — 판정자 합의 두-무리 무늬의 법의학 분석', '',
          '- 대상 defs: {0} (5 판정자 전원 존재분)'.format(n),
          '- 전원일치: {0} / A-B 완전분열(full split): {1} / A-B 다수결분열(soft): {2} / 기타 혼재: {3}'.format(
              len(uniform), len(full_split), len(soft_split), len(other)), '',
          '## A무리(fable,sol) 역할 -> B무리(opus,sonnet,grok) 다수결 역할', '']
    for a, b, c, ds in conf_rows:
        md.append('- {0} -> {1}: {2}건  (예: {3})'.format(a, b, c, ', '.join(ds[:5])))
    md += ['', '## 벽확률(wall_likelihood)은 분열 def에서도 일치하는가',
           '- 분열 def에서 무리간 평균 |Δwl| = {0}'.format(wl_split),
           '- 전원일치 def에서 무리간 평균 |Δwl| = {0}'.format(wl_uniform), '',
           '## rationale 대조 표본 (상위 혼동 셀)', '']
    for s in samples:
        md.append('### {0} — {1}'.format(s['def'], s['cell']))
        for jn in ('fable5_high', 'opus48_max'):
            e = s[jn]
            md.append('- {0}: role={1}, wl={2}'.format(jn, e['role'], e['wl']))
            md.append('  - rule: {0}'.format(e['rule']))
            md.append('  - evidence: {0}'.format(e['evidence']))
        md.append('')
    with open(os.path.join(BASE, 'cluster_probe_v1.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(md) + '\n')

    print(json.dumps({k: out[k] for k in
                      ('n_defs', 'pairwise_role_agreement',
                       'pairwise_role_agreement_merged_PF_ETC', 'counts',
                       'wall_likelihood_mean_abs_bloc_diff')}, ensure_ascii=False, indent=1))
    print('confusion top:', [(r['A_role'], r['B_majority_role'], r['n'])
                             for r in out['confusion_A_to_Bmajority'][:6]])


if __name__ == '__main__':
    main()
