"""Independent packed proof and event equivalence on frozen and new evidence."""
from phase2c_common import *
import time
import numpy as np
from pact.scan.model import ScanArchitecture
from pact.test.pattern_parser import parse_fan_pat,map_ppi_patterns
from pact.physical.phase0c_port_policy import frozen_def_ports
from pact.analysis.phase2b_loads import pin_loads,construct_weights
from pact.analysis.phase2a_shift import fixed_bins
from pact.analysis.phase2c_events import (chain_indices,pattern_inputs,shift_events,packed_events,
    event_driven_evaluator,reference_packed_evaluator,packed_peak_witness)

RTOL,ATOL=1e-12,1e-10

def patterns_for(d):
    q=read(A/'test_quality.json')[d]
    return map_ppi_patterns(parse_fan_pat(Path(q['pattern_path'])),read(q['identity_path'])['records'])

def prove_trace(arch,patterns,trace):
    names,chains=chain_indices(arch);n=len(names)
    assert trace['names'].tolist()==names
    packed=trace['toggles_packed'];events=iter(shift_events(chains,pattern_inputs(arch,patterns)))
    actual=next(events,None);expected_count=0
    for cycle,row in enumerate(packed):
        observed=np.zeros(n,dtype=np.uint8)
        if actual is not None and actual[0]==cycle:
            observed[actual[1]]=1;expected_count+=len(actual[1]);actual=next(events,None)
        assert np.array_equal(observed,np.unpackbits(row)[:n]),('event mismatch',cycle)
    assert actual is None
    return expected_count

def compare(events_factory,packed,n,weight,bins):
    ref,rc=reference_packed_evaluator(packed,n,weight,bins)
    got,gc=event_driven_evaluator(events_factory(),n,weight,bins,len(packed),validate=False)
    assert np.array_equal(rc,gc),'Per-FF transition mismatch'
    for k in ref:assert np.isclose(ref[k],got[k],rtol=RTOL,atol=ATOL),(k,ref[k],got[k])
    rw=packed_peak_witness(packed,n,weight,bins)
    # Require the selected witness itself to attain the reference peak. Floating
    # summation can exchange exactly tied windows; explicitly record any such case.
    def value_at(w):
        if w is None:return 0.
        cycle,y,x=w;toggle=np.unpackbits(packed[cycle])[:n]
        keep=np.isin(bins,[y*10+x,(y+1)*10+x,y*10+x+1,(y+1)*10+x+1])
        return float(toggle[keep]@weight[keep])
    assert np.isclose(value_at(got['peak_location']),ref['local_peak'],rtol=RTOL,atol=ATOL)
    assert np.isclose(value_at(rw),got['local_peak'],rtol=RTOL,atol=ATOL)
    return ref,got,dict(status='PASS',counts_exact=True,raw_total=int(gc.sum()),
        reference_peak_location=rw,event_peak_location=got['peak_location'],
        location_exact=rw==got['peak_location'],max_total_abs_error=abs(ref['total']-got['total']),
        max_peak_abs_error=abs(ref['local_peak']-got['local_peak']))

def main():
    require_open_experiment()
    integrity();loads=pin_loads(LIB.read_text());results=[];proofs=[];supplement=[]
    oldrows={(r['design'],r['label']):r for r in read(OLD/'candidate_metrics.json')['rows']}
    traces={(r['design'],r['label']):r for r in read(A/'shift_reconstruction.json')['rows']}
    waves={(r['design'],r['label']):r for r in read(OLD/'waveform_audit.json')['rows']}
    eqfile=REPORT/'evaluator_equivalence.json'
    # Resume verified cells by an explicit content-hashed cache, without replaying
    # completed expensive proof paths after additional routes become available.
    cache_code={str(p):file_sha256(p) for p in (Path(__file__),ROOT/'src/pact/analysis/phase2c_events.py')}
    prior=read(eqfile) if eqfile.exists() else {}
    cache=prior.get('cache',{}) if prior.get('source_hashes')==cache_code else {}
    prior_rows={(r['design'],r['seed'],r['label']):r for r in read(REPORT/'measurements.json')['rows']} if cache else {}
    prior_proofs={(r['design'],r['seed'],r['label']):r for r in prior.get('rows',[])}
    prior_supplement=prior.get('supplementary',[])
    # Primary full trace identity is established independently before any scoring.
    try:
        for row in read(REPORT/'architecture_set.json'):
            d,label=row['design'],row['label'];arch=ScanArchitecture.from_json(Path(row['architecture_path']))
            tr=traces[d,label];assert file_sha256(Path(tr['trace_path']))==tr['trace_sha256']
            with np.load(tr['trace_path']) as trace:
                count=prove_trace(arch,patterns_for(d),trace)
            assert count==sum(tr['FF_transition_totals'].values())
            print('TRACE EXACT',d,label,count,flush=True)
        for row in read(REPORT/'architecture_matrix.json')['rows']:
            if row['status']!='QUALIFIED':continue
            d,s,label=row['design'],row['seed'],row['label'];folder=Path(row['architecture_path']).parent
            arch=ScanArchitecture.from_json(Path(row['architecture_path']));names,chains=chain_indices(arch);n=len(names)
            assert arch.sha256()==row['architecture_sha256'] and order_hash(arch)==row['scan_order_sha256']
            prepared=read(folder.parent/'prepared.json');graph=read(folder.parent/'placed_graph.json')
            assert file_sha256(folder.parent/'placed_graph.json')==prepared['graph_sha256']
            cache_key=f'{d}/{s}/{label}'
            dependencies=[Path(row['architecture_path']),folder.parent/'placed_graph.json',folder.parent/'prepared.json',
                Path(row['physical_path']),Path(row['reference_path']),Path(traces[d,label]['trace_path'])]
            if (folder/'scoring_weights.json').exists():dependencies.append(folder/'scoring_weights.json')
            signature={str(p):file_sha256(p) for p in dependencies}
            key=d,s,label
            if cache.get(cache_key)==signature and key in prior_rows and key in prior_proofs:
                results.append(prior_rows[key]);proofs.append(prior_proofs[key])
                if s==11:supplement.extend(r for r in prior_supplement if r['design']==d and r['label']==label)
                print('REUSED EQUIVALENCE',d,s,label,flush=True);continue
            ports,units=frozen_def_ports(placed_def(d,s),2)
            start=time.perf_counter()
            weights=construct_weights(arch,graph,loads,{k:[v/units for v in xy] for k,xy in ports.items()})
            construction=time.perf_counter()-start
            assert np.array_equal(weights['M3_load'],weights['M4_pin']+.103981*weights['M5_hpwl'])
            xy={c.name:(c.x_um,c.y_um) for c in arch.cells}
            bins=fixed_bins([xy[n] for n in names],prepared['bounds'])
            phy=read(row['physical_path']);cap=read(row['reference_path'])
            weights.update(wire=np.array([phy['FFs'][n]['wire_length_um'] for n in names]),
                cap=np.array([cap[n]['effective_ff'] for n in names]))
            with np.load(traces[d,label]['trace_path']) as trace:packed=trace['toggles_packed']
            patterns=patterns_for(d)
            factory=lambda:shift_events(chains,pattern_inputs(arch,patterns))
            rec=dict(design=d,seed=s,label=label,architecture_sha256=arch.sha256(),scan_order_sha256=order_hash(arch),
                wire_cap_per_um=.103981,predictors={},targets={},weight_construction_seconds=construction)
            erow=dict(design=d,seed=s,label=label,checks={})
            counts=None
            for m in ('M0','M3_load','M5_hpwl','wire','cap'):
                ref,got,proof=compare(factory,packed,n,weights[m],bins)
                erow['checks'][m]=proof
                kind='targets' if m in ('wire','cap') else 'predictors'
                total=m+'_total' if kind=='targets' else m
                local=m+'_local_peak' if kind=='targets' else m+'_local'
                rec[kind][total]=got['total'];rec[kind][local]=got['local_peak']
                if s==11:
                    for key,value in ((total,got['total']),(local,got['local_peak'])):
                        assert np.isclose(value,oldrows[d,label][kind][key],rtol=RTOL,atol=ATOL)
            if s==11 and (d,label) in waves:
                wave=waves[d,label];assert file_sha256(Path(wave['trace_path']))==wave['trace_sha256']
                with np.load(wave['trace_path']) as wt:wp=wt['toggles_packed']
                # Arbitrary captures inject transitions; independent packed adapter
                # validates accumulation. Shift propagation is separately proved above.
                for m in ('M0','M3_load','M5_hpwl','wire','cap'):
                    _,_,proof=compare(lambda:packed_events(wp,n),wp,n,weights[m],bins)
                    supplement.append(dict(design=d,label=label,metric=m,**proof))
            write(folder/'scoring_weights.json',{m:dict(zip(names,map(float,w))) for m,w in weights.items()})
            signature[str(folder/'scoring_weights.json')]=file_sha256(folder/'scoring_weights.json')
            rec['dimensions']=dict(FF_count=n,pattern_count=len(patterns),longest_chain=max(map(len,chains)),
                shift_cycles=len(packed),events=erow['checks']['M0']['raw_total'],placed_instance_count=prepared['placed_instance_count'])
            results.append(rec);proofs.append(erow)
            cache[cache_key]=signature
            write(REPORT/'measurements.json',dict(rows=results))
            write(eqfile,dict(status='IN_PROGRESS',rows=proofs,supplementary=supplement,rtol=RTOL,atol=ATOL,cache=cache,source_hashes=cache_code))
            print('EQUIVALENT',d,s,label,flush=True)
        # Compare ranks and correlations with the independent packed path, without
        # accepting a tolerance for ordering. Recompute packed metrics for all rows.
        from phase2b_report import analyze
        ordering=[]
        for s in SEEDS:
            group=[r for r in results if r['seed']==s];reference=[]
            for r in group:
                d,label=r['design'],r['label'];job=next(j for j in read(WORK/d/f's{s}'/'prepared.json')['jobs'] if j['label']==label)
                arch=ScanArchitecture.from_json(Path(job['architecture_path']));names,_=chain_indices(arch)
                folder=Path(job['architecture_path']).parent;w=read(folder/'scoring_weights.json');prep=read(folder.parent/'prepared.json')
                coords={c.name:(c.x_um,c.y_um) for c in arch.cells};bins=fixed_bins([coords[n] for n in names],prep['bounds'])
                with np.load(traces[d,label]['trace_path']) as trace:packed=trace['toggles_packed']
                rr=dict(design=d,label=label,predictors={},targets={})
                for m in ('M0','M3_load','M5_hpwl','wire','cap'):
                    score,_=reference_packed_evaluator(packed,len(names),[w[m][n] for n in names],bins)
                    kind='targets' if m in ('wire','cap') else 'predictors'
                    rr[kind][m+'_total' if kind=='targets' else m]=score['total']
                    rr[kind][m+'_local_peak' if kind=='targets' else m+'_local']=score['local_peak']
                reference.append(rr)
            if not group:continue
            ec,er,ep=analyze(group);rc,rr,rp=analyze(reference)
            for d in ec['per_design']:
                for m,t in ENDPOINTS:
                    assert ec['per_design'][d][m][t]['spearman']==rc['per_design'][d][m][t]['spearman']
                    assert [p['direction'] for p in ep[d][m][t]['pairs']]==[p['direction'] for p in rp[d][m][t]['pairs']]
                for kind in er[d]:
                    for m in er[d][kind]:assert [r['label'] for r in er[d][kind][m]]==[r['label'] for r in rr[d][kind][m]]
            ordering.append(dict(seed=s,status='PASS',exact_rankings=True,exact_spearman=True,exact_pair_directions=True))
        write(eqfile,dict(status='PASS',primary_traces=21,rows=proofs,supplementary=supplement,ordering=ordering,
            cache=cache,source_hashes=cache_code,
            rtol=RTOL,atol=ATOL,integer_equality='EXACT',primary_propagation='Every event/cycle compared against saved independent full traces',
            supplementary_scope='Accumulator equality on all capture/unload packed traces; no capture-state production generator claimed'))
    except Exception as error:
        write(eqfile,dict(status='EVENT_EVALUATOR_EQUIVALENCE_FAIL',reason=repr(error),rows=proofs,supplementary=supplement))
        raise

if __name__=='__main__':main()
