# Gate 09: b14_opt open-source comparison

## A. Executive classification

PACT_GATE09_COMPETITIVE_COMPARISON_COMPLETE

Primary PACT candidate: CS_C1. Activity classification: PACT_ACTIVITY_IMPROVEMENT_ALL_COORDINATES. The complete four-objective Pareto comparison is retained below; alternative candidates do not replace the primary.

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

B4 and B5 reuse the frozen phase0c A/J50 implementations, one architecture each. Their load-PPI mismatch is a proxy and does not optimize routed exact E directly. B3T is explicitly OPENROAD_QUALIFIED_PATCHED. All methods use the same qualified FAN generic circuit/reporter repair; the earlier b14 446-pattern workload was invalidated and preserved; each design uses its corrected common workload. Minimal probes, source patches, branch SHAs and failed attempts are retained. Upstream issue creation was attempted; GitHub returned 403 “Resource not accessible by integration,” so issue drafts remain saved.

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
    111438,
    111438,
    111438,
    111438,
    111438,
    111438,
    111438,
    111438,
    111438
  ],
  "cycle_note": "Actual chain lengths determine clock count; every method uses the same parallel shift/padding policy and patterns"
}

Common mapped source, FF coordinates, positive-edge CK, SI/SO port policy, K=2, scan enable, FAN collapsed stuck-at workload, compression/X-fill policy, seed 11, two-thread OpenROAD routing, OpenRCX extraction, Nangate45 library, and one-worker CPU exact activity were held constant. Final timing is measured at the global-route stage; DRC is from detailed route. Routed scan WL is the frozen full scan-path net-length upper bound, including functional branches on shared nets.

## F. Search

Search wall 3169.545 s, CPU 3233.805 s, peak process RSS 605532 KiB, exact mutation evaluations 10512. These mutation evaluator calls are distinct from final routed netlist replays. Search estimates remain in candidate receipts.
- ε=0.02: 3008 exact mutations, termination wall_clock; 24601 attempts, 331 accepted.
- ε=0.05: 3597 exact mutations, termination wall_clock; 19651 attempts, 414 accepted.
- ε=0.1: 3907 exact mutations, termination wall_clock; 15239 attempts, 514 accepted.

## G. Physical results

All physical outcomes appear in the primary table, including unsuccessful candidates. Every PACT route corresponds to a preselected architecture; none was hidden or chosen after final measurement.

## H. ATPG

The same fixed patterns and full collapsed-fault identity/weight/status contract were preserved by serial replay and repaired FAN simulation. Coverage is the measured stuck-at percentage; the campaign does not claim complete fault coverage.

Shared ATPG generation wall 545.778 s; the authoritative execution receipt is /mnt/d/PACT_EXPERIMENTS/results/pact_gate09_open_source_20261005/repair_attempts/fan_compound_connectivity/inputs/b14_opt/atpg_generate/stdout.txt.

## I. Exact activity

E sums capacitance-weighted settled transitions over all measured data nets. H4/H8 are the maximum per-cycle source-localized capacitance-weighted bin activity on 4×4/8×8 grids. OpenRCX ground capacitance plus Liberty sink capacitance is used; coupling is retained separately and excluded. These proxies are not joules. Full functional replay and every FF-Q/cycle crosscheck must pass.

## J. Primary comparison

| Design | Method | Scan WL µm | ΔWL % | E | ΔE % | H4 | ΔH4 % | H8 | ΔH8 % | WNS ns | Hold ns | DRC | FC % | Runtime s | Status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| b14_opt | B0 | 7737.925 | 8.552 | 321614006.551 | -15.640 | 1706.705 | 3.381 | 663.024 | 4.322 | 7.619 | 0.000601 | 0.000 | 98.490 | 651.303 | QUALIFIED |
| b14_opt | B1 | 7772.815 | 9.042 | 318399272.682 | -16.483 | 1739.203 | 5.349 | 660.755 | 3.965 | 7.617 | 0.000438 | 0.000 | 98.490 | 599.961 | QUALIFIED |
| b14_opt | B2 | 7134.270 | 0.084 | 321673617.471 | -15.624 | 1766.989 | 7.032 | 709.665 | 11.661 | 7.620 | 0.000599 | 0.000 | 98.490 | 514.656 | QUALIFIED |
| b14_opt | B3T | 7128.285 | 0.000 | 381238038.670 | 0.000 | 1650.895 | 0.000 | 635.554 | 0.000 | 7.614 | 0.000424 | 0.000 | 98.490 | 563.021 | QUALIFIED |
| b14_opt | B4 | 17740.960 | 148.881 | 317798825.640 | -16.640 | 1772.478 | 7.365 | 682.424 | 7.375 | 7.618 | 0.000211 | 0.000 | 98.490 | 502.558 | QUALIFIED |
| b14_opt | B5 | 8321.800 | 16.743 | 304124378.781 | -20.227 | 1739.820 | 5.386 | 680.607 | 7.089 | 7.618 | 0.000456 | 0.000 | 98.490 | 623.359 | QUALIFIED |
| b14_opt | CS_C1 | 7131.400 | 0.044 | 379875624.242 | -0.357 | 1622.700 | -1.708 | 599.406 | -5.688 | 7.614 | 0.000759 | 0.000 | 98.490 | 3646.114 | QUALIFIED |
| b14_opt | CS_C2 | 7192.955 | 0.907 | 374669100.998 | -1.723 | 1677.879 | 1.634 | 666.372 | 4.849 | 7.621 | 0.000601 | 0.000 | 98.490 | 3664.618 | QUALIFIED |
| b14_opt | CS_C3 | 7133.060 | 0.067 | 380193530.162 | -0.274 | 1622.947 | -1.693 | 599.122 | -5.732 | 7.614 | 0.000759 | 0.000 | 98.490 | 3681.215 | QUALIFIED |

Deltas are relative to the frozen B3T reference. Runtime includes generation when measured, route, exact, and shared design search for PACT rows; the PACT search is charged once per design, not once for each candidate. Source preparation/ATPG are shared and reported separately. Peak RSS is the maximum process, not summed simultaneous memory. Per-stage CPU/wall/RSS receipts remain authoritative.

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
| B4 | DOMINATED | B5 |  |
| B5 | NONDOMINATED |  | B4 |
| CS_C1 | NONDOMINATED |  |  |
| CS_C2 | NONDOMINATED |  |  |
| CS_C3 | NONDOMINATED |  |  |

Measured baseline contrasts (destination relative to source):

| Source → destination | ΔScan WL % | ΔE % | ΔH4 % | ΔH8 % |
|---|---:|---:|---:|---:|
| B0 → B1 | 0.451 | -1.000 | 1.904 | -0.342 |
| B0 → B2 | -7.801 | 0.019 | 3.532 | 7.035 |
| B0 → B3T | -7.879 | 18.539 | -3.270 | -4.143 |
| B0 → B4 | 129.273 | -1.186 | 3.854 | 2.926 |
| B0 → B5 | 7.546 | -5.438 | 1.940 | 2.652 |
| B3T → CS_C1 | 0.044 | -0.357 | -1.708 | -5.688 |
| B4 → CS_C1 | -59.803 | 19.533 | -8.450 | -12.165 |
| B5 → CS_C1 | -14.305 | 24.908 | -6.732 | -11.931 |

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
  "GATE09_STATUS": "PACT_GATE09_COMPETITIVE_COMPARISON_COMPLETE",
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
  "COMPETITIVE_RESULTS": "PACT_ACTIVITY_IMPROVEMENT_ALL_COORDINATES",
  "PARETO_RESULTS": {
    "B0": "NONDOMINATED",
    "B1": "NONDOMINATED",
    "B2": "NONDOMINATED",
    "B3T": "NONDOMINATED",
    "B4": "DOMINATED",
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
  "COMPETITIVE_CLASSIFICATION": "PACT_GATE09_COMPETITIVE_COMPARISON_COMPLETE",
  "PR_NUMBER": null,
  "PR_URL": null,
  "MERGED": false,
  "MERGED_SHA": null,
  "WORKTREE_CLEAN": null,
  "SCIENTIFIC_BLOCKERS": [],
  "NEXT_ACTION": "Continue fixed cohort in preregistered order if capacity/runtime admission permits"
}
```
