"""Outcome joins must preserve failures and unknown activity measurements."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from pact_oss_compare import implemented_point
from pact_oss_results import metric_row


def item():
    return dict(design='s5378', method='B2', architecture_hash='a', representative='True', selected='True', roles='single_solution')


def route(status='QUALIFIED'):
    return dict(report=dict(status=status, DRC_errors=0, routed_full_scan_path_net_length_upper_bound_um=100,
        structured_metrics=dict(setup_wns_ns=9, hold_wns_ns=.001)), reused=False,
        report_binding=dict(path='route_result.json'))


def test_unimplemented_remains_unknown():
    row = metric_row(item(), None, None)
    assert row['status'] == 'UNIMPLEMENTED'
    assert row['measured_E'] is None and implemented_point(row) is None


def test_routed_without_activity_is_excluded_from_frontier():
    row = metric_row(item(), route(), None)
    assert row['status'] == 'ACTIVITY_UNMEASURED'
    assert row['routed_scan_path_cost_um'] == 100
    assert row['measured_H8'] is None and implemented_point(row) is None


def test_physical_failure_cannot_be_overridden_by_activity_record():
    row = metric_row(item(), route('POSTROUTE_FAILED'), dict(status='QUALIFIED', reused=True))
    assert row['status'] == 'POSTROUTE_FAILED'
    assert row['topology_qualification'] == 'FAIL' and implemented_point(row) is None


def test_measurement_failure_preserves_physical_diagnostics():
    row = metric_row(item(), route(), dict(status='MEASUREMENT_FAILED', reused=False, error='capture pattern mismatch'))
    assert row['status'] == 'MEASUREMENT_FAILED'
    assert row['DRC'] == 0 and row['setup_WNS_ns'] == 9 and row['hold_WNS_ns'] == .001
    assert row['measured_E'] is None and implemented_point(row) is None
    assert row['failure_stage'] == 'measurement' and row['failure_reason'] == 'capture pattern mismatch'
