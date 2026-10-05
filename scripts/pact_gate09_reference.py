#!/usr/bin/env python3
"""Reuse frozen source preparation and B0/B1/B2/B3T in a new namespace.

Only admitted source paths and receipt destinations change. The library,
commands, algorithms, timing/DRC/FAN gates, and reference ranking are reused.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import pact_gate09_admission as admission
from pact_gate09_source_probe import require_capacity, META as BASE_META, RAW as BASE_RAW
from pact_experiment_receipts import atomic_write


META, RAW = BASE_META, BASE_RAW


def repair_namespace(attempt, dependency_repair):
    if bool(attempt) != bool(dependency_repair):
        raise ValueError('A repair receipt and a separate attempt namespace are both required')
    if attempt and (not attempt.replace('_', '').isalnum() or len(attempt) > 64):
        raise ValueError('Unsafe repair attempt namespace')
    return ((BASE_META / 'repair_attempts' / attempt, BASE_RAW / 'repair_attempts' / attempt)
            if attempt else (BASE_META, BASE_RAW))


def qualified_dependency(path):
    if path is None:
        return None
    repair = admission.read(path)
    if (repair['dependency'] != 'FAN_ATPG' or repair['status'] != 'QUALIFIED_GENERIC_INFRASTRUCTURE_REPAIR'
            or repair['PACT_source_changes'] != 0 or repair['scientific_parameters_changed']
            or repair['benchmark_specific_optimization']):
        raise ValueError('Only a qualified generic FAN infrastructure repair can change the backend')
    if {record['label'] for record in repair['focused_tests']} != {'compound_circuit', 'reporter_control'}:
        raise ValueError('Both circuit and reporter regressions are required')
    for value in [repair['binary'], repair['library'], repair['original_frozen_FAN'], *repair['files'].values()]:
        if admission.verify(value)['status'] != 'PASS':
            raise ValueError('Dependency repair binding changed')
    for record in repair['focused_tests']:
        if record['exit_code'] or any(admission.verify(record[key])['status'] != 'PASS' for key in ('stdout', 'stderr')):
            raise ValueError('Dependency repair focused regression is not qualified')
    return repair


def configure(source_receipt, attempt=None, dependency_repair=None):
    global META, RAW
    META, RAW = repair_namespace(attempt, dependency_repair)
    repair = qualified_dependency(dependency_repair)
    source = admission.read(source_receipt)
    design = source['design']
    if source['status'] != 'SOURCE_MAPPED_EQUIVALENCE_QUALIFIED_PENDING_PHYSICAL_ATPG_REFERENCE':
        raise ValueError('Source and mapped next-state equivalence required')
    for key in ('mapped_netlist', 'mapped_json', 'Liberty', 'Yosys', 'protocol'):
        if admission.verify(source[key])['status'] != 'PASS':
            raise ValueError('Admitted source binding changed: ' + key)
    for value in source['stages'].values():
        if admission.verify(value)['status'] != 'PASS':
            raise ValueError('Source qualification stage binding changed')
        completed = admission.read(value['path'])
        if completed['exit_code'] or completed['timed_out']:
            raise ValueError('Source qualification stage incomplete')
    protocol = admission.read(admission.INTAKE)
    for value in [*protocol['frozen_sources'].values(), *protocol['frozen_tools'].values()]:
        if admission.verify(value)['status'] != 'PASS':
            raise ValueError('Frozen implementation/tool changed')
    require_capacity(protocol)
    os.environ.update(PACT_DEPENDENCY_ROOT='/root/pact-deps', PACT_EXPERIMENT_ROOT='/mnt/d/PACT_EXPERIMENTS',
                      OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', NUMBA_NUM_THREADS='1', PATH='/usr/bin:' + os.environ['PATH'])
    import pact_generalization_infrastructure as infrastructure
    import pact_generalization_physical as physical
    infrastructure.OUT, infrastructure.RUN = META, RAW
    physical.OUT, physical.RUN = META, RAW
    physical.NAMESPACE = RAW / 'namespace'
    if repair:
        infrastructure.REPAIRED = physical.REPAIRED = Path(repair['binary']['path'])
    original_execute = infrastructure.execute
    original_read = infrastructure.read
    original_simulate = physical.simulate

    def context_read(path):
        if Path(path) == META / 'manifests/campaign_preregistration.json':
            return original_read(META / f'manifests/{design}_reference_preparation.json')
        return original_read(path)

    def guarded_execute(command, folder, *args, **kwargs):
        gate = require_capacity(protocol)
        atomic_write(Path(folder) / 'gate09_capacity.json', gate, immutable=True)
        return original_execute(command, folder, *args, **kwargs)

    def guarded_simulate(*args, **kwargs):
        require_capacity(protocol)
        return original_simulate(*args, **kwargs)

    infrastructure.execute = physical.execute = guarded_execute
    infrastructure.read = context_read
    physical.simulate = guarded_simulate
    return design, source, protocol, infrastructure, physical, repair


def register_source(design, source, protocol, dependency_repair=None):
    path = META / f'manifests/{design}_reference_preparation.json'
    entry = next(row for row in protocol['cohort'] if row['design'] == design)
    row = dict(entry, FF_count=source['topology']['FF_count'], source_file=source['mapped_netlist'],
               source_admission=admission.binding(Path(source['mapped_netlist']['path']).parents[0] / 'adapter.json'),
               eligible=False, reference=None, ATPG_pattern_count=None)
    if path.exists():
        existing = admission.read(path)
        if next(r for r in existing['designs'] if r['design'] == design)['source_file'] != row['source_file']:
            raise ValueError('Registered reference source cannot change')
        return
    atomic_write(path, dict(schema='pact_gate09_reference_preparation_v1',
        created_utc=datetime.now(timezone.utc).isoformat(), gate='GATE09',
        original_protocol=admission.binding(admission.INTAKE),
        fixed_method=protocol['fixed_method'], design_order=protocol['cohort_order'], designs=[row],
        other_designs='Remain in immutable prospective cohort; no outcome-dependent substitution',
        physical_parameters=dict(clock_period_ns=10.0, CORE_UTILIZATION=35, PLACE_DENSITY_LB_ADDON=0.20,
                                 TNS_END_PERCENT=100, physical_seed=11, route_threads=2),
        reference_rule=protocol['fixed_method']['reference_rule'],
        dependency_repair=admission.binding(dependency_repair) if dependency_repair else None,
        original_failed_preparation=admission.binding(BASE_META / f'physical/{design}/preparation.json')
            if dependency_repair else None,
        harness=admission.binding(Path(__file__)), scientific_method_changes=0), immutable=True)


def run(action, source_receipt, attempt=None, dependency_repair=None):
    began = time.perf_counter()
    design, source, protocol, infrastructure, physical, repair = configure(source_receipt, attempt, dependency_repair)
    result_path = META / 'workers' / design / (action + '.json')
    if result_path.exists():
        raise ValueError('Preserve prior stage outcome')
    record = dict(schema='pact_gate09_reference_worker_v1', action=action, design=design,
                  created_utc=datetime.now(timezone.utc).isoformat(), PID=os.getpid(),
                  source_admission=admission.binding(source_receipt), harness=admission.binding(Path(__file__)),
                  capacity=require_capacity(protocol), scientific_method_changes=0,
                  repair_attempt=attempt,
                  dependency_repair=admission.binding(dependency_repair) if dependency_repair else None,
                  common_FAN_backend=repair['binary'] if repair else admission.binding(infrastructure.REPAIRED),
                  qualified_repair_source_SHA=repair['combined_SHA'] if repair else None,
                  PACT_search_started=False, source_and_destination_adaptation_only=True)
    state_path = result_path.with_name(action + '.lifecycle.json')
    if state_path.exists():
        raise ValueError('Preserve started/interrupted stage; no implicit replay')
    atomic_write(state_path, dict(record, state='REGISTERED'), immutable=True)
    atomic_write(result_path.parent / (action + '.registered.json'), dict(record, state='REGISTERED'), immutable=True)
    try:
        register_source(design, source, protocol, dependency_repair)
        active = dict(record, state='STARTED', Linux_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
        atomic_write(result_path.parent / (action + '.started.json'), active, immutable=True)
        atomic_write(state_path, active)
        if action == 'prepare':
            result = infrastructure.prepare(design)
            record.update(status=result['status'], receipt=admission.binding(META / f'physical/{design}/preparation.json'))
        else:
            mount = '/mnt/pact-oss-recovery'
            if subprocess.run(['mountpoint', '-q', mount]).returncode:
                Path(mount).mkdir(parents=True, exist_ok=True)
                subprocess.run(['mount', '-o', 'loop,ro',
                    '/mnt/d/PACT_EXPERIMENTS/tmp/pact_oss_20261003/recovery_20261003/build-storage.ext4', mount], check=True)
            record['reference_mount'] = admission.command(['findmnt', '-J', mount])
            record['B2_binary'] = admission.binding(physical.METHODS['B2'][1])
            record['B3T_binary'] = admission.binding(physical.METHODS['B3T'][1])
            for required in (physical.ANNOTATED, *(item[1] for item in physical.METHODS.values())):
                if not required.is_file():
                    raise FileNotFoundError('Qualified baseline input unavailable: ' + str(required))
            physical.references(design)
            outcome = META / f'physical/{design}/presearch_qualification.json'
            record.update(status=admission.read(outcome)['status'], receipt=admission.binding(outcome),
                          records=admission.binding(META / f'baselines/{design}_references.json'))
    except Exception as error:
        record.update(status='PACT_GATE09_REFERENCE_ADMISSION_BLOCKED', error=str(error), traceback=traceback.format_exc())
    usage = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    record.update(completed_utc=datetime.now(timezone.utc).isoformat(), wall_seconds=time.perf_counter() - began,
                  CPU_seconds=usage.ru_utime + usage.ru_stime,
                  children_CPU_seconds=children.ru_utime + children.ru_stime,
                  peak_RSS_KiB=usage.ru_maxrss, child_peak_RSS_KiB=children.ru_maxrss)
    atomic_write(result_path, record, immutable=True)
    atomic_write(state_path, dict(record, state='COMPLETED' if record['status'] in
        ('PLACEMENT_READY_PENDING_REFERENCES', 'INFRASTRUCTURE_QUALIFIED') else 'FAILED', completion_receipt=admission.binding(result_path)))
    print(json.dumps(record, indent=2), flush=True)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'references'))
    parser.add_argument('--source-admission', type=Path, required=True)
    parser.add_argument('--attempt', help='Separate namespace for a qualified infrastructure repair')
    parser.add_argument('--dependency-repair', type=Path)
    args = parser.parse_args()
    result = run(args.action, args.source_admission, args.attempt, args.dependency_repair)
    raise SystemExit(0 if result['status'] in ('PLACEMENT_READY_PENDING_REFERENCES', 'INFRASTRUCTURE_QUALIFIED') else 2)
