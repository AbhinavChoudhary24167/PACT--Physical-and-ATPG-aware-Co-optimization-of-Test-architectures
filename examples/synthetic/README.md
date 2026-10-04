# Synthetic scan optimization

After installing `.[optimizer,dev]`, run these commands from the repository root:

```sh
pact-optimize --synthetic 64 --chains 2 --time-budget 1 --output scratch/example
pact validate-scan --architecture scratch/example/optimized.architecture.json
```

The deterministic synthetic input has 64 flip-flops, two chains and binary target patterns. The optimizer writes supplied/optimized architecture JSON, raw objective results and a constrained recommendation. The second command reloads the selected architecture and checks membership, chains and endpoints. Use a fresh output directory to preserve earlier runs.

No OpenROAD, FAN_ATPG or PDK installation is needed. This is an algorithm smoke example, not a physical or scientific result. See [usage](../../docs/usage.md) for real workflows.
