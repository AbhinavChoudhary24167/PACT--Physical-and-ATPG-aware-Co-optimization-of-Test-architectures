# Usage

## Working optimizer

```sh
pact-optimize --synthetic 64 --chains 2 --time-budget 1 --output scratch/example
python -m pact.cli validate-scan --architecture scratch/example/optimized.architecture.json
```

This is an algorithm smoke example, not scientific evidence. Choose a fresh output namespace. The output contains supplied/optimized architectures, objective archive and constrained recommendation.

Real portable input uses `pact-optimize --input BUNDLE.json --chains K --time-budget 60 --output scratch/run`. A bundle names an architecture, complete binary pattern maps, ports/bounds and either a placed graph/Liberty or compiled functional-source arrays. `optimizer/io.py` rejects invented ports, mismatched FF sets and chain counts. The retained `--design s5378` adapter requires K=2 and external Nangate45 Liberty (`--liberty` or configured ORFS).

## Current stateful Stage B

[The method interface](stage_b_method.md) gives the frozen search command. `python scripts/verify_reproducibility.py` loads all three portable bundles, validates starts/selections, independently replays scores and checks retained input hashes without a new search or physical campaign.

## Implementation integration

`pact-integrate --help` describes qualified placed-design and explicit portable adapters. The qualified path consumes a saved working-solver recommendation, FAN patterns, FF identity map, DEF and frozen input hashes. Output includes a concrete scan-only patch, serial workload and independent replay. Route reuse is valid only for the exact architecture; missing archived databases are unavailable, not qualified reuse.

Physical replay needs the exact placed ODB/SDC, toolchain and functional circuit/library. [Reproducibility](reproducibility.md) explains recovery. Old receipt sealers describe deleted historical working directories and must not be used as current checkout inventories. Retained readers relocate historical paths in memory without altering original receipt bytes.
