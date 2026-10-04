#!/usr/bin/env python3
"""Exact Stage-B measured comparisons and a public report without local receipts."""
import argparse
import csv
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from pact.optimizer.io import read, write_json
from pact_stage_b import DESIGNS, STAGE_A, METRICS, gate
from pact_oss_receiver_results import metric_row

OBJECTIVES = ('routed_scan_path_cost_um', 'measured_E', 'measured_H4', 'measured_H8')


def point(row, four=True):
    keys = OBJECTIVES if four else (OBJECTIVES[0], OBJECTIVES[1], OBJECTIVES[3])
    return np.array([float(row[k]) for k in keys])


def dominates(a, b):
    return bool(np.all(a <= b) and np.any(a < b))


def relation(a, b):
    return 'dominating' if dominates(a, b) else ('dominated' if dominates(b, a) else 'nondominated')


def write_csv(path, rows):
    if not rows:
        return
    with Path(path).open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def table(rows):
    if not rows:
        return 'No qualifying results.\n'
    keys = list(rows[0])
    lines = ['| '+' | '.join(keys)+' |', '| '+' | '.join(['---']*len(keys))+' |']
    for row in rows:
        lines.append('| '+' | '.join(str(row[k]) for k in keys)+' |')
    return '\n'.join(lines)+'\n'


def report(output, public):
    gate()
    public.mkdir(parents=True, exist_ok=True)
    baseline = list(csv.DictReader((STAGE_A/'implemented_metrics.csv').open()))
    indexed = list(csv.DictReader((output/'architecture_index.csv').open()))
    measured, before, searches, comparisons, good, partial = [], [], [], [], [], []
    private = []
    for design in DESIGNS:
        selected = read(output/'selection'/f'{design}.json')
        names = {r['architecture_sha256']: f'{design}_C{i+1}' for i, r in enumerate(selected)}
        for path in sorted((output/design).glob('budget_*/search.json')):
            run = read(path)
            searches.append(dict(design=design, epsilon=run['config']['epsilon'],
                reference=run['reference_label'], search_s=round(run['search_seconds'], 3),
                command_s=round(run['runtime_seconds'], 3), evaluations=run['evaluations'],
                screened=run['screened_infeasible'], accepted=run['accepted'], termination=run['termination']))
            for i, r in enumerate(run['selected']):
                before.append(dict(design=design, epsilon=run['config']['epsilon'],
                    candidate=names.get(r['architecture_sha256'], f'{design}_budget_{run["config"]["epsilon"]:.2f}_winner_{i+1}'),
                    roles=';'.join(r['roles']), new=r['new'], proxy_wire_um=r['metrics']['wire_um'],
                    proxy_E=r['metrics']['E_stateful_ff'], proxy_H4=r['metrics']['H4_stateful_ff'],
                    proxy_H8=r['metrics']['H8_stateful_ff']))
        routes = read(output/'routes'/f'{design}.json')['records']
        measurements = read(output/'measurements'/f'{design}.json')['records']
        physical = min((r for r in baseline if r['design']==design and r['method'] in ('B2', 'B3T')),
                       key=lambda r: float(r['routed_scan_path_cost_um']))
        for item in (r for r in indexed if r['design']==design):
            sha = item['architecture_hash']
            r = metric_row(item, routes.get(sha), measurements.get(sha))
            private.append(r)
            label = names[sha]
            row = dict(design=design, candidate=label, epsilon=float(item['epsilon']), reference=physical['method'],
                status=r['status'], scan_wire_um=r['routed_scan_path_cost_um'], E=r['measured_E'],
                H4=r['measured_H4'], H8=r['measured_H8'], DRC=r['DRC'],
                setup_WNS_ns=r['setup_WNS_ns'], setup_TNS_ns=r['setup_TNS_ns'],
                hold_WNS_ns=r['hold_WNS_ns'], hold_TNS_ns=r['hold_TNS_ns'],
                topology=r['topology_qualification'], functional=r['functional_qualification'],
                FF_transition=r['FF_transition_qualification'])
            if r['status']=='QUALIFIED':
                a = point(r)
                row['routed_wire_overhead_percent'] = 100*(a[0]/float(physical['routed_scan_path_cost_um'])-1)
                row['routed_budget_pass'] = bool(a[0] <= float(physical['routed_scan_path_cost_um'])*(1+float(item['epsilon'])))
                all_base = [b for b in baseline if b['design']==design and b['status']=='QUALIFIED']
                row['Stage_A_front_3_objectives'] = 'dominated' if any(dominates(point(b, False), point(r, False)) for b in all_base) else 'nondominated'
                row['Stage_A_front_4_objectives'] = 'dominated' if any(dominates(point(b), a) for b in all_base) else 'nondominated'
                for b in (b for b in all_base if b['method'] in ('B2','B3T') or (b['method']=='P0' and b['representative']=='True')):
                    pct = 100*(a/point(b)-1)
                    comparisons.append(dict(design=design, candidate=label, versus=b['method'],
                        wire_percent=float(pct[0]), E_percent=float(pct[1]), H4_percent=float(pct[2]), H8_percent=float(pct[3]),
                        dominance_Stage_A=relation(point(r, False), point(b, False)), dominance_with_H4=relation(a, point(b))))
                activity_delta = a[1:]/point(physical)[1:]-1
                if row['routed_budget_pass'] and np.all(activity_delta < 0):
                    good.append(design)
                elif row['routed_budget_pass'] and activity_delta[0]<0 and np.any(activity_delta[1:]<0):
                    partial.append(design)
            else:
                row.update(routed_wire_overhead_percent=None, routed_budget_pass=None,
                    Stage_A_front_3_objectives='unknown', Stage_A_front_4_objectives='unknown')
            measured.append(row)
    status = ('PACT_STAGE_B_MULTI_DESIGN_CONVERGENCE' if len(set(good))==3 else
              'PACT_STAGE_B_PARTIAL_CONVERGENCE' if good else
              'PACT_STAGE_B_ROUTED_ACTIVITY_ADVANCE' if partial else 'PACT_STAGE_B_NO_ADVANCE')
    write_json(output/'private_measured_results.json', private)
    write_json(output/'classification.json', dict(status=status, simultaneous_improvement_designs=sorted(set(good)),
        partial_improvement_designs=sorted(set(partial)), qualified=sum(r['status']=='QUALIFIED' for r in measured),
        criteria='Multi-design convergence requires a measured candidate per design with E,H4,H8 all strictly lower than routed-best B2/B3T and routed wire within its configured epsilon.'))
    write_csv(public/'search_configuration.csv', searches)
    write_csv(public/'candidate_results.csv', before)
    write_csv(public/'routed_results.csv', measured)
    write_csv(public/'comparison.csv', comparisons)
    # Export reviewable architectures with neutral names; private receipts retain hashes.
    for design in DESIGNS:
        for i, r in enumerate(read(output/'selection'/f'{design}.json')):
            arch = json.loads(Path(r['architecture']).read_text())
            write_json(public/'architectures'/f'{design}_C{i+1}.json', arch)
    routed_view = [{k: r[k] for k in ('design','candidate','epsilon','scan_wire_um','E','H4','H8','DRC','setup_WNS_ns','hold_WNS_ns','routed_budget_pass')} for r in measured]
    pre_view = [{k: round(r[k], 4) if isinstance(r[k], float) else r[k] for k in
        ('design','epsilon','candidate','roles','new','proxy_wire_um','proxy_E','proxy_H4','proxy_H8')} for r in before]
    pair_view = [{k: round(r[k], 6) if isinstance(r[k], float) else r[k] for k in r} for r in comparisons]
    lines = ['# PACT Stage-B constrained method-convergence report', '', '## 1. Status', '', status, '',
        'Convergence requires measured E, H4 and H8 improvements against the routed-best B2/B3T reference under the actual routed wire budget. Scalar search scores do not establish superiority.', '',
        '## 2. What changed', '',
        'Added a separate constrained search using the existing candidate-stateful evaluator. Physical cost is a hard feasibility condition. Geometry screens infeasible proposals before waveform updates. Four activity lanes retain E, H4, H8 and balanced winners separately. Fixed-capacity mutation operators, bounded archive and independent final replay are reused. The exact B3T chain-capacity permutation is preserved. No external repair or frozen-method change was made.', '',
        '## 3. Optimization formulation', '',
        '`W_proxy(a) <= (1 + epsilon) W_proxy(reference)`, with epsilon in {0.02, 0.05, 0.10}. Reference selection minimizes frozen routed scan-path cost among B2 and B3T. W_proxy is port-inclusive Manhattan scan HPWL.', '',
        'Within feasibility, three lanes minimize E, H4 and H8. The balanced lane minimizes `sum(w_i metric_i/reference_i)/sum(w_i)` for E,H4,H8 with common weights (1,1,1). Raw quantities remain separate. Source positions, three logic levels, ground-plus-pin capacitance, fixed buffer skeleton and FAN workload follow the existing model.', '',
        'Search feasibility does not imply routed feasibility. Routed scan wire is the frozen full connected scan-net length upper bound including shared functional branches; detailed-route total wire is a different quantity. Routed budget acceptance is independently recorded.', '',
        '## 4. Search configuration', '',
        'Starts: exact frozen B2, B3T and balanced P0; infeasible starts cannot seed search. Seed 11, K=2, 16 neighbors, segment limit 8, 16 archive slots, lane restart every 150 attempts. Each budget has a 300-second mutation-loop ceiling, 20,000 exact-evaluation ceiling and 2,000-attempt no-improvement window. Initialization and retained-candidate replay are additional recorded command time. Weights and operators are shared across designs. A pre-route selection deduplicates across budgets and allows at most three new architectures per design.', '',
        table(searches), '## 5. Candidate results before routing', '', table(pre_view),
        '## 6. Routed/extracted Stage-B results', '',
        'Unchanged Nangate45/ORFS flow, placement, backend, routing seed 11 and two route cores. E uses all-data extracted ground plus pin capacitance and the frozen simulation schedule. Timing fields are global-route values; TNS and structural/functional/FF results are in routed_results.csv.', '', table(routed_view),
        '## 7. Comparison against B2/B3T/P0', '',
        'Percentages use full precision measured values: 100*(candidate/reference-1). P0 denotes the original frozen balanced representative. Negative deltas improve the corresponding metric.', '', table(pair_view),
        '## 8. Pareto interpretation', '',
        'Both exact frozen Stage-A dominance (wire,E,H8) and the expanded set (wire,E,H4,H8) are shown in comparison.csv and routed_results.csv. Front membership compares every qualified measured Stage-A point, including nonrepresentative P0 points. Unmeasured points remain unknown.', '',
        '## 9. Generalization across the three designs', '',
        'Simultaneous bounded improvements: '+(', '.join(sorted(set(good))) or 'none')+'. Partial E/hotspot improvements: '+(', '.join(sorted(set(partial))) or 'none')+'. All three designs remain included.', '',
        '## 10. Failures and limitations', '',
        'The physical estimate constrains scan edges but measured scan cost contains shared fanout, buffers and routed detours. The stateful activity predictor has bounded logic coverage and a fixed baseline buffer skeleton. Hotspot ties and routing-induced load/location changes can prevent proxy improvements from transferring. Search is local and finite; a negative result does not prove infeasibility. s15850 is retained as the difficult case, with its measured deltas and runtime shown above. No watts, IR-drop or signoff-power claim follows from these switching proxies.', '',
        '## 11. External/tool bugs encountered', '',
        'No new external repair was required by this Stage-B implementation. Previously qualified B3T repairs remain frozen Stage-A dependencies. Scientific reproduction receipts and source/configuration hashes stay in private experiment storage; public artifacts contain neutral architecture labels and relative links.', '',
        '## 12. Next action', '',
        ('Repeat the same frozen method on an additional physical context to test transfer before expanding claims.' if len(set(good))==3 else
         'Use these selected measured pairs to isolate proxy-to-route error on the resistant design, then test the smallest activity/load or move-operator correction indicated by the failing metrics. Preserve the present measured campaign as its comparator.'), '']
    (public/'REPORT.md').write_text('\n'.join(lines))
    print(status, 'qualified', sum(r['status']=='QUALIFIED' for r in measured), flush=True)


if __name__=='__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--public', type=Path, default=ROOT/'results/pact_stage_b')
    args = p.parse_args()
    report(args.output, args.public)
