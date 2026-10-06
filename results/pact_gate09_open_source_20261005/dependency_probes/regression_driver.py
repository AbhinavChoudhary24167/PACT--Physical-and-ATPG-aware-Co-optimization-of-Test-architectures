import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
ROOT = Path('/mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT')
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
from pact_gate09_source_probe import require_capacity, RAW
from pact_experiment_receipts import atomic_write
repo = Path('/root/pact-deps/FAN_ATPG-gate09-crash-repair')
attempt, mode = sys.argv[1:]
folder = RAW / 'dependency_probes' / 'fan' / attempt
folder.mkdir(parents=True, exist_ok=False)
capacity = require_capacity(admission.read(admission.INTAKE))
(repo / 'tests').mkdir(exist_ok=True)
for source, target in [('fan_compound_scan.v', 'compound_scan.v'), ('fan_compound_circuit_test.cpp', 'compound_circuit_test.cpp')]:
    original = ROOT / 'scratch' / source
    destination = repo / 'tests' / target
    if destination.exists():
        assert admission.binding(destination)['sha256'] == admission.binding(original)['sha256']
    else:
        shutil.copy2(original, destination)
    shutil.copy2(original, folder / target)
binary = repo / 'tests' / ('compound_circuit_test_' + mode)
command = ['g++', '-std=c++11', '-g', '-O1' if mode == 'dbg' else '-O3', '-I' + str(repo / 'include'),
           str(repo / 'tests/compound_circuit_test.cpp'), '-L' + str(repo / 'lib' / mode), '-lcore', '-linterface', '-lcommon', '-o', str(binary)]
if mode == 'dbg':
    command.extend(['-fsanitize=address,undefined', '-fno-omit-frame-pointer'])
records = []
for label, cmd in [('compile', command), *[(test, [str(binary), str(repo / 'techlib/mod_nangate45.mdt'),
                       str(repo / 'tests/compound_scan.v'), test]) for test in ('depth', 'arity', 'truth')]]:
    start = time.perf_counter()
    completed = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                               env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1'))
    (folder / (label + '.stdout.txt')).write_text(completed.stdout)
    (folder / (label + '.stderr.txt')).write_text(completed.stderr)
    records.append(dict(label=label, command=cmd, exit_code=completed.returncode, wall_seconds=time.perf_counter() - start,
                        stdout=admission.binding(folder / (label + '.stdout.txt')),
                        stderr=admission.binding(folder / (label + '.stderr.txt'))))
    print(label, completed.returncode, completed.stdout, completed.stderr[:500], flush=True)
    if label == 'compile' and completed.returncode:
        break
record = dict(capacity=capacity, mode=mode, results=records,
              source_SHA=admission.command(['git', '-C', str(repo), 'rev-parse', 'HEAD']),
              patch=admission.command(['git', '-C', str(repo), 'diff', '--', 'pkg/core/src/circuit.cpp']),
              tests=[admission.binding(folder / name) for name in ('compound_circuit_test.cpp', 'compound_scan.v')])
atomic_write(folder / 'execution.json', record, immutable=True)
atomic_write(ROOT / 'results/pact_gate09_open_source_20261005/dependency_probes' / (attempt + '.json'), record, immutable=True)
