from pathlib import Path
import os
import subprocess
import sys
import time
ROOT = Path('/mnt/c/Users/Abhinav/OneDrive/Desktop/PACT/PACT')
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
from pact_gate09_source_probe import RAW, META
from pact_experiment_receipts import atomic_write
folder = RAW / 'dependency_probes/runtime_import'
folder.mkdir(parents=True, exist_ok=False)
script = folder / 'import.py'
script.write_text('import pact\nfrom pathlib import Path\n'
                  f'assert Path(pact.__file__).resolve() == Path("{ROOT}/src/pact/__init__.py").resolve()\n'
                  'print("PASS frozen pact package resolution", pact.__file__)\n')
records = []
for label, fixed in [('without_path', False), ('with_registered_path', True)]:
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    if fixed:
        environment['PYTHONPATH'] = str(ROOT / 'src') + ':' + str(ROOT / 'scripts')
    start = time.perf_counter()
    result = subprocess.run(['/usr/bin/openroad', '-python', '-no_init', '-exit', str(script)],
                            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
    for stream in ('stdout', 'stderr'):
        (folder / (label + '.' + stream + '.txt')).write_text(getattr(result, stream))
    record = dict(label=label, exit_code=result.returncode, wall_seconds=time.perf_counter()-start,
        PYTHONPATH=environment.get('PYTHONPATH'), script=admission.binding(script),
        binary=admission.binding('/usr/bin/openroad'),
        stdout=admission.binding(folder / (label + '.stdout.txt')),
        stderr=admission.binding(folder / (label + '.stderr.txt')))
    records.append(record)
assert records[0]['exit_code'] != 0 and records[1]['exit_code'] == 0
atomic_write(META / 'dependency_probes/runtime_import.json', dict(
    status='QUALIFIED_GENERIC_RUNTIME_MODULE_PATH_REPAIR', records=records,
    scope='Set explicit source and script module roots for child OpenROAD Python launches',
    source_changes=0, PACT_method_changes=0, competitor_algorithm_changes=0,
    routing_executions=0, ATPG_generations=0), immutable=True)
print('PASS independent missing-path reproducer and explicit-path recovery', flush=True)
