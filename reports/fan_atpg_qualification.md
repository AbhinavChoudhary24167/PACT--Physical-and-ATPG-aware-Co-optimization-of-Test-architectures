# FAN_ATPG qualification

Date: 2026-09-13 UTC. The specified [NTU-LaDS-II/FAN_ATPG](https://github.com/NTU-LaDS-II/FAN_ATPG) repository was cloned at commit `26b2b36c0e9db11a4b6d9e759df6e44357121f39` to isolated WSL storage. The project identifies itself as version 2023 and has an MIT `LICENSE` (SHA256 in `artifacts/raw/tool_qualification/fan_atpg/license.sha256`). `make -j2` passed after installing Bison, Flex, and build-essential. Generated binaries, libraries, reports, and patterns are untracked build outputs in that isolated checkout; no upstream source file was edited.

Supplied `script/fanScripts/` examples were run with static compression, dynamic compression, and X-fill **on**, using the tool's `saf` stuck-at model and one-frame `BASIC_SCAN` patterns. Each command had a 180-second timeout. Values below are transcribed from the saved tool reports, and corresponding fault-simulation reports agree on coverage and pattern count.

| Design | ATPG exit | Fault-sim exit | Fault coverage | Patterns | ATPG runtime (tool reported) | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| s27 | 0 | 0 | 94.55% | 5 | 0.000235 s | `artifacts/raw/tool_qualification/fan_atpg/reports/FAN_s27.rpt` |
| s5378 | 0 | 0 | 96.04% | 117 | 0.4923 s | `artifacts/raw/tool_qualification/fan_atpg/reports/FAN_s5378.rpt` |
| s9234 | 0 | 0 | 94.14% | 156 | 2.257 s | `artifacts/raw/tool_qualification/fan_atpg/reports/FAN_s9234.rpt` |
| s15850 | 0 | 0 | 94.62% | 133 | 4.746 s | `artifacts/raw/tool_qualification/fan_atpg/reports/FAN_s15850.rpt` |

Full stdout/stderr, exit files, copied patterns, and checksum manifest are under `artifacts/raw/tool_qualification/fan_atpg/`. The `.pat` writer at the recorded commit (`pkg/core/src/pattern_rw.cpp`, `PatternWriter::writePat`) emits three ordered header lines (PI, PPI, PO), then `BASIC_SCAN`, count, and seven fields per pattern: `PI1 | PI2 | PPI | SI | PO1 | PO2 | PPO`. The PPI field supplies logical target scan-FF states. No PPI-to-physical-FF mapping has yet been validated, so these patterns are **not** used for Phase-0 spatial activity conclusions.

The supplied `mod_netlist` circuits contain pre-stitched `SDFF_X1` cells with names matching the PPI header, and ORFS Nangate45 Liberty contains `SDFF_X1`. A fixed-netlist physical import is therefore plausible. It still requires a preserved-instance mapping after placement and a verified method for changing only scan connectivity before it can count as a controlled experiment.
