import json
import os
from pathlib import Path
import resource
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
command = ['make', '-j2', 'install', 'MODE=' + mode]
if mode == 'dbg':
    command.append('CFLAGS=-Wall -g -O1 -fsanitize=address,undefined -fno-omit-frame-pointer')
start = time.perf_counter()
before = resource.getrusage(resource.RUSAGE_CHILDREN)
with (folder / 'stdout.txt').open('w') as out, (folder / 'stderr.txt').open('w') as err:
    completed = subprocess.run(command, cwd=repo, stdout=out, stderr=err, timeout=600)
after = resource.getrusage(resource.RUSAGE_CHILDREN)
record = dict(command=command, cwd=str(repo), source_SHA=admission.command(['git', '-C', str(repo), 'rev-parse', 'HEAD']),
              tracked_diff=admission.command(['git', '-C', str(repo), 'diff', '--', 'pkg']),
              capacity=capacity, exit_code=completed.returncode, wall_seconds=time.perf_counter() - start,
              CPU_seconds=after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
              peak_RSS_KiB=after.ru_maxrss, stdout=admission.binding(folder / 'stdout.txt'),
              stderr=admission.binding(folder / 'stderr.txt'), harness=admission.binding(Path(__file__)))
binary = repo / 'bin' / mode / 'fan'
if completed.returncode == 0:
    record['binary'] = admission.binding(binary)
atomic_write(folder / 'execution.json', record, immutable=True)
atomic_write(ROOT / 'results/pact_gate09_open_source_20261005/dependency_probes' / (attempt + '.json'), record, immutable=True)
print(json.dumps(record, indent=2), flush=True)
raise SystemExit(completed.returncode)
