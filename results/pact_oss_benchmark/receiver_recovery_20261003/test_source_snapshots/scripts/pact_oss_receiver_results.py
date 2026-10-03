#!/usr/bin/env python3
"""Join canonical identities to qualified common-backend outcomes; no selection."""
import csv
from pathlib import Path

from pact_oss_benchmark import read, write
from pact_oss_receiver_stage_a import STAGE, gate
from pact_oss_canonicalize import csv_write
from pact_oss_compare import OBJECTIVES, implemented_point, dominates, pareto_rows


def metric_row(item, route, measurement):
    result = dict(item, status='UNIMPLEMENTED', routed_scan_path_cost_um=None,
        measured_E=None, measured_H4=None, measured_H8=None, H4_peak_bin=None, H4_peak_cycle=None,
        H8_peak_bin=None, H8_peak_cycle=None, DRC=None, setup_WNS_ns=None, setup_TNS_ns=None,
        hold_WNS_ns=None, hold_TNS_ns=None, setup_violated_endpoints=None, hold_violated_endpoints=None,
        timing_stage='global_route', topology_qualification=None, functional_qualification=None,
        FF_transition_qualification=None, route_reused=None, measurement_reused=None,
        route_report=None, activity_summary=None)
    result.update(failure_stage=None, failure_reason=None)
    if route is None:
        return result
    report = route['report']
    result.update(status=report['status'], route_reused=route['reused'], route_report=route['report_binding']['path'],
        routed_scan_path_cost_um=report.get('routed_full_scan_path_net_length_upper_bound_um'),
        DRC=report.get('DRC_errors'))
    structured = report.get('structured_metrics', {})
    for name, key in (('setup_WNS_ns','setup_wns_ns'), ('setup_TNS_ns','setup_tns_ns'),
                      ('hold_WNS_ns','hold_wns_ns'), ('hold_TNS_ns','hold_tns_ns'),
                      ('setup_violated_endpoints','setup_violated_endpoints'), ('hold_violated_endpoints','hold_violated_endpoints')):
        result[name] = structured.get(key)
    result['topology_qualification'] = 'PASS' if report['status'] == 'QUALIFIED' else 'FAIL'
    if report['status'] != 'QUALIFIED':
        result.update(failure_stage=report.get('stage', 'postroute_qualification'), failure_reason=report['status'])
        return result
    if measurement is None:
        result['status'] = 'ACTIVITY_UNMEASURED' if report['status'] == 'QUALIFIED' else report['status']
        return result
    result['measurement_reused'] = measurement['reused']
    if measurement['status'] != 'QUALIFIED':
        result['status'] = measurement['status']
        result.update(failure_stage='measurement', failure_reason=measurement.get('error', measurement['status']))
        return result
    summary = read(measurement['summary']['path'])
    scope = summary['scopes']['all_data']
    result.update(status='QUALIFIED', measured_E=scope['cap_weighted_ff_transitions']['total'],
        functional_qualification='PASS', FF_transition_qualification='PASS', activity_summary=measurement['summary']['path'])
    for resolution in ('4','8'):
        grid = scope['grids'][resolution]
        result['measured_H' + resolution] = grid['cap_peak_per_cycle']['maximum']
        result['H' + resolution + '_peak_bin'] = grid['max_cap_bin']
        result['H' + resolution + '_peak_cycle'] = grid['max_cap_cycle']
    return result


def pairwise(rows):
    result = []
    for left in rows:
        a = implemented_point(left)
        if a is None:
            continue
        for right in rows:
            b = implemented_point(right)
            if b is None or left['design'] != right['design'] or left['architecture_hash'] == right['architecture_hash']:
                continue
            record = dict(design=left['design'], method=left['method'], architecture_hash=left['architecture_hash'],
                representative=left['representative'], selected=left['selected'], roles=left['roles'],
                versus_method=right['method'], versus_architecture_hash=right['architecture_hash'],
                versus_representative=right['representative'], dominates=dominates(a,b), dominated=dominates(b,a))
            for name, x, y in zip(OBJECTIVES, a, b):
                record[name + '_delta'] = x-y
                record[name + '_delta_percent'] = 100*(x-y)/y if y else None
            record['measured_H4_delta'] = float(left['measured_H4'])-float(right['measured_H4'])
            result.append(record)
    return result


def collect():
    gate()
    index = list(csv.DictReader((STAGE / 'architecture_index.csv').open()))
    rows = []
    for item in index:
        design, sha = item['design'], item['architecture_hash']
        routes = read(STAGE / 'routes' / (design + '.json'))['records']
        measurements = read(STAGE / 'measurements' / (design + '.json'))['records']
        rows.append(metric_row(item, routes.get(sha), measurements.get(sha)))
    fronts = pareto_rows(rows)
    representative = [row for row in fronts if row['representative']=='True']
    pairs = pairwise(rows)
    csv_write(STAGE / 'implemented_metrics.csv', list(rows[0]), rows)
    csv_write(STAGE / 'pareto_front.csv', list(fronts[0]), fronts)
    csv_write(STAGE / 'method_comparison.csv', list(representative[0]), representative)
    if pairs:
        csv_write(STAGE / 'pairwise_comparison.csv', list(pairs[0]), pairs)
    write(STAGE / 'comparison_policy.json', dict(objectives=list(OBJECTIVES), dominance='Exact, unweighted; no tolerance',
        missing_measurements='Unknown and excluded from implemented Pareto calculations',
        timing='Existing global-route setup/hold metrics; no new signoff analysis',
        representative='Original predicted minimax normalized-regret P0 role; never reselected',
        frontier='Original retained archive; unselected points contribute only existing qualified measurements',
        comparable_cost='Every pairwise physical-cost delta is retained; no post-outcome matching tolerance',
        all_data_scope=True, E_unit='fF.transitions', H4_H8_unit='fF.transitions per bin/cycle',
        selected_records=len([r for r in rows if r['selected']=='True']),
        qualified_selected_records=len([r for r in rows if r['selected']=='True' and r['status']=='QUALIFIED'])))
    print('STAGE_A_METRICS_COLLECTED', len(rows), flush=True)


if __name__ == '__main__':
    collect()
