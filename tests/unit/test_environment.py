from pathlib import Path
from pact.environment import ROOT, dependency_path, python_executable, relocate


def test_dependency_override_and_receipt_relocation(monkeypatch):
    monkeypatch.setenv('PACT_ORFS_ROOT', '/configured/orfs')
    monkeypatch.setenv('PACT_EXPERIMENT_ROOT', '/configured/runs')
    monkeypatch.setenv('PACT_PYTHON', '/configured/python')
    assert dependency_path('OpenROAD-flow-scripts/flow') == Path('/configured/orfs/flow')
    assert python_executable() == '/configured/python'
    receipt = {'path': '/mnt/c/old/checkouts/PACT/results/example/input.json',
               'nested': ['/root/pact-deps/OpenROAD-flow-scripts/flow',
                          '/mnt/d/PACT_EXPERIMENTS/results/example'], 'sha256': 'unchanged'}
    result = relocate(receipt)
    assert result['path'] == str(ROOT / 'results/example/input.json')
    assert result['nested'] == [str(Path('/configured/orfs/flow')), str(Path('/configured/runs/results/example'))]
    assert result['sha256'] == receipt['sha256'] == 'unchanged'
    assert receipt['path'].startswith('/mnt/c/')
