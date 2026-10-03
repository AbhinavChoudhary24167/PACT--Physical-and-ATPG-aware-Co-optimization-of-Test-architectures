# Stage-A recovery stopped on exact B3 source defect

**PACT_STAGE_A_INCOMPLETE**. Scientific classification: **PACT_BENCHMARK_INCONCLUSIVE**.

B2 was reproduced and qualified. Exact B3 compilation failed because its two scan-pin location accessors call `sta::dbNetwork` member APIs without an object receiver. The user's explicit stop rule applies to any PR source change needed to compile. No PR source change, source-injecting compiler workaround, subsequent build retry or downstream experiment was performed.

## Builds and isolated environment

| Method | Exact source revision | Build status | Binary SHA256 |
| --- | --- | --- | --- |
| B2 | `6fff875551fe13a2aae3a22f871a6ca7f8d5c1cf` | BUILT | `601da32f4493cd9587b53812385af4ec9ed08f1c3f5e9def9c6a7e4897b25087` |
| B3 | `746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656` | COMPILATION_FAILED | unavailable; no executable |

B2 binary: `/mnt/pact-oss-recovery/B2_openroad_10176/build/bin/openroad`. Immutable image: `openroad/orfs@sha256:f05cee3219a02f26289f02f00e11a3fc986ab51a482a0000a2da810cda219a6e`, Ubuntu 22.04.5 amd64. Dedicated D:-backed ext4 build prefixes; repository read-only in network-disabled containers. GCC/G++ 11.4.0 and CMake 3.31.9. Both actual CMakeCache files resolve SWIG 4.3.0 at `/usr/local/bin/swig`, data `/usr/local/share/swig/4.3.0`; Tcl header `/usr/include/tcl8.6/tcl.h`, include `/usr/include/tcl8.6`, library `/usr/lib/x86_64-linux-gnu/libtcl8.6.so`, and interpreter `/usr/bin/tclsh`. Header and linked-library runtime both 8.6.12, independently compiled/linked/loaded before B2 configuration. Exact path/hash/version receipts are in each baseline's `cmake_resolved_dependencies.json` and `toolchain/qualification.json`. A working interpreter alone was not accepted. See [dependency audit](../protocol/build_environment_audit.md).

B2's successful resumed build took 5213.271 seconds, after an intentionally interrupted 1005.735-second storage attempt; maximum child RSS was 2,096,392 kbytes. B3 configure passed in 16.209 seconds; compilation failed after 4178.934 seconds, exit 2, maximum child RSS 2,095,732 kbytes. Complete commands, logs, resource receipts, exact submodule commits and archive hashes remain preserved. The qualified WSL OpenROAD/ORFS/PACT environment was not replaced. Storage relocation and nonfatal Boost/BZip2/GPU-banner warnings are documented in the audit.

## Exact blocker

`src/dft/src/cells/OneBitScanCell.cpp:106`: `getLibertyScanIn` undeclared. Line 111: `getLibertyScanOut` undeclared. `src/dbSta/include/db_sta/dbNetwork.hh:436–437` declares these as members; the header is already included. The same translation unit correctly calls these APIs through `db_network_->` elsewhere. The affected sources and headers match the exact pinned archive. These are source name-lookup errors, with no missing-package remedy. The optimizer static library compiled, but that does not reproduce an executable or qualify behavior. Full diagnostic snapshots and compiler rule/flags are in `baselines/B3_openroad_10666/diagnostics/`; structured evidence is in `compilation_blocker.json`.

## Architecture qualification

B2's compiled Tcl command probe and linked optimizer symbols passed. Actual `execute_dft_plan; scan_opt` runs use native NN and endpoint-inclusive FF-origin Manhattan 2-Opt, maximum 30 iterations. All three outputs preserve exact expected FFs, K=2, domains, capacity, SI/SO legality, canonical assignment/order and endpoint geometry. B3 compiled-command verification and generation remain unavailable.

| Design | B2 chain lengths | B2 qualification | B3 chain lengths / qualification |
| --- | --- | --- | --- |
| s5378 | 90/89 | PASS | unavailable |
| s9234 | 106/105 | PASS | unavailable |
| s15850 | 267/267 | PASS | unavailable |

Full B2 architecture hashes and 924 ordered FF identities are in `baselines/B2_openroad_10176/qualification.json` and `architecture_manifest.csv`. The partial Stage-A inventory records 27 qualified canonical architectures and 8,252 FF rows: the original 24 plus three B2 outputs. B0/B1 and the complete P0 archive and seven predeclared selected P0 identities remain unchanged. B1 was not regenerated. P0 remains `9d9103027918b1d4af2b209e6d36133ad82d4a4e`, candidate_stateful depth 3. No prediction rescoring or selection change occurred.

## Physical/activity outcomes and scientific questions

New physical implementations: **0**. New routing/extraction/simulation/ATPG/placement/root-cause runs: **0**. The common backend remains `/usr/bin/openroad`, revision `08f67ee5ecd14db5a42be8c610bbfd1ccf079299`, version `26Q2-1164-g08f67ee5ec`, SHA256 `fcd7dcfc37d329bd43a7ede75805319a2e70e6879da11d42b4fd1c2e50e645c3`; ORFS remains `5e8b1450d19263f797a27c4f371b9dd19f32a3aa`. Existing physical evidence was not imported past the mandatory B3 gate. New physical qualification outcomes are unavailable.

| Design | Methods | Routed cost (µm) | E (fF·transitions) | H4/H8 (fF·transitions per bin/cycle) |
| --- | --- | --- | --- | --- |
| s5378 | B0/B1/B2/B3/P0 | unavailable | unavailable | unavailable |
| s9234 | B0/B1/B2/B3/P0 | unavailable | unavailable | unavailable |
| s15850 | B0/B1/B2/B3/P0 | unavailable | unavailable | unavailable |

All 19 selected method records retain unknown measurements in `stage_a/implemented_metrics.csv`; representative and Pareto tables explicitly mark them unassessable. Pre-route metrics retain only the original diagnostics, with their source scope recorded in status. P0 versus B0/B1/B2/B3, external Pareto membership and A1–A5 are **unassessed**. No P0 external advantage/disadvantage, B3 dominance, wire/activity relationship or A5 selection-miss conclusion can be drawn from this incomplete campaign.

## Validation, evidence and Git

Relevant unit tests: **47 distinct passed, 0 failed** (55 executions including reruns; no unrelated suites). The tests cover the existing protocol and candidate_stateful model, actual build-resolution parsing, exact Pareto dominance, missing/failed-measurement handling and scientific comparison scope. Separate integrations: three saved-B1 endpoint checks and three actual B2 architecture qualifications passed. Independent SWIG/Tcl C and generated-module compile/link/load probes passed. B3 has zero architecture qualifications. Original integrity checks passed for 454 frozen bindings, 122 sealed bindings and 24 canonical architectures. Failed prerequisite-package and endpoint-adapter attempts remain preserved alongside their corrected successful proofs.

The new evidence manifest binds compact artifacts, executed source snapshots, exact source archives, B2 binary and raw generator/prerequisite files; the previous incomplete seal remains untouched. Prepared downstream helpers were not executed and cannot bypass the qualification gate. A separate diagnostic/recovery commit is permitted because this attempt adds durable reproducibility infrastructure. Its SHA and final Git status will be recorded in a commit receipt. Existing user README/planning/fault-identity/H8 edits are excluded.

Stage B's scientific prerequisite is **not satisfied**. Stage B/P1 and Stage C remain unstarted. The remaining blocker is the exact pinned B3 source defect. Continuing requires a separately authorized change to the source-repair/pinning constraint, with explicit provenance and scientific review; this recovery stops here.
