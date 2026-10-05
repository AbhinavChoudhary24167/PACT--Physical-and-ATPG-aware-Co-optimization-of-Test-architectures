"""Read-only stage/progress diagnosis of a retained incomplete VCD.

Progress markers are execution observations only; they provide no transition,
activity or correctness qualification for an incomplete simulation.
"""
import argparse
from pathlib import Path
import re

from pact_generalization import ROOT, now, read, write, binding
from pact_cold_start_measure import OUT


def observed_vcd_progress(path, tail_bytes=8 * 1024**2):
    path = Path(path)
    marker = None
    scopes = []
    with path.open('rb') as stream:
        for raw in stream:
            parts = raw.decode('ascii').strip().split()
            if not parts:
                continue
            if parts[0] == '$scope':
                scopes.append(parts[2])
            elif parts[0] == '$upscope':
                scopes.pop()
            elif parts[0] == '$var' and scopes == ['tb'] and parts[4] == 'cycle_id':
                marker = parts[3]
            elif parts[0] == '$enddefinitions':
                break
        if marker is None:
            raise ValueError('No unambiguous tb.cycle_id progress marker')
        stream.seek(max(0, path.stat().st_size - tail_bytes))
        tail = stream.read().decode('ascii')
    encoded = [m.group(1) for m in re.finditer(r'(?:^|\n)b([01xz]+)\s+' + re.escape(marker) + r'(?=\s*(?:\n|$))', tail)]
    if any(set(v) - set('01') for v in encoded):
        raise ValueError('Unknown progress marker')
    cycles = [int(v, 2) for v in encoded]
    cycles = [v - (1 << 32) if v >= (1 << 31) else v for v in cycles]
    return dict(marker_symbol=marker, last_observed_cycle_id=cycles[-1] if cycles else None,
        largest_active_cycle_id_in_tail=max([c for c in cycles if c >= 0], default=None),
        tail_bytes_read=len(tail), observed_marker_events_in_tail=len(cycles),
        progress_is_not_correctness_qualification=True)


def diagnose_prior(receipt_path):
    receipt_path = Path(receipt_path).resolve()
    prior = read(receipt_path)
    vcd = Path(prior['partial_VCD']['path'])
    progress = observed_vcd_progress(vcd)
    record = dict(schema='pact_cold_start_retained_measurement_diagnosis_v1', timestamp_utc=now(),
        design=prior['design'], source_failure=binding(receipt_path), prior_cutoff_seconds=prior['wall_seconds_at_cutoff'],
        localized_stage=prior['localized_stage'], completed_stages=prior['completed_stages'],
        VCD_bytes=vcd.stat().st_size, VCD_binding=prior['partial_VCD'], intended_shift_cycles=prior['intended_shift_cycles'],
        execution_progress=progress, CPU_seconds=prior['CPU_seconds'], peak_RSS_KiB=prior['peak_RSS_KiB'],
        attribution='Simulation and VCD emission integrated; no parsing/transition/E/H stage executed',
        exact_metrics_available=False, scientific_method_change=False, additional_tool_executions=0,
        diagnosis_only=True, historical_core_used=False)
    write(OUT / f'scalability/measurement_prior_timeout_diagnosis_{prior["design"]}.json', record, immutable=True)
    print('RETAINED_TIMEOUT_DIAGNOSED', prior['design'], progress, flush=True)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', required=True, type=Path)
    diagnose_prior(parser.parse_args().receipt)
