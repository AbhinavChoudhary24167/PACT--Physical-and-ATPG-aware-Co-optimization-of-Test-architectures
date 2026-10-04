# PACT Stage-B constrained method-convergence report

## 1. Status

PACT_STAGE_B_MULTI_DESIGN_CONVERGENCE

Convergence requires a new measured wire/E/H4/H8 frontier point with E, H4 and H8 improvements against the routed-best B2/B3T reference under the actual routed wire budget. A candidate dominated by the known Stage-A results does not count as an advance. Scalar search scores do not establish superiority.

## 2. What changed

Added a separate constrained search using the existing candidate-stateful evaluator. Physical cost is a hard feasibility condition. Geometry screens infeasible proposals before waveform updates. Four activity lanes retain E, H4, H8 and balanced winners separately. Fixed-capacity mutation operators, bounded archive and independent final replay are reused. The exact B3T chain-capacity permutation is preserved. No external repair or frozen-method change was made.

## 3. Optimization formulation

`W_proxy(a) <= (1 + epsilon) W_proxy(reference)`, with epsilon in {0.02, 0.05, 0.10}. Reference selection minimizes frozen routed scan-path cost among B2 and B3T. W_proxy is port-inclusive Manhattan scan HPWL.

Within feasibility, three lanes minimize E, H4 and H8. The balanced lane minimizes `sum(w_i metric_i/reference_i)/sum(w_i)` for E,H4,H8 with common weights (1,1,1). Raw quantities remain separate. Source positions, three logic levels, ground-plus-pin capacitance, fixed buffer skeleton and FAN workload follow the existing model.

Search feasibility does not imply routed feasibility. Routed scan wire is the frozen full connected scan-net length upper bound including shared functional branches; detailed-route total wire is a different quantity. Routed budget acceptance is independently recorded.

## 4. Search configuration

Starts: exact frozen B2, B3T and balanced P0; infeasible starts cannot seed search. Seed 11, K=2, 16 neighbors, segment limit 8, 16 archive slots, lane restart every 150 attempts. Each budget has a 300-second mutation-loop ceiling, 20,000 exact-evaluation ceiling and 2,000-attempt no-improvement window. Initialization and retained-candidate replay are additional recorded solver time; model loading precedes these timings. Weights and operators are shared across designs. Searches use one numerical thread each, at most two processes concurrently. A pre-route selection deduplicates across budgets and allows at most three new architectures per design.

| design | epsilon | reference | search_s | solver_s | evaluations | screened | accepted | termination |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| s5378 | 0.02 | B2 | 273.899 | 281.685 | 1238 | 13945 | 213 | stagnation |
| s5378 | 0.05 | B2 | 152.954 | 159.211 | 510 | 4672 | 76 | stagnation |
| s5378 | 0.1 | B2 | 300.146 | 306.268 | 1090 | 3419 | 127 | wall_clock |
| s9234 | 0.02 | B3T | 300.171 | 310.001 | 528 | 3526 | 77 | wall_clock |
| s9234 | 0.05 | B3T | 300.609 | 310.979 | 568 | 2875 | 79 | wall_clock |
| s9234 | 0.1 | B3T | 300.029 | 310.487 | 521 | 1558 | 63 | wall_clock |
| s15850 | 0.02 | B2 | 302.284 | 347.725 | 118 | 676 | 28 | wall_clock |
| s15850 | 0.05 | B2 | 301.272 | 340.555 | 148 | 390 | 30 | wall_clock |
| s15850 | 0.1 | B2 | 302.241 | 339.882 | 148 | 382 | 38 | wall_clock |

## 5. Candidate results before routing

| design | epsilon | candidate | roles | new | proxy_wire_um | proxy_E | proxy_H4 | proxy_H8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| s5378 | 0.02 | s5378_budget_0.02_winner_1 | best_E | True | 1347.21 | 15788791.9592 | 362.5999 | 156.1292 |
| s5378 | 0.02 | s5378_budget_0.02_winner_2 | best_H4 | True | 1348.77 | 16173463.2159 | 352.1049 | 162.5778 |
| s5378 | 0.02 | s5378_budget_0.02_winner_3 | best_H8 | True | 1344.17 | 15830312.0886 | 358.5259 | 152.8439 |
| s5378 | 0.02 | s5378_C1 | balanced | True | 1349.39 | 15824700.276 | 357.5082 | 152.8439 |
| s5378 | 0.05 | s5378_budget_0.05_winner_1 | best_E | True | 1384.85 | 15235274.2282 | 367.5506 | 163.8427 |
| s5378 | 0.05 | s5378_budget_0.05_winner_2 | best_H4 | True | 1387.69 | 16215711.3924 | 343.8822 | 172.3095 |
| s5378 | 0.05 | s5378_budget_0.05_winner_3 | best_H8 | True | 1386.99 | 15284604.8358 | 367.5506 | 159.559 |
| s5378 | 0.05 | s5378_budget_0.05_winner_4 | balanced | True | 1389.03 | 15272834.4722 | 363.8802 | 159.559 |
| s5378 | 0.1 | s5378_C2 | best_E | True | 1454.15 | 15173926.0207 | 365.4592 | 162.9972 |
| s5378 | 0.1 | s5378_C3 | best_H4 | True | 1444.69 | 16186140.5267 | 341.5029 | 171.8238 |
| s5378 | 0.1 | s5378_budget_0.10_winner_3 | best_H8 | True | 1450.91 | 15470234.9767 | 402.1082 | 157.5559 |
| s5378 | 0.1 | s5378_budget_0.10_winner_4 | balanced | True | 1454.15 | 15197740.7885 | 351.0361 | 162.9972 |
| s9234 | 0.02 | s9234_budget_0.02_winner_1 | best_E | True | 1766.425 | 28817473.4002 | 429.0091 | 188.5769 |
| s9234 | 0.02 | s9234_budget_0.02_winner_2 | best_H4;balanced | True | 1765.905 | 29074124.6419 | 398.0462 | 187.9791 |
| s9234 | 0.02 | s9234_budget_0.02_winner_3 | best_H8 | True | 1766.905 | 28953514.5663 | 409.1035 | 184.9699 |
| s9234 | 0.05 | s9234_budget_0.05_winner_1 | best_E | True | 1819.025 | 28594551.3857 | 406.3185 | 184.835 |
| s9234 | 0.05 | s9234_budget_0.05_winner_2 | best_H4 | True | 1817.605 | 29148646.4837 | 402.6493 | 194.4939 |
| s9234 | 0.05 | s9234_budget_0.05_winner_3 | best_H8 | True | 1818.225 | 28909609.6262 | 424.3314 | 184.835 |
| s9234 | 0.05 | s9234_budget_0.05_winner_4 | balanced | True | 1816.985 | 28636734.8725 | 405.3862 | 184.835 |
| s9234 | 0.1 | s9234_C2 | best_E | True | 1876.005 | 28054141.152 | 440.9794 | 175.2737 |
| s9234 | 0.1 | s9234_C3 | best_H4 | True | 1896.505 | 28473788.0629 | 394.488 | 174.5389 |
| s9234 | 0.1 | s9234_budget_0.10_winner_3 | best_H8 | True | 1878.605 | 28196532.1129 | 430.7026 | 167.9298 |
| s9234 | 0.1 | s9234_C1 | balanced | True | 1894.785 | 28339147.9736 | 398.4935 | 168.8731 |
| s15850 | 0.02 | s15850_budget_0.02_winner_1 | best_E | True | 3812.81 | 110582628.3136 | 564.6633 | 223.5047 |
| s15850 | 0.02 | s15850_budget_0.02_winner_2 | best_H4 | True | 3812.63 | 111204057.7259 | 539.0744 | 222.3948 |
| s15850 | 0.02 | s15850_budget_0.02_winner_3 | best_H8 | True | 3808.43 | 113148514.0819 | 548.2058 | 217.6233 |
| s15850 | 0.02 | s15850_budget_0.02_winner_4 | balanced | True | 3812.01 | 111131736.3215 | 539.0744 | 222.3948 |
| s15850 | 0.05 | s15850_budget_0.05_winner_1 | best_E | True | 3925.01 | 110697878.1207 | 583.1542 | 225.2592 |
| s15850 | 0.05 | s15850_budget_0.05_winner_2 | best_H4 | True | 3875.53 | 113139853.7245 | 529.6138 | 216.2352 |
| s15850 | 0.05 | s15850_budget_0.05_winner_3 | best_H8 | True | 3921.77 | 113043066.7558 | 548.1207 | 209.1248 |
| s15850 | 0.05 | s15850_budget_0.05_winner_4 | balanced | True | 3924.85 | 113093607.1612 | 529.6138 | 216.2352 |
| s15850 | 0.1 | s15850_C2 | best_E | True | 4109.09 | 110267166.6195 | 572.9125 | 225.6858 |
| s15850 | 0.1 | s15850_C3 | best_H4 | True | 4108.89 | 111002066.2269 | 519.0409 | 221.2386 |
| s15850 | 0.1 | s15850_budget_0.10_winner_3 | best_H8 | True | 4110.49 | 113403801.7569 | 545.0111 | 209.1248 |
| s15850 | 0.1 | s15850_C1 | balanced | True | 4111.17 | 110915632.9865 | 519.0409 | 221.2386 |

## 6. Routed/extracted Stage-B results

Unchanged Nangate45/ORFS flow, placement, backend, routing seed 11 and two route cores. E uses all-data extracted ground plus pin capacitance and the frozen simulation schedule. Timing fields are global-route values; TNS and structural/functional/FF results are in routed_results.csv.

| design | candidate | epsilon | status | scan_wire_um | E | H4 | H8 | DRC | setup_WNS_ns | hold_WNS_ns | routed_budget_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| s5378 | s5378_C1 | 0.02 | QUALIFIED | 4899.28 | 18913553.093274705 | 404.20548257 | 166.60605607 | 0 | 9.08575 | 0.00273321 | True |
| s5378 | s5378_C2 | 0.1 | QUALIFIED | 5159.585 | 18218623.502973676 | 409.56072158999996 | 174.38007253 | 0 | 9.08663 | 0.0027288 | True |
| s5378 | s5378_C3 | 0.1 | QUALIFIED | 5074.96 | 19218672.61615374 | 383.08508187 | 183.61354787 | 0 | 9.08726 | 0.00272932 | True |
| s9234 | s9234_C1 | 0.1 | QUALIFIED | 10696.095 | 38556259.5670017 | 463.14321620000004 | 191.87925199 | 0 | 8.75119 | 0.00072084 | True |
| s9234 | s9234_C2 | 0.1 | QUALIFIED | 10643.935 | 38153295.4760098 | 507.83278949 | 192.35797083 | 0 | 8.74961 | 0.000690004 | True |
| s9234 | s9234_C3 | 0.1 | QUALIFIED | 10653.995 | 38762209.81992033 | 485.46609390000003 | 190.51087882000004 | 0 | 8.74898 | 0.000760211 | True |
| s15850 | s15850_C1 | 0.1 | QUALIFIED | 24208.69 | 158127855.19631428 | 699.96964788 | 276.18001142 | 0 | 8.13166 | 0.000913047 | True |
| s15850 | s15850_C2 | 0.1 | QUALIFIED | 24210.015 | 157217009.2264669 | 653.2513381499999 | 278.59896137 | 0 | 8.1318 | 0.00123894 | True |
| s15850 | s15850_C3 | 0.1 | QUALIFIED | 24191.395 | 158202517.69272432 | 700.5529383 | 278.08832312 | 0 | 8.13186 | 0.000858286 | True |

## 7. Comparison against B2/B3T/P0

Percentages use full precision measured values: 100*(candidate/reference-1). P0 denotes the original frozen balanced representative. Negative deltas improve the corresponding metric.

| design | candidate | versus | wire_percent | E_percent | H4_percent | H8_percent | dominance_Stage_A | dominance_with_H4 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| s5378 | s5378_C1 | P0 | -4.701809 | 2.648254 | -4.954353 | -6.142995 | nondominated | nondominated |
| s5378 | s5378_C1 | B2 | 0.336895 | -3.12339 | -9.417893 | -11.028496 | nondominated | nondominated |
| s5378 | s5378_C1 | B3T | -2.894949 | -1.796968 | 2.193581 | -9.418909 | dominating | nondominated |
| s5378 | s5378_C2 | P0 | 0.361506 | -1.123291 | -3.695112 | -1.763527 | nondominated | nondominated |
| s5378 | s5378_C2 | B2 | 5.667922 | -6.68287 | -8.217789 | -6.876991 | nondominated | nondominated |
| s5378 | s5378_C2 | B3T | 2.264367 | -5.405184 | 3.547524 | -5.192299 | nondominated | nondominated |
| s5378 | s5378_C3 | P0 | -1.284575 | 4.304208 | -9.920644 | 3.438123 | nondominated | nondominated |
| s5378 | s5378_C3 | B2 | 3.934808 | -1.560545 | -14.150957 | -1.946101 | nondominated | nondominated |
| s5378 | s5378_C3 | B3T | 0.587076 | -0.212725 | -3.146202 | -0.172203 | nondominated | nondominated |
| s9234 | s9234_C1 | P0 | 0.624902 | 0.76582 | -6.995272 | 0.365015 | dominated | nondominated |
| s9234 | s9234_C1 | B2 | 1.652359 | -1.382414 | -12.634679 | -3.987163 | nondominated | nondominated |
| s9234 | s9234_C1 | B3T | 1.816421 | -3.165613 | -13.77545 | -1.891009 | nondominated | nondominated |
| s9234 | s9234_C2 | P0 | 0.1342 | -0.287316 | 1.978931 | 0.615416 | nondominated | nondominated |
| s9234 | s9234_C2 | B2 | 1.156646 | -2.413098 | -4.204632 | -3.747621 | nondominated | nondominated |
| s9234 | s9234_C2 | B3T | 1.319908 | -4.17766 | -5.455479 | -1.646237 | nondominated | nondominated |
| s9234 | s9234_C3 | P0 | 0.228841 | 1.304066 | -2.51257 | -0.35073 | nondominated | nondominated |
| s9234 | s9234_C3 | B2 | 1.252254 | -0.855643 | -8.423788 | -4.671872 | nondominated | nondominated |
| s9234 | s9234_C3 | B3T | 1.41567 | -2.648367 | -9.619544 | -2.590666 | nondominated | nondominated |
| s15850 | s15850_C1 | P0 | 0.351956 | -2.27061 | 0.423286 | -0.54082 | nondominated | nondominated |
| s15850 | s15850_C1 | B2 | 1.044538 | -0.078257 | 2.900104 | -1.213872 | nondominated | nondominated |
| s15850 | s15850_C1 | B3T | 0.786959 | -2.233334 | 3.218477 | -0.948383 | nondominated | nondominated |
| s15850 | s15850_C2 | P0 | 0.357448 | -2.833549 | -6.279299 | 0.330303 | nondominated | nondominated |
| s15850 | s15850_C2 | B2 | 1.050069 | -0.653825 | -3.967793 | -0.348644 | nondominated | nondominated |
| s15850 | s15850_C2 | B3T | 0.792476 | -2.796488 | -3.670668 | -0.08083 | nondominated | nondominated |
| s15850 | s15850_C3 | P0 | 0.280263 | -2.224465 | 0.50697 | 0.146409 | nondominated | nondominated |
| s15850 | s15850_C3 | B2 | 0.972351 | -0.031077 | 2.985851 | -0.531293 | nondominated | nondominated |
| s15850 | s15850_C3 | B3T | 0.714956 | -2.187172 | 3.30449 | -0.263969 | nondominated | nondominated |

## 8. Pareto interpretation

Both exact frozen Stage-A dominance (wire,E,H8) and the expanded set (wire,E,H4,H8) are shown in comparison.csv and routed_results.csv. Front membership compares every qualified measured Stage-A point, including nonrepresentative P0 points. Unmeasured points remain unknown.

The combined frontier additionally includes every qualified Stage-B selection.

| candidate | Stage_A_front_3_objectives | Stage_A_front_4_objectives | combined_front_3_objectives | combined_front_4_objectives |
| --- | --- | --- | --- | --- |
| s5378_C1 | nondominated | nondominated | nondominated | nondominated |
| s5378_C2 | nondominated | nondominated | nondominated | nondominated |
| s5378_C3 | nondominated | nondominated | dominated | nondominated |
| s9234_C1 | dominated | nondominated | dominated | nondominated |
| s9234_C2 | dominated | nondominated | dominated | nondominated |
| s9234_C3 | dominated | nondominated | dominated | nondominated |
| s15850_C1 | nondominated | nondominated | nondominated | nondominated |
| s15850_C2 | nondominated | nondominated | nondominated | nondominated |
| s15850_C3 | nondominated | nondominated | nondominated | nondominated |

## 9. Generalization across the three designs

Simultaneous bounded improvements: s15850, s5378, s9234. Designs with only partial E/hotspot improvements: none. All three designs remain included.

The success is over retained endpoints, with one fixed method/configuration across designs. s15850 C2, the E winner, improves all three measured activity metrics; its balanced C1 and H4 C3 winners regress measured H4. Thus a balanced scalar alone does not consistently select the successful endpoint. The s15850 gains are modest, and this single seed/workload/physical context does not establish statistical or technology-wide generalization.

## 10. Failures and limitations

The physical estimate constrains scan edges but measured scan cost contains shared fanout, buffers and routed detours. The stateful activity predictor has bounded logic coverage and a fixed baseline buffer skeleton. Hotspot ties and routing-induced load/location changes can prevent proxy improvements from transferring. Search is local and finite; a negative result does not prove infeasibility. s15850 is retained as the difficult case, with its measured deltas and runtime shown above. No watts, IR-drop or signoff-power claim follows from these switching proxies.

The following focused comparison shows whether the selected predicted improvements transferred to the unchanged routed flow; every delta uses its corresponding physical reference.

| design | candidate | proxy_E_percent | measured_E_percent | proxy_H4_percent | measured_H4_percent | proxy_H8_percent | measured_H8_percent | routed_budget_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| s5378 | s5378_C1 | -3.789744 | -3.12339 | -14.448458 | -9.417893 | -11.513789 | -11.028496 | True |
| s5378 | s5378_C2 | -7.74629 | -6.68287 | -12.5458 | -8.217789 | -5.63572 | -6.876991 | True |
| s5378 | s5378_C3 | -1.592277 | -1.560545 | -18.27852 | -14.150957 | -0.525715 | -1.946101 | True |
| s9234 | s9234_C1 | -2.751114 | -3.165613 | -12.717079 | -13.77545 | -10.496499 | -1.891009 | True |
| s9234 | s9234_C2 | -3.729146 | -4.17766 | -3.411288 | -5.455479 | -7.104153 | -1.646237 | True |
| s9234 | s9234_C3 | -2.289082 | -2.648367 | -13.594419 | -9.619544 | -7.493589 | -2.590666 | True |
| s15850 | s15850_C1 | -0.128123 | -0.078257 | -7.448305 | 2.900104 | -1.043881 | -1.213872 | True |
| s15850 | s15850_C2 | -0.712022 | -0.653825 | 2.157695 | -3.967793 | 0.945281 | -0.348644 | True |
| s15850 | s15850_C3 | -0.050295 | -0.031077 | -7.448305 | 2.985851 | -1.043881 | -0.531293 | True |

A focused s15850 diagnostic reuses saved per-net/per-cycle counts; it adds no search, route or simulation. B2 and the first two selected candidates have exact waveform agreement on all 2,616 source-identical represented nets. At C1's measured H4 peak, the represented contribution is 497.674 fF·transitions and the omitted contribution is 202.295. At B2's full-circuit peak they are 476.436 and 203.806. The routed-minus-model capacitance correction at C1's peak is -2.594, with zero waveform discrepancy. Thus the full peak regresses even as the maximum over the represented subset improves; incomplete spatial coverage changes which bin/cycle is decisive.

A separate diagnostic adds B2's frozen omitted-net bin/cycle background to the unchanged predictor on these saved pairs. For C1, H4 changes from the original prediction of -7.448% to +5.071%, versus measured +2.900%. For C2 it changes from +2.158% to -2.975%, versus measured -3.968%. This recovers both H4 directions without tuning per candidate, but overshoots and does not recover the H8 directions. It is a hypothesis test, not the executed Stage-B method or a qualified replacement. Detailed decompositions and contributors are in s15850_hotspot_diagnostic.csv and s15850_background_probe.csv.

## 11. External/tool bugs encountered

No new external repair was required by this Stage-B implementation. The following previously qualified repairs remain frozen Stage-A dependencies; their public pull requests were open and unmerged when checked for this report.

| Inherited blocker | Repair branch and upstream status | Scientific semantics |
| --- | --- | --- |
| Non-static scan-pin library accessor called without an object receiver | `fix/dft-dbnetwork-member-receiver`: [OpenROAD receiver PR](https://github.com/mwsoli/OpenROAD/pull/1), open | Compile-only qualification of the existing receiver; no objective/operator change. |
| Fixed SO endpoint disconnected after restitching; stale scan-list order | `fix/dft-scan-output-topology`: [OpenROAD topology PR](https://github.com/mwsoli/OpenROAD/pull/2), open | Reconstructs the chosen ordering and preserves functional fanout; clustering, search cost and capacity rules remain unchanged. |
| Renamed input port alias omitted from exported Verilog | `fix/verilog-input-alias`: [OpenSTA alias PR](https://github.com/The-OpenROAD-Project/OpenSTA/pull/420), open | Corrects serialization direction/connectivity; no scan optimization change. |

The qualified backend and its experimental submodule binding were reused without rebuild or retuning. Scientific reproduction receipts and source/configuration hashes stay in private experiment storage; public artifacts contain neutral architecture labels and relative links. Public upstream descriptions, commit messages and patches were checked for local provenance values.

## 12. Next action

Test an omitted-logic/background correction against all saved s15850 pairs, requiring both H4 and H8 ranking to improve before new physical runs. The fixed-background probe identifies the H4 coverage problem but is insufficient for H8; extend only the relevant omitted logic or candidate-sensitive background indicated by these pairs. Preserve this campaign as the measured comparator.
