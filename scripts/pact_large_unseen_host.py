#!/usr/bin/env python3
"""Windows supervision survives Linux worker exit and records WSL restarts."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from pact_experiment_receipts import atomic_write, now, resources, LaneReceipts

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/pact_large_unseen_gate9_20261005'
LINUX_ROOT='/mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT'
PLAN=[('s38584','search'),('s38417','search'),('s38584','physical'),('s38584','activity'),
      ('s38584','aggregate'),('s38417','physical'),('s38417','activity'),('s38417','aggregate')]


def wsl_command(*args):
    return ['wsl','-d','Ubuntu-24.04','--',*args]


def linux_snapshot():
    # Never launch an experiment from this diagnosis command.
    command=wsl_command('sh','-c','cat /proc/sys/kernel/random/boot_id; dmesg --ctime | tail -80')
    result=subprocess.run(command,capture_output=True,text=True,timeout=30,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    rows=result.stdout.splitlines()
    return dict(exit_code=result.returncode,boot_id=rows[0] if rows else None,
                recent_kernel_events=rows[1:],stderr=result.stderr)


def main():
    if os.name!='nt':raise RuntimeError('Host supervisor must run on Windows')
    registration=json.loads((OUT/'campaign_registration.json').read_text())
    host_receipt=OUT/'host_lifecycle.json'
    if host_receipt.exists():raise ValueError('Preserve earlier host attempt')
    record=dict(state='STARTED',PID=os.getpid(),start_utc=now(),end_utc=None,exit_code=None,
                configuration_hash=registration['configuration_hash'],input_hashes=registration['references'],
                host_controller_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                resources=resources(),plan=PLAN,stages=[])
    atomic_write(host_receipt,record,immutable=True)
    for design,action in PLAN:
        observed=resources()
        # The initial registration budgets all six candidates. On later stages
        # retained artifacts consume that budget; keep the 20-GiB scratch floor
        # plus one GiB extra, and the six-GiB Windows reserve.
        if observed['disks']['C']['free']<6*1024**3 or observed['disks']['D']['free']<21*1024**3:
            record.update(state='FAILED',end_utc=now(),completion_reason='capacity_gate',resources=observed)
            atomic_write(host_receipt,record);raise SystemExit(1)
        before=linux_snapshot()
        command=wsl_command('env',f'PYTHONPATH={LINUX_ROOT}/.optimizer-deps:{LINUX_ROOT}/src:{LINUX_ROOT}/scripts',
                            'PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','NUMBA_NUM_THREADS=1',
                            '/root/pact-deps/pact-venv/bin/python',LINUX_ROOT+'/scripts/pact_large_unseen.py',
                            action,'--design',design)
        began=time.perf_counter();started=now()
        log=OUT/'host_logs'/f'{design}_{action}.log'
        log.parent.mkdir(parents=True,exist_ok=True)
        with log.open('x') as stream:
            process=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            record.update(current=dict(design=design,action=action,Windows_WSL_PID=process.pid,
                                       start_utc=started,command=command,Linux_before=before),resources=resources())
            atomic_write(host_receipt,record)
            last=0
            while process.poll() is None:
                clock=time.perf_counter()
                if clock-last>=30:
                    record.update(resources=resources(),last_observation_utc=now(),
                                  elapsed_stage_seconds=clock-began)
                    atomic_write(host_receipt,record)
                    print('HOST_OBSERVATION',design,action,round(clock-began,1),flush=True)
                    last=clock
                time.sleep(1)
        stage_path=OUT/'workers'/design/(action+'.execution.json')
        result=json.loads(stage_path.read_text()) if stage_path.exists() else None
        code=process.returncode
        after=linux_snapshot() if code or result is None else None
        complete=code==0 and result is not None and result['state']=='COMPLETED'
        row=dict(design=design,action=action,Windows_WSL_PID=process.pid,start_utc=started,end_utc=now(),
                 exit_code=code,wall_seconds=time.perf_counter()-began,Linux_receipt=result,
                 Linux_after_failure=after,WSL_restart_observed=bool(after and before['boot_id']!=after['boot_id']),
                 completion_reason='explicit_complete_receipt' if complete else 'worker_failed_or_completion_receipt_missing')
        record['stages'].append(row)
        atomic_write(OUT/'host_stages'/f'{design}_{action}.json',row,immutable=True)
        if not complete:
            if action=='search' and result is None:
                lifecycle=LaneReceipts(OUT/'searches'/design,dict(configuration_hash=registration['configuration_hash'],
                                                               input_hashes=registration['references'][design]))
                lifecycle.interrupt_active('missing_worker_completion_receipt',code,interrupted=True,
                                           Windows_WSL_PID=process.pid,WSL_restart_observed=row['WSL_restart_observed'],
                                           Linux_after_failure=after)
            record.update(state='FAILED',end_utc=now(),exit_code=code,
                          completion_reason=row['completion_reason'],resources=resources())
            atomic_write(host_receipt,record)
            print('HOST_CAMPAIGN_FAILED',design,action,code,flush=True)
            raise SystemExit(1)
        atomic_write(host_receipt,record)
        print('HOST_STAGE_COMPLETE',design,action,round(row['wall_seconds'],3),flush=True)
    record.update(state='COMPLETED',end_utc=now(),exit_code=0,
                  completion_reason='Both registered designs finished search and candidate qualification flow',resources=resources())
    atomic_write(host_receipt,record)
    print('HOST_CAMPAIGN_COMPLETE',flush=True)


if __name__=='__main__':main()
