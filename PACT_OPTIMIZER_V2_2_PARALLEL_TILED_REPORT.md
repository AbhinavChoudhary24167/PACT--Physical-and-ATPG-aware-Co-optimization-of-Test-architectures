# PACT Optimizer-v2.2 Parallel + Tiled Exact Execution Report

## Classification

**PACT_V2_2_PARALLEL_TILED_ADVANCE**

The exact objective semantics, search operators, structural constraints,
archive rules, and evaluation budgets are unchanged. The tiled backend passes
the full 146-test repository suite and produces the same objective fronts,
architecture hashes, archive membership, dominance relations, and stopping
reasons as the frozen retained v2.1 backend for the controlled synthetic and
real-design comparisons.

The classification rests on two material results. First, persistent exact
activity state changes from `(K+1) * P * Lmax * 64 * 8` bytes to
`P * Lmax * 64 * 8` bytes, with no retained per-chain activity fields. At
N=10,000, P=4, K=20 this reduces current H_eff8 state from 21,504,000 bytes to
1,024,000 bytes (95.24%) and total optimizer traced peak from 55,471,492 to
24,602,818 bytes (55.65%). Second, realistic high-P cases benefit materially:
at N=5,000, P=256, B=16, full exact evaluation falls from tiled W1 11.999 s to
W4 3.576 s (3.36x) and W8 2.610 s (4.60x). The old backend was not launched at
that point because its predicted 687.5 MiB persistent state exceeded the hard
512 MiB guard.

## Frozen v2.1 baseline and environment

The pre-edit state was commit
`088dcbb1099788287ccec7dcd664da516bac8ad1`. It was already the uncommitted
v2.1 worktree: two tracked files modified and the v2.1 implementation, tests,
report, and evidence untracked. This state is recorded exactly in
`reports/optimizer_v2_2/baseline_freeze.json`; all historical v2/v2.1 evidence
was preserved.

- CPU: AMD Ryzen 7 7735HS, 8 physical / 16 logical cores.
- Python 3.12.5; NumPy 2.1.3; SciPy 1.15.2.
- OpenBLAS 0.3.27, pthreads, initial 16 threads. Tiled measurements pin BLAS to
  one inner thread, so outer-worker count is the intended CPU budget.
- Pre-edit v2 + v2.1 suite: 10/10 passed. Final full suite: 146/146 passed.

Fresh deterministic P=4 retained-v2.1 baselines and the matched tiled runs are
in `reports/optimizer_v2_2/baseline_results.json`. They include constructor,
exact-evaluator and total times, exact objective values, architecture hashes,
state bytes, traced peak, counters, archive, and stopping reason.

| N | Old total (s) | New total (s) | Old exact (s) | New exact (s) | Old/new state (MiB) | Old/new peak (MiB) | Equivalent |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| 1,000 | 7.215 | 9.415 | 0.390 | 1.203 | 2.930 / 0.977 | 13.119 / 9.092 | yes |
| 5,000 | 44.447 | 45.063 | 1.389 | 2.540 | 10.742 / 0.977 | 28.603 / 13.329 | yes |
| 10,000 | 82.091 | 83.708 | 2.402 | 3.827 | 20.508 / 0.977 | 52.902 / 23.463 | yes |

P=4 is below the tiling/parallel crossover, so v2.2 does not claim a runtime
gain there. It does deliver the state and whole-run peak-memory reductions.

## Constructor concurrency

The physical anchor and unchanged shared-frontier branch can run concurrently.
The implementation provides sequential, one-thread, and one-process modes. It
collects the anchor result before deterministic portfolio assembly; no worker
touches shared mutable architecture state. Every measured mode produced the
same five architecture digests.

| N | Sequential (s) | Thread (s) | Thread speedup | Process (s) | Process speedup | Serialized process input | Main traced peak seq/process |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 | 3.154 | 4.084 | 0.77x | 3.741 | 0.84x | 0.25 MiB | 1.28 / 1.44 MiB |
| 5,000 | 24.978 | 24.594 | 1.02x | 21.612 | 1.16x | 1.27 MiB | 9.54 / 10.41 MiB |
| 10,000 | 54.036 | 49.296 | 1.10x | 42.221 | 1.28x | 2.54 MiB | 19.01 / 21.24 MiB |

The process child is not visible to main-process `tracemalloc`; the table does
not mislabel that number as whole-process-tree memory. Process execution is an
opt-in high-N path and sequential remains the safe default because both forms
lose at N=1,000 and Windows process spawning requires an import-safe caller.

## Frontier vectorization experiment

Candidate IDs, lane IDs, chain IDs, predecessors, successors, coordinates,
physical deltas, activity deltas, and scalar scores were implemented as a
compact batch/structure-of-arrays experiment. Unique physical cache misses use
a NumPy geometry kernel, while the exact Python-integer activity relation and
ordered cache accounting are preserved. At N=1,000 it produced identical
portfolio hashes but changed 0.523 s scalar time to 0.678 s, a 29.8% slowdown.
The frontier bound yields batches of only about ten records, too small to repay
array setup, so scalar record construction remains the default.

## Exact global-only tiled backend

V2.2 stores only the exact summed field `E(pattern, cycle, bin)`. For an
affected chain it reconstructs the old and new order fields exactly and uses
`E' = E + sum(Bnew - Bold)`. Candidate evaluation is read-only. If accepted,
the same bounded tiles are recomputed and committed in fixed tile order; a
rejected candidate allocates no persistent replacement state. An Lmax change
uses the existing full-fallback semantics through the tiled full evaluator.

Tiles are contiguous deterministic pattern ranges. A tile's first initial
state is obtained from the preceding pattern target (or zero for pattern zero),
which makes tiles independent without changing carry-loaded/no-capture shift
semantics. At most W tiles are submitted at once and reductions are yielded in
tile-index order, preventing completion order from affecting floating-point
addition, search choice, archive insertion, tie breaking, or RNG consumption.

For N=1,000, P=128, W1 full times for B=4/8/16/32 were
1.005/1.519/1.480/1.398 s. B=4 is best for a single worker. With W8 the times
were 0.546/0.499/0.494/0.563 s; B=16 was narrowly best but its traced peak was
161.6 MiB. B=16 is used for the high-P scaling table to expose parallel
throughput; B=4 is the lower-memory single-worker choice.

## Synthetic N x P scaling

Times are one exact full evaluation in seconds. S and E are speedup over tiled
W1 and parallel efficiency `S/W`. B=16, inner BLAS threads=1. Incremental
latencies, eval/s, CPU-core utilization, traced peaks, exact values, and hashes
are in `scaling_results.json` and `scaling_summary.csv`.

| N | P | K | Lmax | Old | W1 | W2 (S/E) | W4 (S/E) | W8 (S/E) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 | 4 | 2 | 500 | 0.072 | 0.051 | 0.055 (0.92/0.46) | 0.057 (0.88/0.22) | 0.058 (0.87/0.11) |
| 1,000 | 32 | 2 | 500 | 0.241 | 0.401 | 0.257 (1.56/0.78) | 0.252 (1.59/0.40) | 0.248 (1.62/0.20) |
| 1,000 | 128 | 2 | 500 | 1.360 | 1.432 | 0.786 (1.82/0.91) | 0.543 (2.64/0.66) | 0.405 (3.53/0.44) |
| 1,000 | 256 | 2 | 500 | 2.424 | 2.810 | 1.546 (1.82/0.91) | 1.003 (2.80/0.70) | 0.778 (3.61/0.45) |
| 5,000 | 4 | 10 | 500 | 0.213 | 0.228 | 0.241 (0.95/0.47) | 0.256 (0.89/0.22) | 0.225 (1.01/0.13) |
| 5,000 | 32 | 10 | 500 | 1.461 | 1.604 | 0.938 (1.71/0.85) | 0.900 (1.78/0.45) | 0.945 (1.70/0.21) |
| 5,000 | 128 | 10 | 500 | 6.056 | 5.744 | 3.631 (1.58/0.79) | 2.311 (2.49/0.62) | 1.738 (3.31/0.41) |
| 5,000 | 256 | 10 | 500 | cap | 11.999 | 7.198 (1.67/0.83) | 3.576 (3.36/0.84) | 2.610 (4.60/0.57) |
| 10,000 | 4 | 20 | 500 | 0.268 | 0.274 | 0.270 (1.01/0.51) | 0.269 (1.02/0.25) | 0.266 (1.03/0.13) |
| 10,000 | 32 | 20 | 500 | 1.916 | 1.965 | 1.177 (1.67/0.84) | 1.139 (1.72/0.43) | 1.133 (1.73/0.22) |
| 10,000 | 128 | 20 | 500 | cap | 7.601 | 4.617 (1.65/0.82) | 3.041 (2.50/0.62) | 2.419 (3.14/0.39) |
| 10,000 | 256 | 20 | 500 | cap | 15.266 | 9.174 (1.66/0.83) | 6.151 (2.48/0.62) | 5.076 (3.01/0.38) |

The old N=5,000/P=256, N=10,000/P=128, and N=10,000/P=256 points were skipped
by the hard 512 MiB persistent-state guard; their predicted old states are
687.5, 656.25, and 1,312.5 MiB. New persistent states are 62.5 MiB at P=256
and 31.25 MiB at P=128, independent of K. This is the claimed change from
`O((K+1)PL64)` to `O(PL64)` plus bounded worker tiles.

Parallel efficiency collapses for low P: W8 efficiency is 11-22% at P=4/32.
Even at high P, W8 efficiency is 38-57%; W4 is often the better throughput/
memory compromise. For N=5,000/P=256, doubling W4 to W8 gives only another
1.37x while increasing traced backend peak from the W4 level to 193.3 MiB.

## Real benchmark equivalence

Both designs use their real qualified pattern sets, no routing.

| Design | N/P/K/Lmax | Old/new total (s) | Old/new exact (s) | Old/new state (MiB) | Old/new peak (MiB) | Front/hash/objectives | Stop |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| s5378 | 179/117/2/90 | 2.242 / 3.765 | 1.518 / 2.651 | 15.425 / 5.142 | 31.314 / 19.436 | identical | identical |
| s9234 | 211/156/2/106 | 4.754 / 4.581 | 3.310 / 3.252 | 24.222 / 8.074 | 48.835 / 27.637 | identical | identical |

s5378 is below the useful crossover. s9234 shows a small 1.04x total benefit.
The exact archive rows and hashes are stored in `real_benchmark.json`.

## Correctness and exactness coverage

`tests/unit/test_optimizer_v2_2.py` covers authoritative full equivalence;
incremental old/new reconstruction without persistent chain fields; randomized
chain moves; Lmax fallback; non-divisible pattern counts; B=4/8/16/32; W=1/2/4;
identical optimizer objectives, fronts, hashes and stop reason across workers;
rejection rollback; and read-only parallel candidate evaluation. The full
repository suite passes 146/146. There are no dense N-by-N structures.

## Newly measured dominant bottleneck

On the largest profiled useful case (N=5,000, P=128, B=16, W=4), the largest
named numerical kernel is the spatial convolution/correlation inside each
chain tile: `scipy.ndimage.convolve` accounts for 3.238 s cumulative worker
time (`_nd_image.correlate` 2.337 s cumulative) in a 4.002 s profiled wall run.
Toeplitz construction is next at 1.826 s cumulative. **The one reported next
bottleneck is tiled spatial convolution/correlation.** No follow-on
optimization is implemented here.

## Evidence

- `reports/optimizer_v2_2/baseline_freeze.json`
- `reports/optimizer_v2_2/environment.json`
- `reports/optimizer_v2_2/baseline_results.json`
- `reports/optimizer_v2_2/constructor_results.json`
- `reports/optimizer_v2_2/tile_sweep.json`
- `reports/optimizer_v2_2/scaling_results.json`
- `reports/optimizer_v2_2/scaling_summary.csv`
- `reports/optimizer_v2_2/real_benchmark.json`
- `reports/optimizer_v2_2/profile_top.txt`

No commit was created. The worktree remains intentionally dirty because the
incoming v2.1 work was already uncommitted and v2.2 is layered on top without
rewriting or deleting any historical artifact.
