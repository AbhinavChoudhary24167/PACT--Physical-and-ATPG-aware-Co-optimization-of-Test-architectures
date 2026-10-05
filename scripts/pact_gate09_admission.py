#!/usr/bin/env python3
"""Read-only Gate-09 provenance and capacity audit; never launch a campaign.

The prior intake and all historical receipts stay immutable. Each invocation
requires a fresh output directory. A passing capacity check alone does not
admit a source or a reference and cannot authorize scientific execution.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
INTAKE = ROOT / 'results/pact_gate9_large_scale_unseen_20261005/benchmark_preregistration.json'
PREVIOUS = ROOT / 'results/pact_large_unseen_gate9_20261005'
FROZEN = ROOT / 'results/pact_generalization_20261004/manifests/pact_v1_frozen_manifest.json'
B3 = ROOT / 'results/pact_oss_benchmark/topology_recovery_20261004/baselines/B3T_openroad_10666_serialization_repaired/source_manifest.json'
MINIMUM_D = 25 * 1024**3
MINIMUM_C = 6 * 1024**3


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def binding(path):
    path = Path(path)
    return dict(path=str(path), sha256=digest(path), bytes=path.stat().st_size)


def resolve(raw, root=ROOT):
    if raw.startswith('repo://'):
        return root / raw.removeprefix('repo://')
    if raw.startswith('run://'):
        base = Path('D:/PACT_EXPERIMENTS') if os.name == 'nt' else Path('/mnt/d/PACT_EXPERIMENTS')
        return base / raw.removeprefix('run://')
    if os.name == 'nt' and raw.startswith('/mnt/') and len(raw) > 7 and raw[6] == '/':
        return Path(raw[5].upper() + ':/' + raw[7:])
    if os.name != 'nt' and len(raw) > 2 and raw[1:3] in (':\\', ':/'):
        return Path('/mnt/' + raw[0].lower() + '/' + raw[3:].replace('\\', '/'))
    return Path(raw)


def verify(value):
    path = resolve(value['path'])
    try:
        observed = binding(path)
        valid = observed['sha256'] == value['sha256'] and ('bytes' not in value or observed['bytes'] == value['bytes'])
        return dict(expected=value, observed=observed, status='PASS' if valid else 'HASH_MISMATCH')
    except OSError as error:
        return dict(expected=value, status='UNAVAILABLE', error=str(error))


def capacity(policy, observed):
    """Do not permit a caller or edited protocol to relax the registered floor."""
    if policy['D_minimum_floor_bytes'] < MINIMUM_D or policy['C_minimum_free_bytes'] < MINIMUM_C:
        raise ValueError('Gate-09 fixed capacity floor cannot be reduced')
    rows = {}
    for drive, key in (('C', 'C_minimum_free_bytes'), ('D', 'D_minimum_floor_bytes')):
        minimum = policy[key]
        free = observed.get(drive, {}).get('free')
        rows[drive] = dict(free_bytes=free, minimum_free_bytes=minimum,
                           deficit_bytes=None if free is None else max(0, minimum - free),
                           status='PASS' if free is not None and free >= minimum else 'BLOCKED')
    return dict(volumes=rows, status='PASS' if all(row['status'] == 'PASS' for row in rows.values()) else 'PACT_GATE09_BLOCKED_CAPACITY',
                per_design_margin='Pending admitted artifact dimensions; fixed floor is a minimum, not a sufficient per-design budget')


def command(args, cwd=None):
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return dict(command=list(map(str, args)), exit_code=None, stdout='', stderr='',
                    observation_status='TIMED_OUT', timeout_seconds=30)
    return dict(command=list(map(str, args)), exit_code=result.returncode,
                stdout=result.stdout.strip(), stderr=result.stderr.strip())


def git(path, *args):
    return command(['git', '-C', str(path), *args])


def audit(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Fresh audit directory required; preserve existing receipts')
    intake, historical, b3 = read(INTAKE), read(FROZEN), read(B3)
    component_path = ROOT / 'results/pact_gate09_open_source_20261005/common_backend_components.json'
    components = read(component_path) if component_path.exists() else None
    observed = {}
    for drive in ('C', 'D', 'F'):
        path = drive + ':/' if os.name == 'nt' else '/mnt/' + drive.lower()
        if Path(path).exists():
            observed[drive] = dict(zip(('total', 'used', 'free'), shutil.disk_usage(path)))
    cap = capacity(intake['resource_policy'], observed)
    # Audit only bytes and receipts; do not reexecute qualified experiments.
    sources = {name: verify(value) for name, value in intake['frozen_sources'].items()}
    tools = {name: verify(value) for name, value in intake['frozen_tools'].items()}
    source_inputs = {name: verify(value) for name, value in intake['external_source']['provenance_files'].items()}
    cohort = []
    for row in intake['cohort']:
        inputs = {kind: verify(value) for kind, value in row['source_files'].items()}
        cohort.append(dict(design=row['design'], family=row['family'], independence_role=row['independence_role'],
                           source_FF_count=row['source_FF_count'], source_assignments=row['source_gate_assignments'],
                           source_verification=inputs, source_admission='PENDING_SEQUENTIAL_EQUIVALENCE_AND_MAPPING',
                           reference_status='NOT_ADMITTED', PACT_search_started=False))
    baseline_sources = {}
    for method, path in (
        ('B1', ROOT / 'results/pact_oss_benchmark/baselines/B1_openroad_native/source_pin.json'),
        ('B2', ROOT / 'results/pact_oss_benchmark/recovery_20261003/baselines/B2_openroad_10176/source_manifest.json'),
        ('B3T', B3),
    ):
        data = read(path)
        binary = data.get('immutable_binary')
        baseline_sources[method] = dict(manifest=binding(path), source_commit=data.get('source_commit', data.get('commit')),
                                        binary_verification=verify(binary) if binary else None,
                                        terminology='OPENROAD_QUALIFIED_PATCHED' if method == 'B3T' else 'OPEN_SOURCE_PINNED',
                                        qualified_on_gate09=False)
    cpu = read(ROOT / 'results/pact_cpu_scalability_20261005/gate0.json')
    preservation = {name: verify(dict(path='repo://' + name, sha256=value)) for name, value in cpu['historical_files'].items()}
    recent = {name: verify(value) for name, value in intake['entry_evidence'].items()}
    recent['preservation'] = verify(intake['preservation'])
    for design in ('s38417', 's38584'):
        for name in ('searches/' + design + '/selection.json', 'final/' + design + '.json'):
            p = PREVIOUS / name
            if p.exists():
                recent[name] = dict(observed=binding(p), status='SNAPSHOT_BOUND')
    all_checks = [*sources.values(), *tools.values(), *source_inputs.values(), *preservation.values()]
    all_checks += [value for row in cohort for value in row['source_verification'].values()]
    all_checks += [value for value in recent.values() if 'expected' in value]
    all_checks += [row['binary_verification'] for row in baseline_sources.values() if row['binary_verification']]
    provenance_pass = all(row['status'] == 'PASS' for row in all_checks)
    linux = {}
    if os.name != 'nt':
        for label, path in (('ORFS', '/root/pact-deps/OpenROAD-flow-scripts'),
                            ('OpenROAD_installed_source_checkout', '/root/pact-deps/OpenROAD'),
                            ('FAN_upstream', '/root/pact-deps/FAN_ATPG'),
                            ('FAN_qualified_repair', str(ROOT / 'scratch/FAN_ATPG-report-repair'))):
            linux[label] = dict(head=git(path, 'rev-parse', 'HEAD'), status=git(path, 'status', '--short'))
        linux['OpenROAD_binary_version'] = command(['/usr/bin/openroad', '-version'])
        linux['Yosys_version'] = command(['/usr/bin/yosys', '-V'])
        linux['Yosys_binary'] = binding('/usr/bin/yosys')
    backend = dict(historical['backend'], FAN=historical['FAN_repair'],
                   OpenSTA=dict(B3T_commit=b3['OpenSTA_commit'], B3T_parent=b3['OpenSTA_parent'],
                                common_backend_declared_commit=components['components']['sta']['sha'] if components else None,
                                common_backend_state='Bundled in SHA-bound /usr/bin/openroad; upstream Git pin acquired separately; independent rebuild not performed'),
                   OpenRCX=dict(parent_OpenROAD_revision=historical['backend']['baselines']['B1_openroad_native']['commit'],
                                declared_source_tree_sha=components['components']['rcx']['sha'] if components else None,
                                distribution='Bundled in common OpenROAD binary; src/rcx at the parent revision'),
                   upstream_component_receipt=binding(component_path) if components else None,
                   platform='Nangate45', platform_provenance=binding(ROOT / 'results/pact_cpu_scalability_20261005/spef_patch/implementation_evidence.json'),
                   runtime_tree_observations=linux)
    record = dict(schema='pact_gate09_admission_audit_v1', created_utc=datetime.now(timezone.utc).isoformat(),
                  gate='GATE09', status=cap['status'] if cap['status'] != 'PASS' else 'PACT_GATE09_REFERENCE_ADMISSION_PENDING',
                  repository=dict(head=git(ROOT, 'rev-parse', 'HEAD'), branch=git(ROOT, 'branch', '--show-current'),
                                  status_at_audit=git(ROOT, 'status', '--short')),
                  protocol=binding(INTAKE), frozen_method=dict(implementation_SHA=intake['implementation_SHA'],
                        merged_SHA=intake['merged_SHA'], source_verification=sources,
                        configuration=intake['fixed_method'], metric_definitions=binding(ROOT / 'docs/methodology.md'),
                        method_changed=False, blind_to_gate09_competitor_results=True),
                  backend=backend, tools=tools, baseline_reuse=baseline_sources,
                  external_source=intake['external_source'], source_provenance_verification=source_inputs,
                  cohort_order=intake['cohort_order'], design_admission=cohort,
                  capacity=cap, resource_snapshot=observed,
                  preservation=dict(historical=preservation, recent=recent, scientific_campaigns_reexecuted=0,
                                    prior_registration=binding(PREVIOUS / 'campaign_registration.json'),
                                    count=len(preservation)),
                  provenance_status='PASS' if provenance_pass else 'PACT_GATE09_BLOCKED_PROVENANCE',
                  heavy_launch_allowed=False, reference_qualified=False,
                  missing_stages=['SOURCE_MAPPING', 'REFERENCE_PHYSICAL_ATPG_EXACT_ACTIVITY', 'COMPETITOR_DEFINITION_FREEZE',
                                  'BASELINE_GENERATION', 'FROZEN_PACT_SEARCH', 'CANDIDATE_FREEZE', 'COMMON_QUALIFICATION', 'COMPARISON'],
                  machine=dict(platform=platform.platform(), python=platform.python_version(), CPU_only=True),
                  cleanup_or_relocation=None)
    if not provenance_pass:
        record['status'] = 'PACT_GATE09_BLOCKED_PROVENANCE'
    output.mkdir(parents=True)
    with (output / 'admission.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps(dict(status=record['status'], provenance=record['provenance_status'],
                          sources=len(sources), historical_files=len(preservation),
                          capacity=cap, audit_path=str(output / 'admission.json')), indent=2), flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.output)
    raise SystemExit(0 if result['provenance_status'] == 'PASS' and result['capacity']['status'] == 'PASS' else 2)


if __name__ == '__main__':
    main()
