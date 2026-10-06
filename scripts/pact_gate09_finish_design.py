#!/usr/bin/env python3
"""Sequentially finish one admitted Gate-09 design; never replay prior work."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
import pact_gate09_admission as admission
import pact_gate09_reference as references
from pact_experiment_receipts import atomic_write


def stage(command, outcome, accepted):
    if outcome.exists():
        receipt = admission.read(outcome)
        if receipt['status'] in accepted:
            print('REUSE_PRESERVED_STAGE', str(outcome), flush=True)
            return True
        print('PRESERVED_FAILED_STAGE', str(outcome), receipt['status'], flush=True)
        return False
    result = subprocess.run(list(map(str, command)))
    return bool(result.returncode == 0 and outcome.exists() and admission.read(outcome)['status'] in accepted)


def finish(args):
    meta, raw = references.repair_namespace(args.attempt, args.dependency_repair)
    os.environ['PYTHONPATH'] = ':'.join(str(ROOT / p) for p in ('.optimizer-deps', 'src', 'scripts'))
    common = ['--design', args.design, '--source-admission', args.source_admission,
        '--attempt', args.attempt, '--dependency-repair', args.dependency_repair]
    for action in ('input', 'search'):
        command = [sys.executable, ROOT / 'scripts/pact_gate09_campaign.py', action, *common]
        if not stage(command, meta / f'workers/{args.design}/campaign_{action}.json', {'PASS'}):
            return False
    selection_path = meta / f'selections/{args.design}/preselected_candidates.json'
    selection = admission.read(selection_path)
    measurement = ['--source-admission', args.source_admission, '--attempt', args.attempt,
                   '--dependency-repair', args.dependency_repair]
    for selected in selection['records']:
        method = selected['candidate']
        if not stage([sys.executable, ROOT / 'scripts/pact_gate09_campaign.py', 'route', '--method', method, *common],
                meta / f'workers/{args.design}/campaign_route_{method}.json', {'PASS'}):
            continue
        for action in ('prepare', 'run'):
            stage([sys.executable, ROOT / 'scripts/pact_gate09_competitor_measure.py', action,
                '--method', method, *measurement], meta / f'workers/{args.design}/measure_{action}_{method}.json',
                {'REFERENCE_EXPORT_AND_STIMULUS_QUALIFIED_PENDING_CPU_EXACT', 'QUALIFIED'})
    if args.report_directory.exists():
        raise ValueError('Preserve completed comparison; no implicit report replacement')
    command = [sys.executable, ROOT / 'scripts/pact_gate09_report.py', '--design', args.design,
        '--attempt', args.attempt, '--dependency-repair', args.dependency_repair, '--output', args.report_directory]
    result = subprocess.run(list(map(str, command)))
    if result.returncode:
        return False
    atomic_write(meta / f'completion/{args.design}.json', dict(design=args.design,
        status='COMPETITIVE_COMPARISON_TERMINAL', created_utc=datetime.now(timezone.utc).isoformat(),
        report=admission.binding(args.report_directory / 'comparison.json'),
        selection=admission.binding(selection_path), launcher=admission.binding(Path(__file__)),
        final_candidates_generated=0, extra_seeds=0, hidden_routes=0, scientific_method_changes=0), immutable=True)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design', required=True)
    parser.add_argument('--source-admission', type=Path, required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--dependency-repair', type=Path, required=True)
    parser.add_argument('--report-directory', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if finish(args) else 2)
