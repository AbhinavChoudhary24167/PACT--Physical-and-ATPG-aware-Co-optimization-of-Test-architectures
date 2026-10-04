# Baselines and benchmarks

Definitions derive from source audit and final method/completion manifests. Generation tools and common implementation backend are separate identities. Stage A fixes K=2, placement/endpoints, Nangate45, seed 11, two route cores and original FAN workload.

| Method | Exact definition / source | Modifications |
|---|---|---|
| B0 | Seed-11 K=2 contiguous supplied-order reference, not original K=1 physical chain | PACT canonical representation/qualification |
| B1 | OpenROAD `08f67ee5ecd14db5a42be8c610bbfd1ccf079299`: clock-domain buckets and per-chain nearest-neighbor FF-origin order; `execute_dft_plan`, no `scan_opt` | Endpoint naming/extraction adapter |
| B2 | donn/difetto-ord `6fff875551fe13a2aae3a22f871a6ca7f8d5c1cf`, PR #10176: nearest-neighbor then endpoint-inclusive symmetric FF-origin Manhattan 2-Opt, limit 30 iterations | Exact algorithm; environment prerequisites repaired |
| B3 | mwsoli/OpenROAD `746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656`, PR #10666: capacity/clock-aware farthest-point KMeans, NN, asymmetric scan-pin 2-Opt and direction-preserving 3-Opt | Original build failed; not silently qualified |
| B3R/B3S/B3T | Successive compile-receiver, endpoint/metadata and Verilog-alias repairs; qualified B3T OpenROAD `5c3751171685d507939ee7064a67feec786e5219` | Explicit local compatibility/correctness repairs, not unmodified upstream |
| P0 | Candidate-stateful depth-3 PACT `9d9103027918b1d4af2b209e6d36133ad82d4a4e`; frozen archive/budgets, predicted physical/H8 extrema and balanced minimax-regret selection | PACT-specific model/search/integration |

B3 retains KMeans limit 100, 50 candidate neighbors (100 overquery), original capacities and strict local improvement. Its directed internal pin-distance objective excludes external SI/SO costs.

Repairs: compile receiver `0f8a15ca7fe14bc2445ec4db8a4df0832a136cb8`; DFT endpoints/metadata `03f7b75bae946796aa854c6a596bed6412e8bd63`; OpenSTA alias `d21c1ae6f97cc2f28d7f2ba5892c24293b8d2259` on parent `244797f162b465751912b651d55d9854296aa745`; OpenROAD submodule binding `5c3751171685d507939ee7064a67feec786e5219`. Retained repair manifests and patches bind exact bytes. Contributions were recorded at [receiver PR](https://github.com/mwsoli/OpenROAD/pull/1), [topology PR](https://github.com/mwsoli/OpenROAD/pull/2) and [alias PR](https://github.com/The-OpenROAD-Project/OpenSTA/pull/420); present merge status is not asserted.

Qualification checks capacities/FFs, fixed endpoints, complete traversal, canonical order versus ODB metadata/exported Verilog, unchanged functional connectivity, workload/FF replay, DRC and available timing. Failed/unmeasured outcomes remain explicit in the final CSV export.

Provenance is in `benchmarks/manifests/` and the retained benchmark manifest. Additional ISCAS89 redistribution rights were not independently established in the saved audit; additional designs were not admitted. PACT's MIT license does not grant new rights to external assets.
