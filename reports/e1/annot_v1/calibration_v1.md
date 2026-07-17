# E1.5 calibration v1

Judges: fable5_high, grok45_xhigh, opus48_max, ornith35b_v0, sol56_xhigh, sonnet5_xhigh

| pair | n | role agree | pearson | bucket | jaccard |
| --- | ---: | ---: | ---: | ---: | ---: |
| fable5_high|grok45_xhigh | 384 | 0.7448 | 0.8378 | 0.8047 | 0.3398 |
| fable5_high|opus48_max | 384 | 0.6562 | 0.8095 | 0.7057 | 0.3171 |
| fable5_high|ornith35b_v0 | 377 | 0.5411 | 0.4545 | 0.6631 | 0.0678 |
| fable5_high|sol56_xhigh | 384 | 0.9427 | 0.8800 | 0.9271 | 0.2727 |
| fable5_high|sonnet5_xhigh | 384 | 0.6797 | 0.8504 | 0.9010 | 0.2646 |
| grok45_xhigh|opus48_max | 384 | 0.8724 | 0.8185 | 0.8854 | 0.5130 |
| grok45_xhigh|ornith35b_v0 | 377 | 0.5809 | 0.4861 | 0.5942 | 0.0904 |
| grok45_xhigh|sol56_xhigh | 384 | 0.7474 | 0.8128 | 0.8646 | 0.2649 |
| grok45_xhigh|sonnet5_xhigh | 384 | 0.8620 | 0.7472 | 0.7526 | 0.2712 |
| opus48_max|ornith35b_v0 | 377 | 0.5915 | 0.4398 | 0.5199 | 0.0955 |
| opus48_max|sol56_xhigh | 384 | 0.6615 | 0.7650 | 0.7656 | 0.1871 |
| opus48_max|sonnet5_xhigh | 384 | 0.8724 | 0.8414 | 0.7578 | 0.2896 |
| ornith35b_v0|sol56_xhigh | 377 | 0.5517 | 0.3862 | 0.6393 | 0.0468 |
| ornith35b_v0|sonnet5_xhigh | 377 | 0.5650 | 0.4363 | 0.6419 | 0.0893 |
| sol56_xhigh|sonnet5_xhigh | 384 | 0.6927 | 0.7706 | 0.8854 | 0.1605 |

Fleiss kappa (live judges, role): 0.7032530164095232
Top-tier mean role agreement: 0.7534722222222223
Top-tier mean likelihood pearson: 0.8181758001687531
Verdicts: {"B1_task_well_posed": "well_posed", "B2_ladder_visible": true, "B4_likelihood_usable": "silver_ok"}
