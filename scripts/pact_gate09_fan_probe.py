#!/usr/bin/env python3
"""Preserve short FAN importer/build probes separately from campaign workloads."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import subprocess
import time

import pact_gate09_admission as admission
from pact_gate09_source_probe import require_capacity, META, RAW
from pact_experiment_receipts import atomic_write


def probe(binary, library, netlist, folder, commands):
    protocol = admission.read(admission.INTAKE)
    capacity = require_capacity(protocol)
    folder.mkdir(parents=True, exist_ok=False)
    script = folder / 'probe.script'
    script.write_text(f'read_lib {library}\nread_netlist {netlist}\n' + '\n'.join(commands) + '\nexit\n')
    sanitized = '/bin/dbg/' in str(binary)
    command = ([str(binary), '-f', str(script)] if sanitized else
               ['/usr/bin/stdbuf', '-oL', '-eL', str(binary), '-f', str(script)])
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    timed_out = False
    with (folder / 'stdout.txt').open('w') as out, (folder / 'stderr.txt').open('w') as err:
        process = subprocess.Popen(command, stdout=out, stderr=err,
                                   env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1'))
        try:
            code = process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            code = process.wait()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    record = dict(schema='pact_gate09_fan_diagnostic_v1', created_utc=datetime.now(timezone.utc).isoformat(),
                  command=command, binary=admission.binding(binary), library=admission.binding(library),
                  input=admission.binding(netlist), script=admission.binding(script), capacity=capacity,
                  exit_code=code, timed_out=timed_out, wall_seconds=time.perf_counter() - start,
                  CPU_seconds=after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                  peak_RSS_KiB=after.ru_maxrss, stdout=admission.binding(folder / 'stdout.txt'),
                  stderr=admission.binding(folder / 'stderr.txt'), PACT_search_started=False,
                  optimization_or_workload_generation='run_atpg' in commands)
    atomic_write(folder / 'execution.json', record, immutable=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--netlist', type=Path, required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--stage', choices=('import_build', 'faults_atpg', 'atpg'), default='import_build')
    args = parser.parse_args()
    if not args.attempt.replace('_', '').isalnum():
        raise ValueError('Unsafe attempt name')
    dest = RAW / 'dependency_probes' / 'fan' / args.attempt
    dest.mkdir(parents=True, exist_ok=False)
    fixture = dest / 'single_scan_ff.v'
    fixture.write_text('module single_scan_ff(CK, test_si, test_se, a, y, test_so);\n'
                       'input CK, test_si, test_se, a;\noutput y, test_so;\nwire d;\n'
                       'INV_X1 U_INV (.A(a), .ZN(d));\n'
                       'SDFF_X1 U_FF (.CK(CK), .D(d), .Q(y), .SE(test_se), .SI(test_si));\n'
                       'assign test_so = y;\nendmodule\n')
    records = {}
    cases = (
        ('single_scan_ff', fixture, ['report_netlist', 'build_circuit --frame 1', 'report_circuit']),
        ('source_import', args.netlist, ['report_netlist']),
        ('source_build', args.netlist, ['report_netlist', 'build_circuit --frame 1', 'report_circuit']))
    if args.stage in ('faults_atpg', 'atpg'):
        setup = ['report_netlist', 'build_circuit --frame 1', 'report_circuit', 'set_fault_type saf',
                 'add_fault --all']
        generate = setup + ['set_static_compression on', 'set_dynamic_compression on',
                            'set_X-Fill on', 'run_atpg', 'report_statistics']
        cases = [('single_scan_ff_atpg', fixture, generate), ('source_fault_setup', args.netlist, setup),
                 ('source_atpg', args.netlist, generate)]
        if args.stage == 'atpg':
            cases = [cases[0], cases[2]]
    for label, netlist, commands in cases:
        records[label] = probe(args.binary, args.library, netlist, dest / label, commands)
        print(label, records[label]['exit_code'], flush=True)
        print(Path(records[label]['stdout']['path']).read_text()[-3500:], flush=True)
        print(Path(records[label]['stderr']['path']).read_text()[-3500:], flush=True)
    result = dict(schema='pact_gate09_fan_probe_set_v1', attempt=args.attempt,
                  original_protocol=admission.binding(admission.INTAKE), harness=admission.binding(Path(__file__)),
                  results=records)
    atomic_write(META / 'dependency_probes' / ('fan_' + args.attempt + '.json'), result, immutable=True)


if __name__ == '__main__':
    main()
