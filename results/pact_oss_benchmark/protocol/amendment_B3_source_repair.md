# Stage-A amendment: exact B2 retained; B3 receiver repair separately identified

This amendment implements the user's explicit correction of the baseline identity. Exact B2 (OpenROAD PR #10176, `6fff875551fe13a2aae3a22f871a6ca7f8d5c1cf`) remains unchanged. It already built and qualified on s5378, s9234 and s15850. Its existing source, executable, canonical architectures and qualification receipts are reused by binding; it was neither repaired nor regenerated.

The proposed operational method set is **B0 / B1 / exact B2 / B3R / frozen P0**, conditional on all three B3R designs qualifying. Every B3R result is labeled **B3R — PR #10666 + minimal compile repair**. B3R is never reported as the byte-exact B3 revision. P0 remains frozen at `9d9103027918b1d4af2b209e6d36133ad82d4a4e`; its archive, selection, model and search budget are unchanged. Stage B/P1 remains unstarted.

## Original B3 failure and receiver diagnosis

Exact B3 is PR #10666 at `746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656`. Its original failed build and pinned source remain preserved in [the original recovery](../recovery_20261003/baselines/B3_openroad_10666/compilation_blocker.json). Configuration succeeded in the qualified isolated toolchain; compilation failed at the original `OneBitScanCell.cpp` lines 106 and 111 because `getLibertyScanIn(test_cell_)` and `getLibertyScanOut(test_cell_)` lacked an object receiver.

The declarations in `src/dbSta/include/db_sta/dbNetwork.hh` are nonstatic members. `OneBitScanCell` already stores the network supplied by `ScanCellFactory`, which obtains `sta->getDbNetwork()` and the associated valid TestCell. The surrounding methods use that same stored receiver. STA exists throughout the synchronous DFT operation and owns the network until teardown. No new header, library, API, object ownership or lifetime change is needed. See [the detailed receiver diagnosis](../receiver_recovery_20261003/baselines/B3R_openroad_10666_repaired/repair/diagnosis.md).

## Exact derivative identity and patch

| Binding | Recorded value |
| --- | --- |
| Pinned B3 base SHA | `746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656` |
| B3R repair commit SHA | `0f8a15ca7fe14bc2445ec4db8a4df0832a136cb8` |
| Patch SHA256 | `e6a97bf45c7b97409efbcd91d3ed2b9445cf478163e68828fd0e10d76f716960` |
| Repaired file SHA256 | `ed718ea3061698d5aa00124435fde155b3242e0a0fec461c1393cdf5e9a99a25` |
| Final executable SHA256 | `65cd5dec3d12c46035ef67d0b538aa8d932754247bf3a6626094a8f1dc515da0` |
| Executable size | 131438976 bytes |
| DCO sign-off | `Signed-off-by: abhinav <abhinav24167@iiitd.ac.in>` |

The [recorded patch](../receiver_recovery_20261003/baselines/B3R_openroad_10666_repaired/repair/patch.diff) changes one file, with four added and two removed lines. The two receiver insertions are the sole token changes; the extra line count is required clang-format wrapping of the immediate return statements.

```diff
-  return iTermLocation(findITerm(getLibertyScanIn(test_cell_)), inst_);
+  return iTermLocation(findITerm(db_network_->getLibertyScanIn(test_cell_)),
+                       inst_);
...
-  return iTermLocation(findITerm(getLibertyScanOut(test_cell_)), inst_);
+  return iTermLocation(findITerm(db_network_->getLibertyScanOut(test_cell_)),
+                       inst_);
```

An independent gate compares the entire repaired file against the exact base bytes plus those two receiver qualifications and their immediate formatting. All other pinned algorithm source hashes, the main Git diff and recursive submodule revisions are checked. Scan ordering, clustering, cost functions, NN/2-Opt/3-Opt behavior, parameters and endpoint semantics are unchanged. This compile-only claim does **not** claim that the inherited implementation passes the benchmark's endpoint contract.

## Toolchain and actual CMake resolution

The immutable isolated image is `sha256:f05cee3219a02f26289f02f00e11a3fc986ab51a482a0000a2da810cda219a6e`. Before any baseline configuration, independent C compile/link/runtime and SWIG-module compile/link/load probes verified the Tcl development header and library. A working tclsh alone was never treated as sufficient. The [final B3R CMake resolution](../receiver_recovery_20261003/baselines/B3R_openroad_10666_repaired/configure_final.dependency_resolution.json) records the complete actual cache and resolved paths:

| Component | Version | Recorded path inside isolated toolchain |
| --- | --- | --- |
| SWIG executable | 4.3.0 | `/usr/local/bin/swig` |
| SWIG library directory | 4.3.0 | `/usr/local/share/swig/4.3.0` |
| Tcl development header | 8.6.12 | `/usr/include/tcl8.6/tcl.h` |
| Tcl header directory | 8.6.12 | `/usr/include/tcl8.6` |
| Tcl development/shared library | 8.6.12, independently runtime verified | `/usr/lib/x86_64-linux-gnu/libtcl8.6.so` |
| Tcl shell | 8.6.12 | `/usr/bin/tclsh` |
| CMake | 3.31.9 | `/usr/local/bin/cmake` |
| C/C++ compiler | GCC/G++ 11.4.0 | `/usr/bin/gcc`, `/usr/bin/g++` |

CMake's final cache explicitly resolves `SWIG_EXECUTABLE`, `SWIG_DIR`, `SWIG_VERSION`, `TCL_HEADER` and `TCL_LIBRARY` to the entries above. Tcl header/library versions and the shell path come from the independent prerequisite probe; the saved CMake cache does not claim a separate shell resolution. The Tcl header directory is the directory containing the resolved development header.

No B2 configuration was retried in this amendment. The derivative reused an independently copied, byte-verified build cache; container aliases refer to the derivative's own source/build directories, never the preserved exact B3 directories. Generated version headers and restored exact submodule Git metadata are separately documented. The compiler image and algorithm source remain unchanged.

## Build, tests and upstream contribution

The affected `dft_cells_lib` target passed (344.079 seconds), the full repair-validation executable built (2649.092 seconds), and the final immutable-commit incremental build passed (194.284 seconds). These are distinct receipts; the final incremental duration is not presented as a full fresh compilation time. The final executable reports the repair SHA. Its actual compiled command probe passed and executed `scan_opt` during the subsequent benchmark attempt.

Three existing DFT regressions (`scan_opt_sky130`, `place_sort_sky130`, `one_cell_sky130`) passed with exact golden-output comparisons on the preserved precommit repair-validation executable. That executable has SHA256 `bcf4a6be99366e5e5a6062b625cbadd65c945025b561a05912caee74d8f03ff3`; the independently hashed final executable is listed above. No new upstream tests were added. [Native test receipts](../receiver_recovery_20261003/baselines/B3R_openroad_10666_repaired/repair/tests.json) and [final build receipt](../receiver_recovery_20261003/baselines/B3R_openroad_10666_repaired/build_result.json) preserve the distinction.

The exact signed repair commit was pushed without force or rebasing to `AbhinavChoudhary24167/OpenROAD`, branch `fix/dft-dbnetwork-member-receiver`. [A targeted PR was opened](https://github.com/mwsoli/OpenROAD/pull/1) against `mwsoli/OpenROAD:dft/scan-chain-optimizer`, the branch underlying [original PR #10666](https://github.com/The-OpenROAD-Project/OpenROAD/pull/10666). GitHub confirmed the same one-commit, one-file patch. CI at capture was `action_required`, not verified passing. The benchmark did not wait for CI, review or merge. [Contribution metadata](../receiver_recovery_20261003/upstream/github_contribution.json) records the submission and target.

## Observed qualification failure and stop condition

The first s5378 generation executed `execute_dft_plan` followed by the actual compiled `scan_opt`. K-means reassigned all 179 cells across two chains with bit cap 90; optimization reported two chains. The frozen adapter then rejected physical SI/SO connectivity. Read-only analysis of the saved generated ODB independently confirms:

- chain 0 follows 90 distinct FFs from `U_n1525gat` to `U_n2510gat`, terminating on net `n2510gat`;
- chain 1 follows 89 distinct FFs from `U_n2347gat` to `U_n707gat`, terminating on net `n707gat`;
- the fixed output BTerms remain attached to old nets `n2502gat` and `n2121gat`, which occur inside the first new chain;
- neither new tail reaches its required fixed output, while FF inventory, masters, placement, orientation and functional D/CK connectivity remain unchanged.

The distinct inherited cause is `src/dft/src/Dft.cpp`, `RestitchChain`: it rewires first-SI and internal SO-to-SI edges but only calls `chain->setScanOut(last_so)` for the new tail. That updates metadata, not the physical fixed output connection. This behavior is byte-identical to pinned B3 and was not introduced by the compile repair. The adapter correctly rejects it; metadata alone cannot replace the required physical SI/SO proof. [The preserved failure log](../receiver_recovery_20261003/baselines/B3R_openroad_10666_repaired/s5378/generate.log) and saved-ODB diagnostics provide the evidence.

Consequently **B3R built, but did not qualify**. s9234 and s15850 generation were not attempted after this separate source/endpoint failure. No additional B3R source patch, output reconnection, substitute optimizer, parameter change or weakened qualification is authorized by this amendment. The failed output is diagnostic evidence and contributes no canonical B3R architecture or measured comparison.

Stage A remains **PACT_STAGE_A_INCOMPLETE / PACT_BENCHMARK_INCONCLUSIVE**. New physical route/extraction/simulation runs are zero. Historical complete results remain provenance; no compile failure or invalid architecture is counted as a PACT advantage. The selected B0/B1/exact B2/P0 data and exact B3 failure are retained. Continuing with a further endpoint-semantics repair requires a separate scope decision and a separately identified derivative; it cannot be silently folded into this receiver-only B3R. P0 and P1 remain untouched.
