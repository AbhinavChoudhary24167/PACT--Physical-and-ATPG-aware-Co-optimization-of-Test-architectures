from pathlib import Path
import sys

from pact.phase0d.external import extract_structured_metrics, run_bounded


def test_bounded_command_is_resumable(tmp_path: Path) -> None:
    output = tmp_path / "made.txt"
    command = [sys.executable, "-c", f"from pathlib import Path; Path({str(output)!r}).write_text('ok')"]
    first = run_bounded(command, tmp_path / "run", tmp_path, 5, [output])
    assert first["exit_code"] == 0 and first["required_outputs_present"]
    second = run_bounded(command, tmp_path / "run", tmp_path, 5, [output])
    assert second["resumed_valid_result"] is True


def test_strict_route_metric_extraction() -> None:
    grt = {
        "globalroute__timing__setup__ws": 1.0,
        "globalroute__timing__setup__tns": 0.0,
        "globalroute__timing__hold__ws": 0.5,
        "globalroute__timing__hold__tns": 0.0,
        "globalroute__timing__drv__setup_violation_count": 0,
        "globalroute__timing__drv__hold_violation_count": 0,
        "globalroute__timing__drv__max_slew": 0,
        "globalroute__timing__drv__max_cap": 0,
        "globalroute__timing__drv__max_fanout": 0,
        "globalroute__global_route__wirelength": 100,
        "globalroute__global_route__overflow": 0,
    }
    drt = {
        "detailedroute__route__wirelength": 120,
        "detailedroute__route__drc_errors": 0,
        "detailedroute__route__vias": 42,
    }
    result = extract_structured_metrics(grt, drt)
    assert result["total_detailed_route_wirelength_um"] == 120
    assert result["detailed_route_drc_errors"] == 0
    assert result["detailed_route_vias"] == 42
