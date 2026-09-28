"""Descriptive physical comparison and scientific figures; never fits a model."""
from physical_effect import *
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def delta(a,b): return 100*(a/b-1)

def collect():
    old={(r['design'],r['method']):r for r in csv.DictReader((ROOT/'reports/working_solver/comparison.csv').open())}
    rows=[]; physical=[]
    for entry in read(OUT/'manifest.json')['rows']:
        d,role=entry['design'],entry['role']; folder=OUT/d/role
        if not (folder/'activity_summary.json').exists(): continue
        data=read(folder/'activity_summary.json'); route=read(entry['qualification']['path'])
        oldrow=old[d,'PACT_recommended' if role=='PACT' else role]
        for scope,s in data['scopes'].items():
            for grid,g in s['grids'].items():
                physical.append(dict(design=d,architecture=role,scope=scope,grid=grid,nets=s['nets'],
                    **{'transitions_'+k:v for k,v in s['transitions'].items()},
                    **{'cap_'+k:v for k,v in s['cap_weighted_ff_transitions'].items()},
                    **{'local_'+k:v for k,v in g['peak_per_cycle'].items()},
                    **{'local_cap_'+k:v for k,v in g['cap_peak_per_cycle'].items()}))
        s=data['scopes']['all_data']; q=data['scopes']['scan_data']; g=s['grids']['8']; qg=q['grids']['8']
        row=dict(design=d,architecture=role,patterns=entry['patterns'],shift_cycles=entry['shift_cycles'],
            total_transitions=int(s['transitions']['total']),peak_transitions=int(s['transitions']['maximum']),
            cap_weighted_ff_transitions=s['cap_weighted_ff_transitions']['total'],
            peak_cap_ff=s['cap_weighted_ff_transitions']['maximum'],peak_local=int(g['peak_per_cycle']['maximum']),
            peak_local_cap_ff=g['cap_peak_per_cycle']['maximum'],
            scan_transitions=int(q['transitions']['total']),scan_cap_weighted=q['cap_weighted_ff_transitions']['total'],
            scan_peak_local=int(qg['peak_per_cycle']['maximum']),scan_peak_local_cap_ff=qg['cap_peak_per_cycle']['maximum'],
            routed_path_upper_bound_um=route['routed_full_scan_path_net_length_upper_bound_um'],
            setup_wns_ns=route['structured_metrics']['setup_wns_ns'],hold_wns_ns=route['structured_metrics']['hold_wns_ns'],
            timing_stage=route['structured_metrics'].get('timing_stage','global_route'),DRC=0,
            **{k:float(oldrow[k]) for k in ('M3_load','M3_load_local','M5_hpwl','M5_hpwl_local')})
        rows.append(row)
    keys=['total_transitions','peak_transitions','cap_weighted_ff_transitions','peak_cap_ff','peak_local','peak_local_cap_ff',
          'scan_transitions','scan_cap_weighted','scan_peak_local','scan_peak_local_cap_ff','routed_path_upper_bound_um',
          'M3_load','M3_load_local','M5_hpwl','M5_hpwl_local']
    for row in rows:
        same=[r for r in rows if r['design']==row['design']]
        for reference in ('physical_start','J50'):
            role=('T' if row['design']=='s9234' else 'P') if reference=='physical_start' else 'J50'
            baseline=next((r for r in same if r['architecture']==role),None)
            for k in keys: row[k+'_pct_vs_'+reference]=delta(row[k],baseline[k]) if baseline else None
    for name,rr in [('comparison.csv',rows),('physical_metrics.csv',physical)]:
        if rr:
            with (OUT/name).open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rr[0])); w.writeheader(); w.writerows(rr)
    return rows

def plots(rows):
    colors=['#31688e','#e08430','#21918c']
    for design in ('s5378','s9234','s15850'):
        rr=[r for r in rows if r['design']==design]
        if len(rr)!=3: continue
        fig,axs=plt.subplots(3,2,figsize=(12,8),sharex=True,sharey='col',layout='constrained')
        for i,row in enumerate(rr):
            role=row['architecture']; folder=OUT/design/role
            a=np.genfromtxt(folder/'per_cycle.csv',delimiter=',',names=True,dtype=None,encoding='utf8')
            for j,key in enumerate(('all_data_transitions','all_data_local_8')):
                axs[i,j].plot(a['cycle'],a[key],lw=.45,color=colors[i]); axs[i,j].set_title(role)
                axs[i,j].set_ylabel('Net transitions / cycle' if j==0 else 'Peak local transitions / cycle')
                axs[i,j].grid(alpha=.18)
        for ax in axs[-1]: ax.set_xlabel('Measured shift cycle (load and unload; capture excluded)')
        fig.suptitle(design+' | exact routed netlist, ATPG shift, non-clock data scope')
        fig.savefig(OUT/design/'activity_cycles.png',dpi=160); plt.close(fig)
        fig,axs=plt.subplots(2,3,figsize=(12,7),layout='constrained')
        maps=[read(OUT/design/r['architecture']/'spatial_bins.json')['all_data_8'] for r in rr]
        for j,key in enumerate(('transition_map','cap_map')):
            vmax=max(max(m[key]) for m in maps)
            for i,(row,m) in enumerate(zip(rr,maps)):
                im=axs[j,i].imshow(np.array(m[key]).reshape(8,8),origin='lower',vmin=0,vmax=vmax,cmap='magma')
                axs[j,i].set_title(f'{row["architecture"]}: cycle {m["transition_cycle" if j==0 else "cap_cycle"]}')
                axs[j,i].set_xlabel('Die bin X'); axs[j,i].set_ylabel('Die bin Y')
            fig.colorbar(im,ax=list(axs[j]),label='Transitions' if j==0 else 'Ground + pin fF transitions')
        fig.suptitle(design+' | each architecture at its peak cycle; source-cell attribution')
        fig.savefig(OUT/design/'spatial_hotspots.png',dpi=160); plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,6),layout='constrained')
    for i,d in enumerate(('s5378','s9234','s15850')):
        for r in [r for r in rows if r['design']==d]:
            x=r['routed_path_upper_bound_um_pct_vs_physical_start']; y=r['peak_local_pct_vs_physical_start']
            if r['architecture'] in ('P','T'): continue
            ax.scatter(x,y,c=colors[i],marker='*' if r['architecture']=='PACT' else 'o',s=140 if r['architecture']=='PACT' else 45)
            offset=(5,24) if i==0 and r['architecture']=='PACT' else ((5,8) if i%2==0 else (5,-13))
            ax.annotate(d+' '+r['architecture'],(x,y),xytext=offset,textcoords='offset points',fontsize=8)
    ax.scatter([0],[0],c='black',s=35,marker='+')
    ax.annotate('Physical starts',(0,0),xytext=(5,-18),textcoords='offset points',fontsize=8)
    ax.axhline(0,color='grey',lw=.6); ax.axvline(0,color='grey',lw=.6)
    ax.set(xlabel='Routed scan-path net-length upper-bound change (%)',ylabel='Peak local transition change (%)',
           title='Tradeoff relative to physical start | lower activity is negative')
    ax.set_xlim(-.8,18)
    ax.grid(alpha=.15); fig.savefig(OUT/'tradeoff.png',dpi=170); plt.close(fig)
    pact=[r for r in rows if r['architecture']=='PACT']
    if pact:
        keys=['M3_load','M5_hpwl','total_transitions','cap_weighted_ff_transitions','M3_load_local','M5_hpwl_local','peak_local','peak_local_cap_ff']
        labels=['M3 total','M5 total','Transitions','C*N','M3 local','M5 local','Local transitions','Local C*N']
        fig,axs=plt.subplots(1,len(pact),figsize=(13,5),layout='constrained',squeeze=False,sharex=True)
        for ax,r in zip(axs[0],pact):
            vals=[r[k+'_pct_vs_physical_start'] for k in keys]
            ax.barh(labels,vals,color=['#777777']*2+['#21918c']*2+['#777777']*2+['#21918c']*2)
            ax.axvline(0,color='black',lw=.5); ax.set_title(r['design']); ax.set_xlabel('PACT change vs physical start (%)'); ax.invert_yaxis()
        fig.suptitle('Frozen M3/M5 versus independent routed simulation | descriptive only')
        fig.savefig(OUT/'objective_correspondence.png',dpi=170); plt.close(fig)

if __name__=='__main__':
    rows=collect(); plots(rows)
    for r in rows:
        print(r['design'],r['architecture'],{k:r[k] for k in ('total_transitions','peak_transitions','peak_local','cap_weighted_ff_transitions','peak_local_cap_ff')})
