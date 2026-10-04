# PACT

**Physical and ATPG-aware Co-optimization of Test Architectures.** PACT is a deterministic research tool for constructing legal scan orders, optimizing physical/activity tradeoffs and qualifying implementations with OpenROAD/ORFS and stored FAN ATPG workloads.

## Motivation and key idea

Short scan wire need not mean low switching hotspots. PACT preserves FF membership, capacities, clock domains and serial load/unload semantics while searching physical cost and separate activity objectives. Proxy improvements must survive implemented measurement.

## Architecture / workflow

Architecture + stored workload → candidate evaluation → bounded search → selective physical implementation → measured comparison. PACT includes an exact incremental M3/M5 working solver, bounded candidate-stateful evaluator, Stage-B physical-budget activity lanes, scan-only export, independent workload replay and topology/functional/FF/routing qualification. See [architecture](docs/architecture.md) and [methodology](docs/methodology.md).

## Current status

Saved records at `f2569d498cd5f26a88c4954ec163498eb3cf7d91` support completed Stage A (`PACT_STAGE_A_PHYSICAL_RESULTS_COMPLETE`, `PACT_EXTERNAL_BENCHMARK_COMPLETE`) and later Stage B (`PACT_STAGE_B_MULTI_DESIGN_CONVERGENCE`), with nine qualified Stage-B selections across s5378/s9234/s15850. The research program remains in progress: full-network hotspot prediction and complete detected-fault identity equivalence remain unresolved. [Research status](docs/research_status.md) is canonical.

## Repository structure

| Path | Purpose |
|---|---|
| `src/pact/` | Solver, scan/activity/physical models and integration |
| `scripts/`, `tests/` | Current runners, adapters and essential regressions |
| `config/`, `experiments/`, `benchmarks/` | Schemas, physical settings and provenance |
| `artifacts/` | Minimal placed/workload inputs and fixtures |
| `results/pact_stage_b/`, `results/stage_a/` | Portable current inputs/orders and compact measured comparisons |
| `docs/` | Canonical user/research documentation |
| `reports/repository_cleanup/` | Storage audit, decisions and validation |

## Requirements and installation

Python 3.11+ and numerical dependencies support portable workflows/tests. Physical work additionally needs Linux/WSL, qualified OpenROAD/ORFS, FAN_ATPG and Icarus Verilog.

```sh
python -m venv .venv
# Linux/WSL: source .venv/bin/activate
# PowerShell: .venv/Scripts/Activate.ps1
python -m pip install -e '.[optimizer,dev]'
```

Dependency pins and configurable locations are in [installation](docs/installation.md).

## Quick start / running PACT

```sh
pact-optimize --synthetic 64 --chains 2 --time-budget 1 --output scratch/example
python -m pact.cli validate-scan --architecture scratch/example/optimized.architecture.json
python -m pytest -q
```

This is an algorithm example, not research evidence. Use `pact-optimize --help`, `pact-integrate --help` and [usage](docs/usage.md) for real input/integration workflows.

## Reproducing current experiments and benchmarks

```sh
python scripts/verify_reproducibility.py
python scripts/pact_stage_b_search.py --input results/pact_stage_b/inputs/s5378.json.gz --output scratch/stage_b/s5378 --seconds 300 --epsilons 0.02 0.05 0.10
```

The first command checks saved inputs/orders without a new search. The second runs the recorded method; use one numerical thread and fresh output. Wall-clock endpoints vary across hosts. See [experiment registry](docs/experiments.md), [baseline definitions](docs/benchmarks.md), [method](docs/stage_b_method.md) and [reproducibility](docs/reproducibility.md), including exact physical inputs not distributed publicly.

## Tests, limitations and research

`python -m pytest -q` runs unit and small integration regressions. External physical qualification requires separate tools/inputs. Current evidence is small Nangate45 designs, fixed workload/placement and K=2; it does not establish industrial stateful scaling, watts, IR-drop or signoff power/timing. Negative/dominated outcomes remain in the result tables. No learned model has been introduced. [History](docs/history.md) summarizes unsuccessful gates and corrected methodology.

## Contributing, citation and license

Preserve independent replay, topology invariants and the distinction between predicted and measured results; see [development](docs/development.md). No paper DOI is declared. Cite this repository, exact revision and experiment export using [CITATION.cff](CITATION.cff). PACT code is [MIT licensed](LICENSE); external tools/imported assets retain their own provenance and licensing.
