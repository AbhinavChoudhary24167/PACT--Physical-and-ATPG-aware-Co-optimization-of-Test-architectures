#!/usr/bin/env python3
"""Aggregate Gate-09 receipts without selecting or rerunning any candidate."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
import pact_gate09_admission as admission
import pact_gate09_reference as references
from pact_experiment_receipts import atomic_write

COSTS = ('routed_scan_wirelength_um', 'E', 'H4', 'H8')
TOLERANCE = 1e-10


def dominates(a, b):
    if a.get('qualification_status') != 'QUALIFIED' or b.get('qualification_status') != 'QUALIFIED':
        return False
    tolerance = [TOLERANCE*max(1., abs(a[k]), abs(b[k])) for k in COSTS]
    return all(a[k] <= b[k]+t for k, t in zip(COSTS, tolerance)) and any(
        a[k] < b[k]-t for k, t in zip(COSTS, tolerance))


def classify(primary, reference):
    if primary is None:
        return 'PACT_NO_NEW_PRESELECTED_ARCHITECTURE'
    if primary['qualification_status'] != 'QUALIFIED':
        return 'PACT_PHYSICAL_OR_EXACT_QUALIFICATION_FAIL'
    activity = ['E', 'H4', 'H8']
    better = [primary[k] < reference[k]-TOLERANCE*max(1., abs(primary[k]), abs(reference[k])) for k in activity]
    worse = [primary[k] > reference[k]+TOLERANCE*max(1., abs(primary[k]), abs(reference[k])) for k in activity]
    if all(better):
        return 'PACT_ACTIVITY_IMPROVEMENT_ALL_COORDINATES'
    if any(better):
        return 'PACT_ACTIVITY_MIXED'
    if not any(worse):
        return 'PACT_ACTIVITY_NEGLIGIBLE'
    return 'PACT_NO_MEANINGFUL_ADVANTAGE'


def physical_rows(meta, design):
    records = admission.read(meta / f'baselines/{design}_references.json')['records']
    records += [admission.read(meta / f'baselines/{design}_{m}.json') for m in ('B4', 'B5')]
    selection = admission.read(meta / f'selections/{design}/preselected_candidates.json')
    for candidate in selection['records']:
        path = meta / f'baselines/{design}_{candidate["candidate"]}.json'
        if path.exists():
            records.append(admission.read(path))
        else:
            raise ValueError('Preselected candidate has no preserved terminal physical outcome: '+candidate['candidate'])
    return records, selection


def row(meta, design, item, family, reference_hash):
    role = item['method']
    exact_path = meta / f'activity/GATE09_PRIMARY/{design}/{role}/normal/result.json'
    result = admission.read(exact_path) if exact_path.exists() else None
    physical_ok = item['status'] == 'QUALIFIED'
    exact_ok = bool(result and result['status'] == 'QUALIFIED' and result['complete'])
    out = dict(gate='GATE09', design=design, design_family=family,
        method='PACT' if role.startswith('CS_C') else role, role=role,
        implementation_sha=admission.digest(ROOT / 'src/pact/scan/phase0c.py') if role=='B0' else item['source_revision'],
        architecture_hash=item['architecture_hash'],
        reference_hash=reference_hash, seed=11, chain_count=item.get('chain_count', 2),
        ff_count=None, patterns=None, search_runtime_seconds=0., peak_rss_kib=None,
        exact_evaluations=0, exact_final_netlist_replays=int(exact_ok), candidates=1,
        routed_scan_wirelength_um=item.get('routed_scan_wirelength_um'),
        delta_routed_WL_percent=None, E=None, delta_E_percent=None, H4=None, delta_H4_percent=None,
        H8=None, delta_H8_percent=None, WNS=None, hold_WNS=None, DRC=item.get('DRC'),
        fault_coverage=None, qualification_status='QUALIFIED' if physical_ok and exact_ok else 'FAILED',
        termination_reason=result.get('termination_reason') if result else item.get('error'),
        receipt_paths=[item['architecture']['path']], CPU_only=True,
        search_threads=1, route_threads=2, exact_workers=1,
        timing_stage='global_route', metric_units=dict(WL='um', E='capacitance-weighted transition proxy, not joules',
            H4='maximum capacitance-weighted per-cycle bin activity on 4x4 grid',
            H8='maximum capacitance-weighted per-cycle bin activity on 8x8 grid'))
    from pact.scan.model import ScanArchitecture
    arch = ScanArchitecture.from_json(admission.resolve(item['architecture']['path']))
    out['ff_count'] = len(arch.cells)
    out['chain_lengths'] = [len(c.cells) for c in arch.chains]
    if physical_ok:
        if admission.verify(item['provenance'])['status'] != 'PASS':
            raise ValueError('Qualified physical receipt changed')
        route = admission.read(item['provenance']['path'])
        out.update(WNS=item['timing']['setup_wns_ns'], hold_WNS=item['timing']['hold_wns_ns'],
            fault_coverage=item['correctness']['statistics']['coverage'], patterns=item['correctness']['statistics']['patterns'],
            routing_seconds=route['route_wall_seconds'],
            total_routed_WL_um=item['timing']['total_detailed_route_wirelength_um'],
            fault_target_count=item['correctness']['statistics']['total'])
        out['receipt_paths'] += [item['provenance']['path'], item['correctness']['faults']['path']]
    if exact_ok:
        if result['architecture_sha256'] != item['architecture_hash']:
            raise ValueError('Exact measurement belongs to another architecture')
        folder = admission.resolve(result['output_folder'])
        cross = admission.read(folder / 'FF_transition_crosscheck.json')
        summary = admission.read(folder / 'activity_summary.json')
        manifest = admission.read(result['manifest']['path'])
        if cross['status'] != 'PASS' or not summary['activity_trace']['complete']:
            raise ValueError('Exact activity crosscheck failed')
        out.update(E=result['E'], H4=result['H4'], H8=result['H8'], exact_runtime_seconds=result['wall_seconds'],
            exact_CPU_seconds=result['CPU_seconds'], peak_rss_kib=result['peak_RSS_KiB'],
            cycles=summary['activity_trace']['cycles'], mapped_nets=summary['activity_trace']['mapped_nets'],
            simulation_cells_hash=manifest['simulation_cells']['sha256'],
            exact_trace=summary['activity_trace'], exact_manifest=result['manifest'],
            common_inputs=manifest['rows'][0]['inputs'],
            source_placed_database=manifest['rows'][0]['source_placed_database'],
            source_netlist=manifest['rows'][0]['source_netlist'], SDC=manifest['rows'][0]['SDC'])
        out['receipt_paths'] += [str(exact_path), str(folder / 'FF_transition_crosscheck.json')]
    elif physical_ok:
        worker = meta / f'workers/{design}/measure_run_{role}.json'
        prep_worker = meta / f'workers/{design}/measure_prepare_{role}.json'
        outcome = admission.read(worker if worker.exists() else prep_worker)
        out.update(error=outcome.get('error'), termination_reason=outcome['status'])
        out['receipt_paths'].append(str(worker if worker.exists() else prep_worker))
    if role.startswith('CS_C'):
        search = admission.read(meta / f'searches/{design}/search_results.json')
        out.update(search_runtime_seconds=search['wall_seconds'], search_CPU_seconds=search['CPU_seconds'],
            search_peak_rss_kib=search['peak_RSS_KiB'], exact_evaluations=search['total_exact_mutation_evaluations'],
            search_estimates=item['metrics'], route_roles=item['route_roles'],
            lane_epsilon=item['epsilon'], candidates=len(admission.read(meta / f'selections/{design}/preselected_candidates.json')['records']))
    else:
        out['generation_seconds'] = item.get('generation_wall_seconds')
        if role in ('B1', 'B2', 'B3T'):
            generation = admission.resolve(item['architecture']['path']).parents[1] / 'generation/execution.json'
            if generation.exists():
                out['generation_seconds'] = admission.read(generation)['wall_seconds']
                out['receipt_paths'].append(str(generation))
    out['runtime_seconds'] = (out.get('generation_seconds') or 0)+(out.get('routing_seconds') or 0)+(out.get('exact_runtime_seconds') or 0)+out['search_runtime_seconds']
    out['runtime_scope'] = 'generation when measured + route + exact + shared PACT design search when applicable; shared source preparation and ATPG reported separately'
    return out


def validate_fairness(rows, meta, design):
    qualified = [r for r in rows if r['qualification_status'] == 'QUALIFIED']
    common_keys = ('ff_count', 'chain_count', 'patterns', 'fault_coverage', 'fault_target_count',
        'simulation_cells_hash', 'source_placed_database', 'source_netlist', 'SDC', 'timing_stage')
    for key in common_keys:
        values = [json.dumps(r[key], sort_keys=True) for r in qualified]
        if len(set(values)) != 1:
            raise ValueError('Common backend fairness mismatch: '+key)
    for key in ('patterns', 'placement', 'identity_map'):
        hashes = {r['common_inputs'][key]['sha256'] for r in qualified}
        if len(hashes) != 1:
            raise ValueError('Frozen pattern/placement/identity mismatch: '+key)
    from pact.scan.model import ScanArchitecture
    inventories = []
    for r in rows:
        arch = ScanArchitecture.from_json(admission.resolve(r['receipt_paths'][0]))
        inventories.append(json.dumps(arch.canonical_dict()['cells'], sort_keys=True))
    if len(set(inventories)) != 1:
        raise ValueError('Frozen FF population or coordinates differ')
    selection = admission.read(meta / f'selections/{design}/preselected_candidates.json')
    if selection['candidate_routes_before_selection'] != 0 or len(selection['records']) > 3:
        raise ValueError('Candidate-selection integrity failed')
    return dict(status='PASS', equal_fields=list(common_keys)+['pattern_hash', 'placement_hash', 'identity_hash', 'FF_coordinates'],
        physical_seed=11, K=2, route_backend='Pinned common /usr/bin/openroad',
        extraction='Same frozen OpenRCX parameters and Nangate45 RC rules',
        fixed_endpoints='Common index-based canonical port policy; test_si_0/test_si aliases denote identical first-chain endpoint',
        candidate_preselection='Before final routing and exact; maximum three new PACT architectures',
        qualified_rows=len(qualified), measured_cycle_counts=[r['cycles'] for r in qualified],
        cycle_note='Actual chain lengths determine clock count; every method uses the same parallel shift/padding policy and patterns')


def aggregate(meta, design, output):
    if output.exists():
        raise ValueError('Preserve prior report; choose a fresh explicit output directory')
    protocol = admission.read(admission.INTAKE)
    family = next(r['family'] for r in protocol['cohort'] if r['design'] == design)
    physical, selection = physical_rows(meta, design)
    reference_hash = selection['reference_hash']
    rows = [row(meta, design, item, family, reference_hash) for item in physical]
    selected = admission.read(meta / f'baselines/{design}_selected.json')
    reference = next(r for r in rows if r['role'] == selected['method'])
    for r in rows:
        for metric, field in (('routed_scan_wirelength_um', 'delta_routed_WL_percent'),
                              ('E', 'delta_E_percent'), ('H4', 'delta_H4_percent'), ('H8', 'delta_H8_percent')):
            r[field] = 100*(r[metric]/reference[metric]-1) if r[metric] is not None else None
        r['dominated_by'] = [other['role'] for other in rows if dominates(other, r)]
        r['dominates'] = [other['role'] for other in rows if dominates(r, other)]
        r['pareto_status'] = ('DOMINATED' if r['dominated_by'] else 'NONDOMINATED') if r['qualification_status']=='QUALIFIED' else 'NOT_QUALIFIED'
    primary = next((r for r in rows if r['role'] == selection['primary_candidate']), None)
    classification = classify(primary, reference)
    competitors = [r for r in rows if r['method'] != 'PACT']
    dominated_by = [r['role'] for r in competitors if primary and dominates(r, primary)]
    dominates_list = [r['role'] for r in competitors if primary and dominates(primary, r)]
    mutual = [r['role'] for r in competitors if primary and primary['qualification_status']=='QUALIFIED'
        and r['qualification_status']=='QUALIFIED' and not dominates(r, primary) and not dominates(primary, r)]
    fair = validate_fairness(rows, meta, design)
    status = ('PACT_GATE09_COMPETITOR_DOMINANCE_OBSERVED' if dominated_by else
        'PACT_GATE09_MIXED_GENERALIZATION' if classification=='PACT_ACTIVITY_MIXED' else
        'PACT_GATE09_COMPETITIVE_COMPARISON_COMPLETE' if all(r['qualification_status']=='QUALIFIED' for r in rows) else
        'PACT_GATE09_INCONCLUSIVE')
    summary = dict(GATE09_STATUS=status, PACT_FROZEN=True, PACT_SHA='71b059d9d1a00735d79b6a428693eaba549a5f33',
        OPENROAD_SHA='08f67ee5ecd14db5a42be8c610bbfd1ccf079299',
        FAN_ATPG_SHA='4c253bfa613e5827f17c42a5fce8be7bea779e1e', ORFS_SHA='5e8b1450d19263f797a27c4f371b9dd19f32a3aa',
        CAPACITY_GATE='PASS_AT_EACH_HEAVY_STAGE', B14_REFERENCE_STATUS='QUALIFIED',
        BASELINES_IMPLEMENTED=['B0', 'B1', 'B2', 'B3T', 'B4', 'B5'],
        BASELINES_QUALIFIED=[r['role'] for r in competitors if r['qualification_status']=='QUALIFIED'],
        PACT_SEARCH_STATUS='SEARCH_COMPLETE', PACT_CANDIDATES_FROZEN=[r['candidate'] for r in selection['records']],
        COMMON_BACKEND_QUALIFIED=fair['status']=='PASS', ATPG_QUALIFIED=[r['role'] for r in rows if r['fault_coverage'] is not None],
        EXACT_ACTIVITY_QUALIFIED=[r['role'] for r in rows if r['E'] is not None],
        COMPETITIVE_RESULTS=classification, PARETO_RESULTS={r['role']:r['pareto_status'] for r in rows},
        PACT_DOMINATES=dominates_list, PACT_DOMINATED_BY=dominated_by, MUTUALLY_NONDOMINATED=mutual,
        GENERALIZATION_CLASSIFICATION='ONE_UNSEEN_BASE_FAMILY_MEASURED; no universal confirmation',
        COMPETITIVE_CLASSIFICATION=status, PR_NUMBER=None, PR_URL=None, MERGED=False, MERGED_SHA=None,
        WORKTREE_CLEAN=None, SCIENTIFIC_BLOCKERS=[r['role'] for r in rows if r['qualification_status']!='QUALIFIED'],
        NEXT_ACTION='Continue fixed cohort in preregistered order if capacity/runtime admission permits')
    report = dict(schema='pact_gate09_comparison_v1', created_utc=datetime.now(timezone.utc).isoformat(),
        design=design, primary_candidate=selection['primary_candidate'], reference_method=selected['method'],
        classification=classification, rows=rows, fairness=fair, summary=summary,
        frozen_method=admission.binding(references.BASE_META / 'manifests/competitive_method_definitions.json'),
        preselection=admission.binding(meta / f'selections/{design}/preselected_candidates.json'),
        source_preparation=admission.binding(meta / f'physical/{design}/preparation.json'),
        optional_competitors=admission.read(references.BASE_META / 'optional_competitor_discovery.json')['projects'],
        claims=dict(established='These design/method measurements and qualification receipts',
            observed=design+' at primary seed 11 and Nangate45',
            hypothesis='Any explanation of proxy/final differences requires follow-up after this campaign',
            not_established='Universal superiority, joules/power reduction, arbitrary scaling, independent evidence from related compositions'),
        no_proprietary_benchmarking=True, no_post_outcome_tuning=True)
    output.mkdir(parents=True)
    atomic_write(output / 'comparison.json', report, immutable=True)
    atomic_write(output / 'machine_summary.json', summary, immutable=True)
    render(report, output / 'report.md', protocol, meta)
    print('GATE09_COMPARISON', design, status, classification, flush=True)


def number(value, digits=3):
    return '—' if value is None else f'{value:.{digits}f}'


def render(report, path, protocol, meta):
    design, rows = report['design'], report['rows']
    prep = admission.read(meta / f'physical/{design}/preparation.json')
    search = admission.read(meta / f'searches/{design}/search_results.json')
    lines = [f'# Gate 09: {design} open-source comparison', '', '## A. Executive classification', '',
        report['summary']['GATE09_STATUS'], '',
        f"Primary PACT candidate: {report['primary_candidate']}. Activity classification: {report['classification']}. "
        'The complete four-objective Pareto comparison is retained below; alternative candidates do not replace the primary.', '',
        '## B. Admission', '', 'The fixed C≥6 GiB and D≥25 GiB floors passed before heavy stages. '
        'D also reserves 20 GiB plus max(5 GiB, the per-design retained/projected trace and count-cache allowance). '
        'The source and mapped all-state next-state equivalence, FF inventory, placement, route, extraction, '
        'timing, DRC, FAN workload and exact external-reference activity gates passed. '
        'The admitted source is pinned cad-polito-it/I99T, EUPL-1.2; this design was admitted as unseen in PACT campaigns.', '',
        '## C. Frozen methodology', '',
        'PACT source 71b059d9d1a00735d79b6a428693eaba549a5f33; qualified CPU continuation from merged PR #3. '
        'K=2, seed 11, epsilon 0.02/0.05/0.10, 900 seconds per mutation loop, 7200-second search worker ceiling. '
        'Max 20,000 evaluations, stagnation 2000, lane attempts 150, neighbors 16, segment 8, archive 16, '
        'equal E/H4/H8 weights, logic depth 3 with BUF/INV transparent. '
        'Initialize only from the frozen minimum-qualified-routed-WL B0/B1/B2/B3T reference. '
        'Balanced/best E/best H4/best H8 role selection, hash deduplication, at most three new candidates before final routing. '
        'An exact evaluation in flight may finish past a loop deadline. No tuning or extra seed was used.', '',
        '## D. Competitors', '']
    methods = admission.read(report['frozen_method']['path'])['methods']
    for name, definition in methods.items():
        lines.append(f'- **{name}**: '+definition.get('algorithm', definition.get('status', ''))+
            (' Source '+definition['source_SHA']+'.' if 'source_SHA' in definition else '')+
            (' Parameters '+json.dumps(definition['parameters'], sort_keys=True)+'.' if 'parameters' in definition else ''))
    lines += ['', 'B4 and B5 reuse the frozen phase0c A/J50 implementations, one architecture each. '
        'Their load-PPI mismatch is a proxy and does not optimize routed exact E directly. '
        'B3T is explicitly OPENROAD_QUALIFIED_PATCHED. All methods use the same qualified FAN generic circuit/reporter repair; '
        'the earlier b14 446-pattern workload was invalidated and preserved; each design uses its corrected common workload. '
        'Minimal probes, source patches, branch SHAs and failed attempts are retained. Upstream issue creation was attempted; '
        'GitHub returned 403 “Resource not accessible by integration,” so issue drafts remain saved.', '',
        '## E. Fairness', '', json.dumps(report['fairness'], indent=2), '',
        'Common mapped source, FF coordinates, positive-edge CK, SI/SO port policy, K=2, scan enable, '
        'FAN collapsed stuck-at workload, compression/X-fill policy, seed 11, two-thread OpenROAD routing, '
        'OpenRCX extraction, Nangate45 library, and one-worker CPU exact activity were held constant. '
        'Final timing is measured at the global-route stage; DRC is from detailed route. '
        'Routed scan WL is the frozen full scan-path net-length upper bound, including functional branches on shared nets.', '',
        '## F. Search', '',
        f"Search wall {number(search['wall_seconds'])} s, CPU {number(search['CPU_seconds'])} s, "
        f"peak process RSS {search['peak_RSS_KiB']} KiB, exact mutation evaluations {search['total_exact_mutation_evaluations']}. "
        'These mutation evaluator calls are distinct from final routed netlist replays. Search estimates remain in candidate receipts.']
    for lane in search['lanes']:
        receipt = admission.read(admission.resolve(lane['receipt']['path']))
        lines += [f"- ε={lane['epsilon']}: {receipt['evaluations']} exact mutations, termination {receipt['termination']}; "
            f"{receipt['attempts']} attempts, {receipt['accepted']} accepted."]
    lines += ['', '## G. Physical results', '', 'All physical outcomes appear in the primary table, including unsuccessful candidates. '
        'Every PACT route corresponds to a preselected architecture; none was hidden or chosen after final measurement.', '',
        '## H. ATPG', '',
        'The same fixed patterns and full collapsed-fault identity/weight/status contract were preserved by serial replay and repaired FAN simulation. '
        'Coverage is the measured stuck-at percentage; the campaign does not claim complete fault coverage.', '',
        f"Shared ATPG generation wall {number(prep['ATPG_execution']['wall_seconds'])} s; the authoritative execution receipt is "+
        prep['ATPG_execution']['stdout']['path']+'.', '',
        '## I. Exact activity', '', 'E sums capacitance-weighted settled transitions over all measured data nets. '
        'H4/H8 are the maximum per-cycle source-localized capacitance-weighted bin activity on 4×4/8×8 grids. '
        'OpenRCX ground capacitance plus Liberty sink capacitance is used; coupling is retained separately and excluded. '
        'These proxies are not joules. Full functional replay and every FF-Q/cycle crosscheck must pass.', '',
        '## J. Primary comparison', '',
        '| Design | Method | Scan WL µm | ΔWL % | E | ΔE % | H4 | ΔH4 % | H8 | ΔH8 % | WNS ns | Hold ns | DRC | FC % | Runtime s | Status |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in rows:
        values = [r[k] for k in ('routed_scan_wirelength_um', 'delta_routed_WL_percent', 'E', 'delta_E_percent',
            'H4', 'delta_H4_percent', 'H8', 'delta_H8_percent', 'WNS', 'hold_WNS', 'DRC', 'fault_coverage', 'runtime_seconds')]
        lines.append('| '+design+' | '+r['role']+' | '+' | '.join(number(v, 6 if i==9 else 3) for i,v in enumerate(values))+' | '+r['qualification_status']+' |')
    lines += ['', 'Deltas are relative to the frozen '+report['reference_method']+' reference. Runtime includes generation when measured, route, exact, and shared design search for PACT rows; '
        'the PACT search is charged once per design, not once for each candidate. Source preparation/ATPG are shared and reported separately. '
        'Peak RSS is the maximum process, not summed simultaneous memory. Per-stage CPU/wall/RSS receipts remain authoritative.', '',
        'Optional discovery outcomes:', '']
    for project in report['optional_competitors']:
        lines.append('- '+(project.get('repository_url') or project.get('source_url'))+': '+project['classification']+'. '+project['reason'])
    lines += ['', '## K. Pareto', '',
        'Dominance uses routed scan WL, E, H4, H8 with relative 1e-10 equality and at least one strict improvement. '
        'Timing, DRC, topology, preserved workload and exact replay remain hard qualification gates.', '',
        '| Method | Pareto state | Dominated by | Dominates |', '|---|---|---|---|']
    for r in rows:
        lines.append('| '+r['role']+' | '+r['pareto_status']+' | '+', '.join(r['dominated_by'])+' | '+', '.join(r['dominates'])+' |')
    lines += ['', 'Measured baseline contrasts (destination relative to source):', '',
        '| Source → destination | ΔScan WL % | ΔE % | ΔH4 % | ΔH8 % |',
        '|---|---:|---:|---:|---:|']
    by_role = {r['role']:r for r in rows}
    pairs = [('B0', method) for method in ('B1','B2','B3T','B4','B5')]
    if report['primary_candidate']:
        pairs += [(method, report['primary_candidate']) for method in ('B3T','B4','B5')]
    for source, destination in pairs:
        before, after = by_role[source], by_role[destination]
        values = [100*(after[k]/before[k]-1) if before['qualification_status']=='QUALIFIED'
                  and after['qualification_status']=='QUALIFIED' and before[k] else None for k in COSTS]
        lines.append('| '+source+' → '+destination+' | '+' | '.join(number(v) for v in values)+' |')
    lines += ['', 'These contrasts quantify physical-only ordering, the activity-only heuristic, the simple hybrid, '
        'and the preselected primary PACT result. A negative activity delta with positive wire delta is a trade-off. '
        'The four-objective dominance audit above determines superiority; these columns do not establish a causal mechanism.', '']
    lines += ['', '## L. Generalization', '',
        'Established: these fully qualified measurements on this unseen design. Observed: the recorded primary seed and Nangate45 behavior. '
        'Hypothesis: any explanation of proxy-to-final differences needs a later study. Not established: universal superiority, '
        'power reduction, guaranteed routed cost, arbitrary scaling, or four independent families from the composed cohort.', '',
        '## M. Limitations', '',
        'One primary seed, one technology and finite registered budgets. b14/b15 are the two base families; b17 derives from b15 and '
        'b18 combines b14/b17. Composition tests size scaling rather than independent-family replication. '
        'The activity model is zero-delay settled switching and capacitance proxies; it excludes glitches and coupling from the primary metric. '
        'The search uses a depth-3 stateful approximation and scan HPWL constraints, not a routed-wire guarantee. '
        'B6 search was bounded, and no claim is made that no other open implementation exists.', '',
        '## N. Next scientific step', '', report['summary']['NEXT_ACTION'], '',
        'The campaign-level recommendation and GitHub merge provenance will be recorded only after all admitted cohort outcomes are terminal.', '',
        '```json', json.dumps(report['summary'], indent=2), '```', '']
    path.write_text('\n'.join(lines))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--dependency-repair', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    meta, raw = references.repair_namespace(args.attempt, args.dependency_repair)
    aggregate(meta, args.design, args.output)
