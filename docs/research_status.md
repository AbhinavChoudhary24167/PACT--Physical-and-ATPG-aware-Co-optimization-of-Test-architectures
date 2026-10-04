# Research status

Baseline: `f2569d498cd5f26a88c4954ec163498eb3cf7d91`, 4 October 2026. This status uses saved records; cleanup is not a new research campaign.

PACT asks whether legal scan transformations can trade physical cost against ATPG-derived switching/hotspots while preserving test behavior. The current deterministic method combines bounded search, exact scan-state replay, bounded simultaneous settled logic, candidate shared-net geometry and separate physical/activity coordinates. No learned model is implemented.

| State | Established scope |
|---|---|
| Implemented | M3/M5 solver, implementation-aware/stateful evaluation, Stage-B constrained lanes, scan-only integration and independent replay |
| Validated | Incremental/reference/rollback contracts and selected structural/functional/FF/DRC/global-route timing checks |
| Stage A benchmarked | Completion receipt confirms B0/B1/exact B2/B3T/P0: 19/19 preselected records qualified, 27/30 indexed records measured/qualified; common Nangate45 backend, seed 11, original FAN workload |
| Stage B benchmarked | `PACT_STAGE_B_MULTI_DESIGN_CONVERGENCE`; nine routed selections qualified and passed routed wire budgets, across three designs with one fixed method/configuration |
| End to end qualified | `PACT_END_TO_END_SOLUTION_QUALIFIED`; frozen B2/B3T/B2 and nine exact selected orders pass physical, independent serial replay and complete FAN collapsed-class identity/weight comparisons |
| In progress | Reliable full-network hotspot prediction, throughput, uncollapsed fault-member identity enumeration and portable physical data distribution |
| Future | Evidence-led coverage/C extensions, broader designs/contexts/K and actual power-integrity analysis |

Stage A classifications are `PACT_STAGE_A_PHYSICAL_RESULTS_COMPLETE` and `PACT_EXTERNAL_BENCHMARK_COMPLETE`. Stage B uses B2/B3T/P0 starts, epsilon {0.02,0.05,0.10}, seed 11, K=2, 300 seconds per budget, 20,000 evaluations and 2,000-attempt stagnation. [Its report](../results/pact_stage_b/REPORT.md) and CSVs preserve every selected outcome.

Simultaneous E/H4/H8 improvement under routed budget exists across retained endpoints on all three designs, not every winner. s15850 C2 improves all activity coordinates; balanced C1/H4 C3 regress measured H4. All s9234 selections are dominated on the combined original three-objective front; adding H4 changes interpretation. Several proxy gains fail to transfer.

The supplied active H8 diagnosis identifies omitted depth-limited spatial regions and candidate ground-C errors in saved pairs. Counterfactual substitutions depend on order and a nonlinear maximum; they do not uniquely allocate causality or validate a replacement model. Stage B's s15850 diagnostic also finds omitted coverage changes the decisive peak. A fixed-background probe recovers H4 directions but fails H8 and is not the executed method.

Research designs are s5378 (179 FFs), s9234 (211) and s15850 (534), using stored FAN workloads and qualified identity maps. s27/`pact_sanity` are testing/debugging assets. The [end-to-end gate](end_to_end_qualification.md) repairs only FAN reporting, preserves original simulation statistics and compares every collapsed target-class identity and weight for the frozen references and all nine selections. Individual uncollapsed equivalence-class members are not enumerated and are not claimed equivalent.

Latest-model evidence is limited to small Nangate45 circuits, fixed workload/placement and K=2. Earlier 100K-FF synthetic scaling belongs to the working solver, not candidate-stateful industrial scaling. Fixed buffers, bounded logic, ground-C error and costly spatial accumulation remain limitations. Switching proxies establish neither watts/IR-drop nor signoff power/timing. Adaptive P1 and Stage C are not claimed complete.
