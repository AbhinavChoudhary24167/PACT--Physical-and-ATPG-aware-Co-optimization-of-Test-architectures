"""Fresh-process evaluator-only timing; no physical conclusions from synthetic data."""
from phase2c_common import *
import argparse
import resource
import subprocess
import time
import numpy as np
from pact.analysis.phase2c_events import (chain_indices,pattern_inputs,shift_events,
    event_driven_evaluator,reference_packed_evaluator)
from pact.scan.model import ScanArchitecture
from pact.analysis.phase2a_shift import fixed_bins

def pack_reference(chains,inputs,n):
    """Independent cycle-by-cycle reconstruction, no proof instrumentation.

    Packed full history is the Phase-2B scorer input. Build in chunks to avoid
    an artificially inflated dense trace baseline; only 1024 dense cycles live.
    """
    state=np.zeros(n,dtype=np.uint8);chunks=[];chunk=np.empty((1024,n),dtype=np.uint8);used=0
    for values in inputs:
        old=state.copy()
        for c,v in zip(chains,values):
            state[c[0]]=v;state[c[1:]]=old[c[:-1]]
        chunk[used]=state^old;used+=1
        if used==1024:chunks.append(np.packbits(chunk,axis=1));used=0
    if used:chunks.append(np.packbits(chunk[:used],axis=1))
    return np.concatenate(chunks) if chunks else np.empty((0,(n+7)//8),dtype=np.uint8)

def worker(kind,case,repeat):
    if case.startswith('real:'):
        from phase2c_measure import patterns_for
        d=case.split(':')[1];job=next(j for j in read(WORK/d/'s11/prepared.json')['jobs'] if j['label']=='P')
        arch=ScanArchitecture.from_json(Path(job['architecture_path']));names,chains=chain_indices(arch);n=len(names)
        patterns=patterns_for(d);p=len(patterns);cycles=p*max(map(len,chains))
        factory=lambda:pattern_inputs(arch,patterns)
        old=next(r for r in read(OLD/'architecture_set.json') if r['design']==d and r['label']=='P')
        weights_json=read(Path('/mnt/d/PACT_EXPERIMENTS/results/phase2b_activity_model')/old['architecture_sha256']/'predictor_weights.json')
        weights=np.array([weights_json['M3_load'][name] for name in names])
        xy={c.name:(c.x_um,c.y_um) for c in arch.cells}
        bins=fixed_bins([xy[name] for name in names],read(WORK/d/'s11/prepared.json')['bounds'])
    else:
        _,n,mode=case.split(':');n=int(n);p=4;cycles=1024
        chains=[np.arange(n//2),np.arange(n//2,n)]
        # Deterministic bounded SI sequence, four 256-cycle synthetic segments.
        # Dense alternates every clock; sparse injects a single step at cycle 0.
        factory=lambda:((int(t%2) if mode=='dense' else 1,)*2 for t in range(cycles))
        weights=1+(np.arange(n)%17)/17;bins=np.arange(n)%100
    start=time.perf_counter();cpu=time.process_time()
    if kind=='packed':
        packed=pack_reference(chains,factory(),n);generation=time.perf_counter()-start
        tick=time.perf_counter();score,counts=reference_packed_evaluator(packed,n,weights,bins);scoring=time.perf_counter()-tick
        events=int(counts.sum())
    else:
        generation=None;tick=time.perf_counter()
        score,counts=event_driven_evaluator(shift_events(chains,factory()),n,weights,bins,cycles,validate=False)
        scoring=time.perf_counter()-tick;events=score['event_count']
    result=dict(case=case,kind=kind,repeat=repeat,scope='MEASURED',synthetic=not case.startswith('real:'),
        FF_count=n,pattern_count=p if case.startswith('real:') else None,
        synthetic_input_segments=None if case.startswith('real:') else p,
        shift_cycles=cycles,event_count=events,events_per_cycle=events/cycles,
        wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
        peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        generation_seconds=generation,scoring_seconds=scoring,total=score['total'],local_peak=score['local_peak'])
    write(WORK/'benchmarks'/f'{case.replace(":","_")}_{kind}_{repeat}.json',result)
    print(json.dumps(result),flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--kind',choices=['packed','event']);parser.add_argument('--case')
    parser.add_argument('--repeat',type=int,default=0)
    parser.add_argument('--engineering-only',action='store_true',help='Benchmark supplied numeric weights only; makes no physical-definition/generalization claim.')
    args=parser.parse_args()
    if not args.engineering_only:require_open_experiment()
    if args.kind:worker(args.kind,args.case,args.repeat);return
    rows=[];cases=['real:'+d for d in DESIGNS]+[f'synthetic:{n}:{mode}' for n in (1000,10000,100000) for mode in ('sparse','dense')]
    commands=[]
    for case in cases:
        for repeat in range(3):
            for kind in ('packed','event'):
                command=[sys.executable,str(Path(__file__).resolve()),'--kind',kind,'--case',case,'--repeat',str(repeat)]
                if args.engineering_only:command.append('--engineering-only')
                commands.append(command)
                ex=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=600)
                if ex.returncode:raise RuntimeError(ex.stderr)
                row=read(WORK/'benchmarks'/f'{case.replace(":","_")}_{kind}_{repeat}.json');rows.append(row)
                print(case,kind,repeat,row['wall_seconds'],row['peak_RSS_KiB'],flush=True)
                write(REPORT/'benchmark_raw.json',dict(rows=rows,commands=commands))
    summaries=[]
    for case in cases:
        group=[r for r in rows if r['case']==case]
        packed=[r for r in group if r['kind']=='packed'];event=[r for r in group if r['kind']=='event']
        for r in event:
            assert r['event_count']==packed[0]['event_count']
            assert np.isclose(r['total'],packed[0]['total'],rtol=1e-12,atol=1e-10)
            assert np.isclose(r['local_peak'],packed[0]['local_peak'],rtol=1e-12,atol=1e-10)
        median=lambda group,key:float(np.median([r[key] for r in group]))
        pt,et=median(packed,'wall_seconds'),median(event,'wall_seconds')
        pm,em=median(packed,'peak_RSS_KiB'),median(event,'peak_RSS_KiB')
        summaries.append(dict(case=case,FF_count=packed[0]['FF_count'],event_count=packed[0]['event_count'],
            packed_seconds=pt,event_seconds=et,speedup=pt/et,packed_peak_RSS_KiB=pm,event_peak_RSS_KiB=em,
            memory_reduction_fraction=1-em/pm,memory_ratio=pm/em,
            packed_scoring_seconds=median(packed,'scoring_seconds'),synthetic=packed[0]['synthetic']))
    real=[r for r in summaries if not r['synthetic']]
    speed=float(np.median([r['speedup'] for r in real]));memory=float(np.median([r['memory_ratio'] for r in real]))
    write(REPORT/'complexity.json',dict(rows=summaries,real_median_speedup=speed,real_median_memory_ratio=memory,
        engineering_only=args.engineering_only,physical_definition_qualification='WITHHELD_LEGACY_DEFINITION_BUG' if args.engineering_only else 'See generalization_results.json',
        scalability_gate='PASS' if speed>1 and memory>=1 else 'FAIL',
        packed='Time O(P*N + T*N + B*T), T=P*Lmax; chunk working O(1024*(N+B)) plus packed O(N*T/8); input patterns O(P*N).',
        event='Time O(P*N + K*T + E + B*T_active); boundary positions O(N), counts/weights/bins O(N), input-pattern storage O(P*N); no full FF history. B=100 and 81 windows fixed. Uniqueness validation is disabled only for the proven internal producer.',
        dense_regime='E can approach N*T. Dense ATPG switching eliminates sparse advantage; vectorized packed operations can be faster.',
        projections=[dict(FF_count=n,status='EXTRAPOLATED',assumptions='K=2, P=100, toggle density 0.5, uint8 input patterns; conceptual arrays exclude Python object overhead',
            shift_cycles=100*((n+1)//2),toggle_events=.5*n*100*((n+1)//2),
            packed_trace_bytes=n*100*((n+1)//2)/8,event_numeric_state_bytes=40*n,pattern_bytes=100*n)
            for n in (100000,1000000)],
        not_demonstrated=['100k/1M FF physical generalization','million-gate optimizer throughput','technology generalization','causal optimization improvement'],
        measurement='Fresh process per run, three repeats, one BLAS thread. End-to-end includes shift generation plus total/local scoring, excludes common input loading. RSS is absolute whole-process peak including common inputs/imports. Packed generation uses independent chunked state simulation without proof overhead. Real P architectures only; synthetic bounded 1024-cycle streams are separate. The four synthetic patterns in the registration denote four 256-clock stimulus segments, not four complete ATPG loads; pattern_count is null for those cases to avoid implying full-pattern execution.'))

if __name__=='__main__':main()
