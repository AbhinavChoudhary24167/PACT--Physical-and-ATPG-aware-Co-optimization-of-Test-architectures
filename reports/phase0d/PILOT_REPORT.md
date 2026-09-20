# PACT Phase-0D Pilot Report

**Pilot status:** `PILOT_COMPLETE_NO_ROUTE_QUALIFIED`

**Phase-0C decision preserved:** `PACT_PHASE0C_LEARNING_GATE_FAIL`

**Pilot contract SHA256:** `1785bd6ca4367bb3bace9fffb7fff2ef66d03b7b9fa27b1317d157370fd7b5ad`

## Scope and provenance

The frozen pilot uses `s5378`, physical seed 11, K=2, and the qualified Phase-0C `P` architecture as its start. Phase-0C evidence was reused after hash verification; no Phase-0C ATPG, placement, architecture, or route was regenerated. The audit covers 8,050 tracked Phase-0C files and 83 upstream dependency files, with 375 qualified routes reused as existing baseline evidence.

The pilot is deliberately small: seven one-step operator checks, then four deterministic optimizers with a maximum of 16 proxy evaluations each. At most one new Phase-0D candidate is routed.

## Operator preflight

Every required operator generated a structurally legal child and reconstructed all 117 frozen ATPG targets under the fully clocked parallel-loading model.

| Operator | Delta physical proxy (um) | Delta H_eff8 | Delta shift cycles | Evaluation |
|---|---:|---:|---:|---|
| swap | 95.780 | 1.500 | 0 | EXECUTED_NEW |
| two_opt | 4.460 | 2.000 | 0 | EXECUTED_NEW |
| block_relocation | 89.840 | 1.000 | 0 | EXECUTED_NEW |
| cross_chain_move | 54.340 | 2.167 | 0 | EXECUTED_NEW |
| cross_chain_swap | 145.160 | 1.500 | 0 | EXECUTED_NEW |
| endpoint_reassignment | 186.340 | 0.000 | 0 | EXECUTED_NEW |
| cross_chain_block_move | 55.320 | 1.667 | 0 | EXECUTED_NEW |

The complete analytical pre-legality neighborhood sizes are recorded in `artifacts/derived/phase0d/pilot/s5378/s11/k2/operator_screen.json`; only bounded deterministic samples were evaluated.

## Equal-budget search

| Optimizer | Proxy evaluations | Accepted moves | Unique Pareto solutions | Final normalized HV | Wall seconds | Stop |
|---|---:|---:|---:|---:|---:|---|
| greedy_best_improvement | 8 | 0 | 1 | 0.704348 | 20.563 | PARETO_PLATEAU |
| greedy_first_improvement | 8 | 0 | 1 | 0.704348 | 0.281 | PARETO_PLATEAU |
| beam_search | 8 | 0 | 1 | 0.704348 | 0.281 | PARETO_PLATEAU |
| simulated_annealing | 8 | 6 | 1 | 0.704348 | 11.141 | PARETO_PLATEAU |

The hypervolume bounds were frozen from the six qualified Phase-0C K=2 portfolio rows before any Phase-0D child was evaluated: ideal=[1380.8300000000002, 60.5, 10530.0], reference=[10426.805, 70.08333333333331, 11583.0]. These are pilot bounds, not a claim of global optimality.

## Selective physical evaluation

No searched child was nondominated against the qualified Phase-0C `P` start, so the frozen proxy-to-route filter selected no new route. This is a valid negative pilot result; routing a dominated child solely to consume the budget would violate the contract.

- New-route status: `NOT_RUN_NO_PROXY_NONDOMINATED_CANDIDATE`
- New route wall time: `None` seconds
- Compressed routed ODB storage: `None` bytes
- HPWL remains a port-aware FF-origin proxy and is not called routed scan wirelength.

## Runtime and storage projection

- Bounded candidate-generation sample: 128 operations in 0.928638 seconds (0.007254982 seconds/operation)
- New unique pilot proxy artifacts: 22
- Median new proxy evaluation time: 1.397695 seconds
- Measured unique proxy compute time: 40.187 seconds
- Report/finalization invocation time: 0.172 seconds
- Phase-0D derived pilot storage: 1395827 bytes
- Historical successful Phase-0C route samples: 375
- Historical median successful route time: 109.18433516299996 seconds
- Historical median compressed ODB: 738859.0 bytes
- Full matrix proxy evaluations at B=128: 30720
- Full matrix new routes at R=8: 1920
- Projected serial proxy time: 42937.193 seconds
- Projected serial route time from recorded historical median: 209633.924 seconds
- Projected serial total: 252571.117 seconds
- Projected new compressed-route storage: 1418609280.0 bytes
- Runtime policy: `VERY_LONG_REDUCE_AND_STAGE`

The naive full 60-context x four-optimizer x maximum-budget matrix is therefore not launched. It is a several-hour campaign even before scheduling overhead. The scientifically appropriate next stage is a reduced proxy qualification across all three designs and a predeclared seed/K subset, followed by selective routing only for methods/operators that show replicated proxy benefit.

## Resource reuse accounting

- Frozen tracked Phase-0C evidence files hash-verified: 8,050
- Upstream Phase-0C dependency files hash-verified: 83
- Existing qualified Phase-0C routes reused: 375
- New Phase-0D proxy artifacts executed: 22
- Logical search/preflight proxy evaluations: 39
- Proxy evaluations reused from valid candidate cache: 17
- New Phase-0D physical routes: 0
- Avoided Phase-0C route re-executions: 375
- New-route wall time: None seconds
- Directly recorded Phase-0C route compute reused rather than repeated: 45440.295 seconds

## Failures and limitations

This is one ISCAS89-scale context, not a cross-seed or cross-design result. H_eff is a dimensionless proxy; shift-mode power and test-mode IR drop remain unavailable. A completed pilot does not evaluate D4-D6 and cannot establish either Phase-0D final decision. No ML model was trained.
