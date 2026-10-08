"""Synthetic threshold controls for the frozen decision, never final results."""
from copy import deepcopy

import pytest

from pact import gate10a_decision as decision


def comparison(design, candidate, *, benefit=False):
    sign = -1 if benefit else 0
    return dict(design=design, candidate=candidate, reference=decision.REFERENCES[design], status="QUALIFIED",
                delta_worst_ir_v=sign * 0.0001, delta_worst_ir_fraction=sign * 0.01,
                delta_p99_ir_v=sign * 0.0001, delta_p99_ir_fraction=sign * 0.01,
                delta_dynamic_power_fraction=0.01, delta_peak_segment_current_fraction=0.01,
                delta_routed_scan_wire_fraction=0.02)


def comparisons():
    return [comparison(design, candidate) for design, candidate in decision.PACT_COMPARISONS]


def spatial_rows(rho=0.5):
    return [dict(design=design, method=method, resolution=resolution,
                 status="AVAILABLE", spearman_rho=rho, reason=None)
            for design, method, resolution in decision.SPATIAL_RECORDS]


def classify(rows, spatial=None, **kwargs):
    return decision.classify_campaign(rows, spatial_rows() if spatial is None else spatial,
                                      evidence_complete=kwargs.get("evidence_complete", True))


def test_material_thresholds_are_inclusive_and_both_voltage_metrics_required():
    row = comparison("b14_opt", "CS_C1", benefit=True)
    result = decision.assess_comparison(row)
    assert result["material_pi_benefit"] is True
    assert result["modest_scan_wire_cost"] is True
    for field in ("delta_worst_ir_fraction", "delta_p99_ir_fraction"):
        changed = dict(row, **{field: -0.009999999})
        assert decision.assess_comparison(changed)["material_pi_benefit"] is False
    for field in ("delta_worst_ir_v", "delta_p99_ir_v"):
        changed = dict(row, **{field: -0.000099999999})
        assert decision.assess_comparison(changed)["material_pi_benefit"] is False
    for field in ("delta_dynamic_power_fraction", "delta_peak_segment_current_fraction"):
        assert decision.assess_comparison(dict(row, **{field: 0.010000001}))["material_pi_benefit"] is False
    assert decision.assess_comparison(dict(row, delta_routed_scan_wire_fraction=0.020000001))["modest_scan_wire_cost"] is False


def test_supported_requires_both_primaries_at_modest_cost():
    rows = comparisons()
    for row in rows:
        if (row["design"], row["candidate"]) in decision.PRIMARY_COMPARISONS:
            row.update(comparison(row["design"], row["candidate"], benefit=True))
    result = classify(rows)
    assert result["classification"] == "PACT_GATE10A_PHYSICAL_IMPACT_SUPPORTED"
    assert result["recommendation"] == "CONTINUE"
    rows[0]["delta_routed_scan_wire_fraction"] = 0.03
    result = classify(rows)
    assert result["classification"] == "PACT_GATE10A_PARTIAL_PHYSICAL_IMPACT"
    assert result["recommendation"] == "CONTINUE"  # other primary remains modest


def test_secondary_only_and_expensive_primary_benefits_recommend_pivot():
    rows = comparisons()
    rows[1] = comparison("b14_opt", "CS_C3", benefit=True)
    result = classify(rows)
    assert result["classification"] == "PACT_GATE10A_PARTIAL_PHYSICAL_IMPACT"
    assert result["recommendation"] == "PIVOT"
    rows = comparisons()
    rows[0] = comparison("b14_opt", "CS_C1", benefit=True)
    rows[0]["delta_routed_scan_wire_fraction"] = 0.021
    assert classify(rows)["recommendation"] == "PIVOT"


def test_partial_continue_requires_no_symmetric_co_primary_adverse_drop():
    rows = comparisons()
    rows[0] = comparison("b14_opt", "CS_C1", benefit=True)
    assert classify(rows)["recommendation"] == "CONTINUE"
    adverse = rows[2]
    adverse.update(delta_worst_ir_v=0.0001, delta_worst_ir_fraction=0.01,
                   delta_p99_ir_v=0.0001, delta_p99_ir_fraction=0.01)
    assert decision.assess_comparison(adverse)["material_adverse_drop"] is True
    assert classify(rows)["recommendation"] == "PIVOT"
    adverse["delta_p99_ir_v"] = 0.000099
    assert decision.assess_comparison(adverse)["material_adverse_drop"] is False
    assert classify(rows)["recommendation"] == "CONTINUE"


def test_complete_spatial_criterion_uses_all_eight_records_and_threshold():
    result = classify(comparisons())
    assert result["classification"] == "PACT_GATE10A_PROXY_CORRELATION_ONLY"
    assert result["recommendation"] == "PIVOT"
    assert result["spatial_correspondence"]["required_records"] == 8
    spatial = spatial_rows()
    spatial[-1]["spearman_rho"] = 0.49999999
    result = classify(comparisons(), spatial)
    assert result["classification"] == "PACT_GATE10A_NO_MATERIAL_PHYSICAL_IMPACT"
    assert result["recommendation"] == "FREEZE"
    spatial[-1].update(status="UNAVAILABLE", spearman_rho=None, reason="constant_vector")
    result = classify(comparisons(), spatial)
    assert result["classification"] == "PACT_GATE10A_NO_MATERIAL_PHYSICAL_IMPACT"
    assert result["evidence_complete"] is True


@pytest.mark.parametrize("invalid", [None, float("nan"), float("inf"), True, ""])
def test_missing_current_is_never_coerced_to_zero_or_a_scientific_loss(invalid):
    rows = comparisons()
    rows[0] = comparison("b14_opt", "CS_C1", benefit=True)
    rows[0]["delta_peak_segment_current_fraction"] = invalid
    result = classify(rows)
    assert result["classification"] == "PACT_GATE10A_INCONCLUSIVE"
    assert result["recommendation"] == "HOLD"
    assert result["comparisons"][0]["material_pi_benefit"] is None


def test_missing_comparison_spatial_record_and_qualification_all_hold():
    assert classify(comparisons()[:-1])["recommendation"] == "HOLD"
    assert classify(comparisons(), spatial_rows()[:-1])["recommendation"] == "HOLD"
    assert classify(comparisons(), evidence_complete=False)["recommendation"] == "HOLD"
    rows = comparisons()
    rows[0]["status"] = "RESOURCE_HOLD"
    assert classify(rows)["recommendation"] == "HOLD"
    spatial = spatial_rows()
    spatial[0].update(status="UNAVAILABLE", spearman_rho=None, reason="missing_occupied_domain_measurements")
    assert classify(comparisons(), spatial)["recommendation"] == "HOLD"


def test_control_benefit_does_not_count_as_pact_benefit_and_reference_is_fixed():
    rows = comparisons()
    rows.append(comparison("b14_opt", "B5", benefit=True))
    assert classify(rows)["classification"] == "PACT_GATE10A_PROXY_CORRELATION_ONLY"
    rows[0]["reference"] = "B5"
    with pytest.raises(ValueError, match="reference differs"):
        classify(rows)


def test_duplicate_records_and_nonboolean_completion_fail_closed():
    rows = comparisons()
    with pytest.raises(ValueError, match="Duplicate registered PACT"):
        classify(rows + [deepcopy(rows[0])])
    spatial = spatial_rows()
    with pytest.raises(ValueError, match="Duplicate registered spatial"):
        classify(rows, spatial + [deepcopy(spatial[0])])
    with pytest.raises(ValueError, match="Boolean"):
        decision.classify_campaign(rows, spatial, evidence_complete="true")
