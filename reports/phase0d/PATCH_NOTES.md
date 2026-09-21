# PACT Phase-0D Patch Notes

## Base

- Starting branch: `codex/pact-phase0c-multichain-conflict`
- Phase-0D branch: `codex/pact-phase0d-budgeted-search`
- Starting and frozen Phase-0C commit: `06d97d82263b3671d8a56c9e6ed104cf88d40266`
- Phase-0C decision preserved: `PACT_PHASE0C_LEARNING_GATE_FAIL`
- Phase-0D state: pilot evidence complete; final campaign not launched

## Added

- frozen Phase-0D pilot contract and manifest schema;
- SHA256 audit of 8,050 tracked Phase-0C files and 83 upstream dependency files;
- resumable execution manifests, deterministic run IDs, status reporting, disk-floor and timeout guards;
- bounded deterministic swap, 2-opt, block-relocation, cross-chain-move, cross-chain-swap, endpoint-reassignment, and cross-chain-block-move operators;
- legality, FF-bijection, fixed-K, endpoint, balance, and exact ATPG-reconstruction proofs;
- greedy-best, greedy-first, beam-search, and simulated-annealing baselines with common budgets and early stopping;
- exact three-objective Pareto, hypervolume, epsilon-coverage, and regret utilities;
- qualified Phase-0C proxy reuse and new Phase-0D proxy caching;
- selective OpenROAD route integration with zero-DRC/topology qualification and compressed ODB retention;
- pilot manifest, machine-readable metrics, status, route-filter result, runtime/storage projection, and report.

## Changed

- README now separates the frozen Phase-0C decision from Phase-0D's pilot-only status.
- Manifest status vocabulary records a route skipped because no candidate passed the frozen Pareto filter.

## Preserved

- all tracked Phase-0C campaign files, reports, manifests, thresholds, gate decisions, ATPG evidence, and qualified routes;
- all inherited untracked Phase-0B files that were present before Phase-0D work;
- the Phase-0C interpretation that ML necessity was not established.

## Validation

- 110/110 unit tests passed after the pilot;
- all seven richer operators produced legal children in the pilot;
- all pilot children reconstructed all 117 frozen s5378 ATPG targets;
- pilot manifest artifact hashes verified;
- Phase-0C dependency hashes verified with no mismatch;
- no Phase-0C tracked file was modified.

## Pilot result

- context: s5378, seed 11, K=2, starting method P;
- logical proxy evaluations: 39 (seven operator checks plus 32 search evaluations);
- unique new proxy artifacts: 22;
- valid cached proxy reuses across search methods: 17;
- new physical routes: 0, because no searched child passed the proxy-nondominance filter;
- projected naive full-campaign serial time: approximately 70 hours;
- repository scientific state: `PILOT_COMPLETE_NO_ROUTE_QUALIFIED`;
- final Phase-0D decision: not evaluated.

## Known limitations

- the pilot covers one ISCAS89-scale context and cannot establish cross-seed or cross-design gates;
- H_eff is a dimensionless proxy, not measured power or current;
- shift-mode power and test-mode IR-drop evidence remain unavailable;
- the selective physical route stage was not invoked because no candidate qualified;
- the working tree had 3,889 inherited untracked Phase-0B paths before Phase-0D began, so Git cleanliness must be reported relative to Phase-0D work rather than by discarding those files.

## Optimizer v1

### Added

- a five-start global constructor using endpoint-aware balanced cheapest/regret insertion from empty chains;
- a labeled static direct-sink-weighted ATPG target-compatibility relation for construction only;
- region, hotspot, segment, cross-chain, and seeded guided LNS destroy operators;
- physical-best, balanced, activity-best, and regret repair strategies at 5%, 10%, and 20% neighborhood sizes;
- an exact two-objective fixed-K Pareto archive over the qualified HPWL proxy and exact H_eff8;
- exact chain-local incremental physical deltas, asserted against the full proxy after each new LNS evaluation;
- cumulative wall-clock checkpoints, resumable state, exact candidate records, cache accounting, and seven focused figures;
- a selective routing namespace and corrected post-route verifier bootstrap;
- cleanup classification, large-file audit, and a SHA256 manifest for the preserved external raw Phase-0B archive.

### Runtime-accounting correction

The historical pilot files were not rewritten. Its STATUS elapsed value described the current/finalization invocation, whereas the larger summed proxy time described unique cached proxy work created across earlier invocations. Optimizer v1 now records process invocation, cumulative search wall time, accumulated new-proxy time, rewire time, route time, all post-route verification attempts, report finalization, and total active campaign time as distinct quantities.

### Validation and result

- 120/120 unit tests passed before the frozen run;
- the frozen s5378/seed11/K2 run proposed and exactly evaluated 24 unique architectures in 61.313 seconds of measured search time;
- five PACT architectures entered the combined Phase-0C/PACT proxy Pareto front;
- the prior Phase-0C front was P (1380.83, 63.33), T (1421.17, 62.33), J50 (2634.75, 61.67), and A (6850.21, 60.50), in (HPWL proxy µm, H_eff8);
- the selected PACT representative was (2157.81, 59.00);
- its new route had zero detailed-route DRC, 26,982 µm full-netlist detailed-route wirelength, 13,469 vias, 9.08672 ns setup WNS, 0.00273018 ns hold WNS, 23.81% initial global-route utilization, zero overflow, and a passing structural reconstruction proof;
- exact status: `PACT_OPTIMIZER_V1_PROXY_ADVANCE` and `PACT_OPTIMIZER_V1_ROUTE_QUALIFIED`;
- no ML model was introduced and no multi-design/multi-seed campaign was launched.

### Resource reuse and limitations

- all six qualified Phase-0C proxy rows and all 375 Phase-0C routes remained existing evidence; none was recomputed;
- the final optimizer run had zero cache hits because all 24 generated architectures were unique, while frozen Phase-0C rows were reused directly as the reference set;
- H_eff remains a dimensionless proxy rather than power/current, and the construction activity relation is explicitly not H_eff8;
- the v1 global insertion implementation is O(N^3) worst-case time with O(N) working storage and does not claim 100K-FF scalability;
- activity-heuristic delta versus exact H_eff8 delta had Pearson r=0.234 over 19 LNS samples, so the relation is useful only as a weak ranking heuristic and warrants deliberate refinement before scale-up.
