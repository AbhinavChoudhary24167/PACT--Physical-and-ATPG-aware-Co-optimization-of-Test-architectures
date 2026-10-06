from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from pact_gate09_report import dominates, classify
from pact_gate09_campaign_report import classify_campaign


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


def test_generalization_does_not_turn_qualification_or_admission_holds_into_confirmation():
    report = dict(primary_candidate='CS_C1', reference_method='B3T',
        rows=[dict(role='CS_C1', qualification_status='QUALIFIED')],
        classification='PACT_ACTIVITY_IMPROVEMENT_ALL_COORDINATES',
        summary=dict(PACT_DOMINATES=[], PACT_DOMINATED_BY=[]))
    status, generalization = classify_campaign([report], [], ['b14','b15'])
    assert status == 'PACT_GATE09_MIXED_GENERALIZATION'
    assert generalization == 'PACT_GATE09_UNSEEN_QUALIFICATION_OBSERVED_WITHIN_FIXED_COHORT'
    report['summary']['PACT_DOMINATES'] = ['B3T','B4','B5']
    assert classify_campaign([report], [], ['b14','b15'])[0] == 'PACT_GATE09_COMPETITIVE_GENERALIZATION_CONFIRMED'
    assert classify_campaign([report], [dict(status='SOURCE_ADMISSION_HOLD')], ['b14','b15'])[1] == 'PACT_GATE09_INCONCLUSIVE_RESOURCE_OR_ADMISSION_LIMITED'
    report['summary']['PACT_DOMINATED_BY'] = ['B2']
    assert classify_campaign([report], [], ['b14','b15'])[0] == 'PACT_GATE09_COMPETITOR_DOMINANCE_OBSERVED'
