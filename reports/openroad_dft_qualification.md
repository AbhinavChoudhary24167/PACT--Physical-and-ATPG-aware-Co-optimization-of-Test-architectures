# OpenROAD DFT qualification

Date: 2026-09-13 UTC. Environment: Ubuntu 24.04.4 LTS under WSL2.

The installed OpenROAD binary is the official Ubuntu 24.04 prebuilt package `26Q2-1164-g08f67ee5ec`. Its package SHA256 is in `artifacts/raw/tool_qualification/openroad/package.sha256`. This release tag embeds a shortened source hash; the full binary build commit was not independently recovered. Separately cloned, unmodified upstream OpenROAD source at `dc5eee77c45dba8e5ace2fc89c38c6d9a4ed6e0f` supplied regression fixtures, and ORFS source is at `5e8b1450d19263f797a27c4f371b9dd19f32a3aa`. The fixture-source commit is **not** claimed to be the binary's commit.

| Check | Observed result | Raw evidence |
| --- | --- | --- |
| `scan_replace` | PASS in upstream `one_cell_sky130.tcl` and `place_sort_sky130.tcl` | `artifacts/raw/tool_qualification/openroad/one_cell_sky130.log`, `place_sort_sky130.log` |
| `report_dft_plan -verbose` | PASS; plan reported in both scripts | Same logs |
| `execute_dft_plan` | PASS; stitched netlist and DEF match upstream expected files | Same logs, two `No differences found` messages in one-cell test |
| `scan_opt` | Command exists, warns `DFT-0014 Scan Opt is not currently implemented`; before/after Verilog SHA256s identical | `artifacts/raw/tool_qualification/openroad/scan_opt.log`, `scan_opt_netlists.sha256`, `scan_opt_netlist_cmp.exit` |

The regression cases were run unmodified from an isolated WSL directory with symlinks to upstream SKY130 fixtures. Each OpenROAD invocation had a 120-second timeout. Actual DFT output netlists remain under `artifacts/raw/tool_qualification/openroad/results/`. This demonstrates installed DFT replacement and stitching, but does not establish user-defined scan rewiring or full ORFS routing.
