# B3R s5378 connectivity diagnosis

**B3R — PR #10666 + minimal compile repair fails the frozen physical SI/SO topology qualification.** The failure is a distinct inherited `RestitchChain` output-endpoint semantics defect under this benchmark's fixed endpoint contract. The frozen native adapter correctly rejects the saved generated database. No additional source repair, optimizer execution, canonical architecture substitution, route or measurement is justified by this diagnosis.

The actual `scan_opt` command completed successfully before the adapter failed at `pact_oss_native.py:106`. Successful command execution does not establish a legal scan architecture. The emitted Verilog and saved-ODB observation independently agree on two disjoint internal paths covering all 179 FFs:

| Physical input | FF count | First FF | Last FF | Terminal Q net | Fixed output attachment |
| --- | --- | --- | --- | --- | --- |
| `test_si_0` | 90 | `U_n1525gat` | `U_n2510gat` | `n2510gat` | `test_so_0` remains on `n2502gat`, FF position 67 in this path |
| `test_si_1` | 89 | `U_n2347gat` | `U_n707gat` | `n707gat` | `test_so_1` remains on `n2121gat`, FF position 79 in the first path |

Neither tail net has the required fixed SO BTerm or a transparent buffer path to that SO. The first tail drives functional inverter input `U_n2508gat/A`; the second tail has functional logic fanout. Treating either functional logic path as a transparent scan connection would be incorrect. Both fixed SO nets have an onward FF SI load in the first path. The second path therefore lacks its fixed physical output, while both outputs sample intermediate positions in the first path.

The 179 FF identities, masters, locations, orientations and functional D/CK nets are unchanged. That preservation and the internal 90/89 capacities do not cure the output connectivity failure. The primary evidence is the actual generated connectivity, rather than an inference from an exception message.

`src/dft/src/Dft.cpp` is byte-identical to upstream base `746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656`, SHA256 `ea2b2d2f02b1b0c79149156c694509dae9240e29d62a1281660e3bc30c101ce3`. Its `RestitchChain` implementation at lines 79–128 reconnects the first SI and interior SO-to-SI edges, but lines 123–127 only call `chain->setScanOut(last_so)` for the new tail. The explicit comment at lines 76–78 says the original output net is retained and only the chain metadata pointer is updated. The final optimizer calls this function at line 568. The authorized two-statement compile repair in `OneBitScanCell.cpp` does not change this implementation.

The saved scan metadata also disagrees with the observed physical order. Chain 0 has the same 90 members but 87 different positions; its first difference is position 2 (`U_n1340gat` in metadata versus `U_n1740gat` physically). Chain 1 has the same 89 members but 88 different positions; its first difference is position 1 (`U_n2343gat` versus `U_n2347gat`). This is a secondary observation. Metadata iteration cannot substitute for the physically traced ordering or supply an output-qualified canonical architecture.

The diagnosis binds repair commit `0f8a15ca7fe14bc2445ec4db8a4df0832a136cb8` and patch SHA256 `e6a97bf45c7b97409efbcd91d3ed2b9445cf478163e68828fd0e10d76f716960`. The structured [diagnosis receipt](independent_diagnosis.json) records the exact built binary SHA and hashes of the generated ODB, emitted Verilog, [saved-ODB read execution](connectivity_read_attempt2.execution.json), inherited source comparison and frozen adapter. The [independent netlist review](independent_netlist_review.py) compared every emitted FF's SI/Q/D/CK nets with the actual saved-ODB observation, then separately reconstructed both complete internal FF orders.

A preliminary read with the fixed downstream binary failed because generated ODB schema 0.132 exceeds that reader's supported 0.129. The successful saved-ODB diagnostic used the actual B3R binary in the isolated image. This read compatibility issue is separate from the physical SO failure and contributes no route or measurement attempt.

The compile-only contribution was opened as [mwsoli/OpenROAD PR #1](https://github.com/mwsoli/OpenROAD/pull/1), related to PR #10666. Its submission does not qualify this benchmark architecture or authorize a further behavioral source patch.

Preserve the failed s5378 generation and diagnostics, retain `SOURCE_TOPOLOGY_BLOCKER_STOPPED`, and keep downstream routing and measurements gated. `s9234` and `s15850` remain unattempted. Seal Stage A as incomplete with its actual blocker; do not restitch endpoints, reinterpret metadata, fabricate a canonical architecture or rerun generation under the compile-only amendment.
