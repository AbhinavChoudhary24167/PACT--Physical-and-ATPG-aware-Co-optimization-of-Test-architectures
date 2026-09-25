# Working scan solver

Install `pip install -e '.[optimizer,dev]'`, then:

```sh
pact-optimize --design s5378 --chains 2 --time-budget 60 --output run/s5378
# From a source checkout: python scripts/pact_optimize.py with the same flags.
pact-optimize --synthetic 100000 --time-budget 60 --output run/scaling_100k
```

The repository adapter uses placed seed-11 inputs and mapped FAN ATPG patterns,
including B0, P, A, J50 and T starts. It requires the existing local evidence and
Nangate Liberty (`--liberty` can override its path). It never reads routed
metrics as optimizer inputs. Synthetic workloads use complete binary target
loads, carry between loads, and default to K=ceil(N/500), at least two chains.
They measure algorithm scaling only. `--chains 2` explicitly exercises long
chains. The repaired repository topology exporter currently supports K=2.

For other designs use `--input problem.json --chains K`. The JSON contains
`architecture` (relative path to the canonical architecture), `patterns` (list
of complete binary FF-name -> target-bit maps), and fixed die `bounds`.
Provide either `placed_graph` and `liberty` paths (the strict repaired K=2
schema), or `input_ports`, `output_ports`, and `compiled_functional_sources`:

- `pin_ff`, `wire_um`: functional source-cone pin load and net HPWL per FF;
- `si_pin_ff`: SI pin load per FF;
- `q_boxes`: [xmin,ymin,xmax,ymax] of each Q net's fixed functional point set.

All arrays follow the architecture's cell-array order. The generic adapter uses
direct scan-output ports; inherited buffered outputs must use the repaired
graph adapter. It does not silently infer missing physical information.
Inputs currently require a single clock domain and fixed nonempty chain
capacities. Equal-length cross-chain moves preserve those capacities and test
cycles; arbitrary unbalanced migration is not implemented.

## Algorithm and costs

Morton spatial hierarchy plus bounded 32-FF greedy leaves constructs physical
and hybrid starts. A packed-target signature sort gives an activity-only start.
cKDTree neighbor lists contain at most 17 FFs per cell. Search applies swaps,
cross-chain swaps, bounded relocation/reversal and equal-length segment/tail
exchange. Each move is a small position transaction, with exact inverse rollback.

The retained objectives are port-aware scan Manhattan HPWL, M3 total/local and
M5 total/local. M3/M5 weights reproduce `phase2cr_loads`: functional plus scan
pin/HPWL loads, CAP_PER_UM=0.103981, and complete inherited SO branch ownership.
Activity uses zero initial state, carried loaded state, no capture/final unload,
fixed 10×10 bins and the peak of all 81 contained 2×2 windows.

An exact shift field is a Toeplitz product: toggle(t,j)=d[t-j+m-1]. A swap
changes only a few target-transition diagonals and spatial weight columns.
The solver updates these terms, not all FF waveforms. Physical edges and source
loads are O(s) for s changed positions. Activity updates are O(P L s), plus
O(P L B) exact spatial reduction. They are **not O(1)**. B=100, P is the number
of patterns, L is maximum chain length. Short-chain initial scoring costs
O(P N L); chains longer than 1024 use tiled FFT products, approximately
O(P B sum_k L log L). No N×N matrix is built. Memory is
O(P N + P L B + N q + A N), with fixed neighbor q and archive bound A.
The exact field has a 1 GiB allocation guard; larger P×L needs a tiled field
backend. Input and compiled-topology memory are additional.

No weighted sum controls objective admission. A bounded five-objective Pareto
archive uses crowding distance; search rotates lexicographic preferences with
an explicit wire constraint. The default recommendation minimizes M3 total at
no more than `--wire-allowance` (default 0.10) extra scan HPWL versus the best
physical start, and does not worsen either local peak. This is a user-visible
engineering allowance, not a guarantee about routed wire or power. Its incumbent
is preserved separately from archive diversity pruning. All tradeoffs remain in
the returned archive. This is a heuristic, not a global optimality claim.

## Time and outputs

`--time-budget` covers optimizer preprocessing, construction, initial scoring,
search and checkpoints. Input loading, Numba compilation/warmup, and final JSON
serialization are reported separately. Checks occur between constructors'
bounded leaves, chain evaluations, FFT tiles and complete transactional moves.
One operation/checkpoint can overrun the deadline; the actual overrun is emitted.
A tiny budget returns the supplied legal architecture with unscored status.

`optimized.architecture.json`, canonical Pareto architectures, `result.json`,
`convergence.json` and atomic `checkpoint.json` are written. Checkpoints contain
complete indexed best-known chain lists, mapped by `ff_names.json`, while the
solver runs. Above 10K FF, Pareto outputs use the same compact indexed format
and reference shared cells in `supplied.architecture.json`; the recommended
`optimized.architecture.json` remains fully canonical. Results report qualified
costs, evaluations, accepted moves, per-stage time, retained-array bytes and
absolute process peak RSS (including Python/Numba imports). `--profile` writes
human-readable and cProfile data. A full field rebuild occurs only at construction
or archive restart, not each local proposal. Selected architectures are compatible
with the existing rewire/route tools.

Measured restart work is limited to approximately 10% of elapsed solver time
(one restart may exceed the estimate). Objective preferences still rotate when
a restart is skipped. Checkpoint intervals start after each write completes;
their measured duration also imposes a duty-cycle limit to prevent I/O starvation.

## Bounded routing

`python scripts/pact_solver_routes.py --design s5378 --run run/s5378 --output run/routes/s5378`
reuses hash-verified B0/P/A route archives and routes at most two new orders:
the recommendation and physical extreme. Each gets one bounded rewire, route,
and postroute structural check. Thus at most five distinct architectures/design
are compared. Route and optimizer output directories are separate. No route
is launched inside optimization. Historical experiments are not modified.
