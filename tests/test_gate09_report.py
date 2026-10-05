from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from pact_gate09_report import dominates, classify


def candidate(w, e, h4, h8, status='QUALIFIED'):
    return dict(routed_scan_wirelength_um=w, E=e, H4=h4, H8=h8, qualification_status=status)


def test_four_objective_dominance_retains_tradeoffs_and_excludes_failed_rows():
    base = candidate(100, 100, 100, 100)
    activity = candidate(101, 90, 90, 90)
    assert not dominates(activity, base) and not dominates(base, activity)
    assert dominates(candidate(100, 90, 90, 90), base)
    assert not dominates(candidate(99, 90, 90, 90, 'FAILED'), base)
    assert not dominates(candidate(100, 100-1e-9, 100, 100), base)


def test_classification_never_promotes_alternative_or_ignores_mixed_activity():
    base = candidate(100, 100, 100, 100)
    assert classify(candidate(102, 90, 110, 95), base) == 'PACT_ACTIVITY_MIXED'
    assert classify(candidate(102, 90, 90, 90), base) == 'PACT_ACTIVITY_IMPROVEMENT_ALL_COORDINATES'
    assert classify(None, base) == 'PACT_NO_NEW_PRESELECTED_ARCHITECTURE'
