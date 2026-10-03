#!/usr/bin/env python3
"""Audit historical cache eligibility without rerouting or changing old evidence.

PASS means the eligibility policy was verified. Explicitly ineligible caches
remain preserved and are excluded from reuse; they do not become qualified.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from pact_oss_benchmark import ROOT, OUT, DESIGNS, GIT, binding, read, write

P0 = '9d9103027918b1d4af2b209e6d36133ad82d4a4e'
ORFS = Path('/root/pact-deps/OpenROAD-flow-scripts')
ORFS_PIN = '5e8b1450d19263f797a27c4f371b9dd19f32a3aa'
RECEIPT = OUT / 'receiver_recovery_20261003/reuse_preflight/eligibility.json'
NAMESPACES = ('pact_candidate_stateful', 'pact_candidate_sensitive', 'pact_v2')
MEASUREMENT_FILES = {
    'manifest.json', 'activity_summary.json', 'FF_transition_crosscheck.json',
    'simulation_manifest.json', 'simulate.log', 'topology_verification.json',
    'functional_verification.json', 'export.execution.json', 'extract.execution.json',
    'compile.execution.json', 'simulate.execution.json', 'extract.tcl',
}


def key(path):
    return str(Path(path).resolve())


def checked(item):
    actual = binding(item['path'])
    if actual['sha256'] != item['sha256']:
        raise ValueError('Historical sealed artifact changed: ' + item['path'])
    return actual


def add_expected(catalog, path, digest, origin):
    path = key(path)
    previous = catalog.get(path)
    if previous and previous['sha256'] != digest:
        raise ValueError('Historical seals disagree: ' + path)
    catalog[path] = dict(path=path, sha256=digest,
        origins=sorted(set((previous or {}).get('origins', [])) | {origin}))


def git_expected(path):
    """Use the immutable frozen P0 Git object for legacy sealed roots/receipts."""
    relative = Path(path).relative_to(ROOT).as_posix()
    raw = subprocess.check_output([GIT, 'show', P0 + ':' + relative], cwd=ROOT)
    result = dict(path=key(path), sha256=hashlib.sha256(raw).hexdigest(),
                  immutable_git_commit=P0, repository_relative_path=relative)
    checked(result)
    return result


def environment():
    frozen = read(OUT / 'protocol/tool_versions.json')
    backend = binding('/usr/bin/openroad')
    if backend['sha256'] != frozen['implementation_binary_sha256']:
        raise ValueError('Frozen implementation backend changed')
    version = subprocess.check_output(['/usr/bin/openroad', '-version'], text=True).strip()
    if version != frozen['implementation_openroad_version'].strip():
        raise ValueError('Frozen implementation backend version changed')
    pin = subprocess.check_output(['git', '-C', str(ORFS), 'rev-parse', 'HEAD'], text=True).strip()
    if pin != ORFS_PIN or pin != frozen['ORFS_commit']:
        raise ValueError('Frozen ORFS commit changed')
    # Generated products may be untracked; tracked flow edits would change execution.
    dirty = subprocess.check_output(['git', '-C', str(ORFS), 'diff', 'HEAD', '--name-only'], text=True)
    if dirty.strip():
        raise ValueError('Pinned ORFS has tracked source modifications: ' + dirty.strip())
    return dict(backend=dict(backend, reported_version=version), ORFS_path=str(ORFS),
                ORFS_commit=pin, ORFS_tracked_diff='CLEAN',
                source='Actual executable hash/version and actual ORFS Git state')


def route_policy(report, execution, stdout, expected_version):
    """Evaluate recorded settings, never infer absent NUM_CORES from a default."""
    reasons = []
    command = execution.get('command', [])
    if execution.get('exit_code') != 0 or execution.get('timed_out'):
        reasons.append('ROUTE_EXECUTION_NOT_SUCCESSFUL')
    if 'GRT_SEED=11' not in command:
        reasons.append('ROUTING_SEED_NOT_FROZEN_11')
    if 'OPENROAD_EXE=/usr/bin/openroad' not in command:
        reasons.append('BACKEND_PATH_NOT_FROZEN')
    observed_threads = sorted({int(value) for value in re.findall(r'Using (\d+) thread\(s\)', stdout)})
    if 'NUM_CORES=2' not in command or (observed_threads and observed_threads != [2]):
        reasons.append('THREAD_COUNT_NOT_FROZEN_2')
    first = next((line.strip() for line in stdout.splitlines() if line.startswith('OpenROAD ')), '')
    if first != 'OpenROAD ' + expected_version.strip():
        reasons.append('HISTORICAL_BACKEND_VERSION_NOT_VERIFIED')
    if report.get('status') != 'QUALIFIED' or report.get('DRC_errors') != 0:
        reasons.append('HISTORICAL_ROUTE_NOT_QUALIFIED')
    return dict(eligible=not reasons, reasons=reasons, observed_threads=observed_threads,
                seed_11='GRT_SEED=11' in command,
                explicit_NUM_CORES_2='NUM_CORES=2' in command,
                backend_path='/usr/bin/openroad' if 'OPENROAD_EXE=/usr/bin/openroad' in command else None,
                backend_reported_version=first.removeprefix('OpenROAD '))


def load_catalog():
    catalog, parents = {}, {}
    freeze = read(OUT / 'stage_a/P0_FREEZE.json')
    if freeze['commit'] != P0:
        raise ValueError('Historical P0 freeze differs')
    original_seal = read(OUT / 'stage_a/evidence_manifest.json')
    freeze_binding = next(item for item in original_seal['artifacts'].values()
                          if item['path'] == str(OUT / 'stage_a/P0_FREEZE.json'))
    checked(freeze_binding)
    parents['P0_FREEZE'] = freeze_binding
    groups = [freeze['historical_evidence'], freeze['h8_diagnosis'], *freeze['frozen_inputs'].values()]
    for group in groups:
        for item in group.values():
            add_expected(catalog, item['path'], item['sha256'], 'P0_FREEZE')
    for namespace in NAMESPACES:
        path = ROOT / 'results' / namespace / 'evidence_manifest.json'
        expected = catalog[key(path)]
        checked(expected)
        parents[namespace] = expected
        for relative, item in read(path)['artifacts'].items():
            digest = item if isinstance(item, str) else item['sha256']
            add_expected(catalog, ROOT / relative, digest, str(path))
    h8_path = ROOT / 'results/pact_h8_rootcause/evidence_manifest.json'
    checked(catalog[key(h8_path)])
    parents['h8_source_evidence'] = catalog[key(h8_path)]
    for item in read(h8_path)['source_evidence'].values():
        if isinstance(item, dict) and 'path' in item and 'sha256' in item:
            add_expected(catalog, item['path'], item['sha256'], str(h8_path))
    physical_seal = ROOT / 'reports/physical_effect/evidence_manifest.json'
    parents['physical_effect_P0_git_root'] = git_expected(physical_seal)
    for relative, digest in read(physical_seal)['artifacts'].items():
        add_expected(catalog, ROOT / relative, digest if isinstance(digest, str) else digest['sha256'], str(physical_seal))
    qualification = ROOT / 'artifacts/manifests/phase0c/tool_qualification.json'
    parents['historical_environment_P0_git_root'] = git_expected(qualification)
    qualified = read(qualification)['WSL']
    frozen_tools = read(OUT / 'protocol/tool_versions.json')
    if (qualified['OpenROAD']['binary_sha256'] != frozen_tools['implementation_binary_sha256']
            or qualified['OpenROAD']['version'] != frozen_tools['implementation_openroad_version']
            or qualified['ORFS']['commit'] != ORFS_PIN):
        raise ValueError('Historical qualified environment differs from the fixed backend/ORFS')
    return catalog, parents


def preflight():
    if RECEIPT.exists():
        require_preflight()
        print('EXISTING_REUSE_ELIGIBILITY_PREFLIGHT_PASS', flush=True)
        return
    runtime = environment()
    catalog, parents = load_catalog()
    candidates, verified = {}, {}
    paths = [path for namespace in NAMESPACES for design in DESIGNS
             for path in (ROOT / 'results' / namespace / 'routes' / design).glob('*/route_result.json')]
    paths += [path for design in DESIGNS
              for path in (ROOT / 'artifacts/raw/phase0c/physical' / design / 's11/k2').glob('*/route_metrics.json')]
    for path in sorted(paths):
        if key(path) not in catalog:
            expected = git_expected(path)
            add_expected(catalog, path, expected['sha256'], 'P0_GIT_OBJECT:' + P0)
        checked(catalog[key(path)])
        verified[key(path)] = catalog[key(path)]
        report = read(path)
        exec_path = path.parent / 'route/execution.json'
        stdout_path = path.parent / 'route/stdout.log'
        for evidence in (exec_path, stdout_path):
            if key(evidence) not in catalog:
                item = git_expected(evidence)
                add_expected(catalog, evidence, item['sha256'], 'P0_GIT_OBJECT:' + P0)
            checked(catalog[key(evidence)])
            verified[key(evidence)] = catalog[key(evidence)]
        execution = read(exec_path)
        if report.get('route') is not None and report['route'] != execution:
            raise ValueError('Historical embedded route execution differs: ' + str(path))
        policy = route_policy(report, execution, stdout_path.read_text(), runtime['backend']['reported_version'])
        design = report.get('design')
        if design not in DESIGNS:
            raise ValueError('Historical route design is not frozen: ' + str(path))
        block = 's9234f' if design == 's9234' else design
        source = str(ORFS / 'flow/results/nangate45' / block / 'phase0b_s11_B0/3_place.odb')
        rewire = report.get('rewire', {}).get('command', [])
        if rewire:
            actual_source = rewire[rewire.index('--source') + 1] if '--source' in rewire else None
        else:
            actual_source = report.get('source_placement_odb')
        if actual_source != source:
            raise ValueError('Historical route source placement differs: ' + str(path))
        archive = path.parent / '5_2_route.odb.gz'
        expected_archive = dict(path=str(archive), sha256=report['routed_odb_gzip_sha256'],
            origins=[str(path) + ':routed_odb_gzip_sha256'])
        checked(expected_archive)
        verified[key(archive)] = expected_archive
        candidates[key(path)] = dict(policy, report=catalog[key(path)], execution=catalog[key(exec_path)],
            stdout=catalog[key(stdout_path)], architecture_sha256=report['architecture_sha256'],
            design=design, archive=expected_archive, source_placed_database=source)
    # Compact historical measurements are rooted in the frozen parent seals.
    # Full VCD/input hashes remain checked by the unchanged measurement adapter.
    for path, item in sorted(catalog.items()):
        candidate = Path(path)
        if candidate.name in MEASUREMENT_FILES and ('/measurement/' in path or '/reports/physical_effect/' in path):
            checked(item)
            verified[path] = item
    write(RECEIPT, dict(schema='pact_oss_receiver_reuse_eligibility_v1', status='PASS',
        meaning='Eligibility policy and exact historical bindings verified; exclusions are not qualified reuse',
        environment=runtime, parent_seals=parents, expected_bindings=verified,
        route_candidates=candidates, eligible_route_candidates=sum(c['eligible'] for c in candidates.values()),
        excluded_route_candidates=sum(not c['eligible'] for c in candidates.values()),
        historical_binding_checks=len(verified), source=binding(Path(__file__)),
        cache_exclusions_preserved=True, new_route_runs=0, new_measurement_runs=0,
        policy=dict(GRT_SEED=11, NUM_CORES=2, backend='/usr/bin/openroad', ORFS_commit=ORFS_PIN)))
    print('REUSE_ELIGIBILITY_PREFLIGHT_PASS', len(verified), 'bindings;',
          sum(c['eligible'] for c in candidates.values()), 'eligible;',
          sum(not c['eligible'] for c in candidates.values()), 'excluded', flush=True)


def require_preflight():
    receipt = read(RECEIPT)
    if receipt.get('status') != 'PASS' or receipt.get('schema') != 'pact_oss_receiver_reuse_eligibility_v1':
        raise ValueError('Historical cache eligibility preflight has not passed')
    for item in receipt['parent_seals'].values():
        checked(item)
    checked(receipt['source'])
    backend = receipt['environment']['backend']
    checked(backend)
    return receipt


def checked_cached_binding(path):
    receipt = require_preflight()
    expected = receipt['expected_bindings'].get(key(path))
    if expected is None:
        raise ValueError('Historical artifact is outside the verified preflight: ' + str(path))
    return checked(expected)


def cached_route_eligible(path):
    receipt = require_preflight()
    candidate = receipt['route_candidates'].get(key(path))
    if candidate is None:
        raise ValueError('Historical route is outside the eligibility catalog: ' + str(path))
    for name in ('report', 'execution', 'stdout', 'archive'):
        checked(candidate[name])
    return candidate['eligible']


if __name__ == '__main__':
    preflight()
