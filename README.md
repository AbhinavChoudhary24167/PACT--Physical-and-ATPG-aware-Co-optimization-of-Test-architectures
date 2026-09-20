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

## Research Status

PACT is progressing through a staged qualification process for physical- and ATPG-aware scan-architecture optimization.

### Phase-0C — Completed

Status: `PACT_PHASE0C_LEARNING_GATE_FAIL`

Phase-0C completed a frozen campaign over s5378, s9234, and s15850; five conditional physical seeds; and K in {1, 2, 4, 8}. All 375 planned architecture routes were attempted and qualified with zero detailed-route DRC. The campaign established reproducible physical/activity conflict, cross-seed and cross-design replication, and large legal search spaces. It did not establish that learned optimization is scientifically necessary: the frozen deterministic portfolio covered the observed Pareto set, and the tested local-swap intervention was insufficiently rich. No ML model was trained.

### Phase-0D — Pilot Completed; Campaign Not Yet Launched

Pilot status: `PILOT_COMPLETE_NO_ROUTE_QUALIFIED`

Phase-0D studies richer legal interventions and budgeted deterministic search using a structural-check, analytical-proxy, Pareto-filter, and selective-route funnel. Its primary question is:

> Under bounded compute and physical-evaluation budgets, do deterministic search methods leave a reproducible optimization gap large enough that investigating learned guidance is scientifically justified?

The frozen one-context pilot verified all seven intervention classes and all 117 ATPG target reconstructions. Four equal-budget deterministic searches completed 32 logical search evaluations; early stopping occurred after eight evaluations per method. No child was nondominated against the qualified Phase-0C `P` start, so the frozen filter selected no new physical route. The naive maximum-budget campaign projects to roughly 70 serial hours and was not launched; the next step is a reduced, staged cross-design/cross-seed campaign.

This pilot is not a Phase-0D PASS or FAIL decision. Current evidence and progress are in `reports/phase0d/STATUS.md` and `reports/phase0d/PILOT_REPORT.md`.
