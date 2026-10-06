"""Synthetic controls only; never inspect architecture power/IR outcomes."""
import math

import pytest

from pact import gate10a_spatial as spatial
from pact.physical_effect import spatial_bin


BOUNDS = [0.0, 0.0, 40.0, 40.0]


def test_frozen_coordinate_mapping_boundaries_and_axis_order():
    grid = spatial.grid_metadata(BOUNDS, 4)
    assert grid["bins"][6] == dict(bin_id=6, bx=2, by=1, bounds_um=[20, 10, 30, 20])
    controls = [([0, 0], 0), ([10, 0], 1), ([0, 10], 4), ([20, 10], 6), ([40, 40], 15)]
    for point, expected in controls:
        assert spatial_bin(point, BOUNDS, 4) == expected
        result = spatial.aggregate_points([dict(id="n", x_um=point[0], y_um=point[1], value=1)],
                                          BOUNDS, 4, reduction="sum", unit="W")
        assert result["values"][expected] == 1
        assert sum(result["values"]) == 1
    with pytest.raises(ValueError, match="outside die"):
        spatial.aggregate_points([dict(id="n", x_um=-1, y_um=0, value=1)], BOUNDS, 4,
                                 reduction="sum", unit="W")


def test_regional_activity_is_weighted_mean_not_peak_or_raw_total():
    rows = [dict(net="b", x_um=5, y_um=5, transitions="4", ground_pin_ff="3"),
            dict(net="a", x_um=5, y_um=5, transitions="2", ground_pin_ff="2"),
            dict(net="c", x_um=40, y_um=40, transitions="10", ground_pin_ff="1"),
            dict(net="static", x_um=20, y_um=20, transitions="0", ground_pin_ff="")]
    result = spatial.regional_activity(rows, BOUNDS, 2, 4)
    assert result["values"][0] == 8
    assert result["values"][15] == 5
    assert sum(result["total_cap_ff_transitions"]) == 26
    assert result["total_transitions"][0] == 6
    assert result["missing_static_caps"] == ["static"]
    assert result == spatial.regional_activity(reversed(rows), BOUNDS, 2, 4)
    rows[-1]["transitions"] = "1"
    with pytest.raises(ValueError, match="Switched net missing"):
        spatial.regional_activity(rows, BOUNDS, 2, 4)


def test_sum_power_and_max_ir_have_distinct_empty_region_semantics():
    points = [dict(id="z", x_um=0, y_um=0, value=3), dict(id="a", x_um=0, y_um=0, value=1)]
    power = spatial.aggregate_points(points, BOUNDS, 4, reduction="sum", unit="W")
    ir = spatial.aggregate_points(points, BOUNDS, 4, reduction="maximum", unit="V")
    assert power["values"] == [4] + [0] * 15
    assert ir["values"] == [3] + [None] * 15
    assert ir["support_counts"] == [2] + [0] * 15
    assert ir["missing_bin_ids"] == list(range(1, 16))
    points.append(dict(id="missing", x_um=0, y_um=0, value=None))
    assert spatial.aggregate_points(points, BOUNDS, 4, reduction="sum", unit="W")["values"][0] is None
    incomplete = spatial.aggregate_points(points[:2], BOUNDS, 4, reduction="sum", unit="W", complete_inventory=False)
    assert incomplete["values"] == [None] * 16
    assert incomplete["diagnostic_finite_aggregates"][0] == 4


def test_powered_domain_removes_empty_and_physical_only_bins_without_value_selection():
    rows = [dict(id="logic", x_um=0, y_um=0, powered=True, physical_only=False),
            dict(id="tap", x_um=10, y_um=0, powered=True, physical_only=True),
            dict(id="unpowered", x_um=0, y_um=10, powered=False, physical_only=False),
            dict(id="logic2", x_um=20, y_um=0, powered=True, physical_only=False)]
    domain = spatial.powered_domain(rows, BOUNDS, 4)
    assert domain["bin_ids"] == [0, 2]
    assert domain["support_counts"] == [1, 0, 1] + [0] * 13
    rows[0].pop("physical_only")
    with pytest.raises(KeyError):
        spatial.powered_domain(rows, BOUNDS, 4)


def test_source_origin_crosscheck_preserves_ports_and_rejects_cell_centers():
    nets = [dict(net="n", source="hier/cell/Q", x_um=2, y_um=3),
            dict(net="p", source="PORT/input", x_um=0, y_um=0)]
    instances = [dict(id="hier/cell", x_um=2, y_um=3)]
    result = spatial.crosscheck_source_origins(nets, instances)
    assert result["checked_source_nets"] == 1
    assert result["external_input_nets"] == ["p"]
    instances[0]["x_um"] = 2.1
    with pytest.raises(ValueError, match="source-origin mismatch"):
        spatial.crosscheck_source_origins(nets, instances)


def test_positive_inverse_and_nonlinear_correlations_report_both_statistics():
    x = list(range(16))
    same = spatial.compare_regions(x, [2 * value + 5 for value in x], range(16))["primary"]
    assert same["pearson_r"] == pytest.approx(1)
    assert same["spearman_rho"] == pytest.approx(1)
    assert same["hotspot_iou"] == 1
    assert same["hotspot_k"] == 4
    opposite = spatial.compare_regions(x, list(reversed(x)), range(16))["primary"]
    assert opposite["pearson_r"] == pytest.approx(-1)
    assert opposite["spearman_rho"] == pytest.approx(-1)
    assert opposite["hotspot_iou"] == 0
    nonlinear = spatial.compare_regions(x, [value**2 for value in x], range(16))["primary"]
    assert nonlinear["pearson_r"] < 1
    assert nonlinear["spearman_rho"] == pytest.approx(1)


def test_empty_region_zero_agreement_never_enters_primary_domain():
    x, y = [0.0] * 16, [0.0] * 16
    x[0:4], y[0:4] = [1, 2, 3, 4], [4, 3, 2, 1]
    result = spatial.compare_regions(x, y, [0, 1, 2, 3])
    assert result["primary"]["pearson_r"] == pytest.approx(-1)
    assert result["primary"]["spearman_rho"] == pytest.approx(-1)
    assert result["primary"]["n_bins"] == 4
    assert len(result["activity_vector"]) == 16


def test_hotspot_cutoff_ties_use_stable_bin_order_and_spearman_average_ranks():
    x = [3, 3, 2, 2, 1, 1] + [0] * 10
    y = [3, 2, 3, 2, 1, 1] + [0] * 10
    result = spatial.compare_regions(x, y, [5, 4, 3, 2, 1, 0])["primary"]
    assert result["hotspot_k"] == 2
    assert result["activity_hotspot_bins"] == [0, 1]
    assert result["physical_hotspot_bins"] == [0, 2]
    assert result["hotspot_iou"] == pytest.approx(1 / 3)
    assert result["spearman_rho"] == pytest.approx(0.75)
    # Explicit ties at a cutoff choose the lowest bin ID, not list order.
    tied = spatial.compare_regions([4, 3, 3, 3] + [0] * 12, [4, 3, 3, 3] + [0] * 12,
                                   [3, 2, 1, 0])["primary"]
    assert tied["activity_hotspot_bins"] == [0]


def test_full_8x8_has_sixteen_top_quartile_bins():
    result = spatial.compare_regions(list(range(64)), list(range(64)), range(64))["primary"]
    assert result["hotspot_k"] == 16
    assert result["activity_hotspot_bins"] == list(range(63, 47, -1))


def test_missing_constant_and_small_vectors_stay_unavailable_with_reasons():
    x = list(range(16))
    y = list(x)
    y[1] = None
    missing = spatial.compare_regions(x, y, range(16))
    assert missing["primary"]["reason"] == "missing_occupied_domain_measurements"
    assert missing["primary"]["pearson_r"] is None
    assert missing["missing_domain_bins"] == [1]
    assert missing["diagnostic_pairwise_finite"]["n_bins"] == 15
    assert missing["diagnostic_pairwise_finite"]["pearson_r"] == pytest.approx(1)
    constant = spatial.compare_regions([0] * 16, x, range(16))["primary"]
    assert constant["reason"] == "constant_vector"
    assert constant["hotspot_iou"] is None
    assert spatial.compare_regions(x, x, [0, 1])["primary"]["reason"] == "fewer_than_three_bins"
    assert spatial.compare_regions(x, x, [])["primary"]["n_bins"] == 0


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, True])
def test_invalid_numbers_are_not_dropped_or_imputed(bad):
    with pytest.raises(ValueError, match="Invalid"):
        spatial.compare_regions([bad] + [1] * 15, list(range(16)), range(16))


def test_duplicates_and_unknown_units_fail_closed():
    point = dict(id="same", x_um=0, y_um=0, value=0)
    with pytest.raises(ValueError, match="Duplicate"):
        spatial.aggregate_points([point, point], BOUNDS, 4, reduction="sum", unit="W")
    with pytest.raises(ValueError, match="Registered aggregation"):
        spatial.aggregate_points([point], BOUNDS, 4, reduction="sum", unit="mW")
    with pytest.raises(ValueError, match="Duplicate domain"):
        spatial.compare_regions(list(range(16)), list(range(16)), [0, 0, 1, 2])
    with pytest.raises(ValueError, match="Invalid domain"):
        spatial.compare_regions(list(range(16)), list(range(16)), [True])


def test_current_density_requires_cross_section_and_keeps_units_explicit():
    result = spatial.current_density(-0.02, 2, 0.5)
    assert result["density_a_per_um2"] == pytest.approx(0.02)
    assert result["density_a_per_cm2"] == pytest.approx(2e6)
    assert spatial.current_density(0.02, None, None)["status"] == "NOT_EVALUATED"
    with pytest.raises(ValueError, match="Positive metal"):
        spatial.current_density(0.02, 0, 1)


def test_finite_extreme_scale_correlation_is_stable():
    x = [1e300 * (index + 1) for index in range(16)]
    result = spatial.compare_regions(x, x, range(16))["primary"]
    assert math.isfinite(result["pearson_r"])
    assert result["pearson_r"] == pytest.approx(1)
    tiny = spatial.compare_regions([1e-300 * (index + 1) for index in range(16)],
                                   list(range(16)), range(16))["primary"]
    assert tiny["pearson_r"] == pytest.approx(1)


def test_power_component_normalization_retains_dynamic_and_source_total():
    rows = [dict(instance="u1", x_um="2", y_um="3", internal_w="0.001", switching_w="0.002",
                 leakage_w="0.00001", total_w="0.00302")]
    points = spatial.power_points(rows)
    assert points["dynamic_w"][0] == dict(id="u1", x_um=2, y_um=3, value=pytest.approx(0.003))
    assert points["total_w"][0]["value"] == pytest.approx(0.00302)
    rows[0]["internal_w"] = ""
    assert spatial.power_points(rows)["dynamic_w"][0]["value"] is None
    assert spatial.power_points(rows)["switching_w"][0]["value"] == 0.002


def test_ir_terminal_adapter_uses_source_origin_not_terminal_position():
    rows = [{"Instance": "u1", "Terminal": "VDD", "Layer": "metal1", "X location": "12",
             "Y location": "25", "Voltage": "1.08"}]
    instances = [dict(id="u1", x_um=2, y_um=3)]
    points = spatial.ir_terminal_points(rows, instances, supply_voltage_v=1.1)
    assert points[0]["value"] == pytest.approx(0.02)
    assert points[0]["terminal_x_um"] == 12
    assert points[0]["terminal_y_um"] == 25
    result = spatial.aggregate_points(points, BOUNDS, 4, reduction="maximum", unit="V")
    assert result["values"][0] == pytest.approx(0.02)
    assert result["values"][9] is None
    with pytest.raises(ValueError, match="Duplicate observation"):
        spatial.ir_terminal_points(rows + rows, instances, supply_voltage_v=1.1)
    rows[0]["Voltage"] = "1.2"
    with pytest.raises(ValueError, match="exceeds registered supply"):
        spatial.ir_terminal_points(rows, instances, supply_voltage_v=1.1)
