# Large unseen design results

Both s38584 and s38417 completed three cold-search lanes. Three candidates per design were frozen before physical implementation, and all six passed the existing topology, routing, DRC, timing, FAN and exact compact activity checks.

The preregistered secondary s38417 CS_C2 reduced E by 0.3164%, H4 by 2.4396% and H8 by 0.9961%, with 1.0144% more routed scan wirelength. It had zero DRC errors, nonnegative setup/hold WNS and 96% fault coverage. The other five candidates produced mixed activity tradeoffs. The balanced CS_C1 candidates remain the primary roles; no candidate was selected after routed outcomes.

These measured outcomes support `PACT_LARGE_UNSEEN_GENERALIZATION_CONFIRMED` for these two designs at seed 11. They do not establish universal improvement or independent replication across circuit families.

| Design | Reference | Candidate | Routed scan WL (um) | ΔWL % | E | ΔE % | H4 | ΔH4 % | H8 | ΔH8 % | WNS (ns) | Hold WNS (ns) | DRC | Fault coverage % | Search runtime (s) | Peak RSS (KiB) | Qualification |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| s38584 | REF_B3T | Reference | 97311.1 | 0 | 1.78323e+09 | 0 | 2320.401 | 0 | 796.9224 | 0 | 8.49908 | 6.77236e-06 | 0 | 93.33 | — | — | QUALIFIED_EXTERNAL_REFERENCE |
| s38584 | REF_B3T | CS_C1 | 97819.24 | 0.5221809 | 1.777742e+09 | -0.3077776 | 2273.139 | -2.036817 | 803.5613 | 0.833073 | 8.49904 | 0.000728612 | 0 | 93.33 | 4398.995 | 2518736 | QUALIFIED |
| s38584 | REF_B3T | CS_C2 | 97770.38 | 0.4719708 | 1.775639e+09 | -0.4257068 | 2323.696 | 0.1419931 | 813.0647 | 2.025575 | 8.49866 | 0.000689671 | 0 | 93.33 | 4398.995 | 2518736 | QUALIFIED |
| s38584 | REF_B3T | CS_C3 | 97867.34 | 0.57161 | 1.777922e+09 | -0.2976469 | 2289.076 | -1.349986 | 803.2444 | 0.7932962 | 8.49945 | 6.77236e-06 | 0 | 93.33 | 4398.995 | 2518736 | QUALIFIED |
| s38417 | REF_B2 | Reference | 36842.35 | 0 | 1.391035e+09 | 0 | 2094.429 | 0 | 813.5087 | 0 | 8.72304 | 0.00316436 | 0 | 96 | — | — | QUALIFIED_EXTERNAL_REFERENCE |
| s38417 | REF_B2 | CS_C1 | 37289.89 | 1.21473 | 1.391283e+09 | 0.01785289 | 2051.776 | -2.036527 | 814.4839 | 0.1198758 | 8.72304 | 0.00316436 | 0 | 96 | 3887.367 | 2271204 | QUALIFIED |
| s38417 | REF_B2 | CS_C2 | 37216.09 | 1.01443 | 1.386634e+09 | -0.3163979 | 2043.333 | -2.439634 | 805.4053 | -0.9961037 | 8.72282 | 0.00307385 | 0 | 96 | 3887.367 | 2271204 | QUALIFIED |
| s38417 | REF_B2 | CS_C3 | 37191.46 | 0.947578 | 1.389957e+09 | -0.0774896 | 2054.843 | -1.890054 | 813.56 | 0.006313569 | 8.72304 | 0.00316436 | 0 | 96 | 3887.367 | 2271204 | QUALIFIED |

The CSV and JSON in `results/large_unseen` retain the numeric measurements at full stored precision. E/H4/H8 are the registered activity proxies; E is not a joule measurement. WNS follows the existing global-route timing stage.

Search runtime and peak RSS describe the entire design search worker and are repeated for its candidates. They are not additive per-candidate runtimes. s38584 completed 803 exact evaluations and s38417 completed 1017. Reference rows have no PACT search runtime.

K=2, seed=11, epsilon lanes 0.02/0.05/0.10, 900-second mutation-loop budgets and 7200-second search-worker ceilings stayed fixed. An in-flight exact evaluation may finish after the mutation-loop budget. Objectives, operators, acceptance, H4/H8, FAN workload and qualification gates were unchanged.

Search epsilon screens predicted wirelength. Actual routed wirelength and every activity regression are reported separately; no new routed-wire gate was introduced. No historical qualification campaign or reference simulation was repeated.
