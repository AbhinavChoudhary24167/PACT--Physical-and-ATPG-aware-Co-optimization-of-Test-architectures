"""Read-only inventory diagnosis; never substitutes for a qualification gate."""
import argparse
from collections import Counter
import json
from pathlib import Path
import odb

p=argparse.ArgumentParser()
p.add_argument('--routed',type=Path,required=True)
p.add_argument('--architecture',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
arch=json.loads(a.architecture.read_text())
expected={c['name'] for c in arch['cells']}
db=odb.dbDatabase.create()
odb.read_db(db,str(a.routed))
block=db.getChip().getBlock()
masters=Counter(i.getMaster().getName() for i in block.getInsts() if i.getName() in expected)
missing=sorted(n for n in expected if block.findInst(n) is None)
changed=[dict(instance=n,master=block.findInst(n).getMaster().getName(),
    scan_pins={pin:block.findInst(n).findITerm(pin).getNet().getName() if block.findInst(n).findITerm(pin)
        and block.findInst(n).findITerm(pin).getNet() else None for pin in ('D','CK','SI','SE','Q','QN')})
    for n in sorted(expected) if block.findInst(n) and block.findInst(n).getMaster().getName()!='SDFF_X1']
extra=[dict(instance=i.getName(),master=i.getMaster().getName()) for i in block.getInsts()
    if i.getMaster().getName().startswith(('SDFF','DFF')) and i.getName() not in expected]
report=dict(diagnostic_only=True,expected_FF_count=len(expected),missing=missing,extra=extra,
    expected_instance_master_counts=dict(masters),changed_master_instances=changed)
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='changed_master_instances'}),flush=True)
