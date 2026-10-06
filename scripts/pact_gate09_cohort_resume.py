#!/usr/bin/env python3
"""Resume fixed cohort only after the proven metadata-only registration stop."""
import argparse
import inspect
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
import pact_gate09_cohort as original
import pact_gate09_reference as references
from pact_experiment_receipts import atomic_write


def require_same_preparation(meta, source_path, certificate):
    worker = admission.read(meta / 'workers/b15_opt/prepare.json')
    path = meta / 'physical/b15_opt/preparation.json'
    prep = admission.read(path)
    source = admission.read(source_path)
    repair = references.qualified_dependency(certificate)
    if (worker['status'] != 'PLACEMENT_READY_PENDING_REFERENCES' or
            prep['status'] != 'PLACEMENT_READY_PENDING_REFERENCES' or
            worker['source_admission']['sha256'] != admission.digest(source_path) or
            worker['common_FAN_backend'] != repair['binary'] or
            worker['qualified_repair_source_SHA'] != repair['combined_SHA'] or
            prep['source'] != source['mapped_netlist'] or
            admission.verify(worker['receipt'])['status'] != 'PASS'):
        raise ValueError('Prepared workload/source/backend differs; continuation cannot reuse it')
    for key in ('source','patterns','placed_def','placed_netlist','source_placed_database','SDC','config'):
        if admission.verify(prep[key])['status'] != 'PASS':
            raise ValueError('Prepared artifact changed: '+key)
    return admission.binding(path)


def resume(previous_path, certificate, ledger_path):
    if ledger_path.exists():
        raise ValueError('Preserve previous resume; no implicit replay')
    previous = admission.read(previous_path)
    design = previous['admission_hold_design']
    if previous['state'] != 'COHORT_TERMINAL' or design != 'b15_opt':
        raise ValueError('This adapter only resumes the preserved prospective-registration stop')
    capacity_recovery = previous['records'][1]['status'] == 'PACT_GATE09_BLOCKED_CAPACITY'
    failed_meta, failed_raw = references.repair_namespace('primary_'+design, certificate)
    failure_path = failed_meta / f'workers/{design}/prepare.json'
    failure = admission.read(failure_path)
    missing = references.BASE_META / f'physical/{design}/preparation.json'
    if (failure.get('children_CPU_seconds') != 0 or failed_raw.exists() or
            (failure_path.parent / 'prepare.started.json').exists() or
            str(missing) not in failure.get('error','') or missing.exists()):
        raise ValueError('Scientific work may have begun; generic metadata-only continuation not admitted')
    protocol = admission.read(admission.INTAKE)
    source_path = references.BASE_META / f'source_admission/{design}.json'
    source = admission.read(source_path)
    if source['status'] != 'SOURCE_MAPPED_EQUIVALENCE_QUALIFIED_PENDING_PHYSICAL_ATPG_REFERENCE':
        raise ValueError('Preserved source admission required')
    for binding in (source['mapped_netlist'], source['mapped_json'], *source['stages'].values()):
        if admission.verify(binding)['status'] != 'PASS':
            raise ValueError('Preserved source qualification changed')
    retained_preparation = None
    if capacity_recovery:
        relocation = references.BASE_META / 'storage_fixture_relocation.json'
        if admission.read(relocation)['status'] != 'PASS':
            raise ValueError('Verified cache relocation required before capacity continuation')
        prepared_meta, _ = references.repair_namespace('metadata_registration_'+design, certificate)
        retained_preparation = require_same_preparation(prepared_meta, source_path, certificate)
    script = inspect.getsource(original.admit_and_run)
    replacements = {
        "folder = references.BASE_META / f'cohort/{design}'": ("folder = references.BASE_META / f'cohort_capacity_recovered/{design}'" if capacity_recovery else
            "folder = references.BASE_META / f'cohort_metadata_registration/{design}'"),
        "attempt = 'primary_'+design": "attempt = 'metadata_registration_'+design",
        "ROOT / 'scripts/pact_gate09_cohort_reference.py'": "ROOT / 'scripts/pact_gate09_cohort_reference_registered.py'"}
    expected = [1,1,2]
    for (before, after), count in zip(replacements.items(), expected):
        if script.count(before) != count:
            raise ValueError('Original fixed cohort adapter no longer matches')
        script = script.replace(before, after)
    def run(command, folder, label):
        if label == 'source' and '--design' in command and command[command.index('--design')+1] == design:
            atomic_write(folder / 'source_reuse.json', dict(status='PASS', source=admission.binding(source_path),
                qualification_stages=source['stages'], prior_failure=admission.binding(failure_path),
                source_or_mapping_reexecutions=0, scientific_method_changes=0), immutable=True)
            print('REUSE_QUALIFIED_SOURCE', design, flush=True)
            return True
        if label == 'prepare' and retained_preparation and source_path in command:
            require_same_preparation(prepared_meta, source_path, certificate)
            atomic_write(folder / 'preparation_reuse.json', dict(status='PASS',preparation=retained_preparation,
                source=admission.binding(source_path),dependency_repair=admission.binding(certificate),
                ATPG_or_placement_reexecutions=0,scientific_method_changes=0),immutable=True)
            print('REUSE_IDENTICAL_QUALIFIED_PREPARATION',design,flush=True)
            return True
        return original.run(command, folder, label)
    namespace = dict(original.__dict__, run=run)
    exec(compile(script, '<Gate09-qualified-metadata-only-cohort-continuation>', 'exec'), namespace)
    record = dict(schema='pact_gate09_fixed_cohort_execution_v1', state='RESUMING_FIXED_COHORT',
        created_utc=original.now(), PID=os.getpid(), Linux_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        previous_execution=admission.binding(previous_path), prior_registration_failure=admission.binding(failure_path),
        retained_preparation=retained_preparation,
        storage_relocation=admission.binding(relocation) if capacity_recovery else None,
        protocol=admission.binding(admission.INTAKE), dependency_repair=admission.binding(certificate),
        source=admission.binding(Path(__file__)), original_controller=admission.binding(Path(original.__file__)),
        design_order=protocol['cohort_order'], records=[r for r in previous['records'] if r['status']=='COMPETITIVE_COMPARISON_TERMINAL'],
        stop_policy=previous['stop_policy'], scientific_method_changes=0,
        correction=('Verified cache relocation; identical qualified source/workload/placement/backend retained; no scientific job repeated'
            if capacity_recovery else 'Metadata registration requires a prior failed-preparation binding only when one exists; no scientific job was repeated'))
    atomic_write(ledger_path, record, immutable=True)
    blocked = None
    for current in protocol['cohort_order'][protocol['cohort_order'].index(design):]:
        if blocked:
            record['records'].append(dict(design=current,status='DEFERRED_PRIOR_ADMISSION_HOLD',
                reason='Fixed-order cohort stopped at '+blocked+'; no claim of source incompatibility or PACT failure'))
        else:
            record.update(state='RUNNING_DESIGN',current_design=current)
            atomic_write(ledger_path, record)
            result = namespace['admit_and_run'](current, certificate)
            record['records'].append(result)
            if result['status'] != 'COMPETITIVE_COMPARISON_TERMINAL':
                blocked = current
        atomic_write(ledger_path, record)
    record.update(state='COHORT_TERMINAL',admission_hold_design=blocked,completed_utc=original.now())
    atomic_write(ledger_path, record)
    print('GATE09_RESUMED_COHORT_TERMINAL', blocked, flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous',type=Path,required=True)
    parser.add_argument('--dependency-repair',type=Path,required=True)
    parser.add_argument('--ledger',type=Path,required=True)
    args=parser.parse_args()
    os.environ['PYTHONPATH']=':'.join(str(ROOT / p) for p in ('.optimizer-deps','src','scripts'))
    resume(args.previous,args.dependency_repair,args.ledger)
