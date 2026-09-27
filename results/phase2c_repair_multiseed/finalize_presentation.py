"""Resolve a tied narrative ranking and improve labels; scientific values unchanged."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from phase2crm_audit import OUT,read,write,sha
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

result=read(OUT/'results.json');es=result['endpoints'];held=[e for e in es if e['seed']!=11]
families={f:dict(minimum_heldout_rho=min(e['spearman'] for e in held if e['predictor'].startswith(f)),
    mean_heldout_rho=float(np.mean([e['spearman'] for e in held if e['predictor'].startswith(f)]))) for f in ('M3','M5')}
assert families['M3']['minimum_heldout_rho']==families['M5']['minimum_heldout_rho']
report=OUT/'FINAL_REPORT.md';text=report.read_text();lines=text.splitlines()
for i,line in enumerate(lines):
    if line.startswith('3. **Most stable family?**'):
        lines[i]=f"3. **Most stable family?** No unique winner by the stated worst-held-out-rho criterion: M3 and M5 tie at {families['M3']['minimum_heldout_rho']:.12g}. Descriptive held-out mean rhos are M3 {families['M3']['mean_heldout_rho']:.9g} and M5 {families['M5']['mean_heldout_rho']:.9g}; means do not alter gates."
    if line.startswith('4. **Least stable family?**'):
        lines[i]='4. **Least stable family?** The same minimum-rho criterion is tied, so no unique least-stable family is claimed. Local endpoints are less stable than totals; inspect the separate endpoint ranges and standard deviations below.'
sens=read(OUT/'sensitivity_analysis.json');failed=[r for r in sens['leave_one_architecture_out'] if not r['passed']]
pairfrag=[r for r in sens['leave_one_pair_out'] if r['accuracy_without_one_correct'] is not None and r['accuracy_without_one_correct']<.75]
insert=lines.index('## Physical execution and audit')
lines[insert:insert]=[
    f"Sensitivity findings: {len(failed)}/{len(sens['leave_one_architecture_out'])} leave-one-architecture endpoint analyses fall below an original gate; exact removed architectures are retained in sensitivity_analysis.json. Removing one correct pair causes {len(pairfrag)} endpoint accuracy gates to fail. Every leave-one-seed and leave-one-design classification remains CONFIRMED within the registered regime. These post-qualification descriptive deletions do not replace the complete-set result.",'',
    'Audit scope: topology_audit_raw.json preserves the inherited output. clarify_topology_scope.py marks its seed-11-only legacy archive summary flag as not applicable for new seeds. Every topology assertion passed unchanged; no topology, predictor, target or qualification gate was relaxed.','']
assert all(r['classification'].endswith('GENERALIZATION_CONFIRMED') for key in ('leave_one_seed_out','leave_one_design_out') for r in sens[key])
report.write_text('\n'.join(lines)+'\n')
write(OUT/'presentation_audit.json',dict(family_stability=families,minimum_rho_tie=True,
    leave_one_architecture_failed_endpoints=failed,leave_one_pair_fragile_accuracy=pairfrag,
    scientific_values_changed=False,classification_changed=False,
    reason='Original prose forced an arbitrary family ordering despite an exact tie; corrected narrative. Replaced overlapping point annotations with a row-based seed comparison.'))

keys=[(d,m) for d in ('s5378','s9234','s15850') for m in ('M3_load','M3_load_local','M5_hpwl','M5_hpwl_local')]
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
fig,ax=plt.subplots(figsize=(10,7.5),layout='constrained')
for i,(d,m) in enumerate(keys):
    values=[next(e['spearman'] for e in es if (e['design'],e['predictor'],e['seed'])==(d,m,s)) for s in (11,13,17)]
    ax.plot([min(values),max(values)],[i,i],color='.78',lw=2,zorder=1)
for seed,offset,color,marker in ((11,-.18,'#333333','o'),(13,0,'#2166ac','D'),(17,.18,'#b35806','^')):
    xx=[next(e['spearman'] for e in es if (e['design'],e['predictor'],e['seed'])==(d,m,seed)) for d,m in keys]
    ax.scatter(xx,np.arange(len(keys))+offset,c=color,marker=marker,s=43,label=f'Seed {seed}',zorder=3)
ax.set_yticks(range(len(keys)),[d+' / '+m for d,m in keys]);ax.invert_yaxis()
ax.set_xlim(.65,1.025);ax.axvline(.7,color='.5',ls='--',label='Original rho gate = 0.7')
for y in (3.5,7.5):ax.axhline(y,color='.87',lw=1)
ax.grid(axis='x',alpha=.2);ax.set_xlabel('Spearman rho (each design/seed evaluated separately)')
ax.legend(loc='upper center',bbox_to_anchor=(.5,-.1),ncol=4,frameon=False,fontsize=9)
ax.set_title('Seed 11 versus held-out physical realizations\nEvery endpoint passes; shared global-placement ancestry limits scope',pad=16)
for ext in ('png','pdf'):fig.savefig(OUT/'figures'/('seed11_vs_new_seeds.'+ext),bbox_inches='tight')
plt.close(fig)
print('PRESENTATION_FINALIZED; no scientific values or classification changed')
