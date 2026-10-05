#!/usr/bin/env python3
"""Final read-only qualification audit; no scientific stage is executed."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
from pact_experiment_receipts import atomic_write


def bindings(value):
    if isinstance(value, dict):
        if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
            yield value
        else:
            for child in value.values():
                yield from bindings(child)
    elif isinstance(value, list):
        for child in value:
            yield from bindings(child)


def validate(directory, output):
    if output.exists():
        raise ValueError('Preserve previous validation')
    protocol = admission.read(admission.INTAKE)
    frozen = {name: admission.verify(value) for name,value in protocol['frozen_sources'].items()}
    tools = {name: admission.verify(value) for name,value in protocol['frozen_tools'].items()}
    prior = admission.read(ROOT / 'results/pact_gate09_open_source_20261005/00_preflight/admission.json')
    historical = {name: admission.verify(row['expected']) for name,row in prior['preservation']['historical'].items()}
    recent = {name: admission.verify(row.get('expected', row['observed'])) for name,row in prior['preservation']['recent'].items()}
    failures = []
    checked = {}
    snapshots = {p.stem: p for p in directory.rglob('execution_sources/*.py')}
    files = list(directory.rglob('*.json'))
    # Completed primary packages are rehashed, including compressed counts and
    # bound simulation/tool sources. Failed development attempts remain evidence,
    # but are not reclassified as qualified primary packages.
    for path in files:
        try:
            value = admission.read(path)
        except Exception as error:
            failures.append(dict(path=str(path), error='Invalid JSON: '+str(error)))
            continue
        if (value.get('status') not in ('QUALIFIED', 'PASS', 'SEARCH_COMPLETE', 'SOURCE_MAPPED_EQUIVALENCE_QUALIFIED_PENDING_PHYSICAL_ATPG_REFERENCE',
                'PACT_GATE09_ADMISSION_COMPLETE', 'COMPETITIVE_COMPARISON_TERMINAL') and
                value.get('schema') not in ('pact_cpu_exact_activity_v1', 'pact_cold_start_input_v1',
                    'pact_gate09_comparison_v1', 'pact_gate09_competitor_freeze_v1',
                    'pact_gate09_campaign_report_v1', 'pact_gate09_fixed_cohort_execution_v1')):
            continue
        bound = list(bindings(value))
        if value.get('status') == 'QUALIFIED' and value.get('output_folder') and value.get('complete'):
            folder = admission.resolve(value['output_folder'])
            trace = admission.read(folder / 'activity_summary.json')['activity_trace']
            bound.append(dict(path=str(folder / 'activity.counts.gz'), sha256=trace['sha256'], bytes=trace['bytes']))
        for item in bound:
            key = (item['path'], item['sha256'])
            if key in checked:
                continue
            result = admission.verify(item)
            if result['status'] != 'PASS' and item['sha256'] in snapshots:
                archived = admission.binding(snapshots[item['sha256']])
                result = dict(status='PASS', original_path=item['path'], preserved_execution_source=archived)
            checked[key] = result
            if result['status'] != 'PASS':
                failures.append(dict(receipt=str(path), artifact=item, verification=result))
    for label, group in (('frozen_sources', frozen), ('tools', tools), ('historical', historical), ('recent', recent)):
        failures += [dict(group=label, path=name, result=result) for name,result in group.items() if result['status']!='PASS']
    tracked = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z']).decode().split('\0')
    new_files = [p for p in tracked if p.startswith('results/pact_gate09_open_source_20261005/') and (ROOT / p).is_file()]
    largest = sorted((dict(path=p, bytes=(ROOT / p).stat().st_size) for p in new_files), key=lambda r:r['bytes'], reverse=True)[:10]
    disposables = [p for p in new_files if Path(p).suffix in ('.odb', '.vcd', '.vvp', '.vpi', '.u8', '.whl') or p.endswith('activity.counts.gz')]
    if disposables:
        failures.append(dict(error='Tracked bulk/disposable scientific runtime files', files=disposables))
    record = dict(schema='pact_gate09_final_readonly_audit_v1', created_utc=datetime.now(timezone.utc).isoformat(),
        status='PASS' if not failures else 'FAIL', scientific_campaigns_reexecuted=0,
        frozen_source_count=len(frozen), historical_count=len(historical), recent_count=len(recent),
        qualified_artifacts_rehashed=len(checked), JSON_files_parsed=len(files), failures=failures,
        tracked_campaign_file_count=len(new_files), largest_tracked_campaign_files=largest,
        bulk_disposable_files_tracked=disposables, protocol=admission.binding(admission.INTAKE))
    atomic_write(output, record, immutable=True)
    print(json.dumps(record, indent=2), flush=True)
    return not failures


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if validate(args.directory, args.output) else 2)
