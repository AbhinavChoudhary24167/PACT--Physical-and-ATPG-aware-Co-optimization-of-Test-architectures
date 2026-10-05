"""Read-only OpenROAD probe for the bounded missing-SPEF repair."""
import json
from pathlib import Path
import sys
import odb

folder=Path(sys.argv[-2]); output=Path(sys.argv[-1])
db=odb.dbDatabase.create(); odb.read_db(db,str(folder/'routed.odb'))
block=db.getChip().getBlock()
mapping=json.loads((folder/'net_mapping.json').read_text())
records=[]
for name in ('net654','net655','net714','net719'):
    net=block.findNet(name)
    record=dict(net=name,odb_present=net is not None,mapping=mapping['nets'].get(name))
    if net:
        record.update(iterms=[dict(instance=t.getInst().getName(),master=t.getInst().getMaster().getName(),
            pin=t.getMTerm().getName(),direction=str(t.getIoType()),signal=str(t.getSigType()),
            placement=str(t.getInst().getPlacementStatus()),location=t.getInst().getLocation()) for t in net.getITerms()],
            ports=[dict(name=t.getName(),direction=str(t.getIoType())) for t in net.getBTerms()],
            wire_present=net.getWire() is not None,
            wire_length_DBU=net.getWire().getLength() if net.getWire() else None,
            special_wires=len(net.getSWires()),net_api=[v for v in dir(net) if any(k in v.lower() for k in ('wire','route','connect'))])
    records.append(record)
output.parent.mkdir(parents=True,exist_ok=True)
with output.open('x') as stream:json.dump(dict(block=block.getName(),dbu=block.getDbUnitsPerMicron(),records=records),stream,indent=2)
print(json.dumps(records,indent=2))
