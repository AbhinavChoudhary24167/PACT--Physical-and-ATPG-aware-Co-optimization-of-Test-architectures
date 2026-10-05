#!/usr/bin/env python3
"""Continue the immutable cohort after b14, subject to resource admission.

Stop at the first source/reference/resource admission hold. Scientific wins,
losses and mixed results never change design order, weights, seeds or budgets.
"""
import argparse
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
import pact_gate09_measure as measure
import pact_gate09_reference as references
from pact_experiment_receipts import atomic_write


def now():
    return datetime.now(timezone.utc).isoformat()


def run(command, folder, label):
    path = folder / (label+'.execution.json')
    if path.exists():
        raise ValueError('Preserve prior cohort stage; no implicit replay')
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / (label+'.log')
    start = time.perf_counter()
    with log.open('x') as stream:
        process = subprocess.Popen(list(map(str,command)), stdout=stream, stderr=subprocess.STDOUT)
        atomic_write(folder / (label+'.started.json'), dict(command=list(map(str,command)),
            PID=process.pid, created_utc=now(), state='STARTED'), immutable=True)
        code = process.wait()
    atomic_write(path, dict(command=list(map(str,command)), returncode=code,
        wall_seconds=time.perf_counter()-start, completed_utc=now(), log=admission.binding(log)), immutable=True)
    print('COHORT_STAGE', label, code, flush=True)
    return code == 0


def admit_and_run(design, certificate):
    folder = references.BASE_META / f'cohort/{design}'
    audit_dir = folder / 'capacity'
    command = [sys.executable, ROOT / 'scripts/pact_gate09_admission.py', '--output', audit_dir,
        '--refresh-capacity-from', references.BASE_META / '01_capacity_pass/admission.json']
    if not run(command, folder, 'capacity'):
        return dict(design=design, status='PACT_GATE09_BLOCKED_CAPACITY', reason='Fixed prelaunch capacity floor not satisfied',
                    receipt=str(audit_dir / 'admission.json'))
    command = [sys.executable, ROOT / 'scripts/pact_gate09_source_admit.py', '--design', design,
               '--audit', audit_dir / 'admission.json']
    source = references.BASE_META / f'source_admission/{design}.json'
    if not run(command, folder, 'source'):
        return dict(design=design, status='SOURCE_ADMISSION_HOLD', receipt=str(source),
                    reason=admission.read(source).get('error') if source.exists() else 'See preserved source launch log')
    attempt = 'primary_'+design
    meta, raw = references.repair_namespace(attempt, certificate)
    common = ['--source-admission', source, '--attempt', attempt, '--dependency-repair', certificate]
    command = [sys.executable, ROOT / 'scripts/pact_gate09_cohort_reference.py', 'prepare', *common]
    if not run(command, folder, 'prepare'):
        return dict(design=design, status='ATPG_OR_PLACEMENT_ADMISSION_HOLD',
            receipt=str(meta / f'workers/{design}/prepare.json'), reason='Frozen 900s ATPG / common preparation gate did not qualify')
    prep = admission.read(meta / f'physical/{design}/preparation.json')
    src = admission.read(source)
    from pact.test.pattern_parser import parse_fan_pat
    patterns = len(parse_fan_pat(Path(prep['patterns']['path'])).patterns)
    mapped = admission.read(src['mapped_json']['path'])
    dimensions = dict(nets=2*len(mapped['modules'][design]['netnames']),
        cycles=2*patterns*(math.ceil(src['topology']['FF_count']/2)+2))
    retained = sum(prep[k]['bytes'] for k in ('source', 'patterns', 'placed_def', 'placed_netlist', 'source_placed_database'))
    try:
        projection = measure.capacity(admission.read(admission.INTAKE), dimensions, retained)
        atomic_write(folder / 'projected_activity_capacity.json', dict(status='PASS', capacity=projection,
            dimension_rule='Conservative 2*mapped net names; two*(ceil(FF/2)+2) clocks per observed pattern',
            PACT_search_started=False, before_reference_routing=True), immutable=True)
    except RuntimeError as error:
        atomic_write(folder / 'projected_activity_capacity.json', dict(status='PACT_GATE09_BLOCKED_CAPACITY',
            error=str(error), dimensions=dimensions, retained_bytes=retained,
            PACT_search_started=False, before_reference_routing=True), immutable=True)
        return dict(design=design, status='PACT_GATE09_BLOCKED_CAPACITY',
            receipt=str(folder / 'projected_activity_capacity.json'), reason=str(error))
    if not run([sys.executable, ROOT / 'scripts/pact_gate09_cohort_reference.py', 'references', *common], folder, 'references'):
        return dict(design=design, status='EXTERNAL_REFERENCE_ADMISSION_HOLD',
            receipt=str(meta / f'physical/{design}/presearch_qualification.json'), reason='No admissible resolved external reference')
    selected = admission.read(meta / f'baselines/{design}_selected.json')['method']
    for action in ('prepare', 'run'):
        if not run([sys.executable, ROOT / 'scripts/pact_gate09_competitor_measure.py', action,
            '--method', selected, *common], folder, 'selected_exact_'+action):
            return dict(design=design, status='EXACT_REFERENCE_ADMISSION_HOLD',
                receipt=str(meta / f'workers/{design}/measure_{action}_{selected}.json'), reason='Complete exact external reference did not qualify')
    campaign = ['--design', design, *common]
    for action in ('freeze', 'generate'):
        if not run([sys.executable, ROOT / 'scripts/pact_gate09_campaign.py', action, *campaign], folder, action):
            return dict(design=design, status='REGISTERED_BASELINE_GENERATION_HOLD', reason='See '+action+' launch receipts')
    for method in ('B4', 'B5'):
        run([sys.executable, ROOT / 'scripts/pact_gate09_campaign.py', 'route', '--method', method, *campaign], folder, 'route_'+method)
    for method in ('B0', 'B1', 'B2', 'B3T', 'B4', 'B5'):
        if method == selected:
            continue
        for action in ('prepare', 'run'):
            run([sys.executable, ROOT / 'scripts/pact_gate09_competitor_measure.py', action,
                '--method', method, *common], folder, 'exact_'+method+'_'+action)
    report = references.BASE_META / f'final/{design}'
    if not run([sys.executable, ROOT / 'scripts/pact_gate09_finish_design.py', *campaign,
        '--report-directory', report], folder, 'PACT_finish'):
        return dict(design=design, status='PACT_EXECUTION_OR_REPORT_HOLD', reason='See PACT finish receipts',
            receipt=str(meta / f'workers/{design}/campaign_search.json'))
    return dict(design=design, status='COMPETITIVE_COMPARISON_TERMINAL', report=admission.binding(report / 'comparison.json'),
        classification=admission.read(report / 'comparison.json')['classification'])


def main(certificate):
    ledger_path = references.BASE_META / 'cohort_execution.json'
    if ledger_path.exists():
        raise ValueError('Preserve existing cohort supervision; no implicit replay')
    protocol = admission.read(admission.INTAKE)
    record = dict(schema='pact_gate09_fixed_cohort_execution_v1', created_utc=now(), state='WAITING_B14',
        PID=os.getpid(), Linux_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        protocol=admission.binding(admission.INTAKE), source=admission.binding(Path(__file__)),
        dependency_repair=admission.binding(certificate), design_order=protocol['cohort_order'], records=[],
        stop_policy='First source, reference or resource admission hold; never stop or change order because of PACT activity outcomes',
        scientific_method_changes=0)
    atomic_write(ledger_path, record, immutable=True)
    first = references.BASE_META / 'repair_attempts/python_transport/completion/b14_opt.json'
    supervision = references.BASE_META / 'repair_attempts/python_transport/supervision/b14_opt/finish.json'
    while not first.exists():
        if supervision.exists() and admission.read(supervision)['state'] == 'BLOCKED':
            record.update(state='B14_EXECUTION_HOLD', reason='Existing b14 supervisor requires diagnosis; no stage repeated', completed_utc=now())
            atomic_write(ledger_path, record)
            return False
        time.sleep(2)
    record['records'].append(dict(design='b14_opt', status='COMPETITIVE_COMPARISON_TERMINAL',
        completion=admission.binding(first), report=admission.read(first)['report']))
    blocked = None
    for design in protocol['cohort_order'][1:]:
        if blocked:
            record['records'].append(dict(design=design, status='DEFERRED_PRIOR_ADMISSION_HOLD',
                reason='Fixed-order cohort stopped at '+blocked+'; no claim of source incompatibility or PACT failure'))
        else:
            record.update(state='RUNNING_DESIGN', current_design=design)
            atomic_write(ledger_path, record)
            result = admit_and_run(design, certificate)
            record['records'].append(result)
            if result['status'] != 'COMPETITIVE_COMPARISON_TERMINAL':
                blocked = design
        atomic_write(ledger_path, record)
    record.update(state='COHORT_TERMINAL', completed_utc=now(), admission_hold_design=blocked)
    atomic_write(ledger_path, record)
    print('GATE09_COHORT_TERMINAL', blocked, flush=True)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dependency-repair', type=Path, required=True)
    args = parser.parse_args()
    os.environ['PYTHONPATH'] = ':'.join(str(ROOT / p) for p in ('.optimizer-deps', 'src', 'scripts'))
    raise SystemExit(0 if main(args.dependency_repair) else 2)
