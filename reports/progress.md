# Phase-0 progress

## Bootstrap and tool qualification

DONE: Independent PACT Git repository initialized. Ubuntu WSL2 inventoried. OpenROAD DFT SKY130 replacement/planning/stitching passed; `scan_opt` warned that it is unimplemented and left the netlist unchanged. FAN_ATPG built and its ATPG plus fault-simulation examples passed for s27, s5378, s9234, and s15850.

BLOCKED: The OpenROAD binary's full build commit was not recovered; its release/version and package checksum are recorded. Original ISCAS89 benchmark rights have not been independently resolved.

NEXT: Preserve the pinned tool versions when extending the benchmark matrix.

EVIDENCE: `artifacts/raw/tool_qualification/`, `reports/openroad_dft_qualification.md`, `reports/fan_atpg_qualification.md`, and `benchmarks/manifests/iscas89_from_fan.yaml`.

## Sanity model, ATPG identity, and shift simulation

DONE: Self-authored 64-FF `pact_sanity` synthesized for tool debugging. Canonical scan architecture validation and deterministic hashes, FAN `.pat` parsing, manually checked serial-shift tests, spatial metrics, and all required baseline ordering algorithms are implemented. Exact 179-way s5378 and 211-way s9234 bijections connect FAN PPIs to source and placed SDFF_X1 instances and DEF positions. The final unit suite passed 24 tests; doctor, scan validation, shift activity, comparison, and plots passed on both designs.

BLOCKED: A full-scan extraction from the self-authored sanity RTL into FAN_ATPG's combinational format was not implemented; both research designs rely on FAN's supplied pre-scanned netlists.

NEXT: Validate a general sanity full-scan abstraction before admitting new RTL benchmarks.

EVIDENCE: `artifacts/raw/benchmarks/pact_sanity/`, `artifacts/raw/tests/pytest.log`, `artifacts/raw/cli_checks/`, both `artifacts/derived/{s5378,s9234}/ff_identity_map.json` manifests, and `tests/unit/`.

## Fixed-placement two-design physical campaign

DONE: Explicit BUF_X3→BUF_X4 translations (34 s5378, 96 s9234 cells) allowed Nangate45 ORFS placement and detailed routes of both FAN fixed netlists. Scan-only OpenDB edits produced nearest-neighbor variants. Structural comparison excluding SI/scan-out, all component masters/locations, physical chain order, and ATPG target remappings passed for 117 s5378 and 156 s9234 patterns. Both orders per design completed CTS, global routing, and detailed routing with final DRC 0. Both 14-record campaigns completed with compressed per-clock traces and grids 8, 16, and 32. The cross-design comparison finds a strict proxy wirelength/hotspot conflict in s5378 only.

BLOCKED: Only supplied and nearest-neighbor orders were routed per design. The supplied order is FAN's pre-stitched chain, not OpenROAD's `execute_dft_plan` order. The small s5378 hotspot conflict did not replicate on s9234; no independent physical seeds, routed hotspot-minimizing random/activity-aware variants, structured congestion metric, or PDNSim run exist. The initial WSL CLI request was rejected by automatic review for a usage limit; after its stated reset time the same direct request ran, exposed a plotting syntax error, and passed after repair. Failure logs remain archived.

NEXT: Extract OpenROAD-native ordering for the research scan cells or document inapplicability; route the candidate random/activity-aware orders; repeat on additional physical seeds or designs; then reassess the conflict and Phase-1 gate.

EVIDENCE: `artifacts/raw/orfs_smoke/`, `artifacts/raw/orfs_rewire/`, `artifacts/raw/orfs_physical/`, `artifacts/derived/phase0/{s5378,s9234}/results.jsonl`, `artifacts/derived/phase0/comparison_all.json`, `artifacts/raw/metric_campaign/`, `reports/figures/`, and `reports/PHASE0_FINAL_REPORT.md`.
