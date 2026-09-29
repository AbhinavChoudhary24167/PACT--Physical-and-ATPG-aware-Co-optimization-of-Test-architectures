#!/usr/bin/env python3
"""Strictly additive candidate_stateful mode on the PACT-v2 backend."""
import argparse
import csv
from dataclasses import asdict
import gzip
import json
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
import pact_v2 as backend
import pact_candidate_sensitive as previous
from pact_v2 import ROOT, DESIGNS, binding, read, write_json, ScanArchitecture
from pact.integration.patterns import fan_workload
from pact.optimizer import implementation_v2 as v2
from pact.optimizer import candidate_sensitive as cs
from pact.optimizer import candidate_stateful as sf

OUT = ROOT/'results/pact_candidate_stateful'
SOURCES = ['src/pact/optimizer/candidate_stateful.py', 'src/pact/optimizer/stateful_geometry.py',
    'scripts/pact_candidate_stateful.py', 'scripts/pact_stateful_corpus.py',
    'src/pact/optimizer/implementation_v2.py', 'src/pact/optimizer/search.py']


def load(design, depth=3):
    model, starts, physical, inputs, _ = previous.load(design, ROOT/'results/pact_candidate_sensitive')
    historical = read(ROOT/'results/pact_candidate_sensitive/summary.json')
    search = read(ROOT/'results/pact_candidate_sensitive'/design/'search.json')
    for row in search['selected']:
        arch = ScanArchitecture.from_json(Path(row['architecture']))
        if arch.sha256() != row['architecture_sha256']: raise ValueError('Historical sensitive architecture changed')
        starts.append(('cs_'+arch.sha256()[:12], model.orders(arch)))
        inputs['seed_cs_'+arch.sha256()[:12]] = binding(row['architecture'])
    graph = read(ROOT/'results/pact_candidate_sensitive'/design/'topology.json')
    caprows = list(csv.DictReader(Path(inputs['caps']['path']).open()))
    fan, states = fan_workload(Path(inputs['patterns']['path']), read(inputs['identity_map']['path'])['records'], model.architecture)
    primary = {pin: np.array([int(s['source_fields']['pi1'][i]) for s in states], np.uint8)
               for i, pin in enumerate(fan.primary_inputs)}
    stateful = sf.Model(model, graph, caprows, primary, depth)
    by_sha = {model.architecture_from(o).sha256(): (label, o) for label, o in starts}
    measured = []
    for r in historical['candidates']:
        if r['design'] == design and r['measured'] and r['qualified']:
            label, orders = by_sha[r['architecture_sha256']]
            measured.append(dict(r, orders=orders, label=label))
    inputs['candidate_sensitive_summary'] = binding(ROOT/'results/pact_candidate_sensitive/summary.json')
    inputs['candidate_sensitive_search'] = binding(ROOT/'results/pact_candidate_sensitive'/design/'search.json')
    return stateful, starts, measured, inputs


def provenance(args, inputs):
    return dict(parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        command=sys.argv, inputs=inputs, mode='candidate_stateful', depth=args.depth,
        versions=dict(python=platform.python_version(), numpy=np.__version__, numba=__import__('numba').__version__,
                      scipy=__import__('scipy').__version__), source_code={p: binding(ROOT/p)['sha256'] for p in SOURCES})


def prepare(args):
    from pact_stateful_corpus import reconstruct
    folder = args.output/args.design
    if (folder/'diagnostics.json').exists(): raise ValueError('Diagnostic evidence exists')
    folder.mkdir(parents=True, exist_ok=True)
    began = time.perf_counter()
    model, starts, measured, inputs = load(args.design, args.depth)
    write_json(folder/'model_contract.json', dict(provenance(args, inputs),
        policy='Fixed three nontransparent levels; per-net measured ground/MMST; no outcome tuning',
        graph=model.metadata))
    baseline_caps, baseline_geometry = model.geometry.capacitances(starts[0][1], details=True)
    write_json(folder/'baseline_geometry.json', baseline_geometry)
    mappings, corpus_audit = {}, []
    for namespace in ('pact_v2', 'pact_candidate_sensitive'):
        mapping, audit = reconstruct(model, ROOT/'results'/namespace/args.design, namespace)
        mappings.update(mapping); corpus_audit.append(audit)
    with gzip.open(folder/'prior_corpus.json.gz', 'wt') as f: json.dump(mappings, f, sort_keys=True)
    write_json(folder/'prior_corpus_audit.json', dict(traces=corpus_audit, canonical_architectures=len(set(mappings.values())),
        corpus=binding(folder/'prior_corpus.json.gz')))
    rows = []
    for r in measured:
        state = sf.State(model, r['orders'])
        score = state.score()
        if not rows:
            np.testing.assert_allclose(score, sf.reference(model, r['orders']), rtol=1e-9, atol=1e-6)
        rows.append({k: v for k, v in r.items() if k != 'orders'} | dict(
            stateful=dict(zip(sf.METRICS, map(float, score))), contributions=state.contributions()))
    write_json(folder/'diagnostics.json', dict(rows=rows, seconds=time.perf_counter()-began,
        provenance=provenance(args, inputs), model_contract=binding(folder/'model_contract.json'),
        rule='Read-only rescore; no coefficients/depth/structure selected using these outcomes'))
    print(args.design, 'PREPARED', len(rows), 'historical measurements;', len(mappings), 'canonical prior identities', flush=True)


def search(args):
    folder = args.output/args.design
    if (folder/'search.json').exists() or (folder/'evaluations.csv.gz').exists(): raise ValueError('Search evidence exists; exactly one production run')
    diagnostic = read(folder/'diagnostics.json')
    for p, sha in diagnostic['provenance']['source_code'].items():
        if binding(ROOT/p)['sha256'] != sha: raise ValueError('Model/source changed after diagnostics: '+p)
    began = time.perf_counter()
    model, starts, measured, inputs = load(args.design, args.depth)
    if args.depth != diagnostic['provenance']['depth']: raise ValueError('Depth changed after diagnostics')
    with gzip.open(folder/'prior_corpus.json.gz', 'rt') as f: corpus = json.load(f)
    known = set(corpus.values())
    config = v2.Config(seconds=args.seconds, max_evaluations=args.max_evaluations, seed=11)
    inputs['diagnostics'] = binding(folder/'diagnostics.json'); inputs['prior_corpus'] = binding(folder/'prior_corpus.json.gz')
    write_json(folder/'inputs.json', dict(provenance(args, inputs), config=asdict(config),
        model_initialization_seconds=time.perf_counter()-began))
    evaluated, accepted_stats, rejected_stats = set(), {}, {}
    with gzip.open(folder/'evaluations.csv.gz', 'wt', newline='') as log, gzip.open(folder/'geometry_updates.jsonl.gz', 'wt') as geometry_log:
        writer = None
        def record(row):
            nonlocal writer
            canonical = model.canonical_id(model.current_state.orders)
            evaluated.add(canonical)
            row = {dict(zip(v2.METRICS, sf.METRICS)).get(k, k): v for k, v in row.items()}
            row['architecture_sha256'] = canonical
            row['new_to_complete_prior_corpus'] = canonical not in known
            row.update(model.last_mutation)
            destination = accepted_stats if row['accepted'] else rejected_stats
            for key, value in model.last_mutation.items(): destination[key] = destination.get(key, 0)+value
            if writer is None: writer = csv.DictWriter(log, fieldnames=list(row)); writer.writeheader()
            writer.writerow(row)
            geometry_log.write(json.dumps(dict(evaluation=row['evaluation'], architecture_sha256=canonical,
                accepted=row['accepted'], changed_nets=model.last_geometry), separators=(',', ':'))+'\n')
        result = v2.optimize(model, starts, config, record, state_type=sf.State, reference_evaluator=sf.reference,
            verify_interval=25, profile=model.profile)
    for row in result['archive']: row['new'] = model.canonical_id(row['orders']) not in known
    measured_hashes = {r['architecture_sha256'] for r in measured}
    measured_baselines = [r for r in result['baselines'] if model.canonical_id(r['orders']) in measured_hashes]
    selected = cs.select(result['archive'], measured_baselines, args.route_limit)
    chosen = {model.canonical_id(r['orders']): r['roles'] for r in selected}
    def package(row):
        arch = model.architecture_from(row['orders']); sha = arch.sha256()
        if sha != model.canonical_id(row['orders']): raise ValueError('Canonical hash serializer differs')
        path = folder/'architectures'/(sha+'.json'); arch.to_json(path)
        result_row = dict(architecture=str(path), architecture_sha256=sha, order_id=v2.order_id(row['orders']),
            label=row['label'], metrics=dict(zip(sf.METRICS, map(float, row['score']))),
            new=sha not in known, selected_roles=chosen.get(sha, []), legal=True)
        if sha in chosen:
            result_row['frozen'] = dict(zip(v2.METRICS, map(float, v2.reference(model.frozen, row['orders']))))
            result_row['candidate_sensitive'] = dict(zip(cs.METRICS, map(float, cs.reference(model.sensitive, row['orders']))))
            state = sf.State(model, row['orders'])
            np.testing.assert_allclose(state.score(), row['score'], rtol=1e-9, atol=1e-6)
            result_row['contributions'] = state.contributions()
            _, geometry = model.geometry.capacitances(row['orders'], details=True)
            write_json(folder/'selected_geometry'/(sha+'.json'), geometry)
        return result_row
    result['archive'] = [package(r) for r in result['archive']]
    result['baselines'] = [package(r) for r in result['baselines']]
    result['selected'] = [r for r in result['archive'] if r['selected_roles']]
    result.update(new_unique=len(evaluated-known), config=asdict(config), profile=model.profile,
        accepted_mutation_statistics=accepted_stats, rejected_mutation_statistics=rejected_stats,
        peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        total_seconds=time.perf_counter()-began, depth=args.depth)
    write_json(folder/'search.json', result)
    print(args.design, 'NEW', result['new_unique'], 'EVALUATIONS', result['evaluations'], 'SELECTED', len(result['selected']), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'search', 'route', 'measure', 'report', 'seal'))
    parser.add_argument('--design', choices=DESIGNS)
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--depth', type=int, default=3)
    parser.add_argument('--seconds', type=float, default=180.)
    parser.add_argument('--max-evaluations', type=int, default=20000)
    parser.add_argument('--route-limit', type=int, choices=(1, 2), default=2)
    parser.add_argument('--route-seconds', type=float, default=600.)
    args = parser.parse_args(); args.output = args.output.resolve()
    if args.stage in ('report', 'seal'):
        from pact_stateful_report import report, seal
        (report if args.stage == 'report' else seal)(args.output)
    elif not args.design: parser.error('--design required')
    elif args.stage in ('prepare', 'search'): globals()[args.stage](args)
    else:
        selected = read(args.output/args.design/'search.json')['selected']
        if not selected: print(args.design, 'NO_PROMISING_NEW_CANDIDATE'); return
        if args.stage == 'route':
            # Every design's diagnostics must precede any new route.
            for d in DESIGNS: read(args.output/d/'diagnostics.json')
            with gzip.open(args.output/args.design/'prior_corpus.json.gz', 'rt') as f: known = set(json.load(f).values())
            if len(selected) > 2 or any(r['architecture_sha256'] in known for r in selected): raise ValueError('Invalid route novelty/budget')
            backend.route(args)
        else: backend.measure(args)


if __name__ == '__main__': main()
