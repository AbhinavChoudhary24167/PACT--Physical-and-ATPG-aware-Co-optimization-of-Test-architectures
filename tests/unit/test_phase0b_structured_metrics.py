import pytest

from pact.physical.phase0b_structured_metrics import extract_structured_metrics


def sample():
    grt = {
        "globalroute__timing__setup__ws": 1.0,
        "globalroute__timing__setup__tns": 0,
        "globalroute__timing__hold__ws": 0.1,
        "globalroute__timing__hold__tns": 0,
        "globalroute__timing__drv__setup_violation_count": 0,
        "globalroute__timing__drv__hold_violation_count": 0,
        "globalroute__timing__drv__max_slew": 0,
        "globalroute__timing__drv__max_cap": 0,
        "globalroute__timing__drv__max_fanout": 0,
        "globalroute__global_route__wirelength": 12,
    }
    drt = {"detailedroute__route__wirelength": 10,
           "detailedroute__route__drc_errors": 0,
           "detailedroute__route__vias": 5}
    return grt, drt


def test_missing_congestion_remains_unavailable():
    grt, drt = sample()
    observed = extract_structured_metrics(grt, drt)
    assert observed["congestion"] is None
    assert observed["congestion_classification"] == "UNAVAILABLE_IN_STRUCTURED_METRICS"
    assert observed["total_detailed_route_wirelength_um"] == 10


def test_structured_congestion_is_used_when_present():
    grt, drt = sample()
    grt["globalroute__route__congestion"] = 0.25
    observed = extract_structured_metrics(grt, drt)
    assert observed["congestion"] == 0.25


def test_missing_required_timing_is_rejected():
    grt, drt = sample()
    del grt["globalroute__timing__setup__ws"]
    with pytest.raises(ValueError):
        extract_structured_metrics(grt, drt)
