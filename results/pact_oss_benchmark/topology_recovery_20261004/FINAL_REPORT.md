# PACT frozen Stage A: physical comparison complete

Status: `PACT_STAGE_A_PHYSICAL_RESULTS_COMPLETE` / `PACT_EXTERNAL_BENCHMARK_COMPLETE` for the requested B0/B1/exact-B2/B3T/P0 Stage-A comparison.

All 19 preselected method records qualify on Nangate45 with the unchanged common backend, ORFS revision, two-core policy, seed 11 and original FAN workload. 27 of 30 indexed architecture records have qualified physical measurements. Seven P0 selected candidates and their original balanced representatives remain frozen. No new search, parameter tuning, ATPG or P1 campaign was run.

## Cause and repairs

`Dft.cpp::RestitchChain` rewired the new head and internal SI edges, but overwrote the fixed SO endpoint annotation with the tail ITerm without reconnecting the actual endpoint load. KMeans restitching therefore lost the fixed endpoint before local search. Final reordering also left the ODB scan-list metadata stale. In s5378, the optimized 90/89-FF paths ended on n2510gat/n707gat while fixed SOs stayed on interior n2502gat/n2121gat nets.

B3S preserves the fixed endpoint variant, reconnects that endpoint to the final tail Q/SO net, and refreshes the existing dbScanList from the same final cell sequence. It rejects implicit reuse of a functional output as a movable scan output and adds a dedicated-output regression preserving every functional Q output. KMeans, NN, directed 2-Opt, direction-preserving 3-Opt, objective and parameters are unchanged. The repaired s5378 internal order exactly matches the failed B3R order.

The next independent blocker was `OpenSTA verilog/VerilogWriter.cc::writeAssigns`: renamed input ports lacked `assign internal_net = input_port`, producing disconnected exported Verilog despite connected ODB. The separately approved B3T repair emits that generic input alias; output aliases remain unchanged. A one-buffer witness fails before and passes after. This changes serialization only.

| Repair | Class | Exact commit | Patch SHA-256 |
|---|---|---|---|
| Compile receiver prerequisite | R0 | `0f8a15ca7fe14bc2445ec4db8a4df0832a136cb8` | `e6a97bf45c7b97409efbcd91d3ed2b9445cf478163e68828fd0e10d76f716960` |
| DFT endpoint/metadata (`src/dft/src/Dft.cpp`, scan_opt regression) | R1 | `03f7b75bae946796aa854c6a596bed6412e8bd63` | `d5435586586b3bb274977639d61ec427f0e56c6045b6292712450eaf642f380b` |
| OpenSTA input alias (`verilog/VerilogWriter.cc`) | R1 | `d21c1ae6f97cc2f28d7f2ba5892c24293b8d2259` | `0fbca1ce777eb3d5407d08af9bf430dbf0c25614bf3f8e3f6938d584e94cced6` |
| OpenROAD B3T submodule binding | R1 | `5c3751171685d507939ee7064a67feec786e5219` | `ef9329152295e59fc1c62945283444dd916b0d8bfbc482b1148db1f3dc9469ca` |

B3T binary SHA-256: `93124fbe0514e05268ec8ad8ac30f09d38cb80ab79e11258bb5d70a5d9db020f`. B3S immutable binary SHA-256: `c46965889e953bc99984b2ed0ca39b5522850ee61ab769ddb1dbb494d1d435e4`. OpenSTA parent: `244797f162b465751912b651d55d9854296aa745`. Direct OpenROAD parent: `03f7b75bae946796aa854c6a596bed6412e8bd63`. Source and command receipts bind the unchanged KMeans 100-iteration limit, 50 candidate neighbors, original capacity constraints and endpoint-excluding objective. The three adjacent native DFT regressions pass. Failed build/fixture attempts and earlier immutable binaries remain preserved. B3T reused the owned B3S build prefix; earlier original-path build receipts are retained alongside the immutable executable snapshots, rather than claiming that prefix still holds B3S.

The physical launch also required an R0 runtime repair: use the existing PACT virtual environment (recorded NumPy 2.5.3 and SciPy 1.18.1) and provide the optional import-time Numba 0.67.0 / llvmlite 0.49.0 dependency in an isolated D-backed directory. The old virtual environment and every frozen flow source remain unchanged; no optimizer kernel is invoked. Failure traces, wheel hashes and the successful full route-adapter import are recorded under `stage_a_runtime`.

## Native qualification

| Design | FFs | Chains | Chain lengths | SI | Internal | Fixed SO | Metadata / ODB / Verilog |
|---|---:|---:|---|---|---|---|---|
| s15850 | 534 | 2 | 267/267 | PASS | PASS | PASS | PASS |
| s5378 | 179 | 2 | 90/89 | PASS | PASS | PASS | PASS |
| s9234 | 211 | 2 | 105/106 | PASS | PASS | PASS | PASS |

Exact FF membership once, capacity, complete SI-to-SO traversal, no cycles/forks/orphans, and unchanged FF master/location/orientation/D/CK/functional Q/QN fanout and unrelated nets pass. The canonical order comes directly from the qualified native output.

## Physical results

Wire is the routed full scan-path connected-net length upper bound in µm. E is all-data capacitance-weighted transitions in millions of fF·transitions; H4/H8 are peak fF·transitions per spatial bin/cycle. P0 denotes the original balanced representative, with every other preselected P0 point retained in the CSV.

| Design | Method | Scan wire upper bound (µm) | E (million) | H4 | H8 | DRC |
|---|---|---:|---:|---:|---:|---:|
| s5378 | B0 | 5130.94 | 19.693 | 396.15 | 182.45 | 0 |
| s5378 | B1 | 5189.24 | 19.112 | 442.66 | 190.43 | 0 |
| s5378 | B2 | 4882.83 | 19.523 | 446.23 | 187.26 | 0 |
| s5378 | B3T | 5045.34 | 19.260 | 395.53 | 183.93 | 0 |
| s5378 | P0 | 5141.00 | 18.426 | 425.28 | 177.51 | 0 |
| s9234 | B0 | 13480.00 | 44.256 | 513.02 | 201.30 | 0 |
| s9234 | B1 | 10970.96 | 40.301 | 504.13 | 202.01 | 0 |
| s9234 | B2 | 10522.23 | 39.097 | 530.12 | 199.85 | 0 |
| s9234 | B3T | 10505.27 | 39.817 | 537.14 | 195.58 | 0 |
| s9234 | P0 | 10629.67 | 38.263 | 497.98 | 191.18 | 0 |
| s15850 | B0 | 35457.69 | 178.740 | 732.34 | 284.94 | 0 |
| s15850 | B1 | 24616.24 | 159.775 | 662.38 | 275.59 | 0 |
| s15850 | B2 | 23958.44 | 158.252 | 680.24 | 279.57 | 0 |
| s15850 | B3T | 24019.67 | 161.740 | 678.14 | 278.82 | 0 |
| s15850 | P0 | 24123.78 | 161.802 | 697.02 | 277.68 | 0 |

Detailed-route total wire, global-route setup/hold timing, extracted ground-plus-pin capacitance, load/unload shift activity, hotspot bin/cycle, and secondary scan-data activity are in `stage_a/implemented_metrics.csv`; all exact pairwise deltas and nondominance are retained. Timing is the frozen global-route analysis, not detailed-route signoff. Exact scan-only routed attribution is unknown where Q nets share functional fanout. Congestion/overflow remain unknown when absent from the frozen metrics. Coupling is recorded separately and excluded from the primary activity proxies.

## Upstream

- [https://github.com/mwsoli/OpenROAD/pull/2](https://github.com/mwsoli/OpenROAD/pull/2): open; merged=False; No reviews reported; No check runs reported.
- [https://github.com/The-OpenROAD-Project/OpenSTA/pull/420](https://github.com/The-OpenROAD-Project/OpenSTA/pull/420): open; merged=False; COMMENTED; No check runs reported; license/cla: pending; CI-Public/pr-merge: error.

No separate issue was opened. Benchmark execution did not wait for reviews, CI or merge. The OpenSTA contribution cherry-picks the experimental one-file repair onto the recorded current upstream base; that separate upstream checkout was not rebuilt locally, as disclosed in the PR.

No remaining implementation blocker prevents the requested Stage-A comparison. Scientific interpretation is limited to these three designs, the frozen workload and measured activity proxies.

Receipts: `ROOT_CAUSE.md`, `verilog_input_alias/ROOT_CAUSE.md`, `method_manifest.json`, both repair manifests, `stage_a/selection_receipt.json`, `stage_a/implemented_metrics.csv`, `stage_a/pairwise_comparison.csv`, `stage_a/scientific_questions.json`, and `upstream/final_status.json`. Large ODB/VCD/DEF/SPEF data and exact command logs remain hash-bound at the recorded D: paths.
