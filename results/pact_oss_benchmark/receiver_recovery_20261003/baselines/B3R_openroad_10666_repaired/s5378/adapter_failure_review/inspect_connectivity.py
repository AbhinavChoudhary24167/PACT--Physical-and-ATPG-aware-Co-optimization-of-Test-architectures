"""Read the failed generated ODB without modifying it or executing DFT."""
import hashlib
import json
from pathlib import Path

import odb

ROOT=Path(__file__).resolve().parents[7]
RAW=Path('/mnt/d/PACT_EXPERIMENTS/tmp/pact_oss_20261003/receiver_recovery_20261003/B3R_openroad_10666_repaired/s5378')


def binding(path):
    return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())


database=odb.dbDatabase.create()
odb.read_db(database,str(RAW/'generated.odb'))
block=database.getChip().getBlock()
ff={inst.getName():inst for inst in block.getInsts() if inst.getMaster().getName()=='SDFF_X1'}
ports={name:dict(net=block.findBTerm(name).getNet().getName(),
    geometry=sorted((box.getTechLayer().getName(),box.xMin(),box.yMin(),box.xMax(),box.yMax())
        for pin in block.findBTerm(name).getBPins() for box in pin.getBoxes()))
    for name in ('test_si_0','test_so_0','test_si_1','test_so_1')}
chains=[]
for ci in range(2):
    net=block.findBTerm(f'test_si_{ci}').getNet()
    observed=[]
    visited=set()
    buffers_seen=[]
    while net.getName() not in visited:
        visited.add(net.getName())
        matches=[name for name,inst in ff.items() if inst.findITerm('SI').getNet()==net]
        if len(matches)>1:
            stop='BRANCHED_SI'
            break
        if matches:
            name=matches[0]
            observed.append(name)
            net=ff[name].findITerm('Q').getNet()
            continue
        if net==block.findBTerm(f'test_so_{ci}').getNet():
            stop='REACHED_FIXED_OUTPUT'
            break
        buffers=[term.getInst() for term in net.getITerms()
            if term.getMTerm().getName()=='A' and term.getInst().getMaster().getName().startswith('BUF_')]
        if len(buffers)!=1:
            stop='NO_UNIQUE_BUFFER_TO_FIXED_OUTPUT'
            break
        buffers_seen.append(buffers[0].getName())
        net=buffers[0].findITerm('Z').getNet()
    else:
        stop='NET_LOOP'
    chains.append(dict(input_port=f'test_si_{ci}',expected_output_port=f'test_so_{ci}',
        observed_FF_count=len(observed),order=observed,transparent_buffers=buffers_seen,
        terminal_net=net.getName(),stop=stop,
        terminal_ITerms=sorted((t.getInst().getName(),t.getMTerm().getName()) for t in net.getITerms()),
        fixed_output_positions={name:[index+1 for index,cell in enumerate(observed)
            if ff[cell].findITerm('Q').getNet()==block.findBTerm(name).getNet()]
            for name in ('test_so_0','test_so_1')}))
result=dict(status='OBSERVED_CONNECTIVITY_FAILURE',operation='Read-only ODB connectivity traversal; no DFT or optimization commands',
    generated_ODB=binding(RAW/'generated.odb'),generated_verilog=binding(RAW/'generated.v'),
    reader_binary=binding(Path('/proc/self/exe').resolve()),script=binding(Path(__file__).resolve()),
    FF_count=len(ff),ports=ports,chains=chains,
    internal_paths_disjoint=not set(chains[0]['order'])&set(chains[1]['order']),
    full_inventory_in_internal_paths=set(chains[0]['order'])|set(chains[1]['order'])==set(ff))
target=Path(__file__).with_name('connectivity.json')
if target.exists():
    raise ValueError('Read-only diagnosis receipt already exists')
target.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps(dict(FF_count=len(ff),ports=ports,chains=[{key:value for key,value in item.items() if key not in ('order','terminal_ITerms')} for item in chains]),indent=2))
