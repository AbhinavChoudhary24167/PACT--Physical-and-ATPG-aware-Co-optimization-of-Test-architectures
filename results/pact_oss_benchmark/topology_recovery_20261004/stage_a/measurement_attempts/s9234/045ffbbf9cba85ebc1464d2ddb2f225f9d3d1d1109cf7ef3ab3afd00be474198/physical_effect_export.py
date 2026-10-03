"""OpenROAD-only exact ODB topology, location and net attribution export."""
import sys
from pathlib import Path
from physical_effect import *
import odb
from pact.physical.phase0d_routed import verify_routed
from pact.analysis.phase2b_loads import pin_loads

folder=Path(sys.argv[-1])
row=next(r for r in read(OUT/'manifest.json')['rows'] if r['design']==folder.parent.name and r['role']==folder.name)
arch=ScanArchitecture.from_json(Path(row['architecture']['path']))
verified=verify_routed(folder/'routed.odb',Path(row['architecture']['path']),Path(row['inputs']['placement']['path']))
write(folder/'topology_verification.json',verified)
db=odb.dbDatabase.create(); odb.read_db(db,str(folder/'routed.odb')); block=db.getChip().getBlock()
unit=block.getDbUnitsPerMicron()
for c in arch.cells:
    xy=block.findInst(c.name).getLocation()
    assert all(abs(v/unit-w)<1e-8 for v,w in zip(xy,(c.x_um,c.y_um))), f'Placement mismatch {c.name}'
# Compare functional signal origins through implementation buffers/inverters.
# Scan SI and the scan-output endpoint are the only intentionally changed pins.
source_db=odb.dbDatabase.create(); odb.read_db(source_db,row['source_placed_database']['path'])
source_block=source_db.getChip().getBlock()
def origin(net, seen=None):
    seen=set() if seen is None else seen
    if net is None: return None
    if net.getName() in seen: raise ValueError('Combinational transparent loop')
    seen=seen|{net.getName()}
    ports=[t.getName() for t in net.getBTerms() if str(t.getIoType())=='INPUT']
    drivers=[t for t in net.getITerms() if str(t.getIoType())=='OUTPUT']
    if ports: return ('PORT',tuple(sorted(ports)),0)
    if len(drivers)!=1: return ('UNDRIVEN',net.getName(),0)
    d=drivers[0]; i=d.getInst(); master=i.getMaster().getName()
    if master.startswith(('BUF_X','CLKBUF_X','INV_X')):
        value=origin(i.findITerm('A').getNet(),seen)
        return (*value[:2],value[2]^int(master.startswith('INV_X')))
    return (i.getName(),d.getMTerm().getName(),0)
checked=0
for inst in source_block.getInsts():
    master=inst.getMaster().getName()
    # Transparent cells may be resized/removed by CTS/hold repair. Their
    # semantic effect is checked at functional sinks and output ports.
    if master.startswith(('BUF_X','CLKBUF_X','INV_X','TAPCELL')): continue
    actual=block.findInst(inst.getName())
    assert actual is not None, f'Missing functional cell {inst.getName()}'
    assert actual.getMaster().getName().split('_X')[0]==master.split('_X')[0]
    for term in inst.getITerms():
        pin=term.getMTerm().getName()
        if str(term.getIoType())!='INPUT' or pin=='SI': continue
        if str(term.getSigType()) in ('POWER','GROUND'): continue
        expected=origin(term.getNet()); observed=origin(actual.findITerm(pin).getNet())
        assert expected==observed, f'Functional connection changed {inst.getName()}/{pin}: {expected} != {observed}'
        checked+=1
for p in source_block.getBTerms():
    if str(p.getIoType())=='OUTPUT' and p.getName()!='test_so':
        assert origin(p.getNet())==origin(block.findBTerm(p.getName()).getNet()),p.getName()
        checked+=1
write(folder/'functional_verification.json',dict(status='PASS',functional_sinks_and_outputs=checked,
    rule='source identity and inversion parity through buffers/inverters; gate function families unchanged',
    FF_placement='exact',source_placed_database=row['source_placed_database']))
loads=pin_loads(LIB.read_text())
transparent={}
for i in block.getInsts():
    if i.getMaster().getName().startswith(('BUF_X','CLKBUF_X','INV_X')):
        inp=i.findITerm('A').getNet(); out=i.findITerm('Z') or i.findITerm('ZN')
        if inp and out and out.getNet(): transparent.setdefault(inp.getName(),[]).append(out.getNet().getName())
def closure(roots):
    result=set(); pending=list(roots)
    while pending:
        n=pending.pop()
        if n not in result: result.add(n); pending.extend(transparent.get(n,[]))
    return result
clock=closure([block.findBTerm('CK').getNet().getName()])
scan=closure([block.findInst(c.name).findITerm(p).getNet().getName() for c in arch.cells
              for p in ('Q','QN') if block.findInst(c.name).findITerm(p).getNet()])
scan |= closure([block.findBTerm(p).getNet().getName() for p in ('test_si','test_si_1')])
nets={}; excluded={}
for net in block.getNets():
    name=net.getName()
    if str(net.getSigType()) in ('POWER','GROUND') or name in clock:
        excluded[name]='clock' if name in clock else 'power_ground'; continue
    drivers=[t for t in net.getITerms() if str(t.getIoType())=='OUTPUT']
    inputs=[t for t in net.getBTerms() if str(t.getIoType())=='INPUT']
    if len(drivers)+len(inputs)!=1:
        excluded[name]='no_unique_driver'; continue
    if drivers:
        driver=drivers[0]; xy=[v/unit for v in driver.getInst().getLocation()]
        source=driver.getInst().getName()+'/'+driver.getMTerm().getName()
    else:
        box=inputs[0].getBBox(); xy=[(box.xMin()+box.xMax())/2/unit,(box.yMin()+box.yMax())/2/unit]
        source='PORT/'+inputs[0].getName()
    pin=sum(loads[t.getInst().getMaster().getName(),t.getMTerm().getName()] for t in net.getITerms() if str(t.getIoType())=='INPUT')
    nets[name]=dict(source=source,xy_um=xy,pin_cap_ff=pin,scan_data=name in scan)
die=block.getDieArea()
write(folder/'net_mapping.json',dict(block=block.getName(),bounds_um=[v/unit for v in (die.xMin(),die.yMin(),die.xMax(),die.yMax())],
    ports=[dict(name=t.getName(),net=t.getNet().getName(),direction=str(t.getIoType())) for t in block.getBTerms() if str(t.getSigType()) not in ('POWER','GROUND')],
    nets=nets,excluded=excluded,placement='all FF origins exactly equal qualified architecture',
    attribution='whole net capacitance at source cell origin; external input at port center; source-localized proxy'))
print('PASS exact topology, FF inventory, qualified FF placement and mapping',len(nets))
