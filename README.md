# PACT Phase 0

PACT (Physical- and ATPG-aware Co-optimization of Test Architectures) tests whether legal scan-chain orderings create a reproducible conflict between physical scan cost and ATPG-derived shift-activity hotspots. This repository contains the experimental infrastructure, raw evidence, and a gate-based Phase-0 report. It does not contain machine learning.

The hypothesis is open. A missing tool, unverified flip-flop identity map, or failed physical rerun is recorded as a failed gate, not replaced with simulated research evidence.

## Quick start

Run from this repository in Ubuntu WSL. External ORFS and FAN_ATPG checkouts are kept outside this Git repository; set the three environment variables to the qualified installations before reproducing the observed s5378/s9234 subset:

```bash
bash scripts/collect_versions.sh
export PACT_ORFS_ROOT=/path/to/OpenROAD-flow-scripts
export PACT_FAN_ATPG_ROOT=/path/to/FAN_ATPG
export PACT_VENV=/path/to/pact-venv
bash scripts/run_phase0.sh
```

`run_phase0.sh` intentionally returns status 2 after reproducing the available subset because the central conflict did not replicate and OpenROAD-native ordering was not extracted for these designs. To recheck saved campaigns without repeating physical implementation, run `bash scripts/finalize_phase0.sh`. See `reports/PHASE0_FINAL_REPORT.md` for measured results and `docs/methodology.md` for metric definitions.
