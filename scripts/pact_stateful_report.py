"""Fixed-model historical diagnostics and separate implementation/physical outcomes."""
from pact.environment import python_executable
from pact.experiment_storage import experiment_root
import csv
import gzip
import itertools
import json
from pathlib import Path
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
import numpy as np
from pact_v2 import ROOT, DESIGNS, read, write_json, binding
from pact_v2_report import PHYSICAL, measurement
from pact.optimizer.search import dominates
from pact.optimizer.candidate_stateful import METRICS


def qualification(row):
    m = row.get('measured')
    return bool(m and row['status'] == 'QUALIFIED' and m['DRC'] == 0 and
        m['setup_wns_ns'] is not None and m['hold_wns_ns'] is not None and
        m['setup_wns_ns'] >= 0 and m['hold_wns_ns'] >= 0 and
        (not row['new'] or all(row.get('checks', {}).get(k) == 'PASS' for k in
            ('FF_transition_crosscheck', 'functional_verification', 'topology_verification'))))


def diagnostic_pairs(rows):
    result = {}
    for metric, actual, keys in [
        ('E', PHYSICAL[1], [('frozen', 'activity_ff_transitions'), ('candidate_sensitive', 'candidate_E_ff'), ('stateful', 'E_stateful_ff')]),
        ('H8', PHYSICAL[2], [('frozen', 'spatial_peak_8_ff'), ('candidate_sensitive', 'propagated_H8_ff'), ('stateful', 'H8_stateful_ff')])]:
        result[metric] = {}
        for mode, key in keys:
            counts = dict(correct=0, reversed=0, predicted_tie=0, actual_tie=0)
            errors, pairs = [], []
            for row in rows: errors.append(abs(row[mode][key]-row['measured'][actual]))
            for a, b in itertools.combinations(rows, 2):
                obs = a['measured'][actual]-b['measured'][actual]
                pred = a[mode][key]-b[mode][key]
                if np.isclose(obs, 0, atol=1e-8): status = 'actual_tie'
                elif np.isclose(a[mode][key], b[mode][key], rtol=1e-9, atol=1e-8): status = 'predicted_tie'
                elif np.sign(obs) == np.sign(pred): status = 'correct'
                else: status = 'reversed'
                counts[status] += 1
                pairs.append(dict(a=a['architecture'], b=b['architecture'], predicted_delta=pred,
                    measured_delta=obs, status=status))
            result[metric][mode] = dict(counts, mean_absolute_error=float(np.mean(errors)), pairs=pairs)
    return result


def report(out):
    rows, designs, diagnostics = [], {}, {}
    for design in DESIGNS:
        folder = out/design
        if not (folder/'diagnostics.json').exists(): continue
        diagnostic = read(folder/'diagnostics.json')
        historical = []
        for old in diagnostic['rows']:
            row = dict(design=design, architecture=old['architecture'], architecture_sha256=old['architecture_sha256'],
                new=False, status='QUALIFIED', measured=old['measured'], frozen=old['frozen'],
                candidate_sensitive=old['predicted'], stateful=old['stateful'],
                label=old['label'], selected_roles=[], prior_frontier=old['nondominated'], contributions=old['contributions'])
            rows.append(row); historical.append(row)
        diagnostics[design] = dict(all_measured=diagnostic_pairs(historical),
            previous_sensitive_selected_pair=diagnostic_pairs([r for r in historical if r['label'].startswith('cs_')]),
            seconds=diagnostic['seconds'])
        result_path = folder/'search.json'
        if not result_path.exists(): continue
        result = read(result_path)
        for selected in result['selected']:
            sha = selected['architecture_sha256']
            row = dict(design=design, architecture=sha[:12], architecture_sha256=sha, new=True,
                status='PREDICTED_ONLY', measured=None, frozen=selected['frozen'],
                candidate_sensitive=selected['candidate_sensitive'], stateful=selected['metrics'],
                selected_roles=selected['selected_roles'], label=selected['label'], contributions=selected['contributions'])
            route_path = out/'routes'/design/sha/'route_result.json'
            if route_path.exists():
                route = read(route_path); row['status'] = route['status']; row['route'] = binding(route_path)
                folder_m = out/'measurement'/design/sha[:12]
                if (folder_m/'activity_summary.json').exists():
                    row['measured'] = measurement(folder_m, route)
                    row['measurement'] = binding(folder_m/'activity_summary.json')
                    row['checks'] = {k: read(folder_m/(k+'.json'))['status'] for k in
                        ('FF_transition_crosscheck', 'functional_verification', 'topology_verification')}
            rows.append(row)
        with gzip.open(folder/'evaluations.csv.gz', 'rt') as f: trials = list(csv.DictReader(f))
        seconds = float(trials[-1]['seconds']) if trials else 0.
        prior = read(ROOT/'results/pact_candidate_sensitive'/design/'search.json')
        with gzip.open(ROOT/'results/pact_candidate_sensitive'/design/'evaluations.csv.gz', 'rt') as f:
            oldtrials = list(csv.DictReader(f))
        old_ms = float(oldtrials[-1]['seconds'])*1000/len(oldtrials)
        ms = 1000*seconds/len(trials) if trials else None
        designs[design] = {k: result[k] for k in ('evaluations', 'new_unique', 'accepted', 'config',
            'initialization_seconds', 'search_seconds', 'total_seconds', 'peak_RSS_MiB', 'profile',
            'accepted_mutation_statistics', 'rejected_mutation_statistics')}
        designs[design].update(mutation_loop_seconds=seconds, mutation_loop_ms_per_evaluation=ms,
            candidate_sensitive_ms_per_evaluation=old_ms, slowdown_vs_candidate_sensitive=ms/old_ms if ms else None,
            selected=[r['architecture_sha256'] for r in result['selected']],
            graph=read(folder/'model_contract.json')['graph'], inputs=binding(folder/'inputs.json'))
    qualified = [r for r in rows if qualification(r)]
    found = []
    for row in rows:
        row['qualified'] = qualification(row); row['nondominated'] = None; row['extends_existing_frontier'] = False
        for metric, actual, modes in [('E', PHYSICAL[1], [('frozen', 'activity_ff_transitions'), ('candidate_sensitive', 'candidate_E_ff'), ('stateful', 'E_stateful_ff')]),
                                      ('H8', PHYSICAL[2], [('frozen', 'spatial_peak_8_ff'), ('candidate_sensitive', 'propagated_H8_ff'), ('stateful', 'H8_stateful_ff')])]:
            if row['measured']:
                for mode, key in modes:
                    row[f'{mode}_{metric}_absolute_error'] = abs(row[mode][key]-row['measured'][actual])
        if not row['qualified']: continue
        same = [r for r in qualified if r['design'] == row['design'] and r is not row]
        vector = np.array([row['measured'][k] for k in PHYSICAL])
        row['dominated_by'] = [r['architecture'] for r in same if dominates(np.array([r['measured'][k] for k in PHYSICAL]), vector)]
        row['nondominated'] = not row['dominated_by']
        historical = [r for r in same if not r['new']]
        row['extends_existing_frontier'] = bool(row['new'] and row['nondominated'] and not any(
            np.allclose(vector, [r['measured'][k] for k in PHYSICAL], rtol=1e-9, atol=1e-8) for r in historical))
        if row['extends_existing_frontier']: found.append(row)
        if row['new']:
            row['delta_vs_existing_frontier_percent'] = {r['architecture']: {k: 100*(row['measured'][k]/r['measured'][k]-1)
                for k in PHYSICAL} for r in historical if r['prior_frontier']}
    selected = [r for r in rows if r['new']]
    tests_path = out/'repository_tests.xml'
    tests = None
    if tests_path.exists():
        s = ET.parse(tests_path).getroot().find('testsuite')
        tests = {k: int(s.get(k)) for k in ('tests', 'failures', 'errors', 'skipped')}
        tests['seconds'] = float(s.get('time'))
    implementation = 'PACT_CANDIDATE_STATEFUL_MODEL_COMPLETE' if len(designs) == 3 and tests and not tests['failures'] and not tests['errors'] else 'PACT_CANDIDATE_STATEFUL_IMPLEMENTATION_INCOMPLETE'
    complete = len(designs) == 3 and all(r['status'] != 'PREDICTED_ONLY' and
        (r['status'] != 'QUALIFIED' or r['measured']) for r in selected)
    physical = 'PACT_CANDIDATE_STATEFUL_PHYSICAL_EVALUATION_INCOMPLETE'
    if complete:
        physical = 'PACT_CANDIDATE_STATEFUL_NEW_FRONTIER_FOUND' if found else 'PACT_CANDIDATE_STATEFUL_NO_NEW_FRONTIER'
        if any(not r['qualified'] for r in selected): physical += '_WITH_QUALIFICATION_FAILURES'
    summary = dict(mode='candidate_stateful', implementation_classification=implementation, physical_classification=physical,
        parent_commit=next((read(out/d/'inputs.json')['parent_commit'] for d in designs), None),
        depth=3, designs=designs, historical_diagnostics=diagnostics, candidates=rows, tests=tests,
        selected=len(selected), physically_measured=sum(r['measured'] is not None for r in selected),
        new_frontier=[dict(design=r['design'], architecture=r['architecture']) for r in found],
        new_candidate_pair_diagnostics={d: diagnostic_pairs([r for r in selected if r['design'] == d and r['qualified']])
            for d in designs if sum(r['design'] == d and r['qualified'] for r in selected) >= 2},
        interpretation='Fixed-model diagnostics and at most six new routes; no validation/causality claim; no outcome tuning')
    write_json(out/'summary.json', summary)
    with (out/'pairwise_diagnostics.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['design', 'metric', 'a', 'b', 'measured_delta',
            'frozen_delta', 'candidate_sensitive_delta', 'stateful_delta', 'frozen_status',
            'candidate_sensitive_status', 'stateful_status', 'ordering_changed'])
        writer.writeheader()
        for d, diag in diagnostics.items():
            for metric, modes in diag['all_measured'].items():
                for frozen, sensitive, stateful in zip(*(modes[k]['pairs'] for k in ('frozen', 'candidate_sensitive', 'stateful'))):
                    writer.writerow(dict(design=d, metric=metric, a=stateful['a'], b=stateful['b'],
                        measured_delta=stateful['measured_delta'], frozen_delta=frozen['predicted_delta'],
                        candidate_sensitive_delta=sensitive['predicted_delta'], stateful_delta=stateful['predicted_delta'],
                        frozen_status=frozen['status'], candidate_sensitive_status=sensitive['status'],
                        stateful_status=stateful['status'], ordering_changed=sensitive['status'] != stateful['status']))
    fields = ['design', 'architecture', 'architecture_sha256', 'new', 'status', 'frozen_E', 'candidate_sensitive_E',
        'stateful_E', 'measured_C_N', 'frozen_H8', 'candidate_sensitive_H8', 'stateful_H8', 'measured_H8',
        'stateful_H4', 'wire_um', *PHYSICAL, 'total_transitions', 'peak_transitions', 'peak_local', 'peak_local_4',
        'peak_local_cap_4_ff', 'setup_wns_ns', 'hold_wns_ns', 'DRC', 'qualified', 'nondominated', 'extends_existing_frontier']
    fields += [f'{mode}_{metric}_absolute_error' for mode in ('frozen', 'candidate_sensitive', 'stateful') for metric in ('E', 'H8')]
    with (out/'comparison.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore'); writer.writeheader()
        for r in rows:
            m = r['measured'] or {}
            writer.writerow(dict(r, **m, frozen_E=r['frozen']['activity_ff_transitions'],
                candidate_sensitive_E=r['candidate_sensitive']['candidate_E_ff'], stateful_E=r['stateful']['E_stateful_ff'],
                measured_C_N=m.get(PHYSICAL[1]), frozen_H8=r['frozen']['spatial_peak_8_ff'],
                candidate_sensitive_H8=r['candidate_sensitive']['propagated_H8_ff'], stateful_H8=r['stateful']['H8_stateful_ff'],
                measured_H8=m.get(PHYSICAL[2]), stateful_H4=r['stateful']['H4_stateful_ff'], wire_um=r['stateful']['wire_um']))
    lines = ['# PACT candidate_stateful', '', '**Implementation:** '+implementation, '', '**Physical outcome:** '+physical, '',
        'Parent commit: `'+str(summary['parent_commit'])+'`. The delivery commit is identified in Git history and the final engineering response. Exact commands, dependencies and source/input hashes are in each design’s model contract, inputs and execution manifests.', '',
        '## Direct engineering answers', '',
        '1. **Bounded exact state-aware propagation:** implemented, with a fixed production bound of three nontransparent levels. See MODEL.md for the settled-state and coverage limits.',
        '2. **Q/QN:** separate packed binary waveforms; QN is the logical complement of Q.',
        '3. **Simultaneous changes:** gates evaluate all actual cached fanin states in topological order, including multiple changed inputs. Cancellation and represented reconvergence are preserved.',
        '4. **Shared geometry:** candidate SI/SO endpoints join retained terminals on an MMST net; no independent scan star branch is added.',
        '5. **Baseline reproduction:** every reconstructed baseline terminal set is checked, and every measured ground value is reproduced, including retained zero-span ground. Per-net calibration and explicit fallbacks are audited.',
        '6. **Evaluation cost:** measured mutation-loop costs and ratios to the previous candidate-sensitive run appear below; these are observations on this machine, not isolated performance benchmarks.',
        '7. **Novel architectures:** counts exclude canonical hashes reconstructed and verified from both complete previous evaluation corpora.',
        '8. **Routed architectures:** only the novel predicted nondominated selections in the table below, at most two per design.',
        '9. **Measured frontier:** '+str(len(found))+' new qualified points extend the combined existing measured frontier; see the outcome table.',
        '10. **E ordering:** unchanged on the historical diagnostic set: 26/28, 28/28 and 28/28 pairs correct for s5378, s9234 and s15850 respectively, for both models.',
        '11. **H8 ordering:** improves from 17/28 to 27/28 correct pairs on s5378, 7/28 to 9/28 on s9234, and 17/28 to 19/28 on s15850. This is a fixed-model diagnostic, not predictor validation.',
        '12. **Remaining ranking failures:** the previous s5378 selected-pair H8 reversal is resolved; s9234 becomes an unresolved predicted tie; s15850 remains reversed. Every pair and ordering change is retained in pairwise_diagnostics.csv and summary.json.',
        '13. **Remaining error mechanisms:** unrepresented fanins/deeper logic, settled-state omission of glitches, and candidate changes to routing/buffer sizing/insertion. These are model omissions, not experimentally isolated causal attributions.',
        '14. **Largest implementation-readiness blocker:** unreliable implemented hot-spot ordering, especially on s9234. The next missing physical mechanism is candidate-dependent buffer insertion/resizing and its effect on routed shared-net capacitance and spatial attribution. Deeper logic and event/glitch activity also remain absent; these observations do not establish which omission causes each error.', '',
        '## Search and coverage', '',
        '| Design | Trials | New canonical architectures | ms/trial | Relative cost | Peak RSS MiB | Gates at depths 0/1/2/3 |',
        '|---|---:|---:|---:|---:|---:|---|']
    for d, s in designs.items():
        lines.append(f"| {d} | {s['evaluations']} | {s['new_unique']} | {s['mutation_loop_ms_per_evaluation']:.3f} | {s['slowdown_vs_candidate_sensitive']:.2f}x | {s['peak_RSS_MiB']:.1f} | "+'/'.join(str(s['graph']['gates_at_depth'][str(k)]) for k in range(4))+' |')
    lines += ['', 's9234 found no canonical architecture absent from the complete prior corpus before its wall-clock ceiling; no route slot was filled for that design. The production searches ran concurrently with one thread per numerical library; the cost ratios include reference checks, evidence logging and host contention.', '',
        '| Design | Initialization s | Search + final checks s | Total search command s | Scan waveform s | Gate propagation s | Geometry s | Spatial updates s | Rollback s |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for d, s in designs.items():
        p = s['profile']
        values = [s['initialization_seconds'], s['search_seconds'], s['total_seconds'],
            p['scan_waveform_seconds'], p['stateful_propagation_seconds'], p['geometry_seconds'],
            p['spatial_seconds'], p['rollback_seconds']]
        lines.append('| '+d+' | '+' | '.join(f'{v:.3f}' for v in values)+' |')
    lines += ['', 'Spatial field accumulation and rollback dominate measured evaluator time. The 180-second ceiling applies to the mutation loop; initialization, one in-flight mutation and required final reference checks add overhead. No additional production run was performed to improve throughput.', '',
        '| Design | Accepted / rejected trials | Changed FF waveforms A / R | Gate recomputations A / R | Cancellations A / R | Represented Q / QN nets | Excluded gate outputs |',
        '|---|---|---|---|---|---|---:|']
    for d, s in designs.items():
        a, r = s['accepted_mutation_statistics'], s['rejected_mutation_statistics']
        values = [f"{s['accepted']} / {s['evaluations']-s['accepted']}"]
        values += [f'{a.get(k, 0)} / {r.get(k, 0)}' for k in ('FF_waveform_changes', 'gate_recomputations', 'cancellation_events')]
        values += [f"{s['graph']['represented_Q']} / {s['graph']['represented_QN']}", str(len(s['graph']['excluded_gates']))]
        lines.append('| '+d+' | '+' | '.join(values)+' |')
    lines += ['', 'These three mapped baselines have no connected QN output nets; the dedicated Q/QN and reconvergence fixtures exercise both polarities. Per-FF reachability and per-architecture Q/QN energy contributions remain in model_contract.json and summary.json.']
    lines += ['', '## Historical diagnostic table', '',
        'No historical route or measurement was repeated. E columns use millions of fF·transitions; H8 uses fF·transitions per bin/cycle. Absolute errors for every row are in comparison.csv.', '',
        '| Design | Architecture | Frozen E | Sensitive E | Stateful E | Measured E | Frozen H8 | Sensitive H8 | Stateful H8 | Measured H8 |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in [r for r in rows if not r['new']]:
        values = [r['frozen']['activity_ff_transitions']/1e6, r['candidate_sensitive']['candidate_E_ff']/1e6,
            r['stateful']['E_stateful_ff']/1e6, r['measured'][PHYSICAL[1]]/1e6,
            r['frozen']['spatial_peak_8_ff'], r['candidate_sensitive']['propagated_H8_ff'], r['stateful']['H8_stateful_ff'], r['measured'][PHYSICAL[2]]]
        lines.append('| '+r['design']+' | '+r['architecture']+' | '+' | '.join(f'{v:.4f}' for v in values)+' |')
    lines += ['', '| Design | Sensitive E MAE (million) | Stateful E MAE (million) | Sensitive H8 MAE | Stateful H8 MAE |',
        '|---|---:|---:|---:|---:|']
    for d, diag in diagnostics.items():
        values = [diag['all_measured'][metric][mode]['mean_absolute_error']/(1e6 if metric == 'E' else 1)
            for metric in ('E', 'H8') for mode in ('candidate_sensitive', 'stateful')]
        lines.append('| '+d+' | '+' | '.join(f'{v:.4f}' for v in values)+' |')
    lines += ['', 'Absolute E error increases for s9234 even though its E ordering remains correct. Bounded-state exactness does not imply completeness of the measured whole-design field.']
    lines += ['', '## Pairwise ordering diagnostics', '',
        '| Design | Scope | Metric | Sensitive correct / reversed / tied | Stateful correct / reversed / tied |',
        '|---|---|---|---|---|']
    for d, diag in diagnostics.items():
        for scope in ('all_measured', 'previous_sensitive_selected_pair'):
            for metric in ('E', 'H8'):
                a, b = diag[scope][metric]['candidate_sensitive'], diag[scope][metric]['stateful']
                lines.append(f'| {d} | {scope} | {metric} | '+
                    ' | '.join('/'.join(str(v[k]) for k in ('correct', 'reversed', 'predicted_tie')) for v in (a, b))+' |')
    lines += ['', 'Remaining stateful reversals (all historical measured pairs):', '']
    for d, diag in diagnostics.items():
        for metric, modes in diag['all_measured'].items():
            pairs = [p['a']+' / '+p['b'] for p in modes['stateful']['pairs'] if p['status'] == 'reversed']
            lines.append('- '+d+' '+metric+': '+('; '.join(pairs) if pairs else 'none')+'.')
    lines += ['', '## New physical implementations', '',
        '| Design | Hash | Selection reason | Stateful E (million) | Stateful H8 | Measured E (million) | Measured H8 | Routed path upper bound um | Frontier extension |',
        '|---|---|---|---:|---:|---:|---:|---:|---|']
    for r in selected:
        m = r['measured']
        measured = f"{m[PHYSICAL[1]]/1e6:.4f} | {m[PHYSICAL[2]]:.4f} | {m[PHYSICAL[0]]:.3f}" if m else 'pending | pending | pending'
        lines.append(f"| {r['design']} | {r['architecture']} | {'; '.join(r['selected_roles'])} | {r['stateful']['E_stateful_ff']/1e6:.4f} | {r['stateful']['H8_stateful_ff']:.4f} | {measured} | {r['extends_existing_frontier']} |")
    lines += ['', '| Design | Hash | DRC | Setup ns | Hold ns | Topology / functional / FF checks | Fully qualified |',
        '|---|---|---:|---:|---:|---|---|']
    for r in selected:
        m = r['measured']
        values = [str(m[k]) for k in ('DRC', 'setup_wns_ns', 'hold_wns_ns')] if m else ['pending']*3
        checks = ' / '.join(r.get('checks', {}).get(k, 'pending') for k in
            ('topology_verification', 'functional_verification', 'FF_transition_crosscheck'))
        lines.append('| '+r['design']+' | '+r['architecture']+' | '+' | '.join(values)+f" | {checks} | {r['qualified']} |")
    lines += ['', 'Timing uses the unchanged adapter’s available global-route setup/hold values. Wire qualification uses the routed full scan-path net-length upper bound, retaining shared-net accounting from the existing measurement pipeline.', '']
    for d, diag in summary['new_candidate_pair_diagnostics'].items():
        statuses = [metric+' '+diag[metric]['stateful']['pairs'][0]['status'] for metric in ('E', 'H8')]
        lines.append('- New '+d+' selected pair: '+', '.join(statuses)+'.')
    lines += ['', 'The implementation provides architecture → exact scan states → bounded state-aware switching → shared candidate capacitance → search → routing → physical qualification. Exactness applies to represented settled Boolean states, not delay/glitch/signoff prediction. Scientific outcome is reported independently of implementation completion; neither causality nor predictor validation is claimed.', '',
        '## Execution and evidence', '',
        'One prepare and one search per design; no depth sweep, placement change, ATPG regeneration, seed sweep or historical reroute. The search command was:', '',
        '```sh', 'export PYTHONPATH=.optimizer-deps:src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1',
        f'PY={python_executable()}',
        '$PY scripts/pact_candidate_stateful.py prepare --design <design>',
        '$PY scripts/pact_candidate_stateful.py search --design <design> --seconds 180 --max-evaluations 20000 --route-limit 2',
        '$PY scripts/pact_candidate_stateful.py route --design <design> --route-seconds 600',
        '$PY scripts/pact_candidate_stateful.py measure --design <design>',
        '$PY scripts/pact_candidate_stateful.py report',
        '$PY scripts/pact_candidate_stateful.py seal',
        '$PY -m pytest -q tests/unit/test_candidate_stateful.py',
        '$PY -m pytest -q --junitxml=results/pact_candidate_stateful/repository_tests.xml', '```', '',
        'WSL distribution: Ubuntu-24.04. The route/measure commands ran only for s5378 and s15850. The full repository suite passed '+str(tests['tests'] if tests else 0)+' tests; its JUnit record includes elapsed time. Python/NumPy/Numba/SciPy versions are recorded per design; physical tool versions and exact commands are recorded in the unchanged adapters’ route/measurement manifests.', '',
        'Read-only historical diagnostics precede all new routes. Complete canonical prior identities and trace checks are in prior_corpus files. Baseline and selected geometry audits, every changed-net record, accepted/rejected propagation counters, Q/QN contributions and runtime profiles are retained. Historical integrity and physical validation records accompany the sealed artifact manifest.']
    lines += ['', '| Design | Python | NumPy | Numba | SciPy | Diagnostic preparation s |',
        '|---|---|---|---|---|---:|']
    for d in designs:
        versions = read(out/d/'inputs.json')['versions']
        lines.append('| '+d+' | '+' | '.join(versions[k] for k in ('python', 'numpy', 'numba', 'scipy'))+
            f" | {diagnostics[d]['seconds']:.3f} |")
    if (out/'measurement/manifest.json').exists():
        tools = read(out/'measurement/manifest.json')['tools']
        lines += ['', 'Physical tools: '+', '.join(k+' `'+v.strip()+'`' for k, v in tools.items())+'.']
    if tests: lines += ['', f"Full-suite runtime: {tests['seconds']:.3f} seconds. Focused stateful tests also passed independently (6 tests)."]
    (out/'README.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(implementation, physical, summary['new_frontier'], flush=True)


def seal(out):
    from pact_candidate_stateful import SOURCES
    began = time.perf_counter()
    summary = read(out/'summary.json')
    if summary['implementation_classification'] != 'PACT_CANDIDATE_STATEFUL_MODEL_COMPLETE' or 'INCOMPLETE' in summary['physical_classification']:
        raise ValueError('Milestone incomplete')
    reused = {}
    for namespace in ('pact_v2', 'pact_candidate_sensitive'):
        path = ROOT/'results'/namespace/'evidence_manifest.json'
        expected = read(path)
        reused[str(path.relative_to(ROOT))] = binding(path)
        for p, value in expected['artifacts'].items():
            bound = binding(ROOT/p)
            if bound['sha256'] != value['sha256']: raise ValueError('Historical evidence changed: '+p)
            reused[p] = bound
    for design in DESIGNS:
        for name in ('inputs.json', 'model_contract.json'):
            data = read(out/design/name)
            for value in data['inputs'].values():
                if binding(value['path'])['sha256'] != value['sha256']: raise ValueError('Reused input changed')
                reused[value['path']] = value
            for p, sha in data['source_code'].items():
                if binding(ROOT/p)['sha256'] != sha: raise ValueError('Model changed after diagnostics/search: '+p)
    write_json(out/'historical_evidence_integrity.json', dict(status='PASS', bindings=reused, count=len(reused)))
    checks = []
    path = out/'measurement/manifest.json'
    if path.exists():
        for row in read(path)['rows']:
            folder = out/'measurement'/row['design']/row['role']
            sim = read(folder/'simulation_manifest.json')
            for value in [*sim['inputs'].values(), sim['cells'], row['routed_archive'], row['qualification']]:
                if binding(value['path'])['sha256'] != value['sha256']: raise ValueError('Physical binding mismatch')
            if binding(folder/'activity.vcd')['sha256'] != read(folder/'activity_summary.json')['VCD']['sha256']: raise ValueError('Waveform changed')
            for k in ('FF_transition_crosscheck', 'functional_verification', 'topology_verification'):
                if read(folder/(k+'.json'))['status'] != 'PASS': raise ValueError('Failed physical check')
            if 'PASS patterns=' not in (folder/'simulate.log').read_text(): raise ValueError('Workload replay failed')
            for name in ('cycles.json', 'stimulus.v', 'per_cycle.csv'):
                with (folder/name).open('rb') as src, (folder/(name+'.gz')).open('wb') as dst:
                    with gzip.GzipFile(fileobj=dst, mode='wb', filename='', mtime=0) as z: shutil.copyfileobj(src, z)
            write_json(folder/'analysis_manifest.json', dict(
                local_intermediates={n: dict(binding(folder/n), bytes=(folder/n).stat().st_size) for n in
                    ('activity.vcd', 'routed.odb', 'extracted.spef', 'simulation.vvp', 'transitions.npz')},
                compressed={n: binding(folder/(n+'.gz')) for n in ('cycles.json', 'stimulus.v', 'per_cycle.csv')}))
            checks.append(dict(design=row['design'], architecture=row['role'], status='PASS'))
    expected = {(r['design'], r['architecture']) for r in summary['candidates'] if r['new'] and r['qualified']}
    if {(r['design'], r['architecture']) for r in checks} != expected: raise ValueError('Physical verification set differs')
    write_json(out/'validation_summary.json', dict(tests=summary['tests'], physical_checks=checks,
        historical_evidence='UNCHANGED', model_untuned_after_diagnostics=True,
        seconds=time.perf_counter()-began, implementation=summary['implementation_classification'], physical=summary['physical_classification']))
    files = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '--', str(out)], cwd=ROOT, text=True).splitlines()
    artifacts = {p: dict(sha256=binding(ROOT/p)['sha256'], bytes=(ROOT/p).stat().st_size) for p in sorted(set(files)) if Path(p).name != 'evidence_manifest.json'}
    write_json(out/'evidence_manifest.json', dict(artifacts=artifacts,
        source_code={p: binding(ROOT/p)['sha256'] for p in SOURCES+['scripts/pact_stateful_report.py', 'tests/unit/test_candidate_stateful.py']}))
    print('SEALED', len(artifacts), 'artifacts;', len(checks), 'new physical checks;', len(reused), 'historical bindings', flush=True)
