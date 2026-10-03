#!/usr/bin/env python3
"""Answer frozen A1-A5 with exact implemented comparisons and explicit scope."""
import csv
from itertools import combinations

from pact_oss_benchmark import DESIGNS, write
from pact_oss_topology_stage_a import STAGE, gate, display as method_display
METHODS = {'B0', 'B1', 'B2', 'B3T', 'P0'}
from pact_oss_compare import OBJECTIVES, implemented_point, dominates


def delta(left, right):
    a, b = implemented_point(left), implemented_point(right)
    if a is None or b is None:
        return None
    return dict(left=left['architecture_hash'], right=right['architecture_hash'],
        left_method=left['method'], right_method=right['method'],
        left_method_display=method_display(left['method']), right_method_display=method_display(right['method']),
        **{name: x-y for name, x, y in zip(OBJECTIVES,a,b)},
        left_dominates=dominates(a,b), right_dominates=dominates(b,a))


def analyze(rows):
    result = {}
    for design in DESIGNS:
        data = [r for r in rows if r['design']==design]
        measured = [r for r in data if implemented_point(r) is not None]
        external = [r for r in measured if r['method']!='P0']
        p0 = [r for r in measured if r['method']=='P0']
        balanced = next((r for r in data if r['method']=='P0' and r['representative']=='True'), None)
        b3 = next((r for r in data if r['method']=='B3T'), None)
        b0 = next((r for r in data if r['method']=='B0'), None)
        a1 = [r['architecture_hash'] for r in p0
            if not any(dominates(implemented_point(other), implemented_point(r)) for other in measured)
            and not any(other['architecture_hash']==r['architecture_hash'] for other in external)]
        coordinate_unique = [r['architecture_hash'] for r in p0 if r['architecture_hash'] in a1
            and not any(implemented_point(other)==implemented_point(r) for other in external)]
        a2 = [delta(balanced, other) for other in external] if balanced else []
        a2 = [r for r in a2 if r is not None]
        for pair in a2:
            e, h = pair['measured_E'] < 0, pair['measured_H8'] < 0
            pair['activity_improvement'] = 'both' if e and h else ('E' if e else ('H8' if h else 'neither'))
        a3 = dict(B3T_vs_B0=delta(b3,b0) if b3 and b0 else None,
            B3T_vs_predeclared_P0=[delta(b3,r) for r in data if r['method']=='P0' and r['selected']=='True'] if b3 else [])
        a4 = []
        for left,right in combinations(external,2):
            if implemented_point(left)[0] == implemented_point(right)[0]:
                pair = delta(left,right)
                pair['physical_order']='equal_cost'
            else:
                low,high = sorted((left,right),key=lambda r:implemented_point(r)[0])
                pair=delta(low,high)
                pair['physical_order']='left_has_lower_wire'
            a4.append(pair)
        selected = [r for r in p0 if r['selected']=='True']
        unselected = [r for r in p0 if r['selected']!='True']
        a5 = dict(implemented_archive_points=len(p0), unmeasured_archive_points=len([r for r in data if r['method']=='P0'])-len(p0),
            unselected_archive_points_dominating_balanced=[delta(r,balanced) for r in unselected
                if balanced and implemented_point(balanced) and dominates(implemented_point(r),implemented_point(balanced))],
            unselected_archive_points_with_lower_H8_than_all_measured_selected=[
                dict(architecture_hash=r['architecture_hash'], versus_selected=[delta(r,s) for s in selected])
                for r in unselected if selected and all(implemented_point(r)[2]<implemented_point(s)[2] for s in selected)],
            scope='Only pre-existing implemented archive evidence is reused. Unmeasured archive points remain unknown; no search or outcome-based reselection.',
            causal_limit='A stronger known archive point can show a selection miss; this comparison alone cannot attribute that miss uniquely to H8 predictor incompleteness.')
        result[design]=dict(A1=dict(unique_nondominated_architectures=a1, coordinate_unique_nondominated_architectures=coordinate_unique,
            implemented_scope_only=True, mandatory_external_methods_complete={r['method'] for r in external}==METHODS-{'P0'}), A2=dict(pairwise_deltas=a2,
                comparable_cost_policy='All exact wire deltas shown; no invented matching tolerance'), A3=a3, A4=a4, A5=a5,
            qualified_external_methods=sorted({r['method'] for r in external}), qualified_P0_points=len(p0))
    return result


if __name__=='__main__':
    gate()
    rows=list(csv.DictReader((STAGE/'implemented_metrics.csv').open()))
    write(STAGE/'scientific_questions.json', analyze(rows))
    print('FROZEN_A1_A5_RECORDED', flush=True)

