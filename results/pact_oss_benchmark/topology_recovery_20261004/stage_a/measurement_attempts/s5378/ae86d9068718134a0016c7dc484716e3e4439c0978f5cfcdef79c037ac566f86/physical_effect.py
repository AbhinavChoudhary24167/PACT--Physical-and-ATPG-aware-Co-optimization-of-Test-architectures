"""Independent routed-waveform analysis; no optimizer activity inputs."""
import csv
import hashlib
import json
import math
from pathlib import Path
import numpy as np

def spatial_bin(xy, bounds, resolution):
    x0,y0,x1,y1=bounds
    if x1<=x0 or y1<=y0 or resolution<1:
        raise ValueError('Invalid spatial bounds')
    if not (x0<=xy[0]<=x1 and y0<=xy[1]<=y1):
        raise ValueError('Point outside die')
    bx=min(resolution-1,int((xy[0]-x0)/(x1-x0)*resolution))
    by=min(resolution-1,int((xy[1]-y0)/(y1-y0)*resolution))
    return by*resolution+bx

def vcd_transitions(path, net_names, cycles):
    """Count 0<->1 events in active cycle windows; reject active X/Z events.

    A timestamp batch uses its final cycle_id, independent of declaration/event
    order. cycle_id=-1 explicitly excludes initialization/capture/setup.
    Scalar DUT signals only, with physical-net aliases mapped explicitly.
    """
    wanted=set(net_names); symbols={}; marker=None; scope=[]; values={}
    counts=np.zeros((cycles,len(net_names)),dtype=np.uint8)
    index={n:i for i,n in enumerate(net_names)}; found=set(); timestamp=0
    pending=[]; cycle=-1; times=[]; header=True; ended=False; unknown=set()
    def flush():
        nonlocal cycle
        for code,value in pending:
            if code==marker:
                if set(value)-set('01'): raise ValueError('Unknown cycle marker')
                unsigned=int(value,2)
                cycle=unsigned-(1<<32) if unsigned>=1<<31 else unsigned
                if cycle>=cycles or cycle < -1: raise ValueError('Cycle outside workload')
        for code,value in pending:
            if code not in symbols: continue
            old=values.get(code)
            if cycle>=0 and old is not None and old!=value:
                if old not in '01' or value not in '01':
                    raise ValueError(f'Unknown active net at {timestamp}: {symbols[code]}')
                for name in symbols[code]:
                    if counts[cycle,index[name]]==255: raise ValueError('Per-cycle transition storage overflow')
                    counts[cycle,index[name]]+=1
            values[code]=value
            if value in ('0','1'): unknown.discard(code)
            else: unknown.add(code)
        if cycle>=0 and unknown:
            raise ValueError('Unknown active measured nets: '+str([symbols[c] for c in sorted(unknown)[:5]]))
        if cycle>=0: times.append((timestamp,cycle))
        pending.clear()
    with Path(path).open() as f:
        for raw in f:
            line=raw.strip()
            if not line: continue
            if header:
                parts=line.split()
                if line.startswith('$scope'): scope.append(parts[2])
                elif line.startswith('$upscope'): scope.pop()
                elif line.startswith('$var'):
                    width=int(parts[2]); code=parts[3]; name=parts[4].lstrip('\\')
                    if scope==['tb'] and name=='cycle_id': marker=code
                    if scope==['tb','dut'] and name in wanted:
                        if width!=1: raise ValueError('Non-scalar measured net')
                        if name in found: raise ValueError('Duplicate DUT net declaration')
                        found.add(name); symbols.setdefault(code,[]).append(name); unknown.add(code)
                elif line.startswith('$enddefinitions'): header=False
                continue
            if line.startswith('#'):
                flush(); new=int(line[1:])
                if new<timestamp: raise ValueError('Nonmonotonic VCD time')
                timestamp=new
            elif line[0].lower() in '01xz': pending.append((line[1:],line[0].lower()))
            elif line[0].lower()=='b':
                value,code=line[1:].split(); pending.append((code,value.lower()))
            elif line.startswith('$'): pass
            else: raise ValueError('Unsupported VCD record: '+line)
        flush(); ended=not header
    if not ended or marker is None or found!=wanted:
        raise ValueError(f'Incomplete VCD mapping: missing {sorted(wanted-found)[:15]}')
    seen={c for _,c in times}
    if seen!=set(range(cycles)): raise ValueError('Missing shift cycles')
    return counts,dict(timestamp_unit='1ps (stimulus timescale)',last_timestamp=timestamp,
                      active_timestamps=len(times),mapped_nets=len(found),unique_vcd_symbols=len(symbols))

def weighted(counts, caps):
    if any(c is None or not math.isfinite(c) or c<0 for c in caps):
        raise ValueError('Missing/invalid capacitance; do not fabricate a weight')
    weights=np.asarray(caps)
    # Bound temporary float conversion for the largest real routed waveform.
    result=np.empty(len(counts))
    for i in range(0,len(counts),1024):
        result[i:i+1024]=counts[i:i+1024] @ weights
    return result

def stats(a):
    return dict(total=float(np.sum(a)),mean=float(np.mean(a)),maximum=float(np.max(a)),
                p95=float(np.percentile(a,95)),p99=float(np.percentile(a,99)))

def analyze(folder):
    from pact.analysis.phase2b_reference import parse_spef
    folder=Path(folder)
    def read(p): return json.loads((folder/p).read_text())
    def write(p,v): (folder/p).write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
    mapping=read('net_mapping.json'); workload=read('workload.json'); schedule=read('cycles.json')
    names=sorted(mapping['nets']); counts,vcd=vcd_transitions(folder/'activity.vcd',names,len(schedule))
    root=folder.parents[1]
    manifest=json.loads((root/'manifest.json').read_text())
    entry=next(r for r in manifest['rows'] if r['design']==folder.parent.name and r['role']==folder.name)
    arch=json.loads(Path(entry['architecture']['path']).read_text())
    identity=json.loads(Path(entry['inputs']['identity_map']['path']).read_text())['records']
    from pact.test.pattern_parser import parse_fan_pat
    fan=parse_fan_pat(Path(entry['inputs']['patterns']['path']))
    lookup={r['atpg_signal']:r['physical_instance'] for r in identity}
    # An independent FF-only checker cross-checks every measured Q transition.
    # Final results above and below still come exclusively from the VCD.
    qcols={v['source'][:-2]:i for i,n in enumerate(names) if (v:=mapping['nets'][n])['source'].endswith('/Q')}
    expected_names={c['name'] for c in arch['cells']}
    if set(qcols)!=expected_names: raise ValueError('Incomplete FF Q measurement map')
    cursor=0; checked=0
    state=dict.fromkeys(expected_names,0)
    for pat,source in zip(workload['patterns'],fan.patterns,strict=True):
        for phase in ('load','unload'):
            if phase=='unload':
                state={lookup[n]:int(b) for n,b in zip(fan.pseudo_primary_inputs,source.ppo,strict=True)}
            for t in range(workload['cycles']):
                nxt={}
                for chain in arch['chains']:
                    cells=chain['cells']
                    nxt[cells[0]]=int(pat['load'][chain['chain_id']][t]) if phase=='load' else 0
                    nxt.update({b:state[a] for a,b in zip(cells,cells[1:])})
                for n,col in qcols.items():
                    if counts[cursor,col] != int(state[n]!=nxt[n]):
                        raise ValueError(f'Independent Q toggle mismatch {cursor}/{n}')
                checked+=len(qcols); state=nxt; cursor+=1
    write('FF_transition_crosscheck.json',dict(status='PASS',FF_cycle_values_checked=checked,
        cycles=cursor,scope='Every physical FF Q against independent simultaneous chain replay; VCD is measurement source'))
    spef=parse_spef((folder/'extracted.spef').read_text())
    caps=[]; caprows=[]
    for n in names:
        info=mapping['nets'][n]
        # Extraction omits unconnected/zero-wire constant nets; only permit
        # missing parasitics if no measured transition occurs, and report it.
        s=spef.get(n)
        if s is None and counts[:,len(caps)].any(): raise ValueError('Switched net missing SPEF: '+n)
        c=None if s is None else s['ground_ff']+info['pin_cap_ff']
        caps.append(0 if c is None else c)
        caprows.append(dict(net=n,source=info['source'],x_um=info['xy_um'][0],y_um=info['xy_um'][1],
            scope_scan_data=info['scan_data'],transitions=int(counts[:,len(caps)-1].sum()),
            ground_ff=None if s is None else s['ground_ff'],incident_coupling_ff=None if s is None else s['coupling_ff'],
            pin_ff=info['pin_cap_ff'],ground_pin_ff=c,
            cap_status='EXTRACTED' if s else 'MISSING_STATIC_NET_EXCLUDED'))
    with (folder/'net_activity_capacitance.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(caprows[0])); w.writeheader(); w.writerows(caprows)
    metrics={}; series={}; spatial={}; caps=np.asarray(caps)
    for scope in ('scan_data','all_data'):
        sel=np.asarray([mapping['nets'][n]['scan_data'] or scope=='all_data' for n in names])
        a=counts[:,sel]; c=caps[sel]; ns=np.asarray(names)[sel]
        total=a.sum(axis=1); cw=weighted(a,c)
        result=dict(nets=len(ns),transitions=stats(total),cap_weighted_ff_transitions=stats(cw),grids={})
        series[scope]=dict(transitions=total,cap_weighted=cw)
        for resolution in (4,8):
            bins=np.asarray([spatial_bin(mapping['nets'][n]['xy_um'],mapping['bounds_um'],resolution) for n in ns])
            local=np.zeros((len(schedule),resolution**2),dtype=np.int32)
            localcap=np.zeros_like(local,dtype=float)
            for b in range(resolution**2):
                local[:,b]=a[:,bins==b].sum(axis=1)
                localcap[:,b]=weighted(a[:,bins==b],c[bins==b])
            peak=local.max(axis=1); peakcap=localcap.max(axis=1)
            ic,ib=np.unravel_index(local.argmax(),local.shape)
            ec,eb=np.unravel_index(localcap.argmax(),localcap.shape)
            result['grids'][str(resolution)]=dict(peak_per_cycle=stats(peak),cap_peak_per_cycle=stats(peakcap),
                max_transition_cycle=int(ic),max_transition_bin=int(ib),max_cap_cycle=int(ec),max_cap_bin=int(eb),
                percentile_population='per-cycle maximum over spatial bins')
            series[scope][f'local_{resolution}']=peak; series[scope][f'cap_local_{resolution}']=peakcap
            spatial[f'{scope}_{resolution}']=dict(transition_cycle=int(ic),transition_map=local[ic].tolist(),
                cap_cycle=int(ec),cap_map=localcap[ec].tolist(),bins_total=local.sum(axis=0).tolist())
        # Phase subsets preserve load versus unload distinctions.
        result['phases']={phase:dict(transitions=stats(total[[r['phase']==phase for r in schedule]]),
            cap_weighted=stats(cw[[r['phase']==phase for r in schedule]])) for phase in ('load','unload')}
        metrics[scope]=result
    write('spatial_bins.json',spatial)
    fields=['cycle','pattern','phase','shift']+[scope+'_'+key for scope,data in series.items() for key in data]
    with (folder/'per_cycle.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for i,row in enumerate(schedule):
            w.writerow(dict(row,**{scope+'_'+key:float(a[i]) for scope,data in series.items() for key,a in data.items()}))
    digest=hashlib.sha256()
    with (folder/'activity.vcd').open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): digest.update(b)
    write('activity_summary.json',dict(mode='A',scopes=metrics,VCD=dict(vcd,sha256=digest.hexdigest(),
          bytes=(folder/'activity.vcd').stat().st_size),patterns=len(workload['patterns']),shift_cycles=len(schedule),
          capacitance='OpenRCX ground + Liberty sink pin fF; coupling retained separately, excluded from primary proxy',
          missing_static_caps=[r['net'] for r in caprows if r['ground_pin_ff'] is None]))
    # Compact per-net/per-cycle exact counts, sufficient for deterministic reanalysis.
    np.savez_compressed(folder/'transitions.npz',counts=counts,names=np.asarray(names))
    print('ANALYZED',folder.parent.name,folder.name,metrics['all_data']['transitions']['total'],flush=True)
