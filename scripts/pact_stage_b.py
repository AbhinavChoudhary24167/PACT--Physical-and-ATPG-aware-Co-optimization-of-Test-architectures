#!/usr/bin/env python3
"""Stage-B constrained method campaign; preserve frozen Stage-A evidence."""
import argparse
import csv
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from pact.optimizer import stage_b as solver
from pact.optimizer import candidate_stateful as sf
from pact.optimizer.io import read, write_json
from pact.scan.model import ScanArchitecture
from pact.experiment_storage import configure_experiment_storage, guard_disk_space
from pact.integration.patterns import fan_workload
from pact_v2 import binding

DESIGNS = ('s5378', 's9234', 's15850')
FROZEN = ROOT/'results/pact_oss_benchmark/topology_recovery_20261004'
STAGE_A = FROZEN/'stage_a'
METRICS = ('wire_um', 'E_stateful_ff', 'H8_stateful_ff', 'timing_max_edge_um', 'H4_stateful_ff')


class Model(sf.Model):
    def validate(self, orders):
        # B3T retains reversed chain capacities on s9234. Preserve its exact
        # ordered lengths; every mutation still conserves each starting chain.
        if sorted(map(len, orders)) != sorted(self.capacities) or not np.array_equal(
                np.sort(np.concatenate(orders)), np.arange(len(self.names))):
            raise ValueError('Changed capacity multiset or FF bijection')
        if any(len(set(self.domains[o])) != 1 for o in orders):
            raise ValueError('Mixed clock domains')


def gate():
    checkpoint = read(FROZEN/'completion.json')
    if checkpoint['status'] != 'PACT_STAGE_A_PHYSICAL_RESULTS_COMPLETE':
        raise ValueError('Stage A is incomplete')
    if binding(STAGE_A/'implemented_metrics.csv')['sha256'] != checkpoint['metrics']['sha256']:
        raise ValueError('Frozen Stage-A metrics changed')
    backend = read(ROOT/'results/pact_oss_benchmark/protocol/tool_versions.json')
    if binding('/usr/bin/openroad')['sha256'] != backend['implementation_binary_sha256']:
        raise ValueError('Frozen physical backend changed')


def load(design):
    import pact_candidate_sensitive as prior
    sensitive, _, _, inputs, _ = prior.load(design, ROOT/'results/pact_candidate_sensitive')
    graph = read(ROOT/'results/pact_candidate_sensitive'/design/'topology.json')
    caprows = list(csv.DictReader(Path(inputs['caps']['path']).open()))
    fan, states = fan_workload(Path(inputs['patterns']['path']), read(inputs['identity_map']['path'])['records'], sensitive.architecture)
    primary = {pin: np.array([int(s['source_fields']['pi1'][i]) for s in states], np.uint8)
               for i, pin in enumerate(fan.primary_inputs)}
    model = Model(sensitive, graph, caprows, primary, depth=3)
    measured = [r for r in csv.DictReader((STAGE_A/'implemented_metrics.csv').open())
                if r['design'] == design and (r['method'] in ('B2', 'B3T') or
                    (r['method'] == 'P0' and r['representative'] == 'True'))]
    reference = min((r for r in measured if r['method'] in ('B2', 'B3T')),
                    key=lambda r: float(r['routed_scan_path_cost_um']))
    measured.sort(key=lambda r: (r['method'] != reference['method'], r['method']))
    starts = []
    for row in measured:
        arch = ScanArchitecture.from_json(Path(row['architecture_path']))
        if arch.sha256() != row['architecture_hash']:
            raise ValueError('Frozen reference architecture changed')
        starts.append((row['method'], model.orders(arch)))
        inputs['Stage_A_'+row['method']] = binding(row['architecture_path'])
    return model, starts, inputs, reference


def search(args):
    gate()
    folder = args.output/args.design
    folder.mkdir(parents=True, exist_ok=True)
    model, starts, inputs, reference = load(args.design)
    for epsilon in args.epsilons:
        out = folder/f'budget_{epsilon:.2f}'
        if (out/'search.json').exists():
            print(args.design, epsilon, 'SAVED_SEARCH_REUSED', flush=True)
            continue
        config = solver.Config(epsilon=epsilon, seconds=args.seconds, max_evaluations=args.max_evaluations,
            stagnation_attempts=args.stagnation_attempts, weights=tuple(args.weights))
        out.mkdir(parents=True, exist_ok=True)
        write_json(out/'inputs.json', dict(source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            source_files={p: binding(ROOT/p) for p in ('src/pact/optimizer/stage_b.py', 'scripts/pact_stage_b.py')},
            config=asdict(config), inputs=inputs, physical_reference=reference,
            model=model.metadata, seed=11, fixed_capacity_multiset=list(model.capacities),
            normalization='sum(w_i * metric_i/reference_i)/sum(w_i); metrics E,H4,H8',
            budget_semantics='Port-inclusive scan HPWL relative to routed-best B2/B3T architecture; routed cost checked separately'))
        def progress(row):
            write_json(out/'progress.json', row)
            print(args.design, epsilon, 'PROGRESS', round(row['seconds'], 1), 's', row['evaluations'], 'evaluations',
                  row['screened_infeasible'], 'screened', row['accepted'], 'accepted', flush=True)
        result = solver.optimize(model, starts, reference['method'], config, checkpoint=progress)
        def package(row):
            arch = model.architecture_from(row['orders'])
            path = out/'architectures'/(arch.sha256()+'.json')
            path.parent.mkdir(parents=True, exist_ok=True)
            arch.to_json(path)
            parent_arch = model.architecture_from(next(o for label, o in starts if label == row['parent']))
            return {k: v for k, v in row.items() if k not in ('orders', 'score')} | dict(
                architecture=str(path), architecture_sha256=arch.sha256(), parent_architecture_sha256=parent_arch.sha256(),
                chain_sizes=list(map(len, row['orders'])), metrics=dict(zip(METRICS, map(float, row['score']))))
        result['selected'] = [package(r) for r in result['selected']]
        result['baselines'] = [package(r) for r in result['baselines']]
        result['reference_score'] = result['reference_score'].tolist()
        result.update(config=asdict(config), physical_reference=reference, model_profile=model.profile.copy())
        write_json(out/'search.json', result)
        print(args.design, epsilon, 'SEARCH_COMPLETE', result['evaluations'], 'evaluations',
              result['accepted'], 'accepted', len(result['selected']), 'distinct winners', flush=True)


def selection(args):
    """Pre-route small set: balanced, E, then H4/H8; deduplicate across budgets."""
    rows = []
    for path in sorted((args.output/args.design).glob('budget_*/search.json')):
        data = read(path)
        reference = np.array(data['reference_score'])
        for row in data['selected']:
            if row['new']:
                score = np.array([row['metrics'][m] for m in METRICS])
                rows.append(dict(row, epsilon=data['config']['epsilon'],
                    normalized=(score[solver.ACTIVITY]/np.maximum(reference[solver.ACTIVITY], 1e-12)).tolist()))
    chosen = []
    for role, key in (('balanced', lambda r: np.dot(r['normalized'], args.weights)/sum(args.weights)),
                      ('best_E', lambda r: r['normalized'][0]), ('best_H4', lambda r: r['normalized'][1]),
                      ('best_H8', lambda r: r['normalized'][2])):
        eligible = [r for r in rows if role in r['roles']]
        if not eligible:
            continue
        row = min(eligible, key=lambda r: (key(r), r['epsilon'], r['architecture_sha256']))
        prior = next((r for r in chosen if r['architecture_sha256'] == row['architecture_sha256']), None)
        if prior:
            prior['route_roles'].append(role)
        elif len(chosen) < args.route_limit:
            chosen.append(dict(row, route_roles=[role]))
    path = args.output/'selection'/f'{args.design}.json'
    if path.exists() and read(path) != chosen:
        raise ValueError('Route selection is already frozen')
    write_json(path, chosen)
    return chosen


def route(args):
    gate()
    from pact_solver_routes import route_selected
    from pact_oss_benchmark import binding as full_binding
    selected = selection(args)
    out = args.output/'raw/routes'/args.design
    results = route_selected(args.design, [('_'.join(r['route_roles']), r) for r in selected], out,
                             variant_prefix='stage_b_s11', route_seconds=600)
    records = {}
    for r in results:
        sha = r['architecture_sha256']
        records[sha] = dict(report=r, report_binding=full_binding(out/sha/'route_result.json'),
            archive=full_binding(out/sha/'5_2_route.odb.gz') if (out/sha/'5_2_route.odb.gz').exists() else None,
            reused=False)
    write_json(args.output/'routes'/f'{args.design}.json', dict(records=records))


def measure(args):
    gate()
    import pact_oss_receiver_measure as frozen
    # Reuse the complete unchanged measurement path, with Stage-B paths only.
    frozen.STAGE = args.output
    frozen.RAW = args.output/'raw'
    frozen.gate = gate
    frozen.prior = lambda *unused: None
    frozen.measure(args.design)


def index(args):
    rows = []
    for design in DESIGNS:
        local = argparse.Namespace(**vars(args)); local.design = design
        for r in selection(local):
            rows.append(dict(design=design, method='StageB', architecture_hash=r['architecture_sha256'],
                architecture_path=r['architecture'], roles=';'.join(r['route_roles']), selected='True',
                representative=str('balanced' in r['route_roles']), epsilon=r['epsilon'],
                FF_count=sum(r['chain_sizes']), K=len(r['chain_sizes'])))
    from pact_oss_canonicalize import csv_write
    csv_write(args.output/'architecture_index.csv', list(rows[0]), rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('search', 'index', 'route', 'measure'))
    p.add_argument('--design', choices=DESIGNS)
    p.add_argument('--output', type=Path)
    p.add_argument('--seconds', type=float, default=600.)
    p.add_argument('--max-evaluations', type=int, default=20000)
    p.add_argument('--stagnation-attempts', type=int, default=2000)
    p.add_argument('--epsilons', type=float, nargs='+', default=[.02, .05, .10])
    p.add_argument('--weights', type=float, nargs=3, default=[1., 1., 1.])
    p.add_argument('--route-limit', type=int, choices=(1, 2, 3, 4), default=3)
    args = p.parse_args()
    storage = configure_experiment_storage()
    guard_disk_space(storage, estimated_bytes=2*1024**3)
    args.output = (args.output or storage.results/'stage_b_20261004').resolve()
    os.environ['PATH'] = '/usr/bin:' + os.environ['PATH']
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', NUMBA_NUM_THREADS='1')
    if args.action == 'index':
        index(args)
    else:
        for design in ([args.design] if args.design else DESIGNS):
            args.design = design
            globals()[args.action](args)


if __name__ == '__main__':
    main()
