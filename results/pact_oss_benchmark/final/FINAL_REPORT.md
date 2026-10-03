# Controlled PACT research campaign: incomplete at Stage A

**Engineering: PACT_STAGE_A_INCOMPLETE. Scientific: PACT_BENCHMARK_INCONCLUSIVE.**

## 1. What was benchmarked?

Prepared designs: s5378, s9234 and s15850, existing qualified seed-11 Nangate45 placement, K=2 and existing FAN patterns. Architecture generation was qualified for B0, B1 and the frozen P0 archive. The implemented head-to-head benchmark was not reached.

| Method | Exact revision | Status |
|---|---|---|
| P0 | `9d9103027918b1d4af2b209e6d36133ad82d4a4e` | Frozen candidate_stateful depth=3; complete saved archive retained |
| B1 native | `08f67ee5ecd14db5a42be8c610bbfd1ccf079299` | Actual execute_dft_plan ordering qualifies for all three designs |
| B2 PR #10176 | `6fff875551fe13a2aae3a22f871a6ca7f8d5c1cf` | Full source/submodules acquired; CMake configuration fails |
| B3 PR #10666 | `746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656` | Immutable source acquired and inspected; build/generation not attempted after stop |
| B0 | Existing reference architecture hashes in architecture_manifest.csv | Canonical supplied-order K=2 control retained |

ORFS commit: `5e8b1450d19263f797a27c4f371b9dd19f32a3aa`. Fixed implementation OpenROAD: `26Q2-1164-g08f67ee5ec`, binary SHA256 `fcd7dcfc37d329bd43a7ede75805319a2e70e6879da11d42b4fd1c2e50e645c3`. Its local source checkout was a different revision, so native semantics were inspected using source acquired at the binary revision instead. B2 merge-base: `21512b0ab68cc3bc7e11a772e1ec32f6f90e0eec`. B3 merge-base: `b084e4561bf51f905345ff0f767434095d79d3bc`.

The exact commands, algorithm parameters, configurations, source Git blobs, source SHA256s, architecture identities and native endpoint translations are in protocol/ and baselines/. B2 uses native NN initialization and endpoint-inclusive FF-origin Manhattan 2-Opt, default 30 iterations. B3 uses capacity-aware same-domain K-means (100 iterations maximum), NN, directed scan-pin 2-Opt with reversal correction and direction-preserving 3-Opt over 50 nearest candidates; its local-search cost excludes external endpoints. This description comes from the pinned implementation, not only the PR summary.

## 2. Was the comparison fair?

The contract freezes mapped design, exact FF inventory/coordinates, technology, original Liberty/LEF infrastructure, clocks/constraints, K, placement/seed, FAN pattern hashes, load/capture/unload cycles, routing/extraction/measurement scripts, H4/H8 grids, source attribution and timing methodology. Source/input/evidence verification passes 454 bindings. No production model or optimizer file changed. No placement, routing-method, K, seed, workload or measurement change was made.

Documented generator adapter exceptions: the byte-identical historical test_cell-only Liberty annotation provides missing native DFT metadata without changing functional/timing/C data; indexed native chain-0 ports are translated before STA initialization with endpoint geometry preserved; logical PACT test_si_0/test_so_0 map to physical test_si/test_so in the common adapter. FF membership/order is preserved by translation. Native K=2 lengths are 90/89, 106/105 and 267/267, preserving the maximum-chain workload cycle count. No K=1 native order was split and passed off as native K=2.

There is no fair **implemented** comparison yet, because the requested B2 binary has not been reproduced. No backend was substituted to manufacture a comparison.

## 3. How did P0 compare with OpenROAD?

Unknown. Pre-route scan-edge HPWL and saved P0 E/H4/H8 predictions are diagnostics only. There are no implemented B1/B2/B3 measurements in this campaign. A1–A5 are not assessable; historical PACT measurements have not been relabeled as external-baseline evidence.

## 4. What was wrong with P0?

The existing, hashed H8 root-cause result identifies fixed-depth spatial coverage omissions interacting with candidate-specific extracted ground capacitance. Of 37 problematic saved comparisons, 27 first recover ordering after omitted-net substitution and 10 after capacitance substitution. Coverage of represented measured E is about 83–84%, 72–74% and 69–70% for s5378/s9234/s15850. These are existing diagnosis results, not a repeated root-cause study. They justify the planned adaptive stateful coverage mechanism, while retaining ground-C limitations.

## 5. What changed in P1?

Nothing. P1 implementation has not started. Adaptive stateful cone expansion remains the sole authorized Stage-B mechanism once Stage A is successfully completed and sealed. P0 depth=3 and all optimizer semantics remain unchanged. An incomplete Stage-A seal does not open Stage B.

## 6. Did P1 improve prediction?

Not evaluated. P1 scores, reference/incremental correctness, coverage accounting and historical prediction deltas do not exist. No new expansion rule or threshold was fitted using measured labels.

## 7. Did P1 improve actual implemented outcomes?

Not evaluated. New routes: **0**. New extraction, simulation and ATPG runs: **0**. E/H4/H8 measurements and implemented deltas are blank, not zero. E retains units fF·transitions; H4/H8 retain fF·transitions per bin/cycle. These are C×N switching metrics, not measured power or Joules.

## 8. How does P1 compare with P0?

Unavailable for physical cost, E, H8, runtime, memory and architecture selection. The complete P0 retained archive is copied canonically (18 archive points across designs, plus 6 B0/B1 controls). Predicted-only selection retains seven distinct P0 points. Balanced minimax normalized regret is the method representative; physical and H8 extrema are also retained with SHA tie breaks and deduplication. Multiple PACT points versus single OSS solutions are explicit. Full archive points without imported implementation evidence are not treated as implemented frontier points.

## 9. How does P1 compare with OpenROAD?

Unavailable against B1, B2 and primary B3. B2 failed configuration on missing SWIG >=4.3; Tcl headers are also absent. CMake logged source-archive VCS warnings, while immutable main/submodule commits and hashes are independently recorded. This is a build-environment qualification failure, not proof of an algorithm defect or impossibility of building elsewhere. B3 source inspection passed; its full build was not attempted after the stop condition. Neither baseline is replaced by a Python implementation or a floating branch.

## 10. Does PACT add an external Pareto point?

Unknown. The required three-dimensional implemented space (routed full scan-path wire upper bound, measured E, measured H8) is not populated. No architecture is labeled dominated/nondominated, and no unique external frontier contribution is claimed. No weighted score or post-outcome tolerance was introduced.

## 11. What did adaptive expansion cost?

Not implemented, so P1 graph growth, throughput, rollback cost, runtime and peak RSS are unmeasured. runtime.csv retains the historical frozen P0 command times and RSS (397/203/53 mutation evaluations), actual native generator-command time/RSS and the failed build-configuration resource record. The failed B2 configuration took 108.178 seconds. These phases are not interchangeable search-performance measurements.

## 12. What remains unresolved?

Immediate gate: build the exact pinned B2/B3 revisions in an isolated toolchain and qualify canonical K=2 architectures before implementing/measuring them under the original backend. SWIG >=4.3 and Tcl development headers are demonstrably missing; subsequent build prerequisites remain unchecked. Original source archives and submodule data remain on D: for reproducible recovery. Failed native adapter attempts and their corrections are retained; successful qualified attempts have executed-source snapshots.

Fault coverage/detected-count source evidence is retained with hashes; candidate fault identity-set equivalence is not established. Glitch/delay-aware activity, distributed power density, IR-drop, larger designs, additional K/placements and technology generalization remain outside this controlled campaign. None was introduced as a fallback.

Validation executed: 10 new protocol tests and 6 existing candidate_stateful tests, **16 passed**; native actual DFT/FF/placement/capacity/SI/SO qualification for all three designs; canonical 24-architecture legality and exact inventory/coordinate/endpoint checks; 454 frozen source/input/historical-evidence bindings checked. No P1 test is claimed.

## 13. What is the next scientifically justified milestone?

**Provision an isolated reproducible build toolchain for the two pinned PRs, then complete and seal this unchanged Stage-A benchmark before P1.** Keep the captured revisions, protocol, canonical P0 selection, placement, workload and physical backend fixed.

Commit boundary: this incomplete Stage-A seal is committed separately. Stage-B/model and Stage-C commits do not exist. The exact seal SHA is recorded in the subsequent commit receipt and final response; it cannot be embedded in the same commit that creates it. Initial user README/planning/fault-identity/H8 evidence edits are preserved and excluded from the milestone commit. Final Git status is recorded in the commit receipt.
