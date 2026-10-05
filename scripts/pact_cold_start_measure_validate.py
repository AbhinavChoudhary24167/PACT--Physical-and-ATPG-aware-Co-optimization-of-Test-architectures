"""Validate additive timers against existing qualified unseen waveforms only."""
import argparse
import os
from pathlib import Path
import shutil
import sys

from pact_generalization import ROOT, now, read, sha, write
from pact_generalization_infrastructure import external_binding
from pact_cold_start_measure import RUN, OUT
from pact_cold_start_measure_analyze import analyze_instrumented
import numpy as np


def validate_retained(source):
    source = Path(source)
    manifest_path = source.parents[1] / 'manifest.json'
    original_manifest = read(manifest_path)
    entry = next(r for r in original_manifest['rows'] if r['design'] == source.parent.name and r['role'] == source.name)
    root = RUN / 'measurement_validation' / entry['design']
    folder = root / entry['design'] / entry['role']
    if (root / 'manifest.json').exists():
        raise ValueError('Preserve previous validation: ' + str(root))
    for gate in ('topology_verification.json', 'functional_verification.json', 'FF_transition_crosscheck.json'):
        if read(source / gate)['status'] != 'PASS':
            raise ValueError('Retained unseen measurement was not qualified')
    expected = read(source / 'activity_summary.json')
    if sha(source / 'activity.vcd') != expected['VCD']['sha256']:
        raise ValueError('Retained VCD hash mismatch')
    folder.mkdir(parents=True, exist_ok=True)
    for name in ('net_mapping.json', 'workload.json', 'cycles.json', 'extracted.spef'):
        shutil.copy2(source / name, folder / name)
    # Read-only reanalysis; hardlink shares the existing retained bytes without
    # copying gigabytes. The analyzer never writes its VCD input.
    os.link(source / 'activity.vcd', folder / 'activity.vcd')
    write(root / 'manifest.json', dict(rows=[entry], source_manifest=external_binding(manifest_path)), immutable=True)
    resources = analyze_instrumented(folder)
    actual = read(folder / 'activity_summary.json')
    with np.load(source / 'transitions.npz') as original, np.load(folder / 'transitions.npz') as instrumented:
        np.testing.assert_array_equal(original['names'], instrumented['names'])
        np.testing.assert_array_equal(original['counts'], instrumented['counts'])
        exact_count_entries = int(original['counts'].size)
    if actual != expected:
        raise AssertionError('Instrumented exact activity summary differs from retained qualified result')
    if read(folder / 'FF_transition_crosscheck.json') != read(source / 'FF_transition_crosscheck.json'):
        raise AssertionError('Independent exact FF crosscheck changed')
    data = actual['scopes']['all_data']
    receipt = dict(status='PASS', design=entry['design'], role=entry['role'], timestamp_utc=now(),
        source=external_binding(source / 'activity_summary.json'), source_VCD=external_binding(source / 'activity.vcd'),
        source_transitions=external_binding(source / 'transitions.npz'), exact_net_cycle_counts_compared=exact_count_entries,
        FF_transition_crosscheck='byte-equivalent decoded JSON', complete_activity_summary='exact decoded JSON equality',
        E=data['cap_weighted_ff_transitions']['total'], H4=data['grids']['4']['cap_peak_per_cycle']['maximum'],
        H8=data['grids']['8']['cap_peak_per_cycle']['maximum'], tolerance=0,
        engineering_change='timer context/decorator insertion only; original executable AST preserved after removal',
        additional_simulations=0, additional_routes=0, historical_designs_used=[], analysis_instrumentation=resources)
    write(OUT / f'scalability/measurement_validation/{entry["design"]}.json', receipt, immutable=True)
    print('EXACT_INSTRUMENTATION_VALIDATED', entry['design'], exact_count_entries, receipt['E'], receipt['H4'], receipt['H8'], flush=True)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    validate_retained(parser.parse_args().source)
