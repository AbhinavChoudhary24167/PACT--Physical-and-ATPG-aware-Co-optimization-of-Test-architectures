#!/usr/bin/env python3
"""Implementation-aware synthesis, limited routing and unchanged measurement."""
import argparse
from dataclasses import asdict
import csv
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from pact.optimizer.implementation_v2 import Config, Model, METRICS, optimize, select, order_id, reference
from pact.optimizer.io import read, write_json
from pact.integration.patterns import fan_workload, serialize
from pact.scan.model import ScanArchitecture
from pact.physical.phase0c_port_policy import frozen_def_ports
from pact.phase0d.campaign import file_sha256

DESIGNS = {'s5378': 'P', 's9234': 'T', 's15850': 'P'}


def binding(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=file_sha256(path))


def load(design):
    role = DESIGNS[design]
    old = ROOT/'reports/physical_effect'
    manifest = read(old/'manifest.json')
    entry = next(r for r in manifest['rows'] if r['design'] == design and r['role'] == role)
    paths = dict(architecture=Path(entry['architecture']['path']),
                 caps=old/design/role/'net_activity_capacitance.csv',
                 mapping=old/design/role/'net_mapping.json',
                 manifest=old/'manifest.json', baseline_measurements=old/'comparison.csv',
                 **{k: Path(v['path']) for k, v in entry['inputs'].items()})
    for key in ('architecture', *entry['inputs']):
        expected = entry['architecture'] if key == 'architecture' else entry['inputs'][key]
        if file_sha256(paths[key]) != expected['sha256']:
            raise ValueError('Historical input hash mismatch: '+key)
    arch = ScanArchitecture.from_json(paths['architecture'])
    fan, states = fan_workload(paths['patterns'], read(paths['identity_map'])['records'], arch)
    names = [c.name for c in arch.cells]
    loads = [[s['load_state'][n] for n in names] for s in states]
    responses = [[s['response_state'][n] for n in names] for s in states]
    if any(bit not in ('0', '1') for array in (loads, responses) for row in array for bit in row):
        raise ValueError('Unknown ATPG bits cannot be silently filled')
    caprows = list(csv.DictReader(paths['caps'].open()))
    by_source = {}
    for row in caprows:
        by_source.setdefault(row['source'], []).append(row)
    weights, sources = [], []
    for name in names:
        if name+'/Q' not in by_source:
            raise ValueError('Missing physical FF Q capacitance: '+name)
        rows = by_source[name+'/Q']+by_source.get(name+'/QN', [])
        values = []
        for row in rows:
            pin = float(row['pin_ff'])
            ground = float(row['ground_ff']) if row['ground_ff'] else None
            if not np.isfinite(pin) or pin < 0 or (ground is not None and (not np.isfinite(ground) or ground < 0)):
                raise ValueError('Invalid extracted load')
            values.append(pin+(ground if ground is not None else 0))
        weights.append(sum(values))
        sources.append(dict(FF=name, Ceff_ff=sum(values), nets=[r['net'] for r in rows],
                            source='extracted_ground_plus_pin' if all(r['ground_ff'] for r in rows) else 'pin_fallback'))
    ports, unit = frozen_def_ports(paths['placement'], len(arch.chains))
    inputs = [np.array(ports['test_si'+('_'+str(i) if i else '')])/unit for i in range(len(arch.chains))]
    outputs = [np.array(ports['test_so'+('_'+str(i) if i else '')])/unit for i in range(len(arch.chains))]
    model = Model(arch, np.asarray(loads, np.uint8), np.asarray(responses, np.uint8), weights,
                  read(paths['mapping'])['bounds_um'], inputs, outputs)
    starts = []
    for label in (role, 'J50', 'PACT'):
        row = next(r for r in manifest['rows'] if r['design'] == design and r['role'] == label)
        p = Path(row['architecture']['path'])
        if file_sha256(p) != row['architecture']['sha256']:
            raise ValueError('Baseline changed')
        paths['seed_'+label] = p
        starts.append((label, model.orders(ScanArchitecture.from_json(p))))
    # Include the other physical ordering as a seed, without routing it.
    other = 'T' if role == 'P' else 'P'
    p = ROOT/f'artifacts/derived/phase0c/{design}/s11/k2/{other}.architecture.json'
    paths['seed_'+other] = p
    starts.append((other, model.orders(ScanArchitecture.from_json(p))))
    return model, starts, sources, {k: binding(p) for k, p in paths.items()}


def search(args):
    folder = args.output/args.design
    folder.mkdir(parents=True, exist_ok=True)
    if (folder/'search.json').exists() or (folder/'evaluations.csv').exists():
        raise ValueError('Search evidence exists; use a new --output namespace')
    model, starts, sources, inputs = load(args.design)
    config = Config(seconds=args.seconds, max_evaluations=args.max_evaluations,
                    wire_allowance=args.wire_allowance, timing_allowance=args.timing_allowance, seed=args.seed)
    write_json(folder/'inputs.json', dict(parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        command=sys.argv, config=asdict(config), inputs=inputs,
        versions=dict(python=platform.python_version(), numpy=np.__version__,
                      numba=__import__('numba').__version__, scipy=__import__('scipy').__version__),
        source_code={str(p.relative_to(ROOT)): file_sha256(p) for p in
                     (Path(__file__), ROOT/'src/pact/optimizer/implementation_v2.py', ROOT/'src/pact/optimizer/search.py')},
        FF_count=len(model.names), chain_lengths=list(model.capacities), patterns=len(model.load),
        shift_cycles=2*len(model.load)*model.longest))
    write_json(folder/'weights.json', sources)
    writer = None
    with (folder/'evaluations.csv').open('w', newline='') as f:
        def record(row):
            nonlocal writer
            if writer is None:
                writer = csv.DictWriter(f, fieldnames=list(row))
                writer.writeheader()
            writer.writerow(row)
        result = optimize(model, starts, config, record)
    selected = select(result['archive'], result['baselines'][0]['score'], args.route_limit)
    selected_ids = {order_id(r['orders']): r['roles'] for r in selected}
    def package(row):
        arch = model.architecture_from(row['orders'])
        path = folder/'architectures'/(arch.sha256()+'.json')
        arch.to_json(path)
        oid = order_id(row['orders'])
        return dict(architecture=str(path), architecture_sha256=arch.sha256(), order_id=oid,
                    label=row['label'], metrics=dict(zip(METRICS, map(float, row['score']))),
                    legal=True, chain_lengths=list(model.capacities), new=row.get('new', False),
                    selected_roles=selected_ids.get(oid, []))
    result['archive'] = [package(r) for r in result['archive']]
    result['baselines'] = [package(r) for r in result['baselines']]
    result['selected'] = [r for r in result['archive'] if r['selected_roles']]
    result['config'] = asdict(config)
    write_json(folder/'search.json', result)
    print(args.design, 'NEW', result['new_unique'], 'SELECTED', len(result['selected']), flush=True)


def route(args):
    # Reuse the existing route implementation through its explicit candidate adapter.
    from pact_solver_routes import route_selected
    result = read(args.output/args.design/'search.json')
    selected = [(r['architecture_sha256'][:12], r) for r in result['selected']]
    if not selected:
        raise ValueError('No new feasible nondominated candidate')
    if len(selected) > 3 or any(not r['new'] for _, r in selected):
        raise ValueError('Invalid route selection')
    import fcntl
    output = args.output/'routes'/args.design
    output.mkdir(parents=True, exist_ok=True)
    with (output/'.route.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        route_selected(args.design, selected, output, variant_prefix='pactv2', route_seconds=args.route_seconds)


def measure(args):
    import fcntl
    args.output.mkdir(parents=True, exist_ok=True)
    # One manifest writer/measurement at a time; design routing is independent.
    with (args.output/'.measurement.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _measure(args)


def _measure(args):
    import physical_effect as pe
    measurement = args.output/'measurement'
    measurement.mkdir(parents=True, exist_ok=True)
    pe.OUT = measurement
    os.environ['PACT_PHYSICAL_EFFECT_OUT'] = str(measurement)
    original = read(ROOT/'reports/physical_effect/manifest.json')
    manifest_path = measurement/'manifest.json'
    manifest = read(manifest_path) if manifest_path.exists() else {k: v for k, v in original.items() if k != 'rows'} | {'rows': []}
    result = read(args.output/args.design/'search.json')
    for selected in result['selected']:
        sha = selected['architecture_sha256']
        role = sha[:12]
        evidence = args.output/'routes'/args.design/sha
        report = read(evidence/'route_result.json')
        if report['status'] != 'QUALIFIED':
            continue
        if any(r['design'] == args.design and r['role'] == role for r in manifest['rows']):
            continue
        row = next(r.copy() for r in original['rows'] if r['design'] == args.design and r['role'] == DESIGNS[args.design])
        folder = measurement/args.design/role
        folder.mkdir(parents=True, exist_ok=True)
        arch = ScanArchitecture.from_json(Path(selected['architecture']))
        _, states = fan_workload(Path(row['inputs']['patterns']['path']), read(row['inputs']['identity_map']['path'])['records'], arch)
        workload = dict(architecture_sha256=sha, cycles=max(len(c.cells) for c in arch.chains),
            patterns=[dict(pattern=s['pattern'], source_fields=s['source_fields'], load=serialize(arch, s['load_state']),
                           unload=serialize(arch, s['response_state'], response=True)) for s in states])
        write_json(folder/'workload.json', workload)
        row.update(role=role, architecture=binding(selected['architecture']), architecture_sha256=sha,
                   scan_order_sha256=selected['order_id'], selected_PACT_architecture_sha256=sha,
                   routed_archive=binding(evidence/'5_2_route.odb.gz'), qualification=binding(evidence/'route_result.json'),
                   workload=binding(folder/'workload.json'), PACT_remapped_source=None,
                   chain_lengths=[len(c.cells) for c in arch.chains])
        manifest['rows'].append(row)
    manifest['schema'] = 'pact_v2_physical_effect_v1'
    manifest['base_commit'] = read(args.output/args.design/'inputs.json')['parent_commit']
    manifest['tools'] = {x: subprocess.run([x, '-V' if x == 'iverilog' else '-version'], capture_output=True, text=True).stdout.splitlines()[0]
                         for x in ('iverilog', 'openroad')}
    write_json(args.output/args.design/'measurement_invocation.json', dict(command=sys.argv,
               source_code={str(p.relative_to(ROOT)): file_sha256(p) for p in (
                   Path(__file__), ROOT/'scripts/physical_effect.py', ROOT/'scripts/physical_effect_export.py', ROOT/'src/pact/physical_effect.py')}))
    write_json(manifest_path, manifest)
    pe.execute(args.design, resume=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('search', 'route', 'measure', 'report'))
    p.add_argument('--design', choices=DESIGNS)
    p.add_argument('--output', type=Path, default=ROOT/'results/pact_v2')
    p.add_argument('--seconds', type=float, default=180.)
    p.add_argument('--max-evaluations', type=int, default=100000)
    p.add_argument('--wire-allowance', type=float, default=.10)
    p.add_argument('--timing-allowance', type=float, default=.10)
    p.add_argument('--seed', type=int, default=11)
    p.add_argument('--route-limit', type=int, choices=(1, 2, 3), default=3)
    p.add_argument('--route-seconds', type=float, default=600.)
    args = p.parse_args()
    args.output = args.output.resolve()
    if args.stage == 'report':
        from pact_v2_report import report
        report(args.output)
    else:
        if not args.design:
            p.error('--design is required')
        globals()[args.stage](args)


if __name__ == '__main__':
    main()
