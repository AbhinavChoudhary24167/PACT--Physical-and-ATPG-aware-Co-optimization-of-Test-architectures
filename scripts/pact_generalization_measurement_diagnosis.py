"""Localize a timed-out physical measurement without deriving partial metrics."""
import argparse
import re
from pact_generalization import OUT,read,write,binding
from pact_generalization_infrastructure import RUN,external_binding

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--design',required=True)
a=p.parse_args()
root=RUN/'reference_measurement'/a.design
manifest=read(root/'manifest.json')
folder=root/a.design/manifest['rows'][0]['role']
execution=read(root/'execution/execution.json')
assert execution['timed_out']
stages={name:read(folder/f'{name}.execution.json') for name in ('export','extract','compile','simulate')
    if (folder/f'{name}.execution.json').exists()}
assert all(stages[name]['returncode']==0 for name in ('export','extract','compile'))
assert 'simulate' not in stages,'Timeout is not localized to incomplete simulation'
vcd=folder/'activity.vcd'
code=None
with vcd.open('rb') as stream:
    for line in stream:
        text=line.decode('ascii')
        match=re.match(r'\$var\s+integer\s+\d+\s+(\S+)\s+cycle_id\s+\$end',text)
        if match:
            code=match[1]
        if '$enddefinitions' in text:
            break
    stream.seek(max(0,vcd.stat().st_size-2*1024*1024))
    tail=stream.read().decode('ascii',errors='strict')
cycles=read(folder/'cycles.json')
observed=[int(bits,2) for bits in re.findall(r'^b([01]+) '+re.escape(code)+r'$',tail,re.M)] if code else []
valid=[i for i in observed if i<len(cycles)]
last=max(valid) if valid else None
result=dict(design=a.design,status='RESOURCE_LIMIT',localized_stage='Icarus vvp functional simulation',
    wall_seconds_at_cutoff=execution['wall_seconds'],fixed_timeout_seconds=1800,
    completed_stages=stages,intended_shift_cycles=len(cycles),last_observed_cycle_id=last,
    last_observed_schedule_entry=cycles[last] if last is not None else None,
    progress_is_not_correctness_qualification=True,activity_summary_produced=False,
    partial_VCD=external_binding(vcd),execution=external_binding(root/'execution/execution.json'),
    source_failure=binding(OUT/f'failures/{a.design}_reference_measurement.json'),
    CPU_seconds=None,peak_RSS_KiB=None,
    resource_limitation='Whole-group timeout terminated time(1) before CPU/RSS summary was flushed',
    scientific_conclusion='No E/H4/H8 or FF transition qualification may be derived from the incomplete VCD',
    budget_extended=False,scientific_method_change=False)
write(OUT/f'failures/{a.design}_measurement_localization.json',result,immutable=True)
print('LOCALIZED',a.design,'simulation',last,'/',len(cycles),flush=True)
