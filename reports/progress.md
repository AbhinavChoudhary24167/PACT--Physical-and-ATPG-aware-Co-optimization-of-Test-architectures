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
