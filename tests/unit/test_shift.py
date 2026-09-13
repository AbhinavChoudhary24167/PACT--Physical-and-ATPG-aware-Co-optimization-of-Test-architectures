from __future__ import annotations

from pact.scan.model import ScanArchitecture, ScanCell, ScanChain
from pact.test.shift_simulator import simulate_shift
from pact.test.activity_metrics import activity_metrics


def arch(names: str) -> ScanArchitecture:
    return ScanArchitecture(tuple(ScanCell(n, i, 0, "clk") for i, n in enumerate(names)), (ScanChain("c", tuple(names)),))


def test_shift_two_cell_manual() -> None:
    trace = simulate_shift(arch("ab"), [{"a": 1, "b": 0}])
    assert [c.after for c in trace.cycles] == [{"a": 0, "b": 0}, {"a": 1, "b": 0}]
    assert activity_metrics(trace)["total_shift_toggles"] == 1


def test_shift_three_cell_manual() -> None:
    trace = simulate_shift(arch("abc"), [{"a": 1, "b": 0, "c": 1}])
    assert [c.after for c in trace.cycles] == [
        {"a": 1, "b": 0, "c": 0},
        {"a": 0, "b": 1, "c": 0},
        {"a": 1, "b": 0, "c": 1},
    ]
    assert activity_metrics(trace)["total_shift_toggles"] == 6


def test_shift_four_cell_manual() -> None:
    trace = simulate_shift(arch("abcd"), [{"a": 1, "b": 0, "c": 0, "d": 0}])
    assert activity_metrics(trace)["total_shift_toggles"] == 1


def test_shift_pattern_transition() -> None:
    trace = simulate_shift(arch("ab"), [{"a": 1, "b": 0}, {"a": 0, "b": 1}])
    assert trace.cycles[-2].before == {"a": 1, "b": 0}
    assert trace.cycles[-1].after == {"a": 0, "b": 1}


def test_total_toggle_count() -> None:
    trace = simulate_shift(arch("abc"), [{"a": 1, "b": 0, "c": 1}])
    assert activity_metrics(trace)["total_shift_toggles"] == sum(sum(c.toggles.values()) for c in trace.cycles)


def test_peak_toggle_count() -> None:
    trace = simulate_shift(arch("abc"), [{"a": 1, "b": 0, "c": 1}])
    assert activity_metrics(trace)["peak_simultaneous_toggles"] == 3
