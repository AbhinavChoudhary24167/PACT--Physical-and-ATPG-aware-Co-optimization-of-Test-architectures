"""Strict, stage-labelled metrics from ORFS/OpenROAD JSON records."""
from __future__ import annotations

from typing import Any


def extract_structured_metrics(grt: dict[str, Any], drt: dict[str, Any]) -> dict[str, object]:
    required_grt = {
        "setup_wns_ns": "globalroute__timing__setup__ws",
        "setup_tns_ns": "globalroute__timing__setup__tns",
        "hold_wns_ns": "globalroute__timing__hold__ws",
        "hold_tns_ns": "globalroute__timing__hold__tns",
        "setup_violated_endpoints": "globalroute__timing__drv__setup_violation_count",
        "hold_violated_endpoints": "globalroute__timing__drv__hold_violation_count",
        "max_slew_violations": "globalroute__timing__drv__max_slew",
        "max_cap_violations": "globalroute__timing__drv__max_cap",
        "max_fanout_violations": "globalroute__timing__drv__max_fanout",
        "global_route_wirelength_um": "globalroute__global_route__wirelength",
    }
    required_drt = {
        "total_detailed_route_wirelength_um": "detailedroute__route__wirelength",
        "detailed_route_drc_errors": "detailedroute__route__drc_errors",
        "detailed_route_vias": "detailedroute__route__vias",
    }
    missing = [key for key in required_grt.values() if key not in grt]
    missing += [key for key in required_drt.values() if key not in drt]
    if missing:
        raise ValueError(f"Required structured ORFS metrics absent: {missing}")
    data = {label: grt[key] for label, key in required_grt.items()}
    data.update({label: drt[key] for label, key in required_drt.items()})
    overflow_keys = ("globalroute__global_route__overflow", "globalroute__route__overflow")
    congestion_keys = ("globalroute__global_route__congestion", "globalroute__route__congestion")
    data.update({
        "timing_stage": "global_route",
        "global_route_overflow": next((grt[key] for key in overflow_keys if key in grt), None),
        "congestion": next((grt[key] for key in congestion_keys if key in grt), None),
        "congestion_classification": ("STRUCTURED_AVAILABLE" if any(key in grt for key in congestion_keys)
                                      else "UNAVAILABLE_IN_STRUCTURED_METRICS"),
        "layer_utilization": {key: value for key, value in grt.items() if "layer_utilization" in key},
        "pdnsim_classification": "NOT_RUN_NO_QUALIFIED_TEST_CURRENT_MODEL",
    })
    return data
