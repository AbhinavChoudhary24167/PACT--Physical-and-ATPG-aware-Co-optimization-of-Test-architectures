"""Preregistered descriptive statistics and reproducible scientific figures."""
from phase2crm_validate import *
from phase2a_validate import correlations
from phase2b_report import compare_pairs
from scipy.stats import rankdata
from itertools import combinations
import csv

ENDPOINTS=(('M3_load','cap_total'),('M3_load_local','cap_local_peak'),('M5_hpwl','wire_total'),('M5_hpwl_local','wire_local_peak'))
SEEDS=(11,13,17)

def csv_write(name,rows):
    with (OUT/name).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def stats():
    verify();assert read(OUT/'topology_audit.json')['passed']==63
    rows=read(OUT/'measurements.json')['rows']; assert len(rows)==63
    endpoints=[];pairs=[];architectures=[];cells=[];stability=[];sensitivities=[]
    for d in DESIGNS:
        for s in SEEDS:
            group=sorted([r for r in rows if (r['design'],r['seed'])==(d,s)],key=lambda r:r['label'])
            for m,t in ENDPOINTS:
                labels=[r['label'] for r in group]
                x=np.array([r['predictors'][m] for r in group]);y=np.array([r['targets'][t] for r in group])
                c=correlations(x,y);p=compare_pairs(labels,x,y)
                e=dict(design=d,seed=s,predictor=m,target=t,n=len(group),**c,
                    accuracy=p['non_tied_agreement'],correct=p['counts']['agree'],incorrect=p['counts']['disagree'],
                    tied=sum(v for k,v in p['counts'].items() if k not in ('agree','disagree')),unqualified=0,
                    passed=endpoint_pass(c['spearman'],p['non_tied_agreement']))
                endpoints.append(e)
                for r,xx,yy,xr,yr in zip(group,x,y,rankdata(x),rankdata(y)):
                    architectures.append(dict(design=d,seed=s,label=r['label'],architecture_sha256=r['architecture_sha256'],
                        predictor=m,target=t,predictor_value=float(xx),target_value=float(yy),predictor_rank=float(xr),target_rank=float(yr)))
                for pp in p['pairs']:
                    i,j=labels.index(pp['left']),labels.index(pp['right'])
                    pct,category=effect(pp['predictor_delta'],pp['target_delta'],y[i])
                    pairs.append(dict(design=d,seed=s,predictor=m,target=t,**pp,
                        classification='correct' if pp['direction']=='agree' else 'incorrect' if pp['direction']=='disagree' else 'tied',
                        predicted_delta_percent=100*pp['predictor_delta']/abs(x[i]) if x[i] else None,
                        physical_delta_percent=pct,effect_category=category))
                # Descriptive sensitivity: no alternative gate or exclusion is applied.
                for removed in labels:
                    keep=np.array([label!=removed for label in labels]);cc=correlations(x[keep],y[keep]);pp=compare_pairs([l for l in labels if l!=removed],x[keep],y[keep])
                    sensitivities.append(dict(design=d,seed=s,predictor=m,removed_architecture=removed,
                        spearman=cc['spearman'],accuracy=pp['non_tied_agreement'],passed=endpoint_pass(cc['spearman'],pp['non_tied_agreement'])))
            for family in ('M3_load','M5_hpwl'):
                es=[e for e in endpoints if (e['design'],e['seed'])==(d,s) and e['predictor'] in (family,family+'_local')]
                cells.append(dict(design=d,seed=s,family=family,passed=all(e['passed'] for e in es)))
        for m,t in ENDPOINTS:
            es=[e for e in endpoints if e['design']==d and e['predictor']==m]
            for scope,subset in [('all_seeds',es),('leave_seed11_out',[e for e in es if e['seed']!=11])]:
                vals=[e['spearman'] for e in subset];valid=[v for v in vals if v is not None]
                stability.append(dict(design=d,predictor=m,scope=scope,n=len(vals),mean_rho=float(np.mean(valid)) if valid else None,
                    median_rho=float(np.median(valid)) if valid else None,min_rho=min(valid) if valid else None,max_rho=max(valid) if valid else None,
                    sample_sd=float(np.std(valid,ddof=1)) if len(valid)>1 else None,
                    positive_seeds=sum(v>0 for v in valid),negative_seeds=sum(v<0 for v in valid),zero_seeds=sum(v==0 for v in valid),
                    undefined_seeds=len(vals)-len(valid),seeds_passing=sum(e['passed'] for e in subset)))
    consistency=[]
    for d in DESIGNS:
        labels=sorted({r['label'] for r in rows if r['design']==d})
        for m,t in ENDPOINTS:
            for left,right in combinations(labels,2):
                ps=sorted([p for p in pairs if (p['design'],p['predictor'],p['left'],p['right'])==(d,m,left,right)],key=lambda p:p['seed'])
                xp=[int(np.sign(p['predictor_delta'])) for p in ps];yp=[int(np.sign(p['target_delta'])) for p in ps]
                consistency.append(dict(design=d,predictor=m,target=t,left=left,right=right,
                    predictor_signs=xp,target_signs=yp,predictor_reversal=(-1 in xp and 1 in xp),target_reversal=(-1 in yp and 1 in yp),
                    predictor_consistent=len(set(xp))==1,target_consistent=len(set(yp))==1,
                    correct_all_seeds=all(p['classification']=='correct' for p in ps),
                    correct_stable_all_seeds=len(set(xp))==len(set(yp))==1 and all(p['classification']=='correct' for p in ps),
                    any_tie=0 in xp or 0 in yp,physically_negligible_seeds=[p['seed'] for p in ps if p['physical_delta_percent'] is not None and abs(p['physical_delta_percent'])<1],
                    unstable_across_seeds=len(set(xp))>1 or len(set(yp))>1))
    new=[c for c in cells if c['seed']!=11]
    result=dict(classification=classify(cells),cells=cells,endpoints=endpoints,cross_seed_stability=stability,
        leave_seed11_out=dict(qualifies=all(c['passed'] for c in new),classification=classify(new),cells=new),
        physical_realizations_per_design=3,new_realizations_per_design=2,independent_global_placement_runs=0,
        pair_consistency=consistency,architecture_deletion_sensitivity=sensitivities,
        limits='Conditional perturb-and-legalize replication; 3 physical realizations, 9/6/6 fixed architecture orders. No CI or significance claims; no power or optimization benefit established.',
        seed11_unchanged=True,contract_sha256=sha(OUT/'multiseed_contract.json'))
    write(OUT/'results.json',result)
    csv_write('per_seed_results.csv',endpoints);csv_write('per_architecture_results.csv',architectures);csv_write('pair_direction_results.csv',pairs)
    write(OUT/'pair_consistency.json',dict(rows=consistency))
    write(OUT/'sensitivity_analysis.json',dict(leave_one_architecture_out=sensitivities,
        leave_one_seed_out=[dict(omitted_seed=s,classification=classify([c for c in cells if c['seed']!=s])) for s in SEEDS],
        leave_one_design_out=[dict(omitted_design=d,classification=classify([c for c in cells if c['design']!=d])) for d in DESIGNS],
        leave_one_pair_out=[dict(design=e['design'],seed=e['seed'],predictor=e['predictor'],
            accuracy_without_one_correct=(e['correct']-1)/(e['correct']+e['incorrect']-1) if e['correct'] and e['correct']+e['incorrect']>1 else None,
            accuracy_without_one_incorrect=e['correct']/(e['correct']+e['incorrect']-1) if e['incorrect'] and e['correct']+e['incorrect']>1 else None) for e in endpoints],
        interpretation='Descriptive fragility checks only; no deletions alter primary outcomes.'))
    print(result['classification'],result['leave_seed11_out']['qualifies'],flush=True)
    return result,rows,architectures,pairs

def figures(result,rows,architectures,pairs):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
    folder=OUT/'figures';folder.mkdir(exist_ok=True)
    def save(fig,name):
        fig.savefig(folder/(name+'.png'),bbox_inches='tight');fig.savefig(folder/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
    colors=dict(zip(DESIGNS,('#2166ac','#b2182b','#4d9221')))
    fig,axs=plt.subplots(4,3,figsize=(12,12),layout='constrained')
    for i,(m,t) in enumerate(ENDPOINTS):
        for j,s in enumerate(SEEDS):
            ax=axs[i,j]
            for d in DESIGNS:
                g=[r for r in rows if (r['design'],r['seed'])==(d,s)]
                x=np.array([r['predictors'][m] for r in g]);y=np.array([r['targets'][t] for r in g])
                ax.scatter(x/x.mean(),y/y.mean(),s=23,alpha=.8,color=colors[d],label=d)
            ax.set(title=f'{m} / seed {s}',xlabel='Predictor / within-design mean',ylabel='Target / within-design mean');ax.grid(alpha=.15)
    axs[0,0].legend(fontsize=8);fig.suptitle('Predictor–target comparison: fixed orders, distinct physical realizations\nNormalization is for display only; correlations are calculated within design and seed')
    save(fig,'predictor_target_by_seed')
    es=result['endpoints'];fig,ax=plt.subplots(figsize=(7,7),layout='constrained')
    keys=[(d,m) for d in DESIGNS for m,t in ENDPOINTS]
    data=np.array([[next(e['spearman'] for e in es if (e['design'],e['predictor'],e['seed'])==(d,m,s)) for s in SEEDS] for d,m in keys])
    im=ax.imshow(data,vmin=-1,vmax=1,cmap='RdBu',aspect='auto')
    ax.set_xticks(range(3),SEEDS);ax.set_yticks(range(12),[d+' / '+m for d,m in keys]);ax.set_title('Raw Spearman rho by design and physical seed')
    for i in range(12):
        for j in range(3):ax.text(j,i,f'{data[i,j]:.6f}',ha='center',va='center',color='white' if abs(data[i,j])>.6 else 'black')
    fig.colorbar(im,ax=ax,label='Spearman rho');save(fig,'spearman_by_seed')
    fig,axs=plt.subplots(4,3,figsize=(17,11),layout='constrained')
    for i,(m,t) in enumerate(ENDPOINTS):
        for j,d in enumerate(DESIGNS):
            ax=axs[i,j];pp=[p for p in pairs if p['design']==d and p['predictor']==m]
            ids=sorted({(p['left'],p['right']) for p in pp})
            data=[[next(1 if p['classification']=='correct' else -1 if p['classification']=='incorrect' else 0 for p in pp if p['seed']==s and (p['left'],p['right'])==key) for key in ids] for s in SEEDS]
            ax.imshow(data,vmin=-1,vmax=1,cmap='RdBu',aspect='auto');ax.set_yticks(range(3),SEEDS)
            ax.set_xticks(range(len(ids)),[f'{a[:4]}/{b[:4]}' for a,b in ids],rotation=90,fontsize=5);ax.set_title(d+' / '+m)
    fig.suptitle('Pair directions across physical seeds: blue correct, red incorrect, white tied\nExact full architecture IDs and deltas are in pair_direction_results.csv')
    save(fig,'pair_direction_consistency')
    fig,axs=plt.subplots(3,4,figsize=(17,11),layout='constrained')
    for i,d in enumerate(DESIGNS):
        for j,(m,t) in enumerate(ENDPOINTS):
            ax=axs[i,j];g=[r for r in architectures if (r['design'],r['predictor'])==(d,m)]
            for label in sorted({r['label'] for r in g}):
                rr=sorted([r for r in g if r['label']==label],key=lambda r:r['seed'])
                line=ax.plot(SEEDS,[r['target_rank'] for r in rr],marker='o',lw=1.2,label=label[:6])[0]
                ax.plot(SEEDS,[r['predictor_rank'] for r in rr],ls=':',lw=1,color=line.get_color(),alpha=.7)
            ax.invert_yaxis();ax.set_xticks(SEEDS);ax.set_title(d+' / '+m);ax.set_ylabel('Ascending rank');ax.grid(alpha=.15)
            if j==3:ax.legend(fontsize=6,ncol=2)
    fig.suptitle('Architecture ranking stability: solid = physical target, dotted = predictor\nRank 1 is lowest; average ranks retain ties')
    save(fig,'architecture_rank_stability')
    fig,axs=plt.subplots(1,2,figsize=(11,5),layout='constrained')
    for ax,s in zip(axs,(13,17)):
        for d in DESIGNS:
            for m,t in ENDPOINTS:
                x=next(e['spearman'] for e in es if (e['design'],e['seed'],e['predictor'])==(d,11,m))
                y=next(e['spearman'] for e in es if (e['design'],e['seed'],e['predictor'])==(d,s,m))
                ax.scatter(x,y,color=colors[d],marker='s' if m.endswith('_local') else 'o')
                ax.annotate(d+'/'+m.replace('_load','').replace('_hpwl',''),(x,y),fontsize=5,xytext=(3,3),textcoords='offset points')
        ax.plot([-.1,1.05],[-.1,1.05],color='.65',lw=1);ax.axhline(.7,ls='--',color='.5');ax.axvline(.7,ls='--',color='.5')
        ax.set(xlim=(-.1,1.05),ylim=(-.1,1.05),xlabel='Seed-11 Spearman rho',ylabel=f'Seed-{s} Spearman rho',title=f'Seed 11 versus seed {s}')
    fig.suptitle('Baseline versus held-out physical realizations; gate = 0.7\nCircle: total endpoint. Square: local endpoint. Shared global-placement ancestry.')
    save(fig,'seed11_vs_new_seeds')

def final_report(result,pairs):
    cells=result['cells'];es=result['endpoints'];new=[e for e in es if e['seed']!=11]
    stability=result['cross_seed_stability'];cons=result['pair_consistency']
    family_min={f:min(e['spearman'] for e in new if e['predictor'].startswith(f)) for f in ('M3','M5')}
    ordered=sorted(family_min,key=family_min.get,reverse=True)
    ranges={d:max(r['max_rho']-r['min_rho'] for r in stability if r['design']==d and r['scope']=='all_seeds') for d in DESIGNS}
    failed=[e for e in new if not e['passed']]
    material=sum(p['effect_category']=='directionally_correct_physically_negligible' for p in pairs)
    reverse=sum(c['target_reversal'] for c in cons);predreverse=sum(c['predictor_reversal'] for c in cons)
    tests=read(OUT/'tests.json');physical=read(OUT/'physical_results.json')['rows']
    routes=sum(not r.get('multiseed_reused') and not r.get('reused_route') for r in physical)
    yes=result['leave_seed11_out']['qualifies']
    lines=['# Phase-2C-R multiseed generalization validation','',f"Primary classification: **{result['classification']}**.",'',
        'Scope: three distinct, seeded perturb-and-legalize physical realizations per design (11, 13, 17), descended from one global placement. These are not independent global-placement runs. The 21 fixed scan orders are replicated without architecture search, predictor fitting, threshold tuning or ATPG changes.','',
        f"Leave-seed-11-out qualification: **{'PASS' if yes else 'FAIL'}**. {sum(c['passed'] for c in cells if c['seed']!=11)}/12 new-seed design/family cells pass both original endpoints. Seed 11 contributes to neither this count nor this conclusion.",'',
        '## Direct answers','',
        '1. **Independent physical seeds tested per design?** Three distinct seeded physical realizations, including two new seeds. Zero independent global-placement runs; common ancestry limits independence and generalization.',
        f"2. **Qualifies without seed 11?** {'Yes within the registered physical-seed regime.' if yes else 'No; see every failing endpoint below.'}",
        f"3. **Most stable family?** {ordered[0]} by worst held-out endpoint rho ({family_min[ordered[0]]:.9g}); no average rescues failures.",
        f"4. **Least stable family?** {ordered[-1]} by the same criterion ({family_min[ordered[-1]]:.9g}).",
        f"5. **Most seed-sensitive design?** {max(ranges,key=ranges.get)} by largest within-endpoint rho range across the three seeds; ranges = {ranges}.",
        f"6. **Pair directions consistent across all seeds?** {sum(c['correct_stable_all_seeds'] for c in cons)}/{len(cons)} pair–endpoint comparisons are directionally correct with the same nonzero direction at every seed. {sum(c['correct_all_seeds'] for c in cons)} are correct at every seed allowing joint direction reversal. There are 66 distinct within-design architecture pairs and four endpoints, not 264 independent observations.",
        f"7. **Conclusions dependent on seed 11?** {'No original endpoint qualification fails on the new seeds, within this limited regime.' if not failed else str(len(failed))+' held-out endpoint cells fail despite all seed-11 cells passing; see the table.'}",
        f"8. **Correct rankings but negligible physical effects?** Yes: {material}/{len(pairs)} pair–seed–endpoint comparisons are directionally correct with physical change below the preregistered descriptive 1% tolerance. Exact deltas and percentages remain available; this is not a statistical significance or power threshold.",
        f"9. **Architecture ordering reversals?** {reverse}/{len(cons)} physical-target pair–endpoint orderings reverse sign across seeds; {predreverse} predictor orderings reverse. Exact pairs, signs and ties are in pair_consistency.json.",
        '10. **Strong enough for use inside PACT optimization?** Not established by this validation alone. Fixed-order predictive replication does not establish optimization benefit, evaluator throughput, generalization to independent placer runs, other designs/technologies/K, or power/energy accuracy.',
        '11. **Exact scientific blocker?** '+('Failed held-out endpoint gates and seed-sensitive pair orderings remain, in addition to correlated placement ancestry and untested optimization benefit.' if failed else 'Independent global-placement generalization and prospective optimization benefit remain untested; the evidence is conditional on a shared placement and a selected small architecture set.'),
        '12. **Smallest justified next experiment?** '+('Replicate the failing design/endpoint on one independently generated placement with the same complete frozen architecture set and original gates; retain the nearest/reversing pairs and do not tune the predictor.' if failed else 'One independently generated global placement per design, using the same 9/6/6 frozen scan orders and original gates (at most 21 exact-order routes). This tests the shared-placement limitation before any optimizer integration.')+' Not started.','',
        '## Raw endpoint results','',
        '| Design | Seed | Predictor | Spearman rho | Kendall tau-b | Pair accuracy | Correct | Incorrect | Tied | Gate |',
        '|---|---:|---|---:|---:|---:|---:|---:|---:|---|']
    for e in es:lines.append(f"| {e['design']} | {e['seed']} | {e['predictor']} | {e['spearman']:.12g} | {e['kendall_tau_b']:.12g} | {e['accuracy']:.12g} | {e['correct']} | {e['incorrect']} | {e['tied']} | {'PASS' if e['passed'] else 'FAIL'} |")
    lines+=['','## Cross-seed stability','',
        'All-seed and leave-11-out statistics are separately retained in results.json. SD is the sample SD across the listed seeds, not uncertainty over independent placer optimizations. Undefined values would fail the gates.','',
        '| Design | Predictor | Scope | Mean rho | Median | Min | Max | Sample SD | Positive / seeds | Gates passed |',
        '|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in stability:lines.append(f"| {r['design']} | {r['predictor']} | {r['scope']} | {r['mean_rho']:.9g} | {r['median_rho']:.9g} | {r['min_rho']:.9g} | {r['max_rho']:.9g} | {r['sample_sd']:.9g} | {r['positive_seeds']}/{r['n']} | {r['seeds_passing']}/{r['n']} |")
    lines+=['','## Interpretation and sensitivity','',
        'No failure is removed or averaged away. Family qualification requires both matching total/local endpoints; M3 is paired with capacitance and M5 with routed wire. Exact small-N pair counts, ties, rankings and effect sizes accompany the correlations. No bootstrap, confidence interval or asymptotic significance claim is used. Local peaks remain single-cycle/window maxima under the frozen waveform.',
        'sensitivity_analysis.json retains leave-one-architecture, leave-one-pair, leave-one-seed and leave-one-design descriptive checks. These identify dependence on one case but never change the preregistered result. pair_consistency.json explicitly records prediction sign changes, target sign changes, reversals, ties and negligible effects.','',
        '## Physical execution and audit','',
        f'{routes} new routes completed; 4 additional exact-order archived routes were reused for extraction. All 18 previously complete seed-13/17 s5378 physical cases and all 21 repaired seed-11 cases were reused. All 63 topology cases qualify (42 new-seed audits plus 21 frozen seed-11 proofs). New-source topology adaptation changes only the hardcoded seed selector; every original topology assertion is retained. The corrected predictor and scoring sources are unchanged.',
        f"Focused tests: {tests['focused']['passed']} passed. Full repository regression: {tests['regression']['passed']} passed, {tests['regression']['failures']} failures, {tests['regression']['errors']} errors, {tests['regression']['skipped']} skipped. Existing seed-11 outputs and Attempt 1 remain byte-identical. Raw physical executions retain commands, stdout/stderr, timing, DRC, structure proofs, SPEF and runtime under raw/. New negative STA slack, where present, is disclosed in structured metrics; the inherited contract does not impose a zero-slack gate.",
        'No optimizer, ML, ATPG, Phase-2D or push occurred. The contract predates new outcomes. result_provenance.json and manifest.sha256 cover frozen inputs, reused evidence, sources, contract and outputs; the manifest excludes itself.','',
        '## Figures','']
    for name in ('predictor_target_by_seed','spearman_by_seed','pair_direction_consistency','architecture_rank_stability','seed11_vs_new_seeds'):
        lines.append(f'![{name.replace("_"," ")}](figures/{name}.png)')
    (OUT/'FINAL_REPORT.md').write_text('\n'.join(lines)+'\n')

def main():
    result,rows,architectures,pairs=stats();figures(result,rows,architectures,pairs);final_report(result,pairs)

if __name__=='__main__':main()
