# PACT

**Physical and ATPG-aware Co-optimization of Test Architectures.** PACT constructs legal scan orders and searches physical cost and switching activity using stored ATPG workloads. It combines an exact incremental scan solver, bounded stateful logic evaluation and OpenROAD physical qualification.

Short scan wire need not mean low switching hotspots. PACT preserves flip-flop membership, chain capacities, clock domains and serial load/unload behavior while keeping physical cost, total activity and local peaks separate. Predicted gains are checked against implemented measurements.

## Quick start

Python 3.11+ supports the numerical workflows on Windows and Linux. Run from the repository root:

```sh
python -m venv .venv
# Linux/WSL: source .venv/bin/activate
# PowerShell: .venv/Scripts/Activate.ps1
python -m pip install -e '.[optimizer,dev]'
pact-optimize --synthetic 64 --chains 2 --time-budget 1 --output scratch/example
pact validate-scan --architecture scratch/example/optimized.architecture.json
python -m pytest -q
```

The [synthetic example](examples/synthetic/README.md) needs no physical-design tools. It demonstrates the algorithm; it is not benchmark evidence. Use a fresh output directory for each run. See [installation](docs/installation.md) for dependencies and [usage](docs/usage.md) for real inputs and `pact-integrate`.

## Current research status

| Scope | Retained evidence |
|---|---|
| Implemented | Exact incremental M3/M5 solver, candidate-stateful evaluation, Stage-B activity lanes under physical budgets, scan-only export and independent ATPG replay |
| Stage A measured | 19/19 selected records qualified; 27/30 indexed architectures qualified using the common Nangate45 backend |
| Stage B measured | Nine qualified routed selections across s5378, s9234 and s15850; all pass their routed wire budgets |
| In progress | Reliable full-network hotspot prediction, complete detected-fault identity equivalence and broader scaling |

These claims come from the [Stage-A completion receipt](results/pact_oss_benchmark/topology_recovery_20261004/completion.json) and [Stage-B measured report](results/pact_stage_b/REPORT.md). Several predicted hotspot gains fail to transfer physically, and some selections remain dominated by the original comparison front. [Research status](docs/research_status.md) explains the scope and negative outcomes. The research program remains in progress.

## Workflow

```text
Placed design + stored ATPG workload
                 |
                 v
     Physical and activity evaluation
                 |
                 v
      Constrained multi-objective search
                 |
                 v
       Candidate scan architecture
                 |
                 v
 OpenROAD implementation + independent replay
                 |
                 v
         Measured comparison
```

See [architecture](docs/architecture.md) and [methodology](docs/methodology.md). Physical qualification additionally requires the qualified Linux/WSL OpenROAD/ORFS, FAN_ATPG, simulation toolchain and exact physical inputs; these are not required for the synthetic example or package import.

## Reproducing current results

```sh
python scripts/verify_reproducibility.py
```

This checks retained input bindings, portable Stage-B bundles and saved architecture scores without starting a search or EDA campaign. [Reproducibility](docs/reproducibility.md) distinguishes portable replay from full physical reruns. [Stage-B method](docs/stage_b_method.md) documents the recorded search interface, while [benchmarks](docs/benchmarks.md) preserves exact upstream and local-repair provenance.

## Repository and documentation

| Path | Purpose |
|---|---|
| `src/pact/`, `scripts/`, `tests/` | Current models, entry points, adapters and regression coverage |
| `config/`, `experiments/`, `benchmarks/` | Schemas, physical settings and provenance |
| `examples/` | Small self-contained usage example |
| `artifacts/` | Minimal placed/workload inputs and structural fixtures |
| `results/stage_a/`, `results/pact_stage_b/` | Compact comparisons, portable inputs and selected orders |
| `docs/` | Canonical user and research documentation |
| `reports/` | Scientific evidence and repository maintenance audits |

Start with [installation](docs/installation.md), [usage](docs/usage.md) and [research status](docs/research_status.md). Continue with the [experiment registry](docs/experiments.md), [development guide](docs/development.md) and concise [history](docs/history.md).

## Limitations

Current measured evidence covers small Nangate45 designs, fixed workloads/placements and K=2. Bounded logic coverage and candidate capacitance errors limit hotspot prediction. Coverage/count agreement does not establish complete detected-fault identity equivalence. Switching proxies do not establish watts, IR-drop or signoff power/timing. No learned model is implemented.

## Contributing, citation and license

Contributions should preserve topology invariants, independent replay and the distinction between predicted and measured results; see [development](docs/development.md). Cite this repository, the exact revision and experiment export using [CITATION.cff](CITATION.cff); no publication DOI is declared. PACT code is [MIT licensed](LICENSE). External tools and imported assets retain their own attribution and licensing.
