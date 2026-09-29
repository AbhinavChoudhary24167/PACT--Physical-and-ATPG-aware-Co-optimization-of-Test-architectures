#!/usr/bin/env python3
"""Candidate-sensitive extension of PACT-v2; same routing and measurement adapters."""
import argparse
import csv
from dataclasses import asdict
import gzip
import platform
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
import pact_v2 as backend
from pact_v2 import ROOT, DESIGNS, binding, read, write_json, ScanArchitecture
from pact.optimizer import implementation_v2 as v2
from pact.optimizer import candidate_sensitive as cs
from pact.optimizer.candidate_physical import construct


def load(design, out):
    frozen, starts, _, inputs = backend.load(design)
    previous = ROOT/'results/pact_v2'/design/'search.json'
    summary_path = ROOT/'results/pact_v2/summary.json'
    inputs['previous_search'], inputs['previous_summary'] = binding(previous), binding(summary_path)
    old = read(previous)
    measured = {r['architecture_sha256'] for r in read(summary_path)['candidates']
                if r['design'] == design and r['measured'] and r['status'] == 'QUALIFIED'}
    for row in old['selected']:
        if row['architecture_sha256'] not in measured: continue
        arch = ScanArchitecture.from_json(Path(row['architecture']))
        if arch.sha256() != row['architecture_sha256']: raise ValueError('Changed v2 seed')
        label = 'v2_'+arch.sha256()[:12]
        starts.append((label, frozen.orders(arch)))
        inputs['seed_'+label] = binding(row['architecture'])
    graph_path = out/design/'topology.json'
    graph = read(graph_path)
    for value in graph['inputs'].values():
        if binding(value['path'])['sha256'] != value['sha256']: raise ValueError('Changed physical input')
    inputs['topology'] = binding(graph_path)
    inputs.update({'physical_'+k: v for k, v in graph['inputs'].items()})
    caprows = list(csv.DictReader(Path(inputs['caps']['path']).open()))
    physical = construct(frozen, graph, caprows)
    return cs.Model(frozen, physical, graph['bounds']), starts, physical, inputs, measured


def search(args):
    folder = args.output/args.design
    folder.mkdir(parents=True, exist_ok=True)
    if (folder/'search.json').exists() or (folder/'evaluations.csv').exists():
        raise ValueError('Existing search evidence; use a new output namespace')
    began = time.perf_counter()
    model, starts, physical, inputs, measured = load(args.design, args.output)
    setup = time.perf_counter()-began
    config = v2.Config(seconds=args.seconds, max_evaluations=args.max_evaluations,
        seed=args.seed, wire_allowance=args.wire_allowance, timing_allowance=args.timing_allowance)
    source_paths = [Path(__file__), ROOT/'scripts/pact_candidate_export.py',
        ROOT/'src/pact/optimizer/candidate_sensitive.py', ROOT/'src/pact/optimizer/candidate_physical.py',
        ROOT/'src/pact/optimizer/implementation_v2.py', ROOT/'src/pact/optimizer/search.py',
        ROOT/'scripts/pact_v2.py', ROOT/'src/pact/integration/patterns.py']
    write_json(folder/'inputs.json', dict(parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        command=sys.argv, config=asdict(config), inputs=inputs,
        versions=dict(python=platform.python_version(), numpy=np.__version__, numba=__import__('numba').__version__,
                      scipy=__import__('scipy').__version__),
        source_code={str(p.relative_to(ROOT)): binding(p)['sha256'] for p in source_paths},
        FF_count=len(model.names), chain_lengths=list(model.capacities), patterns=len(model.load),
        shift_cycles=2*len(model.load)*model.longest, model_setup_seconds=setup))
    write_json(folder/'physical_model.json', physical)
    writer = None
    with (folder/'evaluations.csv').open('w', newline='') as f:
        def record(row):
            nonlocal writer
            row = {dict(zip(v2.METRICS, cs.METRICS)).get(k, k): v for k, v in row.items()}
            if writer is None:
                writer = csv.DictWriter(f, fieldnames=list(row)); writer.writeheader()
            writer.writerow(row)
        result = v2.optimize(model, starts, config, record, state_type=cs.State,
                             reference_evaluator=cs.reference, verify_interval=2000, profile=model.profile)
    baselines = [r for r in result['baselines'] if model.architecture_from(r['orders']).sha256() in measured]
    selected = cs.select(result['archive'], baselines, args.route_limit)
    chosen = {v2.order_id(r['orders']): r['roles'] for r in selected}
    def package(row):
        arch = model.architecture_from(row['orders'])
        path = folder/'architectures'/(arch.sha256()+'.json')
        arch.to_json(path)
        frozen = v2.reference(model.frozen, row['orders'])
        source_local = cs.reference(model, row['orders'], source_local=True)
        return dict(architecture=str(path), architecture_sha256=arch.sha256(), order_id=v2.order_id(row['orders']),
            label=row['label'], metrics=dict(zip(cs.METRICS, map(float, row['score']))),
            frozen_metrics=dict(zip(v2.METRICS, map(float, frozen))), source_local_H8_ff=float(source_local[2]),
            source_local_H4_ff=float(source_local[4]), new=row.get('new', False),
            selected_roles=chosen.get(v2.order_id(row['orders']), []), legal=True)
    result['archive'] = [package(r) for r in result['archive']]
    result['baselines'] = [package(r) for r in result['baselines']]
    result['selected'] = [r for r in result['archive'] if r['selected_roles']]
    result.update(config=asdict(config), profile=model.profile, model_setup_seconds=setup,
        peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        evaluations_per_second=result['evaluations']/result['search_seconds'],
        milliseconds_per_evaluation=1000*result['search_seconds']/result['evaluations'],
        total_seconds=time.perf_counter()-began,
        selection_rule='new predicted nondominance against all stored measured architectures; prioritize dominance improvements')
    write_json(folder/'search.json', result)
    with (folder/'evaluations.csv').open('rb') as src, gzip.GzipFile(filename=str(folder/'evaluations.csv.gz'), mode='wb', mtime=0) as dst:
        shutil.copyfileobj(src, dst)
    print(args.design, 'NEW', result['new_unique'], 'SELECTED', len(result['selected']), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('export', 'search', 'route', 'measure', 'report'))
    p.add_argument('--design', choices=DESIGNS)
    p.add_argument('--output', type=Path, default=ROOT/'results/pact_candidate_sensitive')
    p.add_argument('--seconds', type=float, default=180.)
    p.add_argument('--max-evaluations', type=int, default=20000)
    p.add_argument('--wire-allowance', type=float, default=.10)
    p.add_argument('--timing-allowance', type=float, default=.10)
    p.add_argument('--seed', type=int, default=11)
    p.add_argument('--route-limit', type=int, choices=(1, 2, 3), default=3)
    p.add_argument('--route-seconds', type=float, default=600.)
    args = p.parse_args()
    args.output = args.output.resolve()
    if args.stage == 'report':
        from pact_candidate_report import report
        report(args.output)
    elif not args.design:
        p.error('--design required')
    elif args.stage == 'export':
        target = args.output/args.design/'topology.json'
        if target.exists(): raise ValueError('Topology export exists')
        target.parent.mkdir(parents=True, exist_ok=True)
        cmd = ['openroad', '-python', '-no_init', '-exit', str(ROOT/'scripts/pact_candidate_export.py'), args.design, str(target)]
        tick = time.perf_counter()
        with (target.parent/'topology.log').open('w') as f:
            proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
        write_json(target.parent/'topology.execution.json', dict(command=cmd, returncode=proc.returncode,
            seconds=time.perf_counter()-tick, source=binding(ROOT/'scripts/pact_candidate_export.py')))
        if proc.returncode: raise RuntimeError('Topology export failed')
    elif args.stage == 'search': search(args)
    elif args.stage == 'route':
        # Keep the adapter's explicit new-only limit and namespace-local outputs.
        backend.route(args)
    elif args.stage == 'measure': backend.measure(args)


if __name__ == '__main__': main()
