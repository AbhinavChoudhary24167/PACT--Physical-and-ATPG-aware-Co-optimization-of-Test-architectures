"""Document the mandatory stop without inventing a generalization outcome."""
from phase2c_common import *
from datetime import datetime,timezone
from collections import Counter

def main():
    bug=read(REPORT/'legacy_bug_audit.json');assert bug['status']=='CONFIRMED_LEGACY_DEFINITION_BUG'
    matrix=[]
    for d in DESIGNS:
        for s in SEEDS:
            for job in read(WORK/d/f's{s}'/'prepared.json')['jobs']:
                folder=Path(job['architecture_path']).parent;p=folder/'result.json'
                if p.exists():row=read(p)
                else:
                    attempted=(folder/'attempt.json').exists()
                    row=dict(job,status='INTERRUPTED_BY_BUG_STOP' if attempted else 'NOT_RUN_STOP_CONDITION',
                        reason='Explicit user/contract stop rule after confirmed legacy SO-buffer ownership bug',
                        tool_failure=False,scientific_failure=False)
                    if attempted:
                        row['attempt']=read(folder/'attempt.json')
                        for stage in ('rewire','route','verify','extract','reference'):
                            execution=folder/stage/'execution.json'
                            if execution.exists():row[stage+'_execution']=read(execution)
                row['scientific_qualification']='WITHHELD_LEGACY_DEFINITION_BUG'
                row['definition_failure_class']='PROVENANCE_FAILURE'
                matrix.append(row)
    counts=dict(Counter(r['status'] for r in matrix))
    write(REPORT/'architecture_matrix.json',dict(rows=matrix,counts=counts,
        note='QUALIFIED denotes physical route/extraction completion only, not scientific metric qualification. Policy-interrupted attempts are not mislabeled tool or scientific failures.'))
    write(REPORT/'seed_matrix.json',dict(rows=[dict(design=d,seed=s,status_counts=dict(Counter(r['status'] for r in matrix if r['design']==d and r['seed']==s)),
        scientific_status='WITHHELD_LEGACY_DEFINITION_BUG') for d in DESIGNS for s in SEEDS]))
    stop=dict(status='STOPPED_LEGACY_DEFINITION_BUG',final_classification=None,
        classification_reason='No valid multi-seed scientific decision. An inherited definition bug triggered the explicit stop rule; it is neither a measured generalization failure nor an infrastructure outage.',
        closed_utc=datetime.now(timezone.utc).isoformat(),physical_status_counts=counts,
        M3_generalization='NOT_EVALUATED_VALIDLY',M5_generalization='NOT_EVALUATED_VALIDLY',
        seed_specific_calibration=False,wire_cap_per_um=.103981,optimizer_integration_recommended=False,
        required_next_step='Resolve the Phase-2B SI/SO definition discrepancy in a separately authorized correction, preserve original evidence, then preregister new Phase-2C evidence.',
        affected_frozen_architectures=bug['mismatching_architectures'])
    write(REPORT/'generalization_results.json',stop)
    for name in ('correlations.json','rankings.json','pairwise_comparisons.json'):
        write(REPORT/name,dict(status='WITHHELD_LEGACY_DEFINITION_BUG',
            reason='No scientific conclusions reported from contract-inconsistent predictor weights.',
            original_phase2b_reproduction='phase2b_reproduction.json',new_physical_rows_are_provisional=True))
    eq=read(REPORT/'evaluator_equivalence.json')
    write(WORK/'evaluator_equivalence_interrupted.json',eq)
    initial_log=WORK/'equivalence_initial.log'
    initial_text=initial_log.read_text()
    initial_rows=[line for line in initial_text.splitlines() if line.startswith('EQUIVALENT ')]
    trace_rows=[line for line in initial_text.splitlines() if line.startswith('TRACE EXACT ')]
    eq.update(status='STOPPED_AFTER_INITIAL_EQUIVALENCE_PASS',
        initial_run=dict(exit_code=0,primary_traces_exact=len(trace_rows),completed_architecture_weight_sets=len(initial_rows),
            log_path=str(initial_log),log_sha256=file_sha256(initial_log),
            all_21_original_architectures_and_capture_unload_accumulation_passed=True,
            rankings_spearman_and_pair_directions_exact=True),
        final_105_cell_gate='NOT_COMPLETED_BUG_STOP',
        scope='Correctness of accumulation for supplied frozen weights only; cannot validate physical graph semantics.',
        production_capture_generation='Not implemented; supplementary packed-event adapter tests accumulator only')
    write(REPORT/'evaluator_equivalence.json',eq)
    write(REPORT/'complexity.json',dict(status='NOT_MEASURED_BUG_STOP',wall_time=None,cpu_time=None,peak_RSS=None,speedup=None,memory_reduction=None,
        packed='O(P*N + N*T + B*T), T=P*Lmax; packed trace O(N*T/8), 1024-cycle scratch O(1024*(N+B)).',
        event='O(P*N + K*T + E + B*T_active), plus O(N) final dot product; per-FF state/count/weight/index arrays O(N), input patterns O(P*N), no full FF history.',
        regimes='Sparse activity avoids N*T expansion. Dense E≈N*T can erase the advantage; Python event overhead can dominate on small designs. No speedup is claimed.',
        extrapolated=[dict(FF_count=n,K=2,patterns=100,assumed_toggle_density=.5,cycles=100*n//2,
            events=.5*n*100*n/2,packed_trace_bytes=n*100*n/2/8,status='EXTRAPOLATED_NOT_MEASURED') for n in (100000,1000000)],
        physical_scalability='NOT_DEMONSTRATED',synthetic_scaling='NOT_EXECUTED_BUG_STOP'))
    plot_names=[m+'__'+t+'.png' for m,t in ENDPOINTS]+['worst_seed_heatmap.png','architecture_ranks.png','runtime_scaling.png','memory_scaling.png','events_runtime.png']
    write(REPORT/'plot_status.json',dict(status='NOT_PRODUCED_BUG_STOP',plots=plot_names,
        reason='Correlation and performance panels would imply a completed valid experiment. No placeholder numerical plots or invented timings are substituted.'))
    table=['| Design | Original source FF | Output buffer | Pin load fF | Frozen architectures with mismatched owner |',
           '|---|---|---|---:|---:|']
    for r in bug['rows']:table.append(f'| {r["design"]} | {r["original_source_FF"]} | {r["output_buffer"]} | {r["buffer_input_pin_cap_ff"]} | {sum(a["ownership_mismatch"] for a in r["selected_architectures"])}/{len(r["selected_architectures"])} |')
    report='''# Phase-2C mandatory stop: inherited SI/SO graph mismatch

**Status: STOPPED_LEGACY_DEFINITION_BUG. No valid Phase-2C generalization classification.**

The experiment stopped under the user's explicit instruction: “If a bug is found,
stop and document it before changing the experiment.” The same rule was frozen
in section K of EXPERIMENT_CONTRACT.md. This is a demonstrated discrepancy between
the inherited contract and implementation, not a measured failure of M3 or M5
to generalize and not a tool/infrastructure outage.

## Concrete reproducer and cause

In the frozen s5378 seed-11 P architecture, `output38` (BUF_X1) originally has
its A input on `n1588gat`, driven by `U_n1588gat`. The selected chain-0 tail is
`U_n2121gat`. The frozen routed physical inventory assigns `output38` to
`U_n2121gat`, as required by the actual rewiring code.

However, Phase-2B's placed graph retains the `output38/A` sink and `test_so`
transparent child beneath `n1588gat`. The exporter removes the output BTerm,
but not the original scan-output buffer input/branch. `construct_weights`
then adds tail-to-SO geometry with `master=None`, so it does not move that
buffer input capacitance or branch to the selected tail.

- `scripts/phase2b_extract.py:placed_graph`: skips test_si/test_so BTerms, but
  only filters FF SI ITerms from sinks; transparent output-buffer branches remain.
- `src/pact/analysis/phase2b_loads.py:construct_weights`: traverses those original
  roots/branches, then adds direct selected-tail output geometry without a pin load.
- `scripts/phase0c_rewire_odb.py:rewire`: explicitly disconnects output-buffer A
  and reconnects it to the selected chain-0 tail.

This contradicts the contract's removal of original SI/SO connections before
constructing the selected architecture graph. It affects both the ownership
of M3 input-pin load and the M5 tree geometry. It does **not** establish the
magnitude or sign of any correlation change after correction. No corrected
metric, coefficient, graph rule, waveform or historical result was substituted.

The read-only audit reproduces the owner mismatch in all 21 frozen architectures:

'''+ '\n'.join(table)+'''

Run the audit with the existing OpenROAD Python environment:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:/mnt/d/PACT_EXPERIMENTS/cache/phase2a_python \
openroad -python -no_init -exit scripts/phase2c_bug_audit.py
```

`legacy_bug_audit.json` records all concrete instance/net/owner identities, graph,
ODB and physical-inventory hashes. It reads prior evidence only. Reproduction
does not invoke routing, extraction, ATPG or an optimizer.

## Why the previous checks did not catch it

Phase-2B's reported correlations, architecture orders and pairwise comparisons
reproduce exactly; the frozen hashes pass. Event and packed evaluators also
agree for the supplied weights. Both numerical checks can succeed while sharing
the same upstream graph error. The missing test is selected-SO-buffer ownership
against the actual pre-route rewiring semantics, not another correlation threshold.

## Disposition

The source and Phase-2B artifacts remain unchanged. Completed Phase-2C physical
evidence is retained as provisional; ongoing process trees were terminated at
the stop. No failed seed is replaced. New scientific execution is guarded
against accidental resume while this audit exists.

A separately authorized correction must first resolve whether the stated metric
is intended to follow actual selected-architecture SO buffer connectivity or to
be a deliberately different approximation. It must preserve the original result,
document the correction, and create a new freeze before new correlation analysis.
Do not relabel this stop as GENERALIZATION_FAIL or INFRASTRUCTURE_BLOCKED.
'''
    (REPORT/'BUG_REPORT.md').write_text(report)
    summary=f'''# PACT Phase-2C final stop report

**STOPPED_LEGACY_DEFINITION_BUG — no valid generalization classification.**

The inherited SI/SO predictor graph disagrees with selected-architecture output
buffer ownership in all 21 frozen Phase-2B architectures. The explicit bug-stop
rule was enforced before modifying any frozen definition. See [BUG_REPORT.md](BUG_REPORT.md)
and [legacy_bug_audit.json](legacy_bug_audit.json) for the concrete reproducer.

Registered: 3 designs × 5 physical seeds × 9/6/6 architectures = 105 combinations,
K=2. Physical disposition: **{counts}**. Qualified physical results comprise
21 reused seed-11 cases and {counts.get('QUALIFIED',0)-21} newly completed cases.
The {counts.get('INTERRUPTED_BY_BUG_STOP',0)} policy-interrupted attempts are not
tool failures. No completed physical case failed qualification before the stop.
All 105 cells remain visible in [architecture_matrix.json](architecture_matrix.json).

## Direct answers

1. **Did M3 generalize?** Not validly determined. Contract-inconsistent input-pin ownership prevents a conclusion.
2. **Did M5 generalize?** Not validly determined. The inherited owned-tree geometry has the same SO ownership discrepancy.
3. **Strongest counterexample?** A definition counterexample: s5378/P assigns `output38` to `U_n1588gat` in the predictor but to selected tail `U_n2121gat` in the frozen routed reference. All 21 architectures show an analogous mismatch; no new rank-reversal claim is made.
4. **Were rankings stable enough?** Not evaluated as valid multi-seed evidence. The original Phase-2B rankings and gates reproduce numerically; that does not validate their graph semantics.
5. **Seed-specific calibration?** None. The coefficient remains 0.103981 fF/µm and the Phase-2B source functions were reused unchanged.
6. **Event evaluator equivalence?** The initial completed proof matched every primary event for all 21 original architectures, all available capture/unload accumulation traces, and {len(initial_rows)} completed architecture weight sets. Counts were exact; floats used rtol=1e-12/atol=1e-10; rankings, Spearman and pair directions were exact. The later extension was interrupted by the stop. The complete 105-cell gate is not claimed.
7. **Measured speedup?** NOT MEASURED. Quiet, fresh-process benchmarks were deferred until routing finished and were not launched before the stop.
8. **Measured memory reduction?** NOT MEASURED for the same reason. No inferred speedup or RSS reduction is presented as measured.
9. **Measured versus extrapolated?** The measured evidence is numerical reproduction, implemented event correctness, placement qualification and completed physical routes/extractions. Complexity counts in complexity.json are analytical only; no scaling run was completed.
10. **Larger design?** LARGE_DESIGN_NOT_AVAILABLE within the existing qualified scan/ATPG pipeline. Larger local ORFS RTL examples lack the frozen PACT scan mapping/pattern path.
11. **Plausibly usable inside an optimizer?** The O(E + K*T + B*T_active + P*N) event implementation is a correctness-tested building block for supplied weights. Optimizer throughput and a performance advantage are NOT DEMONSTRATED.
12. **Proceed to Phase-2D integration?** No. First resolve the upstream definition bug and preregister valid multi-seed and runtime evidence. No optimizer objective was changed.
13. **What remains unvalidated?** Full multi-seed M3/M5 qualification, corrected SO semantics, measured runtime/memory advantage, large physical designs, other technologies/K, full-chip power/energy and causal optimization benefit.
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
The nine required scientific/performance plot products are explicitly marked
NOT_PRODUCED_BUG_STOP in plot_status.json. Producing numerical panels now would
imply valid, completed evidence; no placeholder numbers were invented.
Provisional measurements and raw OpenROAD output remain auditable under
`D:/PACT_EXPERIMENTS/results/phase2c`, but are withheld from scientific conclusions.

The independent event implementation is in `src/pact/analysis/phase2c_events.py`.
The original packed evaluator, predictor builder, optimizer and prior artifacts
were not modified. `tests.json` and the validation section below record the
complete regression investigation, including its retained initial failure log.
'''
    (REPORT/'FINAL_REPORT.md').write_text(summary)
    readme=REPORT/'README.md';text=readme.read_text()
    prefix='''> **STOPPED_LEGACY_DEFINITION_BUG.** Read [BUG_REPORT.md](BUG_REPORT.md) and
> [FINAL_REPORT.md](FINAL_REPORT.md) first. Scientific execution is guarded;
> the commands below document the original workflow, not permission to resume.
> No valid multi-seed classification or measured speedup is claimed.

'''
    if not text.startswith('> **STOPPED'):readme.write_text(prefix+text)
    print(json.dumps(stop,indent=2))

if __name__=='__main__':main()
