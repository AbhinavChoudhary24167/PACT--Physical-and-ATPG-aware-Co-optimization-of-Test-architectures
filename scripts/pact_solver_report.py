#!/usr/bin/env python3
"""Compact engineering summary of completed solver runs; no new experiments."""
import csv
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/working_solver'
DATA=OUT/'final'


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def main():
    real=[read(DATA/d/'result.json') for d in ('s5378','s9234','s15850')]
    scaling=[dict(read(p),case=p.parent.name) for p in sorted(DATA.glob('scaling_*/result.json'))]
    extra=DATA/'s15850_300/result.json'
    long=read(extra) if extra.exists() else None
    rows=[]
    for run in real:
        for row in run['baselines']:
            rows.append(dict(design=run['design'],method=row['label'],**row['metrics']))
        rows.append(dict(design=run['design'],method='PACT_recommended',**run['selected']['metrics']))
        rows.append(dict(design=run['design'],method='PACT_physical_extreme',**min(run['archive'],key=lambda r:r['metrics']['scan_hpwl_um'])['metrics']))
    with (OUT/'comparison.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    text=['# PACT solution status','','**WORKING_SOLVER** — exact incremental scan-order search, with measured tradeoffs and bounded routing.','',
          '## Real placed designs, 60-second solver budget','',
          'Seed 11, K=2, original mapped ATPG patterns. Deltas compare with the strongest existing physical start: P on s5378/s15850, T on s9234. Negative activity deltas are improvements. The default 10% scan-HPWL allowance is an explicit configurable engineering constraint, not a routed-wire guarantee.','',
          '| Design | FF / patterns | Solver s | Peak RSS MiB | Local eval/s | Scan HPWL Δ | M3 total Δ | M3 local Δ | M5 total Δ | M5 local Δ |',
          '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    pending=[name for name in ('scaling_50000','scaling_100000','scaling_100000_k2','s15850_300') if not (DATA/name/'result.json').exists()]
    for design in ('s5378','s9234','s15850'):
        route_path=OUT/'routes'/design/'summary.json'
        if not route_path.exists() or sum(not r['reused'] for r in read(route_path))<2:pending.append(design+'_route_shortlist')
    if pending:text[4:4]=['This snapshot contains completed measurements. Still in progress: '+', '.join(pending)+'.','']
    for run in real:
        base=min((r for r in run['baselines'] if r['label'] in ('P','T')),key=lambda r:r['metrics']['scan_hpwl_um'])['metrics'];selected=run['selected']['metrics']
        delta=[100*(selected[k]/base[k]-1) for k in base]
        text.append(f"| {run['design']} | {run['FF_count']} / {run['pattern_count']} | {run['runtime_seconds']:.3f} | {run['peak_RSS_bytes']/2**20:.1f} | {run['evaluations_per_second']:.1f} | "+' | '.join(f'{v:+.2f}%' for v in delta)+' |')
    text+=['','The full B0/P/A/J50/T/constructor and PACT objective table is in [comparison.csv](reports/working_solver/comparison.csv). These are five separate objectives; PACT does not claim one architecture dominates every baseline. J50/A retain useful lower-activity, higher-wire tradeoffs. The archive also contains a physical extreme whose local hotspots can be worse than P.','',
           '## Algorithm scaling only','',
           'Synthetic random spatial coordinates and four complete binary target loads; zero initial state and carry between patterns. These are not truncated shift prefixes and provide no evidence of physical-design superiority. Default K bounds chain length at 500; the separately named long-chain run fixes K=2.','',
           '| Case | N | K | Lmax | Solver s | Peak RSS MiB | Local eval/s | Evaluations | Δ wire | Δ M3 total |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for run in sorted(scaling,key=lambda r:(r['FF_count'],r['K'])):
        base=min(run['baselines'],key=lambda r:r['metrics']['scan_hpwl_um'])['metrics']
        selected=run['selected']['metrics']
        dw=100*(selected['scan_hpwl_um']/base['scan_hpwl_um']-1);da=100*(selected['M3_load']/base['M3_load']-1)
        text.append(f"| {run['case']} | {run['FF_count']} | {run['K']} | {run['longest_chain']} | {run['runtime_seconds']:.3f} | {run['peak_RSS_bytes']/2**20:.1f} | {run.get('evaluations_per_second',0):.1f} | {run['evaluations']} | {dw:+.2f}% | {da:+.2f}% |")
    text+=['','Synthetic deltas compare the recommendation with its strongest physical start, not a random-order baseline. Higher throughput alone is not a quality guarantee: restarting less often changes the explored tradeoffs. RSS is absolute process peak, including interpreter, imports, JIT and input data. Solver time excludes loading/JIT/final serialization; results separately record loading, JIT warmup and command wall time after imports. Cooperative deadlines can overrun by an indivisible move, chain initialization or checkpoint. No claim of universal O(N log N) end-to-end time is made.','',
           'The fixed-two-chain 100K test exposes the remaining scaling limit: long-chain field initialization and exact peak reduction substantially reduce throughput and increase peak memory. The 1 GiB guard applies to one activity field, not the whole process; simultaneous initialization fields, FFT scratch and input data add memory. The default 200-chain case demonstrates practical bounded-chain scaling, not equivalent performance for arbitrary K or pattern counts.','',
           '## Anytime recommendation','',
           'M3 total at the last recorded checkpoint at or before each time. Local peaks may trade within their fixed ceilings; the constrained recommendation’s total is monotone.','',
           '| Design/run | 10 s | 30 s | 60 s | 300 s |','|---|---:|---:|---:|---:|']
    for run in real+([long] if long else []):
        values=[]
        for t in (10,30,60,300):
            entries=[r for r in run['convergence'] if r['seconds']<=t and r.get('recommended')]
            if t>run['config']['time_budget']:values.append('—')
            else:values.append(f"{entries[-1]['recommended']['M3_load']:.0f}" if entries else 'not yet scored')
        text.append('| '+run['design']+f" ({run['config']['time_budget']:g}s) | "+' | '.join(values)+' |')
    if long:
        base=min(long['baselines'],key=lambda r:r['metrics']['scan_hpwl_um'])['metrics']
        gain=100*(long['selected']['metrics']['M3_load']/base['M3_load']-1)
        text+=['',f"The extended s15850 run used {long['runtime_seconds']:.3f} s, {long['peak_RSS_bytes']/2**20:.1f} MiB peak RSS and {long['evaluations']} evaluations; final M3 total changed {gain:+.2f}% versus its strongest physical start. The table follows each run independently: wall-clock restart decisions can change the search path between separate runs with the same random seed."]
    text+=['','The 300-second extension measures convergence and is independently rescored. It is not routed; all new routed selections below come from the 60-second runs.','',
           '## Routed outcomes','',
           'At most six architectures in each final comparison: four exact-order, archive-hash-verified historical baselines, plus the new recommendation and physical extreme. Baselines are B0/P/A/J50 on s5378/s15850; s9234 substitutes T for A because T is its stronger physical start and J50 already improves on A in total activity. J50 is the strongest existing total-activity start on all three inputs. The length below is the **full scan-path-net routed upper bound**, including shared functional nets; exact isolated scan length is unavailable. Routing does not establish signoff power or IR-drop improvement.','',
           '| Design | Role | Reused | Status | DRC | Routed path-net upper bound µm | Route s |','|---|---|---|---|---:|---:|---:|']
    route_count=0;route_deltas=[]
    for design in ('s5378','s9234','s15850'):
        path=OUT/'routes'/design/'summary.json'
        if not path.exists():continue
        routes=read(path)
        physical_label='T' if design=='s9234' else 'P'
        physical=next(r for r in routes if r['role']==physical_label)
        recommendation=next((r for r in routes if r['role']=='recommended'),None)
        length_key='routed_full_scan_path_net_length_upper_bound_um'
        if recommendation and recommendation.get(length_key) is not None:
            delta=100*(recommendation[length_key]/physical[length_key]-1)
            route_deltas.append(f'{design} {delta:+.2f}% versus {physical_label}')
        for r in routes:
            route_count+=int(not r['reused'])
            length=r.get('routed_full_scan_path_net_length_upper_bound_um')
            seconds=f"{r['route_wall_seconds']:.2f}" if 'route_wall_seconds' in r else '—'
            text.append(f"| {design} | {r['role']} | {r['reused']} | {r['status']} | {r.get('DRC_errors','—')} | {length if length is not None else '—'} | {seconds} |")
    if route_deltas:text+=['','Recommendation routed upper-bound changes: '+', '.join(route_deltas)+'.']
    text+=['','## Required engineering answers','',
        '1. **Algorithm:** spatial hierarchy and bounded greedy starts, then exact transactional swap/relocate/reversal/cross-chain segment search with a five-objective Pareto archive and constrained recommendation. No learned model or arbitrary weighted objective sum.',
        '2. **Complexity:** geometry/neighbor preprocessing is approximately O(N log N); sparse construction is O(N log N + N b P), fixed leaf b≤32. A size-s move costs O(s) physical/load changes, O(P L s) shift deltas, and O(P L B) peak reduction. Short-chain initialization is O(P N L); long chains use tiled FFT Toeplitz products. P and L are explicit scaling dimensions.',
        '3. **Data structures:** integer chain/position arrays, Morton order, cKDTree with ≤17 neighbors per FF, per-source functional bounding boxes/load aggregates, binary transition diagonals, one global P×L×100×2 activity field and ≤16 archived chain arrays. No N×N distance or waveform matrix.',
        '4. **Incremental costs:** removed/inserted physical boundaries, affected outgoing SI/SO source loads, changed transition diagonals, and changed spatial weight columns. Exact local maxima are reduced from the updated field. Full architecture evaluation occurs only for starts and restarts. Activity deltas are not falsely described as O(1).',
        '5. **Throughput:** measured local evaluations/second are in the tables. A local evaluation computes all four M3/M5 total/local endpoints. Constructor/baseline evaluations are counted separately by subtraction in result.json.',
        '6. **Runtime:** each current design ran for the requested 60-second solver budget, with measured overrun reported. Loading, kernel warmup, command wall time after imports and process RSS are recorded per run. These are single observed engineering runs, not statistical performance estimates.',
        '7. **More runtime:** the anytime table records measured constrained-incumbent evolution. Plateau periods remain visible; improvement is not guaranteed on every interval.',
        '8. **Physical-only comparison:** recommendations provide activity improvements with bounded extra analytical scan wire, not universal Pareto dominance over P. Physical extremes reduce wire but may worsen hotspots. Existing A/J50 alternatives remain reported, not replaced by random baselines.',
        '9. **Activity versus wire:** both local ceilings are inherited from the strongest physical start, and the configurable default wire allowance is 10%. The real table reports every signed tradeoff; routed wire must be judged separately.',
        f'10. **Routing:** {route_count} new selected routes are recorded above, with exact-order baseline reuse and structural/DRC outcomes. No exhaustive routing or historical correlation study was rerun.',
        '11. **Bottleneck:** the measured s5378 profile shifted the main cost to exact spatial reduction and diagonal/column updates. Archive vectorization reduced admission overhead. Initial scaling exposed repeated full-field restarts (25.5/60 s at 10K) and checkpoint starvation (only 158 local evaluations at 100K). The final solver caps restart spending near 10%, uses compact indexed checkpoints/Pareto outputs, and schedules writes after completion. Initial and final runs are retained separately. Long-chain fields and peak reduction remain costs; result.json records every stage including checkpoint time.',
        '12. **100K FF:** the scaling table records what actually ran, including K, P and L. This is an algorithm workload, not a real 100K ATPG design. Large P×L can still exceed the explicit 1 GiB field guard; exact arbitrary-pattern industrial scale needs a tiled retained field. The qualified topology adapter remains K=2; generic inputs support arbitrary K with explicit direct-SO topology. Single clock domain and fixed capacities are current constraints.',
        '13. **Next improvement:** screen physically infeasible moves using cheap edge deltas before exact activity work, then add a tiled/block-maximum activity field so cost and memory depend on touched time/window blocks. Benchmark this against the current measured reduction bottleneck before introducing parallel workers.',
        '', '## Correctness and use','',
        'The final milestone full regression passed **238 tests in 126.21 s**. The subsequent focused run passed **10 tests in 8.93 s**, adding the slow-checkpoint regression to randomized exact deltas/rollback, independent cycle replay, inherited endpoint transfer, FFT equivalence, archive bounds, input validation and deadline fallback. Exported real recommendations/physical extremes are also checked independently against the qualified load/scoring implementations; per-run independent_check.json records those outcomes.',
        '', 'Usage and input schema: [working_optimizer.md](docs/working_optimizer.md). Initial repository reconstruction: [current_solution.md](current_solution.md). Historical evidence is preserved. See [repository update](docs/repository_update.md) for the implementation and experiment files included in the development branch.']
    (ROOT/'solution_status.md').write_text('\n'.join(text)+'\n',encoding='utf-8')


if __name__=='__main__':main()
