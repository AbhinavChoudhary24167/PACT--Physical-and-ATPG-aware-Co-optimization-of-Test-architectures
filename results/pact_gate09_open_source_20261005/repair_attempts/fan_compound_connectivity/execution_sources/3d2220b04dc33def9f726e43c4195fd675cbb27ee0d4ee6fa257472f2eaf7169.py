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


def reference_capacity(protocol, source):
    """Add a source-sized preparation/route allowance to the immutable floor."""
    measured = sum(source[key]['bytes'] for key in ('mapped_netlist', 'mapped_json'))
    margin = dict(C=64 * 1024**2, D=max(512 * 1024**2, 128 * measured))
    policy = dict(protocol['resource_policy'])
    policy['C_minimum_free_bytes'] += margin['C']
    policy['D_minimum_floor_bytes'] += margin['D']
    result = require_capacity(dict(protocol, resource_policy=policy))
    result['per_design_margin'] = dict(stage='ATPG_AND_PHYSICAL_REFERENCE_PREPARATION',
        measured_source_bytes=measured, additional_bytes=margin,
        rule='C +64 MiB; D +max(512 MiB,128*(mapped netlist bytes + mapped JSON bytes))',
        exact_activity_margin='Must be recalculated from the actual pattern/cycle/net dimensions before activity jobs')
    return result


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
    required_tests = {'compound_circuit', 'reporter_control'}
    if repair.get('reporting_only_relative_to_predecessor'):
        required_tests |= {'compound_reporter', 'b14_failed_probe'}
    if repair.get('circuit_connectivity_repair'):
        required_tests |= {'compound_reporter', 'b14_failed_probe', 'shared_net_arity', 'shared_net_truth'}
    if not required_tests <= {record['label'] for record in repair['focused_tests']}:
        raise ValueError('Both circuit and reporter regressions are required')
    for value in [repair['binary'], repair['library'], repair['original_frozen_FAN'], *repair['files'].values()]:
        if admission.verify(value)['status'] != 'PASS':
            raise ValueError('Dependency repair binding changed')
    for record in repair['focused_tests']:
        if record['exit_code'] or any(admission.verify(record[key])['status'] != 'PASS' for key in ('stdout', 'stderr')):
            raise ValueError('Dependency repair focused regression is not qualified')
    return repair


def reuse_preparation(path, source, repair):
    """Reuse completed ATPG/placement only across a qualified reporting-only fix."""
    if not repair or not all(repair.get(flag) is True for flag in
            ('reporting_only_relative_to_predecessor', 'preparation_reuse_permitted')):
        raise ValueError('Preparation reuse requires a qualified reporting-only repair')
    if repair.get('ATPG_generation_algorithm_changed') is not False or repair.get('fault_universe_changed') is not False:
        raise ValueError('ATPG generation and fault universe must be unchanged for reuse')
    predecessor_binding = repair['predecessor']
    if admission.verify(predecessor_binding)['status'] != 'PASS':
        raise ValueError('Preparation predecessor binding changed')
    predecessor = qualified_dependency(Path(predecessor_binding['path']))
    old = admission.read(path)
    if (old['design'] != source['design'] or old['source'] != source['mapped_netlist'] or
            old['status'] != 'PLACEMENT_READY_PENDING_REFERENCES' or
            set(old['gates'].values()) != {'PASS'}):
        raise ValueError('Only the same admitted successfully prepared design can be reused')
    if old['ATPG_execution']['command'][0] != predecessor['binary']['path']:
        raise ValueError('Prepared ATPG backend is not the qualified repair predecessor')
    for key in ('source', 'patterns', 'placed_def', 'placed_netlist', 'config', 'SDC', 'source_placed_database'):
        if admission.verify(old[key])['status'] != 'PASS':
            raise ValueError('Prepared artifact changed: ' + key)
    for key in ('ATPG_execution', 'placement_execution', 'seed_execution'):
        execution = old[key]
        if execution['exit_code'] or execution['timed_out'] or any(
                admission.verify(execution[stream])['status'] != 'PASS' for stream in ('stdout', 'stderr')):
            raise ValueError('Prepared execution evidence is not qualified: ' + key)
    return dict(old, reuse=dict(classification='QUALIFIED_REPORTING_ONLY_INFRASTRUCTURE_REPAIR',
        preparation=admission.binding(path), predecessor=predecessor_binding,
        compatible_netlist=admission.binding(Path(old['patterns']['path']).parent / 'compatible.v'),
        source_scan_order=admission.binding(Path(old['patterns']['path']).parent / 'source_scan_order.json'),
        additional_ATPG_generations=0, additional_placement_executions=0,
        scientific_method_changes=0, workload_unchanged=True, placement_unchanged=True))


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
    reference_capacity(protocol, source)
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
        gate = reference_capacity(protocol, source)
        atomic_write(Path(folder) / 'gate09_capacity.json', gate, immutable=True)
        return original_execute(command, folder, *args, **kwargs)

    def guarded_simulate(*args, **kwargs):
        reference_capacity(protocol, source)
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


def run(action, source_receipt, attempt=None, dependency_repair=None, preparation_from=None):
    began = time.perf_counter()
    design, source, protocol, infrastructure, physical, repair = configure(source_receipt, attempt, dependency_repair)
    result_path = META / 'workers' / design / (action + '.json')
    if result_path.exists():
        raise ValueError('Preserve prior stage outcome')
    record = dict(schema='pact_gate09_reference_worker_v1', action=action, design=design,
                  created_utc=datetime.now(timezone.utc).isoformat(), PID=os.getpid(),
                  source_admission=admission.binding(source_receipt), harness=admission.binding(Path(__file__)),
                  capacity=reference_capacity(protocol, source), scientific_method_changes=0,
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
            if preparation_from:
                retained = reuse_preparation(preparation_from, source, repair)
                atomic_write(META / f'physical/{design}/preparation.json', retained, immutable=True)
                record['retained_preparation'] = admission.binding(preparation_from)
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
    parser.add_argument('--preparation-from', type=Path, help='Reuse bound ATPG/placement across reporting-only repairs')
    args = parser.parse_args()
    if args.preparation_from and args.action != 'references':
        parser.error('--preparation-from applies only to reference qualification')
    result = run(args.action, args.source_admission, args.attempt, args.dependency_repair, args.preparation_from)
    raise SystemExit(0 if result['status'] in ('PLACEMENT_READY_PENDING_REFERENCES', 'INFRASTRUCTURE_QUALIFIED') else 2)
