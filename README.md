# PACT — Physical- and ATPG-aware Co-optimization of Test Architectures

The working optimizer is now available as `pact-optimize` (or
`python scripts/pact_optimize.py` from this checkout). Install with
`pip install -e '.[optimizer]'`, then run
`pact-optimize --design s5378 --chains 2 --time-budget 60 --output run/s5378`.
It uses exact incremental repaired M3/M5 activity costs, spatial construction,
bounded Pareto search and anytime checkpoints. See
[usage and implementation](docs/working_optimizer.md),
[current implementation note](current_solution.md), and
[measured solution status](solution_status.md).
The historical experiment descriptions below remain as background.

## Working solver

Current engineering status: **WORKING_SOLVER**. The maintained entry point is
`pact-optimize`; the older v1/v2 scripts remain available for reproducing their
recorded experiments. The working solver preserves repaired M3/M5 semantics
and returns optimized chains, a bounded Pareto set, objective values, runtime,
peak memory, evaluation counts and convergence checkpoints.

```bash
pip install -e '.[optimizer,dev]'
# Self-contained algorithm-scaling example; no placed-design archives required.
pact-optimize --synthetic 10000 --time-budget 60 --output run/scaling_10k
# Requires the placed design, mapped ATPG inputs and Liberty described in the guide.
pact-optimize --design s5378 --chains 2 --time-budget 60 --output run/s5378
```

The three real 60-second runs improved M3 total by 5.87%, 3.04% and 1.44%
against their strongest existing physical starts, with improved local peaks.
Six selected new routes passed with zero DRC errors. Synthetic 100K-FF scaling
completed in 60.31 seconds at 349 MiB with 200 chains; two long chains required
1.25 GiB and substantially reduced throughput. These measurements do not claim
industrial-scale ATPG performance or signoff power improvement.

See [measured results and limitations](solution_status.md),
[input schema and CLI guide](docs/working_optimizer.md), and the
[repository update and experiment index](docs/repository_update.md).

PACT (Physical- and ATPG-aware Co-optimization of Test Architectures) tests whether legal scan-chain orderings create a reproducible conflict between physical scan cost and ATPG-derived shift-activity hotspots. This repository contains the experimental infrastructure, raw evidence, and a gate-based Phase-0 report. It does not contain machine learning.

The original research question is:

> Can an intervention-aware learning model jointly reason over physical-design state and ATPG-derived activity to predict the marginal impact of legal scan-architecture transformations, enabling closed-loop optimization of test power integrity, routability, timing, and test cost while preserving test quality by construction?

The work evaluates test-mode power and IR-drop risk, scan-chain routing congestion, timing degradation, excessive scan wirelength, test time, physical locality, and costly iteration between DFT and physical-design teams.

The hypothesis is open. A missing tool, unverified flip-flop identity map, or failed physical rerun is recorded as a failed gate, not replaced with simulated research evidence.

## Historical Phase-0 reproduction

Run from this repository in Ubuntu WSL. External ORFS and FAN_ATPG checkouts are kept outside this Git repository; set the three environment variables to the qualified installations before reproducing the observed s5378/s9234 subset:

```bash
bash scripts/collect_versions.sh
export PACT_ORFS_ROOT=/path/to/OpenROAD-flow-scripts
export PACT_FAN_ATPG_ROOT=/path/to/FAN_ATPG
export PACT_VENV=/path/to/pact-venv
bash scripts/run_phase0.sh
```

`run_phase0.sh` intentionally returns status 2 after reproducing the available subset because the central conflict did not replicate and OpenROAD-native ordering was not extracted for these designs. To recheck saved campaigns without repeating physical implementation, run `bash scripts/finalize_phase0.sh`. See `reports/PHASE0_FINAL_REPORT.md` for measured results and `docs/methodology.md` for metric definitions.

## Historical research status

PACT is progressing through a staged qualification process for physical- and ATPG-aware scan-architecture optimization.

### Phase-0C — Completed

Status: `PACT_PHASE0C_LEARNING_GATE_FAIL`

Phase-0C completed a frozen campaign over s5378, s9234, and s15850; five conditional physical seeds; and K in {1, 2, 4, 8}. All 375 planned architecture routes were attempted and qualified with zero detailed-route DRC. The campaign established reproducible physical/activity conflict, cross-seed and cross-design replication, and large legal search spaces. It did not establish that learned optimization is scientifically necessary: the frozen deterministic portfolio covered the observed Pareto set, and the tested local-swap intervention was insufficiently rich. No ML model was trained.

### Phase-0D — Pilot Completed; Optimizer v1 Qualified

Pilot status: `PILOT_COMPLETE_NO_ROUTE_QUALIFIED`

Phase-0D studies richer legal interventions and budgeted deterministic search using a structural-check, analytical-proxy, Pareto-filter, and selective-route funnel. Its primary question is:

> Under bounded compute and physical-evaluation budgets, do deterministic search methods leave a reproducible optimization gap large enough that investigating learned guidance is scientifically justified?

The frozen one-context pilot verified all seven intervention classes and all 117 ATPG target reconstructions. Four equal-budget deterministic searches completed 32 logical search evaluations; early stopping occurred after eight evaluations per method. No child was nondominated against the qualified Phase-0C `P` start, so the frozen filter selected no new physical route. The naive maximum-budget campaign projects to roughly 70 serial hours and was not launched.

This pilot is not a Phase-0D PASS or FAIL decision. Current evidence and progress are in `reports/phase0d/STATUS.md` and `reports/phase0d/PILOT_REPORT.md`.

### Optimizer v1 milestone

Optimizer-v1 status: `PACT_OPTIMIZER_V1_PROXY_ADVANCE`

Routed status: `PACT_OPTIMIZER_V1_ROUTE_QUALIFIED`

The Phase-0D pilot showed that bounded small local perturbations around the physically optimized `P` architecture did not produce a new nondominated solution in the tested context. PACT therefore now treats scan-architecture generation directly as a multi-objective synthesis problem rather than attempting to justify ML a priori.

Optimizer v1 combines:

- global physical/activity-aware construction from empty balanced chains;
- large-neighborhood destroy/repair search;
- a fixed-K Pareto archive over the physical proxy and exact H_eff8;
- bounded, resumable wall-clock optimization; and
- selective physical validation.

The frozen 60-second s5378/seed11/K2 experiment exactly evaluated 24 unique generated architectures and added five points to the combined Phase-0C/PACT proxy Pareto front. The selected balanced/activity representative (2157.81 µm HPWL proxy, H_eff8 59.0) then qualified after routing with zero detailed-route DRC and an exact structural reconstruction pass. HPWL remains a proxy; routed physical evidence is reported separately.

For fixed K, the primary objectives are physical scan cost and effective shift activity. K remains a higher-level architecture variable controlling scan parallelism and test time. Phase-0D is not finished: the next experiment is a frozen-parameter transfer test on s9234/seed11/K2, not a broad benchmark campaign.

ML has not been introduced. It will only be considered later if a working deterministic optimizer demonstrates that candidate-evaluation cost is itself the limiting factor. See `reports/phase0d/optimizer_v1/OPTIMIZER_V1_REPORT.md` and `reports/phase0d/optimizer_v1/OPTIMIZER_V1_METHOD.md`.
