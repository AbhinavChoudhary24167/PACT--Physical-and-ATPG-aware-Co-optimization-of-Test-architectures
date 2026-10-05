#!/usr/bin/env python3
"""Post-merge cold campaign with atomic receipts and one supervised worker."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import traceback

from pact_generalization import ROOT, binding, read, sha
from pact_generalization_infrastructure import external_binding, REPAIRED
from pact_experiment_receipts import atomic_write, now, resources, LaneReceipts

OUT=ROOT/'results/pact_large_unseen_gate9_20261005'
RUN=Path('/mnt/d/PACT_EXPERIMENTS/results/pact_large_unseen_gate9_20261005')
MERGED='084db2f9e164b7757597fec1eec73d9c4049a9a4'
CEILINGS=dict(search=7200, physical=14400, activity=3*7200+3600, aggregate=300)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def configure():
    from pact.experiment_storage import configure_experiment_storage
    configure_experiment_storage('/mnt/d/PACT_EXPERIMENTS')
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', NUMBA_NUM_THREADS='1',
                      PACT_DEPENDENCY_ROOT='/root/pact-deps', PATH='/usr/bin:'+os.environ['PATH'])


def campaign():
    return read(OUT/'campaign_registration.json')


def register():
    from pact_cpu_gates import require_continuation_allowed
    from pact.optimizer.stage_b import Config
    from pact.optimizer.cold_start import ColdStartPACTInput
    require_continuation_allowed()
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    subprocess.run(['git','merge-base','--is-ancestor',MERGED,'HEAD'],cwd=ROOT,check=True)
    if branch!='development/large-unseen-gate9-20261005':
        raise ValueError('Post-merge experiment branch required')
    snapshot=resources()
    # Twenty GiB covers the existing single-workflow scratch requirement.
    # Extra five GiB covers six <=482,381,871-byte traces, observed physical/
    # ATPG/ORFS packages (largest prior aggregate 371 MiB), and two trace sizes
    # of safety. WSL's backing disk and 8-GiB swap already reside on F:.
    budget=dict(C_minimum_free_bytes=6*1024**3, D_minimum_free_bytes=25*1024**3,
                existing_workflow_scratch_bytes=20*1024**3, extra_margin_bytes=5*1024**3,
                measured_largest_trace_bytes=482381871,
                measured_prior_candidate_ORFS_aggregate_bytes=371*1024**2,
                measured_largest_uncompressed_counts_bytes=16838*189658)
    for drive in ('C','D'):
        if snapshot['disks'][drive]['free']<budget[drive+'_minimum_free_bytes']:
            raise RuntimeError('Capacity gate failed for '+drive)
    references={}
    for design in ('s38584','s38417'):
        package=ROOT/f'results/pact_cold_start_unseen_20261004/inputs/{design}/cold_start_input.json'
        contract=ColdStartPACTInput.from_manifest(package)
        receipt=(ROOT/'results/pact_cpu_scalability_20261005/spef_patch/reanalysis/result.json' if design=='s38584'
                 else ROOT/'results/pact_cpu_scalability_20261005/activity/continuation/s38417/REF_B2/normal/result.json')
        result=read(receipt)
        if result['status']!='QUALIFIED' or not result['complete'] or result['architecture_sha256']!=contract.data['reference_architecture_hash']:
            raise ValueError('Qualified frozen reference mismatch')
        references[design]=dict(input=binding(package), architecture_hash=contract.data['reference_architecture_hash'],
                                method=contract.data['reference_method'], exact_activity=binding(receipt))
    configurations=[asdict(Config(epsilon=e,seconds=900,max_evaluations=20000,stagnation_attempts=2000)) for e in (.02,.05,.10)]
    source_paths=sorted(p.relative_to(ROOT).as_posix() for directory in ('src','scripts')
                        for p in (ROOT/directory).rglob('*')
                        if p.is_file() and p.suffix in ('.py','.cpp','.tcl') and '__pycache__' not in p.parts)
    sources={p:binding(ROOT/p) for p in source_paths}
    tools={p:external_binding(p) for p in ('/usr/bin/openroad','/usr/bin/iverilog','/usr/bin/vvp',str(REPAIRED))}
    interrupted=ROOT/'results/pact_cpu_scalability_20261005/continuation'
    preserved={str(p.relative_to(ROOT)):binding(p) for p in interrupted.rglob('*') if p.is_file()}
    oldlog=Path('/mnt/d/PACT_EXPERIMENTS/results/pact_cpu_scalability_20261005/continuation_campaign/workers/s38584/search.log')
    record=dict(schema='pact_large_unseen_postmerge_v1',state='REGISTERED',created_utc=now(),merged_SHA=MERGED,
                branch=branch,implementation_SHA=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                references=references,configurations=configurations,configuration_hash=canonical_hash(configurations),
                sources=sources,tools=tools,experiment_root=str(RUN),storage_budget=budget,resource_snapshot=snapshot,
                design_order=['s38584','s38417'],K=2,seed=11,epsilons=[.02,.05,.10],loop_seconds=900,
                search_worker_ceiling_seconds=7200,heavy_worker_groups=1,scientific_method_changes=0,
                cold_initialization='Frozen external reference only; no interrupted champion, prior archive, or historical PACT architecture',
                candidate_selection='Existing balanced/best_E/best_H4/best_H8 role order, exact hash deduplication, maximum three before routing',
                interrupted_status='INTERRUPTED_NO_COMPLETION_RECEIPT',previous_partial_evidence=preserved,
                previous_partial_log=external_binding(oldlog),reference_simulations_repeated=False)
    atomic_write(OUT/'campaign_registration.json',record,immutable=True)
    print('LARGE_UNSEEN_REGISTERED',record['configuration_hash'],flush=True)


def lanes(design):
    record=campaign()
    return LaneReceipts(OUT/'searches'/design,dict(design=design,
        configuration_hash=record['configuration_hash'],input_hashes=record['references'][design],
        merged_SHA=MERGED,worker_ceiling_seconds=7200))


def search(design):
    import pact_cpu_continue_search as continuation
    import pact_cold_start as cold
    from pact.optimizer.cpu_incremental import State
    from pact.optimizer.cpu_reference import reference
    continuation.OUT,continuation.RUN=OUT,RUN
    continuation.write=atomic_write
    continuation.register(design)
    cold.OUT,cold.RUN=OUT,RUN
    lifecycle=lanes(design)
    original_optimize=cold.solver.optimize
    def observe_optimize(model,starts,label,config,**kwargs):
        lifecycle.transition(config.epsilon,'STARTED')
        return original_optimize(model,starts,label,config,**kwargs)
    def observe_write(path,data,immutable=False):
        atomic_write(path,data,immutable=immutable)
        path=Path(path)
        if path.name=='search_configuration.json':
            if canonical_hash(data['configurations'])!=campaign()['configuration_hash']:
                raise ValueError('Search parameters differ from preregistration')
            for config in data['configurations']:
                lifecycle.transition(config['epsilon'],'REGISTERED',configuration=config,
                                     configuration_receipt=binding(path))
        elif path.parent.name.startswith('budget_'):
            epsilon=float(path.parent.name.removeprefix('budget_'))
            if path.name=='progress.json':
                lifecycle.transition(epsilon,'CHECKPOINTED',last_checkpoint=binding(path),
                                     evaluations=data['evaluations'],mutation_loop_seconds=data['seconds'])
            elif path.name=='search.json':
                lifecycle.transition(epsilon,'COMPLETED',completion_receipt=binding(path),exit_code=0,
                                     completion_reason=data['termination'],evaluations=data['evaluations'])
    cold.solver.optimize=observe_optimize
    cold.write=observe_write
    try:
        cold.search(design,state_type=State,reference_evaluator=reference)
    finally:
        cold.solver.optimize=original_optimize
    selection=OUT/f'selections/{design}/preselected_candidates.json'
    selected=read(selection)
    hashes=[row['architecture_hash'] for row in selected['records']]
    if len(hashes)>3 or len(hashes)!=len(set(hashes)):
        raise ValueError('Registered candidate count/deduplication violated')
    atomic_write(OUT/f'selections/{design}/candidate_freeze.json',dict(
        state='FROZEN_BEFORE_PHYSICAL',created_utc=now(),design=design,selection=binding(selection),
        reference_hash=selected['reference_hash'],optimizer_configuration_hash=campaign()['configuration_hash'],
        records=[dict(architecture_hash=row['architecture_hash'],origin_lane=row['epsilon'],
                      search_metrics=row['metrics'],selection_reason=row['selection_reason'],
                      candidate=row['candidate'],reference_hash=row['parent_reference_hash'],
                      optimizer_configuration_hash=campaign()['configuration_hash']) for row in selected['records']],
        candidate_routes_before_selection=0),immutable=True)


def qualification(action,design):
    import pact_cpu_qualify_continuation as qualifier
    import pact_cpu_activity as activity
    qualifier.OUT,qualifier.RUN=OUT,RUN
    qualifier.ACTIVITY_OUT=OUT/'activity/continuation'
    qualifier.write=atomic_write
    activity.OUT,activity.RUN=OUT,RUN/'compact_activity'
    activity.write=atomic_write
    import pact_cold_start_physical as physical
    physical.write=atomic_write
    freeze=read(OUT/f'selections/{design}/candidate_freeze.json')
    if sha(OUT/f'selections/{design}/preselected_candidates.json')!=freeze['selection']['sha256']:
        raise ValueError('Frozen candidate selection changed')
    getattr(qualifier,action)(design)


def worker(action,design):
    record=campaign()
    for item in record['sources'].values():
        if sha(ROOT/item['path'].removeprefix('repo://'))!=item['sha256']:
            raise ValueError('Registered executed source changed')
    search(design) if action=='search' else qualification(action,design)


def kernel_evidence(pid):
    result=subprocess.run(['dmesg','--ctime'],capture_output=True,text=True,timeout=10)
    rows=[line for line in result.stdout.splitlines() if any(word in line.lower() for word in
          ('out of memory','oom-kill','killed process','segfault'))]
    return dict(dmesg_exit_code=result.returncode,memory_or_crash_events=rows[-40:],
                worker_PID_mentioned=any(str(pid) in line for line in rows))


def supervise(action,design):
    record=campaign()
    folder=RUN/'workers'/design
    folder.mkdir(parents=True,exist_ok=True)
    receipt=OUT/'workers'/design/(action+'.execution.json')
    live=OUT/'workers'/design/(action+'.lifecycle.json')
    if receipt.exists() or live.exists():
        raise ValueError('Preserve earlier worker attempt; use a separate registered namespace')
    started=now();began=time.perf_counter();deadline=began+CEILINGS[action]
    command=[sys.executable,__file__,action,'--design',design,'--worker']
    atomic_write(live,dict(state='REGISTERED',start_utc=None,end_utc=None,exit_code=None,
                          configuration_hash=record['configuration_hash'],input_hashes=record['references'][design],
                          resources=resources(),command=command),immutable=True)
    with (folder/(action+'.log')).open('x') as log:
        process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        timed_out=False;sent=None;next_sample=0
        while True:
            pid,status,usage=os.wait4(process.pid,os.WNOHANG)
            if pid:
                code=os.waitstatus_to_exitcode(status);process.returncode=code;break
            clock=time.perf_counter()
            if clock>=deadline and sent is None:
                timed_out=True;os.killpg(process.pid,signal.SIGTERM);sent=clock
            elif sent is not None and clock-sent>=5:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            if clock>=next_sample:
                atomic_write(live,dict(state='STARTED',PID=process.pid,supervisor_PID=os.getpid(),start_utc=started,
                                      end_utc=None,exit_code=None,configuration_hash=record['configuration_hash'],
                                      input_hashes=record['references'][design],resources=resources(),command=command,
                                      elapsed_seconds=clock-began,worker_ceiling_seconds=CEILINGS[action]))
                next_sample=clock+30
            time.sleep(.1)
    reason='complete' if code==0 and not timed_out else ('worker_ceiling_timeout' if timed_out else 'nonzero_worker_exit')
    evidence=kernel_evidence(process.pid) if code else None
    result=dict(state='COMPLETED' if code==0 and not timed_out else ('INTERRUPTED' if timed_out else 'FAILED'),
                PID=process.pid,supervisor_PID=os.getpid(),start_utc=started,end_utc=now(),exit_code=code,
                timed_out=timed_out,completion_reason=reason,command=command,
                configuration_hash=record['configuration_hash'],input_hashes=record['references'][design],
                wall_seconds=time.perf_counter()-began,CPU_seconds=usage.ru_utime+usage.ru_stime,
                peak_RSS_KiB=usage.ru_maxrss,resources=resources(),kernel_evidence=evidence,
                log=external_binding(folder/(action+'.log')))
    if action=='search' and result['state']=='COMPLETED':
        search_result=read(OUT/'searches'/design/'search_results.json')
        if search_result['status']!='SEARCH_COMPLETE' or len(search_result['lanes'])!=3:
            result.update(state='FAILED',completion_reason='missing_complete_three_lane_receipt')
    if action=='search' and result['state']!='COMPLETED':
        lanes(design).interrupt_active(reason,code,timed_out=timed_out,kernel_evidence=evidence)
    atomic_write(receipt,result,immutable=True)
    atomic_write(live,result)
    print('LARGE_UNSEEN_STAGE',design,action,result['state'],round(result['wall_seconds'],3),flush=True)
    if result['state']!='COMPLETED':raise SystemExit(1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('register',*CEILINGS))
    parser.add_argument('--design',choices=('s38584','s38417'))
    parser.add_argument('--worker',action='store_true')
    args=parser.parse_args()
    configure()
    if args.action=='register':register()
    elif not args.design:parser.error('--design required')
    elif args.worker:worker(args.action,args.design)
    else:supervise(args.action,args.design)


if __name__=='__main__':main()
