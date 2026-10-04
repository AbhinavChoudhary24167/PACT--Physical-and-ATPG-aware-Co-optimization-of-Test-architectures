"""Portable dependency locations and relocation of legacy execution receipts."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def dependency_root():
    return Path(os.environ.get('PACT_DEPENDENCY_ROOT', ROOT / 'external')).expanduser()


def dependency_path(name):
    variable = {'OpenROAD-flow-scripts': 'PACT_ORFS_ROOT', 'FAN_ATPG': 'PACT_FAN_ATPG_ROOT',
                'OpenROAD': 'PACT_OPENROAD_ROOT'}.get(name.split('/')[0])
    head, _, tail = name.partition('/')
    if variable and os.environ.get(variable):
        return Path(os.environ[variable]).expanduser() / tail
    return dependency_root() / name


def python_executable():
    return os.environ.get('PACT_PYTHON', sys.executable)


def relocate(value):
    """Relocate paths in old receipts without changing the on-disk evidence bytes."""
    if isinstance(value, dict):
        return {k: relocate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [relocate(v) for v in value]
    if not isinstance(value, str):
        return value
    normalized = value.replace('\\', '/')
    if normalized.startswith('repo://'):
        return str(ROOT / normalized[len('repo://'):])
    if normalized.startswith('dep://'):
        return str(dependency_path(normalized[len('dep://'):]))
    if normalized.startswith('run://'):
        from .experiment_storage import experiment_root
        return str(experiment_root() / normalized[len('run://'):])
    if normalized.startswith(('/mnt/c/', 'C:/')):
        for folder in ('artifacts', 'reports', 'results', 'src', 'scripts', 'tests', 'config', 'docs', 'experiments'):
            marker = '/' + folder + '/'
            if marker in normalized:
                return str(ROOT / folder / normalized.split(marker, 1)[1])
    if normalized.startswith('/root/pact-deps/'):
        return str(dependency_path(normalized[len('/root/pact-deps/'):]))
    if normalized.startswith('/mnt/d/PACT_EXPERIMENTS/'):
        from .experiment_storage import experiment_root
        return str(experiment_root() / normalized[len('/mnt/d/PACT_EXPERIMENTS/'):])
    return value
