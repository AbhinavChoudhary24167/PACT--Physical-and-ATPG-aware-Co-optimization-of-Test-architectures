# Phase-0 progress

## Bootstrap

DONE: Independent repository initialized with source, config, evidence, and report conventions.

BLOCKED: None for bootstrap.

NEXT: Inspect and qualify the installed WSL toolchain before tool integration.

EVIDENCE: `artifacts/raw/tool_qualification/environment/` and Git history.

## OpenROAD DFT qualification

DONE: Installed pinned OpenROAD prebuilt; cloned upstream OpenROAD and ORFS to isolated WSL storage with exact source commit hashes; passed two SKY130 DFT regressions; observed `scan_opt` no-op.

BLOCKED: Full ORFS physical flow has not yet been qualified. The Ubuntu package Yosys 0.33 predates the version required by current ORFS documentation.

NEXT: Build and qualify FAN_ATPG independently, then attempt a small ORFS smoke flow with version checks.

EVIDENCE: `reports/openroad_dft_qualification.md` and `artifacts/raw/tool_qualification/openroad/`.

## FAN_ATPG qualification

DONE: Built the specified FAN_ATPG commit and passed supplied ATPG and fault-simulation examples for s27, s5378, s9234, and s15850. Inspected the actual .pat files and upstream writer field order. Parser unit test uses the saved s27 pattern.

BLOCKED: FF identity across the ATPG netlist and a placed physical database is not yet proven. ATPG qualification alone does not admit spatial activity research claims.

NEXT: Qualify a fixed-netlist Nangate45 placement, then verify exact PPI-to-placed-instance correspondence.

EVIDENCE: `reports/fan_atpg_qualification.md`, `benchmarks/manifests/iscas89_from_fan.yaml`, and `artifacts/raw/tool_qualification/fan_atpg/`.
