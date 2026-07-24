# S1-E — listing-cap censoring probe

Schema `ariadne.e2_s1_censoring.v1` · list cap **10** · sample cap **30**

## Question

The E1 prompt instructs: *"List up to 10 entity handles that look like wall lines, with a one-phrase reason each."*

So a row with `len(wall_line_handles) == 10` may be an instruction artifact, not a
measurement. Band (preregistered): among defs with `n_handles > 0`, share pinned at
exactly 10 ≥ 0.5 → CAP_CENSORED; ≤ 0.2 → NOT_CENSORED; else MIXED.

## Verdicts

`n_pos` = defs with n_handles > 0 (the band denominator). `no_ans` = rows with no
`wall_line_handles` key at all — counted apart from a deliberate empty list.

| judge | answered | no_ans | n_pos | n@10 | share@10 | verdict |
|---|---:|---:|---:|---:|---:|---|
| ornith_v0 | 377 | 6 | 235 | 161 | 0.6851 | **CAP_CENSORED** |
| opus48_max | 384 | 0 | 64 | 9 | 0.1406 | **NOT_CENSORED** |
| fable5_high | 384 | 0 | 54 | 10 | 0.1852 | **NOT_CENSORED** |
| sol56_xhigh | 384 | 0 | 22 | 10 | 0.4545 | **MIXED** |
| sonnet5_xhigh | 384 | 0 | 61 | 8 | 0.1311 | **NOT_CENSORED** |
| grok45_xhigh | 384 | 0 | 61 | 13 | 0.2131 | **MIXED** |

## Censoring layer 2 — projection sampling (max 30)

- defs: **384**, of which entity_count > 30: **137** (0.3568)
- entities declared: **28121**, shown: **7539**
- hidden by the 30-cap: **20582** (0.7319 of all entities)
- max entity_count: **4723** · percentiles: {'p50': 20.5, 'p75': 47.0, 'p90': 124.1, 'p95': 211.3, 'p99': 780.68}
- unparsed projection lines: 0 · unknown dxf names: {}

## Stratified by the upstream cap

| judge | ≤30 n_pos | ≤30 share@10 | ≤30 verdict | >30 n_pos | >30 share@10 | >30 verdict |
|---|---:|---:|---|---:|---:|---|
| ornith_v0 | 118 | 0.5508 | CAP_CENSORED | 117 | 0.8205 | CAP_CENSORED |
| opus48_max | 23 | 0.0 | NOT_CENSORED | 41 | 0.2195 | MIXED |
| fable5_high | 21 | 0.0 | NOT_CENSORED | 33 | 0.303 | MIXED |
| sol56_xhigh | 2 | 0.0 | NOT_CENSORED | 20 | 0.5 | CAP_CENSORED |
| sonnet5_xhigh | 23 | 0.0 | NOT_CENSORED | 38 | 0.2105 | MIXED |
| grok45_xhigh | 12 | 0.0 | NOT_CENSORED | 49 | 0.2653 | MIXED |

## Does the cap actually bind?

A row at exactly 10 is only *censored* if the projection exposed more than 10 wall-ish
(LINE/LWPOLYLINE) entities. Otherwise 10 was reachable without clipping.

| judge | @10 rows | wall-ish > 10 (cap can bind) | wall-ish ≤ 10 (cap cannot bind) | binding share |
|---|---:|---:|---:|---:|
| ornith_v0 | 161 | 155 | 6 | 0.9627 |
| opus48_max | 9 | 9 | 0 | 1.0 |
| fable5_high | 10 | 10 | 0 | 1.0 |
| sol56_xhigh | 10 | 10 | 0 | 1.0 |
| sonnet5_xhigh | 8 | 8 | 0 | 1.0 |
| grok45_xhigh | 13 | 13 | 0 | 1.0 |

## Handle provenance

| judge | cited handles in projection | not in projection | fabricated share | max n_handles | n>10 |
|---|---:|---:|---:|---:|---:|
| ornith_v0 | 2045 | 0 | 0.0 | 15 | 1 |
| opus48_max | 246 | 0 | 0.0 | 10 | 0 |
| fable5_high | 264 | 0 | 0.0 | 10 | 0 |
| sol56_xhigh | 166 | 0 | 0.0 | 10 | 0 |
| sonnet5_xhigh | 229 | 0 | 0.0 | 10 | 0 |
| grok45_xhigh | 314 | 0 | 0.0 | 10 | 0 |

## n_handles distribution

- **ornith_v0** (n=383): {'0': 142, '1': 1, '2': 6, '3': 10, '4': 4, '5': 16, '6': 5, '7': 3, '8': 22, '9': 6, '10': 161, '15': 1}
- **opus48_max** (n=384): {'0': 320, '1': 9, '2': 26, '3': 4, '4': 7, '5': 3, '6': 4, '8': 2, '10': 9}
- **fable5_high** (n=384): {'0': 330, '1': 7, '2': 10, '4': 16, '5': 3, '6': 2, '7': 2, '8': 4, '10': 10}
- **sol56_xhigh** (n=384): {'0': 362, '2': 1, '3': 2, '4': 2, '5': 1, '6': 1, '7': 1, '8': 4, '10': 10}
- **sonnet5_xhigh** (n=384): {'0': 323, '1': 8, '2': 21, '3': 12, '4': 3, '5': 7, '8': 2, '10': 8}
- **grok45_xhigh** (n=384): {'0': 323, '1': 3, '2': 15, '3': 8, '4': 7, '5': 7, '6': 1, '7': 1, '8': 3, '9': 3, '10': 13}

## Divergence overlay (cluster_probe_v1)

full_split_defs=73 · soft_split_defs=28

| judge | full_split share@10 | soft_split share@10 | rest share@10 |
|---|---:|---:|---:|
| ornith_v0 | 0.7857 | 0.5714 | 0.6646 |
| opus48_max | None | 0.0 | 0.1475 |
| fable5_high | None | None | 0.1852 |
| sol56_xhigh | None | None | 0.4545 |
| sonnet5_xhigh | None | None | 0.1311 |
| grok45_xhigh | None | None | 0.2131 |

