# W2-00 DGX-PREFLIGHT report

- Status: `COMPLETE`
- Generated (UTC): `2026-07-18T17:21:09.406401Z`
- Scope: synthetic data only; no labels, CAD, CubiCasa data, test set, or performance score was accessed or computed.
- Routing decision: `DGX_MEMORY_BOUND_ONLY`
- Cross-device promotion: `ALLOWED_FOR_MATCHING_HASHED_CONFIG`

## Fixed design

- GNN: 100,000 nodes, 500,000 directed edges, 32 input features, 64 hidden features, two mean-message-passing layers, full-graph FP32 MSE training.
- U-Net: batch 2, 1x512x512 synthetic images, base width 16, two down/up levels, FP32 BCE-with-logits training.
- GPU timing: five warm-up steps followed by 50 measured optimization steps; three repetitions; median is the headline value.
- CPU control: 2,000,000 fixed rows, six inputs to 12 context-like features, three kernel passes per repetition, three repetitions.
- TF32 and AMP are disabled; cuDNN autotuning is disabled; same code/config/data/initial-weight hashes are required.

## Throughput and peak memory

| Job | Local median | DGX median | Unit | DGX/local ratio | Local peak MiB | DGX peak MiB |
|---|---:|---:|---|---:|---:|---:|
| gnn | 3.20009e+07 | 7.37735e+06 | samples/s | 0.230535 | 386.969 | 385.969 |
| unet | 61.792 | 19.9274 | samples/s | 0.322492 | 2302.134 | 427.875 |
| cpu_feature | 2.3373e+07 | 1.25171e+07 | rows/s | 0.535538 | 1699.785 | 2270.035 |

### All repetition measurements

#### local — `local_rtx5070ti`

| Job | Rep | Elapsed s | Throughput | Unit | Steps/s or passes/s | Peak allocated MiB | Peak reserved MiB | Checkpoint save s | restore s | bytes |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| gnn | 1 | 0.156245 | 3.20009e+07 | samples/s | 320.009 | 386.969 | 570.000 | 0.00545 | 0.0021893 | 59035 |
| gnn | 2 | 0.152177 | 3.28565e+07 | samples/s | 328.565 | 386.969 | 580.000 | 0.0026029 | 0.0022055 | 59035 |
| gnn | 3 | 0.157745 | 3.16966e+07 | samples/s | 316.966 | 386.969 | 580.000 | 0.0026 | 0.0017727 | 59035 |
| unet | 1 | 1.61833 | 61.792 | samples/s | 30.896 | 2302.134 | 2312.000 | 0.0071678 | 0.0071442 | 1432559 |
| unet | 2 | 1.62825 | 61.4155 | samples/s | 30.7078 | 2302.134 | 2312.000 | 0.008431 | 0.0079282 | 1432559 |
| unet | 3 | 1.61044 | 62.0947 | samples/s | 31.0474 | 2302.134 | 2312.000 | 0.0076119 | 0.0105027 | 1432559 |
| cpu_feature | 1 | 0.256706 | 2.3373e+07 | rows/s | 11.6865 | 1699.785 RSS | N/A | N/A | N/A | N/A |
| cpu_feature | 2 | 0.25417 | 2.36062e+07 | rows/s | 11.8031 | 1699.785 RSS | N/A | N/A | N/A | N/A |
| cpu_feature | 3 | 0.263329 | 2.27852e+07 | rows/s | 11.3926 | 1699.785 RSS | N/A | N/A | N/A | N/A |

#### dgx — `dgx_gb10`

| Job | Rep | Elapsed s | Throughput | Unit | Steps/s or passes/s | Peak allocated MiB | Peak reserved MiB | Checkpoint save s | restore s | bytes |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| gnn | 1 | 0.67725 | 7.3828e+06 | samples/s | 73.828 | 385.969 | 570.000 | 0.00801813 | 0.00396566 | 58835 |
| gnn | 2 | 0.67775 | 7.37735e+06 | samples/s | 73.7735 | 385.969 | 580.000 | 0.0057436 | 0.00337179 | 58835 |
| gnn | 3 | 0.67781 | 7.37669e+06 | samples/s | 73.7669 | 385.969 | 580.000 | 0.00626235 | 0.00335437 | 58835 |
| unet | 1 | 5.01821 | 19.9274 | samples/s | 9.96372 | 427.875 | 538.000 | 0.011728 | 0.0123067 | 1432359 |
| unet | 2 | 4.99834 | 20.0066 | samples/s | 10.0033 | 427.875 | 538.000 | 0.0125139 | 0.0120824 | 1432359 |
| unet | 3 | 5.03716 | 19.8525 | samples/s | 9.92623 | 427.875 | 538.000 | 0.0113888 | 0.0119019 | 1432359 |
| cpu_feature | 1 | 0.479685 | 1.25082e+07 | rows/s | 6.25411 | 2270.035 RSS | N/A | N/A | N/A | N/A |
| cpu_feature | 2 | 0.478618 | 1.25361e+07 | rows/s | 6.26804 | 2270.035 RSS | N/A | N/A | N/A | N/A |
| cpu_feature | 3 | 0.479343 | 1.25171e+07 | rows/s | 6.25857 | 2270.035 RSS | N/A | N/A | N/A | N/A |

## Routing rule result

The sealed threshold is `2x`. The rule is evaluated per measured GPU workload; any ratio below the threshold triggers the downgrade.
GNN ratio = `0.230535x`; U-Net ratio = `0.322492x`; geometric mean = `0.272664x`; downgrade triggered = `true`.

## Same-seed equivalence bands

Band rule: `abs_delta <= absolute_band + relative_band * max(abs(local_loss), abs(dgx_loss)) at every step`. Floors are absolute `0.0001` and relative `0.001`; the larger of each floor and `5x` the within-device p99 spread is sealed. This is an engineering tolerance, not a confidence interval.

| Job | Pass | Abs band | Rel band | Abs median | Abs p95 | Abs max | Rel median | Rel p95 | Rel max | Steps outside |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| gnn | True | 0.0001 | 0.001 | 0 | 1.19209e-07 | 2.38419e-07 | 0 | 9.90518e-08 | 1.48736e-07 | none |
| unet | True | 0.0001 | 0.001 | 1.322e-05 | 4.19281e-05 | 5.317e-05 | 0.000470173 | 0.0242295 | 0.0311389 | none |

### gnn median loss curve and every stepwise deviation

| Step | Local loss | DGX loss | Signed delta | Abs delta | Rel delta | Allowed abs delta | In band |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 3.02486682 | 3.02486682 | 0 | 0 | 0 | 0.00312486682 | True |
| 2 | 2.80068684 | 2.80068684 | 0 | 0 | 0 | 0.00290068684 | True |
| 3 | 2.59978986 | 2.59978986 | 0 | 0 | 0 | 0.00269978986 | True |
| 4 | 2.42146206 | 2.42146206 | 0 | 0 | 0 | 0.00252146206 | True |
| 5 | 2.26474643 | 2.26474643 | 0 | 0 | 0 | 0.00236474643 | True |
| 6 | 2.12845373 | 2.12845373 | 0 | 0 | 0 | 0.00222845373 | True |
| 7 | 2.01116157 | 2.01116157 | 0 | 0 | 0 | 0.00211116157 | True |
| 8 | 1.911201 | 1.91120088 | -1.1920929e-07 | 1.1920929e-07 | 6.23740201e-08 | 0.002011201 | True |
| 9 | 1.8267256 | 1.82672572 | 1.1920929e-07 | 1.1920929e-07 | 6.52584502e-08 | 0.00192672572 | True |
| 10 | 1.75574434 | 1.75574434 | 0 | 0 | 0 | 0.00185574434 | True |
| 11 | 1.69617748 | 1.69617748 | 0 | 0 | 0 | 0.00179617748 | True |
| 12 | 1.64592981 | 1.64592969 | -1.1920929e-07 | 1.1920929e-07 | 7.2426715e-08 | 0.00174592981 | True |
| 13 | 1.60296297 | 1.60296273 | -2.38418579e-07 | 2.38418579e-07 | 1.48736174e-07 | 0.00170296297 | True |
| 14 | 1.56536543 | 1.56536543 | 0 | 0 | 0 | 0.00166536543 | True |
| 15 | 1.53142357 | 1.53142357 | 0 | 0 | 0 | 0.00163142357 | True |
| 16 | 1.49966013 | 1.49966013 | 0 | 0 | 0 | 0.00159966013 | True |
| 17 | 1.46886528 | 1.46886528 | 0 | 0 | 0 | 0.00156886528 | True |
| 18 | 1.43812525 | 1.43812525 | 0 | 0 | 0 | 0.00153812525 | True |
| 19 | 1.40680897 | 1.40680897 | 0 | 0 | 0 | 0.00150680897 | True |
| 20 | 1.374547 | 1.374547 | 0 | 0 | 0 | 0.001474547 | True |
| 21 | 1.3412081 | 1.34120822 | 1.1920929e-07 | 1.1920929e-07 | 8.88820153e-08 | 0.00144120822 | True |
| 22 | 1.30685651 | 1.30685639 | -1.1920929e-07 | 1.1920929e-07 | 9.1218346e-08 | 0.00140685651 | True |
| 23 | 1.27171016 | 1.27171016 | 0 | 0 | 0 | 0.00137171016 | True |
| 24 | 1.23608994 | 1.23608994 | 0 | 0 | 0 | 0.00133608994 | True |
| 25 | 1.20038366 | 1.20038366 | 0 | 0 | 0 | 0.00130038366 | True |
| 26 | 1.16500485 | 1.16500485 | 0 | 0 | 0 | 0.00126500485 | True |
| 27 | 1.13036478 | 1.13036466 | -1.1920929e-07 | 1.1920929e-07 | 1.05460903e-07 | 0.00123036478 | True |
| 28 | 1.09683335 | 1.09683323 | -1.1920929e-07 | 1.1920929e-07 | 1.08684961e-07 | 0.00119683335 | True |
| 29 | 1.06472278 | 1.06472278 | 0 | 0 | 0 | 0.00116472278 | True |
| 30 | 1.03427947 | 1.03427947 | 0 | 0 | 0 | 0.00113427947 | True |
| 31 | 1.00567293 | 1.00567293 | 0 | 0 | 0 | 0.00110567293 | True |
| 32 | 0.978991508 | 0.978991508 | 0 | 0 | 0 | 0.00107899151 | True |
| 33 | 0.954245269 | 0.954245269 | 0 | 0 | 0 | 0.00105424527 | True |
| 34 | 0.931373417 | 0.931373417 | 0 | 0 | 0 | 0.00103137342 | True |
| 35 | 0.910255551 | 0.910255551 | 0 | 0 | 0 | 0.00101025555 | True |
| 36 | 0.890728891 | 0.890728891 | 0 | 0 | 0 | 0.000990728891 | True |
| 37 | 0.872601986 | 0.872601986 | 0 | 0 | 0 | 0.000972601986 | True |
| 38 | 0.855669022 | 0.855669022 | 0 | 0 | 0 | 0.000955669022 | True |
| 39 | 0.839723945 | 0.839723885 | -5.96046448e-08 | 5.96046448e-08 | 7.09812375e-08 | 0.000939723945 | True |
| 40 | 0.824571252 | 0.824571252 | 0 | 0 | 0 | 0.000924571252 | True |
| 41 | 0.810038865 | 0.810038805 | -5.96046448e-08 | 5.96046448e-08 | 7.35824506e-08 | 0.000910038865 | True |
| 42 | 0.795983195 | 0.795983195 | 0 | 0 | 0 | 0.000895983195 | True |
| 43 | 0.782292247 | 0.782292247 | 0 | 0 | 0 | 0.000882292247 | True |
| 44 | 0.768888116 | 0.768888116 | 0 | 0 | 0 | 0.000868888116 | True |
| 45 | 0.755725741 | 0.755725682 | -5.96046448e-08 | 5.96046448e-08 | 7.88707351e-08 | 0.000855725741 | True |
| 46 | 0.74278903 | 0.74278903 | 0 | 0 | 0 | 0.00084278903 | True |
| 47 | 0.730084121 | 0.730084121 | 0 | 0 | 0 | 0.000830084121 | True |
| 48 | 0.717635989 | 0.717635989 | 0 | 0 | 0 | 0.000817635989 | True |
| 49 | 0.705479681 | 0.705479681 | 0 | 0 | 0 | 0.000805479681 | True |
| 50 | 0.693655431 | 0.693655431 | 0 | 0 | 0 | 0.000793655431 | True |

### unet median loss curve and every stepwise deviation

| Step | Local loss | DGX loss | Signed delta | Abs delta | Rel delta | Allowed abs delta | In band |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0.367221236 | 0.367201924 | -1.93119049e-05 | 1.93119049e-05 | 5.25892922e-05 | 0.000467221236 | True |
| 2 | 0.271523505 | 0.271506846 | -1.66594982e-05 | 1.66594982e-05 | 6.13556391e-05 | 0.000371523505 | True |
| 3 | 0.183237046 | 0.183227867 | -9.1791153e-06 | 9.1791153e-06 | 5.00942113e-05 | 0.000283237046 | True |
| 4 | 0.124361135 | 0.124362662 | 1.52736902e-06 | 1.52736902e-06 | 1.22815722e-05 | 0.000224362662 | True |
| 5 | 0.0954473913 | 0.0954552069 | 7.81565905e-06 | 7.81565905e-06 | 8.18777655e-05 | 0.000195455207 | True |
| 6 | 0.0807816535 | 0.0807999969 | 1.83433294e-05 | 1.83433294e-05 | 0.000227021413 | 0.000180799997 | True |
| 7 | 0.0697616786 | 0.0697850361 | 2.33575702e-05 | 2.33575702e-05 | 0.000334707431 | 0.000169785036 | True |
| 8 | 0.0605410635 | 0.0605595 | 1.84364617e-05 | 1.84364617e-05 | 0.0003044355 | 0.0001605595 | True |
| 9 | 0.0510749593 | 0.0510900989 | 1.51395798e-05 | 1.51395798e-05 | 0.000296330994 | 0.000151090099 | True |
| 10 | 0.0428751931 | 0.0428833887 | 8.19563866e-06 | 8.19563866e-06 | 0.00019111453 | 0.000142883389 | True |
| 11 | 0.035604991 | 0.0356081724 | 3.18139791e-06 | 3.18139791e-06 | 8.93445998e-05 | 0.000135608172 | True |
| 12 | 0.0308589023 | 0.0308509823 | -7.91996717e-06 | 7.91996717e-06 | 0.000256650969 | 0.000130858902 | True |
| 13 | 0.026918523 | 0.0269069243 | -1.15986913e-05 | 1.15986913e-05 | 0.000430881417 | 0.000126918523 | True |
| 14 | 0.024489671 | 0.0244755615 | -1.4109537e-05 | 1.4109537e-05 | 0.000576142367 | 0.000124489671 | True |
| 15 | 0.0222795345 | 0.022265343 | -1.41914934e-05 | 1.41914934e-05 | 0.000636974413 | 0.000122279534 | True |
| 16 | 0.0202432163 | 0.0202318579 | -1.13584101e-05 | 1.13584101e-05 | 0.000561097108 | 0.000120243216 | True |
| 17 | 0.0178343691 | 0.0178252831 | -9.08598304e-06 | 9.08598304e-06 | 0.000509464786 | 0.000117834369 | True |
| 18 | 0.015513028 | 0.0155063737 | -6.6542998e-06 | 6.6542998e-06 | 0.000428949125 | 0.000115513028 | True |
| 19 | 0.013222212 | 0.0132215871 | -6.24917448e-07 | 6.24917448e-07 | 4.72627007e-05 | 0.000113222212 | True |
| 20 | 0.0112151261 | 0.011214721 | -4.0512532e-07 | 4.0512532e-07 | 3.61231175e-05 | 0.000111215126 | True |
| 21 | 0.0096886158 | 0.00969004817 | 1.43237412e-06 | 1.43237412e-06 | 0.000147819092 | 0.000109690048 | True |
| 22 | 0.00868188031 | 0.00867964514 | -2.23517418e-06 | 2.23517418e-06 | 0.000257452775 | 0.00010868188 | True |
| 23 | 0.0081307916 | 0.00813003257 | -7.59027898e-07 | 7.59027898e-07 | 9.33522756e-05 | 0.000108130792 | True |
| 24 | 0.00791269541 | 0.0079098139 | -2.88151205e-06 | 2.88151205e-06 | 0.000364163145 | 0.000107912695 | True |
| 25 | 0.00743061258 | 0.00743274577 | 2.13319436e-06 | 2.13319436e-06 | 0.000286999505 | 0.000107432746 | True |
| 26 | 0.00679018069 | 0.00679230224 | 2.12155282e-06 | 2.12155282e-06 | 0.000312346646 | 0.000106792302 | True |
| 27 | 0.00583686866 | 0.00583683234 | -3.63215804e-08 | 3.63215804e-08 | 6.22278529e-06 | 0.000105836869 | True |
| 28 | 0.00520938542 | 0.00520923175 | -1.53668225e-07 | 1.53668225e-07 | 2.94983405e-05 | 0.000105209385 | True |
| 29 | 0.00465458725 | 0.0046547316 | 1.44354999e-07 | 1.44354999e-07 | 3.10125291e-05 | 0.000104654732 | True |
| 30 | 0.00428421376 | 0.00428784499 | 3.63122672e-06 | 3.63122672e-06 | 0.000846865203 | 0.000104287845 | True |
| 31 | 0.0039817798 | 0.0039864867 | 4.70690429e-06 | 4.70690429e-06 | 0.00118071491 | 0.000103986487 | True |
| 32 | 0.00369289145 | 0.00370069174 | 7.80029222e-06 | 7.80029222e-06 | 0.00210779302 | 0.000103700692 | True |
| 33 | 0.00348289846 | 0.00349522894 | 1.23304781e-05 | 1.23304781e-05 | 0.00352780269 | 0.000103495229 | True |
| 34 | 0.00327330176 | 0.00328977266 | 1.64709054e-05 | 1.64709054e-05 | 0.00500670018 | 0.000103289773 | True |
| 35 | 0.00310761691 | 0.00312939472 | 2.17778143e-05 | 2.17778143e-05 | 0.00695911388 | 0.000103129395 | True |
| 36 | 0.00294205896 | 0.00296977907 | 2.77201179e-05 | 2.77201179e-05 | 0.00933406737 | 0.000102969779 | True |
| 37 | 0.00274959579 | 0.002782895 | 3.32992058e-05 | 3.32992058e-05 | 0.011965671 | 0.000102782895 | True |
| 38 | 0.00258680061 | 0.00262483605 | 3.80354468e-05 | 3.80354468e-05 | 0.014490599 | 0.000102624836 | True |
| 39 | 0.00241148402 | 0.00244805822 | 3.65742017e-05 | 3.65742017e-05 | 0.0149400865 | 0.000102448058 | True |
| 40 | 0.00229398743 | 0.00232677534 | 3.27879097e-05 | 3.27879097e-05 | 0.0140915666 | 0.000102326775 | True |
| 41 | 0.0021612721 | 0.00219676481 | 3.54927033e-05 | 3.54927033e-05 | 0.0161568062 | 0.000102196765 | True |
| 42 | 0.00206978898 | 0.00210429542 | 3.45064327e-05 | 3.45064327e-05 | 0.0163980934 | 0.000102104295 | True |
| 43 | 0.00195643422 | 0.00199334882 | 3.69146001e-05 | 3.69146001e-05 | 0.0185188862 | 0.000101993349 | True |
| 44 | 0.00185950473 | 0.00190472801 | 4.5223278e-05 | 4.5223278e-05 | 0.0237426435 | 0.000101904728 | True |
| 45 | 0.00174519035 | 0.00178991572 | 4.47253697e-05 | 4.47253697e-05 | 0.0249874165 | 0.000101789916 | True |
| 46 | 0.00165433926 | 0.00170750928 | 5.31700207e-05 | 5.31700207e-05 | 0.0311389352 | 0.000101707509 | True |
| 47 | 0.00159536465 | 0.00162191549 | 2.65508424e-05 | 2.65508424e-05 | 0.0163700529 | 0.000101621915 | True |
| 48 | 0.00152513268 | 0.00156364194 | 3.85092571e-05 | 3.85092571e-05 | 0.0246279254 | 0.000101563642 | True |
| 49 | 0.00147156604 | 0.00149376283 | 2.2196793e-05 | 2.2196793e-05 | 0.0148596501 | 0.000101493763 | True |
| 50 | 0.00141518656 | 0.00144079921 | 2.56126514e-05 | 2.56126514e-05 | 0.0177766972 | 0.000101440799 | True |

## Checkpoint cost

Checkpoint time includes serialization, close, and `fsync`; restore includes deserialize, model/optimizer load, and device synchronization.

| Job | Device | Median save s | Median restore s | Median bytes | All restored hashes match |
|---|---|---:|---:|---:|---|
| gnn | local_rtx5070ti | 0.0026029 | 0.0021893 | 59035 | True |
| gnn | dgx_gb10 | 0.00626235 | 0.00337179 | 58835 | True |
| unet | local_rtx5070ti | 0.0076119 | 0.0079282 | 1432559 | True |
| unet | dgx_gb10 | 0.011728 | 0.0120824 | 1432359 | True |

## GB10-hour conversion

| Job | Steps/s or passes/s | Per hour | Per 12h cap or rows/hour | Definition |
|---|---:|---:|---:|---|
| gnn | 73.7735 steps/s | 265584 steps/h | 3.18701e+06 steps/12h | one full 100k-node/500k-edge optimization step |
| unet | 9.96372 steps/s | 35869.4 steps/h | 430433 steps/12h | one optimization step over batch size 2 of 512x512 images |
| cpu_feature | 6.25857 passes/s | 22530.8 passes/h | 4.50617e+10 rows/h | one complete 2,000,000-row feature-kernel pass |

## Budget accounting

- Local suite wall: `8.92531` s; charged RTX job wall: `6.85564` s (`0.00190434` h / 12 h cap).
- DGX suite wall: `24.4633` s; charged GB10 job wall: `22.3115` s (`0.00619765` h / 12 h cap).
- Combined local+Grace CPU-control wall: `2.87042` s (`0.000797339` h / 12 h cap).

## Provenance and launch witnesses

- Packet SHA-256: `3d2b5cb05679e8298e501ecadc73d4309a9bb7694ac60dd8bf097e8a4f15ceb1`
- `preflight.py` SHA-256: `80be8b37c078485ab73e8f7fc8a95ff7847234d441706d598ceeef790510a2b0`; same on local/DGX: `True`
- Config SHA-256: `753b3f55c143899ba1ce6a617a4ddcdd8b571a53faa9675f29e5d1f818063405`; same on local/DGX: `True`
- Remote script SHA-256: `d70cbfcb4629696384125aed61dc5a4d4821e4d11c8c5be0ba8ef8c6c5fa732a`
- DGX image: `nvcr.io/nvidia/pytorch:25.04-py3`
- DGX image ID: `sha256:7854310c53f83bdca49319813a0d1bba973c93a97849fa8ea3f26fc408d6133b`
- DGX image digest: `nvcr.io/nvidia/pytorch@sha256:d1eac6220dd98ef5870b1a76673cfb6f84451135a6d8a174cb92258a6bf4576d`
- Container: `w2_00_preflight_20260718T171918Z` (benchmark-owned, retained stopped; pre-existing vLLM containers untouched)
- Remote work directory: `/home/sunapse/w2_00_preflight_20260718T171918Z`
- Local runtime: `{"cpu_count_logical":24,"cuda_available":true,"cuda_device":{"major":12,"minor":0,"multiprocessor_count":70,"name":"NVIDIA GeForce RTX 5070 Ti","total_memory_bytes":17094475776},"cudnn":91900,"hostname":"DESKTOP-PAUL","machine":"AMD64","numpy":"1.26.4","platform":"Windows-11-10.0.26200-SP0","processor":"AMD64 Family 26 Model 68 Stepping 0, AuthenticAMD","python":"3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]","python_executable":"C:\\Users\\PAUL\\AppData\\Local\\Programs\\Python\\Python312\\python.exe","requested_device":"cuda","torch":"2.11.0+cu128","torch_cuda":"12.8","torch_import_error":null}`
- DGX runtime: `{"cpu_count_logical":20,"cuda_available":true,"cuda_device":{"major":12,"minor":1,"multiprocessor_count":48,"name":"NVIDIA GB10","total_memory_bytes":130596818944},"cudnn":90900,"hostname":"e2add015ef2e","machine":"aarch64","numpy":"1.26.4","platform":"Linux-6.17.0-1014-nvidia-aarch64-with-glibc2.39","processor":"aarch64","python":"3.12.3 (main, Feb  4 2025, 14:48:35) [GCC 13.3.0]","python_executable":"/usr/bin/python","requested_device":"cuda","torch":"2.7.0a0+79aa17489c.nv25.04","torch_cuda":"12.9","torch_import_error":null}`
- Local launch: `python 'D:\runs\e2_program\cells\w2_00_preflight\preflight.py' run --role local_rtx5070ti --device cuda --profile full --output 'D:\runs\e2_program\cells\w2_00_preflight\_local_raw.json'`
- Remote transport: `ssh mkdir → scp preflight.py+remote_preflight.sh → ssh bash remote_preflight.sh → scp dgx_raw.json; host=sunapse@172.30.1.1; key=%USERPROFILE%\.ssh\dgx_edgexpert; IdentitiesOnly=yes; BatchMode=yes`
- DGX container launch: `docker exec w2_00_preflight_20260718T171918Z python /workspace/preflight.py run --role dgx_gb10 --device cuda --profile full --output /workspace/dgx_raw.json`
- Aggregate launch: `D:\runs\e2_program\cells\w2_00_preflight\preflight.py aggregate --local D:\runs\e2_program\cells\w2_00_preflight\_local_raw.json --dgx D:\runs\e2_program\cells\w2_00_preflight\_dgx_raw.json --output D:\runs\e2_program\cells\w2_00_preflight\throughput.json --report D:\runs\e2_program\cells\w2_00_preflight\REPORT.md --packet-path D:\runs\e2_program\build\PACKET_w2_00_dgx_preflight.md --packet-sha256 3d2b5cb05679e8298e501ecadc73d4309a9bb7694ac60dd8bf097e8a4f15ceb1 --remote-script-sha256 d70cbfcb4629696384125aed61dc5a4d4821e4d11c8c5be0ba8ef8c6c5fa732a --image nvcr.io/nvidia/pytorch:25.04-py3 --image-id sha256:7854310c53f83bdca49319813a0d1bba973c93a97849fa8ea3f26fc408d6133b --image-digest nvcr.io/nvidia/pytorch@sha256:d1eac6220dd98ef5870b1a76673cfb6f84451135a6d8a174cb92258a6bf4576d --container-name w2_00_preflight_20260718T171918Z --remote-dir /home/sunapse/w2_00_preflight_20260718T171918Z --local-command python 'D:\runs\e2_program\cells\w2_00_preflight\preflight.py' run --role local_rtx5070ti --device cuda --profile full --output 'D:\runs\e2_program\cells\w2_00_preflight\_local_raw.json' --remote-transport-command ssh mkdir → scp preflight.py+remote_preflight.sh → ssh bash remote_preflight.sh → scp dgx_raw.json; host=sunapse@172.30.1.1; key=%USERPROFILE%\.ssh\dgx_edgexpert; IdentitiesOnly=yes; BatchMode=yes --dgx-command docker exec w2_00_preflight_20260718T171918Z python /workspace/preflight.py run --role dgx_gb10 --device cuda --profile full --output /workspace/dgx_raw.json`
- `throughput.json` SHA-256 at report render: `88198f7e9e4a0b75a6d281ef74724b0616ed4ba51a11203d9aee8ecca7c111d9`

## BLOCKED / failure witnesses

- None. All six requested machine/job arms completed.

## Unresolved / interpretation limits

- Measurements cover fixed synthetic FP32 micro-workloads, not full production models or datasets.
- The empirical equivalence band has three timing repetitions and 50 steps per GPU job; it is an engineering tolerance, not a confidence interval.
- Storage-specific checkpoint latency includes each host filesystem and is not isolated from filesystem cache effects.
- NVIDIA PyTorch 25.04 emits a GB10 support warning even though the CUDA allocation and full suite complete.

All per-repetition raw loss values, memory values, checkpoint witnesses, hashes, runtime metadata, and failure fields are preserved in `throughput.json` under `raw`.

CELL_COMPLETE: w2_00
