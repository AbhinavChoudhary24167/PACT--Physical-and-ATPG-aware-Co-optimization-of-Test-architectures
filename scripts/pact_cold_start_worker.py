"""Enforce the preregistered independent per-design solver resource deadline."""
import argparse
import math
import os
import sys
from pact_cold_start import ROOT,OUT,RUN,read,write,now
from pact_generalization_infrastructure import execute

p=argparse.ArgumentParser();p.add_argument('--design',required=True);a=p.parse_args()
data=read(OUT/f'inputs/{a.design}/cold_start_input.json')
loop_seconds=300*max(1,math.ceil(data['FF_count']/600))
folder=RUN/'searches'/a.design
folder.mkdir(parents=True,exist_ok=True)
record=dict(design=a.design,created_utc=now(),per_loop_seconds=loop_seconds,
    worker_deadline_seconds=max(1800,4*loop_seconds),scope='SOLVER_ONLY; no routing/ATPG/extraction')
try:
    result=execute(['/usr/bin/time','-v','-o',folder/'resources.txt',sys.executable,
        ROOT/'scripts/pact_cold_start.py','search','--design',a.design],folder/'execution',
        timeout=record['worker_deadline_seconds'],env=dict(os.environ))
    record.update(status='PASS',execution=result)
except Exception as error:
    execution=read(folder/'execution/execution.json')
    record.update(status='FAILED',execution=execution,error=str(error),
        failure_class='RESOURCE_LIMIT' if execution['timed_out'] or execution['exit_code'] in (-9,137) else 'TOOL_BUG')
    write(OUT/f'failures/{a.design}_solver_worker.json',record,immutable=True)
write(OUT/f'scalability/{a.design}_solver_execution.json',record,immutable=True)
print('COLD_START_SOLVER_WORKER',a.design,record['status'],flush=True)
