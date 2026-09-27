"""Phase-2D paths, immutable identity, and bounded command recording."""
from phase2d_preflight import ROOT, OUT, sha, read, write
from datetime import datetime, timezone
from pathlib import Path
import os
import subprocess
import sys
import time

sys.path.insert(0, str(ROOT / 'src'))
PRIOR = ROOT / 'results/phase2c_repair_multiseed'
REPAIRED = ROOT / 'results/phase2c_repair'
FLOW = Path('/root/pact-deps/OpenROAD-flow-scripts/flow')
PLATFORM = FLOW / 'platforms/nangate45'
DESIGNS = ('s5378', 's9234', 's15850')
BLOCKS = dict(s5378='s5378', s9234='s9234f', s15850='s15850')
SEED = 29
ENDPOINTS = [('M3_load','cap_total'), ('M3_load_local','cap_local_peak'),
             ('M5_hpwl','wire_total'), ('M5_hpwl_local','wire_local_peak')]
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1',
           PYTHONPATH=str(ROOT/'src')+':/mnt/d/PACT_EXPERIMENTS/cache/phase2a_python')

def now():
    return datetime.now(timezone.utc).isoformat()

def run(stage, cmd, timeout=600, cwd=ROOT, env=None):
    folder=OUT/'execution'/stage
    folder.mkdir(parents=True, exist_ok=False)
    start=time.perf_counter()
    record=dict(utc=now(),command=list(map(str,cmd)),cwd=str(cwd),timeout_s=timeout,
                environment={k:v for k,v in (env or ENV).items() if k in
                ('PYTHONPATH','PYTHONDONTWRITEBYTECODE','OPENBLAS_NUM_THREADS','PATH','TMPDIR')})
    write(folder/'launch.json',record)
    with (folder/'stdout.log').open('w') as stdout, (folder/'stderr.log').open('w') as stderr:
        try:
            p=subprocess.run(record['command'],cwd=cwd,env=env or ENV,stdout=stdout,stderr=stderr,timeout=timeout)
            record.update(exit_code=p.returncode,timed_out=False)
        except subprocess.TimeoutExpired:
            record.update(exit_code=None,timed_out=True)
    record.update(runtime_seconds=time.perf_counter()-start,
                  logs={str(p):sha(p) for p in (folder/'stdout.log',folder/'stderr.log')})
    write(folder/'result.json',record)
    print(stage,record['exit_code'],round(record['runtime_seconds'],2),flush=True)
    return record

def verify_contract():
    f=read(OUT/'contract_freeze.json')
    assert sha(OUT/'contract.json')==f['contract_sha256']
    for p,h in read(OUT/'contract.json')['frozen_files'].items():
        assert sha(p)==h, p

def config(design):
    return ROOT / (f'experiments/phase0b/{design}_orfs/config.mk' if design=='s15850'
                   else f'experiments/phase0/{design}_orfs/config.mk')

def source(design):
    return FLOW/'results/nangate45'/BLOCKS[design]/'phase0b_source'

def placement(design):
    return OUT/'orfs/results/nangate45'/BLOCKS[design]/'phase2d_gp29'
