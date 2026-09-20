# PACT Phase-0C final report

**Script-generated decision:** `PACT_PHASE0C_LEARNING_GATE_FAIL`

**Frozen analysis commit:** `3e7b516a6a3b68950aad624b3474bf0c45b78b97`

**Report-generation evidence commit:** `8ce4985089115afd55b662f376b3136bc528e2b9`
**Scientific answer:** **No. The frozen evidence does not satisfy every prerequisite for investigating a learned intervention model.**

No ML model was trained or evaluated. A PASS means only that a later investigation of learned intervention guidance is scientifically justified under this qualified benchmark regime.

## Provenance and benchmark population

The starting commit was `06fe31583b9822368cebe5b98c0e16766969af7f`. Phase-0B remains byte-for-byte preserved across 4,127 hashed files and retains `PACT_PHASE0B_CONFLICT_NOT_REPLICATED_PHASE1_NO_GO`. The Phase-0C contract, campaign, objectives, methods, hashes, toolchain and benchmark audit were frozen before final execution. The campaign used OpenROAD `26Q2-1164-g08f67ee5ec`, ORFS `5e8b1450d19263f797a27c4f371b9dd19f32a3aa`, Yosys `0.33 (git sha1 2584903a060)`, FAN commit `26b2b36c0e9db11a4b6d9e759df6e44357121f39`, and Nangate45 Liberty `8d540a4d4cf6d09d27c87ad067857a9c0c2eeb023ab7a56e058cd3113db4e9b1`.

| Design | Scan FFs | FAN patterns | Frozen stuck-at coverage |
|---|---:|---:|---:|
| s5378 | 179 | 117 | 96.04% |
| s9234 | 211 | 156 | 94.14% |
| s15850 | 534 | 133 | 94.62% |

No additional benchmark was admitted: the saved audit found no reproducible FAN full-scan/PPI-to-FF mapping for the otherwise licensed Ibex and JPEG candidates. The three ISCAS89 designs therefore support conditional conclusions within this benchmark regime.

## Campaign and infrastructure qualification

The frozen matrix contains 3 designs × 5 physical seeds × 4 K values × 6 common families, plus native B1 at K=1: **375 planned physical rows**. The original session stopped at the frozen disk floor after 27 qualified rows; its manifest is immutable. The precommitted recovery ledger contains 348 eligible rows and status `COMPLETED`. Combined ledger rows=375, physically attempted=375, qualified zero-DRC rows=375, status counts={'QUALIFIED': 375}. All 375 architecture rows use frozen input hashes and deterministic run IDs. Routed structural proofs passed=375/375; fixed-port proofs passed=375/375; K-chain SI/SO proofs passed=375/375.

Each architecture preserves the placed FF bijection and reconstructs all frozen ATPG PPI targets through fully clocked parallel loading, including leading padding on short chains. Every final route begins from its design/seed's identical Phase-0B `3_place.odb`. Failed and superseded attempts retain commands, return codes, logs and partial artifacts.

## Physical, activity and scaling results

The primary physical quantity is the **port-aware FF-origin scan HPWL proxy**, measured at fixed placement after including all 2K SI/SO links. It is a proxy, not routed scan wirelength. Full-netlist detailed-route wirelength/vias, detailed-route DRC, global-route setup/hold results, and initial global-route utilization/overflow are tool outputs. The verified mixed-net SI-to-SO total is an upper bound. Exact exclusive scan-only routed length qualified in 0 rows.

| Design | Qualified rows | HPWL proxy median/IQR/range (µm) | H_eff8 median/IQR/range | Full-net DR wirelength (µm) | Full scan-path upper bound (µm) | Route runtime (s) |
|---|---:|---|---|---|---|---|
| s5378 | 125 | 2,365.400 (IQR 5,273.145; range 1,185.205–9,037.420; n=125) | 62.833 (IQR 5.333; range 53.833–70.833; n=125) | 27,335.000 (IQR 4,512.000; range 25,810.000–33,480.000; n=125) | 5,823.555 (IQR 4,485.085; range 4,859.400–11,722.030; n=125) | 86.680 (IQR 10.604; range 75.852–161.265; n=125) |
| s9234 | 125 | 3,895.765 (IQR 7,956.740; range 1,456.805–11,517.715; n=125) | 167.833 (IQR 15.167; range 142.000–199.000; n=125) | 39,753.000 (IQR 5,533.000; range 36,767.000–46,297.000; n=125) | 12,174.570 (IQR 5,717.100; range 10,336.295–18,385.370; n=125) | 107.949 (IQR 7.888; range 93.834–154.826; n=125) |
| s15850 | 125 | 10,310.950 (IQR 33,281.670; range 3,226.860–40,239.330; n=125) | 165.167 (IQR 20.000; range 137.500–181.333; n=125) | 85,032.000 (IQR 27,153.000; range 79,556.000–111,445.000; n=125) | 28,684.740 (IQR 27,550.320; range 23,171.665–54,782.190; n=125) | 163.400 (IQR 16.586; range 134.475–232.528; n=125) |

Logical shift toggles are exact within the no-capture model; H_eff8 is a dimensionless direct-sink-weighted spatial proxy. Shift-mode power and test-mode PDNSim were not qualified, so watts, current and IR drop remain null. Median exact total toggles=1,716,219.000 (IQR 2,814,707.000; range 159,401.000–18,483,084.000; n=375); peak simultaneous toggles=127.000 (IQR 152.000; range 88.000–308.000; n=375). Compressed routed ODB size per row=0.706 (IQR 0.738; range 0.532–1.337; n=375) MiB.

## Effect of K

| K | Qualified rows | Normalized chain imbalance | Exact shift clocks | HPWL proxy (µm) | H_eff8 | Setup WNS (ns) | Initial GRT usage (%) |
|---:|---:|---|---|---|---|---|---|
| 1 | 105 | 0.000 (IQR 0.000; range 0.000–0.000; n=105) | 32,916.000 (IQR 50,079.000; range 20,943.000–71,022.000; n=105) | 3,417.780 (IQR 7,396.315; range 1,185.205–39,105.680; n=105) | 161.667 (IQR 107.000; range 56.833–194.667; n=105) | 8.732 (IQR 0.944; range 8.086–9.108; n=105) | 23.750 (IQR 3.650; range 22.230–32.730; n=105) |
| 2 | 90 | 0.009 (IQR 0.011; range 0.000–0.011; n=90) | 16,536.000 (IQR 24,981.000; range 10,530.000–35,511.000; n=90) | 5,187.690 (IQR 7,764.467; range 1,253.970–39,238.130; n=90) | 160.167 (IQR 106.708; range 57.000–199.000; n=90) | 8.732 (IQR 0.942; range 8.087–9.108; n=90) | 24.200 (IQR 3.690; range 22.330–32.750; n=90) |
| 4 | 90 | 0.019 (IQR 0.015; range 0.007–0.022; n=90) | 8,268.000 (IQR 12,557.000; range 5,265.000–17,822.000; n=90) | 5,716.958 (IQR 7,428.470; range 1,533.880–39,567.870; n=90) | 153.917 (IQR 104.458; range 53.833–195.167; n=90) | 8.732 (IQR 0.940; range 8.087–9.107; n=90) | 24.300 (IQR 3.683; range 22.540–32.860; n=90) |
| 8 | 90 | 0.038 (IQR 0.030; range 0.015–0.045; n=90) | 4,212.000 (IQR 6,220.000; range 2,691.000–8,911.000; n=90) | 6,423.097 (IQR 7,435.730; range 2,078.780–40,239.330; n=90) | 151.333 (IQR 104.208; range 55.333–193.500; n=90) | 8.732 (IQR 0.942; range 8.088–9.109; n=90) | 24.645 (IQR 3.520; range 22.880–33.060; n=90) |

K changes the number and location of fixed SI/SO ports, chain balance, exact parallel test time, physical proxy, activity concentration, routed timing and congestion together. Results are paired within design×physical-seed contexts; architecture variants are not counted as independent design samples.

## Conflict and replication

The frozen C3 test compares the physically best and H_eff8-best qualified methods inside each complete design-seed-K group. A hit requires at least 5% H_eff8 improvement with at least 10% physical penalty.

| Design | Practical hits | Seeds with ≥1 hit | Physical penalty % | H_eff8 gain % |
|---|---:|---:|---|---|
| s5378 | 18/20 design-seed-K groups | 5/5 | 376.222 (IQR 174.562; range 39.811–484.500; n=20) | 9.409 (IQR 5.382; range 4.474–13.867; n=20) |
| s9234 | 20/20 design-seed-K groups | 5/5 | 407.012 (IQR 239.780; range 78.073–595.590; n=20) | 11.885 (IQR 2.855; range 7.407–14.836; n=20) |
| s15850 | 20/20 design-seed-K groups | 5/5 | 892.818 (IQR 186.089; range 642.275–1,069.740; n=20) | 15.338 (IQR 2.106; range 7.064–18.999; n=20) |

The seed replicas are conditional perturb-and-legalize placements around a source placement. Medians and IQRs are descriptive; no population p-values or independence claim is made.

## Deterministic heuristics and intervention landscape

| Method | Median physical regret | Physical IQR | Median activity regret | Activity IQR | Pareto memberships |
|---|---:|---:|---:|---:|---:|
| A | 484.692% | 335.462% | 0.000% | 0.000% | 55 |
| B0 | 284.254% | 293.298% | 15.712% | 4.830% | 2 |
| B1 | 0.000% | 3.088% | 14.972% | 7.328% | 10 |
| J50 | 77.746% | 61.636% | 4.667% | 5.019% | 57 |
| P | 1.479% | 6.158% | 14.660% | 5.250% | 37 |
| R | 579.529% | 309.380% | 14.910% | 5.525% | 0 |
| T | 0.339% | 2.933% | 13.722% | 6.719% | 43 |

C6 tests both each simple method and the frozen deterministic portfolio at 2% two-objective coverage. Its measured maximum single-method coverage is 0.000; portfolio coverage is 1.000 over 60 complete groups.

The C7 screen applies 20 predeclared, deterministic local swaps around every qualified P/K2 parent. Children preserve FF inventory and exact ATPG loading; their physical response is the port-aware HPWL proxy and is not called routed.

| Design | Eligible swaps | Contexts passing both-sign rule | Negative ΔHPWL | Positive ΔHPWL | ΔHPWL median/IQR/range (µm) |
|---|---:|---:|---:|---:|---|
| s5378 | 100 | 0/5 | 1 | 99 | 30.200 (IQR 56.430; range -2.800–241.420; n=100) |
| s9234 | 100 | 0/5 | 2 | 98 | 53.230 (IQR 63.255; range -3.040–182.840; n=100) |
| s15850 | 100 | 0/5 | 0 | 99 | 82.170 (IQR 131.325; range 0.000–343.800; n=100) |

## Frozen learning gates

| Gate | Status | Exact mechanical reason and counts |
|---|---|---|
| C1 | **PASS** | all planned proxy rows, structural checks, provenance and frozen contract required; proxy_rows=375; expected_proxy_rows=375; execution_manifest_intact=True; missing_rows=0; extra_rows=0; duplicate_rows=0; invalid_rows=0; original_campaign_and_recovery_union_intact=True; recovery_ledger={"errors":[],"expected_recovery_rows":348,"original_qualified_rows":27,"planned_union_rows":375,"recorded_recovery_rows":348,"recovery_counts":{"QUALIFIED":348},"recovery_manifest_present":true,"recovery_status":"COMPLETED"} |
| C2 | **PASS** | qualified routes compared with predeclared 375-row matrix; qualified_new_routes=375; planned_routes=375; completion_fraction=1; complete_pairs=60; planned_pairs=60; complete_pair_fraction=1 |
| C3 | **PASS** | both 5% effective-activity improvement and 10% physical penalty required; practical_hits=58; assessed_pairs=60 |
| C4 | **PASS** | at least 4 of 5 physical seeds on one design; replicated_designs=["s5378","s9234","s15850"]; qualifying_seed_counts={"s15850":5,"s5378":5,"s9234":5} |
| C5 | **PASS** | at least two designs satisfy C4; replicated_design_count=3 |
| C6 | **FAIL** | neither one simple heuristic nor their fixed portfolio may epsilon-cover all Pareto points in 80% of complete cases; complete_pairs=60; max_simple_heuristic_coverage=0; deterministic_portfolio_coverage=1; per_method_coverage={} |
| C7 | **FAIL** | material opposite-sign port-aware HPWL proxy deltas around qualified routed parents required; children are structurally verified but not routed; qualified_parent_proxy_interventions=300; qualifying_design_count=0 |
| C8 | **PASS** | combinatorial lower-bound scale of ordered labelled nonempty chains; log10_architecture_counts={"s15850":{"1":1226.3567062533932,"2":1229.08343346242,"4":1233.7562883654127,"8":1241.7241851587335},"s5378":{"1":327.0476989196904,"2":329.2981189219993,"4":333.0134536057916,"8":339.046336166735},"s9234":{"1":400.34886507023367,"2":402.67108436496756,"4":406.5311427356577,"8":412.8580850439036}} |
| C9 | **FAIL** | all C1-C8 must pass on the original-plus-recovery execution union;  |

## Reproducible figures

The figure source dataset records hashes for every proxy, final route, execution manifest, analysis and intervention input. The figure manifest records each output and generator hash.

- [01_physical_vs_effective_activity.png](../reports/figures/phase0c/01_physical_vs_effective_activity.png): All qualified frozen-campaign rows (`b99972187aa2…`)
- [02_pareto_frontier_by_design.png](../reports/figures/phase0c/02_pareto_frontier_by_design.png): Representative paired Pareto front for each design (`6ceda2a4c853…`)
- [03_multichain_scan_overlays.png](../reports/figures/phase0c/03_multichain_scan_overlays.png): Representative placed FF-origin chain overlays (`e29e9c51be69…`)
- [04_activity_hotspot_maps.png](../reports/figures/phase0c/04_activity_hotspot_maps.png): Exact cumulative logical toggle maps for representative B0/K8 rows (`5ee5c0b7ece4…`)
- [05_effective_activity_maps.png](../reports/figures/phase0c/05_effective_activity_maps.png): Exact cumulative direct-sink-weighted logical toggle maps (`91c599bcc551…`)
- [06_chain_length_distribution.png](../reports/figures/phase0c/06_chain_length_distribution.png): All chain lengths grouped by K (`0b64d4bb36cd…`)
- [07_timing_comparison.png](../reports/figures/phase0c/07_timing_comparison.png): Tool-reported global-route setup and hold WNS (`8acf4a3a094a…`)
- [08_test_cycle_comparison.png](../reports/figures/phase0c/08_test_cycle_comparison.png): Median exact shift-clock counts by design and K (`a6beb8c67443…`)
- [09_congestion_comparison.png](../reports/figures/phase0c/09_congestion_comparison.png): Initial global-route resource use and overflow (`fb3e9512fa34…`)
- [10_physical_seed_variability.png](../reports/figures/phase0c/10_physical_seed_variability.png): Paired physical-seed variability at K=8 (`03a362513acd…`)
- [11_intervention_delta_distributions.png](../reports/figures/phase0c/11_intervention_delta_distributions.png): Frozen C7 local-swap delta distributions (`ca435da174e6…`)
- [12_heuristic_regret.png](../reports/figures/phase0c/12_heuristic_regret.png): Median paired regret from complete design-seed-K groups (`cbcdb0bed128…`)
- [13_objective_correlation_matrix.png](../reports/figures/phase0c/13_objective_correlation_matrix.png): Descriptive rank correlations over qualified rows (`4d28a60d27d1…`)
- [14_pareto_membership_frequency.png](../reports/figures/phase0c/14_pareto_membership_frequency.png): Frequency across complete design-seed-K groups (`98b81fd1ac24…`)
- [15_cross_design_aggregate.png](../reports/figures/phase0c/15_cross_design_aggregate.png): Within-design normalized aggregate by method (`925d17908542…`)
- [16_tradeoff_change_vs_k.png](../reports/figures/phase0c/16_tradeoff_change_vs_k.png): Median paired optimum differences by K (`dfdff8b8a70f…`)
- [17_search_space_scaling.png](../reports/figures/phase0c/17_search_space_scaling.png): N! × binomial(N−1,K−1) architecture count (`774d9616ece7…`)
- [18_runtime_and_storage_scaling.png](../reports/figures/phase0c/18_runtime_and_storage_scaling.png): Recorded final route time and archive storage (`567dc591de47…`)

## Answers to the 28 required questions

| # | Evidence-based answer |
|---:|---|
| 1 | 3 benchmarks qualified; Ibex and JPEG were audited but not admitted. |
| 2 | s5378=179, s9234=211, s15850=534 scan FFs. |
| 3 | s5378=117, s9234=156, s15850=133 frozen FAN patterns. |
| 4 | s5378=96.04%, s9234=94.14%, s15850=94.62% stuck-at coverage. |
| 5 | K=[1, 2, 4, 8] qualified under the final physical campaign. |
| 6 | 15 design-seed units and 5/5 physical seeds completed qualified rows. |
| 7 | 375 architecture variants were generated; planned=375. |
| 8 | 375 final variants were physically attempted; qualified=375. |
| 9 | 375 final routed variants passed structural verification. |
| 10 | 375 final variants had zero detailed-route DRC; status counts={'QUALIFIED': 375}. |
| 11 | Exact tool outputs include full-netlist detailed-route wirelength, via count, DRC, global-route timing and initial global-route utilization/overflow; exact exclusive scan-only routed length exists for 0 rows. |
| 12 | Port-aware FF-origin scan HPWL and mixed-net full-scan-path length upper bounds are physical proxies/bounds. |
| 13 | Per-clock logical scan toggles, totals, peaks, quantiles and ATPG target reconstruction are exact within the frozen no-capture shift simulator. |
| 14 | H8/H16/H32 and direct-sink-weighted H_eff are dimensionless activity proxies. |
| 15 | Shift-mode power status: COMMANDS_AVAILABLE_SHIFT_MODE_ACTIVITY_AND_POWER_NOT_QUALIFIED; no watts are reported. |
| 16 | PDNSim status: COMMAND_AVAILABLE_SHIFT_MODE_INSTANCE_POWER_NOT_QUALIFIED; no test-mode IR drop is reported. |
| 17 | K effects on exact shift cycles are reported in the K table; capture cycles are excluded and reported separately in proxy rows. |
| 18 | K effects on the port-aware physical proxy are reported as median/IQR/range in the K table. |
| 19 | K effects on H_eff8 and exact cumulative hotspot maps are reported in the K table and figures 04–05. |
| 20 | K effects on global-route setup WNS are reported in the K table; negative values, if present, are retained. |
| 21 | C3=PASS; practical conflict hits=58/60 assessed groups. |
| 22 | C4=PASS; qualifying seed counts={'s5378': 5, 's9234': 5, 's15850': 5}. |
| 23 | C5=PASS; replicated design count=3. |
| 24 | C6=FAIL; maximum single-method 2% coverage=0.000, fixed-portfolio coverage=1.000. |
| 25 | Median/IQR physical and activity regret for every deterministic method is reported in the heuristic table. |
| 26 | 300 frozen local-swap records were eligible; C7=FAIL with qualifying design count=0. |
| 27 | C8=PASS; formal log10 architecture counts={'s5378': {'1': 327.0476989196904, '2': 329.2981189219993, '4': 333.0134536057916, '8': 339.046336166735}, 's9234': {'1': 400.34886507023367, '2': 402.67108436496756, '4': 406.5311427356577, '8': 412.8580850439036}, 's15850': {'1': 1226.3567062533932, '2': 1229.08343346242, '4': 1233.7562883654127, '8': 1241.7241851587335}}. |
| 28 | Phase 1 decision: PACT_PHASE0C_LEARNING_GATE_FAIL; No. The frozen evidence does not satisfy every prerequisite for investigating a learned intervention model. |

## Scientific conclusion

**Has PACT demonstrated a problem for which investigating a learned intervention model is justified?** **No. The frozen evidence does not satisfy every prerequisite for investigating a learned intervention model.** The conclusion follows the frozen C1–C9 contract and remains valid whether it is GO or NO-GO.

`PACT_PHASE0C_LEARNING_GATE_FAIL`
