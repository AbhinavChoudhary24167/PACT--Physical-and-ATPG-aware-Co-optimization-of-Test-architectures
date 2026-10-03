`OneBitScanCell::getScanInLocation()` and `getScanOutLocation()` currently call the non-static `sta::dbNetwork` methods `getLibertyScanIn()` and `getLibertyScanOut()` without an object receiver. At PR #10666 revision `746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656`, both calls fail to compile.

Qualify these two existing calls with the cell's existing `db_network_` member. `ScanCellFactory` obtains this network from the active STA instance and passes it with the corresponding `TestCell` to `OneBitScanCell`. `clang-format-18` wraps only these two repaired return statements onto two lines each, producing four added lines and two removed lines in one file. The functional changes are only the two missing receivers; scan ordering, cost functions, clustering, NN/2-Opt/3-Opt logic, parameters, and scan-pin endpoint semantics are unchanged.

This contribution targets `mwsoli/OpenROAD:dft/scan-chain-optimizer`, the head branch of [The-OpenROAD-Project/OpenROAD#10666](https://github.com/The-OpenROAD-Project/OpenROAD/pull/10666). The receiver defect is absent from exact PR #10176 and current upstream `master`.

Local validation at the pinned PR revision plus this repair:

- Independent WSL formatter `Ubuntu clang-format version 18.1.3 (1ubuntu1)` validates the immediate call sites with `clang-format-18 -i --lines=106:111`; `git diff --check` passes. The committed source matches the exact parent plus the two receiver additions and immediate formatting.
- `dft_cells_lib` and the full `openroad` target build successfully with GCC 11.4.0, SWIG 4.3.0, and Tcl development headers/library 8.6.12 in the isolated toolchain.
- Existing DFT integration tests `scan_opt_sky130`, `place_sort_sky130`, and `one_cell_sky130` pass, including their checked golden outputs.
- DCO sign-off is present in commit `0f8a15ca7fe14bc2445ec4db8a4df0832a136cb8`.

Base: `746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656`. Repair commit: `0f8a15ca7fe14bc2445ec4db8a4df0832a136cb8`. Patch SHA256: `e6a97bf45c7b97409efbcd91d3ed2b9445cf478163e68828fd0e10d76f716960`. The controlled PACT benchmark uses this same immutable commit under the explicit label **B3R — PR #10666 + minimal compile repair**; exact B2 remains unchanged.
