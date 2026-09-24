"""Bounded Pareto search with spatial construction and exact local transactions.

No weighted objective sum. Five qualified quantities are retained separately;
acceptance uses rotating epsilon constraints / lexicographic preferences.
The explicit wire allowance is an engineering choice, not a physical guarantee.
"""
from dataclasses import dataclass
import time
import numpy as np
from scipy.spatial import cKDTree
from .costs import ShiftState

METRICS=('scan_hpwl_um','M3_load','M3_load_local','M5_hpwl','M5_hpwl_local')


@dataclass(frozen=True)
class Config:
    time_budget: float=60.
    archive_size: int=16
    neighbors: int=16
    segment: int=8
    wire_allowance: float=.10
    seed: int=11
    log_interval: float=1.

    def __post_init__(self):
        if not np.isfinite(self.time_budget) or self.time_budget<=0: raise ValueError('time budget must be positive')
        if self.archive_size<5 or self.neighbors<1 or self.segment<2: raise ValueError('Invalid search bounds')
        if not np.isfinite(self.wire_allowance) or self.wire_allowance<0: raise ValueError('Invalid wire allowance')
        if not np.isfinite(self.log_interval) or self.log_interval<=0: raise ValueError('Invalid log interval')


def dominates(a,b):
    tol=1e-9*np.maximum(1.,np.maximum(np.abs(a),np.abs(b)))
    return bool(np.all(a<=b+tol) and np.any(a<b-tol))


class Archive:
    def __init__(self,maximum): self.maximum=maximum;self.rows=[];self.admissions=0

    def insert(self,score,orders,label):
        kept=self.rows.copy()
        if self.rows:
            values=np.array([r['score'] for r in self.rows])
            tol=1e-9*np.maximum(1.,np.maximum(np.abs(values),np.abs(score)))
            superior=np.all(values<=score+tol,axis=1)&np.any(values<score-tol,axis=1)
            equal=np.all(np.abs(values-score)<=1e-8+1e-10*np.abs(score),axis=1)
            if np.any(superior|equal):return False
            inferior=np.all(score<=values+tol,axis=1)&np.any(score<values-tol,axis=1)
            kept=[r for i,r in enumerate(self.rows) if not inferior[i]]
        item=dict(score=score.copy(),orders=None,label=label)
        kept.append(item)
        if len(kept)>self.maximum:
            # NSGA-style crowding protects coordinate extremes. Bound is fixed.
            values=np.array([r['score'] for r in kept]);dist=np.zeros(len(kept))
            for q in range(values.shape[1]):
                order=np.argsort(values[:,q],kind='stable');span=np.ptp(values[:,q])
                if span<=1e-10: continue
                dist[order[0]]=dist[order[-1]]=np.inf
                dist[order[1:-1]]+=(values[order[2:],q]-values[order[:-2],q])/span
            dropped=int(np.argmin(dist))
            if kept[dropped] is item: return False
            kept.pop(dropped)
        item['orders']=[o.copy() for o in orders]
        self.rows=kept;self.admissions+=1
        return True


def spatial_order(xy):
    """Morton grid hierarchy, O(N log N) sort and O(N) scratch."""
    span=np.maximum(np.ptp(xy,axis=0),1e-12)
    ij=np.minimum(65535,((xy-xy.min(axis=0))/span*65535)).astype(np.uint64)
    code=np.zeros(len(xy),np.uint64)
    for bit in range(16):
        code |= ((ij[:,0]>>bit)&1)<<(2*bit)
        code |= ((ij[:,1]>>bit)&1)<<(2*bit+1)
    return np.argsort(code,kind='stable').astype(np.int32)


def construct(costs,patterns,capacities,mode,deadline):
    """Greedy inside <=32-FF spatial leaves; bounded deterministic diversity."""
    order=spatial_order(costs.xy)
    if mode=='activity':
        # Pattern signature order is a global activity-only alternative, no N².
        packed=np.packbits(patterns.T,axis=1)
        order=np.lexsort(tuple(packed[:,i] for i in reversed(range(packed.shape[1])))).astype(np.int32)
    result=[];cursor=0
    for ci,capacity in enumerate(capacities):
        group=[];previous=costs.inputs[ci]
        for start in range(cursor,cursor+capacity,32):
            if time.perf_counter()>=deadline: raise TimeoutError('Constructor deadline')
            remaining=order[start:min(cursor+capacity,start+32)].tolist()
            while remaining:
                ids=np.asarray(remaining)
                distance=np.abs(costs.xy[ids]-previous).sum(axis=1)
                if mode=='hybrid' and group:
                    # Epsilon-restricted choice, no scalarized final objective.
                    shortlist=np.argsort(distance,kind='stable')[:min(8,len(ids))]
                    activity=np.count_nonzero(patterns[:,ids[shortlist]]!=patterns[:,group[-1],None],axis=0)
                    pick=int(shortlist[np.lexsort((distance[shortlist],activity))[0]])
                elif mode=='activity': pick=0
                else: pick=int(np.argmin(distance))
                node=remaining.pop(pick);group.append(node);previous=costs.xy[node]
        result.append(np.asarray(group,np.int32));cursor+=capacity
    return result


def proposal(state,neighbor,rng,iteration,segment):
    n=len(state.costs.names)
    first=int(rng.integers(n));ci=int(state.chain_of[first]);p=int(state.position[first])
    a=state.orders[ci];kind=iteration%5
    if kind in (0,1):
        second=int(neighbor[first,int(rng.integers(neighbor.shape[1]))]) if kind==0 else int(rng.integers(n))
        if first==second:return None,'noop'
        cj=int(state.chain_of[second]);q=int(state.position[second])
        if ci==cj:return {ci:(np.array([p,q]),np.array([second,first]))},'swap'
        return {ci:(np.array([p]),np.array([second])),cj:(np.array([q]),np.array([first]))},'cross_chain_swap'
    length=min(int(rng.integers(2,segment+1)),len(a)-p)
    if length<2:return None,'noop'
    positions=np.arange(p,p+length)
    if kind==2:return {ci:(positions,a[positions][::-1].copy())},'2opt'
    if kind==3:return {ci:(positions,np.roll(a[positions],-1))},'relocate'
    # Equal length segment exchange includes bounded tail exchange; capacities
    # and ATPG shift-cycle count remain fixed, no empty-chain special cases.
    cj=int(rng.integers(len(state.orders)))
    if cj==ci:return None,'noop'
    b=state.orders[cj];length=min(length,len(b))
    q=len(b)-length if iteration%2 else int(rng.integers(len(b)-length+1))
    left=np.arange(p,p+length);right=np.arange(q,q+length)
    return {ci:(left,b[right].copy()),cj:(right,a[left].copy())},'segment_exchange'


def locate(state):
    n=len(state.costs.names);state.chain_of=np.empty(n,np.int32);state.position=np.empty(n,np.int32)
    for ci,o in enumerate(state.orders):state.chain_of[o]=ci;state.position[o]=np.arange(len(o))


def update_locations(state,patch):
    for ci,(positions,_) in patch.items():
        nodes=state.orders[ci][positions];state.chain_of[nodes]=ci;state.position[nodes]=positions


def optimize(costs,patterns,starts,config=Config(),checkpoint=None):
    started=time.perf_counter();deadline=started+config.time_budget
    archive=Archive(config.archive_size);evaluations=accepted=attempts=0
    timings=dict(initialization=0.,construction=0.,delta=0.,reduction=0.,archive=0.,restart=0.)
    baseline=[];log=[];operators={};state=None;best=np.full(5,np.inf)
    next_log=started;peak_state_bytes=0;recommended=None
    supplied=starts[0][1];capacities=list(map(len,supplied))
    def record(label):
        nonlocal next_log
        row=dict(seconds=time.perf_counter()-started,evaluations=evaluations,accepted_moves=accepted,
                 archive_size=len(archive.rows),best=dict(zip(METRICS,map(float,best))),stage=label,
                 frontier=[r['score'].tolist() for r in archive.rows])
        if recommended is not None:row['recommended']=dict(zip(METRICS,recommended['score'].tolist()))
        log.append(row);next_log=time.perf_counter()+config.log_interval
        if checkpoint:checkpoint(archive.rows+([dict(recommended,label='recommended')] if recommended is not None else []),row)
    # Initial exact scoring is indivisible per chain, with checks between chains.
    for label,orders in starts:
        if time.perf_counter()>=deadline:break
        tick=time.perf_counter()
        try: candidate=ShiftState(costs,patterns,orders,deadline)
        except TimeoutError:break
        timings['initialization']+=time.perf_counter()-tick
        score=np.r_[candidate.physical,candidate.metrics];evaluations+=1
        best=np.minimum(best,score);peak_state_bytes=max(peak_state_bytes,candidate.bytes)
        archive.insert(score,candidate.orders,label)
        baseline.append(dict(label=label,metrics=dict(zip(METRICS,map(float,score)))))
        if state is None or score[0]<state.physical:state=candidate
        record(label)
    for mode in ('physical','hybrid','activity'):
        if time.perf_counter()>=deadline:break
        tick=time.perf_counter()
        try: orders=construct(costs,patterns,capacities,mode,deadline)
        except TimeoutError:break
        timings['construction']+=time.perf_counter()-tick
        tick=time.perf_counter()
        try:candidate=ShiftState(costs,patterns,orders,deadline)
        except TimeoutError:break
        timings['initialization']+=time.perf_counter()-tick
        score=np.r_[candidate.physical,candidate.metrics];evaluations+=1
        best=np.minimum(best,score);peak_state_bytes=max(peak_state_bytes,candidate.bytes)
        archive.insert(score,candidate.orders,'constructed_'+mode)
        baseline.append(dict(label='constructed_'+mode,metrics=dict(zip(METRICS,map(float,score)))))
        if state is None or score[0]<state.physical:state=candidate
        record(mode)
    if state is None:
        return dict(status='BUDGET_EXHAUSTED_BEFORE_EXACT_SCORE',archive=[],baselines=baseline,
                    runtime_seconds=time.perf_counter()-started,evaluations=evaluations,convergence=log,
                    fallback_orders=supplied)
    locate(state);current=np.r_[state.physical,state.metrics]
    physical_reference=min(r['metrics']['scan_hpwl_um'] for r in baseline)
    reference=min(baseline,key=lambda r:r['metrics']['scan_hpwl_um'])['metrics']
    cap=physical_reference*(1+config.wire_allowance)
    def consider(score,orders,label):
        nonlocal recommended
        # Preserve a deliverable independently of diversity pruning. Both local
        # peaks must stay within the strongest physical start's values.
        if (score[0]<=cap+1e-8 and score[2]<=reference['M3_load_local']+1e-8
                and score[4]<=reference['M5_hpwl_local']+1e-8
                and (recommended is None or score[1]<recommended['score'][1]-1e-7)):
            recommended=dict(score=score.copy(),orders=[o.copy() for o in orders],label=label)
    consider(current,state.orders,'physical_start')
    for row in archive.rows:consider(row['score'],row['orders'],row['label'])
    tick=time.perf_counter()
    _,neighbor=cKDTree(costs.xy).query(costs.xy,k=min(len(costs.names),config.neighbors+1),workers=1)
    neighbor=np.asarray(neighbor,np.int32).reshape(len(costs.names),-1)
    timings['construction']+=time.perf_counter()-tick
    rng=np.random.default_rng(config.seed);stalled=0;epoch=0
    while time.perf_counter()<deadline:
        patch,kind=proposal(state,neighbor,rng,attempts,config.segment);attempts+=1
        if patch is None:continue
        old=current.copy();tick=time.perf_counter();undo=state.change(patch)
        timings['delta']+=time.perf_counter()-tick
        tick=time.perf_counter();score=state.score();timings['reduction']+=time.perf_counter()-tick
        evaluations+=1;operators[kind]=operators.get(kind,0)+1
        consider(score,state.orders,kind)
        best=np.minimum(best,score)
        tick=time.perf_counter();admitted=archive.insert(score,state.orders,kind)
        timings['archive']+=time.perf_counter()-tick
        # Rotate among pure physical and activity endpoints under wire caps.
        priority=(0,1,2,3,4)[epoch%5]
        improved=score[priority]<old[priority]-1e-9*max(1.,abs(old[priority]))
        take=dominates(score,old) or (improved and (priority==0 or score[0]<=cap))
        if take:
            current=score;accepted+=1;stalled=0;update_locations(state,patch)
        else:
            tick=time.perf_counter();state.change(undo);state.physical=float(old[0])
            timings['delta']+=time.perf_counter()-tick;current=old;stalled+=1
        if time.perf_counter()>=next_log:record('search')
        if stalled>=64 or attempts%128==0:
            epoch+=1;stalled=0
            priority=epoch%5
            eligible=[r for r in archive.rows if r['score'][0]<=cap or priority==0]
            if not eligible:eligible=archive.rows
            parent=min(eligible,key=lambda r:(r['score'][priority],r['score'][0]))
            # Restart only when useful; initialization has cooperative deadline.
            if not np.allclose(current,parent['score'],rtol=1e-10):
                tick=time.perf_counter()
                try:replacement=ShiftState(costs,patterns,parent['orders'],deadline)
                except TimeoutError:break
                state=replacement;locate(state);current=np.r_[state.physical,state.metrics]
                timings['restart']+=time.perf_counter()-tick
    record('complete')
    elapsed=time.perf_counter()-started
    return dict(status='WORKING_SOLVER',archive=archive.rows,baselines=baseline,convergence=log,
                runtime_seconds=elapsed,budget_overrun_seconds=max(0.,elapsed-config.time_budget),
                evaluations=evaluations,local_evaluations=sum(operators.values()),accepted_moves=accepted,
                evaluations_per_second=sum(operators.values())/max(elapsed,1e-9),
                operators=operators,timings=timings,peak_state_bytes=peak_state_bytes,
                neighbor_bytes=neighbor.nbytes,archive_bytes=sum(o.nbytes for r in archive.rows for o in r['orders']),
                physical_reference_um=physical_reference,wire_allowance=config.wire_allowance,
                recommended=recommended,recommendation_constraints=dict(wire_cap_um=cap,
                M3_load_local_max=reference['M3_load_local'],M5_hpwl_local_max=reference['M5_hpwl_local']))
