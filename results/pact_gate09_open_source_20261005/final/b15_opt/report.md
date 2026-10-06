# Gate 09: b15_opt open-source comparison

## A. Executive classification

PACT_GATE09_MIXED_GENERALIZATION

Primary PACT candidate: CS_C1. Activity classification: PACT_ACTIVITY_MIXED. The complete four-objective Pareto comparison is retained below; alternative candidates do not replace the primary.

## B. Admission

The fixed C≥6 GiB and D≥25 GiB floors passed before heavy stages. D also reserves 20 GiB plus max(5 GiB, the per-design retained/projected trace and count-cache allowance). The source and mapped all-state next-state equivalence, FF inventory, placement, route, extraction, timing, DRC, FAN workload and exact external-reference activity gates passed. The admitted source is pinned cad-polito-it/I99T, EUPL-1.2; this design was admitted as unseen in PACT campaigns.

## C. Frozen methodology

PACT source 71b059d9d1a00735d79b6a428693eaba549a5f33; qualified CPU continuation from merged PR #3. K=2, seed 11, epsilon 0.02/0.05/0.10, 900 seconds per mutation loop, 7200-second search worker ceiling. Max 20,000 evaluations, stagnation 2000, lane attempts 150, neighbors 16, segment 8, archive 16, equal E/H4/H8 weights, logic depth 3 with BUF/INV transparent. Initialize only from the frozen minimum-qualified-routed-WL B0/B1/B2/B3T reference. Balanced/best E/best H4/best H8 role selection, hash deduplication, at most three new candidates before final routing. An exact evaluation in flight may finish past a loop deadline. No tuning or extra seed was used.

## D. Competitors

- **B0**: Supplied source scan order split contiguously into balanced K=2 capacities; common original control Parameters {"K": 2}.
- **B1**: Native placed-cell greedy nearest neighbor; Boost Geometry Cartesian nearest uses Euclidean ranking; start minimizes x+y Manhattan distance to origin; no endpoint-inclusive local refinement Source 08f67ee5ecd14db5a42be8c610bbfd1ccf079299.
- **B2**: Established native FF-origin nearest neighbor followed by endpoint-inclusive symmetric Manhattan 2-opt, maximum 30 iterations Source 6fff875551fe13a2aae3a22f871a6ca7f8d5c1cf.
- **B3T**: Qualified patched OpenROAD K-means partition plus directed scan-pin Manhattan nearest neighbor and strict improving 2-opt/3-opt; external endpoints excluded by optimizer and included by common qualification Source 5c3751171685d507939ee7064a67feec786e5219. Parameters {"capacity": "ceil(FF/K)", "kmeans_iterations": 100, "neighbor_count": 50, "overquery": 100}.
- **B4**: Existing phase0c A: global greedy balanced chain extensions minimizing mean load-PPI bit disagreement over the identical frozen FAN patterns; activity proxy, not exact E Parameters {"K": 2, "alpha_physical": 0.0, "beta_activity": 1.0}.
- **B5**: Existing phase0c J50: global greedy balanced extensions of 0.5 normalized FF-origin Manhattan distance + 0.5 mean load-PPI disagreement Parameters {"K": 2, "alpha_physical": 0.5, "beta_activity": 0.5}.
- **B6**: NO_ADMITTED_DIRECT_COMPARATOR

B4 and B5 reuse the frozen phase0c A/J50 implementations, one architecture each. Their load-PPI mismatch is a proxy and does not optimize routed exact E directly. B3T is explicitly OPENROAD_QUALIFIED_PATCHED. All methods use the same qualified FAN generic circuit/reporter repair; the earlier b14 446-pattern workload was invalidated and preserved; each design uses its corrected common workload. Minimal probes, source patches, branch SHAs and failed attempts are retained. The initial connector attempt returned GitHub 403 “Resource not accessible by integration”; its evidence remains saved. The construction defects were subsequently published and visibly verified as [FAN_ATPG issue #5](https://github.com/NTU-LaDS-II/FAN_ATPG/issues/5), with the body and submission proof in publication/FAN_upstream_issue.json. The separate fault-identity reporting defect is [FAN_ATPG issue #6](https://github.com/NTU-LaDS-II/FAN_ATPG/issues/6), bound by publication/FAN_reporter_upstream_issue.json.

## E. Fairness

{
  "status": "PASS",
  "equal_fields": [
    "ff_count",
    "chain_count",
    "patterns",
    "fault_coverage",
    "fault_target_count",
    "simulation_cells_hash",
    "source_placed_database",
    "source_netlist",
    "SDC",
    "timing_stage",
    "pattern_hash",
    "placement_hash",
    "identity_hash",
    "FF_coordinates"
  ],
  "physical_seed": 11,
  "K": 2,
  "route_backend": "Pinned common /usr/bin/openroad",
  "extraction": "Same frozen OpenRCX parameters and Nangate45 RC rules",
  "fixed_endpoints": "Common index-based canonical port policy; test_si_0/test_si aliases denote identical first-chain endpoint",
  "candidate_preselection": "Before final routing and exact; maximum three new PACT architectures",
  "qualified_rows": 9,
  "measured_cycle_counts": [
    208800,
    208800,
    208800,
    208800,
    208800,
    208800,
    208800,
    208800,
    208800
  ],
  "cycle_note": "Actual chain lengths determine clock count; every method uses the same parallel shift/padding policy and patterns"
}

Common mapped source, FF coordinates, positive-edge CK, SI/SO port policy, K=2, scan enable, FAN collapsed stuck-at workload, compression/X-fill policy, seed 11, two-thread OpenROAD routing, OpenRCX extraction, Nangate45 library, and one-worker CPU exact activity were held constant. Final timing is measured at the global-route stage; DRC is from detailed route. Routed scan WL is the frozen full scan-path net-length upper bound, including functional branches on shared nets.

## F. Search

Search wall 3651.418 s, CPU 3738.656 s, peak process RSS 1330428 KiB, exact mutation evaluations 2748. These mutation evaluator calls are distinct from final routed netlist replays. Search estimates remain in candidate receipts.
- ε=0.02: 756 exact mutations, termination wall_clock; 6301 attempts, 112 accepted.
- ε=0.05: 978 exact mutations, termination wall_clock; 4501 attempts, 127 accepted.
- ε=0.1: 1014 exact mutations, termination wall_clock; 3996 attempts, 154 accepted.

## G. Physical results

All physical outcomes appear in the primary table, including unsuccessful candidates. Every PACT route corresponds to a preselected architecture; none was hidden or chosen after final measurement.

## H. ATPG

The same fixed patterns and full collapsed-fault identity/weight/status contract were preserved by serial replay and repaired FAN simulation. Coverage is the measured stuck-at percentage; the campaign does not claim complete fault coverage.

Shared ATPG generation wall 118.682 s; the authoritative execution receipt is /mnt/d/PACT_EXPERIMENTS/results/pact_gate09_open_source_20261005/repair_attempts/metadata_registration_b15_opt/inputs/b15_opt/atpg_generate/stdout.txt.

## I. Exact activity

E sums capacitance-weighted settled transitions over all measured data nets. H4/H8 are the maximum per-cycle source-localized capacitance-weighted bin activity on 4×4/8×8 grids. OpenRCX ground capacitance plus Liberty sink capacitance is used; coupling is retained separately and excluded. These proxies are not joules. Full functional replay and every FF-Q/cycle crosscheck must pass.

## J. Primary comparison

| Design | Method | Scan WL µm | ΔWL % | E | ΔE % | H4 | ΔH4 % | H8 | ΔH8 % | WNS ns | Hold ns | DRC | FC % | Runtime s | Status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| b15_opt | B0 | 22724.085 | 9.309 | 722000716.372 | -5.339 | 1682.491 | 4.440 | 756.854 | 4.471 | 7.503 | 0.000576 | 0.000 | 96.750 | 928.216 | QUALIFIED |
| b15_opt | B1 | 21667.565 | 4.227 | 769712632.615 | 0.916 | 1509.254 | -6.313 | 738.816 | 1.981 | 7.501 | 0.001363 | 0.000 | 96.750 | 924.003 | QUALIFIED |
| b15_opt | B2 | 20788.795 | 0.000 | 762723552.495 | 0.000 | 1610.960 | 0.000 | 724.461 | 0.000 | 7.505 | 0.000001 | 0.000 | 96.750 | 908.209 | QUALIFIED |
| b15_opt | B3T | 20996.255 | 0.998 | 850179717.043 | 11.466 | 1496.128 | -7.128 | 693.367 | -4.292 | 7.499 | 0.001171 | 0.000 | 96.750 | 931.709 | QUALIFIED |
| b15_opt | B4 | 37422.085 | 80.011 | 675469434.621 | -11.440 | 1403.901 | -12.853 | 699.184 | -3.489 | 7.502 | 0.001768 | 0.000 | 96.750 | 922.031 | QUALIFIED |
| b15_opt | B5 | 23782.035 | 14.398 | 610729605.623 | -19.928 | 1496.339 | -7.115 | 720.438 | -0.555 | 7.497 | 0.001342 | 0.000 | 96.750 | 885.223 | QUALIFIED |
| b15_opt | CS_C1 | 21066.570 | 1.336 | 753061810.773 | -1.267 | 1653.142 | 2.618 | 712.270 | -1.683 | 7.505 | 0.000626 | 0.000 | 96.750 | 4565.834 | QUALIFIED |
| b15_opt | CS_C2 | 20975.105 | 0.896 | 752304978.541 | -1.366 | 1584.504 | -1.642 | 754.535 | 4.151 | 7.504 | 0.000680 | 0.000 | 96.750 | 4534.604 | QUALIFIED |
| b15_opt | CS_C3 | 21048.475 | 1.249 | 755008752.684 | -1.011 | 1653.047 | 2.613 | 714.750 | -1.340 | 7.506 | 0.000626 | 0.000 | 96.750 | 4531.799 | QUALIFIED |

Deltas are relative to the frozen B2 reference. Runtime includes generation when measured, route, exact, and shared design search for PACT rows; the PACT search is charged once per design, not once for each candidate. Source preparation/ATPG are shared and reported separately. Peak RSS is the maximum process, not summed simultaneous memory. Per-stage CPU/wall/RSS receipts remain authoritative.

Optional discovery outcomes:

- https://github.com/Rueilian/ScanForge: NOT_COMPARABLE. The documented active problem changes the scanned FF population through partial-scan exclusion and sequential ATPG. The full-scan analysis reports current-order activity rather than a comparable full-scan ordering optimizer.
- https://github.com/anadipandey/togglestimate: NOT_ADMITTED_SOURCE_AND_BACKEND_CONTRACT. Documented primitive-Verilog parser, exhaustive Boolean truth-table enumeration, and single-chain activity-parameter sort. No qualified Nangate full-scan K=2 adapter is available; the source has no explicit license. A faithful port would need separate admission work.
- https://cse.iitkgp.ac.in/~anshumant/reports/testing.pdf: NOT_ADMITTED_SOURCE_NOT_LOCATED. The author report describes a simulated-annealing scan-order method and lists C source filenames, but no source repository or runnable source bundle was found in this bounded search.
- https://www.princeton.edu/~carch/sinha/Report_Manual.pdf: NOT_ADMITTED_SOURCE_NOT_LOCATED. A design report was located; a licensed executable source repository and qualified common-backend adapter were not established.

## K. Pareto

Dominance uses routed scan WL, E, H4, H8 with relative 1e-10 equality and at least one strict improvement. Timing, DRC, topology, preserved workload and exact replay remain hard qualification gates.

| Method | Pareto state | Dominated by | Dominates |
|---|---|---|---|
| B0 | NONDOMINATED |  |  |
| B1 | NONDOMINATED |  |  |
| B2 | NONDOMINATED |  |  |
| B3T | NONDOMINATED |  |  |
| B4 | NONDOMINATED |  |  |
| B5 | NONDOMINATED |  |  |
| CS_C1 | NONDOMINATED |  |  |
| CS_C2 | NONDOMINATED |  |  |
| CS_C3 | NONDOMINATED |  |  |

Measured baseline contrasts (destination relative to source):

| Source → destination | ΔScan WL % | ΔE % | ΔH4 % | ΔH8 % |
|---|---:|---:|---:|---:|
| B0 → B1 | -4.649 | 6.608 | -10.296 | -2.383 |
| B0 → B2 | -8.516 | 5.640 | -4.251 | -4.280 |
| B0 → B3T | -7.604 | 17.753 | -11.077 | -8.388 |
| B0 → B4 | 64.680 | -6.445 | -16.558 | -7.620 |
| B0 → B5 | 4.656 | -15.411 | -11.064 | -4.812 |
| B3T → CS_C1 | 0.335 | -11.423 | 10.495 | 2.726 |
| B4 → CS_C1 | -43.706 | 11.487 | 17.754 | 1.872 |
| B5 → CS_C1 | -11.418 | 23.305 | 10.479 | -1.134 |

These contrasts quantify physical-only ordering, the activity-only heuristic, the simple hybrid, and the preselected primary PACT result. A negative activity delta with positive wire delta is a trade-off. The four-objective dominance audit above determines superiority; these columns do not establish a causal mechanism.


## L. Generalization

Established: these fully qualified measurements on this unseen design. Observed: the recorded primary seed and Nangate45 behavior. Hypothesis: any explanation of proxy-to-final differences needs a later study. Not established: universal superiority, power reduction, guaranteed routed cost, arbitrary scaling, or four independent families from the composed cohort.

## M. Limitations

One primary seed, one technology and finite registered budgets. b14/b15 are the two base families; b17 derives from b15 and b18 combines b14/b17. Composition tests size scaling rather than independent-family replication. The activity model is zero-delay settled switching and capacitance proxies; it excludes glitches and coupling from the primary metric. The search uses a depth-3 stateful approximation and scan HPWL constraints, not a routed-wire guarantee. B6 search was bounded, and no claim is made that no other open implementation exists.

## N. Next scientific step

Continue fixed cohort in preregistered order if capacity/runtime admission permits

The campaign-level recommendation and GitHub merge provenance will be recorded only after all admitted cohort outcomes are terminal.

```json
{
  "GATE09_STATUS": "PACT_GATE09_MIXED_GENERALIZATION",
  "PACT_FROZEN": true,
  "PACT_SHA": "71b059d9d1a00735d79b6a428693eaba549a5f33",
  "OPENROAD_SHA": "08f67ee5ecd14db5a42be8c610bbfd1ccf079299",
  "FAN_ATPG_SHA": "4c253bfa613e5827f17c42a5fce8be7bea779e1e",
  "ORFS_SHA": "5e8b1450d19263f797a27c4f371b9dd19f32a3aa",
  "CAPACITY_GATE": "PASS_AT_EACH_HEAVY_STAGE",
  "B14_REFERENCE_STATUS": "QUALIFIED",
  "BASELINES_IMPLEMENTED": [
    "B0",
    "B1",
    "B2",
    "B3T",
    "B4",
    "B5"
  ],
  "BASELINES_QUALIFIED": [
    "B0",
    "B1",
    "B2",
    "B3T",
    "B4",
    "B5"
  ],
  "PACT_SEARCH_STATUS": "SEARCH_COMPLETE",
  "PACT_CANDIDATES_FROZEN": [
    "CS_C1",
    "CS_C2",
    "CS_C3"
  ],
  "COMMON_BACKEND_QUALIFIED": true,
  "ATPG_QUALIFIED": [
    "B0",
    "B1",
    "B2",
    "B3T",
    "B4",
    "B5",
    "CS_C1",
    "CS_C2",
    "CS_C3"
  ],
  "EXACT_ACTIVITY_QUALIFIED": [
    "B0",
    "B1",
    "B2",
    "B3T",
    "B4",
    "B5",
    "CS_C1",
    "CS_C2",
    "CS_C3"
  ],
  "COMPETITIVE_RESULTS": "PACT_ACTIVITY_MIXED",
  "PARETO_RESULTS": {
    "B0": "NONDOMINATED",
    "B1": "NONDOMINATED",
    "B2": "NONDOMINATED",
    "B3T": "NONDOMINATED",
    "B4": "NONDOMINATED",
    "B5": "NONDOMINATED",
    "CS_C1": "NONDOMINATED",
    "CS_C2": "NONDOMINATED",
    "CS_C3": "NONDOMINATED"
  },
  "PACT_DOMINATES": [],
  "PACT_DOMINATED_BY": [],
  "MUTUALLY_NONDOMINATED": [
    "B0",
    "B1",
    "B2",
    "B3T",
    "B4",
    "B5"
  ],
  "GENERALIZATION_CLASSIFICATION": "ONE_UNSEEN_BASE_FAMILY_MEASURED; no universal confirmation",
  "COMPETITIVE_CLASSIFICATION": "PACT_GATE09_MIXED_GENERALIZATION",
  "PR_NUMBER": null,
  "PR_URL": null,
  "MERGED": false,
  "MERGED_SHA": null,
  "WORKTREE_CLEAN": null,
  "SCIENTIFIC_BLOCKERS": [],
  "NEXT_ACTION": "Continue fixed cohort in preregistered order if capacity/runtime admission permits"
}
```
