# Gate 09: frozen PACT unseen-design and open-source comparison

## A. Executive classification

PACT_GATE09_MIXED_GENERALIZATION

Generalization: PACT_GATE09_INCONCLUSIVE_RESOURCE_OR_ADMISSION_LIMITED. The primary balanced candidate is preserved for every design; alternatives remain separate. Admission and resource holds are reported without treating unexecuted designs as PACT losses.

## B. Admission

C≥6 GiB and D≥25 GiB remained fixed. Per-design D admission adds the registered 20 GiB scratch reserve plus max(5 GiB, retained packages, projected complete traces and one complete count cache). The inactive 16 GiB build image was relocated to F with copy/rehash verification and a D symlink; required evidence was preserved. A later projected-capacity hold was resolved by relocating 37 inactive build-source fixtures (1,083,340,023 bytes) to F, rehashing each copy, removing only its verified duplicate and retaining a byte-identical D-path symlink. All deletion/relocation receipts remain in the campaign. Qualified uncompressed count caches were removed only after gzip evidence and crosschecks passed. The prospective source-registration adapter binds a failed predecessor only when one exists; its first failed launch performed no scientific work. Both b15 continuations reused the admitted source; the capacity continuation also reused identical qualified patterns and placement without repeating ATPG or placement. The later cold-input directory collision stopped before any search: source preparation and prospective input had shared a directory. A qualified adapter allocates a fresh PACT_primary child and retains the original complete input validation. All six b15 baseline results and original preparation bytes were preserved; no baseline or PACT search was repeated. The failed launch, focused controls and complete production audit remain recorded separately.

| Design | Base/composition family | Source FFs | Admission/comparison outcome |
|---|---|---:|---|
| b14_opt | b14 (base family) | 245 | COMPETITIVE_COMPARISON_TERMINAL |
| b15_opt | b15 (base family) | 449 | COMPETITIVE_COMPARISON_TERMINAL |
| b17_opt | b15 (composition scaling stress) | 1414 | ATPG_OR_PLACEMENT_ADMISSION_HOLD |
| b18_opt | b14+b15 composition (composition scaling stress) | 3270 | DEFERRED_PRIOR_ADMISSION_HOLD |

Sources: cad-polito-it/I99T commit 8a2c3b500ee7ff20e7031de92592b737bedc6d8c, EUPL-1.2. BENCH/BLIF and mapped all-state next-state equivalence precede ATPG/placement/reference admission. A first source/reference/runtime/resource hold stops the fixed cohort order; deferred rows make no source-compatibility claim.

## C. Frozen methodology

K=2; primary seed 11; ε=0.02/0.05/0.10; 900 seconds per mutation loop; 7200-second search worker ceiling. 20,000 maximum evaluations, stagnation 2000, lane attempts 150, neighbors 16, segment 8, archive 16, equal normalized E/H4/H8 weights. Existing operators, archive, depth-3 stateful model, CPU evaluator and independent replay remain frozen. The budget adapter changes only the legacy seconds expression and its receipt text to the already preregistered 900 seconds. The sole initial state is the minimum-qualified-routed-WL B0/B1/B2/B3T reference, selected before search. Balanced/best E/best H4/best H8 roles, exact hash deduplication, at most three new candidates before routing. An in-flight exact mutation can finish past a loop deadline. No extra seed, weight sweep, GPU, hidden route or post-result tuning was used.

## D. Competitors

- **B0**: Supplied source scan order split contiguously into balanced K=2 capacities; common original control Parameters {"K": 2}.
- **B1**: Native placed-cell greedy nearest neighbor; Boost Geometry Cartesian nearest uses Euclidean ranking; start minimizes x+y Manhattan distance to origin; no endpoint-inclusive local refinement Source SHA 08f67ee5ecd14db5a42be8c610bbfd1ccf079299.
- **B2**: Established native FF-origin nearest neighbor followed by endpoint-inclusive symmetric Manhattan 2-opt, maximum 30 iterations Source SHA 6fff875551fe13a2aae3a22f871a6ca7f8d5c1cf.
- **B3T**: Qualified patched OpenROAD K-means partition plus directed scan-pin Manhattan nearest neighbor and strict improving 2-opt/3-opt; external endpoints excluded by optimizer and included by common qualification Source SHA 5c3751171685d507939ee7064a67feec786e5219. Parameters {"capacity": "ceil(FF/K)", "kmeans_iterations": 100, "neighbor_count": 50, "overquery": 100}.
- **B4**: Existing phase0c A: global greedy balanced chain extensions minimizing mean load-PPI bit disagreement over the identical frozen FAN patterns; activity proxy, not exact E Parameters {"K": 2, "alpha_physical": 0.0, "beta_activity": 1.0}.
- **B5**: Existing phase0c J50: global greedy balanced extensions of 0.5 normalized FF-origin Manhattan distance + 0.5 mean load-PPI disagreement Parameters {"K": 2, "alpha_physical": 0.5, "beta_activity": 0.5}.
- **B6**: NO_ADMITTED_DIRECT_COMPARATOR

B1 uses native Cartesian Euclidean nearest ranking and an x+y lower-left start. B2 uses the established endpoint-inclusive Manhattan refinement. B3T is OPENROAD_QUALIFIED_PATCHED, with its source/STA repairs, binaries, build commands and tests preserved. B4 A and B5 J50 reuse the frozen phase0c code; B5 weights are 0.5/0.5 for every design. B6 discovery preserved repository/commit/license/adapter exclusions; no additional direct competitor was admitted, and no claim is made that no other open implementation exists.

## E. Fairness

Admitted comparisons share the mapped source, FF population and placement, clocks, K, fixed endpoint policy, seed 11, scan enable, patterns, compression/X-fill policy, fault model, two-thread routing, extraction and one-worker CPU measurement. Per-design machine audits verify source/placement/identity/workload hashes and candidate selection. Timing is from global route; DRC is from detailed route. The routed scan-path net-length upper bound includes functional branches. OpenROAD common binary SHA fcd7dcfc37d329bd43a7ede75805319a2e70e6879da11d42b4fd1c2e50e645c3 and ORFS SHA 5e8b1450d19263f797a27c4f371b9dd19f32a3aa are fixed. Common backend component provenance records associated OpenSTA/OpenRCX source identities without claiming an independently reproduced binary linkage.

## F. Search

Per-design reports retain each lane, configuration, archive/discovery statistics, exact mutation counts, CPU/wall/RSS, termination reason, independent endpoint winner replay, architectures and selection receipt. Mutation evaluator metrics are separate from final routed netlist measurements. The primary is never promoted after final results.

## G. Physical

All selected architectures, routing failures, topology proofs, timing and DRC outcomes remain in the per-design receipts. The launch-path repair reused four completed b14 reference routes and added zero reference reroutes.

## H. ATPG

All methods share the qualified generic FAN repair 4c253bfa613e5827f17c42a5fce8be7bea779e1e. Compound primitive levels/arity, shared-net drivers and internal-fault identities were minimally repaired with ASAN/truth/reporter controls. The earlier b14 446-pattern workload was invalidated and preserved; the qualified workload has 453 patterns, 36,236 full weighted stuck-at targets and 35,688 detected (98.49%). Coverage is for the frozen mapped-source collapsed-fault universe; post-route inserted buffers do not create new target classes. Serial recovery and source FAN simulation preserve identities, weights and status. The initial upstream connector attempt returned GitHub 403 “Resource not accessible by integration”; its drafts and evidence remain saved. A browser submission subsequently published the construction defects as [FAN_ATPG issue #5](https://github.com/NTU-LaDS-II/FAN_ATPG/issues/5). The submitted body and visible proof are bound by publication/FAN_upstream_issue.json. The separate reporting defect is [FAN_ATPG issue #6](https://github.com/NTU-LaDS-II/FAN_ATPG/issues/6), with its own body and proof bound by publication/FAN_reporter_upstream_issue.json.

## I. Exact activity

E is capacitance-weighted settled data-net transitions, not joules. H4/H8 are the per-cycle maximum source-localized capacitance-weighted bins on 4×4/8×8 grids. OpenRCX ground plus Liberty sink pin capacitance is used; coupling is excluded from the primary proxy. Every qualified netlist replay must finish all patterns and pass every FF-Q/cycle crosscheck. The normal CPU exact ceiling is 7200 seconds; diagnostic 14400 seconds is separate and does not replace primary outcomes.

## J. Complete comparative table

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
| b15_opt | B0 | 22724.085 | 9.309 | 722000716.372 | -5.339 | 1682.491 | 4.440 | 756.854 | 4.471 | 7.503 | 0.000576 | 0.000 | 96.750 | 928.216 | QUALIFIED |
| b15_opt | B1 | 21667.565 | 4.227 | 769712632.615 | 0.916 | 1509.254 | -6.313 | 738.816 | 1.981 | 7.501 | 0.001363 | 0.000 | 96.750 | 924.003 | QUALIFIED |
| b15_opt | B2 | 20788.795 | 0.000 | 762723552.495 | 0.000 | 1610.960 | 0.000 | 724.461 | 0.000 | 7.505 | 0.000001 | 0.000 | 96.750 | 908.209 | QUALIFIED |
| b15_opt | B3T | 20996.255 | 0.998 | 850179717.043 | 11.466 | 1496.128 | -7.128 | 693.367 | -4.292 | 7.499 | 0.001171 | 0.000 | 96.750 | 931.709 | QUALIFIED |
| b15_opt | B4 | 37422.085 | 80.011 | 675469434.621 | -11.440 | 1403.901 | -12.853 | 699.184 | -3.489 | 7.502 | 0.001768 | 0.000 | 96.750 | 922.031 | QUALIFIED |
| b15_opt | B5 | 23782.035 | 14.398 | 610729605.623 | -19.928 | 1496.339 | -7.115 | 720.438 | -0.555 | 7.497 | 0.001342 | 0.000 | 96.750 | 885.223 | QUALIFIED |
| b15_opt | CS_C1 | 21066.570 | 1.336 | 753061810.773 | -1.267 | 1653.142 | 2.618 | 712.270 | -1.683 | 7.505 | 0.000626 | 0.000 | 96.750 | 4565.834 | QUALIFIED |
| b15_opt | CS_C2 | 20975.105 | 0.896 | 752304978.541 | -1.366 | 1584.504 | -1.642 | 754.535 | 4.151 | 7.504 | 0.000680 | 0.000 | 96.750 | 4534.604 | QUALIFIED |
| b15_opt | CS_C3 | 21048.475 | 1.249 | 755008752.684 | -1.011 | 1653.047 | 2.613 | 714.750 | -1.340 | 7.506 | 0.000626 | 0.000 | 96.750 | 4531.799 | QUALIFIED |
| b17_opt | B0 | — | — | — | — | — | — | — | — | — | — | — | — | — | NOT_ADMITTED |
| b17_opt | B1 | — | — | — | — | — | — | — | — | — | — | — | — | — | NOT_ADMITTED |
| b17_opt | B2 | — | — | — | — | — | — | — | — | — | — | — | — | — | NOT_ADMITTED |
| b17_opt | B3T | — | — | — | — | — | — | — | — | — | — | — | — | — | NOT_ADMITTED |
| b17_opt | B4 | — | — | — | — | — | — | — | — | — | — | — | — | — | NOT_ADMITTED |
| b17_opt | B5 | — | — | — | — | — | — | — | — | — | — | — | — | — | NOT_ADMITTED |
| b17_opt | PACT | — | — | — | — | — | — | — | — | — | — | — | — | — | NOT_ADMITTED |
| b18_opt | B0 | — | — | — | — | — | — | — | — | — | — | — | — | — | NOT_ADMITTED |
| b18_opt | B1 | — | — | — | — | — | — | — | — | — | — | — | — | — | NOT_ADMITTED |
| b18_opt | B2 | — | — | — | — | — | — | — | — | — | — | — | — | — | NOT_ADMITTED |
| b18_opt | B3T | — | — | — | — | — | — | — | — | — | — | — | — | — | NOT_ADMITTED |
| b18_opt | B4 | — | — | — | — | — | — | — | — | — | — | — | — | — | NOT_ADMITTED |
| b18_opt | B5 | — | — | — | — | — | — | — | — | — | — | — | — | — | NOT_ADMITTED |
| b18_opt | PACT | — | — | — | — | — | — | — | — | — | — | — | — | — | NOT_ADMITTED |

Deltas use each design’s frozen selected external reference. Runtime includes measured generation, route, exact, and shared design search for PACT rows. Search is charged once per design, not separately for each candidate. Shared source preparation and ATPG costs, stage CPU/RSS and machine details appear in the receipts. Display values are rounded; dominance uses full-precision JSON. No losing or held method is removed.

## K. Pareto

Four costs: routed scan WL, E, H4, H8. Relative 1e-10 equality, at least one strict reduction, with timing/DRC/topology/workload/exact replay as hard qualification gates. Primary relationships:

```json
{
  "PACT_DOMINATES": {
    "b14_opt": [],
    "b15_opt": []
  },
  "PACT_DOMINATED_BY": {
    "b14_opt": [],
    "b15_opt": []
  },
  "MUTUALLY_NONDOMINATED": {
    "b14_opt": [
      "B0",
      "B1",
      "B2",
      "B3T",
      "B4",
      "B5"
    ],
    "b15_opt": [
      "B0",
      "B1",
      "B2",
      "B3T",
      "B4",
      "B5"
    ]
  }
}
```

## L. Generalization

PACT_GATE09_INCONCLUSIVE_RESOURCE_OR_ADMISSION_LIMITED. 
Established: admitted-design measurements and qualification. Observed: the exact Pareto relationships at one seed and technology. Hypothesis: reasons for proxy/final differences need later experiments. Not established: universal superiority, power reduction, industry-tool superiority, guaranteed routed cost or arbitrary scaling. Related b17/b18 compositions are scaling checks and do not make four independent families.

## M. Limitations

Finite fixed CPU budgets, one primary seed, Nangate45, zero-delay settled activity, no glitch/power/current model, ground-plus-pin proxy excluding coupling, depth-3 search approximation, HPWL constraint without a routed-WL guarantee, bounded B6 search, and every source/reference/resource admission hold listed below.

- b17_opt: ATPG_OR_PLACEMENT_ADMISSION_HOLD. Frozen 900s ATPG / common preparation gate did not qualify
- b18_opt: DEFERRED_PRIOR_ADMISSION_HOLD. Fixed-order cohort stopped at b17_opt; no claim of source incompatibility or PACT failure
- b17_opt passed source/mapped equivalence and capacity admission, but FAN_ATPG timed out at 900.047326 seconds (frozen limit 900; termination -15). Placement, reference routing and PACT search never started. Empty buffered stdout/stderr do not establish a source defect or crash. b18_opt remained deferred under the fixed-order stop rule. No budget extension or rerun was performed.

## N. Next scientific step

Resolve the documented source/reference/runtime/resource admission hold in a separately preregistered study, then test further unseen base-family designs with the frozen method and common controls. Do not extend or rerun this primary campaign.

Per-design evidence:

- [b14_opt](/mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT/results/pact_gate09_open_source_20261005/final/b14_opt/report.md)
- [b15_opt](/mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT/results/pact_gate09_open_source_20261005/final/b15_opt/report.md)

```json
{
  "GATE09_STATUS": "PACT_GATE09_MIXED_GENERALIZATION",
  "PACT_FROZEN": true,
  "PACT_SHA": "71b059d9d1a00735d79b6a428693eaba549a5f33",
  "OPENROAD_SHA": "08f67ee5ecd14db5a42be8c610bbfd1ccf079299",
  "FAN_ATPG_SHA": "4c253bfa613e5827f17c42a5fce8be7bea779e1e",
  "ORFS_SHA": "5e8b1450d19263f797a27c4f371b9dd19f32a3aa",
  "CAPACITY_GATE": "FIXED_FLOORS_ENFORCED_AT_EVERY_HEAVY_STAGE",
  "B14_REFERENCE_STATUS": "QUALIFIED",
  "BASELINES_IMPLEMENTED": [
    "B0",
    "B1",
    "B2",
    "B3T",
    "B4",
    "B5"
  ],
  "BASELINES_QUALIFIED": {
    "b14_opt": [
      "B0",
      "B1",
      "B2",
      "B3T",
      "B4",
      "B5"
    ],
    "b15_opt": [
      "B0",
      "B1",
      "B2",
      "B3T",
      "B4",
      "B5"
    ]
  },
  "PACT_SEARCH_STATUS": {
    "b14_opt": "SEARCH_COMPLETE",
    "b15_opt": "SEARCH_COMPLETE"
  },
  "PACT_CANDIDATES_FROZEN": {
    "b14_opt": [
      "CS_C1",
      "CS_C2",
      "CS_C3"
    ],
    "b15_opt": [
      "CS_C1",
      "CS_C2",
      "CS_C3"
    ]
  },
  "COMMON_BACKEND_QUALIFIED": {
    "b14_opt": "PASS",
    "b15_opt": "PASS"
  },
  "ATPG_QUALIFIED": {
    "b14_opt": [
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
    "b15_opt": [
      "B0",
      "B1",
      "B2",
      "B3T",
      "B4",
      "B5",
      "CS_C1",
      "CS_C2",
      "CS_C3"
    ]
  },
  "EXACT_ACTIVITY_QUALIFIED": {
    "b14_opt": [
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
    "b15_opt": [
      "B0",
      "B1",
      "B2",
      "B3T",
      "B4",
      "B5",
      "CS_C1",
      "CS_C2",
      "CS_C3"
    ]
  },
  "COMPETITIVE_RESULTS": {
    "b14_opt": "PACT_ACTIVITY_IMPROVEMENT_ALL_COORDINATES",
    "b15_opt": "PACT_ACTIVITY_MIXED"
  },
  "PARETO_RESULTS": {
    "b14_opt": {
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
    "b15_opt": {
      "B0": "NONDOMINATED",
      "B1": "NONDOMINATED",
      "B2": "NONDOMINATED",
      "B3T": "NONDOMINATED",
      "B4": "NONDOMINATED",
      "B5": "NONDOMINATED",
      "CS_C1": "NONDOMINATED",
      "CS_C2": "NONDOMINATED",
      "CS_C3": "NONDOMINATED"
    }
  },
  "PACT_DOMINATES": {
    "b14_opt": [],
    "b15_opt": []
  },
  "PACT_DOMINATED_BY": {
    "b14_opt": [],
    "b15_opt": []
  },
  "MUTUALLY_NONDOMINATED": {
    "b14_opt": [
      "B0",
      "B1",
      "B2",
      "B3T",
      "B4",
      "B5"
    ],
    "b15_opt": [
      "B0",
      "B1",
      "B2",
      "B3T",
      "B4",
      "B5"
    ]
  },
  "GENERALIZATION_CLASSIFICATION": "PACT_GATE09_INCONCLUSIVE_RESOURCE_OR_ADMISSION_LIMITED",
  "COMPETITIVE_CLASSIFICATION": "PACT_GATE09_MIXED_GENERALIZATION",
  "PR_NUMBER": null,
  "PR_URL": null,
  "MERGED": false,
  "MERGED_SHA": null,
  "WORKTREE_CLEAN": null,
  "SCIENTIFIC_BLOCKERS": [
    {
      "design": "b17_opt",
      "reason": "Frozen 900s ATPG / common preparation gate did not qualify",
      "receipt": "/mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT/results/pact_gate09_open_source_20261005/repair_attempts/metadata_registration_b17_opt/workers/b17_opt/prepare.json",
      "status": "ATPG_OR_PLACEMENT_ADMISSION_HOLD"
    },
    {
      "design": "b18_opt",
      "reason": "Fixed-order cohort stopped at b17_opt; no claim of source incompatibility or PACT failure",
      "status": "DEFERRED_PRIOR_ADMISSION_HOLD"
    }
  ],
  "NEXT_ACTION": "Resolve the documented source/reference/runtime/resource admission hold in a separately preregistered study, then test further unseen base-family designs with the frozen method and common controls. Do not extend or rerun this primary campaign.",
  "publication_note": "Post-merge GitHub/branch/cleanliness provenance is recorded in a separate immutable publication receipt."
}
```
