"""Frozen predictor evaluation with separate physical validation and labels."""
from phase2crm_execute import *
import inspect
from copy import deepcopy
import numpy as np
from pact.scan.model import ScanArchitecture
from pact.analysis.phase2cr_loads import construct_with_audit
from pact.analysis.phase2b_loads import construct_weights as legacy, pin_loads
from pact.analysis.phase2b_scoring import score_packed, fixed_bins
import phase2cr_run as repaired

def endpoint_pass(rho,accuracy):
    return rho is not None and accuracy is not None and rho>=.7 and accuracy>=.75

def classify(cells,complete=True):
    prefix='PACT_PHASE2CR_MULTISEED_'
    if not complete:return prefix+'VALIDATION_INCOMPLETE'
    new=[c for c in cells if c['seed']!=11]
    if not new:return prefix+'VALIDATION_INCOMPLETE'
    if all(c['passed'] for c in cells):return prefix+'GENERALIZATION_CONFIRMED'
    if any(c['passed'] for c in new):return prefix+'GENERALIZATION_PARTIAL'
    return prefix+'GENERALIZATION_FAIL'

def effect(dx,dy,left_target):
    pct=100*dy/abs(left_target) if left_target else None
    if dx==0 or dy==0:label='tied'
    elif dx*dy<0:label='directionally_incorrect'
    elif pct is None:label='directionally_correct_materiality_undefined'
    elif abs(pct)<1:label='directionally_correct_physically_negligible'
    else:label='directionally_correct_materially_different'
    return pct,label

def topology_function():
    # Reuse EVERY repaired assertion. Only the hardcoded seed selector is generalized.
    source=inspect.getsource(repaired.topology)
    assert source.count("r['seed']==11")==1
    adapted=source.replace("r['seed']==11","r['seed']==row['seed']")
    namespace=dict(repaired.__dict__)
    exec(compile(adapted,'<reused-phase2cr-topology-seed-adapter>','exec'),namespace)
    return namespace['topology'],source,adapted

def topology():
    verify();assert not (OUT/'topology_audit.json').exists()
    loads=pin_loads(LIB.read_text());contract=read(OUT/'multiseed_contract.json')
    physical=read(OUT/'physical_results.json')['rows'];proofs=[];weight_manifest=[]
    fn,original,adapted=topology_function()
    write(OUT/'topology_adapter.json',dict(original_function_sha256=hashlib.sha256(original.encode()).hexdigest(),
        adapted_function_sha256=hashlib.sha256(adapted.encode()).hexdigest(),
        sole_substitution={"r['seed']==11":"r['seed']==row['seed']"},predictor_source_changed=False))
    for d in DESIGNS:
        for s in contract['new_seeds']:
            group=[r for r in physical if r['design']==d and r['seed']==s]
            views=OUT/'views'/d/f's{s}';q=deepcopy(read(A/'test_quality.json'))
            q[d]['placed_def']=str(ROOT/f'artifacts/raw/phase0b/placements/{d}/s{s}/placed.def')
            write(views/'test_quality.json',q)
            write(views/'architecture_matrix.json',dict(rows=group))
            prow=[]
            for r in group:
                assert r['status']=='QUALIFIED'
                extraction=r['extraction']; ph=read(r['physical_path'])
                assert extraction['inputs'][r['routed_path']]==r['route_sha256']
                check(r['routed_path'],r['route_sha256'])
                for p,h in dict(extraction['inputs'],**extraction['outputs']).items():check(p,h)
                a=ScanArchitecture.from_json(Path(r['architecture_path']))
                assert a.sha256()==r['architecture_sha256']
                # Enrich a COPY with identities already proven by immutable extraction inputs.
                ph.update(architecture_sha256=a.sha256(),odb_sha256=r['route_sha256'])
                path=views/(r['label']+'.physical.json');write(path,ph)
                prow.append(dict(design=d,label=r['label'],physical_path=str(path),physical_sha256=sha(path)))
            write(views/'physical_weighting.json',dict(rows=prow))
            fn.__globals__.update(A=views,C=views)
            for r in group:
                a=ScanArchitecture.from_json(Path(r['architecture_path']));g=read(OUT/'graphs'/f'{d}.s{s}.json')
                names=sorted(c.name for c in a.cells);old=legacy(a,repaired.old_graph(g),loads,g['scan_ports'])
                new,audit=construct_with_audit(a,g,loads)
                row=dict(r,FFs=names,odb_sha256=r['route_sha256'],K=2,
                    cells=[dict(name=c.name,x_um=c.x_um,y_um=c.y_um) for c in a.cells],
                    chains=[dict(chain_id=c.chain_id,cells=list(c.cells)) for c in a.chains])
                proofpath=views/(r['label']+'.proof.json');write(proofpath,r['extraction']['proof']);row['proof_path']=str(proofpath)
                try:
                    proof=fn(row,(a,g,names,old,new,audit),loads)
                    ph=read(r['physical_path']);cap=read(r['reference_path'])
                    assert set(cap)==set(names)==set(ph['FFs'])
                    for c in a.cells:
                        assert (ph['FFs'][c.name]['x_um'],ph['FFs'][c.name]['y_um'])==(c.x_um,c.y_um)
                        predicted={v['net'] for v in audit['FFs'][c.name]}
                        assert predicted==set(ph['FFs'][c.name]['nets']),('electrical ownership',d,s,r['label'],c.name)
                        assert cap[c.name]['effective_ff']>0
                    proof.update(seed=s,electrical_ownership='PASS',coordinate_correspondence='PASS',
                        source_physical_path=r['physical_path'],source_reference_path=r['reference_path'])
                    wp=OUT/'weights'/f'{d}.s{s}.{r["label"]}.json'
                    write(wp,{m:dict(zip(names,map(float,w))) for m,w in new.items()})
                    ap=OUT/'ownership'/f'{d}.s{s}.{r["label"]}.json';write(ap,audit)
                    weight_manifest.append(dict(design=d,seed=s,label=r['label'],path=str(wp),sha256=sha(wp),
                        ownership_audit_path=str(ap),ownership_audit_sha256=sha(ap)))
                    proofs.append(proof)
                    print('TOPOLOGY_PASS',d,s,r['label'],flush=True)
                except Exception as e:
                    write(OUT/'topology_audit.json',dict(status='STOP',reason=repr(e),failed_cell=dict(design=d,seed=s,label=r['label']),rows=proofs))
                    raise
    baseline=read(REPORT/'topology_equivalence.json')['rows']
    proofs.extend(dict(p,seed=11,reused_frozen=True) for p in baseline)
    write(OUT/'topology_audit.json',dict(status='PASS',passed=len(proofs),rows=proofs))
    write(OUT/'predictor_weights_manifest.json',dict(rows=weight_manifest))
    verify()

def measure():
    verify();assert read(OUT/'topology_audit.json')['status']=='PASS'
    assert not (OUT/'measurements.json').exists()
    contract=read(OUT/'multiseed_contract.json');physical=read(OUT/'physical_results.json')['rows']
    rows=[dict(r,seed=11,reused_frozen=True) for r in read(REPORT/'corrected_metrics.json')['rows']]
    weights=read(OUT/'predictor_weights_manifest.json')['rows']
    traces={(r['design'],r['label']):r for r in read(A/'shift_reconstruction.json')['rows']}
    for r in physical:
        if r['seed']==11:continue
        start=time.perf_counter();d,s,label=r['design'],r['seed'],r['label']
        a=ScanArchitecture.from_json(Path(r['architecture_path']));names=sorted(c.name for c in a.cells)
        tr=traces[d,label];check(tr['trace_path'],tr['trace_sha256']);trace=np.load(tr['trace_path'])
        assert trace['names'].tolist()==names
        wrow=next(w for w in weights if (w['design'],w['seed'],w['label'])==(d,s,label));check(wrow['path'],wrow['sha256'])
        w=read(wrow['path']);xy={c.name:(c.x_um,c.y_um) for c in a.cells}
        bins=fixed_bins([xy[n] for n in names],read(CW/d/f's{s}'/'prepared.json')['bounds'])
        rec=dict(design=d,seed=s,label=label,architecture_sha256=a.sha256(),scan_order_sha256=order_hash(a),predictors={},targets={})
        for m in ('M3_load','M5_hpwl'):
            scores,counts=score_packed(trace['toggles_packed'],len(names),[w[m][n] for n in names],bins)
            assert counts.tolist()==[tr['FF_transition_totals'][n] for n in names]
            rec['predictors'][m]=scores['total'];rec['predictors'][m+'_local']=scores['local_peak']
        # Labels are obtained only after predictors are constructed and scored.
        ph=read(r['physical_path']);cap=read(r['reference_path'])
        for prefix,values in [('wire',[ph['FFs'][n]['wire_length_um'] for n in names]),('cap',[cap[n]['effective_ff'] for n in names])]:
            scores,counts=score_packed(trace['toggles_packed'],len(names),values,bins)
            rec['targets'][prefix+'_total']=scores['total'];rec['targets'][prefix+'_local_peak']=scores['local_peak']
        rec.update(runtime_seconds=time.perf_counter()-start,provenance=dict(predictor=wrow,
            trace_path=tr['trace_path'],trace_sha256=tr['trace_sha256'],physical_path=r['physical_path'],
            physical_sha256=sha(r['physical_path']),reference_path=r['reference_path'],reference_sha256=sha(r['reference_path'])))
        rows.append(rec);print('SCORED',d,s,label,flush=True)
    write(OUT/'measurements.json',dict(rows=rows,score_implementation='unchanged phase2b_scoring.score_packed',targets_labels_only=True))
    verify()

if __name__=='__main__':
    {'topology':topology,'measure':measure}[sys.argv[1]]()
