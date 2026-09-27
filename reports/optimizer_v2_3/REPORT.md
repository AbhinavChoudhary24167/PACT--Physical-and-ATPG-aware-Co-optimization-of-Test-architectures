# PACT Optimizer-v2.3 Independent Parallel Pareto Search

**Classification:** `PACT_V2_3_PARALLEL_PARETO_ADVANCE`

The equal-evaluation result controls the scientific classification. Equal-wall results are reported separately and do not establish a search-quality advance merely by completing more work.

## Results

| Design | Budget | W | Exact evals | Archive | Unique | Best physical | Best H_eff8 | Hypervolume | Duplicate rate | Wall (s) | CPU util. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| s5378 | equal_evaluations | 1 | 64 | 6 | 6 | 1370.29 | 60.1667 | 80899.1 | 0.000% | 26.416 | 98.4% |
| s5378 | equal_evaluations | 2 | 64 | 4 | 4 | 1366.35 | 59.1667 | 84608.4 | 3.125% | 13.534 | 86.1% |
| s5378 | equal_evaluations | 4 | 64 | 4 | 4 | 1369.15 | 59.1667 | 79216.6 | 6.250% | 9.610 | 77.2% |
| s5378 | equal_wall | 1 | 71 | 6 | 6 | 1370.29 | 60.1667 | 80924.9 | 0.000% | 30.439 | 99.4% |
| s5378 | equal_wall | 2 | 156 | 6 | 6 | 1366.35 | 59.1667 | 85331.2 | 1.282% | 30.566 | 94.5% |
| s5378 | equal_wall | 4 | 278 | 7 | 7 | 1351.59 | 58.3333 | 89981.7 | 1.439% | 30.671 | 92.5% |
| s9234 | equal_evaluations | 1 | 64 | 9 | 9 | 1723.95 | 150.833 | 348277 | 0.000% | 22.759 | 98.6% |
| s9234 | equal_evaluations | 2 | 64 | 5 | 5 | 1723.57 | 152.5 | 329524 | 3.125% | 16.193 | 86.7% |
| s9234 | equal_evaluations | 4 | 64 | 5 | 5 | 1723.95 | 155.667 | 298994 | 6.250% | 10.783 | 71.8% |
| s9234 | equal_wall | 1 | 50 | 7 | 7 | 1723.95 | 150.833 | 347248 | 0.000% | 31.060 | 97.7% |
| s9234 | equal_wall | 2 | 105 | 5 | 5 | 1723.57 | 152.5 | 330826 | 1.905% | 30.834 | 93.4% |
| s9234 | equal_wall | 4 | 186 | 13 | 13 | 1723.57 | 153.167 | 327030 | 2.688% | 31.131 | 92.2% |
| s15850 | equal_evaluations | 1 | 64 | 11 | 11 | 3524.47 | 140.333 | 1.66536e+06 | 0.000% | 75.960 | 98.6% |
| s15850 | equal_evaluations | 2 | 64 | 8 | 8 | 3513.57 | 142.167 | 1.58489e+06 | 3.125% | 38.493 | 93.1% |
| s15850 | equal_evaluations | 4 | 64 | 14 | 14 | 3525.47 | 139.167 | 1.55255e+06 | 6.250% | 25.959 | 84.9% |
| s15850 | equal_wall | 1 | 27 | 4 | 4 | 3525.47 | 140.333 | 1.62242e+06 | 0.000% | 30.953 | 98.9% |
| s15850 | equal_wall | 2 | 51 | 6 | 6 | 3513.57 | 142.167 | 1.57718e+06 | 3.922% | 31.592 | 93.6% |
| s15850 | equal_wall | 4 | 104 | 9 | 9 | 3513.57 | 139.167 | 1.65542e+06 | 3.846% | 31.386 | 92.4% |

## Correctness and provenance

- Frozen v2.2 baseline: 146 tests passed.
- Post-change repository status: FULL_REPOSITORY_TESTS_PASS_157.
- Frozen host configuration: AMD Ryzen 7 7735HS, 8 physical / 16 logical cores; v2.2 real-search budget 12 exact evaluations and 16 local moves with the tiled H_eff8 backend (B=16, W=4).
- W=1 uses the existing serial v2.2 engine; W=2/W=4 use independent mutable state and deterministic lane seeds.
- Global Pareto membership uses only the two authoritative exact objectives and canonical serial merge order.
- No routing was launched.
- Additional qualified benchmark evidence: True.
- s5378 diversity improved: True.

## Storage

- Experiment root: `D:\PACT_EXPERIMENTS`
- Total bytes written to D: 5511344
- Peak experiment-directory size: 34566502 bytes
- Residual worker scratch: 0 bytes
- Cleanup: worker_scratch_cleaned_and_obsolete_smoke_outputs_pruned
- Large PACT-controlled file observed on C: False

## Remaining bottleneck

The exact tiled spatial convolution/correlation kernel remains the dominant numerical bottleneck; it was measured but deliberately not optimized in v2.3.

## Git

- Commit: `088dcbb1099788287ccec7dcd664da516bac8ad1`
- Status is recorded verbatim in `environment.json`.
