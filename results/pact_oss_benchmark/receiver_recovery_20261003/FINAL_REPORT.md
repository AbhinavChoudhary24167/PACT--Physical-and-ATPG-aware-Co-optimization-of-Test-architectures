# Receiver-repair recovery stopped at architecture qualification

**PACT_STAGE_A_INCOMPLETE**. Scientific classification: **PACT_BENCHMARK_INCONCLUSIVE**.

The proposed method set remains B0 / B1 / exact B2 / B3R — PR #10666 + minimal compile repair / frozen P0. B3R builds and its compiled-command probe passes, but its actual s5378 output fails fixed SI/SO topology qualification. This is an additional source-behavior blocker beyond the authorized compile repair. No further source repair or endpoint adaptation is applied. s9234 and s15850 are not attempted after the stop.

## Exact repair, builds and validation

Exact B2 remains `6fff875551fe13a2aae3a22f871a6ca7f8d5c1cf`, binary SHA256 `601da32f4493cd9587b53812385af4ec9ed08f1c3f5e9def9c6a7e4897b25087`, with all three existing qualifications unchanged. Exact B3 `746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656` retains its failed build as provenance. B3R is repair commit `0f8a15ca7fe14bc2445ec4db8a4df0832a136cb8`, patch SHA256 `e6a97bf45c7b97409efbcd91d3ed2b9445cf478163e68828fd0e10d76f716960`, final binary SHA256 `65cd5dec3d12c46035ef67d0b538aa8d932754247bf3a6626094a8f1dc515da0` at `/mnt/pact-oss-recovery/B3R_openroad_10666_repaired/build/bin/openroad`. Only the two missing `db_network_->` receiver qualifications and their immediate clang-format wrapping differ. Algorithm sources, ordering rules, KMeans/NN/directed 2-Opt/3-Opt costs, parameters and intended endpoint semantics are unchanged.

Actual final CMake resolution passes: SWIG 4.3.0 `/usr/local/bin/swig`; Tcl development header 8.6.12 `/usr/include/tcl8.6/tcl.h`, include `/usr/include/tcl8.6`, and runtime-linked library 8.6.12 `/usr/lib/x86_64-linux-gnu/libtcl8.6.so`; interpreter `/usr/bin/tclsh`. Independent C compile/link/runtime and SWIG-module compile/link/load proofs precede configuration. A Tcl interpreter alone was not accepted. The exact cache, paths, hashes and versions are bound in `baselines/B3R_openroad_10666_repaired/configure_final.dependency_resolution.json`; GCC/G++ 11.4.0 and CMake 3.31.9 run in the preserved immutable Ubuntu 22.04.5 toolchain image.

| method | stage | elapsed_seconds | peak_RSS_kbytes | reused |
| --- | --- | --- | --- | --- |
| B2 | historical_exact_compilation | 5213.271426556 | 2096392 | True |
| B3R — PR #10666 + minimal compile repair | receiver_repair_narrow_target | 344.07921800599996 | 1035184 | False |
| B3R — PR #10666 + minimal compile repair | receiver_repair_full_build_validation | 2649.092169238 | 1615500 | False |
| B3R — PR #10666 + minimal compile repair | final_immutable_commit_incremental_build | 194.283790183 | 1390464 | False |
| B3R — PR #10666 + minimal compile repair | failed_architecture_qualification | 3.660208830000002 | 188156 | False |

Native DFT tests: three PASS (`scan_opt_sky130`, `place_sort_sky130`, `one_cell_sky130`) on the preserved precommit validation binary `bcf4a6be99366e5e5a6062b625cbadd65c945025b561a05912caee74d8f03ff3`. No new upstream test was added. The final immutable binary's command probe confirms native KMeans (100 iterations), NN, directed 2-Opt and direction-preserving 3-Opt over 50 nearest candidates, with external endpoints excluded from local optimization cost. Command availability and small regressions do not establish all-design benchmark qualification.

## Observed qualification blocker

The actual command log reports spatial preclustering of 179 cells across two chains (capacity 90), then `Optimized 2 scan chain(s).` The frozen adapter subsequently raises `Cannot faithfully trace native SI/SO connectivity`. A separate read-only saved-ODB inspection and an independent generated-Verilog graph find internal FF paths of 90 and 89 ending on `n2510gat` and `n707gat` without the fixed scan-output ports. The fixed SO outputs remain attached to interior Q nets. FF inventory, master, position, orientation and functional D/CK connections remain unchanged. The richer diagnosis also records any metadata-versus-ODB order discrepancy separately. The failed generated ODB/Verilog are preserved as raw diagnostic evidence; neither is canonicalized, translated into a qualifying architecture, or physically implemented.

| design | method | chain_lengths | status |
| --- | --- | --- | --- |
| s5378 | B2 | 90/89 | PASS |
| s9234 | B2 | 106/105 | PASS |
| s15850 | B2 | 267/267 | PASS |
| s5378 | B3R — PR #10666 + minimal compile repair | unavailable; no qualified canonical output | FAILED_SCAN_OUTPUT_TOPOLOGY |
| s9234 | B3R — PR #10666 + minimal compile repair | unavailable; no qualified canonical output | NOT_ATTEMPTED_AFTER_STOP |
| s15850 | B3R — PR #10666 + minimal compile repair | unavailable; no qualified canonical output | NOT_ATTEMPTED_AFTER_STOP |

The partial canonical inventory contains only the original 24 B0/B1/P0 records and three exact-B2 records: 27 architectures and 8,252 ordered FF rows. B3R contributes zero qualified canonical architectures. The seven predeclared P0 selected identities and roles remain frozen at `9d9103027918b1d4af2b209e6d36133ad82d4a4e`, candidate_stateful depth 3; B1 is not regenerated.

## Physical outcomes and scientific scope

New routing, extraction, simulation, ATPG, placement and root-cause runs: **0**. No historical physical results are imported past the failed mandatory qualification gate. All 19 proposed selected-method records retain unknown routed wire, E, H4 and H8; all Pareto and representative rows are unassessable. A1–A5 remain unassessed. This incomplete attempt establishes no P0 advantage, parity or disadvantage and no valid B3R comparison.

Cache eligibility preflight verified 460 historical bindings, with 19 eligible route candidates and 18 preserved ineligible phase0c caches. The excluded caches used four threads and lacked explicit NUM_CORES=2; no grandfathering or rerouting occurred after the qualification stop. The fixed backend and current ORFS `5e8b1450d19263f797a27c4f371b9dd19f32a3aa` are verified, with clean tracked ORFS files.

## Upstream contribution, evidence and Git

The minimal compile repair was submitted as [https://github.com/mwsoli/OpenROAD/pull/1](https://github.com/mwsoli/OpenROAD/pull/1) against `mwsoli/OpenROAD:dft/scan-chain-optimizer`, with the same immutable repair commit used locally, and relates to original PR #10666. CI at capture: `action_required`; passing CI, review or merge is not claimed. The benchmark does not wait for upstream review. The additional topology diagnosis is documented locally; no additional source fix or upstream comment is sent.

Final relevant unit cases: 129 distinct PASS, zero unresolved failures (211 valid-suite executions including recorded reruns). Of these, 47 historical cases (55 executions) are reused; 82 new receiver cases are passed. An initial synthetic test fixture omitted its required commit field: that superseded 27-case attempt had five failures and 22 passes. Its XML, execution, initial fixture and corrected successful 27-case run are preserved separately in `blocked_harness_attempt1_superseded.json`; they do not change benchmark output or source. Three native DFT regressions, the compiled command probe, three unchanged exact-B2 qualifications, and one failed B3R s5378 attempt are counted separately. Original checks verify 454 frozen bindings, 122 sealed bindings and 24 original canonical identities; the prior recovery's 530 file bindings remain intact.

The new seal binds compact artifacts, source snapshots, the exact patch, provisional/final binaries, prerequisite and build receipts, failed raw ODB/Verilog and file-level D: data. The historical seals and user edits remain preserved. The formal [source-repair amendment](../protocol/amendment_B3_source_repair.md) records the compile-only derivative and its independent qualification stop. A separate milestone commit receipt will record the actual recovery commit without rewriting this seal.

Stage B/P1 and Stage C remain unstarted. Stage A is not complete or sealed as a completed benchmark; this is a sealed incomplete recovery attempt. Continuing would require a separately authorized source-behavior change with new provenance and qualification.
