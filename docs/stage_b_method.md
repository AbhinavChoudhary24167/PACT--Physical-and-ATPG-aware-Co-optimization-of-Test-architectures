# Stage-B method interface

Stage B constrains port-inclusive scan HPWL relative to the routed-best B2/B3T reference, then retains E, H4, H8 and balanced endpoint winners. Exact reversed B3T capacities are preserved. The portable interface reconstructs the frozen candidate-stateful model; physical qualification is separate.

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1 python scripts/pact_stage_b_search.py --input results/pact_stage_b/inputs/s5378.json.gz --output scratch/stage_b/s5378 --seconds 300 --epsilons 0.02 0.05 0.10
```

Use the corresponding s9234/s15850 input. Defaults: seed 11, 20,000 evaluations, 2,000 stagnation attempts, 16 neighbors, segment limit 8, 16 archive slots, 150-attempt lane restarts and equal balanced weights. Model loading/initialization/final replay are outside the mutation-loop timer; indivisible evaluation can finish after it. Saved orders preserve measured selections because host-dependent stopping changes endpoints.

Saved CSVs cover all winners, routed selections, exact dominance/deltas, prediction transfer and s15850 omitted-background diagnostics. Predictor inputs and measured labels stay separate. See [methodology](methodology.md), [recorded report](../results/pact_stage_b/REPORT.md) and [reproducibility](reproducibility.md).
