`OneBitScanCell::getScanInLocation()` and `getScanOutLocation()` call the non-static `sta::dbNetwork` APIs `getLibertyScanIn()` and `getLibertyScanOut()` without an object receiver, causing compilation to fail at PR #10666 revision `746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656`.

Qualify both calls with the existing `db_network_` member. `ScanCellFactory` supplies this network from the active STA instance together with the corresponding `TestCell`. The repair uses the established API ownership and lifetime; `findITerm()` and `iTermLocation()` retain their existing behavior. The diff contains only these two receiver qualifications and immediate formatting of the affected return statements. Scan ordering, cost functions, clustering, NN/2-Opt/3-Opt behavior, parameters, and endpoint semantics are unchanged.

Validation:

- `dft_cells_lib` and the full `openroad` target build with GCC 11.4.0, SWIG 4.3.0, and Tcl development headers/library 8.6.12.
- The existing DFT regressions `scan_opt_sky130`, `place_sort_sky130`, and `one_cell_sky130` pass their golden-output checks.
- `git diff --check` passes, and the repair commit includes the DCO sign-off.

This PR targets `mwsoli/OpenROAD:dft/scan-chain-optimizer`, the head branch of [The-OpenROAD-Project/OpenROAD#10666](https://github.com/The-OpenROAD-Project/OpenROAD/pull/10666).

Base: `746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656`. Repair commit: `0f8a15ca7fe14bc2445ec4db8a4df0832a136cb8`. Patch SHA256: `e6a97bf45c7b97409efbcd91d3ed2b9445cf478163e68828fd0e10d76f716960`.
