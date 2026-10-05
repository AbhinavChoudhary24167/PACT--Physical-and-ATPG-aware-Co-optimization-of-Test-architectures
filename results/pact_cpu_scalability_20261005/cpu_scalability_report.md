# PACT CPU scalability — 2026-10-05

The exact CPU evaluator improves s35932 mutation throughput **4.74×**. Compact
activity reproduces the complete VCD oracle and reduces the s35932 trace
**8.56×**. The new s38417 external-reference measurement qualifies. s38584
finishes simulation but fails the unchanged missing-switched-net SPEF rule;
the campaign stops under the requested scientific policy.

Baseline: commit `9a8a63cb003e9eea966e47769073a65a758029db`, dedicated branch
`development/cpu-scalability-20261005`. WSL exposes four logical CPUs and
3.8 GiB RAM. Python 3.12.3, GCC 13.3, Icarus 12.0 and the frozen OpenROAD/FAN
executables are recorded in `gate0.json` and `cpu_worker_policy.json`. The final
audit verifies **1772 historical files unchanged**, the preserved oracle, and
**57 focused tests passed**. All new raw artifacts use the separate
`/mnt/d/PACT_EXPERIMENTS/results/pact_cpu_scalability_20261005` namespace.

| Question | Evidence-driven answer |
|---|---|
| A. Original spatial bottleneck | Each changed source decoded all packed cycles and updated one column of a C-contiguous 64-column field, producing strided writes. Unchanged packed blocks were still traversed. Spatial and rollback consumed 337.327 s of the 380.431 s witness loop. |
| B. Rollback bottleneck | Rejection reran source waveform/field updates to reverse deltas. Bulk array copying was not the dominant original cost: all NumPy array-copy calls took 0.117 s in cProfile. |
| C. Exact CPU changes | Contiguous spatial tile columns; skip equal eight-cycle packed blocks when capacitance is equal; cached exact integer transition totals; recompute only affected H8 tiles and H4 parents; sparse transaction snapshots restore affected state directly. Stage-B uses the new state, while the original evaluator remains the oracle. An optional per-pattern independent reference reduces replay memory. |
| D. Outputs unchanged? | More than 2000 evaluated mutations from 4096 deterministic proposals cover all five operators, mixed commits/rejections, E/H4/H8, objective and acceptance under the original `rtol=1e-9, atol=1e-6` policy. Rejected-state hashes restore bitwise. The s35932 128-evaluation path, acceptance decisions, selected architectures and independently replayed selected metrics are identical. Trial E accumulation differs by at most 0.000030756, within the registered tolerance. |
| E. Throughput | 0.336460 → 1.596226 exact mutations/s; **4.744×**. This is the same fixed-evaluation path, not a rerun of the historical campaign. |
| F. Spatial | 179.872 → 25.174 s; **86.00% lower**. |
| G. Rollback | 157.456 → 0.529 s; **99.66% lower**. |
| H. Memory | Witness peak RSS 1,537,588 → 1,551,964 KiB, **+14.04 MiB / +0.94%**. Independent reference worker RSS separately falls 1,321,484 → 275,472 KiB (79.15% lower), with oracle time increasing 11.150 → 16.800 s. This memory tradeoff is not a speedup claim. |
| I. Activity backend | CPU Icarus VPI settled-timestamp callbacks emit a gzip binary matrix of complete scalar-net/cycle counts. The same mapped circuit, stimulus, simulation mode, capacitance definitions, spatial bins, scopes and reductions remain. Full completion, functional replay, unknown/overflow checks and independent FF validation are required. |
| J. VCD oracle reproduced? | s953, s1196 and s35932 compare all counts and source totals exactly: 1,300,290; 1,288,008; and 556,948,224 count values. All scope statistics and spatial maps match; 1818 numeric summary/map values have **zero absolute difference** under the stricter original `1e-10*max(1,abs(reference))` activity policy. Fresh full-VCD controls also reproduce the entire original event streams. |
| K. Trace size | s953: 561,671 → 109,189 bytes (5.14× smaller). s1196: 420,655 → 89,626 (4.69×). s35932: 589,581,353 → 68,900,761 (8.56× / 88.31% fewer bytes). |
| L. s38417 completes? | **Exact frozen REF_B2 activity qualifies**, with 171,780 cycles, 13,582 mapped nets and 281,032,080 independent FF-cycle checks. Wall 1013.712 s; CPU 926.482 s; peak RSS 2,543,880 KiB; simulator 852.591 s; trace 374,107,061 bytes; normal 7200 s ceiling. E=1,391,034,999.4807134, H4=2094.4293152, H8=813.50868644. This recovers reference measurement; full cold-search/candidate qualification was not launched before the stop. |
| M. s38584 completes? | **Simulation/count collection completes, scientific activity remains unqualified.** 189,658 cycles, 16,838 mapped nets and 270,452,308 FF-cycle checks pass. Wall 1195.856 s; CPU 1071.730 s; peak RSS 3,299,524 KiB; simulator 1029.984 s; trace 482,381,871 bytes; normal 7200 s ceiling. Analysis rejects switched net654; net655/net714/net719 also have no extracted SPEF section. No E/H4/H8 is accepted. |
| N. Current dominant bottleneck | In the characterized single-thread mutation loop, spatial updates and scan waveform generation each take about 25.17 s; gate propagation takes 9.68 s. Outside the loop, evaluator construction and independent replay remain substantial. For large activity, simulation dominates; s38584's remaining blocker is scientific capacitance completeness. |
| O. CPU parallelism worthwhile? | Not demonstrated or implemented. The measured 1.55-million-KiB evaluator footprint plus recorded background/reserve permits one full evaluator worker on this 3.8-GiB host. Policy fixes one Python/native/simulator/physical job group; OpenROAD retains the frozen two-thread setting. No 2-/4-worker wall-time claim is made. |

The single-thread profile separates mutation generation, archive work, state
construction, scan activity, gate propagation, geometry, spatial updates,
reduction and rollback. cProfile attributes allocations/copies and Python calls;
native Numba time is charged to its caller, so a separately isolated native
dispatch overhead is unavailable. Timers and cProfile spans overlap and must
not be added indiscriminately.

| Same s35932 witness, 128 exact evaluations | Original | CPU incremental |
|---|---:|---:|
| Mutation loop wall, s | 380.431 | 80.189 |
| Full witness wall, s | 421.130 | 131.524 |
| Full witness CPU, s | 423.786 | 131.655 |
| Scan waveform, s | 24.207 | 25.160 |
| Gate propagation, s | 9.810 | 9.684 |
| Geometry, s | 0.486 | 0.484 |
| Spatial, s | 179.872 | 25.174 |
| Rollback, s | 157.456 | 0.529 |
| Reduction, s | 0.458 | 0.447 |
| State construction, s | 16.790 | 37.484 |
| Proposal / archive, s | 0.020 / 0.019 | 0.018 / 0.018 |

The controlled s35932 simulator comparison is **386.645 s full VCD vs
234.406 s compact (1.65×)**. Recorded workflow resources have different scopes:

| s35932 workflow | Wall s | CPU s | Peak RSS KiB | Trace bytes |
|---|---:|---:|---:|---:|
| Historical full VCD plus analysis | 962.153 | 812.701 | 1,275,988 | 589,581,353 |
| Fresh full VCD plus event verification | 411.777 | 292.018 | 402,232 | 589,581,353 |
| Compact plus complete full-VCD oracle comparison | 682.851 | 606.257 | 3,536,760 | 68,900,761 |

The compact row includes a 399.390 s independent proof stage. Compact analysis
alone takes 30.665 s and peaks at 776,564 KiB; the proof causes the larger RSS.
The fresh full-VCD row does not rerun the full old analyzer, and historical
timings had different background execution. These rows do not establish a
controlled total-workflow speedup.

Supported classifications: `PACT_CPU_INCREMENTAL_EVALUATOR_QUALIFIED`,
`PACT_CPU_SPATIAL_SCALABILITY_ADVANCE`,
`PACT_CPU_ROLLBACK_SCALABILITY_ADVANCE`,
`PACT_EXACT_ACTIVITY_BACKEND_EQUIVALENCE_CONFIRMED`, and
`PACT_LARGE_UNSEEN_MEASUREMENT_RECOVERED` **for s38417 reference activity only**.

`scientific_stop.json` binds the s38584 diagnosis, full compact trace, frozen
SPEF, completed simulation and failed analysis. Four switched nets lack D_NET
sections despite appearing in NAME_MAP; zero sink-pin capacitance does not
override the original prohibition. No missing value was filled. Cold search,
candidate preselection/physical/FAN/activity/final qualification and Gate 9
expansion were not launched. Continuations fail closed while the stop exists.
Historical 1800-second blocked records remain unchanged; every new run declares
normal 7200 s or diagnostic 14400 s ceilings, and no partial activity is used.

Evidence: `evaluator_equivalence.json`, `profile_oracle_128.json`,
`profile_incremental_128_sparse.json`, `reference/equivalence.json`,
`activity/equivalence/*/CS_C1/normal/`, `activity/fresh_vcd/`,
`activity/continuation/`, `scientific_stop.json`, and `verification.json`.
