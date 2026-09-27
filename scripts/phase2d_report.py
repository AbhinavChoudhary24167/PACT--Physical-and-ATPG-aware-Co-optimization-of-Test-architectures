"""All-endpoint decision and descriptive comparisons; no fitting or rescue."""
from phase2d_common import *
from phase2a_validate import correlations
from phase2b_report import compare_pairs
from phase2crm_validate import effect, endpoint_pass
from scipy.stats import rankdata
import numpy as np
import csv

def csv_write(name,rows,fields=None):
    with (OUT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)

def classify(endpoints,engineering_pass):
    expected={(d,m,t) for d in DESIGNS for m,t in ENDPOINTS}
    actual=[(e['design'],e['predictor'],e['target']) for e in endpoints]
    if not engineering_pass or len(actual)!=12 or set(actual)!=expected:
        return 'PACT_PHASE2D_ENGINEERING_BLOCKED'
    return 'PACT_PHASE2D_INDEPENDENT_GP_GENERALIZATION_'+('CONFIRMED' if all(
        endpoint_pass(e['spearman'],e['accuracy']) for e in endpoints) else 'NOT_CONFIRMED')

def analyze():
    verify_contract();assert read(OUT/'topology_results.json')['passed']==21
    new=read(OUT/'measurements.json')['rows'];prior=read(PRIOR/'measurements.json')['rows']
    assert len(new)==21 and len(prior)==63
    allrows=prior+new;endpoints=[];pairs=[];architecture=[];sens=[]
    for d in DESIGNS:
        for seed in (11,13,17,29):
            group=sorted((r for r in allrows if r['design']==d and r['seed']==seed),key=lambda r:r['label'])
            assert len(group)==(9 if d=='s5378' else 6)
            labels=[r['label'] for r in group]
            for m,t in ENDPOINTS:
                x=np.array([r['predictors'][m] for r in group]);y=np.array([r['targets'][t] for r in group])
                c=correlations(x,y);p=compare_pairs(labels,x,y)
                e=dict(design=d,seed=seed,predictor=m,target=t,n=len(group),**c,accuracy=p['non_tied_agreement'],
                    correct=p['counts']['agree'],incorrect=p['counts']['disagree'],
                    tied=sum(v for k,v in p['counts'].items() if k not in ('agree','disagree')),
                    passed=endpoint_pass(c['spearman'],p['non_tied_agreement']))
                endpoints.append(e)
                for r,xx,yy,xr,yr in zip(group,x,y,rankdata(x),rankdata(y)):
                    architecture.append(dict(design=d,seed=seed,label=r['label'],predictor=m,target=t,
                        frozen_architecture_id=next(a['frozen_architecture_id'] for a in read(OUT/'contract.json')['cells'] if (a['design'],a['label'])==(d,r['label'])),
                        predictor_value=float(xx),target_value=float(yy),predictor_rank=float(xr),target_rank=float(yr)))
                for pp in p['pairs']:
                    pct,category=effect(pp['predictor_delta'],pp['target_delta'],y[labels.index(pp['left'])])
                    pairs.append(dict(design=d,seed=seed,predictor=m,target=t,**pp,
                        predictor_direction=int(np.sign(pp['predictor_delta'])),target_direction=int(np.sign(pp['target_delta'])),
                        classification='correct' if pp['direction']=='agree' else 'incorrect' if pp['direction']=='disagree' else 'tied',
                        physical_delta_percent=pct,absolute_physical_delta=abs(pp['target_delta']),effect_category=category))
                if seed==29:
                    for removed in labels:
                        keep=np.array([l!=removed for l in labels]);cc=correlations(x[keep],y[keep])
                        pp=compare_pairs([l for l in labels if l!=removed],x[keep],y[keep])
                        sens.append(dict(design=d,predictor=m,removed_architecture=removed,spearman=cc['spearman'],accuracy=pp['non_tied_agreement']))
    primary=[e for e in endpoints if e['seed']==29];comparison=[];npairs=[]
    for e in primary:
        old=[v for v in endpoints if v['seed']!=29 and (v['design'],v['predictor'])==(e['design'],e['predictor'])]
        vals={v['seed']:v['spearman'] for v in old}
        comparison.append(dict(design=e['design'],predictor=e['predictor'],target=e['target'],
            rho_seed11=vals[11],rho_seed13=vals[13],rho_seed17=vals[17],rho_independent=e['spearman'],
            delta_from_seed11=e['spearman']-vals[11] if e['spearman'] is not None else None,
            min_perturb_seed_rho=min(vals.values()),max_perturb_seed_rho=max(vals.values())))
    for p in (p for p in pairs if p['seed']==29):
        row=dict(p);tr=[];pr=[]
        for s in (11,13,17):
            old=next(o for o in pairs if o['seed']==s and all(o[k]==p[k] for k in ('design','predictor','left','right')))
            row[f'target_reversal_vs_{s}']=old['target_direction']*p['target_direction']<0
            row[f'predictor_reversal_vs_{s}']=old['predictor_direction']*p['predictor_direction']<0
            row[f'target_tie_transition_vs_{s}']=(old['target_direction']==0)!=(p['target_direction']==0)
            row[f'predictor_tie_transition_vs_{s}']=(old['predictor_direction']==0)!=(p['predictor_direction']==0)
            tr.append(row[f'target_reversal_vs_{s}']);pr.append(row[f'predictor_reversal_vs_{s}'])
        row.update(target_reversal_any_previous=any(tr),predictor_reversal_any_previous=any(pr));npairs.append(row)
    classification=classify(primary,True)
    result=dict(classification=classification,contract_sha256=sha(OUT/'contract.json'),endpoints=primary,
        endpoint_comparison=comparison,all_endpoints_pass=all(e['passed'] for e in primary),
        worst_spearman=min((e['spearman'] for e in primary if e['spearman'] is not None),default=None),
        most_affected_by_absolute_rho_change=max(comparison,key=lambda e:abs(e['delta_from_seed11']) if e['delta_from_seed11'] is not None else float('inf')),
        new_exact_order_implementations=read(OUT/'physical_results.json')['new_exact_order_implementations'],
        independent_gp_per_design=1,topology_passed=21,
        reversals=dict(unique_pair_endpoints=len(npairs),target_any_previous=sum(p['target_reversal_any_previous'] for p in npairs),
            predictor_any_previous=sum(p['predictor_reversal_any_previous'] for p in npairs),
            per_previous_seed={str(s):dict(target=sum(p[f'target_reversal_vs_{s}'] for p in npairs),predictor=sum(p[f'predictor_reversal_vs_{s}'] for p in npairs)) for s in (11,13,17)}),
        negligible_correct=sum(p['effect_category']=='directionally_correct_physically_negligible' for p in npairs),
        scientific_scope='One fresh seeded global placement per design under the tested Nangate45, benchmark and architecture regime; initialization mode differs from the earlier center-initialized GP. No broader design/technology, optimization, power, IR-drop, ATPG-quality or production claim.',
        qualification_uses_only_independent_endpoints=True)
    write(OUT/'results.json',result)
    csv_write('raw_endpoint_results.csv',endpoints);csv_write('per_architecture_results.csv',architecture)
    csv_write('pair_direction_results.csv',npairs);csv_write('all_realization_pair_results.csv',pairs)
    csv_write('endpoint_comparison.csv',comparison)
    write(OUT/'sensitivity_analysis.json',dict(leave_one_architecture_out=sens,
        leave_one_pair_out=[dict(design=e['design'],predictor=e['predictor'],
            accuracy_without_one_correct=(e['correct']-1)/(e['correct']+e['incorrect']-1) if e['correct'] else None,
            accuracy_without_one_incorrect=e['correct']/(e['correct']+e['incorrect']-1) if e['incorrect'] else None) for e in primary],
        interpretation='Descriptive only. No omission, average, previous seed or negligible-effect label modifies the primary endpoint gates.'))
    return result,endpoints,architecture,pairs

def figures(result,eps,ars,pairs):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    folder=OUT/'figures';folder.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':8,'savefig.dpi':160})
    seeds=(11,13,17,29);colors=('#8c8c8c','#529bb7','#9569af','#d55e00')
    def save(fig,name):
        fig.savefig(folder/(name+'.png'),bbox_inches='tight');fig.savefig(folder/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
    fig,axs=plt.subplots(4,3,figsize=(14,13),layout='constrained')
    for i,(m,t) in enumerate(ENDPOINTS):
        for j,d in enumerate(DESIGNS):
            ax=axs[i,j]
            for s,col in zip(seeds,colors):
                group=[r for r in ars if (r['design'],r['predictor'],r['seed'])==(d,m,s)]
                ax.scatter([r['predictor_value'] for r in group],[r['target_value'] for r in group],
                    color=col,marker='D' if s==29 else 'o',s=30 if s==29 else 17,alpha=.85,label='Independent GP' if s==29 else f'Seed {s}')
            ax.set(title=f'{d} / {m}',xlabel='Frozen predictor score',ylabel=t);ax.ticklabel_format(axis='both',style='sci',scilimits=(0,0));ax.grid(alpha=.15)
    axs[0,0].legend(fontsize=7);fig.suptitle('Frozen predictors versus routed targets: one independent GP per design')
    save(fig,'predictor_target_scatter')
    keys=[(d,m) for d in DESIGNS for m,t in ENDPOINTS]
    data=np.array([[next(e['spearman'] for e in eps if (e['design'],e['predictor'],e['seed'])==(d,m,s)) for s in seeds] for d,m in keys],dtype=float)
    fig,ax=plt.subplots(figsize=(9,8),layout='constrained');im=ax.imshow(data,vmin=-1,vmax=1,cmap='RdBu',aspect='auto')
    ax.set_xticks(range(4),['Seed 11','Seed 13','Seed 17','Independent GP']);ax.set_yticks(range(12),[d+' / '+m for d,m in keys])
    for i in range(12):
        for j in range(4):ax.text(j,i,f'{data[i,j]:.3f}' if np.isfinite(data[i,j]) else 'undefined',ha='center',va='center',color='white' if abs(data[i,j])>.6 else 'black')
    fig.colorbar(im,ax=ax,label='Spearman rho');ax.set_title('Every endpoint separately; original rho gate = 0.7');save(fig,'rho_heatmap')
    fig,axs=plt.subplots(4,3,figsize=(17,17),layout='constrained')
    for i,(m,t) in enumerate(ENDPOINTS):
        for j,d in enumerate(DESIGNS):
            ax=axs[i,j];group=[p for p in pairs if (p['design'],p['predictor'])==(d,m)]
            ids=sorted({(p['left'],p['right']) for p in group});mat=[]
            for left,right in ids:
                mat.append([{'correct':1,'incorrect':-1,'tied':0}[next(p['classification'] for p in group if (p['left'],p['right'],p['seed'])==(left,right,s))] for s in seeds])
            ax.imshow(mat,cmap=ListedColormap(['#d55e00','#cccccc','#20856e']),vmin=-1,vmax=1,aspect='auto')
            ax.set_xticks(range(4),['11','13','17','GP B']);ax.set_yticks(range(len(ids)),[a[:6]+' / '+b[:6] for a,b in ids],fontsize=5)
            ax.set_title(d+' / '+m)
    fig.suptitle('Pair-direction agreement: green correct, orange incorrect, gray tied\nAll pairs retained; GP B is the independent placement');save(fig,'pair_direction_consistency')
    fig,axs=plt.subplots(4,3,figsize=(16,13),layout='constrained')
    for i,(m,t) in enumerate(ENDPOINTS):
        for j,d in enumerate(DESIGNS):
            ax=axs[i,j];group=[r for r in ars if (r['design'],r['predictor'])==(d,m)]
            labels=sorted({r['label'] for r in group})
            for k,label in enumerate(labels):
                records=[next(r for r in group if (r['label'],r['seed'])==(label,s)) for s in seeds]
                color=plt.get_cmap('tab10')(k)
                ax.plot(range(4),[r['target_rank'] for r in records],color=color,marker='o',lw=1,label=label[:8])
                ax.plot(range(4),[r['predictor_rank'] for r in records],color=color,ls=':',alpha=.6,lw=.8)
            ax.set_xticks(range(4),['11','13','17','GP B']);ax.set_yticks(range(1,len(labels)+1));ax.invert_yaxis();ax.set_title(d+' / '+m)
            if i==0:ax.legend(fontsize=6,ncol=3)
    fig.suptitle('Architecture ranking stability: solid target, dotted predictor\nAverage ranks for ties; rank 1 is the smallest score');save(fig,'architecture_ranking_stability')
    fig,ax=plt.subplots(figsize=(10,8),layout='constrained')
    for i,c in enumerate(result['endpoint_comparison']):
        ax.plot([c['min_perturb_seed_rho'],c['max_perturb_seed_rho']],[i,i],color='#777777',lw=5)
        ax.scatter(c['rho_seed11'],i,color='#222222',s=22,marker='o',zorder=3)
        if c['rho_independent'] is not None:ax.scatter(c['rho_independent'],i,color='#d55e00',s=50,marker='D',zorder=4)
        else:ax.text(.7,i,'Independent rho undefined',fontsize=7)
    ax.axvline(.7,color='#b2182b',ls='--',label='Original rho gate')
    ax.set_yticks(range(12),[r['design']+' / '+r['predictor'] for r in result['endpoint_comparison']]);ax.invert_yaxis()
    ax.set(xlabel='Spearman rho',title='Gray: previous-seed range; black: seed 11; orange: independent GP')
    ax.legend();ax.grid(axis='x',alpha=.15);save(fig,'previous_range_vs_independent')

def report(result):
    e=result['endpoints'];c=result['endpoint_comparison'];rev=result['reversals']
    totals=[abs(x['delta_from_seed11']) for x in c if not x['predictor'].endswith('_local') and x['delta_from_seed11'] is not None]
    locals_=[abs(x['delta_from_seed11']) for x in c if x['predictor'].endswith('_local') and x['delta_from_seed11'] is not None]
    totalmean=sum(totals)/len(totals) if len(totals)==6 else float('nan')
    localmean=sum(locals_)/len(locals_) if len(locals_)==6 else float('nan')
    stability=('Total predictors show a smaller mean absolute rho change' if totalmean<localmean else 'Local predictors show a smaller mean absolute rho change' if localmean<totalmean else 'Total and local predictors tie in mean absolute rho change')
    worst=result['most_affected_by_absolute_rho_change'];success=result['all_endpoints_pass']
    fmt=lambda v: 'undefined' if v is None else f'{v:.6f}'
    tests=read(OUT/'tests.json')
    focus=tests.get('focused_phase2d',tests['focused']);reg=tests.get('regression_final',tests['regression'])
    lines=['# PACT Phase-2D independent global-placement validation','',f"**{result['classification']}**",'',
        'The frozen M3/M5 predictor-target relationships replicated on one independently generated global placement per design under the tested technology, benchmark and architecture regime.' if success else 'At least one preregistered independent-placement endpoint failed its original gate. The independent-GP relationship is not confirmed for the complete frozen set.', '',
        '## Method and independence','',
        'The installed OpenROAD 26Q2-1164-g08f67ee5ec does not expose a global-placement random-seed flag. The contract therefore preregistered seed 29 for Python random.Random scratch initialization from each retained 2_floorplan.odb. Every movable input instance had NONE/UNPLACED status. Coordinates were sampled from core bounds, with no old placed coordinates read. Both ORFS global-placement stages then ran, followed by the qualified resizing and detailed-placement steps. The hook removes force_center_initial_place and uses skip_initial_place to preserve that new initialization. This tests a fresh seeded initialization regime; it is not a native OpenROAD seed-only perturbation of otherwise identical GP settings.', '',
        'The ancestry is pre-GP floorplan → fresh initialization → skip-IO GP → new IO placement → final GP → resize/detail placement. Independent placement commands, logs, original unplaced statuses, generated coordinates and intermediate/final hashes are retained. Phase-2C seed-11 DEFs were read only afterward for descriptive comparison. Coordinate differences alone are corroboration, not the causal proof.', '',
        'All 21 frozen logical architecture IDs and scan-order hashes are recorded in contract.json. Physical serialization hashes naturally differ with coordinates. Pattern, FF identity and packed activity hashes were verified; ATPG was not regenerated. Predictors, target extraction, exact tie statistics, coefficient 0.103981, 10x10 bins, 81 contained 2x2 windows and all topology assertions remain unchanged.', '',
        f"Contract SHA256: `{sha(OUT/'contract.json')}`. Original gates: rho ≥ 0.7 and non-tied accuracy ≥ 0.75 for each endpoint; undefined fails. No pooled rescue.",'',
        '## Endpoint results','',
        '| Design | Predictor | rho 11 | rho 13 | rho 17 | Independent rho | Delta vs 11 | tau-b | Accuracy | Correct / incorrect / tied | Pass |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|']
    for x in c:
        r=next(r for r in e if (r['design'],r['predictor'])==(x['design'],x['predictor']))
        lines.append(f"| {x['design']} | {x['predictor']} | {fmt(x['rho_seed11'])} | {fmt(x['rho_seed13'])} | {fmt(x['rho_seed17'])} | {fmt(r['spearman'])} | {fmt(x['delta_from_seed11'])} | {fmt(r['kendall_tau_b'])} | {fmt(r['accuracy'])} | {r['correct']} / {r['incorrect']} / {r['tied']} | {r['passed']} |")
    lines+=['','## Mandatory direct answers','',
        '1. **Independent from pre-GP state?** Yes, for all three designs; one new placement per design.',
        '2. **Evidence of no Phase-2C placed ancestry?** The input floorplan hashes and all-movable-unplaced status audit, seeded initialization coordinate records, commands loading only the new ancestry, GP logs and DEF/ODB hashes are in independent_placement_proof.json and execution/. The Phase-2C comparison DEF is accessed only after placement.',
        f"3. **New exact-order implementations?** {result['new_exact_order_implementations']} (budget 21).",
        f"4. **Every endpoint passes?** {'Yes, 12/12.' if success else 'No; see every individual gate above.'}",
        f"5. **Worst independent rho?** {fmt(result['worst_spearman'])}.",
        f"6. **Most affected endpoint?** {worst['design']} / {worst['predictor']}, rho change {fmt(worst['delta_from_seed11'])} from seed 11; ties are visible in endpoint_comparison.csv.",
        f"7. **Are total predictors more stable?** {stability}: total mean absolute change {totalmean:.9f}, local {localmean:.9f}. This descriptive summary never rescues an endpoint.",
        f"8. **Target reversals?** {rev['target_any_previous']} of {rev['unique_pair_endpoints']} unique pair-endpoints reverse relative to at least one prior seed. Per-seed counts: "+', '.join(f"{s}: {v['target']}" for s,v in rev['per_previous_seed'].items())+'.',
        f"9. **Predictor reversals?** {rev['predictor_any_previous']} unique pair-endpoints; per-seed counts: "+', '.join(f"{s}: {v['predictor']}" for s,v in rev['per_previous_seed'].items())+'.',
        f"10. **Correct predictions with <1% target difference?** {'Yes' if result['negligible_correct'] else 'No'}: {result['negligible_correct']} independent pair-endpoints. This is a descriptive tolerance, not statistical significance.",
        '11. **May these predictors be used in a prospective optimizer experiment?** '+('The tested physical-generalization prerequisite is satisfied within this regime; this supports preregistering a bounded prospective optimizer experiment, not claiming optimizer benefit.' if success else 'Not on the strength of this validation: the complete endpoint gate did not pass.'),
        '12. **Exact blocker?** '+('No remaining Phase-2D gate blocker in the tested regime. Broader validity and optimization benefit remain untested.' if success else '; '.join(f"{r['design']}/{r['predictor']}: rho={r['spearman']}, accuracy={r['accuracy']}" for r in e if not r['passed'])),
        '13. **Smallest justified next experiment?** '+('A separately preregistered, bounded prospective comparison of a frozen predictor-guided selection rule against fixed baseline architectures, with held-out routed outcomes and unchanged ATPG. Phase-3 was not started.' if success else 'A separately preregistered replication on one additional fresh GP per design with the same frozen orders and gates, preceded by read-only diagnosis of the failed endpoints. No tuning or optimizer experiment.'),
        '', '## Verification and limits','',
        f"Focused tests: {focus['passed']} passed. Full repository regression: {reg['passed']} passed. New physical/topology checks: 21/21. Upstream manifests and final byte-preservation checks are in initial_integrity.json, final_integrity.json and result_provenance.json.", '',
        'One independent GP per design is a limited replication. No inference is made across technologies, arbitrary designs, power, IR drop, ATPG quality, production readiness or optimization benefit. Seeded scratch initialization and the changed GP initialization mode must remain part of the stated scope. All failed attempts, if any, are preserved. No push and no Phase-3.', '',
        '## Figures','']
    for name in ('predictor_target_scatter','rho_heatmap','pair_direction_consistency','architecture_ranking_stability','previous_range_vs_independent'):
        lines.append(f'![{name}](figures/{name}.png)\n')
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':
    result,eps,ars,pairs=analyze();figures(result,eps,ars,pairs);report(result)
    print(result['classification'],result['worst_spearman'],flush=True)
