Cold-start unseen designs attempted: 8
Cold-start searches completed: 4
PACT candidates physically qualified: 12
Designs with useful activity improvement: 4
Designs with mixed/no improvement: 1
Designs blocked by infrastructure/scalability: 4

Classification: `PACT_COLD_START_GENERALIZATION_MIXED`.
Milestone: `PACT_COLD_START_UNSEEN_DESIGN_CAMPAIGN_COMPLETE`.
Secondary classifications: `PACT_COLD_START_MEASUREMENT_SCALABILITY_BLOCKED`

PROSPECTIVE UNSEEN COLD-START RESULTS

| Design | Reference | PACT candidate | Δ routed WL % | ΔE % | ΔH4 % | ΔH8 % | WNS ns | DRC | Fault coverage % | Search runtime s | Status |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| s953 | B2 | CS_C1 | 7.011 | -20.412 | -9.321 | -11.289 | 9.350 | 0 | 97.853 | 26.698 | PACT_STRONG_IMPROVEMENT |
| s953 | B2 | CS_C2 | 4.812 | -14.467 | -8.275 | -11.237 | 9.349 | 0 | 97.853 | 26.698 | PACT_STRONG_IMPROVEMENT |
| s953 | B2 | CS_C3 | 5.551 | -4.224 | -2.274 | 3.273 | 9.350 | 0 | 97.853 | 26.698 | PACT_MIXED_TRADEOFF |
| s1196 | B2 | CS_C1 | 0.818 | -18.908 | -10.022 | -6.448 | 9.134 | 0 | 98.840 | 19.382 | PACT_STRONG_IMPROVEMENT |
| s1196 | B2 | CS_C2 | 0.577 | -24.377 | -0.171 | -7.069 | 9.133 | 0 | 98.840 | 19.382 | PACT_STRONG_IMPROVEMENT |
| s1196 | B2 | CS_C3 | 0.343 | -11.404 | -4.047 | 1.933 | 9.134 | 0 | 98.840 | 19.382 | PACT_MIXED_TRADEOFF |
| s1238 | B3T | CS_C1 | -3.148 | -23.255 | -7.312 | 1.476 | 9.076 | 0 | 96.363 | 27.412 | PACT_MIXED_TRADEOFF |
| s1238 | B3T | CS_C2 | 0.090 | -26.665 | -7.489 | -0.182 | 9.076 | 0 | 96.363 | 27.412 | PACT_STRONG_IMPROVEMENT |
| s1238 | B3T | CS_C3 | -1.945 | -9.129 | -9.225 | 1.065 | 9.076 | 0 | 96.363 | 27.412 | PACT_MIXED_TRADEOFF |
| s35932 | B2 | CS_C1 | 2.103 | -0.141 | -1.636 | -2.687 | 8.415 | 0 | 87.578 | 2908.540 | PACT_STRONG_IMPROVEMENT |
| s35932 | B2 | CS_C2 | 1.291 | -0.650 | -1.916 | -2.610 | 8.415 | 0 | 87.578 | 2908.540 | PACT_STRONG_IMPROVEMENT |
| s35932 | B2 | CS_C3 | 0.959 | -0.284 | -1.373 | -2.572 | 8.415 | 0 | 87.578 | 2908.540 | PACT_STRONG_IMPROVEMENT |

Negative percentages are improvements. N/A means unavailable exact data. Search estimates are kept in JSON and never substituted for measured activity. Physically qualified means route/topology/function/placement/timing/DRC, FAN identities/weights, and complete VCD FF transitions all passed.
Useful activity improvement counts any exact E/H4/H8 gain above the fixed tolerance among retained candidates. It does not erase another metric regression or routed-wire increase. The design status follows its preselected balanced primary. All alternatives contribute to explicitly named any-candidate counts.

| Design | FFs | FAN patterns | Reference | Initialized | Search completed | Preselected | Qualified | Design status | Blocker reason |
|---|---:|---:|---|---|---|---:|---:|---|---|
| s208 | 8 | 29 | N/A | False | False | 0 | 0 | PACT_EXECUTION_BLOCKED | Frozen K=2 minimum eight FFs per chain |
| s510 | 6 | 59 | N/A | False | False | 0 | 0 | PACT_EXECUTION_BLOCKED | Frozen K=2 minimum eight FFs per chain |
| s953 | 29 | 89 | B2 | True | True | 3 | 3 | PACT_STRONG_IMPROVEMENT | N/A |
| s1196 | 18 | 134 | B2 | True | True | 3 | 3 | PACT_STRONG_IMPROVEMENT | N/A |
| s1238 | 18 | 145 | B3T | True | True | 3 | 3 | PACT_MIXED_TRADEOFF | N/A |
| s35932 | 1728 | 21 | B2 | True | True | 3 | 3 | PACT_STRONG_IMPROVEMENT | N/A |
| s38417 | 1636 | 105 | B2 | True | False | 0 | 0 | PACT_EXECUTION_BLOCKED | New independent REF_B2 exact-activity measurement failed (RESOURCE_LIMIT) at the fixed 1800-second deadline; complete VCD and exact E/H4/H8 are unavailable; only this design stops independently |
| s38584 | 1426 | 133 | B3T | True | False | 0 | 0 | PACT_EXECUTION_BLOCKED | New independent REF_B3T exact-activity measurement failed (RESOURCE_LIMIT) at the fixed 1800-second deadline; complete VCD and exact E/H4/H8 are unavailable; only this design stops independently |

6 designs initialized with zero historical per-design state; 4 completed all registered epsilon lanes; 4 produced at least one exactly qualified candidate.
E improved on 4 designs, H4 on 4, H8 on 4, and all three on 4. Routed cost, WNS, DRC and weighted FAN coverage accompany every available comparison above.
The opening mixed/no count describes 1 preselected-primary outcomes (including completed searches with no new candidate). Separately, 3 designs have at least one exact mixed candidate, including 3 with a mixed alternative; 0 have a no/negligible-benefit candidate. These flags can overlap useful-improvement counts and never change the primary.
The minimum qualified routed scan cost among B0/B1/B2/B3T was frozen before input construction. The selected external architecture is the sole search start. No P0, prior PACT archive, precursor search, manually mapped unseen design, learned initialization or tuned weights are used. Seed 11, K=2, epsilons .02/.05/.10 and all existing operators/archive/restart settings remain fixed. Mutation-loop budgets are 300*max(1,ceil(FF/600)) seconds. s208 and s510 remain blocked by the minimum eight FFs per chain.

Solver and physical scalability

scalability/solver_scalability.csv and .json report completed epsilon lanes independently. Model setup, lane initialization, mutation loop, independent replay and full worker timing are different domains. Whole-worker CPU/RSS and model setup repeat as context in lane rows and must not be summed. Exact mutation evaluations exclude wire-screened proposals; exact state-score calls and independent replay counters are also retained. Archive admission counts include the explicitly reported initial reference insertion.
The measured evaluator subtotal adds six disjoint original forward/rollback/reduction spans across the whole lane. state_score_seconds overlaps reduction_seconds and is not added again. Independent retained-candidate replay is reported separately, after the mutation loop. Whole-lane un-attributed time is the remainder after those measured components and replay; it includes untimed evaluator construction/restarts, allocations/setup and solver work. solver_overhead_seconds is unavailable. No component subtotal is subtracted from mutation-loop time to invent an overhead measurement.
scalability/physical_measurement_scalability.json reports compile, VVP simulation, VCD bytes, parser/transition spans and exact E/H4/H8 reductions separately. VCD generation shares the VVP process; isolated generation time is unavailable. Parser CPU/RSS are inclusive; exclusive parse/transition wall times must not be added to their inclusive span.

| Design | FFs | Patterns | Epsilon | Exact mutations | Eval/s | Loop s | Termination |
|---|---:|---:|---:|---:|---:|---:|---|
| s953 | 29 | 89 | 0.020 | 416 | 107.272 | 3.878 | stagnation |
| s953 | 29 | 89 | 0.050 | 775 | 154.540 | 5.015 | stagnation |
| s953 | 29 | 89 | 0.100 | 2329 | 168.725 | 13.804 | stagnation |
| s1196 | 18 | 134 | 0.020 | 1452 | 226.923 | 6.399 | stagnation |
| s1196 | 18 | 134 | 0.050 | 621 | 243.710 | 2.548 | stagnation |
| s1196 | 18 | 134 | 0.100 | 1530 | 252.669 | 6.055 | stagnation |
| s1238 | 18 | 145 | 0.020 | 1812 | 257.701 | 7.031 | stagnation |
| s1238 | 18 | 145 | 0.050 | 1552 | 233.406 | 6.649 | stagnation |
| s1238 | 18 | 145 | 0.100 | 2350 | 260.436 | 9.023 | stagnation |
| s35932 | 1728 | 21 | 0.020 | 269 | 0.298 | 901.801 | wall_clock |
| s35932 | 1728 | 21 | 0.050 | 262 | 0.290 | 901.936 | wall_clock |
| s35932 | 1728 | 21 | 0.100 | 255 | 0.282 | 905.284 | wall_clock |

For the largest observed search (s35932, 1728 FFs, 21 FAN patterns), the largest instrumented evaluator component is spatial_seconds: 1308.986 seconds across completed lanes. This profile covers evaluator components and does not attribute all initialization, solver overhead or independent replay time.

First observed solver computational bottleneck: s35932 epsilon 0.02 concentrated measured evaluator time in spatial_seconds 433.693 s, rollback_seconds 372.718 s. The lane performed 269 exact mutations in 901.801 loop seconds (0.298 evaluations/s). Completed small-design lanes ranged from 107.272 to 260.436 evaluations/s. This observation is separate from a registered resource-policy failure. It establishes neither a scaling law nor a memory-bandwidth or other hardware cause.

First observed solver resource bottleneck: No solver resource bottleneck established by completed observations; limited samples do not support extrapolation.
Earlier campaign measurement evidence (separate from new attempts): the prior s38417 reference VVP simulation reached its fixed 1,800-second deadline before parsing or metric reductions. Its retained partial VCD and prior timeout diagnosis are diagnostic only and do not terminate a new campaign unit or supply E/H4/H8.
New independent s38417 REF_B2 exact-reference attempt: FAILED/RESOURCE_LIMIT; reached its independently fixed 1800-second deadline during functional VVP simulation with integrated VCD emission. Workflow wall 1800.314 s, CPU 1418.068 s, maximum process RSS 1302900 KiB; VVP wall 1728.661 s, CPU 1369.130 s, process RSS 262172 KiB. VCD complete=False, bytes=1695037021; parser/transition and exact E/H4/H8 stages were not executed. No partial activity value is included. Only this design stops under the independent-unit policy; the other registered units continue independently. Result: repo://results/pact_cold_start_unseen_20261004/physical/s38417/REF_B2/activity/result.json; new terminal diagnosis: repo://results/pact_cold_start_unseen_20261004/scalability/measurement_s38417_terminal_diagnosis.json.
New independent s38584 REF_B3T exact-reference attempt: FAILED/RESOURCE_LIMIT; reached its independently fixed 1800-second deadline during functional VVP simulation with integrated VCD emission. Workflow wall 1800.277 s, CPU 1395.341 s, maximum process RSS 1446208 KiB; VVP wall 1719.954 s, CPU 1340.945 s, process RSS 290340 KiB. VCD complete=False, bytes=2011730179; parser/transition and exact E/H4/H8 stages were not executed. No partial activity value is included. Only this design stops under the independent-unit policy; the other registered units continue independently. Result: repo://results/pact_cold_start_unseen_20261004/physical/s38584/REF_B3T/activity/result.json; new terminal diagnosis: repo://results/pact_cold_start_unseen_20261004/scalability/measurement_s38584_terminal_diagnosis.json.
Solver runtime growth is observable only through the measured FF/pattern/evaluation rows. No fitted scalability law or extrapolated FF cutoff is claimed. Sparse size coverage and workload differences prevent attributing a runtime change solely to FF count.

Execution hardware: WSL kernel 6.18.33.2, four logical cores, MemTotal 4,010,612 KiB and 8 GiB swap. Solver and physical measurement jobs may overlap. These runtimes are observations from concurrent campaign execution, not isolated scaling benchmarks.

Provenance and limits

reference_frozen -> cold_start_input -> search_configuration -> search_results -> preselected_candidates -> selection_snapshot -> per-candidate rewire -> physical -> ATPG -> final_qualification is audited by bound receipts. The immutable selection snapshot binds every retained candidate and the input; each rewire command binds its preselected architecture. Rewire execution-interval starts are reconstructed explicitly as completion timestamp minus measured wall duration, proving selection preceded implementation; they are not separately recorded process-launch timestamps. Physical/ATPG per-candidate completions establish subsequent gate order, and aggregate timestamps summarize completed gates. Every retained candidate remains in the dataset, including failures. Engineering observer repairs and failed diagnostic attempts are retained separately from scientific outcomes.
The metric scope remains all_data ground-plus-pin capacitance times measured transitions. H4/H8 locate demand at sources in fixed spatial bins per cycle. Routed scan cost is the connected scan-net upper bound and can include functional branches. Search scores omit unrepresented fanins, delay/glitches and candidate resizing/buffer changes; actual route and exact activity remain authoritative. These are not watts, IR-drop, signoff power, reliability, or uncollapsed-member identity claims.

HISTORICAL QUALIFIED CORE

The s5378/s9234/s15850 core appears only in canonical/historical_qualified_core.json and this separate section. All 12 original record dictionaries and historical primary choices are copied exactly, with their original values and classifications. They were not cold-start training, seeds or runtime inputs.

| Historical design | Frozen reference | Frozen primary |
|---|---|---|
| s5378 | B2 | s5378_C1 |
| s9234 | B3T | s9234_C1 |
| s15850 | B2 | s15850_C1 |
