# Repository update — 2026-09-27

This update brings the existing development branch together with all remaining
unignored local work. The current product is the [working scan solver](working_optimizer.md);
its measured engineering status is [WORKING_SOLVER](../solution_status.md).
Earlier experiment reports retain their original results, terminology and
limitations. They describe completed historical work, not a new execution plan.

## Implementation included

- `src/pact/optimizer/` and `scripts/pact_optimize.py`: spatial construction,
  sparse local moves, exact incremental M3/M5 costs, a bounded Pareto archive,
  cooperative time budgets and exported scan architectures.
- `src/pact/phase0d/`: shared-frontier construction, tiled exact H_eff8 and
  independent parallel search for the earlier v2.1–v2.3 implementations.
  H_eff8 results must not be substituted for the working solver's M3/M5 results.
- `src/pact/experiment_storage.py`: configurable experiment storage and disk
  guards for the historical runners. `PACT_EXPERIMENT_ROOT` or the runner's
  `--experiment-root` overrides the workstation-specific default.
- `scripts/phase1*`, `scripts/phase2*`, related analysis modules and unit tests:
  the existing route, activity, topology-repair and placement experiment tools.

## Experiment index

| Work | Report / evidence |
|---|---|
| Current working solver, scaling and bounded routes | [Solution status](../solution_status.md), [saved outputs](../reports/working_solver/) |
| v2.1 shared-frontier constructors | [Report](../PACT_OPTIMIZER_V2_1_SHARED_FRONTIER_REPORT.md), [measurements](../reports/optimizer_v2_1/) |
| v2.2 parallel tiled exact activity | [Report](../PACT_OPTIMIZER_V2_2_PARALLEL_TILED_REPORT.md), [measurements](../reports/optimizer_v2_2/) |
| v2.3 independent parallel search | [Report](../reports/optimizer_v2_3/REPORT.md) |
| Multi-design routed comparisons | [Report](../PACT_PHASE1_MULTI_DESIGN_ROUTED_VALIDATION.md) |
| Shift-activity implementations | [Report](../PACT_PHASE2A_SHIFT_ACTIVITY_VALIDATION.md) |
| Initial physical/activity engineering | [Engineering report](../reports/phase2c/ENGINEERING_REPORT.md) |
| Seed-11 repaired output topology | [Final report](../results/phase2c_repair/FINAL_REPORT.md) |
| Perturb-and-legalize physical seeds | [Final report](../results/phase2c_repair_multiseed/FINAL_REPORT.md) |
| Independent global placement | [Report](../results/phase2d_independent_gp/report.md) |

## Evidence and storage

The update includes the previously untracked `results/` trees, including saved
OpenROAD outputs, logs, snapshots and earlier failed attempts. These trees total
approximately 1.5 GB before Git compression. No new physical experiments were
run for publication. Hashes and absolute workstation paths in historical
records remain unchanged; reproducing those executions requires their external
tools and inputs. A checkout alone is not a complete OpenROAD/ATPG installation.

The pre-existing removal of the generated
`artifacts/derived/phase0b/lib/NangateOpenCellLibrary_typical_dft.lib` and fourteen
compressed s9234 metric-campaign traces is recorded. Earlier Git revisions retain
those tracked files. Their absence must not be interpreted as a fresh successful
reproduction. The working solver accepts an external Liberty through `--liberty`.

Existing ignore rules remain in effect: dependency caches, temporary files,
selected large generated solver architectures, checkpoints and ignored physical
archives remain local. No ignored files were force-added. The complete current
real-design recommendations and compact synthetic measurements are versioned.

## Verification

The working-solver milestone passed 238 repository tests in 126.21 seconds.
The subsequent 10-test focused run passed in 8.93 seconds. Four real-run exports
passed independent rescoring; six newly selected routes passed structural checks
and had zero DRC errors. See [test evidence](../reports/working_solver/test_summary.json).
These runs already included the earlier local implementation and test files
now being committed. Publication does not introduce optimizer behavior changes;
the documentation update does not require repeating physical experiments.
