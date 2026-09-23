#!/usr/bin/env python3
"""Descriptive ranking, cross-design pooling, fixed decision gate and figures."""
from phase2b_common import *
from phase2a_validate import correlations, weighted_corr
from itertools import combinations
import numpy as np
from scipy.stats import rankdata

DESIGNS=('s5378','s9234','s15850')

def compare_pairs(labels,x,y):
    pairs=[]
    for i,j in combinations(range(len(x)),2):
        dx=float(x[j]-x[i]);dy=float(y[j]-y[i])
        direction=('both_tied' if dx==0 and dy==0 else 'predictor_tied' if dx==0 else
                   'target_tied' if dy==0 else 'agree' if dx*dy>0 else 'disagree')
        pairs.append(dict(left=labels[i],right=labels[j],predictor_delta=dx,target_delta=dy,direction=direction))
    counts={k:sum(p['direction']==k for p in pairs) for k in ('agree','disagree','both_tied','predictor_tied','target_tied')}
    denominator=counts['agree']+counts['disagree']
    return dict(counts=counts,non_tied_agreement=counts['agree']/denominator if denominator else None,pairs=pairs)

def analyze(rows):
    metrics=list(rows[0]['predictors']);targets=list(rows[0]['targets'])
    stats={};rankings={};pairwise={};pooled={}
    designs=[d for d in DESIGNS if any(r['design']==d for r in rows)]
    for d in designs:
        group=[r for r in rows if r['design']==d];labels=[r['label'] for r in group]
        stats[d]={};rankings[d]={};pairwise[d]={}
        for kind,keys in [('predictors',metrics),('targets',targets)]:
            rankings[d][kind]={key:[dict(label=r['label'],value=r[kind][key]) for r in
                sorted(group,key=lambda r:(r[kind][key],r['label']))] for key in keys}
        for metric in metrics:
            x=np.array([r['predictors'][metric] for r in group]);stats[d][metric]={};pairwise[d][metric]={}
            for target in targets:
                y=np.array([r['targets'][target] for r in group])
                pair=compare_pairs(labels,x,y)
                stats[d][metric][target]=dict(**correlations(x,y),pairwise_non_tied_agreement=pair['non_tied_agreement'],pair_counts=pair['counts'])
                pairwise[d][metric][target]=pair
    for metric in metrics:
        pooled[metric]={}
        for target in targets:
            xx=[];yy=[];ww=[];rx=[];ry=[]
            for d in designs:
                g=[r for r in rows if r['design']==d];n=len(g)
                x=np.array([r['predictors'][metric] for r in g]);y=np.array([r['targets'][target] for r in g])
                xx.extend(x/x.mean());yy.extend(y/y.mean());ww.extend([1/n]*n)
                rx.extend((rankdata(x)-1)/(n-1));ry.extend((rankdata(y)-1)/(n-1))
            pooled[metric][target]=dict(mean_normalized=weighted_corr(xx,yy,ww),
                fractional_ranks=weighted_corr(rx,ry,ww))
    return dict(per_design=stats,pooled=pooled,
        methodology='Average ties; tau-b; Pearson secondary; each design weight 1. Selected finite set, no random sampling/significance/generalization inference. No fitted coefficients; no LODO tuning.'),rankings,pairwise


def gate(stats, qualified):
    families=[m for m in stats['s5378'] if not m.endswith('_local') and m!='M1_H_eff8']
    evaluations={}
    for family in families:
        endpoints=[(family,'wire_total'),(family+'_local','wire_local_peak')]
        def passes(items):
            return all(stats[d][m][t]['spearman'] is not None and stats[d][m][t]['spearman']>=.7 and
                       stats[d][m][t]['pairwise_non_tied_agreement'] is not None and
                       stats[d][m][t]['pairwise_non_tied_agreement']>=.75 for d in DESIGNS for m,t in items)
        geometric=passes(endpoints)
        electrical=passes([(family,'cap_total'),(family+'_local','cap_local_peak')]) if qualified else None
        improved=[d for d in DESIGNS if all(stats[d][m][t]['spearman'] is not None and
                  stats[d][m][t]['spearman']-stats[d]['M1_H_eff8'][t]['spearman']>=.2-1e-12 for m,t in endpoints)]
        evaluations[family]=dict(geometric_pass=geometric,electrical_pass=electrical,improved_designs=improved)
    strong=any(v['geometric_pass'] and (not qualified or v['electrical_pass']) for v in evaluations.values())
    partial=any(len(v['improved_designs'])>=2 for v in evaluations.values())
    classification='PACT_PHASE2B_SURROGATE_'+('QUALIFIED' if strong else 'PARTIAL' if partial else 'FAIL')
    return dict(classification=classification,families=evaluations,
        geometric_validation='QUALIFIED_ON_FROZEN_SET' if any(v['geometric_pass'] for v in evaluations.values()) else 'PARTIAL_OR_FAIL',
        electrical_load_validation=('QUALIFIED_ON_FROZEN_SET' if any(v['electrical_pass'] for v in evaluations.values()) else 'PARTIAL') if qualified else 'PACT_PHASE2B_ELECTRICAL_VALIDATION_BLOCKED',
        electrical_energy_validation='INCOMPLETE: load-transition surrogate only, not power/energy, no timed full-circuit activity.')


def plots(rows,corr):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    families=['M1_H_eff8','M0','M2_scan','M2_port','M4_fanout','M4_pin','M5_hpwl','M5_star','M3_load',
              'M4_functional_fanout','M4_functional_pin','M5_functional_hpwl']
    targets=[('wire_total','surrogate_vs_wireweighted_total.png'),('wire_local_peak','surrogate_vs_wireweighted_local_peak.png')]
    if 'cap_total' in rows[0]['targets']:
        targets += [('cap_total','surrogate_vs_capweighted_total.png'),('cap_local_peak','surrogate_vs_capweighted_local_peak.png')]
    for target,filename in targets:
        fig,axes=plt.subplots(3,len(families),figsize=(30,8),layout='constrained')
        local='local' in target
        for i,d in enumerate(DESIGNS):
            g=[r for r in rows if r['design']==d]
            for j,f in enumerate(families):
                metric=f+'_local' if local and f!='M1_H_eff8' else f
                x=np.array([r['predictors'][metric] for r in g]);y=np.array([r['targets'][target] for r in g])
                ax=axes[i,j]; ax.scatter(x/x.mean(),y/y.mean(),s=15,color='#167b9a')
                for r,a,b in zip(g,x/x.mean(),y/y.mean()): ax.annotate(r['label'][:4],(a,b),fontsize=5,xytext=(2,2),textcoords='offset points')
                rho=corr['per_design'][d][metric][target]['spearman']
                ax.set_title(f'{d} / {metric}\nrho={rho:.3f}',fontsize=8)
                ax.set_xlabel('Predictor / mean',fontsize=7);ax.set_ylabel('Target / mean',fontsize=7);ax.tick_params(labelsize=6);ax.grid(alpha=.2)
                inset=ax.inset_axes([.62,.08,.32,.28]);inset.scatter(rankdata(x),rankdata(y),s=5,color='#ad4c31')
                inset.set_title('ranks',fontsize=5);inset.tick_params(labelsize=4)
        fig.suptitle(target+' — primary shift-only waveform; insets show ascending ranks',fontsize=14)
        fig.savefig(REPORT/filename,dpi=150);plt.close(fig)
    selected=['M1_H_eff8','M0','M2_port','M4_pin','M5_hpwl','M3_load']
    fig,axes=plt.subplots(1,len(targets),figsize=(16,4),layout='constrained')
    for ax,(target,_) in zip(np.atleast_1d(axes),targets):
        local='local' in target
        values=np.array([[corr['per_design'][d][f+'_local' if local and f!='M1_H_eff8' else f][target]['spearman'] for f in selected] for d in DESIGNS])
        im=ax.imshow(values,vmin=-1,vmax=1,cmap='RdBu',aspect='auto')
        ax.set_xticks(range(len(selected)),selected,rotation=55,ha='right',fontsize=8)
        ax.set_yticks(range(3),DESIGNS);ax.set_title(target,fontsize=10)
        for i in range(3):
            for j in range(len(selected)): ax.text(j,i,f'{values[i,j]:.2f}',ha='center',va='center',fontsize=8,color='white' if abs(values[i,j])>.65 else 'black')
    fig.colorbar(im,ax=np.atleast_1d(axes),shrink=.75,label='Spearman rho')
    fig.savefig(REPORT/'activity_model_comparison.png',dpi=170);plt.close(fig)
    # Comprehensive atlas covers every predictor/target cross-comparison without
    # dozens of individual plots. Each cell has normalized scatter and rank inset.
    for d in DESIGNS:
        g=[r for r in rows if r['design']==d];metrics=list(g[0]['predictors']);alltargets=list(g[0]['targets'])
        fig,axes=plt.subplots(len(metrics),len(alltargets),figsize=(18,2*len(metrics)),layout='constrained')
        for i,m in enumerate(metrics):
            for j,t in enumerate(alltargets):
                ax=axes[i,j];x=np.array([r['predictors'][m] for r in g]);y=np.array([r['targets'][t] for r in g])
                ax.scatter(x/x.mean(),y/y.mean(),s=8);ax.set_title(f'{m} / {t}',fontsize=7);ax.tick_params(labelsize=5)
                inset=ax.inset_axes([.65,.08,.3,.3]);inset.scatter(rankdata(x),rankdata(y),s=4,color='#b34d31');inset.tick_params(labelsize=4)
        fig.suptitle(d+' complete normalized scatter / rank atlas')
        fig.savefig(REPORT/(d+'_scatter_rank_atlas.png'),dpi=110);plt.close(fig)


def main():
    integrity();data=read(REPORT/'candidate_metrics.json');rows=data['rows']
    corr,ranks,pairs=analyze(rows);decision=gate(corr['per_design'],data['capacitance_qualified'])
    corr.update(decision=decision)
    write(REPORT/'correlation.json',corr);write(REPORT/'rankings.json',ranks);write(REPORT/'pairwise_comparisons.json',pairs)
    supplement=read(REPORT/'waveform_sensitivity.json')['rows']
    if supplement:
        sc,sr,sp=analyze(supplement)
        write(REPORT/'waveform_sensitivity_statistics.json',dict(correlation=sc,rankings=sr,pairs=sp))
    # Explain successive weighting changes by direct target-vs-target evidence.
    target_comparison={}
    for d in DESIGNS:
        g=[r for r in rows if r['design']==d];target_comparison[d]={}
        pairs_to_test=[('raw_total','wire_total'),('wire_total','cap_total'),('wire_local_peak','cap_local_peak'),
                       ('cap_ground_total','cap_total'),('cap_ground_local_peak','cap_local_peak')]
        for a,b in pairs_to_test:
            if a not in g[0]['targets'] or b not in g[0]['targets']: continue
            x=np.array([r['targets'][a] for r in g]);y=np.array([r['targets'][b] for r in g])
            target_comparison[d][a+'__'+b]=dict(**correlations(x,y),**compare_pairs([r['label'] for r in g],x,y))
    write(REPORT/'target_comparison.json',target_comparison)
    plots(rows,corr)
    print(json.dumps(decision,indent=2))
    print('MAIN CORRELATIONS')
    for d in DESIGNS:
        for m in ('M1_H_eff8','M0','M2_port','M4_pin','M5_hpwl','M3_load'):
            print(d,m,{t:round(corr['per_design'][d][m+'_local' if 'local' in t and m!='M1_H_eff8' else m][t]['spearman'],3) for t in ('wire_total','wire_local_peak','cap_total','cap_local_peak') if t in rows[0]['targets']})
    integrity()

if __name__=='__main__':main()
