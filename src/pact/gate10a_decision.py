"""Frozen Gate 10A decision rules; input records are qualified delta evidence.

Relative deltas are fractions, absolute drop deltas are volts, and every delta
is candidate minus reference (positive means an increase). These functions do
not choose architectures, compute new physical outcomes, or fill unknowns.
The caller separately qualifies all nine selected architecture records and
supplies that result as the required ``evidence_complete`` flag.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping


MATERIAL_RELATIVE = 0.01
MATERIAL_ABSOLUTE_DROP_V = 0.0001
MAX_DYNAMIC_OR_CURRENT_REGRESSION = 0.01
MODEST_SCAN_WIRE_INCREASE = 0.02
SPATIAL_MIN_SPEARMAN = 0.5
REFERENCES = {"b14_opt": "B3T", "b15_opt": "B2"}
PACT_COMPARISONS = (("b14_opt", "CS_C1"), ("b14_opt", "CS_C3"),
                    ("b15_opt", "CS_C1"), ("b15_opt", "CS_C2"), ("b15_opt", "CS_C3"))
PRIMARY_COMPARISONS = (("b14_opt", "CS_C1"), ("b15_opt", "CS_C1"))
SPATIAL_RECORDS = tuple((design, method, resolution)
                       for design, reference in REFERENCES.items()
                       for method in (reference, "CS_C1") for resolution in (4, 8))
DELTA_FIELDS = ("delta_worst_ir_v", "delta_worst_ir_fraction", "delta_p99_ir_v",
                "delta_p99_ir_fraction", "delta_dynamic_power_fraction",
                "delta_peak_segment_current_fraction", "delta_routed_scan_wire_fraction")


def _finite(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None


def assess_comparison(row: Mapping) -> dict:
    """Evaluate symmetric voltage thresholds and the preregistered guardrails.

    A missing relative delta (for example a zero reference denominator) stays
    unavailable. Current guardrails require the measured peak absolute segment
    current; an optional unavailable density metric does not supply it.
    Adverse drop uses both worst and p99 voltage increases at the same absolute
    and relative thresholds as benefit, independently of the power guardrail.
    """
    values = {key: _finite(row.get(key)) for key in DELTA_FIELDS}
    missing = [key for key, value in values.items() if value is None]
    result = dict(design=row.get("design"), candidate=row.get("candidate"),
                  reference=row.get("reference"), deltas=values, missing_fields=missing,
                  material_pi_benefit=None, material_adverse_drop=None, modest_scan_wire_cost=None,
                  voltage_benefit=None, dynamic_guardrail_pass=None, current_guardrail_pass=None)
    if row.get("status") != "QUALIFIED":
        return dict(result, status="UNAVAILABLE", reason="comparison_not_qualified")
    if missing:
        return dict(result, status="UNAVAILABLE", reason="missing_or_invalid_required_delta")
    voltage_benefit = all(values[relative] <= -MATERIAL_RELATIVE and values[absolute] <= -MATERIAL_ABSOLUTE_DROP_V
                          for relative, absolute in (("delta_worst_ir_fraction", "delta_worst_ir_v"),
                                                     ("delta_p99_ir_fraction", "delta_p99_ir_v")))
    adverse = all(values[relative] >= MATERIAL_RELATIVE and values[absolute] >= MATERIAL_ABSOLUTE_DROP_V
                  for relative, absolute in (("delta_worst_ir_fraction", "delta_worst_ir_v"),
                                             ("delta_p99_ir_fraction", "delta_p99_ir_v")))
    dynamic = values["delta_dynamic_power_fraction"] <= MAX_DYNAMIC_OR_CURRENT_REGRESSION
    current = values["delta_peak_segment_current_fraction"] <= MAX_DYNAMIC_OR_CURRENT_REGRESSION
    result.update(status="AVAILABLE", reason=None, voltage_benefit=voltage_benefit,
                  dynamic_guardrail_pass=dynamic, current_guardrail_pass=current,
                  material_pi_benefit=voltage_benefit and dynamic and current,
                  material_adverse_drop=adverse,
                  modest_scan_wire_cost=values["delta_routed_scan_wire_fraction"] <= MODEST_SCAN_WIRE_INCREASE)
    return result


def spatial_correspondence(spatial_rows: Iterable[Mapping]) -> dict:
    """Require all eight primary/reference architecture/grid IR rank records.

    This implements the pre-outcome interpretation: the four architecture
    records are b14 B3T/CS_C1 and b15 B2/CS_C1, each at both 4x4 and 8x8.
    Rows are the primary mean-activity versus static-IR comparison only, using
    design,method,resolution,status,spearman_rho,reason. Legitimately constant
    or too-small domains have an evaluated but unmet correspondence criterion.
    Missing occupied measurements remain incomplete evidence.
    """
    required = set(SPATIAL_RECORDS)
    rows = {}
    for row in spatial_rows:
        key = (row.get("design"), row.get("method"), row.get("resolution"))
        if key not in required:
            continue
        if key in rows:
            raise ValueError("Duplicate registered spatial record")
        rows[key] = row
    details, incomplete = [], []
    for key in SPATIAL_RECORDS:
        row = rows.get(key)
        rho = None if row is None else _finite(row.get("spearman_rho"))
        reason = "missing_record" if row is None else row.get("reason")
        evaluated_undefined = (row is not None and row.get("status") == "UNAVAILABLE"
                               and reason in ("constant_vector", "fewer_than_three_bins"))
        evaluated = (row is not None and row.get("status") == "AVAILABLE" and rho is not None
                     and -1 <= rho <= 1) or evaluated_undefined
        if not evaluated:
            incomplete.append(dict(design=key[0], method=key[1], resolution=key[2], reason=reason or "invalid_statistic"))
        details.append(dict(design=key[0], method=key[1], resolution=key[2], spearman_rho=rho,
                            evaluated=bool(evaluated), criterion_pass=bool(evaluated and rho is not None and rho >= SPATIAL_MIN_SPEARMAN),
                            reason=reason))
    return dict(complete=not incomplete, passes=not incomplete and all(row["criterion_pass"] for row in details),
                required_records=len(SPATIAL_RECORDS), records=details, incomplete_records=incomplete,
                criterion="reference and CS_C1 in both designs at both grids; each primary IR Spearman >=0.5")


def classify_campaign(comparison_rows: Iterable[Mapping], spatial_rows: Iterable[Mapping],
                      *, evidence_complete: bool) -> dict:
    """Choose the exact frozen classification and development recommendation.

    ``evidence_complete`` includes source/model/flow qualification and all nine
    selected architecture records, including B5 controls. The five PACT
    comparison deltas and eight primary spatial IR records are validated here.
    No incomplete result is coerced into a scientific loss or into zero change.
    """
    if type(evidence_complete) is not bool:
        raise ValueError("Explicit complete-evidence Boolean required")
    required = set(PACT_COMPARISONS)
    rows = {}
    for row in comparison_rows:
        key = (row.get("design"), row.get("candidate"))
        if key not in required:
            continue  # B5 is a frozen control, not a PACT benefit candidate.
        if key in rows:
            raise ValueError("Duplicate registered PACT comparison")
        if row.get("reference") != REFERENCES[key[0]]:
            raise ValueError("PACT comparison reference differs from preregistration")
        rows[key] = assess_comparison(row)
    assessments, incomplete = [], []
    for key in PACT_COMPARISONS:
        row = rows.get(key)
        if row is None:
            incomplete.append(dict(design=key[0], candidate=key[1], reason="missing_comparison"))
        else:
            assessments.append(row)
            if row["status"] != "AVAILABLE":
                incomplete.append(dict(design=key[0], candidate=key[1], reason=row["reason"], missing_fields=row["missing_fields"]))
    spatial = spatial_correspondence(spatial_rows)
    if not evidence_complete:
        incomplete.append(dict(reason="selected_architecture_or_shared_method_evidence_incomplete"))
    incomplete.extend(spatial["incomplete_records"])
    if incomplete:
        classification, recommendation = "INCONCLUSIVE", "HOLD"
        rationale = "Incomplete or invalid required measurement evidence prevents the registered distinctions."
    else:
        primary = [rows[key] for key in PRIMARY_COMPARISONS]
        supported = all(row["material_pi_benefit"] and row["modest_scan_wire_cost"] for row in primary)
        any_benefit = any(row["material_pi_benefit"] for row in assessments)
        if supported:
            classification, recommendation = "PHYSICAL_IMPACT_SUPPORTED", "CONTINUE"
            rationale = "Both co-primary comparisons meet material PI benefit within the 2% scan-wire cost limit."
        elif any_benefit:
            classification = "PARTIAL_PHYSICAL_IMPACT"
            continue_partial = (any(row["material_pi_benefit"] and row["modest_scan_wire_cost"] for row in primary)
                                and not any(row["material_adverse_drop"] for row in primary))
            recommendation = "CONTINUE" if continue_partial else "PIVOT"
            rationale = ("A modest-cost co-primary material benefit exists and neither co-primary has symmetric material adverse drop."
                         if continue_partial else "Material benefit is limited to secondary/expensive comparisons or a co-primary has material adverse drop.")
        elif spatial["passes"]:
            classification, recommendation = "PROXY_CORRELATION_ONLY", "PIVOT"
            rationale = "No registered PACT material PI benefit; all eight spatial correspondence records meet the frozen rank criterion."
        else:
            classification, recommendation = "NO_MATERIAL_PHYSICAL_IMPACT", "FREEZE"
            rationale = "Complete admissible evidence meets neither the material PI benefit nor spatial correspondence criterion."
    return dict(classification="PACT_GATE10A_" + classification, recommendation=recommendation,
                rationale=rationale, evidence_complete=not incomplete, incomplete_records=incomplete,
                comparisons=assessments, spatial_correspondence=spatial,
                thresholds=dict(relative_drop_reduction=MATERIAL_RELATIVE,
                                absolute_drop_reduction_v=MATERIAL_ABSOLUTE_DROP_V,
                                maximum_dynamic_or_peak_current_regression=MAX_DYNAMIC_OR_CURRENT_REGRESSION,
                                modest_scan_wire_increase=MODEST_SCAN_WIRE_INCREASE,
                                minimum_spatial_spearman=SPATIAL_MIN_SPEARMAN),
                temporal_limit="activity-derived averaged power and static VDD IR; no transient or thermal validation")
