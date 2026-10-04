#!/usr/bin/env python3
"""Resume the unchanged Stage-A protocol after both external generators qualify.

P0 search/selection/model and B0/B1 generation are never rerun here. Heavy new
implementation data lives on D:. The common route/measurement code is reused.
"""
import argparse
import csv
from pathlib import Path
import os
import shutil

from pact_oss_benchmark import ROOT, OUT, DESIGNS, binding, read, verify, write
from pact_oss_recovery import RECOVERY, TEMP
from pact_oss_canonicalize import csv_write, validate_architecture
from pact.scan.model import ScanArchitecture
from pact.physical.phase0c_port_policy import frozen_def_ports

STAGE = RECOVERY / 'stage_a'
RAW = TEMP / 'recovery_20261003/stage_a'


def gate():
    from pact_oss_storage import ensure
    ensure()
    verify()
    contract = read(OUT / 'protocol/benchmark_contract.json')
    if binding('/usr/bin/openroad')['sha256'] != read(OUT / 'protocol/tool_versions.json')['implementation_binary_sha256']:
        raise ValueError('Common implementation backend changed')
    for name in ('B2_openroad_10176', 'B3_openroad_10666'):
        qualification = read(RECOVERY / 'baselines' / name / 'qualification.json')
        pin = read(OUT / 'baselines' / name / 'source_pin.json')
        if qualification['status'] != 'PASS' or qualification['source_commit'] != pin['commit'] or set(qualification['designs']) != set(DESIGNS):
            raise ValueError('Mandatory pinned external generator qualification has not passed: ' + name)
        build = read(RECOVERY / 'baselines' / name / 'build_result.json')
        if build['status'] != 'BUILT' or build['binary_sha256'] != qualification['binary_sha256']:
            raise ValueError('Qualified generator does not match its exact build')
        for design, item in qualification['designs'].items():
            if binding(item['canonical']['path'])['sha256'] != item['canonical']['sha256']:
                raise ValueError('Qualified external architecture changed')
    receipt = STAGE / 'selection_receipt.json'
    if receipt.exists():
        for key in ('architecture_index', 'architecture_manifest', 'pre_route_metrics', 'original_selection', 'original_policy'):
            item = read(receipt)[key]
            if binding(item['path'])['sha256'] != item['sha256']:
                raise ValueError('Pre-implementation identity/selection evidence changed: ' + key)
    return contract


def prepare():
    gate()
    rows = list(csv.DictReader((OUT / 'stage_a/architecture_index.csv').open()))
    frozen = read(OUT / 'stage_a/P0_FREEZE.json')
    for method, name in (('B2', 'B2_openroad_10176'), ('B3', 'B3_openroad_10666')):
        qualification = read(RECOVERY / 'baselines' / name / 'qualification.json')
        for design in DESIGNS:
            item = qualification['designs'][design]
            path = Path(item['canonical']['path'])
            architecture = ScanArchitecture.from_json(path)
            rows.append(dict(design=design, method=method, architecture_hash=architecture.sha256(), architecture_path=str(path),
                roles='single_solution', selected='True', representative='True', status='CANONICAL_QUALIFIED',
                FF_count=len(architecture.cells), K=2, predicted_E='', predicted_H8='', predicted_H4=''))
    manifest, diagnostics = [], []
    for row in rows:
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
    csv_write(STAGE / 'architecture_index.csv', list(rows[0]), rows)
    csv_write(STAGE / 'architecture_manifest.csv', list(manifest[0]), manifest)
    csv_write(STAGE / 'pre_route_metrics.csv', list(diagnostics[0]), diagnostics)
    write(STAGE / 'selection_receipt.json', dict(original_selection=binding(OUT / 'stage_a/P0_SELECTION.json'),
        architecture_index=binding(STAGE / 'architecture_index.csv'), architecture_manifest=binding(STAGE / 'architecture_manifest.csv'),
        pre_route_metrics=binding(STAGE / 'pre_route_metrics.csv'),
        original_policy=binding(OUT / 'protocol/architecture_policy.md'), original_canonical_index=binding(OUT / 'stage_a/architecture_index.csv'),
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
        archive = path.parent / '5_2_route.odb.gz'
        if not archive.exists() or binding(archive)['sha256'] != report['routed_odb_gzip_sha256']:
            continue
        return dict(report=report, report_binding=binding(path), archive=binding(archive), reused=True)
    return None


def route(design):
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
    result = route_selected(design, pending, output, variant_prefix='oss_stagea_s11', route_seconds=600)
    for report in result:
        sha = report['architecture_sha256']
        path = output / sha / 'route_result.json'
        archive = output / sha / '5_2_route.odb.gz'
        if not path.exists():
            write(path, report)
        records[sha] = dict(report=report, report_binding=binding(path), archive=binding(archive) if archive.exists() else None, reused=False)
    write(STAGE / 'routes' / (design+'.json'), dict(design=design, records=records,
        common_route_adapter=binding(ROOT / 'scripts/pact_solver_routes.py'),
        rewiring_adapter=binding(ROOT / 'scripts/phase0c_rewire_odb.py'),
        input_backend=binding('/usr/bin/openroad'),
        new_route_attempts=len(pending), qualified_new_routes=sum(r['status']=='QUALIFIED' for r in result)))
    print('STAGE_A_ROUTES_RECORDED', design, 'new', len(pending), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare','route'))
    parser.add_argument('--design', choices=DESIGNS)
    args = parser.parse_args()
    os.environ.setdefault('PACT_BENCHMARK_GIT', 'git')
    if args.action=='prepare': prepare()
    elif args.design: route(args.design)
    else: parser.error('--design is required')
