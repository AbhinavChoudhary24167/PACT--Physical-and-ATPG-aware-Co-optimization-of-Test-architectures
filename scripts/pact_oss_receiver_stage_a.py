#!/usr/bin/env python3
"""Additive Stage-A continuation with exact B2 and minimally repaired B3R.

P0 search/selection/model and B0/B1 generation are never rerun here. Heavy new
implementation data lives on D:. The common route/measurement code is reused.
"""
import argparse
import csv
from pathlib import Path
import os
import shutil
import hashlib
from contextlib import contextmanager

from pact_oss_benchmark import ROOT, OUT, DESIGNS, binding, read, verify, write
from pact_oss_recovery import TEMP, MOUNT
from pact_oss_canonicalize import csv_write, validate_architecture
from pact.scan.model import ScanArchitecture
from pact.physical.phase0c_port_policy import frozen_def_ports

RECOVERY = OUT / 'receiver_recovery_20261003'
PREVIOUS = OUT / 'recovery_20261003'
DATA = TEMP / 'receiver_recovery_20261003'
STAGE = RECOVERY / 'stage_a'
RAW = DATA / 'stage_a'
REPAIRED_FILE = 'src/dft/src/cells/OneBitScanCell.cpp'
BASELINES = {
    'B2': dict(name='B2_openroad_10176', folder=PREVIOUS / 'baselines/B2_openroad_10176',
               upstream_base_sha='6fff875551fe13a2aae3a22f871a6ca7f8d5c1cf', repaired=False),
    'B3R': dict(name='B3R_openroad_10666_repaired', folder=RECOVERY / 'baselines/B3R_openroad_10666_repaired',
                upstream_base_sha='746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656', repaired=True),
}
METHODS = {'B0', 'B1', 'B2', 'B3R', 'P0'}
B3R_DISPLAY = 'B3R — PR #10666 + minimal compile repair'


def method_display(method):
    return B3R_DISPLAY if method=='B3R' else method


def checked(item):
    actual = binding(item['path'])
    if actual['sha256'] != item['sha256']:
        raise ValueError('Evidence changed: ' + item['path'])
    return actual


@contextmanager
def exclusive(folder, label):
    """Prevent duplicate invocation of an output namespace while work is active."""
    import fcntl
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / ('.' + label + '.lock')).open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('An active ' + label + ' invocation owns this namespace') from error
        yield


def receiver_correction(original, formatted=False):
    """The sole authorized semantic edit, verified independently of a diff label."""
    corrected = original
    for member in ('getLibertyScanIn', 'getLibertyScanOut'):
        before = ('findITerm(' + member + '(test_cell_)), inst_)').encode()
        separator = ',\n                       ' if formatted else ', '
        after = ('findITerm(db_network_->' + member + '(test_cell_))' + separator + 'inst_)').encode()
        if corrected.count(before) != 1:
            raise ValueError('Pinned receiver diagnosis does not match source: ' + member)
        corrected = corrected.replace(before, after)
    return corrected


def validate_repair(source, manifest, original_hashes, original_source):
    if manifest['upstream_base_sha'] != BASELINES['B3R']['upstream_base_sha']:
        raise ValueError('B3R repair parent differs from exact pinned B3')
    if set(manifest['changed_files']) != {REPAIRED_FILE}:
        raise ValueError('Repair includes an unauthorized changed file')
    patch = manifest.get('patch', dict(path=str(BASELINES['B3R']['folder'] / 'repair/patch.diff'), sha256=manifest['patch_sha256']))
    if checked(patch)['sha256'] != manifest['patch_sha256']:
        raise ValueError('Repair patch identity differs')
    if not manifest['repair_commit_sha'] or manifest['repair_commit_sha'] == manifest['upstream_base_sha']:
        raise ValueError('Repaired derivative must have its own immutable commit')
    original = original_source.read_bytes()
    if hashlib.sha256(original).hexdigest() != original_hashes[REPAIRED_FILE]:
        raise ValueError('Sealed pinned source diagnostic changed')
    actual_source = (source / REPAIRED_FILE).read_bytes()
    allowed = (receiver_correction(original), receiver_correction(original, formatted=True))
    if actual_source not in allowed:
        raise ValueError('B3R source differs from the exact two receiver qualifications and their targeted formatting')
    expected = actual_source
    for relative, digest in original_hashes.items():
        path = source / relative
        actual = hashlib.sha256(os.readlink(path).encode()).hexdigest() if path.is_symlink() else binding(path)['sha256']
        wanted = hashlib.sha256(expected).hexdigest() if relative == REPAIRED_FILE else digest
        if actual != wanted:
            raise ValueError('B3R has an additional pinned source change: ' + relative)
    changes = manifest['changed_source_sha256']
    if set(changes) != {REPAIRED_FILE} or changes[REPAIRED_FILE] != hashlib.sha256(expected).hexdigest():
        raise ValueError('Repaired source hash differs from repair manifest')


def validate_baseline(method, spec):
    folder = spec['folder']
    qualification = read(folder / 'qualification.json')
    build = read(folder / 'build_result.json')
    if qualification['status'] != 'PASS' or qualification['method'] != method or set(qualification['designs']) != set(DESIGNS):
        raise ValueError('Mandatory generator has not qualified all frozen designs: ' + method)
    if build['status'] != 'BUILT' or build['binary_sha256'] != qualification['binary_sha256']:
        raise ValueError('Qualified generator does not match its build: ' + method)
    if checked(build['binary'])['sha256'] != build['binary_sha256'] or build['commit'] != qualification['source_commit']:
        raise ValueError('Generator binary/source identity differs: ' + method)
    source = Path(build['binary']['path']).parents[2] / 'source'
    if spec['repaired']:
        repair = read(folder / 'repair/repair_manifest.json')
        original = PREVIOUS / 'baselines/B3_openroad_10666'
        original_hashes = read(original / 'source_manifest.json')['pinned_source_blobs_checked']
        validate_repair(source, repair, original_hashes, original / 'diagnostics' / REPAIRED_FILE)
        identities = (build['upstream_base_sha'], qualification['upstream_base_sha'], repair['upstream_base_sha'])
        if set(identities) != {spec['upstream_base_sha']} or build['commit'] != repair['repair_commit_sha']:
            raise ValueError('B3R repair/base identities disagree')
        source_manifest = read(folder / 'source_manifest.json')
        if source_manifest['upstream_base_sha'] != spec['upstream_base_sha'] or source_manifest['repair_commit_sha'] != build['commit'] or source_manifest['patch_sha256'] != repair['patch_sha256']:
            raise ValueError('B3R source manifest differs from the committed repair')
    else:
        if build['commit'] != spec['upstream_base_sha']:
            raise ValueError('Exact B2 source revision changed')
        source_manifest = read(folder / 'source_manifest.json')
        if source_manifest['source_modifications']:
            raise ValueError('Exact B2 source was modified')
        for relative, digest in source_manifest['pinned_source_blobs_checked'].items():
            path = source / relative
            actual = hashlib.sha256(os.readlink(path).encode()).hexdigest() if path.is_symlink() else binding(path)['sha256']
            if actual != digest:
                raise ValueError('Exact B2 source changed: ' + relative)
    for key in ('build', 'configuration', 'source_manifest'):
        if isinstance(build.get(key), dict) and 'path' in build[key]:
            checked(build[key])
    checked(qualification['compiled_behavior'])
    behavior = read(qualification['compiled_behavior']['path'])
    if behavior['status'] != 'PASS' or behavior['binary_sha256'] != build['binary_sha256'] or behavior['source_commit'] != build['commit']:
        raise ValueError('Compiled command probe identity differs: ' + method)
    for design, item in qualification['designs'].items():
        checked(item['canonical'])
        checked(item['proof'])
        proof = read(item['proof']['path'])
        architecture = ScanArchitecture.from_json(Path(item['canonical']['path']))
        reference = ScanArchitecture.from_json(Path(read(OUT / 'stage_a/P0_FREEZE.json')['frozen_inputs'][design]['B0_reference']['path']))
        validate_architecture(architecture, reference)
        if proof['status'] != 'PASS' or proof['binary_sha256'] != build['binary_sha256'] or proof['source_commit'] != build['commit'] or not proof['endpoint_geometry_unchanged']:
            raise ValueError('Generator runtime qualification differs: ' + method)
        if architecture.sha256() != item['architecture_hash'] or architecture.sha256() != proof['canonical_architecture_hash']:
            raise ValueError('Qualified generator canonical identity differs')
    return qualification


def gate():
    from pact_oss_storage import ensure
    ensure()
    from pact_oss_verify import audit as original_audit
    original_audit()
    contract = read(OUT / 'protocol/benchmark_contract.json')
    if binding('/usr/bin/openroad')['sha256'] != read(OUT / 'protocol/tool_versions.json')['implementation_binary_sha256']:
        raise ValueError('Common implementation backend changed')
    for method, spec in BASELINES.items():
        validate_baseline(method, spec)
    receipt = STAGE / 'selection_receipt.json'
    if receipt.exists():
        for key in ('architecture_index', 'architecture_manifest', 'pre_route_metrics', 'original_selection', 'original_policy', 'original_canonical_index', 'reuse_preflight'):
            item = read(receipt)[key]
            if binding(item['path'])['sha256'] != item['sha256']:
                raise ValueError('Pre-implementation identity/selection evidence changed: ' + key)
    return contract


def prepare():
    gate()
    from pact_oss_receiver_reuse_preflight import require_preflight
    require_preflight()
    rows = list(csv.DictReader((OUT / 'stage_a/architecture_index.csv').open()))
    frozen = read(OUT / 'stage_a/P0_FREEZE.json')
    for method, spec in BASELINES.items():
        qualification = read(spec['folder'] / 'qualification.json')
        for design in DESIGNS:
            item = qualification['designs'][design]
            path = Path(item['canonical']['path'])
            architecture = ScanArchitecture.from_json(path)
            rows.append(dict(design=design, method=method, architecture_hash=architecture.sha256(), architecture_path=str(path),
                roles='single_solution', selected='True', representative='True', status='CANONICAL_QUALIFIED',
                FF_count=len(architecture.cells), K=2, predicted_E='', predicted_H8='', predicted_H4=''))
    manifest, diagnostics = [], []
    for row in rows:
        row['method_display'] = method_display(row['method'])
        design = row['design']
        inputs = frozen['frozen_inputs'][design]
        architecture = ScanArchitecture.from_json(Path(row['architecture_path']))
        reference = ScanArchitecture.from_json(Path(inputs['B0_reference']['path']))
        validate_architecture(architecture, reference)
        if architecture.sha256() != row['architecture_hash']:
            raise ValueError('Architecture identity changed after selection/qualification')
        ports, unit = frozen_def_ports(Path(inputs['placement']['path']), 2)
        xy = {cell.name: (cell.x_um, cell.y_um) for cell in architecture.cells}
        wire, endpoints = 0., 0.
        for chain in architecture.chains:
            wire += sum(abs(xy[a][0]-xy[b][0])+abs(xy[a][1]-xy[b][1]) for a,b in zip(chain.cells,chain.cells[1:]))
            si = 'test_si' if chain.scan_in == 'test_si_0' else chain.scan_in
            so = 'test_so' if chain.scan_out == 'test_so_0' else chain.scan_out
            endpoints += sum(abs(xy[chain.cells[0]][axis]-ports[si][axis]/unit)+abs(xy[chain.cells[-1]][axis]-ports[so][axis]/unit) for axis in (0,1))
            for index, ff in enumerate(chain.cells):
                manifest.append(dict(row, chain_id=chain.chain_id, chain_index=index, ordered_ff_identity=ff,
                                     scan_in=chain.scan_in, scan_out=chain.scan_out, chain_length=len(chain.cells)))
        lengths = [len(chain.cells) for chain in architecture.chains]
        diagnostics.append(dict(row, scan_hpwl_um=wire, port_inclusive_scan_hpwl_um=wire+endpoints,
                                maximum_chain_length=max(lengths), minimum_chain_length=min(lengths), chain_imbalance=max(lengths)-min(lengths),
                                estimated_scan_path_length_um=wire+endpoints))
    if len(rows) != 30 or len(manifest) != 9176 or sum(r['selected']=='True' for r in rows) != 19:
        raise ValueError('Frozen extended architecture inventory differs')
    csv_write(STAGE / 'architecture_index.csv', list(rows[0]), rows)
    csv_write(STAGE / 'architecture_manifest.csv', list(manifest[0]), manifest)
    csv_write(STAGE / 'pre_route_metrics.csv', list(diagnostics[0]), diagnostics)
    write(STAGE / 'selection_receipt.json', dict(original_selection=binding(OUT / 'stage_a/P0_SELECTION.json'),
        architecture_index=binding(STAGE / 'architecture_index.csv'), architecture_manifest=binding(STAGE / 'architecture_manifest.csv'),
        pre_route_metrics=binding(STAGE / 'pre_route_metrics.csv'),
        original_policy=binding(OUT / 'protocol/architecture_policy.md'), original_canonical_index=binding(OUT / 'stage_a/architecture_index.csv'),
        reuse_preflight=binding(RECOVERY / 'reuse_preflight/eligibility.json'),
        canonical_architectures=len(rows), selected_P0=sum(r['method']=='P0' and r['selected']=='True' for r in rows),
        selected_method_records=sum(r['selected']=='True' for r in rows), new_search_runs=0,
        policy='Reuse exact sealed roles; no selection using any implemented outcome',
        new_physical_implementations_before_selection=0))
    print('STAGE_A_CANONICAL_PREPARATION_PASS', len(rows), flush=True)


def old_route(design, sha):
    candidates = []
    for namespace in ('pact_candidate_stateful', 'pact_candidate_sensitive', 'pact_v2'):
        path = ROOT / 'results' / namespace / 'routes' / design / sha / 'route_result.json'
        if path.exists():
            candidates.append(path)
    for path in (ROOT / f'artifacts/raw/phase0c/physical/{design}/s11/k2').glob('*/route_metrics.json'):
        if read(path).get('architecture_sha256') == sha:
            candidates.append(path)
    for path in candidates:
        report = read(path)
        if report.get('architecture_sha256') != sha or report.get('status') != 'QUALIFIED':
            continue
        from pact_oss_receiver_reuse_preflight import cached_route_eligible
        if not cached_route_eligible(path):
            continue
        archive = path.parent / '5_2_route.odb.gz'
        if not archive.exists() or binding(archive)['sha256'] != report['routed_odb_gzip_sha256']:
            continue
        return dict(report=report, report_binding=binding(path), archive=binding(archive), reused=True)
    return None


def route_unlocked(design):
    gate()
    os.environ['PATH'] = '/usr/bin:' + os.environ['PATH']
    if shutil.which('openroad') != '/usr/bin/openroad':
        raise ValueError('Common rewiring/verification backend does not resolve to /usr/bin/openroad')
    from pact_solver_routes import route_selected
    rows = [row for row in csv.DictReader((STAGE / 'architecture_index.csv').open()) if row['design']==design]
    records, pending = {}, []
    for row in rows:
        sha = row['architecture_hash']
        reused = old_route(design, sha)
        if reused:
            records[sha] = reused
        elif row['selected']=='True' and sha not in {r[1]['architecture_sha256'] for r in pending}:
            pending.append((row['method']+'_'+sha[:12], dict(architecture_sha256=sha, architecture=row['architecture_path'], metrics={})))
    output = RAW / 'routes' / design
    output.mkdir(parents=True, exist_ok=True)
    prior_attempts = {sha for _, item in pending if (output / (sha := item['architecture_sha256']) / 'attempt.json').exists()}
    result = route_selected(design, pending, output, variant_prefix='oss_receiver_s11', route_seconds=600)
    for report in result:
        sha = report['architecture_sha256']
        path = output / sha / 'route_result.json'
        archive = output / sha / '5_2_route.odb.gz'
        if not path.exists():
            write(path, report)
        records[sha] = dict(report=report, report_binding=binding(path), archive=binding(archive) if archive.exists() else None,
                            reused=False, attempt_started_this_invocation=sha not in prior_attempts)
    write(STAGE / 'routes' / (design+'.json'), dict(design=design, records=records,
        common_route_adapter=binding(ROOT / 'scripts/pact_solver_routes.py'),
        rewiring_adapter=binding(ROOT / 'scripts/phase0c_rewire_odb.py'),
        input_backend=binding('/usr/bin/openroad'),
        new_route_attempts=len(pending)-len(prior_attempts),
        qualified_new_routes=sum(r['status']=='QUALIFIED' and r['architecture_sha256'] not in prior_attempts for r in result),
        previous_attempts_recovered=len(prior_attempts)))
    print('STAGE_A_ROUTES_RECORDED', design, 'new', len(pending)-len(prior_attempts), flush=True)


def route(design):
    with exclusive(RAW / 'routes' / design, 'route'):
        return route_unlocked(design)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare','route'))
    parser.add_argument('--design', choices=DESIGNS)
    args = parser.parse_args()
    os.environ.setdefault('PACT_BENCHMARK_GIT', 'git')
    if args.action=='prepare': prepare()
    elif args.design: route(args.design)
    else: parser.error('--design is required')
