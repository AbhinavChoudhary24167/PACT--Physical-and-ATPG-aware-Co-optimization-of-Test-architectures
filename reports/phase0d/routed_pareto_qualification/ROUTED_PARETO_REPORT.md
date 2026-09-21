# Phase-0D Routed Pareto Qualification

## Executive result

**`PACT_PHASE0D_ROUTED_PARETO_CONFIRMED`.** Exactly four previously unrouted Optimizer-v1 Pareto candidates were physically implemented; all four qualified, giving five QUALIFIED Optimizer-v1 points including the previously routed `1f1a3a458946...`. Routed Pareto improvement is established: `a78c6ce1a5a1...`, `75ea663523d9...`, and `1f1a3a458946...` are nondominated against all available Phase-0C P/T/J50/A routed baselines in routed full scan-path cost versus H_eff8 space.

## Experiment contract

- Benchmark: `s5378`
- Physical seed: `11`
- Scan chains: `K=2`
- No new optimization, no new architecture generation, and no ML
- Exactly four new OpenROAD routes; no reroute of `1f1a3a458946...` or Phase-0C
- Prior qualified evidence reused for Phase-0C P/T/J50/A and Optimizer-v1 `1f1a3a458946...`
- Same Nangate45/ORFS flow, seed-11 base placement, SDC, routing configuration, reconstruction rules, and metric extraction as the prior qualified Optimizer-v1 route
- Per-candidate cap 750 s; route-stage timeout 600 s

The repository began clean on the requested branch. Its effective pre-experiment HEAD was `386f25201c29d50d11ac18fe25cd334ff0e2667f`, not the prompt's `4242c0d5...`; `4242c0d5...` is its ancestor and the intervening merge changes only `README.md`, not scientific evidence.

## Proxy front

Lower is better for both objectives. The first four Phase-0C points are the frozen Phase-0C front; the five Optimizer-v1 points are the combined proxy front.

| Source | Architecture | HPWL proxy (µm) | H_eff8 |
|---|---|---:|---:|
| Phase-0C P | `bf4923662baa...` | 1380.830 | 63.333333 |
| Phase-0C T | `37deaa7b3eee...` | 1421.170 | 62.333333 |
| Phase-0C J50 | `9c54b48f2ab8...` | 2634.750 | 61.666667 |
| Phase-0C A | `16904eaa0db2...` | 6850.210 | 60.500000 |
| Optimizer-v1 | `44b1a2ab5a1e...` | 1180.750 | 64.833333 |
| Optimizer-v1 | `0348f2cc6b9d...` | 1305.770 | 62.833333 |
| Optimizer-v1 | `a78c6ce1a5a1...` | 1306.550 | 62.666667 |
| Optimizer-v1 | `75ea663523d9...` | 1319.110 | 60.833333 |
| Optimizer-v1 | `1f1a3a458946...` | 2157.810 | 59.000000 |

## Routed results

`Existing` means `MEASURED_EXISTING`; `New` means `MEASURED_NEW`. The physical cost is the existing qualified full scan-path routed net-length upper bound. All nine routes reconstructed 177 expected scan edges over 179 FFs and two chains, passed the membership/inventory bijection check and chain endpoint checks, completed global and detailed routing with zero overflow and zero DRC errors, and had positive setup and hold WNS. Exact scan-only routed length is `NOT_AVAILABLE` for every row because none of the 177 FF-to-FF links is an exclusive scan-only net after routing.

| Architecture | Evidence | Status | Proxy (µm) | H_eff8 | Routed scan cost (µm) | Full DRT WL (µm) | Vias | GRT util. | Setup WNS (ns) | Hold WNS (ns) | Route (s) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P `bf4923662baa...` | Existing | QUALIFIED | 1380.830 | 63.333333 | 5172.870 | 26691 | 13409 | 23.55% | 9.08788 | 0.00272910 | 78.419 |
| T `37deaa7b3eee...` | Existing | QUALIFIED | 1421.170 | 62.333333 | 5281.515 | 26781 | 13458 | 23.61% | 9.08786 | 0.00270743 | 77.896 |
| J50 `9c54b48f2ab8...` | Existing | QUALIFIED | 2634.750 | 61.666667 | 5911.570 | 27404 | 13488 | 24.17% | 9.08673 | 0.00273859 | 78.997 |
| A `16904eaa0db2...` | Existing | QUALIFIED | 6850.210 | 60.500000 | 9593.485 | 31158 | 13892 | 27.34% | 9.07944 | 0.00272724 | 86.470 |
| `44b1a2ab5a1e...` | New | QUALIFIED | 1180.750 | 64.833333 | 4891.025 | 26347 | 13337 | 23.25% | 9.08790 | 0.00273845 | 95.161 |
| `0348f2cc6b9d...` | New | QUALIFIED | 1305.770 | 62.833333 | 4892.570 | 26423 | 13395 | 23.25% | 9.08716 | 0.00272916 | 85.143 |
| `a78c6ce1a5a1...` | New | QUALIFIED | 1306.550 | 62.666667 | 4864.580 | 26395 | 13361 | 23.24% | 9.08775 | 0.00272829 | 78.971 |
| `75ea663523d9...` | New | QUALIFIED | 1319.110 | 60.833333 | 4872.250 | 26355 | 13395 | 23.24% | 9.08775 | 0.00272889 | 84.897 |
| `1f1a3a458946...` | Existing | QUALIFIED | 2157.810 | 59.000000 | 5494.140 | 26982 | 13469 | 23.81% | 9.08672 | 0.00273018 | 78.070 |

Routability counts for the five Optimizer-v1 proxy-front architectures: QUALIFIED 5; DRC_FAIL 0; TIMING_FAIL 0; STRUCTURAL_FAIL 0; FLOW_FAIL 0; PROVENANCE_BLOCKED 0.

## Proxy-to-route fidelity

Across all nine available qualified points, Pearson `r = 0.9959117686` and Spearman `rho = 0.8666666667`. Across the five Optimizer-v1 points alone, Pearson `r = 0.9855360175` but Spearman `rho = 0.2`. These are descriptive correlations for a deliberately tiny sample, not statistically conclusive results, and no significance claim is made. The high Pearson values are strongly influenced by the wider-range points; local rank fidelity among the tightly clustered new candidates is weak.

| Architecture | Proxy rank | Routed rank | Change | Routed − proxy (µm) | Increase vs proxy |
|---|---:|---:|---:|---:|---:|
| `44b1a2ab5a1e...` | 1 | 3 | +2 | 3710.275 | 314.23% |
| `0348f2cc6b9d...` | 2 | 4 | +2 | 3586.800 | 274.69% |
| `a78c6ce1a5a1...` | 3 | 1 | −2 | 3558.030 | 272.32% |
| `75ea663523d9...` | 4 | 2 | −2 | 3553.140 | 269.36% |
| P | 5 | 5 | 0 | 3792.040 | 274.62% |
| T | 6 | 6 | 0 | 3860.345 | 271.63% |
| `1f1a3a458946...` | 7 | 7 | 0 | 3336.330 | 154.62% |
| J50 | 8 | 8 | 0 | 3276.820 | 124.37% |
| A | 9 | 9 | 0 | 2743.275 | 40.05% |

The main local outlier is `44b1a2ab5a1e...`: it is best by proxy but only third by routed scan cost and is routed-space dominated. Conversely, `a78c6ce1a5a1...` moves from third to first in physical-cost rank. Thus the proxy is useful at broad scale here, but it is not a reliable fine-ordering metric for the closely spaced new points.

## Routed Pareto analysis

Using `(routed full scan-path net-length upper bound, H_eff8)` with both objectives minimized, the nondominated routed front is:

| Architecture | Routed scan cost (µm) | H_eff8 | Evidence |
|---|---:|---:|---|
| `a78c6ce1a5a1...` | 4864.580 | 62.666667 | MEASURED_NEW |
| `75ea663523d9...` | 4872.250 | 60.833333 | MEASURED_NEW |
| `1f1a3a458946...` | 5494.140 | 59.000000 | MEASURED_EXISTING |

No Phase-0C P/T/J50/A point remains nondominated after including the qualified Optimizer-v1 points. Two newly routed architectures survive directly on the routed front; the already-qualified Optimizer-v1 activity extreme remains the third front member. Successful routing and routed Pareto survival are separate findings; both happen here.

## Critical P-vs-75ea comparison

In frozen proxy space, `75ea663523d9...` improves on P by 61.72 µm (4.47%) in HPWL and by 2.5 (3.95%) in H_eff8. After routing, its full scan-path upper bound is 4872.25 µm versus P's 5172.87 µm: an improvement of 300.62 µm (5.81%). Both objectives remain lower, so the P-dominance result survives physical implementation.

## Verification and repository integrity

The full regression suite passed: **120 passed, 0 failed in 22.39 s**. The authoritative run used the installed Windows pytest with `src` inserted on `sys.path`; two prior environment probes stopped before test collection and therefore were not test failures. All 8,050 entries in the frozen Phase-0C hash manifest matched, with zero mismatches and zero missing files. The Phase-0D pilot manifest and Optimizer-v1 manifest each had zero mismatches, and Git showed no tracked changes to Phase-0C, Phase-0D pilot, or pre-existing Optimizer-v1 evidence. All four new route input hash maps and decompressed routed-ODB hashes verified. Credential-scan, new-artifact-hash, final git-status, and commit details are recorded in `run_manifest.json`, `new_evidence.sha256`, and the final task handoff. Raw logs, structured route metrics, routed structural proofs, and compressed routed ODBs for the four new runs are under `artifacts/raw/phase0d/optimizer_v1/s5378/s11/k2/<architecture_sha256>/`.

## Limitations

- One benchmark (`s5378`), one physical seed (`11`), and `K=2` only.
- Nine routed comparison points and only five Optimizer-v1 points: correlation is descriptive, not statistically conclusive.
- No scalability or generalization claim follows from this experiment.
- H_eff8 remains a test-activity objective/proxy according to its existing definition.
- Routing qualification establishes physical feasibility and routed Pareto behavior under this flow; it does not by itself establish industrial test-power integrity.
- The routed physical-cost measure is a conservative full-path net-length upper bound, not an exclusive scan-only wirelength.

## Next scientific decision

**Reproduce the routed result on s9234.** The s5378 result is sufficiently clean to justify an independent benchmark reproduction, but this report does not start that work.
