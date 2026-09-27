# PACT Phase-2C final stop report

**STOPPED_LEGACY_DEFINITION_BUG — no valid generalization classification.**

The inherited SI/SO predictor graph disagrees with selected-architecture output
buffer ownership in all 21 frozen Phase-2B architectures. The explicit bug-stop
rule was enforced before modifying any frozen definition. See [BUG_REPORT.md](BUG_REPORT.md)
and [legacy_bug_audit.json](legacy_bug_audit.json) for the concrete reproducer.

Registered: 3 designs × 5 physical seeds × 9/6/6 architectures = 105 combinations,
K=2. Physical disposition: **{'QUALIFIED': 41, 'INTERRUPTED_BY_BUG_STOP': 4, 'NOT_RUN_STOP_CONDITION': 60}**. Qualified physical results comprise
21 reused seed-11 cases and 20 newly completed cases.
The 4 policy-interrupted attempts are not
tool failures. No completed physical case failed qualification before the stop.
All 105 cells remain visible in [architecture_matrix.json](architecture_matrix.json).

## Direct answers

1. **Did M3 generalize?** Not validly determined. Contract-inconsistent input-pin ownership prevents a conclusion.
2. **Did M5 generalize?** Not validly determined. The inherited owned-tree geometry has the same SO ownership discrepancy.
3. **Strongest counterexample?** A definition counterexample: s5378/P assigns `output38` to `U_n1588gat` in the predictor but to selected tail `U_n2121gat` in the frozen routed reference. All 21 architectures show an analogous mismatch; no new rank-reversal claim is made.
4. **Were rankings stable enough?** Not evaluated as valid multi-seed evidence. The original Phase-2B rankings and gates reproduce numerically; that does not validate their graph semantics.
5. **Seed-specific calibration?** None. The coefficient remains 0.103981 fF/µm and the Phase-2B source functions were reused unchanged.
6. **Event evaluator equivalence?** The initial completed proof matched every primary event for all 21 original architectures, all available capture/unload accumulation traces, and 27 completed architecture weight sets. Counts were exact; floats used rtol=1e-12/atol=1e-10; rankings, Spearman and pair directions were exact. The later extension was interrupted by the stop. The complete 105-cell gate is not claimed.
7. **Measured speedup?** After the user requested continuation, independent numerical benchmarks measured a median real packed/event ratio of 0.252× (event slower when below 1). See ENGINEERING_REPORT.md for all absolute timings. Physical claims remain withheld.
8. **Measured memory reduction?** Median real packed/event peak-RSS ratio 1.058×. Absolute process peaks and reduction percentages for each case are in ENGINEERING_REPORT.md; imports/input overhead is included.
9. **Measured versus extrapolated?** The measured evidence is numerical reproduction, implemented event correctness, placement qualification and completed physical routes/extractions. After user continuation, 54 fresh-process evaluator benchmarks were completed on three real P cases and six synthetic 1k/10k/100k-FF cases. Synthetic 1024-cycle prefixes are not full large-design loads. 1M-FF projections remain analytical only.
10. **Larger design?** LARGE_DESIGN_NOT_AVAILABLE within the existing qualified scan/ATPG pipeline. Larger local ORFS RTL examples lack the frozen PACT scan mapping/pattern path.
11. **Plausibly usable inside an optimizer?** The O(E + K*T + B*T_active + P*N) event implementation is a correctness-tested building block for supplied weights. Optimizer throughput and a performance advantage are NOT DEMONSTRATED.
12. **Proceed to Phase-2D integration?** No. First resolve the upstream definition bug and preregister valid multi-seed and runtime evidence. No optimizer objective was changed.
13. **What remains unvalidated?** Full multi-seed M3/M5 qualification, corrected SO semantics, a runtime advantage on real workloads, large physical designs, other technologies/K, full-chip power/energy and causal optimization benefit.
14. **Exact final classification?** None of the preregistered generalization outcomes is valid. Execution status is STOPPED_LEGACY_DEFINITION_BUG. This stop is not recast as a scientific negative or infrastructure outage.

## Frozen baseline and limits

Phase-2B remains numerically PACT_PHASE2B_SURROGATE_PARTIAL: M3 separately passes
its electrical gates and M5 its geometric gates on seed 11. Across designs the
M3 total/local rhos are 1.000/0.983, 0.943/0.886, 0.943/0.943; M5 total/local
rhos are 0.967/0.983, 1.000/1.000, 0.943/0.943. The new bug audit limits their
interpretation; it does not overwrite these historical numbers.

Seeds 11,13,17,19,23 are conditional perturb-and-legalize replicas from one global
placement, not independent placer runs. The raw paths and all input hashes are
retained. No new surrogate, calibration, ML, ATPG, optimizer or Git push occurred.

## Artifact and plot disposition

[README.md](README.md) indexes the registration, matrices, tests and provenance.
Six physical-correlation/rank panels are withheld by the bug-stop rule. Three measured numerical-engineering panels were produced after the user requested continuation; see plot_status.json and ENGINEERING_REPORT.md. No physical results are inferred from them.
Provisional measurements and raw OpenROAD output remain auditable under
`D:/PACT_EXPERIMENTS/results/phase2c`, but are withheld from scientific conclusions.

The independent event implementation is in `src/pact/analysis/phase2c_events.py`.
The original packed evaluator, predictor builder, optimizer and prior artifacts
were not modified. `tests.json` and the validation section below record the
complete regression investigation, including its retained initial failure log.

## Independent engineering continuation

See [ENGINEERING_REPORT.md](ENGINEERING_REPORT.md). The measured scalability gate is FAIL. This does not resolve or override the inherited definition bug.

## Executed regression evidence

- focused: {'passed': 44}, 10.14 s.
- regression: {'failed': 1, 'passed': 200}, 119.98 s.
- regression_isolated: {'passed': 203}, 133.48 s.

Initial ENOMEM was an OS/filesystem enumeration exception; the isolated rerun above is the final regression result. Old tests were not modified.
