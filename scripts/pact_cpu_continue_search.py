#!/usr/bin/env python3
"""Resume new large-design cold search from the sole frozen external reference."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
import time
from pact_generalization import ROOT,read,write,binding,now
from pact_generalization_infrastructure import external_binding
from pact_cold_start_measure import execute_stage
from pact_cpu_gates import require_continuation_allowed,register_policy

OUT=ROOT/'results/pact_cpu_scalability_20261005/continuation'
RUN=Path('/mnt/d/PACT_EXPERIMENTS/results/pact_cpu_scalability_20261005/continuation_campaign')
OLD=ROOT/'results/pact_cold_start_unseen_20261004'


def register(design):
    require_continuation_allowed();policy=register_policy()
    source=OLD/f'inputs/{design}/cold_start_input.json';package=read(source)
    reference=(ROOT/'results/pact_cpu_scalability_20261005/spef_patch/reanalysis/result.json' if design=='s38584'
        else ROOT/'results/pact_cpu_scalability_20261005/activity/continuation/s38417/REF_B2/normal/result.json')
    measured=read(reference)
    if measured['status']!='QUALIFIED' or not measured['complete'] or measured['architecture_sha256']!=package['reference_architecture_hash']:
        raise ValueError('Frozen external reference exact activity does not qualify')
    registration=OUT/f'manifests/{design}_search.json'
    if registration.exists():return read(registration)
    target=OUT/f'inputs/{design}/cold_start_input.json';target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():raise ValueError('Preserve existing new input package')
    shutil.copy2(source,target)
    import pact_cold_start as cold
    from pact.optimizer.cold_start import ColdStartPACTInput
    ColdStartPACTInput.from_manifest(target)
    seconds=300*max(1,math.ceil(package['FF_count']/600))
    record=dict(design=design,created_utc=now(),original_input=binding(source),new_input=binding(target),
        exact_reference_activity=binding(reference),reference_architecture_hash=package['reference_architecture_hash'],
        reference_method=package['reference_method'],K=2,seed=11,epsilons=[.02,.05,.10],loop_seconds=seconds,
        scientific_method_changes=0,initialization='Only frozen external reference; no previous PACT architecture/archive',
        selection='Unchanged Stage-B role ordering and exact hash deduplication, maximum three before routing',
        CPU_worker_policy=policy,worker_ceiling_seconds=7200,normal_activity_ceiling_seconds=7200,
        diagnostic_activity_ceiling_seconds=14400,
        executed_sources={p:binding(ROOT/p) for p in (*cold.SOURCE_NAMES,'scripts/pact_cpu_continue_search.py')})
    write(registration,record,immutable=True)
    return record


def search(design):
    register(design)
    import pact_cold_start as cold
    from pact.optimizer.cpu_incremental import State
    from pact.optimizer.cpu_reference import reference
    cold.OUT,cold.RUN=OUT,RUN
    cold.search(design,state_type=State,reference_evaluator=reference)


def run(design):
    record=register(design);folder=RUN/'workers'/design
    folder.mkdir(parents=True,exist_ok=True)
    try:
        result=execute_stage([sys.executable,ROOT/'scripts/pact_cpu_continue_search.py','search','--design',design],
            folder,'search',time.perf_counter()+record['worker_ceiling_seconds'])
    finally:
        target=OUT/'workers'/design;target.mkdir(parents=True,exist_ok=True)
        if (folder/'search.execution.json').exists():shutil.copy2(folder/'search.execution.json',target/'search.execution.json')
    print('CPU_COLD_SEARCH_COMPLETE',design,result['wall_seconds'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('run','search'))
    p.add_argument('--design',choices=('s38417','s38584'),required=True);a=p.parse_args()
    os.environ.update(PACT_DEPENDENCY_ROOT='/root/pact-deps',PACT_EXPERIMENT_ROOT='/mnt/d/PACT_EXPERIMENTS',
        OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='1',PATH='/usr/bin:'+os.environ['PATH'])
    globals()[a.action](a.design)
