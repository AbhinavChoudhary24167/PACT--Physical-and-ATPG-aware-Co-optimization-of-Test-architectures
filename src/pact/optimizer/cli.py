"""pact-optimize entrypoint. Outputs are atomically checkpointed during search."""
import argparse
import cProfile
from dataclasses import asdict
import json
import hashlib
from pathlib import Path
import platform
import time
import numpy as np
from .io import load_design,load_bundle,synthetic,architecture_from,write_json
from .search import Config,METRICS,optimize
from .costs import ShiftState


def warmup():
    # Compile all kernels before the search clock. Cold startup is reported.
    a,c,p,s,_=synthetic(8,2,2)
    state=ShiftState(c,p,s[0][1])
    undo=state.change({0:(np.array([0,1]),np.array([1,0]))})
    state.score();state.change(undo)


def peak_rss():
    if platform.system()!='Windows':
        import resource
        value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value if platform.system()=='Darwin' else value*1024)
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    counters=Counters();counters.cb=ctypes.sizeof(counters)
    kernel=ctypes.WinDLL('kernel32');kernel.GetCurrentProcess.restype=wintypes.HANDLE
    if not ctypes.WinDLL('psapi').GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):return None
    return int(counters.PeakWorkingSetSize)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--design',choices=('s5378','s9234','s15850'))
    source.add_argument('--input',type=Path)
    source.add_argument('--synthetic',type=int,metavar='N')
    parser.add_argument('--chains',type=int)
    parser.add_argument('--patterns',type=int,default=4,help='Synthetic full ATPG-style loads only')
    parser.add_argument('--time-budget',type=float,default=60)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--wire-allowance',type=float,default=.10)
    parser.add_argument('--archive-size',type=int,default=16)
    parser.add_argument('--seed',type=int,default=11)
    parser.add_argument('--liberty',type=Path)
    parser.add_argument('--profile',action='store_true')
    args=parser.parse_args();start=time.perf_counter()
    config=Config(time_budget=args.time_budget,archive_size=args.archive_size,wire_allowance=args.wire_allowance,seed=args.seed)
    if args.synthetic:data=synthetic(args.synthetic,args.chains,args.patterns)
    elif args.input:data=load_bundle(args.input,args.chains or 2)
    else:data=load_design(Path(__file__).resolve().parents[3],args.design,args.chains or 2,args.liberty)
    arch,costs,patterns,starts,meta=data
    if len({c.clock_domain for c in arch.cells})!=1:raise ValueError('This milestone supports one clock domain; partition domains before optimization')
    if any(list(map(len,s[1]))!=list(map(len,starts[0][1])) for s in starts):raise ValueError('Start chain capacities differ')
    load_seconds=time.perf_counter()-start
    tick=time.perf_counter();warmup();warmup_seconds=time.perf_counter()-tick
    args.output.mkdir(parents=True,exist_ok=True)
    # Always leave a valid supplied architecture, even if no exact score fits.
    arch.to_json(args.output/'supplied.architecture.json')
    write_json(args.output/'ff_names.json',costs.names,compact=True)
    def checkpoint(rows,progress):
        write_json(args.output/'checkpoint.json',dict(schema='indexed_scan_chains_v1',names_file='ff_names.json',progress=progress,frontier=[dict(label=r['label'],metrics=dict(zip(METRICS,r['score'].tolist())),chains=[o.tolist() for o in r['orders']]) for r in rows]),compact=True)
    profiler=cProfile.Profile() if args.profile else None
    if profiler:profiler.enable()
    result=optimize(costs,patterns,starts,config,checkpoint)
    if profiler:
        profiler.disable();profiler.dump_stats(str(args.output/'profile.pstats'))
        import pstats
        with (args.output/'profile.txt').open('w') as handle:pstats.Stats(profiler,stream=handle).strip_dirs().sort_stats('cumtime').print_stats(30)
    rows=result.pop('archive');result.pop('fallback_orders',None)
    recommended=result.pop('recommended',None)
    front=[]
    for i,row in enumerate(rows):
        if len(arch.cells)>10000:
            path=args.output/f'pareto_{i:02d}.chains.json'
            digest=hashlib.sha256()
            for o in row['orders']:
                digest.update(len(o).to_bytes(8,'little'));digest.update(np.asarray(o,dtype='<i4').tobytes())
            write_json(path,dict(schema='indexed_scan_chains_v1',cells_from='supplied.architecture.json',names_file='ff_names.json',chains=[o.tolist() for o in row['orders']]),compact=True)
            identity=dict(format='indexed_scan_chains_v1',chain_order_sha256=digest.hexdigest())
        else:
            path=args.output/f'pareto_{i:02d}.architecture.json'
            selected=architecture_from(arch,costs,row['orders']);selected.to_json(path)
            identity=dict(format='canonical_scan_architecture',architecture_sha256=selected.sha256())
        front.append(dict(label=row['label'],metrics=dict(zip(METRICS,row['score'].tolist())),architecture=str(path.resolve()),**identity))
    if recommended is not None:
        selected_arch=architecture_from(arch,costs,recommended['orders'])
        selected_arch.to_json(args.output/'optimized.architecture.json')
        selected=dict(label=recommended['label'],metrics=dict(zip(METRICS,recommended['score'].tolist())),
                      architecture=str((args.output/'optimized.architecture.json').resolve()),architecture_sha256=selected_arch.sha256())
    else:
        selected=None;arch.to_json(args.output/'optimized.architecture.json')
    result.update(meta,config=asdict(config),FF_count=len(arch.cells),K=len(arch.chains),pattern_count=len(patterns),
                  longest_chain=max(len(c.cells) for c in arch.chains),archive=front,selected=selected,
                  input_load_seconds=load_seconds,kernel_warmup_seconds=warmup_seconds,
                  peak_RSS_bytes=peak_rss(),command_seconds_after_import=time.perf_counter()-start,
                  activity_semantics='zero initial; carry loaded; no capture/final unload; fixed 10x10 bins; 81 contained 2x2 windows',
                  budget_scope='optimizer preprocessing, constructors, exact scoring, search and checkpoints; excludes input loading, JIT warmup, final serialization; cooperative between chains/moves')
    write_json(args.output/'result.json',result)
    write_json(args.output/'convergence.json',result['convergence'])
    print(json.dumps({k:result[k] for k in ('status','design','FF_count','K','runtime_seconds','evaluations','peak_RSS_bytes','selected')},allow_nan=False),flush=True)


if __name__=='__main__':main()
