# E2 S1-D — Sort-key artifact probe

**VERDICT: MIXED** (mean pairwise Jaccard of top-20 = 0.4437; <0.4 artifact, >0.7 stable)

## Question

Is the E1 'divergent top-20' a property of the drawings, or of the `_score_divergence`
sort design in `reports/e1/panel_20260717/evidence/e1_crosscheck.py`?

## Ranking keys

| key | definition |
| --- | --- |
| `a_original` | mirrored _score_divergence: gate + lexicographic tiers (kind, likelihood, n_pairs) |
| `b_absdiff` | |v0 wall_likelihood - detector max_conf|, ungated |
| `c_wrankdiff` | v0 wall_likelihood * |rank_llm - rank_detector| / N |
| `d_bootstrap` | annot_v1 judges, 5C3=10 subsets, ranked by top-20 selection frequency |

## Universe

- Controlled universe (v0 ∩ 5 judges ∩ detector pairs): **374** defs
- v0 rows: 383 · detector defs: 407
- dropped: no_def=6 · no_pairs=1 · dup_pair_key=0 · missing_judge=2

## Top-20 Jaccard matrix

| | `a_original` | `b_absdiff` | `c_wrankdiff` | `d_bootstrap` |
| --- | ---: | ---: | ---: | ---: |
| `a_original` | 1.000 | 0.818 | 1.000 | 0.000 |
| `b_absdiff` | 0.818 | 1.000 | 0.818 | 0.026 |
| `c_wrankdiff` | 1.000 | 0.818 | 1.000 | 0.000 |
| `d_bootstrap` | 0.000 | 0.026 | 0.000 | 1.000 |

### Pairwise detail

| pair | Jaccard | ∩ | ∪ |
| --- | ---: | ---: | ---: |
| `a_original` vs `b_absdiff` | 0.818 | 18 | 22 |
| `a_original` vs `c_wrankdiff` | 1.000 | 20 | 20 |
| `a_original` vs `d_bootstrap` | 0.000 | 0 | 40 |
| `b_absdiff` vs `c_wrankdiff` | 0.818 | 18 | 22 |
| `b_absdiff` vs `d_bootstrap` | 0.026 | 1 | 39 |
| `c_wrankdiff` vs `d_bootstrap` | 0.000 | 0 | 40 |

## Decomposition — gate vs ordering

- Gated candidates: **69** of 374 defs (tier0 high_likelihood_zero_pairs = 52, tier1 many_pairs_low_likelihood = 17)
- Original top-20 lies entirely inside tier0: **True**

| key | fraction of its top-20 the original gate would admit |
| --- | ---: |
| `a_original` | 1.000 |
| `b_absdiff` | 0.950 |
| `c_wrankdiff` | 1.000 |
| `d_bootstrap` | 0.000 |

> gate_passing_frac is how much of each key's top-20 the original gate would have even admitted. A low value for (b)/(c)/(d) means the hard gate -- not the tie ordering -- is what selects the original top-20.

## Factorial control — sort key vs annotator

Key (d) changes two things at once (the ranking key *and* the LLM side), so the low
a-vs-d Jaccard above cannot on its own blame the sort key. Crossing {key form} x
{LLM side} separates them:

- **Key-form effect** (swap the key, hold the annotator): pooled mean Jaccard = **0.488** — but this pools two regimes, see below
    - under annotator `v0`: **0.879** (sort key barely moves the top-20)
    - under annotator `panel`: **0.097** (sort key almost entirely determines the top-20)
    - interaction spread = **0.782**
- **Annotator effect** (swap the annotator, hold the key): mean Jaccard = **0.036**

| held fixed | compared | Jaccard |
| --- | --- | ---: |
| llm_side=v0 | `a_original` vs `b_absdiff` | 0.818 |
| llm_side=v0 | `a_original` vs `c_wrankdiff` | 1.000 |
| llm_side=v0 | `b_absdiff` vs `c_wrankdiff` | 0.818 |
| llm_side=panel | `a_original` vs `b_absdiff` | 0.290 |
| llm_side=panel | `a_original` vs `c_wrankdiff` | 0.000 |
| llm_side=panel | `b_absdiff` vs `c_wrankdiff` | 0.000 |
| key=a_original | `v0` vs `panel` | 0.000 |
| key=b_absdiff | `v0` vs `panel` | 0.026 |
| key=c_wrankdiff | `v0` vs `panel` | 0.081 |

### Gate population under each annotator

| annotator | gated candidates | tier0 (high_likelihood_zero_pairs) | tier1 |
| --- | ---: | ---: | ---: |
| v0 | 69 | 52 | 17 |
| panel | 63 | 0 | 63 |

### Signed divergence — which side over-calls walls?

| annotator | LLM says wall, detector silent | detector says wall, LLM silent | mean likelihood |
| --- | ---: | ---: | ---: |
| v0 | 60 | 59 | 0.350 |
| panel | 0 | 112 | 0.169 |

> The two factors interact, so neither marginal mean stands alone. Read key_form_effect_by_side first: if the top-20 is sort-key-robust under one annotator and sort-key-fragile under another, the pooled key_form_effect is an average across regimes that describes neither. A large interaction_spread means the sort key's apparent robustness is contingent on the annotator, not a property of the data.

## Judge-subset bootstrap (5 choose 3)

- Subsets: 10
- Distinct defs entering any subset's top-20: **31** (churn ratio 1.55× vs a stable 20)
- Defs present in all 10 subsets' top-20: **16**
- Selection-count histogram (count → #defs): `{"10": 16, "7": 1, "5": 2, "4": 1, "3": 4, "1": 7, "0": 343}`

> churn_ratio = distinct defs that entered any subset's top-20, divided by 20. 1.0 means the panel choice never changes the top-20; higher means it does.

## Tier diagnostic — is `high_likelihood_zero_pairs` a representation artifact?

The projection's bbox is derived *from LINE start/end* and the detector pairs LINE
segments, so a def drawn with LWPOLYLINE/ARC/SPLINE exposes no pairable coordinates.

| def group | n | mean LINE count | zero-LINE frac | curve/polyline frac |
| --- | ---: | ---: | ---: | ---: |
| high_likelihood_zero_pairs | 52 | 0.67 | 0.904 | 0.981 |
| many_pairs_low_likelihood | 17 | 119.59 | 0.000 | 0.529 |
| non_candidate | 305 | 29.97 | 0.315 | 0.616 |

> If zero_LINE_frac / curve_or_polyline_frac is much higher for high_likelihood_zero_pairs than for non_candidate defs, the tier is at least partly a projection-representation artifact, not an LLM-vs-detector conflict.

## Sensitivity & parity

- Key (b) under max-conf vs mean-conf detector signal: Jaccard = 0.905
- Parity vs untouched `e1_crosscheck.run()`: identical_order=**True**, set Jaccard=1.000

## Cross-reference — E1 cluster probe

- full_split_defs: 73 · soft_split_defs: 28

| key | ∩ full_split | ∩ soft_split |
| --- | ---: | ---: |
| `a_original` | 7 | 2 |
| `b_absdiff` | 6 | 2 |
| `c_wrankdiff` | 7 | 2 |
| `d_bootstrap` | 0 | 0 |

## Top-20 per key

- **`a_original`**: X-평면도(기본형)$0$111BRF2, *U103, *U142, *U45, *U53, *U55, *U88, X-평면도(기본형)$0$111ARF2, X-평면도(기본형)$0$A$C4B913E7C, *D324, *U105, *U106, *U107, *U109, *U111, *U125, *U171, *U184, *U187, *U239
- **`b_absdiff`**: X-평면도(기본형)$0$111BRF2, *U103, *U142, *U45, *U53, *U55, *U88, X-평면도(기본형)$0$111ARF2, X-평면도(기본형)$0$A$C4B913E7C, X-평면도(기본형)$0$phg1200, X-평면도(기본형)$0$pd900, *D324, *U105, *U106, *U107, *U109, *U111, *U125, *U171, *U184
- **`c_wrankdiff`**: X-평면도(기본형)$0$111BRF2, *U103, *U142, *U45, *U53, *U55, *U88, X-평면도(기본형)$0$111ARF2, X-평면도(기본형)$0$A$C4B913E7C, *D324, *U105, *U106, *U107, *U109, *U111, *U125, *U171, *U184, *U187, *U239
- **`d_bootstrap`**: X-평면도(기본형)$0$A$C5C7666B6, X-FORM_청주, X-평면도(기본형)$0$A$C5FEA68FE, X-평면도(기본형)$0$SB1703 1500, X-평면도(기본형)$0$국기계양대, X-평면도(기본형)$0$IC708, X-평면도(기본형)$0$FSDFSDF321, X-평면도(기본형)$0$A$C019C01BD, X-평면도(기본형)$0$hd1050, X-평면도(기본형)$0$A$C7D8E4760, X-평면도(기본형)$0$A$C71B42895, X-평면도(기본형)$0$KH-530S-1 TOP, X-평면도(기본형)$0$pkdr750190-1, X-평면도(기본형)$0$pkdr750190, X-평면도(기본형)$0$T1, X-평면도(기본형)$0$Ca2405caa, X-평면도(기본형)$0$pd900, X-평면도(기본형)$0$A$C49112A41, X-평면도(기본형)$0$A$C41D360DF, X-평면도(기본형)$0$FSD1500-2
