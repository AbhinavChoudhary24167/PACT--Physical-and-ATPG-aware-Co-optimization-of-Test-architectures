#!/usr/bin/env python3
"""Separate prospective PACT input from source-preparation storage; no replay."""
import argparse
import inspect
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
import pact_gate09_campaign as campaign
import pact_gate09_cohort as cohort
import pact_gate09_finish_design as finishing
import pact_gate09_reference as references
from pact_experiment_receipts import atomic_write

INPUT_ID = 'input_namespace'
BASE_HASHES = {
    'pact_gate09_campaign.py': '3c9880f2f44af40fdc689de34de2eff0f75f07fa34a467108e9ab8a9faa657c9',
    'pact_gate09_cohort.py': '4ed6aff54f09378a2b6c3ceb774d16b3a4df40ee84abded5df66160f278d9eb0',
    'pact_gate09_finish_design.py': 'f4724bc9c1a5da6c84de029edb365ca6e0dceac75f828a273d8094fd05e07561',
}


def check_bases():
    for name, expected in BASE_HASHES.items():
        if admission.digest(ROOT / 'scripts' / name) != expected:
            raise ValueError('Preserved orchestration source changed: '+name)


def allocate_input(raw, design):
    path = raw / 'inputs' / design / 'PACT_primary'
    if path.exists():
        raise ValueError('Preserve prospective PACT input')
    path.mkdir(parents=True)
    return path


def require_unstarted_primary(meta, raw, design):
    protected = [meta / f'inputs/{design}/cold_start_input.json',
                 meta / f'searches/{design}', raw / f'search_worker/{design}',
                 meta / f'selections/{design}', meta / f'workers/{design}/campaign_search.lifecycle.json']
    if any(path.exists() for path in protected):
        raise ValueError('Primary input/search already started; no namespace recovery')
    legacy = raw / f'inputs/{design}'
    if any((legacy / name).exists() for name in ('net_mapping.json','routed.odb','net_activity_capacitance.csv','topology.json')):
        raise ValueError('Prior prospective artifacts exist; preserve them')
    failure = meta / f'workers/{design}/campaign_input.json'
    if failure.exists():
        record = admission.read(failure)
        if record.get('status') != 'PACT_GATE09_CAMPAIGN_STAGE_BLOCKED' or record.get('error') != 'Preserve prospective PACT input':
            raise ValueError('Only the proven pre-copy directory collision may be continued')


def adapted_input():
    source = inspect.getsource(campaign.prepare_input)
    before = "    input_root = raw / f'inputs/{design}'\n    if input_root.exists():\n        raise ValueError('Preserve prospective PACT input')\n    input_root.mkdir(parents=True)"
    if source.count(before) != 1:
        raise ValueError('Preserved input adapter no longer matches')
    namespace = dict(campaign.__dict__, allocate_input=allocate_input)
    exec(compile(source.replace(before, '    input_root = allocate_input(raw, design)'),
                 '<Gate09-input-directory-qualification>', 'exec'), namespace)
    return namespace['prepare_input']


def adapted_admission():
    source = inspect.getsource(cohort.admit_and_run)
    replacements = {
        "folder = references.BASE_META / f'cohort/{design}'": "folder = references.BASE_META / f'cohort_input_namespaced/{design}'",
        "attempt = 'primary_'+design": "attempt = 'metadata_registration_'+design",
        "ROOT / 'scripts/pact_gate09_cohort_reference.py'": "ROOT / 'scripts/pact_gate09_cohort_reference_registered.py'",
        "ROOT / 'scripts/pact_gate09_finish_design.py', *campaign": "ROOT / 'scripts/pact_gate09_input_recovery.py', 'finish', *campaign",
    }
    for (before, after), count in zip(replacements.items(), (1,1,2,1)):
        if source.count(before) != count:
            raise ValueError('Preserved cohort adapter no longer matches')
        source = source.replace(before, after)
    namespace = dict(cohort.__dict__)
    exec(compile(source, '<Gate09-preserved-cohort-admission>', 'exec'), namespace)
    return namespace['admit_and_run']


def input_stage(args):
    check_bases()
    meta, raw = references.repair_namespace(args.attempt, args.dependency_repair)
    require_unstarted_primary(meta, raw, args.design)
    args.action, args.method, args.execution_id = 'input', None, INPUT_ID
    namespace = dict(campaign.__dict__, prepare_input=adapted_input(), __file__=__file__)
    exec(compile(inspect.getsource(campaign.worker), '<Gate09-preserved-campaign-worker>', 'exec'), namespace)
    return bool(namespace['worker'](args)['completed'])


def finish(args):
    check_bases()
    meta, raw = references.repair_namespace(args.attempt, args.dependency_repair)
    corrected = meta / f'workers/{args.design}/campaign_input_{INPUT_ID}.json'
    if not corrected.exists():
        command = [sys.executable, Path(__file__), 'input', '--design', args.design,
                   '--source-admission', args.source_admission, '--attempt', args.attempt,
                   '--dependency-repair', args.dependency_repair]
        if subprocess.run(list(map(str, command))).returncode:
            return False

    def stage(command, outcome, accepted):
        if outcome.name == 'campaign_input.json':
            return finishing.stage(command, corrected, accepted)
        return finishing.stage(command, outcome, accepted)

    namespace = dict(finishing.__dict__, stage=stage, __file__=__file__)
    exec(compile(inspect.getsource(finishing.finish), '<Gate09-preserved-design-finisher>', 'exec'), namespace)
    return namespace['finish'](args)


def resume(args):
    check_bases()
    admit_and_run = adapted_admission()
    previous = admission.read(args.previous)
    if previous['state'] != 'COHORT_TERMINAL' or previous['admission_hold_design'] != 'b15_opt':
        raise ValueError('Expected preserved b15 pre-search input stop')
    if args.ledger.exists():
        raise ValueError('Preserve previous continuation')
    design, attempt = 'b15_opt', 'metadata_registration_b15_opt'
    meta, raw = references.repair_namespace(attempt, args.dependency_repair)
    require_unstarted_primary(meta, raw, design)
    failure = meta / f'workers/{design}/campaign_input.json'
    if not failure.exists():
        raise ValueError('Preserved collision outcome required')
    for method in ('B0','B1','B2','B3T','B4','B5'):
        path = meta / f'activity/GATE09_PRIMARY/{design}/{method}/normal/result.json'
        value = admission.read(path)
        if value['status'] != 'QUALIFIED' or not value['complete']:
            raise ValueError('All preserved b15 baselines must be fully qualified')
        if admission.verify(value['manifest'])['status'] != 'PASS':
            raise ValueError('Preserved baseline manifest changed')
    protocol = admission.read(admission.INTAKE)
    record = dict(schema='pact_gate09_fixed_cohort_execution_v1', state='RUNNING_DESIGN',
        current_design=design, created_utc=cohort.now(), PID=os.getpid(),
        Linux_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        previous_execution=admission.binding(args.previous), prior_input_failure=admission.binding(failure),
        source=admission.binding(Path(__file__)), protocol=admission.binding(admission.INTAKE),
        dependency_repair=admission.binding(args.dependency_repair), design_order=protocol['cohort_order'],
        records=[r for r in previous['records'] if r['status']=='COMPETITIVE_COMPARISON_TERMINAL'],
        stop_policy=previous['stop_policy'], scientific_method_changes=0,
        correction='Fresh child directory for prospective input; all source/reference/baseline results reused without replay')
    atomic_write(args.ledger, record, immutable=True)
    folder = references.BASE_META / f'cohort_input_namespaced/{design}'
    report = references.BASE_META / f'final/{design}'
    command = [sys.executable, Path(__file__), 'finish', '--design', design,
        '--source-admission', references.BASE_META / f'source_admission/{design}.json',
        '--attempt', attempt, '--dependency-repair', args.dependency_repair, '--report-directory', report]
    ok = cohort.run(command, folder, 'PACT_finish')
    record['records'].append(dict(design=design, status='COMPETITIVE_COMPARISON_TERMINAL',
        report=admission.binding(report / 'comparison.json'), classification=admission.read(report / 'comparison.json')['classification'])
        if ok else dict(design=design,status='PACT_EXECUTION_OR_REPORT_HOLD',reason='See preserved namespaced-input finish receipts',
            receipt=str(meta / f'workers/{design}/campaign_input_{INPUT_ID}.json')))
    blocked = None if ok else design
    for current in protocol['cohort_order'][2:]:
        if blocked:
            result = dict(design=current,status='DEFERRED_PRIOR_ADMISSION_HOLD',
                reason='Fixed-order cohort stopped at '+blocked+'; no claim of source incompatibility or PACT failure')
        else:
            record.update(current_design=current)
            atomic_write(args.ledger, record)
            result = admit_and_run(current, args.dependency_repair)
            if result['status'] != 'COMPETITIVE_COMPARISON_TERMINAL':
                blocked = current
        record['records'].append(result)
        atomic_write(args.ledger, record)
    record.update(state='COHORT_TERMINAL',completed_utc=cohort.now(),admission_hold_design=blocked)
    atomic_write(args.ledger, record)
    print('GATE09_INPUT_CONTINUATION_TERMINAL',blocked,flush=True)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('input','finish','resume'))
    parser.add_argument('--design')
    parser.add_argument('--source-admission',type=Path)
    parser.add_argument('--attempt')
    parser.add_argument('--dependency-repair',type=Path,required=True)
    parser.add_argument('--report-directory',type=Path)
    parser.add_argument('--previous',type=Path)
    parser.add_argument('--ledger',type=Path)
    args = parser.parse_args()
    os.environ['PYTHONPATH'] = ':'.join(str(ROOT / p) for p in ('.optimizer-deps','src','scripts'))
    if args.action == 'resume':
        resume(args)
    else:
        raise SystemExit(0 if (input_stage(args) if args.action=='input' else finish(args)) else 2)
