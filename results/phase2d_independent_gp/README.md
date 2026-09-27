# Phase-2D reproduction and artifact index

This is a separate experiment. Historical Phase-2C-R result directories are immutable inputs.
Completed execution stages refuse replacement; do not rerun a physical stage over existing files.

Execution order (Ubuntu-24.04 WSL, `/root/pact-deps/pact-venv/bin/python`):

1. `scripts/phase2d_preflight.py`: check historical hashes and snapshot both repaired result trees.
2. `scripts/phase2d_register.py`: freeze exact logical architecture IDs, scan orders, activity evidence, predictors, gates and the scratch-initialization protocol.
3. `scripts/phase2d_execute.py gp`: one fresh seed-29 initialization and independent placement per design.
4. `scripts/phase2d_execute.py prepare`: export the new DEF/graph, preserve frozen scan orders, prove coordinate differences and compare HPWL.
5. `scripts/phase2d_execute.py physical`: at most 21 exact-order route attempts; unchanged downstream routing, verification and extraction commands.
6. `scripts/phase2d_finalize.py environment`: tool capabilities, binary hashes and historical source-flow provenance.
7. `scripts/phase2d_finalize.py freeze`: hash execution/analysis sources before scoring.
8. `scripts/phase2d_execute.py topology`: every repaired topology assertion, with physical-source paths and seed selector adapted.
9. `scripts/phase2d_execute.py measure`: frozen predictors and scorer on the new placement; routed targets remain labels only.
10. `scripts/phase2d_execute.py report`: all 12 independent endpoints, all pairs, prior-seed comparisons and five PNG/PDF figure sets.
11. `scripts/phase2d_finalize.py finalize`: exhaustive preservation verification and final manifest.

Regression stages are `focused`, `regression`, `focused_phase2d`, and `regression_final`.
The latter two include the five new all-endpoint decision tests. Their isolated logs and JUnit XML are retained.
Environment: `PYTHONDONTWRITEBYTECODE=1`, `OPENBLAS_NUM_THREADS=1`,
`PYTHONPATH=src:/mnt/d/PACT_EXPERIMENTS/cache/phase2a_python`.

The installed OpenROAD binary has no native GP seed argument. The preregistered seed belongs to
Python's scratch initializer; the original movable floorplan instances must all be unplaced.
`-skip_initial_place` and removal of `-force_center_initial_place` retain those fresh coordinates
as the Nesterov global-placement initialization. No Phase-2C placed database is used as a physical
source. Detailed placement after the new global placement is the ordinary downstream flow,
not the historical perturb-and-legalize replica method.

The inherited route helper still uses the directory-name prefix `phase2c_s29_`. This is only a
filename under this experiment's new `raw/orfs` root. `route_adapter.json`, each rewire execution
record and the actual input paths establish that these cases start from Phase-2D placement B.

Logical identity is `frozen_architecture_id` plus `scan_order_sha256`. The physical architecture
serialization hash includes coordinates and therefore changes naturally. No chain is regenerated.

Primary artifacts:

- `contract.json`, `contract_freeze.json`: pre-outcome protocol and digest.
- `initial_integrity.json`, `final_integrity.json`: historical dependency and preservation checks.
- `initialization/`, `independent_placement_proof.json`, `environment.json`: causal ancestry and tool provenance.
- `placement_comparison.csv`: descriptive FF displacement, coordinate identity, HPWL and density.
- `physical_results.json`, `raw/`, `execution/`, `orfs/`: bounded attempts, all commands, logs, metrics, databases and SPEFs.
- `topology_results.json`, `ownership/`, `weights/`: full repaired assertions and placed-only feature witnesses.
- `raw_endpoint_results.csv`: separate endpoints for seeds 11/13/17 and independent GP 29.
- `pair_direction_results.csv`: independent pairs with reversals against every previous seed and descriptive 1% materiality.
- `per_architecture_results.csv`, `endpoint_comparison.csv`: raw scores, ranks and rho changes.
- `results.json`, `sensitivity_analysis.json`, `report.md`: decision, descriptive sensitivities and all mandatory direct answers.
- `figures/`: five requested figures as PNG and PDF.
- `manifest.sha256`, `result_provenance.json`: final cryptographic evidence index.

The original per-endpoint gates alone determine generalization; no historical seed, mean,
pair deletion, architecture deletion or negligible-effect label can rescue a failed endpoint.
No optimizer, ATPG rerun, Phase-3 or push is part of this experiment.
