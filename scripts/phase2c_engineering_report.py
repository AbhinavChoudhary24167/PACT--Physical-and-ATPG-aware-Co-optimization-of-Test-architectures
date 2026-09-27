"""Report unaffected numerical-engineering evidence after the physical bug stop."""
from phase2c_common import *
import numpy as np

def main():
    cost=read(REPORT/'complexity.json');assert cost['engineering_only']
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    raw=read(REPORT/'benchmark_raw.json')['rows']
    for row in cost['rows']:
        case=next(r for r in raw if r['case']==row['case'])
        row['measured_toggle_density']=case['event_count']/(case['FF_count']*case['shift_cycles'])
    cost['synthetic_regime_caveat']='Synthetic dense means alternating SI, not dense activity throughout all FFs. Zero initial state and a 1024-cycle prefix activate at most 2048 FFs of the two long chains; this is sparse over the full 100k-FF inventory. Real ATPG cases provide the measured dense-activity regime. No complete 100k-FF ATPG load was measured.'
    write(REPORT/'complexity.json',cost)
    for metric,label,filename in [('seconds','Wall time (s)','runtime_scaling.png'),('peak_RSS_KiB','Peak RSS (MiB)','memory_scaling.png')]:
        fig,axes=plt.subplots(1,3,figsize=(12,3.8),layout='constrained')
        for ax,regime in zip(axes,['real','sparse','dense']):
            group=sorted([r for r in cost['rows'] if (not r['synthetic'] if regime=='real' else r['case'].endswith(regime))],key=lambda r:r['FF_count'])
            for kind in ['packed','event']:
                scale=1024 if metric=='peak_RSS_KiB' else 1
                ax.plot([r['FF_count'] for r in group],[r[kind+'_'+metric]/scale for r in group],'-o',label=kind)
            title={'real':'Real ATPG / legacy numeric weights','sparse':'Synthetic step SI / 1024 clocks','dense':'Synthetic alternating SI / 1024 clocks'}[regime]
            ax.set(xscale='log',yscale='log',xlabel='FF inventory',ylabel=label,title=title);ax.legend();ax.grid(alpha=.2)
        fig.suptitle('MEASURED evaluator-only cost; physical predictor semantics remain unqualified',fontsize=10)
        fig.savefig(REPORT/filename,dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.5,3.8),layout='constrained')
    for synthetic,marker in [(False,'o'),(True,'x')]:
        group=[r for r in cost['rows'] if r['synthetic']==synthetic]
        for kind in ('packed','event'):
            ax.scatter([r['event_count'] for r in group],[r[kind+'_seconds'] for r in group],marker=marker,label=kind+(' synthetic' if synthetic else ' real'))
    ax.set(xscale='log',yscale='log',xlabel='Actual FF transition events',ylabel='Wall time (s)',title='MEASURED supplied-weight evaluation');ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.savefig(REPORT/'events_runtime.png',dpi=160);plt.close(fig)
    plot=read(REPORT/'plot_status.json');plot['status']='ENGINEERING_ONLY_FIGURES_COMPLETE'
    plot['produced']=['runtime_scaling.png','memory_scaling.png','events_runtime.png']
    plot['withheld']=[p for p in plot['plots'] if p not in plot['produced']]
    plot['reason']='Six physical-correlation/rank panels withheld by the bug-stop rule. Three independently authorized engineering cost figures use supplied numeric weights only.'
    write(REPORT/'plot_status.json',plot)
    status=read(REPORT/'generalization_results.json')
    status['independent_engineering_benchmarks']='COMPLETED_AFTER_USER_CONTINUE'
    status['scalability_gate']=cost['scalability_gate'];write(REPORT/'generalization_results.json',status)
    lines=['# Phase-2C independent evaluator engineering results','',
        'The user requested continuation after the legacy-definition stop. These measurements evaluate numerical code for supplied weights; physical generalization remains withheld pending the definition decision. No predictor, coefficient, target or physical route was changed.','',
        cost['measurement'],'',cost['synthetic_regime_caveat'],'',
        f'**Measured scalability gate: {cost["scalability_gate"]}.** Median real packed/event time ratio is {cost["real_median_speedup"]:.3f}×. A ratio below 1 means the event evaluator is slower. Median real packed/event RSS ratio is {cost["real_median_memory_ratio"]:.3f}×.','',
        '| Case | FF toggle density | Packed s | Event s | Speedup | Packed MiB | Event MiB | Memory reduction |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in cost['rows']:lines.append(f'| {r["case"]} | {r["measured_toggle_density"]:.4f} | {r["packed_seconds"]:.4f} | {r["event_seconds"]:.4f} | {r["speedup"]:.3f}× | {r["packed_peak_RSS_KiB"]/1024:.2f} | {r["event_peak_RSS_KiB"]/1024:.2f} | {100*r["memory_reduction_fraction"]:.1f}% |')
    lines+=['','![Runtime](runtime_scaling.png)','','![Memory](memory_scaling.png)','','![Event count](events_runtime.png)','',
        'The event algorithm removes full FF-history storage and sparse inactive-FF scans. It does not remove K×T input inspection or dense event work. The real workload results do not support an optimizer-integration performance claim. Synthetic improvements describe only the measured bounded prefix.','',
        'The original packed numerical routine is unchanged. Both methods reconstruct exactly the same SI stimulus and agree on raw event counts, total and local peak at rtol=1e-12/atol=1e-10 for all 54 fresh-process benchmark executions. The packed baseline uses chunked direct simulation without expensive independent proof instrumentation.','',
        'The 100k/1M-FF full-load feasibility numbers in complexity.json are analytical operation and storage projections only. No 1M-FF runtime, large physical-correlation experiment, power, energy or causal optimization benefit was measured.']
    (REPORT/'ENGINEERING_REPORT.md').write_text('\n'.join(lines)+'\n')
    final=REPORT/'FINAL_REPORT.md';text=final.read_text()
    text=text.replace('7. **Measured speedup?** NOT MEASURED. Quiet, fresh-process benchmarks were deferred until routing finished and were not launched before the stop.',
        f'7. **Measured speedup?** After the user requested continuation, independent numerical benchmarks measured a median real packed/event ratio of {cost["real_median_speedup"]:.3f}× (event slower when below 1). See ENGINEERING_REPORT.md for all absolute timings. Physical claims remain withheld.')
    text=text.replace('8. **Measured memory reduction?** NOT MEASURED for the same reason. No inferred speedup or RSS reduction is presented as measured.',
        f'8. **Measured memory reduction?** Median real packed/event peak-RSS ratio {cost["real_median_memory_ratio"]:.3f}×. Absolute process peaks and reduction percentages for each case are in ENGINEERING_REPORT.md; imports/input overhead is included.')
    text=text.replace('Complexity counts in complexity.json are analytical only; no scaling run was completed.',
        'After user continuation, 54 fresh-process evaluator benchmarks were completed on three real P cases and six synthetic 1k/10k/100k-FF cases. Synthetic 1024-cycle prefixes are not full large-design loads. 1M-FF projections remain analytical only.')
    text=text.replace('measured runtime/memory advantage, large physical designs','a runtime advantage on real workloads, large physical designs')
    text=text.replace('The nine required scientific/performance plot products are explicitly marked\nNOT_PRODUCED_BUG_STOP in plot_status.json. Producing numerical panels now would\nimply valid, completed evidence; no placeholder numbers were invented.',
        'Six physical-correlation/rank panels are withheld by the bug-stop rule. Three measured numerical-engineering panels were produced after the user requested continuation; see plot_status.json and ENGINEERING_REPORT.md. No physical results are inferred from them.')
    text+='\n## Independent engineering continuation\n\nSee [ENGINEERING_REPORT.md](ENGINEERING_REPORT.md). The measured scalability gate is '+cost['scalability_gate']+'. This does not resolve or override the inherited definition bug.\n'
    final.write_text(text)
    print('ENGINEERING',cost['scalability_gate'],cost['real_median_speedup'],cost['real_median_memory_ratio'])

if __name__=='__main__':main()
