# PACT solution status

**WORKING_SOLVER** — exact incremental scan-order search, with measured tradeoffs and bounded routing.

## Real placed designs, 60-second solver budget

Seed 11, K=2, original mapped ATPG patterns. Deltas compare with the strongest existing physical start: P on s5378/s15850, T on s9234. Negative activity deltas are improvements. The default 10% scan-HPWL allowance is an explicit configurable engineering constraint, not a routed-wire guarantee.

| Design | FF / patterns | Solver s | Peak RSS MiB | Local eval/s | Scan HPWL Δ | M3 total Δ | M3 local Δ | M5 total Δ | M5 local Δ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| s5378 | 179 / 117 | 60.028 | 219.5 | 168.3 | +9.92% | -5.87% | -5.04% | -5.58% | -0.71% |
| s9234 | 211 / 156 | 60.030 | 231.1 | 109.1 | +9.83% | -3.04% | -2.39% | -2.87% | -1.51% |
| s15850 | 534 / 133 | 60.040 | 323.4 | 51.9 | +9.43% | -1.44% | -0.62% | -1.01% | -0.14% |

The full B0/P/A/J50/T/constructor and PACT objective table is in [comparison.csv](reports/working_solver/comparison.csv). These are five separate objectives; PACT does not claim one architecture dominates every baseline. J50/A retain useful lower-activity, higher-wire tradeoffs. The archive also contains a physical extreme whose local hotspots can be worse than P.

## Algorithm scaling only

Synthetic random spatial coordinates and four complete binary target loads; zero initial state and carry between patterns. These are not truncated shift prefixes and provide no evidence of physical-design superiority. Default K bounds chain length at 500; the separately named long-chain run fixes K=2.

| Case | N | K | Lmax | Solver s | Peak RSS MiB | Local eval/s | Evaluations | Δ wire | Δ M3 total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scaling_1000 | 1000 | 2 | 500 | 60.029 | 167.9 | 720.2 | 43239 | +9.98% | -15.49% |
| scaling_5000 | 5000 | 10 | 500 | 60.038 | 168.5 | 697.4 | 41873 | +9.24% | -5.68% |
| scaling_10000 | 10000 | 20 | 500 | 60.053 | 179.3 | 668.3 | 40136 | +5.24% | -2.70% |
| scaling_50000 | 50000 | 100 | 500 | 60.184 | 262.6 | 567.0 | 34128 | +3.38% | -1.14% |
| scaling_100000_k2 | 100000 | 2 | 50000 | 60.629 | 1283.2 | 4.6 | 284 | +0.01% | -0.01% |
| scaling_100000 | 100000 | 200 | 500 | 60.312 | 348.7 | 451.9 | 27260 | +0.30% | -0.12% |

Synthetic deltas compare the recommendation with its strongest physical start, not a random-order baseline. Higher throughput alone is not a quality guarantee: restarting less often changes the explored tradeoffs. RSS is absolute process peak, including interpreter, imports, JIT and input data. Solver time excludes loading/JIT/final serialization; results separately record loading, JIT warmup and command wall time after imports. Cooperative deadlines can overrun by an indivisible move, chain initialization or checkpoint. No claim of universal O(N log N) end-to-end time is made.

The fixed-two-chain 100K test exposes the remaining scaling limit: long-chain field initialization and exact peak reduction substantially reduce throughput and increase peak memory. The 1 GiB guard applies to one activity field, not the whole process; simultaneous initialization fields, FFT scratch and input data add memory. The default 200-chain case demonstrates practical bounded-chain scaling, not equivalent performance for arbitrary K or pattern counts.

## Anytime recommendation

M3 total at the last recorded checkpoint at or before each time. Local peaks may trade within their fixed ceilings; the constrained recommendation’s total is monotone.

| Design/run | 10 s | 30 s | 60 s | 300 s |
|---|---:|---:|---:|---:|
| s5378 (60s) | 12503133 | 12403068 | 12232118 | — |
| s9234 (60s) | 23602108 | 23602108 | 23214054 | — |
| s15850 (60s) | 90835246 | 90731271 | 90609572 | — |
| s15850 (300s) | 91022112 | 91022112 | 91022112 | 90151645 |

The extended s15850 run used 300.048 s, 323.3 MiB peak RSS and 16383 evaluations; final M3 total changed -1.94% versus its strongest physical start. The table follows each run independently: wall-clock restart decisions can change the search path between separate runs with the same random seed.

The 300-second extension measures convergence and is independently rescored. It is not routed; all new routed selections below come from the 60-second runs.

## Routed outcomes

At most six architectures in each final comparison: four exact-order, archive-hash-verified historical baselines, plus the new recommendation and physical extreme. Baselines are B0/P/A/J50 on s5378/s15850; s9234 substitutes T for A because T is its stronger physical start and J50 already improves on A in total activity. J50 is the strongest existing total-activity start on all three inputs. The length below is the **full scan-path-net routed upper bound**, including shared functional nets; exact isolated scan length is unavailable. Routing does not establish signoff power or IR-drop improvement.

| Design | Role | Reused | Status | DRC | Routed path-net upper bound µm | Route s |
|---|---|---|---|---:|---:|---:|
| s5378 | B0 | True | QUALIFIED | 0 | 5130.94 | — |
| s5378 | P | True | QUALIFIED | 0 | 5172.87 | — |
| s5378 | A | True | QUALIFIED | 0 | 9593.485 | — |
| s5378 | J50 | True | QUALIFIED | 0 | 5911.57 | — |
| s5378 | recommended | False | QUALIFIED | 0 | 5189.61 | 123.32 |
| s5378 | physical_extreme | False | QUALIFIED | 0 | 5149.92 | 112.97 |
| s9234 | B0 | True | QUALIFIED | 0 | 13480.005 | — |
| s9234 | P | True | QUALIFIED | 0 | 10671.18 | — |
| s9234 | T | True | QUALIFIED | 0 | 10520.985 | — |
| s9234 | J50 | True | QUALIFIED | 0 | 11490.195 | — |
| s9234 | recommended | False | QUALIFIED | 0 | 10622.83 | 150.92 |
| s9234 | physical_extreme | False | QUALIFIED | 0 | 10467.13 | 165.36 |
| s15850 | B0 | True | QUALIFIED | 0 | 35457.69 | — |
| s15850 | P | True | QUALIFIED | 0 | 24095.05 | — |
| s15850 | A | True | QUALIFIED | 0 | 51657.94 | — |
| s15850 | J50 | True | QUALIFIED | 0 | 27774.43 | — |
| s15850 | recommended | False | QUALIFIED | 0 | 24290.78 | 275.91 |
| s15850 | physical_extreme | False | QUALIFIED | 0 | 24101.495 | 243.83 |

Recommendation routed upper-bound changes: s5378 +0.32% versus P, s9234 +0.97% versus T, s15850 +0.81% versus P.

## Required engineering answers

1. **Algorithm:** spatial hierarchy and bounded greedy starts, then exact transactional swap/relocate/reversal/cross-chain segment search with a five-objective Pareto archive and constrained recommendation. No learned model or arbitrary weighted objective sum.
2. **Complexity:** geometry/neighbor preprocessing is approximately O(N log N); sparse construction is O(N log N + N b P), fixed leaf b≤32. A size-s move costs O(s) physical/load changes, O(P L s) shift deltas, and O(P L B) peak reduction. Short-chain initialization is O(P N L); long chains use tiled FFT Toeplitz products. P and L are explicit scaling dimensions.
3. **Data structures:** integer chain/position arrays, Morton order, cKDTree with ≤17 neighbors per FF, per-source functional bounding boxes/load aggregates, binary transition diagonals, one global P×L×100×2 activity field and ≤16 archived chain arrays. No N×N distance or waveform matrix.
4. **Incremental costs:** removed/inserted physical boundaries, affected outgoing SI/SO source loads, changed transition diagonals, and changed spatial weight columns. Exact local maxima are reduced from the updated field. Full architecture evaluation occurs only for starts and restarts. Activity deltas are not falsely described as O(1).
5. **Throughput:** measured local evaluations/second are in the tables. A local evaluation computes all four M3/M5 total/local endpoints. Constructor/baseline evaluations are counted separately by subtraction in result.json.
6. **Runtime:** each current design ran for the requested 60-second solver budget, with measured overrun reported. Loading, kernel warmup, command wall time after imports and process RSS are recorded per run. These are single observed engineering runs, not statistical performance estimates.
7. **More runtime:** the anytime table records measured constrained-incumbent evolution. Plateau periods remain visible; improvement is not guaranteed on every interval.
8. **Physical-only comparison:** recommendations provide activity improvements with bounded extra analytical scan wire, not universal Pareto dominance over P. Physical extremes reduce wire but may worsen hotspots. Existing A/J50 alternatives remain reported, not replaced by random baselines.
9. **Activity versus wire:** both local ceilings are inherited from the strongest physical start, and the configurable default wire allowance is 10%. The real table reports every signed tradeoff; routed wire must be judged separately.
10. **Routing:** 6 new selected routes are recorded above, with exact-order baseline reuse and structural/DRC outcomes. No exhaustive routing or historical correlation study was rerun.
11. **Bottleneck:** the measured s5378 profile shifted the main cost to exact spatial reduction and diagonal/column updates. Archive vectorization reduced admission overhead. Initial scaling exposed repeated full-field restarts (25.5/60 s at 10K) and checkpoint starvation (only 158 local evaluations at 100K). The final solver caps restart spending near 10%, uses compact indexed checkpoints/Pareto outputs, and schedules writes after completion. Initial and final runs are retained separately. Long-chain fields and peak reduction remain costs; result.json records every stage including checkpoint time.
12. **100K FF:** the scaling table records what actually ran, including K, P and L. This is an algorithm workload, not a real 100K ATPG design. Large P×L can still exceed the explicit 1 GiB field guard; exact arbitrary-pattern industrial scale needs a tiled retained field. The qualified topology adapter remains K=2; generic inputs support arbitrary K with explicit direct-SO topology. Single clock domain and fixed capacities are current constraints.
13. **Next improvement:** screen physically infeasible moves using cheap edge deltas before exact activity work, then add a tiled/block-maximum activity field so cost and memory depend on touched time/window blocks. Benchmark this against the current measured reduction bottleneck before introducing parallel workers.

## Correctness and use

The final milestone full regression passed **238 tests in 126.21 s**. The subsequent focused run passed **10 tests in 8.93 s**, adding the slow-checkpoint regression to randomized exact deltas/rollback, independent cycle replay, inherited endpoint transfer, FFT equivalence, archive bounds, input validation and deadline fallback. Exported real recommendations/physical extremes are also checked independently against the qualified load/scoring implementations; per-run independent_check.json records those outcomes.

Usage and input schema: [working_optimizer.md](docs/working_optimizer.md). Initial repository reconstruction: [current_solution.md](current_solution.md). Original uncommitted work and historical evidence were preserved. Changes were committed on the existing development branch; nothing was pushed.
