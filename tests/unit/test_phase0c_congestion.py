from pact.physical.phase0c_congestion import parse_grt_congestion


def test_parse_saved_global_route_congestion_table():
    stdout = """[INFO GRT-0096] Final congestion report:
Layer Resource Demand Usage (%) Max H / Max V / Total Overflow
---------------------------------------------------------------
metal2 100 60 60.00% 0 / 1 / 2
metal3 50 30 60.00% 0 / 0 / 0
---------------------------------------------------------------
Total 150 90 60.00% 0 / 1 / 2
"""
    result = parse_grt_congestion(stdout)
    assert result["total"]["total_overflow"] == 2
    assert result["layers"]["metal2"]["usage_percent"] == 60.0
    assert result["stage"] == "initial_global_route_before_incremental_repairs"


def test_missing_congestion_report_is_unavailable():
    assert parse_grt_congestion("[INFO GRT-0018] Total wirelength: 10 um") is None
