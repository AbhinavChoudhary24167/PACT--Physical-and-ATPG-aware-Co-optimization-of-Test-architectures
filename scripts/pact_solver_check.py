#!/usr/bin/env python3
"""Verify exported solutions against independent shift replay and qualified costs."""
import argparse
from pathlib import Path
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pact.optimizer.io import load_design,read,write_json
from pact.scan.model import ScanArchitecture
from pact.analysis.phase2cr_loads import construct_weights
from pact.analysis.phase2b_loads import pin_loads
from pact.analysis.phase2b_scoring import score_packed
from pact.physical.phase0c_scan_geometry import phase0c_scan_geometry


def check(design,folder):
    start=time.perf_counter()
    _,costs,patterns,_,_=load_design(ROOT,design,2)
    result=read(folder/'result.json')
    graph=read(ROOT/f'results/phase2c_repair/{design}.placed_graph.json')
    loads=pin_loads(Path('/root/pact-deps/OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib').read_text())
    rows=[result['selected'],min(result['archive'],key=lambda r:r['metrics']['scan_hpwl_um'])]
    checked=[]
    for row in rows:
        arch=ScanArchitecture.from_json(Path(row['architecture']))
        assert arch.sha256()==row['architecture_sha256']
        names=sorted(costs.names);index={n:i for i,n in enumerate(names)}
        ordered_patterns=patterns[:,[costs.index[n] for n in names]]
        chains=[np.array([index[n] for n in c.cells]) for c in arch.chains]
        longest=max(map(len,chains));state=np.zeros(len(names),np.uint8);packed=[]
        for target in ordered_patterns:
            chunk=np.empty((longest,len(names)),np.uint8)
            for t in range(longest):
                before=state.copy()
                for order in chains:
                    state[order[0]]=0 if t<longest-len(order) else target[order[longest-1-t]]
                    state[order[1:]]=before[order[:-1]]
                chunk[t]=before^state
            np.testing.assert_array_equal(state,target)
            packed.append(np.packbits(chunk,axis=1))
        weights=construct_weights(arch,graph,loads)
        packed=np.concatenate(packed);bins=costs.bins[[costs.index[n] for n in names]]
        expected=dict(scan_hpwl_um=phase0c_scan_geometry(arch,ROOT/f'artifacts/raw/phase0b/placements/{design}/s11/placed.def')['total_scan_hpwl_um'])
        for name in ('M3_load','M5_hpwl'):
            scored,_=score_packed(packed,len(names),weights[name],bins)
            expected[name]=scored['total'];expected[name+'_local']=scored['local_peak']
        for key,value in expected.items():np.testing.assert_allclose(row['metrics'][key],value,rtol=1e-9,atol=1e-6)
        checked.append(dict(architecture_sha256=arch.sha256(),status='PASS',independent_metrics=expected))
    frozen=read(ROOT/'results/phase2c_repair/corrected_metrics.json')['rows']
    for base in result['baselines']:
        old=next((r for r in frozen if r['design']==design and r['label']==base['label']),None)
        if old:
            for key,value in old['predictors'].items():np.testing.assert_allclose(base['metrics'][key],value,rtol=1e-9,atol=1e-6)
    out=dict(status='PASS',selected_outputs=checked,existing_baseline_score_agreement=True,runtime_seconds=time.perf_counter()-start)
    write_json(folder/'independent_check.json',out)
    print(design,'independent output check PASS',round(out['runtime_seconds'],3),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--design',required=True);parser.add_argument('--run',type=Path,required=True)
    args=parser.parse_args();check(args.design,args.run)
