#!/usr/bin/env python3
"""R0: supply the unused import-time optimizer dependency in isolated storage."""
from pact.environment import python_executable
from pact.experiment_storage import experiment_root
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pact_oss_topology as r
from pact_oss_benchmark import ROOT, binding, write

FOLDER = r.CAMPAIGN / 'stage_a_runtime'
EXTRA = r.DATA / 'stage_a_runtime/extra'
WHEELS = r.DATA / 'stage_a_runtime/wheels'
PYTHON = f'{python_executable()}'


def execute(command, label, env=None):
    result = subprocess.run(command, text=True, capture_output=True, env=env)
    log = FOLDER / (label+'.log')
    log.write_text(result.stdout+result.stderr)
    write(FOLDER / (label+'.execution.json'), dict(command=command, cwd=str(ROOT),
        returncode=result.returncode, log=binding(log), timestamp_utc=datetime.now(timezone.utc).isoformat()))
    return result


def main():
    r.ensure()
    FOLDER.mkdir(parents=True, exist_ok=True)
    code = 'import sys; sys.path.insert(0,"scripts"); import pact_solver_routes'
    first = execute(['/usr/bin/python3', '-c', code], 'system_python_import')
    second = execute([PYTHON, '-c', code], 'prior_venv_import')
    if "No module named 'scipy'" not in first.stderr or "No module named 'numba'" not in second.stderr:
        raise ValueError('Preserve and diagnose any different runtime failure')
    (FOLDER / 'ROOT_CAUSE.md').write_text('''# Stage-A runtime import blocker (R0)

The unchanged route adapter imports `pact.optimizer.io`, then `PlacedCosts`,
`phase2a_shift` (SciPy) and `optimizer.kernels` (Numba). System Python lacks
SciPy; the existing PACT virtual environment has the recorded NumPy 2.5.3 and
SciPy 1.18.1 but lacks the optional optimizer Numba dependency. These imports
occur before the route plan or any physical attempt is created. No optimizer
kernel is called by the route adapter.

Restore the existing PACT virtual environment and supply Numba 0.67.0 plus
llvmlite 0.49.0 in an owned D-backed import directory. Official Numba 0.67
supports NumPy 2.5: https://numba.readthedocs.io/en/latest/release/0.67.0-notes.html
No prior environment, algorithm, architecture, parameter, route command,
measurement source or common backend is changed. Wheels and versions are bound.
''')
    WHEELS.mkdir(parents=True, exist_ok=True)
    packages = ['numba==0.67.0', 'llvmlite==0.49.0']
    download = execute([PYTHON, '-m', 'pip', 'download', '--only-binary=:all:', '--no-deps',
        '--dest', str(WHEELS), *packages], 'download')
    if download.returncode:
        raise RuntimeError('Dependency download failed; see preserved receipt')
    wheels = sorted(WHEELS.glob('*.whl'))
    install = execute([PYTHON, '-m', 'pip', 'install', '--no-deps', '--target', str(EXTRA),
        *map(str, wheels)], 'install')
    if install.returncode:
        raise RuntimeError('Isolated dependency installation failed')
    env = dict(os.environ, PYTHONPATH=str(EXTRA))
    check = execute([PYTHON, '-c', code+'; import numpy,scipy,numba,llvmlite,json; '
        'print(json.dumps(dict(numpy=numpy.__version__,scipy=scipy.__version__,numba=numba.__version__,llvmlite=llvmlite.__version__)))'],
        'qualified_import', env)
    if check.returncode:
        raise RuntimeError('Full frozen route adapter import still fails')
    versions = json.loads(check.stdout.splitlines()[-1])
    if versions['numpy'] != '2.5.3' or versions['scipy'] != '1.18.1':
        raise ValueError('Prior recorded numerical libraries must remain unchanged')
    write(FOLDER / 'runtime.json', dict(repair_class='R0', source_change=False, runtime=PYTHON,
        extra_pythonpath=str(EXTRA), versions=versions, wheels=[binding(p) for p in wheels],
        qualified_import=binding(FOLDER / 'qualified_import.execution.json'),
        prior_environment=binding(ROOT / 'results/phase2c_repair_multiseed/environment.json'),
        original_venv_modified=False, optimizer_kernels_called=False, architecture_or_flow_change=False))
    print('STAGE_A_RUNTIME_QUALIFIED', versions, flush=True)


if __name__ == '__main__':
    main()
