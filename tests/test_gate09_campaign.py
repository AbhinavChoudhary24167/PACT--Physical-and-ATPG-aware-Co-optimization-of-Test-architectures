import inspect
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pact_gate09_campaign as campaign
import pact_gate09_competitor_measure as competitor


def test_registered_budget_bridge_changes_only_the_two_preregistered_lines():
    import pact_cold_start as cold
    original = inspect.getsource(cold.search)
    adapted = campaign.budget_adapter(cold.search)
    before, after = original.splitlines(), adapted.splitlines()
    differences = [(a, b) for a, b in zip(before, after) if a != b]
    assert len(before) == len(after)
    assert len(differences) == 2
    assert differences[0][1].strip() == 'seconds=900'
    assert 'runtime_policy=' in differences[1][1]
    assert 'solver.optimize' in adapted and 'select(design)' in adapted


def test_missing_complete_exact_reference_blocks_optimization(tmp_path):
    with pytest.raises(FileNotFoundError):
        campaign.require_exact_reference(tmp_path, 'not_admitted')


def test_common_measurement_extension_rejects_unqualified_candidate(monkeypatch):
    adapted = competitor.namespace()
    def read(path):
        if path.name == 'presearch_qualification.json':
            return dict(status='INFRASTRUCTURE_QUALIFIED')
        if path.name == 'd_B4.json':
            return dict(method='B4', status='FAILED')
        return {}
    monkeypatch.setattr(competitor.frozen.admission, 'read', read)
    with pytest.raises(ValueError, match='Only qualified routes'):
        adapted['reference_row'](Path('/metadata'), Path('/raw'), 'd', 'B4')
