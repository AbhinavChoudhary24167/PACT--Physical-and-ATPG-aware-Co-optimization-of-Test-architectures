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
