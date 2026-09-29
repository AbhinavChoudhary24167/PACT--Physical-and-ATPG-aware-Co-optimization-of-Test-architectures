# PACT candidate_stateful

**Implementation:** PACT_CANDIDATE_STATEFUL_MODEL_COMPLETE

**Physical outcome:** PACT_CANDIDATE_STATEFUL_NEW_FRONTIER_FOUND

Parent commit: `70b7d06a5c1325663afe71d43a959f1ca9ee004d`. The delivery commit is identified in Git history and the final engineering response. Exact commands, dependencies and source/input hashes are in each design’s model contract, inputs and execution manifests.

## Direct engineering answers

1. **Bounded exact state-aware propagation:** implemented, with a fixed production bound of three nontransparent levels. See MODEL.md for the settled-state and coverage limits.
2. **Q/QN:** separate packed binary waveforms; QN is the logical complement of Q.
3. **Simultaneous changes:** gates evaluate all actual cached fanin states in topological order, including multiple changed inputs. Cancellation and represented reconvergence are preserved.
4. **Shared geometry:** candidate SI/SO endpoints join retained terminals on an MMST net; no independent scan star branch is added.
5. **Baseline reproduction:** every reconstructed baseline terminal set is checked, and every measured ground value is reproduced, including retained zero-span ground. Per-net calibration and explicit fallbacks are audited.
6. **Evaluation cost:** measured mutation-loop costs and ratios to the previous candidate-sensitive run appear below; these are observations on this machine, not isolated performance benchmarks.
7. **Novel architectures:** counts exclude canonical hashes reconstructed and verified from both complete previous evaluation corpora.
8. **Routed architectures:** only the novel predicted nondominated selections in the table below, at most two per design.
9. **Measured frontier:** 3 new qualified points extend the combined existing measured frontier; see the outcome table.
10. **E ordering:** unchanged on the historical diagnostic set: 26/28, 28/28 and 28/28 pairs correct for s5378, s9234 and s15850 respectively, for both models.
11. **H8 ordering:** improves from 17/28 to 27/28 correct pairs on s5378, 7/28 to 9/28 on s9234, and 17/28 to 19/28 on s15850. This is a fixed-model diagnostic, not predictor validation.
12. **Remaining ranking failures:** the previous s5378 selected-pair H8 reversal is resolved; s9234 becomes an unresolved predicted tie; s15850 remains reversed. Every pair and ordering change is retained in pairwise_diagnostics.csv and summary.json.
13. **Remaining error mechanisms:** unrepresented fanins/deeper logic, settled-state omission of glitches, and candidate changes to routing/buffer sizing/insertion. These are model omissions, not experimentally isolated causal attributions.
14. **Largest implementation-readiness blocker:** unreliable implemented hot-spot ordering, especially on s9234. The next missing physical mechanism is candidate-dependent buffer insertion/resizing and its effect on routed shared-net capacitance and spatial attribution. Deeper logic and event/glitch activity also remain absent; these observations do not establish which omission causes each error.

## Search and coverage

| Design | Trials | New canonical architectures | ms/trial | Relative cost | Peak RSS MiB | Gates at depths 0/1/2/3 |
|---|---:|---:|---:|---:|---:|---|
| s5378 | 397 | 371 | 453.586 | 43.36x | 304.2 | 301/314/303/182 |
| s9234 | 203 | 0 | 887.201 | 34.03x | 373.0 | 298/314/233/169 |
| s15850 | 53 | 39 | 3364.843 | 56.08x | 982.4 | 654/463/531/353 |

s9234 found no canonical architecture absent from the complete prior corpus before its wall-clock ceiling; no route slot was filled for that design. The production searches ran concurrently with one thread per numerical library; the cost ratios include reference checks, evidence logging and host contention.

| Design | Initialization s | Search + final checks s | Total search command s | Scan waveform s | Gate propagation s | Geometry s | Spatial updates s | Rollback s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| s5378 | 5.936 | 191.194 | 204.081 | 5.689 | 3.985 | 0.290 | 74.147 | 73.133 |
| s9234 | 8.570 | 189.323 | 202.028 | 6.439 | 2.180 | 0.176 | 77.545 | 75.393 |
| s15850 | 34.311 | 225.963 | 290.495 | 8.154 | 1.463 | 0.079 | 83.117 | 70.507 |

Spatial field accumulation and rollback dominate measured evaluator time. The 180-second ceiling applies to the mutation loop; initialization, one in-flight mutation and required final reference checks add overhead. No additional production run was performed to improve throughput.

| Design | Accepted / rejected trials | Changed FF waveforms A / R | Gate recomputations A / R | Cancellations A / R | Represented Q / QN nets | Excluded gate outputs |
|---|---|---|---|---|---|---:|
| s5378 | 16 / 381 | 1518 / 43704 | 7954 / 225624 | 610 / 13869 | 179 / 0 | 658 |
| s9234 | 7 / 196 | 950 / 27108 | 4276 / 118790 | 286 / 7383 | 211 / 0 | 1368 |
| s15850 | 9 / 44 | 2403 / 14952 | 8112 / 45875 | 276 / 1538 | 534 / 0 | 2439 |

These three mapped baselines have no connected QN output nets; the dedicated Q/QN and reconvergence fixtures exercise both polarities. Per-FF reachability and per-architecture Q/QN energy contributions remain in model_contract.json and summary.json.

## Historical diagnostic table

No historical route or measurement was repeated. E columns use millions of fF·transitions; H8 uses fF·transitions per bin/cycle. Absolute errors for every row are in comparison.csv.

| Design | Architecture | Frozen E | Sensitive E | Stateful E | Measured E | Frozen H8 | Sensitive H8 | Stateful H8 | Measured H8 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| s5378 | P | 6.5516 | 15.5695 | 16.2021 | 19.3755 | 74.0893 | 169.0817 | 174.6760 | 186.5643 |
| s5378 | J50 | 6.1194 | 15.2539 | 15.6704 | 18.6337 | 74.0893 | 174.1118 | 163.4257 | 176.1684 |
| s5378 | PACT | 6.2889 | 15.0718 | 15.5871 | 18.5634 | 74.0893 | 162.7506 | 158.2918 | 167.8027 |
| s5378 | c4eabc41cb50 | 5.9541 | 14.3912 | 15.0561 | 18.1176 | 74.0893 | 171.4425 | 181.7455 | 195.0216 |
| s5378 | b5c4710dcf54 | 6.1087 | 14.6783 | 15.3343 | 18.4256 | 74.0893 | 174.6565 | 168.8892 | 177.5105 |
| s5378 | 3b627d8af4f2 | 5.7135 | 13.8234 | 14.5327 | 17.4848 | 74.0893 | 172.3974 | 173.6364 | 181.8272 |
| s5378 | c11dfeee8d44 | 6.1543 | 14.7443 | 15.4316 | 18.5423 | 74.0893 | 164.6442 | 163.7201 | 177.6667 |
| s5378 | b72833ffdd2b | 6.2250 | 14.8651 | 15.5539 | 18.6885 | 74.0893 | 168.8138 | 161.8197 | 174.5503 |
| s9234 | T | 15.9394 | 31.3990 | 29.0100 | 39.3431 | 142.7131 | 183.9647 | 182.9812 | 192.0393 |
| s9234 | J50 | 14.3369 | 28.9601 | 26.3705 | 36.4532 | 151.7292 | 175.7465 | 182.3334 | 197.3931 |
| s9234 | PACT | 15.6606 | 30.9548 | 28.5813 | 38.8815 | 139.3301 | 184.1951 | 183.2559 | 188.3433 |
| s9234 | 53bb5b018758 | 15.7572 | 31.0363 | 28.7507 | 39.0925 | 139.3301 | 177.8160 | 174.1670 | 190.5728 |
| s9234 | 797aff0b91f6 | 15.4097 | 30.3795 | 28.1146 | 38.2632 | 132.7539 | 171.5599 | 168.8731 | 191.1814 |
| s9234 | f4bca5652bda | 14.9856 | 29.5287 | 27.4240 | 37.5122 | 139.3301 | 177.2299 | 172.3148 | 190.5031 |
| s9234 | 4d6ff90b2adc | 15.3578 | 30.2981 | 28.0435 | 38.1605 | 136.7661 | 158.4089 | 162.0639 | 192.6641 |
| s9234 | 1359e456272b | 15.3563 | 30.3021 | 28.0454 | 38.1692 | 136.7661 | 157.2967 | 162.0639 | 194.0487 |
| s15850 | P | 64.7377 | 112.8735 | 113.2206 | 161.9348 | 142.3448 | 192.9146 | 230.2748 | 277.1768 |
| s15850 | J50 | 54.8224 | 100.7263 | 101.2836 | 145.2769 | 129.0253 | 200.5060 | 228.2107 | 267.9924 |
| s15850 | PACT | 63.9643 | 111.8768 | 112.1769 | 160.4748 | 141.6561 | 195.6953 | 227.4215 | 277.0502 |
| s15850 | e14689c97ca5 | 64.6525 | 112.7179 | 113.0794 | 161.8017 | 142.3448 | 192.9146 | 229.2901 | 277.6818 |
| s15850 | f3e118a35e7b | 63.8362 | 111.6731 | 111.9653 | 160.3819 | 128.4636 | 187.8498 | 227.4215 | 271.8514 |
| s15850 | 1c4fe83a6b04 | 63.6783 | 111.3802 | 111.7308 | 159.9398 | 141.6561 | 196.5328 | 235.0196 | 279.7404 |
| s15850 | 630da6943398 | 63.7955 | 111.6008 | 111.8425 | 160.2679 | 129.8254 | 181.0448 | 226.9534 | 271.5374 |
| s15850 | a3dd757a7e17 | 63.7678 | 111.5292 | 111.7958 | 160.1220 | 132.7264 | 183.5374 | 227.4215 | 270.5425 |

| Design | Sensitive E MAE (million) | Stateful E MAE (million) | Sensitive H8 MAE | Stateful H8 MAE |
|---|---:|---:|---:|---:|
| s5378 | 3.6792 | 3.0579 | 9.9017 | 11.3634 |
| s9234 | 7.8771 | 10.1919 | 18.8160 | 18.5866 |
| s15850 | 48.2278 | 47.8881 | 82.8222 | 45.1950 |

Absolute E error increases for s9234 even though its E ordering remains correct. Bounded-state exactness does not imply completeness of the measured whole-design field.

## Pairwise ordering diagnostics

| Design | Scope | Metric | Sensitive correct / reversed / tied | Stateful correct / reversed / tied |
|---|---|---|---|---|
| s5378 | all_measured | E | 26/2/0 | 26/2/0 |
| s5378 | all_measured | H8 | 17/11/0 | 27/1/0 |
| s5378 | previous_sensitive_selected_pair | E | 1/0/0 | 1/0/0 |
| s5378 | previous_sensitive_selected_pair | H8 | 0/1/0 | 1/0/0 |
| s9234 | all_measured | E | 28/0/0 | 28/0/0 |
| s9234 | all_measured | H8 | 7/21/0 | 9/18/1 |
| s9234 | previous_sensitive_selected_pair | E | 1/0/0 | 1/0/0 |
| s9234 | previous_sensitive_selected_pair | H8 | 0/1/0 | 0/0/1 |
| s15850 | all_measured | E | 28/0/0 | 28/0/0 |
| s15850 | all_measured | H8 | 17/10/1 | 19/6/3 |
| s15850 | previous_sensitive_selected_pair | E | 1/0/0 | 1/0/0 |
| s15850 | previous_sensitive_selected_pair | H8 | 0/1/0 | 0/1/0 |

Remaining stateful reversals (all historical measured pairs):

- s5378 E: J50 / b72833ffdd2b; PACT / b72833ffdd2b.
- s5378 H8: b5c4710dcf54 / c11dfeee8d44.
- s9234 E: none.
- s9234 H8: T / J50; T / PACT; T / 4d6ff90b2adc; T / 1359e456272b; J50 / PACT; PACT / 53bb5b018758; PACT / 797aff0b91f6; PACT / f4bca5652bda; PACT / 4d6ff90b2adc; PACT / 1359e456272b; 53bb5b018758 / 797aff0b91f6; 53bb5b018758 / 4d6ff90b2adc; 53bb5b018758 / 1359e456272b; 797aff0b91f6 / f4bca5652bda; 797aff0b91f6 / 4d6ff90b2adc; 797aff0b91f6 / 1359e456272b; f4bca5652bda / 4d6ff90b2adc; f4bca5652bda / 1359e456272b.
- s15850 E: none.
- s15850 H8: P / e14689c97ca5; J50 / PACT; J50 / f3e118a35e7b; J50 / 630da6943398; J50 / a3dd757a7e17; 630da6943398 / a3dd757a7e17.

## New physical implementations

| Design | Hash | Selection reason | Stateful E (million) | Stateful H8 | Measured E (million) | Measured H8 | Routed path upper bound um | Frontier extension |
|---|---|---|---:|---:|---:|---:|---:|---|
| s5378 | 42dfdefa6950 | predicted_dominates:J50 | 15.5037 | 158.2918 | 18.4688 | 167.9856 | 5180.620 | False |
| s5378 | b2614a3a06b3 | predicted_dominates:J50 | 15.4924 | 158.2918 | 18.4453 | 167.0995 | 5168.530 | True |
| s15850 | 5d90e5faf9dc | predicted_new_tradeoff | 112.9976 | 230.2748 | 161.6728 | 277.4584 | 24122.050 | True |
| s15850 | f47e6837c4da | predicted_new_tradeoff | 112.9884 | 230.2748 | 161.5876 | 277.5690 | 24180.440 | True |

| Design | Hash | DRC | Setup ns | Hold ns | Topology / functional / FF checks | Fully qualified |
|---|---|---:|---:|---:|---|---|
| s5378 | 42dfdefa6950 | 0 | 9.08654 | 0.00271005 | PASS / PASS / PASS | True |
| s5378 | b2614a3a06b3 | 0 | 9.08656 | 0.00272901 | PASS / PASS / PASS | True |
| s15850 | 5d90e5faf9dc | 0 | 8.13298 | 0.000720604 | PASS / PASS / PASS | True |
| s15850 | f47e6837c4da | 0 | 8.13227 | 0.000720604 | PASS / PASS / PASS | True |

Timing uses the unchanged adapter’s available global-route setup/hold values. Wire qualification uses the routed full scan-path net-length upper bound, retaining shared-net accounting from the existing measurement pipeline.

- New s5378 selected pair: E correct, H8 predicted_tie.
- New s15850 selected pair: E correct, H8 predicted_tie.

The implementation provides architecture → exact scan states → bounded state-aware switching → shared candidate capacitance → search → routing → physical qualification. Exactness applies to represented settled Boolean states, not delay/glitch/signoff prediction. Scientific outcome is reported independently of implementation completion; neither causality nor predictor validation is claimed.

## Execution and evidence

One prepare and one search per design; no depth sweep, placement change, ATPG regeneration, seed sweep or historical reroute. The search command was:

```sh
export PYTHONPATH=.optimizer-deps:src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/root/pact-deps/pact-venv/bin/python
$PY scripts/pact_candidate_stateful.py prepare --design <design>
$PY scripts/pact_candidate_stateful.py search --design <design> --seconds 180 --max-evaluations 20000 --route-limit 2
$PY scripts/pact_candidate_stateful.py route --design <design> --route-seconds 600
$PY scripts/pact_candidate_stateful.py measure --design <design>
$PY scripts/pact_candidate_stateful.py report
$PY scripts/pact_candidate_stateful.py seal
$PY -m pytest -q tests/unit/test_candidate_stateful.py
$PY -m pytest -q --junitxml=results/pact_candidate_stateful/repository_tests.xml
```

WSL distribution: Ubuntu-24.04. The route/measure commands ran only for s5378 and s15850. The full repository suite passed 294 tests; its JUnit record includes elapsed time. Python/NumPy/Numba/SciPy versions are recorded per design; physical tool versions and exact commands are recorded in the unchanged adapters’ route/measurement manifests.

Read-only historical diagnostics precede all new routes. Complete canonical prior identities and trace checks are in prior_corpus files. Baseline and selected geometry audits, every changed-net record, accepted/rejected propagation counters, Q/QN contributions and runtime profiles are retained. Historical integrity and physical validation records accompany the sealed artifact manifest.

| Design | Python | NumPy | Numba | SciPy | Diagnostic preparation s |
|---|---|---|---|---|---:|
| s5378 | 3.12.3 | 2.5.3 | 0.67.0 | 1.18.1 | 23.874 |
| s9234 | 3.12.3 | 2.5.3 | 0.67.0 | 1.18.1 | 24.034 |
| s15850 | 3.12.3 | 2.5.3 | 0.67.0 | 1.18.1 | 49.146 |

Physical tools: iverilog `Icarus Verilog version 12.0 (stable) ()`, openroad `26Q2-1164-g08f67ee5ec`.

Full-suite runtime: 144.603 seconds. Focused stateful tests also passed independently (6 tests).
