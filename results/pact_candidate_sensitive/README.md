# PACT candidate-sensitive physical model

**PACT_CANDIDATE_SENSITIVE_NEW_FRONTIER_FOUND**

One bounded synthesis per design, one established placement/workload regime. Prior measured evidence is reused unchanged.

| Design | New architectures | Evaluations/s | ms/evaluation | Peak RSS MiB | Wire fF/um | Samples | Selected |
|---|---:|---:|---:|---:|---:|---:|---:|
| s5378 | 16537 | 88.02 | 11.361 | 222.1 | 0.064920 | 7 | 2 |
| s9234 | 6601 | 33.03 | 30.277 | 263.5 | 0.066939 | 7 | 2 |
| s15850 | 2733 | 9.88 | 101.255 | 577.4 | 0.065168 | 9 | 2 |

## Selected predictions and measurements

| Design | Hash | Frozen E | New E | Measured C·N | Frozen H8 | Propagated H8 | Measured H8 | Route um | Extends v2 frontier |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| s5378 | c11dfeee8d44 | 6154348.5409 | 14744347.8286 | 18542313.1900 | 74.0893 | 164.6442 | 177.6667 | 5166.1700 | False |
| s5378 | b72833ffdd2b | 6224984.5734 | 14865111.4638 | 18688484.8737 | 74.0893 | 168.8138 | 174.5503 | 5160.9150 | True |
| s9234 | 4d6ff90b2adc | 15357827.7960 | 30298138.5140 | 38160460.3309 | 136.7661 | 158.4089 | 192.6641 | 10671.6250 | False |
| s9234 | 1359e456272b | 15356327.9681 | 30302122.5884 | 38169211.1891 | 136.7661 | 157.2967 | 194.0487 | 10674.8300 | False |
| s15850 | 630da6943398 | 63795531.1542 | 111600805.1969 | 160267911.9852 | 129.8254 | 181.0448 | 271.5374 | 24295.4600 | False |
| s15850 | a3dd757a7e17 | 63767805.1417 | 111529152.5815 | 160122049.2135 | 132.7264 | 183.5374 | 270.5425 | 24280.3400 | True |

## Selection and interpretation

- s5378 `c11dfeee8d44`: predicted_dominates:J50; QUALIFIED.
- s5378 `b72833ffdd2b`: predicted_dominates:J50; QUALIFIED.
- s9234 `4d6ff90b2adc`: predicted_dominates:PACT; QUALIFIED.
- s9234 `1359e456272b`: predicted_dominates:PACT; QUALIFIED.
- s15850 `630da6943398`: predicted_dominates:v2_f3e118a35e7b; QUALIFIED.
- s15850 `a3dd757a7e17`: predicted_dominates:PACT; QUALIFIED.

## Measured frontier changes

| Design | New point | Prior frontier reference | Route delta % | C·N delta % | H8 delta % |
|---|---|---|---:|---:|---:|
| s5378 | b72833ffdd2b | PACT | -0.5529 | +0.6739 | +4.0212 |
| s5378 | b72833ffdd2b | c4eabc41cb50 | -0.0565 | +3.1512 | -10.4969 |
| s5378 | b72833ffdd2b | b5c4710dcf54 | +0.3874 | +1.4268 | -1.6676 |
| s5378 | b72833ffdd2b | 3b627d8af4f2 | -0.3856 | +6.8841 | -4.0021 |
| s15850 | a3dd757a7e17 | P | +0.7690 | -1.1195 | -2.3935 |
| s15850 | a3dd757a7e17 | J50 | -12.5802 | +10.2185 | +0.9516 |
| s15850 | a3dd757a7e17 | e14689c97ca5 | +0.6490 | -1.0381 | -2.5710 |
| s15850 | a3dd757a7e17 | f3e118a35e7b | +0.0631 | -0.1620 | -0.4815 |
| s15850 | a3dd757a7e17 | 1c4fe83a6b04 | +0.1324 | +0.1139 | -3.2880 |

## Prediction behavior on the selected pairs

The following compares the ordering of the two selected candidates within each design. A correct ordering on two points is only a diagnostic; it is not a validation campaign.

| Design | Metric | Frozen pair ordering | Candidate-sensitive pair ordering |
|---|---|---|---|
| s5378 | E | correct | correct |
| s5378 | H8 | tied | reversed |
| s9234 | E | reversed | correct |
| s9234 | H8 | tied | reversed |
| s15850 | E | correct | correct |
| s15850 | H8 | reversed | reversed |

Improved electrical coverage and a newly measured frontier point do not guarantee better ranking. In particular, replacing a tied frozen H8 estimate with distinct values is useful information only when the ordering survives physical implementation. Remaining ranking errors must be preserved alongside successful frontier extensions.

All supplied measured architectures, including the strongest v2 candidates, were rescored with the new model before selection. Only genuinely new predicted nondominated points were eligible; the quota was a maximum.

New architecture counts above exclude every order in the entire previous v2 evaluation log, not just the starting seeds. Every selected order is also verified absent from that prior corpus. Search JSON retains its original seed-relative unique count. Runtime rates in the table include final reference checks; summary JSON also gives mutation-loop-only cost.

The CSV records both predictors and every measured metric for retained candidates and stored measured references. Per-design compressed logs record every evaluated order hash, parent hash, operator, feasibility, acceptance and score. Summary JSON includes paired relative prediction errors against each prior frontier point; smaller error on this selected sample does not establish general predictive validity or isolate the effect of the model from search stochasticity.

The electrical model partitions actual Liberty input pins exactly and apportions shared extracted ground capacitance by functional/total HPWL. Candidate scan load is the measured median scan-only ground capacitance per Manhattan micrometre times candidate edge length, plus actual SI/port-buffer input capacitance. Transparent descendants and one combinational level use precomputed spatial influence; the latter uses normalized uniform Boolean sensitivity. No new fitted proxy, random workload, ATPG run, physical seed sweep or timing model is introduced.

See `docs/pact_candidate_sensitive_model.md` for equations, limitations and implementation. Search/route/measurement commands, hashes, versions, configuration and runtimes are bound in the per-design and per-candidate manifests. The historical physical measurement implementation is unchanged.

Remaining bottlenecks are shared-route geometry, candidate buffer insertion/resizing, input-state correlation and switching beyond the first combinational level. A next implementation milestone should improve bounded state-aware cone propagation and shared-net geometry using these selected implementations as diagnostics, preserving the existing route budget.
