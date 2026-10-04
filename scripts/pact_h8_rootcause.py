#!/usr/bin/env python3
"""Diagnose saved PACT H8 evidence. Never invokes search, routing or simulation."""
from pact.environment import python_executable
from pact.experiment_storage import experiment_root
import argparse
import csv
import gzip
import itertools
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from pact.analysis.h8_rootcause import (canonical_json, sha256, write_csv,
    match_architecture, source_index, compare_bins, ordering, pair_classification, decompose_net)
from pact.physical_effect import spatial_bin

DESIGNS = ('s9234', 's15850', 's5378')
SOURCES = ('src/pact/optimizer/candidate_stateful.py', 'src/pact/optimizer/stateful_geometry.py',
    'src/pact/physical_effect.py', 'scripts/physical_effect_export.py', 'scripts/physical_effect.py',
    'scripts/pact_candidate_stateful.py', 'scripts/pact_v2.py', 'scripts/pact_candidate_export.py',
    'scripts/pact_h8_rootcause.py', 'scripts/pact_h8_export.py', 'src/pact/analysis/h8_rootcause.py')


def read(path):
    path = Path(path)
    with (gzip.open(path, 'rt') if path.suffix == '.gz' else path.open()) as stream:
        return json.load(stream)


def local(path):
    """Stored manifests use the qualified WSL checkout's absolute paths."""
    path = str(path).replace('\\','/')
    marker = '/PACT/PACT/'
    if marker in path:
        return ROOT/path.split(marker, 1)[1]
    return Path(path)


def write(path, data):
    Path(path).write_text(canonical_json(data), encoding='utf-8')


def binding(path):
    path = Path(path)
    return dict(path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                sha256=sha256(path), bytes=path.stat().st_size)


def index(out):
    if (out/'evidence_index.json').exists():
        raise ValueError('Output already initialized; use analyze/report or a new directory')
    out.mkdir(parents=True, exist_ok=True)
    summary = read(ROOT/'results/pact_candidate_stateful/summary.json')
    manifests = [ROOT/'reports/physical_effect/manifest.json'] + [
        ROOT/'results'/ns/'measurement/manifest.json' for ns in
        ('pact_v2', 'pact_candidate_sensitive', 'pact_candidate_stateful')]
    entries = []
    for path in manifests:
        for row in read(path)['rows']:
            entries.append(dict(row, folder=str(path.parent/row['design']/row['role']), manifest=str(path)))
    common = dict(repository_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        timestamp=datetime.now(timezone.utc).isoformat(), model_version='candidate_stateful/depth=3/baseline=9d910302',
        script_invocation='PYTHONPATH=.optimizer-deps:src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 '
                          ('' + python_executable() + ' scripts/pact_h8_rootcause.py {index|analyze --design DESIGN|report}'),
        export_invocation='openroad -python -no_init -exit scripts/pact_h8_export.py results/pact_h8_rootcause',
        source_code={p:sha256(ROOT/p) for p in SOURCES})
    architectures = []
    for candidate in summary['candidates']:
        if not candidate['measured']:
            continue
        d, h = candidate['design'], candidate['architecture_sha256']
        entry = match_architecture(d, h, entries)
        archpath = local(entry['architecture']['path'])
        if sha256(archpath) != entry['architecture']['sha256']:
            raise ValueError('Architecture artifact checksum mismatch')
        # Canonical identity differs from the JSON file checksum.
        from pact.scan.model import ScanArchitecture
        if ScanArchitecture.from_json(archpath).sha256() != h:
            raise ValueError('Canonical architecture mismatch')
        folder = local(entry['folder'])
        files = ['net_mapping.json','net_activity_capacitance.csv','transitions.npz',
            'activity_summary.json','spatial_bins.json','cycles.json.gz','workload.json',
            'analysis_manifest.json','routed.odb','routed.v','extracted.spef',
            'FF_transition_crosscheck.json','functional_verification.json','topology_verification.json']
        bindings = {n:binding(folder/n) for n in files if (folder/n).exists()}
        analysis = read(folder/'analysis_manifest.json')
        for n in ('transitions.npz','routed.odb','extracted.spef'):
            expected = analysis.get('local_intermediates',{}).get(n,{}).get('sha256')
            if expected and expected != bindings[n]['sha256']:
                raise ValueError('Historical evidence checksum mismatch: '+str(folder/n))
        for n in ('FF_transition_crosscheck.json','functional_verification.json','topology_verification.json'):
            if read(folder/n)['status'] != 'PASS':
                raise ValueError('Historical qualification failure: '+n)
        evidence = dict(manifest=binding(entry['manifest']), architecture=binding(archpath), artifacts=bindings,
            VCD=dict(sha256=read(folder/'activity_summary.json')['VCD']['sha256'],
                     verification='historically recorded; counts consumed from hash-checked transitions.npz'))
        provenance = dict(common, design=d, architecture_hash=h,
            source_evidence_sha256=__import__('hashlib').sha256(canonical_json(evidence).encode()).hexdigest(),
            source_evidence=evidence)
        architectures.append(dict(design=d, architecture=candidate['architecture'], architecture_sha256=h,
            architecture_path=str(archpath), folder=str(folder), provenance=provenance))
    write(out/'evidence_index.json',dict(provenance=common, architectures=architectures))
    print('INDEXED',len(architectures),'qualified saved architectures',flush=True)


def csv_provenance(rows, provenance):
    keys = ('repository_commit','timestamp','model_version','script_invocation','design','architecture_hash',
            'source_evidence_sha256')
    return [dict(row, **{k:provenance[k] for k in keys}) for row in rows]


def exclusions(model):
    """Separate depth limitation from unavailable fanins without expanding the model."""
    graph = model.graph
    depths = dict.fromkeys(model.roots,0)
    pending = {}
    for cell in graph['cells'].values():
        for pin, n in cell['outputs'].items():
            if n in graph['nets'] and n not in depths:
                formula = graph['functions'].get(cell['master']+'/'+pin)
                if formula:
                    from pact.optimizer.candidate_stateful import expression
                    _, pins, _ = expression(formula)
                    pending[n] = ([cell['inputs'][p] for p in pins],0 if cell['transparent'] else 1)
    while True:
        ready = {n:max((depths[f] for f in fan),default=0)+delta
                 for n,(fan,delta) in pending.items() if all(f in depths for f in fan)}
        if not ready:
            break
        depths.update(ready)
        for n in ready:
            pending.pop(n)
    return {n:('represented' if n in model.represented else 'depth_limited' if n in depths else
               'unrepresented_fanin' if n in pending else 'unsupported_or_excluded') for n in graph['nets']}


def analyze(out, design):
    from pact_candidate_stateful import load
    from pact.optimizer import candidate_stateful as sf
    from pact.optimizer.stateful_geometry import mmst
    idx = read(out/'evidence_index.json')
    saved = read(ROOT/'results/pact_candidate_stateful/summary.json')
    model, _, _, _ = load(design, depth=3)
    baseline_sources = source_index(model.graph['nets'])
    coverage = exclusions(model)
    for entry in [e for e in idx['architectures'] if e['design'] == design]:
        h = entry['architecture_sha256']
        target = out/design/h
        target.mkdir(parents=True,exist_ok=True)
        folder = local(entry['folder'])
        provenance = dict(entry['provenance'], diagnostic_sources={p:sha256(ROOT/p) for p in SOURCES})
        architecture = sf.v2.ScanArchitecture.from_json(local(entry['architecture_path']))
        if architecture.sha256() != h:
            raise ValueError('Canonical architecture mismatch')
        state = sf.State(model,model.orders(architecture))
        score = state.score()
        candidate = match_architecture(design,h,saved['candidates'])
        np.testing.assert_allclose(score[1:3],[candidate['stateful']['E_stateful_ff'],
            candidate['stateful']['H8_stateful_ff']],rtol=1e-10,atol=1e-6)
        counts_archive = np.load(folder/'transitions.npz',allow_pickle=False)
        counts, names = counts_archive['counts'],counts_archive['names'].tolist()
        counts_archive.close()
        mapping = read(folder/'net_mapping.json')
        if names != sorted(mapping['nets']) or len(counts) != model.cycles:
            raise ValueError('Saved counts/net/cycle alignment mismatch')
        schedule = read(folder/'cycles.json.gz')
        expected_schedule = [(p['pattern'],phase,t) for p in read(folder/'workload.json')['patterns']
                             for phase in ('load','unload') for t in range(model.longest)]
        if [(r['pattern'],r['phase'],r['shift']) for r in schedule] != expected_schedule:
            raise ValueError('Cycle order mismatch')
        caprows = {r['net']:r for r in csv.DictReader((folder/'net_activity_capacitance.csv').open())}
        mcaps = {n:float(caprows[n]['ground_pin_ff']) if caprows[n]['ground_pin_ff'] else None for n in names}
        mbins = {n:spatial_bin(mapping['nets'][n]['xy_um'],mapping['bounds_um'],8) for n in names}
        columns = {n:i for i,n in enumerate(names)}
        measured = np.zeros_like(state.field)
        for n in names:
            c = mcaps[n]
            if c is None and counts[:,columns[n]].any():
                raise ValueError('Switched net missing measured C')
            measured[:,mbins[n]] += counts[:,columns[n]]*(c or 0.)
        np.testing.assert_allclose([measured.sum(),measured.max()],
            [candidate['measured']['cap_weighted_ff_transitions'],candidate['measured']['peak_local_cap_ff']],
            rtol=1e-10,atol=1e-5)
        bins, peaks = compare_bins(state.field,measured,model.graph['bounds'],mapping['bounds_um'])
        write_csv(target/'bin_comparison.csv',csv_provenance(bins,provenance))
        msources = source_index(mapping['nets'])
        psources = {model.graph['nets'][n]['source']:n for n in model.represented}
        topology_path = target/'routed_topology.json'
        if not topology_path.exists():
            topology_path=target/'routed_topology.json.gz'
        topology = read(topology_path) if topology_path.exists() else None
        if topology is None:
            raise ValueError('Missing read-only routed topology export: '+str(topology_path))
        if topology['provenance']['source_evidence_sha256'] != provenance['source_evidence_sha256']:
            raise ValueError('Routed topology evidence mismatch')
        deltas = {k:np.zeros_like(state.field) for k in
                  ('activity','capacitance','geometry','omitted','new_topology','removed_topology')}
        rows, peakrows = [], []
        energy_coverage = dict.fromkeys(('represented','depth_limited','unrepresented_fanin',
                                       'unsupported_or_excluded','new_topology'),0.)
        c = peaks['meas_peak_cycle']; b = peaks['meas_peak_bin']
        for source in sorted(set(msources)|set(psources)):
            pn, mn = psources.get(source),msources.get(source)
            pc = state.caps[pn] if pn else None
            mc = mcaps[mn] if mn else None
            pb = model.bins_by_net[pn] if pn else None
            mb = mbins[mn] if mn else None
            pt = None
            if pn:
                wave = np.unpackbits(state.waves[pn],bitorder='little')[:model.cycles*3].reshape(-1,3)
                pt = (wave[:,0]^wave[:,1])+(wave[:,1]^wave[:,2])
            mt = counts[:,columns[mn]] if mn else None
            bn = baseline_sources.get(source)
            category = coverage[bn] if bn else 'new_topology'
            if mn:
                energy_coverage[category] += float(mt.sum())*(mc or 0.)
            if pn and mn:
                deltas['activity'][:,pb] += (mt.astype(float)-pt)*(pc or 0.)
                deltas['capacitance'][:,pb] += mt*((mc or 0.)-(pc or 0.))
                if pb != mb:
                    deltas['geometry'][:,pb] -= mt*(mc or 0.)
                    deltas['geometry'][:,mb] += mt*(mc or 0.)
            elif mn:
                deltas['omitted' if bn else 'new_topology'][:,mb] += mt*(mc or 0.)
            else:
                deltas['removed_topology'][:,pb] -= pt*(pc or 0.)
            small = decompose_net(None if pt is None else pt[c:c+1],None if mt is None else mt[c:c+1],
                                  pc,mc,pb,mb,1)
            terms = {k:float(v[0,b]) for k,v in small.items()}
            measured_at_peak = float(mt[c])*(mc or 0.) if mn and mb == b else 0.
            predicted_at_peak = float(pt[c])*(pc or 0.) if pn and pb == b else 0.
            peakrow = dict(source=source,pred_net=pn,meas_net=mn,coverage=category,
                measured_contribution=measured_at_peak,predicted_contribution=predicted_at_peak,
                residual=measured_at_peak-predicted_at_peak,**terms)
            peakrows.append(peakrow)
            pred_ground = model.geometry.evaluate(pn,state.endpoints.get(pn))[1] if pn else None
            actual_net = topology['nets'].get(mn) if mn else None
            actual_cell = topology['cells'].get(source.rsplit('/',1)[0])
            assumed_cell = model.graph['cells'].get(source.rsplit('/',1)[0])
            assumed_terms = pred_ground['candidate_terminals'] if pred_ground else []
            actual_terms = (actual_net['sinks']+actual_net['ports']) if actual_net else []
            # Source pin itself is excluded from sink-set comparisons.
            assumed_sinks = {t['id'] for t in assumed_terms if not t['id'].startswith('DRIVER/')}
            actual_sinks = {t['id'] for t in actual_terms}
            actual_points = ([mapping['nets'][mn]['xy_um']] + [t['xy'] for t in actual_terms]) if mn else []
            rows.append(dict(source=source,pred_net=pn,meas_net=mn,coverage=category,
                pred_transitions=int(pt.sum()) if pn else None,meas_transitions=int(mt.sum()) if mn else None,
                transition_delta=int(mt.sum())-int(pt.sum()) if pn and mn else None,
                cycle_activity_l1=int(np.abs(mt.astype(np.int16)-pt).sum()) if pn and mn else None,
                cycles_measured_more=int((mt>pt).sum()) if pn and mn else None,
                cycles_measured_above_two=int((mt>2).sum()) if mn else None,
                pred_cap_ff=pc,meas_cap_ff=mc,cap_error_ff=mc-pc if pc is not None and mc is not None else None,
                pred_ground_ff=pred_ground['candidate_ground_ff'] if pn else None,
                meas_ground_ff=float(caprows[mn]['ground_ff']) if mn and caprows[mn]['ground_ff'] else None,
                pred_pin_ff=pred_ground['candidate_pin_ff'] if pn else None,
                meas_pin_ff=float(caprows[mn]['pin_ff']) if mn else None,
                pred_bin=pb,meas_bin=mb,pred_energy=float(pt.sum())*pc if pn else 0.,
                meas_energy=float(mt.sum())*(mc or 0.) if mn else 0.,
                pred_master=assumed_cell['master'] if assumed_cell else None,
                meas_master=actual_cell['master'] if actual_cell else None,
                master_changed=bool(assumed_cell and actual_cell and assumed_cell['master']!=actual_cell['master']),
                sink_set_changed=assumed_sinks != actual_sinks if pn and mn else None,
                sinks_added=';'.join(sorted(actual_sinks-assumed_sinks)),
                sinks_removed=';'.join(sorted(assumed_sinks-actual_sinks)),
                pred_mmst_um=pred_ground['candidate_mmst_um'] if pn else None,
                actual_terminal_mmst_um=mmst(actual_points) if mn else None,
                routed_length_um=actual_net['routed_length_um'] if actual_net else None,
                actual_terminal_bins=';'.join(str(x) for x in sorted({spatial_bin(t, mapping['bounds_um'],8) for t in actual_points})),
                **{('peak_'+k):v for k,v in peakrow.items() if k in
                   ('residual','activity','capacitance','geometry','unmatched','measured_contribution','predicted_contribution')}))
        np.testing.assert_allclose(state.field+sum(deltas.values()),measured,rtol=1e-10,atol=1e-7)
        np.testing.assert_allclose(sum(r['residual'] for r in peakrows),measured[c,b]-state.field[c,b],atol=1e-7)
        write_csv(target/'net_discrepancy.csv',csv_provenance(rows,provenance))
        write_csv(target/'peak_contributors.csv',csv_provenance(sorted(peakrows,key=lambda r:(-abs(r['residual']),r['source'])),provenance))
        current = state.field.copy()
        stages = [dict(stage='predicted',H8=float(current.max()))]
        terms_at_peak = {}
        for kind, delta in deltas.items():
            current += delta
            stages.append(dict(stage=kind,H8=float(current.max()),
                               max_change=float(current.max())-stages[-1]['H8']))
            terms_at_peak[kind] = float(delta[c,b])
        cap_errors = [r['cap_error_ff'] for r in rows if r['cap_error_ff'] is not None]
        buf = lambda cells: {n:v for n,v in cells.items() if v['master'].startswith(('BUF_X','INV_X','CLKBUF_X'))}
        oldbuf,newbuf = buf(model.graph['cells']),buf(topology['cells'])
        peak_coverage = {k:sum(r['measured_contribution'] for r in peakrows if r['coverage']==k) for k in energy_coverage}
        notes = dict(provenance=provenance,architecture=entry['architecture'],**peaks,
            predicted_E=float(state.field.sum()),measured_E=float(measured.sum()),
            decomposition_order=list(deltas),counterfactual_maxima=stages,terms_at_measured_peak=terms_at_peak,
            coverage_energy=energy_coverage,coverage_at_measured_peak=peak_coverage,
            measured_energy_represented_fraction=energy_coverage['represented']/measured.sum(),
            buffers=dict(baseline=len(oldbuf),actual=len(newbuf),inserted=sorted(set(newbuf)-set(oldbuf)),
                removed=sorted(set(oldbuf)-set(newbuf)),resized=sorted(n for n in set(oldbuf)&set(newbuf)
                if oldbuf[n]['master']!=newbuf[n]['master'])),
            matched_sources=sum(bool(r['pred_net'] and r['meas_net']) for r in rows),
            bin_moved_sources=sum(r['pred_bin']!=r['meas_bin'] for r in rows if r['pred_net'] and r['meas_net']),
            matched_activity_l1=sum(r['cycle_activity_l1'] for r in rows if r['cycle_activity_l1'] is not None),
            q_activity_l1=sum(r['cycle_activity_l1'] for r in rows if r['source'].endswith('/Q') and r['cycle_activity_l1'] is not None),
            cap_error_distribution_ff=dict(min=min(cap_errors),median=float(np.median(cap_errors)),
                p05=float(np.percentile(cap_errors,5)),p95=float(np.percentile(cap_errors,95)),max=max(cap_errors),
                mean_abs=float(np.mean(np.abs(cap_errors)))),
            cycles_above_two=sum(r['cycles_measured_above_two'] for r in rows if r['cycles_measured_above_two'] is not None),
            spatial_assignment='whole-net driver origin; physical route overlap is not used by either metric',
            limitations=['Ordered substitutions are not unique independent causal effects; H8 maximum is nonlinear.',
                'Route length and terminal-bin span retained; segment RC/bin weights are not stored by this export.',
                'Zero-delay VCD cannot establish physical timing glitches; >settled counts are event/representation evidence.'])
        write(target/'topology_notes.json',notes)
        print('ANALYZED',design,entry['architecture'],'peaks',peaks['pred_peak_bin'],peaks['meas_peak_bin'],
              'terms',terms_at_peak,flush=True)
        del state,counts,measured,deltas,current


def report(out):
    from pact_h8_report import report as build_report
    build_report(out,ROOT)


def seal(out):
    from pact_h8_report import seal as seal_report
    seal_report(out,ROOT)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('index','analyze','report','seal'))
    parser.add_argument('--design',choices=DESIGNS)
    parser.add_argument('--output',type=Path,default=ROOT/'results/pact_h8_rootcause')
    args=parser.parse_args()
    if args.stage=='analyze':
        if not args.design:
            parser.error('analyze requires --design')
        analyze(args.output,args.design)
    else:
        globals()[args.stage](args.output)


if __name__=='__main__':
    main()
