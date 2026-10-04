"""Read-only diagnosis; this never substitutes for the frozen topology gate."""
import argparse
from collections import deque
import json
from pathlib import Path
import odb


def probe(routed,architecture,output):
    arch=json.loads(architecture.read_text())
    db=odb.dbDatabase.create()
    odb.read_db(db,str(routed))
    block=db.getChip().getBlock()
    graph={}
    for inst in block.getInsts():
        master=inst.getMaster().getName()
        if not master.startswith(('BUF_X','CLKBUF_X','INV_X')):
            continue
        inp=inst.findITerm('A')
        out=inst.findITerm('Z') or inst.findITerm('ZN')
        if inp and out and inp.getNet() and out.getNet():
            graph.setdefault(inp.getNet().getName(),[]).append(dict(net=out.getNet().getName(),
                instance=inst.getName(),master=master,invert=int(master.startswith('INV_X'))))
    rows=[]
    for i,chain in enumerate(arch['chains']):
        port=block.findBTerm('test_si' if i==0 else f'test_si_{i}')
        target=block.findInst(chain['cells'][0]).findITerm('SI').getNet()
        start=port.getNet()
        queue=deque([(start.getName(),0,[])])
        visited=set()
        solutions=[]
        while queue:
            net,parity,path=queue.popleft()
            if (net,parity) in visited:
                continue
            visited.add((net,parity))
            if net==target.getName():
                solutions.append(dict(parity=parity,path=path))
                continue
            for edge in graph.get(net,[]):
                queue.append((edge['net'],parity^edge['invert'],path+[edge]))
        rows.append(dict(chain=i,input_net=start.getName(),target_net=target.getName(),
            target_drivers=[dict(instance=t.getInst().getName(),master=t.getInst().getMaster().getName(),pin=t.getMTerm().getName())
                for t in target.getITerms() if str(t.getIoType())=='OUTPUT'],
            solutions=solutions,visited_net_parity_states=len(visited)))
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(dict(diagnostic_only=True,frozen_gate_unchanged=True,chains=rows),indent=2)+'\n')
    print(json.dumps(rows),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--routed',type=Path,required=True)
    p.add_argument('--architecture',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    probe(a.routed,a.architecture,a.output)
