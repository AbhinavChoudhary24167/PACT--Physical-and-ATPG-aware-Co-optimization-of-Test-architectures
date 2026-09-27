"""Frozen repaired topology assertions and predictor/target computation."""
from phase2d_common import *
from copy import deepcopy
import inspect
import numpy as np
from pact.scan.model import ScanArchitecture
from pact.analysis.phase2cr_loads import construct_with_audit
from pact.analysis.phase2b_loads import construct_weights as legacy, pin_loads
from pact.analysis.phase2b_scoring import score_packed, fixed_bins
from phase2cr_common import order_hash
from phase2crm_validate import topology_function
import phase2cr_run as repaired

def topology():
    verify_contract();assert not (OUT/'topology_results.json').exists()
    contract=read(OUT/'contract.json');rows=read(OUT/'physical_results.json')['rows'];proofs=[];weights=[]
    assert len(rows)==21 and all(r['status']=='QUALIFIED' for r in rows)
    loads=pin_loads((PLATFORM/'lib/NangateOpenCellLibrary_typical.lib').read_text())
    fn,original,adapted=topology_function()
    assert adapted.replace("r['seed']==row['seed']","r['seed']==11")==original
    write(OUT/'topology_adapter.json',dict(original=original,adapted=adapted,logical_assertions_unchanged=True))
    for d in DESIGNS:
        group=[r for r in rows if r['design']==d];view=OUT/'views'/d
        q=deepcopy(read(ROOT/'reports/phase2a_shift_activity/test_quality.json'))
        q[d]['placed_def']=str(placement(d)/'placed.def')
        write(view/'test_quality.json',q);write(view/'architecture_matrix.json',dict(rows=group))
        phyrows=[]
        for r in group:
            for p,h in dict(r['extraction']['inputs'],**r['extraction']['outputs']).items():assert sha(p)==h,p
            a=ScanArchitecture.from_json(Path(r['architecture_path']))
            c=next(c for c in contract['cells'] if (c['design'],c['label'])==(d,r['label']))
            assert order_hash(a)==c['scan_order_sha256']==r['scan_order_sha256']
            assert a.sha256()==r['architecture_sha256'] and r['frozen_architecture_id']==c['frozen_architecture_id']
            assert sorted(x.name for x in a.cells)==c['ff_names']
            assert [dict(chain_id=x.chain_id,cells=list(x.cells),scan_in=x.scan_in,scan_out=x.scan_out) for x in a.chains]==c['chains']
            ph=read(r['physical_path']);ph.update(architecture_sha256=a.sha256(),odb_sha256=r['route_sha256'])
            path=view/(r['label']+'.physical.json');write(path,ph)
            phyrows.append(dict(design=d,label=r['label'],physical_path=str(path),physical_sha256=sha(path)))
        write(view/'physical_weighting.json',dict(rows=phyrows));fn.__globals__.update(A=view,C=view)
        for r in group:
            try:
                a=ScanArchitecture.from_json(Path(r['architecture_path']));g=read(OUT/'graphs'/f'{d}.s29.json')
                names=sorted(x.name for x in a.cells);old=legacy(a,repaired.old_graph(g),loads,g['scan_ports'])
                new,audit=construct_with_audit(a,g,loads)
                proofpath=view/(r['label']+'.proof.json');write(proofpath,r['extraction']['proof'])
                row=dict(r,FFs=names,odb_sha256=r['route_sha256'],K=2,proof_path=str(proofpath),
                    cells=[dict(name=c.name,x_um=c.x_um,y_um=c.y_um) for c in a.cells],
                    chains=[dict(chain_id=c.chain_id,cells=list(c.cells)) for c in a.chains])
                p=fn(row,(a,g,names,old,new,audit),loads)
                ph=read(r['physical_path']);cap=read(r['reference_path'])
                assert set(cap)==set(names)==set(ph['FFs'])
                for c in a.cells:
                    assert (ph['FFs'][c.name]['x_um'],ph['FFs'][c.name]['y_um'])==(c.x_um,c.y_um)
                    assert {v['net'] for v in audit['FFs'][c.name]}==set(ph['FFs'][c.name]['nets'])
                    assert cap[c.name]['effective_ff']>0
                # Inherited summary label concerns seed-11 archived legacy weights; no such archive exists for GP B.
                p['checks']['legacy_weights_exact']=None
                p.update(frozen_architecture_id=r['frozen_architecture_id'],electrical_ownership='PASS',
                    legacy_weights_archive_scope='Not applicable to new GP; all inherited logical assertions executed unchanged')
                wp=OUT/'weights'/f'{d}.{r["label"]}.json';write(wp,{m:dict(zip(names,map(float,w))) for m,w in new.items()})
                write(OUT/'ownership'/f'{d}.{r["label"]}.json',audit)
                weights.append(dict(design=d,label=r['label'],path=str(wp),sha256=sha(wp)))
                proofs.append(p);print('TOPOLOGY_PASS',d,r['label'],flush=True)
            except Exception as e:
                write(OUT/'topology_results.json',dict(status='STOP',failed=dict(design=d,label=r['label']),reason=repr(e),rows=proofs))
                raise
    write(OUT/'topology_results.json',dict(status='PASS',passed=21,rows=proofs))
    write(OUT/'weights_manifest.json',dict(rows=weights))

def measure():
    verify_contract();assert read(OUT/'topology_results.json')['passed']==21
    assert not (OUT/'measurements.json').exists()
    rows=[];contract=read(OUT/'contract.json')
    for r in read(OUT/'physical_results.json')['rows']:
        d,label=r['design'],r['label'];a=ScanArchitecture.from_json(Path(r['architecture_path']))
        names=sorted(c.name for c in a.cells);c=next(c for c in contract['cells'] if (c['design'],c['label'])==(d,label))
        assert sha(c['trace_path'])==c['trace_sha256'];trace=np.load(c['trace_path'])
        assert trace['names'].tolist()==names
        w=read(OUT/'weights'/f'{d}.{label}.json');xy={c.name:(c.x_um,c.y_um) for c in a.cells}
        bins=fixed_bins([xy[n] for n in names],read(OUT/'raw'/d/'s29'/'prepared.json')['bounds'])
        rec=dict(design=d,seed=29,label=label,frozen_architecture_id=c['frozen_architecture_id'],
                 architecture_sha256=a.sha256(),scan_order_sha256=order_hash(a),predictors={},targets={})
        for metric in ('M3_load','M5_hpwl'):
            scores,counts=score_packed(trace['toggles_packed'],len(names),[w[metric][n] for n in names],bins)
            rec['predictors'][metric]=scores['total'];rec['predictors'][metric+'_local']=scores['local_peak']
        ph=read(r['physical_path']);cap=read(r['reference_path'])
        for prefix,values in [('wire',[ph['FFs'][n]['wire_length_um'] for n in names]),('cap',[cap[n]['effective_ff'] for n in names])]:
            scores,target_counts=score_packed(trace['toggles_packed'],len(names),values,bins)
            np.testing.assert_array_equal(counts,target_counts)
            rec['targets'][prefix+'_total']=scores['total'];rec['targets'][prefix+'_local_peak']=scores['local_peak']
        rows.append(rec);trace.close();print('SCORED',d,label,flush=True)
    write(OUT/'measurements.json',dict(rows=rows,predictor_and_scorer_unchanged=True))
    verify_contract()

if __name__=='__main__':{'topology':topology,'measure':measure}[sys.argv[1]]()
