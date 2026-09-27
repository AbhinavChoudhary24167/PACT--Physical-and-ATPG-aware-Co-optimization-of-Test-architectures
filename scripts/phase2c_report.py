"""Per-seed analysis, counterexamples, compact decision figures and final report."""
from phase2c_common import *
from itertools import combinations
import numpy as np
from scipy.stats import rankdata
from phase2b_report import analyze
from phase2a_validate import correlations
from pact.analysis.phase2c_decision import endpoint_pass,classify
from pact.analysis.phase2a_shift import fixed_bins
from pact.scan.model import ScanArchitecture

def summarize(rows):
    correlations_by_seed={};rankings={};pairs={};cells=[];stability=[]
    for s in SEEDS:
        group=[r for r in rows if r['seed']==s]
        # Never qualify a design/seed on a surviving subset of its architectures.
        expected={d:{r['label'] for r in read(REPORT/'architecture_set.json') if r['design']==d} for d in DESIGNS}
        complete_designs={d for d in DESIGNS if {r['label'] for r in group if r['design']==d}==expected[d]}
        group=[r for r in group if r['design'] in complete_designs]
        if not group:continue
        corr,rank,pair=analyze(group)
        correlations_by_seed[str(s)]=corr;rankings[str(s)]=rank;pairs[str(s)]=pair
        for d in DESIGNS:
            if d not in corr['per_design']:continue
            for m,t in ENDPOINTS:
                stat=corr['per_design'][d][m][t]
                cells.append(dict(design=d,seed=s,predictor=m,target=t,**stat,passed=endpoint_pass(stat)))
    summary=[];family_flags={'M3':[],'M5':[]}
    for d in DESIGNS:
        for family in family_flags:
            for s in SEEDS:
                subset=[r for r in cells if r['design']==d and r['seed']==s and r['predictor'].startswith(family)]
                family_flags[family].append(len(subset)==2 and all(r['passed'] for r in subset))
        for m,t in ENDPOINTS:
            group=[r for r in cells if r['design']==d and r['predictor']==m and r['target']==t]
            rho=[r['spearman'] for r in group if r['spearman'] is not None]
            summary.append(dict(design=d,predictor=m,target=t,observed_seeds=len(group),required_seeds=len(SEEDS),
                worst_seed_rho=min(rho) if rho else None,mean_rho=float(np.mean(rho)) if rho else None,
                median_rho=float(np.median(rho)) if rho else None,passing_seeds=sum(r['passed'] for r in group),
                passing_fraction=sum(r['passed'] for r in group)/len(SEEDS)))
            for a,b in combinations(SEEDS,2):
                ga={r['label']:r for r in rows if r['design']==d and r['seed']==a}
                gb={r['label']:r for r in rows if r['design']==d and r['seed']==b}
                expected_count=9 if d=='s5378' else 6
                if len(ga)!=expected_count or set(ga)!=set(gb):continue
                labels=sorted(ga)
                stability.append(dict(design=d,seeds=[a,b],predictor=m,target=t,
                    predictor_rank_stability=correlations([ga[l]['predictors'][m] for l in labels],[gb[l]['predictors'][m] for l in labels]),
                    reference_rank_stability=correlations([ga[l]['targets'][t] for l in labels],[gb[l]['targets'][t] for l in labels])))
    equal_design={m+'__'+t:dict(mean_rho=float(np.mean([r['mean_rho'] for r in summary if r['predictor']==m and r['mean_rho'] is not None])),
        worst_rho=min(r['worst_seed_rho'] for r in summary if r['predictor']==m and r['worst_seed_rho'] is not None)) for m,t in ENDPOINTS}
    return correlations_by_seed,rankings,pairs,cells,summary,stability,family_flags,equal_design

def diagnostics(rows,cells,pairs):
    failures=[]
    for cell in cells:
        if cell['passed']:continue
        d,s,m,t=cell['design'],cell['seed'],cell['predictor'],cell['target']
        reversed_pairs=[p for p in pairs[str(s)][d][m][t]['pairs'] if p['direction']=='disagree']
        for pair in reversed_pairs:
            architectures=[]
            for label in (pair['left'],pair['right']):
                job=next(j for j in read(WORK/d/f's{s}'/'prepared.json')['jobs'] if j['label']==label)
                folder=Path(job['architecture_path']).parent;result=read(folder/'result.json')
                weights=read(folder/'scoring_weights.json');physical=read(result['physical_path']);cap=read(result['reference_path'])
                arch=ScanArchitecture.from_json(Path(job['architecture_path']));names=sorted(c.name for c in arch.cells)
                coords={c.name:(c.x_um,c.y_um) for c in arch.cells}
                bins=fixed_bins([coords[n] for n in names],read(folder.parent/'prepared.json')['bounds'])
                proof=next(r for r in read(A/'shift_reconstruction.json')['rows'] if r['design']==d and r['label']==label)
                original=next(r for r in read(REPORT/'architecture_set.json') if r['design']==d and r['label']==label)
                original_arch=ScanArchitecture.from_json(Path(original['architecture_path']))
                original_coords={c.name:(c.x_um,c.y_um) for c in original_arch.cells}
                original_bins=fixed_bins([original_coords[n] for n in names],read(A/'test_quality.json')[d]['die_bounds_um'])
                from pact.analysis.phase2b_scoring import score_packed
                with np.load(proof['trace_path']) as trace:packed=trace['toggles_packed']
                ground_score,_=score_packed(packed,len(names),np.array([cap[n]['ground_pin_ff'] for n in names]),bins)
                eqrow=next(r for r in read(REPORT/'evaluator_equivalence.json')['rows'] if r['design']==d and r['seed']==s and r['label']==label)
                target_metric='cap' if t.startswith('cap') else 'wire'
                target_peak=eqrow['checks'][target_metric]['event_peak_location']
                peak_components={}
                if target_peak is not None:
                    cycle,y,x=target_peak;toggle=np.unpackbits(packed[cycle])[:len(names)]
                    active=toggle*np.isin(bins,[y*10+x,(y+1)*10+x,y*10+x+1,(y+1)*10+x+1])
                    for field in ('ground_ff','coupling_ff','pin_ff'):
                        peak_components[field]=float(active@np.array([cap[n][field] for n in names]))
                ff=[]
                for n,b in zip(names,bins):
                    count=proof['FF_transition_totals'][n]
                    ff.append(dict(name=n,toggles=count,bin=int(b),xy=coords[n],
                        owned_tree_HPWL_um=weights['M5_hpwl'][n],hpwl_contribution=count*weights['M5_hpwl'][n],
                        input_pin_ff=weights['M4_pin'][n],pin_contribution=count*weights['M4_pin'][n],
                        estimated_wire_ff=.103981*weights['M5_hpwl'][n],estimated_wire_contribution=count*.103981*weights['M5_hpwl'][n],
                        extracted_ground_ff=cap[n]['ground_ff'],incident_coupling_ff=cap[n]['coupling_ff'],routed_pin_ff=cap[n]['pin_ff'],
                        routed_wirelength_um=physical['FFs'][n]['wire_length_um'],
                        transparent_branches=physical['FFs'][n]['transparent_branches']))
                diagnostic_path=folder/'failure_diagnostics.json';write(diagnostic_path,dict(FFs=ff))
                score=next(r for r in rows if r['design']==d and r['seed']==s and r['label']==label)
                architectures.append(dict(label=label,predictor=score['predictors'][m],reference=score['targets'][t],
                    detail_path=str(diagnostic_path),detail_sha256=file_sha256(diagnostic_path),
                    ground_activity=sum(r['toggles']*r['extracted_ground_ff'] for r in ff),
                    coupling_activity=sum(r['toggles']*r['incident_coupling_ff'] for r in ff),
                    routed_pin_activity=sum(r['toggles']*r['routed_pin_ff'] for r in ff),
                    hpwl_activity=sum(r['hpwl_contribution'] for r in ff),
                    routed_wire_activity=sum(r['toggles']*r['routed_wirelength_um'] for r in ff),
                    buffer_branches=sum(len(r['transparent_branches']) for r in ff),
                    FFs_changing_bins_from_seed11=int(np.count_nonzero(bins!=original_bins)),
                    mean_FF_displacement_from_seed11_um=float(np.mean([sum(abs(a-b) for a,b in zip(coords[n],original_coords[n])) for n in names])),
                    target_peak_cycle_window=target_peak,cap_components_at_target_peak=peak_components,
                    ground_only_reference=ground_score['local_peak' if 'local' in t else 'total'],
                    pin_fraction_of_total_cap=sum(r['toggles']*r['routed_pin_ff'] for r in ff)/sum(r['toggles']*cap[r['name']]['effective_ff'] for r in ff)))
            relative=lambda a,b:abs(b-a)/max(abs(a),abs(b),1e-30)
            gap=relative(architectures[0]['predictor'],architectures[1]['predictor'])
            ground_delta=architectures[1]['ground_only_reference']-architectures[0]['ground_only_reference']
            failures.append(dict(design=d,seed=s,predictor=m,target=t,pair=pair,architectures=architectures,
                predictor_relative_gap=gap,
                association=dict(architecture_near_tie=gap<.01,
                    ground_only_removes_cap_rank_reversal=(ground_delta*pair['predictor_delta']>0) if t.startswith('cap') else None,
                    buffer_branch_count_difference=architectures[1]['buffer_branches']-architectures[0]['buffer_branches'],
                    local_spatial_assignment='Inspect per-FF bins and saved peak witnesses' if 'local' in t else 'Not a local endpoint',
                    waveform_behavior='Same invariant scan orders and exact primary traces at every seed',
                    placement_perturbation='Only registered seed placement and route realization vary',
                    routed_detour='Compare routed_wire_activity to hpwl_activity',
                    buffer_insertion='Branch identities retained; count difference alone is not causal attribution',
                    coupling='Incident coupling contribution retained; frozen convention unchanged',
                    pin_load_dominance='Routed and predicted pin contributions retained',
                    target_definition_sensitivity='Not changed or retuned; alternative physical objectives untested')))
    write(REPORT/'failure_diagnostics.json',dict(rows=failures,scope='Explanatory associations, not causal decomposition. Near-tie <1% is diagnostic only, never a gate/exclusion.'))
    return failures

def figures(rows,cells,summary,cost):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors=['#167b9a','#bd592b','#5b4d9d']
    for m,t in ENDPOINTS:
        fig,ax=plt.subplots(figsize=(6,3.5),layout='constrained')
        for d,color in zip(DESIGNS,colors):
            g=sorted([r for r in cells if r['design']==d and r['predictor']==m],key=lambda r:r['seed'])
            ax.plot([r['seed'] for r in g],[r['spearman'] for r in g],'-o',label=d,color=color)
        ax.axhline(.7,color='black',ls='--',lw=1,label='Frozen rho gate')
        ax.set(xticks=SEEDS,ylim=(-1.05,1.05),xlabel='Physical seed',ylabel='Spearman rho',title=m+' → '+t)
        ax.legend(fontsize=8);ax.grid(alpha=.2);fig.savefig(REPORT/(m+'__'+t+'.png'),dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,3),layout='constrained')
    values=np.array([[next(r['worst_seed_rho'] for r in summary if r['design']==d and r['predictor']==m) for m,t in ENDPOINTS] for d in DESIGNS])
    im=ax.imshow(values,vmin=-1,vmax=1,cmap='RdBu');ax.set_yticks(range(3),DESIGNS)
    ax.set_xticks(range(4),['M3 cap total','M3 cap local','M5 wire total','M5 wire local'],rotation=15,ha='right')
    for i in range(3):
        for j in range(4):ax.text(j,i,f'{values[i,j]:.3f}',ha='center',va='center',color='white' if abs(values[i,j])>.65 else 'black')
    ax.set_title('Worst physical-seed rho');fig.colorbar(im,ax=ax);fig.savefig(REPORT/'worst_seed_heatmap.png',dpi=160);plt.close(fig)
    # Compact 3x4, seeds are colors rather than a 60-panel atlas.
    fig,axes=plt.subplots(3,4,figsize=(12,8),layout='constrained')
    for i,d in enumerate(DESIGNS):
        for j,(m,t) in enumerate(ENDPOINTS):
            ax=axes[i,j]
            for s in SEEDS:
                g=[r for r in rows if r['design']==d and r['seed']==s]
                ax.scatter(rankdata([r['predictors'][m] for r in g]),rankdata([r['targets'][t] for r in g]),s=20,alpha=.6,label=str(s))
            ax.set_title(d+' / '+t,fontsize=9);ax.set_xlabel('Predicted rank');ax.set_ylabel('Reference rank');ax.grid(alpha=.2)
    axes[0,0].legend(title='Seed',fontsize=7);fig.savefig(REPORT/'architecture_ranks.png',dpi=160);plt.close(fig)
    for metric,label,filename in [('seconds','Wall time (s)','runtime_scaling.png'),('peak_RSS_KiB','Peak RSS (MiB)','memory_scaling.png')]:
        fig,axes=plt.subplots(1,3,figsize=(12,3.5),layout='constrained')
        for ax,regime in zip(axes,['real','sparse','dense']):
            g=sorted([r for r in cost['rows'] if (not r['synthetic'] if regime=='real' else r['case'].endswith(regime))],key=lambda r:r['FF_count'])
            for kind in ['packed','event']:
                scale=1024 if metric=='peak_RSS_KiB' else 1
                ax.plot([r['FF_count'] for r in g],[r[kind+'_'+metric]/scale for r in g],'-o',label=kind)
            ax.set(xscale='log',yscale='log',xlabel='FF count',ylabel=label,title='MEASURED '+('real P orders' if regime=='real' else 'synthetic '+regime));ax.legend();ax.grid(alpha=.2)
        fig.savefig(REPORT/filename,dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(6,3.5),layout='constrained')
    for syn,marker in [(False,'o'),(True,'x')]:
        g=[r for r in cost['rows'] if r['synthetic']==syn]
        for kind in ['packed','event']:
            ax.scatter([r['event_count'] for r in g],[r[kind+'_seconds'] for r in g],marker=marker,label=kind+(' synthetic' if syn else ' real'))
    ax.set(xscale='log',yscale='log',xlabel='Actual FF transition events',ylabel='Wall time (s)',title='Measured event count and runtime');ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.savefig(REPORT/'events_runtime.png',dpi=160);plt.close(fig)

def main():
    require_open_experiment()
    eq=read(REPORT/'evaluator_equivalence.json');assert eq['status']=='PASS','Event conclusions prohibited'
    rows=read(REPORT/'measurements.json')['rows'];matrix=read(REPORT/'architecture_matrix.json')['rows']
    # Verify provenance again before inspecting ANY Phase-2C correlations.
    # Output hashes were recorded at extraction, independently of this analysis.
    for row in matrix:
        if row['status']!='QUALIFIED':continue
        ext=row['extraction']
        if row['seed']==11:
            assert file_sha256(Path(ext['weights_path']))==ext['weights_sha256']
            assert file_sha256(Path(ext['spef_path']))==ext['spef_sha256']
        else:
            for path,sha in {**ext['inputs'],**ext['outputs']}.items():
                assert file_sha256(Path(path))==sha,('PROVENANCE_FAILURE',path)
            assert file_sha256(Path(row['routed_path']))==row['route_sha256']
        prepared=read(Path(row['architecture_path']).parent.parent/'prepared.json')
        for path,sha in prepared['inputs'].items():assert file_sha256(Path(path))==sha
    corr,ranks,pairs,cells,summary,stability,families,aggregate=summarize(rows)
    complete=len(rows)==105 and all(r['status']=='QUALIFIED' for r in matrix)
    classification=classify(families,complete,eq['status'])
    write(REPORT/'correlations.json',dict(per_seed=corr,endpoint_cells=cells,equal_design=aggregate))
    write(REPORT/'rankings.json',dict(per_seed=ranks,seed_to_seed_stability=stability))
    write(REPORT/'pairwise_comparisons.json',dict(per_seed=pairs))
    failures=diagnostics(rows,cells,pairs)
    cost=read(REPORT/'complexity.json')
    decision=dict(classification=classification,complete=complete,required_runs=105,qualified_runs=len(rows),
        failed_runs=[dict(design=r['design'],seed=r['seed'],label=r['label'],status=r['status']) for r in matrix if r['status']!='QUALIFIED'],
        families={k:dict(all_seeds_pass=all(v),passing_design_seed_cells=sum(v),required_design_seed_cells=15) for k,v in families.items()},
        endpoint_seed_summaries=summary,equal_design=aggregate,event_equivalence=eq['status'],scalability_gate=cost['scalability_gate'],
        seed_specific_calibration=False,wire_cap_per_um=.103981,
        optimizer_integration_recommended=classification.endswith('_CONFIRMED') and cost['scalability_gate']=='PASS')
    write(REPORT/'generalization_results.json',decision);figures(rows,cells,summary,cost)
    worst=min(cells,key=lambda r:r['spearman'] if r['spearman'] is not None else -2)
    worst_pairs=[p for p in pairs[str(worst['seed'])][worst['design']][worst['predictor']][worst['target']]['pairs'] if p['direction']=='disagree']
    worst_pair=max(worst_pairs,key=lambda p:abs(p['target_delta']),default=None)
    lines=['# PACT Phase-2C: surrogate generalization and scalable activity evaluation','',f'**Classification: `{classification}`.**','',
        f'Completed {len(rows)}/105 registered physical architecture evaluations on all five fixed seeds. '
        f'M3 passed {sum(families["M3"])}/15 design/seed cells; M5 passed {sum(families["M5"])}/15. '
        'Both endpoints must pass rho ≥ 0.7 and ≥75% non-tied pair agreement in each cell. No pooled statistic overrides a failure.','',
        '## Direct answers','',
        f'1. **Did M3 generalize?** {"Yes on this registered set" if all(families["M3"]) else "Not across the complete registered set"}; {sum(families["M3"])}/15 design/seed cells pass both capacitance endpoints.',
        f'2. **Did M5 generalize?** {"Yes on this registered set" if all(families["M5"]) else "Not across the complete registered set"}; {sum(families["M5"])}/15 design/seed cells pass both geometric endpoints.',
        f'3. **Worst counterexample:** {worst["design"]}, seed {worst["seed"]}, {worst["predictor"]} → {worst["target"]}: rho={worst["spearman"]:.6f}, pair agreement={worst["pairwise_non_tied_agreement"]:.6f}. Largest absolute reference-gap reversed pair within that cell: {worst_pair}.',
        f'4. **Ranking stability:** {sum(c["passed"] for c in cells)}/60 endpoint cells pass. `rankings.json` reports every architecture order and all pairwise seed-to-seed rho/tau-b stability comparisons; stability is descriptive, not an additional fitted gate.',
        '5. **Seed-specific calibration:** None. All 105 cells use the unchanged Phase-2B functions and 0.103981 fF/µm technology coefficient. No architecture search or pattern regeneration occurred.',
        f'6. **Event equivalence:** {eq["status"]}. Every primary transition matched 21 independent saved traces; all measured weights/bins match integer counts exactly and totals/peaks at rtol=1e-12, atol=1e-10. Rankings, Spearman and pair directions are exactly equal. All 21 available capture/unload traces additionally test accumulation; production capture generation is not claimed.',
        f'7. **Speedup:** Median real-design end-to-end packed/event ratio {cost["real_median_speedup"]:.3f}×. Ratios below 1 mean event processing is slower. Absolute timings are below.',
        f'8. **Memory reduction:** Median real-design packed/event peak-RSS ratio {cost["real_median_memory_ratio"]:.3f}×. Absolute process peaks include input/import overhead; this is not an isolated allocator measurement.',
        '9. **Measured versus extrapolated:** Physical results cover 179, 211 and 534 FFs. Runtime measurements cover these real P architectures plus separately labelled synthetic 1k/10k/100k-FF, 1024-cycle streams. 100k/1M full workloads are analytical projections only; no million-gate claim.',
        '10. **Larger design evidence:** LARGE_DESIGN_NOT_AVAILABLE in the qualified PACT scan/ATPG pipeline. Local larger ORFS RTL examples lack frozen scan mapping/patterns; they were not promoted to physical evidence.',
        f'11. **Usable inside an optimizer?** Equivalence makes the implementation a correctness-qualified building block. The preregistered measured scalability gate is {cost["scalability_gate"]}; candidate-generation, graph updates and optimizer throughput are not demonstrated.',
        f'12. **Proceed to optimizer integration?** {"A separately preregistered causal optimization experiment is justified; no integration implemented here." if decision["optimizer_integration_recommended"] else "No broad integration recommendation: address the failed scientific or performance gates without altering these frozen results."}',
        '13. **Unvalidated:** Independent placer seeds, different technologies, larger qualified physical designs, K sensitivity, capture production streaming, incremental graph updates, full-chip timed power/energy and causal optimization benefit.',
        f'14. **Exact final classification:** `{classification}`. Scientific failures remain failures; they are not infrastructure blockers.','',
        '## Per-design seed summary','',
        '| Design | Predictor → target | Worst rho | Mean rho | Median rho | Seeds passing |',
        '|---|---|---:|---:|---:|---:|']
    for r in summary:lines.append(f'| {r["design"]} | {r["predictor"]} → {r["target"]} | {r["worst_seed_rho"]:.3f} | {r["mean_rho"]:.3f} | {r["median_rho"]:.3f} | {r["passing_seeds"]}/5 |')
    lines+=['','![Worst seed](worst_seed_heatmap.png)','','![Rank comparisons](architecture_ranks.png)','',
        '## Measured evaluator cost','',cost['measurement'],'',
        '| Case | Packed s | Event s | Speedup | Packed MiB | Event MiB | Memory reduction |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in cost['rows']:lines.append(f'| {r["case"]} | {r["packed_seconds"]:.4f} | {r["event_seconds"]:.4f} | {r["speedup"]:.3f}× | {r["packed_peak_RSS_KiB"]/1024:.2f} | {r["event_peak_RSS_KiB"]/1024:.2f} | {100*r["memory_reduction_fraction"]:.1f}% |')
    lines+=['','![Runtime scaling](runtime_scaling.png)','','![Memory scaling](memory_scaling.png)','',
        '## Complexity and limits','',cost['packed'],'',cost['event'],'',cost['dense_regime'],'',
        'With K=2, 100 patterns and 50% transition density, a 100k-FF workload has 5M clocks and 250 billion toggle events; a 1M-FF workload has 50M clocks and 25 trillion events. Event representation avoids the full trace (62.5 GB and 6.25 TB packed respectively), but does not remove this dense compute burden. Compact numeric event state is roughly 40 bytes/FF plus patterns; Python object storage can be much larger. These are EXTRAPOLATED operation/storage counts, not measured runtimes or optimizer feasibility.','',
        '## Counterexample evidence','',
        f'{len(failures)} reversed pairs from failed endpoint cells have per-FF diagnostic manifests in `failure_diagnostics.json`: toggle distribution, HPWL, predicted pin/wire loads, extracted ground/coupling/routed-pin loads, routed length, transparent branches and bin assignments. Near-tie annotations are explanatory only. No metric was repaired.','',
        'The same waveforms and logical scan orders hold across seeds. Differences therefore arise through physical realization and spatial weighting, not new test patterns. Ground/coupling/buffer/local changes are associations; this experiment does not identify a unique causal decomposition.','',
        '## Reproducibility and validation','',
        'See `EXPERIMENT_CONTRACT.md`, `freeze.json`, `environment.json`, `provenance.json`, `integrity_audit.json`, `commands.json` and `tests.json`. Raw ODB/SPEF, per-FF weights, executions and diagnostics remain under `D:/PACT_EXPERIMENTS/results/phase2c`. Earlier evidence and unrelated dirty work are hash-protected. No optimizer objective change or Git push.','']
    (REPORT/'FINAL_REPORT.md').write_text('\n'.join(lines))
    print(json.dumps(decision,indent=2))

if __name__=='__main__':main()
