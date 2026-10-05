#!/usr/bin/env python3
"""Measure equivalent independent reference scores in isolated processes."""
import argparse
import json
from pathlib import Path
import resource
import sys
import time
from pact_generalization import ROOT, read, write, binding, now
from pact.optimizer.cold_start import load
from pact.optimizer.candidate_stateful import reference as full
from pact.optimizer.cpu_reference import reference as bounded

OUT = ROOT/'results/pact_cpu_scalability_20261005/reference'


def worker(backend):
    began = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_SELF)
    manifest = ROOT/'results/pact_cold_start_unseen_20261004/inputs/s35932/cold_start_input.json'
    model, starts, _ = load(manifest)
    initialized = time.perf_counter()
    score = (full if backend == 'full' else bounded)(model,starts[0][1])
    after = resource.getrusage(resource.RUSAGE_SELF)
    write(OUT/f'{backend}.json',dict(status='PASS',backend=backend,witness='s35932',created_utc=now(),input=binding(manifest),
        initial_order_only=True,scientific_semantics='Original independent simultaneous-state oracle; all patterns and cycles',
        score=score.tolist(),wall_seconds=time.perf_counter()-began,reference_seconds=time.perf_counter()-initialized,
        CPU_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,peak_RSS_KiB=after.ru_maxrss),immutable=True)
    print('CPU_REFERENCE_COMPLETE',backend,score.tolist(),after.ru_maxrss,flush=True)


def compare():
    import numpy as np
    left,right = read(OUT/'full.json'),read(OUT/'bounded.json')
    np.testing.assert_allclose(left['score'],right['score'],rtol=1e-9,atol=1e-6)
    write(OUT/'equivalence.json',dict(status='PASS',registered_tolerance=dict(rtol=1e-9,atol=1e-6),
        full=left,bounded=right,absolute_errors=np.abs(np.asarray(left['score'])-right['score']).tolist()),immutable=True)
    print('CPU_REFERENCE_EQUIVALENCE_PASS',flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('full','bounded','compare'))
    args = parser.parse_args()
    compare() if args.stage == 'compare' else worker(args.stage)
