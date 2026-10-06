#!/usr/bin/env python3
"""Supervise the current fixed-order run, then finish its frozen PACT phase.

This is a live campaign process, not a scheduled task or recurring automation.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
import pact_gate09_reference as references
from pact_experiment_receipts import atomic_write


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design', required=True)
    parser.add_argument('--source-admission', type=Path, required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--dependency-repair', type=Path, required=True)
    parser.add_argument('--report-directory', type=Path, required=True)
    args = parser.parse_args()
    meta, raw = references.repair_namespace(args.attempt, args.dependency_repair)
    folder = meta / f'supervision/{args.design}'
    folder.mkdir(parents=True, exist_ok=False)
    path = folder / 'finish.json'
    record = dict(schema='pact_gate09_live_supervision_v1', state='WAITING_CURRENT_BASELINES',
        created_utc=datetime.now(timezone.utc).isoformat(), PID=os.getpid(),
        Linux_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        source=admission.binding(Path(__file__)), design=args.design, CPU_only=True,
        source_admission=admission.binding(args.source_admission),
        execution_order='Existing baseline exact jobs -> frozen PACT search -> preselection -> route/exact -> report',
        methods=['B0', 'B1', 'B2', 'B3T', 'B4', 'B5'])
    atomic_write(path, record, immutable=True)
    while True:
        states = [meta / f'workers/{args.design}/measure_run_{method}.lifecycle.json' for method in record['methods']]
        if all(p.exists() and admission.read(p)['state'] in ('COMPLETED', 'FAILED') for p in states):
            break
        time.sleep(2)
    command = [sys.executable, ROOT / 'scripts/pact_gate09_finish_design.py', *sys.argv[1:]]
    log = folder / 'finish.log'
    with log.open('x') as stream:
        child = subprocess.Popen(list(map(str, command)), stdout=stream, stderr=subprocess.STDOUT)
        record.update(state='RUNNING_FINISH', child_PID=child.pid, command=list(map(str, command)),
            started_finish_utc=datetime.now(timezone.utc).isoformat(), launcher=admission.binding(command[1]))
        atomic_write(path, record)
        code = child.wait()
    record.update(state='COMPLETED' if code == 0 else 'BLOCKED', exit_code=code,
        completed_utc=datetime.now(timezone.utc).isoformat(), log=admission.binding(log))
    atomic_write(path, record)
    print('GATE09_FINISH_SUPERVISOR', args.design, record['state'], flush=True)
    raise SystemExit(code)
