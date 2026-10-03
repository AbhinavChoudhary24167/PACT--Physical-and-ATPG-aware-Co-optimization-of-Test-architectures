#!/usr/bin/env python3
"""Expose existing route, capacitance and waveform measurements without reruns."""
import csv
import json
import math
from pathlib import Path

from pact_oss_benchmark import binding, read, write
import pact_oss_topology_stage_a as stage


def augment(original):
    def metric_row(item, route, measurement):
        result = original(item, route, measurement)
        extra = dict(total_detailed_route_wirelength_um=None, global_route_wirelength_um=None,
            exact_scan_only_routed_length_um=None, global_route_overflow=None, congestion=None,
            layer_utilization=None, all_data_ground_pin_capacitance_fF=None,
            scan_data_ground_pin_capacitance_fF=None, all_data_incident_coupling_fF=None,
            all_data_transitions=None, scan_data_transitions=None, scan_data_E=None,
            scan_data_H4=None, scan_data_H8=None, patterns=None, shift_cycles=None,
            missing_static_capacitance_nets=None, capacitance_table=None, spatial_bins=None)
        if route:
            report = route['report']
            metrics = report.get('structured_metrics', {})
            for name in ('total_detailed_route_wirelength_um', 'global_route_wirelength_um',
                         'global_route_overflow', 'congestion'):
                extra[name] = metrics.get(name)
            extra['exact_scan_only_routed_length_um'] = report.get('exact_scan_only_routed_length_um')
            extra['layer_utilization'] = json.dumps(metrics.get('layer_utilization', {}), sort_keys=True)
        if measurement and measurement['status'] == 'QUALIFIED':
            summary = read(measurement['summary']['path'])
            for name in ('patterns', 'shift_cycles'):
                extra[name] = summary[name]
            for scope in ('all_data', 'scan_data'):
                extra[scope+'_transitions'] = summary['scopes'][scope]['transitions']['total']
            scan = summary['scopes']['scan_data']
            extra['scan_data_E'] = scan['cap_weighted_ff_transitions']['total']
            extra['scan_data_H4'] = scan['grids']['4']['cap_peak_per_cycle']['maximum']
            extra['scan_data_H8'] = scan['grids']['8']['cap_peak_per_cycle']['maximum']
            extra['missing_static_capacitance_nets'] = len(summary['missing_static_caps'])
            extra['spatial_bins'] = measurement['spatial_bins']['path']
            table = Path(measurement['folder']) / 'net_activity_capacitance.csv'
            if table.exists():
                caps = list(csv.DictReader(table.open()))
                for scope in ('all_data', 'scan_data'):
                    selected = [r for r in caps if scope == 'all_data' or r['scope_scan_data'] == 'True']
                    expected = summary['scopes'][scope]
                    transitions = sum(int(r['transitions']) for r in selected)
                    energy = sum(int(r['transitions'])*float(r['ground_pin_ff']) for r in selected if r['ground_pin_ff'])
                    if len(selected) != expected['nets'] or transitions != expected['transitions']['total'] or not math.isclose(
                            energy, expected['cap_weighted_ff_transitions']['total'], rel_tol=1e-10, abs_tol=1e-6):
                        raise ValueError('Capacitance table does not reproduce the qualified waveform summary')
                    extra[scope+'_ground_pin_capacitance_fF'] = sum(float(r['ground_pin_ff']) for r in selected if r['ground_pin_ff'])
                extra['all_data_incident_coupling_fF'] = sum(float(r['incident_coupling_ff']) for r in caps if r['incident_coupling_ff'])
                extra['capacitance_table'] = str(table)
        return dict(result, **extra)
    return metric_row


def main():
    _, results = stage.configure_modules()
    results.metric_row = augment(results.metric_row)
    results.collect()
    rows = list(csv.DictReader((stage.STAGE / 'implemented_metrics.csv').open()))
    bindings = {}
    for row in rows:
        for name in ('capacitance_table', 'spatial_bins'):
            if row[name]:
                bindings[row[name]] = binding(row[name])
    write(stage.STAGE / 'additional_measurement_policy.json', dict(
        source='Existing frozen detailed-route/OpenRCX/Icarus measurements; no flow change or rerun',
        primary_scope='all_data', capacitance='Sum of extracted ground and Liberty sink pin capacitance over mapped data nets',
        static_nets='Missing unswitched parasitics remain excluded and counted explicitly',
        incident_coupling='Sum over incident mapped-net coupling; may double-count coupling between mapped nets; excluded from E/H4/H8',
        routed_scan_cost='Full connected net length upper bound because functional and scan fanout share Q nets',
        exact_scan_only='Unknown when any shared functional fanout prevents an exclusive scan attribution',
        congestion='Only fields supplied by frozen structured metrics; absent fields remain unknown',
        timing='Global-route timing; detailed-route signoff timing was not part of the frozen flow',
        bindings=bindings))


if __name__ == '__main__':
    main()
