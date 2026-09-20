# PACT Phase-0D method

Phase-0D is a quality-versus-compute study. It does not train or evaluate a learned model. Its question is whether richer legal scan transformations expose useful multi-objective solutions that bounded deterministic methods fail to find efficiently.

## Evidence dependency map

```text
frozen Phase-0C placements, ATPG patterns, identity maps, routes
             |                                  |
             | reused and hash-verified         | never regenerated
             v                                  v
   Phase-0C portfolio                    richer intervention
             |                                  |
             +------------------+---------------+
                                v
                 structural and ATPG proof
                                |
                                v
                      analytical proxies
                                |
                                v
                       Pareto filtering
                                |
                                v
                 selective NEW physical routes
```

Existing Phase-0C routes are reference evidence and are counted separately from new Phase-0D routes. A cache hit is recorded as `REUSED_VERIFIED` or `SKIPPED_EXISTING`; it is never presented as a newly executed route.

## Evaluation funnel

Level 0 checks the FF bijection, chain and endpoint legality, fixed K, balance constraint, architecture hash, and exact frozen-pattern parallel loading. Invalid children do not enter quality statistics.

Level 1 computes the existing port-aware FF-origin scan HPWL proxy, exact no-capture logical shift activity, H_eff on the frozen 8/16/32 grids, peak simultaneous toggles, exact shift clocks, chain imbalance, and endpoint contribution.

Level 2 maintains a nondominated archive in the three primary minimization objectives. Hypervolume is computed only after bounds are frozen from information available before the evaluated trajectory.

Level 3 routes only a small proxy-nondominated shortlist. Physical qualification retains zero-DRC, full-netlist detailed-route wirelength, via count, timing, initial global-route use/overflow, runtime, storage, structural proof, commands, logs, hashes, and provenance. HPWL remains explicitly a proxy.

## Pilot and freeze order

The pilot contract is frozen before the pilot. It uses one qualified context (`s5378`, physical seed 11, K=2), tiny equal proxy budgets, and at most one new route. The pilot measures operator validity and timing, proxy timing, route timing if the toolchain is available, and projected storage/runtime. Exact final D1-D9 thresholds and normalization bounds are frozen only after this pilot and before any final campaign data are inspected.

The full campaign is not launched by the pilot runner. A projected duration above 45 minutes requires a checkpointed background runner; a several-hour projection requires a reduced staged experiment first.
