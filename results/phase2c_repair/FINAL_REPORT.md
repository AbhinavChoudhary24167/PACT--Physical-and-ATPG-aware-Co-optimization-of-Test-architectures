# PACT Phase-2C-R authorized continuation

Final classification: **PACT_PHASE2CR_SEED11_REQUALIFIED**.
Execution: **PACT_PHASE2CR_TOPOLOGY_PASS**. Decision: **MULTISEED_REPAIR_RERUN_JUSTIFIED**.

## Attempt 1 — preserved

PACT_PHASE2CR_TOPOLOGY_FAIL: the representative audit compared compensated built-in sum with sequential predictor addition. The run stopped correctly; scientific results were not evaluated. Initial witness remains FAIL / FLOAT_REDUCTION_ORDER. Original reports, test results and pre-fix runner are in attempt1/; the original witness.log remains at its original path with the same SHA256.

## Authorized continuation — required answers

1. The exact failed assertion was built-in sum(audit HPWL terms) == predictor M5. See FLOAT_REDUCTION_AUDIT.md and its JSON.
2. Yes: 1.4210854715202004e-14 um is solely floating reduction algorithm/association; operand order is identical. Sequential recomputation matches exactly.
3. No scientific or predictor definition changed. phase2cr_loads.py, M3, M5, CAP_PER_UM=0.103981, scan semantics, archived orders and activity remain hash-identical. Only the witness reduction was repaired; new scripts record continuation evidence.
4. Current focused tests: 14 passed, 0 failed, 0 skipped, 6.165 s command runtime. The test file was not edited during continuation.
5. PACT_PHASE2CR_REPRESENTATIVE_WITNESS_PASS for s5378 / physical seed 11 / P; required architecture SHA verified.
6. output38 moved exactly from U_n1588gat to U_n2121gat; unrelated functional sinks are preserved.
7. Exactly one BUF_X1/A input of 0.974659 fF transferred; transparent output branch and test_so geometry each occur once.
8. M5 was recomputed from actual point sets, with exact sequential reproduction. All affected net points and per-FF pin/M3/M5 values are emitted.
9. All 21 topology cases pass: s5378 9, s9234 6, s15850 6. Each row has explicit ownership, count, chain, identity and point witnesses. Same-owner synthetic fixture also has exactly one input, branch and SO point.
10. No unexplained FF-weight changes. Every changed M3/M5 FF lies in the old-owner/selected-tail cone; weight_change_audit.json records every affected FF and its points.
11. M3 total/local changes for every architecture are in the score table and metric_deltas.json.
12. M5 total/local changes for every architecture are in the score table and metric_deltas.json.
13. Across the 12 design/endpoint predictor vectors, 7 architecture-rank entries changed; see the comparison table.
14. Pair directions flipped: 4 across those 12 vectors; changes including transitions to/from ties: 4.
15. Corrected M3 capacitance total/local correlations are in the endpoint table below.
16. Corrected M5 wire total/local correlations are in the endpoint table below.
17. Original complete design/family qualification outcomes changed: 0. Undefined values fail; rho >= 0.7 and direction accuracy >= 75% on both endpoints remain mandatory.
18. Complete regression: 217 passed, 0 failed, 0 skipped, 143.103 s command runtime. Fresh Linux temporary directory; no old tests modified. Initial continuation regression had 3 collection errors because threadpoolctl was absent from PYTHONPATH; its log/XML/result are preserved. The isolated rerun restored the historical phase2a_python dependency cache. The earlier Phase-2C filesystem failure also remains in reports/phase2c/tests.json.
19. MULTISEED_REPAIR_RERUN_JUSTIFIED. All engineering gates pass; retained complete design/family qualification cells justify testing generalization.
20. Exact final classification: PACT_PHASE2CR_SEED11_REQUALIFIED. Seed-11 only; this is not multi-seed generalization.

## Numerical, ranking and qualification effects are distinct

A. Numerical scores changed beyond representation roundoff: maximum absolute relative changes are M3 total 0.250456%, M3 local 1.110834%, M5 total 0.553567%, and M5 local 3.977054%. These semantic-repair score changes are distinct from the 1.42e-14 witness-arithmetic discrepancy. No quantitative materiality threshold was preregistered.

B. Ranking changed: 7 architecture-rank entries across the 12 design/endpoint vectors, 4 pair flips, and maximum rank displacement 2. These are predictor-vector entries, not a count of distinct architectures.

C. Scientific qualification changed in 0 of six design/family cells. The original per-design, two-endpoint gates are applied independently; no aggregation rescues a failure.

| Design | Predictor | Legacy rho | Corrected rho | Delta rho | Legacy pair accuracy | Corrected pair accuracy | old/new Spearman | old/new rank tau-b | Changed ranks | Max displacement | Pair flips | Max abs score delta | Max abs relative delta |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| s5378 | M3_load | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0 | 0 | 0 | 15105.3985 | 0.00115144277 |
| s5378 | M3_load_local | 0.983333 | 1.000000 | 0.016667 | 0.972222 | 1.000000 | 0.983333 | 0.944444 | 2 | 1 | 1 | 3.98802838 | 0.0111083421 |
| s5378 | M5_hpwl | 0.966667 | 0.966667 | 0.000000 | 0.944444 | 0.944444 | 1.000000 | 1.000000 | 0 | 0 | 0 | 144024.09 | 0.00428374216 |
| s5378 | M5_hpwl_local | 0.983333 | 0.933333 | -0.050000 | 0.972222 | 0.916667 | 0.950000 | 0.888889 | 3 | 2 | 2 | 28.98 | 0.039770544 |
| s9234 | M3_load | 0.942857 | 0.942857 | 0.000000 | 0.933333 | 0.933333 | 1.000000 | 1.000000 | 0 | 0 | 0 | 26140.0475 | 0.00109297342 |
| s9234 | M3_load_local | 0.885714 | 0.885714 | 0.000000 | 0.866667 | 0.866667 | 1.000000 | 1.000000 | 0 | 0 | 0 | 1.1202324 | 0.00268367656 |
| s9234 | M5_hpwl | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0 | 0 | 0 | 251289.43 | 0.00299361149 |
| s9234 | M5_hpwl_local | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0 | 0 | 0 | 1.4 | 0.000987138989 |
| s15850 | M3_load | 0.942857 | 0.942857 | 0.000000 | 0.933333 | 0.933333 | 1.000000 | 1.000000 | 0 | 0 | 0 | 228106.039 | 0.00250456077 |
| s15850 | M3_load_local | 0.942857 | 0.942857 | 0.000000 | 0.933333 | 0.933333 | 1.000000 | 1.000000 | 0 | 0 | 0 | 0 | 0 |
| s15850 | M5_hpwl | 0.942857 | 1.000000 | 0.057143 | 0.933333 | 1.000000 | 0.942857 | 0.866667 | 2 | 1 | 1 | 2194196.75 | 0.00553566548 |
| s15850 | M5_hpwl_local | 0.942857 | 0.942857 | 0.000000 | 0.933333 | 0.933333 | 1.000000 | 1.000000 | 0 | 0 | 0 | 0 | 0 |

## Per-architecture scores

Each cell is legacy → corrected (signed delta; relative delta). Units: M3 fF-transitions; M5 um-transitions. Local scores retain frozen cycle/window peak definitions. Absolute deltas and changed FF identities are in metric_deltas.json.

| Design / architecture | M3 total | M3 local | M5 total | M5 local | Changed FF count | Moved pin fF | Old owner → new owner |
|---|---:|---:|---:|---:|---:|---:|---|
| s5378 / P | 12997301.42 → 12995366.71 (-1934.7041; -0.014885%) | 374.8050305 → 374.8050305 (+0; +0.000000%) | 33612297.91 → 33594000.91 (-18297; -0.054435%) | 699.13 → 699.13 (+0; +0.000000%) | 2 | 0.974659 | U_n1588gat → U_n2121gat |
| s5378 / A | 9928293.544 → 9935319.36 (+7025.8166; +0.070766%) | 379.7632102 → 383.7512386 (+3.9880284; +1.050136%) | 36460616.57 → 36533199.63 (+72583.06; +0.199072%) | 1007.78 → 1036.76 (+28.98; +2.875628%) | 2 | 0.974659 | U_n1588gat → U_n2407gat |
| s5378 / J50 | 9913038.408 → 9922004.978 (+8966.5707; +0.090452%) | 359.0120226 → 363.000051 (+3.9880284; +1.110834%) | 27933818.49 → 28020079.39 (+86260.9; +0.308805%) | 728.68 → 757.66 (+28.98; +3.977054%) | 2 | 0.974659 | U_n1588gat → U_n2490gat |
| s5378 / T | 12977184.21 → 12991319.43 (+14135.22; +0.108924%) | 381.0153798 → 381.0153798 (+0; +0.000000%) | 33868711.95 → 34004961.69 (+136249.74; +0.402288%) | 744.43 → 744.43 (+0; +0.000000%) | 2 | 0.974659 | U_n1588gat → U_n463gat |
| s9234 / P | 24122023.44 → 24120796.75 (-1226.6879; -0.005085%) | 449.5523773 → 448.4321449 (-1.1202324; -0.249188%) | 84972733.56 → 84961348.76 (-11384.8; -0.013398%) | 1513.46 → 1512.06 (-1.4; -0.092503%) | 2 | 0.974659 | U_g59 → U_g139 |
| s9234 / A | 21275688.25 → 21276485.02 (+796.76872; +0.003745%) | 428.0459768 → 428.0459768 (+0; +0.000000%) | 97278870.3 → 97286757.9 (+7887.6; +0.008108%) | 1676.85 → 1676.85 (+0; +0.000000%) | 2 | 0.974659 | U_g59 → U_g170 |
| s9234 / J50 | 20367891.57 → 20366941.46 (-950.11323; -0.004665%) | 417.6350619 → 416.5148295 (-1.1202324; -0.268232%) | 75067591.47 → 75058463.47 (-9128; -0.012160%) | 1492.74 → 1491.34 (-1.4; -0.093787%) | 2 | 0.974659 | U_g59 → U_g148 |
| s9234 / T | 23916453.13 → 23942593.18 (+26140.047; +0.109297%) | 444.9571024 → 443.83687 (-1.1202324; -0.251762%) | 83941897.87 → 84193187.3 (+251289.43; +0.299361%) | 1500.24 → 1498.84 (-1.4; -0.093318%) | 2 | 0.974659 | U_g59 → U_g699 |
| s15850 / P | 91703792.52 → 91931898.56 (+228106.04; +0.248742%) | 424.5235766 → 424.5235766 (+0; +0.000000%) | 396374520.3 → 398568717.1 (+2194196.8; +0.553567%) | 2124.395 → 2124.395 (+0; +0.000000%) | 2 | 0.974659 | U_g73 → U_g1289 |
| s15850 / A | 84168673.73 → 84187730.95 (+19057.219; +0.022642%) | 525.3811148 → 525.3811148 (+0; +0.000000%) | 513851193.9 → 514034882.3 (+183688.4; +0.035747%) | 3355.065 → 3355.065 (+0; +0.000000%) | 2 | 0.974659 | U_g73 → U_g1166 |
| s15850 / J50 | 70286904.13 → 70461686.14 (+174782.01; +0.248669%) | 385.9425732 → 385.9425732 (+0; +0.000000%) | 326655699.1 → 328333734.2 (+1678035.1; +0.513701%) | 2110.04 → 2110.04 (+0; +0.000000%) | 2 | 0.974659 | U_g73 → U_g312 |
| s15850 / T | 91882068.99 → 91995775.34 (+113706.34; +0.123752%) | 410.3232289 → 410.3232289 (+0; +0.000000%) | 397407447.9 → 398499281.3 (+1091833.4; +0.274739%) | 2117.005 → 2117.005 (+0; +0.000000%) | 2 | 0.974659 | U_g73 → U_g1453 |
| s5378 / 44b1a2ab5a1e | 13118670.68 → 13133776.08 (+15105.399; +0.115144%) | 378.3017046 → 378.3017046 (+0; +0.000000%) | 33621092.19 → 33765116.28 (+144024.09; +0.428374%) | 712.02 → 712.02 (+0; +0.000000%) | 2 | 0.974659 | U_n1588gat → U_n1740gat |
| s5378 / 0348f2cc6b9d | 11144371.16 → 11156502.28 (+12131.115; +0.108854%) | 373.0105735 → 373.0105735 (+0; +0.000000%) | 28603053.38 → 28721763.44 (+118710.06; +0.415026%) | 733.08 → 733.08 (+0; +0.000000%) | 2 | 0.974659 | U_n1588gat → U_n2091gat |
| s5378 / a78c6ce1a5a1 | 11461940.79 → 11475016.14 (+13075.346; +0.114076%) | 367.3470201 → 367.3470201 (+0; +0.000000%) | 29327640.77 → 29452807.07 (+125166.3; +0.426786%) | 724.1 → 724.1 (+0; +0.000000%) | 2 | 0.974659 | U_n1588gat → U_n2091gat |
| s5378 / 75ea663523d9 | 11209204.53 → 11221733.47 (+12528.932; +0.111774%) | 364.9039403 → 364.9039403 (+0; +0.000000%) | 28746699.29 → 28867754.21 (+121054.92; +0.421109%) | 709.93 → 709.93 (+0; +0.000000%) | 2 | 0.974659 | U_n1588gat → U_n2091gat |
| s5378 / 1f1a3a458946 | 10281669.37 → 10289675.88 (+8006.5068; +0.077872%) | 368.1620384 → 368.1620384 (+0; +0.000000%) | 27887858.05 → 27965841.97 (+77983.92; +0.279634%) | 718.24 → 718.24 (+0; +0.000000%) | 2 | 0.974659 | U_n1588gat → U_n1336gat |
| s15850 / balanced | 71424989.23 → 71603877.46 (+178888.23; +0.250456%) | 403.6980995 → 403.6980995 (+0; +0.000000%) | 331489179.9 → 333205430.2 (+1716250.3; +0.517739%) | 2172.21 → 2172.21 (+0; +0.000000%) | 2 | 0.974659 | U_g73 → U_g312 |
| s15850 / activity_extreme | 85990716.71 → 86010321.95 (+19605.246; +0.022799%) | 525.2952158 → 525.2952158 (+0; +0.000000%) | 523527441 → 523716418.6 (+188977.6; +0.036097%) | 3387.125 → 3387.125 (+0; +0.000000%) | 2 | 0.974659 | U_g73 → U_g1166 |
| s9234 / balanced | 23906818.26 → 23932882.34 (+26064.084; +0.109024%) | 452.6499575 → 451.5297251 (-1.1202324; -0.247483%) | 84041618.87 → 84292327.72 (+250708.85; +0.298315%) | 1529.08 → 1527.68 (-1.4; -0.091558%) | 2 | 0.974659 | U_g59 → U_g699 |
| s9234 / activity_extreme | 20502573.92 → 20501623.8 (-950.11323; -0.004634%) | 417.4245199 → 416.3042875 (-1.1202324; -0.268368%) | 75572973.1 → 75563845.1 (-9128; -0.012078%) | 1418.24 → 1416.84 (-1.4; -0.098714%) | 2 | 0.974659 | U_g59 → U_g148 |

## Original qualification cells

| Design | Family | Legacy | Corrected |
|---|---|---|---|
| s5378 | M3_load | PASS | PASS |
| s5378 | M5_hpwl | PASS | PASS |
| s9234 | M3_load | PASS | PASS |
| s9234 | M5_hpwl | PASS | PASS |
| s15850 | M3_load | PASS | PASS |
| s15850 | M5_hpwl | PASS | PASS |

## Provenance and boundary

All 534 frozen input hashes and the preregistered contract were verified before/after continuation. Existing activity, targets, OpenRCX/SPEF, route evidence and historical weights were reused without modification. Targets are labels only, never predictor inputs. commands.json and tests.json include runtime/environment/logs. result_provenance.json hashes the final outputs, attempt-1 snapshot and continuation sources. No ATPG, routing, placement, new physical implementation, optimizer/search, ML, event-engine integration, extra seeds, Phase-2D or GitHub push was performed. Phase-2C remains STOPPED_LEGACY_DEFINITION_BUG.
