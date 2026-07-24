# E6 Calibration and IID Style-Slice Numeric Report

승계 봉인 SHA-256 — `prereg.json`: `7cc9492512980396ca0062a23d75a2a4f77cfb8ad65416f1fbefdc5e280d6083`
승계 봉인 SHA-256 — `PREREG.csv`: `191fb4ad45bf83c252041cab55d580e222e2f1a81dd3491b404b09ad8488928f`

The two inherited seals were adopted unchanged; no re-sealing was performed.

## Execution scope

- Frozen GNN-A checkpoints: inference only; seeds 17, 29, 43.
- RTX inference with deterministic destination-sorted CPU auxiliary relation reduction; two bitwise comparison passes per seed.
- Classical control: fresh sealed 30-feature HistGradientBoosting fit on train-only labels/design.
- Calibration split: deterministic family-hash cal-fit/cal-eval; temperature fit only on cal-fit.
- Reported measurement universe: cal-eval only.
- Classification threshold: 0.5 fixed; threshold search count: 0.
- Band adjudication output count: 0.
- Repository file mutation count: 0; git command count after packet read: 0; subagent count: 0.

## Inherited band text (not adjudicated)

- temperature 전후 REL≤0.03 ∧ RES≥0.03
- style drop≤0.10
- calibration 실패를 threshold 재탐색으로 덮지 않는다

## Selftest

| test | ok | numeric/detail |
|---|---|---|
| split_determinism | 1 | {"assignment_sha256": "a3f40d2c61eddc83a434ace020b2bd52c2d448051db78b65ef005aa6b23fa96e", "ok": true} |
| cal_fit_cal_eval_family_intersection_zero | 1 | {"count": 0, "ok": true} |
| GNN_A_checkpoint_hashes_unchanged | 1 | {"hashes": {"17": "612e4bf954ff5967853f7a08e66195b79dfa15250d6e9d42f88a877c92a3952c", "29": "1b4bbd004491609cfe8cfc217d18b0ec5ff344f8fee43c67b392a4c37dbc6877", "43": "ab37cf25894e8ed7f2e96ca287a21da961c68d37bcf2bd9633ae1cb9b663e2a3"}, "ok": true} |
| val_B_blocked_before_path_construction_read | 1 | {"filesystem_read_delta": 0, "ok": true, "path_construction_delta": 0} |
| test_blocked_before_path_construction_read | 1 | {"filesystem_read_delta": 0, "ok": true, "path_construction_delta": 0} |
| fixed_threshold_0_5 | 1 | {"ok": true, "threshold": 0.5} |
| universe_guards | 1 | {"ok": true, "reported_metric_required_universe": "cal-eval", "temperature_fit_required_universe": "cal-fit"} |

## Calibration split

Assignment SHA-256: `a3f40d2c61eddc83a434ace020b2bd52c2d448051db78b65ef005aa6b23fa96e`

| split | drawings | rows | families_crossing | high_quality_architectural | high_quality | colorful |
|---|---|---|---|---|---|---|
| cal_fit | 99 | 85421 | 0 | 61 | 27 | 11 |
| cal_eval | 99 | 82135 | 0 | 58 | 27 | 14 |

## Per-seed cal-eval measurements

| arm | seed | state | T | ECE | Brier | REL | RES | UNC | decomp residual | NLL | AUPRC | P | R | F1 | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GNN_A_no_pretrain | 17 | before_temperature | 1.42212342776 | 0.0300280609477 | 0.0244340143715 | 0.00920134202063 | 0.0846987683434 | 0.100529999947 | -0.000598559252444 | 0.0745866833316 | 0.97732992807 | 0.77652217912 | 0.98872543756 | 0.869869160644 | 9208 | 2650 | 105 | 70172 |
| GNN_A_no_pretrain | 17 | after_temperature | 1.42212342776 | 0.0307214188977 | 0.0228733873785 | 0.00855828442197 | 0.0861280091975 | 0.100529999947 | -8.68877926599e-05 | 0.0704353267881 | 0.97732992807 | 0.77652217912 | 0.98872543756 | 0.869869160644 | 9208 | 2650 | 105 | 70172 |
| GNN_A_no_pretrain | 29 | before_temperature | 1.72387128432 | 0.025855399042 | 0.0235715137764 | 0.00740145982749 | 0.083586330875 | 0.100529999947 | -0.000773615122867 | 0.0752062013893 | 0.975434462107 | 0.788881251074 | 0.985826264362 | 0.876425946256 | 9181 | 2457 | 132 | 70365 |
| GNN_A_no_pretrain | 29 | after_temperature | 1.72387128432 | 0.0253981992111 | 0.0209628461822 | 0.00625459072574 | 0.0857074816638 | 0.100529999947 | -0.000114262826443 | 0.0649035338468 | 0.975434462107 | 0.788881251074 | 0.985826264362 | 0.876425946256 | 9181 | 2457 | 132 | 70365 |
| GNN_A_no_pretrain | 43 | before_temperature | 1.46797427808 | 0.0276198099035 | 0.0235709019441 | 0.00796805679687 | 0.0843659845084 | 0.100529999947 | -0.000561170291038 | 0.0724878737684 | 0.976031814157 | 0.784345456094 | 0.988832814346 | 0.874798138121 | 9209 | 2532 | 104 | 70290 |
| GNN_A_no_pretrain | 43 | after_temperature | 1.46797427808 | 0.027518146757 | 0.0219002783494 | 0.00726629777899 | 0.0857894717522 | 0.100529999947 | -0.000106547624108 | 0.0673393286239 | 0.976031814157 | 0.784345456094 | 0.988832814346 | 0.874798138121 | 9209 | 2532 | 104 | 70290 |
| control_twohop_GBDT_full | 17 | before_temperature | 0.885474389248 | 0.00791126021296 | 0.0347984467661 | 0.000113838466773 | 0.0655563805438 | 0.100529999947 | -0.000289011103637 | 0.115638099985 | 0.877643651771 | 0.831349454956 | 0.712444969398 | 0.767318145021 | 6635 | 1346 | 2678 | 71476 |
| control_twohop_GBDT_full | 17 | after_temperature | 0.885474389248 | 0.00453012443987 | 0.0347710686792 | 9.9020916487e-05 | 0.0653475361763 | 0.100529999947 | -0.000510416007779 | 0.113951505476 | 0.877643651771 | 0.831349454956 | 0.712444969398 | 0.767318145021 | 6635 | 1346 | 2678 | 71476 |
| control_twohop_GBDT_full | 29 | before_temperature | 0.883856746453 | 0.00838778066368 | 0.0347542711623 | 0.000113697902208 | 0.0655570616448 | 0.100529999947 | -0.000332365041813 | 0.115449976877 | 0.877499348314 | 0.835212159595 | 0.708042521207 | 0.766387726639 | 6594 | 1301 | 2719 | 71521 |
| control_twohop_GBDT_full | 29 | after_temperature | 0.883856746453 | 0.00530279720164 | 0.0347250509546 | 0.00011170480572 | 0.0654919634202 | 0.100529999947 | -0.000424690377695 | 0.113666404586 | 0.877499348314 | 0.835212159595 | 0.708042521207 | 0.766387726639 | 6594 | 1301 | 2719 | 71521 |
| control_twohop_GBDT_full | 43 | before_temperature | 0.882601192539 | 0.00840364264465 | 0.0346981496057 | 0.000132222940902 | 0.0656686778347 | 0.100529999947 | -0.000295395447289 | 0.115456394345 | 0.878494061187 | 0.833605220228 | 0.713303983679 | 0.768776761949 | 6643 | 1326 | 2670 | 71496 |
| control_twohop_GBDT_full | 43 | after_temperature | 0.882601192539 | 0.00479728271611 | 0.0346669479321 | 0.000104754445854 | 0.0654535040982 | 0.100529999947 | -0.000514302362333 | 0.113607740647 | 0.878494061187 | 0.833605220228 | 0.713303983679 | 0.768776761949 | 6643 | 1326 | 2670 | 71496 |

## Three-seed mean and population SD

| arm | state | metric | mean | SD(pop) | min | max |
|---|---|---|---|---|---|---|
| GNN_A_no_pretrain | before_temperature | ece | 0.0278344232977 | 0.00171022825504 | 0.025855399042 | 0.0300280609477 |
| GNN_A_no_pretrain | before_temperature | brier | 0.0238588100307 | 0.000406730966678 | 0.0235709019441 | 0.0244340143715 |
| GNN_A_no_pretrain | before_temperature | brier_rel | 0.008190286215 | 0.000751413518205 | 0.00740145982749 | 0.00920134202063 |
| GNN_A_no_pretrain | before_temperature | brier_res | 0.084217027909 | 0.00046620477023 | 0.083586330875 | 0.0846987683434 |
| GNN_A_no_pretrain | before_temperature | brier_unc | 0.100529999947 | 1.38777878078e-17 | 0.100529999947 | 0.100529999947 |
| GNN_A_no_pretrain | before_temperature | brier_decomposition_residual | -0.000644448222116 | 9.26014751357e-05 | -0.000773615122867 | -0.000561170291038 |
| GNN_A_no_pretrain | before_temperature | nll | 0.0740935861631 | 0.00116323826075 | 0.0724878737684 | 0.0752062013893 |
| GNN_A_no_pretrain | before_temperature | auprc | 0.976265401445 | 0.000791252201839 | 0.975434462107 | 0.97732992807 |
| GNN_A_no_pretrain | before_temperature | precision | 0.783249628763 | 0.00510472284911 | 0.77652217912 | 0.788881251074 |
| GNN_A_no_pretrain | before_temperature | recall | 0.987794838756 | 0.00139268237649 | 0.985826264362 | 0.988832814346 |
| GNN_A_no_pretrain | before_temperature | f1 | 0.87369774834 | 0.00278759186877 | 0.869869160644 | 0.876425946256 |
| GNN_A_no_pretrain | after_temperature | ece | 0.0278792549553 | 0.00218814477069 | 0.0253981992111 | 0.0307214188977 |
| GNN_A_no_pretrain | after_temperature | brier | 0.0219121706367 | 0.00078002050639 | 0.0209628461822 | 0.0228733873785 |
| GNN_A_no_pretrain | after_temperature | brier_rel | 0.0073597243089 | 0.000942796389781 | 0.00625459072574 | 0.00855828442197 |
| GNN_A_no_pretrain | after_temperature | brier_res | 0.0858749875378 | 0.000182017515351 | 0.0857074816638 | 0.0861280091975 |
| GNN_A_no_pretrain | after_temperature | brier_unc | 0.100529999947 | 1.38777878078e-17 | 0.100529999947 | 0.100529999947 |
| GNN_A_no_pretrain | after_temperature | brier_decomposition_residual | -0.00010256608107 | 1.15249767135e-05 | -0.000114262826443 | -8.68877926599e-05 |
| GNN_A_no_pretrain | after_temperature | nll | 0.0675593964196 | 0.00226369987151 | 0.0649035338468 | 0.0704353267881 |
| GNN_A_no_pretrain | after_temperature | auprc | 0.976265401445 | 0.000791252201839 | 0.975434462107 | 0.97732992807 |
| GNN_A_no_pretrain | after_temperature | precision | 0.783249628763 | 0.00510472284911 | 0.77652217912 | 0.788881251074 |
| GNN_A_no_pretrain | after_temperature | recall | 0.987794838756 | 0.00139268237649 | 0.985826264362 | 0.988832814346 |
| GNN_A_no_pretrain | after_temperature | f1 | 0.87369774834 | 0.00278759186877 | 0.869869160644 | 0.876425946256 |
| GNN_A_no_pretrain | temperature_fit | T | 1.53798966339 | 0.132764347295 | 1.42212342776 | 1.72387128432 |
| control_twohop_GBDT_full | before_temperature | ece | 0.00823422784043 | 0.000228464390962 | 0.00791126021296 | 0.00840364264465 |
| control_twohop_GBDT_full | before_temperature | brier | 0.034750289178 | 4.1042841403e-05 | 0.0346981496057 | 0.0347984467661 |
| control_twohop_GBDT_full | before_temperature | brier_rel | 0.000119919769961 | 8.69984486464e-06 | 0.000113697902208 | 0.000132222940902 |
| control_twohop_GBDT_full | before_temperature | brier_res | 0.0655940400078 | 5.27776460157e-05 | 0.0655563805438 | 0.0656686778347 |
| control_twohop_GBDT_full | before_temperature | brier_unc | 0.100529999947 | 1.38777878078e-17 | 0.100529999947 | 0.100529999947 |
| control_twohop_GBDT_full | before_temperature | brier_decomposition_residual | -0.000305590530913 | 1.91110053184e-05 | -0.000332365041813 | -0.000289011103637 |
| control_twohop_GBDT_full | before_temperature | nll | 0.115514823736 | 8.72088343539e-05 | 0.115449976877 | 0.115638099985 |
| control_twohop_GBDT_full | before_temperature | auprc | 0.877879020424 | 0.000438871451911 | 0.877499348314 | 0.878494061187 |
| control_twohop_GBDT_full | before_temperature | precision | 0.833388944926 | 0.00158434066983 | 0.831349454956 | 0.835212159595 |
| control_twohop_GBDT_full | before_temperature | recall | 0.711263824761 | 0.00230464369262 | 0.708042521207 | 0.713303983679 |
| control_twohop_GBDT_full | before_temperature | f1 | 0.767494211203 | 0.000983233408514 | 0.766387726639 | 0.768776761949 |
| control_twohop_GBDT_full | after_temperature | ece | 0.00487673478587 | 0.000320406276196 | 0.00453012443987 | 0.00530279720164 |
| control_twohop_GBDT_full | after_temperature | brier | 0.034721022522 | 4.26024545278e-05 | 0.0346669479321 | 0.0347710686792 |
| control_twohop_GBDT_full | after_temperature | brier_rel | 0.00010516005602 | 5.18611294529e-06 | 9.9020916487e-05 | 0.00011170480572 |
| control_twohop_GBDT_full | after_temperature | brier_res | 0.0654310012315 | 6.10714960893e-05 | 0.0653475361763 | 0.0654919634202 |
| control_twohop_GBDT_full | after_temperature | brier_unc | 0.100529999947 | 1.38777878078e-17 | 0.100529999947 | 0.100529999947 |
| control_twohop_GBDT_full | after_temperature | brier_decomposition_residual | -0.000483136249269 | 4.13579163398e-05 | -0.000514302362333 | -0.000424690377695 |
| control_twohop_GBDT_full | after_temperature | nll | 0.11374188357 | 0.00015014742108 | 0.113607740647 | 0.113951505476 |
| control_twohop_GBDT_full | after_temperature | auprc | 0.877879020424 | 0.000438871451911 | 0.877499348314 | 0.878494061187 |
| control_twohop_GBDT_full | after_temperature | precision | 0.833388944926 | 0.00158434066983 | 0.831349454956 | 0.835212159595 |
| control_twohop_GBDT_full | after_temperature | recall | 0.711263824761 | 0.00230464369262 | 0.708042521207 | 0.713303983679 |
| control_twohop_GBDT_full | after_temperature | f1 | 0.767494211203 | 0.000983233408514 | 0.766387726639 | 0.768776761949 |
| control_twohop_GBDT_full | temperature_fit | T | 0.883977442747 | 0.00117607837874 | 0.882601192539 | 0.885474389248 |

## IID source-category style slices (cal-eval)

| arm | seed | state | category | drawings | rows | AUPRC | F1 | pooled-category AUPRC | pooled-category F1 |
|---|---|---|---|---|---|---|---|---|---|
| GNN_A_no_pretrain | 17 | before_temperature | pooled | 99 | 82135 | 0.97732992807 | 0.869869160644 | 0 | 0 |
| GNN_A_no_pretrain | 17 | before_temperature | high_quality_architectural | 58 | 53829 | 0.975467311378 | 0.863983845377 | 0.00186261669245 | 0.0058853152671 |
| GNN_A_no_pretrain | 17 | before_temperature | high_quality | 27 | 16627 | 0.981014052321 | 0.879379157428 | -0.00368412425051 | -0.00950999678366 |
| GNN_A_no_pretrain | 17 | before_temperature | colorful | 14 | 11679 | 0.980013153868 | 0.883720930233 | -0.0026832257974 | -0.0138517695883 |
| GNN_A_no_pretrain | 17 | after_temperature | pooled | 99 | 82135 | 0.97732992807 | 0.869869160644 | 0 | 0 |
| GNN_A_no_pretrain | 17 | after_temperature | high_quality_architectural | 58 | 53829 | 0.975467311378 | 0.863983845377 | 0.00186261669245 | 0.0058853152671 |
| GNN_A_no_pretrain | 17 | after_temperature | high_quality | 27 | 16627 | 0.981014052321 | 0.879379157428 | -0.00368412425051 | -0.00950999678366 |
| GNN_A_no_pretrain | 17 | after_temperature | colorful | 14 | 11679 | 0.980013153868 | 0.883720930233 | -0.0026832257974 | -0.0138517695883 |
| GNN_A_no_pretrain | 29 | before_temperature | pooled | 99 | 82135 | 0.975434462107 | 0.876425946256 | 0 | 0 |
| GNN_A_no_pretrain | 29 | before_temperature | high_quality_architectural | 58 | 53829 | 0.973929445786 | 0.87257051001 | 0.00150501632091 | 0.00385543624532 |
| GNN_A_no_pretrain | 29 | before_temperature | high_quality | 27 | 16627 | 0.976338398116 | 0.880872856825 | -0.000903936009739 | -0.00444691056921 |
| GNN_A_no_pretrain | 29 | before_temperature | colorful | 14 | 11679 | 0.981067360205 | 0.888248017304 | -0.0056328980985 | -0.011822071048 |
| GNN_A_no_pretrain | 29 | after_temperature | pooled | 99 | 82135 | 0.975434462107 | 0.876425946256 | 0 | 0 |
| GNN_A_no_pretrain | 29 | after_temperature | high_quality_architectural | 58 | 53829 | 0.973929445786 | 0.87257051001 | 0.00150501632091 | 0.00385543624532 |
| GNN_A_no_pretrain | 29 | after_temperature | high_quality | 27 | 16627 | 0.976338398116 | 0.880872856825 | -0.000903936009739 | -0.00444691056921 |
| GNN_A_no_pretrain | 29 | after_temperature | colorful | 14 | 11679 | 0.981067360205 | 0.888248017304 | -0.0056328980985 | -0.011822071048 |
| GNN_A_no_pretrain | 43 | before_temperature | pooled | 99 | 82135 | 0.976031814157 | 0.874798138121 | 0 | 0 |
| GNN_A_no_pretrain | 43 | before_temperature | high_quality_architectural | 58 | 53829 | 0.973556949523 | 0.869514675966 | 0.00247486463394 | 0.00528346215473 |
| GNN_A_no_pretrain | 43 | before_temperature | high_quality | 27 | 16627 | 0.980379849547 | 0.880159786951 | -0.00434803538943 | -0.00536164882971 |
| GNN_A_no_pretrain | 43 | before_temperature | colorful | 14 | 11679 | 0.980415120671 | 0.89224137931 | -0.00438330651403 | -0.0174432411893 |
| GNN_A_no_pretrain | 43 | after_temperature | pooled | 99 | 82135 | 0.976031814157 | 0.874798138121 | 0 | 0 |
| GNN_A_no_pretrain | 43 | after_temperature | high_quality_architectural | 58 | 53829 | 0.973556949523 | 0.869514675966 | 0.00247486463394 | 0.00528346215473 |
| GNN_A_no_pretrain | 43 | after_temperature | high_quality | 27 | 16627 | 0.980379849547 | 0.880159786951 | -0.00434803538943 | -0.00536164882971 |
| GNN_A_no_pretrain | 43 | after_temperature | colorful | 14 | 11679 | 0.980415120671 | 0.89224137931 | -0.00438330651403 | -0.0174432411893 |
| control_twohop_GBDT_full | 17 | before_temperature | pooled | 99 | 82135 | 0.877643651771 | 0.767318145021 | 0 | 0 |
| control_twohop_GBDT_full | 17 | before_temperature | high_quality_architectural | 58 | 53829 | 0.87301441193 | 0.759698180204 | 0.00462923984036 | 0.00761996481722 |
| control_twohop_GBDT_full | 17 | before_temperature | high_quality | 27 | 16627 | 0.895861642755 | 0.791655377946 | -0.0182179909846 | -0.024337232925 |
| control_twohop_GBDT_full | 17 | before_temperature | colorful | 14 | 11679 | 0.870322649248 | 0.765611633875 | 0.00732100252238 | 0.00170651114629 |
| control_twohop_GBDT_full | 17 | after_temperature | pooled | 99 | 82135 | 0.877643651771 | 0.767318145021 | 0 | 0 |
| control_twohop_GBDT_full | 17 | after_temperature | high_quality_architectural | 58 | 53829 | 0.87301441193 | 0.759698180204 | 0.00462923984036 | 0.00761996481722 |
| control_twohop_GBDT_full | 17 | after_temperature | high_quality | 27 | 16627 | 0.895861642755 | 0.791655377946 | -0.0182179909846 | -0.024337232925 |
| control_twohop_GBDT_full | 17 | after_temperature | colorful | 14 | 11679 | 0.870322649248 | 0.765611633875 | 0.00732100252238 | 0.00170651114629 |
| control_twohop_GBDT_full | 29 | before_temperature | pooled | 99 | 82135 | 0.877499348314 | 0.766387726639 | 0 | 0 |
| control_twohop_GBDT_full | 29 | before_temperature | high_quality_architectural | 58 | 53829 | 0.87414081819 | 0.757875948237 | 0.00335853012386 | 0.00851177840138 |
| control_twohop_GBDT_full | 29 | before_temperature | high_quality | 27 | 16627 | 0.892471746582 | 0.789545330792 | -0.0149723982681 | -0.0231576041535 |
| control_twohop_GBDT_full | 29 | before_temperature | colorful | 14 | 11679 | 0.870567033812 | 0.770815450644 | 0.00693231450182 | -0.004427724005 |
| control_twohop_GBDT_full | 29 | after_temperature | pooled | 99 | 82135 | 0.877499348314 | 0.766387726639 | 0 | 0 |
| control_twohop_GBDT_full | 29 | after_temperature | high_quality_architectural | 58 | 53829 | 0.87414081819 | 0.757875948237 | 0.00335853012386 | 0.00851177840138 |
| control_twohop_GBDT_full | 29 | after_temperature | high_quality | 27 | 16627 | 0.892471746582 | 0.789545330792 | -0.0149723982681 | -0.0231576041535 |
| control_twohop_GBDT_full | 29 | after_temperature | colorful | 14 | 11679 | 0.870567033812 | 0.770815450644 | 0.00693231450182 | -0.004427724005 |
| control_twohop_GBDT_full | 43 | before_temperature | pooled | 99 | 82135 | 0.878494061187 | 0.768776761949 | 0 | 0 |
| control_twohop_GBDT_full | 43 | before_temperature | high_quality_architectural | 58 | 53829 | 0.873898800312 | 0.761456483126 | 0.00459526087465 | 0.00732027882274 |
| control_twohop_GBDT_full | 43 | before_temperature | high_quality | 27 | 16627 | 0.89642506485 | 0.787763941527 | -0.0179310036627 | -0.018987179578 |
| control_twohop_GBDT_full | 43 | before_temperature | colorful | 14 | 11679 | 0.871468363854 | 0.774054982818 | 0.00702569733273 | -0.00527822086902 |
| control_twohop_GBDT_full | 43 | after_temperature | pooled | 99 | 82135 | 0.878494061187 | 0.768776761949 | 0 | 0 |
| control_twohop_GBDT_full | 43 | after_temperature | high_quality_architectural | 58 | 53829 | 0.873898800312 | 0.761456483126 | 0.00459526087465 | 0.00732027882274 |
| control_twohop_GBDT_full | 43 | after_temperature | high_quality | 27 | 16627 | 0.89642506485 | 0.787763941527 | -0.0179310036627 | -0.018987179578 |
| control_twohop_GBDT_full | 43 | after_temperature | colorful | 14 | 11679 | 0.871468363854 | 0.774054982818 | 0.00702569733273 | -0.00527822086902 |

## Three-seed style-slice mean and population SD

| arm | state | category | drawings | rows | metric | mean | SD(pop) |
|---|---|---|---|---|---|---|---|
| GNN_A_no_pretrain | before_temperature | pooled | 99 | 82135 | auprc | 0.976265401445 | 0.000791252201839 |
| GNN_A_no_pretrain | before_temperature | pooled | 99 | 82135 | f1 | 0.87369774834 | 0.00278759186877 |
| GNN_A_no_pretrain | before_temperature | pooled | 99 | 82135 | pooled_minus_category_auprc | 0 | 0 |
| GNN_A_no_pretrain | before_temperature | pooled | 99 | 82135 | pooled_minus_category_f1 | 0 | 0 |
| GNN_A_no_pretrain | before_temperature | high_quality_architectural | 58 | 53829 | auprc | 0.974317902229 | 0.000826859282595 |
| GNN_A_no_pretrain | before_temperature | high_quality_architectural | 58 | 53829 | f1 | 0.868689677118 | 0.00355369945315 |
| GNN_A_no_pretrain | before_temperature | high_quality_architectural | 58 | 53829 | pooled_minus_category_auprc | 0.00194749921576 | 0.000400462415752 |
| GNN_A_no_pretrain | before_temperature | high_quality_architectural | 58 | 53829 | pooled_minus_category_f1 | 0.00500807122238 | 0.000851266638595 |
| GNN_A_no_pretrain | before_temperature | high_quality | 27 | 16627 | auprc | 0.979244099995 | 0.00207089044352 |
| GNN_A_no_pretrain | before_temperature | high_quality | 27 | 16627 | f1 | 0.880137267068 | 0.000610008104242 |
| GNN_A_no_pretrain | before_temperature | high_quality | 27 | 16627 | pooled_minus_category_auprc | -0.00297869854989 | 0.00149190576079 |
| GNN_A_no_pretrain | before_temperature | high_quality | 27 | 16627 | pooled_minus_category_f1 | -0.00643951872753 | 0.00220303777259 |
| GNN_A_no_pretrain | before_temperature | colorful | 14 | 11679 | auprc | 0.980498544915 | 0.000434401852205 |
| GNN_A_no_pretrain | before_temperature | colorful | 14 | 11679 | f1 | 0.888070108949 | 0.00348073284035 |
| GNN_A_no_pretrain | before_temperature | colorful | 14 | 11679 | pooled_minus_category_auprc | -0.00423314346997 | 0.00120887092661 |
| GNN_A_no_pretrain | before_temperature | colorful | 14 | 11679 | pooled_minus_category_f1 | -0.0143723606085 | 0.00232417005936 |
| GNN_A_no_pretrain | after_temperature | pooled | 99 | 82135 | auprc | 0.976265401445 | 0.000791252201839 |
| GNN_A_no_pretrain | after_temperature | pooled | 99 | 82135 | f1 | 0.87369774834 | 0.00278759186877 |
| GNN_A_no_pretrain | after_temperature | pooled | 99 | 82135 | pooled_minus_category_auprc | 0 | 0 |
| GNN_A_no_pretrain | after_temperature | pooled | 99 | 82135 | pooled_minus_category_f1 | 0 | 0 |
| GNN_A_no_pretrain | after_temperature | high_quality_architectural | 58 | 53829 | auprc | 0.974317902229 | 0.000826859282595 |
| GNN_A_no_pretrain | after_temperature | high_quality_architectural | 58 | 53829 | f1 | 0.868689677118 | 0.00355369945315 |
| GNN_A_no_pretrain | after_temperature | high_quality_architectural | 58 | 53829 | pooled_minus_category_auprc | 0.00194749921576 | 0.000400462415752 |
| GNN_A_no_pretrain | after_temperature | high_quality_architectural | 58 | 53829 | pooled_minus_category_f1 | 0.00500807122238 | 0.000851266638595 |
| GNN_A_no_pretrain | after_temperature | high_quality | 27 | 16627 | auprc | 0.979244099995 | 0.00207089044352 |
| GNN_A_no_pretrain | after_temperature | high_quality | 27 | 16627 | f1 | 0.880137267068 | 0.000610008104242 |
| GNN_A_no_pretrain | after_temperature | high_quality | 27 | 16627 | pooled_minus_category_auprc | -0.00297869854989 | 0.00149190576079 |
| GNN_A_no_pretrain | after_temperature | high_quality | 27 | 16627 | pooled_minus_category_f1 | -0.00643951872753 | 0.00220303777259 |
| GNN_A_no_pretrain | after_temperature | colorful | 14 | 11679 | auprc | 0.980498544915 | 0.000434401852205 |
| GNN_A_no_pretrain | after_temperature | colorful | 14 | 11679 | f1 | 0.888070108949 | 0.00348073284035 |
| GNN_A_no_pretrain | after_temperature | colorful | 14 | 11679 | pooled_minus_category_auprc | -0.00423314346997 | 0.00120887092661 |
| GNN_A_no_pretrain | after_temperature | colorful | 14 | 11679 | pooled_minus_category_f1 | -0.0143723606085 | 0.00232417005936 |
| control_twohop_GBDT_full | before_temperature | pooled | 99 | 82135 | auprc | 0.877879020424 | 0.000438871451911 |
| control_twohop_GBDT_full | before_temperature | pooled | 99 | 82135 | f1 | 0.767494211203 | 0.000983233408514 |
| control_twohop_GBDT_full | before_temperature | pooled | 99 | 82135 | pooled_minus_category_auprc | 0 | 0 |
| control_twohop_GBDT_full | before_temperature | pooled | 99 | 82135 | pooled_minus_category_f1 | 0 | 0 |
| control_twohop_GBDT_full | before_temperature | high_quality_architectural | 58 | 53829 | auprc | 0.873684676811 | 0.00048413801136 |
| control_twohop_GBDT_full | before_temperature | high_quality_architectural | 58 | 53829 | f1 | 0.759676870523 | 0.00146182490954 |
| control_twohop_GBDT_full | before_temperature | high_quality_architectural | 58 | 53829 | pooled_minus_category_auprc | 0.00419434361296 | 0.000591172159891 |
| control_twohop_GBDT_full | before_temperature | high_quality_architectural | 58 | 53829 | pooled_minus_category_f1 | 0.00781734068045 | 0.000506053841017 |
| control_twohop_GBDT_full | before_temperature | high_quality | 27 | 16627 | auprc | 0.894919484729 | 0.00174602933163 |
| control_twohop_GBDT_full | before_temperature | high_quality | 27 | 16627 | f1 | 0.789654883422 | 0.00159055979367 |
| control_twohop_GBDT_full | before_temperature | high_quality | 27 | 16627 | pooled_minus_category_auprc | -0.0170404643051 | 0.00146702948869 |
| control_twohop_GBDT_full | before_temperature | high_quality | 27 | 16627 | pooled_minus_category_f1 | -0.0221606722188 | 0.00229509225171 |
| control_twohop_GBDT_full | before_temperature | colorful | 14 | 11679 | auprc | 0.870786015638 | 0.000492700226358 |
| control_twohop_GBDT_full | before_temperature | colorful | 14 | 11679 | f1 | 0.770160689112 | 0.00347793711268 |
| control_twohop_GBDT_full | before_temperature | colorful | 14 | 11679 | pooled_minus_category_auprc | 0.00709300478564 | 0.000165664951525 |
| control_twohop_GBDT_full | before_temperature | colorful | 14 | 11679 | pooled_minus_category_f1 | -0.00266647790925 | 0.00311160314402 |
| control_twohop_GBDT_full | after_temperature | pooled | 99 | 82135 | auprc | 0.877879020424 | 0.000438871451911 |
| control_twohop_GBDT_full | after_temperature | pooled | 99 | 82135 | f1 | 0.767494211203 | 0.000983233408514 |
| control_twohop_GBDT_full | after_temperature | pooled | 99 | 82135 | pooled_minus_category_auprc | 0 | 0 |
| control_twohop_GBDT_full | after_temperature | pooled | 99 | 82135 | pooled_minus_category_f1 | 0 | 0 |
| control_twohop_GBDT_full | after_temperature | high_quality_architectural | 58 | 53829 | auprc | 0.873684676811 | 0.00048413801136 |
| control_twohop_GBDT_full | after_temperature | high_quality_architectural | 58 | 53829 | f1 | 0.759676870523 | 0.00146182490954 |
| control_twohop_GBDT_full | after_temperature | high_quality_architectural | 58 | 53829 | pooled_minus_category_auprc | 0.00419434361296 | 0.000591172159892 |
| control_twohop_GBDT_full | after_temperature | high_quality_architectural | 58 | 53829 | pooled_minus_category_f1 | 0.00781734068045 | 0.000506053841017 |
| control_twohop_GBDT_full | after_temperature | high_quality | 27 | 16627 | auprc | 0.894919484729 | 0.00174602933163 |
| control_twohop_GBDT_full | after_temperature | high_quality | 27 | 16627 | f1 | 0.789654883422 | 0.00159055979367 |
| control_twohop_GBDT_full | after_temperature | high_quality | 27 | 16627 | pooled_minus_category_auprc | -0.0170404643051 | 0.00146702948869 |
| control_twohop_GBDT_full | after_temperature | high_quality | 27 | 16627 | pooled_minus_category_f1 | -0.0221606722188 | 0.00229509225171 |
| control_twohop_GBDT_full | after_temperature | colorful | 14 | 11679 | auprc | 0.870786015638 | 0.000492700226358 |
| control_twohop_GBDT_full | after_temperature | colorful | 14 | 11679 | f1 | 0.770160689112 | 0.00347793711268 |
| control_twohop_GBDT_full | after_temperature | colorful | 14 | 11679 | pooled_minus_category_auprc | 0.00709300478564 | 0.000165664951525 |
| control_twohop_GBDT_full | after_temperature | colorful | 14 | 11679 | pooled_minus_category_f1 | -0.00266647790925 | 0.00311160314402 |

## Reliability diagram numeric table (cal-eval)

| arm | seed | state | bin | low | high | count | conf | acc | signed gap | abs gap |
|---|---|---|---|---|---|---|---|---|---|---|
| GNN_A_no_pretrain | 17 | before_temperature | 0 | 0 | 0.1 | 67982 | 0.0023211344522 | 0.000353034626813 | 0.00196809982538 | 0.00196809982538 |
| GNN_A_no_pretrain | 17 | before_temperature | 1 | 0.1 | 0.2 | 940 | 0.145209389687 | 0.018085106383 | 0.127124283304 | 0.127124283304 |
| GNN_A_no_pretrain | 17 | before_temperature | 2 | 0.2 | 0.3 | 592 | 0.246682023378 | 0.0253378378378 | 0.22134418554 | 0.22134418554 |
| GNN_A_no_pretrain | 17 | before_temperature | 3 | 0.3 | 0.4 | 393 | 0.349790730473 | 0.058524173028 | 0.291266557445 | 0.291266557445 |
| GNN_A_no_pretrain | 17 | before_temperature | 4 | 0.4 | 0.5 | 370 | 0.446880070905 | 0.0702702702703 | 0.376609800635 | 0.376609800635 |
| GNN_A_no_pretrain | 17 | before_temperature | 5 | 0.5 | 0.6 | 312 | 0.549847119512 | 0.0833333333333 | 0.466513786178 | 0.466513786178 |
| GNN_A_no_pretrain | 17 | before_temperature | 6 | 0.6 | 0.7 | 404 | 0.654321024619 | 0.155940594059 | 0.498380430559 | 0.498380430559 |
| GNN_A_no_pretrain | 17 | before_temperature | 7 | 0.7 | 0.8 | 571 | 0.755622038699 | 0.285464098074 | 0.470157940626 | 0.470157940626 |
| GNN_A_no_pretrain | 17 | before_temperature | 8 | 0.8 | 0.9 | 2107 | 0.860776164858 | 0.476032273374 | 0.384743891483 | 0.384743891483 |
| GNN_A_no_pretrain | 17 | before_temperature | 9 | 0.9 | 1 | 8464 | 0.987145545542 | 0.939626654064 | 0.0475188914778 | 0.0475188914778 |
| GNN_A_no_pretrain | 17 | after_temperature | 0 | 0 | 0.1 | 66725 | 0.00427317193917 | 0.000179842637692 | 0.00409332930147 | 0.00409332930147 |
| GNN_A_no_pretrain | 17 | after_temperature | 1 | 0.1 | 0.2 | 1514 | 0.142544674638 | 0.00924702774108 | 0.133297646897 | 0.133297646897 |
| GNN_A_no_pretrain | 17 | after_temperature | 2 | 0.2 | 0.3 | 891 | 0.2473205688 | 0.023569023569 | 0.223751545231 | 0.223751545231 |
| GNN_A_no_pretrain | 17 | after_temperature | 3 | 0.3 | 0.4 | 632 | 0.347599128493 | 0.0300632911392 | 0.317535837354 | 0.317535837354 |
| GNN_A_no_pretrain | 17 | after_temperature | 4 | 0.4 | 0.5 | 515 | 0.449230204461 | 0.0757281553398 | 0.373502049121 | 0.373502049121 |
| GNN_A_no_pretrain | 17 | after_temperature | 5 | 0.5 | 0.6 | 455 | 0.551266586547 | 0.0989010989011 | 0.452365487646 | 0.452365487646 |
| GNN_A_no_pretrain | 17 | after_temperature | 6 | 0.6 | 0.7 | 613 | 0.652690611721 | 0.213703099511 | 0.43898751221 | 0.43898751221 |
| GNN_A_no_pretrain | 17 | after_temperature | 7 | 0.7 | 0.8 | 1721 | 0.764484960454 | 0.444509006392 | 0.319975954062 | 0.319975954062 |
| GNN_A_no_pretrain | 17 | after_temperature | 8 | 0.8 | 0.9 | 1693 | 0.840047955158 | 0.588304784406 | 0.251743170752 | 0.251743170752 |
| GNN_A_no_pretrain | 17 | after_temperature | 9 | 0.9 | 1 | 7376 | 0.986328555847 | 0.985764642082 | 0.000563913764402 | 0.000563913764402 |
| GNN_A_no_pretrain | 29 | before_temperature | 0 | 0 | 0.1 | 69093 | 0.00142430665075 | 0.000636822832993 | 0.000787483817752 | 0.000787483817752 |
| GNN_A_no_pretrain | 29 | before_temperature | 1 | 0.1 | 0.2 | 542 | 0.1440315855 | 0.0313653136531 | 0.112666271847 | 0.112666271847 |
| GNN_A_no_pretrain | 29 | before_temperature | 2 | 0.2 | 0.3 | 352 | 0.245317442216 | 0.0568181818182 | 0.188499260397 | 0.188499260397 |
| GNN_A_no_pretrain | 29 | before_temperature | 3 | 0.3 | 0.4 | 267 | 0.346210360862 | 0.0823970037453 | 0.263813357117 | 0.263813357117 |
| GNN_A_no_pretrain | 29 | before_temperature | 4 | 0.4 | 0.5 | 243 | 0.450711367797 | 0.119341563786 | 0.331369804011 | 0.331369804011 |
| GNN_A_no_pretrain | 29 | before_temperature | 5 | 0.5 | 0.6 | 255 | 0.550640519226 | 0.109803921569 | 0.440836597658 | 0.440836597658 |
| GNN_A_no_pretrain | 29 | before_temperature | 6 | 0.6 | 0.7 | 281 | 0.65197747967 | 0.17793594306 | 0.474041536609 | 0.474041536609 |
| GNN_A_no_pretrain | 29 | before_temperature | 7 | 0.7 | 0.8 | 421 | 0.757400240723 | 0.266033254157 | 0.491366986566 | 0.491366986566 |
| GNN_A_no_pretrain | 29 | before_temperature | 8 | 0.8 | 0.9 | 1753 | 0.863449947533 | 0.460924130063 | 0.402525817471 | 0.402525817471 |
| GNN_A_no_pretrain | 29 | before_temperature | 9 | 0.9 | 1 | 8928 | 0.987425339338 | 0.916554659498 | 0.0708706798399 | 0.0708706798399 |
| GNN_A_no_pretrain | 29 | after_temperature | 0 | 0 | 0.1 | 67673 | 0.00381957116525 | 0.000192100246775 | 0.00362747091848 | 0.00362747091848 |
| GNN_A_no_pretrain | 29 | after_temperature | 1 | 0.1 | 0.2 | 1275 | 0.143670677915 | 0.0235294117647 | 0.12014126615 | 0.12014126615 |
| GNN_A_no_pretrain | 29 | after_temperature | 2 | 0.2 | 0.3 | 641 | 0.246247432668 | 0.0234009360374 | 0.22284649663 | 0.22284649663 |
| GNN_A_no_pretrain | 29 | after_temperature | 3 | 0.3 | 0.4 | 503 | 0.348625858579 | 0.0616302186879 | 0.286995639891 | 0.286995639891 |
| GNN_A_no_pretrain | 29 | after_temperature | 4 | 0.4 | 0.5 | 405 | 0.451025759016 | 0.106172839506 | 0.34485291951 | 0.34485291951 |
| GNN_A_no_pretrain | 29 | after_temperature | 5 | 0.5 | 0.6 | 433 | 0.549734087372 | 0.140877598152 | 0.40885648922 | 0.40885648922 |
| GNN_A_no_pretrain | 29 | after_temperature | 6 | 0.6 | 0.7 | 598 | 0.655767664513 | 0.255852842809 | 0.399914821704 | 0.399914821704 |
| GNN_A_no_pretrain | 29 | after_temperature | 7 | 0.7 | 0.8 | 2116 | 0.756797891491 | 0.479206049149 | 0.277591842342 | 0.277591842342 |
| GNN_A_no_pretrain | 29 | after_temperature | 8 | 0.8 | 0.9 | 1126 | 0.844319934754 | 0.651865008881 | 0.192454925873 | 0.192454925873 |
| GNN_A_no_pretrain | 29 | after_temperature | 9 | 0.9 | 1 | 7365 | 0.985645320658 | 0.980176510523 | 0.00546881013531 | 0.00546881013531 |
| GNN_A_no_pretrain | 43 | before_temperature | 0 | 0 | 0.1 | 68393 | 0.00189582376529 | 0.000380155863904 | 0.00151566790139 | 0.00151566790139 |
| GNN_A_no_pretrain | 43 | before_temperature | 1 | 0.1 | 0.2 | 827 | 0.144054484573 | 0.0193470374849 | 0.124707447088 | 0.124707447088 |
| GNN_A_no_pretrain | 43 | before_temperature | 2 | 0.2 | 0.3 | 513 | 0.247086367964 | 0.0311890838207 | 0.215897284143 | 0.215897284143 |
| GNN_A_no_pretrain | 43 | before_temperature | 3 | 0.3 | 0.4 | 354 | 0.347441768411 | 0.0508474576271 | 0.296594310783 | 0.296594310783 |
| GNN_A_no_pretrain | 43 | before_temperature | 4 | 0.4 | 0.5 | 307 | 0.448241253047 | 0.0912052117264 | 0.35703604132 | 0.35703604132 |
| GNN_A_no_pretrain | 43 | before_temperature | 5 | 0.5 | 0.6 | 280 | 0.548485090477 | 0.114285714286 | 0.434199376191 | 0.434199376191 |
| GNN_A_no_pretrain | 43 | before_temperature | 6 | 0.6 | 0.7 | 386 | 0.653246977786 | 0.212435233161 | 0.440811744626 | 0.440811744626 |
| GNN_A_no_pretrain | 43 | before_temperature | 7 | 0.7 | 0.8 | 608 | 0.757108355921 | 0.304276315789 | 0.452832040132 | 0.452832040132 |
| GNN_A_no_pretrain | 43 | before_temperature | 8 | 0.8 | 0.9 | 1979 | 0.860706946445 | 0.489641232946 | 0.371065713499 | 0.371065713499 |
| GNN_A_no_pretrain | 43 | before_temperature | 9 | 0.9 | 1 | 8488 | 0.986805974229 | 0.935556079171 | 0.0512498950587 | 0.0512498950587 |
| GNN_A_no_pretrain | 43 | after_temperature | 0 | 0 | 0.1 | 67209 | 0.00354608170776 | 0.000208305435284 | 0.00333777627247 | 0.00333777627247 |
| GNN_A_no_pretrain | 43 | after_temperature | 1 | 0.1 | 0.2 | 1348 | 0.143764145911 | 0.0103857566766 | 0.133378389234 | 0.133378389234 |
| GNN_A_no_pretrain | 43 | after_temperature | 2 | 0.2 | 0.3 | 807 | 0.246377293946 | 0.0210656753408 | 0.225311618606 | 0.225311618606 |
| GNN_A_no_pretrain | 43 | after_temperature | 3 | 0.3 | 0.4 | 585 | 0.348071579125 | 0.042735042735 | 0.30533653639 | 0.30533653639 |
| GNN_A_no_pretrain | 43 | after_temperature | 4 | 0.4 | 0.5 | 445 | 0.44977915529 | 0.076404494382 | 0.373374660908 | 0.373374660908 |
| GNN_A_no_pretrain | 43 | after_temperature | 5 | 0.5 | 0.6 | 444 | 0.552397547909 | 0.15990990991 | 0.392487637999 | 0.392487637999 |
| GNN_A_no_pretrain | 43 | after_temperature | 6 | 0.6 | 0.7 | 613 | 0.653241425173 | 0.254486133768 | 0.398755291405 | 0.398755291405 |
| GNN_A_no_pretrain | 43 | after_temperature | 7 | 0.7 | 0.8 | 1737 | 0.759995435183 | 0.459988485895 | 0.300006949288 | 0.300006949288 |
| GNN_A_no_pretrain | 43 | after_temperature | 8 | 0.8 | 0.9 | 1628 | 0.839509142829 | 0.601351351351 | 0.238157791477 | 0.238157791477 |
| GNN_A_no_pretrain | 43 | after_temperature | 9 | 0.9 | 1 | 7319 | 0.984553323576 | 0.984287470966 | 0.000265852610247 | 0.000265852610247 |
| control_twohop_GBDT_full | 17 | before_temperature | 0 | 0 | 0.1 | 65278 | 0.0119961941778 | 0.00595912864977 | 0.00603706552807 | 0.00603706552807 |
| control_twohop_GBDT_full | 17 | before_temperature | 1 | 0.1 | 0.2 | 3758 | 0.142170102278 | 0.143161255987 | -0.000991153708876 | 0.000991153708876 |
| control_twohop_GBDT_full | 17 | before_temperature | 2 | 0.2 | 0.3 | 2228 | 0.247863102989 | 0.254937163375 | -0.0070740603861 | 0.0070740603861 |
| control_twohop_GBDT_full | 17 | before_temperature | 3 | 0.3 | 0.4 | 1535 | 0.347358008714 | 0.371335504886 | -0.0239774961725 | 0.0239774961725 |
| control_twohop_GBDT_full | 17 | before_temperature | 4 | 0.4 | 0.5 | 1355 | 0.447933648581 | 0.452398523985 | -0.00446487540418 | 0.00446487540418 |
| control_twohop_GBDT_full | 17 | before_temperature | 5 | 0.5 | 0.6 | 1387 | 0.551098238326 | 0.566690699351 | -0.0155924610252 | 0.0155924610252 |
| control_twohop_GBDT_full | 17 | before_temperature | 6 | 0.6 | 0.7 | 1104 | 0.648218201442 | 0.682971014493 | -0.0347528130512 | 0.0347528130512 |
| control_twohop_GBDT_full | 17 | before_temperature | 7 | 0.7 | 0.8 | 945 | 0.749218535652 | 0.75873015873 | -0.00951162307865 | 0.00951162307865 |
| control_twohop_GBDT_full | 17 | before_temperature | 8 | 0.8 | 0.9 | 1189 | 0.853814940447 | 0.903280067283 | -0.0494651268366 | 0.0494651268366 |
| control_twohop_GBDT_full | 17 | before_temperature | 9 | 0.9 | 1 | 3356 | 0.964968325266 | 0.984505363528 | -0.0195370382616 | 0.0195370382616 |
| control_twohop_GBDT_full | 17 | after_temperature | 0 | 0 | 0.1 | 66608 | 0.00944399543738 | 0.00816718712467 | 0.00127680831271 | 0.00127680831271 |
| control_twohop_GBDT_full | 17 | after_temperature | 1 | 0.1 | 0.2 | 3066 | 0.143641586423 | 0.170580560992 | -0.0269389745682 | 0.0269389745682 |
| control_twohop_GBDT_full | 17 | after_temperature | 2 | 0.2 | 0.3 | 1928 | 0.245916338133 | 0.281639004149 | -0.0357226660159 | 0.0357226660159 |
| control_twohop_GBDT_full | 17 | after_temperature | 3 | 0.3 | 0.4 | 1367 | 0.34727182073 | 0.389904901244 | -0.0426330805131 | 0.0426330805131 |
| control_twohop_GBDT_full | 17 | after_temperature | 4 | 0.4 | 0.5 | 1185 | 0.448213831493 | 0.451476793249 | -0.00326296175576 | 0.00326296175576 |
| control_twohop_GBDT_full | 17 | after_temperature | 5 | 0.5 | 0.6 | 1231 | 0.551379483248 | 0.553208773355 | -0.00182929010662 | 0.00182929010662 |
| control_twohop_GBDT_full | 17 | after_temperature | 6 | 0.6 | 0.7 | 1057 | 0.648397340018 | 0.666982024598 | -0.0185846845803 | 0.0185846845803 |
| control_twohop_GBDT_full | 17 | after_temperature | 7 | 0.7 | 0.8 | 891 | 0.749065723247 | 0.75645342312 | -0.00738769987295 | 0.00738769987295 |
| control_twohop_GBDT_full | 17 | after_temperature | 8 | 0.8 | 0.9 | 1112 | 0.854587953378 | 0.862410071942 | -0.00782211856477 | 0.00782211856477 |
| control_twohop_GBDT_full | 17 | after_temperature | 9 | 0.9 | 1 | 3690 | 0.970123200061 | 0.979945799458 | -0.00982259939704 | 0.00982259939704 |
| control_twohop_GBDT_full | 29 | before_temperature | 0 | 0 | 0.1 | 65249 | 0.0120940342586 | 0.00605373262425 | 0.00604030163433 | 0.00604030163433 |
| control_twohop_GBDT_full | 29 | before_temperature | 1 | 0.1 | 0.2 | 3713 | 0.142890240128 | 0.136816590358 | 0.00607364976999 | 0.00607364976999 |
| control_twohop_GBDT_full | 29 | before_temperature | 2 | 0.2 | 0.3 | 2268 | 0.246347687407 | 0.26102292769 | -0.0146752402827 | 0.0146752402827 |
| control_twohop_GBDT_full | 29 | before_temperature | 3 | 0.3 | 0.4 | 1613 | 0.346565482689 | 0.364538127712 | -0.0179726450235 | 0.0179726450235 |
| control_twohop_GBDT_full | 29 | before_temperature | 4 | 0.4 | 0.5 | 1397 | 0.448799369962 | 0.455261274159 | -0.0064619041973 | 0.0064619041973 |
| control_twohop_GBDT_full | 29 | before_temperature | 5 | 0.5 | 0.6 | 1306 | 0.550042395937 | 0.574272588055 | -0.0242301921182 | 0.0242301921182 |
| control_twohop_GBDT_full | 29 | before_temperature | 6 | 0.6 | 0.7 | 1068 | 0.647640636752 | 0.674157303371 | -0.0265166666191 | 0.0265166666191 |
| control_twohop_GBDT_full | 29 | before_temperature | 7 | 0.7 | 0.8 | 962 | 0.74802528568 | 0.762993762994 | -0.0149684773141 | 0.0149684773141 |
| control_twohop_GBDT_full | 29 | before_temperature | 8 | 0.8 | 0.9 | 1184 | 0.852269702012 | 0.897804054054 | -0.0455343520418 | 0.0455343520418 |
| control_twohop_GBDT_full | 29 | before_temperature | 9 | 0.9 | 1 | 3375 | 0.964243590672 | 0.985777777778 | -0.0215341871053 | 0.0215341871053 |
| control_twohop_GBDT_full | 29 | after_temperature | 0 | 0 | 0.1 | 66533 | 0.00942560773632 | 0.00792088136714 | 0.00150472636918 | 0.00150472636918 |
| control_twohop_GBDT_full | 29 | after_temperature | 1 | 0.1 | 0.2 | 3142 | 0.144446134408 | 0.168682367919 | -0.0242362335108 | 0.0242362335108 |
| control_twohop_GBDT_full | 29 | after_temperature | 2 | 0.2 | 0.3 | 1950 | 0.246957340311 | 0.287692307692 | -0.0407349673815 | 0.0407349673815 |
| control_twohop_GBDT_full | 29 | after_temperature | 3 | 0.3 | 0.4 | 1396 | 0.347656640647 | 0.386103151862 | -0.0384465112151 | 0.0384465112151 |
| control_twohop_GBDT_full | 29 | after_temperature | 4 | 0.4 | 0.5 | 1219 | 0.449348286821 | 0.461033634126 | -0.0116853473054 | 0.0116853473054 |
| control_twohop_GBDT_full | 29 | after_temperature | 5 | 0.5 | 0.6 | 1160 | 0.550265762691 | 0.561206896552 | -0.0109411338603 | 0.0109411338603 |
| control_twohop_GBDT_full | 29 | after_temperature | 6 | 0.6 | 0.7 | 1020 | 0.648314077115 | 0.671568627451 | -0.0232545503361 | 0.0232545503361 |
| control_twohop_GBDT_full | 29 | after_temperature | 7 | 0.7 | 0.8 | 920 | 0.750312165119 | 0.732608695652 | 0.0177034694665 | 0.0177034694665 |
| control_twohop_GBDT_full | 29 | after_temperature | 8 | 0.8 | 0.9 | 1083 | 0.854169113965 | 0.865189289012 | -0.0110201750474 | 0.0110201750474 |
| control_twohop_GBDT_full | 29 | after_temperature | 9 | 0.9 | 1 | 3712 | 0.969747120037 | 0.982489224138 | -0.0127421041012 | 0.0127421041012 |
| control_twohop_GBDT_full | 43 | before_temperature | 0 | 0 | 0.1 | 65286 | 0.0122469906969 | 0.00608093618846 | 0.00616605450847 | 0.00616605450847 |
| control_twohop_GBDT_full | 43 | before_temperature | 1 | 0.1 | 0.2 | 3726 | 0.141893091053 | 0.138754696726 | 0.00313839432694 | 0.00313839432694 |
| control_twohop_GBDT_full | 43 | before_temperature | 2 | 0.2 | 0.3 | 2217 | 0.24563570831 | 0.251691474966 | -0.00605576665585 | 0.00605576665585 |
| control_twohop_GBDT_full | 43 | before_temperature | 3 | 0.3 | 0.4 | 1612 | 0.346405027061 | 0.375310173697 | -0.0289051466366 | 0.0289051466366 |
| control_twohop_GBDT_full | 43 | before_temperature | 4 | 0.4 | 0.5 | 1325 | 0.448852563046 | 0.447547169811 | 0.00130539323458 | 0.00130539323458 |
| control_twohop_GBDT_full | 43 | before_temperature | 5 | 0.5 | 0.6 | 1323 | 0.55016778867 | 0.575207860922 | -0.0250400722521 | 0.0250400722521 |
| control_twohop_GBDT_full | 43 | before_temperature | 6 | 0.6 | 0.7 | 1128 | 0.647064658659 | 0.675531914894 | -0.0284672562343 | 0.0284672562343 |
| control_twohop_GBDT_full | 43 | before_temperature | 7 | 0.7 | 0.8 | 1012 | 0.750187440121 | 0.762845849802 | -0.012658409681 | 0.012658409681 |
| control_twohop_GBDT_full | 43 | before_temperature | 8 | 0.8 | 0.9 | 1224 | 0.853636556271 | 0.906862745098 | -0.0532261888275 | 0.0532261888275 |
| control_twohop_GBDT_full | 43 | before_temperature | 9 | 0.9 | 1 | 3282 | 0.964950069079 | 0.986593540524 | -0.021643471445 | 0.021643471445 |
| control_twohop_GBDT_full | 43 | after_temperature | 0 | 0 | 0.1 | 66692 | 0.00960372494195 | 0.00833683200384 | 0.00126689293811 | 0.00126689293811 |
| control_twohop_GBDT_full | 43 | after_temperature | 1 | 0.1 | 0.2 | 3056 | 0.145457054497 | 0.168520942408 | -0.0230638879114 | 0.0230638879114 |
| control_twohop_GBDT_full | 43 | after_temperature | 2 | 0.2 | 0.3 | 1868 | 0.246853456767 | 0.291755888651 | -0.0449024318844 | 0.0449024318844 |
| control_twohop_GBDT_full | 43 | after_temperature | 3 | 0.3 | 0.4 | 1378 | 0.346356209825 | 0.377358490566 | -0.031002280741 | 0.031002280741 |
| control_twohop_GBDT_full | 43 | after_temperature | 4 | 0.4 | 0.5 | 1172 | 0.448425339229 | 0.455631399317 | -0.00720606008823 | 0.00720606008823 |
| control_twohop_GBDT_full | 43 | after_temperature | 5 | 0.5 | 0.6 | 1195 | 0.551451369351 | 0.577405857741 | -0.0259544883897 | 0.0259544883897 |
| control_twohop_GBDT_full | 43 | after_temperature | 6 | 0.6 | 0.7 | 1053 | 0.648968346416 | 0.641975308642 | 0.00699303777432 | 0.00699303777432 |
| control_twohop_GBDT_full | 43 | after_temperature | 7 | 0.7 | 0.8 | 930 | 0.750651735821 | 0.75376344086 | -0.0031117050391 | 0.0031117050391 |
| control_twohop_GBDT_full | 43 | after_temperature | 8 | 0.8 | 0.9 | 1138 | 0.85304277832 | 0.870826010545 | -0.017783232225 | 0.017783232225 |
| control_twohop_GBDT_full | 43 | after_temperature | 9 | 0.9 | 1 | 3653 | 0.969752237559 | 0.98138516288 | -0.0116329253207 | 0.0116329253207 |

## Direction numeric profile (cal-eval)

| arm | seed | state | recall@0.5 | recall-0.99 | mean_p-positive_rate | positive gap mass | negative gap mass | positive-bin row frac | negative-bin row frac |
|---|---|---|---|---|---|---|---|---|---|
| GNN_A_no_pretrain | 17 | before_temperature | 0.98872543756 | -0.0012745624396 | 0.0300280609477 | 0.0300280609477 | 0 | 1 | 0 |
| GNN_A_no_pretrain | 17 | after_temperature | 0.98872543756 | -0.0012745624396 | 0.0307214188977 | 0.0307214188977 | 0 | 1 | 0 |
| GNN_A_no_pretrain | 29 | before_temperature | 0.985826264362 | -0.00417373563835 | 0.025855399042 | 0.025855399042 | 0 | 1 | 0 |
| GNN_A_no_pretrain | 29 | after_temperature | 0.985826264362 | -0.00417373563835 | 0.0253981992111 | 0.0253981992111 | 0 | 1 | 0 |
| GNN_A_no_pretrain | 43 | before_temperature | 0.988832814346 | -0.00116718565446 | 0.0276198099035 | 0.0276198099035 | 0 | 1 | 0 |
| GNN_A_no_pretrain | 43 | after_temperature | 0.988832814346 | -0.00116718565446 | 0.027518146757 | 0.027518146757 | 0 | 1 | 0 |
| control_twohop_GBDT_full | 17 | before_temperature | 0.712444969398 | -0.277555030602 | 0.00168483313437 | 0.00479804667367 | -0.00311321353929 | 0.794764716625 | 0.205235283375 |
| control_twohop_GBDT_full | 17 | after_temperature | 0.712444969398 | -0.277555030602 | -0.00245924970697 | 0.00103543736645 | -0.00349468707342 | 0.810957569855 | 0.189042430145 |
| control_twohop_GBDT_full | 29 | before_temperature | 0.708042521207 | -0.281957478793 | 0.00175832277418 | 0.00507305171893 | -0.00331472894475 | 0.839617702563 | 0.160382297437 |
| control_twohop_GBDT_full | 29 | after_temperature | 0.708042521207 | -0.281957478793 | -0.00246841109512 | 0.00141719305326 | -0.00388560414838 | 0.82124551044 | 0.17875448956 |
| control_twohop_GBDT_full | 43 | before_temperature | 0.713303983679 | -0.276696016321 | 0.0017255431577 | 0.00506459290117 | -0.00333904974348 | 0.856358434285 | 0.143641565715 |
| control_twohop_GBDT_full | 43 | after_temperature | 0.713303983679 | -0.276696016321 | -0.00256059208227 | 0.00111834531692 | -0.00367893739919 | 0.824800633104 | 0.175199366896 |

Signed gap is mean probability minus positive rate; positive sign is overconfidence.

## Temperature invariance measurements

| arm | seed | decision mismatch | pooled AUPRC delta | pooled F1 delta | max style AUPRC delta | max style F1 delta |
|---|---|---|---|---|---|---|
| GNN_A_no_pretrain | 17 | 0 | 0 | 0 | 0 | 0 |
| GNN_A_no_pretrain | 29 | 0 | 0 | 0 | 0 | 0 |
| GNN_A_no_pretrain | 43 | 0 | 0 | 0 | 1.11022302463e-16 | 0 |
| control_twohop_GBDT_full | 17 | 0 | 0 | 0 | 0 | 0 |
| control_twohop_GBDT_full | 29 | 0 | -1.11022302463e-16 | 0 | 2.22044604925e-16 | 0 |
| control_twohop_GBDT_full | 43 | 0 | 0 | 0 | 0 | 0 |

## Data and resource audit

| measurement | value |
|---|---|
| val-A drawings | 198 |
| val-A rows | 167556 |
| val-A positives | 19584 |
| val-A directed edges | 4082196 |
| val-B reads | 0 |
| test reads | 0 |
| original CAD reads | 0 |
| RTX inference seconds | 14.6638572 |
| wall seconds | 165.7611982 |
| peak RSS bytes | 1859694592 |
| peak CUDA allocated bytes | 36148224 |

## Explicit style limitation

This is IID source-category slice measurement of frozen models, not held-out-style retraining OOD; a true OOD arm belongs to a future preregistration.

## Reproducibility

휘발 필드 제외 수치 전 필드 동일

Stable numeric measurement SHA-256: `d5a42a29765bf5d2a59e15594eb8e5ee8137cdeeba714ae32ecff7710192f734`
GNN-A repeat probability bitwise equality (all seeds): 1

## Unresolved

- The required load_workspace_dependencies surface for @oai/artifact-tool is not available in this runtime; the inherited seal authorizes a single row-complete evidence.csv fallback, and no alternate workbook library was used.
- This is IID source-category slice measurement of frozen models, not held-out-style retraining OOD; a true OOD arm belongs to a future preregistration.

## Artifact hashes

| artifact | SHA-256 |
|---|---|
| e6_calibration_ood_py_sha256 | 06fcbb8ff8d2ebf0eee38c4f8e729e3d3bbec22c151cfa4afa98a50fb5cf9f9f |
| evidence_csv_sha256 | 4745e84a0017a51ce385f1f39f09ef7d9627f249565d7d342a9e48f679b15e8e |
| prereg_json_sha256 | 7cc9492512980396ca0062a23d75a2a4f77cfb8ad65416f1fbefdc5e280d6083 |
| prereg_csv_sha256 | 191fb4ad45bf83c252041cab55d580e222e2f1a81dd3491b404b09ad8488928f |
| results_json_sha256 | 055d504edbc60e105cbc66d1c10de68463f09530a3d984604f2ddce12bc6a492 |

CELL_COMPLETE: e6_calibration_ood
