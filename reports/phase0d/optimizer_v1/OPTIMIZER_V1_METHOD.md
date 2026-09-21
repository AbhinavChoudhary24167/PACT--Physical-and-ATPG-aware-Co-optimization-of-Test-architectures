# PACT Optimizer v1 Method

## Fixed context and objectives

The frozen development context is `s5378 / seed11 / K2`. All six qualified
Phase-0C proxy rows were discovered from the context directory and reused by
verified architecture/input hashes. Placement, ATPG patterns, FF identity, K,
and SI/SO identities remain fixed.

For fixed K the primary minimization archive is exactly:

1. the qualified port-aware FF-origin scan HPWL proxy; and
2. exact H_eff8 from the existing no-capture, fully clocked parallel-shift model.

Exact H_eff16/H_eff32, total and peak toggles, chain imbalance, and shift cycles
are reported only. Equal final capacities keep exact shift cycles constant.

## Construction and activity relation

Five chains-from-scratch starts use physical weights 1.0, 0.8, 0.5, 0.2, and
0.0. Endpoint-aware Manhattan insertion uses the identical additive terms as
the Phase-0C proxy. The balanced 0.5 start uses regret insertion; the others use
cheapest insertion. Every final candidate receives exact structural and ATPG
reconstruction proof before metric evaluation.

H_eff8 is a maximum over cycle-aligned, spatially convolved,
direct-sink-weighted toggle fields, so it is not an independent pairwise-edge
sum. Construction therefore uses a labeled heuristic: for directed adjacency
`i -> j`, static target compatibility is the fraction of frozen ATPG targets
where bits i and j differ, multiplied by j's direct-sink weight normalized by
the mean weight. This score is never reported as H_eff8. Final candidates are
always evaluated by exact H_eff8. On the evaluated LNS sample, heuristic delta
versus exact H_eff8 delta has Pearson r=0.2338014779665888 over
19 points; this is validation evidence, not an
identity claim.

## Large-neighborhood refinement

Deterministic LNS removes 5%, 10%, or 20% of FFs using spatial-region,
activity-hotspot, contiguous-segment, cross-chain-segment, or seeded guided
destroy. Repair uses physical-best, activity-best, balanced, or regret
insertion while restoring exact capacities. Five weighted lanes retain moves
that dominate their current point or improve their lane-normalized scalar.
Every unique repaired architecture receives exact proxy evaluation and is
offered to the combined Phase-0C plus PACT two-objective archive.

## Exact incremental physical evaluation and complexity

The Manhattan proxy decomposes into chain-local SI/FF, FF/FF, and FF/SO edges.
Replacement delta is computed only for changed chains and is asserted against
the full qualified proxy after every new LNS evaluation (absolute tolerance
1e-6 µm). Exact H_eff is not incrementally substituted.

Construction uses no dense FF-pair matrix: relations are computed on demand.
Cheapest/regret insertion is O(N^3) worst-case time and O(N) working memory in
this v1 research implementation. Each LNS proposal removes qN FFs and repairs
in O(qN^2) worst-case time with O(N) state; exact activity evaluation retains
the existing streamed pattern/cycle implementation. The lack of a sparse
activity-neighbor index is a known scale limitation, so no 100K-FF scalability
claim is made.

## Runtime and reuse

Search uses a resumable 60-second cumulative monotonic
wall-clock budget with checkpoints at 5/10/20/30/60 seconds. Process invocation,
search wall time, accumulated new-proxy time, route time, and total campaign time
are distinct fields. No OpenROAD command runs inside construction or LNS.
